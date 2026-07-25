from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass, replace
import hashlib
import json
from typing import Any, Callable, Mapping, Sequence

import torch
from torch import Tensor, nn

from .allocator import DeterministicGlobalAllocator
from .calibration_query import HiddenQueryOracle, QueryAnchorBatch
from .calibration_query import (
    REGISTERED_DERANGEMENT_SEEDS,
    build_balanced_derangement_bank,
)
from .schemas import (
    AllocationPlan,
    MatchPlan,
    ProjectedTokenBundle,
    RegionBatch,
    RelationCandidates,
    TokenBundle,
)
from .tokenizer import assemble_capes_ci_tokens, build_soft_relation_candidates


R6_COUNTERFACTUAL_SCHEMA_VERSION = "visualvit.r6_counterfactual_audits.v1"
DEFAULT_FLOAT_ATOL = 1e-6


@dataclass(frozen=True)
class R6ChainHooks:
    """The only runner-specific seams used by the full-chain audits.

    ``matching_regions`` and ``token_regions`` are the only hooks that receive
    the full batch.  A registered run must make both invariant to hidden-ID
    relabeling.  The matcher itself receives only the returned ``RegionBatch``;
    the hidden oracle is never an argument to matcher/tokenizer/projector/
    adapter forward calls.
    """

    matching_regions: Callable[[QueryAnchorBatch], RegionBatch]
    token_regions: Callable[[QueryAnchorBatch], RegionBatch]
    matcher: Any
    allocator: DeterministicGlobalAllocator
    projector: nn.Module
    adapter: nn.Module
    prompt_factory: Callable[[int, torch.device | str], Tensor]
    build_candidates: Callable[[RegionBatch, MatchPlan], RelationCandidates] = (
        build_soft_relation_candidates
    )
    tokenize: Callable[[RegionBatch, MatchPlan, AllocationPlan], TokenBundle] = (
        assemble_capes_ci_tokens
    )


@dataclass(frozen=True)
class _ChainTrace:
    matching_regions: RegionBatch
    token_regions: RegionBatch
    utilities: tuple[Tensor, ...]
    soft_plan: MatchPlan
    plan: MatchPlan
    candidates: RelationCandidates
    allocation: AllocationPlan
    tokens: TokenBundle
    projected: ProjectedTokenBundle
    adapter_scores: Tensor
    predictions: Tensor


def _tensor_value_sha256(value: Tensor) -> str:
    cpu = value.detach().cpu().contiguous()
    digest = hashlib.sha256()
    digest.update(str(cpu.dtype).encode("ascii"))
    digest.update(str(tuple(cpu.shape)).encode("ascii"))
    digest.update(cpu.numpy().tobytes())
    return digest.hexdigest()


def _json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _storage_pointer(value: Tensor) -> int:
    return int(value.untyped_storage().data_ptr())


def _walk_tensors(value: Any, prefix: str = "") -> dict[str, Tensor]:
    output: dict[str, Tensor] = {}
    if isinstance(value, Tensor):
        output[prefix or "tensor"] = value
        return output
    if is_dataclass(value):
        for field in fields(value):
            child = getattr(value, field.name)
            path = f"{prefix}.{field.name}" if prefix else field.name
            output.update(_walk_tensors(child, path))
        return output
    if isinstance(value, Mapping):
        for key in sorted(value, key=str):
            path = f"{prefix}.{key}" if prefix else str(key)
            output.update(_walk_tensors(value[key], path))
        return output
    if isinstance(value, (tuple, list)):
        for index, child in enumerate(value):
            path = f"{prefix}.{index}" if prefix else str(index)
            output.update(_walk_tensors(child, path))
    return output


def source_tensor_snapshot(value: Any) -> dict[str, Any]:
    """Capture values and physical tensor layout, including storage aliases."""

    tensors = _walk_tensors(value)
    signatures: dict[str, dict[str, Any]] = {}
    aliases: dict[str, list[str]] = {}
    for path, tensor in sorted(tensors.items()):
        pointer = _storage_pointer(tensor)
        device = str(tensor.device)
        alias_key = f"{device}:{pointer}"
        aliases.setdefault(alias_key, []).append(path)
        signatures[path] = {
            "value_sha256": _tensor_value_sha256(tensor),
            "dtype": str(tensor.dtype),
            "shape": list(tensor.shape),
            "stride": list(tensor.stride()),
            "storage_offset": int(tensor.storage_offset()),
            "storage_pointer": pointer,
            "device": device,
            "requires_grad": bool(tensor.requires_grad),
            "alias_key": alias_key,
        }
    alias_groups = sorted(
        (sorted(paths) for paths in aliases.values() if len(paths) > 1),
        key=lambda paths: tuple(paths),
    )
    payload = {
        "schema_version": f"{R6_COUNTERFACTUAL_SCHEMA_VERSION}.source_snapshot",
        "tensor_count": len(signatures),
        "tensors": signatures,
        "alias_groups": alias_groups,
    }
    payload["snapshot_sha256"] = _json_sha256(payload)
    return payload


def _tensor_fields(value: Any) -> dict[str, Tensor]:
    return {
        path: tensor
        for path, tensor in _walk_tensors(value).items()
        if not path.endswith("diagnostics")
    }


def _tensor_group_equality(
    left: Any,
    right: Any,
    *,
    atol: float,
) -> dict[str, Any]:
    left_fields = _tensor_fields(left)
    right_fields = _tensor_fields(right)
    same_fields = set(left_fields) == set(right_fields)
    field_names = sorted(set(left_fields) | set(right_fields))
    exact: dict[str, bool] = {}
    close: dict[str, bool] = {}
    max_abs_error: dict[str, float | None] = {}
    hashes: dict[str, dict[str, str | None]] = {}
    for name in field_names:
        lhs = left_fields.get(name)
        rhs = right_fields.get(name)
        if lhs is None or rhs is None:
            exact[name] = False
            close[name] = False
            max_abs_error[name] = None
            hashes[name] = {
                "left": _tensor_value_sha256(lhs) if lhs is not None else None,
                "right": _tensor_value_sha256(rhs) if rhs is not None else None,
            }
            continue
        exact[name] = torch.equal(lhs, rhs)
        if lhs.shape != rhs.shape or lhs.dtype != rhs.dtype:
            close[name] = False
            max_abs_error[name] = None
        elif lhs.is_floating_point() or lhs.is_complex():
            close[name] = torch.allclose(lhs, rhs, atol=atol, rtol=0)
            max_abs_error[name] = float((lhs - rhs).abs().max()) if lhs.numel() else 0.0
        else:
            close[name] = exact[name]
            max_abs_error[name] = 0.0 if exact[name] else None
        hashes[name] = {
            "left": _tensor_value_sha256(lhs),
            "right": _tensor_value_sha256(rhs),
        }
    return {
        "fields_exact": same_fields,
        "all_exact": same_fields and all(exact.values()),
        "all_close": same_fields and all(close.values()),
        "exact_by_field": exact,
        "close_by_field": close,
        "max_abs_error_by_field": max_abs_error,
        "value_sha256_by_field": hashes,
    }


