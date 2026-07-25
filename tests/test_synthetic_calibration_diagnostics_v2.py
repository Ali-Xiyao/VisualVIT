from __future__ import annotations

# ruff: noqa: E402

from pathlib import Path
import sys

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))

import pytest

from scripts.run_synthetic_calibration_diagnostics_v2 import (
    DEFAULT_SEED_BANK,
    EVIDENCE_CLASS,
    FROZEN_VLM_SEED,
    MODE_SPECS,
    PROTOCOL_VERSION,
    _build_seed_factorized_model,
    _competence_gate,
    _frozen_vlm_hash,
    _neutralization_contract_audit,
    _shared_allocation,
    _trainable_state_hash,
    build_parser,
    make_anchor_batch,
    run_diagnostics,
)


def _args(*values: str):
    return build_parser().parse_args(["--run-dir", "unused-diagnostic-v2-run", *values])


def test_registered_modes_change_exactly_one_declared_factor() -> None:
    assert MODE_SPECS["D1"].parent == "S075"
    assert MODE_SPECS["D1"].steps == 80
    assert MODE_SPECS["D1"].neutralize_global_entity_payloads is False
    assert MODE_SPECS["D2"].parent == "D1"
    assert MODE_SPECS["D2"].steps == 500
    assert MODE_SPECS["D2"].neutralize_global_entity_payloads is False
    assert MODE_SPECS["D3"].parent == "D2"
    assert MODE_SPECS["D3"].steps == 500
    assert MODE_SPECS["D3"].neutralize_global_entity_payloads is True


def test_fixed_vlm_seed_is_crossed_with_independent_trainable_seeds() -> None:
    first = _build_seed_factorized_model(
        trainable_seed=17, feature_dim=12, hidden_size=16
    )
    second = _build_seed_factorized_model(
        trainable_seed=29, feature_dim=12, hidden_size=16
    )
    assert FROZEN_VLM_SEED == 91_001
    assert _frozen_vlm_hash(first) == _frozen_vlm_hash(second)
    assert _trainable_state_hash(first) != _trainable_state_hash(second)


@pytest.mark.parametrize(
    ("values", "status", "passed"),
    (
        ([0.80, 0.81, 0.94], "PASS_D3_ELIGIBILITY", True),
        ([0.99, 0.79, 0.99], "NOT_EVALUABLE_READOUT_INCOMPETENT", False),
    ),
)
def test_D2_admission_is_every_seed_at_least_point_80(
    values: list[float], status: str, passed: bool
) -> None:
    aggregate = {
        "metrics": {"train": {"B4b_oracle": {"case_balanced_macro_f1_values": values}}}
    }
    gate = _competence_gate(args=_args("--mode", "D2"), aggregate=aggregate)
    assert gate["status"] == status
    assert gate["pass"] is passed
    assert gate["D3_eligibility_threshold_every_seed"] == 0.80
    assert gate["strict_train_fit_threshold_every_seed"] == 0.95


def test_D3_neutralizes_only_global_entity_projected_payloads() -> None:
    batch = make_anchor_batch(
        cases_per_class=1,
        feature_dim=12,
        seed=3_401,
        split="unit",
        namespace=1,
    )
    model = _build_seed_factorized_model(
        trainable_seed=17, feature_dim=12, hidden_size=16
    )
    allocation = _shared_allocation(model, batch.regions)
    audit = _neutralization_contract_audit(
        base_model=model,
        batch=batch,
        plan=batch.oracle,
        allocation=allocation,
    )
    assert audit["pass"]
    assert all(audit["checks"].values())
    assert audit["neutralized_slots"] == {
        "start_inclusive": 0,
        "stop_exclusive": 32,
    }
    assert audit["preserved_slots"] == {
        "start_inclusive": 32,
        "stop_exclusive": 64,
    }


