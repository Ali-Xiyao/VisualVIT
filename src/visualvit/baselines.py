from __future__ import annotations

from dataclasses import dataclass
import math

import torch
from torch import Tensor, nn

from .matching import _hungarian_minimize
from .schemas import MatchPlan


@dataclass(frozen=True, slots=True)
class DevelopmentFrozenThreshold:
    """Immutable provenance for a reject threshold selected on development data."""

    value: float
    source_split: str = "development"
    selection_rule: str = "pre-registered development selection"

    def __post_init__(self) -> None:
        if not math.isfinite(self.value):
            raise ValueError("reject threshold must be finite")
        normalized_split = self.source_split.strip().lower().replace("_", "-")
        if not (
            normalized_split.startswith("dev")
            or normalized_split.startswith("validation")
        ):
            raise ValueError(
                "reject threshold provenance must name a development/validation split"
            )
        if not self.selection_rule.strip():
            raise ValueError("selection_rule must be non-empty")


def _validate_contract(
    cost: Tensor,
    support: Tensor,
    prior_marginal: Tensor,
    current_marginal: Tensor,
) -> tuple[Tensor, Tensor]:
    """Validate the shared cost/support/marginal contract.

    Unsupported costs may use arbitrary sentinels (including infinity); supported
    costs and both marginals must be finite.  The returned cost is finite
    everywhere and the returned support excludes zero-mass endpoints.
    """

    if cost.ndim != 3:
        raise ValueError("cost must have shape [B, Rp, Rc]")
    batch, prior_count, current_count = cost.shape
    if batch <= 0:
        raise ValueError("the batch dimension must be positive")
    if not cost.is_floating_point():
        raise TypeError("cost must be floating point")
    if tuple(support.shape) != tuple(cost.shape):
        raise ValueError(
            f"support must have shape {tuple(cost.shape)}, got {tuple(support.shape)}"
        )
    if support.dtype is not torch.bool:
        raise TypeError("support must be bool")
    if tuple(prior_marginal.shape) != (batch, prior_count):
        raise ValueError(
            "prior_marginal must have shape "
            f"{(batch, prior_count)}, got {tuple(prior_marginal.shape)}"
        )
    if tuple(current_marginal.shape) != (batch, current_count):
        raise ValueError(
            "current_marginal must have shape "
            f"{(batch, current_count)}, got {tuple(current_marginal.shape)}"
        )
    for name, value in (
        ("support", support),
        ("prior_marginal", prior_marginal),
        ("current_marginal", current_marginal),
    ):
        if value.device != cost.device:
            raise ValueError(f"{name} and cost must be on the same device")
    for name, value in (
        ("prior_marginal", prior_marginal),
        ("current_marginal", current_marginal),
    ):
        if not value.is_floating_point():
            raise TypeError(f"{name} must be floating point")
        if value.dtype != cost.dtype:
            raise ValueError(f"{name} and cost must share dtype")
        if not bool(torch.isfinite(value).all()):
            raise ValueError(f"{name} contains non-finite values")
        if bool((value < 0).any()):
            raise ValueError(f"{name} contains negative mass")

    supported_cost = cost.masked_select(support)
    if supported_cost.numel() and not bool(torch.isfinite(supported_cost).all()):
        raise ValueError("supported costs must be finite")
    finite_cost = torch.where(support, cost, torch.zeros_like(cost))
    active_support = (
        support
        & (prior_marginal > 0).unsqueeze(-1)
        & (current_marginal > 0).unsqueeze(-2)
    )
    return finite_cost, active_support


def _maximum_or_zero(value: Tensor) -> Tensor:
    return value.max() if value.numel() else value.new_zeros(())


def _augment_with_null_residuals(
    real_transport: Tensor,
    prior_marginal: Tensor,
    current_marginal: Tensor,
) -> Tensor:
    death = (prior_marginal - real_transport.sum(dim=-1)).clamp_min(0.0)
    birth = (current_marginal - real_transport.sum(dim=-2)).clamp_min(0.0)
    upper = torch.cat((real_transport, death.unsqueeze(-1)), dim=-1)
    lower = torch.cat(
        (
            birth.unsqueeze(-2),
            real_transport.new_zeros((real_transport.shape[0], 1, 1)),
        ),
        dim=-1,
    )
    return torch.cat((upper, lower), dim=-2)


