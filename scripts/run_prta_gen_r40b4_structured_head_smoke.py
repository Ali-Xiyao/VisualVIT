from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import torch
import torch.nn.functional as F

from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from scripts.run_prta_gen_r40b_overfit_smoke import load_selected_tokens
from visualvit.prta_gen import (
    PROGRESSION_CLASSES,
    ProgressionDecisionHead,
    exact64_semantic_mean_features,
)


CONFIG_STATUS = "FROZEN_PRTA_GEN_R40B4_STRUCTURED_HEAD_SMOKE"
COHORT_STATUS = "PASS_PRTA_GEN_R40B4_SMOKE_COHORT"


def structured_text(finding: str, progression: str) -> str:
    return json.dumps(
        {"finding": finding, "progression": progression},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def run_smoke(
    *,
    config_path: Path,
    cohort_path: Path,
    device_name: str,
) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R40B.4 config is not frozen")
    cohort = read_json(cohort_path)
    if (
        cohort.get("status") != COHORT_STATUS
        or cohort.get("protocol_id") != config["protocol_id"]
        or cohort.get("row_count") != int(config["source"]["rows"])
        or cohort.get("excluded_parent_patient_count") != 128
        or cohort.get("excluded_parent_patients_absent") is not True
        or cohort.get("protected_300_dev_read") is not False
        or cohort.get("revealed_483_test_read") is not False
        or cohort.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("R40B.4 cohort receipt drift")
    output_root = Path(config["runtime"]["root"])
    if output_root.exists():
        raise FileExistsError(f"R40B.4 output must be fresh: {output_root}")
    token_index = read_json(Path(config["source"]["token_index"]))
    if (
        token_index.get("status") != config["source"]["required_token_status"]
        or token_index.get("scope") != "training"
        or token_index.get("labels_in_cache") is not False
        or token_index.get("sentences_in_cache") is not False
        or token_index.get("revealed_483_test_read") is not False
        or token_index.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("R40B.4 token-cache firewall drift")
    rows = list(cohort["rows"])
    loaded = load_selected_tokens(
        token_index,
        {str(row["example_id"]) for row in rows},
        token_key=str(config["source"]["token_variant"]),
    )
    patient_receipt = loaded.pop("_patient_receipt")  # type: ignore[arg-type]
    finding_receipt = loaded.pop("_finding_receipt")  # type: ignore[arg-type]
    for row in rows:
        example_id = row["example_id"]
        if (
            patient_receipt[example_id] != row["patient_id"]
            or finding_receipt[example_id] != row["finding"]
        ):
            raise ValueError("R40B.4 cohort/token alignment drift")
    device = torch.device(device_name)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("R40B.4 smoke requires CUDA")
    torch.cuda.set_device(device)
    torch.cuda.reset_peak_memory_stats(device)
    training = config["training"]
    seed = int(training["seed"])
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    token_tensor = torch.stack(
        [loaded[row["example_id"]] for row in rows]
    ).to(device=device, dtype=torch.float32)
    features = exact64_semantic_mean_features(token_tensor)
    if tuple(features.shape) != (
        len(rows),
        int(config["head"]["input_width"]),
    ):
        raise ValueError("R40B.4 semantic feature-width drift")
    feature_mean = features.mean(dim=0, keepdim=True)
    feature_std = features.std(dim=0, unbiased=False, keepdim=True).clamp_min(
        1e-6
    )
    normalized = (features - feature_mean) / feature_std
    class_to_index = {
        label: index for index, label in enumerate(PROGRESSION_CLASSES)
    }
    labels = torch.tensor(
        [class_to_index[row["progression"]] for row in rows],
        dtype=torch.long,
        device=device,
    )
    head = ProgressionDecisionHead(
        input_width=int(config["head"]["input_width"]),
        hidden_width=int(config["head"]["hidden_width"]),
        class_count=int(config["head"]["class_count"]),
    ).to(device)
    parameter_count = sum(parameter.numel() for parameter in head.parameters())
    if parameter_count != int(config["head"]["parameter_count"]):
        raise ValueError("R40B.4 parameter-count drift")
    optimizer = torch.optim.AdamW(
        head.parameters(),
        lr=float(training["learning_rate"]),
        weight_decay=float(training["weight_decay"]),
    )
    with torch.no_grad():
        initial_loss = float(F.cross_entropy(head(normalized), labels).cpu())
    history = []
    head.train()
    for epoch in range(1, int(training["epochs"]) + 1):
        logits = head(normalized)
        loss = F.cross_entropy(logits, labels)
        if not bool(torch.isfinite(loss)):
            raise FloatingPointError("non-finite R40B.4 loss")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(
            head.parameters(), float(training["gradient_clip_norm"])
        )
        optimizer.step()
        if epoch % 100 == 0 or epoch == int(training["epochs"]):
            history.append({"epoch": epoch, "loss": float(loss.detach().cpu())})
    head.eval()
    with torch.no_grad():
        logits = head(normalized)
        final_loss = float(F.cross_entropy(logits, labels).cpu())
        predictions = logits.argmax(dim=-1)
    accuracy = float(predictions.eq(labels).float().mean().cpu())
    outputs = []
    for row, prediction in zip(rows, predictions.tolist(), strict=True):
        progression = PROGRESSION_CLASSES[int(prediction)]
        text = structured_text(row["finding"], progression)
        parsed = json.loads(text)
        outputs.append(
            {
                "example_id": row["example_id"],
                "generated_text": text,
                "schema_valid": list(parsed) == ["finding", "progression"],
                "finding_correct": parsed["finding"] == row["finding"],
                "progression_correct": progression == row["progression"],
                "expected_progression": row["progression"],
                "selected_progression": progression,
            }
        )
    schema_validity = sum(row["schema_valid"] for row in outputs) / len(outputs)
    finding_accuracy = sum(row["finding_correct"] for row in outputs) / len(outputs)
    progression_accuracy = (
        sum(row["progression_correct"] for row in outputs) / len(outputs)
    )
    gate = config["gate"]
    passed = bool(
        math.isfinite(initial_loss)
        and math.isfinite(final_loss)
        and final_loss / initial_loss
        <= float(gate["final_to_initial_loss_ratio_at_most"])
        and accuracy == float(gate["training_progression_accuracy"])
        and schema_validity == float(gate["structured_schema_validity"])
        and finding_accuracy
        == float(gate["structured_finding_echo_accuracy"])
        and progression_accuracy
        == float(gate["structured_progression_accuracy"])
    )
    status = (
        config["result_statuses"]["pass"]
        if passed
        else config["result_statuses"]["stop"]
    )
    output_root.mkdir(parents=True, exist_ok=False)
    checkpoint_path = output_root / "checkpoint.pt"
    torch.save(
        {
            "schema": "visualvit.prta-gen.r40b4-head-checkpoint.v1",
            "head": head.state_dict(),
            "feature_mean": feature_mean.cpu(),
            "feature_std": feature_std.cpu(),
            "classes": PROGRESSION_CLASSES,
        },
        checkpoint_path,
    )
    result = {
        "schema": "visualvit.prta-gen.r40b4-structured-head-result.v1",
        "status": status,
        "protocol_id": config["protocol_id"],
        "rows": len(rows),
        "patients": len({row["patient_id"] for row in rows}),
        "parameter_count": parameter_count,
        "initial_loss": initial_loss,
        "final_loss": final_loss,
        "final_to_initial_loss_ratio": final_loss / initial_loss,
        "training_progression_accuracy": accuracy,
        "structured": {
            "schema_validity": schema_validity,
            "finding_echo_accuracy": finding_accuracy,
            "progression_accuracy": progression_accuracy,
        },
        "outputs": outputs,
        "history": history,
        "checkpoint": str(checkpoint_path),
        "checkpoint_bytes": checkpoint_path.stat().st_size,
        "exact64_tokens_used": True,
        "semantic_layout": "4/12/16/16/12/4",
        "reserved_positions_used": False,
        "pixel_inputs_used": False,
        "qwen_free_generation_unlocked": False,
        "progression_structured_route_unlocked": passed,
        "laterality_generation_unlocked": False,
        "anatomy_generation_unlocked": False,
        "degree_generation_unlocked": False,
        "evidence_generation_unlocked": False,
        "r41_qwen_sft_unlocked": False,
        "scientific_claim_allowed": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(device),
    }
    write_json(output_root / "result.json", result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the R40B.4 structured progression-head smoke"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--device", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_smoke(
        config_path=args.config,
        cohort_path=args.cohort,
        device_name=args.device,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return (
        0
        if result["status"]
        == "PASS_PRTA_GEN_R40B4_STRUCTURED_HEAD_SMOKE"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
