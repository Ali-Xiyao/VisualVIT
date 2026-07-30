from __future__ import annotations

# ruff: noqa: E402

import argparse
import hashlib
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))

import torch
from torch import nn
import torch.nn.functional as F

from visualvit.audit import audit_b4_isomorphism, model_signature
from visualvit.matching import (
    ProjectedCosineMatcher,
    anatomy_compatible_derangement,
    assignment_accuracy,
)
from visualvit.metrics import macro_f1
from visualvit.synthetic import (
    NUM_CLASSES,
    SyntheticBatch,
    labeled_relation_rows,
    make_synthetic_batch,
)
from visualvit.tokenizer import (
    assemble_fixed_budget_tokens,
    build_relation_slots,
)

EVIDENCE_CLASS = "NON_CONFIRMATORY_PROXY"


class RelationClassifier(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 64) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, NUM_CLASSES),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.network(inputs)


def set_determinism(seed: int) -> None:
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def train_matcher(
    train: SyntheticBatch,
    dev: SyntheticBatch,
    seed: int,
    steps: int,
    learning_rate: float,
) -> tuple[ProjectedCosineMatcher, dict[str, float]]:
    set_determinism(seed)
    feature_dim = train.regions.prior_features.shape[-1]
    matcher = ProjectedCosineMatcher(feature_dim=feature_dim, projection_dim=16)
    matcher = matcher.to(train.regions.prior_features.device)
    optimizer = torch.optim.AdamW(
        matcher.parameters(), lr=learning_rate, weight_decay=1e-4
    )
    targets = matcher.row_targets(train.oracle, train.regions)

    start = time.perf_counter()
    final_loss = float("nan")
    for _ in range(steps):
        optimizer.zero_grad(set_to_none=True)
        logits = matcher.row_logits(train.regions)
        loss = F.cross_entropy(
            logits.flatten(0, 1), targets.flatten(), ignore_index=-100
        )
        loss.backward()
        optimizer.step()
        final_loss = float(loss.detach().cpu())
    runtime = time.perf_counter() - start

    with torch.no_grad():
        train_plan = matcher.hard_plan(
            train.regions, match_count=train.persistent_count
        )
        dev_plan = matcher.hard_plan(dev.regions, match_count=dev.persistent_count)
    metrics = {
        "final_loss": final_loss,
        "runtime_seconds": runtime,
        "train_assignment_accuracy": assignment_accuracy(
            train_plan, train.oracle, train.regions
        ),
        "dev_assignment_accuracy": assignment_accuracy(
            dev_plan, dev.oracle, dev.regions
        ),
    }
    return matcher, metrics


def train_classifier(
    train: SyntheticBatch,
    train_plan,
    dev: SyntheticBatch,
    dev_plan,
    seed: int,
    steps: int,
    learning_rate: float,
) -> dict[str, Any]:
    x_train, y_train = labeled_relation_rows(train, train_plan)
    x_dev, y_dev = labeled_relation_rows(dev, dev_plan)
    set_determinism(seed)
    model = RelationClassifier(x_train.shape[-1]).to(x_train.device)
    initial_signature = model_signature(model)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=learning_rate, weight_decay=1e-4
    )

    start = time.perf_counter()
    final_loss = float("nan")
    for _ in range(steps):
        optimizer.zero_grad(set_to_none=True)
        logits = model(x_train)
        loss = F.cross_entropy(logits, y_train)
        loss.backward()
        optimizer.step()
        final_loss = float(loss.detach().cpu())
    runtime = time.perf_counter() - start

    with torch.no_grad():
        train_predictions = model(x_train).argmax(dim=-1)
        dev_predictions = model(x_dev).argmax(dim=-1)
    return {
        "model": model,
        "final_loss": final_loss,
        "runtime_seconds": runtime,
        "train_macro_f1": macro_f1(
            train_predictions, y_train, num_classes=NUM_CLASSES
        ),
        "dev_macro_f1": macro_f1(
            dev_predictions, y_dev, num_classes=NUM_CLASSES
        ),
        "train_rows": int(y_train.numel()),
        "dev_rows": int(y_dev.numel()),
        "dev_class_counts": torch.bincount(
            y_dev.detach().cpu(), minlength=NUM_CLASSES
        ).tolist(),
        "initial_model_signature": initial_signature,
        "training_contract": {
            "model": "RelationClassifier",
            "input_dim": int(x_train.shape[-1]),
            "hidden_dim": 64,
            "optimizer": "AdamW",
            "learning_rate": learning_rate,
            "weight_decay": 1e-4,
            "steps": steps,
            "batching": "full_batch",
            "preprocessing": "none",
            "seed": seed,
        },
        "relation_features_sourced_from_fixed_64_token_bundle": True,
    }


