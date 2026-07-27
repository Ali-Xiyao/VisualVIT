from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

import pandas as pd


SCHEMA = "visualvit.r37.report-transitions.v1"
RULESET_VERSION = "r37-report-transition-v4.1"
LABELS = ("Stable", "Improved", "Worse", "New", "Resolved")
DYNAMIC_LABELS = ("Improved", "Worse", "New", "Resolved")

FINDING_ALIASES: dict[str, tuple[str, ...]] = {
    "Atelectasis": (r"\batelecta(?:sis|tic)\b",),
    "Cardiomegaly": (
        r"\bcardiomegaly\b",
        r"\benlargement of (?:the )?(?:cardiac|cardiomediastinal) silhouette\b",
    ),
    "Consolidation": (
        r"\bconsolidation\b",
        r"\bairspace (?:disease|consolidation)\b",
    ),
    "Edema": (
        r"\b(?:pulmonary |interstitial )?edema\b",
        r"\bvascular congestion\b",
    ),
    "Enlarged Cardiomediastinum": (
        r"\bcardiomediastinal silhouette\b",
        r"\bmediastinal widening\b",
    ),
    "Fracture": (r"\bfracture[sd]?\b",),
    "Lung Lesion": (
        r"\b(?:lung |pulmonary )?(?:nodule|nodules|mass|masses)\b",
    ),
    "Lung Opacity": (
        r"\b(?:lung |pulmonary |airspace |parenchymal )?"
        r"(?:opacity|opacities|infiltrate|infiltrates)\b",
    ),
    "Pleural Effusion": (
        r"\b(?:pleural )?effusion[sd]?\b",
    ),
    "Pleural Other": (
        r"\bpleural (?:thickening|scar|scarring)\b",
    ),
    "Pneumonia": (r"\bpneumonia\b",),
    "Pneumothorax": (r"\bpneumothora(?:x|ces)\b",),
}

CUE_PATTERNS: dict[str, tuple[str, ...]] = {
    "New": (
        r"\bnew(?:ly)?\b",
        r"\binterval development of\b",
        r"\bhas developed\b",
    ),
    "Resolved": (
        r"\b(?:has |have )?resolved\b",
        r"\binterval resolution of\b",
        r"\bno longer (?:seen|present|visualized)\b",
        r"\b(?:has |have )?(?:cleared|disappeared)\b",
    ),
    "Improved": (
        r"\b(?:almost|nearly|largely|essentially)(?: completely)? "
        r"(?:resolved|cleared)\b",
        r"\bimprov(?:ed|ing)\b",
        r"\bdecreas(?:ed|ing)\b",
        r"\bdiminish(?:ed|ing)\b",
        r"\b(?:slightly )?smaller (?:than|compared (?:to|with)|since)\b",
        r"\bless (?:prominent|conspicuous|severe|extensive)\b",
        r"\bresolving\b",
    ),
    "Worse": (
        r"\bworsen(?:ed|ing)\b",
        r"\bincreas(?:ed|ing)\b",
        r"\bprogress(?:ed|ing|ion)\b",
        r"\b(?:slightly )?larger (?:than|compared (?:to|with)|since)\b",
        r"\bmore prominent\b",
    ),
    "Stable": (
        r"\bunchanged\b",
        r"\bstable\b",
        r"\bsimilar (?:to|in appearance)\b",
        r"\bno significant (?:interval )?change\b",
        r"\bnot substantially changed\b",
    ),
}

