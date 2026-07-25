from __future__ import annotations

# ruff: noqa: E402

import copy
import math
from pathlib import Path
import sys

import torch

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))

from scripts.run_query_anchor_v2 import (
    COMPETENCE_DEVELOPMENT_SEED,
    COMPETENCE_SEED_OFFSET,
    COMPETENCE_SIGNAL_AMPLITUDE,
    COMPETENCE_SIGNAL_CHANNELS,
    COMPETENCE_TRAIN_SEED,
    _assignment_diagnostics,
    _compare_independent_reproduction,
    _evaluate_marginal_control_gate,
    _fixed_adapter,
    _initial_projector,
    _json_hash,
    _marginal_competence_probe_batch,
    _source_manifest,
    _train_learned,
    _train_marginal_competence_probe,
    _train_marginal_control,
    _train_provided,
    build_parser,
    run,
)
from visualvit.calibration_query import make_global_assignment_query_anchor_batch


def _args(*extra: str):
    return build_parser().parse_args(["--run-dir", "unused-query-anchor", *extra])


def _recompute_macro_f1(raw: dict[str, list[int]], label_count: int = 3) -> float:
    predictions = raw["predictions"]
    targets = raw["targets"]
    values = []
    for label in range(label_count):
        true_positives = sum(
            prediction == label and target == label
            for prediction, target in zip(predictions, targets, strict=True)
        )
        false_positives = sum(
            prediction == label and target != label
            for prediction, target in zip(predictions, targets, strict=True)
        )
        false_negatives = sum(
            prediction != label and target == label
            for prediction, target in zip(predictions, targets, strict=True)
        )
        denominator = 2 * true_positives + false_positives + false_negatives
        values.append(2 * true_positives / denominator if denominator else 0.0)
    return sum(values) / label_count


def test_assignment_diagnostics_recompute_float_mass_nll_and_brier() -> None:
    batch = make_global_assignment_query_anchor_batch(cases_per_label=2, seed=70_021)
    soft = copy.deepcopy(batch.oracle.plan)
    soft.transport = soft.transport.float()
    hard = copy.deepcopy(batch.oracle.plan)
    persistent_cases = torch.nonzero(batch.persistent_main_mask).flatten().tolist()
    requested_masses = (0.0, 1e-9, 1e-8, 1.0000001e-8, 0.123456789, 0.9)

    for case_index, requested_mass in zip(
        persistent_cases, requested_masses, strict=True
    ):
        query_prior = int(torch.nonzero(batch.prior_query_marker[case_index]).item())
        oracle_current = int(
            torch.nonzero(
                batch.oracle.plan.transport[case_index, query_prior, :-1] > 0.5
            ).item()
        )
        alternative_current = (oracle_current + 1) % (
            batch.regions.current_features.shape[1]
        )
        row = soft.transport[case_index, query_prior, :-1]
        row.zero_()
        row[oracle_current] = requested_mass
        row[alternative_current] = 1.0 - requested_mass

    diagnostics = _assignment_diagnostics(batch, soft, hard)
    persisted_rows = []
    oracle_indices = []
    for case_index in persistent_cases:
        query_prior = int(torch.nonzero(batch.prior_query_marker[case_index]).item())
        oracle_current = int(
            torch.nonzero(
                batch.oracle.plan.transport[case_index, query_prior, :-1] > 0.5
            ).item()
        )
        persisted_rows.append(
            soft.transport[case_index, query_prior, :-1].detach().cpu().tolist()
        )
        oracle_indices.append(oracle_current)

    persisted_masses = [
        row[oracle_current]
        for row, oracle_current in zip(persisted_rows, oracle_indices, strict=True)
    ]
    expected_nll = math.fsum(
        -math.log(max(mass, 1e-8)) for mass in persisted_masses
    ) / len(persisted_masses)
    expected_brier = math.fsum(
        math.fsum(
            (value - (1.0 if column == oracle_current else 0.0)) ** 2
            for column, value in enumerate(row)
        )
        / len(row)
        for row, oracle_current in zip(persisted_rows, oracle_indices, strict=True)
    ) / len(persisted_rows)

    assert diagnostics["soft_oracle_query_mass"] == (
        math.fsum(persisted_masses) / len(persisted_masses)
    )
    assert diagnostics["soft_query_nll"] == expected_nll
    assert diagnostics["soft_query_brier"] == expected_brier
    assert -math.log(max(persisted_masses[0], 1e-8)) == -math.log(1e-8)
    assert -math.log(max(persisted_masses[1], 1e-8)) == -math.log(1e-8)
    assert -math.log(max(persisted_masses[2], 1e-8)) == -math.log(1e-8)
    assert -math.log(max(persisted_masses[3], 1e-8)) < -math.log(1e-8)


