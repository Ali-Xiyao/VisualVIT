from __future__ import annotations

import json

import torch

from scripts import run_r28_tier_mvp as runner
from visualvit.tier import (
    EXPERT_NAMES,
    expert_router_features,
    fit_expert_bundle,
    fit_router,
    signed_random_projection,
    uniform_fusion,
)


def test_protocol_and_prerequisite_hashes_are_frozen() -> None:
    assert runner.r27.sha256_file(runner.PROTOCOL_PATH) == runner.PROTOCOL_SHA256
    assert runner.r27.sha256_file(runner.FEATURE_CACHE) == (
        runner.FEATURE_CACHE_SHA256
    )
    assert runner.r27.sha256_file(
        runner.CASE_ROOT / "artifact_manifest.json"
    ) == runner.CASE_MANIFEST_SHA256


def test_signed_projection_is_deterministic_and_capacity_matched() -> None:
    values = torch.arange(60, dtype=torch.float32).reshape(5, 12)
    first, first_hash = signed_random_projection(
        values, output_dim=8, seed=17
    )
    second, second_hash = signed_random_projection(
        values, output_dim=8, seed=17
    )
    different, different_hash = signed_random_projection(
        values, output_dim=8, seed=18
    )
    assert first.shape == (5, 8)
    assert torch.equal(first, second)
    assert first_hash == second_hash
    assert not torch.equal(first, different)
    assert first_hash != different_hash


def test_router_feature_contract_has_no_forbidden_fields() -> None:
    assert not (
        set(runner.ROUTER_BASE_FIELDS) & set(runner.FORBIDDEN_ROUTER_FIELDS)
    )
    base = torch.randn(7, len(runner.ROUTER_BASE_FIELDS))
    logits = torch.randn(7, 3, 3)
    features = expert_router_features(base, logits)
    assert features.shape == (
        7,
        len(runner.ROUTER_BASE_FIELDS) + 3 * 3 + 3 + 3 + 3,
    )
    assert torch.isfinite(features).all()


def test_uniform_fusion_is_exact_logit_mean() -> None:
    logits = torch.arange(54, dtype=torch.float32).reshape(6, 3, 3)
    assert torch.equal(uniform_fusion(logits), logits.mean(1))


def test_expert_bundle_can_overfit_separable_toy() -> None:
    generator = torch.Generator().manual_seed(7)
    prototypes = torch.randn(3, 16, generator=generator)
    targets = torch.arange(3).repeat_interleave(10)
    values = prototypes[targets]
    logits, fit = fit_expert_bundle(
        [values, values, values],
        targets,
        [values, values, values],
        seed=9,
        class_count=3,
        steps=150,
        learning_rate=0.01,
        device="cpu",
    )
    assert fit["finite"] is True
    assert all(value >= 0.95 for value in fit["train_accuracy"])
    assert all(
        float((logits[:, index].argmax(-1) == targets).float().mean()) >= 0.95
        for index in range(len(EXPERT_NAMES))
    )


def test_linear_and_nonlinear_routers_learn_toy_regimes() -> None:
    targets = (torch.arange(90) // 3) % 3
    routes = torch.arange(90) % 3
    base = torch.nn.functional.one_hot(routes, num_classes=3).float()
    logits = torch.full((90, 3, 3), -3.0)
    for index in range(90):
        logits[index, int(routes[index]), int(targets[index])] = 3.0
    for kind in ("linear", "nonlinear"):
        mixture, weights, fit = fit_router(
            base[:60],
            logits[:60],
            targets[:60],
            base[60:],
            logits[60:],
            kind=kind,
            seed=11,
            steps=250,
            learning_rate=0.01,
            device="cpu",
        )
        assert fit["finite"] is True
        assert torch.isfinite(weights).all()
        assert float(
            (mixture.argmax(-1) == targets[60:]).float().mean()
        ) >= 0.90


def test_real_frozen_representations_are_finite_and_aligned() -> None:
    cohort = json.loads(runner.r27.R26_ROOT_DEFAULT.joinpath("cohort.json").read_text(encoding="utf-8"))
    features = torch.load(
        runner.FEATURE_CACHE, map_location="cpu", weights_only=True
    )
    projected, router_base, targets, manifest = runner.build_representations(
        cohort, features
    )
    assert targets.shape == (774,)
    assert router_base.shape == (774, len(runner.ROUTER_BASE_FIELDS))
    assert manifest["finite"] is True
    assert all(value.shape == (774, runner.PROJECTION_DIM) for value in projected.values())


def test_runner_sanity_gate_passes() -> None:
    audit = runner.run_sanity_audit()
    assert audit["passed"] is True
    assert all(audit["checks"].values())
