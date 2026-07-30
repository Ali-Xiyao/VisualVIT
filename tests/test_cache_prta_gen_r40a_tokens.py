import pytest
import torch

from scripts.cache_prta_gen_r40a_tokens import (
    compact_get_many,
    materialize_required_features,
    prior_shuffle_assignment,
    select_rows,
    stable_order,
    token_cache_output_root,
)


def rows():
    return [
        {
            "example_id": f"example-{index}",
            "patient_id": f"patient-{index}",
            "finding": "Edema",
            "prior_dicom_id": f"prior-{index}",
        }
        for index in range(5)
    ]


def test_prior_shuffle_is_deterministic_cross_patient_and_complete():
    first = prior_shuffle_assignment(rows(), seed=40011)
    second = prior_shuffle_assignment(rows(), seed=40011)

    assert first == second
    assert set(first) == {row["example_id"] for row in rows()}
    original = {row["example_id"]: row["prior_dicom_id"] for row in rows()}
    assert all(first[key] != original[key] for key in first)


def test_prior_shuffle_requires_two_patients_per_finding():
    duplicate_patient = rows()
    for row in duplicate_patient:
        row["patient_id"] = "one-patient"

    with pytest.raises(ValueError, match="two patients"):
        prior_shuffle_assignment(duplicate_patient, seed=40011)


def test_smoke_selection_is_outcome_independent_and_fixed_size():
    selected = select_rows(rows(), smoke_rows=3)
    expected = sorted(
        rows(),
        key=lambda row: (
            stable_order(
                "prta-gen-r40a-token-smoke-v1",
                0,
                row["example_id"],
            ),
            row["example_id"],
        ),
    )[:3]

    assert selected == expected
    with pytest.raises(ValueError, match="invalid smoke"):
        select_rows(rows(), smoke_rows=6)


def test_formal_and_smoke_outputs_are_fresh_siblings(tmp_path):
    config = {
        "token_cache_root": str(tmp_path / "tokens"),
        "frozen_prta_seed": 17,
    }

    formal = token_cache_output_root(
        config, scope="development", smoke_rows=0
    )
    smoke = token_cache_output_root(
        config, scope="development", smoke_rows=64
    )

    assert formal.name == "formal"
    assert smoke.name == "smoke_64"
    assert formal.parent == smoke.parent


def test_compact_materialization_reads_only_selected_rows(tmp_path):
    shard_path = tmp_path / "block8.pt"
    features = torch.arange(
        3 * 197 * 768, dtype=torch.float16
    ).view(3, 197, 768)
    torch.save({"features": features}, shard_path)

    class FakeCache:
        locations = {
            "a": (shard_path, 0),
            "b": (shard_path, 2),
        }

    compact = materialize_required_features(FakeCache(), ["b", "a", "b"])
    batch = compact_get_many(compact, ["b", "a"])

    assert set(compact) == {"a", "b"}
    assert torch.equal(batch[0], features[2])
    assert torch.equal(batch[1], features[0])
    assert (
        compact["a"].untyped_storage().data_ptr()
        != features.untyped_storage().data_ptr()
    )
