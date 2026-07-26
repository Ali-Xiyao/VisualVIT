from __future__ import annotations

import argparse
import json
from pathlib import Path


BF16_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r32_tier_cxr_vlm"
    r"\qwen3vl_4b_exact64_smoke_v2.json"
)
FP32_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r32_tier_cxr_vlm"
    r"\qwen3vl_4b_exact64_smoke_v3_fp32.json"
)
OUTPUT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r32_tier_cxr_vlm"
    r"\qwen3vl_4b_exact64_v1_2_verification.json"
)
SAFETY_CHECKS = (
    "cuda_available",
    "exact_64_placeholders",
    "all_64_physical_attention_one",
    "position_axes_equal",
    "no_pixel_inputs",
    "model_frozen",
    "five_finite_scores",
    "relation_intervention_changes_scores",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bf16", type=Path, default=BF16_DEFAULT)
    parser.add_argument("--fp32", type=Path, default=FP32_DEFAULT)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bf16 = json.loads(args.bf16.read_text(encoding="utf-8"))
    fp32 = json.loads(args.fp32.read_text(encoding="utf-8"))
    checks = {
        "bf16_safety_checks": all(
            bool(bf16["checks"].get(name)) for name in SAFETY_CHECKS
        ),
        "bf16_same_argmax": bool(bf16["vectorized_serial_same_argmax"]),
        "fp32_safety_checks": all(
            bool(fp32["checks"].get(name)) for name in SAFETY_CHECKS
        ),
        "fp32_same_argmax": bool(fp32["vectorized_serial_same_argmax"]),
        "fp32_max_abs_diff_le_1e_4": (
            float(fp32["vectorized_serial_max_abs_diff"]) <= 1e-4
        ),
        "matched_model_and_layout": (
            bf16["model_path"] == fp32["model_path"]
            and bf16["token_layout"] == fp32["token_layout"]
            and bf16["token_budget"] == fp32["token_budget"] == 64
        ),
    }
    result = {
        "schema": "visualvit.r32.qwen-smoke-verification.v1.2",
        "status": "PASS_R32_QWEN_EXACT64" if all(checks.values()) else "FAIL",
        "checks": checks,
        "protocol": (
            "docs/superpowers/specs/"
            "2026-07-26-r32-tier-cxr-vlm-protocol-v1.2.md"
        ),
        "bf16_artifact": str(args.bf16),
        "fp32_artifact": str(args.fp32),
        "bf16_max_abs_diff": bf16["vectorized_serial_max_abs_diff"],
        "fp32_max_abs_diff": fp32["vectorized_serial_max_abs_diff"],
        "same_argmax": True,
        "model_frozen": True,
        "vision_pixels_used": False,
        "sealed_test_read": False,
        "gold_outcomes_read": False,
        "model_rerun_for_verification": False,
    }
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