def _eligible_reproduction_summary(
    *, pid: int, instance_uuid: str, walltime: float
) -> dict[str, object]:
    trace = {
        "passed": True,
        "observed_adapter_score_calls": {
            "training": 500,
            "final_train_evaluation": 1,
            "final_development_evaluation": 1,
        },
        "observed_total_adapter_score_calls": 502,
        "train_placeholder_counts": [64],
        "development_placeholder_counts": [64],
        "pixel_inputs_used": False,
        "model_frozen": True,
    }
    execution = {
        "initial_state_sha256": "initial",
        "final_state_sha256": "final",
        "complete_initial_state_sha256": "complete-initial",
        "complete_final_state_sha256": "complete-final",
        "frozen_adapter_before_sha256": "frozen",
        "frozen_adapter_after_sha256": "frozen",
        "frozen_adapter_unchanged": True,
        "exact64_execution_audit": trace,
    }
    seeds = ("17", "29", "43")
    derangements = ("81001", "81002", "81003")
    splits = {
        name: {
            "composite_sha256": f"{name}-sha",
            "ordered_tensor_sha256": {"tensor": f"{name}-tensor-sha"},
        }
        for name in ("train", "inner_development", "development")
    }
    marginal_controls = {}
    for seed in seeds:
        marginal_controls[seed] = {}
        for mode in (
            "current_only",
            "prior_current_separate_pooling",
            "current_only_deepsets",
            "prior_only_deepsets",
            "prior_current_deepsets",
        ):
            control = {
                "development_macro_f1": 0.20,
                "actual_visible_unchanged": True,
                "actual_visible_before_sha256": "c" * 64,
                "actual_visible_after_sha256": "c" * 64,
            }
            if mode.endswith("_deepsets"):
                control["competence_probe"] = {
                    "signal": "amplitude-4 persistent-label one-hot",
                    "signal_side": (
                        "current" if mode == "current_only_deepsets" else "prior"
                    ),
                    "signal_channels": list(COMPETENCE_SIGNAL_CHANNELS),
                    "signal_amplitude": COMPETENCE_SIGNAL_AMPLITUDE,
                    "uses_separate_feature_copies": True,
                    "train_seed": COMPETENCE_TRAIN_SEED,
                    "development_seed": COMPETENCE_DEVELOPMENT_SEED,
                    "model_seed": int(seed) + COMPETENCE_SEED_OFFSET,
                    "train_macro_f1": 1.0,
                    "development_macro_f1": 1.0,
                    "final_train_loss": 0.0,
                    "all_gradients_finite": True,
                    "finite_gradient_steps": 500,
                    "permutation_invariance_max_logit_error": 0.0,
                    "cyclic_code_derangement_macro_f1": 0.0,
                    "train_batch_sha256": "d" * 64,
                    "development_batch_sha256": "e" * 64,
                    "probe_train_feature_sha256": "f" * 64,
                    "probe_development_feature_sha256": "1" * 64,
                    "initial_state_sha256": "2" * 64,
                    "final_state_sha256": "3" * 64,
                }
            marginal_controls[seed][mode] = control
    summary = {
        "status": "PASS_GATES_1_TO_6_AWAITING_INDEPENDENT_REPRODUCTION",
        "protocol_version": "CAPES_CI_QUERY_ANCHOR_V2_R3_2026_07_22",
        "evidence_class": "QUERY_GATED_RELATION_MEDIATOR_ENGINEERING_NONCONFIRMATORY",
        "config": {
            "trainable_seeds": [17, 29, 43],
            "derangement_seeds": [81001, 81002, 81003],
            "actual_steps": 500,
            "registered_steps": 500,
            "dry_run": False,
            "smoke": False,
            "formal_test": "SEALED",
            "protocol_version": "CAPES_CI_QUERY_ANCHOR_V2_R3_2026_07_22",
            "evidence_class": "QUERY_GATED_RELATION_MEDIATOR_ENGINEERING_NONCONFIRMATORY",
            "competence_probe": {
                "train_seed": COMPETENCE_TRAIN_SEED,
                "development_seed": COMPETENCE_DEVELOPMENT_SEED,
                "model_seed_offset": COMPETENCE_SEED_OFFSET,
                "signal_channels": list(COMPETENCE_SIGNAL_CHANNELS),
                "signal_amplitude": COMPETENCE_SIGNAL_AMPLITUDE,
                "train_cases_per_label": 16,
                "development_cases_per_label": 24,
            },
        },
        "source_manifest": _source_manifest(),
        "split_manifests": splits,
        "pretraining_fairness": {
            "frozen_adapter_sha256": "frozen",
            "trainable_initial_states_distinct_across_seeds": True,
            "trainable_initial_state_sha256": {seed: seed for seed in seeds},
            "split_order_sha256": {name: f"{name}-sha" for name in splits},
        },
        "process_identity": {"pid": pid, "instance_uuid": instance_uuid},
        "runtime_environment": {
            "deterministic_algorithms_enabled": True,
            "pythonhashseed": "0",
            "omp_num_threads": "1",
            "mkl_num_threads": "1",
        },
        "structural_audits": {"passed": True},
        "working_oracle_gate": {"passed": True},
        "marginal_control_gate": {"passed": True},
        "persistent_binding_gate": {"passed": True},
        "learned_recovery_gate": {"passed": True},
        "baseline_noninferiority_gate": {"passed": True},
        "oracle_results": {seed: execution for seed in seeds},
        "b4a_results": {
            seed: {derangement: execution for derangement in derangements}
            for seed in seeds
        },
        "learned_results": {seed: execution for seed in seeds},
        "baseline_results": {
            seed: {"hungarian": execution, "sinkhorn": execution} for seed in seeds
        },
        "baseline_execution": {
            "plans_are_seed_invariant": True,
            "train_contract_sha256": "train-contract",
            "development_contract_sha256": "development-contract",
        },
        "marginal_controls": marginal_controls,
        "formal_test_used": False,
        "formal_claim_allowed": False,
        "independent_process_reproduction_required": True,
        "walltime_seconds": walltime,
    }
    summary["config_sha256"] = _json_hash(summary["config"])
    return summary


