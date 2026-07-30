import pytest
import torch

from visualvit.prta_gen import (
    LinearInformationProbe,
    exact64_summary_features,
    extract_explicit_generative_target,
    field_support,
    format_structured_target,
    generative_prior_preference_loss,
)


def test_literal_target_masks_finding_and_never_invents_missing_fields():
    target = extract_explicit_generative_target(
        {
            "finding": "Pleural Effusion",
            "label": "Improved",
            "sentence": (
                "The small right pleural effusion has mildly decreased "
                "since the prior study."
            ),
        }
    )

    assert target.progression == "Improved"
    assert target.laterality == "Right"
    assert target.anatomy == "Unspecified"
    assert target.degree == "Mild"
    assert target.quality_tier == "A"
    assert target.literal_laterality
    assert not target.literal_anatomy


def test_literal_target_extracts_coarse_anatomy_and_fails_closed_on_conflict():
    supported = extract_explicit_generative_target(
        {
            "finding": "Lung Opacity",
            "label": "Worse",
            "sentence": (
                "The left lower lung opacity has moderately increased."
            ),
        }
    )
    conflict = extract_explicit_generative_target(
        {
            "finding": "Lung Opacity",
            "label": "Worse",
            "sentence": (
                "The left upper and lower lung opacity has increased."
            ),
        }
    )

    assert supported.laterality == "Left"
    assert supported.anatomy == "Lower lung"
    assert supported.degree == "Moderate"
    assert conflict.anatomy == "Unspecified"


def test_structured_target_omits_locked_and_unspecified_fields():
    target = extract_explicit_generative_target(
        {
            "finding": "Pneumothorax",
            "label": "Resolved",
            "sentence": "The right pneumothorax has resolved.",
        }
    )
    formatted = format_structured_target(
        target,
        unlocked_fields=("progression", "laterality", "anatomy"),
        include_evidence=True,
    )

    assert "<progression>Resolved</progression>" in formatted
    assert "<laterality>Right</laterality>" in formatted
    assert "<anatomy>" not in formatted
    assert target.evidence in formatted


def test_evidence_requires_tier_a_literal_location():
    target = extract_explicit_generative_target(
        {
            "finding": "Edema",
            "label": "Stable",
            "sentence": "Pulmonary edema is unchanged.",
        }
    )
    assert target.quality_tier == "C"
    with pytest.raises(PermissionError, match="Tier-A"):
        format_structured_target(
            target,
            unlocked_fields=("progression",),
            include_evidence=True,
        )


def test_exact64_summary_uses_only_registered_three_token_groups():
    tokens = torch.zeros(2, 64, 3)
    tokens[:, 0:20] = 1
    tokens[:, 20:40] = 2
    tokens[:, 40:60] = 3
    tokens[:, 60:64] = 1000
    valid = torch.ones(2, 64, dtype=torch.bool)
    valid[:, 60:] = False

    features = exact64_summary_features(tokens, valid_mask=valid)

    assert features.shape == (2, 9)
    assert torch.equal(features[0], torch.tensor([1.0] * 3 + [2.0] * 3 + [3.0] * 3))
    probe = LinearInformationProbe(features.shape[-1], 5)
    assert probe(features).shape == (2, 5)


def test_field_support_and_g_cmcp_loss_are_deterministic():
    targets = [
        extract_explicit_generative_target(
            {
                "finding": "Pneumothorax",
                "label": "New",
                "sentence": "A new left pneumothorax is present.",
            }
        ),
        extract_explicit_generative_target(
            {
                "finding": "Pneumothorax",
                "label": "Resolved",
                "sentence": "The right pneumothorax has resolved.",
            }
        ),
    ]
    support = field_support(targets, "laterality")
    loss = generative_prior_preference_loss(
        torch.tensor([-0.2, -0.5]),
        torch.tensor([-0.6, -0.4]),
        margin=0.2,
    )

    assert support["Left"] == 1
    assert support["Right"] == 1
    assert support["Unspecified"] == 0
    assert torch.allclose(loss, torch.tensor(0.15))
