from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import torch

from visualvit.hierarchical_temporal_tokens import fixed_token_types
from visualvit.schemas import TokenBundle


WORKSPACE = Path(__file__).resolve().parents[1]
DEFAULT_R39_CONFIG = (
    WORKSPACE / "configs" / "r39" / "r39_frozen_vlm_transfer_v1.json"
)
TARGET_TO_VLM = {
    "Stable": 0,
    "Worse": 1,
    "Improved": 2,
    "New": 3,
    "Resolved": 4,
}


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True), encoding="utf-8"
    )


def load_r39_config(path: Path = DEFAULT_R39_CONFIG) -> dict[str, Any]:
    config = read_json(path)
    if config.get("status") != "FROZEN_R39_TRANSFER_AFTER_R38_GO":
        raise PermissionError("R39 configuration is not frozen")
    if config.get("candidate_id") != "r37-1-a6-three-seed-v1":
        raise ValueError("R39 candidate drift")
    if config["training"] != {
        "source": "r37c_300_dev_already_revealed_after_candidate_freeze",
        "patients": 300,
        "rows": 2453,
        "seeds": [17, 29, 43],
        "epochs": 1,
        "batch_size": 1,
        "gradient_accumulation": 32,
        "effective_batch_size": 32,
        "learning_rate": 0.0001,
        "weight_decay": 0.01,
        "loss": {
            "a6_selected": 1.0,
            "a0_frozen_difference": 0.25,
        },
        "order": "sha256_r39_projector_order_v1_seed_record_id",
        "class_patient_balanced_loss": True,
        "early_stopping": False,
        "seed_selection": False,
        "retain_all_three_projectors": True,
    }:
        raise ValueError("R39 training contract drift")
    if (
        config["model"]["all_frozen"] is not True
        or config["interface"]["token_budget"] != 64
        or config["interface"]["projector_parameter_count"] != 7_948_800
        or config["interface"]["pixel_bypass"] is not False
        or config["interface"]["pixel_inputs_used"] is not False
        or config["sealed_test"]["reveal_count"] != 1
    ):
        raise PermissionError("R39 model/interface firewall drift")
    upstream = read_json(Path(config["upstream_r38"]))
    if (
        upstream.get("status") != config["required_upstream_status"]
        or upstream.get("scientific_go") is not True
        or upstream.get("r39_unlocked") is not True
        or upstream.get("sealed_483_test_read") is not False
        or upstream.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("R39 upstream GO/firewall drift")
    return config


def stable_order(seed: int, record_id: str) -> str:
    return hashlib.sha256(
        f"r39-projector-order-v1|{seed}|{record_id}".encode()
    ).hexdigest()


def patient_class_weights(rows: list[dict[str, Any]]) -> list[float]:
    labels = Counter(str(row["label"]) for row in rows)
    patients = Counter(str(row["patient_id"]) for row in rows)
    if set(labels) != set(TARGET_TO_VLM):
        raise ValueError("R39 training requires all five labels")
    raw = [
        1.0 / (labels[str(row["label"])] * patients[str(row["patient_id"])])
        for row in rows
    ]
    mean = sum(raw) / len(raw)
    return [value / mean for value in raw]


def prior_shuffle_assignment(
    rows: list[dict[str, Any]], *, seed: int
) -> dict[str, str]:
    """Assign an outcome-free mismatched prior within each finding."""

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["finding"]), []).append(row)
    result: dict[str, str] = {}
    for finding_rows in grouped.values():
        ordered = sorted(
            finding_rows,
            key=lambda row: stable_order(seed, str(row["record_id"])),
        )
        patient_count = len({str(row["patient_id"]) for row in ordered})
        if patient_count < 2:
            raise ValueError("prior shuffle requires at least two patients")
        for index, row in enumerate(ordered):
            for offset in range(1, len(ordered) + 1):
                candidate = ordered[(index + offset) % len(ordered)]
                if str(candidate["patient_id"]) != str(row["patient_id"]):
                    result[str(row["record_id"])] = str(
                        candidate["prior_dicom_id"]
                    )
                    break
            else:
                raise RuntimeError("unable to assign a cross-patient prior")
    if len(result) != len(rows):
        raise RuntimeError("prior shuffle assignment is incomplete")
    return result


def build_prompt(
    tokenizer: Any,
    *,
    template: str,
    finding: str,
    placeholder_token_id: int,
) -> torch.Tensor:
    prefix = tokenizer(
        template.format(finding=finding),
        add_special_tokens=True,
    )["input_ids"]
    suffix = tokenizer(
        "\nAnswer:",
        add_special_tokens=False,
    )["input_ids"]
    ids = [*prefix, *([placeholder_token_id] * 64), *suffix]
    prompt = torch.tensor([ids], dtype=torch.long)
    if int(prompt.eq(placeholder_token_id).sum()) != 64:
        raise RuntimeError("R39 prompt does not contain exactly 64 placeholders")
    return prompt


def token_bundle(tokens: torch.Tensor) -> TokenBundle:
    if tokens.ndim != 3 or tuple(tokens.shape[1:]) != (64, 768):
        raise ValueError("R39 cached tokens must have shape [B,64,768]")
    batch = tokens.shape[0]
    valid = torch.ones(
        batch, 64, dtype=torch.bool, device=tokens.device
    )
    valid[:, 60:] = False
    return TokenBundle(
        tokens=tokens,
        token_types=fixed_token_types(tokens.device),
        valid_mask=valid,
        assignment=torch.zeros(batch, 1, 1, device=tokens.device),
    )


def iter_token_rows(index: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for shard_entry in index["shards"]:
        shard = torch.load(
            shard_entry["path"], map_location="cpu", weights_only=True
        )
        count = len(shard["record_ids"])
        for position in range(count):
            yield {
                "record_id": str(shard["record_ids"][position]),
                "patient_id": str(shard["patient_ids"][position]),
                "finding": str(shard["findings"][position]),
                "true_tokens": shard["true_tokens"][position],
                "current_tokens": shard["current_tokens"][position],
                "a0_tokens": shard["a0_tokens"][position],
                "shuffled_tokens": shard["shuffled_tokens"][position],
            }