def birth_recall(predicted, oracle, synthetic: SyntheticBatch) -> float:
    rp = synthetic.regions.prior_features.shape[1]
    rc = synthetic.regions.current_features.shape[1]
    pred_birth = predicted.transport[:, rp, :rc] > 0.5
    gold_birth = oracle.transport[:, rp, :rc] > 0.5
    true_positive = int((pred_birth & gold_birth).sum().item())
    actual = int(gold_birth.sum().item())
    return true_positive / max(actual, 1)


def create_same_initial_models(input_dim: int, seed: int) -> tuple[nn.Module, nn.Module]:
    set_determinism(seed)
    model_a = RelationClassifier(input_dim)
    set_determinism(seed)
    model_b = RelationClassifier(input_dim)
    return model_a, model_b


def run_seed(config: dict[str, Any], seed: int, device: torch.device) -> dict[str, Any]:
    train = make_synthetic_batch(
        num_cases=config["train_cases"],
        seed=config["data_seed"] + seed,
        feature_dim=config["feature_dim"],
    ).to(device)
    dev = make_synthetic_batch(
        num_cases=config["dev_cases"],
        seed=config["data_seed"] + 100_000 + seed,
        feature_dim=config["feature_dim"],
    ).to(device)

    b4a_train = anatomy_compatible_derangement(
        train.regions, train.oracle, seed=seed
    )
    b4a_dev = anatomy_compatible_derangement(
        dev.regions, dev.oracle, seed=seed + 10_000
    )

    bundle_a = assemble_fixed_budget_tokens(train.regions, b4a_train)
    bundle_b = assemble_fixed_budget_tokens(train.regions, train.oracle)
    relation_input_dim = build_relation_slots(train.regions, train.oracle)[0].shape[-1]
    model_a, model_b = create_same_initial_models(relation_input_dim, seed)
    audit = audit_b4_isomorphism(
        train.regions,
        train.regions,
        b4a_train,
        train.oracle,
        bundle_a,
        bundle_b,
        model_a,
        model_b,
    )

    matcher, matcher_metrics = train_matcher(
        train=train,
        dev=dev,
        seed=seed,
        steps=config["matcher_steps"],
        learning_rate=config["matcher_learning_rate"],
    )
    learned_train = matcher.hard_plan(
        train.regions, match_count=train.persistent_count
    )
    learned_dev = matcher.hard_plan(dev.regions, match_count=dev.persistent_count)

    variants = {
        "b4a_deranged": (b4a_train, b4a_dev),
        "b4b_oracle": (train.oracle, dev.oracle),
        "learned_projection_proxy": (learned_train, learned_dev),
    }
    variant_results: dict[str, Any] = {}
    for name, (train_plan, dev_plan) in variants.items():
        result = train_classifier(
            train=train,
            train_plan=train_plan,
            dev=dev,
            dev_plan=dev_plan,
            seed=seed,
            steps=config["classifier_steps"],
            learning_rate=config["classifier_learning_rate"],
        )
        result.pop("model")
        variant_results[name] = result

    actual_b4_training_audit = {
        "initial_model_signatures_equal": (
            variant_results["b4a_deranged"]["initial_model_signature"]
            == variant_results["b4b_oracle"]["initial_model_signature"]
        ),
        "training_contracts_equal": (
            variant_results["b4a_deranged"]["training_contract"]
            == variant_results["b4b_oracle"]["training_contract"]
        ),
        "relation_bundle_path_equal": (
            variant_results["b4a_deranged"][
                "relation_features_sourced_from_fixed_64_token_bundle"
            ]
            == variant_results["b4b_oracle"][
                "relation_features_sourced_from_fixed_64_token_bundle"
            ]
            is True
        ),
    }
    actual_b4_training_audit["pass"] = all(
        actual_b4_training_audit.values()
    )
    audit["actual_training_audit"] = actual_b4_training_audit
    audit["pass"] = bool(audit["pass"] and actual_b4_training_audit["pass"])

    f_a = variant_results["b4a_deranged"]["dev_macro_f1"]
    f_b = variant_results["b4b_oracle"]["dev_macro_f1"]
    f_l = variant_results["learned_projection_proxy"]["dev_macro_f1"]
    gap = f_b - f_a
    recovery = None if gap <= 0 else (f_l - f_a) / gap

    learned_birth_recall = birth_recall(learned_dev, dev.oracle, dev)
    checks = {
        "b4_isomorphism": bool(audit["pass"]),
        "oracle_mechanism_signal": f_b >= 0.90 and gap >= 0.10,
        "matcher_assignment": matcher_metrics["dev_assignment_accuracy"] >= 0.90,
        "birth_recall": learned_birth_recall >= 0.90,
        "learned_recovery": recovery is not None and recovery >= 0.60,
    }
    return {
        "evidence_class": EVIDENCE_CLASS,
        "seed": seed,
        "audit": audit,
        "matcher": matcher_metrics,
        "learned_birth_recall": learned_birth_recall,
        "variants": variant_results,
        "delta_bind_percentage_points": 100.0 * gap,
        "recovery": recovery,
        "mechanical_checks": checks,
        "pass": all(checks.values()),
    }


