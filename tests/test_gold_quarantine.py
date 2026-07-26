import json

import pytest

from visualvit.gold_quarantine import (
    GoldAccessEvent,
    append_access_event,
    assert_access_is_id_only,
    canonical_manifest,
    quarantined_for_source,
)


def test_manifest_qualifies_patient_ids_by_source():
    manifest = canonical_manifest(
        {"mimic": ["patient12", "12"], "chexpert": ["patient12"]}
    )
    assert manifest["patient_count"] == 2
    assert quarantined_for_source(manifest, "mimic") == {"patient12"}
    assert quarantined_for_source(manifest, "chexpert") == {"patient12"}


def test_gold_access_rejects_outcomes_and_records_id_only_event(tmp_path):
    with pytest.raises(ValueError, match="ID/source"):
        assert_access_is_id_only(["patient_id", "progression"])

    path = tmp_path / "gold_access_log.jsonl"
    append_access_event(
        path,
        GoldAccessEvent(
            source="official_gold",
            fields=("dataset", "patient_id"),
            purpose="quarantine",
            row_count=7,
        ),
    )
    event = json.loads(path.read_text(encoding="utf-8"))
    assert event["outcomes_read"] is False
    assert event["predictions_generated"] is False
