from types import SimpleNamespace

import pytest
import torch
from torch import nn

from visualvit.projector import RelationProjector
from visualvit.qwen_adapter import FrozenVLMAdapter, PROGRESSION_LABELS
from visualvit.schemas import TokenBundle


PLACEHOLDER_ID = 1
LABEL_TOKEN_IDS = {
    "stable": (5,),
    "worse": (6, 7),
    "improved": (8,),
    "new": (9, 10, 11),
    "resolved": (12, 13),
}


class ToyCausalLM(nn.Module):
    def __init__(self, vocab_size: int = 32, hidden_size: int = 10) -> None:
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, hidden_size)
        self.mix = nn.Linear(hidden_size, hidden_size, bias=False)
        self.lm_head = nn.Linear(hidden_size, vocab_size, bias=False)
        self.last_attention_mask = None
        self.last_position_ids = None
        self.last_use_cache = None
        self.last_logits_to_keep = None

    def get_input_embeddings(self) -> nn.Module:
        return self.embedding

    def forward(
        self,
        *,
        inputs_embeds: torch.Tensor,
        attention_mask: torch.Tensor,
        position_ids: torch.Tensor,
        use_cache: bool,
        logits_to_keep: int,
    ) -> SimpleNamespace:
        if position_ids.shape != (3, *attention_mask.shape):
            raise ValueError("toy LM requires three text-like position axes")
        self.last_attention_mask = attention_mask.detach().clone()
        self.last_position_ids = position_ids.detach().clone()
        self.last_use_cache = use_cache
        self.last_logits_to_keep = logits_to_keep
        masked = self.mix(inputs_embeds) * attention_mask.unsqueeze(-1)
        hidden = torch.tanh(torch.cumsum(masked, dim=1))
        return SimpleNamespace(logits=self.lm_head(hidden))


def _token_bundle(batch_size: int = 2, input_dim: int = 7) -> TokenBundle:
    torch.manual_seed(23)
    token_types = torch.tensor(
        [0] * 4 + [1] * 28 + [2] * 28 + [3] * 4, dtype=torch.long
    )
    valid = torch.ones(batch_size, 64, dtype=torch.bool)
    valid[:, -4:] = False
    return TokenBundle(
        tokens=torch.randn(batch_size, 64, input_dim),
        token_types=token_types,
        valid_mask=valid,
        assignment=torch.zeros(batch_size, 1, 1),
    )


def _prompt(batch_size: int = 2) -> torch.Tensor:
    row = torch.tensor([2, 3] + [PLACEHOLDER_ID] * 64 + [4], dtype=torch.long)
    return row.view(1, -1).expand(batch_size, -1).clone()


def _system(batch_size: int = 2):
    projector = RelationProjector(input_dim=7, hidden_size=10)
    projected = projector(_token_bundle(batch_size=batch_size))
    model = ToyCausalLM(hidden_size=10)
    adapter = FrozenVLMAdapter(model, PLACEHOLDER_ID, LABEL_TOKEN_IDS)
    return projector, projected, model, adapter


def test_exact_64_placeholder_replacement_preserves_text_and_qwen_masks():
    _, projected, model, adapter = _system()
    input_ids = _prompt()
    ordinary = model.get_input_embeddings()(input_ids)
    model_inputs, audit = adapter.prepare_inputs(input_ids, projected)
    placeholder_mask = input_ids.eq(PLACEHOLDER_ID)

    assert torch.equal(
        model_inputs["inputs_embeds"][placeholder_mask],
        projected.embeddings.reshape(-1, projected.embeddings.shape[-1]),
    )
    assert torch.equal(
        model_inputs["inputs_embeds"][~placeholder_mask], ordinary[~placeholder_mask]
    )
    assert torch.equal(model_inputs["attention_mask"], torch.ones_like(input_ids))
    assert model_inputs["position_ids"].shape == (3, 2, input_ids.shape[1])
    assert torch.equal(model_inputs["position_ids"][0], model_inputs["position_ids"][1])
    assert audit["placeholder_count"].tolist() == [64, 64]
    assert audit["pixel_inputs_used"] is False
    assert model_inputs["use_cache"] is False
    assert model_inputs["logits_to_keep"] == 0
    injected, injected_mask = adapter.inject(input_ids, projected)
    assert torch.equal(injected, model_inputs["inputs_embeds"])
    assert torch.equal(injected_mask, placeholder_mask)


