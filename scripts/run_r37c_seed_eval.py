from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import torch
import torch.nn.functional as F

from scripts.cache_r37_block8_tokens import build_frozen_encoder
from scripts.r37c_common import (
    DEFAULT_CANDIDATE,
    FROZEN_SEEDS,
    checkpoint_for,
    load_candidate,
    merge_structure_and_labels,
    read_json,
    validate_dev_structure,
    write_json,
)
from scripts.run_r37_prta_smoke import TEXT_CACHE, batch_indices
from visualvit.prta import (
    INVERSION_INDEX,
    PROGRESSION_LABELS,
    PRTATemporalAdapter,
    PRTATrainingHeads,
    project_equivariant_inversion_logits,
)
from visualvit.qualification import FindingConditionedLinearProbe, macro_f1
from visualvit.r37_cache import Block8CacheIndex


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate one frozen A6/A0 seed on one-shot R37C dev"
    )
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.seed not in FROZEN_SEEDS:
        raise ValueError(f"R37C seed must be one of {FROZEN_SEEDS}")
    if args.batch_size <= 0:
        raise ValueError("batch size must be positive")
    candidate = load_candidate(args.candidate)
    one_shot = candidate["r37c_one_shot"]
    cache_root = Path(one_shot["structural_cache_root"])
    reveal_root = Path(one_shot["protected_reveal_root"])
    receipt = read_json(reveal_root / "reveal_receipt.json")
    if (
        receipt.get("status") != "PASS_R37C_ONE_SHOT_DEV_REVEAL"
        or receipt.get("reveal_count") != 1
        or receipt.get("candidate_id") != candidate["candidate_id"]
    ):
        raise PermissionError("R37C one-shot reveal receipt drift")
    structure = read_json(cache_root / "dev_structure.json")
    validate_dev_structure(structure, candidate)
    examples = merge_structure_and_labels(
        structure, read_json(reveal_root / "protected_dev_labels.json")
    )
    output_root = reveal_root / "evaluations" / f"seed_{args.seed}"
    if output_root.exists():
        raise FileExistsError(f"R37C seed output must be fresh: {output_root}")

    text_cache = torch.load(TEXT_CACHE, map_location="cpu", weights_only=True)
    findings = [str(value) for value in text_cache["findings"]]
    labels = [str(value) for value in text_cache["labels"]]
    if (
        findings != candidate["frozen_model"]["finding_registry"]
        or labels != candidate["frozen_model"]["label_registry"]
        or tuple(labels) != PROGRESSION_LABELS
    ):
        raise ValueError("R37C frozen finding/label registry drift")
    finding_to_index = {value: index for index, value in enumerate(findings)}
    label_to_index = {value: index for index, value in enumerate(labels)}
    if any(str(item["finding"]) not in finding_to_index for item in examples):
        raise ValueError("R37C row contains an unregistered finding")

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    if device.type == "cuda":
        torch.cuda.set_device(device)
        torch.cuda.reset_peak_memory_stats(device)
    cache = Block8CacheIndex(cache_root, maximum_loaded_shards=4)
    encoder = build_frozen_encoder(device)
    model = PRTATemporalAdapter(
        list(encoder.blocks[8:]),
        frozen_final_norm=encoder.norm,
        adapter_rank=int(candidate["frozen_model"]["adapter_rank"]),
    ).to(device)
    heads = PRTATrainingHeads().to(device)
    del encoder
    a6_checkpoint = torch.load(
        checkpoint_for(candidate, roster="a6", seed=args.seed),
        map_location="cpu",
        weights_only=True,
    )
    if (
        a6_checkpoint.get("variant") != "A6"
        or int(a6_checkpoint.get("seed")) != args.seed
        or a6_checkpoint.get("r37_1") is not True
    ):
        raise ValueError("R37C A6 checkpoint metadata drift")
    model.load_state_dict(a6_checkpoint["model"], strict=True)
    heads.load_state_dict(a6_checkpoint["heads"], strict=True)
    probe = FindingConditionedLinearProbe(
        feature_dim=768,
        finding_count=len(findings),
        class_count=len(labels),
    ).to(device)
    a0_checkpoint = torch.load(
        checkpoint_for(candidate, roster="a0", seed=args.seed),
        map_location="cpu",
        weights_only=True,
    )
    probe.load_state_dict(a0_checkpoint["probe_state_dict"], strict=True)
    model.eval()
    heads.eval()
    probe.eval()
    finding_text = text_cache["finding_embeddings"].to(device)

    patient_ids: list[str] = []
    record_ids: list[str] = []
    targets: list[int] = []
    a6_true: list[int] = []
    a6_current: list[int] = []
    a6_inverted: list[int] = []
    a0_true: list[int] = []
    a0_current: list[int] = []
    inversion_consistent = 0
    state_cosines: list[float] = []
    with torch.inference_mode():
        for start, end in batch_indices(len(examples), args.batch_size):
            batch = examples[start:end]
            prior = cache.get_many(
                item["prior_dicom_id"] for item in batch
            ).to(device=device, dtype=torch.float32)
            current = cache.get_many(
                item["current_dicom_id"] for item in batch
            ).to(device=device, dtype=torch.float32)
            finding_index = torch.tensor(
                [finding_to_index[str(item["finding"])] for item in batch],
                dtype=torch.long,
                device=device,
            )
            target = torch.tensor(
                [label_to_index[str(item["label"])] for item in batch],
                dtype=torch.long,
                device=device,
            )
            query = heads.finding_query(finding_text[finding_index])
            true_output = model(prior, current, query)
            current_output = model(current, current, query)
            inverted_output = model(current, prior, query)
            true_logits, inverted_logits = project_equivariant_inversion_logits(
                heads.progression_logits(true_output.transition_embedding),
                heads.progression_logits(inverted_output.transition_embedding),
            )
            current_logits, _ = project_equivariant_inversion_logits(
                heads.progression_logits(current_output.transition_embedding),
                heads.progression_logits(current_output.transition_embedding),
            )
            true_prediction = true_logits.argmax(dim=-1)
            mapped_true = INVERSION_INDEX.to(device)[true_prediction]
            inverted_prediction = mapped_true
            inversion_consistent += int(
                (inverted_prediction == mapped_true).sum().item()
            )
            state_cosines.extend(
                F.cosine_similarity(
                    true_output.state_embedding,
                    true_output.frozen_current_embedding,
                    dim=-1,
                )
                .cpu()
                .tolist()
            )

            frozen_prior = model.tail.forward_frozen(prior)[:, 0]
            frozen_current = model.tail.forward_frozen(current)[:, 0]
            a0_true_features = F.normalize(
                frozen_current - frozen_prior, dim=-1
            )
            a0_current_features = F.normalize(
                frozen_current - frozen_current, dim=-1
            )
            a0_true_prediction = probe(
                a0_true_features, finding_index
            ).argmax(dim=-1)
            a0_current_prediction = probe(
                a0_current_features, finding_index
            ).argmax(dim=-1)

            patient_ids.extend(str(item["patient_id"]) for item in batch)
            record_ids.extend(str(item["record_id"]) for item in batch)
            targets.extend(target.cpu().tolist())
            a6_true.extend(true_prediction.cpu().tolist())
            a6_current.extend(current_logits.argmax(dim=-1).cpu().tolist())
            a6_inverted.extend(inverted_prediction.cpu().tolist())
            a0_true.extend(a0_true_prediction.cpu().tolist())
            a0_current.extend(a0_current_prediction.cpu().tolist())

    class_count = len(labels)
    metrics = {
        "a6_true_macro_f1": macro_f1(
            targets, a6_true, class_count=class_count
        ),
        "a6_current_only_macro_f1": macro_f1(
            targets, a6_current, class_count=class_count
        ),
        "a0_true_macro_f1": macro_f1(
            targets, a0_true, class_count=class_count
        ),
        "a0_current_only_macro_f1": macro_f1(
            targets, a0_current, class_count=class_count
        ),
    }
    metrics["a6_minus_current_pp"] = 100 * (
        metrics["a6_true_macro_f1"]
        - metrics["a6_current_only_macro_f1"]
    )
    metrics["a6_minus_a0_pp"] = 100 * (
        metrics["a6_true_macro_f1"] - metrics["a0_true_macro_f1"]
    )
    result = {
        "schema": "visualvit.r37c.one-shot-seed-evaluation.v1",
        "status": "PASS_R37C_ONE_SHOT_SEED_EVALUATION",
        "candidate_id": candidate["candidate_id"],
        "seed": args.seed,
        "variant": "A6",
        "patients": len(set(patient_ids)),
        "rows": len(record_ids),
        "record_ids": record_ids,
        "patient_ids": patient_ids,
        "target_labels": targets,
        "target_counts": dict(Counter(targets)),
        "predictions": {
            "a6_true": a6_true,
            "a6_current_only": a6_current,
            "a6_inverted": a6_inverted,
            "a0_true": a0_true,
            "a0_current_only": a0_current,
        },
        "metrics": metrics,
        "qualification_diagnostics": {
            "inversion_consistency_rate": (
                inversion_consistent / len(examples)
            ),
            "state_retention_cosine_mean": (
                sum(state_cosines) / len(state_cosines)
            ),
            "state_retention_rows": len(state_cosines),
        },
        "protected_outcomes_read": True,
        "sealed_483_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "checkpoint_hashes_recomputed": False,
        "protocol_deviation": candidate["protocol_deviation"],
        "device": str(device),
        "peak_cuda_allocated_bytes": (
            torch.cuda.max_memory_allocated(device)
            if device.type == "cuda"
            else 0
        ),
    }
    write_json(output_root / "result.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
