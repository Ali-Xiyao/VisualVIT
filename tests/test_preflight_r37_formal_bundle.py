from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.preflight_r37_formal_bundle import inspect_bundle


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _spec(tmp_path: Path, *, human_unlocked: bool = False) -> dict:
    transition_root = tmp_path / "transitions"
    cache_root = tmp_path / "cache"
    output_root = tmp_path / "formal"
    transition_root.mkdir(parents=True)
    cache_root.mkdir(parents=True)
    for name in (
        "r37_pretrain_manifest.jsonl",
        "r37_internal_calibration_manifest.jsonl",
    ):
        (transition_root / name).write_text("{}\n", encoding="utf-8")
    text_cache = tmp_path / "text.pt"
    text_cache.write_bytes(b"fixture")
    cmcp_path = tmp_path / "cmcp.json"
    _write_json(
        transition_root / "r37_transition_audit.json",
        {
            "status": (
                "PASS_R37A_TRANSITION_QUALITY"
                if human_unlocked
                else "PASS_R37A_TRANSITION_SUPPORT_PENDING_HUMAN_QA"
            ),
            "ruleset_version": "r37-report-transition-v4.1",
            "formal_training_unlocked": human_unlocked,
            "eligible_transition_pair_counts": {
                "pretrain": 33621,
                "internal_calibration": 3770,
            },
            "transition_example_counts": {
                "pretrain": 46349,
                "internal_calibration": 5242,
            },
            "protected_outcomes_read": False,
        },
    )
    _write_json(
        cache_root / "cache_manifest.json",
        {
            "status": "PASS_R37_BLOCK8_FORMAL_CACHE",
            "cached_image_count": 144423,
            "formal_inventory_count": 144423,
            "shard_count": 566,
            "protected_outcomes_read": False,
            "source_hashes_recomputed": False,
            "per_shard_hashes_computed": False,
        },
    )
    _write_json(
        cmcp_path,
        {
            "status": "PASS_R37A_CMCP_COVERAGE",
            "partition_counts": {
                "pretrain": {
                    "coverage": 1.0,
                    "dynamic_examples": 23416,
                    "matched_dynamic_examples": 23416,
                },
                "internal_calibration": {
                    "coverage": 1.0,
                    "dynamic_examples": 2625,
                    "matched_dynamic_examples": 2625,
                },
            },
            "protected_outcomes_read": False,
            "target_outcome_passed_to_model": False,
        },
    )
    return {
        "schema": "visualvit.r37.prta-formal-bundle-spec.v1",
        "bundle_id": "r37-a6-formal-bundle-v1",
        "variant": "A6",
        "seeds": [17, 29, 43],
        "training": {
            "selection": "all_seed_independent_order",
            "train_examples": 46349,
            "calibration_examples": 5242,
            "train_pairs": 33621,
            "calibration_pairs": 3770,
            "epochs": 3,
            "batch_size": 2,
            "learning_rate": 0.0001,
            "adapter_rank": 32,
        },
        "qualification": {
            "bootstrap_unit": "patient_cluster",
            "bootstrap_replicates": 2000,
            "bootstrap_seed": 37001,
            "inversion_consistency_minimum": 0.9,
            "state_retention_cosine_minimum": 0.99,
            "a6_minus_a0_minimum_pp": 2.0,
            "controls": ["current_only", "cmcp"],
        },
        "artifacts": {
            "transition_root": str(transition_root),
            "block8_cache_root": str(cache_root),
            "text_cache": str(text_cache),
            "cmcp_index": str(cmcp_path),
            "formal_output_root": str(output_root),
        },
        "expected": {
            "transition_ruleset": "r37-report-transition-v4.1",
            "transition_status_pending": (
                "PASS_R37A_TRANSITION_SUPPORT_PENDING_HUMAN_QA"
            ),
            "block8_status": "PASS_R37_BLOCK8_FORMAL_CACHE",
            "block8_images": 144423,
            "block8_shards": 566,
            "cmcp_status": "PASS_R37A_CMCP_COVERAGE",
            "cmcp_dynamic_examples": 26041,
            "cmcp_coverage": 1.0,
        },
        "firewall": {
            "protected_outcomes_read": False,
            "sealed_test_read": False,
            "gold_outcomes_read": False,
            "source_hashes_recomputed": False,
            "per_shard_hashes_computed": False,
        },
        "baseline_a0": {
            "selection": "all_seed_independent_order",
            "seeds": [17, 29, 43],
            "epochs": 100,
            "batch_size": 16,
            "learning_rate": 0.01,
            "formal_output_root": str(tmp_path / "formal_a0"),
        },
    }


def test_preflight_passes_engineering_and_stays_human_qa_locked(tmp_path):
    result = inspect_bundle(_spec(tmp_path))
    assert result["status"] == (
        "READY_R37_FORMAL_BUNDLE_PENDING_HUMAN_QA"
    )
    assert result["engineering_preflight_passed"] is True
    assert result["formal_execution_allowed"] is False
    assert {item["state"] for item in result["seed_output_states"]} == {
        "fresh"
    }
    assert result["source_hashes_recomputed"] is False


def test_preflight_unlocks_only_from_formal_transition_audit(tmp_path):
    result = inspect_bundle(_spec(tmp_path, human_unlocked=True))
    assert result["status"] == "READY_R37_FORMAL_BUNDLE"
    assert result["formal_execution_allowed"] is True


def test_preflight_stops_on_partial_output_or_spec_drift(tmp_path):
    spec = _spec(tmp_path)
    seed_root = Path(spec["artifacts"]["formal_output_root"]) / "seed_17"
    seed_root.mkdir(parents=True)
    (seed_root / "checkpoint.pt").write_bytes(b"partial")
    result = inspect_bundle(spec)
    assert result["status"] == "STOP_R37_FORMAL_BUNDLE_PREFLIGHT"
    assert result["checks"]["a6_output_states_resumable"] is False

    drifted = copy.deepcopy(_spec(tmp_path / "drift"))
    drifted["seeds"] = [17, 29, 44]
    result = inspect_bundle(drifted)
    assert result["status"] == "STOP_R37_FORMAL_BUNDLE_PREFLIGHT"
    assert result["checks"]["seeds"] is False