@pytest.mark.parametrize("placeholder_count", [63, 65])
def test_adapter_rejects_any_nonexact_placeholder_count(placeholder_count):
    _, projected, _, adapter = _system(batch_size=1)
    input_ids = torch.tensor(
        [[2] + [PLACEHOLDER_ID] * placeholder_count + [3]], dtype=torch.long
    )
    with pytest.raises(ValueError, match="exactly 64"):
        adapter.prepare_inputs(input_ids, projected)


def test_adapter_rejects_masked_placeholders_and_all_bypass_inputs():
    _, projected, _, adapter = _system(batch_size=1)
    input_ids = _prompt(batch_size=1)
    attention_mask = torch.ones_like(input_ids)
    attention_mask[0, 2] = 0
    with pytest.raises(ValueError, match="physical attention one"):
        adapter(input_ids, projected, attention_mask=attention_mask)
    with pytest.raises(ValueError, match="forbids pixel/image/video or multimodal"):
        adapter(input_ids, projected, pixel_values=torch.zeros(1, 3, 2, 2))
    with pytest.raises(ValueError, match="forbids pixel/image/video or multimodal"):
        adapter(input_ids, projected, image_grid_thw=torch.ones(1, 3))
    with pytest.raises(ValueError, match="forbids pixel/image/video or multimodal"):
        adapter(input_ids, projected, mm_token_type_ids=torch.zeros_like(input_ids))
    with pytest.raises(ValueError, match="constructs these model inputs explicitly"):
        adapter(input_ids, projected, use_cache=True)
    with pytest.raises(ValueError, match="constructs these model inputs explicitly"):
        adapter(input_ids, projected, past_key_values=object())
    with pytest.raises(ValueError, match="constructs these model inputs explicitly"):
        adapter(input_ids, projected, logits_to_keep=1)


def test_five_label_scores_are_raw_length_normalized_log_likelihoods():
    _, projected, model, adapter = _system(batch_size=1)
    with torch.no_grad():
        model.mix.weight.zero_()
        model.lm_head.weight.zero_()
    scores, audit = adapter.score_labels(
        _prompt(batch_size=1), projected, return_audit=True
    )

    expected = torch.full((1, 5), -torch.log(torch.tensor(32.0)))
    assert scores.shape == (1, 5)
    assert torch.allclose(scores, expected)
    assert audit["labels"] == PROGRESSION_LABELS
    assert audit["label_lengths"].tolist() == [1, 2, 1, 3, 2]
    assert audit["normalization"] == "mean_token_log_likelihood"


def test_label_scoring_compacts_right_padding_before_candidate_tokens():
    _, projected, _, adapter = _system(batch_size=2)
    prompt = _prompt()
    padded_prompt = torch.cat((prompt, torch.tensor([[14, 15], [16, 17]])), dim=1)
    padded_attention = torch.cat(
        (torch.ones_like(prompt), torch.zeros(2, 2, dtype=torch.long)), dim=1
    )
    padded_scores = adapter.score_labels(
        padded_prompt, projected, attention_mask=padded_attention
    )
    compact_scores = adapter.score_labels(prompt, projected)
    assert torch.allclose(padded_scores, compact_scores)


def test_lm_stays_frozen_while_score_gradients_reach_only_projector():
    projector, projected, model, adapter = _system(batch_size=2)
    adapter.train()
    audit = adapter.freeze_audit()
    assert audit["all_frozen"]
    assert audit["trainable_parameter_count"] == 0
    assert model.training is False

    scores = adapter.score_labels(_prompt(), projected)
    (-scores[:, 0].mean()).backward()
    projector_gradients = [parameter.grad for parameter in projector.parameters()]
    assert any(
        gradient is not None and bool(gradient.abs().sum() > 0)
        for gradient in projector_gradients
    )
    assert all(parameter.grad is None for parameter in model.parameters())
    assert model.last_attention_mask is not None
    assert bool(model.last_attention_mask.eq(1).all())
    assert torch.equal(model.last_position_ids[0], model.last_position_ids[2])
    assert model.last_use_cache is False
    assert model.last_logits_to_keep == 0
