from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter
import json
from pathlib import Path
import random
import sys
from typing import Any, Iterable

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import torch
import torch.nn.functional as F

from scripts.cache_r37_block8_tokens import build_frozen_encoder
from visualvit.cmcp import stable_hash, transition_examples
from visualvit.prta import (
    PROGRESSION_LABELS,
    PRTATemporalAdapter,
    PRTATrainingHeads,
    cmcp_margin_loss,
    prta_variant_registry,
    state_preservation_loss,
    temporal_inversion_loss,
)
from visualvit.r37_cache import Block8CacheIndex


TRANSITION_ROOT = Path(
    r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr"
    r"\r37a_transitions_v4_1"
)
CACHE_ROOT = Path(
    r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr"
    r"\r37_block8_token_cache"
)
TEXT_CACHE = Path(
    r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr"
    r"\r37_biomedclip_text_embeddings.pt"
)
CMCP_INDEX = Path(
    r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr"
    r"\r37_counterfactual_prior_index.json"
)
OUTPUT_BASE = Path(
    r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r37b_smokes"
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def flatten_partition(
    transition_root: Path, partition: str
) -> list[dict[str, Any]]:
    name = (
        "r37_pretrain_manifest.jsonl"
        if partition == "pretrain"
        else "r37_internal_calibration_manifest.jsonl"
    )
    rows = read_jsonl(transition_root / name)
    pair_by_id = {str(row["pair_id"]): row for row in rows}
    result = []
    for example in transition_examples(rows):
        pair = pair_by_id[example["pair_id"]]
        result.append(
            {
                **example,
                "patient_id": str(pair["patient_id"]),
                "prior_dicom_id": str(pair["prior_dicom_id"]),
                "current_dicom_id": str(pair["current_dicom_id"]),
            }
        )
    return result


def balanced_sample(
    examples: Iterable[dict[str, Any]], *, maximum: int, seed: int
) -> list[dict[str, Any]]:
    if maximum <= 0:
        raise ValueError("maximum examples must be positive")
    groups: dict[str, list[dict[str, Any]]] = {
        label: [] for label in PROGRESSION_LABELS
    }
    for item in examples:
        groups[str(item["label"])].append(item)
    per_label = max(1, maximum // len(PROGRESSION_LABELS))
    selected = []
    for label in PROGRESSION_LABELS:
        ordered = sorted(
            groups[label],
            key=lambda item: stable_hash(
                "r37-smoke-sample-v1", seed, item["example_id"]
            ),
        )
        selected.extend(ordered[:per_label])
    return sorted(
        selected,
        key=lambda item: stable_hash(
            "r37-smoke-order-v1", seed, item["example_id"]
        ),
    )


def macro_f1(targets: list[int], predictions: list[int]) -> float:
    scores = []
    for label in range(len(PROGRESSION_LABELS)):
        true_positive = sum(
            target == label and prediction == label
            for target, prediction in zip(targets, predictions)
        )
        false_positive = sum(
            target != label and prediction == label
            for target, prediction in zip(targets, predictions)
        )
        false_negative = sum(
            target == label and prediction != label
            for target, prediction in zip(targets, predictions)
        )
        denominator = 2 * true_positive + false_positive + false_negative
        scores.append(2 * true_positive / denominator if denominator else 0.0)
    return sum(scores) / len(scores)


def responsiveness_diagnostics(
    reference_embeddings: torch.Tensor,
    control_embeddings: torch.Tensor,
    reference_logits: torch.Tensor,
    control_logits: torch.Tensor,
) -> dict[str, float | int]:
    if reference_embeddings.shape != control_embeddings.shape:
        raise ValueError("responsiveness embedding shapes differ")
    if reference_logits.shape != control_logits.shape:
        raise ValueError("responsiveness logit shapes differ")
    if reference_embeddings.shape[0] != reference_logits.shape[0]:
        raise ValueError("responsiveness row counts differ")
    if reference_embeddings.shape[0] == 0:
        raise ValueError("responsiveness diagnostics require rows")
    embedding_l2 = (reference_embeddings - control_embeddings).norm(dim=-1)
    logit_l2 = (reference_logits - control_logits).norm(dim=-1)
    prediction_changes = (
        reference_logits.argmax(dim=-1) != control_logits.argmax(dim=-1)
    )
    return {
        "rows": int(reference_embeddings.shape[0]),
        "embedding_cosine_mean": float(
            F.cosine_similarity(
                reference_embeddings, control_embeddings, dim=-1
            )
            .mean()
            .item()
        ),
        "embedding_l2_mean": float(embedding_l2.mean().item()),
        "embedding_l2_max": float(embedding_l2.max().item()),
        "logit_l2_mean": float(logit_l2.mean().item()),
        "logit_l2_max": float(logit_l2.max().item()),
        "prediction_change_count": int(prediction_changes.sum().item()),
        "prediction_change_rate": float(prediction_changes.float().mean().item()),
    }


def batch_indices(length: int, batch_size: int) -> Iterable[tuple[int, int]]:
    for start in range(0, length, batch_size):
        yield start, min(start + batch_size, length)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run an engineering-only PRTA end-to-end token smoke"
    )
    parser.add_argument("--variant", choices=[f"A{i}" for i in range(2, 7)], default="A3")
    parser.add_argument("--transition-root", type=Path, default=TRANSITION_ROOT)
    parser.add_argument("--cache-root", type=Path, default=CACHE_ROOT)
    parser.add_argument("--text-cache", type=Path, default=TEXT_CACHE)
    parser.add_argument("--cmcp-index", type=Path, default=CMCP_INDEX)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--max-train-examples", type=int, default=100)
    parser.add_argument("--max-calibration-examples", type=int, default=50)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--adapter-rank", type=int, default=32)
    parser.add_argument("--formal", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_root = args.output_root or (
        OUTPUT_BASE / f"{args.variant.lower()}_seed{args.seed}_engineering_v1"
    )
    if output_root.exists():
        raise FileExistsError(f"output root must be fresh: {output_root}")
    if args.batch_size <= 0 or args.epochs <= 0:
        raise ValueError("batch size and epochs must be positive")
    transition_audit = json.loads(
        (args.transition_root / "r37_transition_audit.json").read_text(
            encoding="utf-8"
        )
    )
    if transition_audit["ruleset_version"] != "r37-report-transition-v4.1":
        raise ValueError("transition ruleset drift")
    if args.formal and not transition_audit["formal_training_unlocked"]:
        raise PermissionError(
            "formal R37B remains locked pending independent human QA"
        )
    if not args.formal and (
        args.max_train_examples > 1000
        or args.max_calibration_examples > 500
        or args.epochs > 3
    ):
        raise ValueError("engineering smoke exceeds its non-formal scale limit")

    variant = prta_variant_registry()[args.variant]
    cmcp_by_target: dict[str, dict[str, Any]] = {}
    if variant.cmcp:
        if not args.cmcp_index.is_file():
            raise FileNotFoundError("CMCP variant requires the frozen index")
        cmcp_payload = json.loads(args.cmcp_index.read_text(encoding="utf-8"))
        if cmcp_payload["status"] != "PASS_R37A_CMCP_COVERAGE":
            raise ValueError("CMCP coverage gate has not passed")
        cmcp_by_target = {
            str(item["target_example_id"]): item
            for item in cmcp_payload["matches"]
        }

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")

    train_examples = balanced_sample(
        flatten_partition(args.transition_root, "pretrain"),
        maximum=args.max_train_examples,
        seed=args.seed,
    )
    calibration_examples = balanced_sample(
        flatten_partition(args.transition_root, "internal_calibration"),
        maximum=args.max_calibration_examples,
        seed=args.seed + 1,
    )
    cache = Block8CacheIndex(args.cache_root, maximum_loaded_shards=4)
    text_cache = torch.load(
        args.text_cache, map_location="cpu", weights_only=True
    )
    findings = [str(value) for value in text_cache["findings"]]
    labels = [str(value) for value in text_cache["labels"]]
    if tuple(labels) != PROGRESSION_LABELS:
        raise ValueError("text-cache label order drift")
    finding_to_index = {value: index for index, value in enumerate(findings)}
    label_to_index = {value: index for index, value in enumerate(labels)}
    finding_text = text_cache["finding_embeddings"].to(device)
    transition_text = text_cache["transition_embeddings"].to(device)

    encoder = build_frozen_encoder(device)
    tail_blocks = list(encoder.blocks[8:])
    final_norm = encoder.norm
    model = PRTATemporalAdapter(
        tail_blocks,
        frozen_final_norm=final_norm,
        adapter_rank=args.adapter_rank,
    ).to(device)
    heads = PRTATrainingHeads().to(device)
    del encoder
    trainable = [
        parameter
        for module in (model, heads)
        for parameter in module.parameters()
        if parameter.requires_grad
    ]
    optimizer = torch.optim.AdamW(
        trainable, lr=args.learning_rate, weight_decay=0.05
    )

    def tensors(examples: list[dict[str, Any]]):
        prior = cache.get_many(item["prior_dicom_id"] for item in examples)
        current = cache.get_many(item["current_dicom_id"] for item in examples)
        finding_indices = torch.tensor(
            [finding_to_index[item["finding"]] for item in examples],
            dtype=torch.long,
            device=device,
        )
        label_indices = torch.tensor(
            [label_to_index[item["label"]] for item in examples],
            dtype=torch.long,
            device=device,
        )
        prototype_indices = finding_indices * len(labels) + label_indices
        return (
            prior.to(device=device, dtype=torch.float32),
            current.to(device=device, dtype=torch.float32),
            finding_indices,
            label_indices,
            prototype_indices,
        )

    history = []
    for epoch in range(args.epochs):
        model.train()
        heads.train()
        generator = torch.Generator().manual_seed(args.seed + epoch)
        order = torch.randperm(len(train_examples), generator=generator).tolist()
        ordered = [train_examples[index] for index in order]
        epoch_losses = Counter()
        steps = 0
        for start, end in batch_indices(len(ordered), args.batch_size):
            batch = ordered[start:end]
            prior, current, finding_index, label_index, prototype_index = tensors(
                batch
            )
            query = heads.finding_query(finding_text[finding_index])
            output = model(prior, current, query)
            logits = heads.progression_logits(output.transition_embedding)
            losses: dict[str, torch.Tensor] = {
                "classification": F.cross_entropy(logits, label_index)
            }
            projected_prototypes = heads.transition_text(transition_text)
            target_text = projected_prototypes[prototype_index]
            if variant.transition_alignment:
                prototype_logits = (
                    output.transition_embedding
                    @ projected_prototypes.transpose(0, 1)
                    / 0.07
                )
                losses["transition"] = F.cross_entropy(
                    prototype_logits, prototype_index
                )
            if variant.temporal_inversion:
                reversed_output = model(current, prior, query)
                reversed_logits = heads.progression_logits(
                    reversed_output.transition_embedding
                )
                losses["inversion"] = temporal_inversion_loss(
                    logits, reversed_logits
                )
            if variant.state_preservation:
                losses["state"] = state_preservation_loss(
                    output.state_embedding, output.frozen_current_embedding
                )
            if variant.cmcp:
                dynamic_positions = [
                    index
                    for index, item in enumerate(batch)
                    if item["label"] != "Stable"
                    and item["example_id"] in cmcp_by_target
                ]
                if dynamic_positions:
                    counterfactual_prior = cache.get_many(
                        cmcp_by_target[batch[index]["example_id"]][
                            "counterfactual_prior_dicom_id"
                        ]
                        for index in dynamic_positions
                    ).to(device=device, dtype=torch.float32)
                    selected_current = current[dynamic_positions]
                    selected_query = query[dynamic_positions]
                    counterfactual_output = model(
                        counterfactual_prior,
                        selected_current,
                        selected_query,
                    )
                    losses["cmcp"] = cmcp_margin_loss(
                        output.transition_embedding[dynamic_positions],
                        counterfactual_output.transition_embedding,
                        target_text[dynamic_positions],
                    )
            total = sum(losses.values())
            optimizer.zero_grad(set_to_none=True)
            total.backward()
            optimizer.step()
            for name, value in losses.items():
                epoch_losses[name] += float(value.detach().item())
            epoch_losses["total"] += float(total.detach().item())
            steps += 1
        history.append(
            {
                "epoch": epoch,
                "steps": steps,
                "mean_losses": {
                    name: value / steps for name, value in epoch_losses.items()
                },
            }
        )

    def evaluate(examples: list[dict[str, Any]]) -> dict[str, Any]:
        model.eval()
        heads.eval()
        targets = []
        true_predictions = []
        current_only_predictions = []
        inverted_predictions = []
        cmcp_patient_ids = []
        cmcp_targets = []
        cmcp_true_predictions = []
        cmcp_predictions = []
        true_embeddings = []
        current_embeddings = []
        inverted_embeddings = []
        true_logits_parts = []
        current_logits_parts = []
        inverted_logits_parts = []
        cmcp_true_embeddings = []
        cmcp_control_embeddings = []
        cmcp_true_logits_parts = []
        cmcp_control_logits_parts = []
        with torch.inference_mode():
            for start, end in batch_indices(len(examples), args.batch_size):
                batch = examples[start:end]
                prior, current, finding_index, label_index, _ = tensors(batch)
                query = heads.finding_query(finding_text[finding_index])
                true_output = model(prior, current, query)
                current_output = model(current, current, query)
                inverted_output = model(current, prior, query)
                true_logits = heads.progression_logits(
                    true_output.transition_embedding
                )
                current_logits = heads.progression_logits(
                    current_output.transition_embedding
                )
                inverted_logits = heads.progression_logits(
                    inverted_output.transition_embedding
                )
                batch_true_predictions = true_logits.argmax(dim=-1)
                true_predictions.extend(
                    batch_true_predictions.cpu().tolist()
                )
                current_only_predictions.extend(
                    current_logits.argmax(dim=-1).cpu().tolist()
                )
                inverted_predictions.extend(
                    inverted_logits.argmax(dim=-1).cpu().tolist()
                )
                true_embeddings.append(
                    true_output.transition_embedding.cpu()
                )
                current_embeddings.append(
                    current_output.transition_embedding.cpu()
                )
                inverted_embeddings.append(
                    inverted_output.transition_embedding.cpu()
                )
                true_logits_parts.append(true_logits.cpu())
                current_logits_parts.append(current_logits.cpu())
                inverted_logits_parts.append(inverted_logits.cpu())
                if variant.cmcp:
                    positions = [
                        index
                        for index, item in enumerate(batch)
                        if item["label"] != "Stable"
                        and item["example_id"] in cmcp_by_target
                    ]
                    if positions:
                        counterfactual_prior = cache.get_many(
                            cmcp_by_target[batch[index]["example_id"]][
                                "counterfactual_prior_dicom_id"
                            ]
                            for index in positions
                        ).to(device=device, dtype=torch.float32)
                        cmcp_output = model(
                            counterfactual_prior,
                            current[positions],
                            query[positions],
                        )
                        cmcp_logits = heads.progression_logits(
                            cmcp_output.transition_embedding
                        )
                        cmcp_predictions.extend(
                            cmcp_logits.argmax(dim=-1).cpu().tolist()
                        )
                        cmcp_true_embeddings.append(
                            true_output.transition_embedding[positions].cpu()
                        )
                        cmcp_control_embeddings.append(
                            cmcp_output.transition_embedding.cpu()
                        )
                        cmcp_true_logits_parts.append(
                            true_logits[positions].cpu()
                        )
                        cmcp_control_logits_parts.append(cmcp_logits.cpu())
                        cmcp_patient_ids.extend(
                            str(batch[index]["patient_id"])
                            for index in positions
                        )
                        cmcp_targets.extend(
                            label_index[positions].cpu().tolist()
                        )
                        cmcp_true_predictions.extend(
                            batch_true_predictions[positions].cpu().tolist()
                        )
                targets.extend(label_index.cpu().tolist())
        true_f1 = macro_f1(targets, true_predictions)
        current_f1 = macro_f1(targets, current_only_predictions)
        responsiveness = {
            "true_vs_current": responsiveness_diagnostics(
                torch.cat(true_embeddings),
                torch.cat(current_embeddings),
                torch.cat(true_logits_parts),
                torch.cat(current_logits_parts),
            ),
            "true_vs_inverted": responsiveness_diagnostics(
                torch.cat(true_embeddings),
                torch.cat(inverted_embeddings),
                torch.cat(true_logits_parts),
                torch.cat(inverted_logits_parts),
            ),
            "true_vs_cmcp": (
                responsiveness_diagnostics(
                    torch.cat(cmcp_true_embeddings),
                    torch.cat(cmcp_control_embeddings),
                    torch.cat(cmcp_true_logits_parts),
                    torch.cat(cmcp_control_logits_parts),
                )
                if cmcp_true_embeddings
                else None
            ),
        }
        return {
            "examples": len(examples),
            "patient_ids": [str(item["patient_id"]) for item in examples],
            "target_counts": dict(Counter(targets)),
            "target_labels": targets,
            "true_pair_predictions": true_predictions,
            "current_only_predictions": current_only_predictions,
            "inverted_predictions": inverted_predictions,
            "true_pair_macro_f1": true_f1,
            "current_only_macro_f1": current_f1,
            "true_minus_current_pp": (true_f1 - current_f1) * 100,
            "responsiveness": responsiveness,
            "cmcp": {
                "patient_ids": cmcp_patient_ids,
                "target_labels": cmcp_targets,
                "true_pair_predictions": cmcp_true_predictions,
                "control_predictions": cmcp_predictions,
            },
        }

    calibration = evaluate(calibration_examples)
    frozen_gradients_absent = all(
        parameter.grad is None
        for parameter in model.tail.frozen_blocks.parameters()
    )
    adapter_gradients_present = all(
        any(parameter.grad is not None for parameter in adapter.parameters())
        for adapter in model.tail.adapters
    )
    result = {
        "schema": "visualvit.r37.prta-engineering-smoke.v1",
        "status": (
            "PASS_R37_PRTA_ENGINEERING_SMOKE"
            if frozen_gradients_absent and adapter_gradients_present
            else "STOP_R37_PRTA_GRADIENT_AUDIT"
        ),
        "formal": args.formal,
        "scientific_claim_allowed": False if not args.formal else None,
        "formal_training_unlocked": bool(
            args.formal and transition_audit["formal_training_unlocked"]
        ),
        "variant": args.variant,
        "variant_config": variant.__dict__,
        "seed": args.seed,
        "train_examples": len(train_examples),
        "calibration": calibration,
        "history": history,
        "gradient_audit": {
            "frozen_base_gradients_absent": frozen_gradients_absent,
            "all_adapter_stages_received_gradients": adapter_gradients_present,
        },
        "protected_outcomes_read": False,
        "sealed_test_read": False,
        "gold_outcomes_read": False,
    }
    output_root.mkdir(parents=True, exist_ok=False)
    (output_root / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    torch.save(
        {
            "model": model.state_dict(),
            "heads": heads.state_dict(),
            "variant": args.variant,
            "seed": args.seed,
        },
        output_root / "checkpoint.pt",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    print(f"RESULT_DIR={output_root}")
    return 0 if result["status"] == "PASS_R37_PRTA_ENGINEERING_SMOKE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
