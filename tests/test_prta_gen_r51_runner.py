from __future__ import annotations

import json
from pathlib import Path

import torch

import scripts.aggregate_prta_gen_r51_matched_interface as r51_aggregate
from scripts.run_prta_gen_r51_matched_interface import _load_arm_tokens


WORKSPACE = Path(__file__).resolve().parents[1]
CONFIG = (
    WORKSPACE
    / "configs"
    / "prta_gen"
    / "prta_gen_r51_matched_interface_v1.json"
)


def _config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_r51_authority_is_fully_matched_and_frozen() -> None:
    config = _config()
    assert config["status"] == "FROZEN_PRTA_GEN_R51_MATCHED_INTERFACE"
    assert config["authority"]["training_rows"] == 2500
    assert config["authority"]["evaluation_rows"] == 500
    assert config["training"]["seeds"] == [17, 29, 43]
    assert config["evaluation"]["arms"] == [
        "prta_exact64",
        "tila_exact64",
        "b2_exact64",
    ]
    assert config["translation"]["trainable_parameters"] == 0
    assert config["model"]["qwen_frozen"] is True
    assert config["methods"]["tila_exact64"]["provenance"].startswith(
        "official_pretrained"
    )
    assert config["methods"]["b2_exact64"]["provenance"].startswith(
        "locally_implemented"
    )


def test_r51_loader_merges_sources_and_applies_common_rms(tmp_path: Path) -> None:
    rows = [
        {"example_id": "e1", "patient_id": "p1", "finding": "Edema"},
        {"example_id": "e2", "patient_id": "p2", "finding": "Edema"},
    ]
    sources = {}
    for name, row in zip(("prta_training", "prta_evaluation"), rows, strict=True):
        tokens = torch.randn(1, 64, 768)
        tokens[:, 60:64] = 0
        shard = tmp_path / f"{name}.pt"
        torch.save(
            {
                "example_ids": [row["example_id"]],
                "patient_ids": [row["patient_id"]],
                "findings": [row["finding"]],
                "true_tokens": tokens,
            },
            shard,
        )
        index = tmp_path / f"{name}.json"
        index.write_text(
            json.dumps({"shards": [{"path": str(shard), "rows": 1}]}),
            encoding="utf-8",
        )
        sources[name] = {"path": str(index), "token_key": "true_tokens"}
    loaded = _load_arm_tokens({"token_sources": sources}, "prta_exact64", rows)
    assert set(loaded) == {"e1", "e2"}
    for value in loaded.values():
        assert value.shape == (64, 768)
        assert value[60:64].eq(0).all()
        rms = value[:60].float().square().mean(dim=-1).sqrt()
        assert torch.allclose(rms, torch.ones_like(rms), atol=2e-3)


def test_r51_aggregate_enforces_shared_rows_and_initialization(
    tmp_path: Path, monkeypatch
) -> None:
    config = _config()
    config["training"]["seeds"] = [17, 29]
    config["evaluation"]["paired_patient_bootstrap_replicates"] = 20
    config["runtime"]["runs"] = str(tmp_path / "runs")
    config["runtime"]["aggregate"] = str(tmp_path / "aggregate.json")
    rows = [
        {
            "patient_id": f"p{i}",
            "example_id": f"e{i}",
            "progression": label,
        }
        for i, label in enumerate(("Stable", "Improved", "Worse", "New", "Resolved"))
    ]
    monkeypatch.setattr(
        r51_aggregate,
        "validate_authority",
        lambda *_args, **_kwargs: (config, [], rows),
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
                            "progression_accuracy": 1.0 if arm == "prta_exact64" else 0.8,
                            "schema_validity": 1.0,
                            "finding_echo_accuracy": 1.0,
                            "per_class_recall": {},
                        },
                        "projector_initialization_sha256": f"init-{seed}",
                        "projector_trainable_parameters": 10,
                        "qwen_trainable_parameters": 0,
                        "translation_trainable_parameters": 0,
                        "elapsed_seconds": 1.0,
                        "peak_cuda_allocated_bytes": 1,
                        "method_provenance": config["methods"][arm]["provenance"],
                    }
                ),
                encoding="utf-8",
            )
    result = r51_aggregate.aggregate(tmp_path / "unused-config.json")
    assert result["same_patients_targets_prompt_projector_qwen"] is True
    assert result["patients"] == 5
    assert result["methods"]["prta_exact64"]["macro_f1_mean"] == 1.0
    assert set(result["comparisons"]) == {
        "tila_exact64_minus_prta_exact64",
        "b2_exact64_minus_prta_exact64",
        "tila_exact64_minus_b2_exact64",
    }
