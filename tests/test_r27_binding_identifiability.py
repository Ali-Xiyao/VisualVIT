from __future__ import annotations

import ast
from collections import Counter
import hashlib
from pathlib import Path

import pytest

from scripts import audit_r26_binding_identifiability as r27
from scripts import verify_r27_binding_identifiability as verify_r27


def _record(
    qid: str,
    anatomy: str,
    progression: str,
    *,
    labels: tuple[str, ...] = ("a", "b", "c"),
    patient: str = "p1",
) -> dict[str, object]:
    boxes = [
        {"label": label, "x1": i, "y1": i, "x2": i + 1, "y2": i + 1}
        for i, label in enumerate(labels)
    ]
    return {
        "qualification_id": qid,
        "patient_id": patient,
        "prior_dicom_id": f"{patient}-prior",
        "current_dicom_id": f"{patient}-current",
        "prior_boxes": boxes,
        "current_boxes": boxes,
        "anatomy": anatomy,
        "progression": progression,
    }


def _b4_item(record: dict[str, object]) -> dict[str, object]:
    basis = "|".join(
        str(record[key])
        for key in ("patient_id", "prior_dicom_id", "current_dicom_id")
    )
    return {
        "qualification_id": record["qualification_id"],
        "pair_seed_basis": basis,
        "passed": True,
        "derangements": [
            {
                "derangement_id": value,
                "passed": True,
                "checks": {"zero_fixed_point": True},
            }
            for value in r27.DERANGEMENT_IDS
        ],
    }


def test_protocol_and_frozen_inputs_are_sha_pinned() -> None:
    assert r27.sha256_file(r27.PROTOCOL_PATH) == r27.PROTOCOL_SHA256
    for name, expected in r27.R26_INPUT_HASHES.items():
        assert r27.sha256_file(r27.R26_ROOT_DEFAULT / name) == expected


def test_frozen_r26_sources_match_registered_hashes() -> None:
    for relative, expected in r27.FROZEN_SOURCE_HASHES.items():
        assert r27.sha256_file(r27.WORKSPACE / relative) == expected


def test_bii_toy_examples() -> None:
    assert r27.bii_from_counts({"Stable": 3, "Improved": 0, "Worse": 0}) == 0
    assert r27.bii_from_counts({"Stable": 1, "Improved": 1, "Worse": 1}) == 1
    assert r27.bii_from_counts({"Stable": 2, "Improved": 1, "Worse": 0}) == pytest.approx(
        2 / 3
    )
    assert r27.bii_stratum(0) == "BII-0"
    assert r27.bii_stratum(0.2) == "BII-Low"
    assert r27.bii_stratum(0.5) == "BII-Mid"
    assert r27.bii_stratum(0.8) == "BII-High"


@pytest.mark.parametrize("length", [2, 3, 4, 11])
def test_reconstructed_derangements_have_zero_fixed_points(length: int) -> None:
    permutation = r27.derangement_indices(length, seed=20260726)
    assert sorted(permutation) == list(range(length))
    assert all(index != value for index, value in enumerate(permutation))


def test_semantic_audit_classifies_lpd_and_lcd_without_overwriting_r26() -> None:
    records = [
        _record("q-a", "a", "Stable"),
        _record("q-b", "b", "Stable"),
        _record("q-c", "c", "Worse"),
    ]
    key = r27.pair_key(records[0])
    result = r27.reconstruct_semantic_audit(
        {key: records}, [_b4_item(record) for record in records]
    )
    classes = Counter(item["audit_class"] for item in result["records"])
    assert classes["LPD"] > 0
    assert classes["LCD"] > 0
    assert result["overall"]["zero_fixed_points"] == 0
    assert result["assignment_indices_serialized_by_r26"] is False
    assert result["assignment_source"] == "DETERMINISTIC_RECONSTRUCTION"


