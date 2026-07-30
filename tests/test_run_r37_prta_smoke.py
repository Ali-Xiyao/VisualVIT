from argparse import Namespace

import pytest
import torch

from scripts.run_r37_prta_smoke import (
    R40_CONFIG,
    balanced_sample,
    formal_partition,
    load_r40_config,
    macro_f1,
    resolve_r40_variant,
    responsiveness_diagnostics,
    validate_formal_args,
    validate_r37_1_args,
    validate_r40_args,
)


def test_balanced_smoke_sample_is_deterministic():
    examples = [
        {
            "example_id": f"{label}-{index}",
            "label": label,
        }
        for label in ("Stable", "Improved", "Worse", "New", "Resolved")
        for index in range(5)
    ]
    first = balanced_sample(examples, maximum=10, seed=17)
    second = balanced_sample(examples, maximum=10, seed=17)
    assert first == second
    counts = {}
    for item in first:
        counts[item["label"]] = counts.get(item["label"], 0) + 1
    assert set(counts.values()) == {2}


def test_formal_partition_has_seed_independent_complete_order():
    examples = [
        {"patient_id": "p2", "example_id": "e2"},
        {"patient_id": "p1", "example_id": "e3"},
        {"patient_id": "p1", "example_id": "e1"},
    ]
    expected = [
        {"patient_id": "p1", "example_id": "e1"},
        {"patient_id": "p1", "example_id": "e3"},
        {"patient_id": "p2", "example_id": "e2"},
    ]
    assert formal_partition(examples, expected_count=3) == expected
    assert formal_partition(reversed(examples), expected_count=3) == expected
    with pytest.raises(ValueError, match="count drift"):
        formal_partition(examples, expected_count=2)


def test_formal_args_require_exact_frozen_bundle():
    args = Namespace(
        variant="A6",
        seed=17,
        epochs=3,
        batch_size=2,
        learning_rate=1e-4,
        adapter_rank=32,
        max_train_examples=0,
        max_calibration_examples=0,
    )
    validate_formal_args(args)
    args.seed = 44
    with pytest.raises(ValueError, match="frozen seeds"):
        validate_formal_args(args)
    args.seed = 17
    args.epochs = 4
    with pytest.raises(ValueError, match="configuration drift"):
        validate_formal_args(args)


def test_r37_1_args_require_exact_frozen_bundle():
    args = Namespace(
        variant="A6",
        seed=17,
        epochs=3,
        batch_size=2,
        learning_rate=1e-4,
        adapter_rank=32,
        max_train_examples=0,
        max_calibration_examples=0,
        formal=False,
    )
    validate_r37_1_args(args)
    args.seed = 44
    with pytest.raises(ValueError, match="frozen seeds"):
        validate_r37_1_args(args)
    args.seed = 17
    args.learning_rate = 2e-4
    with pytest.raises(ValueError, match="configuration drift"):
        validate_r37_1_args(args)


def test_r40_component_args_and_no_state_variant_are_frozen():
    config = load_r40_config(R40_CONFIG)
    args = Namespace(
        variant="A6_no_state",
        seed=17,
        epochs=3,
        batch_size=2,
        learning_rate=1e-4,
        adapter_rank=32,
        max_train_examples=0,
        max_calibration_examples=0,
        formal=False,
        r37_1=False,
        r37_1_engineering=False,
    )
    validate_r40_args(args, config)
    variant = resolve_r40_variant(args.variant, config)
    assert variant.temporal_inversion
    assert variant.cmcp
    assert not variant.state_preservation
    args.epochs = 4
    with pytest.raises(ValueError, match="configuration drift"):
        validate_r40_args(args, config)


def test_macro_f1_is_one_for_perfect_five_class_predictions():
    values = [0, 1, 2, 3, 4]
    assert macro_f1(values, values) == 1.0


def test_responsiveness_diagnostics_distinguish_continuous_and_argmax_change():
    reference_embeddings = torch.tensor([[1.0, 0.0], [0.0, 1.0]])
    control_embeddings = torch.tensor([[1.0, 0.0], [1.0, 0.0]])
    reference_logits = torch.tensor([[2.0, 1.0], [1.0, 2.0]])
    control_logits = torch.tensor([[2.0, 1.0], [2.0, 1.0]])

    result = responsiveness_diagnostics(
        reference_embeddings,
        control_embeddings,
        reference_logits,
        control_logits,
    )

    assert result["rows"] == 2
    assert result["embedding_l2_mean"] > 0
    assert result["logit_l2_mean"] > 0
    assert result["prediction_change_count"] == 1
    assert result["prediction_change_rate"] == 0.5
