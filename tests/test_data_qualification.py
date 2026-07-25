import json
import shutil
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest

from visualvit.data_qualification import (
    MANIFEST_SCHEMA_V1,
    MANIFEST_SCHEMA_VERSION,
    normalize_identifier,
    qualify_longitudinal_assets,
    sha256_file,
    write_audit_json,
)


@pytest.fixture
def safe_tmp_path():
    path = Path.cwd() / "artifacts" / "test_tmp_dataqual" / uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path)


def _source(source_id: str = "MIMIC_CXR") -> dict[str, object]:
    return {
        "source_id": source_id,
        "license_status": "verified",
        "license_reference": "fixture-license",
        "dua_status": "signed",
        "dua_reference": "fixture-dua",
        "authorized": True,
    }


def _record(
    path: Path,
    *,
    source_id: str = "MIMIC_CXR",
    lineage_source_id: str = "MIMIC CXR",
    patient_id: str = "P001",
    study_id: str = "S001",
    image_id: str = "IMG001",
    split: str = "train",
    expected_hash: str | None = None,
) -> dict[str, object]:
    record: dict[str, object] = {
        "source_id": source_id,
        "lineage_source_id": lineage_source_id,
        "patient_id": patient_id,
        "study_id": study_id,
        "image_id": image_id,
        "split": split,
        "file_path": path.name,
    }
    if expected_hash is not None:
        record["sha256"] = expected_hash
    return record


def _manifest(records: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "sources": [_source()],
        "records": records,
        "images_to_avoid": [],
    }


def test_manifest_schema_and_identifier_normalization_are_explicit():
    assert MANIFEST_SCHEMA_V1["$id"] == MANIFEST_SCHEMA_VERSION
    assert set(MANIFEST_SCHEMA_V1["required"]) == {
        "schema_version",
        "sources",
        "records",
        "images_to_avoid",
    }
    assert normalize_identifier(" Ｐatient_００１ ", kind="patient_id") == "patient-001"
    assert normalize_identifier(7, kind="study_id") == "7"
    with pytest.raises(ValueError):
        normalize_identifier(True, kind="patient_id")
    with pytest.raises(ValueError):
        normalize_identifier("---", kind="image_id")


def test_valid_fixture_is_hashed_normalized_and_sealed_deterministically(
    safe_tmp_path,
):
    train_image = safe_tmp_path / "train.bin"
    dev_image = safe_tmp_path / "dev.bin"
    train_image.write_bytes(b"train-fixture")
    dev_image.write_bytes(b"dev-fixture")
    records = [
        _record(
            train_image,
            expected_hash=sha256_file(train_image).upper(),
        ),
        _record(
            dev_image,
            patient_id=" P-002 ",
            study_id="S_002",
            image_id="IMG 002",
            split="dev",
        ),
    ]
    report = qualify_longitudinal_assets(_manifest(records), base_dir=safe_tmp_path)

    assert report["status"] == "PASS"
    assert report["qualified"] is True
    assert report["formal_use_allowed"] is True
    assert all(report["checks"].values())
    assert set(report["sealed_splits"]) == {"train", "dev"}
    assert len(report["sealed_split_hash"]) == 64
    assert report["records"][0]["patient_id"] == "p-002"
    assert report["records"][1]["source_id"] == "mimic-cxr"
    assert report["records"][1]["sha256"] == sha256_file(train_image)

    reversed_manifest = _manifest(list(reversed(records)))
    reversed_report = qualify_longitudinal_assets(
        reversed_manifest,
        base_dir=safe_tmp_path,
    )
    assert reversed_report["sealed_split_hash"] == report["sealed_split_hash"]
    assert reversed_report["sealed_splits"] == report["sealed_splits"]
    assert (
        reversed_report["qualification_input_hash"]
        == report["qualification_input_hash"]
    )


