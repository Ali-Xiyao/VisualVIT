from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
from typing import Any, Iterable, Mapping, Sequence

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))

import numpy as np
import torch

from visualvit.real_progression import metrics_from_confusion


LABELS = ("Improved", "Stable", "Worse")
SYSTEMS = ("B4a_deranged", "B4b_oracle", "current_only")
ALL_R26_SYSTEMS = (
    "B4a_deranged",
    "B4b_oracle",
    "current_only",
    "oracle_geometry_only",
    "oracle_visual_only",
)
TRAINING_SEEDS = (17, 29, 43)
DERANGEMENT_IDS = (81001, 81002, 81003)
STRATUM_ORDER = ("BII-0", "BII-Low", "BII-Mid", "BII-High")
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 20260726
MINIMUM_VALID_FRACTION = 0.95
FROZEN_COMMIT = "8c2ea0b"

PROTOCOL_PATH = (
    WORKSPACE
    / "docs/superpowers/specs/"
    "2026-07-26-r27-binding-identifiability-audit-v1.md"
)
PROTOCOL_SHA256 = (
    "08d235a5d645225e908bde03d635b795cf15743914c3cc3ae643a1368720f887"
)
R26_ROOT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r26_c1_oracle_binding\run_v1"
)
OUTPUT_ROOT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r27_binding_identifiability\run_v1"
)
REPORT_PATH_DEFAULT = WORKSPACE / "reports/R27_BINDING_IDENTIFIABILITY_AUDIT.md"

R26_INPUT_HASHES = {
    "summary.json": "2fbb63a5fb97d4be30a6c13daa8c91015cfa2450bd8026c4546540ee1df8e5c0",
    "predictions.json": "160f9c66e6009d3e2d45cb4a7b28e06d1e94b037c2112925a9d8af156be40613",
    "bootstrap.json": "2d8bf9a2bec80fcfba5cdd9cc02222772b9390d0b6836712cec882d8ae17202a",
    "b4_isomorphism.json": "b3390da9779d580f6605469b803863ae31b44f80885941afde3312c45020a139",
    "folds.json": "472ecbdaded2e2e980459c42a9cf6e8e7f854595d5e6f017d1d2b9be31b7ef2b",
    "fit_audit.json": "785d8a6ca71bb34d581d5b21d17e6a7e972a686a4827d35ca08f6834666c9cc2",
    "cohort.json": "71013a070cba1133512408b62d232c13440f343cbafe03aa27be4a7bb8d3fd03",
}
FROZEN_SOURCE_HASHES = {
    "scripts/run_r26_c1_oracle_binding.py": (
        "951e86bd6c4fc715e159f6a3aece07f8b58aca916a816adb7e5a84e907db28ba"
    ),
    "src/visualvit/matching.py": (
        "6186fa380093e984430f8170439f447026a52dab9bdf847b2cc1edf2d02b23ec"
    ),
    "src/visualvit/real_progression.py": (
        "ed9e7dc57d70f33e3eb781540a9036c248ecadc4d5ac038279ff554249b11078"
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only exploratory audit of frozen R26 assignments/predictions"
    )
    parser.add_argument("--r26-root", type=Path, default=R26_ROOT_DEFAULT)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT_DEFAULT)
    parser.add_argument("--report-path", type=Path, default=REPORT_PATH_DEFAULT)
    parser.add_argument(
        "--bootstrap-replicates", type=int, default=BOOTSTRAP_REPLICATES
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def read_json(path: Path, expected: type) -> Any:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, expected):
        raise ValueError(f"{path} must contain {expected.__name__}")
    return value


def write_json_exclusive(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing artifact: {path}")
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def pair_key(record: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(record["patient_id"]),
        str(record["prior_dicom_id"]),
        str(record["current_dicom_id"]),
    )


def pair_id_from_key(key: Sequence[str]) -> str:
    return hashlib.sha256("|".join(key).encode("utf-8")).hexdigest()[:20]


def pair_seed(record: Mapping[str, Any], derangement_id: int) -> int:
    payload = "|".join(
        str(record[key])
        for key in ("patient_id", "prior_dicom_id", "current_dicom_id")
    )
    digest = int(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8], 16)
    return (digest + int(derangement_id)) % (2**31)


def derangement_indices(length: int, seed: int) -> list[int]:
    """Exact CPU reconstruction of the frozen R26 matching._derangement."""
    if length < 2:
        return list(range(length))
    if length == 2:
        return [1, 0]
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    base = torch.arange(length)
    for _ in range(128):
        candidate = torch.randperm(length, generator=generator)
        if bool((candidate != base).all()):
            return [int(value) for value in candidate.tolist()]
    return [int(value) for value in torch.roll(base, shifts=1).tolist()]