def test_r2_query_anchor_dry_run_closes_structural_gates() -> None:
    summary = run(_args("--dry-run"))
    assert summary["status"] == "DRY_RUN_VALIDATED"
    assert summary["structural_audits"]["passed"]
    assert summary["structural_audits"]["adapter_equivalence"]["passed"]
    assert summary["structural_audits"]["hidden_id_relabel_invariance"]["passed"]
    assert summary["structural_audits"]["development"]["marginal_structure"]["passed"]
    assert summary["formal_test_used"] is False
    assert summary["formal_claim_allowed"] is False


def test_r2_one_seed_smoke_runs_exact64_and_stays_nonconfirmatory() -> None:
    summary = run(_args("--smoke", "--seeds", "17"))
    assert summary["status"] == "SMOKE_COMPLETE"
    assert summary["working_oracle_gate"]["passed"]
    assert summary["marginal_control_gate"]["passed"]
    assert not summary["marginal_control_gate"]["competence_required"]
    assert summary["persistent_binding_gate"]["passed"]
    assert not summary["learned_recovery_gate"]["passed"]
    assert summary["formal_claim_allowed"] is False
    assert summary["config"]["actual_steps"] == 1
    assert summary["baseline_execution"]["plans_are_seed_invariant"]
    for family in (
        summary["oracle_results"]["17"],
        *summary["b4a_results"]["17"].values(),
        *summary["baseline_results"]["17"].values(),
        summary["learned_results"]["17"],
    ):
        assert family["exact64_execution_audit"]["passed"]


