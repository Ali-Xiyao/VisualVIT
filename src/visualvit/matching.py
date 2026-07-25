from __future__ import annotations

from collections import defaultdict
import math
from typing import Sequence

import torch
from torch import Tensor, nn
import torch.nn.functional as F

from .schemas import MatchPlan, RegionBatch


def _hungarian_minimize(cost: Sequence[Sequence[float]]) -> list[int]:
    """Return the minimum-cost column for every row of a square matrix.

    This is the shortest-augmenting-path Hungarian algorithm.  Keeping the
    implementation here avoids making inference hardening depend on SciPy on
    deployment hosts.  Ordered scans make its choice deterministic when costs
    tie.
    """

    size = len(cost)
    if size == 0:
        return []
    if any(len(row) != size for row in cost):
        raise ValueError("Hungarian cost matrix must be square")

    row_potential = [0.0] * (size + 1)
    column_potential = [0.0] * (size + 1)
    matched_row = [0] * (size + 1)
    predecessor = [0] * (size + 1)

    for row in range(1, size + 1):
        matched_row[0] = row
        current_column = 0
        minimum = [math.inf] * (size + 1)
        used = [False] * (size + 1)
        while True:
            used[current_column] = True
            current_row = matched_row[current_column]
            delta = math.inf
            next_column = 0
            for column in range(1, size + 1):
                if used[column]:
                    continue
                reduced_cost = (
                    float(cost[current_row - 1][column - 1])
                    - row_potential[current_row]
                    - column_potential[column]
                )
                if reduced_cost < minimum[column]:
                    minimum[column] = reduced_cost
                    predecessor[column] = current_column
                if minimum[column] < delta:
                    delta = minimum[column]
                    next_column = column

            if not math.isfinite(delta):
                raise ValueError("assignment matrix has no finite solution")
            for column in range(size + 1):
                if used[column]:
                    row_potential[matched_row[column]] += delta
                    column_potential[column] -= delta
                else:
                    minimum[column] -= delta
            current_column = next_column
            if matched_row[current_column] == 0:
                break

        while True:
            previous_column = predecessor[current_column]
            matched_row[current_column] = matched_row[previous_column]
            current_column = previous_column
            if current_column == 0:
                break

    assignment = [-1] * size
    for column in range(1, size + 1):
        if matched_row[column] != 0:
            assignment[matched_row[column] - 1] = column - 1
    return assignment


def oracle_plan_from_entity_ids(regions: RegionBatch) -> MatchPlan:
    """Construct exact persistent/death/birth assignments from entity ids."""

    regions.validate()
    b, rp, _ = regions.prior_features.shape
    rc = regions.current_features.shape[1]
    transport = torch.zeros(
        b,
        rp + 1,
        rc + 1,
        dtype=regions.prior_features.dtype,
        device=regions.prior_features.device,
    )
    for batch_index in range(b):
        matched_current: set[int] = set()
        for prior_index in range(rp):
            if not bool(regions.prior_valid[batch_index, prior_index]):
                continue
            entity_id = int(regions.prior_entity_ids[batch_index, prior_index])
            candidates = [
                j
                for j in range(rc)
                if bool(regions.current_valid[batch_index, j])
                and int(regions.current_entity_ids[batch_index, j]) == entity_id
            ]
            if len(candidates) > 1:
                raise ValueError(f"duplicate current entity id {entity_id}")
            if candidates:
                current_index = candidates[0]
                if current_index in matched_current:
                    raise ValueError(
                        f"current region {current_index} matched more than once"
                    )
                transport[batch_index, prior_index, current_index] = 1.0
                matched_current.add(current_index)
            else:
                transport[batch_index, prior_index, rc] = 1.0

        for current_index in range(rc):
            if bool(regions.current_valid[batch_index, current_index]) and (
                current_index not in matched_current
            ):
                transport[batch_index, rp, current_index] = 1.0

    plan = MatchPlan(transport=transport, mode="oracle")
    plan.validate(regions)
    return plan


def _derangement(length: int, generator: torch.Generator) -> list[int]:
    if length < 2:
        return list(range(length))
    if length == 2:
        return [1, 0]
    base = torch.arange(length)
    for _ in range(128):
        candidate = torch.randperm(length, generator=generator)
        if bool((candidate != base).all()):
            return candidate.tolist()
    return torch.roll(base, shifts=1).tolist()


def anatomy_compatible_derangement(
    regions: RegionBatch,
    oracle: MatchPlan,
    seed: int,
    require_all_persistent_changed: bool = True,
) -> MatchPlan:
    """Derange only real-real oracle edges within anatomy groups.

    Birth/death edges and all source features remain unchanged.
    """

    oracle.validate(regions)
    b, rp, _ = regions.prior_features.shape
    rc = regions.current_features.shape[1]
    transport = oracle.transport.clone()
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)

    for batch_index in range(b):
        groups: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for prior_index in range(rp):
            current_hits = torch.nonzero(
                oracle.transport[batch_index, prior_index, :rc] > 0.5,
                as_tuple=False,
            ).flatten()
            if len(current_hits) == 1:
                current_index = int(current_hits.item())
                prior_anatomy = int(regions.prior_anatomy[batch_index, prior_index])
                current_anatomy = int(
                    regions.current_anatomy[batch_index, current_index]
                )
                if prior_anatomy != current_anatomy:
                    raise ValueError("oracle persistent match crosses anatomy groups")
                groups[prior_anatomy].append((prior_index, current_index))

        for anatomy, pairs in groups.items():
            if len(pairs) < 2:
                if require_all_persistent_changed:
                    raise ValueError(
                        f"anatomy group {anatomy} has only {len(pairs)} persistent pair; "
                        "a full derangement is impossible"
                    )
                continue
            permutation = _derangement(len(pairs), generator)
            original_currents = [current for _, current in pairs]
            for prior_index, _ in pairs:
                transport[batch_index, prior_index, :rc] = 0.0
            for pair_index, (prior_index, _) in enumerate(pairs):
                new_current = original_currents[permutation[pair_index]]
                transport[batch_index, prior_index, new_current] = 1.0

    plan = MatchPlan(transport=transport, mode=f"deranged_seed_{seed}")
    plan.validate(regions)
    return plan


