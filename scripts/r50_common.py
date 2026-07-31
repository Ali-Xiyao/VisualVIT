from __future__ import annotations

import hashlib
import json
from pathlib import Path
import random
from typing import Any, Iterable

import torch

from scripts.audit_prta_gen_r44_independent_support import sha256_file
from visualvit.prta import PROGRESSION_LABELS
from visualvit.qualification import macro_f1


WORKSPACE = Path(__file__).resolve().parents[1]
CONFIG_STATUS = "FROZEN_PRTA_GEN_R50_METHOD_BENCHMARK"
METHODS = (
    "tila_ce",
    "tila_bice_tcl",
    "siamese_signed_abs",
    "tac_temporal_fusion_adapted",
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )


def verify_file(path: Path, expected_bytes: int, expected_sha256: str) -> None:
    if (
        not path.is_file()
        or path.stat().st_size != int(expected_bytes)
        or sha256_file(path) != str(expected_sha256).upper()
    ):
        raise PermissionError(f"R50 authority drift: {path}")


def partition_rows(
    roster: dict[str, Any], partitions: Iterable[str]
) -> list[dict[str, Any]]:
    rows = [
        row
        for partition in partitions
        for row in roster["partitions"][str(partition)]["rows"]
    ]
    patients = [str(row["patient_id"]) for row in rows]
    if len(patients) != len(set(patients)):
        raise PermissionError("R50 requires one row per patient")
    return rows


def validate_authority(
    config_path: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R50 config is not frozen")
    if tuple(config["methods"]) != METHODS:
        raise PermissionError("R50 method registry drift")
    authority = config["authority"]
    r49_path = WORKSPACE / authority["r49_config"]
    verify_file(
        r49_path,
        authority["r49_config_bytes"],
        authority["r49_config_sha256"],
    )
    roster_path = Path(authority["r49_roster"])
    verify_file(
        roster_path,
        authority["r49_roster_bytes"],
        authority["r49_roster_sha256"],
    )
    roster = read_json(roster_path)
    if (
        roster.get("status") != authority["r49_roster_status"]
        or roster.get("one_row_per_patient") is not True
        or roster.get("patient_sets_disjoint") is not True
    ):
        raise PermissionError("R50 roster metadata drift")
    training_rows = partition_rows(
        roster, [str(authority["training_partition"])]
    )
    evaluation_rows = partition_rows(
        roster, [str(value) for value in authority["evaluation_partitions"]]
    )
    if (
        len(training_rows) != int(authority["training_rows"])
        or len(evaluation_rows) != int(authority["evaluation_rows"])
        or {str(row["patient_id"]) for row in training_rows}
        & {str(row["patient_id"]) for row in evaluation_rows}
    ):
        raise PermissionError("R50 roster row contract drift")
    required = {
        "example_id",
        "patient_id",
        "prior_image_id",
        "current_image_id",
        "prior_path",
        "current_path",
        "finding",
        "progression",
    }
    for row in training_rows + evaluation_rows:
        if not required.issubset(row):
            raise PermissionError("R50 roster schema drift")
        if str(row["progression"]) not in PROGRESSION_LABELS:
            raise PermissionError("R50 progression label drift")
    labels = [str(row["progression"]) for row in training_rows + evaluation_rows]
    if {label: labels.count(label) for label in PROGRESSION_LABELS} != {
        label: 650 for label in PROGRESSION_LABELS
    }:
        raise PermissionError("R50 frozen full-roster class balance drift")
    for reference in config["r49_references"].values():
        verify_file(
            Path(reference["path"]),
            reference["bytes"],
            reference["sha256"],
        )
    cache = config["cache"]
    verify_file(
        Path(cache["naive_token_index"]),
        cache["naive_token_index_bytes"],
        cache["naive_token_index_sha256"],
    )
    return config, roster, training_rows, evaluation_rows


def epoch_order(
    rows: list[dict[str, Any]], *, namespace: str, seed: int, epoch: int
) -> list[int]:
    values = list(range(len(rows)))
    keyed_seed = int.from_bytes(
        hashlib.sha256(f"{namespace}|{seed}|{epoch}".encode()).digest()[:8],
        byteorder="big",
    )
    random.Random(keyed_seed).shuffle(values)
    return values


def finding_registry(
    training_rows: list[dict[str, Any]],
    evaluation_rows: list[dict[str, Any]],
) -> tuple[list[str], dict[str, int]]:
    findings = sorted(
        {str(row["finding"]) for row in training_rows + evaluation_rows}
    )
    return findings, {value: index for index, value in enumerate(findings)}


def row_tensors(
    rows: list[dict[str, Any]],
    *,
    finding_to_index: dict[str, int],
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor]:
    findings = torch.tensor(
        [finding_to_index[str(row["finding"])] for row in rows],
        dtype=torch.long,
        device=device,
    )
    label_to_index = {
        label: index for index, label in enumerate(PROGRESSION_LABELS)
    }
    targets = torch.tensor(
        [label_to_index[str(row["progression"])] for row in rows],
        dtype=torch.long,
        device=device,
    )
    return findings, targets


def load_naive_tokens(
    index_path: Path,
    rows: list[dict[str, Any]],
) -> torch.Tensor:
    index = read_json(index_path)
    requested = [str(row["example_id"]) for row in rows]
    positions = {value: index for index, value in enumerate(requested)}
    result = torch.empty((len(rows), 64, 768), dtype=torch.float16)
    seen: set[str] = set()
    for shard in index["shards"]:
        payload = torch.load(
            shard["path"], map_location="cpu", weights_only=True
        )
        for source_index, example_id in enumerate(payload["example_ids"]):
            key = str(example_id)
            if key not in positions:
                continue
            if key in seen:
                raise PermissionError("R50 duplicate naive-token row")
            result[positions[key]].copy_(payload["naive_tokens"][source_index])
            seen.add(key)
    if seen != set(requested) or torch.count_nonzero(result[:, 60:]).item():
        raise PermissionError("R50 naive-token coverage/layout drift")
    return result


def prediction_metrics(
    targets: list[int], predictions: list[int]
) -> dict[str, Any]:
    if len(targets) != len(predictions):
        raise ValueError("R50 metric row lengths differ")
    per_class_recall: dict[str, float] = {}
    for index, label in enumerate(PROGRESSION_LABELS):
        positions = [i for i, value in enumerate(targets) if value == index]
        per_class_recall[label] = sum(
            predictions[i] == index for i in positions
        ) / len(positions)
    return {
        "macro_f1": macro_f1(
            targets, predictions, class_count=len(PROGRESSION_LABELS)
        ),
        "accuracy": sum(a == b for a, b in zip(targets, predictions))
        / len(targets),
        "per_class_recall": per_class_recall,
    }