def _transport_audit(
    transport: Tensor,
    support: Tensor,
    prior_marginal: Tensor,
    current_marginal: Tensor,
) -> dict[str, Tensor | float | int | str]:
    prior_count = prior_marginal.shape[1]
    current_count = current_marginal.shape[1]
    real = transport[:, :prior_count, :current_count]
    death = transport[:, :prior_count, current_count]
    birth = transport[:, prior_count, :current_count]
    prior_total = transport[:, :prior_count, :].sum(dim=-1)
    current_total = transport[:, :, :current_count].sum(dim=-2)
    expected_death = prior_marginal - real.sum(dim=-1)
    expected_birth = current_marginal - real.sum(dim=-2)
    null_errors = torch.cat(
        (
            (death - expected_death).abs().flatten(),
            (birth - expected_birth).abs().flatten(),
        )
    )
    unsupported_mass = real.masked_select(~support).abs()
    return {
        "min_mass": transport.min().detach(),
        "max_prior_residual": _maximum_or_zero(
            (prior_total - prior_marginal).abs()
        ).detach(),
        "max_current_residual": _maximum_or_zero(
            (current_total - current_marginal).abs()
        ).detach(),
        "max_null_residual": _maximum_or_zero(null_errors).detach(),
        "max_prior_capacity_violation": _maximum_or_zero(
            (real.sum(dim=-1) - prior_marginal).clamp_min(0.0)
        ).detach(),
        "max_current_capacity_violation": _maximum_or_zero(
            (real.sum(dim=-2) - current_marginal).clamp_min(0.0)
        ).detach(),
        "max_support_violation": _maximum_or_zero(unsupported_mass).detach(),
        "dustbin_dustbin": transport[:, prior_count, current_count]
        .abs()
        .max()
        .detach(),
        "matched_mass": real.sum(dim=(-2, -1)).detach(),
    }


def _assert_feasible(
    diagnostics: dict[str, Tensor | float | int | str],
    *,
    tolerance: float,
) -> None:
    if float(diagnostics["min_mass"]) < -tolerance:
        raise RuntimeError("baseline produced negative transport mass")
    for key in (
        "max_prior_residual",
        "max_current_residual",
        "max_null_residual",
        "max_prior_capacity_violation",
        "max_current_capacity_violation",
        "max_support_violation",
        "dustbin_dustbin",
    ):
        if float(diagnostics[key]) > tolerance:
            raise RuntimeError(f"baseline feasibility audit failed: {key}")


