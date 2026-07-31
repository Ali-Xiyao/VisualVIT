from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter
import json
from pathlib import Path
import random
import sys
import time
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import torch
import torch.nn.functional as F

from scripts.r50_common import (
    METHODS,
    epoch_order,
    finding_registry,
    load_naive_tokens,
    prediction_metrics,
    row_tensors,
    validate_authority,
    write_json,
)
from visualvit.prta import PROGRESSION_LABELS
from visualvit.qualification import FindingConditionedLinearProbe
from visualvit.r50_method_baselines import (
    INVERSION_INDEX,
    TACTemporalFusionAdapted,
    tila_bice_tcl_loss,
    tila_combined_probabilities,
)


DEFAULT_CONFIG = (
    WORKSPACE / "configs" / "prta_gen" / "prta_gen_r50_method_benchmark_v1.json"
)


def _device(name: str) -> torch.device:
    device = torch.device(name)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("R50 method runs require explicit CUDA")
    torch.cuda.set_device(device)
    torch.empty(1, device=device)
    torch.cuda.reset_peak_memory_stats(device)
    return device


def _validate_feature_cache(
    payload: dict[str, Any],
    *,
    status: str,
    rows: list[dict[str, Any]],
) -> None:
    if (
        payload.get("status") != status
        or payload.get("labels_in_cache") is not False
        or payload.get("protected_483_test_read") is not False
        or payload.get("gold_outcomes_read") is not False
        or payload.get("external_outcomes_read") is not False
        or payload.get("example_ids")
        != [str(row["example_id"]) for row in rows]
        or payload.get("patient_ids")
        != [str(row["patient_id"]) for row in rows]
        or payload.get("findings")
        != [str(row["finding"]) for row in rows]
    ):
        raise PermissionError("R50 feature-cache contract drift")


def _load_inputs(
    config: dict[str, Any],
    method: str,
    rows: list[dict[str, Any]],
) -> tuple[torch.Tensor, torch.Tensor | None]:
    if method in ("tila_ce", "tila_bice_tcl"):
        payload = torch.load(
            config["runtime"]["tila_cache"],
            map_location="cpu",
            weights_only=True,
        )
        _validate_feature_cache(
            payload,
            status=config["result_statuses"]["tila_cache_pass"],
            rows=rows,
        )
        return payload["forward_features"].float(), payload[
            "reversed_features"
        ].float()
    if method == "siamese_signed_abs":
        payload = torch.load(
            config["runtime"]["b2_cache"],
            map_location="cpu",
            weights_only=True,
        )
        _validate_feature_cache(
            payload,
            status=config["result_statuses"]["b2_cache_pass"],
            rows=rows,
        )
        return payload["forward_features"].float(), payload[
            "reversed_features"
        ].float()
    tokens = load_naive_tokens(Path(config["cache"]["naive_token_index"]), rows)
    return tokens, None


def _batch_logits(
    *,
    method: str,
    inputs: torch.Tensor,
    indices: torch.Tensor,
    findings: torch.Tensor,
    probe: FindingConditionedLinearProbe,
    adapter: TACTemporalFusionAdapted | None,
    device: torch.device,
    reverse: bool,
) -> torch.Tensor:
    batch_findings = findings.index_select(0, indices).to(device)
    if method == "tac_temporal_fusion_adapted":
        if adapter is None:
            raise RuntimeError("R50 TAC adapter is missing")
        tokens = inputs.index_select(0, indices.cpu()).to(
            device=device, dtype=torch.float32
        )
        prior, current = tokens[:, :30], tokens[:, 30:60]
        features = (
            adapter(current, prior) if reverse else adapter(prior, current)
        )
    else:
        features = inputs.index_select(0, indices.cpu()).to(
            device=device, dtype=torch.float32
        )
    return probe(features, batch_findings)


