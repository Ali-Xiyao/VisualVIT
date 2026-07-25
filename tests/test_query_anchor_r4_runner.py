from __future__ import annotations

# ruff: noqa: E402

import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import SimpleNamespace
import uuid

import pytest
import torch

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))

import scripts.run_query_anchor_r4 as r4
import scripts.run_query_anchor_r4_reproduction as r4_reproduction


def _args(*extra: str):
    return r4.build_parser().parse_args(["--run-dir", "unused-r6", *extra])


def _fresh_source_manifest() -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json; import scripts.run_query_anchor_r4 as r; "
                "print(json.dumps(r._source_manifest(), sort_keys=True))"
            ),
        ],
        cwd=WORKSPACE,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


_FRESH_SOURCE_MANIFEST = _fresh_source_manifest()


@pytest.fixture(autouse=True)
def _unit_process_uses_fresh_closed_source_manifest(monkeypatch) -> None:
    """Keep full-suite pytest imports outside the production closed world."""

    monkeypatch.setattr(
        r4,
        "_source_manifest",
        lambda: copy.deepcopy(_FRESH_SOURCE_MANIFEST),
    )


def _gate(name: str, *, failed_gate: str | None = None) -> dict[str, object]:
    passed = name != failed_gate
    return {
        "status": "PASS" if passed else f"FAIL_{name.upper()}",
        "passed": passed,
        "checks": {"injected_gate_result": passed},
    }


def _stop_status(reason: str) -> str:
    prefix = r4.R10_REGISTRY["status_vocabulary"]["scientific_stop_prefix"]
    return f"{prefix}{reason.upper()}"


def test_bridge_uses_explicit_method_order_and_exact_method_key_sets() -> None:
    leaf = {"passed": True, "common_oracle_readout_sha256": "0" * 64}
    methods = {name: copy.deepcopy(leaf) for name in reversed(r4.EXACT64_METHOD_ORDER)}
    bridge = r4._bridge_gate(
        oracle_readouts={"17": {"exact64_execution_audit": {"passed": True}}},
        mediator_results={"17": {"exact64_execution_audit": {"passed": True}}},
        baseline_results={"17": {"clean": methods}},
        exact64_method_order=list(r4.EXACT64_METHOD_ORDER),
    )
    assert bridge["checks"]["baseline_method_order_exact"] is True
    assert bridge["passed"] is True

    reordered = r4._bridge_gate(
        oracle_readouts={"17": {"exact64_execution_audit": {"passed": True}}},
        mediator_results={"17": {"exact64_execution_audit": {"passed": True}}},
        baseline_results={"17": {"clean": methods}},
        exact64_method_order=list(reversed(r4.EXACT64_METHOD_ORDER)),
    )
    assert reordered["checks"]["baseline_method_order_exact"] is False
    assert reordered["passed"] is False


def _force_resolution_pass(monkeypatch) -> None:
    monkeypatch.setattr(
        r4,
        "_resolution_gate",
        lambda *args, **kwargs: _gate("resolution_freeze"),
    )


def _isolated_cli_output_root(monkeypatch, tmp_path: Path, *, mode: str) -> Path:
    monkeypatch.setattr(r4, "WORKSPACE", tmp_path)
    monkeypatch.setattr(
        r4,
        "_source_manifest",
        lambda: {"test_source_manifest": "stable"},
    )
    parent = tmp_path / "artifacts" / "calibration"
    parent.mkdir(parents=True)
    leaf = r4.R10_REGISTRY["output_root_contract"]["phase_leaf_names"][mode]
    return parent / leaf


def test_r25_active_authority_is_direct_and_pins_frozen_r24_full_registry() -> None:
    assert r4.FROZEN_R6_REGISTRY is r4.R25_REGISTRY
    assert r4.PROTOCOL_VERSION == "CAPES_CI_QPTM_R25_2026_07_25"
    assert (
        r4.R25_PROTOCOL_SHA256
        == r4.hashlib.sha256(r4.R25_PROTOCOL_PATH.read_bytes()).hexdigest()
    )
    assert r4.R25_REGISTRY["base_dependency"] == {
        "path": "refine-logs/CALIBRATION_PROTOCOL_R24_2026-07-24.md",
        "protocol_sha256": r4.R24_BASE_PROTOCOL_SHA256,
        "registry_sha256": r4.R24_BASE_REGISTRY_SHA256,
        "registry_sha256_semantics": (
            "r24_full_canonical_registry_including_complete_freeze_record"
        ),
        "authority_state": "FROZEN_BEFORE_R24_REPRODUCTION",
    }
    assert r4._json_hash(r4.R24_REGISTRY) == r4.R24_BASE_REGISTRY_SHA256
    assert (
        r4.IMPLEMENTED_OUTPUT_LEAVES
        == r4.R25_REGISTRY["output_root_contract"]["phase_leaf_names"]
    )


def test_r25_r14_evidence_anchor_is_distinct_from_r24_base() -> None:
    phase_contract = r4.R25_REGISTRY["phase_authorization_contract"]
    runner_guard = phase_contract["runner_guard"]
    r14_anchor = phase_contract["frozen_validator_dependency_bundle"]["origin_protocol"]

    assert runner_guard["phase_authorization_mode_closed_set"] == [
        "independent_reproduction"
    ]
    assert runner_guard["phase_authorization_required_modes"] == [
        "independent_reproduction"
    ]
    assert runner_guard["phase_authorization_denied_all_other_modes"] is True
    assert r14_anchor == {
        "relative_path": "refine-logs/CALIBRATION_PROTOCOL_R14_2026-07-23.md",
        "sha256": r4.R14_EVIDENCE_PROTOCOL_SHA256,
        "registry_sha256": r4.R14_EVIDENCE_REGISTRY_SHA256,
        "authority_state": "FROZEN_BEFORE_R14_DRY_RUN",
    }
    assert r14_anchor["sha256"] != r4.R25_REGISTRY["base_dependency"]["protocol_sha256"]


