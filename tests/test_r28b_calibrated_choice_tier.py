from __future__ import annotations

import torch

from scripts import run_r28b_calibrated_choice_tier as runner
from visualvit.tier_choice import (
    apply_temperatures,
    expert_choice_targets,
    fit_choice_router,
    fit_scalar_temperatures,
    select_routed_logits,
)


def test_r28b_protocol_hash_is_frozen() -> None:
    assert (
        runner.r27.sha256_file(runner.PROTOCOL_PATH)
        == runner.PROTOCOL_SHA256
    )


def test_temperature_fit_is_positive_finite_and_improves_loss() -> None:
    targets = torch.arange(3).repeat(20)
    base = torch.nn.functional.one_hot(targets, num_classes=3).float()
    logits = torch.stack((base * 18.0, base * 9.0, base * 4.0), dim=1)
    logits = logits + torch.randn(
        logits.shape, generator=torch.Generator().manual_seed(3)
    )
    before = sum(
        torch.nn.functional.cross_entropy(logits[:, index], targets)
        for index in range(3)
    )
    temperatures, fit = fit_scalar_temperatures(
        logits, targets, steps=80, learning_rate=0.03
    )
    calibrated = apply_temperatures(logits, temperatures)
    after = sum(
        torch.nn.functional.cross_entropy(calibrated[:, index], targets)
        for index in range(3)
    )
    assert fit["finite"] is True
    assert bool((temperatures > 0).all())
    assert after < before


def test_choice_targets_use_first_correct_then_target_probability() -> None:
    logits = torch.tensor(
        [
            [[4.0, 0.0, 0.0], [5.0, 0.0, 0.0], [0.0, 4.0, 0.0]],
            [[3.0, 1.0, 0.0], [2.0, 1.9, 0.0], [1.0, 2.5, 0.0]],
        ]
    )
    targets = torch.tensor([0, 2])
    choices = expert_choice_targets(logits, targets)
    assert choices.tolist() == [0, 1]


def test_hard_and_guarded_selection_obey_frozen_contract() -> None:
    logits = torch.arange(18, dtype=torch.float32).reshape(2, 3, 3)
    probabilities = torch.tensor(
        [[0.10, 0.20, 0.70], [0.35, 0.40, 0.25]]
    )
    hard, hard_choices, hard_accepted = select_routed_logits(
        logits, probabilities, mode="hard"
    )
    guarded, guarded_choices, guarded_accepted = select_routed_logits(
        logits,
        probabilities,
        mode="guarded",
        fallback_expert=1,
        minimum_probability=0.60,
        minimum_margin=0.15,
    )
    assert hard_choices.tolist() == [2, 1]
    assert hard_accepted.tolist() == [True, True]
    assert guarded_choices.tolist() == [2, 1]
    assert guarded_accepted.tolist() == [True, False]
    assert torch.equal(hard[0], logits[0, 2])
    assert torch.equal(guarded[1], logits[1, 1])


def test_choice_router_learns_separable_route_targets() -> None:
    routes = torch.arange(90) % 3
    targets = (torch.arange(90) // 3) % 3
    base = torch.nn.functional.one_hot(routes, num_classes=3).float()
    logits = torch.full((90, 3, 3), -4.0)
    for index in range(90):
        route = int(routes[index])
        target = int(targets[index])
        for expert in range(3):
            logits[index, expert, (target + 1) % 3] = 4.0
        logits[index, route, (target + 1) % 3] = -4.0
        logits[index, route, target] = 4.0
    probabilities, fit = fit_choice_router(
        base[:60],
        logits[:60],
        targets[:60],
        base[60:],
        logits[60:],
        seed=13,
        steps=250,
        learning_rate=0.01,
    )
    assert fit["finite"] is True
    assert probabilities.shape == (30, 3)
    assert float(
        (probabilities.argmax(-1) == routes[60:]).float().mean()
    ) >= 0.90