class ProjectedCosineMatcher(nn.Module):
    """Small supervised projection used only for the synthetic qualification pilot."""

    def __init__(
        self,
        feature_dim: int,
        projection_dim: int = 16,
        temperature: float = 0.10,
    ) -> None:
        super().__init__()
        self.projection = nn.Linear(feature_dim, projection_dim, bias=False)
        self.dustbin_logit = nn.Parameter(torch.tensor(0.0))
        self.temperature = temperature

    def row_logits(self, regions: RegionBatch) -> Tensor:
        prior = F.normalize(self.projection(regions.prior_features), dim=-1)
        current = F.normalize(self.projection(regions.current_features), dim=-1)
        real_logits = torch.einsum("brd,bsd->brs", prior, current) / self.temperature
        real_logits = real_logits.masked_fill(
            ~regions.current_valid[:, None, :], torch.finfo(real_logits.dtype).min
        )
        dustbin = self.dustbin_logit.expand(
            real_logits.shape[0], real_logits.shape[1], 1
        )
        logits = torch.cat([real_logits, dustbin], dim=-1)
        return logits.masked_fill(
            ~regions.prior_valid[:, :, None], torch.finfo(logits.dtype).min
        )

    @staticmethod
    def row_targets(oracle: MatchPlan, regions: RegionBatch) -> Tensor:
        b, rp, _ = regions.prior_features.shape
        targets = torch.full(
            (b, rp), -100, dtype=torch.long, device=oracle.transport.device
        )
        for batch_index in range(b):
            for prior_index in range(rp):
                if not bool(regions.prior_valid[batch_index, prior_index]):
                    continue
                hits = torch.nonzero(
                    oracle.transport[batch_index, prior_index] > 0.5,
                    as_tuple=False,
                ).flatten()
                if len(hits) != 1:
                    raise ValueError("oracle prior row must have one assignment")
                targets[batch_index, prior_index] = int(hits.item())
        return targets

    def hard_plan(
        self,
        regions: RegionBatch,
        match_count: int | Tensor | None = None,
    ) -> MatchPlan:
        """Make a unique hard partial plan from projected similarity.

        The optional match_count is an explicit synthetic qualification oracle.
        Formal experiments must replace it with a preregistered null estimator.
        """

        logits = self.row_logits(regions).detach()
        b, rp, width = logits.shape
        rc = width - 1
        transport = torch.zeros(
            b,
            rp + 1,
            rc + 1,
            dtype=regions.prior_features.dtype,
            device=regions.prior_features.device,
        )

        for batch_index in range(b):
            valid_priors = [
                i for i in range(rp) if bool(regions.prior_valid[batch_index, i])
            ]
            valid_currents = [
                j for j in range(rc) if bool(regions.current_valid[batch_index, j])
            ]
            candidates = sorted(
                (
                    (float(logits[batch_index, i, j]), i, j)
                    for i in valid_priors
                    for j in valid_currents
                ),
                reverse=True,
            )
            if match_count is None:
                target_matches = min(len(valid_priors), len(valid_currents))
            elif isinstance(match_count, Tensor):
                target_matches = int(match_count[batch_index].item())
            else:
                target_matches = int(match_count)

            used_prior: set[int] = set()
            used_current: set[int] = set()
            for _, prior_index, current_index in candidates:
                if len(used_prior) >= target_matches:
                    break
                if prior_index in used_prior or current_index in used_current:
                    continue
                used_prior.add(prior_index)
                used_current.add(current_index)
                transport[batch_index, prior_index, current_index] = 1.0

            for prior_index in valid_priors:
                if prior_index not in used_prior:
                    transport[batch_index, prior_index, rc] = 1.0
            for current_index in valid_currents:
                if current_index not in used_current:
                    transport[batch_index, rp, current_index] = 1.0

        plan = MatchPlan(transport=transport, mode="learned_projection_proxy")
        plan.validate(regions)
        return plan


