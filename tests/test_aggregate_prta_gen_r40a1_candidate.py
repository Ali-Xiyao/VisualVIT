import json

import pytest

from scripts.aggregate_prta_gen_r40a1_candidate import (
    aggregate_candidate,
    finalize_early_stop,
)
from scripts.build_prta_gen_r40a1_roster import CONFIG_STATUS, ROSTER_PASS
from scripts.run_prta_gen_r40a1_probe import RESULT_STATUS
from scripts.select_prta_gen_r40a1_candidate import select_candidate


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_fixture(tmp_path, *, passing=True, include_second=False):
    roster_path = tmp_path / "roster.json"
    write_json(
        roster_path,
        {
            "status": ROSTER_PASS,
            "patient_sets_disjoint": True,
            "qualification_outcomes_read": False,
            "revealed_483_test_read": False,
            "gold_outcomes_read": False,
        },
    )
    config_path = tmp_path / "config.json"
    write_json(
        config_path,
        {
            "status": CONFIG_STATUS,
            "protocol_id": "test",
            "candidate_order": [
                {"name": "regional_moments_v1"},
                {"name": "regional_cosine4_v1"},
            ],
            "candidate_selection": {"rule": "first"},
            "probe": {
                "seeds": [17, 29, 43],
                "patient_bootstrap_replicates": 100,
                "patient_bootstrap_seed": 40101,
            },
            "discovery_gate": {
                "all_three_seed_effects_at_least_pp": 2.0,
                "required_controls": ["query_only", "prior_shuffle"],
            },
            "qualification_gate": {
                "all_three_seed_effects_at_least_pp": 2.0,
                "required_controls": ["query_only", "prior_shuffle"],
            },
        },
    )
    targets = [0, 1] * 4
    perfect = targets
    poor = [0] * 8
    for candidate in (
        ["regional_moments_v1", "regional_cosine4_v1"]
        if include_second
        else ["regional_moments_v1"]
    ):
        for seed in (17, 29, 43):
            true_predictions = perfect if passing or candidate.endswith("cosine4_v1") else poor
            result = {
                "status": RESULT_STATUS,
                "candidate": candidate,
                "scope": "discovery",
                "seed": seed,
                "classes": ["Stable", "New"],
                "patient_ids": [f"p{index}" for index in range(8)],
                "example_ids": [f"e{index}" for index in range(8)],
                "targets": targets,
                "predictions": {
                    "true_pair": true_predictions,
                    "current_only": poor,
                    "query_only": poor,
                    "prior_shuffle": poor,
                },
                "progression_generation_unlocked": False,
                "protected_300_dev_read": False,
                "revealed_483_test_read": False,
                "gold_outcomes_read": False,
                "old_r40a_development_used_for_selection": False,
            }
            write_json(
                tmp_path
                / "probes"
                / candidate
                / "discovery"
                / f"seed_{seed}"
                / "result.json",
                result,
            )
    return config_path, roster_path


def test_passing_candidate_aggregate_unlocks_selection(tmp_path):
    config, roster = write_fixture(tmp_path, passing=True)
    aggregate = aggregate_candidate(
        config_path=config,
        roster_path=roster,
        candidate_name="regional_moments_v1",
        scope="discovery",
    )
    selection = select_candidate(config_path=config, roster_path=roster)

    assert aggregate["status"] == "GO_PRTA_GEN_R40A1_DISCOVERY"
    assert aggregate["progression_generation_unlocked"] is False
    assert selection["selected_candidate"] == "regional_moments_v1"
    assert selection["qualification_unlocked"] is True


def test_selector_requires_next_ordered_aggregate_after_stop(tmp_path):
    config, roster = write_fixture(tmp_path, passing=False)
    aggregate = aggregate_candidate(
        config_path=config,
        roster_path=roster,
        candidate_name="regional_moments_v1",
        scope="discovery",
    )

    assert aggregate["status"] == "STOP_PRTA_GEN_R40A1_DISCOVERY"
    with pytest.raises(FileNotFoundError, match="cosine"):
        select_candidate(config_path=config, roster_path=roster)


def test_early_stop_skips_remaining_seeds_after_point_gate_failure(tmp_path):
    config, roster = write_fixture(tmp_path, passing=False)
    seed_29_path = (
        tmp_path
        / "probes"
        / "regional_moments_v1"
        / "discovery"
        / "seed_29"
        / "result.json"
    )
    seed_43_path = (
        tmp_path
        / "probes"
        / "regional_moments_v1"
        / "discovery"
        / "seed_43"
        / "result.json"
    )
    seed_29_path.unlink()
    seed_43_path.unlink()
    seed_17 = json.loads(
        (
            tmp_path
            / "probes"
            / "regional_moments_v1"
            / "discovery"
            / "seed_17"
            / "result.json"
        ).read_text(encoding="utf-8")
    )
    seed_17["metrics"] = {
        "true_minus_query_pp": 3.0,
        "true_minus_shuffle_pp": -1.0,
    }
    write_json(
        tmp_path
        / "probes"
        / "regional_moments_v1"
        / "discovery"
        / "seed_17"
        / "result.json",
        seed_17,
    )

    result = finalize_early_stop(
        config_path=config,
        roster_path=roster,
        candidate_name="regional_moments_v1",
        scope="discovery",
    )

    assert result["status"] == "STOP_PRTA_GEN_R40A1_DISCOVERY"
    assert result["completed_seeds"] == [17]
    assert result["skipped_seeds_after_first_failed_gate"] == [29, 43]
