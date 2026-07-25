import copy

import torch

from visualvit.allocator import DeterministicGlobalAllocator
from visualvit.matching import anatomy_compatible_derangement
from visualvit.schemas import MatchPlan
from visualvit.synthetic import make_synthetic_batch
from visualvit.tokenizer import (
    ENTITY_TOKENS,
    GLOBAL_TOKENS,
    RELATION_TOKENS,
    assemble_capes_ci_tokens,
    build_soft_relation_candidates,
)


def _allocate(regions, plan):
    candidates = build_soft_relation_candidates(regions, plan)
    allocation = DeterministicGlobalAllocator(max_slots=ENTITY_TOKENS)(candidates)
    return candidates, allocation


def test_soft_candidates_never_read_gold_entity_ids():
    synthetic = make_synthetic_batch(num_cases=2, seed=101)
    changed = copy.copy(synthetic.regions)
    changed.prior_entity_ids = torch.full_like(changed.prior_entity_ids, 999_001)
    changed.current_entity_ids = torch.full_like(changed.current_entity_ids, -999_001)

    original = build_soft_relation_candidates(synthetic.regions, synthetic.oracle)
    mutated = build_soft_relation_candidates(changed, synthetic.oracle)
    assert torch.equal(original.entity_features, mutated.entity_features)
    assert torch.equal(original.relation_features, mutated.relation_features)
    assert torch.equal(original.source_ids, mutated.source_ids)


def test_b4_shares_allocator_entity_stream_layout_and_changes_relations():
    synthetic = make_synthetic_batch(num_cases=3, seed=103)
    oracle = synthetic.oracle
    deranged = anatomy_compatible_derangement(synthetic.regions, oracle, seed=1701)
    candidates_b, allocation = _allocate(synthetic.regions, oracle)
    candidates_a = build_soft_relation_candidates(synthetic.regions, deranged)
    assert torch.equal(candidates_a.entity_features, candidates_b.entity_features)
    assert not torch.equal(
        candidates_a.relation_features, candidates_b.relation_features
    )

    bundle_a = assemble_capes_ci_tokens(synthetic.regions, deranged, allocation)
    bundle_b = assemble_capes_ci_tokens(synthetic.regions, oracle, allocation)
    entity_start = GLOBAL_TOKENS
    entity_stop = entity_start + ENTITY_TOKENS
    relation_stop = entity_stop + RELATION_TOKENS
    assert torch.equal(
        bundle_a.tokens[:, entity_start:entity_stop],
        bundle_b.tokens[:, entity_start:entity_stop],
    )
    assert not torch.equal(
        bundle_a.tokens[:, entity_stop:relation_stop],
        bundle_b.tokens[:, entity_stop:relation_stop],
    )
    assert torch.equal(bundle_a.token_types, bundle_b.token_types)
    assert torch.equal(bundle_a.valid_mask, bundle_b.valid_mask)
    assert torch.equal(bundle_a.source_ids, bundle_b.source_ids)
    assert bundle_a.tokens.shape[1] == 64


def test_fractional_transport_is_differentiable_through_soft_assembly():
    synthetic = make_synthetic_batch(num_cases=2, seed=107)
    deranged = anatomy_compatible_derangement(
        synthetic.regions, synthetic.oracle, seed=1703
    )
    transport = (
        (0.55 * synthetic.oracle.transport + 0.45 * deranged.transport)
        .detach()
        .requires_grad_(True)
    )
    plan = MatchPlan(transport=transport, mode="fractional_gradient_test")
    _, allocation = _allocate(synthetic.regions, plan)
    bundle = assemble_capes_ci_tokens(synthetic.regions, plan, allocation)
    loss = bundle.tokens.square().mean()
    loss.backward()
    assert transport.grad is not None
    assert torch.isfinite(transport.grad).all()
    assert float(transport.grad.abs().sum()) > 0


def test_overflow_uses_fixed_summary_instead_of_raising():
    synthetic = make_synthetic_batch(
        num_cases=1,
        seed=109,
        persistent=14,
        deaths=1,
        births=0,
    )
    candidates, allocation = _allocate(synthetic.regions, synthetic.oracle)
    assert candidates.entity_features.shape[1] == 29
    assert torch.allclose(
        allocation.weights.sum(dim=1),
        candidates.valid_mask.to(allocation.weights.dtype),
    )
    assert bool(allocation.overflow_mask.any())
    assert int((allocation.selected_source_ids == -2).sum()) == 1
    bundle = assemble_capes_ci_tokens(synthetic.regions, synthetic.oracle, allocation)
    bundle.validate()
    assert bundle.tokens.shape[1] == 64
    assert torch.equal(
        bundle.valid_mask[:, GLOBAL_TOKENS : GLOBAL_TOKENS + ENTITY_TOKENS],
        bundle.valid_mask[
            :,
            GLOBAL_TOKENS + ENTITY_TOKENS : GLOBAL_TOKENS
            + ENTITY_TOKENS
            + RELATION_TOKENS,
        ],
    )
