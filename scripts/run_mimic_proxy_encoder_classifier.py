from __future__ import annotations

# ruff: noqa: E402

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))

import pandas as pd
from PIL import Image
import timm
import torch
from torch import nn
from torchvision import transforms

from visualvit.metrics import macro_f1
from visualvit.audit import training_convergence_pass

EVIDENCE_CLASS = "NON_CONFIRMATORY_PROXY"
CLIP_MEAN = (0.48145466, 0.4578275, 0.40821073)
CLIP_STD = (0.26862954, 0.26130258, 0.27577711)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def set_determinism(seed: int) -> None:
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)


class ProxyClassifier(nn.Module):
    def __init__(self, input_dim: int) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.LayerNorm(input_dim),
            nn.Linear(input_dim, 64),
            nn.GELU(),
            nn.Linear(64, 3),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)


def load_encoder(weights: Path, device: torch.device) -> nn.Module:
    checkpoint = torch.load(weights, map_location="cpu", weights_only=True)
    state = checkpoint.get("model", checkpoint)
    model = timm.create_model(
        "vit_base_patch16_224", pretrained=False, num_classes=0
    )
    result = model.load_state_dict(state, strict=True)
    if result.missing_keys or result.unexpected_keys:
        raise RuntimeError("strict encoder load failed")
    return model.eval().to(device)


def extract_features(
    paths: list[str],
    model: nn.Module,
    device: torch.device,
    batch_size: int,
) -> tuple[dict[str, torch.Tensor], float, int]:
    preprocessing = transforms.Compose(
        [
            transforms.Resize((224, 224), antialias=True),
            transforms.ToTensor(),
            transforms.Normalize(CLIP_MEAN, CLIP_STD),
        ]
    )
    cache: dict[str, torch.Tensor] = {}
    start = time.perf_counter()
    torch.cuda.reset_peak_memory_stats(device)
    with torch.inference_mode():
        for start_index in range(0, len(paths), batch_size):
            batch_paths = paths[start_index : start_index + batch_size]
            images = torch.stack(
                [
                    preprocessing(Image.open(path).convert("RGB"))
                    for path in batch_paths
                ]
            ).to(device)
            features = model.forward_features(images)[:, 0].detach().cpu()
            if not torch.isfinite(features).all():
                raise ValueError("non-finite proxy encoder features")
            for path, feature in zip(batch_paths, features):
                cache[path] = feature
    torch.cuda.synchronize(device)
    return (
        cache,
        time.perf_counter() - start,
        int(torch.cuda.max_memory_allocated(device)),
    )


def derange_indices(frame: pd.DataFrame, seed: int) -> torch.Tensor:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    result = torch.arange(len(frame), dtype=torch.long)
    for _, group in frame.groupby("view", sort=True):
        indices = torch.tensor(group.index.to_list(), dtype=torch.long)
        if len(indices) < 2:
            raise ValueError("view group too small for derangement")
        base = torch.arange(len(indices))
        permutation = None
        for _ in range(128):
            candidate = torch.randperm(len(indices), generator=generator)
            if bool((candidate != base).all()):
                permutation = candidate
                break
        if permutation is None:
            permutation = torch.roll(base, shifts=1)
        result[indices] = indices[permutation]
    if bool((result == torch.arange(len(frame))).any()):
        raise ValueError("derangement contains fixed points")
    return result


def relation_features(prior: torch.Tensor, current: torch.Tensor) -> torch.Tensor:
    return torch.cat((prior, current, current - prior, (current - prior).abs()), dim=-1)


def train_variant(
    x_train: torch.Tensor,
    y_train: torch.Tensor,
    x_dev: torch.Tensor,
    y_dev: torch.Tensor,
    seed: int,
    steps: int,
    learning_rate: float,
    device: torch.device,
) -> dict[str, Any]:
    set_determinism(seed)
    model = ProxyClassifier(x_train.shape[-1]).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=learning_rate, weight_decay=1e-4
    )
    x_train = x_train.to(device)
    y_train = y_train.to(device)
    x_dev = x_dev.to(device)
    y_dev = y_dev.to(device)
    start = time.perf_counter()
    final_loss = float("nan")
    for _ in range(steps):
        optimizer.zero_grad(set_to_none=True)
        logits = model(x_train)
        loss = nn.functional.cross_entropy(logits, y_train)
        loss.backward()
        optimizer.step()
        final_loss = float(loss.detach().cpu())
    torch.cuda.synchronize(device)
    runtime = time.perf_counter() - start
    with torch.inference_mode():
        train_pred = model(x_train).argmax(-1)
        dev_pred = model(x_dev).argmax(-1)
    return {
        "train_macro_f1": macro_f1(train_pred, y_train, 3),
        "dev_macro_f1": macro_f1(dev_pred, y_dev, 3),
        "final_loss": final_loss,
        "runtime_seconds": runtime,
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
    }


