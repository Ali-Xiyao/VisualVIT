import torch

from visualvit.cmcp import build_cmcp_matches, transition_examples


def example(
    *,
    pair: str,
    patient: str,
    label: str,
    current: str,
    prior: str,
    view: str = "AP",
    finding: str = "Edema",
):
    return {
        "example_id": pair,
        "pair_id": pair,
        "patient_id": patient,
        "partition": "pretrain",
        "finding": finding,
        "label": label,
        "current_view": view,
        "prior_dicom_id": prior,
        "current_dicom_id": current,
    }


def test_transition_examples_are_finding_level_and_deterministic():
    rows = [
        {
            "pair_id": "p1",
            "patient_id": "patient1",
            "partition": "pretrain",
            "current_view": "AP",
            "prior_dicom_id": "a",
            "current_dicom_id": "b",
            "transition_supervision": [
                {"finding": "Edema", "label": "Worse"},
                {"finding": "Pleural Effusion", "label": "Stable"},
            ],
        }
    ]
    first = transition_examples(rows)
    second = transition_examples(rows)
    assert first == second
    assert len(first) == 2
    assert {item["finding"] for item in first} == {
        "Edema",
        "Pleural Effusion",
    }


def test_cmcp_uses_similar_current_but_different_patient_and_label():
    examples = [
        example(
            pair="target",
            patient="p1",
            label="Worse",
            current="c1",
            prior="a1",
        ),
        example(
            pair="same_patient",
            patient="p1",
            label="Improved",
            current="c2",
            prior="a2",
        ),
        example(
            pair="same_label",
            patient="p2",
            label="Worse",
            current="c3",
            prior="a3",
        ),
        example(
            pair="eligible_close",
            patient="p3",
            label="Improved",
            current="c4",
            prior="a4",
        ),
        example(
            pair="eligible_far",
            patient="p4",
            label="Resolved",
            current="c5",
            prior="a5",
        ),
    ]
    embeddings = {
        "c1": torch.tensor([1.0, 0.0]),
        "c2": torch.tensor([1.0, 0.0]),
        "c3": torch.tensor([1.0, 0.0]),
        "c4": torch.tensor([0.99, 0.01]),
        "c5": torch.tensor([0.0, 1.0]),
    }
    matches, audit = build_cmcp_matches(examples, embeddings, chunk_size=2)
    target = next(
        item for item in matches if item["target_pair_id"] == "target"
    )
    assert target["counterfactual_pair_id"] == "eligible_close"
    assert target["counterfactual_patient_id"] != "p1"
    assert target["counterfactual_label"] != "Worse"
    assert audit["coverage"] == 1.0


def test_cmcp_does_not_cross_view_or_finding_group():
    examples = [
        example(
            pair="target",
            patient="p1",
            label="New",
            current="c1",
            prior="a1",
        ),
        example(
            pair="wrong_view",
            patient="p2",
            label="Resolved",
            current="c2",
            prior="a2",
            view="PA",
        ),
        example(
            pair="wrong_finding",
            patient="p3",
            label="Resolved",
            current="c3",
            prior="a3",
            finding="Pneumothorax",
        ),
    ]
    embeddings = {key: torch.tensor([1.0, 0.0]) for key in ("c1", "c2", "c3")}
    matches, audit = build_cmcp_matches(examples, embeddings)
    assert matches == []
    assert audit["dynamic_examples"] == 3
    assert audit["coverage"] == 0.0
