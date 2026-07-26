from types import SimpleNamespace

import torch
from torch import nn

from visualvit.projector import RelationProjector
from visualvit.schemas import TokenBundle
from visualvit.tier_cxr_vlm import TierCXRAdapter


LABEL_IDS = {
    "stable": (5,),
    "worse": (6, 7),
    "improved": (8,),
    "new": (9, 10, 11),
    "resolved": (12, 13),
}


class ToyLM(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.embedding = nn.Embedding(32, 10)
        self.mix = nn.Linear(10, 10, bias=False)
        self.head = nn.Linear(10, 32, bias=False)
        self.last_batch = 0

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
        self.last_batch = inputs_embeds.shape[0]
        hidden = torch.tanh(
            torch.cumsum(
                self.mix(inputs_embeds) * attention_mask.unsqueeze(-1), dim=1
            )
        )
        return SimpleNamespace(logits=self.head(hidden))


def _system():
    torch.manual_seed(23)
    bundle = TokenBundle(
        tokens=torch.randn(2, 64, 7),
        token_types=torch.tensor([0] * 4 + [1] * 28 + [2] * 28 + [3] * 4),
        valid_mask=torch.ones(2, 64, dtype=torch.bool),
        assignment=torch.zeros(2, 1, 1),
    )
    projected = RelationProjector(7, 10)(bundle)
    model = ToyLM()
    adapter = TierCXRAdapter(model, 1, LABEL_IDS)
    prompt = torch.tensor(
        [[2, 3] + [1] * 64 + [4], [2, 3] + [1] * 64 + [4]]
    )
    return projected, model, adapter, prompt


def test_vectorized_candidate_scores_match_serial_at_toy_tolerance():
    projected, model, adapter, prompt = _system()
    serial = adapter.score_labels(prompt, projected)
    vectorized, audit = adapter.score_labels_vectorized(
        prompt, projected, return_audit=True
    )
    assert torch.allclose(vectorized, serial, atol=1e-6, rtol=1e-6)
    assert audit["vectorized_candidates"] is True
    assert model.last_batch == 10


def test_vectorized_scoring_compacts_right_padding():
    projected, _, adapter, prompt = _system()
    padded = torch.cat((prompt, torch.tensor([[14, 15], [16, 17]])), dim=1)
    attention = torch.cat(
        (torch.ones_like(prompt), torch.zeros(2, 2, dtype=torch.long)), dim=1
    )
    serial = adapter.score_labels(padded, projected, attention_mask=attention)
    vectorized = adapter.score_labels_vectorized(
        padded, projected, attention_mask=attention
    )
    assert torch.allclose(vectorized, serial, atol=1e-6, rtol=1e-6)
