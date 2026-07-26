from __future__ import annotations

from pathlib import Path

import torch

from scripts import run_r26_c1_oracle_binding as runner
from scripts import run_chest_imagenome_mimic_matcher_qualification as r25
from visualvit.matching import (
    anatomy_compatible_derangement,
    oracle_plan_from_entity_ids,
)


def _fixture() -> tuple[dict, dict[str, torch.Tensor]]:
    prior_path = "prior.png"
    current_path = "current.png"
    prior_boxes = [
        {"label": "a", "x1": 0.0, "y1": 0.0, "x2": 10.0, "y2": 10.0},
        {"label": "b", "x1": 10.0, "y1": 0.0, "x2": 20.0, "y2": 10.0},
        {"label": "c", "x1": 20.0, "y1": 0.0, "x2": 30.0, "y2": 10.0},
    ]
    current_boxes = [
        {"label": "a", "x1": 1.0, "y1": 0.0, "x2": 11.0, "y2": 10.0},
        {"label": "b", "x1": 11.0, "y1": 0.0, "x2": 21.0, "y2": 10.0},
        {"label": "c", "x1": 21.0, "y1": 0.0, "x2": 31.0, "y2": 10.0},
    ]
    record = {
        "qualification_id": "q1",
        "patient_id": "p1",
        "prior_dicom_id": "d1",
        "current_dicom_id": "d2",
        "prior_path": prior_path,
        "current_path": current_path,
        "prior_boxes": prior_boxes,
        "current_boxes": current_boxes,
        "anatomy": "a",
        "progression": "Stable",
        "shared_count": 3,
    }
    features = {}
    for index, box in enumerate(prior_boxes):
        features[r25._crop_key(prior_path, box)] = torch.tensor(
            [1.0 + index, 2.0 + index, 3.0 + index, 4.0 + index]
        )
    for index, box in enumerate(current_boxes):
        features[r25._crop_key(current_path, box)] = torch.tensor(
            [5.0 + index, 6.0 + index, 7.0 + index, 8.0 + index]
        )
    return record, features


def test_relation_vector_changes_only_with_assignment() -> None:
    record, features = _fixture()
    regions = r25._region_batch(record, features, "visual_geometry_equal")
    oracle = oracle_plan_from_entity_ids(regions)
    wrong = anatomy_compatible_derangement(regions, oracle, seed=17)

    correct = runner._relation_vector(record, regions, oracle)
    deranged = runner._relation_vector(record, regions, wrong)

    assert correct.shape == deranged.shape
    assert not torch.equal(correct, deranged)
    feature_dim = regions.prior_features.shape[-1]
    assert torch.equal(correct[:feature_dim], deranged[:feature_dim])
    assert torch.equal(correct[-3:], torch.tensor([1.0, 0.0, 0.0]))
    assert torch.equal(deranged[-3:], torch.tensor([1.0, 0.0, 0.0]))


def test_current_only_zeros_prior_without_changing_shape() -> None:
    record, features = _fixture()
    regions = r25._region_batch(record, features, "visual_geometry_equal")
    oracle = oracle_plan_from_entity_ids(regions)

    paired = runner._relation_vector(record, regions, oracle)
    current_only = runner._relation_vector(
        record,
        regions,
        oracle,
        current_only=True,
    )

    feature_dim = regions.prior_features.shape[-1]
    assert paired.shape == current_only.shape
    assert torch.count_nonzero(current_only[:feature_dim]) == 0
    assert torch.equal(
        paired[feature_dim : 2 * feature_dim],
        current_only[feature_dim : 2 * feature_dim],
    )


def test_representations_are_entity_specific_and_b4_isomorphic() -> None:
    record, features = _fixture()

    invariant, deranged, audits = runner._representations([record], features)

    assert set(invariant) == {
        "B4b_oracle",
        "oracle_visual_only",
        "oracle_geometry_only",
        "current_only",
    }
    assert set(deranged) == set(runner.DERANGEMENT_IDS)
    assert all(value.shape[0] == 1 for value in invariant.values())
    assert all(value.shape == invariant["B4b_oracle"].shape for value in deranged.values())
    assert audits[0]["passed"]
    assert all(item["passed"] for item in audits[0]["derangements"])


def test_r26_protocol_and_r25_prerequisites_are_frozen_and_pinned() -> None:
    protocol_text = runner.PROTOCOL_PATH.read_text(encoding="utf-8")

    assert "Status: `FROZEN_BEFORE_EXECUTION`" in protocol_text
    assert runner.sha256_file(runner.PROTOCOL_PATH) == runner.PROTOCOL_SHA256
    assert runner.R25_CERTIFICATE_SHA256 in protocol_text
    assert runner.R25_PROCESS_A_SUMMARY_SHA256 in protocol_text
    assert runner.R25_PROCESS_B_SUMMARY_SHA256 in protocol_text
    assert runner.R25_COHORT_SHA256 in protocol_text
    assert runner.R25_FEATURE_CACHE_SHA256 in protocol_text


def test_live_r25_prerequisite_hashes_match_frozen_pins() -> None:
    root = Path(r"F:\VisualVIT_runtime\050_routeC\r25_1_matching_qualification")

    assert runner.sha256_file(root / "reproduction_certificate.json") == (
        runner.R25_CERTIFICATE_SHA256
    )
    assert runner.sha256_file(root / "process_a/summary.json") == (
        runner.R25_PROCESS_A_SUMMARY_SHA256
    )
    assert runner.sha256_file(root / "process_b/summary.json") == (
        runner.R25_PROCESS_B_SUMMARY_SHA256
    )
    assert runner.sha256_file(root / "process_a/cohort.json") == (
        runner.R25_COHORT_SHA256
    )
    assert runner.sha256_file(root / "process_a/crop_features.pt") == (
        runner.R25_FEATURE_CACHE_SHA256
    )
