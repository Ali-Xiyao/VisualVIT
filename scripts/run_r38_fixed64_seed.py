from __future__ import annotations

# ruff: noqa: E402

import argparse
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
    FROZEN_SEEDS,
    canonical_registry_value,
    checkpoint_for,
    load_candidate,
    merge_structure_and_labels,
    read_json,
    validate_dev_structure,
)
from scripts.r38_common import DEFAULT_R38_CONFIG, load_r38_config, write_json
from scripts.run_r37_prta_smoke import TEXT_CACHE, batch_indices
from visualvit.prta import (
    PRTATemporalAdapter,
    PRTATrainingHeads,
    project_equivariant_inversion_logits,
)
from visualvit.qualification import macro_f1
from visualvit.r37_cache import Block8CacheIndex
from visualvit.r38_fixed64 import (
    R38_TOKEN_COUNT,
    R38_TOKEN_LAYOUT,
    global_transition_tokens,
    pack_fixed64,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one frozen R38 fixed-64 survival seed"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_R38_CONFIG)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.seed not in FROZEN_SEEDS:
        raise ValueError(f"R38 seed must be one of {FROZEN_SEEDS}")
    config = load_r38_config(args.config)
    candidate = load_candidate(WORKSPACE / config["source_candidate"])
    one_shot = candidate["r37c_one_shot"]
    cache_root = Path(one_shot["structural_cache_root"])
    reveal_root = Path(one_shot["protected_reveal_root"])
    structure = read_json(cache_root / "dev_structure.json")
    validate_dev_structure(structure, candidate)
    examples = merge_structure_and_labels(
        structure, read_json(reveal_root / "protected_dev_labels.json")
    )
    r37c_result = read_json(
        reveal_root
        / "evaluations"
        / f"seed_{args.seed}"
        / "result.json"
    )
    output_root = Path(config["output_root"]) / f"seed_{args.seed}"
    if output_root.exists():
        raise FileExistsError(f"R38 seed output must be fresh: {output_root}")

    text_cache = torch.load(TEXT_CACHE, map_location="cpu", weights_only=True)
    findings = [str(value) for value in text_cache["findings"]]
    finding_to_index = {value: index for index, value in enumerate(findings)}
    label_to_index = {
        value: index for index, value in enumerate(text_cache["labels"])
    }
    for item in examples:
        item["finding"] = canonical_registry_value(item["finding"], findings)

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
    checkpoint = torch.load(
        checkpoint_for(candidate, roster="a6", seed=args.seed),
        map_location="cpu",
        weights_only=True,
    )
    model.load_state_dict(checkpoint["model"], strict=True)
    heads.load_state_dict(checkpoint["heads"], strict=True)
    model.eval()
    heads.eval()
    finding_text = text_cache["finding_embeddings"].to(device)

    patient_ids: list[str] = []
    record_ids: list[str] = []
    targets: list[int] = []
    true_predictions: list[int] = []
    current_predictions: list[int] = []
    maximum_embedding_difference = 0.0
    token_layout_valid = True
    attention_valid = True
    reserved_valid = True
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
                [finding_to_index[item["finding"]] for item in batch],
                dtype=torch.long,
                device=device,
            )
            target = torch.tensor(
                [label_to_index[item["label"]] for item in batch],
                dtype=torch.long,
                device=device,
            )
            query = heads.finding_query(finding_text[finding_index])
            true_output = model(prior, current, query)
            current_output = model(current, current, query)
            reversed_output = model(current, prior, query)
            bundles = [
                pack_fixed64(
                    finding_query=query,
                    state_tokens=output.state_tokens,
                    transition_tokens=output.transition_tokens,
                    aligned_prior_tokens=output.aligned_prior_tokens,
                )
                for output in (true_output, current_output, reversed_output)
            ]

            fixed_embeddings = [
                F.normalize(
                    model.transition_norm(
                        global_transition_tokens(bundle).mean(dim=1)
                    ),
                    dim=-1,
                )
                for bundle in bundles
            ]
            maximum_embedding_difference = max(
                maximum_embedding_difference,
                float(
                    (
                        fixed_embeddings[0]
                        - true_output.transition_embedding
                    )
                    .abs()
                    .max()
                    .item()
                ),
                float(
                    (
                        fixed_embeddings[1]
                        - current_output.transition_embedding
                    )
                    .abs()
                    .max()
                    .item()
                ),
                float(
                    (
                        fixed_embeddings[2]
                        - reversed_output.transition_embedding
                    )
                    .abs()
                    .max()
                    .item()
                ),
            )
            true_logits, _ = project_equivariant_inversion_logits(
                heads.progression_logits(fixed_embeddings[0]),
                heads.progression_logits(fixed_embeddings[2]),
            )
            current_logits, _ = project_equivariant_inversion_logits(
                heads.progression_logits(fixed_embeddings[1]),
                heads.progression_logits(fixed_embeddings[1]),
            )
            true_prediction = true_logits.argmax(dim=-1)
            current_prediction = current_logits.argmax(dim=-1)
            expected_types = [
                type_id
                for type_id, (_, count) in enumerate(R38_TOKEN_LAYOUT)
                for _ in range(count)
            ]
            for bundle in bundles:
                token_layout_valid = token_layout_valid and (
                    tuple(bundle.tokens.shape[1:]) == (R38_TOKEN_COUNT, 768)
                    and bundle.token_type_ids[0].tolist() == expected_types
                )
                attention_valid = attention_valid and bool(
                    bundle.physical_attention.all()
                )
                reserved_valid = reserved_valid and bool(
                    bundle.tokens[:, 60:64].eq(0).all()
                )
            patient_ids.extend(str(item["patient_id"]) for item in batch)
            record_ids.extend(str(item["record_id"]) for item in batch)
            targets.extend(target.cpu().tolist())
            true_predictions.extend(true_prediction.cpu().tolist())
            current_predictions.extend(current_prediction.cpu().tolist())

    reference_record_ids = r37c_result["record_ids"]
    if record_ids != reference_record_ids or targets != r37c_result["target_labels"]:
        raise ValueError("R38/R37C row order or target drift")
    class_count = len(label_to_index)
    true_f1 = macro_f1(
        targets, true_predictions, class_count=class_count
    )
    current_f1 = macro_f1(
        targets, current_predictions, class_count=class_count
    )
    result = {
        "schema": "visualvit.r38.fixed64-seed-survival.v1",
        "status": "PASS_R38_FIXED64_SEED_SURVIVAL",
        "candidate_id": config["candidate_id"],
        "seed": args.seed,
        "patients": len(set(patient_ids)),
        "rows": len(record_ids),
        "record_ids": record_ids,
        "patient_ids": patient_ids,
        "target_labels": targets,
        "predictions": {
            "fixed64_true": true_predictions,
            "fixed64_current_only": current_predictions,
        },
        "metrics": {
            "fixed64_true_macro_f1": true_f1,
            "fixed64_current_only_macro_f1": current_f1,
            "fixed64_true_minus_current_pp": 100 * (true_f1 - current_f1),
            "uncompressed_true_minus_current_pp": r37c_result["metrics"][
                "a6_minus_current_pp"
            ],
            "fixed64_matches_uncompressed_true_predictions": (
                true_predictions
                == r37c_result["predictions"]["a6_true"]
            ),
            "fixed64_matches_uncompressed_current_predictions": (
                current_predictions
                == r37c_result["predictions"]["a6_current_only"]
            ),
        },
        "token_audit": {
            "token_count": R38_TOKEN_COUNT,
            "layout_counts": {
                name: count for name, count in R38_TOKEN_LAYOUT
            },
            "token_layout_valid": token_layout_valid,
            "physical_attention_all_one": attention_valid,
            "reserved_tokens_shared_zero": reserved_valid,
            "maximum_transition_embedding_absolute_difference": (
                maximum_embedding_difference
            ),
            "sample_level_routing": False,
            "trainable_packing_parameters": 0,
            "labels_or_probe_logits_in_tokens": False,
        },
        "protected_300_dev_read": True,
        "sealed_483_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "checkpoint_hashes_recomputed": False,
        "r39_unlocked": False,
    }
    audits_pass = (
        token_layout_valid
        and attention_valid
        and reserved_valid
        and maximum_embedding_difference <= 1e-5
    )
    if not audits_pass:
        result["status"] = "STOP_R38_FIXED64_TOKEN_AUDIT"
    write_json(output_root / "result.json", result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "seed": args.seed,
                "metrics": result["metrics"],
                "token_audit": result["token_audit"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if audits_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
