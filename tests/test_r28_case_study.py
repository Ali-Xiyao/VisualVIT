from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

from scripts import run_r28_case_study as r28


def test_registry_protocol_hash_is_frozen() -> None:
    assert r28.r27.sha256_file(r28.REGISTRY_PROTOCOL) == (
        r28.REGISTRY_PROTOCOL_SHA256
    )


def test_majority_vote_uses_frozen_label_order_for_ties() -> None:
    assert r28.majority_label(["Stable", "Improved"]) == "Improved"
    assert r28.majority_label(["Worse", "Stable", "Worse"]) == "Worse"


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ((1.0, 1.0, 1.0), {"STATE_SUFFICIENT"}),
        ((0.0, 1.0, 0.0), {"TEMPORAL_HELPED", "BINDING_HELPED"}),
        ((0.0, 0.0, 1.0), {"BINDING_HARMED"}),
        ((0.0, 0.0, 0.0), {"ALL_EXPERTS_FAIL"}),
    ],
)
def test_frozen_archetype_rules(
    values: tuple[float, float, float], expected: set[str]
) -> None:
    item = {
        "current_accuracy": values[0],
        "oracle_accuracy": values[1],
        "deranged_accuracy": values[2],
    }
    assert set(r28.archetype_memberships(item)) == expected


def test_registry_tie_break_is_deterministic() -> None:
    summaries = [
        {
            "qualification_id": qid,
            "current_accuracy": 1.0,
            "oracle_accuracy": 1.0,
            "deranged_accuracy": 1.0,
        }
        for qid in ("c", "a", "b")
    ]
    selected, support = r28.select_registry(summaries, limit=2)
    assert support["STATE_SUFFICIENT"] == 3
    assert selected["STATE_SUFFICIENT"] == ["a", "b"]


def _headroom_summaries() -> list[dict[str, object]]:
    result = []
    targets = r28.LABELS
    for patient_index in range(6):
        for label_index, target in enumerate(targets):
            current = target if patient_index % 2 == 0 else "Stable"
            oracle = target if patient_index % 2 == 1 else "Worse"
            result.append(
                {
                    "qualification_id": f"p{patient_index}-{label_index}",
                    "patient_id": f"p{patient_index}",
                    "target": target,
                    "consensus_prediction": {
                        "current_only": current,
                        "B4b_oracle": oracle,
                        "B4a_deranged": "Improved",
                    },
                }
            )
    return result


def test_case_oracle_headroom_is_patient_bootstrapped() -> None:
    result = r28.case_oracle_headroom(
        _headroom_summaries(), replicates=100, rng_seed=7
    )
    assert result["label_derived_router"] is True
    assert result["bootstrap"]["unit"] == "patient"
    assert result["case_oracle_minus_best_fixed"] > 0


def test_case_panel_uses_target_boxes_and_writes_png(tmp_path: Path) -> None:
    prior = tmp_path / "prior.png"
    current = tmp_path / "current.png"
    Image.new("L", (224, 224), color=30).save(prior)
    Image.new("L", (224, 224), color=200).save(current)
    record = {
        "prior_path": str(prior),
        "current_path": str(current),
        "anatomy": "left lung",
        "progression": "Improved",
        "prior_boxes": [
            {"label": "left lung", "x1": 20, "y1": 30, "x2": 120, "y2": 180}
        ],
        "current_boxes": [
            {"label": "left lung", "x1": 25, "y1": 35, "x2": 125, "y2": 185}
        ],
    }
    output = tmp_path / "panel.png"
    r28.render_case_panel(record, output)
    assert output.is_file()
    assert Image.open(output).size == (620, 540)