ALL_SECTION_PATTERN = re.compile(
    r"(?im)^\s*(FINDINGS?|IMPRESSION|CONCLUSION|INDICATION|HISTORY|"
    r"CLINICAL HISTORY|REASON FOR EXAM|COMPARISON|EXAMINATION|TECHNIQUE)"
    r"\s*:\s*"
)
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])(?:\s+|(?=[A-Z]))")
CLAUSE_SPLIT = re.compile(
    r";\s*|,\s*(?:but|while|whereas|with)\s+|"
    r"\s+(?:and|or|but|while|whereas|with|without|due to|secondary to|"
    r"suggesting|compatible with|consistent with)\s+",
    re.I,
)
NEGATED_NEW = re.compile(
    r"\b(?:no|without)\b.{0,72}\b(?:new(?:ly)?|interval development)\b",
    re.I,
)
NEGATED_CHANGE = re.compile(
    r"\b(?:no|without)\s+(?:significant\s+)?"
    r"(?:increase|decrease|improvement|worsening|progression|resolution)\b|"
    r"\bnot\s+(?:improved|improving|worsened|worsening|resolved|cleared)\b",
    re.I,
)
NON_ASSERTION = re.compile(
    r"\b(?:evaluate|evaluation|assess|assessment|question|rule out|"
    r"progression vs|resolution vs|improvement/worsening|scheduled for)\b|\?",
    re.I,
)
UNCERTAINTY_SCOPE = re.compile(
    r"\b(?:may|might|could|possibly|potential(?:ly)?|suggest(?:s|ing)?|"
    r"suggestion of|concerning for|worrisome for|"
    r"question of|versus|vs\.?)\b",
    re.I,
)
DIAGNOSTIC_UNCERTAINTY = re.compile(r"\b(?:likely|probably)\b", re.I)
AMBIGUOUS_ALTERNATIVE = re.compile(
    r"\b(?:stable|unchanged|improved|worsened|smaller|larger)\s+or\s+"
    r"(?:stable|unchanged|improved|worsened|increasing|decreasing|resolved)\b",
    re.I,
)
DEVICE_SCOPE = re.compile(r"\b(?:marker|tube|line|catheter|device|lead)\b", re.I)
VOLUME_SCOPE = re.compile(r"\b(?:lung volumes?|inspiration)\b", re.I)
TECHNIQUE_ARTIFACT = re.compile(
    r"\b(?:portable technique|projectional|positioning|rotation|"
    r"body habitus|technique creating|artifact)\b",
    re.I,
)


def stable_hash(*parts: object) -> str:
    return hashlib.sha256(
        "|".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    row, sort_keys=True, ensure_ascii=False, separators=(",", ":")
                )
                + "\n"
            )


def report_sections(text: str) -> list[tuple[str, str]]:
    normalized = text.replace("\x00", " ")
    matches = list(ALL_SECTION_PATTERN.finditer(normalized))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        name = match.group(1).upper()
        if name == "FINDING":
            name = "FINDINGS"
        if name == "CONCLUSION":
            name = "IMPRESSION"
        end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
        sections.append((name, normalized[match.end() : end]))
    selected = [
        item for item in sections if item[0] in {"FINDINGS", "IMPRESSION"}
    ]
    if matches:
        return selected
    return [("UNSECTIONED", normalized)]


def _matches(patterns: Iterable[str], text: str) -> list[re.Match[str]]:
    result: list[re.Match[str]] = []
    for pattern in patterns:
        result.extend(re.finditer(pattern, text, flags=re.I))
    return result


