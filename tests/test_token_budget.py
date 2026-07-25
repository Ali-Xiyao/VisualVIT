import torch
import pytest

from visualvit.synthetic import make_synthetic_batch
from visualvit.tokenizer import (
    ENTITY_TOKENS,
    GLOBAL_TOKENS,
    RELATION_TOKENS,
    RESERVED_TOKENS,
    assemble_fixed_budget_tokens,
)


def test_exact_fixed_token_budget():
    synthetic = make_synthetic_batch(num_cases=2, seed=13)
    bundle = assemble_fixed_budget_tokens(synthetic.regions, synthetic.oracle)
    bundle.validate()

    assert bundle.tokens.shape[1] == 64
    counts = torch.bincount(bundle.token_types, minlength=4).tolist()
    assert counts == [
        GLOBAL_TOKENS,
        ENTITY_TOKENS,
        RELATION_TOKENS,
        RESERVED_TOKENS,
    ]
    # Four globals + 16 entity regions + 10 relations (8 prior + 2 births).
    assert bundle.valid_mask.sum(dim=1).tolist() == [30, 30]
    assert torch.all(bundle.valid_mask[:, -RESERVED_TOKENS:] == 0)


def test_overflow_is_a_hard_gate_until_global_allocator_exists():
    synthetic = make_synthetic_batch(
        num_cases=1,
        seed=37,
        persistent=14,
        deaths=1,
        births=0,
    )
    # 15 prior + 14 current = 29 entity inputs, exceeding the registered 28.
    with pytest.raises(ValueError, match="entity token budget exceeded"):
        assemble_fixed_budget_tokens(synthetic.regions, synthetic.oracle)