def _evaluate(
    *,
    method: str,
    inputs: torch.Tensor,
    reverse_inputs: torch.Tensor | None,
    findings: torch.Tensor,
    targets: torch.Tensor,
    probe: FindingConditionedLinearProbe,
    adapter: TACTemporalFusionAdapted | None,
    device: torch.device,
    batch_size: int,
) -> tuple[dict[str, Any], dict[str, list[int]]]:
    probe.eval()
    if adapter is not None:
        adapter.eval()
    forward_predictions: list[int] = []
    reverse_predictions: list[int] = []
    combined_predictions: list[int] = []
    with torch.inference_mode():
        for start in range(0, len(targets), batch_size):
            indices = torch.arange(start, min(start + batch_size, len(targets)))
            forward_logits = _batch_logits(
                method=method,
                inputs=inputs,
                indices=indices,
                findings=findings,
                probe=probe,
                adapter=adapter,
                device=device,
                reverse=False,
            )
            reverse_source = inputs if reverse_inputs is None else reverse_inputs
            reverse_logits = _batch_logits(
                method=method,
                inputs=reverse_source,
                indices=indices,
                findings=findings,
                probe=probe,
                adapter=adapter,
                device=device,
                reverse=reverse_inputs is None,
            )
            forward_predictions.extend(forward_logits.argmax(dim=-1).cpu().tolist())
            reverse_predictions.extend(reverse_logits.argmax(dim=-1).cpu().tolist())
            if method == "tila_bice_tcl":
                combined_predictions.extend(
                    tila_combined_probabilities(
                        forward_logits, reverse_logits
                    ).argmax(dim=-1).cpu().tolist()
                )
            else:
                combined_predictions.extend(forward_logits.argmax(dim=-1).cpu().tolist())
    target_values = targets.cpu().tolist()
    mapped_reverse = [INVERSION_INDEX[value] for value in reverse_predictions]
    metrics = prediction_metrics(target_values, combined_predictions)
    metrics["forward"] = prediction_metrics(target_values, forward_predictions)
    reverse_targets = [INVERSION_INDEX[value] for value in target_values]
    metrics["reversed"] = prediction_metrics(reverse_targets, reverse_predictions)
    metrics["mapped_prediction_consistency"] = sum(
        forward == mapped
        for forward, mapped in zip(forward_predictions, mapped_reverse)
    ) / len(forward_predictions)
    return metrics, {
        "primary": combined_predictions,
        "forward": forward_predictions,
        "reversed": reverse_predictions,
        "mapped_reversed": mapped_reverse,
    }


