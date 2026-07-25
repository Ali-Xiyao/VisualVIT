from __future__ import annotations

import hashlib
import math
from typing import Any, Mapping

import torch
from torch import nn

from .schemas import MatchPlan, RegionBatch, TokenBundle


def training_convergence_pass(
    metrics: Mapping[str, Any],
    *,
    train_macro_f1_min: float = 0.95,
    final_loss_max: float = 0.20,
) -> bool:
    """Apply the preregistered proxy convergence gate without defaults."""

    train_macro_f1 = float(metrics["train_macro_f1"])
    final_loss = float(metrics["final_loss"])
    return bool(
        math.isfinite(train_macro_f1)
        and math.isfinite(final_loss)
        and train_macro_f1 >= train_macro_f1_min
        and final_loss <= final_loss_max
    )


def tensor_sha256(tensor: torch.Tensor) -> str:
    contiguous = tensor.detach().to("cpu").contiguous()
    payload = contiguous.numpy().tobytes()
    return hashlib.sha256(payload).hexdigest()


def model_signature(model: nn.Module) -> dict[str, Any]:
    return {
        name: {
            "shape": list(parameter.shape),
            "dtype": str(parameter.dtype),
            "numel": parameter.numel(),
            "sha256": tensor_sha256(parameter),
        }
        for name, parameter in model.named_parameters()
    }


def audit_b4_isomorphism(
    regions_a: RegionBatch,
    regions_b: RegionBatch,
    b4a: MatchPlan,
    b4b: MatchPlan,
    bundle_a: TokenBundle,
    bundle_b: TokenBundle,
    model_a: nn.Module,
    model_b: nn.Module,
) -> dict[str, Any]:
    b4a.validate_hard(regions_a)
    b4b.validate_hard(regions_b)
    bundle_a.validate()
    bundle_b.validate()

    input_hashes_a = {
        "prior_features": tensor_sha256(regions_a.prior_features),
        "current_features": tensor_sha256(regions_a.current_features),
        "prior_valid": tensor_sha256(regions_a.prior_valid),
        "current_valid": tensor_sha256(regions_a.current_valid),
        "prior_anatomy": tensor_sha256(regions_a.prior_anatomy),
        "current_anatomy": tensor_sha256(regions_a.current_anatomy),
        "prior_entity_ids": tensor_sha256(regions_a.prior_entity_ids),
        "current_entity_ids": tensor_sha256(regions_a.current_entity_ids),
    }
    input_hashes_b = {
        "prior_features": tensor_sha256(regions_b.prior_features),
        "current_features": tensor_sha256(regions_b.current_features),
        "prior_valid": tensor_sha256(regions_b.prior_valid),
        "current_valid": tensor_sha256(regions_b.current_valid),
        "prior_anatomy": tensor_sha256(regions_b.prior_anatomy),
        "current_anatomy": tensor_sha256(regions_b.current_anatomy),
        "prior_entity_ids": tensor_sha256(regions_b.prior_entity_ids),
        "current_entity_ids": tensor_sha256(regions_b.current_entity_ids),
    }
    report = {
        "input_checksums_equal": input_hashes_a == input_hashes_b,
        "transport_marginals_equal": torch.equal(
            b4a.transport.sum(dim=-1), b4b.transport.sum(dim=-1)
        )
        and torch.equal(b4a.transport.sum(dim=-2), b4b.transport.sum(dim=-2)),
        "token_types_equal": torch.equal(bundle_a.token_types, bundle_b.token_types),
        "token_valid_masks_equal": torch.equal(
            bundle_a.valid_mask, bundle_b.valid_mask
        ),
        "model_signatures_equal": model_signature(model_a) == model_signature(model_b),
        "assignments_different": not torch.equal(b4a.transport, b4b.transport),
        "input_hashes_a": input_hashes_a,
        "input_hashes_b": input_hashes_b,
        "assignment_hash_b4a": tensor_sha256(b4a.transport),
        "assignment_hash_b4b": tensor_sha256(b4b.transport),
    }
    report["pass"] = all(
        report[key]
        for key in (
            "input_checksums_equal",
            "transport_marginals_equal",
            "token_types_equal",
            "token_valid_masks_equal",
            "model_signatures_equal",
            "assignments_different",
        )
    )
    return report