class NullAwareMatchGraph(nn.Module):
    """Learned two-sided-null matcher with soft and exact hard plans.

    Only region features, validity masks and anatomy groups enter this module.
    Gold entity IDs and oracle cardinalities are deliberately absent from its
    API.  The learned utilities are an edge utility, a prior-side death
    utility and a current-side birth utility.
    """

    def __init__(
        self,
        feature_dim: int,
        hidden_dim: int = 32,
        temperature: float = 0.20,
        projection_iterations: int = 20,
        feasibility_tolerance: float = 1e-6,
        anatomy_constrained: bool = True,
    ) -> None:
        super().__init__()
        if feature_dim <= 0 or hidden_dim <= 0:
            raise ValueError("feature_dim and hidden_dim must be positive")
        if temperature <= 0 or not math.isfinite(temperature):
            raise ValueError("temperature must be finite and positive")
        if projection_iterations <= 0:
            raise ValueError("projection_iterations must be positive")
        if feasibility_tolerance <= 0 or not math.isfinite(feasibility_tolerance):
            raise ValueError("feasibility_tolerance must be finite and positive")

        self.feature_dim = int(feature_dim)
        self.hidden_dim = int(hidden_dim)
        self.temperature = float(temperature)
        self.projection_iterations = int(projection_iterations)
        self.feasibility_tolerance = float(feasibility_tolerance)
        self.anatomy_constrained = bool(anatomy_constrained)

        self.prior_projection = nn.Linear(feature_dim, hidden_dim, bias=False)
        self.current_projection = nn.Linear(feature_dim, hidden_dim, bias=False)
        self.prior_null_head = nn.Linear(feature_dim, 1)
        self.current_null_head = nn.Linear(feature_dim, 1)

    def compute_utilities(self, regions: RegionBatch) -> tuple[Tensor, Tensor, Tensor]:
        """Emit real-edge, death and birth utilities without oracle inputs."""

        regions.validate()
        if regions.prior_features.shape[-1] != self.feature_dim:
            raise ValueError(
                f"expected feature dimension {self.feature_dim}, "
                f"got {regions.prior_features.shape[-1]}"
            )
        prior = self.prior_projection(regions.prior_features)
        current = self.current_projection(regions.current_features)
        edge_logits = torch.einsum("brh,bsh->brs", prior, current) / math.sqrt(
            self.hidden_dim
        )
        prior_null_logits = self.prior_null_head(regions.prior_features).squeeze(-1)
        current_null_logits = self.current_null_head(regions.current_features).squeeze(
            -1
        )
        return edge_logits, prior_null_logits, current_null_logits

    # A concise alias is useful to callers that log the three utility tensors.
    utilities = compute_utilities

    def _compatibility_mask(self, regions: RegionBatch) -> Tensor:
        mask = regions.prior_valid[:, :, None] & regions.current_valid[:, None, :]
        if self.anatomy_constrained:
            mask = mask & (
                regions.prior_anatomy[:, :, None] == regions.current_anatomy[:, None, :]
            )
        return mask

    @staticmethod
    def _validate_utilities(
        regions: RegionBatch,
        edge_logits: Tensor,
        prior_null_logits: Tensor,
        current_null_logits: Tensor,
    ) -> None:
        regions.validate()
        batch, prior_count, _ = regions.prior_features.shape
        current_count = regions.current_features.shape[1]
        expected = (
            ("edge_logits", edge_logits, (batch, prior_count, current_count)),
            ("prior_null_logits", prior_null_logits, (batch, prior_count)),
            ("current_null_logits", current_null_logits, (batch, current_count)),
        )
        for name, value, shape in expected:
            if tuple(value.shape) != shape:
                raise ValueError(
                    f"{name} must have shape {shape}, got {tuple(value.shape)}"
                )
            if not value.is_floating_point():
                raise TypeError(f"{name} must be floating point")
            if value.device != edge_logits.device or value.dtype != edge_logits.dtype:
                raise ValueError("all utility tensors must share device and dtype")
            if not torch.isfinite(value).all():
                raise ValueError(f"{name} contains non-finite values")
        if edge_logits.device != regions.prior_features.device:
            raise ValueError("utilities and region features must be on the same device")

    @staticmethod
    def _augment_transport(
        real_transport: Tensor,
        prior_mass: Tensor,
        current_mass: Tensor,
    ) -> Tensor:
        death = (prior_mass - real_transport.sum(dim=-1)).clamp_min(0.0)
        birth = (current_mass - real_transport.sum(dim=-2)).clamp_min(0.0)
        upper = torch.cat((real_transport, death.unsqueeze(-1)), dim=-1)
        lower = torch.cat(
            (
                birth.unsqueeze(-2),
                real_transport.new_zeros((real_transport.shape[0], 1, 1)),
            ),
            dim=-1,
        )
        return torch.cat((upper, lower), dim=-2)

    def _soft_transport(
        self,
        relative_benefit: Tensor,
        compatibility: Tensor,
        prior_mass: Tensor,
        current_mass: Tensor,
    ) -> Tensor:
        # Sigmoid converts relative benefit to finite-temperature match mass.
        # Alternating down-scalings project onto row and column capacities;
        # neither operation can invalidate the capacity projected before it.
        real_transport = torch.sigmoid(relative_benefit / self.temperature)
        real_transport = real_transport * compatibility.to(real_transport.dtype)
        tiny = torch.finfo(real_transport.dtype).tiny
        for _ in range(self.projection_iterations):
            row_sum = real_transport.sum(dim=-1)
            row_scale = torch.where(
                row_sum > prior_mass,
                prior_mass / row_sum.clamp_min(tiny),
                torch.ones_like(row_sum),
            )
            real_transport = real_transport * row_scale.unsqueeze(-1)

            column_sum = real_transport.sum(dim=-2)
            column_scale = torch.where(
                column_sum > current_mass,
                current_mass / column_sum.clamp_min(tiny),
                torch.ones_like(column_sum),
            )
            real_transport = real_transport * column_scale.unsqueeze(-2)

        return self._augment_transport(real_transport, prior_mass, current_mass)

    def _hard_transport(
        self,
        relative_benefit: Tensor,
        compatibility: Tensor,
        prior_mass: Tensor,
        current_mass: Tensor,
    ) -> Tensor:
        batch, prior_count, current_count = relative_benefit.shape
        real_transport = relative_benefit.new_zeros((batch, prior_count, current_count))

        # Solving on detached scalar utilities is intentional: hardening is an
        # inference/audit operation.  The returned logits still retain their
        # graph, while the discrete assignment does not claim a gradient.
        benefits_cpu = relative_benefit.detach().to(device="cpu", dtype=torch.float64)
        compatible_cpu = compatibility.detach().to(device="cpu")
        prior_valid_cpu = (prior_mass > 0).detach().to(device="cpu")
        current_valid_cpu = (current_mass > 0).detach().to(device="cpu")

        for batch_index in range(batch):
            valid_priors = [
                index
                for index in range(prior_count)
                if bool(prior_valid_cpu[batch_index, index])
            ]
            valid_currents = [
                index
                for index in range(current_count)
                if bool(current_valid_cpu[batch_index, index])
            ]
            prior_size = len(valid_priors)
            current_size = len(valid_currents)
            assignment_size = prior_size + current_size
            if assignment_size == 0:
                continue

            # The augmented matrix always has a complete zero-weight dummy
            # assignment, so any negative sentinel is safely forbidden.
            forbidden = -1.0
            weights = [
                [0.0 for _ in range(assignment_size)] for _ in range(assignment_size)
            ]
            allowed = [[False] * current_size for _ in range(prior_size)]
            for local_prior, prior_index in enumerate(valid_priors):
                for local_current, current_index in enumerate(valid_currents):
                    benefit = float(
                        benefits_cpu[batch_index, prior_index, current_index]
                    )
                    is_allowed = (
                        bool(compatible_cpu[batch_index, prior_index, current_index])
                        and benefit > 0.0
                    )
                    allowed[local_prior][local_current] = is_allowed
                    weights[local_prior][local_current] = (
                        benefit if is_allowed else forbidden
                    )

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

        return self._augment_transport(real_transport, prior_mass, current_mass)

    @staticmethod
    def _objective(
        transport: Tensor,
        edge_logits: Tensor,
        prior_null_logits: Tensor,
        current_null_logits: Tensor,
    ) -> Tensor:
        prior_count = edge_logits.shape[1]
        current_count = edge_logits.shape[2]
        real = transport[:, :prior_count, :current_count]
        death = transport[:, :prior_count, current_count]
        birth = transport[:, prior_count, :current_count]
        return (
            (real * edge_logits).sum(dim=(-2, -1))
            + (death * prior_null_logits).sum(dim=-1)
            + (birth * current_null_logits).sum(dim=-1)
        )

    @staticmethod
    def _maximum_or_zero(value: Tensor) -> Tensor:
        return value.max() if value.numel() else value.new_zeros(())

    def _diagnostics(
        self,
        selected_transport: Tensor,
        soft_transport: Tensor,
        hard_transport: Tensor,
        edge_logits: Tensor,
        prior_null_logits: Tensor,
        current_null_logits: Tensor,
        prior_mass: Tensor,
        current_mass: Tensor,
    ) -> dict[str, Tensor | float | int | str]:
        prior_count = edge_logits.shape[1]
        current_count = edge_logits.shape[2]
        real = selected_transport[:, :prior_count, :current_count]
        selected_prior_total = selected_transport[:, :prior_count, :].sum(dim=-1)
        selected_current_total = selected_transport[:, :, :current_count].sum(dim=-2)
        prior_residual = torch.maximum(
            (selected_prior_total - prior_mass).abs(),
            (real.sum(dim=-1) - prior_mass).clamp_min(0.0),
        )
        current_residual = torch.maximum(
            (selected_current_total - current_mass).abs(),
            (real.sum(dim=-2) - current_mass).clamp_min(0.0),
        )
        objective_soft = self._objective(
            soft_transport,
            edge_logits,
            prior_null_logits,
            current_null_logits,
        )
        objective_hard = self._objective(
            hard_transport,
            edge_logits,
            prior_null_logits,
            current_null_logits,
        )
        return {
            "min_mass": selected_transport.min().detach(),
            "max_prior_residual": self._maximum_or_zero(prior_residual).detach(),
            "max_current_residual": self._maximum_or_zero(current_residual).detach(),
            "dustbin_dustbin": selected_transport[:, prior_count, current_count]
            .abs()
            .max()
            .detach(),
            "iterations": self.projection_iterations,
            "temperature": self.temperature,
            "objective_soft": objective_soft.detach(),
            "objective_hard": objective_hard.detach(),
            "approximation_gap": (objective_hard - objective_soft).detach(),
            "objective": ("sum(P*u_edge) + sum(death*u_death) + sum(birth*u_birth)"),
        }

    def plan_from_utilities(
        self,
        regions: RegionBatch,
        edge_logits: Tensor,
        prior_null_logits: Tensor,
        current_null_logits: Tensor,
        *,
        hard: bool = False,
    ) -> MatchPlan:
        """Build a soft or globally optimal hard plan from explicit utilities."""

        self._validate_utilities(
            regions, edge_logits, prior_null_logits, current_null_logits
        )
        prior_mass = regions.prior_valid.to(dtype=edge_logits.dtype)
        current_mass = regions.current_valid.to(dtype=edge_logits.dtype)
        compatibility = self._compatibility_mask(regions)
        relative_benefit = (
            edge_logits
            - prior_null_logits.unsqueeze(-1)
            - current_null_logits.unsqueeze(-2)
        )
        soft_transport = self._soft_transport(
            relative_benefit, compatibility, prior_mass, current_mass
        )
        hard_transport = self._hard_transport(
            relative_benefit, compatibility, prior_mass, current_mass
        )
        selected_transport = hard_transport if hard else soft_transport
        diagnostics = self._diagnostics(
            selected_transport,
            soft_transport,
            hard_transport,
            edge_logits,
            prior_null_logits,
            current_null_logits,
            prior_mass,
            current_mass,
        )
        plan = MatchPlan(
            transport=selected_transport,
            mode="null_aware_hard" if hard else "null_aware_soft",
            edge_logits=edge_logits,
            prior_null_logits=prior_null_logits,
            current_null_logits=current_null_logits,
            diagnostics=diagnostics,
        )
        if hard:
            plan.validate_hard(regions, atol=self.feasibility_tolerance)
        else:
            plan.validate(regions, atol=self.feasibility_tolerance)
        return plan

    def soft_plan(self, regions: RegionBatch) -> MatchPlan:
        utilities = self.compute_utilities(regions)
        return self.plan_from_utilities(regions, *utilities, hard=False)

    def hard_plan(self, regions: RegionBatch) -> MatchPlan:
        utilities = self.compute_utilities(regions)
        return self.plan_from_utilities(regions, *utilities, hard=True)

    def forward(self, regions: RegionBatch, *, hard: bool = False) -> MatchPlan:
        return self.hard_plan(regions) if hard else self.soft_plan(regions)


