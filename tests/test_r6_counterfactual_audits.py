from __future__ import annotations

# ruff: noqa: E402

import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

import torch
import pytest

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))

import scripts.run_query_anchor_r4 as r5_runner
from visualvit.allocator import DeterministicGlobalAllocator
from visualvit.projector import RelationProjector
from visualvit.query_anchor_model import query_prompt
from visualvit.r6_counterfactual_audits import (
    R6_COUNTERFACTUAL_SCHEMA_VERSION,
    R6ChainHooks,
    equality_preserving_hidden_relabel,
    hidden_relabel_contract,
    run_r6_counterfactual_audits,
    source_tensor_snapshot,
    validate_r6_counterfactual_audit,
)


def _reseal(report: dict) -> None:
    payload = json.dumps(
        {key: value for key, value in report.items() if key != "report_sha256"},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    report["report_sha256"] = hashlib.sha256(payload).hexdigest()


def _fixture_and_hooks() -> tuple[object, R6ChainHooks]:
    strata, _, _ = r5_runner._build_strata(("train",))
    batch = strata["clean"]["train"]
    matcher = r5_runner._new_matcher(17)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(61_607)
        projector = RelationProjector(input_dim=75, hidden_size=8)
    hooks = R6ChainHooks(
        matching_regions=r5_runner._matching_regions,
        token_regions=lambda value: value.regions,
        matcher=matcher,
        allocator=DeterministicGlobalAllocator(),
        projector=projector,
        adapter=r5_runner._fixed_adapter(),
        prompt_factory=query_prompt,
    )
    return batch, hooks


def test_r6_full_chain_counterfactual_audits_pass_with_strict_schema() -> None:
    batch, hooks = _fixture_and_hooks()
    report = run_r6_counterfactual_audits(batch, hooks)
    assert report["schema_version"] == R6_COUNTERFACTUAL_SCHEMA_VERSION
    assert report["status"] == "PASS_R6_COUNTERFACTUAL_AUDITS"
    assert report["passed"]
    assert all(report["checks"].values())
    validate_r6_counterfactual_audit(report)
    assert len(report["report_sha256"]) == 64
    assert report["forward_boundary"]["hidden_oracle_passed_to_matcher"] is False
    hidden = report["hidden_id_relabel"]
    assert hidden["contract"]["checks"]["counterfactual_nonvacuous"]
    assert hidden["contract"]["checks"]["gold_equality_relation_exact"]
    assert hidden["full_chain"]["checks"] == {
        "matching_regions": True,
        "token_regions": True,
        "utilities": True,
        "soft_plan": True,
        "plan": True,
        "relation_candidates": True,
        "allocation": True,
        "token_order_and_values": True,
        "projected_tokens": True,
        "adapter_scores": True,
        "predictions": True,
    }
    permutation = report["endpoint_permutation"]
    assert permutation["passed"]
    assert permutation["checks"]["prior_permutation_nonidentity"]
    assert permutation["checks"]["current_permutation_nonidentity"]
    assert permutation["checks"]["soft_plan_restored"]
    for name in (
        "query_value_substitution",
        "forbidden_state_channel_substitution",
    ):
        audit = report[name]
        assert audit["passed"]
        assert audit["checks"] == {
            "counterfactual_nonvacuous": True,
            "matching_and_transport_exact": True,
            "full_chain_covered": True,
            "downstream_change_observed": True,
        }
        assert {
            "utilities",
            "plan",
            "relation_candidates",
            "allocation",
            "tokens",
            "projected_tokens",
            "adapter_scores",
            "predictions",
        }.issubset(audit["comparisons"])
    b4 = report["b4a_deranged_vs_b4b_oracle"]
    assert b4["passed"]
    assert b4["diff_entries"]
    assert not b4["unexpected_paths"]
    assert all(entry["allowlist_category"] for entry in b4["diff_entries"])
    assert b4["b4a_assignment_sha256"] != b4["b4b_assignment_sha256"]
    assert {entry["path"] for entry in b4["diff_entries"]} >= {
        "plan.mode",
        "plan.transport.value_sha256",
    }


def test_r6_source_snapshot_covers_physical_layout_and_aliases_without_mutation() -> (
    None
):
    batch, hooks = _fixture_and_hooks()
    before = source_tensor_snapshot(batch)
    report = run_r6_counterfactual_audits(batch, hooks)
    after = source_tensor_snapshot(batch)
    assert before == after
    assert report["source_tensor_audit"]["passed"]
    signature = before["tensors"]["regions.prior_features"]
    assert set(signature) == {
        "value_sha256",
        "dtype",
        "shape",
        "stride",
        "storage_offset",
        "storage_pointer",
        "device",
        "requires_grad",
        "alias_key",
    }
    assert isinstance(before["alias_groups"], list)


def test_r6_malicious_side_specific_hidden_relabel_is_rejected() -> None:
    batch, _ = _fixture_and_hooks()
    good = equality_preserving_hidden_relabel(batch)
    bad = replace(
        good,
        oracle=replace(
            good.oracle,
            current_gold_ids=good.oracle.current_gold_ids + 9_999_991,
        ),
    )
    contract = hidden_relabel_contract(batch, bad)
    assert not contract["passed"]
    assert not contract["checks"]["gold_equality_relation_exact"]
    assert not contract["checks"]["relabeled_plan_matches_gold_equality"]


def test_r6_malicious_oracle_id_forward_leak_is_detected() -> None:
    batch, hooks = _fixture_and_hooks()

    def leaky_matching_regions(value):
        regions = r5_runner._matching_regions(value)
        prior = regions.prior_features.clone()
        current = regions.current_features.clone()
        prior[..., 2] = value.oracle.prior_gold_ids.to(prior.dtype)
        current[..., 2] = value.oracle.current_gold_ids.to(current.dtype)
        return replace(regions, prior_features=prior, current_features=current)

    malicious = replace(hooks, matching_regions=leaky_matching_regions)
    report = run_r6_counterfactual_audits(batch, malicious)
    assert not report["passed"]
    assert report["status"] == "FAIL_R6_COUNTERFACTUAL_AUDITS"
    assert not report["checks"]["hidden_id_full_chain_invariance"]
    assert not report["hidden_id_relabel"]["full_chain"]["checks"]["matching_regions"]
    assert not report["hidden_id_relabel"]["full_chain"]["checks"]["utilities"]


def test_r6_validator_rejects_missing_full_chain_stage_after_valid_reseal() -> None:
    batch, hooks = _fixture_and_hooks()
    report = run_r6_counterfactual_audits(batch, hooks)
    malicious = copy.deepcopy(report)
    del malicious["query_value_substitution"]["comparisons"]["allocation"]
    _reseal(malicious)
    with pytest.raises(ValueError, match="full chain"):
        validate_r6_counterfactual_audit(malicious)


def test_r6_validator_rejects_forged_top_level_pass_after_hidden_leak() -> None:
    batch, hooks = _fixture_and_hooks()

    def leaky_matching_regions(value):
        regions = r5_runner._matching_regions(value)
        prior = regions.prior_features.clone()
        prior[..., 2] = value.oracle.prior_gold_ids.to(prior.dtype)
        return replace(regions, prior_features=prior)

    report = run_r6_counterfactual_audits(
        batch, replace(hooks, matching_regions=leaky_matching_regions)
    )
    malicious = copy.deepcopy(report)
    malicious["passed"] = True
    malicious["status"] = "PASS_R6_COUNTERFACTUAL_AUDITS"
    malicious["checks"] = {key: True for key in malicious["checks"]}
    _reseal(malicious)
    with pytest.raises(ValueError, match="top-level counterfactual checks"):
        validate_r6_counterfactual_audit(malicious)


def test_r6_validator_rejects_nonallowlisted_recursive_b4_diff() -> None:
    batch, hooks = _fixture_and_hooks()
    report = run_r6_counterfactual_audits(batch, hooks)
    malicious = copy.deepcopy(report)
    malicious_b4 = malicious["b4a_deranged_vs_b4b_oracle"]
    malicious_b4["b4b_trace"]["relation_candidates"]["entity_features"][
        "value_sha256"
    ] = "0" * 64
    malicious_b4["diff_entries"].append(
        {
            "path": "relation_candidates.entity_features.value_sha256",
            "allowlist_category": "causally_downstream_relation_change_values",
        }
    )
    _reseal(malicious)
    with pytest.raises(ValueError, match="recursive diff entries"):
        validate_r6_counterfactual_audit(malicious)
