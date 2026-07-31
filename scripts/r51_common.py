from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from scripts.build_prta_gen_r40b_smoke_cohort import read_json


WORKSPACE = Path(__file__).resolve().parents[1]
PRECACHE_STATUS = "FROZEN_PRTA_GEN_R51_MATCHED_INTERFACE_PRECACHE"
FROZEN_STATUS = "FROZEN_PRTA_GEN_R51_MATCHED_INTERFACE"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def verify_file(path: Path, expected_bytes: int, expected_sha256: str) -> None:
    if (
        not path.is_file()
        or path.stat().st_size != expected_bytes
        or sha256_file(path) != expected_sha256
    ):
        raise PermissionError(f"R51 authority drift: {path}")


def validate_authority(
    config_path: Path, *, require_pinned_caches: bool
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    config = read_json(config_path)
    allowed = {FROZEN_STATUS} if require_pinned_caches else {PRECACHE_STATUS, FROZEN_STATUS}
    if config.get("status") not in allowed:
        raise PermissionError("R51 benchmark config status is not authorized")
    authority = config["authority"]
    for prefix in ("roster_config", "r49_config", "r50_config"):
        verify_file(
            WORKSPACE / authority[prefix],
            int(authority[f"{prefix}_bytes"]),
            str(authority[f"{prefix}_sha256"]),
        )
    for prefix in ("evaluation_roster", "training_roster"):
        verify_file(
            Path(authority[prefix]),
            int(authority[f"{prefix}_bytes"]),
            str(authority[f"{prefix}_sha256"]),
        )
    evaluation_roster = read_json(Path(authority["evaluation_roster"]))
    training_roster = read_json(Path(authority["training_roster"]))
    if (
        evaluation_roster.get("status") != authority["evaluation_roster_status"]
        or training_roster.get("status") != authority["training_roster_status"]
        or evaluation_roster.get("evaluation_model_outcomes_read") is not False
        or evaluation_roster.get("patient_sets_disjoint") is not True
    ):
        raise PermissionError("R51 roster receipt drift")
    training_rows = list(
        training_roster["partitions"][authority["training_partition"]]["rows"]
    )
    evaluation_rows = list(
        evaluation_roster["partitions"][authority["evaluation_partition"]]["rows"]
    )
    train_patients = {str(row["patient_id"]) for row in training_rows}
    eval_patients = {str(row["patient_id"]) for row in evaluation_rows}
    if (
        len(training_rows) != int(authority["training_rows"])
        or len(evaluation_rows) != int(authority["evaluation_rows"])
        or len(train_patients) != len(training_rows)
        or len(eval_patients) != len(evaluation_rows)
        or train_patients & eval_patients
    ):
        raise PermissionError("R51 train/evaluation patient contract drift")
    translation = config["translation"]
    if (
        translation["token_shape"] != [64, 768]
        or translation["active_positions"] != [0, 60]
        or translation["reserved_zero_positions"] != [60, 64]
        or int(translation["trainable_parameters"]) != 0
        or len(translation["tila_patch_positions_zero_based"]) != 60
        or len(translation["b2_patch_positions_with_cls_offset"]) != 15
    ):
        raise PermissionError("R51 translation contract drift")
    model = config["model"]
    model_root = Path(model["path"])
    for name, bytes_key, hash_key in (
        ("config.json", "config_bytes", "config_sha256"),
        ("preprocessor_config.json", "preprocessor_config_bytes", "preprocessor_config_sha256"),
        ("model.safetensors.index.json", "weight_index_bytes", "weight_index_sha256"),
    ):
        verify_file(model_root / name, int(model[bytes_key]), str(model[hash_key]))
    cache = config["cache"]
    verify_file(
        WORKSPACE / cache["source_candidate"],
        int(cache["source_candidate_bytes"]),
        str(cache["source_candidate_sha256"]),
    )
    verify_file(
        Path(cache["text_cache"]),
        int(cache["text_cache_bytes"]),
        str(cache["text_cache_sha256"]),
    )
    verify_file(
        Path(config["external_methods"]["tila"]["local_model_root"])
        / config["external_methods"]["tila"]["weights_filename"],
        int(config["external_methods"]["tila"]["weights_bytes"]),
        str(config["external_methods"]["tila"]["weights_sha256"]),
    )
    for name, source in config["token_sources"].items():
        if source["bytes"] is None or source["sha256"] is None:
            if require_pinned_caches:
                raise PermissionError(f"R51 token source is unpinned: {name}")
            continue
        verify_file(Path(source["path"]), int(source["bytes"]), str(source["sha256"]))
        index = read_json(Path(source["path"]))
        if index.get("status") != source["status"]:
            raise PermissionError(f"R51 token source status drift: {name}")
    return config, training_rows, evaluation_rows