def _with_stable_source_ids(batch: QueryAnchorBatch) -> QueryAnchorBatch:
    regions = batch.regions
    batch_size, prior_count = regions.prior_valid.shape
    current_count = regions.current_valid.shape[1]
    device = regions.prior_valid.device
    prior = regions.prior_source_ids
    current = regions.current_source_ids
    if prior is None:
        prior = torch.arange(prior_count, device=device).expand(batch_size, -1).clone()
    if current is None:
        current = (
            (torch.arange(current_count, device=device) + prior_count)
            .expand(batch_size, -1)
            .clone()
        )
    return replace(
        batch,
        regions=replace(
            regions,
            prior_source_ids=prior,
            current_source_ids=current,
        ),
    )


def _gold_equality(batch: QueryAnchorBatch) -> Tensor:
    return batch.oracle.prior_gold_ids.unsqueeze(-1).eq(
        batch.oracle.current_gold_ids.unsqueeze(-2)
    )


def _gold_plan_semantics(batch: QueryAnchorBatch) -> bool:
    prior_count = batch.regions.prior_features.shape[1]
    current_count = batch.regions.current_features.shape[1]
    plan = batch.oracle.plan.transport
    equality = _gold_equality(batch)
    real = plan[:, :prior_count, :current_count] > 0.5
    death = plan[:, :prior_count, current_count] > 0.5
    birth = plan[:, prior_count, :current_count] > 0.5
    expected_death = batch.regions.prior_valid & ~equality.any(dim=-1)
    expected_birth = batch.regions.current_valid & ~equality.any(dim=-2)
    return bool(
        torch.equal(real, equality)
        and torch.equal(death, expected_death)
        and torch.equal(birth, expected_birth)
    )


def equality_preserving_hidden_relabel(batch: QueryAnchorBatch) -> QueryAnchorBatch:
    """Apply a case-local bijection to gold IDs, preserving only equality."""

    prior = batch.oracle.prior_gold_ids
    current = batch.oracle.current_gold_ids
    relabeled_prior = torch.empty_like(prior)
    relabeled_current = torch.empty_like(current)
    for case in range(prior.shape[0]):
        joined = torch.cat((prior[case], current[case]))
        unique = torch.unique(joined, sorted=True)
        base = 10_000_019 * (case + 1)
        for rank, old_id in enumerate(unique.tolist()):
            new_id = base + 2 * rank + 1
            relabeled_prior[case][prior[case] == old_id] = new_id
            relabeled_current[case][current[case] == old_id] = new_id
    return replace(
        batch,
        oracle=replace(
            batch.oracle,
            prior_gold_ids=relabeled_prior,
            current_gold_ids=relabeled_current,
        ),
    )


def hidden_relabel_contract(
    original: QueryAnchorBatch,
    relabeled: QueryAnchorBatch,
) -> dict[str, Any]:
    original_equality = _gold_equality(original)
    relabeled_equality = _gold_equality(relabeled)
    ids_changed = not torch.equal(
        original.oracle.prior_gold_ids, relabeled.oracle.prior_gold_ids
    ) and not torch.equal(
        original.oracle.current_gold_ids, relabeled.oracle.current_gold_ids
    )
    checks = {
        "counterfactual_nonvacuous": ids_changed,
        "gold_equality_relation_exact": torch.equal(
            original_equality, relabeled_equality
        ),
        "oracle_plan_exact": torch.equal(
            original.oracle.plan.transport, relabeled.oracle.plan.transport
        ),
        "original_plan_matches_gold_equality": _gold_plan_semantics(original),
        "relabeled_plan_matches_gold_equality": _gold_plan_semantics(relabeled),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "original_equality_sha256": _tensor_value_sha256(original_equality),
        "relabeled_equality_sha256": _tensor_value_sha256(relabeled_equality),
        "original_ids_sha256": _json_sha256(
            {
                "prior": _tensor_value_sha256(original.oracle.prior_gold_ids),
                "current": _tensor_value_sha256(original.oracle.current_gold_ids),
            }
        ),
        "relabeled_ids_sha256": _json_sha256(
            {
                "prior": _tensor_value_sha256(relabeled.oracle.prior_gold_ids),
                "current": _tensor_value_sha256(relabeled.oracle.current_gold_ids),
            }
        ),
    }


def _execute_chain(
    batch: QueryAnchorBatch,
    hooks: R6ChainHooks,
    *,
    plan_override: MatchPlan | None = None,
) -> _ChainTrace:
    matching_regions = hooks.matching_regions(batch)
    token_regions = hooks.token_regions(batch)
    matching_regions.validate()
    token_regions.validate()
    utilities = tuple(hooks.matcher.compute_utilities(matching_regions))
    soft_plan = hooks.matcher.soft_plan(matching_regions)
    soft_plan.validate(matching_regions)
    plan = (
        hooks.matcher.hard_plan(matching_regions)
        if plan_override is None
        else plan_override
    )
    plan.validate_hard(token_regions)
    candidates = hooks.build_candidates(token_regions, plan)
    candidates.validate()
    allocation = hooks.allocator(candidates)
    allocation.validate()
    tokens = hooks.tokenize(token_regions, plan, allocation)
    tokens.validate()
    projected = hooks.projector(tokens)
    projected.validate()
    prompt = hooks.prompt_factory(tokens.tokens.shape[0], tokens.tokens.device)
    scores = hooks.adapter.score_labels(prompt, projected)
    if not isinstance(scores, Tensor):
        scores = scores[0]
    predictions = scores.argmax(dim=-1)
    return _ChainTrace(
        matching_regions=matching_regions,
        token_regions=token_regions,
        utilities=utilities,
        soft_plan=soft_plan,
        plan=plan,
        candidates=candidates,
        allocation=allocation,
        tokens=tokens,
        projected=projected,
        adapter_scores=scores,
        predictions=predictions,
    )


def _trace_evidence(trace: _ChainTrace) -> dict[str, Any]:
    groups = {
        "matching_regions": trace.matching_regions,
        "token_regions": trace.token_regions,
        "utilities": trace.utilities,
        "soft_plan": trace.soft_plan,
        "plan": trace.plan,
        "relation_candidates": trace.candidates,
        "allocation": trace.allocation,
        "tokens": trace.tokens,
        "projected_tokens": trace.projected,
        "adapter_scores": trace.adapter_scores,
        "predictions": trace.predictions,
    }
    result: dict[str, Any] = {}
    for name, value in groups.items():
        hashes = {
            path: _tensor_value_sha256(tensor)
            for path, tensor in sorted(_tensor_fields(value).items())
        }
        result[name] = {
            "value_sha256_by_field": hashes,
            "group_sha256": _json_sha256(hashes),
        }
    return result


