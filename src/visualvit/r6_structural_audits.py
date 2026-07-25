"""Fail-closed structural microcases for the R6 partial-OT matcher."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import itertools
import json
import math
from typing import Any, Mapping

import torch
from torch import Tensor

from .matching import InvariantPartialOTMatcher
from .schemas import RegionBatch


R6_STRUCTURAL_AUDIT_SCHEMA_VERSION = "visualvit.r6-structural-audits.v3"
R6_STRUCTURAL_CASE_IDS = (
    "one_persistent_1x1",
    "one_death_1x0",
    "one_birth_0x1",
    "collision_2x1",
    "crossing_2x2",
    "tied_utility_2x2",
    "mixed_persistent_death_birth_2x2",
    "anatomy_forbidden_edge",
)
R6_REQUIRED_PER_CASE_EVIDENCE = (
    "input_sha256_before",
    "input_sha256_after",
    "utility_sha256",
    "soft_plan_sha256",
    "hard_plan_sha256",
    "feasibility_residuals",
    "expected_plan_exact",
    "completion_counts",
    "gradient_audit",
)

_TOP_LEVEL_KEYS = {
    "schema_version",
    "passed",
    "required_case_ids",
    "required_per_case_evidence",
    "microcases",
    "ordered_microcase_projection_sha256",
    "registered_gradient_audit",
    "audit_sha256",
}
_CASE_KEYS = set(R6_REQUIRED_PER_CASE_EVIDENCE)
_PLAN_KEYS = {
    "prior_count",
    "current_count",
    "prior_valid",
    "current_valid",
    "prior_anatomy",
    "current_anatomy",
    "edge_utility",
    "prior_null_utility",
    "current_null_utility",
    "compatibility",
    "soft_transport",
    "soft_internal_transport",
    "hard_transport",
    "expected_hard_transport",
    "hard_plan_matches_expected",
    "tie_policy",
}
_FEASIBILITY_KEYS = {
    "enumerated_feasible_assignments",
    "optimal_assignment_count",
    "exhaustive_optimal_utility",
    "selected_utility",
    "hard_optimality_gap",
    "hard_prior_mass_max_residual",
    "hard_current_mass_max_residual",
    "soft_internal_row_mass_max_residual",
    "soft_internal_column_mass_max_residual",
    "soft_prior_capacity_max_excess",
    "soft_current_capacity_max_excess",
    "forbidden_hard_mass",
    "forbidden_soft_mass",
    "lexicographic_tie_selected",
}
_COMPLETION_KEYS = {
    "valid_prior_count",
    "valid_current_count",
    "persistent_count",
    "death_count",
    "birth_count",
    "hard_covers_every_prior_once",
    "hard_covers_every_current_once",
    "persistent_death_birth_partition_exact",
    "no_duplicate_real_current",
}
_GRADIENT_AUDIT_KEYS = {
    "applicability",
    "na_reason",
    "registered_parameter_names",
    "registered_parameter_names_exact",
    "loss",
    "finite_loss",
    "gradients",
    "finite_gradients",
    "nonzero_expected_gradient_each_trainable_parameter",
    "forbidden_input_or_query_gradient",
    "optimizer_owner_exact",
}
_GRADIENT_NAMES = (
    "view_weight_logits[0]",
    "view_weight_logits[1]",
    "residual_coefficient",
    "prior_null_utility",
    "current_null_utility",
)
_GRADIENT_VALUE_KEYS = {"finite", "nonzero", "value"}
_TIE_POLICY = "lexicographically-smallest semantic hard transport"
_NOT_APPLICABLE = "NOT_APPLICABLE_ANALYTIC_UTILITY_FIXTURE"


def _require_finite_json(value: Any, path: str = "report") -> None:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} contains a non-finite float")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} keys must be strings")
            _require_finite_json(item, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _require_finite_json(item, f"{path}[{index}]")
        return
    raise TypeError(f"{path} contains non-JSON value {type(value).__name__}")


def canonical_sha256(value: Any) -> str:
    """Hash a finite JSON value with stable key order and separators."""

    _require_finite_json(value)
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_exact_keys(
    value: Mapping[str, Any], expected: set[str], path: str
) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{path} schema mismatch; missing={missing}, extra={extra}")


def _region_batch(
    matcher: InvariantPartialOTMatcher,
    prior_anatomy: list[int],
    current_anatomy: list[int],
) -> RegionBatch:
    prior_count = len(prior_anatomy)
    current_count = len(current_anatomy)
    prior = torch.zeros((1, prior_count, matcher.feature_dim), dtype=torch.float32)
    current = torch.zeros((1, current_count, matcher.feature_dim), dtype=torch.float32)
    return RegionBatch(
        prior_features=prior,
        current_features=current,
        prior_valid=torch.ones((1, prior_count), dtype=torch.bool),
        current_valid=torch.ones((1, current_count), dtype=torch.bool),
        prior_anatomy=torch.tensor([prior_anatomy], dtype=torch.long),
        current_anatomy=torch.tensor([current_anatomy], dtype=torch.long),
        prior_entity_ids=torch.arange(prior_count, dtype=torch.long).unsqueeze(0),
        current_entity_ids=torch.arange(current_count, dtype=torch.long).unsqueeze(0),
    )


def _fixture(matcher: InvariantPartialOTMatcher) -> RegionBatch:
    if len(matcher.identity_views) != 2:
        raise ValueError("R6 structural audit requires exactly two identity views")
    for start, end in matcher.identity_views:
        if end - start < 2:
            raise ValueError("each R6 identity view must have at least two channels")
    regions = _region_batch(matcher, [0, 0], [0, 0])
    for view_index, (start, _end) in enumerate(matcher.identity_views):
        regions.prior_features[0, 0, start] = 1.0
        regions.prior_features[0, 1, start + 1] = 1.0
        if view_index == 0:
            regions.current_features[0, 0, start] = 1.0
            regions.current_features[0, 1, start + 1] = 1.0
        else:
            regions.current_features[0, 1, start] = 1.0
            regions.current_features[0, 0, start + 1] = 1.0
    return regions


def _registered_gradient_audit(
    matcher: InvariantPartialOTMatcher,
) -> dict[str, Any]:
    probe = deepcopy(matcher).to("cpu")
    named = dict(probe.named_parameters())
    required_tensors = {
        "view_weight_logits",
        "residual_coefficient",
        "prior_null_utility",
        "current_null_utility",
    }
    if set(named) != required_tensors:
        raise ValueError(f"unexpected R6 matcher parameters: {sorted(named)}")
    if named["view_weight_logits"].numel() != 2:
        raise ValueError("R6 view_weight_logits must contain exactly two scalars")
    if sum(parameter.numel() for parameter in named.values()) != 5:
        raise ValueError("R6 matcher must expose exactly five trainable scalars")
    for name, parameter in named.items():
        if not bool(torch.isfinite(parameter).all()):
            raise ValueError(f"matcher parameter {name} is non-finite at step 0")

    regions = _fixture(probe)
    regions.prior_features.requires_grad_(True)
    regions.current_features.requires_grad_(True)
    transport = probe.soft_plan(regions).transport
    loss = (
        -(transport[0, 0, 0] + transport[0, 1, 1])
        + 0.7 * transport[0, 0, 1]
        + 0.3 * transport[0, 1, 0]
        - 0.2 * transport[0, 0, 2]
        - 0.4 * transport[0, 2, 1]
    )
    if not bool(torch.isfinite(loss)):
        raise ValueError("step-0 structural loss is non-finite")
    loss.backward()
    gradient_values = {
        "view_weight_logits[0]": named["view_weight_logits"].grad[0],
        "view_weight_logits[1]": named["view_weight_logits"].grad[1],
        "residual_coefficient": named["residual_coefficient"].grad,
        "prior_null_utility": named["prior_null_utility"].grad,
        "current_null_utility": named["current_null_utility"].grad,
    }
    gradients: dict[str, dict[str, Any]] = {}
    for name, gradient in gradient_values.items():
        scalar = float(gradient.detach()) if gradient is not None else 0.0
        gradients[name] = {
            "finite": gradient is not None and math.isfinite(scalar),
            "nonzero": gradient is not None and scalar != 0.0,
            "value": scalar,
        }
    forbidden_gradients = torch.cat(
        (
            regions.prior_features.grad[..., :2].flatten(),
            regions.current_features.grad[..., :2].flatten(),
        )
    )
    names_exact = list(gradients) == list(_GRADIENT_NAMES)
    finite_gradients = all(item["finite"] for item in gradients.values())
    nonzero = all(item["nonzero"] for item in gradients.values())
    return {
        "applicability": "APPLICABLE_REGISTERED_STEP0_MATCHER",
        "na_reason": "",
        "registered_parameter_names": list(gradients),
        "registered_parameter_names_exact": names_exact,
        "loss": float(loss.detach()),
        "finite_loss": math.isfinite(float(loss.detach())),
        "gradients": gradients,
        "finite_gradients": finite_gradients,
        "nonzero_expected_gradient_each_trainable_parameter": nonzero,
        "forbidden_input_or_query_gradient": bool(
            torch.equal(forbidden_gradients, torch.zeros_like(forbidden_gradients))
        ),
        "optimizer_owner_exact": set(named) == required_tensors,
    }


def _na_gradient_audit() -> dict[str, Any]:
    return {
        "applicability": _NOT_APPLICABLE,
        "na_reason": (
            "case uses frozen analytic utilities; gradients are audited once on the "
            "registered matcher forward in registered_gradient_audit"
        ),
        "registered_parameter_names": [],
        "registered_parameter_names_exact": True,
        "loss": 0.0,
        "finite_loss": True,
        "gradients": {},
        "finite_gradients": True,
        "nonzero_expected_gradient_each_trainable_parameter": True,
        "forbidden_input_or_query_gradient": True,
        "optimizer_owner_exact": True,
    }


def _case_specs() -> dict[str, dict[str, Any]]:
    return {
        "one_persistent_1x1": {
            "prior_anatomy": [0],
            "current_anatomy": [0],
            "edge": [[0.08]],
            "death": [0.01],
            "birth": [0.01],
            "expected": [[1.0, 0.0], [0.0, 0.0]],
        },
        "one_death_1x0": {
            "prior_anatomy": [0],
            "current_anatomy": [],
            "edge": [[]],
            "death": [0.03],
            "birth": [],
            "expected": [[1.0], [0.0]],
        },
        "one_birth_0x1": {
            "prior_anatomy": [],
            "current_anatomy": [0],
            "edge": [],
            "death": [],
            "birth": [0.03],
            "expected": [[1.0, 0.0]],
        },
        "collision_2x1": {
            "prior_anatomy": [0, 0],
            "current_anatomy": [0],
            "edge": [[0.09], [0.08]],
            "death": [0.01, 0.01],
            "birth": [0.0],
            "expected": [[1.0, 0.0], [0.0, 1.0], [0.0, 0.0]],
        },
        "crossing_2x2": {
            "prior_anatomy": [0, 0],
            "current_anatomy": [0, 0],
            "edge": [[0.01, 0.09], [0.08, 0.02]],
            "death": [0.0, 0.0],
            "birth": [0.0, 0.0],
            "expected": [
                [0.0, 1.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],
            ],
        },
        "tied_utility_2x2": {
            "prior_anatomy": [0, 0],
            "current_anatomy": [0, 0],
            "edge": [[0.05, 0.05], [0.05, 0.05]],
            "death": [-0.02, -0.02],
            "birth": [-0.02, -0.02],
            "expected": [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0],
            ],
        },
        "mixed_persistent_death_birth_2x2": {
            "prior_anatomy": [0, 0],
            "current_anatomy": [0, 0],
            "edge": [[0.09, -0.05], [-0.05, -0.05]],
            "death": [0.0, 0.02],
            "birth": [0.0, 0.03],
            "expected": [
                [1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0],
                [0.0, 1.0, 0.0],
            ],
        },
        "anatomy_forbidden_edge": {
            "prior_anatomy": [0, 1],
            "current_anatomy": [0, 1],
            "edge": [[0.02, 0.099], [0.099, 0.03]],
            "death": [0.005, 0.005],
            "birth": [0.005, 0.005],
            "expected": [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0],
            ],
        },
    }


def _augmented_from_snapshot(
    snapshot: Mapping[str, Any],
) -> tuple[list[list[float]], list[list[bool]]]:
    prior_count = int(snapshot["prior_count"])
    current_count = int(snapshot["current_count"])
    size = prior_count + current_count
    utility = [[0.0] * size for _ in range(size)]
    allowed = [[False] * size for _ in range(size)]
    edge = snapshot["edge_utility"]
    compatibility = snapshot["compatibility"]
    for prior in range(prior_count):
        for current in range(current_count):
            utility[prior][current] = float(edge[prior][current])
            allowed[prior][current] = bool(compatibility[prior][current])
        utility[prior][current_count + prior] = float(
            snapshot["prior_null_utility"][prior]
        )
        allowed[prior][current_count + prior] = True
    for current in range(current_count):
        utility[prior_count + current][current] = float(
            snapshot["current_null_utility"][current]
        )
        allowed[prior_count + current][current] = True
    for row in range(prior_count, size):
        for column in range(current_count, size):
            allowed[row][column] = True
    return utility, allowed


def _enumerate_optima(
    utility: list[list[float]], allowed: list[list[bool]]
) -> tuple[float, list[tuple[int, ...]], int]:
    size = len(utility)
    if size == 0:
        return 0.0, [()], 1
    optimum = -math.inf
    optima: list[tuple[int, ...]] = []
    feasible = 0
    for columns in itertools.permutations(range(size)):
        if not all(allowed[row][column] for row, column in enumerate(columns)):
            continue
        feasible += 1
        value = sum(utility[row][column] for row, column in enumerate(columns))
        if value > optimum + 1e-12:
            optimum = value
            optima = [columns]
        elif abs(value - optimum) <= 1e-12:
            optima.append(columns)
    if not feasible:
        raise ValueError("microcase has no feasible augmented assignment")
    return optimum, optima, feasible


def _semantic_transport_from_assignment(
    assignment: tuple[int, ...], prior_count: int, current_count: int
) -> list[list[float]]:
    transport = [[0.0] * (current_count + 1) for _ in range(prior_count + 1)]
    matched_currents: set[int] = set()
    for prior in range(prior_count):
        column = assignment[prior]
        if column < current_count:
            transport[prior][column] = 1.0
            matched_currents.add(column)
        else:
            transport[prior][current_count] = 1.0
    for current in range(current_count):
        if current not in matched_currents:
            transport[prior_count][current] = 1.0
    return transport


def _semantic_lexicographic_minimum(
    assignments: list[tuple[int, ...]], prior_count: int, current_count: int
) -> list[list[float]]:
    candidates = [
        _semantic_transport_from_assignment(item, prior_count, current_count)
        for item in assignments
    ]

    def assignment_key(matrix: list[list[float]]) -> tuple[int, ...]:
        return tuple(matrix[prior].index(1.0) for prior in range(prior_count))

    return min(candidates, key=assignment_key)


def _input_snapshot(
    regions: RegionBatch,
    edge: Tensor,
    death: Tensor,
    birth: Tensor,
    compatibility: Tensor,
) -> dict[str, Any]:
    prior_count = regions.prior_features.shape[1]
    current_count = regions.current_features.shape[1]
    return {
        "prior_count": prior_count,
        "current_count": current_count,
        "prior_valid": regions.prior_valid[0].tolist(),
        "current_valid": regions.current_valid[0].tolist(),
        "prior_anatomy": regions.prior_anatomy[0].tolist(),
        "current_anatomy": regions.current_anatomy[0].tolist(),
        "edge_utility": edge[0].tolist(),
        "prior_null_utility": death[0].tolist(),
        "current_null_utility": birth[0].tolist(),
        "compatibility": compatibility[0].tolist(),
    }


def _matrix_residuals(
    hard: list[list[float]],
    soft: list[list[float]],
    internal_soft: Tensor,
    snapshot: Mapping[str, Any],
    optimum: float,
    optima: list[tuple[int, ...]],
    feasible: int,
) -> dict[str, Any]:
    prior_count = int(snapshot["prior_count"])
    current_count = int(snapshot["current_count"])
    hard_tensor = torch.tensor(hard, dtype=torch.float64)
    soft_tensor = torch.tensor(soft, dtype=torch.float64)
    edge = torch.tensor(snapshot["edge_utility"], dtype=torch.float64).reshape(
        prior_count, current_count
    )
    death = torch.tensor(snapshot["prior_null_utility"], dtype=torch.float64)
    birth = torch.tensor(snapshot["current_null_utility"], dtype=torch.float64)
    selected = float(
        (hard_tensor[:prior_count, :current_count] * edge).sum()
        + (hard_tensor[:prior_count, current_count] * death).sum()
        + (hard_tensor[prior_count, :current_count] * birth).sum()
    )
    hard_prior = hard_tensor[:prior_count].sum(dim=-1)
    hard_current = hard_tensor[:, :current_count].sum(dim=-2)
    soft_real = soft_tensor[:prior_count, :current_count]
    compatibility = torch.tensor(snapshot["compatibility"], dtype=torch.bool).reshape(
        prior_count, current_count
    )
    forbidden_hard = (
        float(hard_tensor[:prior_count, :current_count][~compatibility].sum())
        if compatibility.numel()
        else 0.0
    )
    forbidden_soft = (
        float(soft_real[~compatibility].sum()) if compatibility.numel() else 0.0
    )
    one = torch.ones(internal_soft.shape[0], dtype=internal_soft.dtype)
    lexicographic = _semantic_lexicographic_minimum(optima, prior_count, current_count)
    return {
        "enumerated_feasible_assignments": feasible,
        "optimal_assignment_count": len(optima),
        "exhaustive_optimal_utility": optimum,
        "selected_utility": selected,
        "hard_optimality_gap": optimum - selected,
        "hard_prior_mass_max_residual": (
            float((hard_prior - 1.0).abs().max()) if prior_count else 0.0
        ),
        "hard_current_mass_max_residual": (
            float((hard_current - 1.0).abs().max()) if current_count else 0.0
        ),
        "soft_internal_row_mass_max_residual": (
            float((internal_soft.sum(dim=-1) - one).abs().max())
            if internal_soft.numel()
            else 0.0
        ),
        "soft_internal_column_mass_max_residual": (
            float((internal_soft.sum(dim=-2) - one).abs().max())
            if internal_soft.numel()
            else 0.0
        ),
        "soft_prior_capacity_max_excess": (
            max(float(soft_real.sum(dim=-1).max()) - 1.0, 0.0) if prior_count else 0.0
        ),
        "soft_current_capacity_max_excess": (
            max(float(soft_real.sum(dim=-2).max()) - 1.0, 0.0) if current_count else 0.0
        ),
        "forbidden_hard_mass": forbidden_hard,
        "forbidden_soft_mass": forbidden_soft,
        "lexicographic_tie_selected": hard == lexicographic,
    }


def _completion_counts(
    hard: list[list[float]], prior_count: int, current_count: int
) -> dict[str, Any]:
    persistent = sum(
        int(hard[prior][current] == 1.0)
        for prior in range(prior_count)
        for current in range(current_count)
    )
    death = sum(int(hard[prior][current_count] == 1.0) for prior in range(prior_count))
    birth = sum(
        int(hard[prior_count][current] == 1.0) for current in range(current_count)
    )
    prior_cover = all(sum(hard[prior]) == 1.0 for prior in range(prior_count))
    current_cover = all(
        sum(hard[row][current] for row in range(prior_count + 1)) == 1.0
        for current in range(current_count)
    )
    real_current_counts = [
        sum(int(hard[prior][current] == 1.0) for prior in range(prior_count))
        for current in range(current_count)
    ]
    return {
        "valid_prior_count": prior_count,
        "valid_current_count": current_count,
        "persistent_count": persistent,
        "death_count": death,
        "birth_count": birth,
        "hard_covers_every_prior_once": prior_cover,
        "hard_covers_every_current_once": current_cover,
        "persistent_death_birth_partition_exact": (
            persistent + death == prior_count and persistent + birth == current_count
        ),
        "no_duplicate_real_current": all(count <= 1 for count in real_current_counts),
    }


def _run_case(
    matcher: InvariantPartialOTMatcher, case_id: str, spec: Mapping[str, Any]
) -> dict[str, Any]:
    regions = _region_batch(
        matcher, list(spec["prior_anatomy"]), list(spec["current_anatomy"])
    )
    edge = torch.tensor([spec["edge"]], dtype=torch.float32).reshape(
        1, len(spec["prior_anatomy"]), len(spec["current_anatomy"])
    )
    death = torch.tensor([spec["death"]], dtype=torch.float32)
    birth = torch.tensor([spec["birth"]], dtype=torch.float32)
    compatibility = matcher._compatibility_mask(regions)
    source_before = _input_snapshot(regions, edge, death, birth, compatibility)
    soft_plan = matcher.plan_from_utilities(regions, edge, death, birth, hard=False)
    hard_plan = matcher.plan_from_utilities(regions, edge, death, birth, hard=True)
    source_after = _input_snapshot(regions, edge, death, birth, compatibility)
    soft = soft_plan.transport[0].tolist()
    hard = hard_plan.transport[0].tolist()
    expected = spec["expected"]

    valid_priors = torch.arange(len(spec["prior_anatomy"]))
    valid_currents = torch.arange(len(spec["current_anatomy"]))
    augmented, allowed = matcher._augmented_utility(
        edge, death, birth, compatibility, 0, valid_priors, valid_currents
    )
    internal_soft = (
        matcher._sinkhorn(augmented, allowed) if augmented.numel() else augmented
    )
    snapshot = dict(source_before)
    utility, allowed_list = _augmented_from_snapshot(snapshot)
    optimum, optima, feasible = _enumerate_optima(utility, allowed_list)
    expected_evidence = {
        **snapshot,
        "soft_transport": soft,
        "soft_internal_transport": internal_soft.tolist(),
        "hard_transport": hard,
        "expected_hard_transport": expected,
        "hard_plan_matches_expected": hard == expected,
        "tie_policy": _TIE_POLICY,
    }
    utility_payload = {
        key: snapshot[key]
        for key in (
            "edge_utility",
            "prior_null_utility",
            "current_null_utility",
            "compatibility",
        )
    }
    return {
        "input_sha256_before": canonical_sha256(source_before),
        "input_sha256_after": canonical_sha256(source_after),
        "utility_sha256": canonical_sha256(utility_payload),
        "soft_plan_sha256": canonical_sha256(soft),
        "hard_plan_sha256": canonical_sha256(hard),
        "feasibility_residuals": _matrix_residuals(
            hard, soft, internal_soft, snapshot, optimum, optima, feasible
        ),
        "expected_plan_exact": expected_evidence,
        "completion_counts": _completion_counts(
            hard, len(spec["prior_anatomy"]), len(spec["current_anatomy"])
        ),
        "gradient_audit": _na_gradient_audit(),
    }


def _validate_gradient_audit(value: Mapping[str, Any], *, applicable: bool) -> None:
    _require_exact_keys(value, _GRADIENT_AUDIT_KEYS, "gradient_audit")
    if applicable:
        if value["applicability"] != "APPLICABLE_REGISTERED_STEP0_MATCHER":
            raise ValueError("registered gradient audit applicability mismatch")
        if value["na_reason"] != "":
            raise ValueError("applicable gradient audit must have empty na_reason")
        if value["registered_parameter_names"] != list(_GRADIENT_NAMES):
            raise ValueError("registered gradient parameter names mismatch")
        gradients = value["gradients"]
        if not isinstance(gradients, Mapping):
            raise TypeError("registered gradient gradients must be a mapping")
        _require_exact_keys(gradients, set(_GRADIENT_NAMES), "gradients")
        for name, item in gradients.items():
            if not isinstance(item, Mapping):
                raise TypeError(f"gradient {name} must be a mapping")
            _require_exact_keys(item, _GRADIENT_VALUE_KEYS, f"gradient.{name}")
            if item["finite"] is not math.isfinite(float(item["value"])):
                raise ValueError(f"gradient finite flag mismatch for {name}")
            if item["nonzero"] is not (float(item["value"]) != 0.0):
                raise ValueError(f"gradient nonzero flag mismatch for {name}")
        derived_finite = all(item["finite"] for item in gradients.values())
        derived_nonzero = all(item["nonzero"] for item in gradients.values())
        if value["registered_parameter_names_exact"] is not True:
            raise ValueError("registered gradient parameter-name flag mismatch")
        if value["finite_loss"] is not math.isfinite(float(value["loss"])):
            raise ValueError("registered gradient finite-loss flag mismatch")
        if value["finite_gradients"] is not derived_finite:
            raise ValueError("registered finite-gradients flag mismatch")
        if (
            value["nonzero_expected_gradient_each_trainable_parameter"]
            is not derived_nonzero
        ):
            raise ValueError("registered nonzero-gradient flag mismatch")
        if value["forbidden_input_or_query_gradient"] is not True:
            raise ValueError("forbidden input/query gradient check failed")
        if value["optimizer_owner_exact"] is not True:
            raise ValueError("optimizer-owner check failed")
        return

    if value != _na_gradient_audit():
        raise ValueError("analytic microcase gradient N/A record mismatch")


def _validate_case(case_id: str, case: Mapping[str, Any]) -> None:
    _require_exact_keys(case, _CASE_KEYS, f"microcases.{case_id}")
    plan = case["expected_plan_exact"]
    residuals = case["feasibility_residuals"]
    counts = case["completion_counts"]
    gradient = case["gradient_audit"]
    for name, value, keys in (
        ("expected_plan_exact", plan, _PLAN_KEYS),
        ("feasibility_residuals", residuals, _FEASIBILITY_KEYS),
        ("completion_counts", counts, _COMPLETION_KEYS),
        ("gradient_audit", gradient, _GRADIENT_AUDIT_KEYS),
    ):
        if not isinstance(value, Mapping):
            raise TypeError(f"microcases.{case_id}.{name} must be a mapping")
        _require_exact_keys(value, keys, f"microcases.{case_id}.{name}")

    snapshot = {
        key: plan[key]
        for key in _PLAN_KEYS
        if key
        not in {
            "soft_transport",
            "soft_internal_transport",
            "hard_transport",
            "expected_hard_transport",
            "hard_plan_matches_expected",
            "tie_policy",
        }
    }
    if case["input_sha256_before"] != canonical_sha256(snapshot):
        raise ValueError(f"{case_id} input-before hash mismatch")
    if case["input_sha256_after"] != canonical_sha256(snapshot):
        raise ValueError(f"{case_id} input-after hash mismatch or input mutation")
    utility_payload = {
        key: plan[key]
        for key in (
            "edge_utility",
            "prior_null_utility",
            "current_null_utility",
            "compatibility",
        )
    }
    if case["utility_sha256"] != canonical_sha256(utility_payload):
        raise ValueError(f"{case_id} utility hash mismatch")
    if case["soft_plan_sha256"] != canonical_sha256(plan["soft_transport"]):
        raise ValueError(f"{case_id} soft-plan hash mismatch")
    if case["hard_plan_sha256"] != canonical_sha256(plan["hard_transport"]):
        raise ValueError(f"{case_id} hard-plan hash mismatch")
    if plan["hard_plan_matches_expected"] is not (
        plan["hard_transport"] == plan["expected_hard_transport"]
    ):
        raise ValueError(f"{case_id} expected-plan flag mismatch")
    if plan["hard_plan_matches_expected"] is not True:
        raise ValueError(f"{case_id} hard plan differs from frozen expectation")
    if plan["tie_policy"] != _TIE_POLICY:
        raise ValueError(f"{case_id} tie policy mismatch")

    utility, allowed = _augmented_from_snapshot(plan)
    optimum, optima, feasible = _enumerate_optima(utility, allowed)
    prior_count = int(plan["prior_count"])
    current_count = int(plan["current_count"])
    hard = plan["hard_transport"]
    soft = plan["soft_transport"]
    expected_counts = _completion_counts(hard, prior_count, current_count)
    if counts != expected_counts:
        raise ValueError(f"{case_id} completion counts are not derivable")
    if not all(
        counts[key] is True
        for key in (
            "hard_covers_every_prior_once",
            "hard_covers_every_current_once",
            "persistent_death_birth_partition_exact",
            "no_duplicate_real_current",
        )
    ):
        raise ValueError(f"{case_id} hard completion conservation failed")

    internal_soft = torch.tensor(plan["soft_internal_transport"], dtype=torch.float32)
    derived_residuals = _matrix_residuals(
        hard,
        soft,
        internal_soft,
        plan,
        optimum,
        optima,
        feasible,
    )
    for name, expected in derived_residuals.items():
        observed = residuals[name]
        if isinstance(expected, float):
            if not math.isclose(float(observed), expected, abs_tol=1e-12, rel_tol=0):
                raise ValueError(f"{case_id} {name} is not derivable")
        elif observed != expected:
            raise ValueError(f"{case_id} {name} is not derivable")
    tolerance = 1e-5
    for name in (
        "hard_prior_mass_max_residual",
        "hard_current_mass_max_residual",
        "soft_internal_row_mass_max_residual",
        "soft_internal_column_mass_max_residual",
        "soft_prior_capacity_max_excess",
        "soft_current_capacity_max_excess",
        "forbidden_hard_mass",
        "forbidden_soft_mass",
    ):
        if not 0.0 <= float(residuals[name]) <= tolerance:
            raise ValueError(f"{case_id} feasibility residual {name} exceeds tolerance")
    if residuals["hard_optimality_gap"] != 0.0:
        raise ValueError(f"{case_id} hard plan is not globally optimal")
    if residuals["lexicographic_tie_selected"] is not True:
        raise ValueError(f"{case_id} hard tie resolution is not lexicographic")
    _validate_gradient_audit(gradient, applicable=False)


def validate_r6_structural_audit(report: Mapping[str, Any]) -> None:
    """Validate schema and independently recompute all derivable R6 evidence."""

    if not isinstance(report, Mapping):
        raise TypeError("report must be a mapping")
    _require_exact_keys(report, _TOP_LEVEL_KEYS, "report")
    _require_finite_json(report)
    if report["schema_version"] != R6_STRUCTURAL_AUDIT_SCHEMA_VERSION:
        raise ValueError("unexpected R6 structural-audit schema version")
    required_case_ids = report["required_case_ids"]
    if required_case_ids != list(R6_STRUCTURAL_CASE_IDS):
        raise ValueError("required structural case IDs mismatch")
    if report["required_per_case_evidence"] != list(R6_REQUIRED_PER_CASE_EVIDENCE):
        raise ValueError("required per-case evidence keys mismatch")
    microcases = report["microcases"]
    if not isinstance(microcases, Mapping):
        raise TypeError("report.microcases must be a mapping")
    _require_exact_keys(microcases, set(R6_STRUCTURAL_CASE_IDS), "report.microcases")
    ordered_projection = [
        {"case_id": case_id, "evidence": microcases[case_id]}
        for case_id in required_case_ids
    ]
    expected_projection_sha256 = canonical_sha256(ordered_projection)
    if report["ordered_microcase_projection_sha256"] != expected_projection_sha256:
        raise ValueError("ordered structural microcase projection SHA-256 mismatch")
    # JSON object member order is not semantic.  The registered list is the
    # ordering authority; its ordered projection is committed explicitly.
    for case_id in required_case_ids:
        case = microcases[case_id]
        if not isinstance(case, Mapping):
            raise TypeError(f"microcases.{case_id} must be a mapping")
        _validate_case(case_id, case)
    registered = report["registered_gradient_audit"]
    if not isinstance(registered, Mapping):
        raise TypeError("registered_gradient_audit must be a mapping")
    _validate_gradient_audit(registered, applicable=True)
    if report["passed"] is not True:
        raise ValueError("report.passed must be true")
    expected_hash = canonical_sha256(
        {key: value for key, value in report.items() if key != "audit_sha256"}
    )
    if report["audit_sha256"] != expected_hash:
        raise ValueError("R6 structural-audit SHA-256 mismatch")


def run_r6_structural_audits(
    matcher: InvariantPartialOTMatcher,
) -> dict[str, Any]:
    """Run all eight deterministic R6 structural cases without mutation."""

    if not isinstance(matcher, InvariantPartialOTMatcher):
        raise TypeError("matcher must be an InvariantPartialOTMatcher")
    probe = deepcopy(matcher).to("cpu")
    _fixture(probe)
    registered_gradient_audit = _registered_gradient_audit(probe)
    microcases = {
        case_id: _run_case(probe, case_id, spec)
        for case_id, spec in _case_specs().items()
    }
    report: dict[str, Any] = {
        "schema_version": R6_STRUCTURAL_AUDIT_SCHEMA_VERSION,
        "passed": True,
        "required_case_ids": list(R6_STRUCTURAL_CASE_IDS),
        "required_per_case_evidence": list(R6_REQUIRED_PER_CASE_EVIDENCE),
        "microcases": microcases,
        "ordered_microcase_projection_sha256": canonical_sha256(
            [
                {"case_id": case_id, "evidence": microcases[case_id]}
                for case_id in R6_STRUCTURAL_CASE_IDS
            ]
        ),
        "registered_gradient_audit": registered_gradient_audit,
    }
    report["audit_sha256"] = canonical_sha256(report)
    validate_r6_structural_audit(report)
    return report
