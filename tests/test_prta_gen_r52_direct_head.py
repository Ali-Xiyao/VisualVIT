from __future__ import annotations

import json
from pathlib import Path

import torch

import scripts.aggregate_prta_gen_r52_matched_direct_head as r52_aggregate
from scripts.run_prta_gen_r52_matched_direct_head import flatten_active_exact64


WORKSPACE = Path(__file__).resolve().parents[1]
CONFIG = (
    WORKSPACE
    / "configs"
    / "prta_gen"
    / "prta_gen_r52_matched_direct_head_v1.json"
)


def _config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_r52_frozen_shared_direct_head_contract() -> None:
    config = _config()
    assert config["status"] == "FROZEN_PRTA_GEN_R52_MATCHED_DIRECT_HEAD"
    assert config["source"]["training_rows"] == 2500
    assert config["source"]["evaluation_rows"] == 500
    assert config["evaluation"]["arms"] == [
        "prta_exact64",
        "tila_exact64",
        "b2_exact64",
    ]
    assert config["head"]["input_width"] == 60 * 768
    assert config["head"]["parameter_count"] == 5_991_173
    assert config["head"]["arm_specific_trainable_adapter_allowed"] is False
    assert config["training"]["expected_updates_per_arm"] == 2000
    assert config["disclosure"]["any_r52_direct_head_outcome_visible_before_freeze"] is False


def test_r52_flatten_uses_all_and_only_active_positions() -> None:
    tokens = torch.arange(2 * 64 * 768, dtype=torch.float32).reshape(2, 64, 768)
    tokens[:, 60:64] = 0
    features = flatten_active_exact64(tokens)
    assert features.shape == (2, 60 * 768)
    assert torch.equal(features[0], tokens[0, :60].reshape(-1))
    invalid = tokens.clone()
    invalid[0, 63, 0] = 1
    try:
        flatten_active_exact64(invalid)
    except PermissionError:
        pass
    else:
        raise AssertionError("reserved-token drift must fail closed")


def test_r52_aggregate_enforces_shared_head_and_rows(tmp_path: Path, monkeypatch) -> None:
    config = _config()
    config["training"]["seeds"] = [17, 29]
    config["evaluation"]["paired_patient_bootstrap_replicates"] = 20
    config["runtime"]["runs"] = str(tmp_path / "runs")
    config["runtime"]["aggregate"] = str(tmp_path / "aggregate.json")
    rows = [
        {"patient_id": f"p{i}", "example_id": f"e{i}", "progression": label}
        for i, label in enumerate(("Stable", "Improved", "Worse", "New", "Resolved"))
    ]
    monkeypatch.setattr(
        r52_aggregate,
        "validate_r52_authority",
        lambda *_args, **_kwargs: (config, {}, [], rows),
    )
    targets = list(range(5))
    predictions = {
        "prta_exact64": [0, 1, 2, 3, 4],
        "tila_exact64": [0, 1, 2, 0, 4],
        "b2_exact64": [0, 0, 2, 3, 4],
    }
    for arm in config["evaluation"]["arms"]:
        for seed in config["training"]["seeds"]:
            path = tmp_path / "runs" / f"seed_{seed}" / arm
            path.mkdir(parents=True)
            (path / "result.json").write_text(
                json.dumps(
                    {
                        "status": config["result_statuses"]["arm_complete"],
                        "protocol_id": config["protocol_id"],
                        "arm": arm,
                        "seed": seed,
                        "evaluation_rows": 5,
                        "evaluation_patient_ids": [f"p{i}" for i in range(5)],
                        "evaluation_example_ids": [f"e{i}" for i in range(5)],
                        "targets": targets,
                        "predictions": predictions[arm],
                        "metrics": {
                            "macro_f1": 1.0 if arm == "prta_exact64" else 0.8,
                            "accuracy": 1.0 if arm == "prta_exact64" else 0.8,
                            "per_class_recall": {},
                        },
                        "head_initialization_sha256": f"init-{seed}",
                        "head_trainable_parameters": config["head"]["parameter_count"],
                        "arm_specific_trainable_parameters": 0,
                        "elapsed_seconds": 1.0,
                        "peak_cuda_allocated_bytes": 1,
                        "method_provenance": config["methods"][arm]["provenance"],
                    }
                ),
                encoding="utf-8",
            )
    result = r52_aggregate.aggregate(tmp_path / "unused.json")
    assert result["same_patients_exact64_head_initialization_training"] is True
    assert result["methods"]["prta_exact64"]["macro_f1_mean"] == 1.0
    assert result["prta_strict_superiority_supported"] in (True, False)
    assert set(result["comparisons"]) == {
        "prta_exact64_minus_tila_exact64",
        "prta_exact64_minus_b2_exact64",
        "tila_exact64_minus_b2_exact64",
    }