def _hidden_invariance(
    original: _ChainTrace,
    relabeled: _ChainTrace,
    *,
    atol: float,
) -> dict[str, Any]:
    comparisons = {
        "matching_regions": _tensor_group_equality(
            original.matching_regions, relabeled.matching_regions, atol=atol
        ),
        "token_regions": _tensor_group_equality(
            original.token_regions, relabeled.token_regions, atol=atol
        ),
        "utilities": _tensor_group_equality(
            original.utilities, relabeled.utilities, atol=atol
        ),
        "soft_plan": _tensor_group_equality(
            original.soft_plan, relabeled.soft_plan, atol=atol
        ),
        "plan": _tensor_group_equality(original.plan, relabeled.plan, atol=atol),
        "relation_candidates": _tensor_group_equality(
            original.candidates, relabeled.candidates, atol=atol
        ),
        "allocation": _tensor_group_equality(
            original.allocation, relabeled.allocation, atol=atol
        ),
        "token_order_and_values": _tensor_group_equality(
            original.tokens, relabeled.tokens, atol=atol
        ),
        "projected_tokens": _tensor_group_equality(
            original.projected, relabeled.projected, atol=atol
        ),
        "adapter_scores": _tensor_group_equality(
            original.adapter_scores, relabeled.adapter_scores, atol=atol
        ),
        "predictions": _tensor_group_equality(
            original.predictions, relabeled.predictions, atol=atol
        ),
    }
    checks = {name: result["all_exact"] for name, result in comparisons.items()}
    return {
        "passed": all(checks.values()),
        "equality_policy": "bitwise_exact",
        "checks": checks,
        "comparisons": comparisons,
    }


def _permute_endpoint_tensor(
    value: Tensor | None, permutation: Tensor
) -> Tensor | None:
    return None if value is None else value.index_select(1, permutation).clone()


def _permuted_plan(
    plan: MatchPlan,
    prior_permutation: Tensor,
    current_permutation: Tensor,
) -> MatchPlan:
    prior_count = len(prior_permutation)
    current_count = len(current_permutation)
    source = plan.transport
    output = source.new_zeros(source.shape)
    output[:, :prior_count, :current_count] = source[:, prior_permutation][
        :, :, current_permutation
    ]
    output[:, :prior_count, current_count] = source[:, prior_permutation, current_count]
    output[:, prior_count, :current_count] = source[:, prior_count, current_permutation]
    return MatchPlan(transport=output, mode=f"{plan.mode}_r6_permuted")


def independently_permute_endpoints(
    batch: QueryAnchorBatch,
) -> tuple[QueryAnchorBatch, Tensor, Tensor]:
    prior_count = batch.regions.prior_features.shape[1]
    current_count = batch.regions.current_features.shape[1]
    device = batch.regions.prior_features.device
    prior_permutation = torch.roll(torch.arange(prior_count, device=device), shifts=1)
    current_permutation = torch.roll(
        torch.arange(current_count, device=device), shifts=-1
    )
    regions = batch.regions
    permuted_regions = replace(
        regions,
        **{
            name: _permute_endpoint_tensor(
                getattr(regions, name),
                prior_permutation if name.startswith("prior_") else current_permutation,
            )
            for name in (
                "prior_features",
                "current_features",
                "prior_valid",
                "current_valid",
                "prior_anatomy",
                "current_anatomy",
                "prior_entity_ids",
                "current_entity_ids",
                "prior_boxes",
                "current_boxes",
                "prior_confidence",
                "current_confidence",
                "prior_source_ids",
                "current_source_ids",
            )
        },
    )
    permuted = replace(
        batch,
        regions=permuted_regions,
        prior_query_marker=_permute_endpoint_tensor(
            batch.prior_query_marker, prior_permutation
        ),
        current_query_marker=_permute_endpoint_tensor(
            batch.current_query_marker, current_permutation
        ),
        prior_carrier_control=_permute_endpoint_tensor(
            batch.prior_carrier_control, prior_permutation
        ),
        current_carrier_control=_permute_endpoint_tensor(
            batch.current_carrier_control, current_permutation
        ),
        oracle=HiddenQueryOracle(
            prior_gold_ids=_permute_endpoint_tensor(
                batch.oracle.prior_gold_ids, prior_permutation
            ),
            current_gold_ids=_permute_endpoint_tensor(
                batch.oracle.current_gold_ids, current_permutation
            ),
            labels=batch.oracle.labels.clone(),
            plan=_permuted_plan(
                batch.oracle.plan, prior_permutation, current_permutation
            ),
        ),
    )
    return permuted, prior_permutation, current_permutation


def _restore_endpoint_tensor(
    value: Tensor, permutation: Tensor, dim: int = 1
) -> Tensor:
    return value.index_select(dim, torch.argsort(permutation))


def _restore_plan(
    plan: MatchPlan,
    prior_permutation: Tensor,
    current_permutation: Tensor,
) -> MatchPlan:
    prior_count = len(prior_permutation)
    current_count = len(current_permutation)
    source = plan.transport
    prior_inverse = torch.argsort(prior_permutation)
    current_inverse = torch.argsort(current_permutation)
    output = source.new_zeros(source.shape)
    output[:, :prior_count, :current_count] = source[:, prior_inverse][
        :, :, current_inverse
    ]
    output[:, :prior_count, current_count] = source[:, prior_inverse, current_count]
    output[:, prior_count, :current_count] = source[:, prior_count, current_inverse]
    return MatchPlan(transport=output, mode=f"{plan.mode}_r6_restored")


def _restore_candidates(
    candidates: RelationCandidates,
    prior_permutation: Tensor,
    current_permutation: Tensor,
) -> RelationCandidates:
    prior_count = len(prior_permutation)
    order = torch.cat(
        (
            torch.argsort(prior_permutation),
            prior_count + torch.argsort(current_permutation),
        )
    )
    return replace(
        candidates,
        **{
            name: getattr(candidates, name).index_select(1, order)
            for name in (
                "entity_features",
                "relation_features",
                "valid_mask",
                "unary_scores",
                "anatomy_ids",
                "temporal_ids",
                "source_ids",
                "relation_mass",
            )
        },
    )


def _restore_allocation(
    allocation: AllocationPlan,
    prior_permutation: Tensor,
    current_permutation: Tensor,
) -> AllocationPlan:
    prior_count = len(prior_permutation)
    order = torch.cat(
        (
            torch.argsort(prior_permutation),
            prior_count + torch.argsort(current_permutation),
        )
    )
    return replace(
        allocation,
        weights=allocation.weights.index_select(2, order),
        source_valid=allocation.source_valid.index_select(1, order),
        overflow_mask=allocation.overflow_mask.index_select(1, order),
    )