def run_method(
    config_path: Path,
    *,
    method: str,
    seed: int,
    device_name: str,
) -> dict[str, Any]:
    config, _, training_rows, evaluation_rows = validate_authority(config_path)
    if method not in METHODS:
        raise ValueError(f"unregistered R50 method: {method}")
    training = config["training"]
    if seed not in [int(value) for value in training["seeds"]]:
        raise ValueError("R50 seed is not frozen")
    output = Path(config["runtime"]["runs"]) / method / f"seed_{seed}"
    if output.exists():
        raise FileExistsError(f"R50 method output must be fresh: {output}")
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    device = _device(device_name)
    rows = training_rows + evaluation_rows
    inputs, reverse_inputs = _load_inputs(config, method, rows)
    train_count = len(training_rows)
    train_inputs = inputs[:train_count]
    train_reverse = None if reverse_inputs is None else reverse_inputs[:train_count]
    eval_inputs = inputs[train_count:]
    eval_reverse = None if reverse_inputs is None else reverse_inputs[train_count:]
    findings, finding_to_index = finding_registry(training_rows, evaluation_rows)
    all_finding_tensor, all_target_tensor = row_tensors(
        rows, finding_to_index=finding_to_index, device=torch.device("cpu")
    )
    train_findings = all_finding_tensor[:train_count]
    train_targets = all_target_tensor[:train_count]
    eval_findings = all_finding_tensor[train_count:]
    eval_targets = all_target_tensor[train_count:]

    feature_dim = 768 if method == "tac_temporal_fusion_adapted" else int(inputs.shape[-1])
    probe = FindingConditionedLinearProbe(
        feature_dim=feature_dim,
        finding_count=len(findings),
        class_count=len(PROGRESSION_LABELS),
    ).to(device)
    adapter = None
    if method == "tac_temporal_fusion_adapted":
        method_spec = config["methods"][method]
        adapter = TACTemporalFusionAdapted(
            width=feature_dim,
            heads=int(method_spec["attention_heads"]),
            dropout=float(method_spec["dropout"]),
        ).to(device)
    parameters = list(probe.parameters())
    if adapter is not None:
        parameters.extend(adapter.parameters())
    learning_rate = (
        float(training["tac_learning_rate"])
        if adapter is not None
        else float(training["probe_learning_rate"])
    )
    optimizer = torch.optim.AdamW(
        parameters,
        lr=learning_rate,
        weight_decay=float(training["weight_decay"]),
    )
    batch_size = int(
        training["tac_batch_size"]
        if adapter is not None
        else training["probe_batch_size"]
    )
    started = time.perf_counter()
    history: list[dict[str, Any]] = []
    for epoch in range(int(training["epochs"])):
        probe.train()
        if adapter is not None:
            adapter.train()
        order = epoch_order(
            training_rows,
            namespace=str(training["shuffle_namespace"]),
            seed=seed,
            epoch=epoch,
        )
        total_loss = 0.0
        total_bice = 0.0
        total_tcl = 0.0
        batches = 0
        for start in range(0, train_count, batch_size):
            indices = torch.tensor(order[start : start + batch_size], dtype=torch.long)
            forward_logits = _batch_logits(
                method=method,
                inputs=train_inputs,
                indices=indices,
                findings=train_findings,
                probe=probe,
                adapter=adapter,
                device=device,
                reverse=False,
            )
            targets = train_targets.index_select(0, indices).to(device)
            if method == "tila_bice_tcl":
                if train_reverse is None:
                    raise RuntimeError("R50 TILA reverse cache is missing")
                reverse_logits = _batch_logits(
                    method=method,
                    inputs=train_reverse,
                    indices=indices,
                    findings=train_findings,
                    probe=probe,
                    adapter=None,
                    device=device,
                    reverse=False,
                )
                weight = (
                    float(training["tila_tcl_weight"])
                    if epoch + 1 >= int(training["tila_tcl_start_epoch_one_based"])
                    else 0.0
                )
                loss, pieces = tila_bice_tcl_loss(
                    forward_logits,
                    reverse_logits,
                    targets,
                    tcl_weight=weight,
                )
                total_bice += float(pieces["bice"].detach().cpu())
                total_tcl += float(pieces["tcl"].detach().cpu())
            else:
                loss = F.cross_entropy(forward_logits, targets)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                parameters, float(training["gradient_clip_norm"])
            )
            optimizer.step()
            total_loss += float(loss.detach().cpu())
            batches += 1
        history.append(
            {
                "epoch": epoch + 1,
                "loss": total_loss / batches,
                "bice": total_bice / batches if method == "tila_bice_tcl" else None,
                "tcl": total_tcl / batches if method == "tila_bice_tcl" else None,
                "tcl_active": method == "tila_bice_tcl"
                and epoch + 1 >= int(training["tila_tcl_start_epoch_one_based"]),
            }
        )
    metrics, predictions = _evaluate(
        method=method,
        inputs=eval_inputs,
        reverse_inputs=eval_reverse,
        findings=eval_findings,
        targets=eval_targets,
        probe=probe,
        adapter=adapter,
        device=device,
        batch_size=batch_size,
    )
    result = {
        "schema": "visualvit.prta-gen.r50-method-seed.v1",
        "status": config["result_statuses"]["method_pass"],
        "protocol_id": config["protocol_id"],
        "method": method,
        "reproduction_label": config["methods"][method]["reproduction_label"],
        "seed": seed,
        "training_rows": len(training_rows),
        "evaluation_rows": len(evaluation_rows),
        "evaluation_patient_ids": [str(row["patient_id"]) for row in evaluation_rows],
        "evaluation_example_ids": [str(row["example_id"]) for row in evaluation_rows],
        "targets": eval_targets.tolist(),
        "predictions": predictions,
        "metrics": metrics,
        "feature_dim": feature_dim,
        "finding_count": len(findings),
        "findings": findings,
        "trainable_parameters": sum(value.numel() for value in parameters),
        "probe_trainable_parameters": sum(
            value.numel() for value in probe.parameters()
        ),
        "adapter_trainable_parameters": 0
        if adapter is None
        else sum(value.numel() for value in adapter.parameters()),
        "training_label_counts": dict(
            Counter(str(row["progression"]) for row in training_rows)
        ),
        "history": history,
        "elapsed_seconds": time.perf_counter() - started,
        "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(device),
        "protected_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "posthoc_internal_benchmark": True,
        "clinical_claim_allowed": False,
    }
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "result.json", result)
    torch.save(
        {
            "protocol_id": config["protocol_id"],
            "method": method,
            "seed": seed,
            "probe_state_dict": probe.state_dict(),
            "adapter_state_dict": None if adapter is None else adapter.state_dict(),
        },
        output / "checkpoint.pt",
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one R50 method seed")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--method", choices=METHODS, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--device", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_method(
        args.config,
        method=args.method,
        seed=args.seed,
        device_name=args.device,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "method": result["method"],
                "seed": result["seed"],
                "macro_f1": result["metrics"]["macro_f1"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
