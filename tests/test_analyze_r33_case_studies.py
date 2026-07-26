import torch

from scripts.analyze_r33_case_studies import (
    archetype_counts,
    dominant_archetype,
    summarize_group,
)


def test_archetype_counts_distinguish_help_and_harm():
    labels = torch.tensor([0, 1])
    robust = torch.tensor([[1, 1], [1, 1], [0, 1]])
    rich = torch.tensor([[0, 0], [0, 1], [0, 0]])
    counts = archetype_counts(labels, robust, rich)
    assert counts["rich_helped"].tolist() == [2, 0]
    assert counts["rich_harmed"].tolist() == [0, 2]
    assert dominant_archetype(counts, 0) == "rich_helped"
    assert dominant_archetype(counts, 1) == "rich_harmed"


def test_group_summary_reports_route_capture():
    labels = torch.tensor([0, 1])
    robust = torch.tensor([[1, 1], [0, 1], [0, 1]])
    rich = torch.tensor([[0, 0], [0, 0], [0, 1]])
    result = summarize_group(
        [0, 1],
        labels,
        robust,
        rich,
        torch.tensor([True, False]),
    )
    assert result["records"] == 2
    assert result["rich_helped_units"] == 1
    assert result["rich_harmed_units"] == 2
    assert result["route_help_capture"] == 1.0
