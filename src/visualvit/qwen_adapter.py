from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import torch
from torch import Tensor, nn

from .schemas import ProjectedTokenBundle


PROGRESSION_LABELS = ("stable", "worse", "improved", "new", "resolved")
_FORBIDDEN_IMAGE_KEY_PARTS = ("pixel", "image", "video")
_FORBIDDEN_MULTIMODAL_KEYS = {
    "deepstack_visual_embeds",
    "mm_token_type_ids",
    "visual_pos_masks",
}
_RESERVED_FORWARD_KEYS = {
    "input_ids",
    "inputs_embeds",
    "attention_mask",
    "position_ids",
    "past_key_values",
    "cache_position",
    "use_cache",
    "logits_to_keep",
}


def freeze_module(module: nn.Module) -> nn.Module:
    """Freeze a module without disabling input gradients through its operations."""

    module.requires_grad_(False)
    module.eval()
    return module


def frozen_parameter_audit(module: nn.Module) -> dict[str, Any]:
    parameters = list(module.named_parameters())
    trainable_names = [name for name, value in parameters if value.requires_grad]
    parameter_count = sum(value.numel() for _, value in parameters)
    trainable_parameter_count = sum(
        value.numel() for _, value in parameters if value.requires_grad
    )
    return {
        "parameter_count": parameter_count,
        "parameter_tensor_count": len(parameters),
        "trainable_parameter_count": trainable_parameter_count,
        "trainable_parameter_names": tuple(trainable_names),
        "all_frozen": not trainable_names,
        "training": module.training,
    }


def tokenize_progression_labels(
    tokenizer: Any,
    *,
    label_prefix: str = "",
) -> dict[str, tuple[int, ...]]:
    """Tokenize the five fixed labels without importing Transformers."""

    result: dict[str, tuple[int, ...]] = {}
    for label in PROGRESSION_LABELS:
        encoded = tokenizer(f"{label_prefix}{label}", add_special_tokens=False)
        token_ids = encoded["input_ids"] if isinstance(encoded, Mapping) else encoded
        if isinstance(token_ids, Tensor):
            token_ids = token_ids.detach().cpu().tolist()
        if token_ids and isinstance(token_ids[0], list):
            if len(token_ids) != 1:
                raise ValueError("tokenizer returned more than one sequence per label")
            token_ids = token_ids[0]
        normalized = tuple(int(token_id) for token_id in token_ids)
        if not normalized:
            raise ValueError(f"label {label!r} tokenized to an empty sequence")
        result[label] = normalized
    return result


def text_like_position_ids(attention_mask: Tensor) -> Tensor:
    """Return equal three-axis text positions for Qwen-style M-RoPE."""

    if attention_mask.ndim != 2:
        raise ValueError("attention_mask must have shape [B, L]")
    positions = attention_mask.to(torch.long).cumsum(dim=-1) - 1
    positions = positions.clamp_min(0)
    return positions.unsqueeze(0).expand(3, -1, -1).contiguous()


