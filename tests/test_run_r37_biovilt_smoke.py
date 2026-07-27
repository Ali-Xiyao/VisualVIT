import torch

from visualvit.prta import PROGRESSION_LABELS

from scripts.run_r37_biovilt_smoke import (
    balanced_sample,
    extract_cached_controls,
    unique_pairs,
)


def _examples():
    return [
        {
            "example_id": f"{label}-{index}",
            "pair_id": f"pair-{label}-{index}",
            "label": label,
            "prior_path": f"prior-{label}-{index}",
            "current_path": f"current-{label}-{index}",
        }
        for label in PROGRESSION_LABELS
        for index in range(3)
    ]


def test_balanced_sample_is_deterministic_and_balanced():
    first = balanced_sample(_examples(), maximum=10, seed=17)
    second = balanced_sample(_examples(), maximum=10, seed=17)
    assert [item["example_id"] for item in first] == [
        item["example_id"] for item in second
    ]
    assert {
        label: sum(item["label"] == label for item in first)
        for label in PROGRESSION_LABELS
    } == {label: 2 for label in PROGRESSION_LABELS}


def test_unique_pairs_collapses_repeated_finding_rows():
    examples = _examples()
    duplicate = dict(examples[0])
    duplicate["example_id"] = "second-finding"
    result = unique_pairs(examples, [duplicate])
    assert len(result) == len(examples)


def test_cached_controls_are_indexed_by_pair_id():
    class Cache:
        def get_many(self, pair_ids, *, mode):
            offset = {"true_pair": 0, "current_only": 1, "inverted": 2}[mode]
            return torch.tensor(
                [[float(index + offset)] for index, _ in enumerate(pair_ids)]
            )

    pairs = [{"pair_id": "a"}, {"pair_id": "b"}]
    result = extract_cached_controls(Cache(), pairs)
    assert result["a"]["true_pair"].item() == 0
    assert result["b"]["inverted"].item() == 3
