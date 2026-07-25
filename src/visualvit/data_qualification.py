from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


MANIFEST_SCHEMA_VERSION = "visualvit.longitudinal-assets.v1"
AUDIT_SCHEMA_VERSION = "visualvit.data-qualification-audit.v1"
ALLOWED_SPLITS = ("train", "dev", "test", "external_test")

MANIFEST_SCHEMA_V1: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": MANIFEST_SCHEMA_VERSION,
    "type": "object",
    "required": ["schema_version", "sources", "records", "images_to_avoid"],
    "properties": {
        "schema_version": {"const": MANIFEST_SCHEMA_VERSION},
        "sources": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": [
                    "source_id",
                    "license_status",
                    "license_reference",
                    "dua_status",
                    "dua_reference",
                    "authorized",
                ],
            },
        },
        "records": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": [
                    "source_id",
                    "lineage_source_id",
                    "patient_id",
                    "study_id",
                    "image_id",
                    "split",
                    "file_path",
                ],
                "properties": {
                    "split": {"enum": list(ALLOWED_SPLITS)},
                    "sha256": {
                        "type": "string",
                        "pattern": "^[0-9a-fA-F]{64}$",
                    },
                },
            },
        },
        "images_to_avoid": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["lineage_source_id", "image_id"],
            },
        },
    },
}

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Return the SHA256 of a regular file without loading it into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_identifier(value: object, *, kind: str) -> str:
    """Normalize an opaque lineage ID conservatively and deterministically.

    Unicode is normalized with NFKC, text is case-folded, and punctuation or
    whitespace runs become one hyphen. Leading zeroes are retained because IDs
    are opaque rather than numbers.
    """

    if isinstance(value, bool) or value is None:
        raise ValueError(f"{kind} must be a non-empty string or integer")
    if not isinstance(value, (str, int)):
        raise ValueError(f"{kind} must be a non-empty string or integer")
    text = unicodedata.normalize("NFKC", str(value)).strip().casefold()
    pieces: list[str] = []
    separator_pending = False
    for character in text:
        if character.isalnum():
            if separator_pending and pieces:
                pieces.append("-")
            pieces.append(character)
            separator_pending = False
        else:
            separator_pending = True
    normalized = "".join(pieces).strip("-")
    if not normalized:
        raise ValueError(f"{kind} normalizes to an empty identifier")
    return normalized