@pytest.mark.xfail(
    reason="R14-era bundle bytes unrecoverable: no git history, backups, or finalizer",
    strict=True,
)
def test_frozen_r14_validation_bundle_cannot_observe_live_r24_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A historical R14 receipt is validated by frozen bytes, never live R24.

    This is deliberately an in-process regression: preloading and then
    mutating the live semantic-validator constant must not leak through the
    isolated R14 bundle loader into the strict historical-summary validation.
    """

    from visualvit import r6_validation as live_validation

    assert live_validation._R6_INITIALIZATION_SCHEMA_VERSION == (
        "r24_initialization_evidence_v1"
    )
    monkeypatch.setattr(
        live_validation,
        "_R6_INITIALIZATION_SCHEMA_VERSION",
        "r24_live_process_mutation_must_not_leak",
    )
    declared_bundle = r4.FROZEN_R6_REGISTRY["phase_authorization_contract"][
        "frozen_validator_dependency_bundle"
    ]
    assert declared_bundle["bundle_relative_directory"] == (
        ".tmp/r16_frozen_r14_validator_bundle_v5"
    )
    assert {
        "refine-logs/CALIBRATION_PROTOCOL_R5_2026-07-22.md",
        "refine-logs/CALIBRATION_PROTOCOL_R13_2026-07-23.md",
        "refine-logs/CALIBRATION_PROTOCOL_R14_2026-07-23.md",
    }.issubset(declared_bundle["required_file_sha256"])
    loader_path = WORKSPACE / ".tmp" / "r16_frozen_r14_validation_bundle.py"
    spec = importlib.util.spec_from_file_location(
        "r16_frozen_r14_test_loader", loader_path
    )
    assert spec is not None and spec.loader is not None
    loader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loader)

    frozen_r14 = loader.load_frozen_r14_validator(workspace=WORKSPACE)
    summary_path = (
        WORKSPACE
        / "artifacts/calibration/capes_ci_qptm_r14_registered_local_20260723_v1/summary.json"
    )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    strict = frozen_r14._strict_summary_validation(summary)
    provenance = frozen_r14._r16_frozen_validation_bundle_provenance
    frozen_validator = frozen_r14.validate_r6_metric_evidence

    assert strict["passed"] is True
    assert summary["phase_authorization"]["certificate_type"] == (
        "registered_authorization"
    )
    assert (
        frozen_r14.FROZEN_R6_REGISTRY["phase_authorization_contract"]["schema_version"]
        == "r14_phase_authorization_contract_v1"
    )
    assert (
        r4.FROZEN_R6_REGISTRY["phase_authorization_contract"]["schema_version"]
        == "r24_phase_authorization_contract_v1"
    )
    assert frozen_validator.__globals__["_R6_INITIALIZATION_SCHEMA_VERSION"] == (
        "r14_initialization_evidence_v1"
    )
    assert (
        Path(frozen_validator.__code__.co_filename).resolve()
        == WORKSPACE
        / str(declared_bundle["bundle_relative_directory"])
        / "src/visualvit/r6_validation.py"
    )
    assert (
        provenance["manifest_sha256"]
        == r4.hashlib.sha256(
            (WORKSPACE / str(declared_bundle["manifest_relative_path"])).read_bytes()
        ).hexdigest()
    )
    assert provenance["module_origins"]["visualvit.r6_validation"] == (
        "src/visualvit/r6_validation.py"
    )


def test_r4_challenge_adapter_preserves_visible_wall_and_query_semantics() -> None:
    _, _, raw = r4._build_strata()
    for split, challenge in raw.items():
        adapted = r4._challenge_as_query_anchor(challenge)
        adapted.regions.validate()
        adapted.oracle.validate(adapted.regions)
        assert adapted.regions is challenge.regions
        assert adapted.oracle.labels is challenge.oracle.labels
        assert adapted.prior_query_marker.sum(dim=-1).eq(1).all(), split
        assert adapted.current_query_marker.sum() == 0
        assert adapted.oracle.plan.transport[:, -1, -1].eq(0).all()


def test_r6_resolution_and_nested_manifests_are_exact_and_fail_closed() -> None:
    strata, raw_clean, raw_challenge = r4._build_strata()
    manifest = r4._r4_split_manifest(strata, raw_clean, raw_challenge)
    source = _fresh_source_manifest()
    config = r4._registered_config(
        seeds=r4.TRAINABLE_SEEDS,
        actual_steps=r4.REGISTERED_STEPS,
        smoke=False,
        dry_run=False,
    )
    gate = r4._resolution_gate(config, source)
    assert gate["passed"] is all(gate["checks"].values())
    expected_frozen = (
        r4.R10_REGISTRY["authority_state"]
        == r4.R10_REGISTRY["status_vocabulary"]["protocol_frozen"]
        and r4.R10_REGISTRY["freeze_requirements"]["implementation_hashes_frozen"]
        and r4.R10_REGISTRY["freeze_requirements"]["dry_run_authorized"] is False
    )
    assert gate["passed"] is expected_frozen
    assert gate["checks"]["authority_final_frozen"] is expected_frozen
    assert gate["checks"]["r25_protocol_sole_authority"]
    assert gate["checks"]["r24_base_dependency_exact"]
    assert gate["checks"]["r24_base_dependency_live_sha256_exact"]
    assert gate["checks"]["r24_base_registry_live_sha256_exact"]
    assert gate["checks"]["summary_serialization_contract_exact"]
    assert gate["checks"]["atomic_failure_r12_paths_and_stages_exact"]
    assert gate["checks"]["machine_registry_exact"]
    assert gate["checks"]["enumerator_authority_files_exact"]
    assert config["protocol_authority"]["protocol_sha256"] == r4.R10_PROTOCOL_SHA256
    assert (
        config["protocol_authority"]["authority_state"]
        == (r4.R10_REGISTRY["authority_state"])
    )
    assert config["thresholds"] == r4.FROZEN_R5_REGISTRY["thresholds"]
    assert set(source) == {
        "schema_version",
        "allowlist",
        "files",
        "observed_workspace_imports",
        "source_manifest_authority_sha256",
    }
    assert set(manifest) == {"clean", "challenge"}
    assert all(set(manifest[name]) == set(r4.SPLIT_NAMES) for name in r4.STRATA)
    assert manifest["challenge"]["development"]["distractor_mapping_sha256"]


def test_r6_freeze_record_recomputes_nonself_projections(monkeypatch) -> None:
    source = _fresh_source_manifest()
    observation = r4._implementation_observation(source)
    registry = copy.deepcopy(r4.R10_REGISTRY)
    required = list(registry["freeze_requirements"]["required_hash_fields"])
    registry["implementation_observation_expected"] = observation
    registry["freeze_requirements"]["required_hash_fields"] = required
    registry.pop("freeze_record", None)
    nonprotocol_paths = [
        path for path in r4.SOURCE_ALLOWLIST if path != r4._R10_PROTOCOL_RELATIVE_PATH
    ]
    record = {
        "schema_version": r4.IMPLEMENTED_SCHEMA_VERSIONS["freeze_record"],
        "canonicalization": "utf8_json_sort_keys_compact_ascii_no_nan_v1",
        "registry_projection_excluded_json_pointers": ["/freeze_record"],
        "closed_manifest_excluded_paths": [r4._R10_PROTOCOL_RELATIVE_PATH],
        "protocol_candidate_sha256": "a" * 64,
        "implementation_observation_sha256": r4._json_hash(observation),
        **{
            field: source["files"][path]
            for field, path in tuple(r4._FREEZE_RECORD_SOURCE_FIELDS.items())[:-3]
        },
        "closed_manifest_sha256": r4._json_hash(
            {
                "allowlist": nonprotocol_paths,
                "files": {path: source["files"][path] for path in nonprotocol_paths},
            }
        ),
        "canonical_registry_sha256": r4._json_hash(registry),
        **{
            field: source["files"][path]
            for field, path in tuple(r4._FREEZE_RECORD_SOURCE_FIELDS.items())[-3:]
        },
    }
    registry["freeze_record"] = record
    monkeypatch.setattr(r4, "FROZEN_R6_REGISTRY", registry)

    checks = r4._freeze_record_validation(source, observation)
    assert all(checks.values())

    reordered = {key: record[key] for key in reversed(record)}
    assert set(reordered) == set(record)
    registry["freeze_record"] = reordered
    checks = r4._freeze_record_validation(source, observation)
    assert not checks["freeze_record_keys_exact"]

    registry["freeze_record"] = record
    registry["freeze_record"]["runner_sha256"] = "0" * 64
    checks = r4._freeze_record_validation(source, observation)
    assert not checks["freeze_record_runner_sha256_exact"]


def test_transport_stage_optimizer_owns_only_matcher_and_freezes_checkpoint() -> None:
    strata, _, _ = r4._build_strata()
    result = r4._train_transport(seed=17, strata=strata, steps=1)
    assert result["optimizer_only_matcher"]
    assert set(result["optimizer_parameter_names"]) == {
        "current_null_utility",
        "prior_null_utility",
        "residual_coefficient",
        "view_weight_logits",
    }
    assert result["finite_gradient_steps"] == 1
    assert result["nonzero_gradient_steps"] == 1
    assert result["state_unchanged_by_freeze"]
    assert all(
        not parameter.requires_grad for parameter in result["matcher"].parameters()
    )


def test_transport_metric_evidence_recomputes_all_registered_base_metrics() -> None:
    strata, _, _ = r4._build_strata()
    result = r4._train_transport(seed=17, strata=strata, steps=1)
    r4._evaluate_transport_results(
        {"17": result}, {"clean": {"development": strata["clean"]["development"]}}
    )
    metrics = result["evaluations"]["clean"]["development"]
    evidence = metrics["metric_evidence"]
    endpoint = evidence["hard_endpoint_correct"]
    assert metrics["hard_all_endpoint_assignment_accuracy"] == sum(endpoint) / len(
        endpoint
    )
    assert metrics["row_top1_accuracy"] == sum(
        predicted == actual
        for predicted, actual in zip(
            evidence["row_top1_predicted"],
            evidence["row_top1_actual"],
            strict=True,
        )
    ) / len(evidence["row_top1_actual"])
    assert metrics["soft_all_endpoint_oracle_mass"] == pytest.approx(
        sum(evidence["soft_endpoint_oracle_mass_values"])
        / evidence["soft_endpoint_oracle_mass_denominator"]
    )
    query = evidence["query"]
    assert metrics["query"]["hard_query_identity_accuracy"] == sum(
        query["hard_query_correct"]
    ) / len(query["hard_query_correct"])
    assert metrics["query"]["soft_oracle_query_mass"] == pytest.approx(
        sum(query["soft_oracle_query_mass_values"])
        / len(query["soft_oracle_query_mass_values"])
    )
    null = metrics["null_metrics"]
    for name in ("death", "birth"):
        actual = null[name]["actual"]
        predicted = null[name]["predicted"]
        assert null[name]["tp"] == sum(
            a == 1 and p == 1 for a, p in zip(actual, predicted, strict=True)
        )
        assert null[name]["tn"] == sum(
            a == 0 and p == 0 for a, p in zip(actual, predicted, strict=True)
        )


def test_query_metric_evidence_uses_the_persisted_probability_row() -> None:
    strata, _, _ = r4._build_strata()
    batch = strata["challenge"]["development"]
    hard, _, _ = r4._r4_fixed_assignment_baseline_plans(batch)
    metrics = r4._transport_metrics(batch, hard, hard)
    evidence = metrics["metric_evidence"]["query"]

    assert min(evidence["soft_oracle_query_mass_values"]) < 1e-8
    for row, oracle_index, mass, nll, brier in zip(
        evidence["soft_query_probability_rows"],
        evidence["oracle_current_indices"],
        evidence["soft_oracle_query_mass_values"],
        evidence["soft_query_nll_values"],
        evidence["soft_query_brier_values"],
        strict=True,
    ):
        assert mass == row[oracle_index]
        assert nll == -math.log(max(mass, 1e-8))
        assert brier == math.fsum(
            (value - (1.0 if column == oracle_index else 0.0)) ** 2
            for column, value in enumerate(row)
        ) / len(row)

    persisted = json.loads(
        r4._serialize_json_bytes(
            {
                "transport_results": {
                    "17": {
                        "evaluations": {
                            "challenge": {"development": metrics},
                        }
                    }
                }
            }
        )
    )
    certificate = r4.validate_r6_metric_evidence(persisted)
    assert certificate["validated"] is True
    assert certificate["checked_block_count"] == 1


def test_r6_seed_initialization_is_repeatable_distinct_and_protocol_exact() -> None:
    hashes = {
        seed: r4._state_hash(r4._new_matcher(seed)) for seed in r4.TRAINABLE_SEEDS
    }
    assert len(set(hashes.values())) == len(r4.TRAINABLE_SEEDS)
    assert r4._state_hash(r4._new_matcher(17)) == hashes[17]
    matcher = r4._new_matcher(17)
    evidence = r4._initialization_evidence(17, matcher)
    assert evidence["runtime_initial_state_sha256"] == hashes[17]
    assert evidence["runtime_state_dict_parameter_order"] == sorted(
        matcher.state_dict()
    )
    assert evidence["runtime_state_dict_shapes"]["view_weight_logits"] == [2]
    assert evidence["checks"]["runtime_state_metadata_exact"]
    assert evidence["checks"]["runtime_state_hash_exact"]
    assert (
        evidence["raw_initial_state_sha256"] != evidence["runtime_initial_state_sha256"]
    )
    values = torch.cat(
        (
            matcher.residual_coefficient.reshape(1),
            matcher.view_weight_logits,
            matcher.prior_null_utility.reshape(1),
            matcher.current_null_utility.reshape(1),
        )
    )
    assert values.tolist() == pytest.approx(
        [
            -0.014135131612420082,
            0.002336307428777218,
            0.0003403318114578724,
            0.003499172627925873,
            -0.00014521554112434387,
        ]
    )


def test_r6_null_metrics_do_not_allow_majority_accuracy_to_hide_null_failure() -> None:
    expected = torch.tensor([[True, False, False, False]])
    predicted = torch.zeros_like(expected)
    metrics = r4._binary_event_metrics(expected, predicted)
    assert metrics["non_gating_accuracy"] == 0.75
    assert metrics["recall"] == 0.0
    assert metrics["f1"] == 0.0


def test_r6_structural_counterfactuals_are_nonvacuous_and_invariant() -> None:
    strata, _, _ = r4._build_strata()
    batch = strata["clean"]["train"]
    matcher = r4._new_matcher(17)
    hidden = r4._hidden_id_relabel_audit(batch, matcher)
    permutation = r4._endpoint_permutation_audit(batch, matcher)
    assert hidden["passed"]
    assert hidden["original_id_sha256"] != hidden["relabeled_id_sha256"]
    assert permutation["passed"]


def test_r6_local_baseline_is_pure_row_local_and_allows_duplicate_current() -> None:
    strata, _, _ = r4._build_strata()
    batch = strata["challenge"]["development"]

    class CollidingMatcher:
        def compute_utilities(self, regions):
            batch_size, prior_count = regions.prior_valid.shape
            current_count = regions.current_valid.shape[1]
            edge = torch.full((batch_size, prior_count, current_count), -1.0)
            for case in range(batch_size):
                for anatomy in regions.prior_anatomy[case].unique().tolist():
                    current = int(
                        torch.nonzero(regions.current_anatomy[case] == anatomy)[0]
                    )
                    edge[case, :, current] = 1.0
            return (
                edge,
                torch.zeros(batch_size, prior_count),
                torch.zeros(batch_size, current_count),
            )

    output = r4._local_row_output(CollidingMatcher(), batch)
    metrics = r4._local_row_metrics(batch, output)
    contract = r4._local_query_contract(batch, output)
    assert torch.allclose(
        output["row_probabilities"].sum(dim=-1),
        torch.ones_like(output["row_probabilities"][..., 0]),
    )
    assert metrics["duplicate_current_rows"] > 0
    assert contract.tokens.shape[1] == 64
    assert not hasattr(output, "validate")


def test_r6_local_baseline_one_step_updates_only_matched_parameters() -> None:
    strata, _, _ = r4._build_strata()
    result = r4._train_local_baseline(seed=17, strata=strata, steps=1)
    assert result["allocator"] == "pure_row_local_softmax_with_private_death"
    assert result["calls_global_solver"] is False
    assert result["column_normalization_used"] is False
    assert result["column_competition_used"] is False
    assert result["finite_gradient_steps"] == 1
    assert result["registered_gradient_steps"] == 1
    assert (
        result["initial_state_sha256"]
        == result["initialization"]["runtime_initial_state_sha256"]
    )
    assert (
        result["initial_state_sha256"]
        != result["initialization"]["raw_initial_state_sha256"]
    )
    assert set(result["optimizer_parameter_names"]) == {
        "current_null_utility",
        "prior_null_utility",
        "residual_coefficient",
        "view_weight_logits",
    }


def test_gate_zero_failure_materializes_no_split(monkeypatch) -> None:
    monkeypatch.setattr(
        r4,
        "_resolution_gate",
        lambda *args, **kwargs: {"status": "FAIL_RESOLUTION_FREEZE", "passed": False},
    )

    def forbidden():
        raise AssertionError("split materialized before Gate 0 passed")

    monkeypatch.setattr(r4, "_build_strata", forbidden)
    summary = r4.run(_args())
    assert summary["status"] == _stop_status("resolution_freeze")
    assert summary["data_access_ledger"] == []
    assert "split_manifests" not in summary


def test_r6_audit_fixture_hashes_match_registry_without_registered_dev() -> None:
    _, raw = r4._build_audit_fixtures()
    for stratum in r4.STRATA:
        observed = r4._raw_fixture_hashes(raw[stratum])
        expected = r4.FROZEN_R5_REGISTRY["fixture_hashes"][stratum]
        assert observed["visible"] == expected["fixture_development_visible"]
        assert observed["hidden_oracle"] == expected["fixture_development_oracle"]


def test_r6_dry_run_ledger_rejects_registered_development_hash() -> None:
    stages = [
        ("structural_input", "clean", "literal_audit_fixture"),
        ("structural_input", "challenge", "literal_audit_fixture"),
        ("fixture_identifiability", "clean", "frozen_fixture_audit"),
        ("fixture_identifiability", "challenge", "frozen_fixture_audit"),
    ]
    ledger = []
    for index, (gate_name, stratum, split) in enumerate(stages):
        ledger.append(
            r4._access_ledger_entry(
                gate=gate_name,
                stratum=stratum,
                split=split,
                name=f"{stratum}_{split}",
                purpose="unit_test_registry_allowlist",
                content_hash=f"{index + 1:064x}",
                cache_hit=gate_name == "fixture_identifiability",
            )
        )
    manifests = {stratum: {"audit_fixture": {}} for stratum in r4.STRATA}
    assert r4._dry_run_access_ledger_gate(ledger, manifests)["passed"]

    tampered = copy.deepcopy(ledger)
    tampered[-1]["content_sha256"] = r4.FROZEN_R5_REGISTRY["fixture_hashes"]["clean"][
        "development_visible"
    ]
    gate = r4._dry_run_access_ledger_gate(tampered, manifests)
    assert not gate["passed"]
    assert not gate["checks"]["registered_inner_or_development_hash_absent"]


def test_mediator_stage_freezes_matcher_and_exact64_adapter() -> None:
    strata, _, _ = r4._build_strata()
    transport = r4._train_transport(seed=17, strata=strata, steps=1)
    matcher = transport["matcher"]
    matcher_before = r4._state_hash(matcher)
    plans = r4._frozen_matcher_plans(matcher, strata)
    result = r4._fit_readout(
        adapter=r4._fixed_adapter(),
        seed=17,
        strata=strata,
        plans=plans,
        steps=1,
        phase_prefix="mediator_readout",
        frozen_matcher=matcher,
    )
    assert result["exact64_execution_audit"]["passed"]
    assert result["matcher_gradients_zero"]
    assert result["matcher_unchanged"]
    assert r4._state_hash(matcher) == matcher_before
    assert result["optimizer_only_projector"]


def test_oracle_readout_is_one_joint_fit_and_then_frozen() -> None:
    strata, _, _ = r4._build_strata()
    result = r4._fit_readout(
        adapter=r4._fixed_adapter(),
        seed=17,
        strata=strata,
        plans=r4._oracle_plans(strata),
        steps=1,
        phase_prefix="oracle_readout",
    )
    expected = {
        "oracle_readout_training_clean": 1,
        "oracle_readout_training_challenge": 1,
        "oracle_readout_final_clean_train": 1,
        "oracle_readout_final_clean_development": 1,
        "oracle_readout_final_challenge_train": 1,
        "oracle_readout_final_challenge_development": 1,
    }
    assert result["exact64_execution_audit"]["observed_adapter_score_calls"] == expected
    assert result["projector_state_unchanged_by_freeze"]
    assert all(
        not parameter.requires_grad for parameter in result["model"].parameters()
    )


def test_r4_fixed_baselines_are_feasible_on_both_strata() -> None:
    strata, _, _ = r4._build_strata()
    for stratum in r4.STRATA:
        batch = strata[stratum]["development"]
        hard, soft, contract_hash = r4._r4_fixed_assignment_baseline_plans(batch)
        hard.validate(batch.regions)
        soft.validate(batch.regions)
        assert len(contract_hash) == 64
        assert hard.transport[:, -1, -1].eq(0).all()
        assert soft.transport[:, -1, -1].eq(0).all()


def test_registered_run_stops_at_structural_failure_without_training(
    monkeypatch,
) -> None:
    _force_resolution_pass(monkeypatch)
    monkeypatch.setattr(
        r4,
        "_structural_gate",
        lambda *args, **kwargs: {
            "status": "FAIL_STRUCTURAL_INPUT",
            "passed": False,
        },
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("training was executed after structural failure")

    monkeypatch.setattr(r4, "_fit_readout", forbidden)
    summary = r4.run(_args())
    assert summary["status"] == _stop_status("structural_input")
    assert summary["stopped_at_gate"] == "structural_input"
    assert "oracle_readout_results" not in summary
    assert all(
        set(summary["split_manifests"][stratum]) == {"audit_fixture"}
        for stratum in r4.STRATA
    )
    assert [
        (entry["gate"], entry["stratum"], entry["split"])
        for entry in summary["data_access_ledger"]
    ] == [
        ("structural_input", "clean", "literal_audit_fixture"),
        ("structural_input", "challenge", "literal_audit_fixture"),
    ]


def test_registered_run_stops_at_transport_before_mediator_or_baseline(
    monkeypatch,
) -> None:
    _force_resolution_pass(monkeypatch)
    monkeypatch.setattr(
        r4,
        "_structural_gate",
        lambda *args, **kwargs: {"status": "PASS", "passed": True},
    )
    monkeypatch.setattr(
        r4,
        "_fixture_authority_dry_run_gate",
        lambda **kwargs: _gate("fixture_identifiability"),
    )
    matcher = r4._new_matcher()
    for parameter in matcher.parameters():
        parameter.requires_grad_(False)
    monkeypatch.setattr(
        r4,
        "_train_transport",
        lambda **kwargs: {
            "matcher": matcher,
            "evaluations": {stratum: {} for stratum in r4.STRATA},
        },
    )
    monkeypatch.setattr(r4, "_evaluate_transport_results", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        r4,
        "_transport_gates",
        lambda *args, **kwargs: (
            {"status": "FAIL_TRANSPORT_COMPETENCE", "passed": False},
            {"status": "FAIL_ANTI_EQUIVALENCE", "passed": False},
        ),
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("downstream gate executed after transport failure")

    monkeypatch.setattr(r4, "_frozen_matcher_plans", forbidden)
    monkeypatch.setattr(r4, "_baseline_gate", forbidden)
    summary = r4.run(_args())
    assert summary["status"] == _stop_status("transport_competence")
    assert summary["stopped_at_gate"] == "transport_competence"
    assert "mediator_results" not in summary
    assert "fair_baseline_gate" not in summary
    assert [
        (entry["gate"], entry["stratum"], entry["split"])
        for entry in summary["data_access_ledger"]
    ] == [
        ("structural_input", "clean", "literal_audit_fixture"),
        ("structural_input", "challenge", "literal_audit_fixture"),
        ("fixture_identifiability", "clean", "frozen_fixture_audit"),
        ("fixture_identifiability", "challenge", "frozen_fixture_audit"),
        ("transport_competence", "clean", "train"),
        ("transport_competence", "challenge", "train"),
        ("transport_competence", "clean", "inner_development"),
        ("transport_competence", "challenge", "inner_development"),
        ("transport_competence", "clean", "development"),
    ]


@pytest.mark.parametrize(
    "failed_gate",
    [
        "resolution_freeze",
        "fixture_identifiability",
        "anti_equivalence",
        "mediator_recovery",
        "fair_baseline",
        "exact64_bridge",
    ],
)
def test_registered_run_stops_at_every_remaining_failed_gate(
    monkeypatch, failed_gate: str
) -> None:
    monkeypatch.setattr(
        r4,
        "_resolution_gate",
        lambda *args, **kwargs: _gate("resolution_freeze", failed_gate=failed_gate),
    )
    monkeypatch.setattr(
        r4,
        "_structural_gate",
        lambda *args, **kwargs: _gate("structural_input", failed_gate=failed_gate),
    )
    monkeypatch.setattr(
        r4,
        "_fixture_authority_dry_run_gate",
        lambda **kwargs: _gate("fixture_identifiability", failed_gate=failed_gate),
    )

    dummy_projector = r4._initial_projector(17)
    for parameter in dummy_projector.parameters():
        parameter.requires_grad_(False)
    monkeypatch.setattr(
        r4,
        "_fit_readout",
        lambda **kwargs: {
            "model": dummy_projector,
            "execution_kind": kwargs["phase_prefix"],
        },
    )
    monkeypatch.setattr(
        r4,
        "_fixture_gate",
        lambda **kwargs: (
            {"status": "PASS", "passed": True},
            {},
            {},
        ),
    )

    matcher = r4._new_matcher()
    for parameter in matcher.parameters():
        parameter.requires_grad_(False)
    monkeypatch.setattr(
        r4,
        "_train_transport",
        lambda **kwargs: {
            "matcher": matcher,
            "evaluations": {stratum: {} for stratum in r4.STRATA},
        },
    )
    monkeypatch.setattr(r4, "_evaluate_transport_results", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        r4,
        "_transport_gates",
        lambda *args, **kwargs: (
            _gate("transport_competence", failed_gate=failed_gate),
            _gate("anti_equivalence", failed_gate=failed_gate),
        ),
    )
    monkeypatch.setattr(
        r4,
        "_frozen_matcher_plans",
        lambda frozen_matcher, strata: r4._oracle_plans(strata),
    )
    monkeypatch.setattr(
        r4,
        "_mediator_gate",
        lambda *args, **kwargs: _gate("mediator_recovery", failed_gate=failed_gate),
    )
    monkeypatch.setattr(r4, "_train_local_baseline", lambda **kwargs: {})
    monkeypatch.setattr(
        r4,
        "_baseline_gate",
        lambda **kwargs: (
            _gate("fair_baseline", failed_gate=failed_gate),
            {},
        ),
    )
    monkeypatch.setattr(
        r4,
        "_bridge_gate",
        lambda **kwargs: _gate("exact64_bridge", failed_gate=failed_gate),
    )
    monkeypatch.setattr(
        r4,
        "run_r6_counterfactual_audits",
        lambda *args, **kwargs: {
            "passed": True,
            "report_sha256": r4._json_hash({"passed": True}),
        },
    )
    monkeypatch.setattr(
        r4,
        "validate_r6_counterfactual_audit",
        lambda *args, **kwargs: None,
    )

    summary = r4.run(_args())
    gate_index = r4.GATE_ORDER.index(failed_gate)
    assert summary["status"] == _stop_status(failed_gate)
    assert summary["stopped_at_gate"] == failed_gate
    assert [record["name"] for record in summary["completed_gates"]] == list(
        r4.GATE_ORDER[: gate_index + 1]
    )
    assert summary["not_run_gates"] == list(r4.GATE_ORDER[gate_index + 1 :])


def test_reproduction_eligibility_fails_closed_on_config_or_freeze_tampering() -> None:
    summary = {
        "status": r4.PENDING_STATUS,
        "config": r4._registered_config(
            seeds=r4.TRAINABLE_SEEDS,
            actual_steps=r4.REGISTERED_STEPS,
            smoke=False,
            dry_run=False,
        ),
    }
    summary["config_sha256"] = r4._json_hash(summary["config"])
    assert not r4._registered_reproduction_eligibility(summary)["passed"]
    tampered = copy.deepcopy(summary)
    tampered["config"]["transport"]["residual_cap"] = 0.03
    tampered["config_sha256"] = r4._json_hash(tampered["config"])
    eligibility = r4._registered_reproduction_eligibility(tampered)
    assert not eligibility["passed"]
    assert not eligibility["checks"]["config_exact"]
    assert not eligibility["checks"]["summary_keys_exact"]


def test_r9_external_materializer_provenance_is_exact_and_fail_closed(
    monkeypatch,
) -> None:
    registry = copy.deepcopy(r4.FROZEN_R6_REGISTRY)
    registry["phase_authorization_contract"]["external_materializers"] = {
        "test_auditor": {
            "relative_path": ".tmp/test_auditor.py",
            "sha256": "a" * 64,
            "sha256_rule": "sha256_over_exact_regular_file_bytes",
            "invocation": {
                "working_directory_relative": ".",
                "argv0_must_resolve_to_materializer_relative_path": True,
                "argv_tail": [],
            },
        }
    }
    monkeypatch.setattr(r4, "FROZEN_R6_REGISTRY", registry)
    provenance = {
        "materializer_id": "test_auditor",
        "relative_path": ".tmp/test_auditor.py",
        "sha256": "a" * 64,
        "invocation": {
            "working_directory_relative": ".",
            "argv0_relative_path": ".tmp/test_auditor.py",
            "argv_tail": [],
        },
    }
    assert r4._materializer_provenance_matches_frozen_contract(
        provenance, materializer_id="test_auditor"
    )

    for mutation in (
        lambda value: value.__setitem__("sha256", "b" * 64),
        lambda value: value["invocation"].__setitem__("argv_tail", ["--extra"]),
        lambda value: value.__setitem__("unexpected", True),
    ):
        tampered = copy.deepcopy(provenance)
        mutation(tampered)
        assert not r4._materializer_provenance_matches_frozen_contract(
            tampered, materializer_id="test_auditor"
        )


def test_r15_prerequisite_audit_requires_its_frozen_materializer_provenance(
    monkeypatch,
) -> None:
    registry = copy.deepcopy(r4.FROZEN_R6_REGISTRY)
    contract = registry["phase_authorization_contract"]
    contract["external_materializers"]["registered_reproduction_authorizer"][
        "sha256"
    ] = "a" * 64
    monkeypatch.setattr(r4, "FROZEN_R6_REGISTRY", registry)
    audit_contract = contract["registered_postrun_audit_contract"]
    specification = contract["reproduction_authorization"]
    materializer = contract["external_materializers"][
        "registered_reproduction_authorizer"
    ]
    audit = {
        "schema_version": audit_contract["schema_version"],
        "run_dir": "artifacts/calibration/dry-run",
        "passed": True,
        "verdict": specification["prerequisite_audit_verdict"],
        "checks": {name: True for name in audit_contract["required_exact_check_keys"]},
        "failed_checks": [],
        "evidence": {
            "materializer_provenance": {
                "materializer_id": "registered_reproduction_authorizer",
                "relative_path": materializer["relative_path"],
                "sha256": materializer["sha256"],
                "invocation": {
                    "working_directory_relative": ".",
                    "argv0_relative_path": materializer["relative_path"],
                    "argv_tail": [],
                },
            }
        },
    }
    audit["audit_sha256"] = r4._authorization_self_hash(audit, "audit_sha256")
    assert r4._validate_prerequisite_audit(audit, specification)

    audit["evidence"]["materializer_provenance"]["materializer_id"] = "forged"
    audit["audit_sha256"] = r4._authorization_self_hash(audit, "audit_sha256")
    assert not r4._validate_prerequisite_audit(audit, specification)


def test_stop_status_cli_exit_is_nonzero(monkeypatch, tmp_path: Path) -> None:
    _force_resolution_pass(monkeypatch)
    monkeypatch.setattr(r4, "_phase_authorize", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        r4,
        "_strict_summary_validation",
        lambda summary: {"passed": True, "errors": []},
    )
    monkeypatch.setattr(r4, "_final_publication_authority_recheck", lambda *_args: None)
    monkeypatch.setattr(
        r4,
        "run",
        lambda args: {
            "status": _stop_status("transport_competence"),
            "formal_claim_allowed": False,
        },
    )
    run_dir = _isolated_cli_output_root(monkeypatch, tmp_path, mode="registered_local")
    exit_code = r4.main(["--run-dir", str(run_dir)])
    assert exit_code == 3
    assert (run_dir / "summary.json").is_file()


def test_gate_zero_cli_failure_does_not_create_output_root(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        r4,
        "_resolution_gate",
        lambda *args, **kwargs: _gate(
            "resolution_freeze", failed_gate="resolution_freeze"
        ),
    )
    run_dir = _isolated_cli_output_root(monkeypatch, tmp_path, mode="registered_local")
    exit_code = r4.main(["--run-dir", str(run_dir)])
    assert exit_code == 4
    assert not run_dir.exists()


def test_r13_dry_run_reaches_run_only_after_resolution_without_phase_claim(
    monkeypatch, tmp_path: Path
) -> None:
    run_dir = _isolated_cli_output_root(monkeypatch, tmp_path, mode="dry_run")
    run_called = False

    monkeypatch.setattr(
        r4,
        "_resolution_gate",
        lambda *args, **kwargs: {
            "status": "PASS",
            "passed": True,
            "checks": {
                "authority_final_frozen": True,
                "dry_run_authorized": True,
            },
        },
    )
    monkeypatch.setattr(
        r4,
        "_phase_authorize",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("dry run must not authorize a phase")
        ),
    )
    monkeypatch.setattr(
        r4,
        "_write_phase_claim",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("dry run must not create a phase claim")
        ),
    )
    monkeypatch.setattr(
        r4,
        "_strict_summary_validation",
        lambda _summary: {"passed": True, "errors": []},
    )
    monkeypatch.setattr(r4, "_final_publication_authority_recheck", lambda *_args: None)

    def run_dry_run(_args):
        nonlocal run_called
        run_called = True
        return {
            "status": r4.IMPLEMENTED_STATUS_VOCABULARY["dry_run_success"],
            "formal_claim_allowed": False,
        }

    monkeypatch.setattr(r4, "run", run_dry_run)

    assert r4.main(["--run-dir", str(run_dir), "--dry-run"]) == 0
    assert run_called is True
    assert (run_dir / "summary.json").is_file()


def test_r13_dry_run_resolution_failure_is_pre_root(
    monkeypatch, tmp_path: Path
) -> None:
    run_dir = _isolated_cli_output_root(monkeypatch, tmp_path, mode="dry_run")
    monkeypatch.setattr(
        r4,
        "_resolution_gate",
        lambda *args, **kwargs: {
            "status": "FAIL_RESOLUTION_FREEZE",
            "passed": False,
            "checks": {
                "authority_final_frozen": False,
                "dry_run_authorized": False,
            },
        },
    )
    monkeypatch.setattr(
        r4,
        "run",
        lambda _args: (_ for _ in ()).throw(
            AssertionError("dry run executed after failed frozen resolution")
        ),
    )

    assert r4.main(["--run-dir", str(run_dir), "--dry-run"]) == 4
    assert not run_dir.exists()


@pytest.mark.parametrize(
    ("mode", "argv"),
    [
        ("smoke", ["--smoke", "--seeds", "17"]),
        ("registered_local", []),
    ],
)
def test_r13_smoke_and_registered_modes_require_pre_root_authorization(
    monkeypatch, tmp_path: Path, mode: str, argv: list[str]
) -> None:
    run_dir = _isolated_cli_output_root(monkeypatch, tmp_path, mode=mode)
    _force_resolution_pass(monkeypatch)
    monkeypatch.setattr(
        r4,
        "_phase_authorize",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            r4._phase_authorization_failure("R13 certificate is absent")
        ),
    )
    monkeypatch.setattr(
        r4,
        "run",
        lambda _args: (_ for _ in ()).throw(
            AssertionError("unauthorized R13 mode reached run")
        ),
    )

    assert r4.main(["--run-dir", str(run_dir), *argv]) == 4
    assert not run_dir.exists()


def test_cli_rejects_noncanonical_output_root_before_resolution(
    monkeypatch, tmp_path: Path
) -> None:
    called = False

    def resolution(*args, **kwargs):
        nonlocal called
        called = True
        return _gate("resolution_freeze")

    monkeypatch.setattr(r4, "_resolution_gate", resolution)
    monkeypatch.setattr(r4, "WORKSPACE", tmp_path)
    (tmp_path / "artifacts" / "calibration").mkdir(parents=True)
    run_dir = tmp_path / "wrong-output-root"
    exit_code = r4.main(["--run-dir", str(run_dir)])
    assert exit_code == 4
    assert called is False
    assert not run_dir.exists()


def test_output_root_contract_rejects_workspace_internal_reparse_component(
    monkeypatch, tmp_path: Path
) -> None:
    run_dir = _isolated_cli_output_root(monkeypatch, tmp_path, mode="registered_local")
    args = r4.build_parser().parse_args(["--run-dir", str(run_dir)])
    args._raw_run_dir = args.run_dir
    args.run_dir = args.run_dir.resolve()
    original_stat = os.stat
    reparse_component = tmp_path / "artifacts"

    def mocked_stat(path, *args, **kwargs):
        metadata = original_stat(path, *args, **kwargs)
        if Path(path) == reparse_component:
            return SimpleNamespace(
                st_mode=metadata.st_mode,
                st_file_attributes=getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400),
            )
        return metadata

    monkeypatch.setattr(r4.os, "stat", mocked_stat)
    contract = r4._output_root_contract(args)
    assert contract["checks"]["plain_workspace_ancestor_chain"] is False
    assert contract["passed"] is False


def test_pre_root_authorization_target_path_accepts_absent_authorized_smoke_root(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(r4, "WORKSPACE", tmp_path)
    specification = r4.FROZEN_R6_REGISTRY["phase_authorization_contract"][
        "reproduction_authorization"
    ]
    target = tmp_path / str(
        specification["child_certificates"]["process_a"]["target_output_root_relative"]
    )
    target.parent.mkdir(parents=True)

    assert not target.exists()
    assert (
        r4._pre_root_authorization_target_relative(target)
        == specification["child_certificates"]["process_a"][
            "target_output_root_relative"
        ]
    )


@pytest.mark.parametrize("target_kind", ("missing_parent", "escape", "reparse"))
def test_pre_root_authorization_target_path_rejects_unsafe_target(
    monkeypatch, tmp_path: Path, target_kind: str
) -> None:
    monkeypatch.setattr(r4, "WORKSPACE", tmp_path)
    safe_parent = tmp_path / "artifacts" / "calibration"
    safe_parent.mkdir(parents=True)
    if target_kind == "missing_parent":
        target = tmp_path / "missing" / "leaf"
    elif target_kind == "escape":
        target = tmp_path.parent / "outside" / "leaf"
    else:
        target = safe_parent / "leaf"
        original_stat = os.stat

        def mocked_stat(path, *args, **kwargs):
            metadata = original_stat(path, *args, **kwargs)
            if Path(path) == safe_parent:
                return SimpleNamespace(
                    st_mode=metadata.st_mode,
                    st_file_attributes=getattr(
                        stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400
                    ),
                )
            return metadata

        monkeypatch.setattr(r4.os, "stat", mocked_stat)

    with pytest.raises(ValueError):
        r4._pre_root_authorization_target_relative(target)


def test_safe_authority_read_rejects_parent_identity_drift(
    monkeypatch, tmp_path: Path
) -> None:
    """A post-validation parent swap must not be silently followed for authority IO."""

    monkeypatch.setattr(r4, "WORKSPACE", tmp_path)
    parent = tmp_path / "authority"
    parent.mkdir()
    artifact = parent / "certificate.json"
    artifact.write_text('{"ok":true}', encoding="utf-8")
    original_stat = os.stat
    parent_observations = 0

    def drifting_stat(path, *args, **kwargs):
        nonlocal parent_observations
        metadata = original_stat(path, *args, **kwargs)
        if Path(path) == parent and kwargs.get("follow_symlinks") is False:
            parent_observations += 1
            if parent_observations >= 2:
                return SimpleNamespace(
                    st_dev=metadata.st_dev,
                    st_ino=metadata.st_ino + 1,
                    st_mode=metadata.st_mode,
                    st_size=metadata.st_size,
                    st_mtime_ns=metadata.st_mtime_ns,
                    st_ctime_ns=metadata.st_ctime_ns,
                    st_file_attributes=getattr(metadata, "st_file_attributes", 0),
                )
        return metadata

    monkeypatch.setattr(r4.os, "stat", drifting_stat)
    with pytest.raises(ValueError, match="workspace path.*drifted"):
        r4._authorization_snapshot(artifact)


def test_phase_claim_revalidates_target_and_parent_immediately_before_excl_open(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(r4, "WORKSPACE", tmp_path)
    parent = tmp_path / "claims"
    parent.mkdir()
    claim_path = parent / "claim.json"
    observed_rechecks: list[Path] = []
    original_revalidate = r4._revalidate_workspace_path_snapshot
    original_open = os.open

    def recording_revalidate(snapshot, **kwargs):
        observed_rechecks.append(Path(snapshot["raw_path"]))
        return original_revalidate(snapshot, **kwargs)

    def guarded_open(path, flags, mode=0o777):
        if Path(path) == claim_path and flags & os.O_EXCL:
            assert observed_rechecks[-2:] == [claim_path, parent]
        return original_open(path, flags, mode)

    monkeypatch.setattr(r4, "_revalidate_workspace_path_snapshot", recording_revalidate)
    monkeypatch.setattr(r4.os, "open", guarded_open)
    payload = {"claim": "fixed"}
    assert r4._write_phase_claim(
        claim_path, payload
    ) == r4._authorization_canonical_bytes(payload)
    assert json.loads(claim_path.read_text(encoding="utf-8")) == payload


def test_unhandled_cli_failure_writes_fail_closed_evidence(
    monkeypatch, tmp_path: Path
) -> None:
    def fail(args):
        raise RuntimeError("synthetic baseline failure")

    _force_resolution_pass(monkeypatch)
    monkeypatch.setattr(r4, "_phase_authorize", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(r4, "run", fail)
    run_dir = _isolated_cli_output_root(monkeypatch, tmp_path, mode="smoke")
    exit_code = r4.main(["--run-dir", str(run_dir), "--smoke", "--seeds", "17"])
    failure = json.loads((run_dir / "failure.json").read_text(encoding="utf-8"))
    assert exit_code == 4
    assert (
        failure["status"]
        == r4.FROZEN_R6_REGISTRY["status_vocabulary"]["technical_failure"]
    )
    assert failure["exception_type"] == "RuntimeError"
    assert failure["summary_written"] is False
    assert failure["formal_claim_allowed"] is False
    assert not (run_dir / "summary.json").exists()


def test_r24_child_certificates_are_leaf_bound_and_claimed_independently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One R24 child certificate must neither authorize nor replay as the other."""

    workspace = WORKSPACE / ".tmp" / f"r24-child-cert-test-{uuid.uuid4().hex}"
    workspace.mkdir(parents=False, exist_ok=False)
    parent = (
        workspace
        / "artifacts"
        / "calibration"
        / r4.IMPLEMENTED_OUTPUT_LEAVES["reproduction_local"]
    )
    parent.mkdir(parents=True)
    # R25 is the live authority; the reproduction certificate flow runs under
    # R25's authority_state/protocol_id, so the fixture must derive from R25.
    registry = copy.deepcopy(r4.R25_REGISTRY)
    registry["authority_state"] = registry["status_vocabulary"]["protocol_frozen"]
    registry["freeze_requirements"]["implementation_hashes_frozen"] = True
    contract = registry["phase_authorization_contract"]
    specification = contract["reproduction_authorization"]
    authorization_root = workspace / contract["authorization_root_relative"]
    authorization_root.mkdir(parents=True)
    prerequisite_summary = workspace / specification["prerequisite_summary_path"]
    prerequisite_summary.parent.mkdir(parents=True, exist_ok=True)
    prerequisite_summary.write_text(
        json.dumps({"status": specification["prerequisite_summary_status"]}),
        encoding="utf-8",
    )
    prerequisite_audit = workspace / specification["prerequisite_audit_path"]
    prerequisite_audit.parent.mkdir(parents=True, exist_ok=True)
    prerequisite_audit.write_text('{"audit_sha256":null}', encoding="utf-8")
    source = copy.deepcopy(_FRESH_SOURCE_MANIFEST)

    monkeypatch.setattr(r4, "WORKSPACE", workspace)
    monkeypatch.setattr(r4, "FROZEN_R6_REGISTRY", registry)
    monkeypatch.setattr(
        r4,
        "_relative_authorization_path",
        lambda path: Path(path).relative_to(workspace).as_posix(),
    )
    monkeypatch.setattr(
        r4, "_materializer_provenance_matches_frozen_contract", lambda *_a, **_k: True
    )
    monkeypatch.setattr(r4, "_validate_prerequisite_audit", lambda *_a, **_k: True)

    certificates: dict[str, Path] = {}
    for index, leaf in enumerate(specification["target_child_leaf_names"]):
        child = specification["child_certificates"][leaf]
        certificate = {
            "schema_version": child["schema_version"],
            "certificate_type": child["certificate_type"],
            "certificate_id": (
                "11111111-1111-4111-8111-111111111111"
                if index == 0
                else "22222222-2222-4222-8222-222222222222"
            ),
            "phase_nonce": ("a" if index == 0 else "b") * 64,
            "protocol_id": r4.PROTOCOL_VERSION,
            "protocol_sha256": r4.R11_PROTOCOL_SHA256,
            "registry_sha256": r4._json_hash(registry),
            "source_manifest_authority_sha256": source[
                "source_manifest_authority_sha256"
            ],
            "materializer_provenance": {},
            "target_phase": specification["target_phase"],
            "target_output_parent_relative": specification[
                "target_output_parent_relative"
            ],
            "target_child_leaf": leaf,
            "target_output_root_relative": child["target_output_root_relative"],
            "target_seeds": list(r4.TRAINABLE_SEEDS),
            "target_steps": r4.REGISTERED_STEPS,
            "target_device": "cpu",
            "prerequisite_summary_path": specification["prerequisite_summary_path"],
            "prerequisite_summary_sha256": r4.hashlib.sha256(
                prerequisite_summary.read_bytes()
            ).hexdigest(),
            "prerequisite_audit_path": specification["prerequisite_audit_path"],
            "prerequisite_audit_file_sha256": r4.hashlib.sha256(
                prerequisite_audit.read_bytes()
            ).hexdigest(),
            "prerequisite_audit_self_sha256": None,
            "prerequisite_audit_verdict": specification["prerequisite_audit_verdict"],
            "prerequisite_audit_passed": True,
            "formal_data_authorization": specification[
                "formal_data_authorization_expected"
            ],
            "formal_test_used": specification["formal_test_used_expected"],
            "formal_claim_flags": specification["formal_claim_flags_expected"],
            "checks": {
                key: True
                for key in specification["child_certificate_required_exact_check_keys"]
            },
            "authorized": True,
            "authorization_status": specification["authorization_status"],
            "issued_utc": "2026-07-23T00:00:00.000000Z",
        }
        certificate["certificate_self_sha256"] = r4._authorization_self_hash(
            certificate, "certificate_self_sha256"
        )
        path = workspace / child["relative_path"]
        path.write_bytes(r4._authorization_canonical_bytes(certificate))
        certificates[leaf] = path

    def authorize(leaf: str, process_uuid: str):
        args = r4.build_parser().parse_args(
            [
                "--run-dir",
                str(parent / leaf),
                "--steps",
                "500",
                "--seeds",
                "17",
                "29",
                "43",
            ]
        )
        return r4._phase_authorize(
            args, process_uuid=process_uuid, source_manifest=source
        )

    receipt_a = authorize("process_a", "33333333-3333-4333-8333-333333333333")
    receipt_b = authorize("process_b", "44444444-4444-4444-8444-444444444444")
    assert receipt_a["certificate_path"] != receipt_b["certificate_path"]
    assert receipt_a["target_child_leaf"] == "process_a"
    assert receipt_b["target_child_leaf"] == "process_b"
    assert receipt_a["claim_path"] != receipt_b["claim_path"]

    assert (
        receipt_a["source_manifest_authority_sha256"]
        == source["source_manifest_authority_sha256"]
    )
    assert r4._authorization_source_manifest_hash_matches(
        receipt_a, {"source_manifest": source}
    )
    assert not r4._authorization_source_manifest_hash_matches(
        receipt_a,
        {"source_manifest": {"source_manifest_authority_sha256": "c" * 64}},
    )

    with pytest.raises(RuntimeError, match="certificate claim already exists"):
        authorize("process_a", "55555555-5555-4555-8555-555555555555")

    # A process-A certificate cannot be made to authorize B merely by swapping
    # files: the fixed certificate type/root pair is checked before any claim.
    certificates["process_b"].write_bytes(certificates["process_a"].read_bytes())
    with pytest.raises(RuntimeError, match="fixed authority fields differ"):
        authorize("process_b", "66666666-6666-4666-8666-666666666666")


