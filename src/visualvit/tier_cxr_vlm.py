from __future__ import annotations

from typing import Any

import torch
from torch import Tensor

from .qwen_adapter import FrozenVLMAdapter, PROGRESSION_LABELS
from .schemas import ProjectedTokenBundle


class TierCXRAdapter(FrozenVLMAdapter):
    """R32 adapter extension with expanded-batch candidate scoring."""

    @staticmethod
    def _repeat_projected(
        projected: ProjectedTokenBundle, repeats: int
    ) -> ProjectedTokenBundle:
        if repeats <= 0:
            raise ValueError("repeats must be positive")
        projected.validate()
        return ProjectedTokenBundle(
            embeddings=projected.embeddings.repeat_interleave(repeats, dim=0),
            token_types=projected.token_types,
            valid_mask=projected.valid_mask.repeat_interleave(repeats, dim=0),
            attention_mask=projected.attention_mask.repeat_interleave(
                repeats, dim=0
            ),
            position_ids=projected.position_ids.repeat_interleave(
                repeats, dim=1
            ),
            audit=dict(projected.audit),
        )

    def score_labels_vectorized(
        self,
        input_ids: Tensor,
        projected: ProjectedTokenBundle,
        *,
        attention_mask: Tensor | None = None,
        return_audit: bool = False,
        **model_kwargs: Any,
    ) -> Tensor | tuple[Tensor, dict[str, Any]]:
        """Score all five labels in one sample-major expanded-batch forward."""

        self._validate_model_kwargs(model_kwargs)
        if input_ids.ndim != 2 or input_ids.shape[1] == 0:
            raise ValueError("input_ids must be a non-empty [B, L] tensor")
        placeholder_mask = self._placeholder_mask(input_ids)
        if attention_mask is None:
            prompt_attention = torch.ones_like(input_ids, dtype=torch.long)
        elif tuple(attention_mask.shape) != tuple(input_ids.shape):
            raise ValueError("attention_mask must match input_ids")
        else:
            prompt_attention = attention_mask.to(
                device=input_ids.device, dtype=torch.long
            )
        if not bool(((prompt_attention == 0) | (prompt_attention == 1)).all()):
            raise ValueError("attention_mask must contain only zero or one")
        if not bool(prompt_attention[placeholder_mask].eq(1).all()):
            raise ValueError(
                "all 64 relation placeholders must have physical attention one"
            )

        batch_size = input_ids.shape[0]
        label_count = len(PROGRESSION_LABELS)
        prompt_lengths = prompt_attention.sum(dim=1)
        if bool(prompt_lengths.eq(0).any()):
            raise ValueError("each prompt must contain at least one attended token")
        candidate_lengths = self.label_lengths.to(input_ids.device)
        expanded_prompt_lengths = prompt_lengths.repeat_interleave(label_count)
        expanded_candidate_lengths = candidate_lengths.repeat(batch_size)
        full_lengths = expanded_prompt_lengths + expanded_candidate_lengths
        full_length = int(full_lengths.max().item())
        expanded_batch = batch_size * label_count
        full_input_ids = torch.zeros(
            expanded_batch,
            full_length,
            dtype=input_ids.dtype,
            device=input_ids.device,
        )
        full_attention = torch.zeros(
            expanded_batch,
            full_length,
            dtype=prompt_attention.dtype,
            device=prompt_attention.device,
        )
        max_candidate_length = int(candidate_lengths.max().item())
        prediction_positions = torch.zeros(
            expanded_batch,
            max_candidate_length,
            dtype=torch.long,
            device=input_ids.device,
        )
        candidate_targets = torch.zeros_like(prediction_positions)
        candidate_mask = torch.zeros_like(prediction_positions, dtype=torch.bool)

        for sample_index in range(batch_size):
            prompt_ids = input_ids[
                sample_index, prompt_attention[sample_index].bool()
            ]
            prompt_length = int(prompt_ids.numel())
            for label_index in range(label_count):
                row_index = sample_index * label_count + label_index
                label_length = int(candidate_lengths[label_index].item())
                label_ids = self.label_token_ids[
                    label_index, :label_length
                ].to(input_ids.device)
                full_input_ids[row_index, :prompt_length] = prompt_ids
                full_input_ids[
                    row_index, prompt_length : prompt_length + label_length
                ] = label_ids
                full_attention[
                    row_index, : prompt_length + label_length
                ] = 1
                prediction_positions[row_index, :label_length] = torch.arange(
                    prompt_length - 1,
                    prompt_length + label_length - 1,
                    device=input_ids.device,
                )
                candidate_targets[row_index, :label_length] = label_ids
                candidate_mask[row_index, :label_length] = True

        output = self.forward(
            full_input_ids,
            self._repeat_projected(projected, label_count),
            attention_mask=full_attention,
            **model_kwargs,
        )
        logits = self._extract_logits(output)
        if logits.shape[:2] != (expanded_batch, full_length):
            raise ValueError(
                "causal LM logits must preserve the expanded batch and sequence"
            )
        prediction_logits = logits.gather(
            1,
            prediction_positions.unsqueeze(-1).expand(
                -1, -1, logits.shape[-1]
            ),
        )
        if int(candidate_targets.max().item()) >= prediction_logits.shape[-1]:
            raise ValueError("label token ID exceeds the causal LM vocabulary")
        log_probabilities = prediction_logits.float().log_softmax(dim=-1)
        token_log_likelihood = log_probabilities.gather(
            -1, candidate_targets.unsqueeze(-1)
        ).squeeze(-1)
        normalized = (token_log_likelihood * candidate_mask).sum(
            dim=-1
        ) / expanded_candidate_lengths
        scores = normalized.view(batch_size, label_count)
        if not return_audit:
            return scores
        return scores, {
            "labels": PROGRESSION_LABELS,
            "label_lengths": self.label_lengths.detach().clone(),
            "normalization": "mean_token_log_likelihood",
            "placeholder_count": placeholder_mask.sum(dim=1).detach(),
            "pixel_inputs_used": False,
            "model_frozen": self.freeze_audit()["all_frozen"],
            "vectorized_candidates": True,
            "vlm_forward_count": 1,
        }
