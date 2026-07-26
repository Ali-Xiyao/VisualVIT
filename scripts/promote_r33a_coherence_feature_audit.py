from __future__ import annotations

import json
from pathlib import Path

import torch


SOURCE = Path(
    r"F:\VisualVIT_runtime\050_routeC\r33a_case_study"
    r"\coherence_features_v1\token_features.pt"
)
OUTPUT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r33a_case_study"
    r"\coherence_features_v2\token_features.pt"
)


def main() -> int:
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    if OUTPUT.exists():
        raise FileExistsError(f"output must be fresh: {OUTPUT}")
    payload = torch.load(SOURCE, map_location="cpu", weights_only=False)
    if payload.get("variant") != "r33a_coherence_adapter_v1":
        raise RuntimeError("unexpected source variant")
    payload.update(
        {
            "variant": "r33a_coherence_adapter_v2_audit_registered",
            "biomedclip_text_encoder_frozen": True,
            "builders_frozen": True,
            "prior_shuffle_cross_patient": True,
            "literal_query_only_type": True,
            "finding_query_outcome_free": True,
            "anatomy_masks_outcome_free": True,
            "audit_promotion_source": str(SOURCE),
            "audit_promotion_recomputed_features": False,
            "audit_promotion_recomputed_hashes": False,
        }
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=False)
    torch.save(payload, OUTPUT)
    summary = {
        key: value
        for key, value in payload.items()
        if key not in {"records", "features"}
    }
    summary.update(
        {
            "record_count": len(payload["records"]),
            "patient_count": len(
                {str(row["patient_id"]) for row in payload["records"]}
            ),
            "output": str(OUTPUT),
            "output_bytes": OUTPUT.stat().st_size,
        }
    )
    (OUTPUT.parent / "feature_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