def test_pair_composition_conserves_entities_and_labels() -> None:
    records = [
        _record("q-a", "a", "Stable"),
        _record("q-b", "b", "Improved"),
        _record("q-c", "c", "Worse"),
    ]
    output = r27.build_pair_composition({r27.pair_key(records[0]): records})
    assert len(output) == 1
    assert output[0]["entity_count"] == 3
    assert output[0]["label_counts"] == {
        "Improved": 1,
        "Stable": 1,
        "Worse": 1,
    }
    assert output[0]["bii"] == 1
    assert output[0]["bii_stratum"] == "BII-High"


def _prediction_rows() -> list[dict[str, object]]:
    rows = []
    targets = dict(zip(("a", "b", "c"), r27.LABELS, strict=True))
    wrong = {"Improved": "Stable", "Stable": "Worse", "Worse": "Improved"}
    for patient_index in range(4):
        patient = f"p{patient_index}"
        for system in r27.SYSTEMS:
            for seed in r27.TRAINING_SEEDS:
                for derangement in r27.DERANGEMENT_IDS:
                    for anatomy, target in targets.items():
                        prediction = {
                            "B4b_oracle": target,
                            "B4a_deranged": wrong[target],
                            "current_only": "Stable",
                        }[system]
                        rows.append(
                            {
                                "patient_id": patient,
                                "observation_id": f"{patient}-{anatomy}",
                                "target": target,
                                "prediction": prediction,
                                "system": system,
                                "training_seed": seed,
                                "derangement_id": derangement,
                                "weight": 1 / 3,
                            }
                        )
    return rows


def test_bootstrap_resamples_patients_and_keeps_entities_clustered() -> None:
    result = r27.bootstrap_stratum(
        _prediction_rows(), replicates=100, rng_seed=123
    )
    assert result["bootstrap"]["resampled_levels"] == ["patient"]
    assert result["bootstrap"]["fixed_levels"] == [
        "training_seed",
        "derangement_id",
    ]
    assert result["bootstrap"]["inference_valid"] is True
    assert result["contrasts"]["B4b_minus_B4a"]["point"] == pytest.approx(1.0)
    assert result["per_seed_contrasts"]["17"]["B4b_minus_B4a"] == pytest.approx(
        1.0
    )


def test_sparse_high_bii_support_has_terminal_precedence() -> None:
    support = {
        "high_bii_support_passed": False,
    }
    stratified = {
        stratum: {
            "contrasts": {
                "B4b_minus_B4a": {
                    "point": 0.1 * (index + 1),
                    "interval": {"lower": 0.01, "upper": 0.5},
                }
            },
            "per_seed_contrasts": {
                str(seed): {"B4b_minus_B4a": 0.1}
                for seed in r27.TRAINING_SEEDS
            },
        }
        for index, stratum in enumerate(r27.STRATUM_ORDER)
    }
    verdict, checks = r27.terminal_verdict(stratified, support)
    assert verdict == "C_SPARSE_HIGH_BII_SUPPORT"
    assert checks["high_bii_support"] is False


def test_runner_imports_no_training_or_process_launcher_modules() -> None:
    source = Path(r27.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
    assert "subprocess" not in imported
    assert "torch.optim" not in imported
    assert not any(name.startswith("scripts.run_") for name in imported)


def test_manifest_payload_hash_is_canonical() -> None:
    first = {"b": 2, "a": [1, 3]}
    second = {"a": [1, 3], "b": 2}
    assert r27.canonical_sha256(first) == r27.canonical_sha256(second)
    assert r27.canonical_sha256(first) == hashlib.sha256(
        b'{"a":[1,3],"b":2}'
    ).hexdigest()


def test_exclusive_json_writer_refuses_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "artifact.json"
    r27.write_json_exclusive(target, {"exploratory_only": True})
    with pytest.raises(FileExistsError):
        r27.write_json_exclusive(target, {"exploratory_only": False})


def test_frozen_r27_package_passes_independent_verification() -> None:
    result = verify_r27.verify(r27.OUTPUT_ROOT_DEFAULT)
    assert result["status"] == "PASS_R27_INDEPENDENT_VERIFICATION"
    assert result["failed"] == []
