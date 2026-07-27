from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys
from typing import Any

from PIL import Image
import torch
from torch import nn
import torch.nn.functional as F
from torchvision import transforms


BIOVILT_HUB_REVISION = "692f09e9be1bfe5fdd5f3efdd0e1eca7d2c10b23"
HI_ML_REVISION = "b67c1d27c6b17d8e8ff01f8c507f3cabdb307388"
BIOVILT_FEATURE_DIM = 128
BIOVILT_RESIZE = 512
BIOVILT_CROP = 448
R37_FINDING_COUNT = 12
BIOVILT_CONTROL_MODES = ("true_pair", "current_only", "inverted")


class ExpandGrayscaleChannels:
    def __call__(self, value: torch.Tensor) -> torch.Tensor:
        if value.ndim != 3 or value.shape[0] != 1:
            raise ValueError(
                f"expected grayscale [1, H, W] tensor, got {tuple(value.shape)}"
            )
        return value.repeat(3, 1, 1)


def official_biovilt_transform() -> transforms.Compose:
    return transforms.Compose(
        (
            transforms.Resize(BIOVILT_RESIZE),
            transforms.CenterCrop(BIOVILT_CROP),
            transforms.ToTensor(),
            ExpandGrayscaleChannels(),
        )
    )


def load_biovilt_image(path: str | Path) -> torch.Tensor:
    with Image.open(path) as image:
        return official_biovilt_transform()(image.convert("L"))


def _official_modules(source_root: Path) -> tuple[Any, Any]:
    source_root = source_root.resolve()
    package_root = source_root / "health_multimodal"
    if not (package_root / "image" / "model" / "model.py").is_file():
        raise FileNotFoundError(
            f"HI-ML source root is missing health_multimodal: {source_root}"
        )
    source_text = str(source_root)
    sys.path.insert(0, source_text)
    try:
        model_module = importlib.import_module(
            "health_multimodal.image.model.model"
        )
        types_module = importlib.import_module(
            "health_multimodal.image.model.types"
        )
    finally:
        if sys.path and sys.path[0] == source_text:
            sys.path.pop(0)
    for module in (model_module, types_module):
        module_path = Path(module.__file__).resolve()
        if not module_path.is_relative_to(source_root):
            raise RuntimeError(
                f"health_multimodal resolved outside pinned source: {module_path}"
            )
    return model_module.MultiImageModel, types_module.ImageEncoderType


def load_frozen_biovilt(
    checkpoint: str | Path,
    source_root: str | Path,
    device: torch.device,
) -> nn.Module:
    checkpoint = Path(checkpoint)
    if not checkpoint.is_file():
        raise FileNotFoundError(f"BioViL-T checkpoint not found: {checkpoint}")
    MultiImageModel, ImageEncoderType = _official_modules(Path(source_root))
    model = MultiImageModel(
        img_encoder_type=ImageEncoderType.RESNET50_MULTI_IMAGE,
        joint_feature_size=BIOVILT_FEATURE_DIM,
    )
    state = torch.load(checkpoint, map_location="cpu", weights_only=True)
    loaded = model.load_state_dict(state, strict=True)
    if loaded.missing_keys or loaded.unexpected_keys:
        raise RuntimeError(
            "strict BioViL-T load mismatch: "
            f"{loaded.missing_keys}, {loaded.unexpected_keys}"
        )
    model.eval().requires_grad_(False).to(device)
    if model.training or any(
        parameter.requires_grad for parameter in model.parameters()
    ):
        raise RuntimeError("BioViL-T freeze audit failed")
    return model


@torch.no_grad()
def canonical_pair_embedding(
    model: nn.Module,
    *,
    current_image: torch.Tensor,
    prior_image: torch.Tensor | None,
) -> torch.Tensor:
    outputs = model(
        current_image=current_image,
        previous_image=prior_image,
    )
    embeddings = outputs.projected_global_embedding
    if embeddings.ndim != 2 or embeddings.shape[1] != BIOVILT_FEATURE_DIM:
        raise ValueError(
            "unexpected BioViL-T projected embedding shape: "
            f"{tuple(embeddings.shape)}"
        )
    embeddings = F.normalize(embeddings.float(), dim=-1)
    if not torch.isfinite(embeddings).all():
        raise ValueError("BioViL-T projected embeddings contain nonfinite values")
    return embeddings