def bii_from_counts(counts: Mapping[str, int]) -> float:
    total = sum(int(value) for value in counts.values())
    if total < 2:
        raise ValueError("BII requires at least two entities")
    numerator = sum(
        int(value) * (total - int(value)) for value in counts.values()
    )
    return float(numerator / (total * (total - 1)))


def bii_stratum(value: float) -> str:
    if not math.isfinite(value) or value < 0.0 or value > 1.0:
        raise ValueError(f"BII lies outside [0, 1]: {value}")
    if math.isclose(value, 0.0, abs_tol=1e-12):
        return "BII-0"
    if value <= 0.33:
        return "BII-Low"
    if value <= 0.66:
        return "BII-Mid"
    return "BII-High"


def label_entropy(counts: Mapping[str, int]) -> float:
    total = sum(int(value) for value in counts.values())
    result = 0.0
    for value in counts.values():
        if value:
            probability = int(value) / total
            result -= probability * math.log(probability)
    return float(result)


def group_cohort(
    cohort: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    qualification_ids: set[str] = set()
    for raw in cohort:
        record = dict(raw)
        qid = str(record["qualification_id"])
        if qid in qualification_ids:
            raise ValueError(f"duplicate qualification id: {qid}")
        qualification_ids.add(qid)
        if str(record["progression"]) not in LABELS:
            raise ValueError(f"unregistered progression label for {qid}")
        groups[pair_key(record)].append(record)
    if len(groups) != 170 or len(qualification_ids) != 774:
        raise ValueError("frozen cohort must contain 170 pairs and 774 entities")
    return groups


def build_pair_composition(
    groups: Mapping[tuple[str, str, str], Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    output = []
    for key in sorted(groups):
        records = list(groups[key])
        counts = Counter(str(record["progression"]) for record in records)
        complete_counts = {label: int(counts[label]) for label in LABELS}
        value = bii_from_counts(complete_counts)
        prior_layouts = {
            tuple(str(box["label"]) for box in record["prior_boxes"])
            for record in records
        }
        current_layouts = {
            tuple(str(box["label"]) for box in record["current_boxes"])
            for record in records
        }
        if len(prior_layouts) != 1 or len(current_layouts) != 1:
            raise ValueError(f"inconsistent box layouts within pair {key}")
        prior_labels = next(iter(prior_layouts))
        current_labels = next(iter(current_layouts))
        if len(prior_labels) < 2 or set(prior_labels) != set(current_labels):
            raise ValueError(f"pair is not fully derangeable: {key}")
        anatomy_map = {
            str(record["anatomy"]): str(record["progression"]) for record in records
        }
        if len(anatomy_map) != len(records) or set(anatomy_map) != set(prior_labels):
            raise ValueError(f"pair anatomy labels do not cover box labels: {key}")
        output.append(
            {
                "pair_id": pair_id_from_key(key),
                "patient_id": key[0],
                "prior_dicom_id": key[1],
                "current_dicom_id": key[2],
                "entity_count": len(records),
                "label_counts": complete_counts,
                "label_entropy_nats": label_entropy(complete_counts),
                "distinct_label_count": sum(value > 0 for value in counts.values()),
                "homogeneous": len(counts) == 1,
                "contains_improved_and_worse": (
                    counts["Improved"] > 0 and counts["Worse"] > 0
                ),
                "bii": value,
                "bii_stratum": bii_stratum(value),
                "anatomy_labels": sorted(anatomy_map),
            }
        )
    return output


def reconstruct_semantic_audit(
    groups: Mapping[tuple[str, str, str], Sequence[Mapping[str, Any]]],
    b4_audit: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    audits_by_qid = {str(item["qualification_id"]): dict(item) for item in b4_audit}
    cohort_qids = {
        str(record["qualification_id"])
        for records in groups.values()
        for record in records
    }
    if set(audits_by_qid) != cohort_qids:
        raise ValueError("B4 audit qualification ids do not match frozen cohort")

    records_out: list[dict[str, Any]] = []
    pair_rates: dict[str, list[bool]] = defaultdict(list)
    transition_counts = {
        target: {selected: 0 for selected in LABELS} for target in LABELS
    }
    anatomy_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for key in sorted(groups):
        pair_records = list(groups[key])
        exemplar = pair_records[0]
        prior_labels = [
            str(box["label"]) for box in exemplar["prior_boxes"]
        ]
        current_labels = [
            str(box["label"]) for box in exemplar["current_boxes"]
        ]
        oracle_currents = [current_labels.index(label) for label in prior_labels]
        label_by_anatomy = {
            str(record["anatomy"]): str(record["progression"])
            for record in pair_records
        }
        pid = pair_id_from_key(key)

        for record in pair_records:
            qid = str(record["qualification_id"])
            frozen_audit = audits_by_qid[qid]
            expected_basis = "|".join(key)
            if frozen_audit.get("pair_seed_basis") != expected_basis:
                raise ValueError(f"pair seed basis mismatch for {qid}")
            declared = {
                int(item["derangement_id"]): dict(item)
                for item in frozen_audit["derangements"]
            }
            if set(declared) != set(DERANGEMENT_IDS):
                raise ValueError(f"derangement id mismatch for {qid}")
            target_anatomy = str(record["anatomy"])
            target_label = str(record["progression"])
            target_prior = prior_labels.index(target_anatomy)

            for derangement_id in DERANGEMENT_IDS:
                frozen_item = declared[derangement_id]
                if frozen_item.get("passed") is not True:
                    raise ValueError(f"frozen B4 audit is not green for {qid}")
                permutation = derangement_indices(
                    len(prior_labels), pair_seed(record, derangement_id)
                )
                selected_current = oracle_currents[permutation[target_prior]]
                selected_anatomy = current_labels[selected_current]
                selected_label = label_by_anatomy[selected_anatomy]
                fixed_point = selected_anatomy == target_anatomy
                if fixed_point:
                    raise ValueError(
                        f"reconstructed assignment has a fixed point for {qid}"
                    )
                changed = selected_label != target_label
                pair_rates[pid].append(changed)
                transition_counts[target_label][selected_label] += 1
                anatomy_counts[target_anatomy]["total"] += 1
                anatomy_counts[target_anatomy]["label_changing"] += int(changed)
                records_out.append(
                    {
                        "pair_id": pid,
                        "patient_id": str(record["patient_id"]),
                        "qualification_id": qid,
                        "derangement_id": derangement_id,
                        "target_anatomy": target_anatomy,
                        "target_label": target_label,
                        "selected_anatomy": selected_anatomy,
                        "selected_label": selected_label,
                        "zero_fixed_point": True,
                        "label_changed": changed,
                        "audit_class": "LCD" if changed else "LPD",
                        "assignment_source": "DETERMINISTIC_RECONSTRUCTION",
                    }
                )

    total = len(records_out)
    changed_total = sum(item["label_changed"] for item in records_out)
    return {
        "exploratory_only": True,
        "assignment_source": "DETERMINISTIC_RECONSTRUCTION",
        "assignment_indices_serialized_by_r26": False,
        "records": records_out,
        "overall": {
            "assignments": total,
            "zero_fixed_points": 0,
            "label_preserving": total - changed_total,
            "label_changing": changed_total,
            "semantic_corruption_rate": changed_total / total,
        },
        "transition_counts": transition_counts,
        "pair_semantic_corruption_rate": {
            pid: sum(values) / len(values) for pid, values in sorted(pair_rates.items())
        },
        "anatomy": {
            anatomy: {
                "assignments": int(counts["total"]),
                "label_changing": int(counts["label_changing"]),
                "semantic_corruption_rate": (
                    counts["label_changing"] / counts["total"]
                ),
            }
            for anatomy, counts in sorted(anatomy_counts.items())
        },
    }


def validate_predictions(
    predictions: Sequence[Mapping[str, Any]],
    cohort: Sequence[Mapping[str, Any]],
) -> None:
    cohort_by_qid = {
        str(record["qualification_id"]): dict(record) for record in cohort
    }
    expected_rows = (
        len(cohort_by_qid)
        * len(ALL_R26_SYSTEMS)
        * len(TRAINING_SEEDS)
        * len(DERANGEMENT_IDS)
    )
    if len(predictions) != expected_rows:
        raise ValueError(
            f"prediction row count mismatch: {len(predictions)} != {expected_rows}"
        )
    seen = set()
    patient_weight_sums: Counter[tuple[str, int, int, str]] = Counter()
    for raw in predictions:
        row = dict(raw)
        qid = str(row["observation_id"])
        source = cohort_by_qid.get(qid)
        if source is None:
            raise ValueError(f"prediction references unknown observation {qid}")
        if str(row["patient_id"]) != str(source["patient_id"]):
            raise ValueError(f"patient mismatch for prediction {qid}")
        if str(row["target"]) != str(source["progression"]):
            raise ValueError(f"target mismatch for prediction {qid}")
        if str(row["prediction"]) not in LABELS:
            raise ValueError(f"unregistered prediction for {qid}")
        key = (
            str(row["system"]),
            int(row["training_seed"]),
            int(row["derangement_id"]),
            qid,
        )
        if key in seen:
            raise ValueError(f"duplicate prediction row: {key}")
        seen.add(key)
        patient_weight_sums[
            (
                str(row["system"]),
                int(row["training_seed"]),
                int(row["derangement_id"]),
                str(row["patient_id"]),
            )
        ] += float(row["weight"])
    if {key[0] for key in seen} != set(ALL_R26_SYSTEMS):
        raise ValueError("R26 prediction systems differ from the frozen design")
    if {key[1] for key in seen} != set(TRAINING_SEEDS):
        raise ValueError("R26 prediction seeds differ from the frozen design")
    if {key[2] for key in seen} != set(DERANGEMENT_IDS):
        raise ValueError("R26 prediction derangements differ from the frozen design")
    bad_weights = {
        key: value
        for key, value in patient_weight_sums.items()
        if not math.isclose(value, 1.0, abs_tol=1e-8)
    }
    if bad_weights:
        raise ValueError(f"patient weights do not sum to one: {bad_weights}")


def bootstrap_stratum(
    rows: Sequence[Mapping[str, Any]],
    *,
    replicates: int,
    rng_seed: int,
) -> dict[str, Any]:
    patients = sorted({str(row["patient_id"]) for row in rows})
    patient_index = {patient: index for index, patient in enumerate(patients)}
    label_index = {label: index for index, label in enumerate(LABELS)}
    system_index = {system: index for index, system in enumerate(SYSTEMS)}
    seed_index = {seed: index for index, seed in enumerate(TRAINING_SEEDS)}
    derangement_index = {
        value: index for index, value in enumerate(DERANGEMENT_IDS)
    }
    confusion = np.zeros(
        (
            len(SYSTEMS),
            len(TRAINING_SEEDS),
            len(DERANGEMENT_IDS),
            len(patients),
            len(LABELS),
            len(LABELS),
        ),
        dtype=np.float64,
    )
    for raw in rows:
        system = str(raw["system"])
        if system not in system_index:
            continue
        confusion[
            system_index[system],
            seed_index[int(raw["training_seed"])],
            derangement_index[int(raw["derangement_id"])],
            patient_index[str(raw["patient_id"])],
            label_index[str(raw["target"])],
            label_index[str(raw["prediction"])],
        ] += float(raw["weight"])

    expected_blocks = (
        len(SYSTEMS)
        * len(TRAINING_SEEDS)
        * len(DERANGEMENT_IDS)
        * len(patients)
    )
    nonempty_blocks = int((confusion.sum(axis=(-1, -2)) > 0).sum())
    if nonempty_blocks != expected_blocks:
        raise ValueError("stratum prediction design is not fully crossed")

    def evaluate(
        patient_counts: np.ndarray, seed_offsets: Iterable[int]
    ) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for system_offset, system in enumerate(SYSTEMS):
            block_metrics = []
            for seed_offset in seed_offsets:
                for derangement_offset in range(len(DERANGEMENT_IDS)):
                    matrix = np.tensordot(
                        patient_counts,
                        confusion[
                            system_offset, seed_offset, derangement_offset
                        ],
                        axes=(0, 0),
                    )
                    block_metrics.append(
                        metrics_from_confusion(matrix, labels=LABELS)
                    )
            result[system] = {
                "macro_f1": float(
                    np.mean([value["macro_f1"] for value in block_metrics])
                ),
                "balanced_accuracy": float(
                    np.mean(
                        [value["balanced_accuracy"] for value in block_metrics]
                    )
                ),
                "per_class_f1": {
                    label: float(
                        np.mean(
                            [
                                value["per_class_f1"][label]
                                for value in block_metrics
                            ]
                        )
                    )
                    for label in LABELS
                },
            }
        return result

    point = evaluate(np.ones(len(patients), dtype=np.int64), range(len(TRAINING_SEEDS)))
    point_contrasts = {
        "B4b_minus_B4a": (
            point["B4b_oracle"]["macro_f1"]
            - point["B4a_deranged"]["macro_f1"]
        ),
        "B4b_minus_current": (
            point["B4b_oracle"]["macro_f1"]
            - point["current_only"]["macro_f1"]
        ),
    }
    per_seed = {}
    for offset, seed in enumerate(TRAINING_SEEDS):
        metrics = evaluate(
            np.ones(len(patients), dtype=np.int64), (offset,)
        )
        per_seed[str(seed)] = {
            "B4b_minus_B4a": (
                metrics["B4b_oracle"]["macro_f1"]
                - metrics["B4a_deranged"]["macro_f1"]
            ),
            "B4b_minus_B4a_pp": 100.0
            * (
                metrics["B4b_oracle"]["macro_f1"]
                - metrics["B4a_deranged"]["macro_f1"]
            ),
        }

    rng = np.random.default_rng(rng_seed)
    samples = {system: [] for system in SYSTEMS}
    contrast_samples = {name: [] for name in point_contrasts}
    invalid = Counter()
    for _ in range(replicates):
        draw = rng.integers(0, len(patients), size=len(patients))
        counts = np.bincount(draw, minlength=len(patients))
        try:
            metrics = evaluate(counts, range(len(TRAINING_SEEDS)))
        except ValueError as error:
            invalid[str(error)] += 1
            continue
        for system in SYSTEMS:
            samples[system].append(metrics[system]["macro_f1"])
        contrast_samples["B4b_minus_B4a"].append(
            metrics["B4b_oracle"]["macro_f1"]
            - metrics["B4a_deranged"]["macro_f1"]
        )
        contrast_samples["B4b_minus_current"].append(
            metrics["B4b_oracle"]["macro_f1"]
            - metrics["current_only"]["macro_f1"]
        )

    valid = len(samples[SYSTEMS[0]])
    valid_fraction = valid / replicates
    inference_valid = valid >= 2 and valid_fraction >= MINIMUM_VALID_FRACTION

    def interval(values: Sequence[float]) -> dict[str, float] | None:
        if not inference_valid:
            return None
        lower, upper = np.quantile(values, [0.025, 0.975], method="linear")
        return {
            "lower": float(lower),
            "upper": float(upper),
            "lower_pp": 100.0 * float(lower),
            "upper_pp": 100.0 * float(upper),
            "level": 0.95,
        }

    return {
        "patients": len(patients),
        "point_system_metrics": point,
        "contrasts": {
            name: {
                "point": value,
                "point_pp": 100.0 * value,
                "interval": interval(contrast_samples[name]),
            }
            for name, value in point_contrasts.items()
        },
        "per_seed_contrasts": per_seed,
        "bootstrap": {
            "requested_replicates": replicates,
            "valid_replicates": valid,
            "invalid_replicates": replicates - valid,
            "valid_fraction": valid_fraction,
            "minimum_valid_fraction": MINIMUM_VALID_FRACTION,
            "inference_valid": inference_valid,
            "invalid_reasons": dict(invalid),
            "rng_seed": rng_seed,
            "resampled_levels": ["patient"],
            "fixed_levels": ["training_seed", "derangement_id"],
            "system_intervals": {
                system: interval(values) for system, values in samples.items()
            },
        },
    }


def anatomy_effects(
    rows: Sequence[Mapping[str, Any]],
    cohort_by_qid: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    grouped: dict[
        tuple[str, str, int, int], list[tuple[bool, str]]
    ] = defaultdict(list)
    for raw in rows:
        system = str(raw["system"])
        if system not in SYSTEMS:
            continue
        qid = str(raw["observation_id"])
        anatomy = str(cohort_by_qid[qid]["anatomy"])
        grouped[
            (
                anatomy,
                system,
                int(raw["training_seed"]),
                int(raw["derangement_id"]),
            )
        ].append((str(raw["prediction"]) == str(raw["target"]), qid))
    anatomies = sorted({key[0] for key in grouped})
    result = {}
    for anatomy in anatomies:
        system_accuracy = {}
        entities = {
            qid
            for key, values in grouped.items()
            if key[0] == anatomy
            for _, qid in values
        }
        for system in SYSTEMS:
            block_values = []
            for seed in TRAINING_SEEDS:
                for derangement in DERANGEMENT_IDS:
                    values = grouped[(anatomy, system, seed, derangement)]
                    if values:
                        block_values.append(
                            sum(correct for correct, _ in values) / len(values)
                        )
            system_accuracy[system] = (
                float(np.mean(block_values)) if block_values else None
            )
        left = system_accuracy["B4b_oracle"]
        right = system_accuracy["B4a_deranged"]
        result[anatomy] = {
            "entities": len(entities),
            "point_accuracy": system_accuracy,
            "B4b_minus_B4a_accuracy_pp": (
                None if left is None or right is None else 100.0 * (left - right)
            ),
        }
    return result


def build_support_audit(
    composition: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    strata: dict[str, dict[str, Any]] = {}
    for stratum in STRATUM_ORDER:
        pairs = [item for item in composition if item["bii_stratum"] == stratum]
        label_entities = {
            label: sum(int(item["label_counts"][label]) for item in pairs)
            for label in LABELS
        }
        label_patients = {
            label: sum(int(item["label_counts"][label]) > 0 for item in pairs)
            for label in LABELS
        }
        strata[stratum] = {
            "patients": len(pairs),
            "entities": sum(int(item["entity_count"]) for item in pairs),
            "label_entities": label_entities,
            "label_patients": label_patients,
        }
    high = strata["BII-High"]
    high_checks = {
        "patients_at_least_30": high["patients"] >= 30,
        "entities_at_least_100": high["entities"] >= 100,
        "each_label_at_least_10_patients": all(
            value >= 10 for value in high["label_patients"].values()
        ),
    }
    return {
        "exploratory_only": True,
        "strata": strata,
        "cohort_conservation": {
            "patients": sum(item["patients"] for item in strata.values()),
            "entities": sum(item["entities"] for item in strata.values()),
            "expected_patients": 170,
            "expected_entities": 774,
            "passed": (
                sum(item["patients"] for item in strata.values()) == 170
                and sum(item["entities"] for item in strata.values()) == 774
            ),
        },
        "high_bii_support_checks": high_checks,
        "high_bii_support_passed": all(high_checks.values()),
    }


def terminal_verdict(
    stratified: Mapping[str, Mapping[str, Any]],
    support: Mapping[str, Any],
) -> tuple[str, dict[str, bool]]:
    points = [
        float(
            stratified[stratum]["contrasts"]["B4b_minus_B4a"]["point"]
        )
        for stratum in STRATUM_ORDER
    ]
    high = stratified["BII-High"]
    high_interval = high["contrasts"]["B4b_minus_B4a"]["interval"]
    checks = {
        "high_bii_support": bool(support["high_bii_support_passed"]),
        "nondecreasing_stratum_points": all(
            right >= left for left, right in zip(points, points[1:])
        ),
        "high_bii_point_positive": points[-1] > 0,
        "high_bii_ci_lower_positive": (
            high_interval is not None and float(high_interval["lower"]) > 0
        ),
        "all_high_bii_seed_directions_positive": all(
            float(value["B4b_minus_B4a"]) > 0
            for value in high["per_seed_contrasts"].values()
        ),
    }
    if not checks["high_bii_support"]:
        return "C_SPARSE_HIGH_BII_SUPPORT", checks
    if (
        not checks["high_bii_point_positive"]
        or not checks["high_bii_ci_lower_positive"]
    ):
        return "B_NO_HIGH_BII_GAIN", checks
    if all(checks.values()):
        return "A_MONOTONIC_SUPPORT", checks
    return "INCONCLUSIVE_NONMONOTONIC", checks


def render_report(
    *,
    composition: Sequence[Mapping[str, Any]],
    semantic: Mapping[str, Any],
    stratified: Mapping[str, Mapping[str, Any]],
    support: Mapping[str, Any],
    verdict: str,
    verdict_checks: Mapping[str, bool],
) -> str:
    def contrast_text(stratum: str, name: str) -> str:
        contrast = stratified[stratum]["contrasts"][name]
        interval = contrast["interval"]
        if interval is None:
            ci = "CI invalid (bootstrap valid fraction below 0.95)"
        else:
            ci = (
                f"95% CI [{interval['lower_pp']:+.2f}, "
                f"{interval['upper_pp']:+.2f}] pp"
            )
        return f"{contrast['point_pp']:+.2f} pp; {ci}"

    lines = [
        "# R27 Binding Identifiability Audit",
        "",
        "Date: 2026-07-26",
        "",
        f"Terminal verdict: `{verdict}`",
        "",
        "Evidence class: `EXPLORATORY_POSTHOC_R27_MECHANISM_AUDIT`",
        "",
        "`exploratory_only=true`; `formal_claim_allowed=false`; "
        "`r28_unlocked=false`.",
        "",
        "## Formal boundary",
        "",
        "R26 remains `STOP_C1`. R27 read the frozen R26 cohort and predictions, "
        "did not train a model, and did not regenerate predictions. R26 did not "
        "serialize assignment indices; semantic assignments were deterministically "
        "reconstructed from the frozen cohort order, registered derangement ids, "
        "pair-seed basis, and frozen R26 algorithm.",
        "",
        "## Pair composition",
        "",
        "| Stratum | Patients | Entities |",
        "|---|---:|---:|",
    ]
    for stratum in STRATUM_ORDER:
        item = support["strata"][stratum]
        lines.append(
            f"| {stratum} | {item['patients']} | {item['entities']} |"
        )
    lines.extend(
        [
            "",
            "Cohort conservation: "
            f"{support['cohort_conservation']['patients']}/170 patients and "
            f"{support['cohort_conservation']['entities']}/774 entities.",
            "",
            "## Actual R26 derangement semantics",
            "",
            f"- Assignments audited: {semantic['overall']['assignments']}",
            f"- Label-preserving (LPD-class): {semantic['overall']['label_preserving']}",
            f"- Label-changing (LCD-class): {semantic['overall']['label_changing']}",
            "- Semantic corruption rate: "
            f"{100.0 * semantic['overall']['semantic_corruption_rate']:.2f}%",
            "- Reconstructed fixed points: 0",
            "",
            "## BII-stratified frozen-prediction effects",
            "",
            "| Stratum | B4b − B4a | B4b − Current | Bootstrap valid |",
            "|---|---|---|---:|",
        ]
    )
    for stratum in STRATUM_ORDER:
        item = stratified[stratum]
        lines.append(
            f"| {stratum} | {contrast_text(stratum, 'B4b_minus_B4a')} | "
            f"{contrast_text(stratum, 'B4b_minus_current')} | "
            f"{100.0 * item['bootstrap']['valid_fraction']:.2f}% |"
        )
    high = support["strata"]["BII-High"]
    lines.extend(
        [
            "",
            "## Verdict",
            "",
            f"High-BII support is {high['patients']} patients / "
            f"{high['entities']} entities. The registered support gate requires "
            "at least 30 patients, 100 entities, and at least 10 patients for "
            "each label, so the terminal classification is "
            f"`{verdict}` before any positive subgroup pattern can be elevated.",
            "",
            "Verdict checks:",
            "",
        ]
    )
    for name, passed in verdict_checks.items():
        lines.append(f"- `{name}`: {'PASS' if passed else 'FAIL'}")
    lines.extend(
        [
            "",
            "This result may generate an independently preregistered R28/R29 "
            "hypothesis, but it is not a confirmatory rescue of R26. R28, R29, "
            "TIER, learned matcher, RAD-DINO, frozen VLM, DIVE, and scale-up "
            "remain locked.",
            "",
            "## Provenance",
            "",
            f"- Pairs audited: {len(composition)}",
            f"- Protocol SHA-256: `{PROTOCOL_SHA256}`",
            f"- Frozen R26 commit: `{FROZEN_COMMIT}`",
            f"- Bootstrap: {BOOTSTRAP_REPLICATES} patient-only replicates, "
            f"seed {BOOTSTRAP_SEED}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    if args.bootstrap_replicates != BOOTSTRAP_REPLICATES:
        raise ValueError(
            f"formal R27 requires exactly {BOOTSTRAP_REPLICATES} bootstrap replicates"
        )
    if args.output_root.exists():
        raise FileExistsError(
            f"R27 output root must be fresh: {args.output_root}"
        )
    if args.report_path.exists():
        raise FileExistsError(
            f"R27 report path must be fresh: {args.report_path}"
        )
    if sha256_file(PROTOCOL_PATH) != PROTOCOL_SHA256:
        raise RuntimeError("R27 protocol hash mismatch")

    observed_sources = {}
    for relative, expected_hash in FROZEN_SOURCE_HASHES.items():
        path = WORKSPACE / relative
        observed = sha256_file(path)
        observed_sources[relative] = observed
        if observed != expected_hash:
            raise RuntimeError(f"frozen R26 source hash mismatch: {relative}")

    observed_inputs = {}
    for name, expected_hash in R26_INPUT_HASHES.items():
        path = args.r26_root / name
        if not path.is_file():
            raise FileNotFoundError(f"missing frozen R26 input: {path}")
        observed = sha256_file(path)
        observed_inputs[name] = observed
        if observed != expected_hash:
            raise RuntimeError(f"frozen R26 input hash mismatch: {name}")

    summary = read_json(args.r26_root / "summary.json", dict)
    if summary.get("status") != "STOP_C1":
        raise RuntimeError("R26 terminal status is not STOP_C1")
    cohort = read_json(args.r26_root / "cohort.json", list)
    predictions = read_json(args.r26_root / "predictions.json", list)
    b4_audit = read_json(args.r26_root / "b4_isomorphism.json", list)
    groups = group_cohort(cohort)
    composition = build_pair_composition(groups)
    semantic = reconstruct_semantic_audit(groups, b4_audit)
    actual_rates = semantic["pair_semantic_corruption_rate"]
    for item in composition:
        item["actual_registered_derangement_semantic_corruption_rate"] = (
            actual_rates[item["pair_id"]]
        )

    validate_predictions(predictions, cohort)
    cohort_by_qid = {
        str(record["qualification_id"]): dict(record) for record in cohort
    }
    patient_stratum = {
        str(item["patient_id"]): str(item["bii_stratum"]) for item in composition
    }
    support = build_support_audit(composition)
    if support["cohort_conservation"]["passed"] is not True:
        raise RuntimeError("R27 stratum totals do not conserve the R26 cohort")

    stratified = {}
    for offset, stratum in enumerate(STRATUM_ORDER):
        selected_rows = [
            dict(row)
            for row in predictions
            if patient_stratum[str(row["patient_id"])] == stratum
            and str(row["system"]) in SYSTEMS
        ]
        result = bootstrap_stratum(
            selected_rows,
            replicates=args.bootstrap_replicates,
            rng_seed=BOOTSTRAP_SEED + offset,
        )
        result["stratum"] = stratum
        result["entities"] = support["strata"][stratum]["entities"]
        result["label_f1_effects_pp"] = {
            label: 100.0
            * (
                result["point_system_metrics"]["B4b_oracle"]["per_class_f1"][
                    label
                ]
                - result["point_system_metrics"]["B4a_deranged"]["per_class_f1"][
                    label
                ]
            )
            for label in LABELS
        }
        result["anatomy_effects"] = anatomy_effects(
            selected_rows, cohort_by_qid
        )
        stratified[stratum] = result

    verdict, verdict_checks = terminal_verdict(stratified, support)
    composition_payload = {
        "exploratory_only": True,
        "definition": "expected label-changing fraction over zero-fixed-point derangements",
        "strata": list(STRATUM_ORDER),
        "pairs": composition,
    }
    stratified_payload = {
        "exploratory_only": True,
        "formal_claim_allowed": False,
        "r28_unlocked": False,
        "bootstrap_unit": "patient",
        "strata": stratified,
    }
    support["terminal_verdict"] = verdict
    support["verdict_checks"] = verdict_checks
    support["formal_claim_allowed"] = False
    support["r28_unlocked"] = False

    args.output_root.mkdir(parents=True, exist_ok=False)
    artifacts = {
        "pair_label_composition.json": composition_payload,
        "derangement_semantic_audit.json": semantic,
        "bii_stratified_effects.json": stratified_payload,
        "support_audit.json": support,
    }
    for name, payload in artifacts.items():
        write_json_exclusive(args.output_root / name, payload)

    report = render_report(
        composition=composition,
        semantic=semantic,
        stratified=stratified,
        support=support,
        verdict=verdict,
        verdict_checks=verdict_checks,
    )
    args.report_path.write_text(report, encoding="utf-8")

    output_hashes = {
        name: sha256_file(args.output_root / name) for name in artifacts
    }
    manifest_base = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": verdict,
        "evidence_class": "EXPLORATORY_POSTHOC_R27_MECHANISM_AUDIT",
        "exploratory_only": True,
        "formal_claim_allowed": False,
        "r28_unlocked": False,
        "assignment_source": "DETERMINISTIC_RECONSTRUCTION",
        "assignment_indices_serialized_by_r26": False,
        "protocol": {
            "path": str(PROTOCOL_PATH),
            "sha256": PROTOCOL_SHA256,
        },
        "frozen_commit": FROZEN_COMMIT,
        "r26_root": str(args.r26_root),
        "r26_input_hashes": observed_inputs,
        "frozen_source_hashes": observed_sources,
        "r27_source_hashes": {
            str(Path(__file__).resolve().relative_to(WORKSPACE)): sha256_file(
                Path(__file__).resolve()
            ),
            "src/visualvit/real_progression.py": observed_sources[
                "src/visualvit/real_progression.py"
            ],
        },
        "outputs": output_hashes,
        "report": {
            "path": str(args.report_path),
            "sha256": sha256_file(args.report_path),
        },
        "counts": {
            "patients": 170,
            "pairs": 170,
            "entities": 774,
            "prediction_rows": len(predictions),
            "semantic_assignments": semantic["overall"]["assignments"],
        },
        "bootstrap": {
            "replicates": args.bootstrap_replicates,
            "rng_seed_base": BOOTSTRAP_SEED,
            "resampled_levels": ["patient"],
            "fixed_levels": ["training_seed", "derangement_id"],
        },
        "gates": {
            "frozen_input_integrity": True,
            "frozen_source_integrity": True,
            "cohort_conservation": True,
            "zero_fixed_point_reconstruction": True,
            "high_bii_support": support["high_bii_support_passed"],
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "torch": torch.__version__,
            "numpy": np.__version__,
            "cuda_used": False,
        },
        "manifest_self_binding": (
            "manifest_payload_sha256 hashes this object before the field is added"
        ),
    }
    manifest = dict(manifest_base)
    manifest["manifest_payload_sha256"] = canonical_sha256(manifest_base)
    write_json_exclusive(args.output_root / "artifact_manifest.json", manifest)
    print(
        json.dumps(
            {
                "status": verdict,
                "output_root": str(args.output_root),
                "report": str(args.report_path),
                "manifest_sha256": sha256_file(
                    args.output_root / "artifact_manifest.json"
                ),
                "exploratory_only": True,
                "r28_unlocked": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