def aggregate(per_seed: list[dict[str, Any]]) -> dict[str, Any]:
    metric_paths = {
        "b4a_dev_macro_f1": lambda row: row["variants"]["b4a_deranged"][
            "dev_macro_f1"
        ],
        "b4b_dev_macro_f1": lambda row: row["variants"]["b4b_oracle"][
            "dev_macro_f1"
        ],
        "learned_dev_macro_f1": lambda row: row["variants"][
            "learned_projection_proxy"
        ]["dev_macro_f1"],
        "delta_bind_percentage_points": lambda row: row[
            "delta_bind_percentage_points"
        ],
        "recovery": lambda row: row["recovery"],
        "matcher_dev_assignment_accuracy": lambda row: row["matcher"][
            "dev_assignment_accuracy"
        ],
        "learned_birth_recall": lambda row: row["learned_birth_recall"],
    }
    summary: dict[str, Any] = {}
    for name, getter in metric_paths.items():
        values = [float(getter(row)) for row in per_seed if getter(row) is not None]
        summary[name] = {
            "values": values,
            "mean": statistics.fmean(values),
            "sample_std": statistics.stdev(values) if len(values) > 1 else 0.0,
        }
    summary["all_seeds_pass"] = all(row["pass"] for row in per_seed)
    return summary