def test_cross_split_patient_and_content_overlap_fail_closed(safe_tmp_path):
    train_image = safe_tmp_path / "train.bin"
    test_image = safe_tmp_path / "test.bin"
    train_image.write_bytes(b"same-content")
    test_image.write_bytes(b"same-content")
    manifest = _manifest(
        [
            _record(train_image, patient_id="Patient 9"),
            _record(
                test_image,
                patient_id="patient_9",
                study_id="S009",
                image_id="IMG009",
                split="test",
            ),
        ]
    )
    report = qualify_longitudinal_assets(manifest, base_dir=safe_tmp_path)

    types = {item["identity_type"] for item in report["duplicates"]["cross_split"]}
    assert {"patient", "sha256"} <= types
    assert report["checks"]["no_cross_split_duplicates"] is False
    assert report["status"] == "FAIL"
    assert report["sealed_split_hash"] is None


def test_cross_source_lineage_and_hash_overlap_fail_closed(safe_tmp_path):
    left = safe_tmp_path / "left.bin"
    right = safe_tmp_path / "right.bin"
    left.write_bytes(b"same-pixel")
    right.write_bytes(b"same-pixel")
    manifest = _manifest(
        [
            _record(left, source_id="CheXTemporal"),
            _record(
                right,
                source_id="Chest-ImaGenome",
                study_id="S002",
                image_id="IMG002",
            ),
        ]
    )
    manifest["sources"] = [_source("CheXTemporal"), _source("Chest ImaGenome")]
    report = qualify_longitudinal_assets(manifest, base_dir=safe_tmp_path)

    types = {item["identity_type"] for item in report["duplicates"]["cross_source"]}
    assert {"patient", "sha256"} <= types
    assert report["checks"]["no_cross_source_duplicates"] is False
    assert report["status"] == "FAIL"


def test_same_split_source_content_duplicate_with_distinct_ids_fails_closed(
    safe_tmp_path,
):
    first = safe_tmp_path / "first.bin"
    second = safe_tmp_path / "second.bin"
    first.write_bytes(b"duplicate-pixel")
    second.write_bytes(b"duplicate-pixel")
    manifest = _manifest(
        [
            _record(first),
            _record(
                second,
                patient_id="P002",
                study_id="S002",
                image_id="IMG002",
            ),
        ]
    )
    report = qualify_longitudinal_assets(manifest, base_dir=safe_tmp_path)

    assert report["duplicates"]["cross_split"] == []
    assert report["duplicates"]["cross_source"] == []
    assert report["duplicates"]["exact_records"] == []
    assert len(report["duplicates"]["content"]) == 1
    assert report["checks"]["unique_file_contents"] is False
    assert "CONTENT_DUPLICATE" in {error["code"] for error in report["errors"]}
    assert report["status"] == "FAIL"


def test_images_to_avoid_matches_normalized_lineage_identity(safe_tmp_path):
    image = safe_tmp_path / "image.bin"
    image.write_bytes(b"fixture")
    manifest = _manifest([_record(image, image_id="IMG_001")])
    manifest["images_to_avoid"] = [
        {"lineage_source_id": "mimic-cxr", "image_id": "img 001"}
    ]
    report = qualify_longitudinal_assets(manifest, base_dir=safe_tmp_path)

    assert report["checks"]["images_to_avoid_excluded"] is False
    assert "IMAGE_TO_AVOID" in {error["code"] for error in report["errors"]}
    assert report["sealed_splits"] == {}


