from __future__ import annotations

from typing import Any

import torch
from torch import Tensor, nn

from .allocator import DeterministicGlobalAllocator
from .matching import NullAwareMatchGraph
from .projector import RelationProjector
from .qwen_adapter import FrozenVLMAdapter
from .schemas import (
    AllocationPlan,
    MatchPlan,
    ProjectedTokenBundle,
    RegionBatch,
    TokenBundle,
)
from .tokenizer import (
    assemble_capes_ci_tokens,
    build_soft_relation_candidates,
)


class CAPESCIModel(nn.Module):
    """End-to-end CAPES-CI relation-token path over frozen region features.

    The frozen vision encoder remains outside this module and supplies a
    validated ``RegionBatch``.  This keeps the controlled assignment path
    explicit and makes any pixel bypass impossible at this interface.
    """

    def __init__(
        self,
        matcher: NullAwareMatchGraph,
        projector: RelationProjector,
        vlm_adapter: FrozenVLMAdapter,
        allocator: DeterministicGlobalAllocator | None = None,
    ) -> None:
        super().__init__()
        if matcher.feature_dim <= 0:
            raise ValueError("matcher must declare a positive feature dimension")
        if projector.token_budget != vlm_adapter.token_budget:
            raise ValueError("projector and VLM adapter token budgets must match")
        self.matcher = matcher
        self.allocator = allocator or DeterministicGlobalAllocator(max_slots=28)
        self.projector = projector
        self.vlm_adapter = vlm_adapter

    def train(self, mode: bool = True) -> CAPESCIModel:
        super().train(mode)
        # FrozenVLMAdapter.train() already restores its model to eval, but keep
        # this invariant explicit at the top-level method boundary.
        self.vlm_adapter.model.eval()
        return self

    def trainable_parameter_audit(self) -> dict[str, Any]:
        trainable = [
            name
            for name, parameter in self.named_parameters()
            if parameter.requires_grad
        ]
        forbidden = [
            name for name in trainable if name.startswith("vlm_adapter.model.")
        ]
        return {
            "trainable_parameter_names": tuple(trainable),
            "trainable_parameter_count": sum(
                parameter.numel()
                for parameter in self.parameters()
                if parameter.requires_grad
            ),
            "frozen_vlm": not forbidden,
            "forbidden_vlm_trainable_names": tuple(forbidden),
        }

    def _select_plan(
        self,
        regions: RegionBatch,
        *,
        assignment_mode: str,
        provided_plan: MatchPlan | None,
    ) -> MatchPlan:
        if assignment_mode == "learned_soft":
            if provided_plan is not None:
                raise ValueError("provided_plan is forbidden for learned_soft")
            return self.matcher.soft_plan(regions)
        if assignment_mode == "learned_hard":
            if provided_plan is not None:
                raise ValueError("provided_plan is forbidden for learned_hard")
            return self.matcher.hard_plan(regions)
        if assignment_mode == "provided":
            if provided_plan is None:
                raise ValueError("assignment_mode='provided' requires provided_plan")
            provided_plan.validate(regions)
            return provided_plan
        raise ValueError(
            "assignment_mode must be learned_soft, learned_hard, or provided"
        )

    def encode_relations(
        self,
        regions: RegionBatch,
        *,
        assignment_mode: str = "learned_soft",
        provided_plan: MatchPlan | None = None,
        allocation_plan: AllocationPlan | None = None,
    ) -> tuple[MatchPlan, AllocationPlan, TokenBundle, ProjectedTokenBundle]:
        regions.validate()
        plan = self._select_plan(
            regions,
            assignment_mode=assignment_mode,
            provided_plan=provided_plan,
        )
        candidates = build_soft_relation_candidates(regions, plan)
        if allocation_plan is None:
            allocation_plan = self.allocator(candidates)
        else:
            allocation_plan.validate(slot_count=28)
            if not torch.equal(allocation_plan.source_valid, candidates.valid_mask):
                raise ValueError("provided allocation support does not match regions")
        bundle = assemble_capes_ci_tokens(regions, plan, allocation_plan)
        projected = self.projector(bundle)
        return plan, allocation_plan, bundle, projected

    def forward(
        self,
        regions: RegionBatch,
        input_ids: Tensor,
        *,
        attention_mask: Tensor | None = None,
        assignment_mode: str = "learned_soft",
        provided_plan: MatchPlan | None = None,
        allocation_plan: AllocationPlan | None = None,
        return_adapter_audit: bool = True,
        **model_kwargs: Any,
    ) -> dict[str, Any]:
        plan, allocation, bundle, projected = self.encode_relations(
            regions,
            assignment_mode=assignment_mode,
            provided_plan=provided_plan,
            allocation_plan=allocation_plan,
        )
        scoring = self.vlm_adapter.score_labels(
            input_ids,
            projected,
            attention_mask=attention_mask,
            return_audit=return_adapter_audit,
            **model_kwargs,
        )
        if return_adapter_audit:
            label_scores, adapter_audit = scoring
        else:
            label_scores = scoring
            adapter_audit = None
        audit = {
            "assignment_mode": assignment_mode,
            "token_budget": int(bundle.tokens.shape[1]),
            "allocation_shared_support": True,
            "pixel_inputs_used": False,
            "trainable_parameters": self.trainable_parameter_audit(),
            "match_diagnostics": plan.diagnostics,
            "adapter": adapter_audit,
        }
        return {
            "match_plan": plan,
            "allocation_plan": allocation,
            "token_bundle": bundle,
            "projected_token_bundle": projected,
            "label_scores": label_scores,
            "audits": audit,
        }