def _permutation_equivariance(
    original: _ChainTrace,
    permuted: _ChainTrace,
    prior_permutation: Tensor,
    current_permutation: Tensor,
    *,
    atol: float,
) -> dict[str, Any]:
    prior_inverse = torch.argsort(prior_permutation)
    current_inverse = torch.argsort(current_permutation)
    restored_utilities = (
        permuted.utilities[0]
        .index_select(1, prior_inverse)
        .index_select(2, current_inverse),
        permuted.utilities[1].index_select(1, prior_inverse),
        permuted.utilities[2].index_select(1, current_inverse),
    )
    restored_plan = _restore_plan(permuted.plan, prior_permutation, current_permutation)
    restored_soft_plan = _restore_plan(
        permuted.soft_plan, prior_permutation, current_permutation
    )
    restored_candidates = _restore_candidates(
        permuted.candidates, prior_permutation, current_permutation
    )
    restored_allocation = _restore_allocation(
        permuted.allocation, prior_permutation, current_permutation
    )
    restored_assignment = _restore_plan(
        MatchPlan(transport=permuted.tokens.assignment, mode="token_assignment"),
        prior_permutation,
        current_permutation,
    ).transport
    token_comparisons = _tensor_group_equality(
        replace(permuted.tokens, assignment=restored_assignment),
        original.tokens,
        atol=atol,
    )
    comparisons = {
        "utilities_restored": _tensor_group_equality(
            restored_utilities, original.utilities, atol=atol
        ),
        "plan_restored": _tensor_group_equality(
            restored_plan.transport, original.plan.transport, atol=atol
        ),
        "soft_plan_restored": _tensor_group_equality(
            restored_soft_plan.transport,
            original.soft_plan.transport,
            atol=atol,
        ),
        "relation_candidates_restored": _tensor_group_equality(
            restored_candidates, original.candidates, atol=atol
        ),
        "allocation_restored": _tensor_group_equality(
            restored_allocation, original.allocation, atol=atol
        ),
        "token_order_and_values_invariant": token_comparisons,
        "projected_tokens_invariant": _tensor_group_equality(
            permuted.projected, original.projected, atol=atol
        ),
        "adapter_scores_invariant": _tensor_group_equality(
            permuted.adapter_scores, original.adapter_scores, atol=atol
        ),
        "predictions_invariant": _tensor_group_equality(
            permuted.predictions, original.predictions, atol=atol
        ),
    }
    checks = {name: result["all_close"] for name, result in comparisons.items()}
    checks["prior_permutation_nonidentity"] = not torch.equal(
        prior_permutation,
        torch.arange(len(prior_permutation), device=prior_permutation.device),
    )
    checks["current_permutation_nonidentity"] = not torch.equal(
        current_permutation,
        torch.arange(len(current_permutation), device=current_permutation.device),
    )
    return {
        "passed": all(checks.values()),
        "equality_policy": {"floating_atol": atol, "rtol": 0.0, "discrete": "exact"},
        "checks": checks,
        "comparisons": comparisons,
        "prior_permutation_sha256": _tensor_value_sha256(prior_permutation),
        "current_permutation_sha256": _tensor_value_sha256(current_permutation),
        "prior_permutation": prior_permutation.detach().cpu().tolist(),
        "current_permutation": current_permutation.detach().cpu().tolist(),
    }


_CHAIN_STAGE_NAMES = (
    "matching_regions",
    "token_regions",
    "utilities",
    "soft_plan",
    "plan",
    "relation_candidates",
    "allocation",
    "tokens",
    "projected_tokens",
    "adapter_scores",
    "predictions",
)
_B4_ALLOWLIST = (
    "assignment_mode",
    "assignment_tensor",
    "assignment_sha256",
    "causally_downstream_relation_change_values",
    "assignment_induced_source_order",
    "relation_change_token_values",
    "scores",
    "predictions",
)