class HungarianRejectBaseline(nn.Module):
    """Globally optimal one-to-one matching with a frozen reject threshold.

    Costs strictly below the development-frozen threshold are optional match
    candidates.  The Hungarian solve maximizes their aggregate saving relative
    to rejecting both endpoints.  It never receives an oracle match count.
    """

    def __init__(
        self,
        threshold: DevelopmentFrozenThreshold,
        *,
        feasibility_tolerance: float = 1e-6,
    ) -> None:
        super().__init__()
        if not isinstance(threshold, DevelopmentFrozenThreshold):
            raise TypeError("threshold must be a DevelopmentFrozenThreshold")
        if feasibility_tolerance <= 0 or not math.isfinite(feasibility_tolerance):
            raise ValueError("feasibility_tolerance must be finite and positive")
        self.threshold = threshold
        self.feasibility_tolerance = float(feasibility_tolerance)

    def forward(
        self,
        cost: Tensor,
        support: Tensor,
        prior_marginal: Tensor,
        current_marginal: Tensor,
    ) -> MatchPlan:
        finite_cost, active_support = _validate_contract(
            cost, support, prior_marginal, current_marginal
        )
        for name, marginal in (
            ("prior_marginal", prior_marginal),
            ("current_marginal", current_marginal),
        ):
            is_zero = torch.isclose(marginal, torch.zeros_like(marginal), atol=1e-7)
            is_one = torch.isclose(marginal, torch.ones_like(marginal), atol=1e-7)
            if not bool((is_zero | is_one).all()):
                raise ValueError(f"{name} must be binary for hard Hungarian matching")

        batch, prior_count, current_count = finite_cost.shape
        real_transport = finite_cost.new_zeros((batch, prior_count, current_count))
        cost_cpu = finite_cost.detach().to(device="cpu", dtype=torch.float64)
        support_cpu = active_support.detach().to(device="cpu")
        prior_cpu = (prior_marginal > 0).detach().to(device="cpu")
        current_cpu = (current_marginal > 0).detach().to(device="cpu")

        for batch_index in range(batch):
            valid_priors = [
                index
                for index in range(prior_count)
                if bool(prior_cpu[batch_index, index])
            ]
            valid_currents = [
                index
                for index in range(current_count)
                if bool(current_cpu[batch_index, index])
            ]
            prior_size = len(valid_priors)
            current_size = len(valid_currents)
            assignment_size = prior_size + current_size
            if assignment_size == 0:
                continue

            weights = [
                [0.0 for _ in range(assignment_size)] for _ in range(assignment_size)
            ]
            allowed = [[False] * current_size for _ in range(prior_size)]
            for local_prior, prior_index in enumerate(valid_priors):
                for local_current, current_index in enumerate(valid_currents):
                    saving = self.threshold.value - float(
                        cost_cpu[batch_index, prior_index, current_index]
                    )
                    is_allowed = (
                        bool(support_cpu[batch_index, prior_index, current_index])
                        and saving > 0.0
                    )
                    allowed[local_prior][local_current] = is_allowed
                    weights[local_prior][local_current] = saving if is_allowed else -1.0

            assignment = _hungarian_minimize(
                [[-weight for weight in row] for row in weights]
            )
            for local_prior, column in enumerate(assignment[:prior_size]):
                if column < current_size and allowed[local_prior][column]:
                    real_transport[
                        batch_index,
                        valid_priors[local_prior],
                        valid_currents[column],
                    ] = 1.0

        transport = _augment_with_null_residuals(
            real_transport, prior_marginal, current_marginal
        )
        diagnostics = _transport_audit(
            transport, active_support, prior_marginal, current_marginal
        )
        diagnostics.update(
            {
                "reject_threshold": self.threshold.value,
                "threshold_source_split": self.threshold.source_split,
                "threshold_selection_rule": self.threshold.selection_rule,
                "threshold_comparison": "accept iff supported cost < threshold",
                "rejected_supported_edges": (
                    active_support & (finite_cost >= self.threshold.value)
                )
                .sum()
                .detach(),
            }
        )
        _assert_feasible(diagnostics, tolerance=self.feasibility_tolerance)
        edge_logits = torch.where(
            active_support,
            self.threshold.value - finite_cost,
            torch.zeros_like(finite_cost),
        )
        zeros_prior = torch.zeros_like(prior_marginal)
        zeros_current = torch.zeros_like(current_marginal)
        return MatchPlan(
            transport=transport,
            mode="hungarian_development_frozen_reject",
            edge_logits=edge_logits,
            prior_null_logits=zeros_prior,
            current_null_logits=zeros_current,
            diagnostics=diagnostics,
        )


def _uniform_values(marginal: Tensor) -> Tensor:
    positive = marginal > 0
    return marginal.sum(dim=-1) / positive.sum(dim=-1).clamp_min(1).to(marginal.dtype)


def _maximum_supported_flow(
    support: Tensor,
    prior_marginal: Tensor,
    current_marginal: Tensor,
    batch_index: int,
    *,
    tolerance: float,
) -> float:
    """Compute support-only max flow for one batch without SciPy."""

    prior_count = prior_marginal.shape[1]
    current_count = current_marginal.shape[1]
    source = 0
    prior_start = 1
    current_start = prior_start + prior_count
    sink = current_start + current_count
    node_count = sink + 1
    capacity = [[0.0 for _ in range(node_count)] for _ in range(node_count)]
    prior_cpu = prior_marginal.detach().to(device="cpu", dtype=torch.float64)
    current_cpu = current_marginal.detach().to(device="cpu", dtype=torch.float64)
    support_cpu = support.detach().to(device="cpu")
    total_mass = float(prior_cpu[batch_index].sum())

    for prior_index in range(prior_count):
        capacity[source][prior_start + prior_index] = float(
            prior_cpu[batch_index, prior_index]
        )
        for current_index in range(current_count):
            if bool(support_cpu[batch_index, prior_index, current_index]):
                capacity[prior_start + prior_index][current_start + current_index] = (
                    total_mass
                )
    for current_index in range(current_count):
        capacity[current_start + current_index][sink] = float(
            current_cpu[batch_index, current_index]
        )

    residual = [row.copy() for row in capacity]
    flow = 0.0
    while True:
        parent = [-1] * node_count
        parent[source] = source
        queue = [source]
        queue_index = 0
        while queue_index < len(queue) and parent[sink] == -1:
            node = queue[queue_index]
            queue_index += 1
            for neighbor in range(node_count):
                if parent[neighbor] == -1 and residual[node][neighbor] > tolerance:
                    parent[neighbor] = node
                    queue.append(neighbor)
                    if neighbor == sink:
                        break
        if parent[sink] == -1:
            break
        increment = math.inf
        node = sink
        while node != source:
            previous = parent[node]
            increment = min(increment, residual[previous][node])
            node = previous
        node = sink
        while node != source:
            previous = parent[node]
            residual[previous][node] -= increment
            residual[node][previous] += increment
            node = previous
        flow += increment
    return flow


