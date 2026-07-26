from __future__ import annotations

from .hierarchical_temporal_tokens import TYPE_RESERVED
from .projector import RelationProjector


class TierTokenProjector(RelationProjector):
    """Six-type fixed-64 projector for TIER-CXR-VLM bundles."""

    def __init__(self, input_dim: int, hidden_size: int) -> None:
        super().__init__(
            input_dim=input_dim,
            hidden_size=hidden_size,
            token_budget=64,
            num_token_types=6,
            reserved_token_type=TYPE_RESERVED,
        )