def _status(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().casefold().replace("-", "_").replace(" ", "_")


def _nonempty_text(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _canonical_json_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _record_for_seal(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: record[key]
        for key in (
            "source_id",
            "lineage_source_id",
            "patient_id",
            "study_id",
            "image_id",
            "split",
            "bytes",
            "sha256",
        )
    }


def compute_sealed_split_hash(records: Sequence[Mapping[str, Any]]) -> str:
    """Hash canonical split membership, identities, sizes, and file contents."""

    canonical = [_record_for_seal(record) for record in records]
    canonical.sort(
        key=lambda row: (
            row["split"],
            row["lineage_source_id"],
            row["patient_id"],
            row["study_id"],
            row["image_id"],
            row["source_id"],
            row["sha256"],
        )
    )
    return _canonical_json_sha256(
        {"schema_version": MANIFEST_SCHEMA_VERSION, "records": canonical}
    )


def _duplicate_findings(
    records: Sequence[Mapping[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    identity_specs = {
        "patient": lambda row: (
            row["lineage_source_id"],
            row["patient_id"],
        ),
        "study": lambda row: (
            row["lineage_source_id"],
            row["patient_id"],
            row["study_id"],
        ),
        "image": lambda row: (
            row["lineage_source_id"],
            row["image_id"],
        ),
        "sha256": lambda row: (row["sha256"],),
    }
    cross_split: list[dict[str, Any]] = []
    cross_source: list[dict[str, Any]] = []
    for identity_type, key_function in identity_specs.items():
        groups: dict[tuple[str, ...], list[int]] = defaultdict(list)
        for index, record in enumerate(records):
            if identity_type == "sha256" and record.get("sha256") is None:
                continue
            groups[key_function(record)].append(index)
        for key, indices in sorted(groups.items()):
            splits = sorted({records[index]["split"] for index in indices})
            sources = sorted({records[index]["source_id"] for index in indices})
            if len(splits) > 1:
                cross_split.append(
                    {
                        "identity_type": identity_type,
                        "key": list(key),
                        "splits": splits,
                        "record_indices": indices,
                    }
                )
            if len(sources) > 1:
                cross_source.append(
                    {
                        "identity_type": identity_type,
                        "key": list(key),
                        "sources": sources,
                        "record_indices": indices,
                    }
                )

    exact_groups: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        exact_groups[
            (
                record["source_id"],
                record["lineage_source_id"],
                record["patient_id"],
                record["study_id"],
                record["image_id"],
                record["split"],
            )
        ].append(index)
    duplicate_records = [
        {"key": list(key), "record_indices": indices}
        for key, indices in sorted(exact_groups.items())
        if len(indices) > 1
    ]
    content_groups: dict[str, list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        if record.get("sha256") is not None:
            content_groups[record["sha256"]].append(index)
    content_duplicates = []
    for sha256, indices in sorted(content_groups.items()):
        canonical_identities = {
            (
                records[index]["source_id"],
                records[index]["lineage_source_id"],
                records[index]["patient_id"],
                records[index]["study_id"],
                records[index]["image_id"],
                records[index]["split"],
            )
            for index in indices
        }
        if len(canonical_identities) > 1:
            content_duplicates.append({"sha256": sha256, "record_indices": indices})
    return cross_split, cross_source, duplicate_records, content_duplicates


def qualify_longitudinal_assets(
    manifest: Mapping[str, Any],
    *,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Validate an asset manifest and return a fail-closed audit report."""

    root = (base_dir or Path.cwd()).resolve()
    errors: list[dict[str, Any]] = []

    def add_error(code: str, message: str, **location: int) -> None:
        error: dict[str, Any] = {"code": code, "message": message}
        error.update(location)
        errors.append(error)

    if not isinstance(manifest, Mapping):
        add_error("MANIFEST_SCHEMA", "manifest must be a JSON object")
        manifest = {}
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        add_error(
            "MANIFEST_SCHEMA",
            f"schema_version must equal {MANIFEST_SCHEMA_VERSION!r}",
        )

    raw_sources = manifest.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        add_error("MANIFEST_SCHEMA", "sources must be a non-empty array")
        raw_sources = []
    normalized_sources: list[dict[str, Any]] = []
    source_ids: set[str] = set()
    for source_index, source in enumerate(raw_sources):
        if not isinstance(source, Mapping):
            add_error(
                "MANIFEST_SCHEMA",
                "source entry must be an object",
                source_index=source_index,
            )
            continue
        try:
            source_id = normalize_identifier(source.get("source_id"), kind="source_id")
        except ValueError as error:
            add_error(
                "MANIFEST_SCHEMA",
                str(error),
                source_index=source_index,
            )
            continue
        if source_id in source_ids:
            add_error(
                "MANIFEST_SCHEMA",
                f"duplicate normalized source_id {source_id!r}",
                source_index=source_index,
            )
            continue
        source_ids.add(source_id)
        license_status = _status(source.get("license_status"))
        dua_status = _status(source.get("dua_status"))
        license_reference = _nonempty_text(source.get("license_reference"))
        dua_reference = _nonempty_text(source.get("dua_reference"))
        authorized = source.get("authorized") is True
        if license_status != "verified":
            add_error(
                "SOURCE_QUALIFICATION",
                f"{source_id}: license_status must be 'verified'",
                source_index=source_index,
            )
        if license_reference is None:
            add_error(
                "SOURCE_QUALIFICATION",
                f"{source_id}: license_reference must be explicit",
                source_index=source_index,
            )
        if dua_status not in {"signed", "not_required"}:
            add_error(
                "SOURCE_QUALIFICATION",
                f"{source_id}: dua_status must be 'signed' or 'not_required'",
                source_index=source_index,
            )
        if dua_reference is None:
            add_error(
                "SOURCE_QUALIFICATION",
                f"{source_id}: dua_reference must be explicit",
                source_index=source_index,
            )
        if not authorized:
            add_error(
                "SOURCE_QUALIFICATION",
                f"{source_id}: authorized must be the JSON boolean true",
                source_index=source_index,
            )
        normalized_sources.append(
            {
                "source_id": source_id,
                "license_status": license_status,
                "license_reference": license_reference,
                "dua_status": dua_status,
                "dua_reference": dua_reference,
                "authorized": authorized,
            }
        )

    raw_avoid = manifest.get("images_to_avoid")
    if not isinstance(raw_avoid, list):
        add_error("MANIFEST_SCHEMA", "images_to_avoid must be an explicit array")
        raw_avoid = []
    avoid_keys: set[tuple[str, str]] = set()
    for avoid_index, entry in enumerate(raw_avoid):
        if not isinstance(entry, Mapping):
            add_error(
                "MANIFEST_SCHEMA",
                "images_to_avoid entry must be an object",
                avoid_index=avoid_index,
            )
            continue
        try:
            avoid_keys.add(
                (
                    normalize_identifier(
                        entry.get("lineage_source_id"),
                        kind="lineage_source_id",
                    ),
                    normalize_identifier(entry.get("image_id"), kind="image_id"),
                )
            )
        except ValueError as error:
            add_error(
                "MANIFEST_SCHEMA",
                str(error),
                avoid_index=avoid_index,
            )

    raw_records = manifest.get("records")
    if not isinstance(raw_records, list) or not raw_records:
        add_error("MANIFEST_SCHEMA", "records must be a non-empty array")
        raw_records = []
    normalized_records: list[dict[str, Any]] = []
    for record_index, record in enumerate(raw_records):
        if not isinstance(record, Mapping):
            add_error(
                "MANIFEST_SCHEMA",
                "record must be an object",
                record_index=record_index,
            )
            continue
        try:
            source_id = normalize_identifier(record.get("source_id"), kind="source_id")
            lineage_source_id = normalize_identifier(
                record.get("lineage_source_id"), kind="lineage_source_id"
            )
            patient_id = normalize_identifier(
                record.get("patient_id"), kind="patient_id"
            )
            study_id = normalize_identifier(record.get("study_id"), kind="study_id")
            image_id = normalize_identifier(record.get("image_id"), kind="image_id")
        except ValueError as error:
            add_error(
                "MANIFEST_SCHEMA",
                str(error),
                record_index=record_index,
            )
            continue
        split = _status(record.get("split"))
        if split not in ALLOWED_SPLITS:
            add_error(
                "MANIFEST_SCHEMA",
                f"split must be one of {ALLOWED_SPLITS}",
                record_index=record_index,
            )
            continue
        if source_id not in source_ids:
            add_error(
                "SOURCE_QUALIFICATION",
                f"record source {source_id!r} has no source qualification",
                record_index=record_index,
            )

        path_value = record.get("file_path")
        if not isinstance(path_value, str) or not path_value.strip():
            add_error(
                "MANIFEST_SCHEMA",
                "file_path must be a non-empty string",
                record_index=record_index,
            )
            continue
        path = Path(path_value)
        if not path.is_absolute():
            path = root / path
        path = path.resolve()

        expected_hash = record.get("sha256")
        if expected_hash is not None:
            if not isinstance(expected_hash, str) or not _SHA256_PATTERN.fullmatch(
                expected_hash.casefold()
            ):
                add_error(
                    "MANIFEST_SCHEMA",
                    "sha256 must contain exactly 64 hexadecimal characters",
                    record_index=record_index,
                )
                expected_hash = None
            else:
                expected_hash = expected_hash.casefold()

        actual_hash: str | None = None
        file_bytes: int | None = None
        if not path.is_file():
            add_error(
                "FILE_MISSING",
                f"file does not exist or is not a regular file: {path}",
                record_index=record_index,
            )
        else:
            actual_hash = sha256_file(path)
            file_bytes = path.stat().st_size
            if expected_hash is not None and expected_hash != actual_hash:
                add_error(
                    "HASH_MISMATCH",
                    f"expected SHA256 does not match file: {path}",
                    record_index=record_index,
                )

        if (lineage_source_id, image_id) in avoid_keys:
            add_error(
                "IMAGE_TO_AVOID",
                f"record contains a prohibited image: {lineage_source_id}/{image_id}",
                record_index=record_index,
            )
        normalized_records.append(
            {
                "source_id": source_id,
                "lineage_source_id": lineage_source_id,
                "patient_id": patient_id,
                "study_id": study_id,
                "image_id": image_id,
                "split": split,
                "file_path": str(path),
                "bytes": file_bytes,
                "sha256": actual_hash,
                "expected_sha256": expected_hash,
            }
        )

    cross_split, cross_source, duplicate_records, content_duplicates = (
        _duplicate_findings(normalized_records)
    )
    if cross_split:
        add_error(
            "CROSS_SPLIT_DUPLICATE",
            f"found {len(cross_split)} cross-split identity/content overlaps",
        )
    if cross_source:
        add_error(
            "CROSS_SOURCE_DUPLICATE",
            f"found {len(cross_source)} cross-source identity/content overlaps",
        )
    if duplicate_records:
        add_error(
            "DUPLICATE_RECORD",
            f"found {len(duplicate_records)} duplicate manifest identities",
        )
    if content_duplicates:
        add_error(
            "CONTENT_DUPLICATE",
            f"found {len(content_duplicates)} duplicate file contents",
        )

    error_codes = {error["code"] for error in errors}
    checks = {
        "manifest_schema_valid": "MANIFEST_SCHEMA" not in error_codes,
        "source_license_dua_authorized": "SOURCE_QUALIFICATION" not in error_codes,
        "all_files_present_and_hashed": not (
            {"FILE_MISSING", "MANIFEST_SCHEMA"} & error_codes
        )
        and len(normalized_records) == len(raw_records)
        and all(record["sha256"] is not None for record in normalized_records),
        "expected_hashes_match": "HASH_MISMATCH" not in error_codes,
        "images_to_avoid_excluded": "IMAGE_TO_AVOID" not in error_codes,
        "no_cross_split_duplicates": not cross_split,
        "no_cross_source_duplicates": not cross_source,
        "unique_manifest_records": not duplicate_records,
        "unique_file_contents": not content_duplicates,
    }
    qualified = bool(normalized_records) and all(checks.values())

    sealed_splits: dict[str, dict[str, Any]] = {}
    sealed_split_hash: str | None = None
    if qualified:
        for split in ALLOWED_SPLITS:
            split_records = [
                record for record in normalized_records if record["split"] == split
            ]
            if split_records:
                sealed_splits[split] = {
                    "records": len(split_records),
                    "sha256": compute_sealed_split_hash(split_records),
                }
        sealed_split_hash = compute_sealed_split_hash(normalized_records)

    qualification_input = {
        "schema_version": manifest.get("schema_version"),
        "sources": sorted(normalized_sources, key=lambda row: row["source_id"]),
        "images_to_avoid": [
            {"lineage_source_id": key[0], "image_id": key[1]}
            for key in sorted(avoid_keys)
        ],
        "records": sorted(
            [
                {
                    **_record_for_seal(record),
                    "expected_sha256": record["expected_sha256"],
                }
                for record in normalized_records
            ],
            key=lambda row: (
                row["split"],
                row["lineage_source_id"],
                row["patient_id"],
                row["study_id"],
                row["image_id"],
                row["source_id"],
            ),
        ),
    }
    qualification_input_hash = _canonical_json_sha256(qualification_input)

    return {
        "audit_schema_version": AUDIT_SCHEMA_VERSION,
        "manifest_schema_version": manifest.get("schema_version"),
        "status": "PASS" if qualified else "FAIL",
        "qualified": qualified,
        "formal_use_allowed": qualified,
        "checks": checks,
        "counts": {
            "sources": len(normalized_sources),
            "records_declared": len(raw_records),
            "records_audited": len(normalized_records),
            "images_to_avoid": len(avoid_keys),
        },
        "sources": sorted(normalized_sources, key=lambda row: row["source_id"]),
        "records": sorted(
            normalized_records,
            key=lambda row: (
                row["split"],
                row["lineage_source_id"],
                row["patient_id"],
                row["study_id"],
                row["image_id"],
                row["source_id"],
            ),
        ),
        "duplicates": {
            "cross_split": cross_split,
            "cross_source": cross_source,
            "exact_records": duplicate_records,
            "content": content_duplicates,
        },
        "sealed_splits": sealed_splits,
        "sealed_split_hash": sealed_split_hash,
        "qualification_input_hash": qualification_input_hash,
        "errors": errors,
    }


def write_audit_json(report: Mapping[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
