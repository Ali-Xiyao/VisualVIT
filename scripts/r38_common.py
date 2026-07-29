from __future__ import annotations

import json
from pathlib import Path
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[1]
DEFAULT_R38_CONFIG = (
    WORKSPACE / "configs" / "r38" / "r38_fixed64_survival_v1.json"
)


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True), encoding="utf-8"
    )


def load_r38_config(path: Path = DEFAULT_R38_CONFIG) -> dict[str, Any]:
    config = read_json(path)
    if config.get("status") != "FROZEN_R38_FIXED64_SURVIVAL_AFTER_R37C_GO":
        raise PermissionError("R38 configuration is not frozen")
    if config.get("candidate_id") != "r37-1-a6-three-seed-v1":
        raise ValueError("R38 candidate drift")
    if config.get("seeds") != [17, 29, 43]:
        raise ValueError("R38 seed roster drift")
    if config.get("token_budget") != 64:
        raise ValueError("R38 token budget drift")
    counts = [int(item["count"]) for item in config["layout"]]
    if counts != [4, 12, 16, 16, 12, 4] or sum(counts) != 64:
        raise ValueError("R38 token layout drift")
    packing = config["packing"]
    if (
        packing.get("sample_level_routing") is not False
        or packing.get("trainable_parameters") != 0
        or packing.get("labels_or_probe_logits_in_tokens") is not False
        or packing.get("physical_attention_positions") != 64
    ):
        raise PermissionError("R38 packing firewall drift")
    expected_gate = {
        "minimum_gain_pp": 2.0,
        "ci95_lower_must_exceed": 0.0,
        "all_three_seeds_must_be_positive": True,
        "correct_prior_effect_retention_minimum": 0.7,
        "bootstrap_replicates": 2000,
        "bootstrap_seed": 37001,
        "stop_on_any_failed_gate": True,
    }
    observed = {key: config["gate"].get(key) for key in expected_gate}
    if observed != expected_gate:
        raise ValueError(f"R38 gate drift: {observed}")
    upstream = read_json(Path(config["upstream_qualification"]))
    if (
        upstream.get("status") != config["required_upstream_status"]
        or upstream.get("scientific_go") is not True
        or upstream.get("r38_unlocked") is not True
        or upstream.get("sealed_483_test_read") is not False
        or upstream.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("R38 upstream GO/firewall receipt drift")
    return config
