from types import SimpleNamespace

import pytest
import torch
from torch import nn

from visualvit.qwen_adapter import GenerativeVLMAdapter
from visualvit.schemas import ProjectedTokenBundle


PLACEHOLDER = 31


class ToyGenerativeLM(nn.Module):
    def __init__(self, hidden_size=8, vocab_size=40):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, hidden_size)
        self.base = nn.Linear(hidden_size, hidden_size, bias=False)
        self.lora_adapter = nn.Linear(hidden_size, hidden_size, bias=False)
        self.lm_head = nn.Linear(hidden_size, vocab_size, bias=False)
        self.base.requires_grad_(False)
        self.embedding.requires_grad_(False)
        self.lm_head.requires_grad_(False)
        self.generate_calls = 0
        self.generate_use_cache = None

    def get_input_embeddings(self):
        return self.embedding

    def forward(
        self,
        *,
        inputs_embeds,
        attention_mask,
        position_ids,
        use_cache,
        logits_to_keep=0,
    ):
        assert position_ids.shape == (3, *attention_mask.shape)
        hidden = self.base(inputs_embeds) + self.lora_adapter(inputs_embeds)
        hidden = torch.tanh(torch.cumsum(hidden, dim=1))
        hidden = hidden * attention_mask.unsqueeze(-1)
        return SimpleNamespace(logits=self.lm_head(hidden))

    def generate(
        self,
        *,
        inputs_embeds,
        attention_mask,
        position_ids,
        use_cache,
        max_new_tokens,
        eos_token_id,
        pad_token_id,
        do_sample,
    ):
        self.generate_calls += 1
        self.generate_use_cache = use_cache
        assert inputs_embeds.shape[:2] == attention_mask.shape
        assert position_ids.shape == (3, *attention_mask.shape)
        assert do_sample is False
        eos = 2 if eos_token_id is None else int(eos_token_id)
        return torch.tensor([[7, eos]], device=inputs_embeds.device)


def projected(batch_size=1, hidden_size=8):
    embeddings = torch.randn(batch_size, 64, hidden_size, requires_grad=True)
    valid = torch.ones(batch_size, 64, dtype=torch.bool)
    valid[:, 60:] = False
    physical_attention = torch.ones(batch_size, 64, dtype=torch.long)
    positions = (
        torch.arange(64, dtype=torch.long)
        .view(1, 1, 64)
        .expand(3, batch_size, -1)
        .contiguous()
    )
    return ProjectedTokenBundle(
        embeddings=embeddings,
        token_types=torch.tensor([0] * 20 + [1] * 20 + [2] * 20 + [3] * 4),
        valid_mask=valid,
        attention_mask=physical_attention,
        position_ids=positions,
        audit={},
    )


def full_sft_row():
    return torch.tensor(
        [[3] + [PLACEHOLDER] * 64 + [4, 8, 9, 2]], dtype=torch.long
    )


def test_forward_sft_masks_prefix_and_gradients_reach_only_lora_and_visual_input():
    model = ToyGenerativeLM()
    adapter = GenerativeVLMAdapter(model, PLACEHOLDER)
    input_ids = full_sft_row()
    labels = torch.full_like(input_ids, -100)
    labels[:, -3:] = input_ids[:, -3:]
    visual = projected()

    result = adapter.forward_sft(input_ids, visual, labels=labels)
    result["loss"].backward()

    assert result["audit"]["assistant_only_loss"]
    assert result["audit"]["supervised_token_count"].tolist() == [3]
    assert result["audit"]["placeholder_count"].tolist() == [64]
    assert model.lora_adapter.weight.grad is not None
    assert visual.embeddings.grad is not None
    assert model.base.weight.grad is None
    assert model.embedding.weight.grad is None
    assert model.lm_head.weight.grad is None


def test_forward_sft_rejects_prefix_or_noncontiguous_supervision():
    model = ToyGenerativeLM()
    adapter = GenerativeVLMAdapter(model, PLACEHOLDER)
    input_ids = full_sft_row()
    labels = torch.full_like(input_ids, -100)
    labels[0, 0] = input_ids[0, 0]
    labels[0, -1] = input_ids[0, -1]

    with pytest.raises(ValueError, match="contiguous attended suffix"):
        adapter.forward_sft(input_ids, projected(), labels=labels)


def test_sequence_scoring_is_length_normalized_and_placeholder_safe():
    model = ToyGenerativeLM()
    adapter = GenerativeVLMAdapter(model, PLACEHOLDER)
    prompt = torch.tensor([[3] + [PLACEHOLDER] * 64 + [4]], dtype=torch.long)
    targets = torch.tensor([[8, 9, 2]], dtype=torch.long)

    scores, audit = adapter.score_sequence(
        prompt, projected(), targets, return_audit=True
    )

    assert scores.shape == (1,)
    assert torch.isfinite(scores).all()
    assert audit["normalization"] == "mean_token_log_likelihood"
    assert audit["target_lengths"].tolist() == [3]


def test_generate_injects_visual_embeddings_once_and_stops_on_eos():
    model = ToyGenerativeLM()
    adapter = GenerativeVLMAdapter(model, PLACEHOLDER)
    prompt = torch.tensor([[3] + [PLACEHOLDER] * 64 + [4]], dtype=torch.long)

    generated, audit = adapter.generate_text(
        prompt,
        projected(),
        max_new_tokens=8,
        eos_token_id=2,
        pad_token_id=0,
        return_audit=True,
    )

    assert generated.tolist() == [[7, 2]]
    assert model.generate_calls == 1
    assert model.generate_use_cache is True
    assert audit["visual_injection_calls"] == 1
    assert audit["subsequent_placeholder_replacements"] == 0
    assert audit["pixel_inputs_used"] is False


def test_cached_and_uncached_first_step_logits_match():
    model = ToyGenerativeLM()
    adapter = GenerativeVLMAdapter(model, PLACEHOLDER)
    prompt = torch.tensor([[3] + [PLACEHOLDER] * 64 + [4]], dtype=torch.long)

    audit = adapter.audit_first_step_cache_equivalence(prompt, projected())

    assert audit["passed"]
    assert audit["maximum_absolute_difference"] == 0.0


def test_unregistered_trainable_base_parameter_fails_closed():
    model = ToyGenerativeLM()
    model.base.weight.requires_grad_(True)
    adapter = GenerativeVLMAdapter(model, PLACEHOLDER)
    input_ids = full_sft_row()
    labels = torch.full_like(input_ids, -100)
    labels[:, -3:] = input_ids[:, -3:]

    with pytest.raises(PermissionError, match="unexpected trainable"):
        adapter.forward_sft(input_ids, projected(), labels=labels)


def test_pixel_bypass_remains_forbidden():
    model = ToyGenerativeLM()
    adapter = GenerativeVLMAdapter(model, PLACEHOLDER)
    prompt = torch.tensor([[3] + [PLACEHOLDER] * 64 + [4]], dtype=torch.long)

    with pytest.raises(ValueError, match="forbids pixel/image/video"):
        adapter.generate_text(
            prompt,
            projected(),
            pixel_values=torch.zeros(1, 3, 2, 2),
        )
