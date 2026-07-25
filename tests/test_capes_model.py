from types import SimpleNamespace

import torch
from torch import nn

from visualvit.allocator import DeterministicGlobalAllocator
from visualvit.matching import NullAwareMatchGraph, anatomy_compatible_derangement
from visualvit.model import CAPESCIModel
from visualvit.projector import RelationProjector
from visualvit.qwen_adapter import FrozenVLMAdapter
from visualvit.synthetic import make_synthetic_batch
from visualvit.tokenizer import build_soft_relation_candidates


PLACEHOLDER = 1
LABEL_IDS = {
    "stable": (5,),
    "worse": (6,),
    "improved": (7,),
    "new": (8,),
    "resolved": (9,),
}


class RelationSensitiveToyLM(nn.Module):
    def __init__(self, hidden_size: int = 16, vocab_size: int = 32) -> None:
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, hidden_size)
        self.mix = nn.Linear(hidden_size, hidden_size, bias=False)
        self.head = nn.Linear(hidden_size, vocab_size, bias=False)

    def get_input_embeddings(self):
        return self.embedding

    def forward(
        self,
        *,
        inputs_embeds,
        attention_mask,
        position_ids,
        use_cache,
        logits_to_keep,
    ):
        assert position_ids.shape == (3, *attention_mask.shape)
        assert use_cache is False
        assert logits_to_keep == 0
        hidden = torch.cumsum(
            self.mix(inputs_embeds) * attention_mask.unsqueeze(-1), dim=1
        )
        return SimpleNamespace(logits=self.head(torch.tanh(hidden)))


def _prompt(batch_size: int) -> torch.Tensor:
    row = torch.tensor([2, 3] + [PLACEHOLDER] * 64 + [4], dtype=torch.long)
    return row.unsqueeze(0).expand(batch_size, -1).clone()


def _model(feature_dim: int) -> CAPESCIModel:
    matcher = NullAwareMatchGraph(feature_dim, hidden_dim=12, temperature=0.5)
    projector = RelationProjector(input_dim=4 * feature_dim + 3, hidden_size=16)
    adapter = FrozenVLMAdapter(RelationSensitiveToyLM(), PLACEHOLDER, LABEL_IDS)
    return CAPESCIModel(
        matcher,
        projector,
        adapter,
        DeterministicGlobalAllocator(max_slots=28),
    )


def test_full_learned_soft_chain_has_64_tokens_and_no_pixel_path():
    synthetic = make_synthetic_batch(num_cases=3, seed=211)
    model = _model(synthetic.regions.prior_features.shape[-1])
    output = model(synthetic.regions, _prompt(3))
    assert output["label_scores"].shape == (3, 5)
    assert output["token_bundle"].tokens.shape[1] == 64
    assert output["projected_token_bundle"].embeddings.shape[1] == 64
    assert output["audits"]["pixel_inputs_used"] is False
    assert output["audits"]["adapter"]["placeholder_count"].tolist() == [64] * 3
    assert output["audits"]["trainable_parameters"]["frozen_vlm"]


def test_gradients_reach_matcher_and_projector_but_never_frozen_lm():
    synthetic = make_synthetic_batch(num_cases=2, seed=223)
    model = _model(synthetic.regions.prior_features.shape[-1])
    model.train()
    scores = model(synthetic.regions, _prompt(2))["label_scores"]
    (-scores[:, 0].mean()).backward()
    assert any(
        parameter.grad is not None and bool(parameter.grad.abs().sum() > 0)
        for parameter in model.matcher.parameters()
    )
    assert any(
        parameter.grad is not None and bool(parameter.grad.abs().sum() > 0)
        for parameter in model.projector.parameters()
    )
    assert all(
        parameter.grad is None for parameter in model.vlm_adapter.model.parameters()
    )
    assert model.vlm_adapter.model.training is False


def test_b4_provided_plans_share_allocator_and_only_relation_stream_changes():
    synthetic = make_synthetic_batch(num_cases=2, seed=227)
    oracle = synthetic.oracle
    deranged = anatomy_compatible_derangement(synthetic.regions, oracle, seed=1709)
    model = _model(synthetic.regions.prior_features.shape[-1])
    candidates = build_soft_relation_candidates(synthetic.regions, oracle)
    shared_allocation = model.allocator(candidates)
    out_a = model(
        synthetic.regions,
        _prompt(2),
        assignment_mode="provided",
        provided_plan=deranged,
        allocation_plan=shared_allocation,
    )
    out_b = model(
        synthetic.regions,
        _prompt(2),
        assignment_mode="provided",
        provided_plan=oracle,
        allocation_plan=shared_allocation,
    )
    assert torch.equal(
        out_a["allocation_plan"].weights, out_b["allocation_plan"].weights
    )
    assert torch.equal(
        out_a["token_bundle"].tokens[:, 4:32],
        out_b["token_bundle"].tokens[:, 4:32],
    )
    assert not torch.equal(
        out_a["token_bundle"].tokens[:, 32:60],
        out_b["token_bundle"].tokens[:, 32:60],
    )
    assert not torch.equal(out_a["label_scores"], out_b["label_scores"])


def test_state_dict_round_trip_reproduces_scores_exactly():
    synthetic = make_synthetic_batch(num_cases=2, seed=229)
    first = _model(synthetic.regions.prior_features.shape[-1]).eval()
    expected = first(synthetic.regions, _prompt(2))["label_scores"].detach()
    second = _model(synthetic.regions.prior_features.shape[-1]).eval()
    second.load_state_dict(first.state_dict())
    observed = second(synthetic.regions, _prompt(2))["label_scores"].detach()
    assert torch.equal(expected, observed)
