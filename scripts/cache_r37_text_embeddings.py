from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import torch


BIOMEDCLIP_ROOT = Path(r"H:\Xiyao_Wang\001_models\biomedclip")
OUTPUT = Path(
    r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr"
    r"\r37_biomedclip_text_embeddings.pt"
)
FINDINGS = (
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Enlarged Cardiomediastinum",
    "Fracture",
    "Lung Lesion",
    "Lung Opacity",
    "Pleural Effusion",
    "Pleural Other",
    "Pneumonia",
    "Pneumothorax",
)
LABEL_PHRASES = {
    "Stable": "is unchanged",
    "Improved": "has improved",
    "Worse": "has worsened",
    "New": "is new",
    "Resolved": "has resolved",
}


def build_text_encoder():
    from open_clip.model import CLIPTextCfg, CLIPVisionCfg, CustomTextCLIP

    config = json.loads(
        (BIOMEDCLIP_ROOT / "open_clip_config.json").read_text(encoding="utf-8")
    )["model_cfg"]
    text_config = dict(config["text_cfg"])
    text_config["hf_model_pretrained"] = False
    model = CustomTextCLIP(
        embed_dim=int(config["embed_dim"]),
        vision_cfg=CLIPVisionCfg(**config["vision_cfg"]),
        text_cfg=CLIPTextCfg(**text_config),
    )
    state = torch.load(
        BIOMEDCLIP_ROOT / "open_clip_pytorch_model.bin",
        map_location="cpu",
        weights_only=True,
    )
    state.pop("text.transformer.embeddings.position_ids", None)
    loaded = model.load_state_dict(state, strict=True)
    if loaded.missing_keys or loaded.unexpected_keys:
        raise RuntimeError("BiomedCLIP strict text load failed")
    return model.eval().requires_grad_(False)


def encode_texts(model, texts: Iterable[str]) -> torch.Tensor:
    from transformers import AutoTokenizer

    values = list(texts)
    tokenizer = AutoTokenizer.from_pretrained(
        BIOMEDCLIP_ROOT, local_files_only=True
    )
    encoded = tokenizer(
        values,
        padding="max_length",
        truncation=True,
        max_length=256,
        return_tensors="pt",
    )["input_ids"]
    with torch.inference_mode():
        result = model.encode_text(encoded, normalize=True).cpu()
    if tuple(result.shape) != (len(values), 512):
        raise RuntimeError(f"unexpected text shape: {tuple(result.shape)}")
    if not bool(torch.isfinite(result).all()):
        raise RuntimeError("text embeddings contain non-finite values")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cache frozen BiomedCLIP finding/transition text prototypes"
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"text cache output must be fresh: {args.output}")
    model = build_text_encoder()
    finding_prompts = [f"chest x-ray finding: {finding}" for finding in FINDINGS]
    transition_prompts = [
        f"{finding} {phrase}"
        for finding in FINDINGS
        for phrase in LABEL_PHRASES.values()
    ]
    finding_embeddings = encode_texts(model, finding_prompts)
    transition_embeddings = encode_texts(model, transition_prompts)
    payload = {
        "schema": "visualvit.r37.biomedclip-text-prototypes.v1",
        "status": "PASS_R37_TEXT_PROTOTYPES",
        "encoder": "BiomedCLIP frozen text tower",
        "findings": list(FINDINGS),
        "labels": list(LABEL_PHRASES),
        "finding_prompts": finding_prompts,
        "transition_prompts": transition_prompts,
        "finding_embeddings": finding_embeddings,
        "transition_embeddings": transition_embeddings,
        "shape": {
            "finding_embeddings": list(finding_embeddings.shape),
            "transition_embeddings": list(transition_embeddings.shape),
        },
        "protected_outcomes_read": False,
        "source_hashes_recomputed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, args.output)
    print(
        json.dumps(
            {
                key: value
                for key, value in payload.items()
                if not key.endswith("_embeddings")
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(f"RESULT={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
