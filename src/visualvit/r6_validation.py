"""Strict, runner-independent validation primitives for R6 artifacts.

The module deliberately accepts an external contract.  The runner owns the
registered values; this module owns recursive type/schema checks and the
derivation of terminal state from gate payloads.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
import re
import struct
from typing import Any, Literal, Mapping, Sequence, TypeAlias
import uuid


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_UTC_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")
R6_VALIDATION_SCHEMA_VERSION = "visualvit.r6-validation.v4"

_R6_RESULT_SCHEMA_VERSION = "r6.result.v1"
_R6_INITIALIZATION_SCHEMA_VERSION = "r24_initialization_evidence_v1"
_R6_STRUCTURAL_SCHEMA_VERSION = "visualvit.r6-structural-audits.v3"
_R6_COUNTERFACTUAL_SCHEMA_VERSION = "visualvit.r6_counterfactual_audits.v1"
_R6_STRATA = ("clean", "challenge")
_R6_SPLITS = ("train", "development")
_R6_EXACT64_METHOD_ORDER = (
    "main",
    "local_independent",
    "hungarian",
    "sinkhorn",
)
_R6_MATCHER_PARAMETER_NAMES = (
    "current_null_utility",
    "prior_null_utility",
    "residual_coefficient",
    "view_weight_logits",
)
_R6_INITIAL_PARAMETER_ORDER = (
    "residual_coefficient",
    "view_weight_logits.0",
    "view_weight_logits.1",
    "prior_null_utility_raw",
    "current_null_utility_raw",
)
_R8_RUNTIME_STATE_PARAMETER_ORDER = (
    "current_null_utility",
    "prior_null_utility",
    "residual_coefficient",
    "view_weight_logits",
)
_R8_RUNTIME_STATE_SHAPES = {
    "current_null_utility": [],
    "prior_null_utility": [],
    "residual_coefficient": [],
    "view_weight_logits": [2],
}
_R6_STRUCTURAL_CASE_IDS = (
    "one_persistent_1x1",
    "one_death_1x0",
    "one_birth_0x1",
    "collision_2x1",
    "crossing_2x2",
    "tied_utility_2x2",
    "mixed_persistent_death_birth_2x2",
    "anatomy_forbidden_edge",
)
_R6_STRUCTURAL_EVIDENCE_KEYS = (
    "input_sha256_before",
    "input_sha256_after",
    "utility_sha256",
    "soft_plan_sha256",
    "hard_plan_sha256",
    "feasibility_residuals",
    "expected_plan_exact",
    "completion_counts",
    "gradient_audit",
)
_R6_CHAIN_STAGE_NAMES = (
    "matching_regions",
    "token_regions",
    "utilities",
    "soft_plan",
    "plan",
    "relation_candidates",
    "allocation",
    "tokens",
    "projected_tokens",
    "adapter_scores",
    "predictions",
)


@dataclass(frozen=True)
class ScalarSchema:
    """Schema for one JSON scalar with optional registered constraints."""

    kind: Literal["boolean", "integer", "number", "string", "null"]
    enum: tuple[Any, ...] | None = None
    minimum: int | float | None = None
    maximum: int | float | None = None
    pattern: str | None = None
    sha256: bool = False
    uuid4: bool = False
    utc_z: bool = False


@dataclass(frozen=True)
class LiteralSchema:
    """Schema requiring exact type and value equality."""

    value: Any


@dataclass(frozen=True)
class ListSchema:
    """Schema for a JSON array."""

    items: Schema
    exact_length: int | None = None
    exact_values: tuple[Any, ...] | None = None


@dataclass(frozen=True)
class ObjectSchema:
    """Schema for an object; every declared key is required and extras fail."""

    properties: Mapping[str, Schema]


Schema: TypeAlias = ScalarSchema | LiteralSchema | ListSchema | ObjectSchema


@dataclass(frozen=True)
class R6ModeContract:
    """Registered terminal-state contract for one runner mode."""

    schema: ObjectSchema
    expected_top_level_keys: frozenset[str]
    gate_prefix: tuple[str, ...]
    expected_status: str
    expected_access_prefix: tuple[Mapping[str, Any], ...]
    outcome: Literal["stopped", "dry_run", "success"]
    stopped_at_gate: str | None = None
    expected_not_run_gates: tuple[str, ...] | None = None


@dataclass(frozen=True)
class R6SummaryContract:
    """Runner-supplied authority needed to validate R6 summary families."""

    gate_order: tuple[str, ...]
    gate_fields: Mapping[str, str]
    modes: Mapping[str, R6ModeContract]
    formal_claim_fields: tuple[str, ...] = (
        "formal_test_used",
        "formal_claim_allowed",
        "formal_ablation_claim_allowed",
        "full_method_claim_allowed",
    )
    success_gate_count: int = 8


@dataclass(frozen=True)
class ValidationIssue:
    """One machine-readable RFC 6901 validation failure."""

    pointer: str
    rule: str
    observed_type: str
    observed_value: str

    def as_dict(self) -> dict[str, str]:
        return {
            "pointer": self.pointer,
            "rule": self.rule,
            "observed_type": self.observed_type,
            "observed_value": self.observed_value,
        }


class R6ValidationError(ValueError):
    """Raised with all observed strict-validation failures."""

    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        self.issues = tuple(issues)
        payload = [issue.as_dict() for issue in self.issues]
        super().__init__(json.dumps(payload, sort_keys=True, ensure_ascii=True))


def json_pointer_join(pointer: str, token: str | int) -> str:
    """Append one escaped token to an RFC 6901 JSON Pointer."""

    escaped = str(token).replace("~", "~0").replace("/", "~1")
    return f"{pointer}/{escaped}"


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, Mapping):
        return "object"
    return type(value).__name__


def _observed(value: Any) -> str:
    rendered = repr(value)
    return rendered if len(rendered) <= 300 else f"{rendered[:297]}..."


def _issue(pointer: str, rule: str, value: Any) -> ValidationIssue:
    return ValidationIssue(pointer, rule, _type_name(value), _observed(value))


def _finite_json_issues(value: Any, pointer: str = "") -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if value is None or isinstance(value, (bool, int, str)):
        return issues
    if isinstance(value, float):
        if not math.isfinite(value):
            issues.append(_issue(pointer, "finite JSON number", value))
        return issues
    if isinstance(value, list):
        for index, item in enumerate(value):
            issues.extend(_finite_json_issues(item, json_pointer_join(pointer, index)))
        return issues
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                issues.append(_issue(pointer, "object keys are strings", key))
                continue
            issues.extend(_finite_json_issues(item, json_pointer_join(pointer, key)))
        return issues
    issues.append(_issue(pointer, "JSON-compatible value", value))
    return issues


def _matches_scalar_kind(value: Any, kind: str) -> bool:
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "string":
        return isinstance(value, str)
    return value is None


def _validate_schema(
    value: Any, schema: Schema, pointer: str, issues: list[ValidationIssue]
) -> None:
    if isinstance(schema, LiteralSchema):
        if type(value) is not type(schema.value) or value != schema.value:
            issues.append(
                _issue(pointer, f"literal {schema.value!r} with exact type", value)
            )
        return

    if isinstance(schema, ObjectSchema):
        if not isinstance(value, Mapping):
            issues.append(_issue(pointer, "object", value))
            return
        expected = set(schema.properties)
        actual = set(value)
        for key in sorted(expected - actual):
            issues.append(
                _issue(json_pointer_join(pointer, key), "required key present", None)
            )
        for key in sorted(actual - expected, key=str):
            issues.append(
                _issue(
                    json_pointer_join(pointer, key), "unknown key forbidden", value[key]
                )
            )
        for key in sorted(expected & actual):
            _validate_schema(
                value[key],
                schema.properties[key],
                json_pointer_join(pointer, key),
                issues,
            )
        return

    if isinstance(schema, ListSchema):
        if not isinstance(value, list):
            issues.append(_issue(pointer, "array", value))
            return
        if schema.exact_length is not None and len(value) != schema.exact_length:
            issues.append(
                _issue(pointer, f"array length exactly {schema.exact_length}", value)
            )
        if schema.exact_values is not None:
            expected_values = list(schema.exact_values)
            if value != expected_values:
                issues.append(
                    _issue(pointer, f"ordered list exactly {expected_values!r}", value)
                )
        for index, item in enumerate(value):
            _validate_schema(
                item, schema.items, json_pointer_join(pointer, index), issues
            )
        return

    if not isinstance(schema, ScalarSchema):
        issues.append(_issue(pointer, "recognized explicit schema descriptor", schema))
        return
    if not _matches_scalar_kind(value, schema.kind):
        issues.append(_issue(pointer, schema.kind, value))
        return
    if schema.kind == "number" and not math.isfinite(float(value)):
        issues.append(_issue(pointer, "finite number", value))
        return
    if schema.enum is not None and not any(
        type(value) is type(candidate) and value == candidate
        for candidate in schema.enum
    ):
        issues.append(_issue(pointer, f"one of {schema.enum!r} with exact type", value))
    if schema.minimum is not None and value < schema.minimum:
        issues.append(_issue(pointer, f">= {schema.minimum!r}", value))
    if schema.maximum is not None and value > schema.maximum:
        issues.append(_issue(pointer, f"<= {schema.maximum!r}", value))
    if schema.pattern is not None and not re.fullmatch(schema.pattern, value):
        issues.append(_issue(pointer, f"full regex {schema.pattern!r}", value))
    if schema.sha256 and not is_lowercase_sha256(value):
        issues.append(_issue(pointer, "lowercase SHA-256 hex of length 64", value))
    if schema.uuid4 and not is_uuid4(value):
        issues.append(_issue(pointer, "canonical RFC 4122 UUID v4", value))
    if schema.utc_z and not is_utc_z_timestamp(value):
        issues.append(
            _issue(pointer, "UTC timestamp YYYY-MM-DDTHH:MM:SS.ffffffZ", value)
        )


def validate_schema(value: Any, schema: Schema, pointer: str = "") -> None:
    """Validate finite JSON and an explicit recursive exact schema."""

    issues = _finite_json_issues(value, pointer)
    _validate_schema(value, schema, pointer, issues)
    if issues:
        raise R6ValidationError(issues)


def canonical_json(value: Any) -> str:
    """Return deterministic UTF-8 JSON text; non-finite/non-JSON input fails."""

    issues = _finite_json_issues(value)
    if issues:
        raise R6ValidationError(issues)
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise R6ValidationError([_issue("", "canonical JSON value", value)]) from error


def canonical_sha256(value: Any) -> str:
    """Hash :func:`canonical_json` as UTF-8."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def is_lowercase_sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