def row_multiset_hash(tensor: torch.Tensor) -> str:
    row_hashes = []
    for row in tensor.detach().cpu().contiguous():
        row_hashes.append(hashlib.sha256(row.numpy().tobytes()).hexdigest())
    payload = "\n".join(sorted(row_hashes)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--weights",
        type=Path,
        default=Path(
            r"H:\Xiyao_Wang\021_260129VIVID\pretrained\biomedclip_vit_base.pt"
        ),
    )
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--learning-rate", type=float, default=0.01)
    parser.add_argument("--seeds", type=int, nargs="+", default=[17, 29, 43])
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(r"F:\VisualVIT_runtime\050_routeC\runs"),
    )
    parser.add_argument("--run-id", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    frame = pd.read_csv(args.manifest)
    required = {
        "proxy_id",
        "proxy_split",
        "proxy_label",
        "label_id",
        "subject_id",
        "view",
        "prior_path",
        "current_path",
        "official_split",
        "evidence_class",
    }
    if not required.issubset(frame.columns):
        raise ValueError(f"manifest missing columns: {required - set(frame.columns)}")
    if set(frame["official_split"]) != {"train"}:
        raise ValueError("official validate/test entered proxy run")
    if set(frame["evidence_class"]) != {EVIDENCE_CLASS}:
        raise ValueError("evidence class mismatch")
    if frame["subject_id"].nunique() != len(frame):
        raise ValueError("patient appears more than once")
    train_subjects = set(frame.loc[frame["proxy_split"] == "train", "subject_id"])
    dev_subjects = set(frame.loc[frame["proxy_split"] == "dev", "subject_id"])
    if train_subjects & dev_subjects:
        raise ValueError("patient leakage between proxy train/dev")

    device = torch.device(args.device)
    torch.cuda.set_device(device)
    torch.empty(1, device=device)
    run_id = args.run_id or (
        "mimic_proxy_classifier_" + datetime.now().strftime("%Y%m%dT%H%M%S")
    )
    run_dir = args.output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    model = load_encoder(args.weights, device)
    unique_paths = sorted(
        set(frame["prior_path"].tolist()) | set(frame["current_path"].tolist())
    )
    feature_cache, extraction_seconds, peak_encoder_vram = extract_features(
        unique_paths, model, device, args.batch_size
    )
    cache_path = run_dir / "biomedclip_cls_features.pt"
    torch.save(
        {
            "evidence_class": EVIDENCE_CLASS,
            "encoder_weight_sha256": sha256_file(args.weights),
            "features": feature_cache,
        },
        cache_path,
    )
    del model
    torch.cuda.empty_cache()

    prior = torch.stack([feature_cache[path] for path in frame["prior_path"]])
    current = torch.stack([feature_cache[path] for path in frame["current_path"]])
    labels = torch.tensor(frame["label_id"].to_numpy(), dtype=torch.long)

    per_seed: list[dict[str, Any]] = []
    for seed in args.seeds:
        seed_results: dict[str, Any] = {"seed": seed}
        variant_data = {}
        audits = {}
        for split_name, split_frame in frame.groupby("proxy_split", sort=False):
            split_frame = split_frame.reset_index()
            indices = torch.tensor(split_frame["index"].to_numpy(), dtype=torch.long)
            split_prior = prior[indices]
            split_current = current[indices]
            permutation = derange_indices(
                split_frame.reset_index(drop=True),
                seed + (10_000 if split_name == "dev" else 0),
            )
            deranged_current = split_current[permutation]
            variant_data[split_name] = {
                "labels": labels[indices],
                "current_only": split_current,
                "correct_pair": relation_features(split_prior, split_current),
                "deranged_pair": relation_features(split_prior, deranged_current),
            }
            audits[split_name] = {
                "fixed_point_rate": float(
                    (permutation == torch.arange(len(permutation))).float().mean()
                ),
                "current_feature_multiset_equal": (
                    row_multiset_hash(split_current)
                    == row_multiset_hash(deranged_current)
                ),
                "prior_features_unchanged": True,
                "labels_unchanged": True,
                "view_compatible": all(
                    split_frame.loc[index, "view"]
                    == split_frame.loc[int(permutation[index]), "view"]
                    for index in range(len(split_frame))
                ),
            }

        results = {}
        for variant in ("current_only", "correct_pair", "deranged_pair"):
            results[variant] = train_variant(
                variant_data["train"][variant],
                variant_data["train"]["labels"],
                variant_data["dev"][variant],
                variant_data["dev"]["labels"],
                seed=seed,
                steps=args.steps,
                learning_rate=args.learning_rate,
                device=device,
            )
        seed_results["variants"] = results
        seed_results["assignment_only_audit"] = audits
        seed_results["correct_minus_deranged_pp"] = 100.0 * (
            results["correct_pair"]["dev_macro_f1"]
            - results["deranged_pair"]["dev_macro_f1"]
        )
        assignment_audit_pass = all(
            audit["fixed_point_rate"] == 0.0
            and audit["current_feature_multiset_equal"]
            and audit["view_compatible"]
            for audit in audits.values()
        )
        convergence_gate = {
            variant: training_convergence_pass(results[variant])
            for variant in ("correct_pair", "deranged_pair")
        }
        seed_results["assignment_audit_pass"] = assignment_audit_pass
        seed_results["convergence_gate"] = convergence_gate
        seed_results["pass"] = bool(
            assignment_audit_pass and all(convergence_gate.values())
        )
        per_seed.append(seed_results)

    per_seed_path = run_dir / "per_seed.jsonl"
    with per_seed_path.open("w", encoding="utf-8") as handle:
        for row in per_seed:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    metric_extractors = {
        "current_only_dev_macro_f1": lambda row: row["variants"]["current_only"][
            "dev_macro_f1"
        ],
        "correct_pair_dev_macro_f1": lambda row: row["variants"]["correct_pair"][
            "dev_macro_f1"
        ],
        "deranged_pair_dev_macro_f1": lambda row: row["variants"][
            "deranged_pair"
        ]["dev_macro_f1"],
        "correct_minus_deranged_pp": lambda row: row[
            "correct_minus_deranged_pp"
        ],
    }
    aggregate = {}
    for name, getter in metric_extractors.items():
        values = [float(getter(row)) for row in per_seed]
        aggregate[name] = {
            "values": values,
            "mean": statistics.fmean(values),
            "sample_std": statistics.stdev(values) if len(values) > 1 else 0.0,
        }

    all_seeds_pass = all(row["pass"] for row in per_seed)
    summary = {
        "evidence_class": EVIDENCE_CLASS,
        "formal_claim_allowed": False,
        "status": "PASS" if all_seeds_pass else "FAIL_CONVERGENCE_GATE",
        "run_id": run_id,
        "manifest": {
            "path": str(args.manifest),
            "sha256": sha256_file(args.manifest),
            "rows": len(frame),
            "train_rows": int((frame["proxy_split"] == "train").sum()),
            "dev_rows": int((frame["proxy_split"] == "dev").sum()),
            "unique_patients": int(frame["subject_id"].nunique()),
        },
        "encoder": {
            "weights": str(args.weights),
            "weights_sha256": sha256_file(args.weights),
            "feature_dim": int(prior.shape[-1]),
            "unique_images": len(unique_paths),
            "extraction_seconds": extraction_seconds,
            "peak_vram_bytes": peak_encoder_vram,
        },
        "aggregate": aggregate,
        "config": {
            "device": str(device),
            "batch_size": args.batch_size,
            "steps": args.steps,
            "learning_rate": args.learning_rate,
            "seeds": args.seeds,
            "classifier": "LayerNorm-Linear64-GELU-Linear3",
            "optimizer": "AdamW",
            "weight_decay": 1e-4,
            "convergence_gate": {
                "train_macro_f1_min": 0.95,
                "final_loss_max": 0.20,
                "required_variants": ["correct_pair", "deranged_pair"],
            },
        },
        "aggregate_interpretation_valid": all_seeds_pass,
        "aggregate_interpretation": (
            "DESCRIPTIVE_ONLY_PASSING_CONVERGENCE_GATE"
            if all_seeds_pass
            else "INVALID_FOR_PAIRING_EFFECT_INTERPRETATION"
        ),
        "interpretation_boundary": (
            "This study-level report-derived proxy tests longitudinal pipeline "
            "mechanics only. It is not entity binding, B4 oracle, clinical, or "
            "frozen-VLM evidence."
        ),
        "artifacts": {
            cache_path.name: {
                "sha256": sha256_file(cache_path),
                "bytes": cache_path.stat().st_size,
            },
            per_seed_path.name: {
                "sha256": sha256_file(per_seed_path),
                "bytes": per_seed_path.stat().st_size,
            },
        },
    }
    summary_path = run_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))
    print(f"RESULT_DIR={run_dir}")
    return 0 if summary["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
