from __future__ import annotations

# ruff: noqa: E402

from dataclasses import replace
from pathlib import Path
import sys

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))

import torch

from scripts.run_synthetic_calibration_grid import (
    DEFAULT_SEED_BANK,
    EVIDENCE_CLASS,
    METHOD_NAMES,
    _anatomy_support,
    _cosine_cost_contract,
    audit_anchor_batch,
    build_parser,
    make_anchor_batch,
    run_calibration,
)
from visualvit.baselines import BalancedSinkhornBaseline
from visualvit.matching import anatomy_compatible_derangement


def test_anchor_data_is_balanced_and_every_b4_group_is_derangeable() -> None:
    batch = make_anchor_batch(
        cases_per_class=1,
        feature_dim=8,
        seed=101,
        split="unit",
        namespace=9,
    )
    assert torch.bincount(batch.labels, minlength=5).tolist() == [1, 1, 1, 1, 1]
    assert batch.regions.prior_features.shape[1] == 6
    assert batch.regions.current_features.shape[1] == 6
    deranged = anatomy_compatible_derangement(batch.regions, batch.oracle, seed=7001)
    rp = batch.regions.prior_features.shape[1]
    rc = batch.regions.current_features.shape[1]
    assert (
        torch.count_nonzero(
            batch.oracle.transport[:, :rp, :rc] * deranged.transport[:, :rp, :rc]
        )
        == 0
    )
    assert torch.equal(
        batch.oracle.transport[:, :rp, rc], deranged.transport[:, :rp, rc]
    )
    assert torch.equal(
        batch.oracle.transport[:, rp, :rc], deranged.transport[:, rp, :rc]
    )

    audit = audit_anchor_batch(batch)
    assert all(audit["checks"].values())
    assert (
        min(
            count
            for case_counts in audit["persistent_per_anatomy_group"]
            for count in case_counts
        )
        >= 2
    )

    for label in (3, 4):
        case_index = int(torch.nonzero(batch.labels == label).item())
        death_index = int(
            torch.nonzero(batch.oracle.transport[case_index, :rp, rc] > 0.5).item()
        )
        birth_index = int(
            torch.nonzero(batch.oracle.transport[case_index, rp, :rc] > 0.5).item()
        )
        assert (
            batch.regions.prior_anatomy[case_index, death_index]
            == batch.regions.current_anatomy[case_index, birth_index]
        )


def test_anchor_support_is_strict_balanced_feasible_with_zero_null_mass() -> None:
    batch = make_anchor_batch(cases_per_class=1, feature_dim=8, seed=103)
    support = _anatomy_support(batch.regions)
    cost = torch.zeros_like(support, dtype=torch.float32)
    marginal_prior = batch.regions.prior_valid.float()
    marginal_current = batch.regions.current_valid.float()
    plan = BalancedSinkhornBaseline(epsilon=0.5, iterations=64)(
        cost, support, marginal_prior, marginal_current
    )
    plan.validate(batch.regions)
    rp = marginal_prior.shape[1]
    rc = marginal_current.shape[1]
    assert torch.count_nonzero(plan.transport[:, :rp, rc]) == 0
    assert torch.count_nonzero(plan.transport[:, rp, :rc]) == 0
    assert torch.allclose(plan.transport[:, :rp, :rc].sum(-1), marginal_prior)
    assert torch.allclose(plan.transport[:, :rp, :rc].sum(-2), marginal_current)


def test_baseline_cost_contract_is_deterministic_and_entity_id_free() -> None:
    batch = make_anchor_batch(cases_per_class=1, feature_dim=8, seed=107)
    original = _cosine_cost_contract(batch.regions)
    relabeled = replace(
        batch.regions,
        prior_entity_ids=batch.regions.prior_entity_ids.flip(-1) + 100_000,
        current_entity_ids=batch.regions.current_entity_ids.flip(-1) + 200_000,
    )
    relabeled.validate()
    repeated = _cosine_cost_contract(relabeled)
    for expected, actual in zip(original, repeated, strict=True):
        assert torch.equal(expected, actual)