class FrozenVLMAdapter(nn.Module):
    """Inject exactly 64 projected relation tokens into a frozen causal LM."""

    def __init__(
        self,
        model: nn.Module,
        placeholder_token_id: int,
        label_token_ids: Mapping[str, Sequence[int] | Tensor] | None = None,
        *,
        tokenizer: Any | None = None,
        label_prefix: str = "",
        token_budget: int = 64,
    ) -> None:
        super().__init__()
        if token_budget <= 0:
            raise ValueError("token_budget must be positive")
        if placeholder_token_id < 0:
            raise ValueError("placeholder_token_id must be non-negative")
        if label_token_ids is None:
            if tokenizer is None:
                raise ValueError("provide label_token_ids or tokenizer")
            label_token_ids = tokenize_progression_labels(
                tokenizer, label_prefix=label_prefix
            )
        if tuple(label_token_ids.keys()) != PROGRESSION_LABELS:
            missing = [
                label for label in PROGRESSION_LABELS if label not in label_token_ids
            ]
            extras = [
                label for label in label_token_ids if label not in PROGRESSION_LABELS
            ]
            if missing or extras:
                raise ValueError(
                    "label_token_ids must contain exactly "
                    f"{PROGRESSION_LABELS}; missing={missing}, extras={extras}"
                )

        normalized: list[Tensor] = []
        for label in PROGRESSION_LABELS:
            ids = torch.as_tensor(label_token_ids[label], dtype=torch.long).flatten()
            if ids.numel() == 0:
                raise ValueError(f"label {label!r} must have at least one token")
            if bool((ids < 0).any()):
                raise ValueError("label token IDs must be non-negative")
            if bool(ids.eq(placeholder_token_id).any()):
                raise ValueError(
                    "label token IDs must not contain the placeholder token"
                )
            normalized.append(ids)
        max_length = max(ids.numel() for ids in normalized)
        padded = torch.zeros(len(PROGRESSION_LABELS), max_length, dtype=torch.long)
        lengths = torch.empty(len(PROGRESSION_LABELS), dtype=torch.long)
        for index, ids in enumerate(normalized):
            padded[index, : ids.numel()] = ids
            lengths[index] = ids.numel()

        self.model = freeze_module(model)
        self.placeholder_token_id = int(placeholder_token_id)
        self.token_budget = token_budget
        self.register_buffer("label_token_ids", padded, persistent=True)
        self.register_buffer("label_lengths", lengths, persistent=True)

    @classmethod
    def from_tokenizer(
        cls,
        model: nn.Module,
        tokenizer: Any,
        placeholder_token_id: int,
        *,
        label_prefix: str = "",
        token_budget: int = 64,
    ) -> FrozenVLMAdapter:
        return cls(
            model,
            placeholder_token_id,
            tokenizer=tokenizer,
            label_prefix=label_prefix,
            token_budget=token_budget,
        )

    def train(self, mode: bool = True) -> FrozenVLMAdapter:
        super().train(mode)
        # ``nn.Module.train`` recurses into children; the VLM must remain in
        # deterministic inference mode even while a surrounding projector trains.
        self.model.eval()
        return self

    def freeze_audit(self) -> dict[str, Any]:
        audit = frozen_parameter_audit(self.model)
        audit["pixel_path_available"] = False
        return audit

    @staticmethod
    def _validate_model_kwargs(model_kwargs: Mapping[str, Any]) -> None:
        forbidden = sorted(
            {
                key
                for key in model_kwargs
                if any(part in key.lower() for part in _FORBIDDEN_IMAGE_KEY_PARTS)
            }
            | _FORBIDDEN_MULTIMODAL_KEYS.intersection(model_kwargs)
        )
        if forbidden:
            raise ValueError(
                "relation-token path forbids pixel/image/video or multimodal inputs: "
                + ", ".join(sorted(forbidden))
            )
        reserved = sorted(_RESERVED_FORWARD_KEYS.intersection(model_kwargs))
        if reserved:
            raise ValueError(
                "adapter constructs these model inputs explicitly: "
                + ", ".join(reserved)
            )

    def _placeholder_mask(self, input_ids: Tensor) -> Tensor:
        if input_ids.ndim != 2:
            raise ValueError("input_ids must have shape [B, L]")
        mask = input_ids.eq(self.placeholder_token_id)
        counts = mask.sum(dim=1)
        expected = torch.full_like(counts, self.token_budget)
        if not bool(torch.equal(counts, expected)):
            raise ValueError(
                f"each input row must contain exactly {self.token_budget} placeholders; "
                f"got {counts.detach().cpu().tolist()}"
            )
        return mask

    def _input_embedding_table(self) -> nn.Module:
        getter = getattr(self.model, "get_input_embeddings", None)
        if getter is None or not callable(getter):
            raise TypeError("model must provide get_input_embeddings()")
        table = getter()
        if table is None or not callable(table):
            raise TypeError("get_input_embeddings() must return a callable module")
        return table

    def replace_placeholders(
        self,
        input_ids: Tensor,
        projected: ProjectedTokenBundle,
    ) -> tuple[Tensor, Tensor]:
        """Return ordinary text embeddings with exactly 64 positions replaced."""

        projected.validate(token_budget=self.token_budget)
        placeholder_mask = self._placeholder_mask(input_ids)
        if input_ids.shape[0] != projected.embeddings.shape[0]:
            raise ValueError("input_ids and projected bundle batch sizes must match")
        if not bool(projected.attention_mask.eq(1).all()):
            raise ValueError("projected physical attention_mask must be all ones")
        if not bool(
            torch.equal(projected.position_ids[0], projected.position_ids[1])
            and torch.equal(projected.position_ids[0], projected.position_ids[2])
        ):
            raise ValueError("projected text-like position axes must be equal")

        embedding_table = self._input_embedding_table()
        ordinary_embeddings = embedding_table(input_ids)
        if ordinary_embeddings.ndim != 3:
            raise ValueError("input embedding table must return [B, L, H]")
        if ordinary_embeddings.shape[-1] != projected.embeddings.shape[-1]:
            raise ValueError("projected and text embedding widths must match")

        relation_indices = placeholder_mask.to(torch.long).cumsum(dim=1) - 1
        relation_indices = relation_indices.clamp_min(0)
        gather_index = relation_indices.unsqueeze(-1).expand(
            -1, -1, projected.embeddings.shape[-1]
        )
        replacement_source = projected.embeddings.to(
            device=ordinary_embeddings.device, dtype=ordinary_embeddings.dtype
        )
        replacements = replacement_source.gather(dim=1, index=gather_index)
        injected = torch.where(
            placeholder_mask.to(ordinary_embeddings.device).unsqueeze(-1),
            replacements,
            ordinary_embeddings,
        )
        return injected, placeholder_mask

    def inject(
        self,
        input_ids: Tensor,
        projected: ProjectedTokenBundle,
    ) -> tuple[Tensor, Tensor]:
        """Public shorthand for exact placeholder embedding replacement."""

        return self.replace_placeholders(input_ids, projected)

    def prepare_inputs(
        self,
        input_ids: Tensor,
        projected: ProjectedTokenBundle,
        *,
        attention_mask: Tensor | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        inputs_embeds, placeholder_mask = self.replace_placeholders(
            input_ids, projected
        )
        if attention_mask is None:
            attention_mask = torch.ones_like(input_ids, dtype=torch.long)
        elif tuple(attention_mask.shape) != tuple(input_ids.shape):
            raise ValueError("attention_mask must match input_ids")
        else:
            attention_mask = attention_mask.to(
                device=input_ids.device, dtype=torch.long
            )
        if not bool(((attention_mask == 0) | (attention_mask == 1)).all()):
            raise ValueError("attention_mask must contain only zero or one")
        if not bool(attention_mask[placeholder_mask].eq(1).all()):
            raise ValueError(
                "all 64 relation placeholders must have physical attention one"
            )
        position_ids = text_like_position_ids(attention_mask)
        model_inputs = {
            "inputs_embeds": inputs_embeds,
            "attention_mask": attention_mask,
            "position_ids": position_ids,
            # Qwen3-VL defaults to a mutable DynamicCache. Label scoring performs
            # five independent full-sequence passes, so cache creation is both
            # wasteful and a potential cross-candidate state leak.
            "use_cache": False,
            # Qwen3-VL can truncate returned logits. Full logits are required to
            # gather every candidate-token prediction position exactly.
            "logits_to_keep": 0,
        }
        audit = {
            "placeholder_mask": placeholder_mask.detach(),
            "placeholder_count": placeholder_mask.sum(dim=1).detach(),
            "physical_attention_all_ones_at_placeholders": True,
            "position_axes_equal": True,
            "position_ids_shape": tuple(position_ids.shape),
            "pixel_inputs_used": False,
            "use_cache": False,
            "logits_to_keep": 0,
            "model_frozen": self.freeze_audit()["all_frozen"],
        }
        return model_inputs, audit

    def forward(
        self,
        input_ids: Tensor,
        projected: ProjectedTokenBundle,
        *,
        attention_mask: Tensor | None = None,
        **model_kwargs: Any,
    ) -> Any:
        self._validate_model_kwargs(model_kwargs)
        model_inputs, _ = self.prepare_inputs(
            input_ids, projected, attention_mask=attention_mask
        )
        return self.model(**model_inputs, **model_kwargs)

    @staticmethod
    def _extract_logits(output: Any) -> Tensor:
        if hasattr(output, "logits"):
            logits = output.logits
        elif isinstance(output, Mapping) and "logits" in output:
            logits = output["logits"]
        elif isinstance(output, tuple) and output:
            logits = output[0]
        else:
            raise TypeError("causal LM output must expose logits")
        if not isinstance(logits, Tensor) or logits.ndim != 3:
            raise ValueError("causal LM logits must have shape [B, L, V]")
        return logits

    def score_labels(
        self,
        input_ids: Tensor,
        projected: ProjectedTokenBundle,
        *,
        attention_mask: Tensor | None = None,
        return_audit: bool = False,
        **model_kwargs: Any,
    ) -> Tensor | tuple[Tensor, dict[str, Any]]:
        """Score fixed labels by mean autoregressive token log likelihood."""

        self._validate_model_kwargs(model_kwargs)
        if input_ids.ndim != 2 or input_ids.shape[1] == 0:
            raise ValueError("input_ids must be a non-empty [B, L] tensor")
        # Validate the prompt before labels are appended, so a label token equal
        # to the placeholder ID cannot change the replacement count.
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

        batch_size, _ = input_ids.shape
        prompt_lengths = prompt_attention.sum(dim=1)
        if bool(prompt_lengths.eq(0).any()):
            raise ValueError("each prompt must contain at least one attended token")
        scores: list[Tensor] = []
        for label_index in range(len(PROGRESSION_LABELS)):
            label_length = int(self.label_lengths[label_index].item())
            label_ids = self.label_token_ids[label_index, :label_length].to(
                device=input_ids.device
            )
            candidate_ids = label_ids.view(1, -1).expand(batch_size, -1)
            # Pack attended prompt tokens before appending the candidate. This
            # makes scoring correct for ordinary right-padded prompt batches:
            # the first label token is predicted by the final real prompt token,
            # never by a padding position.
            full_lengths = prompt_lengths + label_length
            full_length = int(full_lengths.max().item())
            full_input_ids = torch.full(
                (batch_size, full_length),
                fill_value=int(label_ids[0].item()),
                dtype=input_ids.dtype,
                device=input_ids.device,
            )
            full_attention = torch.zeros(
                batch_size,
                full_length,
                dtype=prompt_attention.dtype,
                device=prompt_attention.device,
            )
            prediction_positions = torch.empty(
                batch_size,
                label_length,
                dtype=torch.long,
                device=input_ids.device,
            )
            for batch_index in range(batch_size):
                prompt_ids = input_ids[
                    batch_index, prompt_attention[batch_index].bool()
                ]
                prompt_length = int(prompt_ids.numel())
                full_input_ids[batch_index, :prompt_length] = prompt_ids
                full_input_ids[
                    batch_index, prompt_length : prompt_length + label_length
                ] = label_ids
                full_attention[batch_index, : prompt_length + label_length] = 1
                prediction_positions[batch_index] = torch.arange(
                    prompt_length - 1,
                    prompt_length + label_length - 1,
                    device=input_ids.device,
                )
            output = self.forward(
                full_input_ids,
                projected,
                attention_mask=full_attention,
                **model_kwargs,
            )
            logits = self._extract_logits(output)
            if logits.shape[:2] != (batch_size, full_length):
                raise ValueError(
                    "causal LM logits must preserve the supplied batch and sequence length"
                )
            prediction_logits = logits.gather(
                1,
                prediction_positions.unsqueeze(-1).expand(-1, -1, logits.shape[-1]),
            )
            if int(label_ids.max().item()) >= prediction_logits.shape[-1]:
                raise ValueError("label token ID exceeds the causal LM vocabulary")
            log_probabilities = prediction_logits.float().log_softmax(dim=-1)
            targets = candidate_ids.unsqueeze(-1)
            token_log_likelihood = log_probabilities.gather(-1, targets).squeeze(-1)
            scores.append(token_log_likelihood.mean(dim=-1))

        normalized_scores = torch.stack(scores, dim=-1)
        if not return_audit:
            return normalized_scores
        audit = {
            "labels": PROGRESSION_LABELS,
            "label_lengths": self.label_lengths.detach().clone(),
            "normalization": "mean_token_log_likelihood",
            "placeholder_count": placeholder_mask.sum(dim=1).detach(),
            "pixel_inputs_used": False,
            "model_frozen": self.freeze_audit()["all_frozen"],
        }
        return normalized_scores, audit


# The implementation is not tied to a particular Transformers class; this
# alias keeps the relation-token role obvious at Qwen call sites.
QwenRelationAdapter = FrozenVLMAdapter
