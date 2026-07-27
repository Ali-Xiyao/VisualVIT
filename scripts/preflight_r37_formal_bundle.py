from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts.run_r37_prta_smoke import (
    FORMAL_ADAPTER_RANK,
    FORMAL_BATCH_SIZE,
    FORMAL_CALIBRATION_EXAMPLES,
    FORMAL_EPOCHS,
    FORMAL_LEARNING_RATE,
    FORMAL_SEEDS,
    FORMAL_TRAIN_EXAMPLES,
    FORMAL_VARIANT,
)
from scripts.run_r37_a0_frozen_probe import (
    FORMAL_A0_BATCH_SIZE,
    FORMAL_A0_EPOCHS,
    FORMAL_A0_LEARNING_RATE,
)
from visualvit.qualification import (
    PATIENT_BOOTSTRAP_REPLICATES,
    PATIENT_BOOTSTRAP_SEED,
)


DEFAULT_SPEC = Path("configs/r37/prta_a6_formal_bundle_v1.json")
DEFAULT_OUTPUT = Path(
    r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr"
    r"\r37_formal_bundle_preflight.json"
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def exact_spec_checks(spec: dict[str, Any]) -> dict[str, bool]:
    training = spec.get("training", {})
    qualification = spec.get("qualification", {})
    firewall = spec.get("firewall", {})
    baseline = spec.get("baseline_a0", {})
    return {
        "schema": (
            spec.get("schema")
            == "visualvit.r37.prta-formal-bundle-spec.v1"
        ),
        "variant": spec.get("variant") == FORMAL_VARIANT,
        "seeds": tuple(spec.get("seeds", ())) == FORMAL_SEEDS,
        "selection": (
            training.get("selection") == "all_seed_independent_order"
        ),
        "train_examples": (
            training.get("train_examples") == FORMAL_TRAIN_EXAMPLES
        ),
        "calibration_examples": (
            training.get("calibration_examples")
            == FORMAL_CALIBRATION_EXAMPLES
        ),
        "train_pairs": training.get("train_pairs") == 33_621,
        "calibration_pairs": (
            training.get("calibration_pairs") == 3_770
        ),
        "epochs": training.get("epochs") == FORMAL_EPOCHS,
        "batch_size": training.get("batch_size") == FORMAL_BATCH_SIZE,
        "learning_rate": (
            training.get("learning_rate") == FORMAL_LEARNING_RATE
        ),
        "adapter_rank": (
            training.get("adapter_rank") == FORMAL_ADAPTER_RANK
        ),
        "bootstrap_replicates": (
            qualification.get("bootstrap_replicates")
            == PATIENT_BOOTSTRAP_REPLICATES
        ),
        "bootstrap_seed": (
            qualification.get("bootstrap_seed") == PATIENT_BOOTSTRAP_SEED
        ),
        "bootstrap_unit": (
            qualification.get("bootstrap_unit") == "patient_cluster"
        ),
        "controls": qualification.get("controls")
        == ["current_only", "cmcp"],
        "inversion_threshold": (
            qualification.get("inversion_consistency_minimum") == 0.9
        ),
        "state_retention_threshold": (
            qualification.get("state_retention_cosine_minimum") == 0.99
        ),
        "a6_vs_a0_threshold": (
            qualification.get("a6_minus_a0_minimum_pp") == 2.0
        ),
        "a0_selection": (
            baseline.get("selection") == "all_seed_independent_order"
        ),
        "a0_seeds": tuple(baseline.get("seeds", ())) == FORMAL_SEEDS,
        "a0_epochs": baseline.get("epochs") == FORMAL_A0_EPOCHS,
        "a0_batch_size": (
            baseline.get("batch_size") == FORMAL_A0_BATCH_SIZE
        ),
        "a0_learning_rate": (
            baseline.get("learning_rate") == FORMAL_A0_LEARNING_RATE
        ),
        "firewalls_frozen_false": all(
            firewall.get(key) is False
            for key in (
                "protected_outcomes_read",
                "sealed_test_read",
                "gold_outcomes_read",
                "source_hashes_recomputed",
                "per_shard_hashes_computed",
            )
        ),
    }


def seed_output_state(
    root: Path,
    seed: int,
    *,
    schema: str = "visualvit.r37.prta-formal-training.v1",
    status: str = "PASS_R37_PRTA_FORMAL_TRAINING",
    variant: str = FORMAL_VARIANT,
) -> dict[str, Any]:
    seed_root = root / f"seed_{seed}"
    if not seed_root.exists():
        return {"seed": seed, "state": "fresh", "path": str(seed_root)}
    result_path = seed_root / "result.json"
    checkpoint_path = seed_root / "checkpoint.pt"
    if not result_path.is_file() or not checkpoint_path.is_file():
        return {"seed": seed, "state": "partial", "path": str(seed_root)}
    result = read_json(result_path)
    complete = (
        result.get("schema") == schema
        and result.get("status") == status
        and result.get("seed") == seed
        and result.get("variant") == variant
        and result.get("formal") is True
        and result.get("protected_outcomes_read") is False
        and result.get("sealed_test_read") is False
        and result.get("gold_outcomes_read") is False
        and result.get("source_hashes_recomputed") is False
        and result.get("scientific_claim_allowed") is False
    )
    return {
        "seed": seed,
        "state": "complete" if complete else "invalid_complete",
        "path": str(seed_root),
    }


def inspect_bundle(spec: dict[str, Any]) -> dict[str, Any]:
    checks = exact_spec_checks(spec)
    artifacts = spec.get("artifacts", {})
    expected = spec.get("expected", {})
    transition_root = Path(str(artifacts.get("transition_root", "")))
    cache_root = Path(str(artifacts.get("block8_cache_root", "")))
    text_cache = Path(str(artifacts.get("text_cache", "")))
    cmcp_path = Path(str(artifacts.get("cmcp_index", "")))
    output_root = Path(str(artifacts.get("formal_output_root", "")))

    transition_audit_path = transition_root / "r37_transition_audit.json"
    pretrain_path = transition_root / "r37_pretrain_manifest.jsonl"
    calibration_path = (
        transition_root / "r37_internal_calibration_manifest.jsonl"
    )
    cache_manifest_path = cache_root / "cache_manifest.json"
    required_paths = {
        "transition_audit": transition_audit_path,
        "pretrain_manifest": pretrain_path,
        "calibration_manifest": calibration_path,
        "block8_manifest": cache_manifest_path,
        "text_cache": text_cache,
        "cmcp_index": cmcp_path,
    }
    checks.update(
        {
            f"path_{name}": path.is_file()
            for name, path in required_paths.items()
        }
    )
    if not all(checks[f"path_{name}"] for name in required_paths):
        return _result(spec, checks, [], [], human_qa_unlocked=False)

    transition = read_json(transition_audit_path)
    cache = read_json(cache_manifest_path)
    cmcp = read_json(cmcp_path)
    partition_counts = cmcp.get("partition_counts", {})
    dynamic_examples = sum(
        int(item.get("dynamic_examples", -1))
        for item in partition_counts.values()
    )
    matched_examples = sum(
        int(item.get("matched_dynamic_examples", -2))
        for item in partition_counts.values()
    )
    human_qa_unlocked = transition.get("formal_training_unlocked") is True
    checks.update(
        {
            "transition_ruleset": (
                transition.get("ruleset_version")
                == expected.get("transition_ruleset")
            ),
            "transition_status": transition.get("status")
            in {
                expected.get("transition_status_pending"),
                "PASS_R37A_TRANSITION_QUALITY",
            },
            "transition_counts": (
                transition.get("transition_example_counts", {}).get(
                    "pretrain"
                )
                == spec["training"]["train_examples"]
                and transition.get(
                    "transition_example_counts", {}
                ).get("internal_calibration")
                == spec["training"]["calibration_examples"]
            ),
            "transition_pair_counts": (
                transition.get("eligible_transition_pair_counts", {}).get(
                    "pretrain"
                )
                == spec["training"]["train_pairs"]
                and transition.get(
                    "eligible_transition_pair_counts", {}
                ).get("internal_calibration")
                == spec["training"]["calibration_pairs"]
            ),
            "transition_protected_firewall": (
                transition.get("protected_outcomes_read") is False
            ),
            "block8_status": (
                cache.get("status") == expected.get("block8_status")
            ),
            "block8_counts": (
                cache.get("cached_image_count")
                == expected.get("block8_images")
                and cache.get("formal_inventory_count")
                == expected.get("block8_images")
                and cache.get("shard_count") == expected.get("block8_shards")
            ),
            "block8_firewalls": (
                cache.get("protected_outcomes_read") is False
                and cache.get("source_hashes_recomputed") is False
                and cache.get("per_shard_hashes_computed") is False
            ),
            "cmcp_status": (
                cmcp.get("status") == expected.get("cmcp_status")
            ),
            "cmcp_counts": (
                dynamic_examples == expected.get("cmcp_dynamic_examples")
                and matched_examples == dynamic_examples
            ),
            "cmcp_coverage": all(
                item.get("coverage") == expected.get("cmcp_coverage")
                for item in partition_counts.values()
            ),
            "cmcp_firewalls": (
                cmcp.get("protected_outcomes_read") is False
                and cmcp.get("target_outcome_passed_to_model") is False
            ),
        }
    )
    output_states = [
        seed_output_state(output_root, seed) for seed in FORMAL_SEEDS
    ]
    a0_output_root = Path(
        str(spec.get("baseline_a0", {}).get("formal_output_root", ""))
    )
    a0_output_states = [
        seed_output_state(
            a0_output_root,
            seed,
            schema="visualvit.r37.a0-formal-probe.v1",
            status="PASS_R37_A0_FORMAL_PROBE",
            variant="A0",
        )
        for seed in FORMAL_SEEDS
    ]
    checks["a6_output_states_resumable"] = all(
        item["state"] in {"fresh", "complete"} for item in output_states
    )
    checks["a0_output_states_resumable"] = all(
        item["state"] in {"fresh", "complete"} for item in a0_output_states
    )
    return _result(
        spec,
        checks,
        output_states,
        a0_output_states,
        human_qa_unlocked,
    )


def _result(
    spec: dict[str, Any],
    checks: dict[str, bool],
    output_states: list[dict[str, Any]],
    a0_output_states: list[dict[str, Any]],
    human_qa_unlocked: bool,
) -> dict[str, Any]:
    engineering_preflight_passed = all(checks.values())
    formal_execution_allowed = (
        engineering_preflight_passed and human_qa_unlocked
    )
    if not engineering_preflight_passed:
        status = "STOP_R37_FORMAL_BUNDLE_PREFLIGHT"
    elif formal_execution_allowed:
        status = "READY_R37_FORMAL_BUNDLE"
    else:
        status = "READY_R37_FORMAL_BUNDLE_PENDING_HUMAN_QA"
    artifacts = spec.get("artifacts", {})
    commands = [
        (
            "python scripts/run_r37_prta_smoke.py --formal --variant A6 "
            f"--seed {seed} --device cuda:DEVICE "
            "--max-train-examples 0 --max-calibration-examples 0 "
            "--epochs 3 --batch-size 2 --learning-rate 0.0001 "
            "--adapter-rank 32 "
            f"--transition-root \"{artifacts.get('transition_root')}\" "
            f"--cache-root \"{artifacts.get('block8_cache_root')}\" "
            f"--text-cache \"{artifacts.get('text_cache')}\" "
            f"--cmcp-index \"{artifacts.get('cmcp_index')}\" "
            f"--output-root \"{Path(str(artifacts.get('formal_output_root'))) / f'seed_{seed}'}\""
        )
        for seed in FORMAL_SEEDS
    ]
    a0 = spec.get("baseline_a0", {})
    baseline_commands = [
        (
            "python scripts/run_r37_a0_frozen_probe.py --formal "
            f"--seed {seed} --device cuda:DEVICE "
            "--max-train-examples 0 --max-calibration-examples 0 "
            "--epochs 100 --batch-size 16 --learning-rate 0.01 "
            f"--transition-root \"{artifacts.get('transition_root')}\" "
            f"--cache-root \"{artifacts.get('block8_cache_root')}\" "
            f"--text-cache \"{artifacts.get('text_cache')}\" "
            f"--output-root \"{Path(str(a0.get('formal_output_root'))) / f'seed_{seed}'}\""
        )
        for seed in FORMAL_SEEDS
    ]
    return {
        "schema": "visualvit.r37.prta-formal-bundle-preflight.v1",
        "bundle_id": spec.get("bundle_id"),
        "status": status,
        "engineering_preflight_passed": engineering_preflight_passed,
        "formal_execution_allowed": formal_execution_allowed,
        "human_qa_unlocked": human_qa_unlocked,
        "checks": checks,
        "seed_output_states": output_states,
        "a0_seed_output_states": a0_output_states,
        "handoff_commands": commands,
        "baseline_handoff_commands": baseline_commands,
        "protected_outcomes_read": False,
        "sealed_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "scientific_claim_allowed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the frozen R37 A6 formal bundle without training"
    )
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = inspect_bundle(read_json(args.spec))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 2 if result["status"].startswith("STOP_") else 0


if __name__ == "__main__":
    raise SystemExit(main())
