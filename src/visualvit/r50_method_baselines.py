from __future__ import annotations

import torch
from torch import nn
import torch.nn.functional as F


INVERSION_INDEX = (0, 2, 1, 4, 3)


def invert_class_tensor(values: torch.Tensor) -> torch.Tensor:
    if values.shape[-1] != len(INVERSION_INDEX):
        raise ValueError("R50 inversion expects exactly five classes")
    index = torch.tensor(INVERSION_INDEX, device=values.device)
    return values.index_select(-1, index)


def siamese_signed_abs_features(
    prior_cls: torch.Tensor,
    current_cls: torch.Tensor,
) -> torch.Tensor:
    if prior_cls.shape != current_cls.shape or prior_cls.ndim != 2:
        raise ValueError("R50 Siamese features require matching [B,D] tensors")
    prior = F.normalize(prior_cls.float(), dim=-1)
    current = F.normalize(current_cls.float(), dim=-1)
    signed = current - prior
    return F.normalize(
        torch.cat((prior, current, signed, signed.abs()), dim=-1),
        dim=-1,
    )


def tila_bice_tcl_loss(
    forward_logits: torch.Tensor,
    reversed_logits: torch.Tensor,
    targets: torch.Tensor,
    *,
    tcl_weight: float,
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    if forward_logits.shape != reversed_logits.shape:
        raise ValueError("R50 TILA forward/reversed logits differ in shape")
    reversed_targets = torch.tensor(
        INVERSION_INDEX, device=targets.device, dtype=torch.long
    ).index_select(0, targets)
    bice = 0.5 * (
        F.cross_entropy(forward_logits, targets)
        + F.cross_entropy(reversed_logits, reversed_targets)
    )
    forward_probabilities = F.softmax(forward_logits, dim=-1)
    adjusted_reverse = invert_class_tensor(
        F.softmax(reversed_logits, dim=-1)
    )
    tcl = (
        (forward_probabilities - adjusted_reverse)
        .square()
        .sum(dim=-1)
        .mean()
    )
    total = bice + float(tcl_weight) * tcl
    return total, {"bice": bice, "tcl": tcl}


def tila_combined_probabilities(
    forward_logits: torch.Tensor,
    reversed_logits: torch.Tensor,
) -> torch.Tensor:
    if forward_logits.shape != reversed_logits.shape:
        raise ValueError("R50 TILA forward/reversed logits differ in shape")
    return 0.5 * (
        F.softmax(forward_logits, dim=-1)
        + invert_class_tensor(F.softmax(reversed_logits, dim=-1))
    )


class TACTemporalFusionAdapted(nn.Module):
    """Libra TAC temporal-fusion block adapted to one cached encoder layer.

    The original 12-layer RAD-DINO LFE is intentionally omitted because the
    R50 cache contains one frozen BiomedCLIP Block-8 feature layer. The
    current/prior self-attention, current-to-prior cross-attention, residual
    norms, transition MLP, and four-layer output MLP follow Libra's TAC code.
    """

    def __init__(
        self,
        *,
        width: int = 768,
        heads: int = 8,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        if width <= 0 or heads <= 0 or width % heads:
            raise ValueError("invalid R50 TAC width/head configuration")
        self.width = width
        attention_kwargs = {
            "embed_dim": width,
            "num_heads": heads,
            "batch_first": True,
            "add_bias_kv": True,
        }
        self.current_self_attention = nn.MultiheadAttention(**attention_kwargs)
        self.prior_self_attention = nn.MultiheadAttention(**attention_kwargs)
        self.cross_attention = nn.MultiheadAttention(**attention_kwargs)
        self.norm1 = nn.LayerNorm(width)
        self.norm2 = nn.LayerNorm(width)
        self.norm3 = nn.LayerNorm(width)
        self.norm4 = nn.LayerNorm(width)
        self.attention_mlp = nn.Sequential(
            nn.Linear(width, width),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(width, width),
            nn.Dropout(dropout),
        )
        final_layers: list[nn.Module] = []
        for index in range(4):
            final_layers.append(nn.Linear(width, width))
            if index < 3:
                final_layers.append(nn.GELU())
        self.final_mlp = nn.Sequential(*final_layers)
        self.dropout_current = nn.Dropout(dropout)
        self.dropout_prior = nn.Dropout(dropout)
        self.dropout_cross = nn.Dropout(dropout)

    def forward(
        self,
        prior_features: torch.Tensor,
        current_features: torch.Tensor,
    ) -> torch.Tensor:
        if (
            prior_features.shape != current_features.shape
            or prior_features.ndim != 3
            or prior_features.shape[-1] != self.width
        ):
            raise ValueError(
                "R50 TAC requires matching prior/current [B,N,width] tensors"
            )
        current_original = current_features
        current_self = self.current_self_attention(
            current_features, current_features, current_features
        )[0]
        prior_self = self.prior_self_attention(
            prior_features, prior_features, prior_features
        )[0]
        current = self.norm1(
            current_features + self.dropout_current(current_self)
        )
        prior = self.norm2(prior_features + self.dropout_prior(prior_self))
        cross = self.cross_attention(current, prior, prior)[0]
        combined = self.norm3(current + self.dropout_cross(cross))
        output = self.norm4(current_original + self.attention_mlp(combined))
        return F.normalize(self.final_mlp(output).mean(dim=1), dim=-1)
