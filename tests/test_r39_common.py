from __future__ import annotations

import torch

from scripts.aggregate_r39_sealed import aggregate_payload
from scripts.r39_common import (
    TARGET_TO_VLM,
    patient_class_weights,
    prior_shuffle_assignment,
    token_bundle,
)
from visualvit.tier_token_projector import TierTokenProjector


def test_r39_label_order_maps_five_classes_exactly() -> None:
    assert TARGET_TO_VLM == {
        "Stable": 0,
        "Worse": 1,
        "Improved": 2,
        "New": 3,
        "Resolved": 4,
    }


def test_r39_token_bundle_is_exact64_with_reserved_logical_nulls() -> None:
    bundle = token_bundle(torch.randn(2, 64, 768))
    bundle.validate(token_budget=64)
    assert bundle.valid_mask[:, :60].all()
    assert not bundle.valid_mask[:, 60:].any()
    assert bundle.tokens.shape == (2, 64, 768)


def test_r39_projector_parameter_receipt_matches_768_to_2560() -> None:
    projector = TierTokenProjector(768, 2560)
    assert sum(parameter.numel() for parameter in projector.parameters()) == (
        9_873_920
    )


def test_patient_class_weights_are_positive_and_mean_one() -> None:
    rows = [
        {"label": label, "patient_id": f"p{index // 2}"}
        for index, label in enumerate(
            ["Stable", "Worse", "Improved", "New", "Resolved"] * 2
        )
    ]
    weights = patient_class_weights(rows)
    assert all(value > 0 for value in weights)
    assert abs(sum(weights) / len(weights) - 1.0) < 1e-9


def test_prior_shuffle_is_deterministic_cross_patient_within_finding() -> None:
    rows = [
        {
            "record_id": f"r{index}",
            "patient_id": f"p{index // 2}",
            "finding": "Edema",
            "prior_dicom_id": f"d{index}",
        }
        for index in range(6)
    ]
    first = prior_shuffle_assignment(rows, seed=39011)
    second = prior_shuffle_assignment(rows, seed=39011)
    patient_by_dicom = {
        row["prior_dicom_id"]: row["patient_id"] for row in rows
    }
    assert first == second
    assert set(first) == {row["record_id"] for row in rows}
    assert all(
        patient_by_dicom[first[row["record_id"]]] != row["patient_id"]
        for row in rows
    )


def test_r39_aggregate_requires_all_frozen_comparisons() -> None:
    targets = ["Stable", "Worse", "Improved", "New", "Resolved"] * 2
    true = [TARGET_TO_VLM[label] for label in targets]
    control = [(value + 1) % 5 for value in true]
    record_ids = [f"r{index}" for index in range(len(targets))]
    patient_ids = [f"p{index // 2}" for index in range(len(targets))]
    predictions = [
        {
            "status": "PASS_R39_OUTCOME_BLIND_SEALED_PREDICTIONS",
            "seed": seed,
            "record_ids": record_ids,
            "patient_ids": patient_ids,
            "predictions": {
                "a6_true_pair": true,
                "a0_frozen_difference": control,
                "a6_current_only": control,
                "a6_prior_shuffle": control,
                "query_only": control,
            },
            "prediction_keys": [
                "a6_true_pair",
                "a0_frozen_difference",
                "a6_current_only",
                "a6_prior_shuffle",
                "query_only",
            ],
            "all_predictions_frozen_before_label_reveal": True,
            "sealed_483_test_labels_read": False,
            "gold_outcomes_read": False,
            "vlm_all_frozen": True,
            "pixel_inputs_used": False,
            "token_budget": 64,
            "source_hashes_recomputed": False,
            "per_shard_hashes_computed": False,
        }
        for seed in (17, 29, 43)
    ]
    labels = [
        {
            "record_id": record_id,
            "patient_id": patient_id,
            "progression": target,
        }
        for record_id, patient_id, target in zip(
            record_ids, patient_ids, targets, strict=True
        )
    ]
    config = {
        "candidate_id": "r37-1-a6-three-seed-v1",
        "training": {"seeds": [17, 29, 43]},
        "final_gate": {
            "minimum_gain_pp": 2.0,
            "bootstrap_replicates": 100,
            "bootstrap_seed": 39001,
            "required_controls": {
                "a6_true_pair_vs_current_only_minimum_gain_pp": 2.0,
                "a6_true_pair_vs_query_only_minimum_gain_pp": 2.0,
                "a6_true_pair_vs_prior_shuffle_minimum_gain_pp": 2.0,
            },
        },
    }
    output = aggregate_payload(predictions, labels, config)
    assert output["status"] == "GO_R39_FROZEN_VLM_TRANSFER"
    assert all(
        comparison["gate"]["passed"]
        for comparison in output["comparisons"].values()
    )