class InvariantPartialOTMatcher(nn.Module):
    """Query-independent partial OT on a sanitized identity subspace.

    The scorer uses only explicitly declared identity views (the default is
    ``features[..., identity_start:]``).  Per-view cosine similarities are
    combined by non-negative weights that sum to one.  A bounded monotone
    residual cannot reverse the resulting cosine ordering, and independent
    shared orthogonal changes of view coordinates cannot affect the plan.
    Scalar death and birth utilities supply the two null sides without
    consulting state, query, gold identity, or match cardinality.

    Soft plans optimize an entropy-regularized *global* augmented assignment by
    log-domain Sinkhorn.  Hard plans optimize the unregularized assignment by
    the Hungarian algorithm.  Both consume the same augmented utilities and
    support; they do not optimize the same objective.  The augmentation
    contains real-real edges, one private death edge per prior endpoint, one
    private birth edge per current endpoint, and dummy-dummy completion edges.
    """

    def __init__(
        self,
        feature_dim: int,
        *,
        identity_start: int = 2,
        identity_views: Sequence[tuple[int, int]] | None = None,
        residual_cap: float = 0.02,
        null_utility_cap: float = 0.10,
        temperature: float = 0.05,
        sinkhorn_iterations: int = 256,
        feasibility_tolerance: float = 1e-5,
        anatomy_constrained: bool = True,
    ) -> None:
        super().__init__()
        if feature_dim <= 0:
            raise ValueError("feature_dim must be positive")
        if identity_start < 2 or identity_start >= feature_dim:
            raise ValueError(
                "identity_start must exclude the first two query/state channels"
            )
        if identity_views is None:
            identity_views = ((identity_start, feature_dim),)
        identity_views = tuple((int(start), int(end)) for start, end in identity_views)
        if not identity_views:
            raise ValueError("identity_views must contain at least one view")
        occupied: set[int] = set()
        for start, end in identity_views:
            if start < identity_start or start >= end or end > feature_dim:
                raise ValueError(
                    "each identity view must be a non-empty sanitized slice"
                )
            indices = set(range(start, end))
            if occupied & indices:
                raise ValueError("identity views must not overlap")
            occupied.update(indices)
        if not 0 <= residual_cap < 1:
            raise ValueError("residual_cap must be in [0, 1)")
        if not math.isfinite(null_utility_cap) or not 0 < null_utility_cap < 1:
            raise ValueError("null_utility_cap must be finite and in (0, 1)")
        if temperature <= 0 or not math.isfinite(temperature):
            raise ValueError("temperature must be finite and positive")
        if sinkhorn_iterations <= 0:
            raise ValueError("sinkhorn_iterations must be positive")
        if feasibility_tolerance <= 0 or not math.isfinite(feasibility_tolerance):
            raise ValueError("feasibility_tolerance must be finite and positive")

        self.feature_dim = int(feature_dim)
        self.identity_start = int(identity_start)
        self.identity_views = identity_views
        self.residual_cap = float(residual_cap)
        self.null_utility_cap = float(null_utility_cap)
        self.temperature = float(temperature)
        self.sinkhorn_iterations = int(sinkhorn_iterations)
        self.feasibility_tolerance = float(feasibility_tolerance)
        self.anatomy_constrained = bool(anatomy_constrained)

        # The edge residual is initially zero, making the registered
        # initialization the transparent cosine matcher rather than a random
        # learned scorer.  Softmax keeps the view weights on the simplex.
        self.residual_coefficient = nn.Parameter(torch.tensor(0.0))
        self.view_weight_logits = nn.Parameter(torch.zeros(len(identity_views)))
        self.prior_null_utility = nn.Parameter(torch.tensor(0.0))
        self.current_null_utility = nn.Parameter(torch.tensor(0.0))

    def _validate_features(self, regions: RegionBatch) -> None:
        regions.validate()
        if regions.prior_features.shape[-1] != self.feature_dim:
            raise ValueError(
                f"expected feature dimension {self.feature_dim}, "
                f"got {regions.prior_features.shape[-1]}"
            )

    def normalized_view_weights(self) -> Tensor:
        """Return the non-negative simplex weights used by the edge scorer."""

        return torch.softmax(self.view_weight_logits, dim=0)

    def effective_null_utilities(self) -> tuple[Tensor, Tensor]:
        """Return bounded death and birth utilities for protocol audits."""

        return (
            self.null_utility_cap * torch.tanh(self.prior_null_utility),
            self.null_utility_cap * torch.tanh(self.current_null_utility),
        )

    def compute_utilities(self, regions: RegionBatch) -> tuple[Tensor, Tensor, Tensor]:
        """Return rotation-invariant edge, death, and birth utilities."""

        self._validate_features(regions)
        view_cosines = []
        for start, end in self.identity_views:
            prior_identity = F.normalize(regions.prior_features[..., start:end], dim=-1)
            current_identity = F.normalize(
                regions.current_features[..., start:end], dim=-1
            )
            view_cosines.append(
                torch.einsum("brd,bsd->brs", prior_identity, current_identity)
            )
        stacked_cosines = torch.stack(view_cosines, dim=0)
        weights = self.normalized_view_weights().view(
            -1, *([1] * (stacked_cosines.ndim - 1))
        )
        cosine = (weights * stacked_cosines).sum(dim=0)
        coefficient = torch.tanh(self.residual_coefficient)
        residual = self.residual_cap * coefficient * torch.tanh(cosine)
        edge_utility = cosine + residual
        effective_prior_null, effective_current_null = self.effective_null_utilities()
        prior_null = effective_prior_null.expand(cosine.shape[:2])
        current_null = effective_current_null.expand(cosine.shape[0], cosine.shape[2])
        return edge_utility, prior_null, current_null

    utilities = compute_utilities

    def residual(self, cosine: Tensor) -> Tensor:
        """Expose the bounded monotone residual for protocol audits."""

        if not cosine.is_floating_point() or not torch.isfinite(cosine).all():
            raise ValueError("cosine must be a finite floating-point tensor")
        return (
            self.residual_cap
            * torch.tanh(self.residual_coefficient)
            * torch.tanh(cosine)
        )

    def _compatibility_mask(self, regions: RegionBatch) -> Tensor:
        compatible = regions.prior_valid[:, :, None] & regions.current_valid[:, None, :]
        if self.anatomy_constrained:
            compatible = compatible & (
                regions.prior_anatomy[:, :, None] == regions.current_anatomy[:, None, :]
            )
        return compatible

    @staticmethod
    def _augment_transport(
        real_transport: Tensor,
        prior_mass: Tensor,
        current_mass: Tensor,
    ) -> Tensor:
        death = (prior_mass - real_transport.sum(dim=-1)).clamp_min(0.0)
        birth = (current_mass - real_transport.sum(dim=-2)).clamp_min(0.0)
        upper = torch.cat((real_transport, death.unsqueeze(-1)), dim=-1)
        lower = torch.cat(
            (
                birth.unsqueeze(-2),
                real_transport.new_zeros((real_transport.shape[0], 1, 1)),
            ),
            dim=-1,
        )
        return torch.cat((upper, lower), dim=-2)

    def _augmented_utility(
        self,
        edge_utility: Tensor,
        prior_null: Tensor,
        current_null: Tensor,
        compatible: Tensor,
        batch_index: int,
        valid_priors: Tensor,
        valid_currents: Tensor,
    ) -> tuple[Tensor, Tensor]:
        prior_size = int(valid_priors.numel())
        current_size = int(valid_currents.numel())
        size = prior_size + current_size
        augmented = edge_utility.new_zeros((size, size))
        allowed = torch.zeros((size, size), dtype=torch.bool, device=augmented.device)

        if prior_size and current_size:
            pair_utility = (
                edge_utility[batch_index]
                .index_select(0, valid_priors)
                .index_select(1, valid_currents)
            )
            pair_allowed = (
                compatible[batch_index]
                .index_select(0, valid_priors)
                .index_select(1, valid_currents)
            )
            augmented[:prior_size, :current_size] = pair_utility
            allowed[:prior_size, :current_size] = pair_allowed

        if prior_size:
            local_prior = torch.arange(prior_size, device=augmented.device)
            augmented[local_prior, current_size + local_prior] = prior_null[
                batch_index
            ].index_select(0, valid_priors)
            allowed[local_prior, current_size + local_prior] = True
        if current_size:
            local_current = torch.arange(current_size, device=augmented.device)
            augmented[prior_size + local_current, local_current] = current_null[
                batch_index
            ].index_select(0, valid_currents)
            allowed[prior_size + local_current, local_current] = True
        if prior_size and current_size:
            allowed[prior_size:, current_size:] = True
        return augmented, allowed

    def _sinkhorn(self, augmented: Tensor, allowed: Tensor) -> Tensor:
        log_transport = (augmented / self.temperature).masked_fill(~allowed, -torch.inf)
        for _ in range(self.sinkhorn_iterations):
            log_transport = log_transport - torch.logsumexp(
                log_transport, dim=-1, keepdim=True
            )
            log_transport = log_transport - torch.logsumexp(
                log_transport, dim=-2, keepdim=True
            )
        return log_transport.exp().masked_fill(~allowed, 0.0)

    def _batched_augmented_utility(
        self,
        edge_utility: Tensor,
        prior_null: Tensor,
        current_null: Tensor,
        compatible: Tensor,
    ) -> tuple[Tensor, Tensor]:
        """Vectorized augmentation for batches without padded endpoints."""

        batch, prior_count, current_count = edge_utility.shape
        size = prior_count + current_count
        augmented = edge_utility.new_zeros((batch, size, size))
        allowed = torch.zeros(
            (batch, size, size), dtype=torch.bool, device=edge_utility.device
        )
        augmented[:, :prior_count, :current_count] = edge_utility
        allowed[:, :prior_count, :current_count] = compatible
        prior_indices = torch.arange(prior_count, device=edge_utility.device)
        current_indices = torch.arange(current_count, device=edge_utility.device)
        augmented[:, prior_indices, current_count + prior_indices] = prior_null
        allowed[:, prior_indices, current_count + prior_indices] = True
        augmented[:, prior_count + current_indices, current_indices] = current_null
        allowed[:, prior_count + current_indices, current_indices] = True
        allowed[:, prior_count:, current_count:] = True
        return augmented, allowed

    def _soft_real_transport(
        self,
        regions: RegionBatch,
        edge_utility: Tensor,
        prior_null: Tensor,
        current_null: Tensor,
        compatible: Tensor,
    ) -> Tensor:
        batch, prior_count, current_count = edge_utility.shape
        real_transport = edge_utility.new_zeros((batch, prior_count, current_count))
        if prior_count == 0 or current_count == 0:
            return real_transport
        if bool(regions.prior_valid.all() and regions.current_valid.all()):
            augmented, allowed = self._batched_augmented_utility(
                edge_utility, prior_null, current_null, compatible
            )
            real_transport = self._sinkhorn(augmented, allowed)[
                :, :prior_count, :current_count
            ]
        else:
            for batch_index in range(batch):
                valid_priors = torch.nonzero(
                    regions.prior_valid[batch_index], as_tuple=False
                ).flatten()
                valid_currents = torch.nonzero(
                    regions.current_valid[batch_index], as_tuple=False
                ).flatten()
                if not valid_priors.numel() or not valid_currents.numel():
                    continue
                augmented, allowed = self._augmented_utility(
                    edge_utility,
                    prior_null,
                    current_null,
                    compatible,
                    batch_index,
                    valid_priors,
                    valid_currents,
                )
                local_transport = self._sinkhorn(augmented, allowed)
                local_real = local_transport[
                    : valid_priors.numel(), : valid_currents.numel()
                ]
                real_transport[batch_index][
                    valid_priors[:, None], valid_currents[None, :]
                ] = local_real

        # A finite number of Sinkhorn iterations can leave a tiny residual on
        # the last-normalized axis.  Down-scaling only excess real mass is a
        # numerical feasibility correction: it cannot violate a capacity that
        # was already feasible and does not introduce a local matching rule.
        prior_mass = regions.prior_valid.to(real_transport.dtype)
        current_mass = regions.current_valid.to(real_transport.dtype)
        tiny = torch.finfo(real_transport.dtype).tiny
        row_sum = real_transport.sum(dim=-1)
        row_scale = torch.where(
            row_sum > prior_mass,
            prior_mass / row_sum.clamp_min(tiny),
            torch.ones_like(row_sum),
        )
        real_transport = real_transport * row_scale.unsqueeze(-1)
        column_sum = real_transport.sum(dim=-2)
        column_scale = torch.where(
            column_sum > current_mass,
            current_mass / column_sum.clamp_min(tiny),
            torch.ones_like(column_sum),
        )
        real_transport = real_transport * column_scale.unsqueeze(-2)
        return real_transport

    def _hard_real_transport(
        self,
        regions: RegionBatch,
        edge_utility: Tensor,
        prior_null: Tensor,
        current_null: Tensor,
        compatible: Tensor,
    ) -> Tensor:
        batch, prior_count, current_count = edge_utility.shape
        real_transport = edge_utility.new_zeros((batch, prior_count, current_count))
        for batch_index in range(batch):
            valid_priors = torch.nonzero(
                regions.prior_valid[batch_index], as_tuple=False
            ).flatten()
            valid_currents = torch.nonzero(
                regions.current_valid[batch_index], as_tuple=False
            ).flatten()
            augmented, allowed = self._augmented_utility(
                edge_utility,
                prior_null,
                current_null,
                compatible,
                batch_index,
                valid_priors,
                valid_currents,
            )
            size = augmented.shape[0]
            if size == 0:
                continue
            values = augmented.detach().to(device="cpu", dtype=torch.float64)
            allowed_cpu = allowed.detach().to(device="cpu")
            allowed_values = values.masked_select(allowed_cpu)
            value_range = float(allowed_values.max() - allowed_values.min())
            forbidden = float(allowed_values.min()) - (size + 1) * (value_range + 1.0)
            weights = [
                [
                    float(values[row, column])
                    if bool(allowed_cpu[row, column])
                    else forbidden
                    for column in range(size)
                ]
                for row in range(size)
            ]
            assignment = _hungarian_minimize(
                [[-weight for weight in row] for row in weights]
            )
            prior_size = int(valid_priors.numel())
            current_size = int(valid_currents.numel())
            for local_prior, column in enumerate(assignment[:prior_size]):
                if column < current_size and bool(allowed_cpu[local_prior, column]):
                    real_transport[
                        batch_index,
                        valid_priors[local_prior],
                        valid_currents[column],
                    ] = 1.0
        return real_transport

    @staticmethod
    def _objective(
        transport: Tensor,
        edge_utility: Tensor,
        prior_null: Tensor,
        current_null: Tensor,
    ) -> Tensor:
        prior_count = edge_utility.shape[1]
        current_count = edge_utility.shape[2]
        return (
            (transport[:, :prior_count, :current_count] * edge_utility).sum(
                dim=(-2, -1)
            )
            + (transport[:, :prior_count, current_count] * prior_null).sum(dim=-1)
            + (transport[:, prior_count, :current_count] * current_null).sum(dim=-1)
        )

    def plan_from_utilities(
        self,
        regions: RegionBatch,
        edge_utility: Tensor,
        prior_null: Tensor,
        current_null: Tensor,
        *,
        hard: bool = False,
    ) -> MatchPlan:
        NullAwareMatchGraph._validate_utilities(
            regions, edge_utility, prior_null, current_null
        )
        compatible = self._compatibility_mask(regions)
        prior_mass = regions.prior_valid.to(edge_utility.dtype)
        current_mass = regions.current_valid.to(edge_utility.dtype)
        if hard:
            real_transport = self._hard_real_transport(
                regions,
                edge_utility,
                prior_null,
                current_null,
                compatible,
            )
        else:
            real_transport = self._soft_real_transport(
                regions,
                edge_utility,
                prior_null,
                current_null,
                compatible,
            )
        selected = self._augment_transport(real_transport, prior_mass, current_mass)
        selected_objective = self._objective(
            selected, edge_utility, prior_null, current_null
        )
        objective_key = "objective_hard" if hard else "objective_soft"
        plan = MatchPlan(
            transport=selected,
            mode="invariant_partial_ot_hard" if hard else "invariant_partial_ot_soft",
            edge_logits=edge_utility,
            prior_null_logits=prior_null,
            current_null_logits=current_null,
            diagnostics={
                "identity_start": self.identity_start,
                "identity_view_count": len(self.identity_views),
                "view_weights": self.normalized_view_weights().detach(),
                "residual_cap": self.residual_cap,
                "residual_coefficient": torch.tanh(self.residual_coefficient).detach(),
                "null_utility_cap": self.null_utility_cap,
                "effective_prior_null_utility": prior_null[0, 0].detach()
                if prior_null.numel()
                else self.effective_null_utilities()[0].detach(),
                "effective_current_null_utility": current_null[0, 0].detach()
                if current_null.numel()
                else self.effective_null_utilities()[1].detach(),
                "temperature": self.temperature,
                "iterations": self.sinkhorn_iterations,
                objective_key: selected_objective.detach(),
                "optimization_objective": (
                    "unregularized augmented assignment"
                    if hard
                    else "entropy-regularized augmented assignment"
                ),
                "selected_utility_formula": (
                    "sum(P*u_edge) + sum(death*u_death) + sum(birth*u_birth)"
                ),
            },
        )
        if hard:
            plan.validate_hard(regions, atol=self.feasibility_tolerance)
        else:
            plan.validate(regions, atol=self.feasibility_tolerance)
        return plan

    def soft_plan(self, regions: RegionBatch) -> MatchPlan:
        return self.plan_from_utilities(
            regions, *self.compute_utilities(regions), hard=False
        )

    def hard_plan(self, regions: RegionBatch) -> MatchPlan:
        return self.plan_from_utilities(
            regions, *self.compute_utilities(regions), hard=True
        )

    def forward(self, regions: RegionBatch, *, hard: bool = False) -> MatchPlan:
        return self.hard_plan(regions) if hard else self.soft_plan(regions)


def assignment_accuracy(
    predicted: MatchPlan,
    oracle: MatchPlan,
    regions: RegionBatch,
) -> float:
    predicted.validate(regions)
    oracle.validate(regions)
    b, rp, _ = regions.prior_features.shape
    correct = 0
    total = 0
    for batch_index in range(b):
        for prior_index in range(rp):
            if not bool(regions.prior_valid[batch_index, prior_index]):
                continue
            pred = int(predicted.transport[batch_index, prior_index].argmax().item())
            gold = int(oracle.transport[batch_index, prior_index].argmax().item())
            correct += int(pred == gold)
            total += 1
    return correct / max(total, 1)