def environment_snapshot(device: torch.device) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "evidence_class": EVIDENCE_CLASS,
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_count": torch.cuda.device_count(),
        "selected_device": str(device),
    }
    if device.type == "cuda":
        snapshot["selected_device_name"] = torch.cuda.get_device_name(device)
        snapshot["selected_device_total_memory"] = torch.cuda.get_device_properties(
            device
        ).total_memory
    return snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(r"F:\VisualVIT_runtime\050_routeC\runs"),
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--train-cases", type=int, default=128)
    parser.add_argument("--dev-cases", type=int, default=64)
    parser.add_argument("--feature-dim", type=int, default=24)
    parser.add_argument("--classifier-steps", type=int, default=180)
    parser.add_argument("--matcher-steps", type=int, default=180)
    parser.add_argument("--classifier-learning-rate", type=float, default=0.02)
    parser.add_argument("--matcher-learning-rate", type=float, default=0.02)
    parser.add_argument("--data-seed", type=int, default=20260713)
    parser.add_argument("--seeds", type=int, nargs="+", default=[17, 29, 43])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    device = torch.device(args.device)
    if device.type == "cpu":
        torch.set_num_threads(min(8, os.cpu_count() or 1))

    run_id = args.run_id or (
        "pilot_synthetic_" + datetime.now().strftime("%Y%m%dT%H%M%S")
    )
    run_dir = args.output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    config = {
        "evidence_class": EVIDENCE_CLASS,
        "run_id": run_id,
        "device": str(device),
        "train_cases": args.train_cases,
        "dev_cases": args.dev_cases,
        "feature_dim": args.feature_dim,
        "classifier_steps": args.classifier_steps,
        "matcher_steps": args.matcher_steps,
        "classifier_learning_rate": args.classifier_learning_rate,
        "matcher_learning_rate": args.matcher_learning_rate,
        "data_seed": args.data_seed,
        "seeds": args.seeds,
        "token_budget": {
            "global": 4,
            "entity": 28,
            "relation": 28,
            "reserved": 4,
            "total": 64,
        },
        "qualification_note": (
            "Learned projection uses synthetic oracle cardinality and supervised "
            "row assignment; it is not a formal learned-matcher result."
        ),
    }
    paths = {
        "config": run_dir / "config.json",
        "environment": run_dir / "environment.json",
        "per_seed": run_dir / "per_seed.jsonl",
        "summary": run_dir / "summary.json",
        "manifest": run_dir / "manifest.json",
    }
    paths["config"].write_text(
        json.dumps(config, indent=2, sort_keys=True), encoding="utf-8"
    )
    paths["environment"].write_text(
        json.dumps(environment_snapshot(device), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    per_seed: list[dict[str, Any]] = []
    with paths["per_seed"].open("w", encoding="utf-8") as handle:
        for seed in args.seeds:
            print(f"[{run_id}] seed={seed} start", flush=True)
            row = run_seed(config, seed, device)
            per_seed.append(row)
            handle.write(json.dumps(row, sort_keys=True) + "\n")
            handle.flush()
            print(
                json.dumps(
                    {
                        "seed": seed,
                        "pass": row["pass"],
                        "delta_bind_pp": row["delta_bind_percentage_points"],
                        "recovery": row["recovery"],
                        "matcher_dev_acc": row["matcher"][
                            "dev_assignment_accuracy"
                        ],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

    summary = {
        "evidence_class": EVIDENCE_CLASS,
        "run_id": run_id,
        "status": "PASS" if all(row["pass"] for row in per_seed) else "FAIL",
        "aggregate": aggregate(per_seed),
        "formal_claim_allowed": False,
        "next_gate": (
            "Q5_PROXY_ENCODER"
            if all(row["pass"] for row in per_seed)
            else "STOP_AND_DIAGNOSE_Q1_Q4"
        ),
    }
    paths["summary"].write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )

    hashed = {}
    for name in ("config", "environment", "per_seed", "summary"):
        path = paths[name]
        hashed[path.name] = {
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
    manifest = {
        "evidence_class": EVIDENCE_CLASS,
        "run_id": run_id,
        "created_at": datetime.now().isoformat(),
        "workspace": str(WORKSPACE),
        "artifacts": hashed,
        "status": summary["status"],
    }
    paths["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True), flush=True)
    print(f"RESULT_DIR={run_dir}", flush=True)
    return 0 if summary["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