def test_dry_run_schema_uses_registered_default_seed_bank() -> None:
    args = build_parser().parse_args(["--run-dir", "unused", "--dry-run"])
    assert tuple(args.seeds) == DEFAULT_SEED_BANK
    summary = run_calibration(args)
    assert summary["status"] == "DRY_RUN_VALIDATED"
    assert summary["evidence_class"] == EVIDENCE_CLASS
    assert summary["formal_claim_allowed"] is False
    assert summary["formal_ablation_claim_allowed"] is False
    assert summary["seed_results"] == []
    assert len(summary["config_sha256"]) == 64
    assert len(summary["source_hashes"]["manifest_sha256"]) == 64
    assert summary["api_audit"]["oracle_cardinality_in_learned_api"] is False
    assert summary["api_audit"]["oracle_cardinality_in_baseline_api"] is False
    assert all(
        all(split["checks"].values()) for split in summary["data_audits"].values()
    )


def test_one_seed_one_step_runner_emits_complete_nonconfirmatory_schema() -> None:
    args = build_parser().parse_args(
        [
            "--run-dir",
            "unused",
            "--seeds",
            "17",
            "--train-cases-per-class",
            "1",
            "--inner-dev-cases-per-class",
            "1",
            "--dev-cases-per-class",
            "1",
            "--feature-dim",
            "8",
            "--hidden-size",
            "8",
            "--steps",
            "1",
            "--threshold-grid",
            "-1",
            "0",
            "1",
            "--sinkhorn-iterations",
            "2048",
        ]
    )
    summary = run_calibration(args)
    assert summary["status"] == "COMPLETE"
    assert summary["formal_claim_allowed"] is False
    assert summary["aggregate"]["ordered_seeds"] == [17]
    seed = summary["seed_results"][0]
    assert seed["status"] == "COMPLETE"
    assert tuple(seed["controlled_training_systems"]) == (
        "B4a_deranged",
        "B4b_oracle",
        "learned_soft",
    )
    assert tuple(seed["diagnostic_evaluations"]) == ("learned_hard",)
    assert tuple(seed["independent_baseline_systems"]) == (
        "hungarian_dev_frozen_reject",
        "balanced_sinkhorn_no_null",
    )
    assert tuple(seed["engineering_interventions"]) == (
        "A1_identity_masking",
        "A2_null_deletion",
    )
    methods = {
        **seed["controlled_training_systems"],
        **seed["diagnostic_evaluations"],
        **seed["independent_baseline_systems"],
        **seed["engineering_interventions"],
    }
    assert tuple(methods) == METHOD_NAMES
    assert seed["threshold_provenance"]["formal_test_used"] is False
    assert seed["threshold_provenance"]["fixed_grid"] == [-1.0, 0.0, 1.0]
    for split in ("train", "development"):
        feasibility = seed["balanced_feasibility"][split]
        assert feasibility["feasible_rate"] == 1.0
        assert feasibility["null_fallback_used"] is False
        assert feasibility["null_mass"] == 0.0
    assert seed["checks"]["same_allocation_every_method"]
    assert seed["checks"]["exact64_no_pixel_frozen_finite"]
    assert seed["checks"]["oracle_cardinality_argument_used"] is False
    assert seed["checks"]["B4_pair_contract_pass"]
    assert seed["baseline_contract"]["null_head_used"] is False
    assert seed["baseline_contract"]["identical_for_hungarian_and_sinkhorn"]
    assert "cosine distance" in seed["baseline_contract"]["source"]
    b4a = seed["training_system_records"]["B4a_deranged"]
    b4b = seed["training_system_records"]["B4b_oracle"]
    assert b4a["initial_state_sha256"] == b4b["initial_state_sha256"]
    assert b4a["optimizer_spec_sha256"] == b4b["optimizer_spec_sha256"]
    assert b4a["assignment_sha256"] != b4b["assignment_sha256"]
    assert b4a["matcher_frozen"] and b4b["matcher_frozen"]
    assert seed["derangement_count"] == 1
    assert seed["formal_D_requirement_met"] is False
    assert seed["effects"]["recovery_defined_only_for_positive_denominator"]
    assert seed["effects"]["interventions_excluded_from_delta_bind_and_recovery"]
    assert summary["mechanism_gate"]["evaluated"] is False
    assert summary["mechanism_gate"]["pass"] is False
    for method in METHOD_NAMES:
        result = methods[method]
        assert result["formal_ablation"] is False
        assert result["status"] == "COMPLETE"
        assert set(result["assignment"]) >= {
            "persistent",
            "death",
            "birth",
            "macro_f1",
        }
        assert len(result["raw"]["targets"]) == 5
        assert len(result["raw"]["predictions"]) == 5
        assert result["audits"]["exact_64_tokens"]
        assert result["audits"]["no_pixel_path"]
        assert result["audits"]["frozen_vlm"]