class FindingConditionedLinearProbe(nn.Module):
    def __init__(
        self,
        *,
        finding_count: int = R37_FINDING_COUNT,
        class_count: int = 5,
    ) -> None:
        super().__init__()
        if finding_count <= 0 or class_count <= 1:
            raise ValueError("invalid finding or class count")
        self.finding_count = finding_count
        self.classifier = nn.Linear(
            BIOVILT_FEATURE_DIM + finding_count, class_count
        )

    def forward(
        self, embeddings: torch.Tensor, finding_indices: torch.Tensor
    ) -> torch.Tensor:
        if embeddings.ndim != 2 or embeddings.shape[1] != BIOVILT_FEATURE_DIM:
            raise ValueError("unexpected BioViL-T probe embedding shape")
        one_hot = F.one_hot(
            finding_indices, num_classes=self.finding_count
        ).to(dtype=embeddings.dtype)
        return self.classifier(torch.cat((embeddings, one_hot), dim=-1))


class BioViLTControlCacheIndex:
    def __init__(
        self, root: str | Path, *, maximum_loaded_shards: int = 4
    ) -> None:
        self.root = Path(root)
        if maximum_loaded_shards <= 0:
            raise ValueError("maximum loaded shards must be positive")
        self.maximum_loaded_shards = maximum_loaded_shards
        manifest_path = self.root / "r37_biovilt_pair_cache_manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"A1 cache manifest missing: {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") not in {
            "PASS_R37_A1_CONTROL_CACHE",
            "PASS_R37_A1_CONTROL_CACHE_MERGED",
        }:
            raise ValueError("A1 cache gate has not passed")
        controls = tuple(manifest.get("controls", ()))
        if controls != BIOVILT_CONTROL_MODES:
            raise ValueError(f"A1 control-mode drift: {controls}")
        if "parts" in manifest:
            part_roots = [
                self.root / str(part["directory"])
                for part in manifest["parts"]
            ]
        else:
            part_roots = [self.root]

        self.locations: dict[str, tuple[Path, int]] = {}
        for part_root in part_roots:
            part_manifest = json.loads(
                (
                    part_root / "r37_biovilt_pair_cache_manifest.json"
                ).read_text(encoding="utf-8")
            )
            for shard in part_manifest["shards"]:
                shard_path = part_root / str(shard["file"])
                payload = torch.load(
                    shard_path, map_location="cpu", weights_only=True
                )
                pair_ids = [str(value) for value in payload["pair_ids"]]
                if len(pair_ids) != int(shard["count"]):
                    raise ValueError(f"A1 shard count drift: {shard_path}")
                for index, pair_id in enumerate(pair_ids):
                    if pair_id in self.locations:
                        raise ValueError(f"duplicate A1 pair ID: {pair_id}")
                    self.locations[pair_id] = (shard_path, index)
        if len(self.locations) != int(manifest["pair_count"]):
            raise ValueError("A1 merged pair count drift")
        self._loaded: dict[Path, dict[str, torch.Tensor]] = {}
        self._order: list[Path] = []

    def _load(self, path: Path) -> dict[str, torch.Tensor]:
        if path in self._loaded:
            self._order.remove(path)
            self._order.append(path)
            return self._loaded[path]
        payload = torch.load(path, map_location="cpu", weights_only=True)
        embeddings = payload["embeddings"]
        if tuple(embeddings) != BIOVILT_CONTROL_MODES:
            raise ValueError(f"A1 shard control drift: {path}")
        self._loaded[path] = embeddings
        self._order.append(path)
        while len(self._order) > self.maximum_loaded_shards:
            evicted = self._order.pop(0)
            del self._loaded[evicted]
        return embeddings

    def get_many(
        self, pair_ids: Any, *, mode: str
    ) -> torch.Tensor:
        if mode not in BIOVILT_CONTROL_MODES:
            raise ValueError(f"unknown A1 control mode: {mode}")
        values = []
        for pair_id in pair_ids:
            key = str(pair_id)
            if key not in self.locations:
                raise KeyError(f"A1 pair absent from cache: {key}")
            path, index = self.locations[key]
            values.append(self._load(path)[mode][index])
        return torch.stack(values)
