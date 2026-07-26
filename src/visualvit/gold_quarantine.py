from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable, Mapping, Sequence


_ALLOWED_ACCESS_FIELDS = frozenset(
    {
        "dataset",
        "patient_id",
        "subject_id",
        "source",
        "study_id",
        "dicom_id",
        "image_id",
        "img_path_prev",
        "img_path_curr",
    }
)
_FORBIDDEN_ACCESS_TERMS = frozenset(
    {
        "label",
        "progression",
        "outcome",
        "metric",
        "prediction",
        "comparison",
        "attribute",
        "finding",
    }
)


def normalize_patient_id(value: object) -> str:
    text = str(value).strip().lower()
    if not text:
        raise ValueError("patient ID must not be empty")
    numeric = re.sub(r"\D", "", text)
    return f"patient{numeric}" if numeric else text


def qualified_patient_id(dataset: object, patient_id: object) -> str:
    source = str(dataset).strip().lower()
    if not source:
        raise ValueError("dataset/source must not be empty")
    return f"{source}:{normalize_patient_id(patient_id)}"


def canonical_manifest(
    source_to_patients: Mapping[str, Iterable[object]],
) -> dict[str, object]:
    sources = {}
    union = set()
    for source, patients in sorted(source_to_patients.items()):
        normalized = sorted(
            {qualified_patient_id(source, patient) for patient in patients}
        )
        sources[str(source).lower()] = {
            "patient_count": len(normalized),
            "patient_ids": normalized,
        }
        union.update(normalized)
    payload = {
        "schema": "visualvit.r32.gold-quarantine.v1",
        "allowed_access_fields": sorted(_ALLOWED_ACCESS_FIELDS),
        "forbidden_access_terms": sorted(_FORBIDDEN_ACCESS_TERMS),
        "sources": sources,
        "patient_count": len(union),
        "patient_ids": sorted(union),
    }
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    payload["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


def assert_access_is_id_only(fields: Sequence[str]) -> None:
    normalized = {str(field).strip().lower() for field in fields}
    forbidden = sorted(
        field
        for field in normalized
        if field not in _ALLOWED_ACCESS_FIELDS
        or any(term in field for term in _FORBIDDEN_ACCESS_TERMS)
    )
    if forbidden:
        raise ValueError(
            "gold quarantine permits ID/source fields only; forbidden: "
            + ", ".join(forbidden)
        )


@dataclass(frozen=True)
class GoldAccessEvent:
    source: str
    fields: tuple[str, ...]
    purpose: str
    row_count: int

    def to_json(self) -> dict[str, object]:
        assert_access_is_id_only(self.fields)
        if self.row_count < 0:
            raise ValueError("row_count must be non-negative")
        return {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "event": "GOLD_ID_ONLY_ACCESS",
            "source": self.source,
            "fields": list(self.fields),
            "purpose": self.purpose,
            "row_count": self.row_count,
            "outcomes_read": False,
            "metrics_read": False,
            "predictions_generated": False,
        }


def append_access_event(path: Path, event: GoldAccessEvent) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(event.to_json(), ensure_ascii=False, sort_keys=True)
            + "\n"
        )


def quarantined_for_source(
    manifest: Mapping[str, object], source: str
) -> set[str]:
    sources = manifest.get("sources")
    if not isinstance(sources, Mapping):
        raise ValueError("invalid quarantine manifest: missing sources")
    entry = sources.get(source.lower())
    if not isinstance(entry, Mapping):
        return set()
    patient_ids = entry.get("patient_ids")
    if not isinstance(patient_ids, list):
        raise ValueError("invalid quarantine source entry")
    return {
        str(item).split(":", 1)[1]
        for item in patient_ids
        if str(item).startswith(f"{source.lower()}:")
    }