def extract_sentence_annotations(
    sentence: str, *, section: str
) -> list[dict[str, str]]:
    compact = " ".join(sentence.split())
    if len(compact) < 8:
        return []
    if NON_ASSERTION.search(compact):
        return []
    if AMBIGUOUS_ALTERNATIVE.search(compact):
        return []
    if TECHNIQUE_ARTIFACT.search(compact):
        return []
    lowered = compact.lower()
    cue_matches: list[tuple[str, re.Match[str]]] = []
    for label, patterns in CUE_PATTERNS.items():
        for match in _matches(patterns, lowered):
            cue_matches.append((label, match))
    if not cue_matches:
        return []

    annotations: list[dict[str, str]] = []
    for finding, aliases in FINDING_ALIASES.items():
        finding_matches = _matches(aliases, lowered)
        for finding_match in finding_matches:
            candidates: list[tuple[int, str, re.Match[str]]] = []
            finding_center = (finding_match.start() + finding_match.end()) // 2
            for label, cue_match in cue_matches:
                cue_center = (cue_match.start() + cue_match.end()) // 2
                distance = abs(cue_center - finding_center)
                if distance <= 72:
                    candidates.append((distance, label, cue_match))
            if not candidates:
                continue
            candidates.sort(key=lambda item: (item[0], LABELS.index(item[1])))
            distance, label, cue_match = candidates[0]
            local_start = max(0, min(cue_match.start(), finding_match.start()) - 32)
            local_end = min(
                len(lowered), max(cue_match.end(), finding_match.end()) + 24
            )
            local = lowered[local_start:local_end]
            if label == "New" and NEGATED_NEW.search(local):
                continue
            if label in {"Improved", "Worse", "Resolved"} and NEGATED_CHANGE.search(
                local
            ):
                continue
            if (
                label in {"Improved", "Worse"}
                and cue_match.group(0).lower().startswith(
                    ("decreas", "increas")
                )
                and VOLUME_SCOPE.search(local)
            ):
                continue
            if label == "Resolved" and cue_match.group(0).lower().startswith(
                "no longer"
            ) and DEVICE_SCOPE.search(local):
                continue
            if UNCERTAINTY_SCOPE.search(local):
                continue
            if finding in {"Atelectasis", "Edema", "Pneumonia"} and (
                DIAGNOSTIC_UNCERTAINTY.search(local)
            ):
                continue
            if label == "Resolved" and re.search(
                r"(?:cleared|resolved).{0,18}\bmost\b|"
                r"\bmost\b.{0,18}(?:cleared|resolved)",
                local,
                flags=re.I,
            ):
                label = "Improved"
            annotations.append(
                {
                    "finding": finding,
                    "label": label,
                    "section": section,
                    "cue": cue_match.group(0),
                    "sentence": compact,
                    "distance": str(distance),
                }
            )
    unique: dict[tuple[str, str, str], dict[str, str]] = {}
    for item in annotations:
        key = (item["finding"], item["label"], item["sentence"])
        previous = unique.get(key)
        if previous is None or int(item["distance"]) < int(previous["distance"]):
            unique[key] = item
    return list(unique.values())


def extract_report_annotations(text: str) -> list[dict[str, str]]:
    by_section: dict[str, list[dict[str, str]]] = defaultdict(list)
    for section, content in report_sections(text):
        content_without_soft_wraps = " ".join(content.split())
        for sentence in SENTENCE_SPLIT.split(content_without_soft_wraps):
            sentence_compact = " ".join(sentence.split())
            if NEGATED_NEW.search(sentence_compact) or AMBIGUOUS_ALTERNATIVE.search(
                sentence_compact
            ):
                continue
            if UNCERTAINTY_SCOPE.search(sentence_compact):
                continue
            for clause in CLAUSE_SPLIT.split(sentence):
                by_section[section].extend(
                    extract_sentence_annotations(clause, section=section)
                )

    by_finding: dict[str, list[dict[str, str]]] = defaultdict(list)
    for items in by_section.values():
        for item in items:
            by_finding[item["finding"]].append(item)

    accepted: list[dict[str, str]] = []
    for finding, items in by_finding.items():
        impression = [item for item in items if item["section"] == "IMPRESSION"]
        candidates = impression or items
        labels = {item["label"] for item in candidates}
        if len(labels) != 1:
            continue
        candidates.sort(
            key=lambda item: (
                int(item["distance"]),
                item["sentence"],
                item["cue"],
            )
        )
        selected = dict(candidates[0])
        selected.pop("distance", None)
        accepted.append(selected)
    return sorted(accepted, key=lambda item: (item["finding"], item["label"]))


def chexpert_state(value: object) -> int | None:
    if pd.isna(value):
        return None
    numeric = float(value)
    if numeric == 1.0:
        return 1
    if numeric == 0.0:
        return 0
    return None


def consistency_verdict(
    label: str, prior_state: int | None, current_state: int | None
) -> str:
    if prior_state is None or current_state is None:
        return "unknown"
    if label == "New":
        return "pass" if (prior_state, current_state) == (0, 1) else "reject"
    if label == "Resolved":
        return "pass" if (prior_state, current_state) == (1, 0) else "reject"
    if label == "Improved" and (prior_state, current_state) == (0, 1):
        return "reject"
    if label == "Worse" and (prior_state, current_state) == (1, 0):
        return "reject"
    return "pass"


