import json

import pytest

from scripts.aggregate_prta_gen_r40a_field import (
    aggregate_field,
    confusion_by_patient,
    macro_f1_from_confusion,
    paired_patient_bootstrap,
)
from scripts.cache_prta_gen_r40a_tokens import CONFIG_STATUS
from scripts.run_prta_gen_r40a_probe import RESULT_STATUS


def test_confusion_and_macro_f1_are_patient_cluster_ready():
    patients, confusion = confusion_by_patient(
        ["p1", "p1", "p2", "p2"],
        [0, 1, 0, 1],
        [0, 1, 0, 0],
        class_count=2,
    )

    assert patients == ["p1", "p2"]
    assert confusion.shape == (2, 2, 2)
    assert macro_f1_from_confusion(confusion.sum(axis=0)) == pytest.approx(
        (0.8 + 2.0 / 3.0) / 2.0
    )


def test_paired_patient_bootstrap_is_deterministic_and_positive():
    kwargs = {
        "patient_ids": ["p1", "p1", "p2", "p2", "p3", "p3"],
        "targets": [0, 1, 0, 1, 0, 1],
        "true_predictions": [0, 1, 0, 1, 0, 1],
        "control_predictions": [0, 0, 0, 0, 0, 0],
        "class_count": 2,
        "replicates": 200,
        "seed": 40001,
    }

    first = paired_patient_bootstrap(**kwargs)
    second = paired_patient_bootstrap(**kwargs)

    assert first == second
    assert first["effect_pp"] > 0
    assert first["ci95_lower_pp"] > 0


def test_confusion_rejects_invalid_alignment():
    with pytest.raises(ValueError, match="lengths differ"):
        confusion_by_patient(["p1"], [0, 1], [0], class_count=2)


def test_aggregate_field_stops_when_one_required_seed_control_fails(tmp_path):
    config_path = tmp_path / "config.json"
    config = {
        "status": CONFIG_STATUS,
        "protocol_id": "test-protocol",
        "token_cache_root": str(tmp_path / "tokens"),
        "supported_probe_classes": {"progression": ["Stable", "New"]},
        "probe": {
            "seeds": [17, 29, 43],
            "patient_bootstrap_replicates": 100,
            "patient_bootstrap_seed": 40001,
        },
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")
    result_root = tmp_path / "probes" / "progression"
    targets = [0, 1, 0, 1, 0, 1]
    perfect = targets
    poor = [0, 0, 0, 0, 0, 0]
    for seed in config["probe"]["seeds"]:
        seed_root = result_root / f"seed_{seed}"
        seed_root.mkdir(parents=True)
        result = {
            "status": RESULT_STATUS,
            "field": "progression",
            "seed": seed,
            "field_generation_unlocked": False,
            "revealed_483_test_read": False,
            "gold_outcomes_read": False,
            "patient_ids": ["p1", "p1", "p2", "p2", "p3", "p3"],
            "example_ids": [f"e{index}" for index in range(6)],
            "targets": targets,
            "classes": ["Stable", "New"],
            "predictions": {
                "true_pair": perfect,
                "current_only": poor,
                "query_only": poor,
                "prior_shuffle": perfect if seed == 17 else poor,
            },
        }
        (seed_root / "result.json").write_text(
            json.dumps(result), encoding="utf-8"
        )

    aggregate = aggregate_field(
        config_path=config_path, field="progression"
    )

    assert aggregate["status"] == "STOP_PRTA_GEN_R40A_FIELD_INFORMATION"
    assert aggregate["field_generation_unlocked"] is False
    assert (
        aggregate["comparisons"]["prior_shuffle"]["17"]["effect_pp"] == 0.0
    )
    assert (result_root / "aggregate.json").exists()
