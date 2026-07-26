from __future__ import annotations

from scripts import build_r29_fresh_silver_cohort as builder


def test_partition_counts_and_row_cap_are_frozen() -> None:
    assert builder.r27.sha256_file(builder.PROTOCOL_PATH) == (
        builder.PROTOCOL_SHA256
    )
    assert builder.ACTIVE_COUNTS == {"train": 700, "dev": 200, "test": 300}
    assert builder.ROW_CAP == 12
    assert builder.LABELS == ("Stable", "Improved", "Worse")


def test_patient_partition_is_deterministic_and_disjoint() -> None:
    patients = [f"patient{index:08d}" for index in range(1500)]
    first = builder.choose_partitions(patients)
    second = builder.choose_partitions(reversed(patients))
    assert first == second
    assert sum(value == "train" for value in first.values()) == 700
    assert sum(value == "dev" for value in first.values()) == 200
    assert sum(value == "test" for value in first.values()) == 300


def test_scene_and_dicom_parsing_contract() -> None:
    path = "mimic/p10/p10000001/s50000001/abc-def.jpg"
    assert builder.dicom_from_parent(path) == "abc-def"
    assert builder.scene_name("abc-def") == (
        "scene_graph/abc-def_SceneGraph.json"
    )
