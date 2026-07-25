from __future__ import annotations

import torch
from torch import Tensor, nn

from .schemas import ProjectedTokenBundle, TokenBundle


class RelationProjector(nn.Module):
    """Project a fixed token bundle into a frozen language model's width.

    Logical padding and reserved slots are kept in the physical 64-token
    sequence.  They all receive the same learned neutral embedding; metadata
    is applied only to logical, non-reserved tokens.
    """

    def __init__(
        self,
        input_dim: int,
        hidden_size: int,
        *,
        token_budget: int = 64,
        num_token_types: int = 4,
        anatomy_vocab_size: int = 512,
        temporal_vocab_size: int = 2,
        reserved_token_type: int = 3,
    ) -> None:
        super().__init__()
        if input_dim <= 0 or hidden_size <= 0:
            raise ValueError("input_dim and hidden_size must be positive")
        if token_budget <= 0:
            raise ValueError("token_budget must be positive")
        if num_token_types <= 0:
            raise ValueError("num_token_types must be positive")
        if not 0 <= reserved_token_type < num_token_types:
            raise ValueError("reserved_token_type must index a token type")
        if anatomy_vocab_size <= 0 or temporal_vocab_size <= 0:
            raise ValueError("metadata vocabulary sizes must be positive")

        self.input_dim = input_dim
        self.hidden_size = hidden_size
        self.token_budget = token_budget
        self.anatomy_vocab_size = anatomy_vocab_size
        self.temporal_vocab_size = temporal_vocab_size
        self.reserved_token_type = reserved_token_type

        self.feature_projection = nn.Sequential(
            nn.Linear(input_dim, hidden_size),
            nn.GELU(),
            nn.Linear(hidden_size, hidden_size),
        )
        self.token_type_embeddings = nn.Embedding(num_token_types, hidden_size)
        # Index zero is the unknown/not-applicable sentinel. Non-negative
        # metadata IDs are shifted by one before lookup.
        self.anatomy_embeddings = nn.Embedding(anatomy_vocab_size + 1, hidden_size)
        self.temporal_embeddings = nn.Embedding(temporal_vocab_size + 1, hidden_size)
        self.confidence_projection = nn.Linear(1, hidden_size, bias=False)
        self.slot_mass_projection = nn.Linear(1, hidden_size, bias=False)
        self.output_norm = nn.LayerNorm(hidden_size)
        self.neutral_embedding = nn.Parameter(torch.empty(hidden_size))
        nn.init.normal_(self.neutral_embedding, mean=0.0, std=0.02)

    @staticmethod
    def _metadata(bundle: TokenBundle, name: str) -> Tensor | None:
        return getattr(bundle, name, None)

    @staticmethod
    def _check_metadata_shape(name: str, value: Tensor, shape: tuple[int, int]) -> None:
        if tuple(value.shape) != shape:
            raise ValueError(
                f"{name} must have shape {shape}, got {tuple(value.shape)}"
            )

    @staticmethod
    def _categorical_indices(
        name: str,
        value: Tensor,
        *,
        vocab_size: int,
        shape: tuple[int, int],
        device: torch.device,
    ) -> Tensor:
        RelationProjector._check_metadata_shape(name, value, shape)
        value = value.to(device=device, dtype=torch.long)
        if bool((value >= vocab_size).any()):
            largest = int(value.max().item())
            raise ValueError(
                f"{name} contains ID {largest}, outside [0, {vocab_size - 1}]"
            )
        # All negative sentinels map to the shared unknown embedding.
        return torch.where(value >= 0, value + 1, torch.zeros_like(value))

    @staticmethod
    def _continuous_metadata(
        name: str,
        value: Tensor,
        *,
        shape: tuple[int, int],
        reference: Tensor,
    ) -> Tensor:
        RelationProjector._check_metadata_shape(name, value, shape)
        value = value.to(device=reference.device, dtype=reference.dtype)
        if not bool(torch.isfinite(value).all()):
            raise ValueError(f"{name} contains non-finite values")
        return value.unsqueeze(-1)

    def forward(self, bundle: TokenBundle) -> ProjectedTokenBundle:
        bundle.validate(token_budget=self.token_budget)
        if bundle.tokens.shape[-1] != self.input_dim:
            raise ValueError(
                f"expected token feature dimension {self.input_dim}, "
                f"got {bundle.tokens.shape[-1]}"
            )

        tokens = bundle.tokens
        batch_size, token_budget, _ = tokens.shape
        shape = (batch_size, token_budget)
        token_types = bundle.token_types.to(device=tokens.device, dtype=torch.long)
        if token_types.ndim == 2:
            if not bool((token_types == token_types[:1]).all()):
                raise ValueError(
                    "batched token_types must share one layout for projection"
                )
            token_types = token_types[0]
        if bool((token_types < 0).any()) or bool(
            (token_types >= self.token_type_embeddings.num_embeddings).any()
        ):
            raise ValueError("token_types contains an out-of-range type ID")

        projected = self.feature_projection(tokens)
        projected = projected + self.token_type_embeddings(token_types).unsqueeze(0)
        metadata_fields: list[str] = []

        anatomy_ids = self._metadata(bundle, "anatomy_ids")
        if anatomy_ids is not None:
            anatomy_indices = self._categorical_indices(
                "anatomy_ids",
                anatomy_ids,
                vocab_size=self.anatomy_vocab_size,
                shape=shape,
                device=tokens.device,
            )
            projected = projected + self.anatomy_embeddings(anatomy_indices)
            metadata_fields.append("anatomy_ids")

        temporal_ids = self._metadata(bundle, "temporal_ids")
        if temporal_ids is not None:
            temporal_indices = self._categorical_indices(
                "temporal_ids",
                temporal_ids,
                vocab_size=self.temporal_vocab_size,
                shape=shape,
                device=tokens.device,
            )
            projected = projected + self.temporal_embeddings(temporal_indices)
            metadata_fields.append("temporal_ids")

        confidence = self._metadata(bundle, "confidence")
        if confidence is not None:
            confidence_values = self._continuous_metadata(
                "confidence", confidence, shape=shape, reference=tokens
            )
            projected = projected + self.confidence_projection(confidence_values)
            metadata_fields.append("confidence")

        slot_mass = self._metadata(bundle, "slot_mass")
        if slot_mass is not None:
            slot_mass_values = self._continuous_metadata(
                "slot_mass", slot_mass, shape=shape, reference=tokens
            )
            projected = projected + self.slot_mass_projection(slot_mass_values)
            metadata_fields.append("slot_mass")

        projected = self.output_norm(projected)
        shared_types = token_types.view(1, token_budget).expand(batch_size, -1)
        logical_valid = bundle.valid_mask.to(device=tokens.device)
        active_mask = logical_valid & (shared_types != self.reserved_token_type)
        neutral = self.neutral_embedding.to(dtype=projected.dtype).view(1, 1, -1)
        embeddings = torch.where(active_mask.unsqueeze(-1), projected, neutral)

        attention_mask = torch.ones(shape, dtype=torch.long, device=tokens.device)
        one_dimensional_positions = (
            torch.arange(token_budget, dtype=torch.long, device=tokens.device)
            .view(1, 1, token_budget)
            .expand(3, batch_size, -1)
        )
        neutral_mask = ~active_mask
        audit = {
            "token_budget": token_budget,
            "logical_valid_count": logical_valid.sum(dim=1).detach(),
            "active_count": active_mask.sum(dim=1).detach(),
            "neutral_count": neutral_mask.sum(dim=1).detach(),
            "neutral_mask": neutral_mask.detach(),
            "neutral_is_shared": True,
            "physical_attention_all_ones": True,
            "position_axes_equal": True,
            "metadata_fields_embedded": tuple(metadata_fields),
            # Source IDs are provenance/audit metadata, never model features.
            "source_ids_embedded": False,
        }
        output = ProjectedTokenBundle(
            embeddings=embeddings,
            token_types=token_types,
            valid_mask=logical_valid,
            attention_mask=attention_mask,
            position_ids=one_dimensional_positions,
            audit=audit,
        )
        output.validate(token_budget=self.token_budget)
        return output