def test_training_helpers_execute_exact64_path_and_freeze_adapter() -> None:
    train_batch = make_global_assignment_query_anchor_batch(
        cases_per_label=1, seed=70_001
    )
    development_batch = make_global_assignment_query_anchor_batch(
        cases_per_label=1, seed=70_003
    )
    initial_state = copy.deepcopy(_initial_projector(17).state_dict())
    adapter = _fixed_adapter()
    oracle = _train_provided(
        adapter=adapter,
        initial_state=initial_state,
        train_batch=train_batch,
        development_batch=development_batch,
        train_plan=train_batch.oracle.plan,
        development_plan=development_batch.oracle.plan,
        steps=1,
    )
    learned = _train_learned(
        adapter=adapter,
        seed=17,
        initial_projector_state=initial_state,
        train_batch=train_batch,
        development_batch=development_batch,
        steps=1,
    )
    for result in (oracle, learned):
        audit = result["exact64_execution_audit"]
        assert audit["passed"]
        assert audit["observed_adapter_score_calls"] == {
            "training": 1,
            "final_train_evaluation": 1,
            "final_development_evaluation": 1,
        }
        assert audit["observed_total_adapter_score_calls"] == 3
        assert result["frozen_adapter_unchanged"]
        assert result["complete_initial_state_sha256"]
        assert result["complete_final_state_sha256"]


def test_registered_marginal_gate_rejects_incompetent_deepsets() -> None:
    modes = (
        "current_only",
        "prior_current_separate_pooling",
        "current_only_deepsets",
        "prior_only_deepsets",
        "prior_current_deepsets",
    )
    controls = {
        "17": {
            mode: {
                "train_macro_f1": 0.95 if not mode.endswith("_deepsets") else 0.20,
                "development_macro_f1": 0.20,
                "all_gradients_finite": True,
                **(
                    {
                        "competence_probe": {
                            "train_macro_f1": 0.20,
                            "all_gradients_finite": True,
                        }
                    }
                    if mode.endswith("_deepsets")
                    else {}
                ),
            }
            for mode in modes
        }
    }
    gate = _evaluate_marginal_control_gate(controls, (17,), competence_required=True)
    assert not gate["passed"]
    assert gate["status"] == "NOT_EVALUABLE_MARGINAL_CONTROL_INCOMPETENT"

    smoke_gate = _evaluate_marginal_control_gate(
        controls, (17,), competence_required=False
    )
    assert smoke_gate["passed"]
    assert smoke_gate["status"] == "PASS"


def test_marginal_competence_probe_uses_separate_copy() -> None:
    batch = make_global_assignment_query_anchor_batch(cases_per_label=2, seed=70_011)
    prior_before = batch.regions.prior_features.clone()
    current_before = batch.regions.current_features.clone()
    probe, side = _marginal_competence_probe_batch(batch, "prior_only_deepsets")
    assert side == "prior"
    assert torch.equal(batch.regions.prior_features, prior_before)
    assert torch.equal(batch.regions.current_features, current_before)
    assert (
        probe.regions.prior_features.data_ptr()
        != batch.regions.prior_features.data_ptr()
    )
    encoded = probe.regions.prior_features[..., list(COMPETENCE_SIGNAL_CHANNELS)]
    for case in torch.nonzero(batch.persistent_main_mask).flatten().tolist():
        expected = torch.zeros(3)
        expected[int(batch.oracle.labels[case])] = COMPETENCE_SIGNAL_AMPLITUDE
        assert torch.equal(encoded[case], expected.expand(14, -1))


def test_marginal_control_metrics_recompute_from_raw_evidence() -> None:
    train_batch = make_global_assignment_query_anchor_batch(
        cases_per_label=2, seed=70_001
    )
    development_batch = make_global_assignment_query_anchor_batch(
        cases_per_label=2, seed=70_003
    )
    result = _train_marginal_control(
        seed=17,
        train_batch=train_batch,
        development_batch=development_batch,
        mode="current_only",
        steps=1,
    )

    raw = result["raw_evidence"]
    assert _recompute_macro_f1(raw["train"]) == result["train_macro_f1"]
    assert _recompute_macro_f1(raw["development"]) == result["development_macro_f1"]


def test_marginal_competence_metrics_recompute_from_raw_evidence() -> None:
    result = _train_marginal_competence_probe(
        seed=17, mode="prior_only_deepsets", steps=1
    )

    raw = result["raw_evidence"]
    assert _recompute_macro_f1(raw["train"]) == result["train_macro_f1"]
    assert _recompute_macro_f1(raw["development"]) == result["development_macro_f1"]
    assert (
        _recompute_macro_f1(raw["deranged"])
        == result["cyclic_code_derangement_macro_f1"]
    )
    permutation = raw["permutation"]
    assert len(permutation["logit_differences"]) == int(
        torch.tensor(permutation["shape"]).prod()
    )
    assert (
        max(abs(value) for value in permutation["logit_differences"])
        == result["permutation_invariance_max_logit_error"]
    )


