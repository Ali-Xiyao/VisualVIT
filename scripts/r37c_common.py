from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


WORKSPACE = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = (
    WORKSPACE / "configs" / "r37" / "r37_1_candidate_for_r37c_v1.json"
)
FROZEN_SEEDS = (17, 29, 43)
CANDIDATE_STATUS = "FROZEN_R37_1_A6_THREE_SEED_CANDIDATE_FOR_R37C"
STRUCTURAL_FIELDS = (
    "record_id",
    "patient_id",
    "subject_id",
    "partition",
    "prior_study_id",
    "prior_dicom_id",
    "prior_path",
    "prior_view",
    "current_study_id",
    "current_dicom_id",
    "current_path",
    "current_view",
    "finding_token",
    "finding",
    "anatomy",
)


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True), encoding="utf-8"
    )


def load_candidate(path: Path = DEFAULT_CANDIDATE) -> dict[str, Any]:
    candidate = read_json(path)
    if candidate.get("status") != CANDIDATE_STATUS:
        raise PermissionError("R37C candidate is not frozen")
    if candidate.get("candidate_id") != "r37-1-a6-three-seed-v1":
        raise ValueError("R37C candidate identifier drift")
    if tuple(candidate.get("frozen_seeds", ())) != FROZEN_SEEDS:
        raise ValueError("R37C frozen seed drift")
    if candidate.get("frozen_variant") != "A6":
        raise ValueError("R37C requires the frozen A6 candidate")
    one_shot = candidate["r37c_one_shot"]
    expected = {
        "partition": "dev",
        "expected_patients": 300,
        "expected_rows": 2453,
        "bootstrap_replicates": 2000,
        "bootstrap_seed": 37001,
        "minimum_gain_pp": 2.0,
        "outcome_reveal_count": 1,
    }
    observed = {key: one_shot.get(key) for key in expected}
    if observed != expected:
        raise ValueError(
            f"R37C frozen one-shot contract drift: {observed}"
        )
    if candidate["firewall"] != {
        "sealed_483_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "r38_unlocked": False,
        "r39_unlocked": False,
    }:
        raise PermissionError("R37C firewall receipt drift")
    validate_internal_go(candidate)
    validate_checkpoint_receipts(candidate)
    return candidate


def validate_internal_go(candidate: dict[str, Any]) -> None:
    qualification = candidate["internal_qualification"]
    paths = (
        Path(qualification["current_only"]),
        Path(qualification["cmcp"]),
        Path(qualification["a6_vs_a0"]),
    )
    required = tuple(qualification["required_statuses"])
    observed = tuple(read_json(path).get("status") for path in paths)
    if observed != required:
        raise PermissionError(
            f"R37.1 internal GO receipt drift: {observed}"
        )


def validate_checkpoint_receipts(candidate: dict[str, Any]) -> None:
    for roster_name in ("a6_checkpoints", "a0_checkpoints"):
        entries = candidate[roster_name]
        if tuple(int(item["seed"]) for item in entries) != FROZEN_SEEDS:
            raise ValueError(f"{roster_name} seed roster drift")
        for item in entries:
            path = Path(item["path"])
            if not path.is_file():
                raise FileNotFoundError(path)
            if path.stat().st_size != int(item["bytes"]):
                raise ValueError(f"checkpoint byte-size drift: {path}")


def checkpoint_for(
    candidate: dict[str, Any], *, roster: str, seed: int
) -> Path:
    key = f"{roster}_checkpoints"
    matches = [
        item for item in candidate[key] if int(item["seed"]) == int(seed)
    ]
    if len(matches) != 1:
        raise ValueError(f"missing unique {roster} checkpoint for seed {seed}")
    return Path(matches[0]["path"])


def structural_projection(
    rows: Iterable[dict[str, Any]], *, partition: str
) -> list[dict[str, Any]]:
    projected = []
    for row in rows:
        if str(row.get("partition")) != partition:
            continue
        missing = [key for key in STRUCTURAL_FIELDS if key not in row]
        if missing:
            raise ValueError(f"R37C structural row missing fields: {missing}")
        projected.append({key: row[key] for key in STRUCTURAL_FIELDS})
    projected.sort(
        key=lambda item: (
            str(item["patient_id"]),
            str(item["record_id"]),
        )
    )
    return projected


def validate_dev_structure(
    rows: list[dict[str, Any]], candidate: dict[str, Any]
) -> None:
    one_shot = candidate["r37c_one_shot"]
    if len(rows) != int(one_shot["expected_rows"]):
        raise ValueError(
            f"R37C dev row drift: expected {one_shot['expected_rows']}, "
            f"got {len(rows)}"
        )
    patients = {str(row["patient_id"]) for row in rows}
    if len(patients) != int(one_shot["expected_patients"]):
        raise ValueError(
            "R37C dev patient drift: "
            f"expected {one_shot['expected_patients']}, got {len(patients)}"
        )
    record_ids = [str(row["record_id"]) for row in rows]
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("R37C dev record IDs are not unique")
    forbidden = ("progression", "label", "target", "prediction")
    leaked = sorted(
        key
        for row in rows
        for key in row
        if any(token in key.lower() for token in forbidden)
    )
    if leaked:
        raise PermissionError("protected fields leaked into structure")


def merge_structure_and_labels(
    structure: list[dict[str, Any]],
    label_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    labels = {}
    for item in label_rows:
        record_id = str(item["record_id"])
        if record_id in labels:
            raise ValueError(f"duplicate protected label: {record_id}")
        labels[record_id] = str(item["progression"])
    structure_ids = [str(item["record_id"]) for item in structure]
    if set(structure_ids) != set(labels):
        raise ValueError("R37C structure/label record alignment drift")
    return [
        {
            **item,
            "example_id": str(item["record_id"]),
            "label": labels[str(item["record_id"])],
        }
        for item in structure
    ]
