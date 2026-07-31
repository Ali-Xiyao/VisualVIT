from __future__ import annotations

import torch
from torch import Tensor, nn

from .prta_gen import (
    PROGRESSION_CLASSES,
    ProgressionDecisionHead,
    exact64_semantic_mean_features,
)
from .schemas import ProjectedTokenBundle


EVIDENCE_POSITIONS = (60, 61, 62, 63)


class CausalDeltaEvidenceBottleneck(nn.Module):
    """Map a five-way temporal delta decision into four Qwen evidence tokens."""

    def __init__(
        self,
        *,
        feature_mean: Tensor,
        feature_std: Tensor,
        feature_mode: str = "delta",
        feature_width: int = 3840,
        head_hidden_width: int = 128,
        class_count: int = 5,
        bridge_hidden_width: int = 128,
        qwen_hidden_size: int = 2560,
        evidence_token_count: int = 4,
        temperature: float = 1.0,
    ) -> None:
        super().__init__()
        if feature_mode not in {"delta", "true_pair"}:
            raise ValueError("feature_mode must be delta or true_pair")
        if class_count != len(PROGRESSION_CLASSES):
            raise ValueError("CDEB must use the registered five classes")
        if evidence_token_count != len(EVIDENCE_POSITIONS):
            raise ValueError("CDEB requires exactly four evidence tokens")
        if temperature <= 0:
            raise ValueError("CDEB temperature must be positive")
        expected = (1, feature_width)
        if tuple(feature_mean.shape) != expected:
            raise ValueError(f"feature_mean must have shape {expected}")
        if tuple(feature_std.shape) != expected:
            raise ValueError(f"feature_std must have shape {expected}")
        if not bool(
            torch.isfinite(feature_mean).all()
            and torch.isfinite(feature_std).all()
        ):
            raise ValueError("CDEB normalization contains non-finite values")
        if bool(feature_std.le(0).any()):
            raise ValueError("CDEB feature_std must be positive")
        self.feature_mode = feature_mode
        self.feature_width = int(feature_width)
        self.class_count = int(class_count)
        self.qwen_hidden_size = int(qwen_hidden_size)
        self.evidence_token_count = int(evidence_token_count)
        self.temperature = float(temperature)
        self.register_buffer("feature_mean", feature_mean.float().clone())
        self.register_buffer("feature_std", feature_std.float().clone())
        self.decision_head = ProgressionDecisionHead(
            input_width=feature_width,
            hidden_width=head_hidden_width,
            class_count=class_count,
        )
        self.evidence_bridge = nn.Sequential(
            nn.Linear(class_count, bridge_hidden_width),
            nn.GELU(),
            nn.Linear(
                bridge_hidden_width,
                evidence_token_count * qwen_hidden_size,
            ),
        )
        self.evidence_norm = nn.LayerNorm(qwen_hidden_size)

    def decision_features(
        self, true_tokens: Tensor, current_tokens: Tensor
    ) -> Tensor:
        true_features = exact64_semantic_mean_features(true_tokens.float())
        if self.feature_mode == "true_pair":
            features = true_features
        else:
            current_features = exact64_semantic_mean_features(
                current_tokens.float()
            )
            features = true_features - current_features
        if tuple(features.shape[1:]) != (self.feature_width,):
            raise ValueError("CDEB decision feature-width drift")
        return (features - self.feature_mean) / self.feature_std

    def forward(
        self, true_tokens: Tensor, current_tokens: Tensor
    ) -> tuple[Tensor, Tensor, Tensor]:
        features = self.decision_features(true_tokens, current_tokens)
        logits = self.decision_head(features)
        distribution = torch.softmax(logits / self.temperature, dim=-1)
        evidence = self.evidence_bridge(distribution).view(
            len(distribution),
            self.evidence_token_count,
            self.qwen_hidden_size,
        )
        evidence = self.evidence_norm(evidence)
        if not bool(
            torch.isfinite(logits).all()
            and torch.isfinite(distribution).all()
            and torch.isfinite(evidence).all()
        ):
            raise FloatingPointError("CDEB output is non-finite")
        return logits, distribution, evidence


def inject_cdeb_evidence(
    projected: ProjectedTokenBundle,
    evidence: Tensor,
    *,
    enabled: bool,
) -> ProjectedTokenBundle:
    """Replace only the four registered reserve embeddings with evidence."""

    projected.validate(token_budget=64)
    expected = (
        projected.embeddings.shape[0],
        len(EVIDENCE_POSITIONS),
        projected.embeddings.shape[2],
    )
    if tuple(evidence.shape) != expected:
        raise ValueError(f"CDEB evidence must have shape {expected}")
    if not bool(torch.isfinite(evidence).all()):
        raise FloatingPointError("CDEB evidence is non-finite")
    audit = dict(projected.audit)
    audit.update(
        {
            "cdeb_evidence_enabled": bool(enabled),
            "cdeb_evidence_positions": EVIDENCE_POSITIONS,
            "cdeb_evidence_token_count": len(EVIDENCE_POSITIONS),
            "qualified_positions_preserved": (0, 60),
        }
    )
    if not enabled:
        output = ProjectedTokenBundle(
            embeddings=projected.embeddings,
            token_types=projected.token_types,
            valid_mask=projected.valid_mask,
            attention_mask=projected.attention_mask,
            position_ids=projected.position_ids,
            audit=audit,
        )
        output.validate(token_budget=64)
        return output

    embeddings = projected.embeddings.clone()
    embeddings[:, EVIDENCE_POSITIONS] = evidence.to(
        device=embeddings.device, dtype=embeddings.dtype
    )
    valid_mask = projected.valid_mask.clone()
    valid_mask[:, EVIDENCE_POSITIONS] = True
    batch = embeddings.shape[0]
    audit.update(
        {
            "logical_valid_count": torch.full(
                (batch,), 64, dtype=torch.long, device=embeddings.device
            ),
            "active_count": torch.full(
                (batch,), 64, dtype=torch.long, device=embeddings.device
            ),
            "neutral_count": torch.zeros(
                batch, dtype=torch.long, device=embeddings.device
            ),
            "neutral_mask": torch.zeros(
                (batch, 64), dtype=torch.bool, device=embeddings.device
            ),
        }
    )
    output = ProjectedTokenBundle(
        embeddings=embeddings,
        token_types=projected.token_types,
        valid_mask=valid_mask,
        attention_mask=projected.attention_mask,
        position_ids=projected.position_ids,
        audit=audit,
    )
    output.validate(token_budget=64)
    return output