def _clone_tensor_tree(value: Any) -> Any:
    if isinstance(value, Tensor):
        return value.clone()
    if is_dataclass(value):
        return replace(
            value,
            **{
                field.name: _clone_tensor_tree(getattr(value, field.name))
                for field in fields(value)
            },
        )
    if isinstance(value, dict):
        return {key: _clone_tensor_tree(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return tuple(_clone_tensor_tree(child) for child in value)
    if isinstance(value, list):
        return [_clone_tensor_tree(child) for child in value]
    return value


def _portable_source_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Remove process-specific pointers while retaining layout/alias evidence."""

    alias_group_by_path: dict[str, str] = {}
    for index, paths in enumerate(snapshot["alias_groups"]):
        for path in paths:
            alias_group_by_path[path] = f"shared_{index}"
    tensors: dict[str, Any] = {}
    for path, signature in snapshot["tensors"].items():
        portable = {
            key: value
            for key, value in signature.items()
            if key not in {"storage_pointer", "alias_key"}
        }
        portable["storage_group"] = alias_group_by_path.get(path, f"unique:{path}")
        tensors[path] = portable
    result = {
        "schema_version": snapshot["schema_version"],
        "tensor_count": snapshot["tensor_count"],
        "tensors": tensors,
        "alias_groups": snapshot["alias_groups"],
    }
    result["snapshot_sha256"] = _json_sha256(result)
    return result


def _storage_disjoint(source: Any, transformed: Any) -> dict[str, Any]:
    source_tensors = _walk_tensors(source)
    transformed_tensors = _walk_tensors(transformed)
    source_paths_by_pointer: dict[tuple[str, int], list[str]] = {}
    for path, tensor in source_tensors.items():
        key = (str(tensor.device), _storage_pointer(tensor))
        source_paths_by_pointer.setdefault(key, []).append(path)
    overlaps: list[dict[str, str]] = []
    for path, tensor in transformed_tensors.items():
        key = (str(tensor.device), _storage_pointer(tensor))
        for source_path in source_paths_by_pointer.get(key, ()):
            overlaps.append({"source_path": source_path, "transformed_path": path})
    checks = {
        "same_tensor_path_set": set(source_tensors) == set(transformed_tensors),
        "no_source_storage_alias": not overlaps,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "overlapping_paths": overlaps,
        "source_tensor_count": len(source_tensors),
        "transformed_tensor_count": len(transformed_tensors),
    }


def _next_valid_index(valid: Tensor, current: int) -> int:
    candidates = torch.nonzero(valid, as_tuple=False).flatten().tolist()
    if len(candidates) < 2:
        raise ValueError("counterfactual query substitution needs two valid endpoints")
    position = candidates.index(current)
    return int(candidates[(position + 1) % len(candidates)])


def substitute_query_values(batch: QueryAnchorBatch) -> QueryAnchorBatch:
    """Move each visible query marker without changing matcher-visible channels."""

    transformed = _clone_tensor_tree(batch)
    for case in range(transformed.regions.prior_features.shape[0]):
        prior_hits = torch.nonzero(
            transformed.prior_query_marker[case], as_tuple=False
        ).flatten()
        if prior_hits.numel():
            old = int(prior_hits.item())
            new = _next_valid_index(transformed.regions.prior_valid[case], old)
            transformed.prior_query_marker[case].zero_()
            transformed.prior_query_marker[case, new] = True
            transformed.regions.prior_features[case, :, 0].zero_()
            transformed.regions.prior_features[case, new, 0] = 1.0
            continue
        old = int(
            torch.nonzero(transformed.current_query_marker[case], as_tuple=False).item()
        )
        new = _next_valid_index(transformed.regions.current_valid[case], old)
        transformed.current_query_marker[case].zero_()
        transformed.current_query_marker[case, new] = True
        transformed.regions.current_features[case, :, 0].zero_()
        transformed.regions.current_features[case, new, 0] = 1.0
    return transformed


def substitute_forbidden_state_channel(batch: QueryAnchorBatch) -> QueryAnchorBatch:
    """Replace the matcher-forbidden state channel by a fixed nonidentity cycle."""

    transformed = _clone_tensor_tree(batch)
    for features in (
        transformed.regions.prior_features,
        transformed.regions.current_features,
    ):
        original = features[..., 1].clone()
        features[..., 1] = torch.where(
            original == -1,
            torch.zeros_like(original),
            torch.where(
                original == 0, torch.ones_like(original), -torch.ones_like(original)
            ),
        )
    return transformed


def _trace_groups(trace: _ChainTrace) -> dict[str, Any]:
    return {
        "matching_regions": trace.matching_regions,
        "token_regions": trace.token_regions,
        "utilities": trace.utilities,
        "soft_plan": trace.soft_plan,
        "plan": trace.plan,
        "relation_candidates": trace.candidates,
        "allocation": trace.allocation,
        "tokens": trace.tokens,
        "projected_tokens": trace.projected,
        "adapter_scores": trace.adapter_scores,
        "predictions": trace.predictions,
    }


def _compare_traces(
    original: _ChainTrace,
    transformed: _ChainTrace,
    *,
    atol: float,
) -> dict[str, Any]:
    left = _trace_groups(original)
    right = _trace_groups(transformed)
    return {
        name: _tensor_group_equality(left[name], right[name], atol=atol)
        for name in _CHAIN_STAGE_NAMES
    }


def _substitution_audit(
    source: QueryAnchorBatch,
    transformed: QueryAnchorBatch,
    original_trace: _ChainTrace,
    transformed_trace: _ChainTrace,
    *,
    atol: float,
) -> dict[str, Any]:
    comparisons = _compare_traces(original_trace, transformed_trace, atol=atol)
    source_values = {
        path: _tensor_value_sha256(tensor)
        for path, tensor in sorted(_walk_tensors(source).items())
    }
    transformed_values = {
        path: _tensor_value_sha256(tensor)
        for path, tensor in sorted(_walk_tensors(transformed).items())
    }
    changed_input_paths = sorted(
        path
        for path in source_values
        if source_values[path] != transformed_values.get(path)
    )
    pretransport = ("matching_regions", "utilities", "soft_plan", "plan")
    downstream = tuple(name for name in _CHAIN_STAGE_NAMES if name not in pretransport)
    checks = {
        "counterfactual_nonvacuous": bool(changed_input_paths),
        "matching_and_transport_exact": all(
            comparisons[name]["all_exact"] for name in pretransport
        ),
        "full_chain_covered": set(comparisons) == set(_CHAIN_STAGE_NAMES),
        "downstream_change_observed": any(
            not comparisons[name]["all_exact"] for name in downstream
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "changed_input_paths": changed_input_paths,
        "comparisons": comparisons,
    }


def _module_state_sha256(module: nn.Module) -> str:
    hashes = {
        name: _tensor_value_sha256(tensor)
        for name, tensor in sorted(module.state_dict().items())
    }
    return _json_sha256(hashes)


def _canonical_tree(value: Any) -> Any:
    if isinstance(value, Tensor):
        return {
            "dtype": str(value.dtype),
            "shape": list(value.shape),
            "value_sha256": _tensor_value_sha256(value),
        }
    if is_dataclass(value):
        return {
            field.name: _canonical_tree(getattr(value, field.name))
            for field in fields(value)
            if field.name != "diagnostics"
        }
    if isinstance(value, Mapping):
        return {str(key): _canonical_tree(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (tuple, list)):
        return [_canonical_tree(child) for child in value]
    return value


def _recursive_diff(left: Any, right: Any, prefix: str = "") -> list[str]:
    if type(left) is not type(right):
        return [prefix or "$type"]
    if isinstance(left, Mapping):
        paths: list[str] = []
        for key in sorted(set(left) | set(right), key=str):
            path = f"{prefix}.{key}" if prefix else str(key)
            if key not in left or key not in right:
                paths.append(path)
            else:
                paths.extend(_recursive_diff(left[key], right[key], path))
        return paths
    if isinstance(left, list):
        if len(left) != len(right):
            return [f"{prefix}.length"]
        paths = []
        for index, (lhs, rhs) in enumerate(zip(left, right, strict=True)):
            paths.extend(_recursive_diff(lhs, rhs, f"{prefix}.{index}"))
        return paths
    return [] if left == right else [prefix]


def _b4_allowlist_category(path: str) -> str | None:
    if path == "plan.mode":
        return "assignment_mode"
    if path.startswith("plan.transport.") or path.startswith("tokens.assignment."):
        return "assignment_tensor"
    if path.startswith("relation_candidates.relation_features.") or path.startswith(
        "relation_candidates.relation_mass."
    ):
        return "causally_downstream_relation_change_values"
    if path.startswith("allocation."):
        return "assignment_induced_source_order"
    if path.startswith("tokens.") or path.startswith("projected_tokens."):
        return "relation_change_token_values"
    if path.startswith("adapter_scores."):
        return "scores"
    if path.startswith("predictions."):
        return "predictions"
    return None


def _b4_trace_tree(trace: _ChainTrace) -> dict[str, Any]:
    groups = _trace_groups(trace)
    selected = (
        "plan",
        "relation_candidates",
        "allocation",
        "tokens",
        "projected_tokens",
        "adapter_scores",
        "predictions",
    )
    return {name: _canonical_tree(groups[name]) for name in selected}


def _b4_audit(
    batch: QueryAnchorBatch,
    hooks: R6ChainHooks,
    *,
    atol: float,
) -> dict[str, Any]:
    bank = build_balanced_derangement_bank(batch, REGISTERED_DERANGEMENT_SEEDS)
    b4a_plan = bank[REGISTERED_DERANGEMENT_SEEDS[0]]
    b4b_plan = batch.oracle.plan
    projector_before = _module_state_sha256(hooks.projector)
    adapter_before = _module_state_sha256(hooks.adapter)
    b4a_trace = _execute_chain(batch, hooks, plan_override=b4a_plan)
    projector_between = _module_state_sha256(hooks.projector)
    adapter_between = _module_state_sha256(hooks.adapter)
    b4b_trace = _execute_chain(batch, hooks, plan_override=b4b_plan)
    projector_after = _module_state_sha256(hooks.projector)
    adapter_after = _module_state_sha256(hooks.adapter)
    shared_comparisons = {
        name: _tensor_group_equality(
            _trace_groups(b4a_trace)[name],
            _trace_groups(b4b_trace)[name],
            atol=atol,
        )
        for name in ("matching_regions", "token_regions", "utilities", "soft_plan")
    }
    left_tree = _b4_trace_tree(b4a_trace)
    right_tree = _b4_trace_tree(b4b_trace)
    diff_paths = _recursive_diff(left_tree, right_tree)
    diff_entries = [
        {"path": path, "allowlist_category": _b4_allowlist_category(path)}
        for path in diff_paths
    ]
    unexpected = [
        entry["path"] for entry in diff_entries if entry["allowlist_category"] is None
    ]
    observed_categories = sorted(
        {
            entry["allowlist_category"]
            for entry in diff_entries
            if entry["allowlist_category"]
        }
    )
    checks = {
        "b4a_plan_nonidentity": not torch.equal(b4a_plan.transport, b4b_plan.transport),
        "shared_input_utility_chain_exact": all(
            comparison["all_exact"] for comparison in shared_comparisons.values()
        ),
        "projector_state_bitwise_exact": projector_before
        == projector_between
        == projector_after,
        "adapter_state_bitwise_exact": adapter_before
        == adapter_between
        == adapter_after,
        "recursive_diff_nonempty": bool(diff_entries),
        "all_non_allowlisted_paths_exact": not unexpected,
        "scores_and_predictions_covered": {
            "adapter_scores",
            "predictions",
        }.issubset(left_tree),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "allowlist": list(_B4_ALLOWLIST),
        "diff_entries": diff_entries,
        "unexpected_paths": unexpected,
        "observed_allowlist_categories": observed_categories,
        "shared_comparisons": shared_comparisons,
        "b4a_trace": left_tree,
        "b4b_trace": right_tree,
        "b4a_assignment_sha256": _tensor_value_sha256(b4a_plan.transport),
        "b4b_assignment_sha256": _tensor_value_sha256(b4b_plan.transport),
        "projector_state_sha256": {
            "before": projector_before,
            "between": projector_between,
            "after": projector_after,
        },
        "adapter_state_sha256": {
            "before": adapter_before,
            "between": adapter_between,
            "after": adapter_after,
        },
    }


def run_r6_counterfactual_audits(
    batch: QueryAnchorBatch,
    hooks: R6ChainHooks,
    *,
    float_atol: float = DEFAULT_FLOAT_ATOL,
    hidden_relabeler: Callable[
        [QueryAnchorBatch], QueryAnchorBatch
    ] = equality_preserving_hidden_relabel,
) -> dict[str, Any]:
    """Run all five R6 full-chain counterfactual audits fail-closed."""

    if float_atol < 0:
        raise ValueError("float_atol must be nonnegative")
    batch.validate()
    caller_before = source_tensor_snapshot(batch)
    audited_batch = _with_stable_source_ids(batch)
    audited_batch.validate()
    relabeled = hidden_relabeler(_clone_tensor_tree(audited_batch))
    relabel_contract = hidden_relabel_contract(audited_batch, relabeled)
    original_trace = _execute_chain(audited_batch, hooks)
    relabeled_trace = _execute_chain(relabeled, hooks)
    hidden_invariance = _hidden_invariance(
        original_trace, relabeled_trace, atol=float_atol
    )
    permuted, prior_permutation, current_permutation = independently_permute_endpoints(
        _clone_tensor_tree(audited_batch)
    )
    permuted.validate()
    permuted_trace = _execute_chain(permuted, hooks)
    permutation = _permutation_equivariance(
        original_trace,
        permuted_trace,
        prior_permutation,
        current_permutation,
        atol=float_atol,
    )
    query_substituted = substitute_query_values(audited_batch)
    query_trace = _execute_chain(query_substituted, hooks)
    query_substitution = _substitution_audit(
        audited_batch,
        query_substituted,
        original_trace,
        query_trace,
        atol=float_atol,
    )
    state_substituted = substitute_forbidden_state_channel(audited_batch)
    state_trace = _execute_chain(state_substituted, hooks)
    forbidden_state_substitution = _substitution_audit(
        audited_batch,
        state_substituted,
        original_trace,
        state_trace,
        atol=float_atol,
    )
    b4 = _b4_audit(audited_batch, hooks, atol=float_atol)
    transformed_storage = {
        "hidden_id_relabel": _storage_disjoint(audited_batch, relabeled),
        "endpoint_permutation": _storage_disjoint(audited_batch, permuted),
        "query_value_substitution": _storage_disjoint(audited_batch, query_substituted),
        "forbidden_state_channel_substitution": _storage_disjoint(
            audited_batch, state_substituted
        ),
    }
    caller_after = source_tensor_snapshot(batch)
    source_checks = {
        "value_dtype_shape_stride_pointer_exact": caller_before == caller_after,
        "alias_groups_exact": caller_before["alias_groups"]
        == caller_after["alias_groups"],
        "snapshot_hash_exact": caller_before["snapshot_sha256"]
        == caller_after["snapshot_sha256"],
    }
    source_audit = {
        "passed": all(source_checks.values()),
        "checks": source_checks,
        "before": _portable_source_snapshot(caller_before),
        "after": _portable_source_snapshot(caller_after),
    }
    checks = {
        "hidden_relabel_contract": relabel_contract["passed"],
        "hidden_id_full_chain_invariance": hidden_invariance["passed"],
        "endpoint_permutation_full_chain_equivariance": permutation["passed"],
        "query_value_substitution_before_transport": query_substitution["passed"],
        "forbidden_state_channel_substitution": forbidden_state_substitution["passed"],
        "b4a_deranged_vs_b4b_oracle": b4["passed"],
        "transformed_fixtures_storage_disjoint": all(
            audit["passed"] for audit in transformed_storage.values()
        ),
        "source_tensors_immutable": source_audit["passed"],
    }
    report = {
        "schema_version": R6_COUNTERFACTUAL_SCHEMA_VERSION,
        "status": "PASS_R6_COUNTERFACTUAL_AUDITS"
        if all(checks.values())
        else "FAIL_R6_COUNTERFACTUAL_AUDITS",
        "passed": all(checks.values()),
        "checks": checks,
        "forward_boundary": {
            "hidden_oracle_passed_to_matcher": False,
            "hidden_oracle_passed_to_tokenizer": False,
            "hidden_oracle_passed_to_projector": False,
            "hidden_oracle_passed_to_adapter": False,
            "batch_aware_hooks": ["matching_regions", "token_regions"],
        },
        "hidden_id_relabel": {
            "contract": relabel_contract,
            "full_chain": hidden_invariance,
        },
        "endpoint_permutation": permutation,
        "query_value_substitution": query_substitution,
        "forbidden_state_channel_substitution": forbidden_state_substitution,
        "b4a_deranged_vs_b4b_oracle": b4,
        "transformed_storage_audit": transformed_storage,
        "source_tensor_audit": source_audit,
        "reference_trace": _trace_evidence(original_trace),
    }
    report["report_sha256"] = _json_sha256(report)
    return report


def _require_exact_keys(
    value: Mapping[str, Any], expected: Sequence[str], path: str
) -> None:
    if set(value) != set(expected):
        raise ValueError(
            f"{path} key mismatch: expected {sorted(expected)}, got {sorted(value)}"
        )


def _validate_comparison(comparison: Mapping[str, Any], path: str) -> None:
    expected = (
        "fields_exact",
        "all_exact",
        "all_close",
        "exact_by_field",
        "close_by_field",
        "max_abs_error_by_field",
        "value_sha256_by_field",
    )
    _require_exact_keys(comparison, expected, path)
    fields = set(comparison["exact_by_field"])
    if not (
        fields
        == set(comparison["close_by_field"])
        == set(comparison["max_abs_error_by_field"])
        == set(comparison["value_sha256_by_field"])
    ):
        raise ValueError(f"{path} field sets disagree")
    expected_exact = comparison["fields_exact"] and all(
        value is True for value in comparison["exact_by_field"].values()
    )
    expected_close = comparison["fields_exact"] and all(
        value is True for value in comparison["close_by_field"].values()
    )
    if comparison["all_exact"] is not expected_exact:
        raise ValueError(f"{path}.all_exact is not derived from its fields")
    if comparison["all_close"] is not expected_close:
        raise ValueError(f"{path}.all_close is not derived from its fields")


def validate_r6_counterfactual_audit(report: Mapping[str, Any]) -> None:
    """Independently validate schema, derived checks, recursive diff, and seal."""

    if not isinstance(report, Mapping):
        raise TypeError("report must be a mapping")
    _require_exact_keys(
        report,
        (
            "schema_version",
            "status",
            "passed",
            "checks",
            "forward_boundary",
            "hidden_id_relabel",
            "endpoint_permutation",
            "query_value_substitution",
            "forbidden_state_channel_substitution",
            "b4a_deranged_vs_b4b_oracle",
            "transformed_storage_audit",
            "source_tensor_audit",
            "reference_trace",
            "report_sha256",
        ),
        "report",
    )
    if report["schema_version"] != R6_COUNTERFACTUAL_SCHEMA_VERSION:
        raise ValueError("unexpected R6 counterfactual schema version")
    expected_hash = _json_sha256(
        {key: value for key, value in report.items() if key != "report_sha256"}
    )
    if report["report_sha256"] != expected_hash:
        raise ValueError("R6 counterfactual report SHA-256 mismatch")

    forward = report["forward_boundary"]
    _require_exact_keys(
        forward,
        (
            "hidden_oracle_passed_to_matcher",
            "hidden_oracle_passed_to_tokenizer",
            "hidden_oracle_passed_to_projector",
            "hidden_oracle_passed_to_adapter",
            "batch_aware_hooks",
        ),
        "forward_boundary",
    )
    if any(
        forward[key] is not False
        for key in (
            "hidden_oracle_passed_to_matcher",
            "hidden_oracle_passed_to_tokenizer",
            "hidden_oracle_passed_to_projector",
            "hidden_oracle_passed_to_adapter",
        )
    ) or forward["batch_aware_hooks"] != ["matching_regions", "token_regions"]:
        raise ValueError("forward-boundary declaration violates the frozen contract")

    hidden = report["hidden_id_relabel"]
    _require_exact_keys(hidden, ("contract", "full_chain"), "hidden_id_relabel")
    _require_exact_keys(
        hidden["contract"],
        (
            "passed",
            "checks",
            "original_equality_sha256",
            "relabeled_equality_sha256",
            "original_ids_sha256",
            "relabeled_ids_sha256",
        ),
        "hidden_id_relabel.contract",
    )
    _require_exact_keys(
        hidden["contract"]["checks"],
        (
            "counterfactual_nonvacuous",
            "gold_equality_relation_exact",
            "oracle_plan_exact",
            "original_plan_matches_gold_equality",
            "relabeled_plan_matches_gold_equality",
        ),
        "hidden_id_relabel.contract.checks",
    )
    _require_exact_keys(
        hidden["full_chain"],
        ("passed", "equality_policy", "checks", "comparisons"),
        "hidden_id_relabel.full_chain",
    )
    if hidden["contract"]["passed"] is not all(hidden["contract"]["checks"].values()):
        raise ValueError("hidden relabel contract passed flag is not derived")
    if hidden["contract"]["checks"]["counterfactual_nonvacuous"] is not (
        hidden["contract"]["original_ids_sha256"]
        != hidden["contract"]["relabeled_ids_sha256"]
    ) or hidden["contract"]["checks"]["gold_equality_relation_exact"] is not (
        hidden["contract"]["original_equality_sha256"]
        == hidden["contract"]["relabeled_equality_sha256"]
    ):
        raise ValueError("hidden relabel nonvacuity/equality checks are not derived")
    hidden_checks = hidden["full_chain"]["checks"]
    expected_hidden_checks = {
        name: comparison["all_exact"]
        for name, comparison in hidden["full_chain"]["comparisons"].items()
    }
    if hidden_checks != expected_hidden_checks or hidden["full_chain"][
        "passed"
    ] is not all(expected_hidden_checks.values()):
        raise ValueError("hidden full-chain passed flag is not derived")
    for name, comparison in hidden["full_chain"]["comparisons"].items():
        _validate_comparison(comparison, f"hidden_id_relabel.full_chain.{name}")

    permutation = report["endpoint_permutation"]
    _require_exact_keys(
        permutation,
        (
            "passed",
            "equality_policy",
            "checks",
            "comparisons",
            "prior_permutation_sha256",
            "current_permutation_sha256",
            "prior_permutation",
            "current_permutation",
        ),
        "endpoint_permutation",
    )
    prior_permutation = torch.tensor(permutation["prior_permutation"], dtype=torch.long)
    current_permutation = torch.tensor(
        permutation["current_permutation"], dtype=torch.long
    )
    if permutation["prior_permutation_sha256"] != _tensor_value_sha256(
        prior_permutation
    ) or permutation["current_permutation_sha256"] != _tensor_value_sha256(
        current_permutation
    ):
        raise ValueError("endpoint permutation values disagree with their SHA fields")
    expected_permutation_checks = {
        name: comparison["all_close"]
        for name, comparison in permutation["comparisons"].items()
    }
    expected_permutation_checks["prior_permutation_nonidentity"] = not torch.equal(
        prior_permutation, torch.arange(len(prior_permutation))
    )
    expected_permutation_checks["current_permutation_nonidentity"] = not torch.equal(
        current_permutation, torch.arange(len(current_permutation))
    )
    if permutation["checks"] != expected_permutation_checks or permutation[
        "passed"
    ] is not all(expected_permutation_checks.values()):
        raise ValueError("endpoint permutation passed flag is not derived")
    for name, comparison in permutation["comparisons"].items():
        _validate_comparison(comparison, f"endpoint_permutation.{name}")

    for name in (
        "query_value_substitution",
        "forbidden_state_channel_substitution",
    ):
        audit = report[name]
        _require_exact_keys(
            audit,
            ("passed", "checks", "changed_input_paths", "comparisons"),
            name,
        )
        if set(audit["comparisons"]) != set(_CHAIN_STAGE_NAMES):
            raise ValueError(f"{name} does not cover the full chain")
        for stage, comparison in audit["comparisons"].items():
            _validate_comparison(comparison, f"{name}.{stage}")
        recomputed = {
            "counterfactual_nonvacuous": bool(audit["changed_input_paths"]),
            "matching_and_transport_exact": all(
                audit["comparisons"][stage]["all_exact"]
                for stage in ("matching_regions", "utilities", "soft_plan", "plan")
            ),
            "full_chain_covered": set(audit["comparisons"]) == set(_CHAIN_STAGE_NAMES),
            "downstream_change_observed": any(
                not audit["comparisons"][stage]["all_exact"]
                for stage in _CHAIN_STAGE_NAMES
                if stage not in {"matching_regions", "utilities", "soft_plan", "plan"}
            ),
        }
        if audit["checks"] != recomputed or audit["passed"] is not all(
            recomputed.values()
        ):
            raise ValueError(f"{name} derived checks disagree")

    b4 = report["b4a_deranged_vs_b4b_oracle"]
    _require_exact_keys(
        b4,
        (
            "passed",
            "checks",
            "allowlist",
            "diff_entries",
            "unexpected_paths",
            "observed_allowlist_categories",
            "shared_comparisons",
            "b4a_trace",
            "b4b_trace",
            "b4a_assignment_sha256",
            "b4b_assignment_sha256",
            "projector_state_sha256",
            "adapter_state_sha256",
        ),
        "b4a_deranged_vs_b4b_oracle",
    )
    for name, comparison in b4["shared_comparisons"].items():
        _validate_comparison(comparison, f"b4.shared_comparisons.{name}")
    if set(b4["shared_comparisons"]) != {
        "matching_regions",
        "token_regions",
        "utilities",
        "soft_plan",
    }:
        raise ValueError("B4 shared-prefix comparison set is incomplete")
    recomputed_paths = _recursive_diff(b4["b4a_trace"], b4["b4b_trace"])
    recomputed_entries = [
        {"path": path, "allowlist_category": _b4_allowlist_category(path)}
        for path in recomputed_paths
    ]
    if b4["allowlist"] != list(_B4_ALLOWLIST):
        raise ValueError("B4 allowlist differs from the frozen contract")
    if b4["diff_entries"] != recomputed_entries:
        raise ValueError("B4 recursive diff entries are not independently reproducible")
    unexpected = [
        entry["path"]
        for entry in recomputed_entries
        if entry["allowlist_category"] is None
    ]
    categories = sorted(
        {
            entry["allowlist_category"]
            for entry in recomputed_entries
            if entry["allowlist_category"]
        }
    )
    if b4["unexpected_paths"] != unexpected:
        raise ValueError("B4 unexpected path list is not derived")
    if b4["observed_allowlist_categories"] != categories:
        raise ValueError("B4 observed allowlist categories are not derived")
    shared_exact = all(
        comparison["all_exact"] for comparison in b4["shared_comparisons"].values()
    )
    b4a_assignment = b4["b4a_trace"]["plan"]["transport"]["value_sha256"]
    b4b_assignment = b4["b4b_trace"]["plan"]["transport"]["value_sha256"]
    if (
        b4["b4a_assignment_sha256"] != b4a_assignment
        or b4["b4b_assignment_sha256"] != b4b_assignment
    ):
        raise ValueError("B4 assignment SHA fields disagree with trace payloads")
    projector_states = b4["projector_state_sha256"]
    adapter_states = b4["adapter_state_sha256"]
    _require_exact_keys(
        projector_states, ("before", "between", "after"), "B4 projector states"
    )
    _require_exact_keys(
        adapter_states, ("before", "between", "after"), "B4 adapter states"
    )
    b4_recomputed = {
        "b4a_plan_nonidentity": b4a_assignment != b4b_assignment,
        "shared_input_utility_chain_exact": shared_exact,
        "projector_state_bitwise_exact": len(set(projector_states.values())) == 1,
        "adapter_state_bitwise_exact": len(set(adapter_states.values())) == 1,
        "recursive_diff_nonempty": bool(recomputed_entries),
        "all_non_allowlisted_paths_exact": not unexpected,
        "scores_and_predictions_covered": {
            "adapter_scores",
            "predictions",
        }.issubset(b4["b4a_trace"]),
    }
    if b4_recomputed != b4["checks"] or b4["passed"] is not all(b4_recomputed.values()):
        raise ValueError("B4 checks or passed flag are not derived")

    storage = report["transformed_storage_audit"]
    expected_storage_names = {
        "hidden_id_relabel",
        "endpoint_permutation",
        "query_value_substitution",
        "forbidden_state_channel_substitution",
    }
    if set(storage) != expected_storage_names:
        raise ValueError("transformed storage audit set is incomplete")
    for name, audit in storage.items():
        _require_exact_keys(
            audit,
            (
                "passed",
                "checks",
                "overlapping_paths",
                "source_tensor_count",
                "transformed_tensor_count",
            ),
            f"transformed_storage_audit.{name}",
        )
        _require_exact_keys(
            audit["checks"],
            ("same_tensor_path_set", "no_source_storage_alias"),
            f"transformed_storage_audit.{name}.checks",
        )
        if audit["passed"] is not all(audit["checks"].values()):
            raise ValueError(f"storage audit {name} passed flag is not derived")
        if audit["checks"]["no_source_storage_alias"] is not (
            not audit["overlapping_paths"]
        ):
            raise ValueError(f"storage audit {name} overlap relation disagrees")

    source = report["source_tensor_audit"]
    _require_exact_keys(
        source,
        ("passed", "checks", "before", "after"),
        "source_tensor_audit",
    )
    _require_exact_keys(
        source["checks"],
        (
            "value_dtype_shape_stride_pointer_exact",
            "alias_groups_exact",
            "snapshot_hash_exact",
        ),
        "source_tensor_audit.checks",
    )
    before = source["before"]
    after = source["after"]
    for name, snapshot in (("before", before), ("after", after)):
        expected_snapshot_hash = _json_sha256(
            {key: value for key, value in snapshot.items() if key != "snapshot_sha256"}
        )
        if snapshot["snapshot_sha256"] != expected_snapshot_hash:
            raise ValueError(f"source {name} portable snapshot SHA mismatch")
    expected_source_checks = {
        "value_dtype_shape_stride_pointer_exact": before == after,
        "alias_groups_exact": before["alias_groups"] == after["alias_groups"],
        "snapshot_hash_exact": before["snapshot_sha256"] == after["snapshot_sha256"],
    }
    if source["checks"] != expected_source_checks or source["passed"] is not all(
        expected_source_checks.values()
    ):
        raise ValueError("source tensor audit passed flag is not derived")

    reference = report["reference_trace"]
    if set(reference) != {
        "matching_regions",
        "token_regions",
        "utilities",
        "soft_plan",
        "plan",
        "relation_candidates",
        "allocation",
        "tokens",
        "projected_tokens",
        "adapter_scores",
        "predictions",
    }:
        raise ValueError("reference trace stage set is incomplete")
    for stage, evidence in reference.items():
        _require_exact_keys(
            evidence,
            ("value_sha256_by_field", "group_sha256"),
            f"reference_trace.{stage}",
        )
        if evidence["group_sha256"] != _json_sha256(evidence["value_sha256_by_field"]):
            raise ValueError(f"reference trace {stage} group SHA mismatch")
    derived_checks = {
        "hidden_relabel_contract": hidden["contract"]["passed"],
        "hidden_id_full_chain_invariance": hidden["full_chain"]["passed"],
        "endpoint_permutation_full_chain_equivariance": permutation["passed"],
        "query_value_substitution_before_transport": report["query_value_substitution"][
            "passed"
        ],
        "forbidden_state_channel_substitution": report[
            "forbidden_state_channel_substitution"
        ]["passed"],
        "b4a_deranged_vs_b4b_oracle": b4["passed"],
        "transformed_fixtures_storage_disjoint": all(
            audit["passed"] for audit in storage.values()
        ),
        "source_tensors_immutable": source["passed"],
    }
    _require_exact_keys(report["checks"], tuple(derived_checks), "report.checks")
    if report["checks"] != derived_checks:
        raise ValueError("top-level counterfactual checks are not derived")
    passed = all(derived_checks.values())
    expected_status = (
        "PASS_R6_COUNTERFACTUAL_AUDITS" if passed else "FAIL_R6_COUNTERFACTUAL_AUDITS"
    )
    if report["passed"] is not passed or report["status"] != expected_status:
        raise ValueError("top-level passed/status fields are not derived")
    if not passed:
        raise ValueError("R6 counterfactual audit did not pass")


__all__ = [
    "DEFAULT_FLOAT_ATOL",
    "R6_COUNTERFACTUAL_SCHEMA_VERSION",
    "R6ChainHooks",
    "equality_preserving_hidden_relabel",
    "hidden_relabel_contract",
    "independently_permute_endpoints",
    "run_r6_counterfactual_audits",
    "source_tensor_snapshot",
    "substitute_forbidden_state_channel",
    "substitute_query_values",
    "validate_r6_counterfactual_audit",
]
