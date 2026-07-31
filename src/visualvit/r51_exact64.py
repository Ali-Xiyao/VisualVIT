from __future__ import annotations

import torch
from torch import Tensor
import torch.nn.functional as F


TILA_PATCH_POSITIONS = (
    0, 3, 7, 10, 13, 17, 20, 23, 26, 30,
    33, 36, 40, 43, 46, 50, 53, 56, 59, 63,
    66, 69, 73, 76, 79, 83, 86, 89, 93, 96,
    99, 102, 106, 109, 112, 116, 119, 122, 126, 129,
    132, 136, 139, 142, 145, 149, 152, 155, 159, 162,
    165, 169, 172, 175, 178, 182, 185, 188, 192, 195,
)
B2_PATCH_POSITIONS = (1, 15, 29, 43, 57, 71, 85, 99, 112, 126, 140, 154, 168, 182, 196)


def normalize_exact64_tokens(tokens: Tensor, *, epsilon: float = 1e-6) -> Tensor:
    if tuple(tokens.shape[-2:]) != (64, 768):
        raise ValueError("R51 exact64 tokens must end in [64,768]")
    if epsilon <= 0:
        raise ValueError("R51 RMS epsilon must be positive")
    active = tokens[..., :60, :].float()
    if not bool(torch.isfinite(active).all()):
        raise ValueError("R51 exact64 active tokens must be finite")
    rms = active.square().mean(dim=-1, keepdim=True).clamp_min(epsilon).sqrt()
    active = active / rms
    reserved = torch.zeros(
        *tokens.shape[:-2], 4, 768, dtype=active.dtype, device=active.device
    )
    return torch.cat((active, reserved), dim=-2)


def tila_projected_patches_to_exact64(projected_patches: Tensor) -> Tensor:
    if tuple(projected_patches.shape[-3:]) != (128, 14, 14):
        raise ValueError("R51 TILA patches must end in [128,14,14]")
    flat = projected_patches.float().flatten(-2).transpose(-1, -2)
    index = torch.tensor(
        TILA_PATCH_POSITIONS, dtype=torch.long, device=flat.device
    )
    selected = flat.index_select(-2, index)
    expanded = selected.repeat_interleave(6, dim=-1)
    reserved = torch.zeros(
        *expanded.shape[:-2], 4, 768,
        dtype=expanded.dtype,
        device=expanded.device,
    )
    return normalize_exact64_tokens(torch.cat((expanded, reserved), dim=-2))


def b2_patch_tokens_to_exact64(prior: Tensor, current: Tensor) -> Tensor:
    if prior.shape != current.shape or tuple(prior.shape[-2:]) != (197, 768):
        raise ValueError("R51 B2 inputs must be matching [...,197,768]")
    index = torch.tensor(B2_PATCH_POSITIONS, dtype=torch.long, device=prior.device)
    prior_selected = F.normalize(prior.float().index_select(-2, index), dim=-1)
    current_selected = F.normalize(current.float().index_select(-2, index), dim=-1)
    signed = current_selected - prior_selected
    active = torch.cat(
        (prior_selected, current_selected, signed, signed.abs()), dim=-2
    )
    reserved = torch.zeros(
        *active.shape[:-2], 4, 768, dtype=active.dtype, device=active.device
    )
    return normalize_exact64_tokens(torch.cat((active, reserved), dim=-2))