def test_independent_reproduction_requires_exact_payload_and_zero_exit() -> None:
    primary = _eligible_reproduction_summary(
        pid=10,
        instance_uuid="11111111-1111-4111-8111-111111111111",
        walltime=1.0,
    )
    replica = _eligible_reproduction_summary(
        pid=11,
        instance_uuid="22222222-2222-4222-8222-222222222222",
        walltime=99.0,
    )
    exact = _compare_independent_reproduction(
        primary,
        replica,
        primary_returncode=0,
        replica_returncode=0,
        primary_expected_pid=10,
        replica_expected_pid=11,
    )
    assert exact["passed"]
    assert exact["primary_canonical_sha256"] == exact["replica_canonical_sha256"]

    changed = _compare_independent_reproduction(
        primary,
        {**replica, "formal_claim_allowed": True},
        primary_returncode=0,
        replica_returncode=0,
        primary_expected_pid=10,
        replica_expected_pid=11,
    )
    assert not changed["passed"]
    assert not changed["checks"]["canonical_payload_exact"]

    failed_process = _compare_independent_reproduction(
        primary,
        replica,
        primary_returncode=0,
        replica_returncode=1,
        primary_expected_pid=10,
        replica_expected_pid=11,
    )
    assert not failed_process["passed"]
    assert not failed_process["checks"]["replica_process_exit_zero"]


def test_independent_reproduction_rejects_status_only_false_pass() -> None:
    minimal_a = {
        "status": "PASS_GATES_1_TO_6_AWAITING_INDEPENDENT_REPRODUCTION",
        "process_identity": {"pid": 10, "instance_uuid": "a"},
    }
    minimal_b = {
        "status": "PASS_GATES_1_TO_6_AWAITING_INDEPENDENT_REPRODUCTION",
        "process_identity": {"pid": 11, "instance_uuid": "b"},
    }
    result = _compare_independent_reproduction(
        minimal_a,
        minimal_b,
        primary_returncode=0,
        replica_returncode=0,
        primary_expected_pid=10,
        replica_expected_pid=11,
    )
    assert not result["passed"]
    assert not result["checks"]["primary_registered_payload_eligible"]
    assert not result["checks"]["replica_registered_payload_eligible"]


def test_independent_reproduction_rejects_missing_baseline_payload() -> None:
    primary = _eligible_reproduction_summary(
        pid=10,
        instance_uuid="11111111-1111-4111-8111-111111111111",
        walltime=1.0,
    )
    replica = _eligible_reproduction_summary(
        pid=11,
        instance_uuid="22222222-2222-4222-8222-222222222222",
        walltime=1.0,
    )
    primary.pop("baseline_results")
    result = _compare_independent_reproduction(
        primary,
        replica,
        primary_returncode=0,
        replica_returncode=0,
        primary_expected_pid=10,
        replica_expected_pid=11,
    )
    assert not result["passed"]
    assert not result["checks"]["primary_registered_payload_eligible"]


def test_independent_reproduction_rejects_probe_or_manifest_tampering() -> None:
    replica = _eligible_reproduction_summary(
        pid=11,
        instance_uuid="22222222-2222-4222-8222-222222222222",
        walltime=1.0,
    )
    for mutation in ("probe", "manifest"):
        primary = _eligible_reproduction_summary(
            pid=10,
            instance_uuid="11111111-1111-4111-8111-111111111111",
            walltime=1.0,
        )
        if mutation == "probe":
            primary["marginal_controls"]["17"]["prior_only_deepsets"].pop(
                "competence_probe"
            )
        else:
            primary["source_manifest"]["files"][
                "refine-logs/CALIBRATION_PROTOCOL_R3_2026-07-22.md"
            ] = "0" * 64
        result = _compare_independent_reproduction(
            primary,
            replica,
            primary_returncode=0,
            replica_returncode=0,
            primary_expected_pid=10,
            replica_expected_pid=11,
        )
        assert not result["passed"]
        assert not result["checks"]["primary_registered_payload_eligible"]