@pytest.mark.parametrize("mode", ("D1", "D2", "D3"))
def test_each_mode_has_an_independent_fail_closed_dry_run(mode: str) -> None:
    summary = run_diagnostics(_args("--mode", mode, "--dry-run"))
    assert summary["status"] == "DRY_RUN_VALIDATED"
    assert summary["protocol_version"] == PROTOCOL_VERSION
    assert summary["mode"] == mode
    assert summary["evidence_class"] == EVIDENCE_CLASS
    assert summary["formal_claim_allowed"] is False
    assert summary["formal_ablation_claim_allowed"] is False
    assert summary["original_S075_status_mutable"] is False
    assert summary["training_allowed"] is False
    assert summary["seed_results"] == []
    assert summary["config"]["trainable_seed_bank"] == list(DEFAULT_SEED_BANK)
    assert summary["config"]["actual_steps"] == MODE_SPECS[mode].steps
    assert summary["config"]["formal_test"] == "SEALED"
    if mode == "D3":
        assert summary["D3_prerequisite_audit"]["pass"] is False
        assert summary["D3_neutralization_contract_audit"]["pass"]


def test_registered_D3_refuses_training_without_qualified_D2_summary() -> None:
    summary = run_diagnostics(_args("--mode", "D3", "--seeds", "17"))
    assert summary["status"] == "FAIL_PREREQUISITE"
    assert summary["training_allowed"] is False
    assert summary["D3_prerequisite_audit"]["reason"] == "missing_d2_summary"
    assert summary["seed_results"] == []
    assert summary["formal_claim_allowed"] is False


def test_one_seed_D3_smoke_records_hashes_train_dev_metrics_and_contracts() -> None:
    summary = run_diagnostics(_args("--mode", "D3", "--seeds", "17", "--smoke"))
    assert summary["status"] == "SMOKE_COMPLETE"
    assert summary["diagnostic_evaluable"] is False
    assert summary["formal_claim_allowed"] is False
    assert summary["formal_ablation_claim_allowed"] is False
    assert summary["config"]["registered_steps"] == 500
    assert summary["config"]["actual_steps"] == 1
    assert summary["D3_prerequisite_audit"]["pass"] is False
    assert summary["D3_prerequisite_audit"]["reason"] == (
        "explicit_non_diagnostic_smoke_bypass"
    )

    seed_result = summary["seed_results"][0]
    assert seed_result["status"] == "SMOKE_COMPLETE"
    assert seed_result["technical_checks"]["B4_pair_contract_pass"]
    assert seed_result["technical_checks"]["B4_trainable_initial_hash_equal"]
    assert seed_result["technical_checks"]["B4_complete_initial_hash_equal"]
    assert seed_result["technical_checks"]["frozen_vlm_unchanged_after_training"]
    assert seed_result["technical_checks"]["D3_payload_neutralization_pass"]

    initial = seed_result["state_hashes"]["initial"]
    final = seed_result["state_hashes"]["final"]
    for system in ("B4a_deranged", "B4b_oracle", "learned_soft"):
        assert len(initial[system]["frozen_vlm_sha256"]) == 64
        assert len(initial[system]["trainable_sha256"]) == 64
        assert len(initial[system]["complete_sha256"]) == 64
        assert len(final[system]["complete_sha256"]) == 64
        for split in ("train", "development"):
            metrics = seed_result["metrics"][split][system]["label_metrics"]
            assert metrics["label_order"] == [
                "stable",
                "worse",
                "improved",
                "new",
                "resolved",
            ]
            assert metrics["all_five_labels_present"]
            assert set(metrics["per_label"]) == set(metrics["label_order"])
            assert 0.0 <= metrics["case_balanced_macro_f1"] <= 1.0

    payload_hashes = {
        split_audit["neutral_payload_sha256"]
        for system_audit in seed_result["payload_neutrality_audits"].values()
        for split_audit in system_audit.values()
    }
    assert len(payload_hashes) == 1
    assert summary["aggregate"]["state_hash_audit"][
        "fixed_vlm_hash_equal_across_training_seeds"
    ]
    assert summary["diagnostic_gate"]["evaluated"] is False
    assert summary["diagnostic_gate"]["pass"] is False
    assert summary["config"]["device"] == "cpu"