def _r24_terminal_authorization_fixture(
    monkeypatch: pytest.MonkeyPatch,
    workspace: Path,
    *,
    specification_mutation=None,
    provenance_mutation=None,
) -> dict[str, object]:
    """Materialize a complete R24 terminal receipt using production validators."""

    # R25 is the live authority; the terminal receipt must carry R25's
    # protocol_id so it matches the unpatched PROTOCOL_VERSION constant.
    registry = copy.deepcopy(r4.R25_REGISTRY)
    registry["authority_state"] = registry["status_vocabulary"]["protocol_frozen"]
    registry["freeze_requirements"]["implementation_hashes_frozen"] = True
    contract = registry["phase_authorization_contract"]
    specification = contract["reproduction_authorization"]
    if specification_mutation is not None:
        specification_mutation(specification)

    materializer_id = "registered_reproduction_authorizer"
    materializer_path = workspace / ".tmp" / "audit_r24_registered.py"
    materializer_path.parent.mkdir(parents=True)
    materializer_path.write_text("# frozen R24 test materializer\n", encoding="utf-8")
    materializer = contract["external_materializers"][materializer_id]
    materializer["sha256"] = r4.hashlib.sha256(
        materializer_path.read_bytes()
    ).hexdigest()
    provenance = {
        "materializer_id": materializer_id,
        "relative_path": materializer["relative_path"],
        "sha256": materializer["sha256"],
        "invocation": {
            "working_directory_relative": materializer["invocation"][
                "working_directory_relative"
            ],
            "argv0_relative_path": materializer["relative_path"],
            "argv_tail": materializer["invocation"]["argv_tail"],
        },
    }
    if provenance_mutation is not None:
        provenance_mutation(provenance)

    protocol_path = workspace / "refine-logs" / "CALIBRATION_PROTOCOL_R24_TEST.md"
    protocol_path.parent.mkdir(parents=True)
    protocol_path.write_text(
        "# R24 terminal authorization test authority\n\n```json\n"
        + json.dumps(registry, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    protocol_sha256 = r4.hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    registry_sha256 = r4._json_hash(registry)

    prerequisite_summary_path = workspace / specification["prerequisite_summary_path"]
    prerequisite_summary_path.parent.mkdir(parents=True, exist_ok=True)
    # Copy the registered prerequisite bytes verbatim.  This is the real R14
    # summary snapshot pinned by R24, not a test-shaped summary substitute.
    prerequisite_summary_source = WORKSPACE / specification["prerequisite_summary_path"]
    prerequisite_summary_path.write_bytes(prerequisite_summary_source.read_bytes())
    prerequisite_summary_sha256 = r4.hashlib.sha256(
        prerequisite_summary_path.read_bytes()
    ).hexdigest()
    assert prerequisite_summary_sha256 == specification["prerequisite_summary_sha256"]

    audit_contract = contract["registered_postrun_audit_contract"]
    prerequisite_audit_path = workspace / specification["prerequisite_audit_path"]
    prerequisite_audit_path.parent.mkdir(parents=True, exist_ok=True)
    prerequisite_audit = {
        "schema_version": audit_contract["schema_version"],
        "run_dir": "artifacts/calibration/capes_ci_qptm_r14_registered_local_20260723_v1",
        "passed": True,
        "verdict": specification["prerequisite_audit_verdict"],
        "checks": {key: True for key in audit_contract["required_exact_check_keys"]},
        "failed_checks": [],
        "evidence": {"materializer_provenance": copy.deepcopy(provenance)},
        audit_contract["self_hash_field"]: None,
    }
    prerequisite_audit[audit_contract["self_hash_field"]] = r4._authorization_self_hash(
        prerequisite_audit, audit_contract["self_hash_field"]
    )
    prerequisite_audit_path.write_bytes(
        r4._authorization_canonical_bytes(prerequisite_audit)
    )
    prerequisite_audit_file_sha256 = r4.hashlib.sha256(
        prerequisite_audit_path.read_bytes()
    ).hexdigest()

    source_manifest = copy.deepcopy(_FRESH_SOURCE_MANIFEST)
    source_manifest_authority_sha256 = source_manifest[
        "source_manifest_authority_sha256"
    ]
    certificate_ids = {
        "process_a": "11111111-1111-4111-8111-111111111111",
        "process_b": "22222222-2222-4222-8222-222222222222",
    }
    phase_nonces = {"process_a": "a" * 64, "process_b": "b" * 64}
    for leaf in specification["target_child_leaf_names"]:
        child = specification["child_certificates"][leaf]
        certificate = {
            "schema_version": child["schema_version"],
            "certificate_type": child["certificate_type"],
            "certificate_id": certificate_ids[leaf],
            "phase_nonce": phase_nonces[leaf],
            "protocol_id": registry["protocol_id"],
            "protocol_sha256": protocol_sha256,
            "registry_sha256": registry_sha256,
            "source_manifest_authority_sha256": source_manifest_authority_sha256,
            "materializer_provenance": copy.deepcopy(provenance),
            "target_phase": specification["target_phase"],
            "target_output_parent_relative": specification[
                "target_output_parent_relative"
            ],
            "target_child_leaf": leaf,
            "target_output_root_relative": child["target_output_root_relative"],
            "target_seeds": specification["target_seeds"],
            "target_steps": specification["target_steps"],
            "target_device": specification["target_device"],
            "prerequisite_summary_path": specification["prerequisite_summary_path"],
            "prerequisite_summary_sha256": prerequisite_summary_sha256,
            "prerequisite_audit_path": specification["prerequisite_audit_path"],
            "prerequisite_audit_file_sha256": prerequisite_audit_file_sha256,
            "prerequisite_audit_self_sha256": prerequisite_audit[
                specification["prerequisite_audit_self_hash_field"]
            ],
            "prerequisite_audit_verdict": specification["prerequisite_audit_verdict"],
            "prerequisite_audit_passed": True,
            "formal_data_authorization": specification[
                "formal_data_authorization_expected"
            ],
            "formal_test_used": specification["formal_test_used_expected"],
            "formal_claim_flags": specification["formal_claim_flags_expected"],
            "checks": {
                key: True
                for key in specification["child_certificate_required_exact_check_keys"]
            },
            "authorized": True,
            "authorization_status": specification["authorization_status"],
            "issued_utc": "2026-07-23T12:00:00.000000Z",
            contract["certificate_self_hash_field"]: None,
        }
        certificate[contract["certificate_self_hash_field"]] = (
            r4._authorization_self_hash(
                certificate, contract["certificate_self_hash_field"]
            )
        )
        certificate_path = workspace / child["relative_path"]
        certificate_path.parent.mkdir(parents=True, exist_ok=True)
        certificate_path.write_bytes(r4._authorization_canonical_bytes(certificate))

    process_uuid = "33333333-3333-4333-8333-333333333333"
    parent = workspace / specification["target_output_parent_relative"]
    child_run_dir = parent / "process_a"
    launcher_args = r4_reproduction.build_parser().parse_args(
        [
            "--run-dir",
            str(parent),
            "--steps",
            str(specification["target_steps"]),
            "--seeds",
            *(str(seed) for seed in specification["target_seeds"]),
            "--device",
            specification["target_device"],
        ]
    )
    runner_args = r4.build_parser().parse_args(
        [
            "--run-dir",
            str(child_run_dir),
            "--steps",
            str(specification["target_steps"]),
            "--seeds",
            *(str(seed) for seed in specification["target_seeds"]),
            "--device",
            specification["target_device"],
        ]
    )

    monkeypatch.setattr(r4, "WORKSPACE", workspace)
    monkeypatch.setattr(r4, "FROZEN_R6_REGISTRY", registry)
    monkeypatch.setattr(r4, "R10_PROTOCOL_PATH", protocol_path)
    monkeypatch.setattr(r4, "R10_PROTOCOL_SHA256", protocol_sha256)
    monkeypatch.setattr(r4, "R24_PROTOCOL_SHA256", protocol_sha256)
    monkeypatch.setattr(r4, "R25_PROTOCOL_SHA256", protocol_sha256)
    monkeypatch.setattr(r4_reproduction, "WORKSPACE", workspace)
    monkeypatch.setattr(r4_reproduction, "R24_REGISTRY", registry)
    monkeypatch.setattr(r4_reproduction, "R25_REGISTRY", registry)
    return {
        "source_manifest": source_manifest,
        "specification": specification,
        "provenance": provenance,
        "launcher_args": launcher_args,
        "runner_args": runner_args,
        "process_uuid": process_uuid,
        "claims_root": workspace / contract["claims_subdirectory_relative"],
        "parent": parent,
        "child_run_dir": child_run_dir,
    }


def test_r24_real_terminal_authorization_receipt_and_prepublication_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = WORKSPACE / ".tmp" / f"r{uuid.uuid4().hex[:6]}"
    workspace.mkdir(parents=False, exist_ok=False)
    fixture = _r24_terminal_authorization_fixture(monkeypatch, workspace)
    specification = fixture["specification"]
    provenance = fixture["provenance"]
    source_manifest = fixture["source_manifest"]
    claims_root = fixture["claims_root"]
    child_run_dir = fixture["child_run_dir"]

    assert r4._issuing_materializer_id(specification) == (
        "registered_reproduction_authorizer"
    )
    assert r4._materializer_provenance_matches_frozen_contract(
        provenance,
        materializer_id=r4._issuing_materializer_id(specification),
    )
    assert not claims_root.exists()
    assert not child_run_dir.exists()
    reopened = r4_reproduction._validate_issued_reproduction_authority(
        fixture["launcher_args"],
        source_manifest_authority_sha256=source_manifest[
            "source_manifest_authority_sha256"
        ],
    )
    assert set(reopened) == {"process_a", "process_b"}
    # Launcher reopening is read-only.  The child runner owns the one native
    # creation of the fresh claims namespace and its O_EXCL preclaim.
    assert not claims_root.exists()
    assert not child_run_dir.exists()
    r4._safe_workspace_mkdir_new(fixture["parent"])
    receipt = r4._phase_authorize(
        fixture["runner_args"],
        process_uuid=fixture["process_uuid"],
        source_manifest=source_manifest,
    )
    assert "source_manifest_sha256" not in receipt
    assert (
        receipt["source_manifest_authority_sha256"]
        == source_manifest["source_manifest_authority_sha256"]
    )
    assert claims_root.is_dir()
    assert not child_run_dir.exists()
    summary = {
        "config": {
            "trainable_seeds": specification["target_seeds"],
            "actual_steps": specification["target_steps"],
            "device": specification["target_device"],
        },
        "provenance": {"process_uuid": fixture["process_uuid"]},
        "source_manifest": source_manifest,
        "phase_authorization": receipt,
    }
    assert r4._phase_authorization_evidence_valid(summary)
    roundtripped = json.loads(json.dumps(summary))
    assert "source_manifest_sha256" not in roundtripped["phase_authorization"]
    assert r4._phase_authorization_evidence_valid(roundtripped)
    r4._phase_authorization_prepublication_recheck(roundtripped)
    with pytest.raises(RuntimeError, match="certificate claim already exists"):
        r4._phase_authorize(
            fixture["runner_args"],
            process_uuid="44444444-4444-4444-8444-444444444444",
            source_manifest=source_manifest,
        )
    assert not child_run_dir.exists()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda specification: specification.pop("issuing_materializer_id"),
        lambda specification: (
            specification.pop("issuing_materializer_id"),
            specification.__setitem__(
                "issuer_materializer_id", "registered_reproduction_authorizer"
            ),
        ),
        lambda specification: specification.__setitem__(
            "issuer_materializer_id", "registered_reproduction_authorizer"
        ),
        lambda specification: specification.__setitem__(
            "issuing_materializer_id", "forged_materializer"
        ),
    ],
)
def test_r24_terminal_authorization_rejects_missing_alias_or_wrong_issuing_key(
    monkeypatch: pytest.MonkeyPatch, mutation
) -> None:
    workspace = WORKSPACE / ".tmp" / f"r{uuid.uuid4().hex[:6]}"
    workspace.mkdir(parents=False, exist_ok=False)
    fixture = _r24_terminal_authorization_fixture(
        monkeypatch, workspace, specification_mutation=mutation
    )
    specification = fixture["specification"]

    assert r4._issuing_materializer_id(specification) is None or (
        r4._issuing_materializer_id(specification) == "forged_materializer"
    )
    with pytest.raises(
        r4_reproduction.LauncherStageError,
        match="child certificate is not an exact valid authority",
    ):
        r4_reproduction._validate_issued_reproduction_authority(
            fixture["launcher_args"],
            source_manifest_authority_sha256=fixture["source_manifest"][
                "source_manifest_authority_sha256"
            ],
        )
    assert not fixture["claims_root"].exists()
    assert not fixture["parent"].exists()
    assert not fixture["child_run_dir"].exists()