def is_uuid4(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        return False
    return (
        str(parsed) == value and parsed.version == 4 and parsed.variant == uuid.RFC_4122
    )


def is_utc_z_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or _UTC_Z_RE.fullmatch(value) is None:
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        return False
    return True


def recompute_confusion_matrix(
    actual: Sequence[Any], predicted: Sequence[Any], labels: Sequence[Any]
) -> list[list[int]]:
    """Recompute a row-actual/column-predicted confusion matrix."""

    if len(actual) != len(predicted):
        raise R6ValidationError(
            [_issue("", "actual and predicted lengths are equal", [actual, predicted])]
        )
    if len(set(labels)) != len(labels):
        raise R6ValidationError([_issue("/labels", "labels are unique", labels)])
    lookup = {label: index for index, label in enumerate(labels)}
    matrix = [[0 for _ in labels] for _ in labels]
    for index, (truth, guess) in enumerate(zip(actual, predicted, strict=True)):
        if truth not in lookup:
            raise R6ValidationError(
                [_issue(json_pointer_join("/actual", index), "registered label", truth)]
            )
        if guess not in lookup:
            raise R6ValidationError(
                [
                    _issue(
                        json_pointer_join("/predicted", index),
                        "registered label",
                        guess,
                    )
                ]
            )
        matrix[lookup[truth]][lookup[guess]] += 1
    return matrix


def validate_confusion_matrix(
    stored: Any,
    *,
    actual: Sequence[Any],
    predicted: Sequence[Any],
    labels: Sequence[Any],
    pointer: str,
) -> None:
    expected = recompute_confusion_matrix(actual, predicted, labels)
    if stored != expected:
        raise R6ValidationError(
            [_issue(pointer, f"recomputed confusion {expected!r}", stored)]
        )


def recompute_average(values: Sequence[int | float]) -> float:
    """Recompute a finite arithmetic mean, rejecting booleans and empties."""

    if not values:
        raise R6ValidationError([_issue("", "nonempty average inputs", values)])
    for index, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise R6ValidationError(
                [
                    _issue(
                        json_pointer_join("", index), "finite number not boolean", value
                    )
                ]
            )
        if not math.isfinite(float(value)):
            raise R6ValidationError(
                [_issue(json_pointer_join("", index), "finite number", value)]
            )
    return math.fsum(float(value) for value in values) / len(values)


def validate_average(
    stored: Any,
    values: Sequence[int | float],
    *,
    pointer: str,
    absolute_tolerance: float = 0.0,
) -> None:
    expected = recompute_average(values)
    if (
        isinstance(stored, bool)
        or not isinstance(stored, (int, float))
        or not math.isfinite(float(stored))
        or not math.isclose(
            float(stored), expected, rel_tol=0.0, abs_tol=absolute_tolerance
        )
    ):
        raise R6ValidationError(
            [_issue(pointer, f"recomputed average {expected!r}", stored)]
        )


def validate_delta(
    stored: Any,
    *,
    minuend: int | float,
    subtrahend: int | float,
    pointer: str,
    absolute_tolerance: float = 0.0,
) -> None:
    values = (minuend, subtrahend)
    for index, value in enumerate(values):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise R6ValidationError(
                [
                    _issue(
                        json_pointer_join(pointer, index),
                        "finite number not boolean",
                        value,
                    )
                ]
            )
    expected = float(minuend) - float(subtrahend)
    if (
        isinstance(stored, bool)
        or not isinstance(stored, (int, float))
        or not math.isfinite(float(stored))
        or not math.isclose(
            float(stored), expected, rel_tol=0.0, abs_tol=absolute_tolerance
        )
    ):
        raise R6ValidationError(
            [_issue(pointer, f"recomputed delta {expected!r}", stored)]
        )


_LABEL_METRIC_KEYS = frozenset(
    {
        "five_label_macro_f1",
        "persistent_three_label_macro_f1",
        "accuracy",
        "predictions",
        "targets",
    }
)
_BINARY_METRIC_KEYS = frozenset(
    {
        "actual",
        "predicted",
        "tp",
        "fp",
        "fn",
        "tn",
        "positive_support",
        "predicted_positive_support",
        "precision",
        "recall",
        "f1",
        "balanced_accuracy",
        "non_gating_accuracy",
    }
)
_NULL_METRIC_KEYS = frozenset(
    {
        "death",
        "birth",
        "death_exact_case",
        "birth_exact_case",
        "null_exact_case",
        "macro_f1",
        "positive_support_both",
        "metric_evidence",
    }
)
_NULL_EVIDENCE_KEYS = frozenset(
    {"case_count", "death_exact_count", "birth_exact_count", "joint_exact_count"}
)
_QUERY_METRIC_KEYS = frozenset(
    {
        "hard_query_identity_accuracy",
        "hard_query_identity_f1",
        "hard_query_identity_chance_reference",
        "soft_oracle_query_mass",
        "soft_oracle_mass_chance_reference",
        "soft_query_nll",
        "soft_query_brier",
    }
)
_QUERY_EVIDENCE_KEYS = frozenset(
    {
        "hard_query_correct",
        "soft_oracle_query_mass_values",
        "soft_query_nll_values",
        "soft_query_brier_values",
        "soft_query_probability_rows",
        "oracle_current_indices",
    }
)
_TRANSPORT_METRIC_KEYS = frozenset(
    {
        "hard_all_endpoint_assignment_accuracy",
        "soft_all_endpoint_oracle_mass",
        "row_top1_accuracy",
        "null_metrics",
        "query",
        "soft_plan_sha256",
        "hard_plan_sha256",
        "metric_evidence",
    }
)
_TRANSPORT_EVIDENCE_KEYS = frozenset(
    {
        "hard_endpoint_correct",
        "row_top1_actual",
        "row_top1_predicted",
        "soft_endpoint_oracle_mass_values",
        "soft_endpoint_oracle_mass_denominator",
        "query",
    }
)
_CLASSIFICATION_EVIDENCE_KEYS = frozenset({"predictions", "targets"})
_MARGINAL_EVIDENCE_KEYS = frozenset({"train", "development"})
_COMPETENCE_EVIDENCE_KEYS = frozenset(
    {"train", "development", "deranged", "permutation"}
)
_PERMUTATION_EVIDENCE_KEYS = frozenset({"shape", "logit_differences"})
_LOCAL_ROW_METRIC_KEYS = frozenset(
    {
        "row_top1_accuracy",
        "row_top1_actual",
        "row_top1_predicted",
        "row_top1_correct_count",
        "row_top1_support_count",
        "duplicate_current_rows",
        "selected_real_rows",
        "duplicate_current_rate",
        "row_probability_sha256",
        "row_top1_sha256",
        "birth_mask_sha256",
    }
)


def _mapping_or_issue(
    value: Any, pointer: str, issues: list[ValidationIssue]
) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        issues.append(_issue(pointer, "object", value))
        return None
    for key in value:
        if not isinstance(key, str):
            issues.append(_issue(pointer, "object keys are strings", key))
            return None
    return value


def _closed_keys(
    value: Mapping[str, Any],
    expected: frozenset[str],
    pointer: str,
    issues: list[ValidationIssue],
) -> bool:
    actual = set(value)
    for key in sorted(expected - actual):
        issues.append(
            _issue(json_pointer_join(pointer, key), "required key present", None)
        )
    for key in sorted(actual - expected):
        issues.append(
            _issue(json_pointer_join(pointer, key), "unknown key forbidden", value[key])
        )
    return actual == set(expected)


def _list_or_issue(
    value: Any, pointer: str, issues: list[ValidationIssue]
) -> list[Any] | None:
    if not isinstance(value, list):
        issues.append(_issue(pointer, "array", value))
        return None
    return value


def _integer_vector(
    value: Any,
    pointer: str,
    issues: list[ValidationIssue],
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> list[int] | None:
    values = _list_or_issue(value, pointer, issues)
    if values is None:
        return None
    valid = True
    for index, item in enumerate(values):
        item_pointer = json_pointer_join(pointer, index)
        if isinstance(item, bool) or not isinstance(item, int):
            issues.append(_issue(item_pointer, "integer not boolean", item))
            valid = False
        elif minimum is not None and item < minimum:
            issues.append(_issue(item_pointer, f">= {minimum}", item))
            valid = False
        elif maximum is not None and item > maximum:
            issues.append(_issue(item_pointer, f"<= {maximum}", item))
            valid = False
    return values if valid else None


def _number_vector(
    value: Any,
    pointer: str,
    issues: list[ValidationIssue],
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> list[float] | None:
    values = _list_or_issue(value, pointer, issues)
    if values is None:
        return None
    result: list[float] = []
    valid = True
    for index, item in enumerate(values):
        item_pointer = json_pointer_join(pointer, index)
        if (
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or not math.isfinite(float(item))
        ):
            issues.append(_issue(item_pointer, "finite number not boolean", item))
            valid = False
            continue
        number = float(item)
        if minimum is not None and number < minimum:
            issues.append(_issue(item_pointer, f">= {minimum!r}", item))
            valid = False
        elif maximum is not None and number > maximum:
            issues.append(_issue(item_pointer, f"<= {maximum!r}", item))
            valid = False
        result.append(number)
    return result if valid else None


def _integer_value(
    value: Any,
    pointer: str,
    issues: list[ValidationIssue],
    *,
    minimum: int | None = None,
) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        issues.append(_issue(pointer, "integer not boolean", value))
        return None
    if minimum is not None and value < minimum:
        issues.append(_issue(pointer, f">= {minimum}", value))
        return None
    return value


def _number_value(
    value: Any,
    pointer: str,
    issues: list[ValidationIssue],
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float | None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        issues.append(_issue(pointer, "finite number not boolean", value))
        return None
    result = float(value)
    if minimum is not None and result < minimum:
        issues.append(_issue(pointer, f">= {minimum!r}", value))
        return None
    if maximum is not None and result > maximum:
        issues.append(_issue(pointer, f"<= {maximum!r}", value))
        return None
    return result


def _recomputed_number(
    stored: Any,
    expected: float,
    pointer: str,
    issues: list[ValidationIssue],
    *,
    tolerance: float = 1e-7,
) -> None:
    observed = _number_value(stored, pointer, issues)
    if observed is not None and not math.isclose(
        observed, expected, rel_tol=0.0, abs_tol=tolerance
    ):
        issues.append(_issue(pointer, f"recomputed value {expected!r}", stored))


def _recomputed_integer(
    stored: Any, expected: int, pointer: str, issues: list[ValidationIssue]
) -> None:
    observed = _integer_value(stored, pointer, issues, minimum=0)
    if observed is not None and observed != expected:
        issues.append(_issue(pointer, f"recomputed count {expected}", stored))


def _macro_f1_from_vectors(
    predictions: Sequence[int], targets: Sequence[int], label_count: int
) -> float:
    values: list[float] = []
    for label in range(label_count):
        tp = sum(
            int(predicted == label and target == label)
            for predicted, target in zip(predictions, targets, strict=True)
        )
        fp = sum(
            int(predicted == label and target != label)
            for predicted, target in zip(predictions, targets, strict=True)
        )
        fn = sum(
            int(predicted != label and target == label)
            for predicted, target in zip(predictions, targets, strict=True)
        )
        denominator = 2 * tp + fp + fn
        values.append(2 * tp / denominator if denominator else 0.0)
    return math.fsum(values) / label_count


def _classification_vectors(
    value: Any,
    pointer: str,
    issues: list[ValidationIssue],
    *,
    maximum_label: int,
) -> tuple[list[int], list[int]] | None:
    evidence = _mapping_or_issue(value, pointer, issues)
    if evidence is None:
        return None
    _closed_keys(evidence, _CLASSIFICATION_EVIDENCE_KEYS, pointer, issues)
    predictions = _integer_vector(
        evidence.get("predictions"),
        json_pointer_join(pointer, "predictions"),
        issues,
        minimum=0,
        maximum=maximum_label,
    )
    targets = _integer_vector(
        evidence.get("targets"),
        json_pointer_join(pointer, "targets"),
        issues,
        minimum=0,
        maximum=maximum_label,
    )
    if predictions is None or targets is None:
        return None
    if not predictions or len(predictions) != len(targets):
        issues.append(
            _issue(pointer, "nonempty equal-length predictions and targets", evidence)
        )
        return None
    return predictions, targets


def _validate_label_metrics(
    value: Any, pointer: str, issues: list[ValidationIssue]
) -> None:
    metrics = _mapping_or_issue(value, pointer, issues)
    if metrics is None:
        return
    _closed_keys(metrics, _LABEL_METRIC_KEYS, pointer, issues)
    predictions = _integer_vector(
        metrics.get("predictions"),
        json_pointer_join(pointer, "predictions"),
        issues,
        minimum=0,
        maximum=4,
    )
    targets = _integer_vector(
        metrics.get("targets"),
        json_pointer_join(pointer, "targets"),
        issues,
        minimum=0,
        maximum=4,
    )
    if predictions is None or targets is None:
        return
    if not predictions or len(predictions) != len(targets):
        issues.append(
            _issue(pointer, "nonempty equal-length predictions and targets", metrics)
        )
        return
    persistent_indices = [index for index, target in enumerate(targets) if target <= 2]
    if not persistent_indices:
        issues.append(
            _issue(
                json_pointer_join(pointer, "targets"),
                "at least one persistent target in labels 0..2",
                targets,
            )
        )
        return
    persistent_predictions = [predictions[index] for index in persistent_indices]
    persistent_targets = [targets[index] for index in persistent_indices]
    _recomputed_number(
        metrics.get("five_label_macro_f1"),
        _macro_f1_from_vectors(predictions, targets, 5),
        json_pointer_join(pointer, "five_label_macro_f1"),
        issues,
    )
    _recomputed_number(
        metrics.get("persistent_three_label_macro_f1"),
        _macro_f1_from_vectors(persistent_predictions, persistent_targets, 3),
        json_pointer_join(pointer, "persistent_three_label_macro_f1"),
        issues,
    )
    _recomputed_number(
        metrics.get("accuracy"),
        sum(
            int(predicted == target)
            for predicted, target in zip(predictions, targets, strict=True)
        )
        / len(targets),
        json_pointer_join(pointer, "accuracy"),
        issues,
    )


def _validate_binary_metrics(
    value: Any, pointer: str, issues: list[ValidationIssue]
) -> tuple[list[int], list[int]] | None:
    metrics = _mapping_or_issue(value, pointer, issues)
    if metrics is None:
        return None
    _closed_keys(metrics, _BINARY_METRIC_KEYS, pointer, issues)
    actual = _integer_vector(
        metrics.get("actual"),
        json_pointer_join(pointer, "actual"),
        issues,
        minimum=0,
        maximum=1,
    )
    predicted = _integer_vector(
        metrics.get("predicted"),
        json_pointer_join(pointer, "predicted"),
        issues,
        minimum=0,
        maximum=1,
    )
    if actual is None or predicted is None:
        return None
    if not actual or len(actual) != len(predicted):
        issues.append(
            _issue(
                pointer, "nonempty equal-length actual and predicted vectors", metrics
            )
        )
        return None
    tp = sum(a == 1 and p == 1 for a, p in zip(actual, predicted, strict=True))
    fp = sum(a == 0 and p == 1 for a, p in zip(actual, predicted, strict=True))
    fn = sum(a == 1 and p == 0 for a, p in zip(actual, predicted, strict=True))
    tn = sum(a == 0 and p == 0 for a, p in zip(actual, predicted, strict=True))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    expected_counts = {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "positive_support": tp + fn,
        "predicted_positive_support": tp + fp,
    }
    for key, expected in expected_counts.items():
        _recomputed_integer(
            metrics.get(key), expected, json_pointer_join(pointer, key), issues
        )
    expected_numbers = {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "balanced_accuracy": 0.5 * (recall + specificity),
        "non_gating_accuracy": (tp + tn) / len(actual),
    }
    for key, expected in expected_numbers.items():
        _recomputed_number(
            metrics.get(key), expected, json_pointer_join(pointer, key), issues
        )
    return actual, predicted


def _case_exact_flags(
    actual: Sequence[int], predicted: Sequence[int], case_count: int
) -> list[bool] | None:
    if case_count <= 0 or len(actual) % case_count != 0:
        return None
    width = len(actual) // case_count
    return [
        list(actual[index * width : (index + 1) * width])
        == list(predicted[index * width : (index + 1) * width])
        for index in range(case_count)
    ]


def _validate_null_metrics(
    value: Any, pointer: str, issues: list[ValidationIssue]
) -> None:
    metrics = _mapping_or_issue(value, pointer, issues)
    if metrics is None:
        return
    _closed_keys(metrics, _NULL_METRIC_KEYS, pointer, issues)
    death = _validate_binary_metrics(
        metrics.get("death"), json_pointer_join(pointer, "death"), issues
    )
    birth = _validate_binary_metrics(
        metrics.get("birth"), json_pointer_join(pointer, "birth"), issues
    )
    evidence_pointer = json_pointer_join(pointer, "metric_evidence")
    evidence = _mapping_or_issue(
        metrics.get("metric_evidence"), evidence_pointer, issues
    )
    if evidence is None:
        return
    _closed_keys(evidence, _NULL_EVIDENCE_KEYS, evidence_pointer, issues)
    case_count = _integer_value(
        evidence.get("case_count"),
        json_pointer_join(evidence_pointer, "case_count"),
        issues,
        minimum=1,
    )
    if death is None or birth is None or case_count is None:
        return
    death_flags = _case_exact_flags(*death, case_count)
    birth_flags = _case_exact_flags(*birth, case_count)
    if death_flags is None:
        issues.append(
            _issue(
                json_pointer_join(json_pointer_join(pointer, "death"), "actual"),
                "length divisible by case_count",
                death[0],
            )
        )
    if birth_flags is None:
        issues.append(
            _issue(
                json_pointer_join(json_pointer_join(pointer, "birth"), "actual"),
                "length divisible by case_count",
                birth[0],
            )
        )
    if death_flags is None or birth_flags is None:
        return
    death_count = sum(death_flags)
    birth_count = sum(birth_flags)
    joint_count = sum(
        death_exact and birth_exact
        for death_exact, birth_exact in zip(death_flags, birth_flags, strict=True)
    )
    for key, expected in (
        ("death_exact_count", death_count),
        ("birth_exact_count", birth_count),
        ("joint_exact_count", joint_count),
    ):
        _recomputed_integer(
            evidence.get(key),
            expected,
            json_pointer_join(evidence_pointer, key),
            issues,
        )
    for key, expected in (
        ("death_exact_case", death_count / case_count),
        ("birth_exact_case", birth_count / case_count),
        ("null_exact_case", joint_count / case_count),
    ):
        _recomputed_number(
            metrics.get(key), expected, json_pointer_join(pointer, key), issues
        )
    death_metrics = metrics.get("death")
    birth_metrics = metrics.get("birth")
    if isinstance(death_metrics, Mapping) and isinstance(birth_metrics, Mapping):
        death_f1 = _number_value(
            death_metrics.get("f1"),
            json_pointer_join(json_pointer_join(pointer, "death"), "f1"),
            issues,
        )
        birth_f1 = _number_value(
            birth_metrics.get("f1"),
            json_pointer_join(json_pointer_join(pointer, "birth"), "f1"),
            issues,
        )
        if death_f1 is not None and birth_f1 is not None:
            _recomputed_number(
                metrics.get("macro_f1"),
                0.5 * (death_f1 + birth_f1),
                json_pointer_join(pointer, "macro_f1"),
                issues,
            )
        expected_support = bool(sum(death[0]) > 0 and sum(birth[0]) > 0)
        observed_support = metrics.get("positive_support_both")
        if (
            not isinstance(observed_support, bool)
            or observed_support is not expected_support
        ):
            issues.append(
                _issue(
                    json_pointer_join(pointer, "positive_support_both"),
                    f"recomputed boolean {expected_support!r}",
                    observed_support,
                )
            )


def _validate_query_metrics(
    metrics_value: Any,
    evidence_value: Any,
    pointer: str,
    evidence_pointer: str,
    issues: list[ValidationIssue],
) -> None:
    metrics = _mapping_or_issue(metrics_value, pointer, issues)
    evidence = _mapping_or_issue(evidence_value, evidence_pointer, issues)
    if metrics is None or evidence is None:
        return
    _closed_keys(metrics, _QUERY_METRIC_KEYS, pointer, issues)
    _closed_keys(evidence, _QUERY_EVIDENCE_KEYS, evidence_pointer, issues)
    correct = _integer_vector(
        evidence.get("hard_query_correct"),
        json_pointer_join(evidence_pointer, "hard_query_correct"),
        issues,
        minimum=0,
        maximum=1,
    )
    mass = _number_vector(
        evidence.get("soft_oracle_query_mass_values"),
        json_pointer_join(evidence_pointer, "soft_oracle_query_mass_values"),
        issues,
        minimum=0.0,
        maximum=1.0,
    )
    nll = _number_vector(
        evidence.get("soft_query_nll_values"),
        json_pointer_join(evidence_pointer, "soft_query_nll_values"),
        issues,
        minimum=0.0,
    )
    brier = _number_vector(
        evidence.get("soft_query_brier_values"),
        json_pointer_join(evidence_pointer, "soft_query_brier_values"),
        issues,
        minimum=0.0,
        maximum=1.0,
    )
    oracle_indices = _integer_vector(
        evidence.get("oracle_current_indices"),
        json_pointer_join(evidence_pointer, "oracle_current_indices"),
        issues,
        minimum=0,
    )
    raw_rows = _list_or_issue(
        evidence.get("soft_query_probability_rows"),
        json_pointer_join(evidence_pointer, "soft_query_probability_rows"),
        issues,
    )
    probability_rows: list[list[float]] | None = [] if raw_rows is not None else None
    if raw_rows is not None:
        for index, raw_row in enumerate(raw_rows):
            row = _number_vector(
                raw_row,
                json_pointer_join(
                    json_pointer_join(evidence_pointer, "soft_query_probability_rows"),
                    index,
                ),
                issues,
                minimum=0.0,
                maximum=1.0,
            )
            if row is None or not row:
                probability_rows = None
                break
            assert probability_rows is not None
            probability_rows.append(row)
    vectors = (correct, mass, nll, brier, oracle_indices, probability_rows)
    if any(vector is None for vector in vectors):
        return
    assert (
        correct is not None
        and mass is not None
        and nll is not None
        and brier is not None
    )
    lengths = {len(vector) for vector in vectors}
    if lengths != {len(correct)} or not correct:
        issues.append(
            _issue(
                evidence_pointer,
                "six nonempty equal-length query evidence vectors",
                evidence,
            )
        )
        return
    assert oracle_indices is not None and probability_rows is not None
    derived_mass: list[float] = []
    derived_nll: list[float] = []
    derived_brier: list[float] = []
    for index, (row, oracle_index) in enumerate(
        zip(probability_rows, oracle_indices, strict=True)
    ):
        if oracle_index >= len(row):
            issues.append(
                _issue(
                    json_pointer_join(evidence_pointer, "oracle_current_indices")
                    + f"/{index}",
                    f"index below probability-row length {len(row)}",
                    oracle_index,
                )
            )
            return
        oracle_mass = row[oracle_index]
        derived_mass.append(oracle_mass)
        derived_nll.append(-math.log(max(oracle_mass, 1e-8)))
        derived_brier.append(
            math.fsum(
                (value - (1.0 if column == oracle_index else 0.0)) ** 2
                for column, value in enumerate(row)
            )
            / len(row)
        )
    for key, observed, derived in (
        ("soft_oracle_query_mass_values", mass, derived_mass),
        ("soft_query_nll_values", nll, derived_nll),
        ("soft_query_brier_values", brier, derived_brier),
    ):
        assert observed is not None
        if len(observed) != len(derived) or any(
            not math.isclose(left, right, rel_tol=0.0, abs_tol=1e-6)
            for left, right in zip(observed, derived, strict=True)
        ):
            issues.append(
                _issue(
                    json_pointer_join(evidence_pointer, key),
                    f"values derived from probability rows {derived!r}",
                    observed,
                )
            )
    correct_mean = math.fsum(correct) / len(correct)
    expected = {
        "hard_query_identity_accuracy": correct_mean,
        "hard_query_identity_f1": correct_mean,
        "soft_oracle_query_mass": math.fsum(derived_mass) / len(derived_mass),
        "soft_query_nll": math.fsum(derived_nll) / len(derived_nll),
        "soft_query_brier": math.fsum(derived_brier) / len(derived_brier),
        "hard_query_identity_chance_reference": 1.0 / 6.0,
        "soft_oracle_mass_chance_reference": 1.0 / 6.0,
    }
    for key, value in expected.items():
        _recomputed_number(
            metrics.get(key), value, json_pointer_join(pointer, key), issues
        )


def _validate_transport_metrics(
    value: Any, pointer: str, issues: list[ValidationIssue]
) -> None:
    metrics = _mapping_or_issue(value, pointer, issues)
    if metrics is None:
        return
    _closed_keys(metrics, _TRANSPORT_METRIC_KEYS, pointer, issues)
    for key in ("soft_plan_sha256", "hard_plan_sha256"):
        observed = metrics.get(key)
        if not is_lowercase_sha256(observed):
            issues.append(
                _issue(
                    json_pointer_join(pointer, key), "lowercase SHA-256 hex", observed
                )
            )
    _validate_null_metrics(
        metrics.get("null_metrics"), json_pointer_join(pointer, "null_metrics"), issues
    )
    evidence_pointer = json_pointer_join(pointer, "metric_evidence")
    evidence = _mapping_or_issue(
        metrics.get("metric_evidence"), evidence_pointer, issues
    )
    if evidence is None:
        return
    _closed_keys(evidence, _TRANSPORT_EVIDENCE_KEYS, evidence_pointer, issues)
    correct = _integer_vector(
        evidence.get("hard_endpoint_correct"),
        json_pointer_join(evidence_pointer, "hard_endpoint_correct"),
        issues,
        minimum=0,
        maximum=1,
    )
    actual = _integer_vector(
        evidence.get("row_top1_actual"),
        json_pointer_join(evidence_pointer, "row_top1_actual"),
        issues,
        minimum=0,
    )
    predicted = _integer_vector(
        evidence.get("row_top1_predicted"),
        json_pointer_join(evidence_pointer, "row_top1_predicted"),
        issues,
        minimum=0,
    )
    soft_values = _number_vector(
        evidence.get("soft_endpoint_oracle_mass_values"),
        json_pointer_join(evidence_pointer, "soft_endpoint_oracle_mass_values"),
        issues,
        minimum=0.0,
        maximum=1.0,
    )
    denominator = _number_value(
        evidence.get("soft_endpoint_oracle_mass_denominator"),
        json_pointer_join(evidence_pointer, "soft_endpoint_oracle_mass_denominator"),
        issues,
        minimum=0.0,
    )
    if correct is not None and actual is not None and predicted is not None:
        if not actual or len(actual) != len(predicted) or len(actual) != len(correct):
            issues.append(
                _issue(
                    evidence_pointer,
                    "nonempty equal-length endpoint and row vectors",
                    evidence,
                )
            )
        else:
            expected_correct = [
                int(observed == target)
                for observed, target in zip(predicted, actual, strict=True)
            ]
            if correct != expected_correct:
                issues.append(
                    _issue(
                        json_pointer_join(evidence_pointer, "hard_endpoint_correct"),
                        f"row comparisons {expected_correct!r}",
                        correct,
                    )
                )
            accuracy = math.fsum(expected_correct) / len(expected_correct)
            _recomputed_number(
                metrics.get("hard_all_endpoint_assignment_accuracy"),
                accuracy,
                json_pointer_join(pointer, "hard_all_endpoint_assignment_accuracy"),
                issues,
            )
            _recomputed_number(
                metrics.get("row_top1_accuracy"),
                accuracy,
                json_pointer_join(pointer, "row_top1_accuracy"),
                issues,
            )
    if soft_values is not None and denominator is not None:
        if not soft_values or denominator != float(len(soft_values)):
            issues.append(
                _issue(
                    json_pointer_join(
                        evidence_pointer, "soft_endpoint_oracle_mass_denominator"
                    ),
                    f"exact oracle support count {len(soft_values)}",
                    denominator,
                )
            )
        else:
            _recomputed_number(
                metrics.get("soft_all_endpoint_oracle_mass"),
                math.fsum(soft_values) / denominator,
                json_pointer_join(pointer, "soft_all_endpoint_oracle_mass"),
                issues,
                tolerance=1e-6,
            )
    _validate_query_metrics(
        metrics.get("query"),
        evidence.get("query"),
        json_pointer_join(pointer, "query"),
        json_pointer_join(evidence_pointer, "query"),
        issues,
    )


def _validate_marginal_control(
    value: Any, pointer: str, issues: list[ValidationIssue], *, competence: bool
) -> None:
    result = _mapping_or_issue(value, pointer, issues)
    if result is None:
        return
    raw_pointer = json_pointer_join(pointer, "raw_evidence")
    raw = _mapping_or_issue(result.get("raw_evidence"), raw_pointer, issues)
    if raw is None:
        return
    expected_keys = _COMPETENCE_EVIDENCE_KEYS if competence else _MARGINAL_EVIDENCE_KEYS
    _closed_keys(raw, expected_keys, raw_pointer, issues)
    for split, metric_key in (
        ("train", "train_macro_f1"),
        ("development", "development_macro_f1"),
    ):
        vectors = _classification_vectors(
            raw.get(split),
            json_pointer_join(raw_pointer, split),
            issues,
            maximum_label=2,
        )
        if vectors is not None:
            _recomputed_number(
                result.get(metric_key),
                _macro_f1_from_vectors(*vectors, 3),
                json_pointer_join(pointer, metric_key),
                issues,
            )
    if not competence:
        return
    deranged = _classification_vectors(
        raw.get("deranged"),
        json_pointer_join(raw_pointer, "deranged"),
        issues,
        maximum_label=2,
    )
    if deranged is not None:
        _recomputed_number(
            result.get("cyclic_code_derangement_macro_f1"),
            _macro_f1_from_vectors(*deranged, 3),
            json_pointer_join(pointer, "cyclic_code_derangement_macro_f1"),
            issues,
        )
    permutation_pointer = json_pointer_join(raw_pointer, "permutation")
    permutation = _mapping_or_issue(raw.get("permutation"), permutation_pointer, issues)
    if permutation is None:
        return
    _closed_keys(permutation, _PERMUTATION_EVIDENCE_KEYS, permutation_pointer, issues)
    shape = _integer_vector(
        permutation.get("shape"),
        json_pointer_join(permutation_pointer, "shape"),
        issues,
        minimum=0,
    )
    differences = _number_vector(
        permutation.get("logit_differences"),
        json_pointer_join(permutation_pointer, "logit_differences"),
        issues,
    )
    if shape is None or differences is None:
        return
    if len(shape) != 2 or math.prod(shape) != len(differences) or not differences:
        issues.append(
            _issue(
                permutation_pointer,
                "rank-2 shape whose product equals nonempty logit_differences length",
                permutation,
            )
        )
        return
    _recomputed_number(
        result.get("permutation_invariance_max_logit_error"),
        max(abs(value) for value in differences),
        json_pointer_join(pointer, "permutation_invariance_max_logit_error"),
        issues,
    )


def _validate_local_row_metrics(
    value: Any, pointer: str, issues: list[ValidationIssue]
) -> None:
    metrics = _mapping_or_issue(value, pointer, issues)
    if metrics is None:
        return
    _closed_keys(metrics, _LOCAL_ROW_METRIC_KEYS, pointer, issues)
    actual = _integer_vector(
        metrics.get("row_top1_actual"),
        json_pointer_join(pointer, "row_top1_actual"),
        issues,
        minimum=0,
    )
    predicted = _integer_vector(
        metrics.get("row_top1_predicted"),
        json_pointer_join(pointer, "row_top1_predicted"),
        issues,
        minimum=0,
    )
    for key in ("row_probability_sha256", "row_top1_sha256", "birth_mask_sha256"):
        observed = metrics.get(key)
        if not is_lowercase_sha256(observed):
            issues.append(
                _issue(
                    json_pointer_join(pointer, key), "lowercase SHA-256 hex", observed
                )
            )
    if actual is None or predicted is None:
        return
    if not actual or len(actual) != len(predicted):
        issues.append(
            _issue(
                pointer,
                "nonempty equal-length row actual and predicted vectors",
                metrics,
            )
        )
        return
    correct = sum(
        observed == target for observed, target in zip(predicted, actual, strict=True)
    )
    _recomputed_integer(
        metrics.get("row_top1_correct_count"),
        correct,
        json_pointer_join(pointer, "row_top1_correct_count"),
        issues,
    )
    _recomputed_integer(
        metrics.get("row_top1_support_count"),
        len(actual),
        json_pointer_join(pointer, "row_top1_support_count"),
        issues,
    )
    _recomputed_number(
        metrics.get("row_top1_accuracy"),
        correct / len(actual),
        json_pointer_join(pointer, "row_top1_accuracy"),
        issues,
    )
    duplicates = _integer_value(
        metrics.get("duplicate_current_rows"),
        json_pointer_join(pointer, "duplicate_current_rows"),
        issues,
        minimum=0,
    )
    selected = _integer_value(
        metrics.get("selected_real_rows"),
        json_pointer_join(pointer, "selected_real_rows"),
        issues,
        minimum=0,
    )
    if duplicates is not None and selected is not None:
        if duplicates > selected or selected > len(actual):
            issues.append(
                _issue(
                    pointer,
                    "0 <= duplicate_current_rows <= selected_real_rows <= row support",
                    [duplicates, selected, len(actual)],
                )
            )
        _recomputed_number(
            metrics.get("duplicate_current_rate"),
            duplicates / selected if selected else 0.0,
            json_pointer_join(pointer, "duplicate_current_rate"),
            issues,
        )


def _dynamic_children(
    value: Any, pointer: str, issues: list[ValidationIssue]
) -> list[tuple[str, Any, str]]:
    mapping = _mapping_or_issue(value, pointer, issues)
    if mapping is None:
        return []
    if not mapping:
        issues.append(_issue(pointer, "nonempty object", mapping))
        return []
    return [
        (key, mapping[key], json_pointer_join(pointer, key)) for key in sorted(mapping)
    ]


def _derived_value(
    stored: Any,
    expected: Any,
    pointer: str,
    issues: list[ValidationIssue],
    *,
    tolerance: float = 1e-9,
) -> None:
    """Compare one stored derivative without accepting bools as numbers."""

    if isinstance(expected, float):
        if (
            isinstance(stored, bool)
            or not isinstance(stored, (int, float))
            or not math.isfinite(float(stored))
            or not math.isclose(float(stored), expected, rel_tol=0.0, abs_tol=tolerance)
        ):
            issues.append(_issue(pointer, f"recomputed value {expected!r}", stored))
        return
    if type(stored) is not type(expected) or stored != expected:
        issues.append(_issue(pointer, f"recomputed value {expected!r}", stored))


def _gate_derivatives(
    gate: Any,
    pointer: str,
    expected_checks: Mapping[str, bool],
    failure_status: str,
    issues: list[ValidationIssue],
) -> None:
    """Validate a gate's check map, pass bit, and terminal status."""

    value = _mapping_or_issue(gate, pointer, issues)
    if value is None:
        return
    checks_pointer = json_pointer_join(pointer, "checks")
    checks = _mapping_or_issue(value.get("checks"), checks_pointer, issues)
    if checks is None:
        return
    _closed_keys(checks, frozenset(expected_checks), checks_pointer, issues)
    for name, expected in expected_checks.items():
        _derived_value(
            checks.get(name),
            expected,
            json_pointer_join(checks_pointer, name),
            issues,
        )
    passed = all(expected_checks.values()) and all(
        item is True for item in checks.values()
    )
    _derived_value(
        value.get("passed"), passed, json_pointer_join(pointer, "passed"), issues
    )
    _derived_value(
        value.get("status"),
        "PASS" if passed else failure_status,
        json_pointer_join(pointer, "status"),
        issues,
    )


def _seed_results(
    root: Mapping[str, Any], field: str, issues: list[ValidationIssue]
) -> Mapping[str, Any] | None:
    if field not in root:
        return None
    return _mapping_or_issue(root.get(field), json_pointer_join("", field), issues)


_INITIALIZATION_KEYS = frozenset(
    {
        "schema_version",
        "seed",
        "distribution",
        "std",
        "generator",
        "runtime_rule",
        "literal_vector_sha256",
        "observed_literal_vector_sha256",
        "literal_values",
        "literal_float32_little_endian_hex",
        "parameter_order",
        "runtime_parameter_name_mapping",
        "raw_values",
        "effective_values",
        "per_parameter_tensor_sha256",
        "raw_initial_state_sha256",
        "effective_initial_state_sha256",
        "runtime_state_dict_parameter_order",
        "runtime_state_dict_shapes",
        "runtime_state_dict_dtype",
        "runtime_initial_state_sha256",
        "expected_seed_evidence",
        "checks",
        "passed",
        "state_sha256",
    }
)
_INITIALIZATION_CHECK_KEYS = frozenset(
    {
        "literal_vector_hash_exact",
        "protocol_literal_values_exact",
        "parameter_order_exact",
        "per_parameter_hashes_exact",
        "raw_state_hash_exact",
        "effective_state_hash_exact",
        "runtime_state_metadata_exact",
        "runtime_state_hash_exact",
        "absolute_literal_bound_passed",
    }
)


def _named_scalar_bytes(name: str, raw: bytes) -> bytes:
    return name.encode("utf-8") + b"\0torch.float32\0" + raw


def _runtime_matcher_state_hash_from_literal_bytes(literal_bytes: bytes) -> str:
    """Rebuild the four-tensor runtime hash from five registered float32s."""

    if len(literal_bytes) != 20:
        raise ValueError("runtime matcher initialization requires five float32s")
    entries = (
        ("current_null_utility", (), literal_bytes[16:20]),
        ("prior_null_utility", (), literal_bytes[12:16]),
        ("residual_coefficient", (), literal_bytes[0:4]),
        ("view_weight_logits", (2,), literal_bytes[4:12]),
    )
    digest = hashlib.sha256()
    for name, shape, payload in entries:
        digest.update(name.encode("utf-8"))
        digest.update(b"torch.float32")
        digest.update(str(shape).encode("ascii"))
        digest.update(payload)
    return digest.hexdigest()


def _runtime_matcher_state_hash_from_evidence(
    evidence: Mapping[str, Any],
) -> str | None:
    encoded_hex = evidence.get("literal_float32_little_endian_hex")
    if not isinstance(encoded_hex, str):
        return None
    try:
        encoded = bytes.fromhex(encoded_hex)
    except ValueError:
        return None
    if len(encoded) != 20 or encoded_hex != encoded.hex():
        return None
    return _runtime_matcher_state_hash_from_literal_bytes(encoded)


def _validate_initialization_evidence(
    value: Any, pointer: str, issues: list[ValidationIssue]
) -> bool:
    """Rebuild the registered five-scalar raw initialization evidence."""

    evidence = _mapping_or_issue(value, pointer, issues)
    if evidence is None:
        return False
    _closed_keys(evidence, _INITIALIZATION_KEYS, pointer, issues)
    _derived_value(
        evidence.get("schema_version"),
        _R6_INITIALIZATION_SCHEMA_VERSION,
        json_pointer_join(pointer, "schema_version"),
        issues,
    )
    seed = evidence.get("seed")
    seed_valid = isinstance(seed, int) and not isinstance(seed, bool)
    if not seed_valid:
        issues.append(_issue(json_pointer_join(pointer, "seed"), "integer seed", seed))
    _derived_value(
        evidence.get("distribution"),
        "normal",
        json_pointer_join(pointer, "distribution"),
        issues,
    )
    _derived_value(evidence.get("std"), 0.01, json_pointer_join(pointer, "std"), issues)
    if seed_valid:
        _derived_value(
            evidence.get("generator"),
            "torch.Generator(device=cpu).manual_seed(seed)",
            json_pointer_join(pointer, "generator"),
            issues,
        )
    _derived_value(
        evidence.get("runtime_rule"),
        "load_frozen_literals_do_not_redraw",
        json_pointer_join(pointer, "runtime_rule"),
        issues,
    )
    _derived_value(
        evidence.get("parameter_order"),
        list(_R6_INITIAL_PARAMETER_ORDER),
        json_pointer_join(pointer, "parameter_order"),
        issues,
    )
    expected_mapping = {
        "residual_coefficient": "residual_coefficient",
        "view_weight_logits.0": "view_weight_logits[0]",
        "view_weight_logits.1": "view_weight_logits[1]",
        "prior_null_utility_raw": "prior_null_utility",
        "current_null_utility_raw": "current_null_utility",
    }
    _derived_value(
        evidence.get("runtime_parameter_name_mapping"),
        expected_mapping,
        json_pointer_join(pointer, "runtime_parameter_name_mapping"),
        issues,
    )
    _derived_value(
        evidence.get("runtime_state_dict_parameter_order"),
        list(_R8_RUNTIME_STATE_PARAMETER_ORDER),
        json_pointer_join(pointer, "runtime_state_dict_parameter_order"),
        issues,
    )
    _derived_value(
        evidence.get("runtime_state_dict_shapes"),
        _R8_RUNTIME_STATE_SHAPES,
        json_pointer_join(pointer, "runtime_state_dict_shapes"),
        issues,
    )
    _derived_value(
        evidence.get("runtime_state_dict_dtype"),
        "torch.float32",
        json_pointer_join(pointer, "runtime_state_dict_dtype"),
        issues,
    )

    literal_values = _number_vector(
        evidence.get("literal_values"),
        json_pointer_join(pointer, "literal_values"),
        issues,
    )
    if literal_values is not None and len(literal_values) != 5:
        issues.append(
            _issue(
                json_pointer_join(pointer, "literal_values"),
                "exactly five float32 literals",
                literal_values,
            )
        )
        literal_values = None
    encoded_hex = evidence.get("literal_float32_little_endian_hex")
    encoded: bytes | None = None
    if isinstance(encoded_hex, str):
        try:
            encoded = bytes.fromhex(encoded_hex)
        except ValueError:
            encoded = None
    if encoded is None or len(encoded) != 20:
        issues.append(
            _issue(
                json_pointer_join(pointer, "literal_float32_little_endian_hex"),
                "20 little-endian float32 bytes encoded as 40 lowercase hex characters",
                encoded_hex,
            )
        )
        encoded = None
    elif encoded_hex != encoded.hex():
        issues.append(
            _issue(
                json_pointer_join(pointer, "literal_float32_little_endian_hex"),
                "lowercase canonical hex",
                encoded_hex,
            )
        )
    if literal_values is not None:
        packed = struct.pack("<5f", *literal_values)
        if encoded is not None and packed != encoded:
            issues.append(
                _issue(
                    json_pointer_join(pointer, "literal_float32_little_endian_hex"),
                    "byte encoding recomputed from literal_values",
                    encoded_hex,
                )
            )

    observed_literal_hash = hashlib.sha256(encoded).hexdigest() if encoded else None
    runtime_initial_hash = (
        _runtime_matcher_state_hash_from_literal_bytes(encoded)
        if encoded is not None
        else None
    )
    if observed_literal_hash is not None:
        _derived_value(
            evidence.get("observed_literal_vector_sha256"),
            observed_literal_hash,
            json_pointer_join(pointer, "observed_literal_vector_sha256"),
            issues,
        )
    if runtime_initial_hash is not None:
        _derived_value(
            evidence.get("runtime_initial_state_sha256"),
            runtime_initial_hash,
            json_pointer_join(pointer, "runtime_initial_state_sha256"),
            issues,
        )
    raw_values = evidence.get("raw_values")
    raw_map = _mapping_or_issue(
        raw_values, json_pointer_join(pointer, "raw_values"), issues
    )
    raw_hashes: dict[str, str] = {}
    raw_state = hashlib.sha256()
    if raw_map is not None:
        _closed_keys(
            raw_map,
            frozenset(_R6_INITIAL_PARAMETER_ORDER),
            json_pointer_join(pointer, "raw_values"),
            issues,
        )
    if encoded is not None and raw_map is not None:
        unpacked = struct.unpack("<5f", encoded)
        for index, name in enumerate(_R6_INITIAL_PARAMETER_ORDER):
            _derived_value(
                raw_map.get(name),
                float(unpacked[index]),
                json_pointer_join(json_pointer_join(pointer, "raw_values"), name),
                issues,
                tolerance=0.0,
            )
            scalar_bytes = _named_scalar_bytes(name, encoded[index * 4 : index * 4 + 4])
            raw_hashes[name] = hashlib.sha256(scalar_bytes).hexdigest()
            raw_state.update(scalar_bytes)
        _derived_value(
            evidence.get("per_parameter_tensor_sha256"),
            raw_hashes,
            json_pointer_join(pointer, "per_parameter_tensor_sha256"),
            issues,
        )
        _derived_value(
            evidence.get("raw_initial_state_sha256"),
            raw_state.hexdigest(),
            json_pointer_join(pointer, "raw_initial_state_sha256"),
            issues,
        )
        _derived_value(
            evidence.get("state_sha256"),
            raw_state.hexdigest(),
            json_pointer_join(pointer, "state_sha256"),
            issues,
        )

        residual, view0, view1, prior_null, current_null = unpacked
        max_view = max(view0, view1)
        exp0 = math.exp(view0 - max_view)
        exp1 = math.exp(view1 - max_view)
        effective_expected = {
            "residual_coefficient_effective": 0.02 * math.tanh(residual),
            "view_weights_effective.0": exp0 / (exp0 + exp1),
            "view_weights_effective.1": exp1 / (exp0 + exp1),
            "prior_null_utility_effective": 0.10 * math.tanh(prior_null),
            "current_null_utility_effective": 0.10 * math.tanh(current_null),
        }
        effective = _mapping_or_issue(
            evidence.get("effective_values"),
            json_pointer_join(pointer, "effective_values"),
            issues,
        )
        if effective is not None:
            _closed_keys(
                effective,
                frozenset(effective_expected),
                json_pointer_join(pointer, "effective_values"),
                issues,
            )
            for name, expected_value in effective_expected.items():
                _derived_value(
                    effective.get(name),
                    expected_value,
                    json_pointer_join(
                        json_pointer_join(pointer, "effective_values"), name
                    ),
                    issues,
                    tolerance=1e-7,
                )

    expected_seed = _mapping_or_issue(
        evidence.get("expected_seed_evidence"),
        json_pointer_join(pointer, "expected_seed_evidence"),
        issues,
    )
    if expected_seed is not None:
        _closed_keys(
            expected_seed,
            frozenset(
                {
                    "per_parameter_tensor_sha256",
                    "raw_initial_state_sha256",
                    "effective_initial_state_sha256",
                }
            ),
            json_pointer_join(pointer, "expected_seed_evidence"),
            issues,
        )

    expected_checks = {
        "literal_vector_hash_exact": observed_literal_hash is not None
        and evidence.get("literal_vector_sha256") == observed_literal_hash,
        "protocol_literal_values_exact": encoded is not None
        and literal_values is not None
        and struct.pack("<5f", *literal_values) == encoded,
        "parameter_order_exact": evidence.get("parameter_order")
        == list(_R6_INITIAL_PARAMETER_ORDER),
        "per_parameter_hashes_exact": expected_seed is not None
        and evidence.get("per_parameter_tensor_sha256")
        == expected_seed.get("per_parameter_tensor_sha256"),
        "raw_state_hash_exact": expected_seed is not None
        and evidence.get("raw_initial_state_sha256")
        == expected_seed.get("raw_initial_state_sha256"),
        "effective_state_hash_exact": expected_seed is not None
        and evidence.get("effective_initial_state_sha256")
        == expected_seed.get("effective_initial_state_sha256"),
        "runtime_state_metadata_exact": evidence.get(
            "runtime_state_dict_parameter_order"
        )
        == list(_R8_RUNTIME_STATE_PARAMETER_ORDER)
        and evidence.get("runtime_state_dict_shapes") == _R8_RUNTIME_STATE_SHAPES
        and evidence.get("runtime_state_dict_dtype") == "torch.float32",
        "runtime_state_hash_exact": runtime_initial_hash is not None
        and evidence.get("runtime_initial_state_sha256") == runtime_initial_hash,
        "absolute_literal_bound_passed": literal_values is not None
        and max(abs(float(item)) for item in literal_values) <= 0.02,
    }
    checks = _mapping_or_issue(
        evidence.get("checks"), json_pointer_join(pointer, "checks"), issues
    )
    if checks is not None:
        _closed_keys(
            checks,
            _INITIALIZATION_CHECK_KEYS,
            json_pointer_join(pointer, "checks"),
            issues,
        )
        for name, expected in expected_checks.items():
            _derived_value(
                checks.get(name),
                expected,
                json_pointer_join(json_pointer_join(pointer, "checks"), name),
                issues,
            )
    passed = all(expected_checks.values())
    _derived_value(
        evidence.get("passed"), passed, json_pointer_join(pointer, "passed"), issues
    )
    return passed


def _validate_exact64_audit(
    result: Mapping[str, Any], pointer: str, issues: list[ValidationIssue]
) -> bool:
    audit_pointer = json_pointer_join(pointer, "exact64_execution_audit")
    audit = _mapping_or_issue(
        result.get("exact64_execution_audit"), audit_pointer, issues
    )
    if audit is None:
        return False
    _closed_keys(
        audit,
        frozenset(
            {
                "passed",
                "checks",
                "observed_adapter_score_calls",
                "expected_adapter_score_calls",
                "observed_total_adapter_score_calls",
                "expected_total_adapter_score_calls",
                "placeholder_counts",
                "phase_evidence",
            }
        ),
        audit_pointer,
        issues,
    )
    observed = audit.get("observed_adapter_score_calls")
    expected = audit.get("expected_adapter_score_calls")
    observed_map = _mapping_or_issue(
        observed,
        json_pointer_join(audit_pointer, "observed_adapter_score_calls"),
        issues,
    )
    expected_map = _mapping_or_issue(
        expected,
        json_pointer_join(audit_pointer, "expected_adapter_score_calls"),
        issues,
    )
    phase_prefix = result.get("execution_kind")
    steps = result.get("registered_gradient_steps")
    registered_trace: dict[str, int] | None = None
    if (
        isinstance(phase_prefix, str)
        and phase_prefix
        and isinstance(steps, int)
        and not isinstance(steps, bool)
        and steps >= 0
    ):
        registered_trace = {
            f"{phase_prefix}_training_{stratum}": steps for stratum in _R6_STRATA
        }
        registered_trace.update(
            {
                f"{phase_prefix}_final_{stratum}_{split}": 1
                for stratum in _R6_STRATA
                for split in _R6_SPLITS
            }
        )
    calls_exact = (
        observed_map is not None
        and expected_map is not None
        and observed_map == expected_map
        and registered_trace is not None
        and observed_map == registered_trace
    )
    observed_total = (
        sum(observed_map.values())
        if observed_map is not None
        and all(
            isinstance(value, int) and not isinstance(value, bool)
            for value in observed_map.values()
        )
        else None
    )
    expected_total = (
        sum(expected_map.values())
        if expected_map is not None
        and all(
            isinstance(value, int) and not isinstance(value, bool)
            for value in expected_map.values()
        )
        else None
    )
    if observed_total is None:
        issues.append(
            _issue(
                json_pointer_join(audit_pointer, "observed_adapter_score_calls"),
                "integer call-count map",
                observed,
            )
        )
    if expected_total is None:
        issues.append(
            _issue(
                json_pointer_join(audit_pointer, "expected_adapter_score_calls"),
                "integer call-count map",
                expected,
            )
        )
    total_exact = (
        observed_total is not None
        and expected_total is not None
        and observed_total == expected_total
    )
    if observed_total is not None:
        _derived_value(
            audit.get("observed_total_adapter_score_calls"),
            observed_total,
            json_pointer_join(audit_pointer, "observed_total_adapter_score_calls"),
            issues,
        )
    if expected_total is not None:
        _derived_value(
            audit.get("expected_total_adapter_score_calls"),
            expected_total,
            json_pointer_join(audit_pointer, "expected_total_adapter_score_calls"),
            issues,
        )

    placeholders = _mapping_or_issue(
        audit.get("placeholder_counts"),
        json_pointer_join(audit_pointer, "placeholder_counts"),
        issues,
    )
    final_phases = (
        {
            f"{phase_prefix}_final_{stratum}_{split}"
            for stratum in _R6_STRATA
            for split in _R6_SPLITS
        }
        if isinstance(phase_prefix, str) and phase_prefix
        else set()
    )
    all_exact64 = placeholders is not None and bool(placeholders)
    if placeholders is not None:
        if set(placeholders) != final_phases:
            issues.append(
                _issue(
                    json_pointer_join(audit_pointer, "placeholder_counts"),
                    f"phase keys exactly {sorted(final_phases)!r}",
                    placeholders,
                )
            )
            all_exact64 = False
        for phase, counts in placeholders.items():
            vector = _integer_vector(
                counts,
                json_pointer_join(
                    json_pointer_join(audit_pointer, "placeholder_counts"), phase
                ),
                issues,
                minimum=0,
            )
            all_exact64 = (
                all_exact64
                and vector is not None
                and bool(vector)
                and all(value == 64 for value in vector)
            )
    phase_evidence = _mapping_or_issue(
        audit.get("phase_evidence"),
        json_pointer_join(audit_pointer, "phase_evidence"),
        issues,
    )
    no_pixels = phase_evidence is not None and bool(phase_evidence)
    model_frozen = phase_evidence is not None and bool(phase_evidence)
    if phase_evidence is not None:
        if set(phase_evidence) != final_phases:
            issues.append(
                _issue(
                    json_pointer_join(audit_pointer, "phase_evidence"),
                    f"phase keys exactly {sorted(final_phases)!r}",
                    phase_evidence,
                )
            )
            no_pixels = False
            model_frozen = False
        for phase, evidence_value in phase_evidence.items():
            phase_pointer = json_pointer_join(
                json_pointer_join(audit_pointer, "phase_evidence"), phase
            )
            evidence = _mapping_or_issue(evidence_value, phase_pointer, issues)
            if evidence is None:
                no_pixels = False
                model_frozen = False
                continue
            _closed_keys(
                evidence,
                frozenset({"pixel_inputs_used", "model_frozen"}),
                phase_pointer,
                issues,
            )
            no_pixels = no_pixels and evidence.get("pixel_inputs_used") is False
            model_frozen = model_frozen and evidence.get("model_frozen") is True

    non_none = result.get("matcher_gradient_non_none_count")
    nonzero = result.get("matcher_gradient_nonzero_count")
    counts_valid = (
        isinstance(non_none, int)
        and not isinstance(non_none, bool)
        and isinstance(nonzero, int)
        and not isinstance(nonzero, bool)
        and 0 <= nonzero <= non_none
    )
    if not counts_valid:
        issues.append(
            _issue(
                json_pointer_join(pointer, "matcher_gradient_nonzero_count"),
                "integer count between zero and matcher_gradient_non_none_count",
                nonzero,
            )
        )
    gradient_zero = counts_valid and non_none == 0 and nonzero == 0
    _derived_value(
        result.get("matcher_gradients_zero"),
        gradient_zero,
        json_pointer_join(pointer, "matcher_gradients_zero"),
        issues,
    )
    adapter_before = result.get("adapter_before_sha256")
    adapter_after = result.get("adapter_after_sha256")
    final_projector = result.get("final_train_state_sha256")
    frozen_projector = result.get("frozen_state_sha256")
    matcher_before = result.get("matcher_before_sha256")
    matcher_after = result.get("matcher_after_sha256")
    for field, state_hash in (
        ("adapter_before_sha256", adapter_before),
        ("adapter_after_sha256", adapter_after),
        ("final_train_state_sha256", final_projector),
        ("frozen_state_sha256", frozen_projector),
    ):
        if not is_lowercase_sha256(state_hash):
            issues.append(
                _issue(
                    json_pointer_join(pointer, field), "lowercase SHA-256", state_hash
                )
            )
    matcher_hashes_valid = (matcher_before is None and matcher_after is None) or (
        is_lowercase_sha256(matcher_before) and is_lowercase_sha256(matcher_after)
    )
    if not matcher_hashes_valid:
        issues.append(
            _issue(
                json_pointer_join(pointer, "matcher_before_sha256"),
                "both matcher hashes are null or both are lowercase SHA-256",
                [matcher_before, matcher_after],
            )
        )
    adapter_unchanged = (
        is_lowercase_sha256(adapter_before) and adapter_before == adapter_after
    )
    projector_unchanged = (
        is_lowercase_sha256(final_projector) and final_projector == frozen_projector
    )
    matcher_unchanged = matcher_hashes_valid and matcher_before == matcher_after
    _derived_value(
        result.get("adapter_unchanged"),
        adapter_unchanged,
        json_pointer_join(pointer, "adapter_unchanged"),
        issues,
    )
    _derived_value(
        result.get("projector_state_unchanged_by_freeze"),
        projector_unchanged,
        json_pointer_join(pointer, "projector_state_unchanged_by_freeze"),
        issues,
    )
    _derived_value(
        result.get("matcher_unchanged"),
        matcher_unchanged,
        json_pointer_join(pointer, "matcher_unchanged"),
        issues,
    )
    finite_steps = result.get("finite_gradient_steps")
    gradients_finite = (
        isinstance(finite_steps, int)
        and not isinstance(finite_steps, bool)
        and isinstance(steps, int)
        and not isinstance(steps, bool)
        and finite_steps == steps
    )
    _derived_value(
        result.get("all_gradients_finite"),
        gradients_finite,
        json_pointer_join(pointer, "all_gradients_finite"),
        issues,
    )
    optimizer_names = result.get("optimizer_parameter_names")
    trainable_names = result.get("trainable_parameter_names")
    optimizer_only_projector = (
        isinstance(optimizer_names, list)
        and bool(optimizer_names)
        and optimizer_names == trainable_names
        and len(optimizer_names) == len(set(optimizer_names))
        and all(isinstance(name, str) and name for name in optimizer_names)
    )
    _derived_value(
        result.get("optimizer_only_projector"),
        optimizer_only_projector,
        json_pointer_join(pointer, "optimizer_only_projector"),
        issues,
    )
    derived_checks = {
        "adapter_calls_exact": calls_exact,
        "total_adapter_calls_exact": total_exact,
        "all_placeholders_exact64": all_exact64,
        "no_pixels": no_pixels,
        "frozen_adapter_reported": model_frozen,
        "adapter_state_unchanged": adapter_unchanged,
        "projector_frozen_after_fit": projector_unchanged,
        "matcher_state_unchanged": matcher_unchanged,
    }
    checks = _mapping_or_issue(
        audit.get("checks"), json_pointer_join(audit_pointer, "checks"), issues
    )
    if checks is not None:
        _closed_keys(
            checks,
            frozenset(derived_checks),
            json_pointer_join(audit_pointer, "checks"),
            issues,
        )
        for name, expected_value in derived_checks.items():
            _derived_value(
                checks.get(name),
                expected_value,
                json_pointer_join(json_pointer_join(audit_pointer, "checks"), name),
                issues,
            )
    passed = all(derived_checks.values())
    _derived_value(
        audit.get("passed"), passed, json_pointer_join(audit_pointer, "passed"), issues
    )
    return passed


def _validate_transport_gates(
    root: Mapping[str, Any], issues: list[ValidationIssue]
) -> None:
    results = _seed_results(root, "transport_results", issues)
    if results is None:
        return
    seeds = list(results)
    clean_hard: dict[str, Any] = {}
    clean_soft: dict[str, Any] = {}
    clean_null: dict[str, Any] = {}
    transport_execution: dict[str, dict[str, bool]] = {}
    for seed, result_value in results.items():
        result = _mapping_or_issue(result_value, f"/transport_results/{seed}", issues)
        if result is None:
            continue
        result_pointer = f"/transport_results/{seed}"
        execution_present = (
            "transport_competence_gate" in root or "initialization" in result
        )
        initialization_passed = False
        if execution_present:
            initialization_passed = _validate_initialization_evidence(
                result.get("initialization"),
                json_pointer_join(result_pointer, "initialization"),
                issues,
            )
        initial_hash = result.get("initial_state_sha256")
        final_hash = result.get("final_state_sha256")
        frozen_hash = result.get("frozen_state_sha256")
        for field, state_hash in (
            ("initial_state_sha256", initial_hash),
            ("final_state_sha256", final_hash),
            ("frozen_state_sha256", frozen_hash),
        ):
            if execution_present and not is_lowercase_sha256(state_hash):
                issues.append(
                    _issue(
                        json_pointer_join(result_pointer, field),
                        "lowercase SHA-256",
                        state_hash,
                    )
                )
        initialization = result.get("initialization", {})
        runtime_initial_hash = (
            _runtime_matcher_state_hash_from_evidence(initialization)
            if isinstance(initialization, Mapping)
            else None
        )
        init_exact = (
            initialization_passed
            and runtime_initial_hash is not None
            and initialization.get("runtime_initial_state_sha256")
            == runtime_initial_hash
            and initial_hash == runtime_initial_hash
        )
        if execution_present and runtime_initial_hash is not None:
            _derived_value(
                initial_hash,
                runtime_initial_hash,
                json_pointer_join(result_pointer, "initial_state_sha256"),
                issues,
            )
        matcher_changed = (
            is_lowercase_sha256(initial_hash)
            and is_lowercase_sha256(final_hash)
            and initial_hash != final_hash
        )
        frozen = is_lowercase_sha256(final_hash) and final_hash == frozen_hash
        finite_steps = result.get("finite_gradient_steps")
        registered_steps = result.get("registered_gradient_steps")
        gradients_finite = (
            isinstance(finite_steps, int)
            and not isinstance(finite_steps, bool)
            and isinstance(registered_steps, int)
            and not isinstance(registered_steps, bool)
            and finite_steps == registered_steps
        )
        nonzero_steps = result.get("nonzero_gradient_steps")
        nonzero_valid = (
            isinstance(nonzero_steps, int)
            and not isinstance(nonzero_steps, bool)
            and isinstance(registered_steps, int)
            and not isinstance(registered_steps, bool)
            and 0 < nonzero_steps <= registered_steps
        )
        names = result.get("optimizer_parameter_names")
        trainable = result.get("trainable_parameter_names")
        optimizer_only = (
            isinstance(names, list)
            and isinstance(trainable, list)
            and set(names) == set(_R6_MATCHER_PARAMETER_NAMES)
            and set(trainable) == set(_R6_MATCHER_PARAMETER_NAMES)
            and len(names) == len(_R6_MATCHER_PARAMETER_NAMES)
            and len(trainable) == len(_R6_MATCHER_PARAMETER_NAMES)
        )
        for field, expected in (
            ("matcher_changed", matcher_changed),
            ("state_unchanged_by_freeze", frozen),
            ("all_gradients_finite", gradients_finite),
            ("optimizer_only_matcher", optimizer_only),
        ):
            if execution_present:
                _derived_value(
                    result.get(field),
                    expected,
                    json_pointer_join(result_pointer, field),
                    issues,
                )
        if execution_present:
            transport_execution[seed] = {
                "initialization_exact": init_exact,
                "matcher_changed": matcher_changed,
                "frozen": frozen,
                "gradients_finite": gradients_finite,
                "nonzero_gradients": nonzero_valid,
                "optimizer_only": optimizer_only,
            }
        evaluations = result.get("evaluations", {})
        try:
            metrics = evaluations["clean"]["development"]
            clean_hard[seed] = metrics["hard_all_endpoint_assignment_accuracy"]
            clean_soft[seed] = metrics["query"]["soft_oracle_query_mass"]
            clean_null[seed] = metrics["null_metrics"]
        except (KeyError, TypeError):
            continue
    if "transport_competence_gate" in root and set(clean_hard) == set(seeds):
        gate = root["transport_competence_gate"]
        gate_map = _mapping_or_issue(gate, "/transport_competence_gate", issues)
        if gate_map is not None:
            _derived_value(
                gate_map.get("hard_by_seed"),
                clean_hard,
                "/transport_competence_gate/hard_by_seed",
                issues,
            )
            _derived_value(
                gate_map.get("soft_by_seed"),
                clean_soft,
                "/transport_competence_gate/soft_by_seed",
                issues,
            )
            _derived_value(
                gate_map.get("null_metrics_by_seed"),
                clean_null,
                "/transport_competence_gate/null_metrics_by_seed",
                issues,
            )
        initial_hashes = [
            value.get("initialization", {}).get("runtime_initial_state_sha256")
            for value in results.values()
            if isinstance(value, Mapping)
        ]
        init_exact = set(transport_execution) == set(seeds) and all(
            value["initialization_exact"] for value in transport_execution.values()
        )
        expected_checks = {
            "seed_specific_initial_hashes_distinct": len(initial_hashes) == len(seeds)
            and len(set(initial_hashes)) == len(seeds),
            "initial_hashes_rederive_exactly": init_exact,
            "every_seed_hard_at_least_0_90": all(
                value >= 0.90 for value in clean_hard.values()
            ),
            "aggregate_hard_at_least_0_95": recompute_average(list(clean_hard.values()))
            >= 0.95,
            "every_seed_soft_at_least_0_30": all(
                value >= 0.30 for value in clean_soft.values()
            ),
            "aggregate_soft_at_least_0_35": recompute_average(list(clean_soft.values()))
            >= 0.35,
            "every_seed_death_precision_exact": all(
                value["death"]["precision"] >= 1.0 for value in clean_null.values()
            ),
            "every_seed_death_recall_exact": all(
                value["death"]["recall"] >= 1.0 for value in clean_null.values()
            ),
            "every_seed_death_f1_exact": all(
                value["death"]["f1"] >= 1.0 for value in clean_null.values()
            ),
            "every_seed_birth_precision_exact": all(
                value["birth"]["precision"] >= 1.0 for value in clean_null.values()
            ),
            "every_seed_birth_recall_exact": all(
                value["birth"]["recall"] >= 1.0 for value in clean_null.values()
            ),
            "every_seed_birth_f1_exact": all(
                value["birth"]["f1"] >= 1.0 for value in clean_null.values()
            ),
            "every_seed_null_exact_case": all(
                value["null_exact_case"] >= 1.0 for value in clean_null.values()
            ),
            "every_seed_has_death_and_birth_support": all(
                value["positive_support_both"] is True for value in clean_null.values()
            ),
            "all_transport_gradients_finite": all(
                value["gradients_finite"] and value["nonzero_gradients"]
                for value in transport_execution.values()
            ),
            "optimizer_only_matcher": all(
                value["optimizer_only"] for value in transport_execution.values()
            ),
            "matcher_checkpoint_frozen": all(
                value["frozen"] for value in transport_execution.values()
            ),
        }
        _gate_derivatives(
            gate,
            "/transport_competence_gate",
            expected_checks,
            "FAIL_TRANSPORT_COMPETENCE",
            issues,
        )

    if "anti_equivalence_gate" not in root:
        return
    challenge_hard: dict[str, Any] = {}
    challenge_soft: dict[str, Any] = {}
    for seed, result in results.items():
        try:
            metrics = result["evaluations"]["challenge"]["development"]
            challenge_hard[seed] = metrics["hard_all_endpoint_assignment_accuracy"]
            challenge_soft[seed] = metrics["query"]["soft_oracle_query_mass"]
        except (KeyError, TypeError):
            continue
    gate = root["anti_equivalence_gate"]
    gate_map = _mapping_or_issue(gate, "/anti_equivalence_gate", issues)
    if gate_map is not None:
        _derived_value(
            gate_map.get("hard_by_seed"),
            challenge_hard,
            "/anti_equivalence_gate/hard_by_seed",
            issues,
        )
        _derived_value(
            gate_map.get("soft_by_seed"),
            challenge_soft,
            "/anti_equivalence_gate/soft_by_seed",
            issues,
        )
    if set(challenge_hard) != set(seeds):
        return
    expected_checks = {
        "every_seed_hard_at_least_0_70": all(
            value >= 0.70 for value in challenge_hard.values()
        ),
        "aggregate_hard_at_least_0_80": recompute_average(list(challenge_hard.values()))
        >= 0.80,
        "every_seed_soft_at_least_0_30": all(
            value >= 0.30 for value in challenge_soft.values()
        ),
        "aggregate_soft_at_least_0_35": recompute_average(list(challenge_soft.values()))
        >= 0.35,
        "matcher_changed": all(
            value["matcher_changed"] for value in transport_execution.values()
        ),
    }
    _gate_derivatives(
        gate, "/anti_equivalence_gate", expected_checks, "FAIL_ANTI_EQUIVALENCE", issues
    )


def _marginal_gate_derivatives(
    controls: Mapping[str, Any], gate: Any, pointer: str, issues: list[ValidationIssue]
) -> bool:
    gate_map = _mapping_or_issue(gate, pointer, issues)
    if gate_map is None:
        return False
    competence_required = gate_map.get("competence_required") is True
    development: dict[str, dict[str, bool]] = {}
    competence: dict[str, dict[str, bool]] = {}
    combined: dict[str, dict[str, bool]] = {}
    for seed, seed_value in controls.items():
        seed_controls = _mapping_or_issue(
            seed_value, f"/marginal_controls/{seed}", issues
        )
        if seed_controls is None:
            continue
        development[seed] = {}
        competence[seed] = {}
        combined[seed] = {}
        for mode, value in seed_controls.items():
            control = value if isinstance(value, Mapping) else {}
            development[seed][mode] = (
                isinstance(control.get("development_macro_f1"), (int, float))
                and not isinstance(control.get("development_macro_f1"), bool)
                and control["development_macro_f1"] <= 0.45
            )
        for mode in (
            "current_only_deepsets",
            "prior_only_deepsets",
            "prior_current_deepsets",
        ):
            control = seed_controls.get(mode, {})
            probe = (
                control.get("competence_probe", {})
                if isinstance(control, Mapping)
                else {}
            )
            competence[seed][mode] = bool(
                isinstance(probe, Mapping)
                and probe.get("train_macro_f1", -math.inf) >= 0.99
                and probe.get("development_macro_f1", -math.inf) >= 0.99
                and probe.get("final_train_loss", math.inf) <= 0.05
                and probe.get("all_gradients_finite") is True
                and probe.get("finite_gradient_steps")
                == probe.get("registered_gradient_steps", 500)
                and probe.get("permutation_invariance_max_logit_error", math.inf)
                <= 1e-4
                and probe.get("cyclic_code_derangement_macro_f1", math.inf) <= 0.10
                and isinstance(control, Mapping)
                and control.get("actual_visible_unchanged") is True
            )
        for mode, development_pass in development[seed].items():
            combined[seed][mode] = development_pass and (
                competence[seed].get(mode, True) or not competence_required
            )
    _derived_value(
        gate_map.get("maximum_persistent_development_macro_f1"),
        0.45,
        json_pointer_join(pointer, "maximum_persistent_development_macro_f1"),
        issues,
    )
    _derived_value(
        gate_map.get("minimum_deepsets_train_macro_f1"),
        0.99,
        json_pointer_join(pointer, "minimum_deepsets_train_macro_f1"),
        issues,
    )
    _derived_value(
        gate_map.get("minimum_deepsets_development_macro_f1"),
        0.99,
        json_pointer_join(pointer, "minimum_deepsets_development_macro_f1"),
        issues,
    )
    _derived_value(
        gate_map.get("maximum_deepsets_final_train_loss"),
        0.05,
        json_pointer_join(pointer, "maximum_deepsets_final_train_loss"),
        issues,
    )
    _derived_value(
        gate_map.get("maximum_permutation_invariance_logit_error"),
        1e-4,
        json_pointer_join(pointer, "maximum_permutation_invariance_logit_error"),
        issues,
    )
    _derived_value(
        gate_map.get("maximum_cyclic_code_derangement_macro_f1"),
        0.10,
        json_pointer_join(pointer, "maximum_cyclic_code_derangement_macro_f1"),
        issues,
    )
    _derived_value(
        gate_map.get("development_checks"),
        development,
        json_pointer_join(pointer, "development_checks"),
        issues,
    )
    _derived_value(
        gate_map.get("competence_checks"),
        competence,
        json_pointer_join(pointer, "competence_checks"),
        issues,
    )
    _derived_value(
        gate_map.get("checks"), combined, json_pointer_join(pointer, "checks"), issues
    )
    bypass_pass = all(value for seed in development.values() for value in seed.values())
    competence_pass = all(
        value for seed in competence.values() for value in seed.values()
    )
    passed = bypass_pass and (competence_pass or not competence_required)
    status = (
        "PASS"
        if passed
        else (
            "FAIL_ASSIGNMENT_BYPASS"
            if not bypass_pass
            else "NOT_EVALUABLE_MARGINAL_CONTROL_INCOMPETENT"
        )
    )
    _derived_value(
        gate_map.get("passed"), passed, json_pointer_join(pointer, "passed"), issues
    )
    _derived_value(
        gate_map.get("status"), status, json_pointer_join(pointer, "status"), issues
    )
    return passed


def _validate_readout_and_fixture_gates(
    root: Mapping[str, Any], issues: list[ValidationIssue]
) -> None:
    oracle = _seed_results(root, "common_oracle_readout_results", issues)
    mediator = _seed_results(root, "mediator_results", issues)
    oracle_exact: dict[str, bool] = {}
    mediator_exact: dict[str, bool] = {}
    if oracle is not None:
        for seed, value in oracle.items():
            result = _mapping_or_issue(
                value, f"/common_oracle_readout_results/{seed}", issues
            )
            if result is not None and "exact64_execution_audit" in result:
                oracle_exact[seed] = _validate_exact64_audit(
                    result, f"/common_oracle_readout_results/{seed}", issues
                )
    if mediator is not None:
        for seed, value in mediator.items():
            result = _mapping_or_issue(value, f"/mediator_results/{seed}", issues)
            if result is not None and "exact64_execution_audit" in result:
                mediator_exact[seed] = _validate_exact64_audit(
                    result, f"/mediator_results/{seed}", issues
                )

    controls = _seed_results(root, "marginal_controls", issues)
    binding = _seed_results(root, "binding_results", issues)
    fixture = root.get("post_transport_fixture_competence")
    if (
        fixture is not None
        and oracle is not None
        and controls is not None
        and binding is not None
    ):
        pointer = "/post_transport_fixture_competence"
        gate = _mapping_or_issue(fixture, pointer, issues)
        if gate is not None:
            oracle_checks: dict[str, Any] = {}
            for seed, result in oracle.items():
                metrics = (
                    result.get("metrics", {}) if isinstance(result, Mapping) else {}
                )
                oracle_checks[seed] = {
                    stratum: {
                        "train_persistent_at_least_0_95": metrics[stratum]["train"][
                            "persistent_three_label_macro_f1"
                        ]
                        >= 0.95,
                        "development_persistent_at_least_0_85": metrics[stratum][
                            "development"
                        ]["persistent_three_label_macro_f1"]
                        >= 0.85,
                    }
                    for stratum in ("clean", "challenge")
                }
                oracle_checks[seed]["execution"] = {
                    "exact64": oracle_exact.get(seed) is True,
                    "adapter_unchanged": result.get("adapter_unchanged") is True,
                    "projector_frozen": result.get(
                        "projector_state_unchanged_by_freeze"
                    )
                    is True,
                    "oracle_fit_once": result.get("execution_kind") == "oracle_readout",
                }
            _derived_value(
                gate.get("oracle_checks"),
                oracle_checks,
                json_pointer_join(pointer, "oracle_checks"),
                issues,
            )

            marginal_pass = _marginal_gate_derivatives(
                controls,
                gate.get("marginal_control_gate"),
                json_pointer_join(pointer, "marginal_control_gate"),
                issues,
            )
            deltas: dict[str, float] = {}
            isomorphism_expected: dict[str, dict[str, Any]] = {}
            all_binding_scored = True
            all_isomorphic = True
            for seed, seed_results in binding.items():
                clean_oracle = oracle[seed]["metrics"]["clean"]["development"][
                    "persistent_three_label_macro_f1"
                ]
                cells: list[float] = []
                isomorphism_expected[seed] = {}
                stored_iso = gate.get("b4_isomorphism", {}).get(seed, {})
                for derangement, scored in seed_results.items():
                    cells.append(
                        100.0
                        * (
                            clean_oracle
                            - scored["metrics"]["persistent_three_label_macro_f1"]
                        )
                    )
                    scored_passed = scored.get("passed") is True
                    all_binding_scored = all_binding_scored and scored_passed
                    stored = stored_iso.get(derangement, {})
                    passed = bool(
                        scored_passed
                        and stored.get("shared_batch_sha256")
                        == stored.get("b4a_batch_sha256")
                        == stored.get("b4b_batch_sha256")
                        and stored.get("b4a_plan_sha256")
                        != stored.get("b4b_plan_sha256")
                        and stored.get("projector_sha256")
                        == scored.get("projector_sha256")
                        and stored.get("adapter_sha256") == scored.get("adapter_sha256")
                    )
                    expected = dict(stored)
                    expected["passed"] = passed
                    isomorphism_expected[seed][derangement] = expected
                    all_isomorphic = all_isomorphic and passed
                deltas[seed] = recompute_average(cells)
            aggregate_delta = recompute_average(list(deltas.values()))
            _derived_value(
                gate.get("binding_delta_by_seed_percentage_points"),
                deltas,
                json_pointer_join(pointer, "binding_delta_by_seed_percentage_points"),
                issues,
            )
            _derived_value(
                gate.get("binding_aggregate_delta_percentage_points"),
                aggregate_delta,
                json_pointer_join(pointer, "binding_aggregate_delta_percentage_points"),
                issues,
            )
            _derived_value(
                gate.get("b4_isomorphism"),
                isomorphism_expected,
                json_pointer_join(pointer, "b4_isomorphism"),
                issues,
            )
            oracle_pass = all(
                value
                for seed_checks in oracle_checks.values()
                for checks in seed_checks.values()
                for value in checks.values()
            )
            binding_pass = (
                all(value > 0.0 for value in deltas.values())
                and aggregate_delta >= 5.0
                and all_binding_scored
            )
            stored_checks = gate.get("checks", {})
            expected_checks = {
                "oracle_readout_competent_both_strata": oracle_pass,
                "challenge_analytic_identifiability": stored_checks.get(
                    "challenge_analytic_identifiability"
                )
                is True,
                "challenge_row_local_state_attack_blocked": stored_checks.get(
                    "challenge_row_local_state_attack_blocked"
                )
                is True,
                "marginal_bypass_bank": marginal_pass,
                "frozen_readout_binding": binding_pass,
                "b4_isomorphism": all_isomorphic,
            }
            _gate_derivatives(
                fixture,
                pointer,
                expected_checks,
                "FAIL_FIXTURE_IDENTIFIABILITY",
                issues,
            )

    if "mediator_recovery_gate" not in root or mediator is None:
        return
    gate = root["mediator_recovery_gate"]
    f1 = {
        seed: {
            stratum: result["metrics"][stratum]["development"][
                "persistent_three_label_macro_f1"
            ]
            for stratum in ("clean", "challenge")
        }
        for seed, result in mediator.items()
    }
    gate_map = _mapping_or_issue(gate, "/mediator_recovery_gate", issues)
    if gate_map is not None:
        _derived_value(
            gate_map.get("persistent_f1_by_seed_and_stratum"),
            f1,
            "/mediator_recovery_gate/persistent_f1_by_seed_and_stratum",
            issues,
        )
    expected_checks = {
        "every_seed_every_stratum_persistent_f1_at_least_0_80": all(
            value >= 0.80 for seed in f1.values() for value in seed.values()
        ),
        "each_stratum_aggregate_persistent_f1_at_least_0_85": all(
            recompute_average([f1[seed][stratum] for seed in f1]) >= 0.85
            for stratum in ("clean", "challenge")
        ),
        "matcher_gradient_exactly_zero": all(
            result.get("matcher_gradients_zero") is True
            and result.get("matcher_gradient_non_none_count") == 0
            and result.get("matcher_gradient_nonzero_count") == 0
            for result in mediator.values()
        ),
        "matcher_state_unchanged": all(
            result.get("matcher_unchanged") is True for result in mediator.values()
        ),
        "exact64": all(mediator_exact.values())
        and set(mediator_exact) == set(mediator),
    }
    if "post_transport_fixture_competence" in root:
        expected_checks["post_transport_fixture_competence"] = (
            root["post_transport_fixture_competence"].get("passed") is True
        )
    _gate_derivatives(
        gate,
        "/mediator_recovery_gate",
        expected_checks,
        "FAIL_MEDIATOR_RECOVERY",
        issues,
    )


def _scored_leaf_passes(
    value: Any, pointer: str, issues: list[ValidationIssue]
) -> bool:
    result = _mapping_or_issue(value, pointer, issues)
    if result is None:
        return False
    checks = _mapping_or_issue(
        result.get("checks"), json_pointer_join(pointer, "checks"), issues
    )
    if checks is None:
        return False
    trace = _mapping_or_issue(
        result.get("observed_adapter_score_calls"),
        json_pointer_join(pointer, "observed_adapter_score_calls"),
        issues,
    )
    expected_trace = _mapping_or_issue(
        result.get("expected_adapter_score_calls"),
        json_pointer_join(pointer, "expected_adapter_score_calls"),
        issues,
    )
    single_call = (
        trace is not None
        and expected_trace is not None
        and trace == expected_trace
        and len(trace) == 1
        and next(iter(trace.values()), None) == 1
    )
    phase = next(iter(trace), None) if trace is not None and len(trace) == 1 else None
    placeholders = _mapping_or_issue(
        result.get("placeholder_counts"),
        json_pointer_join(pointer, "placeholder_counts"),
        issues,
    )
    placeholders_exact = (
        isinstance(phase, str)
        and placeholders is not None
        and set(placeholders) == {phase}
        and isinstance(placeholders.get(phase), list)
        and bool(placeholders[phase])
        and all(
            isinstance(item, int) and not isinstance(item, bool) and item == 64
            for item in placeholders[phase]
        )
    )
    phase_evidence = _mapping_or_issue(
        result.get("phase_evidence"),
        json_pointer_join(pointer, "phase_evidence"),
        issues,
    )
    phase_record = (
        phase_evidence.get(phase)
        if phase_evidence is not None and isinstance(phase, str)
        else None
    )
    phase_map = _mapping_or_issue(
        phase_record,
        json_pointer_join(json_pointer_join(pointer, "phase_evidence"), phase or ""),
        issues,
    )
    if phase_evidence is not None and isinstance(phase, str):
        _closed_keys(
            phase_evidence,
            frozenset({phase}),
            json_pointer_join(pointer, "phase_evidence"),
            issues,
        )
    if phase_map is not None:
        _closed_keys(
            phase_map,
            frozenset({"pixel_inputs_used", "model_frozen"}),
            json_pointer_join(
                json_pointer_join(pointer, "phase_evidence"), phase or ""
            ),
            issues,
        )
    no_pixels = phase_map is not None and phase_map.get("pixel_inputs_used") is False
    adapter_frozen = phase_map is not None and phase_map.get("model_frozen") is True
    projector_before = result.get("projector_before_sha256")
    projector_after = result.get("projector_after_sha256")
    adapter_before = result.get("adapter_before_sha256")
    adapter_after = result.get("adapter_after_sha256")
    for field, state_hash in (
        ("projector_before_sha256", projector_before),
        ("projector_after_sha256", projector_after),
        ("adapter_before_sha256", adapter_before),
        ("adapter_after_sha256", adapter_after),
    ):
        if not is_lowercase_sha256(state_hash):
            issues.append(
                _issue(
                    json_pointer_join(pointer, field), "lowercase SHA-256", state_hash
                )
            )
    projector_unchanged = (
        is_lowercase_sha256(projector_before) and projector_before == projector_after
    )
    adapter_unchanged = (
        is_lowercase_sha256(adapter_before) and adapter_before == adapter_after
    )
    _derived_value(
        result.get("projector_sha256"),
        projector_before,
        json_pointer_join(pointer, "projector_sha256"),
        issues,
    )
    _derived_value(
        result.get("adapter_sha256"),
        adapter_before,
        json_pointer_join(pointer, "adapter_sha256"),
        issues,
    )
    local = "local_output_sha256" in result or "contract_tokens_sha256" in result
    expected_checks = {
        "single_exact64_call": single_call,
        "placeholders_exact64": placeholders_exact,
        "no_pixels": no_pixels,
        "adapter_frozen": adapter_frozen,
        "projector_unchanged": projector_unchanged,
        "adapter_unchanged": adapter_unchanged,
    }
    if local:
        expected_checks["pure_row_local"] = is_lowercase_sha256(
            result.get("local_output_sha256")
        ) and is_lowercase_sha256(result.get("contract_tokens_sha256"))
    _closed_keys(
        checks,
        frozenset(expected_checks),
        json_pointer_join(pointer, "checks"),
        issues,
    )
    for name, expected in expected_checks.items():
        _derived_value(
            checks.get(name),
            expected,
            json_pointer_join(json_pointer_join(pointer, "checks"), name),
            issues,
        )
    passed = all(expected_checks.values())
    _derived_value(
        result.get("passed"), passed, json_pointer_join(pointer, "passed"), issues
    )
    return passed and result.get("passed") is True


def _validate_baseline_and_bridge_gates(
    root: Mapping[str, Any], issues: list[ValidationIssue]
) -> None:
    if "fair_baseline_gate" not in root:
        return
    gate = _mapping_or_issue(
        root.get("fair_baseline_gate"), "/fair_baseline_gate", issues
    )
    transport = _seed_results(root, "transport_results", issues)
    local = _seed_results(root, "matched_local_results", issues)
    baseline = _seed_results(root, "baseline_results", issues)
    if gate is None or transport is None or local is None or baseline is None:
        return
    seeds = list(transport)
    for seed, result_value in local.items():
        result_pointer = f"/matched_local_results/{seed}"
        result = _mapping_or_issue(result_value, result_pointer, issues)
        if result is None:
            continue
        initialization_pointer = json_pointer_join(result_pointer, "initialization")
        initialization = result.get("initialization")
        initialization_passed = _validate_initialization_evidence(
            initialization, initialization_pointer, issues
        )
        runtime_initial_hash = (
            _runtime_matcher_state_hash_from_evidence(initialization)
            if isinstance(initialization, Mapping)
            else None
        )
        initial_hash = result.get("initial_state_sha256")
        if not is_lowercase_sha256(initial_hash):
            issues.append(
                _issue(
                    json_pointer_join(result_pointer, "initial_state_sha256"),
                    "lowercase SHA-256",
                    initial_hash,
                )
            )
        if initialization_passed and runtime_initial_hash is not None:
            _derived_value(
                initial_hash,
                runtime_initial_hash,
                json_pointer_join(result_pointer, "initial_state_sha256"),
                issues,
            )
    assignment = gate.get("assignment_metrics", {})
    clean_reference = (
        assignment.get("clean", {})
        .get("hungarian", {})
        .get("hard_all_endpoint_assignment_accuracy")
    )
    challenge_reference = max(
        assignment.get("challenge", {})
        .get(name, {})
        .get("hard_all_endpoint_assignment_accuracy", -math.inf)
        for name in ("hungarian", "sinkhorn")
    )
    main_clean = {
        seed: transport[seed]["evaluations"]["clean"]["development"][
            "hard_all_endpoint_assignment_accuracy"
        ]
        for seed in seeds
    }
    main_challenge = {
        seed: transport[seed]["evaluations"]["challenge"]["development"][
            "hard_all_endpoint_assignment_accuracy"
        ]
        for seed in seeds
    }
    main_challenge_row = {
        seed: transport[seed]["evaluations"]["challenge"]["development"][
            "row_top1_accuracy"
        ]
        for seed in seeds
    }
    local_challenge = {
        seed: local[seed]["evaluations"]["challenge"]["development"][
            "row_top1_accuracy"
        ]
        for seed in seeds
    }
    for name, expected in (
        ("clean_hungarian_reference", clean_reference),
        ("challenge_best_fixed_reference", challenge_reference),
        ("main_clean_by_seed", main_clean),
        ("main_challenge_by_seed", main_challenge),
        ("main_challenge_row_top1_by_seed", main_challenge_row),
        ("matched_local_challenge_by_seed", local_challenge),
    ):
        _derived_value(
            gate.get(name),
            expected,
            json_pointer_join("/fair_baseline_gate", name),
            issues,
        )

    fixed = gate.get("fixed_seed_invariance_evidence", {})
    fixed_map = _mapping_or_issue(
        fixed, "/fair_baseline_gate/fixed_seed_invariance_evidence", issues
    )
    fixed_invariant = fixed_map is not None and bool(fixed_map)
    if fixed_map is not None:
        _closed_keys(
            fixed_map,
            frozenset(_R6_STRATA),
            "/fair_baseline_gate/fixed_seed_invariance_evidence",
            issues,
        )
        for stratum in _R6_STRATA:
            by_seed_pointer = (
                f"/fair_baseline_gate/fixed_seed_invariance_evidence/{stratum}"
            )
            by_seed = _mapping_or_issue(fixed_map.get(stratum), by_seed_pointer, issues)
            if by_seed is None:
                fixed_invariant = False
                continue
            _closed_keys(by_seed, frozenset(seeds), by_seed_pointer, issues)
            expected_fixed = {
                "hungarian": assignment[stratum]["hungarian"]["hard_plan_sha256"],
                "sinkhorn": assignment[stratum]["sinkhorn"]["soft_plan_sha256"],
                "contract": assignment[stratum]["contract_sha256"],
            }
            for seed in seeds:
                item_pointer = json_pointer_join(by_seed_pointer, seed)
                item = _mapping_or_issue(by_seed.get(seed), item_pointer, issues)
                if item is None:
                    fixed_invariant = False
                    continue
                _closed_keys(item, frozenset(expected_fixed), item_pointer, issues)
                for name, expected in expected_fixed.items():
                    _derived_value(
                        item.get(name),
                        expected,
                        json_pointer_join(item_pointer, name),
                        issues,
                    )
                    fixed_invariant = fixed_invariant and item.get(name) == expected
    _derived_value(
        gate.get("fixed_seed_invariance_map_sha256"),
        canonical_sha256(fixed),
        "/fair_baseline_gate/fixed_seed_invariance_map_sha256",
        issues,
    )
    plan_hashes = gate.get("plan_sha256", {})
    for stratum in ("clean", "challenge"):
        for name in ("hungarian", "sinkhorn"):
            expected_hash = assignment[stratum][name]["soft_plan_sha256"]
            _derived_value(
                plan_hashes.get(stratum, {}).get(name),
                expected_hash,
                f"/fair_baseline_gate/plan_sha256/{stratum}/{name}",
                issues,
            )

    readout_pass = True
    readout_shared = True
    method_keys_exact = True
    expected_method_order = list(_R6_EXACT64_METHOD_ORDER)
    for seed, seed_results in baseline.items():
        hashes: set[Any] = set()
        for stratum, stratum_results in seed_results.items():
            stratum_pointer = f"/baseline_results/{seed}/{stratum}"
            method_map = _mapping_or_issue(stratum_results, stratum_pointer, issues)
            if method_map is None:
                method_keys_exact = False
                continue
            method_keys_exact = (
                _closed_keys(
                    method_map,
                    frozenset(_R6_EXACT64_METHOD_ORDER),
                    stratum_pointer,
                    issues,
                )
                and method_keys_exact
            )
            for method in _R6_EXACT64_METHOD_ORDER:
                result = method_map.get(method)
                result_pointer = f"/baseline_results/{seed}/{stratum}/{method}"
                readout_pass = (
                    _scored_leaf_passes(result, result_pointer, issues) and readout_pass
                )
                if isinstance(result, Mapping):
                    hashes.add(result.get("common_oracle_readout_sha256"))
                else:
                    readout_shared = False
        readout_shared = readout_shared and len(hashes) == 1
    expected_checks = {
        "clean_every_seed_within_0_10_hungarian": all(
            value >= clean_reference - 0.10 for value in main_clean.values()
        ),
        "clean_aggregate_within_0_05_hungarian": recompute_average(
            list(main_clean.values())
        )
        >= clean_reference - 0.05,
        "challenge_every_seed_improves_best_fixed_by_0_20": all(
            value >= challenge_reference + 0.20 for value in main_challenge.values()
        ),
        "matched_local_has_no_column_competition": all(
            local[seed].get("column_normalization_used") is False
            and local[seed].get("column_competition_used") is False
            and local[seed].get("calls_global_solver") is False
            for seed in seeds
        ),
        "challenge_every_seed_improves_matched_local_row_top1_by_0_20": all(
            main_challenge_row[seed] >= local_challenge[seed] + 0.20 for seed in seeds
        ),
        "common_oracle_readout_shared_per_seed": readout_shared,
        "baseline_readouts_exact64_and_frozen": readout_pass,
        "baseline_plans_seed_invariant_observed": fixed_invariant,
        "matched_local_parameters_optimizer_and_updates_equal": all(
            local[seed].get("registered_gradient_steps")
            == transport[seed].get("registered_gradient_steps")
            and local[seed].get("optimizer_parameter_names")
            == transport[seed].get("optimizer_parameter_names")
            for seed in seeds
        ),
    }
    _derived_value(
        gate.get("exact64_method_order"),
        expected_method_order,
        "/fair_baseline_gate/exact64_method_order",
        issues,
    )
    if not method_keys_exact:
        issues.append(
            _issue(
                "/baseline_results",
                "each stratum has the exact registered method key set",
                baseline,
            )
        )
    _gate_derivatives(
        gate, "/fair_baseline_gate", expected_checks, "FAIL_FAIR_BASELINE", issues
    )


def _validate_bridge_gate(
    root: Mapping[str, Any], issues: list[ValidationIssue]
) -> None:
    if "exact64_bridge_gate" not in root:
        return
    bridge = root["exact64_bridge_gate"]
    oracle = _seed_results(root, "common_oracle_readout_results", issues) or {}
    mediator = _seed_results(root, "mediator_results", issues) or {}
    baseline = _seed_results(root, "baseline_results", issues) or {}
    oracle_exact = bool(oracle) and all(
        isinstance(value, Mapping)
        and _validate_exact64_audit(
            value, f"/common_oracle_readout_results/{seed}", issues
        )
        for seed, value in oracle.items()
    )
    mediator_exact = bool(mediator) and all(
        isinstance(value, Mapping)
        and _validate_exact64_audit(value, f"/mediator_results/{seed}", issues)
        for seed, value in mediator.items()
    )
    readout_pass = bool(baseline)
    method_order_exact = bool(baseline)
    readout_shared = bool(baseline)
    expected_method_order = list(_R6_EXACT64_METHOD_ORDER)
    fair_gate = root.get("fair_baseline_gate")
    explicit_method_order = (
        fair_gate.get("exact64_method_order")
        if isinstance(fair_gate, Mapping)
        else None
    )
    method_order_exact = explicit_method_order == expected_method_order
    _derived_value(
        explicit_method_order,
        expected_method_order,
        "/fair_baseline_gate/exact64_method_order",
        issues,
    )
    for seed, seed_results in baseline.items():
        hashes: set[Any] = set()
        for stratum, stratum_results in seed_results.items():
            stratum_pointer = f"/baseline_results/{seed}/{stratum}"
            method_map = _mapping_or_issue(stratum_results, stratum_pointer, issues)
            if method_map is None:
                method_order_exact = False
                continue
            method_order_exact = (
                _closed_keys(
                    method_map,
                    frozenset(_R6_EXACT64_METHOD_ORDER),
                    stratum_pointer,
                    issues,
                )
                and method_order_exact
            )
            for method in _R6_EXACT64_METHOD_ORDER:
                result = method_map.get(method)
                readout_pass = (
                    _scored_leaf_passes(
                        result,
                        f"/baseline_results/{seed}/{stratum}/{method}",
                        issues,
                    )
                    and readout_pass
                )
                if isinstance(result, Mapping):
                    hashes.add(result.get("common_oracle_readout_sha256"))
                else:
                    readout_shared = False
        readout_shared = readout_shared and len(hashes) == 1
    expected_checks = {
        "oracle_readout_exact64": oracle_exact,
        "mediator_exact64": mediator_exact,
        "baseline_exact64": readout_pass,
        "baseline_method_order_exact": method_order_exact,
        "common_oracle_readout_shared": readout_shared,
        "no_formal_test": root.get("formal_test_used") is False,
    }
    bridge_map = bridge if isinstance(bridge, Mapping) else {}
    counterfactual = bridge_map.get("r6_full_chain_counterfactual")
    counterfactual_pass = _validate_counterfactual_report(
        counterfactual,
        "/exact64_bridge_gate/r6_full_chain_counterfactual",
        issues,
    )
    expected_checks["r6_counterfactual_repeated_at_exact64"] = counterfactual_pass
    expected_checks["r6_counterfactual_hash_exact"] = counterfactual_pass
    _gate_derivatives(
        bridge, "/exact64_bridge_gate", expected_checks, "FAIL_EXACT64_BRIDGE", issues
    )


def _validate_gradient_audit_evidence(
    value: Any, pointer: str, issues: list[ValidationIssue], *, applicable: bool
) -> bool:
    audit = _mapping_or_issue(value, pointer, issues)
    expected_keys = frozenset(
        {
            "applicability",
            "na_reason",
            "registered_parameter_names",
            "registered_parameter_names_exact",
            "loss",
            "finite_loss",
            "gradients",
            "finite_gradients",
            "nonzero_expected_gradient_each_trainable_parameter",
            "forbidden_input_or_query_gradient",
            "optimizer_owner_exact",
        }
    )
    if audit is None:
        return False
    _closed_keys(audit, expected_keys, pointer, issues)
    gradients = _mapping_or_issue(
        audit.get("gradients"), json_pointer_join(pointer, "gradients"), issues
    )
    if gradients is None:
        return False
    if applicable:
        names = [
            "view_weight_logits[0]",
            "view_weight_logits[1]",
            "residual_coefficient",
            "prior_null_utility",
            "current_null_utility",
        ]
        _derived_value(
            audit.get("applicability"),
            "APPLICABLE_REGISTERED_STEP0_MATCHER",
            json_pointer_join(pointer, "applicability"),
            issues,
        )
        _derived_value(
            audit.get("na_reason"), "", json_pointer_join(pointer, "na_reason"), issues
        )
        _derived_value(
            audit.get("registered_parameter_names"),
            names,
            json_pointer_join(pointer, "registered_parameter_names"),
            issues,
        )
        _closed_keys(
            gradients,
            frozenset(names),
            json_pointer_join(pointer, "gradients"),
            issues,
        )
    else:
        names = []
        _derived_value(
            audit.get("applicability"),
            "NOT_APPLICABLE_ANALYTIC_UTILITY_FIXTURE",
            json_pointer_join(pointer, "applicability"),
            issues,
        )
        _derived_value(
            audit.get("registered_parameter_names"),
            [],
            json_pointer_join(pointer, "registered_parameter_names"),
            issues,
        )
        _closed_keys(
            gradients,
            frozenset(),
            json_pointer_join(pointer, "gradients"),
            issues,
        )
    finite: list[bool] = []
    nonzero: list[bool] = []
    for name in names:
        item_pointer = json_pointer_join(json_pointer_join(pointer, "gradients"), name)
        item = _mapping_or_issue(gradients.get(name), item_pointer, issues)
        if item is None:
            continue
        _closed_keys(
            item, frozenset({"finite", "nonzero", "value"}), item_pointer, issues
        )
        scalar = item.get("value")
        is_finite = (
            isinstance(scalar, (int, float))
            and not isinstance(scalar, bool)
            and math.isfinite(float(scalar))
        )
        is_nonzero = is_finite and float(scalar) != 0.0
        _derived_value(
            item.get("finite"),
            is_finite,
            json_pointer_join(item_pointer, "finite"),
            issues,
        )
        _derived_value(
            item.get("nonzero"),
            is_nonzero,
            json_pointer_join(item_pointer, "nonzero"),
            issues,
        )
        finite.append(is_finite)
        nonzero.append(is_nonzero)
    loss = audit.get("loss")
    finite_loss = (
        isinstance(loss, (int, float))
        and not isinstance(loss, bool)
        and math.isfinite(float(loss))
    )
    derived_finite = all(finite) if applicable else True
    derived_nonzero = all(nonzero) if applicable else True
    for field, expected in (
        ("registered_parameter_names_exact", True),
        ("finite_loss", finite_loss),
        ("finite_gradients", derived_finite),
        ("nonzero_expected_gradient_each_trainable_parameter", derived_nonzero),
        ("forbidden_input_or_query_gradient", True),
        ("optimizer_owner_exact", True),
    ):
        _derived_value(
            audit.get(field), expected, json_pointer_join(pointer, field), issues
        )
    return finite_loss and derived_finite and derived_nonzero


def _validate_structural_report(
    value: Any, pointer: str, issues: list[ValidationIssue]
) -> bool:
    report = _mapping_or_issue(value, pointer, issues)
    top_keys = frozenset(
        {
            "schema_version",
            "passed",
            "required_case_ids",
            "required_per_case_evidence",
            "microcases",
            "ordered_microcase_projection_sha256",
            "registered_gradient_audit",
            "audit_sha256",
        }
    )
    if report is None:
        return False
    _closed_keys(report, top_keys, pointer, issues)
    _derived_value(
        report.get("schema_version"),
        _R6_STRUCTURAL_SCHEMA_VERSION,
        json_pointer_join(pointer, "schema_version"),
        issues,
    )
    registered_case_ids = list(_R6_STRUCTURAL_CASE_IDS)
    required_case_ids = report.get("required_case_ids")
    required_case_ids_exact = required_case_ids == registered_case_ids
    _derived_value(
        required_case_ids,
        registered_case_ids,
        json_pointer_join(pointer, "required_case_ids"),
        issues,
    )
    _derived_value(
        report.get("required_per_case_evidence"),
        list(_R6_STRUCTURAL_EVIDENCE_KEYS),
        json_pointer_join(pointer, "required_per_case_evidence"),
        issues,
    )
    microcases = _mapping_or_issue(
        report.get("microcases"), json_pointer_join(pointer, "microcases"), issues
    )
    all_cases_pass = microcases is not None and required_case_ids_exact
    if microcases is not None:
        registered_case_id_set = frozenset(_R6_STRUCTURAL_CASE_IDS)
        microcase_keys_exact = frozenset(microcases) == registered_case_id_set
        _closed_keys(
            microcases,
            registered_case_id_set,
            json_pointer_join(pointer, "microcases"),
            issues,
        )
        all_cases_pass = all_cases_pass and microcase_keys_exact
        projection_exact = False
        if required_case_ids_exact and all(
            case_id in microcases for case_id in required_case_ids
        ):
            ordered_projection = [
                {"case_id": case_id, "evidence": microcases[case_id]}
                for case_id in required_case_ids
            ]
            expected_projection_sha256 = canonical_sha256(ordered_projection)
            projection_exact = (
                report.get("ordered_microcase_projection_sha256")
                == expected_projection_sha256
            )
            _derived_value(
                report.get("ordered_microcase_projection_sha256"),
                expected_projection_sha256,
                json_pointer_join(pointer, "ordered_microcase_projection_sha256"),
                issues,
            )
        all_cases_pass = all_cases_pass and projection_exact
        plan_keys = frozenset(
            {
                "prior_count",
                "current_count",
                "prior_valid",
                "current_valid",
                "prior_anatomy",
                "current_anatomy",
                "edge_utility",
                "prior_null_utility",
                "current_null_utility",
                "compatibility",
                "soft_transport",
                "soft_internal_transport",
                "hard_transport",
                "expected_hard_transport",
                "hard_plan_matches_expected",
                "tie_policy",
            }
        )
        completion_keys = frozenset(
            {
                "valid_prior_count",
                "valid_current_count",
                "persistent_count",
                "death_count",
                "birth_count",
                "hard_covers_every_prior_once",
                "hard_covers_every_current_once",
                "persistent_death_birth_partition_exact",
                "no_duplicate_real_current",
            }
        )
        # JSON object member order is not semantic.  Once the registered list
        # is verified, use it rather than the mapping's insertion order.
        case_ids = required_case_ids if required_case_ids_exact else registered_case_ids
        for case_id in case_ids:
            case_pointer = json_pointer_join(
                json_pointer_join(pointer, "microcases"), case_id
            )
            case = _mapping_or_issue(microcases.get(case_id), case_pointer, issues)
            if case is None:
                all_cases_pass = False
                continue
            _closed_keys(
                case, frozenset(_R6_STRUCTURAL_EVIDENCE_KEYS), case_pointer, issues
            )
            plan_pointer = json_pointer_join(case_pointer, "expected_plan_exact")
            plan = _mapping_or_issue(
                case.get("expected_plan_exact"), plan_pointer, issues
            )
            counts = _mapping_or_issue(
                case.get("completion_counts"),
                json_pointer_join(case_pointer, "completion_counts"),
                issues,
            )
            if plan is None or counts is None:
                all_cases_pass = False
                continue
            _closed_keys(plan, plan_keys, plan_pointer, issues)
            _closed_keys(
                counts,
                completion_keys,
                json_pointer_join(case_pointer, "completion_counts"),
                issues,
            )
            snapshot = {
                key: plan.get(key)
                for key in plan_keys
                if key
                not in {
                    "soft_transport",
                    "soft_internal_transport",
                    "hard_transport",
                    "expected_hard_transport",
                    "hard_plan_matches_expected",
                    "tie_policy",
                }
            }
            utility = {
                key: plan.get(key)
                for key in (
                    "edge_utility",
                    "prior_null_utility",
                    "current_null_utility",
                    "compatibility",
                )
            }
            expected_hashes = {
                "input_sha256_before": canonical_sha256(snapshot),
                "input_sha256_after": canonical_sha256(snapshot),
                "utility_sha256": canonical_sha256(utility),
                "soft_plan_sha256": canonical_sha256(plan.get("soft_transport")),
                "hard_plan_sha256": canonical_sha256(plan.get("hard_transport")),
            }
            for field, expected in expected_hashes.items():
                _derived_value(
                    case.get(field),
                    expected,
                    json_pointer_join(case_pointer, field),
                    issues,
                )
            hard_equal = plan.get("hard_transport") == plan.get(
                "expected_hard_transport"
            )
            _derived_value(
                plan.get("hard_plan_matches_expected"),
                hard_equal,
                json_pointer_join(plan_pointer, "hard_plan_matches_expected"),
                issues,
            )
            _derived_value(
                plan.get("tie_policy"),
                "lexicographically-smallest semantic hard transport",
                json_pointer_join(plan_pointer, "tie_policy"),
                issues,
            )
            prior_count = plan.get("prior_count")
            current_count = plan.get("current_count")
            hard = plan.get("hard_transport")
            if (
                isinstance(prior_count, int)
                and not isinstance(prior_count, bool)
                and isinstance(current_count, int)
                and not isinstance(current_count, bool)
                and isinstance(hard, list)
                and len(hard) == prior_count + 1
                and all(
                    isinstance(row, list) and len(row) == current_count + 1
                    for row in hard
                )
            ):
                hard_binary = all(
                    type(item) in (int, float) and float(item) in (0.0, 1.0)
                    for row in hard
                    for item in row
                )
                if not hard_binary:
                    issues.append(
                        _issue(
                            json_pointer_join(plan_pointer, "hard_transport"),
                            "binary semantic hard transport",
                            hard,
                        )
                    )
                persistent = sum(
                    float(hard[row][column]) != 0.0
                    for row in range(prior_count)
                    for column in range(current_count)
                )
                death = sum(
                    float(hard[row][current_count]) != 0.0 for row in range(prior_count)
                )
                birth = sum(
                    float(hard[prior_count][column]) != 0.0
                    for column in range(current_count)
                )
                expected_counts = {
                    "valid_prior_count": prior_count,
                    "valid_current_count": current_count,
                    "persistent_count": persistent,
                    "death_count": death,
                    "birth_count": birth,
                    "hard_covers_every_prior_once": all(
                        math.isclose(sum(float(item) for item in hard[row]), 1.0)
                        for row in range(prior_count)
                    ),
                    "hard_covers_every_current_once": all(
                        math.isclose(
                            sum(
                                float(hard[row][column])
                                for row in range(prior_count + 1)
                            ),
                            1.0,
                        )
                        for column in range(current_count)
                    ),
                    "persistent_death_birth_partition_exact": persistent + death
                    == prior_count
                    and persistent + birth == current_count,
                    "no_duplicate_real_current": all(
                        sum(
                            float(hard[row][column]) != 0.0
                            for row in range(prior_count)
                        )
                        <= 1
                        for column in range(current_count)
                    ),
                }
                _derived_value(
                    counts,
                    expected_counts,
                    json_pointer_join(case_pointer, "completion_counts"),
                    issues,
                )
                all_cases_pass = (
                    all_cases_pass
                    and hard_binary
                    and hard_equal
                    and all(
                        expected_counts[name]
                        for name in (
                            "hard_covers_every_prior_once",
                            "hard_covers_every_current_once",
                            "persistent_death_birth_partition_exact",
                            "no_duplicate_real_current",
                        )
                    )
                )
            else:
                issues.append(
                    _issue(plan_pointer, "well-shaped semantic hard plan", hard)
                )
                all_cases_pass = False
            all_cases_pass = (
                _validate_gradient_audit_evidence(
                    case.get("gradient_audit"),
                    json_pointer_join(case_pointer, "gradient_audit"),
                    issues,
                    applicable=False,
                )
                and all_cases_pass
            )
    registered_pass = _validate_gradient_audit_evidence(
        report.get("registered_gradient_audit"),
        json_pointer_join(pointer, "registered_gradient_audit"),
        issues,
        applicable=True,
    )
    hash_payload = {key: item for key, item in report.items() if key != "audit_sha256"}
    _derived_value(
        report.get("audit_sha256"),
        canonical_sha256(hash_payload),
        json_pointer_join(pointer, "audit_sha256"),
        issues,
    )
    passed = all_cases_pass and registered_pass
    _derived_value(
        report.get("passed"), passed, json_pointer_join(pointer, "passed"), issues
    )
    return passed


def _validate_comparison_evidence(
    value: Any, pointer: str, issues: list[ValidationIssue]
) -> tuple[bool, bool]:
    comparison = _mapping_or_issue(value, pointer, issues)
    keys = frozenset(
        {
            "fields_exact",
            "all_exact",
            "all_close",
            "exact_by_field",
            "close_by_field",
            "max_abs_error_by_field",
            "value_sha256_by_field",
        }
    )
    if comparison is None:
        return False, False
    _closed_keys(comparison, keys, pointer, issues)
    maps = []
    for name in (
        "exact_by_field",
        "close_by_field",
        "max_abs_error_by_field",
        "value_sha256_by_field",
    ):
        maps.append(
            _mapping_or_issue(
                comparison.get(name), json_pointer_join(pointer, name), issues
            )
        )
    same_fields = all(item is not None for item in maps) and all(
        set(item) == set(maps[0]) for item in maps[1:]
    )
    fields_exact = comparison.get("fields_exact") is True and same_fields
    exact = fields_exact and all(item is True for item in (maps[0] or {}).values())
    close = fields_exact and all(item is True for item in (maps[1] or {}).values())
    _derived_value(
        comparison.get("all_exact"),
        exact,
        json_pointer_join(pointer, "all_exact"),
        issues,
    )
    _derived_value(
        comparison.get("all_close"),
        close,
        json_pointer_join(pointer, "all_close"),
        issues,
    )
    return exact, close


def _validate_counterfactual_report_deep_experimental(
    value: Any, pointer: str, issues: list[ValidationIssue]
) -> bool:
    report = _mapping_or_issue(value, pointer, issues)
    top_keys = frozenset(
        {
            "schema_version",
            "status",
            "passed",
            "checks",
            "forward_boundary",
            "hidden_id_relabel",
            "endpoint_permutation",
            "query_value_substitution",
            "forbidden_state_channel_substitution",
            "b4a_deranged_vs_b4b_oracle",
            "transformed_storage_audit",
            "source_tensor_audit",
            "reference_trace",
            "report_sha256",
        }
    )
    if report is None:
        return False
    _closed_keys(report, top_keys, pointer, issues)
    _derived_value(
        report.get("schema_version"),
        _R6_COUNTERFACTUAL_SCHEMA_VERSION,
        json_pointer_join(pointer, "schema_version"),
        issues,
    )
    expected_hash = canonical_sha256(
        {key: item for key, item in report.items() if key != "report_sha256"}
    )
    _derived_value(
        report.get("report_sha256"),
        expected_hash,
        json_pointer_join(pointer, "report_sha256"),
        issues,
    )
    forward = _mapping_or_issue(
        report.get("forward_boundary"),
        json_pointer_join(pointer, "forward_boundary"),
        issues,
    )
    forward_pass = False
    if forward is not None:
        boundary_keys = frozenset(
            {
                "hidden_oracle_passed_to_matcher",
                "hidden_oracle_passed_to_tokenizer",
                "hidden_oracle_passed_to_projector",
                "hidden_oracle_passed_to_adapter",
                "batch_aware_hooks",
            }
        )
        _closed_keys(
            forward,
            boundary_keys,
            json_pointer_join(pointer, "forward_boundary"),
            issues,
        )
        forward_pass = all(
            forward.get(name) is False
            for name in boundary_keys
            if name != "batch_aware_hooks"
        ) and forward.get("batch_aware_hooks") == ["matching_regions", "token_regions"]
        if not forward_pass:
            issues.append(
                _issue(
                    json_pointer_join(pointer, "forward_boundary"),
                    "frozen no-hidden-oracle forward boundary",
                    forward,
                )
            )
    hidden = _mapping_or_issue(
        report.get("hidden_id_relabel"),
        json_pointer_join(pointer, "hidden_id_relabel"),
        issues,
    )
    hidden_pass = False
    if hidden is not None:
        _closed_keys(
            hidden,
            frozenset({"contract", "full_chain"}),
            json_pointer_join(pointer, "hidden_id_relabel"),
            issues,
        )
        contract = _mapping_or_issue(
            hidden.get("contract"),
            json_pointer_join(
                json_pointer_join(pointer, "hidden_id_relabel"), "contract"
            ),
            issues,
        )
        chain = _mapping_or_issue(
            hidden.get("full_chain"),
            json_pointer_join(
                json_pointer_join(pointer, "hidden_id_relabel"), "full_chain"
            ),
            issues,
        )
        contract_pass = False
        if contract is not None:
            contract_pointer = json_pointer_join(
                json_pointer_join(pointer, "hidden_id_relabel"), "contract"
            )
            _closed_keys(
                contract,
                frozenset(
                    {
                        "passed",
                        "checks",
                        "original_equality_sha256",
                        "relabeled_equality_sha256",
                        "original_ids_sha256",
                        "relabeled_ids_sha256",
                    }
                ),
                contract_pointer,
                issues,
            )
            expected_contract_checks = {
                "counterfactual_nonvacuous": contract.get("original_ids_sha256")
                != contract.get("relabeled_ids_sha256"),
                "gold_equality_relation_exact": contract.get("original_equality_sha256")
                == contract.get("relabeled_equality_sha256"),
                "oracle_plan_exact": contract.get("checks", {}).get("oracle_plan_exact")
                is True,
                "original_plan_matches_gold_equality": contract.get("checks", {}).get(
                    "original_plan_matches_gold_equality"
                )
                is True,
                "relabeled_plan_matches_gold_equality": contract.get("checks", {}).get(
                    "relabeled_plan_matches_gold_equality"
                )
                is True,
            }
            contract_checks = _mapping_or_issue(
                contract.get("checks"),
                json_pointer_join(contract_pointer, "checks"),
                issues,
            )
            if contract_checks is not None:
                _closed_keys(
                    contract_checks,
                    frozenset(expected_contract_checks),
                    json_pointer_join(contract_pointer, "checks"),
                    issues,
                )
                for name, expected in expected_contract_checks.items():
                    _derived_value(
                        contract_checks.get(name),
                        expected,
                        json_pointer_join(
                            json_pointer_join(contract_pointer, "checks"), name
                        ),
                        issues,
                    )
            contract_pass = all(expected_contract_checks.values())
            _derived_value(
                contract.get("passed"),
                contract_pass,
                json_pointer_join(contract_pointer, "passed"),
                issues,
            )
        chain_pass = isinstance(chain, Mapping) and chain.get("passed") is True
        if chain is not None:
            chain_pointer = json_pointer_join(
                json_pointer_join(pointer, "hidden_id_relabel"), "full_chain"
            )
            _closed_keys(
                chain,
                frozenset({"passed", "equality_policy", "checks", "comparisons"}),
                chain_pointer,
                issues,
            )
            comparisons = _mapping_or_issue(
                chain.get("comparisons"),
                json_pointer_join(
                    json_pointer_join(
                        json_pointer_join(pointer, "hidden_id_relabel"), "full_chain"
                    ),
                    "comparisons",
                ),
                issues,
            )
            if comparisons is not None:
                _closed_keys(
                    comparisons,
                    frozenset(_R6_CHAIN_STAGE_NAMES),
                    json_pointer_join(
                        json_pointer_join(
                            json_pointer_join(pointer, "hidden_id_relabel"),
                            "full_chain",
                        ),
                        "comparisons",
                    ),
                    issues,
                )
                exact_by_stage = {
                    stage: _validate_comparison_evidence(
                        comparisons.get(stage),
                        json_pointer_join(
                            json_pointer_join(
                                json_pointer_join(
                                    json_pointer_join(pointer, "hidden_id_relabel"),
                                    "full_chain",
                                ),
                                "comparisons",
                            ),
                            stage,
                        ),
                        issues,
                    )[0]
                    for stage in _R6_CHAIN_STAGE_NAMES
                }
                _derived_value(
                    chain.get("checks"),
                    exact_by_stage,
                    json_pointer_join(
                        json_pointer_join(
                            json_pointer_join(pointer, "hidden_id_relabel"),
                            "full_chain",
                        ),
                        "checks",
                    ),
                    issues,
                )
                chain_pass = all(exact_by_stage.values())
                _derived_value(
                    chain.get("passed"),
                    chain_pass,
                    json_pointer_join(
                        json_pointer_join(
                            json_pointer_join(pointer, "hidden_id_relabel"),
                            "full_chain",
                        ),
                        "passed",
                    ),
                    issues,
                )
        hidden_pass = contract_pass and chain_pass
    permutation_pointer = json_pointer_join(pointer, "endpoint_permutation")
    permutation = _mapping_or_issue(
        report.get("endpoint_permutation"), permutation_pointer, issues
    )
    permutation_pass = False
    if permutation is not None:
        _closed_keys(
            permutation,
            frozenset(
                {
                    "passed",
                    "equality_policy",
                    "checks",
                    "comparisons",
                    "prior_permutation_sha256",
                    "current_permutation_sha256",
                    "prior_permutation",
                    "current_permutation",
                }
            ),
            permutation_pointer,
            issues,
        )
        comparisons = _mapping_or_issue(
            permutation.get("comparisons"),
            json_pointer_join(permutation_pointer, "comparisons"),
            issues,
        )
        close_by_stage: dict[str, bool] = {}
        if comparisons is not None:
            _closed_keys(
                comparisons,
                frozenset(_R6_CHAIN_STAGE_NAMES),
                json_pointer_join(permutation_pointer, "comparisons"),
                issues,
            )
            close_by_stage = {
                stage: _validate_comparison_evidence(
                    comparisons.get(stage),
                    json_pointer_join(
                        json_pointer_join(permutation_pointer, "comparisons"), stage
                    ),
                    issues,
                )[1]
                for stage in _R6_CHAIN_STAGE_NAMES
            }
        prior_permutation = permutation.get("prior_permutation")
        current_permutation = permutation.get("current_permutation")
        expected_permutation_checks = {
            **close_by_stage,
            "prior_permutation_nonidentity": isinstance(prior_permutation, list)
            and prior_permutation != list(range(len(prior_permutation))),
            "current_permutation_nonidentity": isinstance(current_permutation, list)
            and current_permutation != list(range(len(current_permutation))),
        }
        permutation_checks = _mapping_or_issue(
            permutation.get("checks"),
            json_pointer_join(permutation_pointer, "checks"),
            issues,
        )
        if permutation_checks is not None:
            _closed_keys(
                permutation_checks,
                frozenset(expected_permutation_checks),
                json_pointer_join(permutation_pointer, "checks"),
                issues,
            )
            for name, expected in expected_permutation_checks.items():
                _derived_value(
                    permutation_checks.get(name),
                    expected,
                    json_pointer_join(
                        json_pointer_join(permutation_pointer, "checks"), name
                    ),
                    issues,
                )
        permutation_pass = bool(expected_permutation_checks) and all(
            expected_permutation_checks.values()
        )
        _derived_value(
            permutation.get("passed"),
            permutation_pass,
            json_pointer_join(permutation_pointer, "passed"),
            issues,
        )
    substitutions: dict[str, bool] = {}
    for name in ("query_value_substitution", "forbidden_state_channel_substitution"):
        audit_pointer = json_pointer_join(pointer, name)
        audit = _mapping_or_issue(report.get(name), audit_pointer, issues)
        audit_pass = False
        if audit is not None:
            _closed_keys(
                audit,
                frozenset({"passed", "checks", "changed_input_paths", "comparisons"}),
                audit_pointer,
                issues,
            )
            comparisons = _mapping_or_issue(
                audit.get("comparisons"),
                json_pointer_join(audit_pointer, "comparisons"),
                issues,
            )
            if comparisons is not None:
                _closed_keys(
                    comparisons,
                    frozenset(_R6_CHAIN_STAGE_NAMES),
                    json_pointer_join(audit_pointer, "comparisons"),
                    issues,
                )
                exact = {
                    stage: _validate_comparison_evidence(
                        comparisons.get(stage),
                        json_pointer_join(
                            json_pointer_join(audit_pointer, "comparisons"), stage
                        ),
                        issues,
                    )[0]
                    for stage in _R6_CHAIN_STAGE_NAMES
                }
                recomputed = {
                    "counterfactual_nonvacuous": bool(audit.get("changed_input_paths")),
                    "matching_and_transport_exact": all(
                        exact[stage]
                        for stage in (
                            "matching_regions",
                            "utilities",
                            "soft_plan",
                            "plan",
                        )
                    ),
                    "full_chain_covered": set(comparisons)
                    == set(_R6_CHAIN_STAGE_NAMES),
                    "downstream_change_observed": any(
                        not exact[stage]
                        for stage in _R6_CHAIN_STAGE_NAMES
                        if stage
                        not in {"matching_regions", "utilities", "soft_plan", "plan"}
                    ),
                }
                _derived_value(
                    audit.get("checks"),
                    recomputed,
                    json_pointer_join(audit_pointer, "checks"),
                    issues,
                )
                audit_pass = all(recomputed.values())
                _derived_value(
                    audit.get("passed"),
                    audit_pass,
                    json_pointer_join(audit_pointer, "passed"),
                    issues,
                )
        substitutions[name] = audit_pass
    b4_pointer = json_pointer_join(pointer, "b4a_deranged_vs_b4b_oracle")
    b4 = _mapping_or_issue(report.get("b4a_deranged_vs_b4b_oracle"), b4_pointer, issues)
    b4_pass = False
    if b4 is not None:
        b4_keys = frozenset(
            {
                "passed",
                "checks",
                "allowlist",
                "diff_entries",
                "unexpected_paths",
                "observed_allowlist_categories",
                "shared_comparisons",
                "b4a_trace",
                "b4b_trace",
                "b4a_assignment_sha256",
                "b4b_assignment_sha256",
                "projector_state_sha256",
                "adapter_state_sha256",
            }
        )
        _closed_keys(b4, b4_keys, b4_pointer, issues)
        projector_states = _mapping_or_issue(
            b4.get("projector_state_sha256"),
            json_pointer_join(b4_pointer, "projector_state_sha256"),
            issues,
        )
        adapter_states = _mapping_or_issue(
            b4.get("adapter_state_sha256"),
            json_pointer_join(b4_pointer, "adapter_state_sha256"),
            issues,
        )
        states_exact = True
        for states, name in (
            (projector_states, "projector_state_sha256"),
            (adapter_states, "adapter_state_sha256"),
        ):
            if states is None:
                states_exact = False
                continue
            _closed_keys(
                states,
                frozenset({"before", "between", "after"}),
                json_pointer_join(b4_pointer, name),
                issues,
            )
            valid = (
                all(is_lowercase_sha256(item) for item in states.values())
                and len(set(states.values())) == 1
            )
            states_exact = states_exact and valid
        b4_checks = _mapping_or_issue(
            b4.get("checks"), json_pointer_join(b4_pointer, "checks"), issues
        )
        if b4_checks is not None:
            expected_b4_check_keys = frozenset(
                {
                    "b4a_plan_nonidentity",
                    "shared_input_utility_chain_exact",
                    "projector_state_bitwise_exact",
                    "adapter_state_bitwise_exact",
                    "recursive_diff_nonempty",
                    "all_non_allowlisted_paths_exact",
                    "scores_and_predictions_covered",
                }
            )
            _closed_keys(
                b4_checks,
                expected_b4_check_keys,
                json_pointer_join(b4_pointer, "checks"),
                issues,
            )
            _derived_value(
                b4_checks.get("projector_state_bitwise_exact"),
                states_exact,
                json_pointer_join(
                    json_pointer_join(b4_pointer, "checks"),
                    "projector_state_bitwise_exact",
                ),
                issues,
            )
            _derived_value(
                b4_checks.get("adapter_state_bitwise_exact"),
                states_exact,
                json_pointer_join(
                    json_pointer_join(b4_pointer, "checks"),
                    "adapter_state_bitwise_exact",
                ),
                issues,
            )
            b4_pass = states_exact and all(item is True for item in b4_checks.values())
        _derived_value(
            b4.get("passed"), b4_pass, json_pointer_join(b4_pointer, "passed"), issues
        )
    storage_pointer = json_pointer_join(pointer, "transformed_storage_audit")
    storage = _mapping_or_issue(
        report.get("transformed_storage_audit"), storage_pointer, issues
    )
    storage_pass = storage is not None
    storage_names = frozenset(
        {
            "hidden_id_relabel",
            "endpoint_permutation",
            "query_value_substitution",
            "forbidden_state_channel_substitution",
        }
    )
    if storage is not None:
        _closed_keys(storage, storage_names, storage_pointer, issues)
        for name in storage_names:
            audit_pointer = json_pointer_join(storage_pointer, name)
            audit = _mapping_or_issue(storage.get(name), audit_pointer, issues)
            if audit is None:
                storage_pass = False
                continue
            _closed_keys(
                audit,
                frozenset(
                    {
                        "passed",
                        "checks",
                        "overlapping_paths",
                        "source_tensor_count",
                        "transformed_tensor_count",
                    }
                ),
                audit_pointer,
                issues,
            )
            expected_storage_checks = {
                "same_tensor_path_set": audit.get("source_tensor_count")
                == audit.get("transformed_tensor_count"),
                "no_source_storage_alias": not audit.get("overlapping_paths"),
            }
            audit_checks = _mapping_or_issue(
                audit.get("checks"), json_pointer_join(audit_pointer, "checks"), issues
            )
            if audit_checks is not None:
                _closed_keys(
                    audit_checks,
                    frozenset(expected_storage_checks),
                    json_pointer_join(audit_pointer, "checks"),
                    issues,
                )
                for check_name, expected in expected_storage_checks.items():
                    _derived_value(
                        audit_checks.get(check_name),
                        expected,
                        json_pointer_join(
                            json_pointer_join(audit_pointer, "checks"), check_name
                        ),
                        issues,
                    )
            audit_pass = all(expected_storage_checks.values())
            _derived_value(
                audit.get("passed"),
                audit_pass,
                json_pointer_join(audit_pointer, "passed"),
                issues,
            )
            storage_pass = storage_pass and audit_pass
    source_pointer = json_pointer_join(pointer, "source_tensor_audit")
    source = _mapping_or_issue(
        report.get("source_tensor_audit"), source_pointer, issues
    )
    source_pass = False
    if source is not None:
        _closed_keys(
            source,
            frozenset({"passed", "checks", "before", "after"}),
            source_pointer,
            issues,
        )
        before = _mapping_or_issue(
            source.get("before"), json_pointer_join(source_pointer, "before"), issues
        )
        after = _mapping_or_issue(
            source.get("after"), json_pointer_join(source_pointer, "after"), issues
        )
        expected_source_checks = {
            "value_dtype_shape_stride_pointer_exact": before is not None
            and before == after,
            "alias_groups_exact": before is not None
            and after is not None
            and before.get("alias_groups") == after.get("alias_groups"),
            "snapshot_hash_exact": before is not None
            and after is not None
            and before.get("snapshot_sha256") == after.get("snapshot_sha256"),
        }
        source_checks = _mapping_or_issue(
            source.get("checks"), json_pointer_join(source_pointer, "checks"), issues
        )
        if source_checks is not None:
            _closed_keys(
                source_checks,
                frozenset(expected_source_checks),
                json_pointer_join(source_pointer, "checks"),
                issues,
            )
            for name, expected in expected_source_checks.items():
                _derived_value(
                    source_checks.get(name),
                    expected,
                    json_pointer_join(
                        json_pointer_join(source_pointer, "checks"), name
                    ),
                    issues,
                )
        source_pass = all(expected_source_checks.values())
        _derived_value(
            source.get("passed"),
            source_pass,
            json_pointer_join(source_pointer, "passed"),
            issues,
        )
    reference = _mapping_or_issue(
        report.get("reference_trace"),
        json_pointer_join(pointer, "reference_trace"),
        issues,
    )
    reference_pass = reference is not None and set(reference) == set(
        _R6_CHAIN_STAGE_NAMES
    )
    if reference is not None:
        for stage in _R6_CHAIN_STAGE_NAMES:
            stage_pointer = json_pointer_join(
                json_pointer_join(pointer, "reference_trace"), stage
            )
            stage_evidence = _mapping_or_issue(
                reference.get(stage), stage_pointer, issues
            )
            if stage_evidence is None:
                reference_pass = False
                continue
            _closed_keys(
                stage_evidence,
                frozenset({"value_sha256_by_field", "group_sha256"}),
                stage_pointer,
                issues,
            )
            values = _mapping_or_issue(
                stage_evidence.get("value_sha256_by_field"),
                json_pointer_join(stage_pointer, "value_sha256_by_field"),
                issues,
            )
            expected_group = canonical_sha256(values) if values is not None else None
            _derived_value(
                stage_evidence.get("group_sha256"),
                expected_group,
                json_pointer_join(stage_pointer, "group_sha256"),
                issues,
            )
            reference_pass = reference_pass and bool(values)
    if not reference_pass:
        issues.append(
            _issue(
                json_pointer_join(pointer, "reference_trace"),
                "complete registered nonempty chain trace",
                reference,
            )
        )
    expected_checks = {
        "hidden_relabel_contract": hidden_pass,
        "hidden_id_full_chain_invariance": hidden_pass,
        "endpoint_permutation_full_chain_equivariance": permutation_pass,
        "query_value_substitution_before_transport": substitutions.get(
            "query_value_substitution", False
        ),
        "forbidden_state_channel_substitution": substitutions.get(
            "forbidden_state_channel_substitution", False
        ),
        "b4a_deranged_vs_b4b_oracle": b4_pass,
        "transformed_fixtures_storage_disjoint": storage_pass,
        "source_tensors_immutable": source_pass,
    }
    checks = _mapping_or_issue(
        report.get("checks"), json_pointer_join(pointer, "checks"), issues
    )
    if checks is not None:
        _closed_keys(
            checks,
            frozenset(expected_checks),
            json_pointer_join(pointer, "checks"),
            issues,
        )
        for name, expected in expected_checks.items():
            _derived_value(
                checks.get(name),
                expected,
                json_pointer_join(json_pointer_join(pointer, "checks"), name),
                issues,
            )
    passed = forward_pass and reference_pass and all(expected_checks.values())
    _derived_value(
        report.get("passed"), passed, json_pointer_join(pointer, "passed"), issues
    )
    _derived_value(
        report.get("status"),
        "PASS_R6_COUNTERFACTUAL_AUDITS" if passed else "FAIL_R6_COUNTERFACTUAL_AUDITS",
        json_pointer_join(pointer, "status"),
        issues,
    )
    return passed


def _validate_counterfactual_report(
    value: Any, pointer: str, issues: list[ValidationIssue]
) -> bool:
    """Validate the frozen report envelope and all stored comparison arithmetic.

    The runner additionally invokes the native counterfactual validator on every
    loaded report.  This independent standard-library layer deliberately avoids
    importing Torch while still rejecting missing, content-free, wrong-version,
    incorrectly sealed, or internally inconsistent evidence.
    """

    report = _mapping_or_issue(value, pointer, issues)
    top_keys = frozenset(
        {
            "schema_version",
            "status",
            "passed",
            "checks",
            "forward_boundary",
            "hidden_id_relabel",
            "endpoint_permutation",
            "query_value_substitution",
            "forbidden_state_channel_substitution",
            "b4a_deranged_vs_b4b_oracle",
            "transformed_storage_audit",
            "source_tensor_audit",
            "reference_trace",
            "report_sha256",
        }
    )
    if report is None:
        return False
    _closed_keys(report, top_keys, pointer, issues)
    _derived_value(
        report.get("schema_version"),
        _R6_COUNTERFACTUAL_SCHEMA_VERSION,
        json_pointer_join(pointer, "schema_version"),
        issues,
    )
    _derived_value(
        report.get("report_sha256"),
        canonical_sha256(
            {key: item for key, item in report.items() if key != "report_sha256"}
        ),
        json_pointer_join(pointer, "report_sha256"),
        issues,
    )

    forward = _mapping_or_issue(
        report.get("forward_boundary"),
        json_pointer_join(pointer, "forward_boundary"),
        issues,
    )
    forward_pass = False
    if forward is not None:
        forward_keys = frozenset(
            {
                "hidden_oracle_passed_to_matcher",
                "hidden_oracle_passed_to_tokenizer",
                "hidden_oracle_passed_to_projector",
                "hidden_oracle_passed_to_adapter",
                "batch_aware_hooks",
            }
        )
        _closed_keys(
            forward,
            forward_keys,
            json_pointer_join(pointer, "forward_boundary"),
            issues,
        )
        forward_pass = all(
            forward.get(name) is False
            for name in forward_keys
            if name != "batch_aware_hooks"
        ) and forward.get("batch_aware_hooks") == ["matching_regions", "token_regions"]

    required_sections = (
        "hidden_id_relabel",
        "endpoint_permutation",
        "query_value_substitution",
        "forbidden_state_channel_substitution",
        "b4a_deranged_vs_b4b_oracle",
        "transformed_storage_audit",
        "source_tensor_audit",
        "reference_trace",
    )
    sections_present = True
    for name in required_sections:
        section = _mapping_or_issue(
            report.get(name), json_pointer_join(pointer, name), issues
        )
        sections_present = sections_present and section is not None and bool(section)

    comparison_count = 0

    def walk_comparisons(node: Any, node_pointer: str) -> None:
        nonlocal comparison_count
        if isinstance(node, Mapping):
            if {
                "fields_exact",
                "all_exact",
                "all_close",
                "exact_by_field",
                "close_by_field",
                "max_abs_error_by_field",
                "value_sha256_by_field",
            }.issubset(node):
                comparison_count += 1
                _validate_comparison_evidence(node, node_pointer, issues)
                return
            for key, child in node.items():
                walk_comparisons(child, json_pointer_join(node_pointer, str(key)))
        elif isinstance(node, list):
            for index, child in enumerate(node):
                walk_comparisons(child, json_pointer_join(node_pointer, str(index)))

    for name in (
        "hidden_id_relabel",
        "endpoint_permutation",
        "query_value_substitution",
        "forbidden_state_channel_substitution",
        "b4a_deranged_vs_b4b_oracle",
    ):
        walk_comparisons(report.get(name), json_pointer_join(pointer, name))
    if comparison_count == 0:
        issues.append(
            _issue(pointer, "nonempty registered comparison evidence", comparison_count)
        )

    reference = _mapping_or_issue(
        report.get("reference_trace"),
        json_pointer_join(pointer, "reference_trace"),
        issues,
    )
    reference_pass = reference is not None and set(reference) == set(
        _R6_CHAIN_STAGE_NAMES
    )
    if reference is not None:
        _closed_keys(
            reference,
            frozenset(_R6_CHAIN_STAGE_NAMES),
            json_pointer_join(pointer, "reference_trace"),
            issues,
        )
        for stage in _R6_CHAIN_STAGE_NAMES:
            stage_pointer = json_pointer_join(
                json_pointer_join(pointer, "reference_trace"), stage
            )
            evidence = _mapping_or_issue(reference.get(stage), stage_pointer, issues)
            if evidence is None:
                reference_pass = False
                continue
            _closed_keys(
                evidence,
                frozenset({"value_sha256_by_field", "group_sha256"}),
                stage_pointer,
                issues,
            )
            values = _mapping_or_issue(
                evidence.get("value_sha256_by_field"),
                json_pointer_join(stage_pointer, "value_sha256_by_field"),
                issues,
            )
            expected_group = canonical_sha256(values) if values is not None else None
            _derived_value(
                evidence.get("group_sha256"),
                expected_group,
                json_pointer_join(stage_pointer, "group_sha256"),
                issues,
            )
            reference_pass = reference_pass and bool(values)
    if not reference_pass:
        issues.append(
            _issue(
                json_pointer_join(pointer, "reference_trace"),
                "complete registered nonempty chain trace",
                reference,
            )
        )

    root_check_names = frozenset(
        {
            "hidden_relabel_contract",
            "hidden_id_full_chain_invariance",
            "endpoint_permutation_full_chain_equivariance",
            "query_value_substitution_before_transport",
            "forbidden_state_channel_substitution",
            "b4a_deranged_vs_b4b_oracle",
            "transformed_fixtures_storage_disjoint",
            "source_tensors_immutable",
        }
    )
    checks = _mapping_or_issue(
        report.get("checks"), json_pointer_join(pointer, "checks"), issues
    )
    checks_pass = False
    if checks is not None:
        _closed_keys(
            checks, root_check_names, json_pointer_join(pointer, "checks"), issues
        )
        checks_pass = set(checks) == set(root_check_names) and all(
            item is True for item in checks.values()
        )
    passed = (
        forward_pass
        and sections_present
        and comparison_count > 0
        and reference_pass
        and checks_pass
    )
    _derived_value(
        report.get("passed"), passed, json_pointer_join(pointer, "passed"), issues
    )
    _derived_value(
        report.get("status"),
        "PASS_R6_COUNTERFACTUAL_AUDITS" if passed else "FAIL_R6_COUNTERFACTUAL_AUDITS",
        json_pointer_join(pointer, "status"),
        issues,
    )
    return passed


def _validate_embedded_report_hashes(
    root: Mapping[str, Any], issues: list[ValidationIssue]
) -> None:
    structural = root.get("structural_input_gate")
    if not isinstance(structural, Mapping):
        return
    evidence_pointer = "/structural_input_gate/r6_gate1_evidence"
    evidence = _mapping_or_issue(
        structural.get("r6_gate1_evidence"), evidence_pointer, issues
    )
    if evidence is None:
        return
    _closed_keys(
        evidence,
        frozenset(
            {
                "passed",
                "checks",
                "structural_microcases",
                "full_chain_counterfactual",
                "initialization",
            }
        ),
        evidence_pointer,
        issues,
    )
    structural_pass = _validate_structural_report(
        evidence.get("structural_microcases"),
        json_pointer_join(evidence_pointer, "structural_microcases"),
        issues,
    )
    counterfactual_pass = _validate_counterfactual_report(
        evidence.get("full_chain_counterfactual"),
        json_pointer_join(evidence_pointer, "full_chain_counterfactual"),
        issues,
    )
    initialization_pointer = json_pointer_join(evidence_pointer, "initialization")
    initialization = _mapping_or_issue(
        evidence.get("initialization"), initialization_pointer, issues
    )
    initialization_pass = False
    initialization_checks: dict[str, bool] = {}
    if initialization is not None:
        _closed_keys(
            initialization,
            frozenset(
                {
                    "schema_version",
                    "passed",
                    "checks",
                    "seed_evidence",
                    "seed_to_initial_state_sha256",
                    "seed_to_initial_state_sha256_map_sha256",
                }
            ),
            initialization_pointer,
            issues,
        )
        _derived_value(
            initialization.get("schema_version"),
            _R6_INITIALIZATION_SCHEMA_VERSION,
            json_pointer_join(initialization_pointer, "schema_version"),
            issues,
        )
        seed_evidence = _mapping_or_issue(
            initialization.get("seed_evidence"),
            json_pointer_join(initialization_pointer, "seed_evidence"),
            issues,
        )
        seed_map: dict[str, Any] = {}
        seed_passes: list[bool] = []
        if seed_evidence is not None and seed_evidence:
            for seed, item in seed_evidence.items():
                item_pointer = json_pointer_join(
                    json_pointer_join(initialization_pointer, "seed_evidence"), seed
                )
                item_pass = _validate_initialization_evidence(
                    item, item_pointer, issues
                )
                seed_passes.append(item_pass)
                if isinstance(item, Mapping):
                    seed_map[seed] = item.get("raw_initial_state_sha256")
                    _derived_value(
                        item.get("seed"),
                        int(seed) if seed.isdecimal() else None,
                        json_pointer_join(item_pointer, "seed"),
                        issues,
                    )
        else:
            issues.append(
                _issue(
                    json_pointer_join(initialization_pointer, "seed_evidence"),
                    "nonempty registered seed evidence",
                    seed_evidence,
                )
            )
        _derived_value(
            initialization.get("seed_to_initial_state_sha256"),
            seed_map,
            json_pointer_join(initialization_pointer, "seed_to_initial_state_sha256"),
            issues,
        )
        _derived_value(
            initialization.get("seed_to_initial_state_sha256_map_sha256"),
            canonical_sha256(seed_map),
            json_pointer_join(
                initialization_pointer,
                "seed_to_initial_state_sha256_map_sha256",
            ),
            issues,
        )
        initialization_checks = {
            "all_seed_evidence_passed": bool(seed_passes) and all(seed_passes),
            "same_seed_byte_exact": bool(seed_passes) and all(seed_passes),
            "seed_states_pairwise_distinct": bool(seed_map)
            and len(set(seed_map.values())) == len(seed_map),
            "seed_map_hash_exact": initialization.get(
                "seed_to_initial_state_sha256_map_sha256"
            )
            == canonical_sha256(seed_map),
            "global_rng_unchanged": initialization.get("checks", {}).get(
                "global_rng_unchanged"
            )
            is True,
        }
        checks = _mapping_or_issue(
            initialization.get("checks"),
            json_pointer_join(initialization_pointer, "checks"),
            issues,
        )
        if checks is not None:
            _closed_keys(
                checks,
                frozenset(initialization_checks),
                json_pointer_join(initialization_pointer, "checks"),
                issues,
            )
            for name, expected in initialization_checks.items():
                _derived_value(
                    checks.get(name),
                    expected,
                    json_pointer_join(
                        json_pointer_join(initialization_pointer, "checks"), name
                    ),
                    issues,
                )
        initialization_pass = all(initialization_checks.values())
        _derived_value(
            initialization.get("passed"),
            initialization_pass,
            json_pointer_join(initialization_pointer, "passed"),
            issues,
        )
    expected_evidence_checks = {
        "structural_schema_exact": structural_pass,
        "structural_passed": structural_pass,
        "structural_hash_validated": structural_pass,
        "structural_case_order_registered": structural_pass,
        "structural_input_hashes_registered": structural_pass,
        "structural_input_map_hash_registered": structural_pass,
        "counterfactual_schema_exact": counterfactual_pass,
        "counterfactual_passed": counterfactual_pass,
        "counterfactual_hash_exact": counterfactual_pass,
        **initialization_checks,
    }
    evidence_checks = _mapping_or_issue(
        evidence.get("checks"), json_pointer_join(evidence_pointer, "checks"), issues
    )
    if evidence_checks is not None:
        _closed_keys(
            evidence_checks,
            frozenset(expected_evidence_checks),
            json_pointer_join(evidence_pointer, "checks"),
            issues,
        )
        for name, expected in expected_evidence_checks.items():
            _derived_value(
                evidence_checks.get(name),
                expected,
                json_pointer_join(json_pointer_join(evidence_pointer, "checks"), name),
                issues,
            )
    evidence_pass = (
        structural_pass
        and counterfactual_pass
        and initialization_pass
        and all(expected_evidence_checks.values())
    )
    _derived_value(
        evidence.get("passed"),
        evidence_pass,
        json_pointer_join(evidence_pointer, "passed"),
        issues,
    )


def validate_r6_metric_evidence(summary: Any) -> dict[str, Any]:
    """Independently validate raw R6 metric evidence and recompute derivatives.

    The validator has no runner, data, NumPy, or Torch dependency.  Result
    families may be absent before their gate executes; once a family is
    present, every recognized evidence block is required, exact-keyed, typed,
    and arithmetically checked.  All failures are returned together as RFC 6901
    :class:`ValidationIssue` objects through :class:`R6ValidationError`.
    """

    issues = _finite_json_issues(summary)
    root = _mapping_or_issue(summary, "", issues)
    if root is None:
        raise R6ValidationError(issues)
    checked: dict[str, str] = {}

    def record(pointer: str, value: Any) -> None:
        try:
            checked[pointer] = canonical_sha256(value)
        except R6ValidationError:
            # The finite-JSON pass already reports the precise invalid leaf.
            pass

    transport_results = root.get("transport_results")
    if "transport_results" in root:
        for _, seed_value, seed_pointer in _dynamic_children(
            transport_results, "/transport_results", issues
        ):
            seed = _mapping_or_issue(seed_value, seed_pointer, issues)
            if seed is None:
                continue
            for _, stratum_value, stratum_pointer in _dynamic_children(
                seed.get("evaluations"),
                json_pointer_join(seed_pointer, "evaluations"),
                issues,
            ):
                for _, metric_value, metric_pointer in _dynamic_children(
                    stratum_value, stratum_pointer, issues
                ):
                    _validate_transport_metrics(metric_value, metric_pointer, issues)
                    record(metric_pointer, metric_value)

    fair_gate = root.get("fair_baseline_gate")
    if "fair_baseline_gate" in root:
        fair = _mapping_or_issue(fair_gate, "/fair_baseline_gate", issues)
        if fair is not None:
            for _, stratum_value, stratum_pointer in _dynamic_children(
                fair.get("assignment_metrics"),
                "/fair_baseline_gate/assignment_metrics",
                issues,
            ):
                stratum = _mapping_or_issue(stratum_value, stratum_pointer, issues)
                if stratum is None:
                    continue
                for method in ("hungarian", "sinkhorn"):
                    metric_pointer = json_pointer_join(stratum_pointer, method)
                    _validate_transport_metrics(
                        stratum.get(method), metric_pointer, issues
                    )
                    record(metric_pointer, stratum.get(method))

    label_families = (
        ("common_oracle_readout_results", "nested_metrics"),
        ("mediator_results", "nested_metrics"),
        ("binding_results", "direct_metrics"),
        ("baseline_results", "method_metrics"),
    )
    for field, layout in label_families:
        if field not in root:
            continue
        for _, seed_value, seed_pointer in _dynamic_children(
            root.get(field), json_pointer_join("", field), issues
        ):
            if layout == "nested_metrics":
                seed = _mapping_or_issue(seed_value, seed_pointer, issues)
                if seed is None:
                    continue
                metrics_pointer = json_pointer_join(seed_pointer, "metrics")
                for _, stratum_value, stratum_pointer in _dynamic_children(
                    seed.get("metrics"), metrics_pointer, issues
                ):
                    for _, metric_value, metric_pointer in _dynamic_children(
                        stratum_value, stratum_pointer, issues
                    ):
                        _validate_label_metrics(metric_value, metric_pointer, issues)
                        record(metric_pointer, metric_value)
            elif layout == "direct_metrics":
                for _, result_value, result_pointer in _dynamic_children(
                    seed_value, seed_pointer, issues
                ):
                    result = _mapping_or_issue(result_value, result_pointer, issues)
                    metric_pointer = json_pointer_join(result_pointer, "metrics")
                    if result is not None:
                        _validate_label_metrics(
                            result.get("metrics"), metric_pointer, issues
                        )
                        record(metric_pointer, result.get("metrics"))
            else:
                for _, stratum_value, stratum_pointer in _dynamic_children(
                    seed_value, seed_pointer, issues
                ):
                    for _, result_value, result_pointer in _dynamic_children(
                        stratum_value, stratum_pointer, issues
                    ):
                        result = _mapping_or_issue(result_value, result_pointer, issues)
                        metric_pointer = json_pointer_join(result_pointer, "metrics")
                        if result is not None:
                            _validate_label_metrics(
                                result.get("metrics"), metric_pointer, issues
                            )
                            record(metric_pointer, result.get("metrics"))

    if "marginal_controls" in root:
        for _, seed_value, seed_pointer in _dynamic_children(
            root.get("marginal_controls"), "/marginal_controls", issues
        ):
            for mode, control_value, control_pointer in _dynamic_children(
                seed_value, seed_pointer, issues
            ):
                _validate_marginal_control(
                    control_value, control_pointer, issues, competence=False
                )
                record(control_pointer, control_value)
                control = _mapping_or_issue(control_value, control_pointer, issues)
                requires_competence = mode.endswith("_deepsets")
                if control is not None and (
                    requires_competence or "competence_probe" in control
                ):
                    competence_pointer = json_pointer_join(
                        control_pointer, "competence_probe"
                    )
                    _validate_marginal_control(
                        control.get("competence_probe"),
                        competence_pointer,
                        issues,
                        competence=True,
                    )
                    record(competence_pointer, control.get("competence_probe"))

    if "matched_local_results" in root:
        for _, seed_value, seed_pointer in _dynamic_children(
            root.get("matched_local_results"), "/matched_local_results", issues
        ):
            seed = _mapping_or_issue(seed_value, seed_pointer, issues)
            if seed is None:
                continue
            for _, stratum_value, stratum_pointer in _dynamic_children(
                seed.get("evaluations"),
                json_pointer_join(seed_pointer, "evaluations"),
                issues,
            ):
                for _, metric_value, metric_pointer in _dynamic_children(
                    stratum_value, stratum_pointer, issues
                ):
                    _validate_local_row_metrics(metric_value, metric_pointer, issues)
                    record(metric_pointer, metric_value)

    _validate_embedded_report_hashes(root, issues)
    _validate_transport_gates(root, issues)
    _validate_readout_and_fixture_gates(root, issues)
    _validate_baseline_and_bridge_gates(root, issues)
    _validate_bridge_gate(root, issues)

    if issues:
        raise R6ValidationError(issues)
    return {
        "schema_version": R6_VALIDATION_SCHEMA_VERSION,
        "validated": True,
        "checked_block_count": len(checked),
        "checked_pointers": sorted(checked),
        "metric_evidence_sha256": canonical_sha256(checked),
    }


def _trace_from_gates(
    summary: Mapping[str, Any],
    gate_prefix: Sequence[str],
    gate_fields: Mapping[str, str],
) -> tuple[list[dict[str, Any]], list[ValidationIssue]]:
    trace: list[dict[str, Any]] = []
    issues: list[ValidationIssue] = []
    for gate_name in gate_prefix:
        field = gate_fields[gate_name]
        gate = summary.get(field)
        if not isinstance(gate, Mapping):
            issues.append(_issue(json_pointer_join("", field), "gate object", gate))
            continue
        status = gate.get("status")
        passed = gate.get("passed")
        if not isinstance(status, str):
            issues.append(
                _issue(
                    json_pointer_join(json_pointer_join("", field), "status"),
                    "string",
                    status,
                )
            )
        if not isinstance(passed, bool):
            issues.append(
                _issue(
                    json_pointer_join(json_pointer_join("", field), "passed"),
                    "boolean",
                    passed,
                )
            )
        trace.append({"name": gate_name, "status": status, "passed": passed})
    return trace, issues


def validate_r6_summary(
    summary: Any, mode: str, contract: R6SummaryContract
) -> dict[str, Any]:
    """Strictly validate one R6 summary and independently derive its outcome.

    Validation is fail-closed: the selected mode must have a complete explicit
    schema and terminal-state contract.  The returned dictionary contains only
    recomputed terminal evidence and is safe for a caller to persist.
    """

    if mode not in contract.modes:
        raise R6ValidationError([_issue("/mode", "registered validation mode", mode)])
    mode_contract = contract.modes[mode]
    validate_schema(summary, mode_contract.schema)
    assert isinstance(summary, Mapping)  # guaranteed by ObjectSchema

    issues: list[ValidationIssue] = []
    if set(summary) != set(mode_contract.expected_top_level_keys):
        issues.append(
            _issue(
                "",
                f"exact top-level keys {sorted(mode_contract.expected_top_level_keys)!r}",
                sorted(summary),
            )
        )
    if list(summary["gate_order"]) != list(contract.gate_order):
        issues.append(
            _issue(
                "/gate_order",
                f"exact gate order {list(contract.gate_order)!r}",
                summary["gate_order"],
            )
        )
    if (
        tuple(mode_contract.gate_prefix)
        != contract.gate_order[: len(mode_contract.gate_prefix)]
    ):
        issues.append(
            _issue(
                "/completed_gates",
                "completed gates form an exact gate-order prefix",
                mode_contract.gate_prefix,
            )
        )

    expected_trace, trace_issues = _trace_from_gates(
        summary, mode_contract.gate_prefix, contract.gate_fields
    )
    issues.extend(trace_issues)
    if summary["completed_gates"] != expected_trace:
        issues.append(
            _issue(
                "/completed_gates",
                f"recomputed trace {expected_trace!r}",
                summary["completed_gates"],
            )
        )

    expected_not_run = (
        mode_contract.expected_not_run_gates
        if mode_contract.expected_not_run_gates is not None
        else contract.gate_order[len(mode_contract.gate_prefix) :]
    )
    if summary["not_run_gates"] != list(expected_not_run):
        issues.append(
            _issue(
                "/not_run_gates",
                f"exact unrun suffix {list(expected_not_run)!r}",
                summary["not_run_gates"],
            )
        )
    if summary["data_access_ledger"] != list(mode_contract.expected_access_prefix):
        issues.append(
            _issue(
                "/data_access_ledger",
                f"exact registered access prefix {list(mode_contract.expected_access_prefix)!r}",
                summary["data_access_ledger"],
            )
        )

    for field in contract.formal_claim_fields:
        if summary[field] is not False:
            issues.append(
                _issue(
                    json_pointer_join("", field),
                    "formal claim field false",
                    summary[field],
                )
            )

    expected_status = mode_contract.expected_status
    if mode_contract.outcome == "stopped":
        stopped_at = mode_contract.stopped_at_gate
        if stopped_at is None or stopped_at not in contract.gate_order:
            issues.append(
                _issue(
                    "/stopped_at_gate",
                    "contract names one registered stop gate",
                    stopped_at,
                )
            )
        else:
            stop_index = contract.gate_order.index(stopped_at)
            expected_prefix = contract.gate_order[: stop_index + 1]
            if mode_contract.gate_prefix != expected_prefix:
                issues.append(
                    _issue(
                        "/completed_gates",
                        f"stop prefix {expected_prefix!r}",
                        mode_contract.gate_prefix,
                    )
                )
            if summary["stopped_at_gate"] != stopped_at:
                issues.append(
                    _issue(
                        "/stopped_at_gate",
                        f"exact stop gate {stopped_at!r}",
                        summary["stopped_at_gate"],
                    )
                )
            for gate_name in contract.gate_order[stop_index + 1 :]:
                later_field = contract.gate_fields[gate_name]
                if later_field in summary:
                    issues.append(
                        _issue(
                            json_pointer_join("", later_field),
                            "later-stage key forbidden after stop",
                            summary[later_field],
                        )
                    )
        passes = [record["passed"] for record in expected_trace]
        if passes and (
            any(value is not True for value in passes[:-1]) or passes[-1] is not False
        ):
            issues.append(
                _issue(
                    "/completed_gates",
                    "earlier gates pass and first failing gate is last",
                    expected_trace,
                )
            )
    else:
        if summary["stopped_at_gate"] is not None:
            issues.append(
                _issue(
                    "/stopped_at_gate",
                    "null for non-stopped outcome",
                    summary["stopped_at_gate"],
                )
            )
        if any(record["passed"] is not True for record in expected_trace):
            issues.append(
                _issue(
                    "/completed_gates", "every completed gate passes", expected_trace
                )
            )
        if (
            mode_contract.outcome == "success"
            and len(mode_contract.gate_prefix) != contract.success_gate_count
        ):
            issues.append(
                _issue(
                    "/completed_gates",
                    f"success has exactly {contract.success_gate_count} gates",
                    expected_trace,
                )
            )

    if summary["status"] != expected_status:
        issues.append(
            _issue(
                "/status", f"recomputed status {expected_status!r}", summary["status"]
            )
        )
    if issues:
        raise R6ValidationError(issues)
    return {
        "mode": mode,
        "status": expected_status,
        "gate_prefix": list(mode_contract.gate_prefix),
        "gate_trace": expected_trace,
        "data_access_prefix_sha256": canonical_sha256(
            list(mode_contract.expected_access_prefix)
        ),
        "validated": True,
    }