def test_qualification_input_hash_covers_authorization_and_avoid_metadata(
    safe_tmp_path,
):
    image = safe_tmp_path / "image.bin"
    image.write_bytes(b"fixture")
    original = _manifest([_record(image)])
    baseline = qualify_longitudinal_assets(original, base_dir=safe_tmp_path)

    changed_license = deepcopy(original)
    changed_license["sources"][0]["license_reference"] = "new-license-pin"
    license_report = qualify_longitudinal_assets(
        changed_license,
        base_dir=safe_tmp_path,
    )
    changed_dua = deepcopy(original)
    changed_dua["sources"][0]["dua_reference"] = "new-dua-pin"
    dua_report = qualify_longitudinal_assets(changed_dua, base_dir=safe_tmp_path)
    changed_authorization = deepcopy(original)
    changed_authorization["sources"][0]["authorized"] = False
    authorization_report = qualify_longitudinal_assets(
        changed_authorization,
        base_dir=safe_tmp_path,
    )
    changed_avoid = deepcopy(original)
    changed_avoid["images_to_avoid"] = [
        {"lineage_source_id": "mimic-cxr", "image_id": "unrelated-image"}
    ]
    avoid_report = qualify_longitudinal_assets(
        changed_avoid,
        base_dir=safe_tmp_path,
    )
    changed_record = deepcopy(original)
    changed_record["records"][0]["patient_id"] = "P999"
    record_report = qualify_longitudinal_assets(
        changed_record,
        base_dir=safe_tmp_path,
    )

    assert baseline["status"] == license_report["status"] == dua_report["status"]
    assert record_report["status"] == avoid_report["status"] == "PASS"
    assert authorization_report["status"] == "FAIL"
    assert baseline["sealed_split_hash"] == license_report["sealed_split_hash"]
    assert (
        baseline["qualification_input_hash"]
        != license_report["qualification_input_hash"]
    )
    assert (
        baseline["qualification_input_hash"] != dua_report["qualification_input_hash"]
    )
    assert (
        baseline["qualification_input_hash"]
        != authorization_report["qualification_input_hash"]
    )
    assert (
        baseline["qualification_input_hash"] != avoid_report["qualification_input_hash"]
    )
    assert (
        baseline["qualification_input_hash"]
        != record_report["qualification_input_hash"]
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("license_status", "unknown"),
        ("license_reference", ""),
        ("dua_status", "pending"),
        ("dua_reference", None),
        ("authorized", "true"),
    ],
)
def test_license_and_dua_qualification_is_fail_closed(safe_tmp_path, field, value):
    image = safe_tmp_path / "image.bin"
    image.write_bytes(b"fixture")
    manifest = _manifest([_record(image)])
    manifest["sources"][0][field] = value
    report = qualify_longitudinal_assets(manifest, base_dir=safe_tmp_path)

    assert report["checks"]["source_license_dua_authorized"] is False
    assert report["formal_use_allowed"] is False
    assert report["sealed_split_hash"] is None


def test_missing_file_and_hash_mismatch_are_reported_without_a_partial_seal(
    safe_tmp_path,
):
    existing = safe_tmp_path / "existing.bin"
    existing.write_bytes(b"fixture")
    missing = safe_tmp_path / "missing.bin"
    manifest = _manifest(
        [
            _record(existing, expected_hash="0" * 64),
            _record(
                missing,
                patient_id="P002",
                study_id="S002",
                image_id="IMG002",
            ),
        ]
    )
    report = qualify_longitudinal_assets(manifest, base_dir=safe_tmp_path)

    error_codes = {error["code"] for error in report["errors"]}
    assert {"HASH_MISMATCH", "FILE_MISSING"} <= error_codes
    assert report["checks"]["all_files_present_and_hashed"] is False
    assert report["checks"]["expected_hashes_match"] is False
    assert report["sealed_split_hash"] is None


def test_audit_json_round_trip_preserves_seal(safe_tmp_path):
    image = safe_tmp_path / "image.bin"
    image.write_bytes(b"fixture")
    report = qualify_longitudinal_assets(
        _manifest([_record(image)]),
        base_dir=safe_tmp_path,
    )
    output = safe_tmp_path / "audit" / "qualification.json"
    write_audit_json(report, output)

    loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded["status"] == "PASS"
    assert loaded["sealed_split_hash"] == report["sealed_split_hash"]
    assert output.read_bytes().endswith(b"\n")


def test_missing_images_to_avoid_declaration_is_not_silently_defaulted(
    safe_tmp_path,
):
    image = safe_tmp_path / "image.bin"
    image.write_bytes(b"fixture")
    manifest = _manifest([_record(image)])
    del manifest["images_to_avoid"]
    report = qualify_longitudinal_assets(
        deepcopy(manifest),
        base_dir=safe_tmp_path,
    )

    assert report["checks"]["manifest_schema_valid"] is False
    assert report["status"] == "FAIL"