def _validate_strict_balanced_contract(
    support: Tensor,
    prior_marginal: Tensor,
    current_marginal: Tensor,
    *,
    tolerance: float,
) -> tuple[Tensor, Tensor, Tensor]:
    """Require uniform, equal-total marginals and a feasible no-null support."""

    prior_total = prior_marginal.sum(dim=-1)
    current_total = current_marginal.sum(dim=-1)
    if not bool(torch.allclose(prior_total, current_total, atol=tolerance, rtol=0)):
        raise ValueError(
            "balanced Sinkhorn no-null control requires equal prior/current total mass"
        )

    prior_uniform = _uniform_values(prior_marginal)
    current_uniform = _uniform_values(current_marginal)
    prior_deviation = torch.where(
        prior_marginal > 0,
        (prior_marginal - prior_uniform.unsqueeze(-1)).abs(),
        torch.zeros_like(prior_marginal),
    )
    current_deviation = torch.where(
        current_marginal > 0,
        (current_marginal - current_uniform.unsqueeze(-1)).abs(),
        torch.zeros_like(current_marginal),
    )
    if float(_maximum_or_zero(prior_deviation).detach()) > tolerance:
        raise ValueError("prior_marginal must be uniform over positive endpoints")
    if float(_maximum_or_zero(current_deviation).detach()) > tolerance:
        raise ValueError("current_marginal must be uniform over positive endpoints")

    for batch_index in range(support.shape[0]):
        total_mass = float(prior_total[batch_index].detach())
        if total_mass <= tolerance:
            continue
        supported_flow = _maximum_supported_flow(
            support,
            prior_marginal,
            current_marginal,
            batch_index,
            tolerance=tolerance,
        )
        if total_mass - supported_flow > tolerance:
            raise ValueError(
                "support cannot realize all balanced marginal mass without null cells"
            )
    return prior_total, prior_uniform, current_uniform