def enrich_records(
    records: list[dict[str, Any]], labels: pd.DataFrame, *, workers: int = 1
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    labels_index = labels.set_index(["subject_id", "study_id"]).to_dict("index")
    enriched: list[dict[str, Any]] = []
    rejected_consistency = Counter()
    missing_reports = 0
    def process(row: dict[str, Any]) -> tuple[dict[str, Any] | None, list[tuple[str, str]]]:
        report = Path(row["current_report_path"])
        if not report.is_file():
            return None, []
        raw_annotations = extract_report_annotations(
            report.read_text(encoding="utf-8", errors="replace")
        )
        prior_key = (int(row["subject_id"]), int(row["prior_study_id"]))
        current_key = (int(row["subject_id"]), int(row["current_study_id"]))
        prior_labels = labels_index.get(prior_key, {})
        current_labels = labels_index.get(current_key, {})
        accepted = []
        rejected: list[tuple[str, str]] = []
        for item in raw_annotations:
            finding = item["finding"]
            verdict = consistency_verdict(
                item["label"],
                chexpert_state(prior_labels.get(finding)),
                chexpert_state(current_labels.get(finding)),
            )
            if verdict == "reject":
                rejected.append((finding, item["label"]))
                continue
            accepted.append(
                {
                    **item,
                    "chexpert_consistency": verdict,
                    "supervision_source": "current_report_temporal_phrase",
                    "ruleset_version": RULESET_VERSION,
                }
            )
        output = dict(row)
        output["transition_supervision_status"] = (
            "eligible" if accepted else "no_qualified_transition"
        )
        output["transition_supervision"] = accepted
        return output, rejected

    if workers <= 1:
        processed = map(process, records)
    else:
        executor = ThreadPoolExecutor(max_workers=workers)
        processed = executor.map(process, records, chunksize=64)
    try:
        for output, rejected in processed:
            if output is None:
                missing_reports += 1
                continue
            enriched.append(output)
            rejected_consistency.update(rejected)
    finally:
        if workers > 1:
            executor.shutdown(wait=True)
    diagnostics = {
        "missing_current_reports": missing_reports,
        "chexpert_consistency_rejections": {
            f"{finding}|{label}": count
            for (finding, label), count in sorted(rejected_consistency.items())
        },
    }
    return enriched, diagnostics


def sample_case_study(
    rows: list[dict[str, Any]], *, per_class: int
) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        for item in row["transition_supervision"]:
            grouped[item["label"]].append(
                {
                    "case_id": stable_hash(
                        "r37-transition-case-v1",
                        row["pair_id"],
                        item["finding"],
                        item["label"],
                    ),
                    "partition": str(row["partition"]),
                    "pair_id": str(row["pair_id"]),
                    "finding": str(item["finding"]),
                    "label": str(item["label"]),
                    "section": str(item["section"]),
                    "cue": str(item["cue"]),
                    "sentence": str(item["sentence"]),
                    "chexpert_consistency": str(
                        item["chexpert_consistency"]
                    ),
                    "human_direction_correct": "",
                    "human_error_category": "",
                    "human_notes": "",
                }
            )
    selected: list[dict[str, str]] = []
    for label in LABELS:
        candidates = sorted(grouped[label], key=lambda item: item["case_id"])
        selected.extend(candidates[:per_class])
    return selected


def write_case_study(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "case_id",
        "partition",
        "pair_id",
        "finding",
        "label",
        "section",
        "cue",
        "sentence",
        "chexpert_consistency",
        "human_direction_correct",
        "human_error_category",
        "human_notes",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    base = Path(r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r37a_data_v1")
    parser = argparse.ArgumentParser(
        description="Extract auditable R37 report-derived transition supervision"
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        default=base,
    )
    parser.add_argument(
        "--chexpert-labels",
        type=Path,
        default=Path(
            r"H:\Xiyao_Wang\000_Public Dataset\mimic_cxr_other"
            r"\mimic-cxr-2.0.0-chexpert.csv.gz"
        ),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=base.parent / "r37a_transitions_v1",
    )
    parser.add_argument("--case-study-per-class", type=int, default=40)
    parser.add_argument("--workers", type=int, default=16)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output_root.exists():
        raise FileExistsError(f"output root must be fresh: {args.output_root}")
    labels = pd.read_csv(args.chexpert_labels)
    outputs: dict[str, list[dict[str, Any]]] = {}
    diagnostics = {}
    for partition, name in (
        ("pretrain", "r37_pretrain_manifest.jsonl"),
        ("internal_calibration", "r37_internal_calibration_manifest.jsonl"),
    ):
        rows = read_jsonl(args.input_root / name)
        enriched, current_diagnostics = enrich_records(
            rows, labels, workers=args.workers
        )
        if any(row["partition"] != partition for row in enriched):
            raise ValueError(f"partition drift in {name}")
        outputs[partition] = enriched
        diagnostics[partition] = current_diagnostics

    args.output_root.mkdir(parents=True, exist_ok=False)
    for partition, name in (
        ("pretrain", "r37_pretrain_manifest.jsonl"),
        ("internal_calibration", "r37_internal_calibration_manifest.jsonl"),
    ):
        write_jsonl(args.output_root / name, outputs[partition])

    combined = outputs["pretrain"] + outputs["internal_calibration"]
    case_rows = sample_case_study(
        combined, per_class=args.case_study_per_class
    )
    write_case_study(
        args.output_root / "r37_transition_case_study.csv", case_rows
    )
    label_rows = Counter(
        item["label"]
        for row in combined
        for item in row["transition_supervision"]
    )
    label_patients = {
        partition: {
            label: len(
                {
                    row["patient_id"]
                    for row in outputs[partition]
                    if any(
                        item["label"] == label
                        for item in row["transition_supervision"]
                    )
                }
            )
            for label in LABELS
        }
        for partition in outputs
    }
    eligible_pairs = {
        partition: sum(
            bool(row["transition_supervision"]) for row in rows
        )
        for partition, rows in outputs.items()
    }
    transition_examples = {
        partition: sum(
            len(row["transition_supervision"]) for row in rows
        )
        for partition, rows in outputs.items()
    }
    support_checks = {
        "all_five_classes_present": all(label_rows[label] > 0 for label in LABELS),
        "pretrain_dynamic_patient_support": all(
            label_patients["pretrain"][label] >= 500
            for label in DYNAMIC_LABELS
        ),
        "internal_dynamic_patient_support": all(
            label_patients["internal_calibration"][label] >= 50
            for label in DYNAMIC_LABELS
        ),
        "case_study_has_40_per_class": (
            Counter(row["label"] for row in case_rows)
            == Counter({label: args.case_study_per_class for label in LABELS})
        ),
        "protected_outcomes_not_read": True,
    }
    audit = {
        "schema": SCHEMA,
        "ruleset_version": RULESET_VERSION,
        "status": (
            "PASS_R37A_TRANSITION_SUPPORT_PENDING_HUMAN_QA"
            if all(support_checks.values())
            else "STOP_R37A_DATA_SUPPORT"
        ),
        "protected_outcomes_read": False,
        "chextemporal_silver_used": False,
        "source_pair_counts": {
            partition: len(rows) for partition, rows in outputs.items()
        },
        "eligible_transition_pair_counts": eligible_pairs,
        "transition_example_counts": transition_examples,
        "transition_row_counts": dict(label_rows),
        "transition_patient_counts": label_patients,
        "support_checks": support_checks,
        "diagnostics": diagnostics,
        "formal_training_unlocked": False,
        "remaining_gate": (
            "human case-study review: >=90% overall and >=85% each class"
        ),
    }
    (args.output_root / "r37_transition_audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(audit, indent=2, sort_keys=True))
    print(f"RESULT_DIR={args.output_root}")
    return 0 if all(support_checks.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
