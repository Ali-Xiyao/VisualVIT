from argparse import Namespace

import pytest
import torch

from scripts.run_r37_prta_smoke import R40_CONFIG, load_r40_config
from scripts.run_r40_representation_baseline import (
    frozen_a0_features,
    siamese_signed_abs_features,
    validate_args,
    validate_roster_audit,
)


def test_siamese_signed_abs_has_registered_width_and_direction():
    prior = torch.tensor([[1.0, 0.0]])
    current = torch.tensor([[0.0, 1.0]])
    forward = siamese_signed_abs_features(prior, current)
    reversed_ = siamese_signed_abs_features(current, prior)

    assert forward.shape == (1, 8)
    assert torch.allclose(forward[:, :2], reversed_[:, 2:4])
    assert torch.allclose(forward[:, 2:4], reversed_[:, :2])
    assert torch.allclose(forward[:, 4:6], -reversed_[:, 4:6])
    assert torch.allclose(forward[:, 6:8], reversed_[:, 6:8])


def test_frozen_a0_features_match_difference_and_invert():
    prior = torch.tensor([[1.0, 0.0]])
    current = torch.tensor([[0.0, 1.0]])
    forward = frozen_a0_features(prior, current)
    reversed_ = frozen_a0_features(current, prior)
    current_only = frozen_a0_features(current, current)

    assert torch.allclose(forward, -reversed_)
    assert torch.equal(current_only, torch.zeros_like(current_only))


def test_representation_args_are_frozen():
    config = load_r40_config(R40_CONFIG)
    args = Namespace(
        baseline="B2_siamese_signed_abs",
        seed=17,
        epochs=100,
        batch_size=16,
        learning_rate=1e-2,
        max_train_examples=0,
        max_development_examples=0,
    )
    validate_args(args, config)
    args.epochs = 99
    with pytest.raises(ValueError, match="baseline drift"):
        validate_args(args, config)


def test_roster_audit_rejects_protected_drift():
    config = load_r40_config(R40_CONFIG)
    audit = {
        "status": "READY_R40_OUTCOME_INDEPENDENT_ROSTER",
        "protocol_id": config["protocol_id"],
        "formal_training_unlocked": True,
        "patient_disjoint": True,
        "previous_r37_1_validation_excluded": True,
        "one_shot_development": True,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "checkpoint_hashes_recomputed": False,
    }
    validate_roster_audit(audit, config)
    audit["gold_outcomes_read"] = True
    with pytest.raises(PermissionError, match="firewall drift"):
        validate_roster_audit(audit, config)