class BalancedSinkhornBaseline(nn.Module):
    """Strict masked balanced OT control with uniform marginals and no null mass.

    The caller supplies explicit uniform marginals.  Their batch totals must be
    equal and the support must admit a complete flow.  Infeasible inputs fail
    closed rather than borrowing CAPES-CI birth/death semantics.
    """

    def __init__(
        self,
        *,
        epsilon: float = 0.1,
        iterations: int = 128,
        convergence_tolerance: float = 1e-6,
        feasibility_tolerance: float = 1e-6,
    ) -> None:
        super().__init__()
        if epsilon <= 0 or not math.isfinite(epsilon):
            raise ValueError("epsilon must be finite and positive")
        if iterations <= 0:
            raise ValueError("iterations must be positive")
        if convergence_tolerance <= 0 or not math.isfinite(convergence_tolerance):
            raise ValueError("convergence_tolerance must be finite and positive")
        if feasibility_tolerance <= 0 or not math.isfinite(feasibility_tolerance):
            raise ValueError("feasibility_tolerance must be finite and positive")
        self.epsilon = float(epsilon)
        self.iterations = int(iterations)
        self.convergence_tolerance = float(convergence_tolerance)
        self.feasibility_tolerance = float(feasibility_tolerance)

    def forward(
        self,
        cost: Tensor,
        support: Tensor,
        prior_marginal: Tensor,
        current_marginal: Tensor,
    ) -> MatchPlan:
        finite_cost, active_support = _validate_contract(
            cost, support, prior_marginal, current_marginal
        )
        balanced_total, prior_uniform, current_uniform = (
            _validate_strict_balanced_contract(
                active_support,
                prior_marginal,
                current_marginal,
                tolerance=self.feasibility_tolerance,
            )
        )
        sinkhorn_support = active_support

        log_kernel = torch.where(
            sinkhorn_support,
            -finite_cost / self.epsilon,
            torch.full_like(finite_cost, -torch.inf),
        )
        log_u = torch.zeros_like(prior_marginal)
        log_v = torch.zeros_like(current_marginal)
        active_prior = prior_marginal > 0
        active_current = current_marginal > 0
        tiny = torch.finfo(finite_cost.dtype).tiny
        log_target_prior = prior_marginal.clamp_min(tiny).log()
        log_target_current = current_marginal.clamp_min(tiny).log()

        for _ in range(self.iterations):
            row_normalizer = torch.logsumexp(log_kernel + log_v.unsqueeze(-2), dim=-1)
            row_normalizer = torch.where(
                active_prior, row_normalizer, torch.zeros_like(row_normalizer)
            )
            log_u = torch.where(
                active_prior,
                log_target_prior - row_normalizer,
                torch.zeros_like(log_u),
            )
            column_normalizer = torch.logsumexp(
                log_kernel + log_u.unsqueeze(-1), dim=-2
            )
            column_normalizer = torch.where(
                active_current,
                column_normalizer,
                torch.zeros_like(column_normalizer),
            )
            log_v = torch.where(
                active_current,
                log_target_current - column_normalizer,
                torch.zeros_like(log_v),
            )

        real_transport = torch.where(
            sinkhorn_support,
            torch.exp(log_kernel + log_u.unsqueeze(-1) + log_v.unsqueeze(-2)),
            torch.zeros_like(finite_cost),
        )
        balanced_prior_residual = _maximum_or_zero(
            (real_transport.sum(dim=-1) - prior_marginal).abs()
        )
        balanced_current_residual = _maximum_or_zero(
            (real_transport.sum(dim=-2) - current_marginal).abs()
        )
        if (
            float(balanced_prior_residual.detach()) > self.convergence_tolerance
            or float(balanced_current_residual.detach()) > self.convergence_tolerance
        ):
            raise RuntimeError(
                "balanced Sinkhorn did not converge for the supplied support/marginals"
            )

        batch, prior_count, current_count = finite_cost.shape
        upper = torch.cat(
            (real_transport, real_transport.new_zeros((batch, prior_count, 1))),
            dim=-1,
        )
        lower = real_transport.new_zeros((batch, 1, current_count + 1))
        transport = torch.cat((upper, lower), dim=-2)
        diagnostics = _transport_audit(
            transport, active_support, prior_marginal, current_marginal
        )
        diagnostics.update(
            {
                "iterations": self.iterations,
                "epsilon": self.epsilon,
                "max_balanced_prior_residual": balanced_prior_residual.detach(),
                "max_balanced_current_residual": balanced_current_residual.detach(),
                "balanced_total_mass": balanced_total.detach(),
                "prior_uniform_mass": prior_uniform.detach(),
                "current_uniform_mass": current_uniform.detach(),
                "marginal_convention": (
                    "caller-supplied uniform positive marginals; equal batch total; "
                    "no internal renormalization"
                ),
                "null_mass_policy": "forbidden; birth/death cells exactly zero",
                "null_mass": transport.new_zeros(()).detach(),
            }
        )
        _assert_feasible(diagnostics, tolerance=self.feasibility_tolerance)
        edge_logits = torch.where(
            active_support, -finite_cost, torch.zeros_like(finite_cost)
        )
        return MatchPlan(
            transport=transport,
            mode="balanced_sinkhorn",
            edge_logits=edge_logits,
            prior_null_logits=torch.zeros_like(prior_marginal),
            current_null_logits=torch.zeros_like(current_marginal),
            diagnostics=diagnostics,
        )


# Concise aliases for experiment-table configuration files.
HungarianWithReject = HungarianRejectBaseline
BalancedSinkhorn = BalancedSinkhornBaseline