def test_r24_terminal_authorization_rejects_wrong_materializer_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = WORKSPACE / ".tmp" / f"r{uuid.uuid4().hex[:6]}"
    workspace.mkdir(parents=False, exist_ok=False)
    fixture = _r24_terminal_authorization_fixture(
        monkeypatch,
        workspace,
        provenance_mutation=lambda provenance: provenance.__setitem__(
            "sha256", "f" * 64
        ),
    )

    with pytest.raises(
        r4_reproduction.LauncherStageError,
        match="prerequisite summary or freshly issued audit is not exact",
    ):
        r4_reproduction._validate_issued_reproduction_authority(
            fixture["launcher_args"],
            source_manifest_authority_sha256=fixture["source_manifest"][
                "source_manifest_authority_sha256"
            ],
        )
    assert not fixture["claims_root"].exists()
    assert not fixture["parent"].exists()
    assert not fixture["child_run_dir"].exists()


def test_r15_prepublication_recheck_resolves_child_certificate_specification(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A reproduction child type is not a top-level phase-contract key.

    This guards the only post-run authorization path that is different from
    smoke/registered: after a child consumes its own certificate, the
    publication recheck must resolve the common parent specification rather
    than treating the child certificate type as an ordinary phase name.
    """

    legacy_protocol = (
        r4.WORKSPACE / "refine-logs" / "CALIBRATION_PROTOCOL_R11_2026-07-23.md"
    )
    legacy_raw = legacy_protocol.read_bytes()
    registry = r4._first_json_object_text(legacy_raw.decode("utf-8"), label="R11")
    contract = registry["phase_authorization_contract"]
    specification = contract["reproduction_authorization"]
    child = specification["child_certificates"]["process_a"]

    monkeypatch.setattr(r4, "FROZEN_R6_REGISTRY", registry)
    monkeypatch.setattr(r4, "R10_PROTOCOL_PATH", tmp_path / "protocol.md")
    monkeypatch.setattr(r4, "_safe_workspace_read_bytes", lambda _path: legacy_raw)
    monkeypatch.setattr(
        r4, "_materializer_provenance_matches_frozen_contract", lambda *_a, **_k: True
    )
    monkeypatch.setattr(r4, "_validate_prerequisite_audit", lambda *_a, **_k: True)

    certificate = {
        contract["certificate_self_hash_field"]: "certificate-self-hash",
        "materializer_provenance": {},
    }
    audit = {specification["prerequisite_audit_self_hash_field"]: "audit-self-hash"}
    snapshots = iter(
        (
            (b"certificate", certificate, "certificate-file-hash"),
            (b"audit", audit, "audit-file-hash"),
            (b"summary", {"status": "unused"}, "summary-file-hash"),
        )
    )
    monkeypatch.setattr(r4, "_authorization_snapshot", lambda _path: next(snapshots))
    source_manifest = _fresh_source_manifest()
    source_authority_sha256 = source_manifest["source_manifest_authority_sha256"]
    summary = {
        "phase_authorization": {
            "certificate_type": child["certificate_type"],
            "certificate_path": child["relative_path"],
            "certificate_file_sha256": "certificate-file-hash",
            "certificate_self_sha256": "certificate-self-hash",
            "prerequisite_audit_file_sha256": "audit-file-hash",
            "prerequisite_audit_self_sha256": "audit-self-hash",
            "prerequisite_summary_sha256": "summary-file-hash",
            "protocol_sha256": r4.hashlib.sha256(legacy_raw).hexdigest(),
            "registry_sha256": r4._json_hash(registry),
            "source_manifest_authority_sha256": source_authority_sha256,
            "materializer_provenance": {},
        },
        "source_manifest": source_manifest,
    }

    r4._phase_authorization_prepublication_recheck(summary)


def test_r11_native_create_has_no_nonwindows_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(r4.os, "name", "posix")
    with pytest.raises(r4.NativeSafePathUnavailable):
        r4._native_create_new_child(
            tmp_path, "claim.json", directory=False, payload=b"fixed"
        )


def test_r11_native_create_refuses_collision_without_replacement(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    r4._native_create_new_child(parent, "one.json", directory=False, payload=b"one")
    with pytest.raises(FileExistsError):
        r4._native_create_new_child(parent, "one.json", directory=False, payload=b"two")
    assert (parent / "one.json").read_bytes() == b"one"


def test_r11_native_create_exposes_rootdirectory_dontreparse_and_can_abort(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    observed: list[tuple[str, dict]] = []

    def hook(event: str, payload: dict) -> None:
        observed.append((event, payload))
        if event == "child_created":
            raise ValueError("simulated identity drift")

    monkeypatch.setattr(r4, "_NATIVE_OPS_HOOK", hook)
    with pytest.raises(ValueError, match="simulated identity drift"):
        r4._native_create_new_child(parent, "drift.json", directory=False, payload=b"x")
    create = next(payload for event, payload in observed if event == "create")
    assert create["root_directory"]
    assert create["object_attributes"] & 0x1000
    assert create["create_disposition"] == 2
    assert create["create_options"] & 0x00200000


@pytest.mark.parametrize(
    ("event", "error"),
    [
        ("identity", ValueError("simulated reparse attribute")),
        ("ntstatus", OSError("simulated negative NTSTATUS")),
    ],
)
def test_r11_native_create_aborts_on_identity_or_ntstatus_hook(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, event: str, error: Exception
) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()

    def hook(observed_event: str, _payload: dict) -> None:
        if observed_event == event:
            raise error

    monkeypatch.setattr(r4, "_NATIVE_OPS_HOOK", hook)
    with pytest.raises(type(error), match=str(error)):
        r4._native_create_new_child(parent, "abort.json", directory=False, payload=b"x")
    if event == "identity":
        assert not (parent / "abort.json").exists()
