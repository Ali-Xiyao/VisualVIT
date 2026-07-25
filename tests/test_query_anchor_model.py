from __future__ import annotations

import torch
import torch.nn.functional as F

from visualvit.calibration_query import (
    QUERY_RELATION_SLOT,
    build_query_relation_tokens,
    make_query_anchor_batch,
)
from visualvit.matching import NullAwareMatchGraph
from visualvit.query_anchor_model import (
    QueryRelationProjector,
    build_frozen_query_adapter,
    query_prompt,
)


def _scores(batch: object, plan: object) -> tuple[torch.Tensor, object]:
    contract = build_query_relation_tokens(
        batch.regions,
        batch.prior_query_marker,
        batch.current_query_marker,
        plan,
        token_dim=6,
    )
    projector = QueryRelationProjector(input_dim=6, hidden_size=8)
    projected = projector(contract)
    adapter = build_frozen_query_adapter(hidden_size=8)
    scores, audit = adapter.score_labels(
        query_prompt(batch.oracle.labels.numel()),
        projected,
        return_audit=True,
    )
    return scores, audit


def test_registered_query_readout_decodes_oracle_through_exact_64_adapter() -> None:
    batch = make_query_anchor_batch(cases_per_label=3, seed=63_401)
    scores, audit = _scores(batch, batch.oracle.plan)
    assert torch.equal(scores.argmax(dim=-1), batch.oracle.labels)
    assert torch.isfinite(scores).all()
    assert audit["placeholder_count"].tolist() == [64] * 15
    assert audit["pixel_inputs_used"] is False
    assert audit["model_frozen"]


def test_projector_keeps_every_nonquery_projected_payload_literal_zero() -> None:
    batch = make_query_anchor_batch(cases_per_label=1, seed=63_419)
    contract = build_query_relation_tokens(
        batch.regions,
        batch.prior_query_marker,
        batch.current_query_marker,
        batch.oracle.plan,
        token_dim=6,
    )
    projected = QueryRelationProjector()(contract)
    nonquery = projected.embeddings.clone()
    nonquery[:, QUERY_RELATION_SLOT] = 0
    assert torch.count_nonzero(nonquery) == 0
    assert projected.attention_mask.eq(1).all()
    assert projected.position_ids.shape == (3, 5, 64)


def test_label_loss_backpropagates_through_soft_matcher_not_frozen_lm() -> None:
    batch = make_query_anchor_batch(cases_per_label=2, seed=63_433)
    torch.manual_seed(17)
    matcher = NullAwareMatchGraph(
        feature_dim=batch.regions.prior_features.shape[-1],
        hidden_dim=12,
        temperature=0.45,
        projection_iterations=20,
    )
    plan = matcher.soft_plan(batch.regions)
    contract = build_query_relation_tokens(
        batch.regions,
        batch.prior_query_marker,
        batch.current_query_marker,
        plan,
        token_dim=6,
    )
    projector = QueryRelationProjector()
    projected = projector(contract)
    adapter = build_frozen_query_adapter(hidden_size=8)
    scores = adapter.score_labels(query_prompt(10), projected)
    loss = F.cross_entropy(scores, batch.oracle.labels)
    loss.backward()

    matcher_gradients = [
        parameter.grad
        for parameter in matcher.parameters()
        if parameter.requires_grad and parameter.grad is not None
    ]
    assert matcher_gradients
    assert any(torch.count_nonzero(gradient) > 0 for gradient in matcher_gradients)
    assert projector.projection.weight.grad is not None
    assert all(parameter.grad is None for parameter in adapter.model.parameters())
