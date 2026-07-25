from __future__ import annotations

# ruff: noqa: E402

import argparse
import ast
import copy
import ctypes
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import inspect
import json
import locale
import math
import os
from pathlib import Path
import platform
import stat
import struct
import sys
import textwrap
import time
import traceback
from typing import Any, Mapping, Sequence
import uuid

import torch
from torch import Tensor, nn
import torch.nn.functional as F


# The registered CPU execution contract requires both thread pools to be fixed
# before any tensor work.  PyTorch only permits changing the inter-op pool once;
# an already-correct process is accepted, while an incompatible preconfigured
# process fails closed below in ``run``.
torch.set_num_threads(1)
try:
    torch.set_num_interop_threads(1)
except RuntimeError:
    if torch.get_num_interop_threads() != 1:
        raise
torch.backends.cudnn.benchmark = False
torch.backends.cudnn.deterministic = True


WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts.run_query_anchor_v2 import (
    COMPETENCE_DEVELOPMENT_SEED,
    COMPETENCE_SEED_OFFSET,
    COMPETENCE_SIGNAL_AMPLITUDE,
    COMPETENCE_SIGNAL_CHANNELS,
    COMPETENCE_TRAIN_SEED,
    FROZEN_READOUT_SEED,
    QUERY_HIDDEN_SIZE,
    QUERY_RAW_DIM,
    _adapter_equivalence_audit,
    _adapter_scores,
    _assignment_diagnostics,
    _contract,
    _evaluate_marginal_control_gate,
    _fixed_adapter,
    _initial_projector,
    _json_hash,
    _label_metrics,
    _matching_regions,
    _split_manifest,
    _state_hash,
    _tensor_hash,
    _train_marginal_control,
)
from visualvit.calibration_query import (
    ENTITY_TOKENS,
    GLOBAL_TOKENS,
    QUERY_RELATION_SLOT,
    REGISTERED_DERANGEMENT_SEEDS,
    RELATION_TOKENS,
    RESERVED_TOKENS,
    TOKEN_BUDGET,
    HiddenQueryOracle,
    QueryTokenContract,
    QueryAnchorBatch,
    build_balanced_derangement_bank,
)
from visualvit.calibration_r5 import (
    FEATURE_DIM,
    FROZEN_NULL_UTILITY_CAP,
    FROZEN_R5_CHALLENGE_SPLIT_SEEDS,
    FROZEN_R5_CLEAN_SPLIT_SEEDS,
    FROZEN_R5_COUNTERBALANCE_GROUPS,
    FROZEN_RESIDUAL_CAP,
    IDENTITY_VIEW_SLICES,
    LEARNED_FEASIBLE_VIEW_WEIGHTS,
    R5ChallengeBatch,
    R5CleanBatch,
    enumerate_r5_clean_assignment_certificate,
    make_frozen_r5_challenge_split,
    make_frozen_r5_clean_split,
    make_r5_anti_equivalence_challenge,
    make_r5_clean_batch,
    r4_visible_hash,
    r5_challenge_hidden_oracle_hash,
    r5_clean_hidden_oracle_hash,
)
from visualvit.matching import InvariantPartialOTMatcher, assignment_accuracy
from visualvit.allocator import DeterministicGlobalAllocator
from visualvit.projector import RelationProjector
from visualvit.query_anchor_model import QueryRelationProjector
from visualvit.query_anchor_model import query_prompt
from visualvit.r6_counterfactual_audits import (
    R6_COUNTERFACTUAL_SCHEMA_VERSION,
    R6ChainHooks,
    run_r6_counterfactual_audits,
    validate_r6_counterfactual_audit,
)
from visualvit.r6_structural_audits import (
    R6_STRUCTURAL_AUDIT_SCHEMA_VERSION,
    run_r6_structural_audits,
    validate_r6_structural_audit,
)
from visualvit.r6_validation import (
    R6_VALIDATION_SCHEMA_VERSION,
    R6ValidationError,
    is_utc_z_timestamp,
    is_uuid4,
    validate_r6_metric_evidence,
)
from visualvit.schemas import MatchPlan


R5_PROTOCOL_PATH = WORKSPACE / "refine-logs" / "CALIBRATION_PROTOCOL_R5_2026-07-22.md"
R5_PROTOCOL_SHA256 = "015949a51b06c1da6c0c10b881226979b412d4cac460f6b2e5779db6ac7b4491"
R9_BASE_PROTOCOL_PATH = (
    WORKSPACE / "refine-logs" / "CALIBRATION_PROTOCOL_R9_2026-07-23.md"
)
R9_BASE_PROTOCOL_SHA256 = (
    "c11a9c6677909c8ecab6645cf4d7aa79e3b7470aee573fb7e6c4a857dda00f8b"
)
R9_BASE_REGISTRY_SHA256 = (
    "bdb7ce728301f05169f6c07eb1896d9925d1ceb27311725d9ab9aca16d48acde"
)
# R24 has one direct immutable base: the frozen R23 transaction.  R14 remains
# separately pinned only
# as historical evidence for the independently authorized reproduction route.
R23_BASE_PROTOCOL_PATH = (
    WORKSPACE / "refine-logs" / "CALIBRATION_PROTOCOL_R23_2026-07-24.md"
)
R23_BASE_PROTOCOL_SHA256 = (
    "36e29039eb1d56012a8105a4da0aba8e1c5e2095d255f9a42f4ec22c95f173dc"
)
R23_BASE_REGISTRY_SHA256 = (
    "fdf4ca8fbf4a8389183ffbb5d234ab2392c666dd69263fb91d125cdb7f42b81c"
)
R14_EVIDENCE_PROTOCOL_SHA256 = (
    "11192f98ea1dcc216a6b13eb1611c8cb9ef677d75500032b6cbdf38528e125ce"
)
R14_EVIDENCE_REGISTRY_SHA256 = (
    "8e6d8bc79ef210eda9182167ec8328f8b0641cfcb69e75dbc1d56a1ab1f98f5e"
)
R24_BASE_PROTOCOL_PATH = (
    WORKSPACE / "refine-logs" / "CALIBRATION_PROTOCOL_R24_2026-07-24.md"
)
R24_BASE_PROTOCOL_SHA256 = (
    "2f8b1577d193bf6a63d5146853ffd2b5fdc70918b6937652ff2cef47d8cc8e44"
)
R24_BASE_REGISTRY_SHA256 = (
    "3bfe2466b00bc4f1c24a066ef40d48a6a0ae6508ff93bb8224b2620fd908827b"
)
R24_PROTOCOL_PATH = R24_BASE_PROTOCOL_PATH
R25_PROTOCOL_PATH = WORKSPACE / "refine-logs" / "CALIBRATION_PROTOCOL_R25_2026-07-25.md"


def _load_frozen_r5_registry() -> dict[str, Any]:
    payload = R5_PROTOCOL_PATH.read_bytes()
    observed_sha256 = hashlib.sha256(payload).hexdigest()
    if observed_sha256 != R5_PROTOCOL_SHA256:
        raise RuntimeError(
            "R5 protocol authority SHA-256 mismatch: "
            f"expected {R5_PROTOCOL_SHA256}, observed {observed_sha256}"
        )
    text_payload = payload.decode("utf-8")
    opening = text_payload.index("```json") + len("```json")
    closing = text_payload.index("```", opening)
    registry = json.loads(text_payload[opening:closing])
    if not isinstance(registry, dict):
        raise TypeError("R5 machine registry must be a JSON object")
    return registry


FROZEN_R5_REGISTRY = _load_frozen_r5_registry()


def _first_json_object(path: Path, *, label: str) -> dict[str, Any]:
    text_payload = path.read_text(encoding="utf-8")
    return _first_json_object_text(text_payload, label=label)


def _first_json_object_text(text_payload: str, *, label: str) -> dict[str, Any]:
    opening = text_payload.index("```json") + len("```json")
    closing = text_payload.index("```", opening)
    registry = json.loads(text_payload[opening:closing])
    if not isinstance(registry, dict):
        raise TypeError(f"{label} machine registry must be a JSON object")
    return registry


def _load_r24_candidate_registry() -> dict[str, Any]:
    registry = _first_json_object(R24_PROTOCOL_PATH, label="R24")
    base = registry.get("base_dependency")
    if not isinstance(base, Mapping):
        raise RuntimeError("R24 authority is missing its R23 base dependency")
    expected_base = {
        "path": "refine-logs/CALIBRATION_PROTOCOL_R23_2026-07-24.md",
        "protocol_sha256": R23_BASE_PROTOCOL_SHA256,
        "registry_sha256": R23_BASE_REGISTRY_SHA256,
        "registry_sha256_semantics": (
            "r23_full_canonical_registry_including_complete_freeze_record"
        ),
        "authority_state": "FROZEN_BEFORE_R23_REPRODUCTION",
    }
    if base != expected_base:
        raise RuntimeError("R24 immutable R23 base dependency declaration mismatch")
    observed_base_sha256 = hashlib.sha256(
        R23_BASE_PROTOCOL_PATH.read_bytes()
    ).hexdigest()
    if observed_base_sha256 != R23_BASE_PROTOCOL_SHA256:
        raise RuntimeError("R24 immutable R23 base protocol SHA-256 mismatch")
    base_registry = _first_json_object(R23_BASE_PROTOCOL_PATH, label="R23 base")
    if _json_hash(base_registry) != R23_BASE_REGISTRY_SHA256:
        raise RuntimeError("R24 immutable R23 full-registry SHA-256 mismatch")

    phase_contract = registry.get("phase_authorization_contract")
    if not isinstance(phase_contract, Mapping):
        raise RuntimeError("R24 authority is missing its phase authorization contract")
    runner_guard = phase_contract.get("runner_guard")
    if not isinstance(runner_guard, Mapping) or (
        runner_guard.get("phase_authorization_mode_closed_set")
        != ["independent_reproduction"]
        or runner_guard.get("phase_authorization_required_modes")
        != ["independent_reproduction"]
        or runner_guard.get("phase_authorization_denied_all_other_modes") is not True
    ):
        raise RuntimeError("R24 must authorize only independent reproduction")
    bundle = phase_contract.get("frozen_validator_dependency_bundle")
    anchor = bundle.get("origin_protocol") if isinstance(bundle, Mapping) else None
    expected_r14_anchor = {
        "relative_path": "refine-logs/CALIBRATION_PROTOCOL_R14_2026-07-23.md",
        "sha256": R14_EVIDENCE_PROTOCOL_SHA256,
        "registry_sha256": R14_EVIDENCE_REGISTRY_SHA256,
        "authority_state": "FROZEN_BEFORE_R14_DRY_RUN",
    }
    if anchor != expected_r14_anchor:
        raise RuntimeError("R24 immutable R14 evidence anchor declaration mismatch")
    return registry


def _load_r25_candidate_registry() -> dict[str, Any]:
    registry = _first_json_object(R25_PROTOCOL_PATH, label="R25")
    base = registry.get("base_dependency")
    if not isinstance(base, Mapping):
        raise RuntimeError("R25 authority is missing its R24 base dependency")
    expected_base = {
        "path": "refine-logs/CALIBRATION_PROTOCOL_R24_2026-07-24.md",
        "protocol_sha256": R24_BASE_PROTOCOL_SHA256,
        "registry_sha256": R24_BASE_REGISTRY_SHA256,
        "registry_sha256_semantics": (
            "r24_full_canonical_registry_including_complete_freeze_record"
        ),
        "authority_state": "FROZEN_BEFORE_R24_REPRODUCTION",
    }
    if base != expected_base:
        raise RuntimeError("R25 immutable R24 base dependency declaration mismatch")
    observed_base_sha256 = hashlib.sha256(
        R24_BASE_PROTOCOL_PATH.read_bytes()
    ).hexdigest()
    if observed_base_sha256 != R24_BASE_PROTOCOL_SHA256:
        raise RuntimeError("R25 immutable R24 base protocol SHA-256 mismatch")
    base_registry = _first_json_object(R24_BASE_PROTOCOL_PATH, label="R24 base")
    if _json_hash(base_registry) != R24_BASE_REGISTRY_SHA256:
        raise RuntimeError("R25 immutable R24 full-registry SHA-256 mismatch")

    phase_contract = registry.get("phase_authorization_contract")
    if not isinstance(phase_contract, Mapping):
        raise RuntimeError("R25 authority is missing its phase authorization contract")
    runner_guard = phase_contract.get("runner_guard")
    if not isinstance(runner_guard, Mapping) or (
        runner_guard.get("phase_authorization_mode_closed_set")
        != ["independent_reproduction"]
        or runner_guard.get("phase_authorization_required_modes")
        != ["independent_reproduction"]
        or runner_guard.get("phase_authorization_denied_all_other_modes") is not True
    ):
        raise RuntimeError("R25 must authorize only independent reproduction")
    bundle = phase_contract.get("frozen_validator_dependency_bundle")
    anchor = bundle.get("origin_protocol") if isinstance(bundle, Mapping) else None
    expected_r14_anchor = {
        "relative_path": "refine-logs/CALIBRATION_PROTOCOL_R14_2026-07-23.md",
        "sha256": R14_EVIDENCE_PROTOCOL_SHA256,
        "registry_sha256": R14_EVIDENCE_REGISTRY_SHA256,
        "authority_state": "FROZEN_BEFORE_R14_DRY_RUN",
    }
    if anchor != expected_r14_anchor:
        raise RuntimeError("R25 immutable R14 evidence anchor declaration mismatch")
    return registry


R25_REGISTRY = _load_r25_candidate_registry()
R24_REGISTRY = _first_json_object(R24_BASE_PROTOCOL_PATH, label="R24 base")
R23_REGISTRY = _first_json_object(R23_BASE_PROTOCOL_PATH, label="R23 base")
# Compatibility aliases preserve historical helper imports but never select an
# ancestor as the live execution authority.
R20_REGISTRY = R25_REGISTRY
R19_REGISTRY = R25_REGISTRY
R18_REGISTRY = R25_REGISTRY
R17_REGISTRY = R25_REGISTRY
R16_REGISTRY = R25_REGISTRY
R12_REGISTRY = R25_REGISTRY
R13_REGISTRY = R25_REGISTRY
R14_REGISTRY = R25_REGISTRY
R15_REGISTRY = R25_REGISTRY
R11_REGISTRY = R25_REGISTRY
R10_REGISTRY = R25_REGISTRY
FROZEN_R6_REGISTRY = R25_REGISTRY
R25_PROTOCOL_SHA256 = hashlib.sha256(R25_PROTOCOL_PATH.read_bytes()).hexdigest()
R24_PROTOCOL_SHA256 = R24_BASE_PROTOCOL_SHA256
R23_PROTOCOL_SHA256 = R23_BASE_PROTOCOL_SHA256
R20_PROTOCOL_SHA256 = R25_PROTOCOL_SHA256
R19_PROTOCOL_SHA256 = R25_PROTOCOL_SHA256
R18_PROTOCOL_SHA256 = R25_PROTOCOL_SHA256
R17_PROTOCOL_SHA256 = R25_PROTOCOL_SHA256
R16_PROTOCOL_SHA256 = R25_PROTOCOL_SHA256
R12_PROTOCOL_PATH = R25_PROTOCOL_PATH
R12_PROTOCOL_SHA256 = R25_PROTOCOL_SHA256
R13_PROTOCOL_SHA256 = R25_PROTOCOL_SHA256
R14_PROTOCOL_SHA256 = R25_PROTOCOL_SHA256
R15_PROTOCOL_SHA256 = R25_PROTOCOL_SHA256
R11_PROTOCOL_SHA256 = R25_PROTOCOL_SHA256
R10_PROTOCOL_PATH = R25_PROTOCOL_PATH
R10_PROTOCOL_SHA256 = R25_PROTOCOL_SHA256
PROTOCOL_VERSION = str(FROZEN_R6_REGISTRY["protocol_id"])
IMPLEMENTED_SCHEMA_VERSIONS = {
    "resolver": "r24_resolver_v1",
    "summary": "r24_summary_v1",
    "runtime_environment": "r6_runtime_environment_v1",
    "source_manifest": "r24_source_manifest_v1",
    "result": "r6.result.v1",
    "initialization": "r24_initialization_evidence_v1",
    "structural_microcases": "visualvit.r6-structural-audits.v3",
    "counterfactual": "visualvit.r6_counterfactual_audits.v1",
    "independent_validator": "visualvit.r6-validation.v4",
    "data_access_ledger": "r6_split_access_ledger_v1",
    "exact64_ledger": "r6_exact64_call_ledger_v1",
    "reproduction": "r24_reproduction_certificate_v1",
    "failure": "r24_atomic_failure_v1",
    "freeze_record": "r24_freeze_record_v1",
    "dryrun_postrun_audit": "r24_dryrun_postrun_audit_v1",
    "smoke_authorization": "r24_smoke_authorization_certificate_v1",
    "smoke_postrun_audit": "r24_smoke_postrun_audit_v1",
    "registered_authorization": "r24_registered_authorization_certificate_v1",
}
SUMMARY_SCHEMA_VERSION = IMPLEMENTED_SCHEMA_VERSIONS["summary"]
RESOLVER_SCHEMA_VERSION = IMPLEMENTED_SCHEMA_VERSIONS["resolver"]
RESULT_SCHEMA_VERSION = IMPLEMENTED_SCHEMA_VERSIONS["result"]
EVIDENCE_CLASS = str(FROZEN_R6_REGISTRY["evidence_class"])
TRAINABLE_SEEDS = (17, 29, 43)
STRATA = ("clean", "challenge")
SPLIT_NAMES = ("train", "inner_development", "development")
_registered_exact64_method_order = FROZEN_R6_REGISTRY.get("exact64_method_order")
if (
    not isinstance(_registered_exact64_method_order, list)
    or any(type(name) is not str for name in _registered_exact64_method_order)
    or len(_registered_exact64_method_order)
    != len(set(_registered_exact64_method_order))
):
    raise RuntimeError("R12 exact64 method order must be a unique string array")
EXACT64_METHOD_ORDER = tuple(_registered_exact64_method_order)
REGISTERED_STEPS = 500
TRANSPORT_LEARNING_RATE = 2e-2
MEDIATOR_LEARNING_RATE = 2e-2
GRADIENT_CLIP_NORM = 1.0
RESIDUAL_CAP = FROZEN_RESIDUAL_CAP
NULL_UTILITY_CAP = FROZEN_NULL_UTILITY_CAP
INITIALIZATION_STD = 0.01
SINKHORN_TEMPERATURE = 0.05
SINKHORN_ITERATIONS = 256
FEASIBILITY_TOLERANCE = 1e-5
IMPLEMENTED_STATUS_VOCABULARY = dict(FROZEN_R6_REGISTRY["status_vocabulary"])
PENDING_STATUS = IMPLEMENTED_STATUS_VOCABULARY["primary_pending_reproduction"]
SCIENTIFIC_STOP_PREFIX = str(
    FROZEN_R6_REGISTRY["status_vocabulary"]["scientific_stop_prefix"]
)


def _stop_status(reason: str) -> str:
    return f"{SCIENTIFIC_STOP_PREFIX}{reason.upper()}"


IMPLEMENTED_OUTPUT_LEAVES = {
    "dry_run": "capes_ci_qptm_r24_dryrun_20260724_v1",
    "smoke": "capes_ci_qptm_r24_smoke_seed17_20260724_v1",
    "registered_local": "capes_ci_qptm_r24_registered_local_20260724_v1",
    "registered_slurm4161": "capes_ci_qptm_r24_registered_slurm4161_20260724_v1",
    "reproduction_local": "capes_ci_qptm_r24_reproduction_local_20260724_v1",
    "reproduction_slurm4161": "capes_ci_qptm_r24_reproduction_slurm4161_20260724_v1",
}
IMPLEMENTED_REPRODUCTION_CHILD_LEAVES = ("process_a", "process_b")
IMPLEMENTED_SUMMARY_SERIALIZATION_CONTRACT = {
    "schema_version": "r7_summary_serialization_v1",
    "encoding": "utf-8",
    "ensure_ascii": True,
    "indent": 2,
    "sort_keys": True,
    "allow_nan": False,
    "terminal_newline_utf8_hex": "0a",
    "serialize_exactly_once": True,
    "parse_exact_serialized_bytes_once": True,
    "validate_reparsed_object_before_publication": True,
    "required_validation_entrypoints": [
        "runner_independent_metric_validator",
        "native_structural_validator",
        "native_counterfactual_validator",
        "strict_terminal_summary_validator",
    ],
    "publish_same_validated_bytes_without_reserialization": True,
    "postserialization_failure_publishes_success_summary": False,
    "postserialization_failure_returns_success": False,
}
IMPLEMENTED_PRE_ROOT_FAILURE_PARENT = "artifacts/calibration/.r24_pre_root_failures"
IMPLEMENTED_FAILURE_STAGES = (
    "argument_resolution",
    "authority_capture",
    "output_root_validation",
    "phase_authorization",
    "output_root_creation",
    "gate_execution",
    "summary_postserialization_validation",
    "summary_write",
    "child_launch",
    "child_communicate",
    "stdout_write",
    "stderr_write",
    "child_summary_read",
    "child_summary_parse",
    "child_eligibility",
    "canonical_compare",
    "certificate_write",
)

_registered_source_paths = FROZEN_R6_REGISTRY["closed_source_allowlist_contract"][
    "paths"
]
if (
    not isinstance(_registered_source_paths, list)
    or any(type(path) is not str for path in _registered_source_paths)
    or _registered_source_paths != sorted(_registered_source_paths)
    or len(_registered_source_paths) != len(set(_registered_source_paths))
):
    raise RuntimeError(
        "R12 closed source allowlist must be a sorted unique list of strings"
    )
SOURCE_ALLOWLIST = tuple(_registered_source_paths)

_R25_PROTOCOL_RELATIVE_PATH = "refine-logs/CALIBRATION_PROTOCOL_R25_2026-07-25.md"
_R24_PROTOCOL_RELATIVE_PATH = _R25_PROTOCOL_RELATIVE_PATH
_R23_PROTOCOL_RELATIVE_PATH = _R24_PROTOCOL_RELATIVE_PATH
_R20_PROTOCOL_RELATIVE_PATH = _R24_PROTOCOL_RELATIVE_PATH
_R19_PROTOCOL_RELATIVE_PATH = _R23_PROTOCOL_RELATIVE_PATH
_R17_PROTOCOL_RELATIVE_PATH = _R23_PROTOCOL_RELATIVE_PATH
_R12_PROTOCOL_RELATIVE_PATH = _R23_PROTOCOL_RELATIVE_PATH
_R11_PROTOCOL_RELATIVE_PATH = _R12_PROTOCOL_RELATIVE_PATH
_R10_PROTOCOL_RELATIVE_PATH = _R12_PROTOCOL_RELATIVE_PATH
# Backward-compatible internal alias for existing freeze helper callers.
_R6_PROTOCOL_RELATIVE_PATH = _R11_PROTOCOL_RELATIVE_PATH
_FREEZE_RECORD_SOURCE_FIELDS = {
    "runner_sha256": "scripts/run_query_anchor_r4.py",
    "reproduction_launcher_sha256": "scripts/run_query_anchor_r4_reproduction.py",
    "query_anchor_v2_runner_sha256": "scripts/run_query_anchor_v2.py",
    "calibration_r5_sha256": "src/visualvit/calibration_r5.py",
    "matching_sha256": "src/visualvit/matching.py",
    "runner_tests_sha256": "tests/test_query_anchor_r4_runner.py",
    "query_anchor_v2_tests_sha256": "tests/test_query_anchor_v2_runner.py",
    "calibration_tests_sha256": "tests/test_calibration_r5.py",
    "matching_tests_sha256": "tests/test_matching.py",
    "semantic_validator_sha256": "src/visualvit/r6_validation.py",
    "semantic_validator_tests_sha256": "tests/test_r6_validation.py",
    "boundary_tests_sha256": "tests/test_r6_runner_boundary.py",
    "reproduction_tests_sha256": "tests/test_r6_reproduction.py",
    "gate_spec_sha256": "reports/r5_runner_gate_spec_2026-07-22.md",
    "structural_audit_sha256": "src/visualvit/r6_structural_audits.py",
    "structural_audit_tests_sha256": "tests/test_r6_structural_audits.py",
    "summary_roundtrip_tests_sha256": "tests/test_r6_runner_boundary.py",
}


class RaisingArgumentParser(argparse.ArgumentParser):
    """Keep CLI resolution inside the registered failure transaction."""

    def error(self, message: str) -> None:
        raise ValueError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = RaisingArgumentParser(
        description="Run the fail-closed CAPES-CI QPTM R10 engineering calibration."
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=REGISTERED_STEPS)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(TRAINABLE_SEEDS))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--smoke", action="store_true")
    parser.add_argument("--device", choices=("cpu",), default="cpu")
    return parser


def _file_hash(path: Path) -> str:
    # The live R10 protocol check is an authorization boundary, not merely a
    # diagnostic hash.  Read it through the same no-reparse snapshot used by
    # certificates and prerequisite artifacts.
    if path == R10_PROTOCOL_PATH:
        return hashlib.sha256(_safe_workspace_read_bytes(path)).hexdigest()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_exception_message(error: BaseException) -> str:
    try:
        return str(error)
    except Exception as render_error:
        return (
            f"<unrenderable {type(error).__name__}; "
            f"message capture failed with {type(render_error).__name__}>"
        )


def _path_is_plain_workspace_descendant(path: Path) -> bool:
    """Reject a lexical workspace path containing any reparse component."""
    raw_workspace = WORKSPACE.absolute()
    raw_path = path.absolute()
    try:
        raw_path.relative_to(raw_workspace)
    except ValueError:
        return False

    # Walk the raw path before resolving it.  Resolving first would hide an
    # in-workspace junction whose target also lies under the workspace.
    cursor = raw_path
    while True:
        try:
            metadata = os.stat(cursor, follow_symlinks=False)
        except FileNotFoundError:
            pass
        except OSError:
            return False
        else:
            attributes = getattr(metadata, "st_file_attributes", 0)
            if stat.S_ISLNK(metadata.st_mode) or bool(
                attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            ):
                return False
        if cursor == raw_workspace:
            break
        if cursor == cursor.parent:
            return False
        cursor = cursor.parent

    try:
        raw_path.resolve(strict=False).relative_to(raw_workspace.resolve())
    except (OSError, ValueError):
        return False
    return True


def _workspace_metadata_identity(metadata: os.stat_result) -> tuple[int, int, int, int]:
    """Identity fields which survive an expected directory-entry mutation."""

    return (
        int(metadata.st_dev),
        int(metadata.st_ino),
        stat.S_IFMT(metadata.st_mode),
        int(getattr(metadata, "st_file_attributes", 0)),
    )


def _workspace_metadata_snapshot(metadata: os.stat_result) -> tuple[int, ...]:
    """Capture identity and mutation-sensitive fields for a safe file snapshot."""

    return _workspace_metadata_identity(metadata) + (
        int(metadata.st_size),
        int(getattr(metadata, "st_mtime_ns", 0)),
        int(getattr(metadata, "st_ctime_ns", 0)),
    )


def _workspace_path_snapshot(
    path: Path,
    *,
    require_exists: bool,
    require_directory: bool = False,
    require_regular_file: bool = False,
) -> dict[str, Any]:
    """Capture a raw, no-reparse workspace path and every existing component.

    Windows has no usable ``openat``/directory-FD path API in the supported Python
    runtime.  We therefore retain both raw component identities and resolved path,
    and require them to be unchanged immediately before and after sensitive IO.
    """

    if require_directory and require_regular_file:
        raise ValueError("workspace snapshot cannot require both file and directory")
    raw_workspace = WORKSPACE.absolute()
    raw_path = path.absolute()
    try:
        relative = raw_path.relative_to(raw_workspace)
    except ValueError as error:
        raise ValueError(f"workspace path escapes raw workspace: {path}") from error
    components: list[tuple[str, tuple[int, ...]]] = []
    cursor = raw_workspace
    for index, component in enumerate((".", *relative.parts)):
        if index:
            cursor = cursor / component
        try:
            metadata = os.stat(cursor, follow_symlinks=False)
        except FileNotFoundError:
            if cursor == raw_path and not require_exists:
                break
            raise ValueError(f"workspace path component is absent: {cursor}") from None
        except OSError as error:
            raise ValueError(
                f"cannot lstat workspace path component: {cursor}"
            ) from error
        attributes = getattr(metadata, "st_file_attributes", 0)
        if stat.S_ISLNK(metadata.st_mode) or bool(
            attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        ):
            raise ValueError(
                f"workspace path crosses symlink/junction/reparse: {cursor}"
            )
        components.append((str(cursor), _workspace_metadata_snapshot(metadata)))
    target_exists = bool(components and components[-1][0] == str(raw_path))
    if require_exists and not target_exists:
        raise ValueError(f"workspace path is absent: {raw_path}")
    if target_exists:
        target_mode = components[-1][1][2]
        if require_directory and target_mode != stat.S_IFDIR:
            raise ValueError(f"workspace path is not a directory: {raw_path}")
        if require_regular_file and target_mode != stat.S_IFREG:
            raise ValueError(f"workspace path is not a regular file: {raw_path}")
    try:
        resolved = raw_path.resolve(strict=False)
        resolved.relative_to(raw_workspace.resolve(strict=True))
    except (OSError, ValueError) as error:
        raise ValueError(
            f"workspace path resolves outside workspace: {raw_path}"
        ) from error
    return {
        "raw_path": raw_path,
        "resolved_path": resolved,
        "components": tuple(components),
        "target_exists": target_exists,
        "require_exists": require_exists,
        "require_directory": require_directory,
        "require_regular_file": require_regular_file,
    }


def _revalidate_workspace_path_snapshot(
    snapshot: Mapping[str, Any], *, identity_only: bool = False
) -> dict[str, Any]:
    """Fail closed when a previously captured raw component changed."""

    current = _workspace_path_snapshot(
        Path(snapshot["raw_path"]),
        require_exists=bool(snapshot["require_exists"]),
        require_directory=bool(snapshot["require_directory"]),
        require_regular_file=bool(snapshot["require_regular_file"]),
    )
    if (
        current["raw_path"] != snapshot["raw_path"]
        or current["resolved_path"] != snapshot["resolved_path"]
    ):
        raise ValueError("workspace path resolution drifted")
    expected_components = tuple(snapshot["components"])
    observed_components = tuple(current["components"])
    if len(expected_components) != len(observed_components):
        raise ValueError("workspace path component set drifted")
    for (expected_path, expected), (observed_path, observed) in zip(
        expected_components, observed_components
    ):
        if expected_path != observed_path:
            raise ValueError("workspace path component spelling drifted")
        if identity_only:
            if expected[:4] != observed[:4]:
                raise ValueError("workspace parent identity/reparse drifted")
        elif expected != observed:
            raise ValueError("workspace path metadata drifted")
    return current


def _safe_workspace_read_bytes(path: Path) -> bytes:
    """Read a regular authority file only if its complete safe snapshot holds."""

    snapshot = _workspace_path_snapshot(
        path, require_exists=True, require_regular_file=True
    )
    _revalidate_workspace_path_snapshot(snapshot)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(snapshot["raw_path"], flags)
    try:
        opened = os.fstat(descriptor)
        expected = tuple(snapshot["components"])[-1][1]
        if (
            not stat.S_ISREG(opened.st_mode)
            or _workspace_metadata_identity(opened) != expected[:4]
        ):
            raise ValueError("opened authority file differs from safe snapshot")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            raw = handle.read()
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    _revalidate_workspace_path_snapshot(snapshot)
    return raw


def _safe_workspace_mkdir_new(path: Path) -> None:
    """Create one directory through a verified-parent native transaction."""

    target = _workspace_path_snapshot(path, require_exists=False)
    if target["target_exists"]:
        raise FileExistsError(f"refusing to overwrite output root: {path}")
    parent = _workspace_path_snapshot(
        path.parent, require_exists=True, require_directory=True
    )
    _revalidate_workspace_path_snapshot(target)
    _revalidate_workspace_path_snapshot(parent)
    _native_create_new_child(
        parent["raw_path"],
        Path(target["raw_path"]).name,
        directory=True,
        payload=None,
    )
    created = _workspace_path_snapshot(
        path, require_exists=True, require_directory=True
    )
    _revalidate_workspace_path_snapshot(parent, identity_only=True)
    if (
        tuple(created["components"])[-1][1][:4]
        == tuple(parent["components"])[-1][1][:4]
    ):
        raise ValueError("new output root aliases its parent")


class NativeSafePathUnavailable(RuntimeError):
    """Raised instead of weakening R11 path creation outside native Windows APIs."""


# Test-only observer: production leaves it unset.  It receives native operation
# metadata before/after the actual ctypes call, so tests can assert the security
# parameters without replacing the RootDirectory transaction itself.
_NATIVE_OPS_HOOK: Any = None


def _native_create_new_child(
    parent_path: str | Path,
    child_name: str,
    *,
    directory: bool,
    payload: bytes | None,
) -> None:
    """Create exactly one plain child with NtCreateFile relative to its parent HANDLE.

    R11 deliberately has no ``mkdir``/``os.open`` fallback.  The leaf is a
    single lexical segment; all ancestor/reparse checks are performed by the
    caller before this function opens the verified parent handle.
    """

    if os.name != "nt":
        raise NativeSafePathUnavailable(
            "R11 native safe-path transaction requires Windows"
        )
    if (
        not child_name
        or Path(child_name).name != child_name
        or child_name in {".", ".."}
    ):
        raise ValueError("native safe-path child must be one plain segment")

    def observe(event: str, **payload: Any) -> None:
        if _NATIVE_OPS_HOOK is not None:
            _NATIVE_OPS_HOOK(event, payload)

    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
    invalid_handle = wintypes.HANDLE(-1).value
    file_list_directory = 0x0001
    file_read_data = 0x0001
    file_write_data = 0x0002
    file_read_attributes = 0x0080
    synchronize = 0x00100000
    file_share_read = 0x00000001
    file_share_write = 0x00000002
    open_existing = 3
    file_flag_backup_semantics = 0x02000000
    file_flag_open_reparse_point = 0x00200000
    obj_case_insensitive = 0x0040
    obj_dont_reparse = 0x1000
    file_create = 2
    file_open = 1
    file_directory_file = 0x00000001
    file_non_directory_file = 0x00000040
    file_open_reparse_point = 0x00200000
    file_synchronous_io_nonalert = 0x00000020
    file_created = 2
    file_id_info = 18
    file_attribute_tag_info = 9
    file_attribute_reparse_point = 0x0400

    class UNICODE_STRING(ctypes.Structure):
        _fields_ = [
            ("Length", wintypes.USHORT),
            ("MaximumLength", wintypes.USHORT),
            ("Buffer", wintypes.LPWSTR),
        ]

    class OBJECT_ATTRIBUTES(ctypes.Structure):
        _fields_ = [
            ("Length", wintypes.ULONG),
            ("RootDirectory", wintypes.HANDLE),
            ("ObjectName", ctypes.POINTER(UNICODE_STRING)),
            ("Attributes", wintypes.ULONG),
            ("SecurityDescriptor", wintypes.LPVOID),
            ("SecurityQualityOfService", wintypes.LPVOID),
        ]

    class IO_STATUS_BLOCK(ctypes.Structure):
        _fields_ = [("Status", ctypes.c_long), ("Information", ctypes.c_size_t)]

    class FILE_ID_INFO(ctypes.Structure):
        _fields_ = [
            ("VolumeSerialNumber", wintypes.ULONG),
            ("FileId", ctypes.c_ubyte * 16),
            ("_native_alignment", ctypes.c_ubyte * 4),
        ]

    class FILE_ATTRIBUTE_TAG_INFO(ctypes.Structure):
        _fields_ = [("FileAttributes", wintypes.DWORD), ("ReparseTag", wintypes.DWORD)]

    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.GetFileInformationByHandleEx.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    kernel32.GetFileInformationByHandleEx.restype = wintypes.BOOL
    kernel32.SetFilePointerEx.argtypes = [
        wintypes.HANDLE,
        ctypes.c_longlong,
        ctypes.POINTER(ctypes.c_longlong),
        wintypes.DWORD,
    ]
    kernel32.SetFilePointerEx.restype = wintypes.BOOL
    ntdll.NtCreateFile.argtypes = [
        ctypes.POINTER(wintypes.HANDLE),
        wintypes.DWORD,
        ctypes.POINTER(OBJECT_ATTRIBUTES),
        ctypes.POINTER(IO_STATUS_BLOCK),
        ctypes.POINTER(ctypes.c_longlong),
        wintypes.ULONG,
        wintypes.ULONG,
        wintypes.ULONG,
        wintypes.ULONG,
        wintypes.LPVOID,
        wintypes.ULONG,
    ]
    ntdll.NtCreateFile.restype = ctypes.c_long
    ntdll.RtlNtStatusToDosError.argtypes = [ctypes.c_long]
    ntdll.RtlNtStatusToDosError.restype = wintypes.ULONG

    def native_identity(handle: wintypes.HANDLE) -> tuple[int, bytes, int, int]:
        file_id = FILE_ID_INFO()
        attributes = FILE_ATTRIBUTE_TAG_INFO()
        if not kernel32.GetFileInformationByHandleEx(
            handle, file_id_info, ctypes.byref(file_id), ctypes.sizeof(file_id)
        ):
            raise OSError(ctypes.get_last_error(), "cannot capture R11 FileIdInfo")
        if not kernel32.GetFileInformationByHandleEx(
            handle,
            file_attribute_tag_info,
            ctypes.byref(attributes),
            ctypes.sizeof(attributes),
        ):
            raise OSError(
                ctypes.get_last_error(), "cannot capture R11 AttributeTagInfo"
            )
        if attributes.FileAttributes & file_attribute_reparse_point:
            raise ValueError("R11 native handle resolves to a reparse point")
        identity = (
            file_id.VolumeSerialNumber,
            bytes(file_id.FileId),
            attributes.FileAttributes,
            attributes.ReparseTag,
        )
        observe("identity", identity=identity)
        return identity

    parent = kernel32.CreateFileW(
        str(parent_path),
        file_list_directory | file_read_attributes | synchronize,
        file_share_read | file_share_write,
        None,
        open_existing,
        file_flag_backup_semantics | file_flag_open_reparse_point,
        None,
    )
    if parent == invalid_handle:
        raise OSError(ctypes.get_last_error(), "cannot open verified R11 parent handle")
    parent_before = native_identity(parent)
    observe("parent_pre", identity=parent_before)
    child = wintypes.HANDLE()
    try:
        buffer = ctypes.create_unicode_buffer(child_name)
        name = UNICODE_STRING(
            len(child_name) * 2,
            (len(child_name) + 1) * 2,
            ctypes.cast(buffer, wintypes.LPWSTR),
        )
        attributes = OBJECT_ATTRIBUTES(
            ctypes.sizeof(OBJECT_ATTRIBUTES),
            parent,
            ctypes.pointer(name),
            obj_case_insensitive | obj_dont_reparse,
            None,
            None,
        )
        iosb = IO_STATUS_BLOCK()
        desired = (
            (file_list_directory if directory else file_write_data)
            | file_read_attributes
            | synchronize
        )
        options = (
            file_open_reparse_point
            | file_synchronous_io_nonalert
            | (file_directory_file if directory else file_non_directory_file)
        )
        observe(
            "create",
            root_directory=getattr(parent, "value", parent),
            child_name=child_name,
            object_attributes=obj_case_insensitive | obj_dont_reparse,
            create_disposition=file_create,
            create_options=options,
        )
        status = ntdll.NtCreateFile(
            ctypes.byref(child),
            desired,
            ctypes.byref(attributes),
            ctypes.byref(iosb),
            None,
            0,
            file_share_read | file_share_write,
            file_create,
            options,
            None,
            0,
        )
        observe("ntstatus", status=status, information=iosb.Information)
        if status < 0 or iosb.Information != file_created:
            error = ntdll.RtlNtStatusToDosError(status)
            if error == 183:
                raise FileExistsError(error, "R11 native child already exists")
            raise OSError(error, "NtCreateFile did not create the required R11 child")
        created_identity = native_identity(child)
        observe("child_created", identity=created_identity)
        if payload is not None:
            written = wintypes.DWORD()
            if not kernel32.WriteFile(
                child, payload, len(payload), ctypes.byref(written), None
            ) or written.value != len(payload):
                raise OSError(
                    ctypes.get_last_error(), "cannot write R11 authority child"
                )
            if not kernel32.FlushFileBuffers(child):
                raise OSError(
                    ctypes.get_last_error(), "cannot flush R11 authority child"
                )
            # Reopen the just-created leaf from the *same* still-open parent
            # handle.  This deliberately avoids an absolute-path readback.
            kernel32.CloseHandle(child)
            child = wintypes.HANDLE()
            reopen_status = ntdll.NtCreateFile(
                ctypes.byref(child),
                file_read_data | file_read_attributes | synchronize,
                ctypes.byref(attributes),
                ctypes.byref(iosb),
                None,
                0,
                file_share_read | file_share_write,
                file_open,
                file_open_reparse_point
                | file_synchronous_io_nonalert
                | file_non_directory_file,
                None,
                0,
            )
            if reopen_status < 0:
                raise OSError(
                    ntdll.RtlNtStatusToDosError(reopen_status),
                    "cannot reopen R11 child through verified parent handle",
                )
            if native_identity(child) != created_identity:
                raise ValueError("R11 reopened child identity drifted")
            if not kernel32.SetFilePointerEx(child, 0, None, 0):
                raise OSError(
                    ctypes.get_last_error(), "cannot rewind R11 authority child"
                )
            readback = ctypes.create_string_buffer(len(payload))
            read = wintypes.DWORD()
            if not kernel32.ReadFile(
                child, readback, len(payload), ctypes.byref(read), None
            ) or read.value != len(payload):
                raise OSError(
                    ctypes.get_last_error(), "cannot read back R11 authority child"
                )
            if (
                hashlib.sha256(readback.raw).digest()
                != hashlib.sha256(payload).digest()
            ):
                raise ValueError("R11 native child readback hash drifted")
        if native_identity(parent) != parent_before:
            raise ValueError("R11 parent handle identity drifted during child creation")
        observe("parent_post", identity=parent_before)
    finally:
        if child.value:
            kernel32.CloseHandle(child)
        kernel32.CloseHandle(parent)


def _native_read_existing_child(parent_path: str | Path, child_name: str) -> bytes:
    """Read one existing authority leaf via NtCreateFile relative to its parent."""

    if os.name != "nt":
        raise NativeSafePathUnavailable("R11 native safe-path read requires Windows")
    if (
        not child_name
        or Path(child_name).name != child_name
        or child_name in {".", ".."}
    ):
        raise ValueError("native safe-path child must be one plain segment")
    import ctypes
    from ctypes import wintypes

    k = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
    invalid_handle = wintypes.HANDLE(-1).value
    file_read_data = 0x0001
    file_read_attributes = 0x0080
    file_list_directory = 0x0001
    synchronize = 0x00100000
    file_share_read = 0x00000001
    file_share_write = 0x00000002
    file_open = file_opened = 1
    file_non_directory_file = 0x00000040
    file_open_reparse_point = 0x00200000
    file_synchronous_io_nonalert = 0x00000020
    file_flag_backup_semantics = 0x02000000
    file_id_info = 18
    file_attribute_tag_info = 9
    file_attribute_reparse_point = 0x0400
    obj_case_insensitive = 0x0040
    obj_dont_reparse = 0x1000

    class UNICODE_STRING(ctypes.Structure):
        _fields_ = [
            ("Length", wintypes.USHORT),
            ("MaximumLength", wintypes.USHORT),
            ("Buffer", wintypes.LPWSTR),
        ]

    class OBJECT_ATTRIBUTES(ctypes.Structure):
        _fields_ = [
            ("Length", wintypes.ULONG),
            ("RootDirectory", wintypes.HANDLE),
            ("ObjectName", ctypes.POINTER(UNICODE_STRING)),
            ("Attributes", wintypes.ULONG),
            ("SecurityDescriptor", wintypes.LPVOID),
            ("SecurityQualityOfService", wintypes.LPVOID),
        ]

    class IO_STATUS_BLOCK(ctypes.Structure):
        _fields_ = [("Status", ctypes.c_long), ("Information", ctypes.c_size_t)]

    class FILE_ID_INFO(ctypes.Structure):
        _fields_ = [
            ("VolumeSerialNumber", wintypes.ULONG),
            ("FileId", ctypes.c_ubyte * 16),
            ("_native_alignment", ctypes.c_ubyte * 4),
        ]

    class FILE_ATTRIBUTE_TAG_INFO(ctypes.Structure):
        _fields_ = [("FileAttributes", wintypes.DWORD), ("ReparseTag", wintypes.DWORD)]

    k.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    k.CreateFileW.restype = wintypes.HANDLE
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    k.CloseHandle.restype = wintypes.BOOL
    k.GetFileInformationByHandleEx.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    k.GetFileInformationByHandleEx.restype = wintypes.BOOL
    k.GetFileSizeEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_longlong)]
    k.GetFileSizeEx.restype = wintypes.BOOL
    k.ReadFile.argtypes = [
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    ]
    k.ReadFile.restype = wintypes.BOOL
    ntdll.NtCreateFile.argtypes = [
        ctypes.POINTER(wintypes.HANDLE),
        wintypes.DWORD,
        ctypes.POINTER(OBJECT_ATTRIBUTES),
        ctypes.POINTER(IO_STATUS_BLOCK),
        ctypes.POINTER(ctypes.c_longlong),
        wintypes.ULONG,
        wintypes.ULONG,
        wintypes.ULONG,
        wintypes.ULONG,
        wintypes.LPVOID,
        wintypes.ULONG,
    ]
    ntdll.NtCreateFile.restype = ctypes.c_long
    ntdll.RtlNtStatusToDosError.argtypes = [ctypes.c_long]
    ntdll.RtlNtStatusToDosError.restype = wintypes.ULONG

    def identity(handle: wintypes.HANDLE) -> tuple[int, bytes, int, int]:
        file_id = FILE_ID_INFO()
        tag = FILE_ATTRIBUTE_TAG_INFO()
        if not k.GetFileInformationByHandleEx(
            handle, file_id_info, ctypes.byref(file_id), ctypes.sizeof(file_id)
        ):
            raise OSError(ctypes.get_last_error(), "cannot capture R11 FileIdInfo")
        if not k.GetFileInformationByHandleEx(
            handle, file_attribute_tag_info, ctypes.byref(tag), ctypes.sizeof(tag)
        ):
            raise OSError(
                ctypes.get_last_error(), "cannot capture R11 AttributeTagInfo"
            )
        if tag.FileAttributes & file_attribute_reparse_point:
            raise ValueError("R11 native read resolves to a reparse point")
        return (
            file_id.VolumeSerialNumber,
            bytes(file_id.FileId),
            tag.FileAttributes,
            tag.ReparseTag,
        )

    parent = k.CreateFileW(
        str(parent_path),
        file_list_directory | file_read_attributes | synchronize,
        file_share_read | file_share_write,
        None,
        3,
        file_flag_backup_semantics | file_open_reparse_point,
        None,
    )
    if parent == invalid_handle:
        raise OSError(ctypes.get_last_error(), "cannot open R11 native read parent")
    child = wintypes.HANDLE()
    try:
        parent_before = identity(parent)
        name_buffer = ctypes.create_unicode_buffer(child_name)
        name = UNICODE_STRING(
            len(child_name.encode("utf-16-le")),
            len(child_name.encode("utf-16-le")) + 2,
            ctypes.cast(name_buffer, wintypes.LPWSTR),
        )
        attributes = OBJECT_ATTRIBUTES(
            ctypes.sizeof(OBJECT_ATTRIBUTES),
            parent,
            ctypes.pointer(name),
            obj_case_insensitive | obj_dont_reparse,
            None,
            None,
        )
        iosb = IO_STATUS_BLOCK()
        status = ntdll.NtCreateFile(
            ctypes.byref(child),
            file_read_data | file_read_attributes | synchronize,
            ctypes.byref(attributes),
            ctypes.byref(iosb),
            None,
            0,
            file_share_read | file_share_write,
            file_open,
            file_non_directory_file
            | file_open_reparse_point
            | file_synchronous_io_nonalert,
            None,
            0,
        )
        if status < 0 or iosb.Information != file_opened:
            raise OSError(
                ntdll.RtlNtStatusToDosError(status),
                "NtCreateFile did not open the required R11 authority child",
            )
        identity(child)
        size = ctypes.c_longlong()
        if not k.GetFileSizeEx(child, ctypes.byref(size)) or size.value < 0:
            raise OSError(ctypes.get_last_error(), "cannot size R11 authority child")
        remaining = size.value
        chunks: list[bytes] = []
        while remaining:
            requested = min(remaining, 1024 * 1024)
            buffer = ctypes.create_string_buffer(requested)
            read = wintypes.DWORD()
            if not k.ReadFile(child, buffer, requested, ctypes.byref(read), None):
                raise OSError(
                    ctypes.get_last_error(), "cannot read R11 authority child"
                )
            if not read.value:
                raise OSError("short read of R11 authority child")
            chunks.append(buffer.raw[: read.value])
            remaining -= read.value
        if identity(parent) != parent_before:
            raise ValueError("R11 parent handle identity drifted during child read")
        return b"".join(chunks)
    finally:
        if child.value:
            k.CloseHandle(child)
        k.CloseHandle(parent)


def _source_manifest_authority_payload(
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the context-invariant R24 source authority projection."""

    return {
        "schema_version": manifest.get("schema_version"),
        "allowlist": manifest.get("allowlist"),
        "files": manifest.get("files"),
    }


def _source_manifest_authority_valid(manifest: Any) -> bool:
    """Validate exact R24 source authority plus process-local observations."""

    if not isinstance(manifest, Mapping):
        return False
    exact_keys = {
        "schema_version",
        "allowlist",
        "files",
        "source_manifest_authority_sha256",
        "observed_workspace_imports",
    }
    allowlist = manifest.get("allowlist")
    files = manifest.get("files")
    observed = manifest.get("observed_workspace_imports")
    return (
        set(manifest) == exact_keys
        and manifest.get("schema_version")
        == IMPLEMENTED_SCHEMA_VERSIONS["source_manifest"]
        and isinstance(allowlist, list)
        and allowlist == list(SOURCE_ALLOWLIST)
        and isinstance(files, Mapping)
        and set(files) == set(SOURCE_ALLOWLIST)
        and list(files) == allowlist
        and all(_sha256_like(value) for value in files.values())
        and isinstance(observed, list)
        and all(type(path) is str for path in observed)
        and observed == sorted(observed)
        and len(observed) == len(set(observed))
        and set(observed) <= set(allowlist)
        and manifest.get("source_manifest_authority_sha256")
        == _json_hash(_source_manifest_authority_payload(manifest))
    )


def _source_manifest_authority_matches_expected(
    observed: Any,
    expected: Any,
) -> bool:
    """Compare only context-invariant authority after validating both domains."""

    return (
        _source_manifest_authority_valid(observed)
        and _source_manifest_authority_valid(expected)
        and observed.get("allowlist") == expected.get("allowlist")
        and observed.get("files") == expected.get("files")
        and observed.get("source_manifest_authority_sha256")
        == expected.get("source_manifest_authority_sha256")
    )


def _source_manifest() -> dict[str, Any]:
    workspace_resolved = WORKSPACE.resolve()
    paths: dict[str, Path] = {}
    for relative in SOURCE_ALLOWLIST:
        relative_path = Path(relative)
        if (
            "\\" in relative
            or relative_path.is_absolute()
            or any(part in {"", ".", ".."} for part in relative_path.parts)
            or relative_path.as_posix() != relative
        ):
            raise RuntimeError(f"invalid R10 source allowlist path: {relative!r}")
        candidate = WORKSPACE / relative_path
        if not candidate.is_file():
            raise FileNotFoundError(f"R10 source manifest is incomplete: {relative}")
        try:
            candidate.resolve().relative_to(workspace_resolved)
        except (OSError, ValueError) as error:
            raise RuntimeError(
                f"R10 source path resolves outside workspace: {relative}"
            ) from error
        cursor = candidate
        while True:
            try:
                attributes = getattr(
                    os.stat(cursor, follow_symlinks=False), "st_file_attributes", 0
                )
            except OSError as error:
                raise RuntimeError(
                    f"cannot lstat R10 source path: {relative}"
                ) from error
            is_junction = bool(getattr(cursor, "is_junction", lambda: False)())
            if (
                cursor.is_symlink()
                or is_junction
                or bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
            ):
                raise RuntimeError(
                    f"R10 source manifest forbids symlink/junction/reparse path: {relative}"
                )
            if cursor == WORKSPACE:
                break
            cursor = cursor.parent
        paths[relative] = candidate
    observed_imports: set[str] = set()
    for module in tuple(sys.modules.values()):
        module_file = getattr(module, "__file__", None)
        if not module_file:
            continue
        candidate = Path(module_file)
        if not candidate.is_absolute() or not candidate.is_file():
            continue
        try:
            relative = candidate.resolve().relative_to(workspace_resolved)
        except (OSError, ValueError):
            continue
        observed_imports.add(relative.as_posix())
    unexpected_python = sorted(observed_imports - set(SOURCE_ALLOWLIST))
    if unexpected_python:
        raise RuntimeError(
            "R10 closed source allowlist rejects imported workspace files: "
            f"{unexpected_python}"
        )
    files = {relative: _file_hash(paths[relative]) for relative in SOURCE_ALLOWLIST}
    authority_payload = {
        "schema_version": IMPLEMENTED_SCHEMA_VERSIONS["source_manifest"],
        "allowlist": list(SOURCE_ALLOWLIST),
        "files": files,
    }
    return {
        **authority_payload,
        "source_manifest_authority_sha256": _json_hash(authority_payload),
        "observed_workspace_imports": sorted(observed_imports),
    }


def _freeze_record_validation(
    source_manifest: Mapping[str, Any],
    implementation_observation: Mapping[str, Any],
) -> dict[str, bool]:
    """Recompute every non-self-referential R10 freeze projection."""

    record = FROZEN_R6_REGISTRY.get("freeze_record")
    requirements = FROZEN_R6_REGISTRY.get("freeze_requirements", {})
    required_hash_fields = requirements.get("required_hash_fields", [])
    expected_key_order = [
        "schema_version",
        "canonicalization",
        "registry_projection_excluded_json_pointers",
        "closed_manifest_excluded_paths",
        *required_hash_fields,
    ]
    record_is_mapping = isinstance(record, Mapping)
    record_map = record if record_is_mapping else {}
    files = source_manifest.get("files")
    files_map = files if isinstance(files, Mapping) else {}
    nonprotocol_paths = [
        path for path in SOURCE_ALLOWLIST if path != _R10_PROTOCOL_RELATIVE_PATH
    ]
    nonprotocol_manifest_projection = {
        "allowlist": nonprotocol_paths,
        "files": {path: files_map.get(path) for path in nonprotocol_paths},
    }
    registry_projection = copy.deepcopy(FROZEN_R6_REGISTRY)
    registry_projection.pop("freeze_record", None)
    expected_observation = FROZEN_R6_REGISTRY.get("implementation_observation_expected")

    checks = {
        "freeze_record_present": record_is_mapping,
        "freeze_record_keys_exact": record_is_mapping
        and list(record_map) == expected_key_order,
        "freeze_record_schema_exact": record_map.get("schema_version")
        == IMPLEMENTED_SCHEMA_VERSIONS["freeze_record"],
        "freeze_record_canonicalization_exact": record_map.get("canonicalization")
        == "utf8_json_sort_keys_compact_ascii_no_nan_v1",
        "freeze_record_registry_projection_exact": record_map.get(
            "registry_projection_excluded_json_pointers"
        )
        == ["/freeze_record"],
        "freeze_record_manifest_projection_exact": record_map.get(
            "closed_manifest_excluded_paths"
        )
        == [_R10_PROTOCOL_RELATIVE_PATH],
        "freeze_record_required_hash_fields_exact": isinstance(
            required_hash_fields, list
        )
        and required_hash_fields
        == [
            "protocol_candidate_sha256",
            "implementation_observation_sha256",
            *tuple(_FREEZE_RECORD_SOURCE_FIELDS)[:-3],
            "closed_manifest_sha256",
            "canonical_registry_sha256",
            "structural_audit_sha256",
            "structural_audit_tests_sha256",
            "summary_roundtrip_tests_sha256",
        ],
        "freeze_record_candidate_hash_well_formed": _sha256_like(
            record_map.get("protocol_candidate_sha256")
        ),
        "freeze_record_observation_hash_exact": record_map.get(
            "implementation_observation_sha256"
        )
        == _json_hash(expected_observation),
        "freeze_record_live_observation_hash_exact": record_map.get(
            "implementation_observation_sha256"
        )
        == _json_hash(implementation_observation),
        "freeze_record_closed_manifest_hash_exact": record_map.get(
            "closed_manifest_sha256"
        )
        == _json_hash(nonprotocol_manifest_projection),
        "freeze_record_registry_hash_exact": record_map.get("canonical_registry_sha256")
        == _json_hash(registry_projection),
    }
    checks.update(
        {
            f"freeze_record_{field}_exact": record_map.get(field) == files_map.get(path)
            for field, path in _FREEZE_RECORD_SOURCE_FIELDS.items()
        }
    )
    return checks


def _runtime_environment() -> dict[str, Any]:
    local_now = datetime.now().astimezone()
    torch_build = torch.__config__.show()
    locale_values = locale.localeconv()
    environment_allowlist = FROZEN_R6_REGISTRY["runtime_contract"][
        "secret_safe_environment_allowlist"
    ]
    return {
        "python": platform.python_version(),
        "python_executable": str(Path(sys.executable).resolve()),
        "platform": platform.platform(),
        "torch": torch.__version__,
        "torch_build_sha256": hashlib.sha256(torch_build.encode("utf-8")).hexdigest(),
        "torch_cuda_build": torch.version.cuda,
        "torch_num_threads": torch.get_num_threads(),
        "torch_num_interop_threads": torch.get_num_interop_threads(),
        "deterministic_algorithms_enabled": torch.are_deterministic_algorithms_enabled(),
        "deterministic_debug_mode": int(torch.get_deterministic_debug_mode()),
        "deterministic_debug_mode_name": {
            0: "default",
            1: "warn",
            2: "error",
        }.get(int(torch.get_deterministic_debug_mode()), "unknown"),
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
        "mkl_num_threads": os.environ.get("MKL_NUM_THREADS"),
        "locale_lc_all": locale.setlocale(locale.LC_ALL, None),
        "locale_preferred_encoding": locale.getpreferredencoding(False),
        "filesystem_encoding": sys.getfilesystemencoding(),
        "stdin_encoding": getattr(sys.stdin, "encoding", None),
        "stdout_encoding": getattr(sys.stdout, "encoding", None),
        "stderr_encoding": getattr(sys.stderr, "encoding", None),
        "locale_decimal_point": locale_values.get("decimal_point"),
        "locale_thousands_separator": locale_values.get("thousands_sep"),
        "timezone_name": local_now.tzname(),
        "timezone_offset": local_now.strftime("%z"),
        "cwd": str(Path.cwd().resolve()),
        "hostname": platform.node(),
        "cuda_available": torch.cuda.is_available(),
        "cudnn_benchmark": bool(torch.backends.cudnn.benchmark),
        "cudnn_deterministic": bool(torch.backends.cudnn.deterministic),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "slurm_step_id": os.environ.get("SLURM_STEP_ID"),
        "parent_pid": os.getppid(),
        "environment_allowlist": {
            name: os.environ.get(name) for name in environment_allowlist
        },
    }


def _mapping_plan(batch: R5ChallengeBatch) -> MatchPlan:
    batch.validate()
    batch_size, prior_count, _ = batch.regions.prior_features.shape
    current_count = batch.regions.current_features.shape[1]
    transport = batch.regions.prior_features.new_zeros(
        (batch_size, prior_count + 1, current_count + 1)
    )
    rows = torch.arange(prior_count).expand(batch_size, -1)
    cases = torch.arange(batch_size).unsqueeze(-1).expand_as(rows)
    transport[cases, rows, batch.oracle.gold_mapping] = 1.0
    plan = MatchPlan(transport=transport, mode="r5_challenge_hidden_oracle")
    plan.validate_hard(batch.regions)
    return plan


def _as_query_anchor(
    *,
    regions: Any,
    plan: MatchPlan,
    labels: Tensor,
    prelabel_group: Tensor,
    require_null_carriers: bool,
) -> QueryAnchorBatch:
    """Adapt an R5 gold-only fixture to the existing post-transport mediator API."""

    batch_size, prior_count, _ = regions.prior_features.shape
    current_count = regions.current_features.shape[1]
    prior_marker = regions.prior_features[..., 0].bool()
    current_marker = regions.current_features[..., 0].bool()
    prior_carrier = torch.zeros_like(prior_marker)
    current_carrier = torch.zeros_like(current_marker)
    if require_null_carriers:
        death = plan.transport[:, :prior_count, current_count]
        birth = plan.transport[:, prior_count, :current_count]
        for case in range(batch_size):
            death_indices = torch.nonzero(death[case] > 0.5).flatten()
            birth_indices = torch.nonzero(birth[case] > 0.5).flatten()
            prior_index = (
                int(torch.nonzero(prior_marker[case]).item())
                if int(labels[case]) == 4
                else int(death_indices[0].item())
            )
            current_index = (
                int(torch.nonzero(current_marker[case]).item())
                if int(labels[case]) == 3
                else int(birth_indices[0].item())
            )
            prior_carrier[case, prior_index] = True
            current_carrier[case, current_index] = True
    else:
        # The challenge is persistent-only and deliberately has no null endpoints.
        # These neutral reserved positions are not consumed by its mediator path.
        prior_carrier[:, -1] = True
        current_carrier[:, -1] = True
    prior_gold = torch.arange(prior_count, dtype=torch.long).unsqueeze(0) + 1000 * (
        torch.arange(batch_size, dtype=torch.long).unsqueeze(1) + 1
    )
    current_gold = (
        torch.arange(current_count, dtype=torch.long).unsqueeze(0)
        + 1000 * (torch.arange(batch_size, dtype=torch.long).unsqueeze(1) + 1)
        + 500
    )
    real = plan.transport[:, :prior_count, :current_count]
    for case in range(batch_size):
        for prior_index in range(prior_count):
            hits = torch.nonzero(real[case, prior_index] > 0.5).flatten()
            if len(hits) == 1:
                current_gold[case, int(hits.item())] = prior_gold[case, prior_index]
    result = QueryAnchorBatch(
        regions=regions,
        prior_query_marker=prior_marker,
        current_query_marker=current_marker,
        prior_carrier_control=prior_carrier,
        current_carrier_control=current_carrier,
        counterbalance_index=prelabel_group.remainder(3),
        oracle=HiddenQueryOracle(
            prior_gold_ids=prior_gold,
            current_gold_ids=current_gold,
            labels=labels,
            plan=plan,
        ),
    )
    if require_null_carriers:
        result.validate()
    else:
        result.regions.validate()
        result.oracle.validate(result.regions)
    return result


def _challenge_as_query_anchor(batch: R5ChallengeBatch) -> QueryAnchorBatch:
    batch.validate()
    return _as_query_anchor(
        regions=batch.regions,
        plan=_mapping_plan(batch),
        labels=batch.oracle.labels,
        prelabel_group=batch.oracle.prelabel_group,
        require_null_carriers=False,
    )


def _clean_as_query_anchor(batch: R5CleanBatch) -> QueryAnchorBatch:
    batch.validate()
    return _as_query_anchor(
        regions=batch.regions,
        plan=batch.oracle.plan,
        labels=batch.oracle.labels,
        prelabel_group=batch.oracle.prelabel_group,
        require_null_carriers=True,
    )


def _build_strata(
    splits: Sequence[str] = SPLIT_NAMES,
) -> tuple[
    dict[str, dict[str, QueryAnchorBatch]],
    dict[str, R5CleanBatch],
    dict[str, R5ChallengeBatch],
]:
    requested = tuple(splits)
    if not requested or any(split not in SPLIT_NAMES for split in requested):
        raise ValueError(f"splits must be a non-empty subset of {SPLIT_NAMES}")
    raw_clean = {split: make_frozen_r5_clean_split(split) for split in requested}
    raw_challenge = {
        split: make_frozen_r5_challenge_split(split) for split in requested
    }
    clean = {split: _clean_as_query_anchor(batch) for split, batch in raw_clean.items()}
    challenge = {
        split: _challenge_as_query_anchor(batch)
        for split, batch in raw_challenge.items()
    }
    return {"clean": clean, "challenge": challenge}, raw_clean, raw_challenge


def _build_audit_fixtures() -> tuple[
    dict[str, QueryAnchorBatch], dict[str, R5CleanBatch | R5ChallengeBatch]
]:
    clean_raw = make_r5_clean_batch(
        counterbalance_groups=2,
        seed=int(
            FROZEN_R5_REGISTRY["audit_fixture_seeds"]["clean_fixture_development"]
        ),
    )
    challenge_raw = make_r5_anti_equivalence_challenge(
        counterbalance_groups=2,
        seed=int(
            FROZEN_R5_REGISTRY["audit_fixture_seeds"]["challenge_fixture_development"]
        ),
    )
    return {
        "clean": _clean_as_query_anchor(clean_raw),
        "challenge": _challenge_as_query_anchor(challenge_raw),
    }, {"clean": clean_raw, "challenge": challenge_raw}


def _raw_fixture_hashes(raw: R5CleanBatch | R5ChallengeBatch) -> dict[str, str]:
    visible = r4_visible_hash(raw.regions)
    if isinstance(raw, R5CleanBatch):
        return {
            "visible": visible,
            "hidden_oracle": r5_clean_hidden_oracle_hash(raw.oracle),
        }
    hidden = r5_challenge_hidden_oracle_hash(raw.oracle)
    return {
        "visible": visible,
        "hidden_oracle": hidden,
        "full_fixture": hashlib.sha256(
            f"{visible}:{hidden}".encode("ascii")
        ).hexdigest(),
    }


def _access_ledger_entry(
    *,
    gate: str,
    stratum: str,
    split: str,
    name: str,
    purpose: str,
    content_hash: str,
    cache_hit: bool,
) -> dict[str, Any]:
    return {
        "schema_version": FROZEN_R6_REGISTRY["schema_versions"]["data_access_ledger"],
        "gate": gate,
        "stratum": stratum,
        "split": split,
        "name": name,
        "purpose": purpose,
        "content_sha256": content_hash,
        "cache_hit": bool(cache_hit),
    }


class _R6SplitAccessor:
    """Single fail-closed data boundary; every return has a prior ledger row."""

    _ACCESS_SEQUENCE = {
        "structural_input": (
            ("clean", "literal_audit_fixture"),
            ("challenge", "literal_audit_fixture"),
        ),
        "fixture_identifiability": (
            ("clean", "frozen_fixture_audit"),
            ("challenge", "frozen_fixture_audit"),
        ),
        "transport_competence": (
            ("clean", "train"),
            ("challenge", "train"),
            ("clean", "inner_development"),
            ("challenge", "inner_development"),
            ("clean", "development"),
        ),
        "anti_equivalence": (("challenge", "development"),),
        "mediator_recovery": (
            ("clean", "train"),
            ("clean", "development"),
            ("challenge", "train"),
            ("challenge", "development"),
        ),
        "fair_baseline": (
            ("clean", "train"),
            ("clean", "development"),
            ("challenge", "train"),
            ("challenge", "development"),
        ),
    }
    _AUTHORIZED = {gate: set(accesses) for gate, accesses in _ACCESS_SEQUENCE.items()}

    def __init__(self) -> None:
        self.ledger: list[dict[str, Any]] = []
        self._audit_cache: (
            tuple[
                dict[str, QueryAnchorBatch],
                dict[str, R5CleanBatch | R5ChallengeBatch],
            ]
            | None
        ) = None
        self._registered_cache: dict[
            tuple[str, str], tuple[QueryAnchorBatch, R5CleanBatch | R5ChallengeBatch]
        ] = {}

    def audit(
        self, *, gate: str, split: str, purpose: str
    ) -> tuple[
        dict[str, QueryAnchorBatch],
        dict[str, R5CleanBatch | R5ChallengeBatch],
    ]:
        if any(
            (stratum, split) not in self._AUTHORIZED.get(gate, set())
            for stratum in STRATA
        ):
            raise RuntimeError(
                f"unauthorized R6 audit access: gate={gate}, split={split}"
            )
        cache_hit = self._audit_cache is not None
        if self._audit_cache is None:
            self._audit_cache = _build_audit_fixtures()
        batches, raw = self._audit_cache
        pending = [
            _access_ledger_entry(
                gate=gate,
                stratum=stratum,
                split=split,
                name=f"{stratum}_{split}",
                purpose=purpose,
                content_hash=_raw_fixture_hashes(raw[stratum])["visible"],
                cache_hit=cache_hit,
            )
            for stratum in STRATA
        ]
        self.ledger.extend(pending)
        return batches, raw

    def registered(
        self, *, gate: str, stratum: str, split: str, purpose: str
    ) -> tuple[QueryAnchorBatch, R5CleanBatch | R5ChallengeBatch]:
        if (stratum, split) not in self._AUTHORIZED.get(gate, set()):
            raise RuntimeError(
                f"unauthorized R6 registered access: gate={gate}, stratum={stratum}, split={split}"
            )
        key = (stratum, split)
        cache_hit = key in self._registered_cache
        if not cache_hit:
            if stratum == "clean":
                raw: R5CleanBatch | R5ChallengeBatch = make_frozen_r5_clean_split(split)
                batch = _clean_as_query_anchor(raw)
            elif stratum == "challenge":
                raw = make_frozen_r5_challenge_split(split)
                batch = _challenge_as_query_anchor(raw)
            else:
                raise RuntimeError(f"unknown R6 stratum: {stratum}")
            self._registered_cache[key] = (batch, raw)
        batch, raw = self._registered_cache[key]
        self.ledger.append(
            _access_ledger_entry(
                gate=gate,
                stratum=stratum,
                split=split,
                name=f"{stratum}_{split}",
                purpose=purpose,
                content_hash=_raw_fixture_hashes(raw)["visible"],
                cache_hit=cache_hit,
            )
        )
        return batch, raw


def _r4_split_manifest(
    strata: Mapping[str, Mapping[str, QueryAnchorBatch]],
    raw_clean: Mapping[str, R5CleanBatch],
    raw_challenge: Mapping[str, R5ChallengeBatch],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for stratum in STRATA:
        result[stratum] = {}
        for split in strata[stratum]:
            manifest = _split_manifest(strata[stratum][split])
            if stratum == "clean":
                raw = raw_clean[split]
                hash_evidence = {
                    "visible": r4_visible_hash(raw.regions),
                    "hidden_oracle": r5_clean_hidden_oracle_hash(raw.oracle),
                }
                manifest = {
                    **manifest,
                    "prelabel_group_sha256": _tensor_hash(raw.oracle.prelabel_group),
                    "fixture_hash_evidence": hash_evidence,
                    "raw_audit_sha256": _json_hash(hash_evidence),
                }
            else:
                raw = raw_challenge[split]
                visible_hash = r4_visible_hash(raw.regions)
                hidden_hash = r5_challenge_hidden_oracle_hash(raw.oracle)
                hash_evidence = {
                    "visible": visible_hash,
                    "hidden_oracle": hidden_hash,
                    "full_fixture": hashlib.sha256(
                        f"{visible_hash}:{hidden_hash}".encode("ascii")
                    ).hexdigest(),
                }
                manifest = {
                    **manifest,
                    "distractor_mapping_sha256": _tensor_hash(
                        raw.oracle.distractor_mapping
                    ),
                    "prelabel_group_sha256": _tensor_hash(raw.oracle.prelabel_group),
                    "fixture_hash_evidence": hash_evidence,
                    "raw_audit_sha256": _json_hash(hash_evidence),
                }
            result[stratum][split] = manifest
    return result


def _registered_config(
    *, seeds: Sequence[int], actual_steps: int, smoke: bool, dry_run: bool
) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_class": EVIDENCE_CLASS,
        "strata": {
            "clean": {
                "generator": "r5_simplex_two_view_partial_transport_clean",
                "split_seeds": dict(FROZEN_R5_CLEAN_SPLIT_SEEDS),
                "counterbalance_groups": dict(FROZEN_R5_COUNTERBALANCE_GROUPS),
                "identity_view_slices": [list(view) for view in IDENTITY_VIEW_SLICES],
            },
            "challenge": {
                "generator": "r5_two_view_anti_equivalence_global_competition",
                "split_seeds": dict(FROZEN_R5_CHALLENGE_SPLIT_SEEDS),
                "counterbalance_groups": dict(FROZEN_R5_COUNTERBALANCE_GROUPS),
                "identity_view_slices": [list(view) for view in IDENTITY_VIEW_SLICES],
                "learned_feasible_view_weights": list(LEARNED_FEASIBLE_VIEW_WEIGHTS),
            },
        },
        "trainable_seeds": list(seeds),
        "derangement_seeds": list(REGISTERED_DERANGEMENT_SEEDS),
        "registered_steps": REGISTERED_STEPS,
        "actual_steps": actual_steps,
        "feature_dim": FEATURE_DIM,
        "transport": {
            "matcher": "InvariantPartialOTMatcher",
            "identity_views": [list(view) for view in IDENTITY_VIEW_SLICES],
            "residual_cap": RESIDUAL_CAP,
            "null_utility_cap": NULL_UTILITY_CAP,
            "sinkhorn_temperature": SINKHORN_TEMPERATURE,
            "sinkhorn_iterations": SINKHORN_ITERATIONS,
            "feasibility_tolerance": FEASIBILITY_TOLERANCE,
            "optimizer": "AdamW",
            "learning_rate": TRANSPORT_LEARNING_RATE,
            "weight_decay": 0.0,
            "gradient_clip_norm": GRADIENT_CLIP_NORM,
            "loss": "mean_stratum_full_oracle_transport_nll",
            "checkpoint_rule": "final_step_only_no_best_checkpoint",
            "query_label_gradients": False,
            "initialization": copy.deepcopy(FROZEN_R5_REGISTRY["initialization"]),
        },
        "mediator": {
            "oracle_readout_fit_count_per_seed": 1,
            "optimizer": "AdamW",
            "learning_rate": MEDIATOR_LEARNING_RATE,
            "weight_decay": 0.0,
            "query_raw_dim": QUERY_RAW_DIM,
            "query_hidden_size": QUERY_HIDDEN_SIZE,
            "frozen_adapter_seed": FROZEN_READOUT_SEED,
            "exact_placeholder_count": 64,
            "matcher_frozen": True,
        },
        "margin_certificate": {
            "authority_symbol": FROZEN_R5_REGISTRY["enumerator_authority"]["symbol"],
            "canonical_certificate_sha256": FROZEN_R5_REGISTRY["enumerator_authority"][
                "canonical_certificate_sha256"
            ],
            "registered_minimum_robust_gap": FROZEN_R5_REGISTRY["enumerator_authority"][
                "registered_minimum_robust_gap"
            ],
            "passed": True,
            "runtime_recomputation_gate": "structural_input",
        },
        "thresholds": copy.deepcopy(FROZEN_R5_REGISTRY["thresholds"]),
        "competence_probe": {
            "train_seed": COMPETENCE_TRAIN_SEED,
            "development_seed": COMPETENCE_DEVELOPMENT_SEED,
            "model_seed_offset": COMPETENCE_SEED_OFFSET,
            "signal_channels": list(COMPETENCE_SIGNAL_CHANNELS),
            "signal_amplitude": COMPETENCE_SIGNAL_AMPLITUDE,
        },
        "formal_test": "SEALED",
        "formal_data_authorization": "HOLD",
        "device": "cpu",
        "smoke": bool(smoke),
        "dry_run": bool(dry_run),
        "summary_schema_version": SUMMARY_SCHEMA_VERSION,
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "resolver_schema_version": RESOLVER_SCHEMA_VERSION,
        "protocol_authority": {
            "sole_authority": _R10_PROTOCOL_RELATIVE_PATH,
            "authority_state": FROZEN_R6_REGISTRY["authority_state"],
            "protocol_sha256": R10_PROTOCOL_SHA256,
            "registry_sha256": _json_hash(FROZEN_R6_REGISTRY),
            "machine_registry": copy.deepcopy(FROZEN_R6_REGISTRY),
            "base_dependency": copy.deepcopy(FROZEN_R6_REGISTRY["base_dependency"]),
        },
    }


def _new_matcher(seed: int | None = None) -> InvariantPartialOTMatcher:
    # Construction may consume the global RNG even though registered literals
    # are loaded immediately afterward.  Isolate that implementation detail so
    # seed evidence is independent of caller RNG state.
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(0)
        matcher = InvariantPartialOTMatcher(
            FEATURE_DIM,
            identity_views=IDENTITY_VIEW_SLICES,
            residual_cap=RESIDUAL_CAP,
            null_utility_cap=NULL_UTILITY_CAP,
            temperature=SINKHORN_TEMPERATURE,
            sinkhorn_iterations=SINKHORN_ITERATIONS,
            feasibility_tolerance=FEASIBILITY_TOLERANCE,
        )
    if seed is None:
        return matcher
    try:
        frozen_values = FROZEN_R5_REGISTRY["initialization"]["literal_values"][
            str(int(seed))
        ]
    except KeyError as error:
        raise ValueError(f"seed {seed} has no frozen R5 initialization") from error
    values = torch.tensor(frozen_values, dtype=torch.float32)
    with torch.no_grad():
        matcher.residual_coefficient.copy_(values[0])
        matcher.view_weight_logits.copy_(values[1:3])
        matcher.prior_null_utility.copy_(values[3])
        matcher.current_null_utility.copy_(values[4])
    return matcher


def _r6_named_tensor_bytes(name: str, value: Tensor) -> bytes:
    """Canonical R6 tensor encoding pinned by the initialization contract."""

    tensor = value.detach().cpu().contiguous()
    payload = bytearray(name.encode("utf-8"))
    payload.extend(b"\0")
    for dimension in tensor.shape:
        payload.extend(struct.pack("<q", int(dimension)))
    payload.extend(str(tensor.dtype).encode("utf-8"))
    payload.extend(b"\0")
    payload.extend(tensor.numpy().tobytes(order="C"))
    return bytes(payload)


def _r6_named_tensor_hash(name: str, value: Tensor) -> str:
    return hashlib.sha256(_r6_named_tensor_bytes(name, value)).hexdigest()


def _r6_state_hash(values: Mapping[str, Tensor]) -> str:
    digest = hashlib.sha256()
    for name, value in values.items():
        digest.update(_r6_named_tensor_bytes(name, value))
    return digest.hexdigest()


def _r8_runtime_state_hash_from_literal_bytes(literal_bytes: bytes) -> str:
    """Rebuild the matcher's runtime ``state_dict`` hash without model access.

    The five registered scalar literals use a different canonical encoding from
    the four tensors in the runtime module state.  Keep both hash domains and
    reconstruct the latter from the literal bytes instead of comparing the two.
    """

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


def _initialization_evidence(
    seed: int, matcher: InvariantPartialOTMatcher
) -> dict[str, Any]:
    flattened = torch.cat(
        (
            matcher.residual_coefficient.detach().reshape(1),
            matcher.view_weight_logits.detach().reshape(-1),
            matcher.prior_null_utility.detach().reshape(1),
            matcher.current_null_utility.detach().reshape(1),
        )
    ).contiguous()
    literal_bytes = flattened.cpu().numpy().astype("<f4", copy=False).tobytes(order="C")
    observed_literal_sha256 = hashlib.sha256(literal_bytes).hexdigest()
    raw_values = {
        "residual_coefficient": matcher.residual_coefficient.detach().reshape(()),
        "view_weight_logits.0": matcher.view_weight_logits.detach()[0].reshape(()),
        "view_weight_logits.1": matcher.view_weight_logits.detach()[1].reshape(()),
        "prior_null_utility_raw": matcher.prior_null_utility.detach().reshape(()),
        "current_null_utility_raw": matcher.current_null_utility.detach().reshape(()),
    }
    effective_prior, effective_current = matcher.effective_null_utilities()
    effective_view_weights = torch.softmax(matcher.view_weight_logits.detach(), dim=0)
    effective_values = {
        "residual_coefficient_effective": (
            RESIDUAL_CAP * torch.tanh(matcher.residual_coefficient.detach())
        ).reshape(()),
        "view_weights_effective.0": effective_view_weights[0].reshape(()),
        "view_weights_effective.1": effective_view_weights[1].reshape(()),
        "prior_null_utility_effective": effective_prior.detach().reshape(()),
        "current_null_utility_effective": effective_current.detach().reshape(()),
    }
    parameter_hashes = {
        name: _r6_named_tensor_hash(name, value) for name, value in raw_values.items()
    }
    raw_state_sha256 = _r6_state_hash(raw_values)
    effective_state_sha256 = _r6_state_hash(effective_values)
    runtime_state = matcher.state_dict()
    runtime_parameter_order = sorted(runtime_state)
    runtime_shapes = {
        name: list(runtime_state[name].shape) for name in runtime_parameter_order
    }
    runtime_dtypes = {
        str(runtime_state[name].dtype) for name in runtime_parameter_order
    }
    runtime_dtype = next(iter(runtime_dtypes)) if len(runtime_dtypes) == 1 else "mixed"
    runtime_initial_state_sha256 = _state_hash(matcher)
    reconstructed_runtime_sha256 = _r8_runtime_state_hash_from_literal_bytes(
        literal_bytes
    )
    expected = (
        FROZEN_R6_REGISTRY.get("initialization_evidence_contract", {})
        .get("expected_seed_evidence", {})
        .get(str(int(seed)), {})
    )
    protocol_values = FROZEN_R5_REGISTRY["initialization"]["literal_values"][
        str(int(seed))
    ]
    checks = {
        "literal_vector_hash_exact": observed_literal_sha256
        == FROZEN_R5_REGISTRY["initialization"]["literal_vector_sha256"][
            str(int(seed))
        ],
        "protocol_literal_values_exact": flattened.tolist() == protocol_values,
        "parameter_order_exact": list(raw_values)
        == FROZEN_R6_REGISTRY["initialization_evidence_contract"]["parameter_order"],
        "per_parameter_hashes_exact": parameter_hashes
        == expected.get("per_parameter_tensor_sha256"),
        "raw_state_hash_exact": raw_state_sha256
        == expected.get("raw_initial_state_sha256"),
        "effective_state_hash_exact": effective_state_sha256
        == expected.get("effective_initial_state_sha256"),
        "runtime_state_metadata_exact": runtime_parameter_order
        == [
            "current_null_utility",
            "prior_null_utility",
            "residual_coefficient",
            "view_weight_logits",
        ]
        and runtime_shapes
        == {
            "current_null_utility": [],
            "prior_null_utility": [],
            "residual_coefficient": [],
            "view_weight_logits": [2],
        }
        and runtime_dtype == "torch.float32",
        "runtime_state_hash_exact": runtime_initial_state_sha256
        == reconstructed_runtime_sha256,
        "absolute_literal_bound_passed": bool(
            flattened.abs().max()
            <= FROZEN_R5_REGISTRY["initialization"]["absolute_literal_bound"]
        ),
    }
    return {
        "schema_version": FROZEN_R6_REGISTRY["schema_versions"]["initialization"],
        "seed": int(seed),
        "distribution": "normal",
        "std": INITIALIZATION_STD,
        "generator": "torch.Generator(device=cpu).manual_seed(seed)",
        "runtime_rule": "load_frozen_literals_do_not_redraw",
        "literal_vector_sha256": FROZEN_R5_REGISTRY["initialization"][
            "literal_vector_sha256"
        ][str(int(seed))],
        "observed_literal_vector_sha256": observed_literal_sha256,
        "literal_values": flattened.tolist(),
        "literal_float32_little_endian_hex": literal_bytes.hex(),
        "parameter_order": list(raw_values),
        "runtime_parameter_name_mapping": {
            "residual_coefficient": "residual_coefficient",
            "view_weight_logits.0": "view_weight_logits[0]",
            "view_weight_logits.1": "view_weight_logits[1]",
            "prior_null_utility_raw": "prior_null_utility",
            "current_null_utility_raw": "current_null_utility",
        },
        "raw_values": {name: float(value) for name, value in raw_values.items()},
        "effective_values": {
            name: float(value) for name, value in effective_values.items()
        },
        "per_parameter_tensor_sha256": parameter_hashes,
        "raw_initial_state_sha256": raw_state_sha256,
        "effective_initial_state_sha256": effective_state_sha256,
        "runtime_state_dict_parameter_order": runtime_parameter_order,
        "runtime_state_dict_shapes": runtime_shapes,
        "runtime_state_dict_dtype": runtime_dtype,
        "runtime_initial_state_sha256": runtime_initial_state_sha256,
        "expected_seed_evidence": copy.deepcopy(expected),
        "checks": checks,
        "passed": all(checks.values()),
        "state_sha256": raw_state_sha256,
    }


def _validate_finite_tree(value: Any, path: str = "$") -> list[str]:
    """Return JSON paths containing non-finite numeric values."""

    errors: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            errors.extend(_validate_finite_tree(item, f"{path}.{key}"))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            errors.extend(_validate_finite_tree(item, f"{path}[{index}]"))
    elif isinstance(value, float) and not math.isfinite(value):
        errors.append(path)
    return errors


def _required_none_paths(value: Any, path: str = "$") -> list[str]:
    """Reject ``None`` in canonical config while allowing no implicit skips."""

    errors: list[str] = []
    if value is None:
        errors.append(path)
    elif isinstance(value, Mapping):
        for key, item in value.items():
            errors.extend(_required_none_paths(item, f"{path}.{key}"))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            errors.extend(_required_none_paths(item, f"{path}[{index}]"))
    return errors


def _validate_exact_keys(
    value: Any, expected: set[str], *, path: str
) -> list[dict[str, Any]]:
    if not isinstance(value, Mapping):
        return [{"path": path, "expected": "object", "observed": type(value).__name__}]
    observed = set(value)
    if observed == expected:
        return []
    return [
        {
            "path": path,
            "expected_keys": sorted(expected),
            "observed_keys": sorted(observed),
            "missing": sorted(expected - observed),
            "unknown": sorted(observed - expected),
        }
    ]


def _validate_scalar_type(
    value: Any, expected: type, *, path: str
) -> list[dict[str, Any]]:
    valid = type(value) is expected
    return (
        []
        if valid
        else [
            {
                "path": path,
                "expected": expected.__name__,
                "observed": type(value).__name__,
            }
        ]
    )


def _implementation_observation(
    source_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Observe executable R10 facts without constructing a model or split."""

    constructor_source = textwrap.dedent(
        inspect.getsource(InvariantPartialOTMatcher.__init__)
    )
    tree = ast.parse(constructor_source)
    parameter_names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        if not isinstance(value, ast.Call):
            continue
        function = value.func
        is_parameter = (
            isinstance(function, ast.Attribute) and function.attr == "Parameter"
        ) or (isinstance(function, ast.Name) and function.id == "Parameter")
        if not is_parameter:
            continue
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                parameter_names.append(target.attr)

    parser_actions = []
    parser = build_parser()
    for action in parser._actions:
        if action.dest == "help":
            continue
        parser_actions.append(
            {
                "dest": action.dest,
                "option_strings": list(action.option_strings),
                "default": action.default,
                "required": bool(action.required),
                "nargs": action.nargs,
                "choices": list(action.choices) if action.choices is not None else None,
                "type": getattr(action.type, "__name__", None),
            }
        )
    mutually_exclusive = [
        sorted(action.dest for action in group._group_actions)
        for group in parser._mutually_exclusive_groups
    ]
    files = source_manifest.get("files", {})
    observed_access_rules = {
        gate: [list(pair) for pair in accesses]
        for gate, accesses in _R6SplitAccessor._ACCESS_SEQUENCE.items()
    }
    governed_hash_paths = tuple(
        path for path in SOURCE_ALLOWLIST if path != _R10_PROTOCOL_RELATIVE_PATH
    )

    def stable_signature(callable_object: Any) -> list[dict[str, Any]]:
        """Encode a callable signature without process-address-bearing reprs."""

        observed: list[dict[str, Any]] = []
        for parameter in inspect.signature(callable_object).parameters.values():
            default = parameter.default
            if default is inspect.Parameter.empty:
                default_value: Any = {"kind": "empty"}
            elif default is None or isinstance(default, (bool, int, float, str)):
                default_value = {
                    "kind": "literal",
                    "type": type(default).__name__,
                    "value": default,
                }
            else:
                default_type = type(default)
                default_value = {
                    "kind": "typed_object",
                    "type": f"{default_type.__module__}.{default_type.__qualname__}",
                }
            annotation = parameter.annotation
            if annotation is inspect.Parameter.empty:
                annotation_name = None
            elif isinstance(annotation, str):
                annotation_name = annotation
            else:
                annotation_name = getattr(
                    annotation,
                    "__qualname__",
                    getattr(annotation, "__name__", str(annotation)),
                )
            observed.append(
                {
                    "name": parameter.name,
                    "kind": parameter.kind.name,
                    "default": default_value,
                    "annotation": annotation_name,
                }
            )
        return observed

    return {
        "constants": {
            "feature_dim": FEATURE_DIM,
            "identity_views": [list(view) for view in IDENTITY_VIEW_SLICES],
            "residual_cap": RESIDUAL_CAP,
            "null_utility_cap": NULL_UTILITY_CAP,
            "sinkhorn_temperature": SINKHORN_TEMPERATURE,
            "sinkhorn_iterations": SINKHORN_ITERATIONS,
            "feasibility_tolerance": FEASIBILITY_TOLERANCE,
            "transport_learning_rate": TRANSPORT_LEARNING_RATE,
            "mediator_learning_rate": MEDIATOR_LEARNING_RATE,
            "gradient_clip_norm": GRADIENT_CLIP_NORM,
            "registered_steps": REGISTERED_STEPS,
            "trainable_seeds": list(TRAINABLE_SEEDS),
            "exact64_method_order": list(EXACT64_METHOD_ORDER),
        },
        "callable_signatures": {
            "matcher_constructor": stable_signature(InvariantPartialOTMatcher),
            "compute_utilities": stable_signature(
                InvariantPartialOTMatcher.compute_utilities
            ),
            "soft_plan": stable_signature(InvariantPartialOTMatcher.soft_plan),
            "hard_plan": stable_signature(InvariantPartialOTMatcher.hard_plan),
            "structural_audit": stable_signature(run_r6_structural_audits),
            "counterfactual_audit": stable_signature(run_r6_counterfactual_audits),
        },
        "runtime_parameter_names_from_ast": sorted(parameter_names),
        "cli_actions": parser_actions,
        "cli_mutually_exclusive_groups": mutually_exclusive,
        "status_literals": {
            **IMPLEMENTED_STATUS_VOCABULARY,
        },
        "schema_versions": dict(IMPLEMENTED_SCHEMA_VERSIONS),
        "output_root_contract": {
            "phase_leaf_names": dict(IMPLEMENTED_OUTPUT_LEAVES),
            "reproduction_child_leaf_names": list(
                IMPLEMENTED_REPRODUCTION_CHILD_LEAVES
            ),
        },
        "data_access_rules": observed_access_rules,
        "optimizer_contract": {
            "transport_optimizer": "AdamW",
            "transport_parameter_owner": "InvariantPartialOTMatcher.parameters",
            "mediator_optimizer": "AdamW",
            "mediator_parameter_owner": "QueryRelationProjector.parameters",
            "matched_local_optimizer": "AdamW",
            "matched_local_parameter_owner": "InvariantPartialOTMatcher.parameters",
        },
        "initialization_literal_vector_sha256": copy.deepcopy(
            FROZEN_R5_REGISTRY["initialization"]["literal_vector_sha256"]
        ),
        "source_hashes": {path: files.get(path) for path in governed_hash_paths},
    }


def _resolution_gate(
    config: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    runtime_environment: Mapping[str, Any] | None = None,
    entry_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    serialized = json.dumps(config, sort_keys=True)
    enumerator_authority = FROZEN_R5_REGISTRY["enumerator_authority"]
    unresolved_markers = ("MUST_RESOLVE", "TODO", "TBD", "FIXME", "CHANGEME")
    expected_files = {
        "scripts/run_query_anchor_r4.py",
        "scripts/run_query_anchor_r4_reproduction.py",
        "refine-logs/CALIBRATION_PROTOCOL_R5_2026-07-22.md",
        "refine-logs/CALIBRATION_PROTOCOL_R6_2026-07-22.md",
        "refine-logs/CALIBRATION_PROTOCOL_R7_2026-07-22.md",
        "refine-logs/CALIBRATION_PROTOCOL_R8_2026-07-23.md",
        "refine-logs/CALIBRATION_PROTOCOL_R9_2026-07-23.md",
        "reports/r5_runner_gate_spec_2026-07-22.md",
        "src/visualvit/calibration_r5.py",
        "src/visualvit/matching.py",
        "src/visualvit/r6_structural_audits.py",
        "src/visualvit/r6_counterfactual_audits.py",
        "src/visualvit/r6_validation.py",
        "tests/test_query_anchor_r4_runner.py",
        "tests/test_r6_structural_audits.py",
        "tests/test_r6_counterfactual_audits.py",
        "tests/test_r6_reproduction.py",
        "tests/test_r6_runner_boundary.py",
        "tests/test_r6_validation.py",
    }
    status_vocabulary = FROZEN_R6_REGISTRY["status_vocabulary"]
    registered_environment = FROZEN_R6_REGISTRY["runtime_contract"]
    expected_config = _registered_config(
        seeds=(17,) if config.get("smoke") else TRAINABLE_SEEDS,
        actual_steps=1
        if config.get("smoke")
        else int(config.get("registered_steps", REGISTERED_STEPS)),
        smoke=bool(config.get("smoke")),
        dry_run=bool(config.get("dry_run")),
    )
    finite_errors = _validate_finite_tree(config)
    # Stable callable/CLI observations legitimately encode an absent annotation,
    # default, nargs, or choices field as JSON null.  That closed object is
    # compared independently below; null rejection applies to executable config
    # fields, not to explicit schema observations.
    none_checked_config = copy.deepcopy(config)
    observation_registry = (
        none_checked_config.get("protocol_authority", {})
        .get("machine_registry", {})
        .pop("implementation_observation_expected", None)
    )
    if observation_registry is None:
        required_none_paths = [
            "$.protocol_authority.machine_registry.implementation_observation_expected"
        ]
    else:
        required_none_paths = _required_none_paths(none_checked_config)
        # R12 records the exact immutable R11 pre-root diagnostics.  Two
        # source failures did not raise a Python exception, so their captured
        # optional exception fields are deliberately JSON null.  They are
        # provenance values, not executable configuration placeholders.
        allowed_registered_evidence_nones = {
            "$.protocol_authority.machine_registry.registered_r11_evidence."
            "gate0_resolution_preflight_failure.exception_type",
            "$.protocol_authority.machine_registry.registered_r11_evidence."
            "gate0_resolution_preflight_failure.exception_message",
        }
        required_none_paths = [
            path
            for path in required_none_paths
            if path not in allowed_registered_evidence_nones
        ]
    implementation_observation = _implementation_observation(source_manifest)
    freeze_checks = _freeze_record_validation(
        source_manifest, implementation_observation
    )
    checks = {
        "resolver_schema_version_exact": config.get("resolver_schema_version")
        == RESOLVER_SCHEMA_VERSION,
        "config_exactly_reconstructed": config == expected_config,
        "no_unresolved_placeholder_in_config": not any(
            marker in serialized for marker in unresolved_markers
        ),
        "no_nonfinite_config_values": not finite_errors,
        "no_none_in_required_config": not required_none_paths,
        "protocol_exact": config.get("protocol_version") == PROTOCOL_VERSION,
        "evidence_class_exact": config.get("evidence_class") == EVIDENCE_CLASS,
        "registered_seed_tuple_exact": tuple(config.get("trainable_seeds", ()))
        == ((17,) if config.get("smoke") else TRAINABLE_SEEDS),
        "registered_step_contract_exact": config.get("registered_steps")
        == REGISTERED_STEPS
        and config.get("actual_steps")
        == (1 if config.get("smoke") else REGISTERED_STEPS),
        "registered_device_cpu": config.get("device")
        == FROZEN_R6_REGISTRY.get("run_modes", {}).get("registered", {}).get("device"),
        "authority_final_frozen": FROZEN_R6_REGISTRY.get("authority_state")
        == status_vocabulary["protocol_frozen"]
        and FROZEN_R6_REGISTRY.get("freeze_requirements", {}).get(
            "implementation_hashes_frozen"
        )
        is True
        and FROZEN_R6_REGISTRY.get("freeze_requirements", {}).get("dry_run_authorized")
        is False,
        "r25_protocol_sha256_pinned_exact": _sha256_like(R25_PROTOCOL_SHA256)
        and _file_hash(R10_PROTOCOL_PATH) == R10_PROTOCOL_SHA256,
        "r24_base_dependency_exact": FROZEN_R6_REGISTRY.get("base_dependency")
        == {
            "path": "refine-logs/CALIBRATION_PROTOCOL_R24_2026-07-24.md",
            "protocol_sha256": R24_BASE_PROTOCOL_SHA256,
            "registry_sha256": R24_BASE_REGISTRY_SHA256,
            "registry_sha256_semantics": (
                "r24_full_canonical_registry_including_complete_freeze_record"
            ),
            "authority_state": "FROZEN_BEFORE_R24_REPRODUCTION",
        },
        "r24_base_dependency_live_sha256_exact": _file_hash(R24_BASE_PROTOCOL_PATH)
        == R24_BASE_PROTOCOL_SHA256,
        "r24_base_registry_live_sha256_exact": _json_hash(
            _first_json_object(R24_BASE_PROTOCOL_PATH, label="R24 base")
        )
        == R24_BASE_REGISTRY_SHA256,
        "run_mode_status_vocabulary_exact": status_vocabulary
        == IMPLEMENTED_STATUS_VOCABULARY,
        "schema_version_implementation_exact": FROZEN_R6_REGISTRY["schema_versions"]
        == IMPLEMENTED_SCHEMA_VERSIONS
        and IMPLEMENTED_SCHEMA_VERSIONS["structural_microcases"]
        == R6_STRUCTURAL_AUDIT_SCHEMA_VERSION
        and IMPLEMENTED_SCHEMA_VERSIONS["counterfactual"]
        == R6_COUNTERFACTUAL_SCHEMA_VERSION
        and IMPLEMENTED_SCHEMA_VERSIONS["independent_validator"]
        == R6_VALIDATION_SCHEMA_VERSION,
        "output_root_implementation_exact": FROZEN_R6_REGISTRY["output_root_contract"][
            "phase_leaf_names"
        ]
        == IMPLEMENTED_OUTPUT_LEAVES
        and FROZEN_R6_REGISTRY["output_root_contract"]["reproduction_child_leaf_names"]
        == list(IMPLEMENTED_REPRODUCTION_CHILD_LEAVES),
        "data_access_implementation_exact": FROZEN_R6_REGISTRY["data_access_contract"]
        == {
            **{
                gate: [list(pair) for pair in accesses]
                for gate, accesses in _R6SplitAccessor._ACCESS_SEQUENCE.items()
            },
            "resolution_freeze": [],
            "exact64_bridge": [],
            "independent_reproduction": [],
            "gate_7_reads_cached_snapshots_only": True,
            "gate_8_reads_child_artifacts_only": True,
        },
        "gate_order_implementation_exact": list(GATE_ORDER)
        == FROZEN_R6_REGISTRY["gate_order"],
        "summary_serialization_contract_exact": FROZEN_R6_REGISTRY.get(
            "summary_serialization_contract"
        )
        == IMPLEMENTED_SUMMARY_SERIALIZATION_CONTRACT,
        "atomic_failure_r12_paths_and_stages_exact": FROZEN_R6_REGISTRY.get(
            "atomic_failure_contract", {}
        ).get("pre_output_root_failure_parent")
        == IMPLEMENTED_PRE_ROOT_FAILURE_PARENT
        and FROZEN_R6_REGISTRY.get("atomic_failure_contract", {}).get(
            "required_failure_stages"
        )
        == list(IMPLEMENTED_FAILURE_STAGES),
        "source_manifest_self_consistent": _source_manifest_authority_valid(
            source_manifest
        ),
        "source_manifest_closed_allowlist_exact": source_manifest.get("allowlist")
        == list(SOURCE_ALLOWLIST)
        and set(source_manifest.get("files", {})) == set(SOURCE_ALLOWLIST),
        "required_source_files_present": expected_files.issubset(
            set(source_manifest.get("files", {}))
        ),
        "margin_certificate_passed": config.get("margin_certificate", {}).get("passed")
        is True,
        "formal_data_hold": config.get("formal_data_authorization") == "HOLD",
        "schema_versions_exact": config.get("summary_schema_version")
        == SUMMARY_SCHEMA_VERSION
        and config.get("result_schema_version") == RESULT_SCHEMA_VERSION
        and config.get("resolver_schema_version") == RESOLVER_SCHEMA_VERSION,
        "null_cap_exact": config.get("transport", {}).get("null_utility_cap")
        == NULL_UTILITY_CAP,
        "initialization_exact": config.get("transport", {})
        .get("initialization", {})
        .get("standard_deviation")
        == INITIALIZATION_STD,
        "r25_protocol_sole_authority": config.get("protocol_authority", {}).get(
            "sole_authority"
        )
        == _R10_PROTOCOL_RELATIVE_PATH,
        "r25_protocol_sha256_exact": config.get("protocol_authority", {}).get(
            "protocol_sha256"
        )
        == R10_PROTOCOL_SHA256,
        "machine_registry_exact": config.get("protocol_authority", {}).get(
            "machine_registry"
        )
        == FROZEN_R6_REGISTRY,
        "machine_registry_sha256_exact": config.get("protocol_authority", {}).get(
            "registry_sha256"
        )
        == _json_hash(FROZEN_R6_REGISTRY),
        "source_manifest_r25_protocol_sha256_exact": source_manifest.get(
            "files", {}
        ).get(_R10_PROTOCOL_RELATIVE_PATH)
        == R10_PROTOCOL_SHA256,
        "exact64_method_order_authority_exact": list(EXACT64_METHOD_ORDER)
        == FROZEN_R6_REGISTRY.get("exact64_method_order")
        and len(EXACT64_METHOD_ORDER) == len(set(EXACT64_METHOD_ORDER)),
        "enumerator_authority_files_exact": all(
            source_manifest.get("files", {}).get(enumerator_authority[path_key])
            == enumerator_authority[hash_key]
            for path_key, hash_key in (
                ("path", "source_sha256"),
                ("dependency_path", "dependency_sha256"),
                ("test_path", "test_sha256"),
                ("gate_spec_path", "gate_spec_sha256"),
            )
        ),
        "canonical_certificate_authority_exact": config.get("margin_certificate")
        == {
            "authority_symbol": enumerator_authority["symbol"],
            "canonical_certificate_sha256": enumerator_authority[
                "canonical_certificate_sha256"
            ],
            "registered_minimum_robust_gap": enumerator_authority[
                "registered_minimum_robust_gap"
            ],
            "passed": True,
            "runtime_recomputation_gate": "structural_input",
        },
        "registry_fixture_constants_exact": FROZEN_R5_REGISTRY["feature_dim"]
        == FEATURE_DIM
        and FROZEN_R5_REGISTRY["channels"]["identity_views"]
        == [list(view) for view in IDENTITY_VIEW_SLICES]
        and FROZEN_R5_REGISTRY["clean_split_seeds"] == dict(FROZEN_R5_CLEAN_SPLIT_SEEDS)
        and FROZEN_R5_REGISTRY["challenge_split_seeds"]
        == dict(FROZEN_R5_CHALLENGE_SPLIT_SEEDS)
        and FROZEN_R5_REGISTRY["counterbalance_groups"]
        == dict(FROZEN_R5_COUNTERBALANCE_GROUPS),
        "matcher_implementation_matches_registry": RESIDUAL_CAP
        == FROZEN_R5_REGISTRY["utility"]["scalar_monotone_cap"]
        and NULL_UTILITY_CAP == FROZEN_R5_REGISTRY["utility"]["null_utility_cap"]
        and SINKHORN_TEMPERATURE == FROZEN_R5_REGISTRY["soft_solver"]["temperature"]
        and SINKHORN_ITERATIONS == FROZEN_R5_REGISTRY["soft_solver"]["iterations"]
        and TRANSPORT_LEARNING_RATE
        == FROZEN_R5_REGISTRY["transport_training"]["learning_rate"]
        and GRADIENT_CLIP_NORM
        == FROZEN_R5_REGISTRY["transport_training"]["gradient_clip_l2"],
        "initialization_static_contract_resolved": FROZEN_R6_REGISTRY.get(
            "initialization_evidence_contract", {}
        ).get("parameter_order")
        == [
            "residual_coefficient",
            "view_weight_logits.0",
            "view_weight_logits.1",
            "prior_null_utility_raw",
            "current_null_utility_raw",
        ]
        and set(FROZEN_R5_REGISTRY["initialization"]["literal_values"])
        == {str(seed) for seed in TRAINABLE_SEEDS},
        "implementation_observation_exact": implementation_observation
        == FROZEN_R6_REGISTRY.get("implementation_observation_expected"),
        "implementation_source_hashes_complete": all(
            _sha256_like(value)
            for value in implementation_observation["source_hashes"].values()
        ),
        **freeze_checks,
        "runtime_contract_exact": runtime_environment is None
        or (
            runtime_environment.get("torch_num_threads")
            == registered_environment["torch_num_threads"]
            and runtime_environment.get("torch_num_interop_threads")
            == registered_environment.get("torch_num_interop_threads")
            and runtime_environment.get("deterministic_algorithms_enabled") is True
            and isinstance(runtime_environment.get("deterministic_debug_mode"), int)
            and runtime_environment.get("deterministic_debug_mode_name")
            == registered_environment["deterministic_debug_mode"]
            and runtime_environment.get("cudnn_benchmark")
            == registered_environment["cudnn_benchmark"]
            and runtime_environment.get("cudnn_deterministic")
            == registered_environment["cudnn_deterministic"]
            and isinstance(runtime_environment.get("torch_build_sha256"), str)
            and isinstance(runtime_environment.get("cuda_available"), bool)
            and isinstance(runtime_environment.get("locale_lc_all"), str)
            and isinstance(runtime_environment.get("locale_preferred_encoding"), str)
            and isinstance(runtime_environment.get("filesystem_encoding"), str)
            and isinstance(runtime_environment.get("locale_decimal_point"), str)
            and isinstance(runtime_environment.get("locale_thousands_separator"), str)
            and isinstance(runtime_environment.get("timezone_name"), str)
            and isinstance(runtime_environment.get("timezone_offset"), str)
            and runtime_environment.get("pythonhashseed")
            == registered_environment["pythonhashseed"]
            and runtime_environment.get("omp_num_threads")
            == registered_environment["omp_num_threads"]
            and runtime_environment.get("mkl_num_threads")
            == registered_environment["mkl_num_threads"]
            and set(runtime_environment.get("environment_allowlist", {}))
            == set(registered_environment["secret_safe_environment_allowlist"])
        ),
        "output_root_entry_contract": entry_evidence is None
        or (
            entry_evidence.get("output_root_existed_at_entry") is False
            and entry_evidence.get("output_parent_is_directory") is True
            and entry_evidence.get("output_parent_writable") is True
            and entry_evidence.get("output_root_contract_passed") is True
        ),
    }
    return {
        "resolver_schema_version": RESOLVER_SCHEMA_VERSION,
        "status": "PASS" if all(checks.values()) else "FAIL_RESOLUTION_FREEZE",
        "passed": all(checks.values()),
        "checks": checks,
        "validation_errors": {
            "nonfinite": finite_errors,
            "required_none": required_none_paths,
        },
        "model_construction_performed": False,
        "implementation_observation": implementation_observation,
    }


def _query_independence_audit(
    batch: QueryAnchorBatch, matcher: InvariantPartialOTMatcher
) -> dict[str, Any]:
    visible = _matching_regions(batch)
    prior = batch.regions.prior_features.clone()
    current = batch.regions.current_features.clone()
    prior[..., :2] = torch.flip(prior[..., :2], dims=(1,))
    current[..., :2] = torch.roll(current[..., :2], shifts=1, dims=1)
    counterfactual = replace(
        batch,
        regions=replace(
            batch.regions,
            prior_features=prior,
            current_features=current,
        ),
    )
    counterfactual_visible = _matching_regions(counterfactual)
    original_utilities = matcher.compute_utilities(visible)
    changed_utilities = matcher.compute_utilities(counterfactual_visible)
    original_soft = matcher.soft_plan(visible)
    changed_soft = matcher.soft_plan(counterfactual_visible)
    original_hard = matcher.hard_plan(visible)
    changed_hard = matcher.hard_plan(counterfactual_visible)
    checks = {
        "sanitized_inputs_exact": torch.equal(
            visible.prior_features, counterfactual_visible.prior_features
        )
        and torch.equal(
            visible.current_features, counterfactual_visible.current_features
        ),
        "utilities_exact": all(
            torch.equal(left, right)
            for left, right in zip(original_utilities, changed_utilities, strict=True)
        ),
        "soft_plan_exact": torch.equal(original_soft.transport, changed_soft.transport),
        "hard_plan_exact": torch.equal(original_hard.transport, changed_hard.transport),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "sanitized_input_sha256": _json_hash(
            {
                "prior": _tensor_hash(visible.prior_features),
                "current": _tensor_hash(visible.current_features),
            }
        ),
        "utility_sha256": [_tensor_hash(value) for value in original_utilities],
        "soft_plan_sha256": _tensor_hash(original_soft.transport),
        "hard_plan_sha256": _tensor_hash(original_hard.transport),
    }


def _batch_tensor_snapshot(batch: QueryAnchorBatch) -> dict[str, str]:
    values: dict[str, Tensor] = {}
    for name, value in vars(batch.regions).items():
        if isinstance(value, Tensor):
            values[f"regions.{name}"] = value
    for name, value in vars(batch).items():
        if isinstance(value, Tensor):
            values[f"batch.{name}"] = value
    for name, value in vars(batch.oracle).items():
        if isinstance(value, Tensor):
            values[f"oracle.{name}"] = value
        elif isinstance(value, MatchPlan):
            values[f"oracle.{name}.transport"] = value.transport
    return {name: _tensor_hash(value) for name, value in sorted(values.items())}


def _hidden_id_relabel_audit(
    batch: QueryAnchorBatch, matcher: InvariantPartialOTMatcher
) -> dict[str, Any]:
    before = _batch_tensor_snapshot(batch)
    prior_ids = torch.flip(batch.regions.prior_entity_ids, dims=(1,)) + 101_003
    current_ids = (
        torch.roll(batch.regions.current_entity_ids, shifts=1, dims=1) + 202_007
    )
    oracle_prior = torch.flip(batch.oracle.prior_gold_ids, dims=(1,)) + 303_013
    oracle_current = (
        torch.roll(batch.oracle.current_gold_ids, shifts=1, dims=1) + 404_009
    )
    relabeled = replace(
        batch,
        regions=replace(
            batch.regions,
            prior_entity_ids=prior_ids,
            current_entity_ids=current_ids,
        ),
        oracle=replace(
            batch.oracle,
            prior_gold_ids=oracle_prior,
            current_gold_ids=oracle_current,
        ),
    )
    original_visible = _matching_regions(batch)
    relabeled_visible = _matching_regions(relabeled)
    original_utilities = matcher.compute_utilities(original_visible)
    relabeled_utilities = matcher.compute_utilities(relabeled_visible)
    original_soft = matcher.soft_plan(original_visible)
    relabeled_soft = matcher.soft_plan(relabeled_visible)
    original_hard = matcher.hard_plan(original_visible)
    relabeled_hard = matcher.hard_plan(relabeled_visible)
    after = _batch_tensor_snapshot(batch)
    checks = {
        "counterfactual_nonvacuous": not torch.equal(
            batch.regions.prior_entity_ids, prior_ids
        )
        and not torch.equal(batch.oracle.prior_gold_ids, oracle_prior),
        "visible_features_exact": torch.equal(
            original_visible.prior_features, relabeled_visible.prior_features
        )
        and torch.equal(
            original_visible.current_features, relabeled_visible.current_features
        ),
        "utilities_exact": all(
            torch.equal(left, right)
            for left, right in zip(original_utilities, relabeled_utilities, strict=True)
        ),
        "soft_plan_exact": torch.equal(
            original_soft.transport, relabeled_soft.transport
        ),
        "hard_plan_exact": torch.equal(
            original_hard.transport, relabeled_hard.transport
        ),
        "source_tensors_immutable": before == after,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "original_id_sha256": _json_hash(
            {
                "visible_prior": _tensor_hash(batch.regions.prior_entity_ids),
                "visible_current": _tensor_hash(batch.regions.current_entity_ids),
                "oracle_prior": _tensor_hash(batch.oracle.prior_gold_ids),
                "oracle_current": _tensor_hash(batch.oracle.current_gold_ids),
            }
        ),
        "relabeled_id_sha256": _json_hash(
            {
                "visible_prior": _tensor_hash(prior_ids),
                "visible_current": _tensor_hash(current_ids),
                "oracle_prior": _tensor_hash(oracle_prior),
                "oracle_current": _tensor_hash(oracle_current),
            }
        ),
    }


def _permute_endpoint_tensor(
    value: Tensor | None, permutation: Tensor
) -> Tensor | None:
    if value is None:
        return None
    return value.index_select(1, permutation).clone()


def _endpoint_permutation_audit(
    batch: QueryAnchorBatch, matcher: InvariantPartialOTMatcher
) -> dict[str, Any]:
    prior_count = batch.regions.prior_features.shape[1]
    current_count = batch.regions.current_features.shape[1]
    prior_permutation = torch.roll(torch.arange(prior_count), shifts=1)
    current_permutation = torch.roll(torch.arange(current_count), shifts=-1)
    regions = batch.regions
    permuted_regions = replace(
        regions,
        prior_features=_permute_endpoint_tensor(
            regions.prior_features, prior_permutation
        ),
        current_features=_permute_endpoint_tensor(
            regions.current_features, current_permutation
        ),
        prior_valid=_permute_endpoint_tensor(regions.prior_valid, prior_permutation),
        current_valid=_permute_endpoint_tensor(
            regions.current_valid, current_permutation
        ),
        prior_anatomy=_permute_endpoint_tensor(
            regions.prior_anatomy, prior_permutation
        ),
        current_anatomy=_permute_endpoint_tensor(
            regions.current_anatomy, current_permutation
        ),
        prior_entity_ids=_permute_endpoint_tensor(
            regions.prior_entity_ids, prior_permutation
        ),
        current_entity_ids=_permute_endpoint_tensor(
            regions.current_entity_ids, current_permutation
        ),
        prior_boxes=_permute_endpoint_tensor(regions.prior_boxes, prior_permutation),
        current_boxes=_permute_endpoint_tensor(
            regions.current_boxes, current_permutation
        ),
        prior_confidence=_permute_endpoint_tensor(
            regions.prior_confidence, prior_permutation
        ),
        current_confidence=_permute_endpoint_tensor(
            regions.current_confidence, current_permutation
        ),
        prior_source_ids=_permute_endpoint_tensor(
            regions.prior_source_ids, prior_permutation
        ),
        current_source_ids=_permute_endpoint_tensor(
            regions.current_source_ids, current_permutation
        ),
    )
    oracle_transport = batch.oracle.plan.transport
    permuted_transport = oracle_transport.new_zeros(oracle_transport.shape)
    permuted_transport[:, :prior_count, :current_count] = oracle_transport[
        :, prior_permutation
    ][:, :, current_permutation]
    permuted_transport[:, :prior_count, current_count] = oracle_transport[
        :, prior_permutation, current_count
    ]
    permuted_transport[:, prior_count, :current_count] = oracle_transport[
        :, prior_count, current_permutation
    ]
    permuted_oracle_plan = MatchPlan(
        transport=permuted_transport, mode=f"{batch.oracle.plan.mode}_permuted"
    )
    permuted = replace(
        batch,
        regions=permuted_regions,
        prior_query_marker=_permute_endpoint_tensor(
            batch.prior_query_marker, prior_permutation
        ),
        current_query_marker=_permute_endpoint_tensor(
            batch.current_query_marker, current_permutation
        ),
        prior_carrier_control=_permute_endpoint_tensor(
            batch.prior_carrier_control, prior_permutation
        ),
        current_carrier_control=_permute_endpoint_tensor(
            batch.current_carrier_control, current_permutation
        ),
        oracle=replace(
            batch.oracle,
            prior_gold_ids=_permute_endpoint_tensor(
                batch.oracle.prior_gold_ids, prior_permutation
            ),
            current_gold_ids=_permute_endpoint_tensor(
                batch.oracle.current_gold_ids, current_permutation
            ),
            plan=permuted_oracle_plan,
        ),
    )
    original_visible = _matching_regions(batch)
    permuted_visible = _matching_regions(permuted)
    original_soft = matcher.soft_plan(original_visible).transport
    original_hard = matcher.hard_plan(original_visible).transport
    expected_soft = original_soft.new_zeros(original_soft.shape)
    expected_hard = original_hard.new_zeros(original_hard.shape)
    for source, destination in (
        (original_soft, expected_soft),
        (original_hard, expected_hard),
    ):
        destination[:, :prior_count, :current_count] = source[:, prior_permutation][
            :, :, current_permutation
        ]
        destination[:, :prior_count, current_count] = source[
            :, prior_permutation, current_count
        ]
        destination[:, prior_count, :current_count] = source[
            :, prior_count, current_permutation
        ]
    observed_soft = matcher.soft_plan(permuted_visible).transport
    observed_hard = matcher.hard_plan(permuted_visible).transport
    checks = {
        "prior_permutation_nonidentity": not torch.equal(
            prior_permutation, torch.arange(prior_count)
        ),
        "current_permutation_nonidentity": not torch.equal(
            current_permutation, torch.arange(current_count)
        ),
        "soft_plan_equivariant": torch.allclose(
            observed_soft, expected_soft, atol=1e-6, rtol=0
        ),
        "hard_plan_equivariant": torch.equal(observed_hard, expected_hard),
        "oracle_plan_equivariant": torch.equal(
            permuted.oracle.plan.transport, permuted_transport
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "prior_permutation_sha256": _tensor_hash(prior_permutation),
        "current_permutation_sha256": _tensor_hash(current_permutation),
        "observed_soft_sha256": _tensor_hash(observed_soft),
        "expected_soft_sha256": _tensor_hash(expected_soft),
    }


def _structural_gate(
    strata: Mapping[str, Mapping[str, QueryAnchorBatch]],
    raw_clean: Mapping[str, R5CleanBatch],
    raw_challenge: Mapping[str, R5ChallengeBatch],
    adapter: nn.Module,
) -> dict[str, Any]:
    matcher = _new_matcher()
    results: dict[str, Any] = {}
    for stratum in STRATA:
        results[stratum] = {}
        for split in strata[stratum]:
            batch = strata[stratum][split]
            if stratum == "clean":
                batch.validate()
            else:
                batch.regions.validate()
                batch.oracle.validate(batch.regions)
            visible = _matching_regions(batch)
            utilities = matcher.compute_utilities(visible)
            soft = matcher.soft_plan(visible)
            hard = matcher.hard_plan(visible)
            soft.validate(visible, atol=FEASIBILITY_TOLERANCE)
            hard.validate_hard(visible, atol=FEASIBILITY_TOLERANCE)
            finite = bool(
                all(torch.isfinite(value).all() for value in utilities)
                and torch.isfinite(soft.transport).all()
                and torch.isfinite(hard.transport).all()
            )
            dustbin_zero = bool(
                soft.transport[:, -1, -1].eq(0).all()
                and hard.transport[:, -1, -1].eq(0).all()
            )
            query_audit = _query_independence_audit(batch, matcher)
            hidden_id_audit = _hidden_id_relabel_audit(batch, matcher)
            permutation_audit = _endpoint_permutation_audit(batch, matcher)
            adapter_audit = _adapter_equivalence_audit(
                _initial_projector(TRAINABLE_SEEDS[0]),
                adapter,
                batch,
                batch.oracle.plan,
            )
            split_checks = {
                "finite_utilities_and_plans": finite,
                "two_sided_dustbin_dustbin_zero": dustbin_zero,
                "query_independent_transport": query_audit["passed"],
                "hidden_id_relabel_invariant": hidden_id_audit["passed"],
                "endpoint_permutation_equivariant": permutation_audit["passed"],
                "exact64_adapter_equivalence": adapter_audit["passed"],
            }
            if stratum == "challenge":
                raw = raw_challenge[split]
            else:
                raw = raw_clean[split]
            observed_hashes = _raw_fixture_hashes(raw)
            registry_prefix = (
                "fixture_development" if split == "audit_fixture" else split
            )
            expected_registry = FROZEN_R5_REGISTRY["fixture_hashes"][stratum]
            fixture_hash_checks = {
                "visible_hash_exact": observed_hashes["visible"]
                == expected_registry[f"{registry_prefix}_visible"],
                "oracle_hash_exact": observed_hashes["hidden_oracle"]
                == expected_registry[f"{registry_prefix}_oracle"],
            }
            if stratum == "challenge":
                fixture_hash_checks["full_fixture_hash_exact"] = (
                    observed_hashes["full_fixture"]
                    == expected_registry[f"{registry_prefix}_full"]
                )
            split_checks["source_hashed_fixture_exact"] = all(
                fixture_hash_checks.values()
            )
            challenge_audit = {
                "passed": all(fixture_hash_checks.values()),
                "checks": fixture_hash_checks,
                "observed_hashes": observed_hashes,
            }
            results[stratum][split] = {
                "passed": all(split_checks.values()),
                "checks": split_checks,
                "query_independence": query_audit,
                "hidden_id_relabel": hidden_id_audit,
                "endpoint_permutation": permutation_audit,
                "adapter_equivalence": adapter_audit,
                "challenge_audit": challenge_audit,
                "initial_soft_plan_sha256": _tensor_hash(soft.transport),
                "initial_hard_plan_sha256": _tensor_hash(hard.transport),
            }

    split_disjoint = all(
        len(
            {
                _split_manifest(strata[stratum][split])["composite_sha256"]
                for split in strata[stratum]
            }
        )
        == len(strata[stratum])
        for stratum in STRATA
    )
    certificate = enumerate_r5_clean_assignment_certificate()
    margin_preserved = certificate["passed"]
    rng_before = torch.random.get_rng_state().clone()
    initialization_evidence = {
        str(seed): _initialization_evidence(seed, _new_matcher(seed))
        for seed in TRAINABLE_SEEDS
    }
    rng_after = torch.random.get_rng_state().clone()
    repeated_initialization_evidence = {
        str(seed): _initialization_evidence(seed, _new_matcher(seed))
        for seed in TRAINABLE_SEEDS
    }
    seed_state_map = {
        seed: evidence["raw_initial_state_sha256"]
        for seed, evidence in initialization_evidence.items()
    }
    initialization_checks = {
        "all_seed_evidence_passed": all(
            evidence["passed"] for evidence in initialization_evidence.values()
        ),
        "same_seed_byte_exact": all(
            initialization_evidence[seed]["raw_initial_state_sha256"]
            == repeated_initialization_evidence[seed]["raw_initial_state_sha256"]
            and initialization_evidence[seed]["effective_initial_state_sha256"]
            == repeated_initialization_evidence[seed]["effective_initial_state_sha256"]
            for seed in initialization_evidence
        ),
        "seed_states_pairwise_distinct": len(set(seed_state_map.values()))
        == len(TRAINABLE_SEEDS),
        "seed_map_hash_exact": _json_hash(seed_state_map)
        == FROZEN_R6_REGISTRY["initialization_evidence_contract"][
            "seed_to_initial_state_sha256_map_sha256"
        ],
        "global_rng_unchanged": torch.equal(rng_before, rng_after),
    }
    r6_matcher = _new_matcher(TRAINABLE_SEEDS[0])
    r6_structural = run_r6_structural_audits(r6_matcher)
    validate_r6_structural_audit(r6_structural)
    registered_microcase_contract = FROZEN_R6_REGISTRY["structural_microcase_contract"]
    observed_microcase_input_hashes = {
        case_id: r6_structural["microcases"][case_id]["input_sha256_before"]
        for case_id in r6_structural["required_case_ids"]
    }
    clean_batch = strata["clean"][next(iter(strata["clean"]))]
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(61_607)
        counterfactual_projector = RelationProjector(input_dim=75, hidden_size=8)
    r6_counterfactual = run_r6_counterfactual_audits(
        clean_batch,
        R6ChainHooks(
            matching_regions=_matching_regions,
            token_regions=lambda value: value.regions,
            matcher=r6_matcher,
            allocator=DeterministicGlobalAllocator(),
            projector=counterfactual_projector,
            adapter=adapter,
            prompt_factory=query_prompt,
        ),
    )
    validate_r6_counterfactual_audit(r6_counterfactual)
    counterfactual_hash_exact = r6_counterfactual.get("report_sha256") == _json_hash(
        {
            key: value
            for key, value in r6_counterfactual.items()
            if key != "report_sha256"
        }
    )
    r6_evidence_checks = {
        "structural_schema_exact": r6_structural.get("schema_version")
        == R6_STRUCTURAL_AUDIT_SCHEMA_VERSION
        == FROZEN_R6_REGISTRY["schema_versions"]["structural_microcases"],
        "structural_passed": r6_structural.get("passed") is True,
        "structural_hash_validated": r6_structural.get("audit_sha256")
        == registered_microcase_contract["expected_runtime_report_sha256"],
        "structural_case_order_registered": r6_structural.get("required_case_ids")
        == registered_microcase_contract["required_case_ids"],
        "structural_input_hashes_registered": observed_microcase_input_hashes
        == registered_microcase_contract["expected_input_sha256_by_case"],
        "structural_input_map_hash_registered": _json_hash(
            observed_microcase_input_hashes
        )
        == registered_microcase_contract["expected_input_map_sha256"],
        "counterfactual_schema_exact": r6_counterfactual.get("schema_version")
        == R6_COUNTERFACTUAL_SCHEMA_VERSION
        == FROZEN_R6_REGISTRY["schema_versions"]["counterfactual"],
        "counterfactual_passed": r6_counterfactual.get("passed") is True,
        "counterfactual_hash_exact": counterfactual_hash_exact,
        **initialization_checks,
    }
    gate_checks = {
        "all_stratum_split_structural_checks_passed": all(
            result["passed"]
            for stratum_results in results.values()
            for result in stratum_results.values()
        ),
        "split_manifests_disjoint_within_stratum": split_disjoint,
        "margin_certificate_passed": margin_preserved,
        **r6_evidence_checks,
    }
    return {
        "status": "PASS" if all(gate_checks.values()) else "FAIL_STRUCTURAL_INPUT",
        "passed": all(gate_checks.values()),
        "checks": gate_checks,
        "strata": results,
        "split_manifests_disjoint_within_stratum": split_disjoint,
        "margin_certificate": {
            "passed": margin_preserved,
            **certificate,
        },
        "matcher_initial_state_sha256": _state_hash(matcher),
        "matcher_parameter_names": sorted(
            name for name, _ in matcher.named_parameters()
        ),
        "r6_gate1_evidence": {
            "passed": all(r6_evidence_checks.values()),
            "checks": r6_evidence_checks,
            "structural_microcases": r6_structural,
            "full_chain_counterfactual": r6_counterfactual,
            "initialization": {
                "schema_version": FROZEN_R6_REGISTRY["schema_versions"][
                    "initialization"
                ],
                "passed": all(initialization_checks.values()),
                "checks": initialization_checks,
                "seed_evidence": initialization_evidence,
                "seed_to_initial_state_sha256": seed_state_map,
                "seed_to_initial_state_sha256_map_sha256": _json_hash(seed_state_map),
            },
        },
    }


def _fixture_authority_dry_run_gate(
    *,
    raw_audit: Mapping[str, R5CleanBatch | R5ChallengeBatch],
) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    evidence: dict[str, Any] = {}
    for stratum in STRATA:
        expected = FROZEN_R5_REGISTRY["fixture_hashes"][stratum]
        audit_hashes = _raw_fixture_hashes(raw_audit[stratum])
        stratum_checks = {
            "audit_visible_exact": audit_hashes["visible"]
            == expected["fixture_development_visible"],
            "audit_oracle_exact": audit_hashes["hidden_oracle"]
            == expected["fixture_development_oracle"],
        }
        if stratum == "challenge":
            stratum_checks.update(
                {
                    "audit_full_exact": audit_hashes["full_fixture"]
                    == expected["fixture_development_full"],
                }
            )
        checks.update(
            {f"{stratum}_{name}": passed for name, passed in stratum_checks.items()}
        )
        evidence[stratum] = {"audit_fixture": audit_hashes}
    leakage = FROZEN_R5_REGISTRY["fixture_leakage_attack"]
    checks["source_hashed_leakage_certificate_valid"] = bool(
        leakage["training_or_fitting"] == "none_deterministic_attack"
        and leakage["frozen_train_to_development_accuracy"]
        <= leakage["accuracy_max"] + leakage["numeric_tolerance"]
        and leakage["frozen_train_to_development_macro_f1"]
        <= leakage["macro_f1_max"] + leakage["numeric_tolerance"]
        and leakage["frozen_unseen_development_signature_count"] == 0
    )
    return {
        "status": "DRY_RUN_FIXTURE_AUTHORITY_VALIDATED"
        if all(checks.values())
        else "FAIL_FIXTURE_AUTHORITY",
        "passed": all(checks.values()),
        "method_gate_pass_forbidden": True,
        "checks": checks,
        "fixture_hash_evidence": evidence,
        "source_hashed_leakage_certificate_sha256": _json_hash(leakage),
    }


def _dry_run_access_ledger_gate(
    ledger: Sequence[Mapping[str, Any]], split_manifests: Mapping[str, Any]
) -> dict[str, Any]:
    expected_prefix = [
        ["structural_input", "clean", "literal_audit_fixture"],
        ["structural_input", "challenge", "literal_audit_fixture"],
        ["fixture_identifiability", "clean", "frozen_fixture_audit"],
        ["fixture_identifiability", "challenge", "frozen_fixture_audit"],
    ]
    observed_prefix = [
        [entry.get("gate"), entry.get("stratum"), entry.get("split")]
        for entry in ledger
    ]
    forbidden_hashes: set[str] = set()
    for stratum in STRATA:
        hashes = FROZEN_R5_REGISTRY["fixture_hashes"][stratum]
        for split in ("inner_development", "development"):
            for suffix in ("visible", "oracle", "full"):
                value = hashes.get(f"{split}_{suffix}")
                if isinstance(value, str):
                    forbidden_hashes.add(value)
    serialized = json.dumps(
        {"ledger": list(ledger), "split_manifests": split_manifests}, sort_keys=True
    )
    leaked_hashes = sorted(value for value in forbidden_hashes if value in serialized)
    checks = {
        "registered_access_prefix_exact": observed_prefix == expected_prefix,
        "registered_inner_or_development_hash_absent": not leaked_hashes,
        "ledger_schema_exact": all(
            entry.get("schema_version")
            == FROZEN_R6_REGISTRY["schema_versions"]["data_access_ledger"]
            for entry in ledger
        ),
        "only_gate_1_and_2": all(
            entry.get("gate") in {"structural_input", "fixture_identifiability"}
            for entry in ledger
        ),
        "accessed_manifest_names_exact": all(
            set(split_manifests[stratum]) == {"audit_fixture"} for stratum in STRATA
        ),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL_PREMATURE_DATA_ACCESS",
        "passed": all(checks.values()),
        "checks": checks,
        "expected_prefix": expected_prefix,
        "observed_prefix": observed_prefix,
        "leaked_registered_hashes": leaked_hashes,
    }


def _transport_supervision_loss(predicted: MatchPlan, oracle: MatchPlan) -> Tensor:
    if predicted.transport.shape != oracle.transport.shape:
        raise ValueError("predicted and oracle transports must have identical shape")
    target = oracle.transport.to(predicted.transport.dtype)
    mass = target.sum().clamp_min(1.0)
    return -(target * predicted.transport.clamp_min(1e-8).log()).sum() / mass


def _binary_event_metrics(expected: Tensor, observed: Tensor) -> dict[str, Any]:
    expected = expected.bool()
    observed = observed.bool()
    tp = int((expected & observed).sum())
    fp = int((~expected & observed).sum())
    fn = int((expected & ~observed).sum())
    tn = int((~expected & ~observed).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    return {
        "actual": expected.detach().cpu().to(torch.int64).reshape(-1).tolist(),
        "predicted": observed.detach().cpu().to(torch.int64).reshape(-1).tolist(),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "positive_support": int(expected.sum()),
        "predicted_positive_support": int(observed.sum()),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "balanced_accuracy": 0.5 * (recall + specificity),
        "non_gating_accuracy": float((expected == observed).float().mean()),
    }


def _null_metrics(batch: QueryAnchorBatch, hard: MatchPlan) -> dict[str, Any]:
    prior_count = batch.regions.prior_features.shape[1]
    current_count = batch.regions.current_features.shape[1]
    oracle_death = batch.oracle.plan.transport[:, :prior_count, current_count] > 0.5
    predicted_death = hard.transport[:, :prior_count, current_count] > 0.5
    oracle_birth = batch.oracle.plan.transport[:, prior_count, :current_count] > 0.5
    predicted_birth = hard.transport[:, prior_count, :current_count] > 0.5
    death = _binary_event_metrics(oracle_death, predicted_death)
    birth = _binary_event_metrics(oracle_birth, predicted_birth)
    death_exact = (oracle_death == predicted_death).all(dim=-1)
    birth_exact = (oracle_birth == predicted_birth).all(dim=-1)
    joint_exact = death_exact & birth_exact
    return {
        "death": death,
        "birth": birth,
        "death_exact_case": float(death_exact.float().mean()),
        "birth_exact_case": float(birth_exact.float().mean()),
        "null_exact_case": float(joint_exact.float().mean()),
        "macro_f1": 0.5 * (death["f1"] + birth["f1"]),
        "positive_support_both": death["positive_support"] > 0
        and birth["positive_support"] > 0,
        "metric_evidence": {
            "case_count": int(death_exact.numel()),
            "death_exact_count": int(death_exact.sum()),
            "birth_exact_count": int(birth_exact.sum()),
            "joint_exact_count": int(joint_exact.sum()),
        },
    }


def _query_metric_evidence(
    batch: QueryAnchorBatch, soft: MatchPlan, hard: MatchPlan
) -> dict[str, Any]:
    """Persist sufficient query-level evidence for independent metric recomputation."""
    prior_count = batch.regions.prior_features.shape[1]
    current_count = batch.regions.current_features.shape[1]
    oracle_real = batch.oracle.plan.transport[:, :prior_count, :current_count]
    soft_real = soft.transport[:, :prior_count, :current_count]
    hard_real = hard.transport[:, :prior_count, :current_count]
    hard_correct: list[int] = []
    soft_mass: list[float] = []
    nll: list[float] = []
    brier: list[float] = []
    probability_rows: list[list[float]] = []
    oracle_current_indices: list[int] = []
    for case_index in torch.nonzero(batch.persistent_main_mask).flatten().tolist():
        query_prior = int(torch.nonzero(batch.prior_query_marker[case_index]).item())
        oracle_current = int(
            torch.nonzero(oracle_real[case_index, query_prior] > 0.5).item()
        )
        predicted = torch.nonzero(
            hard_real[case_index, query_prior] > 0.5, as_tuple=False
        ).flatten()
        hard_correct.append(
            int(len(predicted) == 1 and int(predicted.item()) == oracle_current)
        )
        row = soft_real[case_index, query_prior]
        probability_row = row.detach().cpu().tolist()
        probability_rows.append(probability_row)
        oracle_current_indices.append(oracle_current)
        mass = probability_row[oracle_current]
        soft_mass.append(mass)
        nll.append(-math.log(max(mass, 1e-8)))
        brier.append(
            math.fsum(
                (value - (1.0 if column == oracle_current else 0.0)) ** 2
                for column, value in enumerate(probability_row)
            )
            / len(probability_row)
        )
    return {
        "hard_query_correct": hard_correct,
        "soft_oracle_query_mass_values": soft_mass,
        "soft_query_nll_values": nll,
        "soft_query_brier_values": brier,
        "soft_query_probability_rows": probability_rows,
        "oracle_current_indices": oracle_current_indices,
    }


def _transport_metrics(
    batch: QueryAnchorBatch, soft: MatchPlan, hard: MatchPlan
) -> dict[str, Any]:
    oracle = batch.oracle.plan.transport.to(soft.transport.dtype)
    soft_oracle_mass = float(
        (oracle * soft.transport).sum() / oracle.sum().clamp_min(1.0)
    )
    query = _assignment_diagnostics(batch, soft, hard)
    prior_count = batch.regions.prior_features.shape[1]
    predicted_rows = hard.transport[:, :prior_count, :].argmax(dim=-1)
    oracle_rows = batch.oracle.plan.transport[:, :prior_count, :].argmax(dim=-1)
    valid_rows = batch.regions.prior_valid
    row_actual = oracle_rows[valid_rows].detach().cpu().tolist()
    row_predicted = predicted_rows[valid_rows].detach().cpu().tolist()
    oracle_support = oracle > 0
    soft_oracle_values = soft.transport[oracle_support]
    return {
        "hard_all_endpoint_assignment_accuracy": assignment_accuracy(
            hard, batch.oracle.plan, batch.regions
        ),
        "soft_all_endpoint_oracle_mass": soft_oracle_mass,
        "row_top1_accuracy": float(
            (predicted_rows[valid_rows] == oracle_rows[valid_rows]).float().mean()
        ),
        "null_metrics": _null_metrics(batch, hard),
        "query": query,
        "soft_plan_sha256": _tensor_hash(soft.transport),
        "hard_plan_sha256": _tensor_hash(hard.transport),
        "metric_evidence": {
            "hard_endpoint_correct": [
                int(predicted == actual)
                for predicted, actual in zip(row_predicted, row_actual, strict=True)
            ],
            "row_top1_actual": row_actual,
            "row_top1_predicted": row_predicted,
            "soft_endpoint_oracle_mass_values": soft_oracle_values.detach()
            .cpu()
            .tolist(),
            "soft_endpoint_oracle_mass_denominator": float(oracle.sum()),
            "query": _query_metric_evidence(batch, soft, hard),
        },
    }


def _train_transport(
    *,
    seed: int,
    strata: Mapping[str, Mapping[str, QueryAnchorBatch]],
    steps: int,
) -> dict[str, Any]:
    matcher = _new_matcher(seed)
    initialization = _initialization_evidence(seed, matcher)
    initial_state = _state_hash(matcher)
    trainable_names = sorted(
        name for name, value in matcher.named_parameters() if value.requires_grad
    )
    optimizer_names = list(trainable_names)
    optimizer = torch.optim.AdamW(
        matcher.parameters(), lr=TRANSPORT_LEARNING_RATE, weight_decay=0.0
    )
    losses: list[float] = []
    finite_gradient_steps = 0
    nonzero_gradient_steps = 0
    for _ in range(steps):
        optimizer.zero_grad(set_to_none=True)
        stratum_losses = []
        for stratum in STRATA:
            batch = strata[stratum]["train"]
            soft = matcher.soft_plan(_matching_regions(batch))
            stratum_losses.append(_transport_supervision_loss(soft, batch.oracle.plan))
        loss = torch.stack(stratum_losses).mean()
        loss.backward()
        parameters = tuple(matcher.parameters())
        gradients_finite = all(
            parameter.grad is not None and bool(torch.isfinite(parameter.grad).all())
            for parameter in parameters
        )
        gradient_nonzero = any(
            parameter.grad is not None and bool(parameter.grad.ne(0).any())
            for parameter in parameters
        )
        finite_gradient_steps += int(gradients_finite)
        nonzero_gradient_steps += int(gradient_nonzero)
        torch.nn.utils.clip_grad_norm_(parameters, GRADIENT_CLIP_NORM)
        optimizer.step()
        losses.append(float(loss.detach()))

    final_state = _state_hash(matcher)
    for parameter in matcher.parameters():
        parameter.requires_grad_(False)
        parameter.grad = None
    matcher.eval()
    frozen_state = _state_hash(matcher)
    return {
        "matcher": matcher,
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "seed": int(seed),
        "initialization": initialization,
        "initial_state_sha256": initial_state,
        "final_state_sha256": final_state,
        "frozen_state_sha256": frozen_state,
        "state_unchanged_by_freeze": final_state == frozen_state,
        "trainable_parameter_names": trainable_names,
        "optimizer_parameter_names": optimizer_names,
        "optimizer_only_matcher": set(optimizer_names) == set(trainable_names),
        "initial_loss": losses[0] if losses else None,
        "final_loss": losses[-1] if losses else None,
        "finite_gradient_steps": finite_gradient_steps,
        "nonzero_gradient_steps": nonzero_gradient_steps,
        "registered_gradient_steps": steps,
        "all_gradients_finite": finite_gradient_steps == steps,
        "matcher_changed": initial_state != final_state,
        "normalized_view_weights": matcher.normalized_view_weights().detach().tolist(),
        "residual_coefficient": float(
            torch.tanh(matcher.residual_coefficient).detach()
        ),
        "effective_null_utilities": [
            float(value.detach()) for value in matcher.effective_null_utilities()
        ],
        "evaluations": {stratum: {} for stratum in STRATA},
    }


def _evaluate_transport_results(
    results: Mapping[str, dict[str, Any]],
    batches: Mapping[str, Mapping[str, QueryAnchorBatch]],
) -> None:
    with torch.inference_mode():
        for result in results.values():
            matcher = result["matcher"]
            all_evaluations = result.setdefault("evaluations", {})
            for stratum, split_batches in batches.items():
                evaluations = all_evaluations.setdefault(stratum, {})
                for split, batch in split_batches.items():
                    visible = _matching_regions(batch)
                    evaluations[split] = _transport_metrics(
                        batch,
                        matcher.soft_plan(visible),
                        matcher.hard_plan(visible),
                    )


def _transport_gates(
    results: Mapping[str, Mapping[str, Any]], seeds: Sequence[int]
) -> tuple[dict[str, Any], dict[str, Any]]:
    clean_hard = {
        str(seed): results[str(seed)]["evaluations"]["clean"]["development"][
            "hard_all_endpoint_assignment_accuracy"
        ]
        for seed in seeds
    }
    clean_soft = {
        str(seed): results[str(seed)]["evaluations"]["clean"]["development"]["query"][
            "soft_oracle_query_mass"
        ]
        for seed in seeds
    }
    clean_null = {
        str(seed): results[str(seed)]["evaluations"]["clean"]["development"][
            "null_metrics"
        ]
        for seed in seeds
    }
    clean_checks = {
        "seed_specific_initial_hashes_distinct": len(
            {results[str(seed)]["initialization"]["state_sha256"] for seed in seeds}
        )
        == len(seeds),
        "initial_hashes_rederive_exactly": all(
            results[str(seed)]["initialization"]["state_sha256"]
            == _initialization_evidence(seed, _new_matcher(seed))[
                "raw_initial_state_sha256"
            ]
            for seed in seeds
        ),
        "every_seed_hard_at_least_0_90": all(
            value >= 0.90 for value in clean_hard.values()
        ),
        "aggregate_hard_at_least_0_95": sum(clean_hard.values()) / len(clean_hard)
        >= 0.95,
        "every_seed_soft_at_least_0_30": all(
            value >= 0.30 for value in clean_soft.values()
        ),
        "aggregate_soft_at_least_0_35": sum(clean_soft.values()) / len(clean_soft)
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
            value["positive_support_both"] for value in clean_null.values()
        ),
        "all_transport_gradients_finite": all(
            result["all_gradients_finite"] for result in results.values()
        ),
        "optimizer_only_matcher": all(
            result["optimizer_only_matcher"] for result in results.values()
        ),
        "matcher_checkpoint_frozen": all(
            result["state_unchanged_by_freeze"] for result in results.values()
        ),
    }
    clean_gate = {
        "status": "PASS" if all(clean_checks.values()) else "FAIL_TRANSPORT_COMPETENCE",
        "passed": all(clean_checks.values()),
        "checks": clean_checks,
        "hard_by_seed": clean_hard,
        "soft_by_seed": clean_soft,
        "null_metrics_by_seed": clean_null,
    }

    challenge_available = all(
        "development" in results[str(seed)]["evaluations"]["challenge"]
        for seed in seeds
    )
    if not challenge_available:
        return clean_gate, {
            "status": "NOT_RUN_ANTI_EQUIVALENCE",
            "passed": False,
            "checks": {"challenge_development_authorized": False},
            "hard_by_seed": {},
            "soft_by_seed": {},
        }
    challenge_hard = {
        str(seed): results[str(seed)]["evaluations"]["challenge"]["development"][
            "hard_all_endpoint_assignment_accuracy"
        ]
        for seed in seeds
    }
    challenge_soft = {
        str(seed): results[str(seed)]["evaluations"]["challenge"]["development"][
            "query"
        ]["soft_oracle_query_mass"]
        for seed in seeds
    }
    challenge_checks = {
        "every_seed_hard_at_least_0_70": all(
            value >= 0.70 for value in challenge_hard.values()
        ),
        "aggregate_hard_at_least_0_80": sum(challenge_hard.values())
        / len(challenge_hard)
        >= 0.80,
        "every_seed_soft_at_least_0_30": all(
            value >= 0.30 for value in challenge_soft.values()
        ),
        "aggregate_soft_at_least_0_35": sum(challenge_soft.values())
        / len(challenge_soft)
        >= 0.35,
        "matcher_changed": all(
            result["matcher_changed"] for result in results.values()
        ),
    }
    challenge_gate = {
        "status": "PASS" if all(challenge_checks.values()) else "FAIL_ANTI_EQUIVALENCE",
        "passed": all(challenge_checks.values()),
        "checks": challenge_checks,
        "hard_by_seed": challenge_hard,
        "soft_by_seed": challenge_soft,
    }
    return clean_gate, challenge_gate


def _exact64_readout_audit(
    *,
    trace: Mapping[str, int],
    expected_trace: Mapping[str, int],
    audits: Mapping[str, Mapping[str, Any]],
    adapter_unchanged: bool,
    projector_frozen_after_fit: bool,
    matcher_unchanged: bool,
) -> dict[str, Any]:
    checks = {
        "adapter_calls_exact": dict(trace) == dict(expected_trace),
        "total_adapter_calls_exact": sum(trace.values())
        == sum(expected_trace.values()),
        "all_placeholders_exact64": all(
            bool(audit["placeholder_count"].eq(64).all()) for audit in audits.values()
        ),
        "no_pixels": all(
            audit["pixel_inputs_used"] is False for audit in audits.values()
        ),
        "frozen_adapter_reported": all(
            bool(audit["model_frozen"]) for audit in audits.values()
        ),
        "adapter_state_unchanged": adapter_unchanged,
        "projector_frozen_after_fit": projector_frozen_after_fit,
        "matcher_state_unchanged": matcher_unchanged,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "observed_adapter_score_calls": dict(trace),
        "expected_adapter_score_calls": dict(expected_trace),
        "observed_total_adapter_score_calls": sum(trace.values()),
        "expected_total_adapter_score_calls": sum(expected_trace.values()),
        "placeholder_counts": {
            phase: audit["placeholder_count"].tolist()
            for phase, audit in audits.items()
        },
        "phase_evidence": {
            phase: {
                "pixel_inputs_used": bool(audit["pixel_inputs_used"]),
                "model_frozen": bool(audit["model_frozen"]),
            }
            for phase, audit in audits.items()
        },
    }


def _fit_readout(
    *,
    adapter: nn.Module,
    seed: int,
    strata: Mapping[str, Mapping[str, QueryAnchorBatch]],
    plans: Mapping[str, Mapping[str, MatchPlan]],
    steps: int,
    phase_prefix: str,
    frozen_matcher: InvariantPartialOTMatcher | None = None,
) -> dict[str, Any]:
    projector = QueryRelationProjector(QUERY_RAW_DIM, QUERY_HIDDEN_SIZE)
    initial_state = copy.deepcopy(_initial_projector(seed).state_dict())
    projector.load_state_dict(initial_state, strict=True)
    initial_hash = _state_hash(projector)
    adapter_before = _state_hash(adapter)
    matcher_before = _state_hash(frozen_matcher) if frozen_matcher is not None else None
    if frozen_matcher is not None and any(
        parameter.requires_grad for parameter in frozen_matcher.parameters()
    ):
        raise ValueError("mediator stage requires a frozen matcher")
    optimizer = torch.optim.AdamW(
        projector.parameters(), lr=MEDIATOR_LEARNING_RATE, weight_decay=0.0
    )
    trace: dict[str, int] = {}
    losses: list[float] = []
    finite_gradient_steps = 0
    for _ in range(steps):
        optimizer.zero_grad(set_to_none=True)
        stratum_losses = []
        for stratum in STRATA:
            batch = strata[stratum]["train"]
            scores = _adapter_scores(
                projector,
                adapter,
                _contract(batch, plans[stratum]["train"]),
                trace=trace,
                phase=f"{phase_prefix}_training_{stratum}",
            )
            stratum_losses.append(F.cross_entropy(scores, batch.oracle.labels))
        loss = torch.stack(stratum_losses).mean()
        loss.backward()
        gradients_finite = all(
            parameter.grad is not None and bool(torch.isfinite(parameter.grad).all())
            for parameter in projector.parameters()
        )
        finite_gradient_steps += int(gradients_finite)
        optimizer.step()
        losses.append(float(loss.detach()))

    final_train_hash = _state_hash(projector)
    for parameter in projector.parameters():
        parameter.requires_grad_(False)
        parameter.grad = None
    projector.eval()
    frozen_projector_hash = _state_hash(projector)
    metrics: dict[str, Any] = {}
    audits: dict[str, Mapping[str, Any]] = {}
    with torch.inference_mode():
        for stratum in STRATA:
            metrics[stratum] = {}
            for split in ("train", "development"):
                phase = f"{phase_prefix}_final_{stratum}_{split}"
                scores, audit = _adapter_scores(
                    projector,
                    adapter,
                    _contract(strata[stratum][split], plans[stratum][split]),
                    return_audit=True,
                    trace=trace,
                    phase=phase,
                )
                metrics[stratum][split] = _label_metrics(
                    scores, strata[stratum][split].oracle.labels
                )
                audits[phase] = audit
    adapter_after = _state_hash(adapter)
    matcher_after = _state_hash(frozen_matcher) if frozen_matcher is not None else None
    expected_trace = {f"{phase_prefix}_training_{stratum}": steps for stratum in STRATA}
    expected_trace.update(
        {
            f"{phase_prefix}_final_{stratum}_{split}": 1
            for stratum in STRATA
            for split in ("train", "development")
        }
    )
    matcher_gradient_non_none_count = (
        0
        if frozen_matcher is None
        else sum(
            parameter.grad is not None for parameter in frozen_matcher.parameters()
        )
    )
    matcher_gradient_nonzero_count = (
        0
        if frozen_matcher is None
        else sum(
            parameter.grad is not None and bool(parameter.grad.ne(0).any())
            for parameter in frozen_matcher.parameters()
        )
    )
    matcher_gradients_zero = matcher_gradient_non_none_count == 0
    exact64 = _exact64_readout_audit(
        trace=trace,
        expected_trace=expected_trace,
        audits=audits,
        adapter_unchanged=adapter_before == adapter_after,
        projector_frozen_after_fit=all(
            not parameter.requires_grad for parameter in projector.parameters()
        ),
        matcher_unchanged=matcher_before == matcher_after,
    )
    return {
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "model": projector,
        "execution_kind": phase_prefix,
        "initial_state_sha256": initial_hash,
        "final_train_state_sha256": final_train_hash,
        "frozen_state_sha256": frozen_projector_hash,
        "projector_state_unchanged_by_freeze": final_train_hash
        == frozen_projector_hash,
        "adapter_before_sha256": adapter_before,
        "adapter_after_sha256": adapter_after,
        "adapter_unchanged": adapter_before == adapter_after,
        "matcher_before_sha256": matcher_before,
        "matcher_after_sha256": matcher_after,
        "matcher_unchanged": matcher_before == matcher_after,
        "matcher_gradients_zero": matcher_gradients_zero,
        "matcher_gradient_non_none_count": matcher_gradient_non_none_count,
        "matcher_gradient_nonzero_count": matcher_gradient_nonzero_count,
        "trainable_parameter_names": sorted(initial_state),
        "optimizer_parameter_names": sorted(initial_state),
        "optimizer_only_projector": True,
        "initial_loss": losses[0] if losses else None,
        "final_loss": losses[-1] if losses else None,
        "finite_gradient_steps": finite_gradient_steps,
        "registered_gradient_steps": steps,
        "all_gradients_finite": finite_gradient_steps == steps,
        "exact64_execution_audit": exact64,
        "metrics": metrics,
        "plan_sha256": {
            stratum: {
                split: _tensor_hash(plans[stratum][split].transport)
                for split in ("train", "development")
            }
            for stratum in STRATA
        },
    }


def _oracle_plans(
    strata: Mapping[str, Mapping[str, QueryAnchorBatch]],
) -> dict[str, dict[str, MatchPlan]]:
    return {
        stratum: {split: batch.oracle.plan for split, batch in strata[stratum].items()}
        for stratum in STRATA
    }


def _frozen_matcher_plans(
    matcher: InvariantPartialOTMatcher,
    strata: Mapping[str, Mapping[str, QueryAnchorBatch]],
) -> dict[str, dict[str, MatchPlan]]:
    if any(parameter.requires_grad for parameter in matcher.parameters()):
        raise ValueError("plans may only be materialized from the frozen matcher")
    plans: dict[str, dict[str, MatchPlan]] = {}
    with torch.inference_mode():
        for stratum in STRATA:
            plans[stratum] = {
                split: matcher.soft_plan(_matching_regions(strata[stratum][split]))
                for split in ("train", "development")
            }
    return plans


def _score_frozen_readout(
    *,
    projector: QueryRelationProjector,
    adapter: nn.Module,
    batch: QueryAnchorBatch,
    plan: MatchPlan,
    phase: str,
) -> dict[str, Any]:
    projector_before = _state_hash(projector)
    adapter_before = _state_hash(adapter)
    if any(parameter.requires_grad for parameter in projector.parameters()):
        raise ValueError("fixed-plan evaluation requires frozen projector")
    trace: dict[str, int] = {}
    with torch.inference_mode():
        scores, audit = _adapter_scores(
            projector,
            adapter,
            _contract(batch, plan),
            return_audit=True,
            trace=trace,
            phase=phase,
        )
    projector_after = _state_hash(projector)
    adapter_after = _state_hash(adapter)
    checks = {
        "single_exact64_call": trace == {phase: 1},
        "placeholders_exact64": bool(audit["placeholder_count"].eq(64).all()),
        "no_pixels": audit["pixel_inputs_used"] is False,
        "adapter_frozen": bool(audit["model_frozen"]),
        "projector_unchanged": projector_before == projector_after,
        "adapter_unchanged": adapter_before == adapter_after,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "metrics": _label_metrics(scores, batch.oracle.labels),
        "plan_sha256": _tensor_hash(plan.transport),
        "projector_sha256": projector_before,
        "adapter_sha256": adapter_before,
        "projector_before_sha256": projector_before,
        "projector_after_sha256": projector_after,
        "adapter_before_sha256": adapter_before,
        "adapter_after_sha256": adapter_after,
        "observed_adapter_score_calls": trace,
        "expected_adapter_score_calls": {phase: 1},
        "placeholder_counts": {phase: audit["placeholder_count"].tolist()},
        "phase_evidence": {
            phase: {
                "pixel_inputs_used": bool(audit["pixel_inputs_used"]),
                "model_frozen": bool(audit["model_frozen"]),
            }
        },
    }


def _score_local_frozen_readout(
    *,
    projector: QueryRelationProjector,
    adapter: nn.Module,
    batch: QueryAnchorBatch,
    local_output: Mapping[str, Tensor],
    phase: str,
) -> dict[str, Any]:
    projector_before = _state_hash(projector)
    adapter_before = _state_hash(adapter)
    if any(parameter.requires_grad for parameter in projector.parameters()):
        raise ValueError("local baseline evaluation requires frozen projector")
    trace: dict[str, int] = {}
    contract = _local_query_contract(batch, local_output)
    with torch.inference_mode():
        scores, audit = _adapter_scores(
            projector,
            adapter,
            contract,
            return_audit=True,
            trace=trace,
            phase=phase,
        )
    projector_after = _state_hash(projector)
    adapter_after = _state_hash(adapter)
    checks = {
        "single_exact64_call": trace == {phase: 1},
        "placeholders_exact64": bool(audit["placeholder_count"].eq(64).all()),
        "no_pixels": audit["pixel_inputs_used"] is False,
        "adapter_frozen": bool(audit["model_frozen"]),
        "projector_unchanged": projector_before == projector_after,
        "adapter_unchanged": adapter_before == adapter_after,
        "pure_row_local": True,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "metrics": _label_metrics(scores, batch.oracle.labels),
        "local_output_sha256": _json_hash(
            {key: _tensor_hash(value) for key, value in local_output.items()}
        ),
        "contract_tokens_sha256": _tensor_hash(contract.tokens),
        "projector_sha256": projector_before,
        "adapter_sha256": adapter_before,
        "projector_before_sha256": projector_before,
        "projector_after_sha256": projector_after,
        "adapter_before_sha256": adapter_before,
        "adapter_after_sha256": adapter_after,
        "observed_adapter_score_calls": trace,
        "expected_adapter_score_calls": {phase: 1},
        "placeholder_counts": {phase: audit["placeholder_count"].tolist()},
        "phase_evidence": {
            phase: {
                "pixel_inputs_used": bool(audit["pixel_inputs_used"]),
                "model_frozen": bool(audit["model_frozen"]),
            }
        },
    }


def _fixture_gate(
    *,
    strata: Mapping[str, Mapping[str, QueryAnchorBatch]],
    raw_challenge: Mapping[str, R5ChallengeBatch],
    adapter: nn.Module,
    oracle_readouts: Mapping[str, Mapping[str, Any]],
    seeds: Sequence[int],
    steps: int,
    enforce_competence: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    controls: dict[str, Any] = {}
    for seed in seeds:
        controls[str(seed)] = {
            mode: _train_marginal_control(
                seed=seed,
                train_batch=strata["challenge"]["train"],
                development_batch=strata["challenge"]["development"],
                mode=mode,
                steps=steps,
            )
            for mode in (
                "current_only",
                "prior_current_separate_pooling",
                "current_only_deepsets",
                "prior_only_deepsets",
                "prior_current_deepsets",
            )
        }
    marginal_gate = _evaluate_marginal_control_gate(
        controls,
        tuple(int(seed) for seed in seeds),
        competence_required=enforce_competence,
    )

    oracle_checks: dict[str, Any] = {}
    binding_results: dict[str, Any] = {}
    binding_deltas: dict[str, float] = {}
    binding_isomorphism: dict[str, Any] = {}
    for seed in seeds:
        key = str(seed)
        result = oracle_readouts[key]
        oracle_checks[key] = {
            stratum: {
                "train_persistent_at_least_0_95": result["metrics"][stratum]["train"][
                    "persistent_three_label_macro_f1"
                ]
                >= 0.95,
                "development_persistent_at_least_0_85": result["metrics"][stratum][
                    "development"
                ]["persistent_three_label_macro_f1"]
                >= 0.85,
            }
            for stratum in STRATA
        }
        oracle_checks[key]["execution"] = {
            "exact64": result["exact64_execution_audit"]["passed"],
            "adapter_unchanged": result["adapter_unchanged"],
            "projector_frozen": result["projector_state_unchanged_by_freeze"],
            "oracle_fit_once": result["execution_kind"] == "oracle_readout",
        }
        projector = result["model"]
        derangements = build_balanced_derangement_bank(
            strata["clean"]["development"], REGISTERED_DERANGEMENT_SEEDS
        )
        binding_results[key] = {}
        binding_isomorphism[key] = {}
        oracle_value = result["metrics"]["clean"]["development"][
            "persistent_three_label_macro_f1"
        ]
        cells = []
        for derangement_seed, plan in derangements.items():
            scored = _score_frozen_readout(
                projector=projector,
                adapter=adapter,
                batch=strata["clean"]["development"],
                plan=plan,
                phase=f"binding_derangement_{derangement_seed}",
            )
            binding_results[key][str(derangement_seed)] = scored
            binding_isomorphism[key][str(derangement_seed)] = {
                "passed": scored["passed"]
                and scored["projector_sha256"] == _state_hash(projector)
                and scored["adapter_sha256"] == _state_hash(adapter)
                and scored["plan_sha256"]
                != _tensor_hash(strata["clean"]["development"].oracle.plan.transport),
                "shared_batch_sha256": _json_hash(
                    _batch_tensor_snapshot(strata["clean"]["development"])
                ),
                "b4a_batch_sha256": _json_hash(
                    _batch_tensor_snapshot(strata["clean"]["development"])
                ),
                "b4b_batch_sha256": _json_hash(
                    _batch_tensor_snapshot(strata["clean"]["development"])
                ),
                "b4a_plan_sha256": scored["plan_sha256"],
                "b4b_plan_sha256": _tensor_hash(
                    strata["clean"]["development"].oracle.plan.transport
                ),
                "projector_sha256": scored["projector_sha256"],
                "adapter_sha256": scored["adapter_sha256"],
            }
            cells.append(
                100.0
                * (oracle_value - scored["metrics"]["persistent_three_label_macro_f1"])
            )
        binding_deltas[key] = sum(cells) / len(cells)

    oracle_pass = all(
        all(all(checks.values()) for checks in per_seed.values())
        for per_seed in oracle_checks.values()
    )
    binding_pass = (
        all(value > 0.0 for value in binding_deltas.values())
        and sum(binding_deltas.values()) / len(binding_deltas) >= 5.0
        and all(
            scored["passed"]
            for seed_results in binding_results.values()
            for scored in seed_results.values()
        )
    )
    expected_challenge_hashes = FROZEN_R5_REGISTRY["fixture_hashes"]["challenge"]
    challenge_audits: dict[str, Any] = {}
    for split in ("train", "development"):
        raw = raw_challenge[split]
        prefix = split
        observed = _raw_fixture_hashes(raw)
        checks = {
            "visible_hash_exact": observed["visible"]
            == expected_challenge_hashes[f"{prefix}_visible"],
            "oracle_hash_exact": observed["hidden_oracle"]
            == expected_challenge_hashes[f"{prefix}_oracle"],
            "full_fixture_hash_exact": observed["full_fixture"]
            == expected_challenge_hashes[f"{prefix}_full"],
        }
        challenge_audits[split] = {
            "passed": all(checks.values()),
            "checks": checks,
            "observed_hashes": observed,
        }
    leakage_certificate = FROZEN_R5_REGISTRY["fixture_leakage_attack"]
    leakage_certificate_pass = bool(
        leakage_certificate["training_or_fitting"] == "none_deterministic_attack"
        and leakage_certificate["frozen_train_to_development_accuracy"]
        <= leakage_certificate["accuracy_max"]
        + leakage_certificate["numeric_tolerance"]
        and leakage_certificate["frozen_train_to_development_macro_f1"]
        <= leakage_certificate["macro_f1_max"]
        + leakage_certificate["numeric_tolerance"]
        and leakage_certificate["frozen_unseen_development_signature_count"] == 0
    )
    analytic_challenge_pass = (
        all(audit["passed"] for audit in challenge_audits.values())
        and leakage_certificate_pass
    )
    gate_checks = {
        "oracle_readout_competent_both_strata": oracle_pass,
        "challenge_analytic_identifiability": analytic_challenge_pass,
        "challenge_row_local_state_attack_blocked": leakage_certificate_pass,
        "marginal_bypass_bank": marginal_gate["passed"],
        "frozen_readout_binding": binding_pass,
        "b4_isomorphism": all(
            audit["passed"]
            for seed_audits in binding_isomorphism.values()
            for audit in seed_audits.values()
        ),
    }
    gate = {
        "status": "PASS"
        if all(gate_checks.values())
        else "FAIL_FIXTURE_IDENTIFIABILITY",
        "passed": all(gate_checks.values()),
        "checks": gate_checks,
        "oracle_checks": oracle_checks,
        "marginal_control_gate": marginal_gate,
        "binding_delta_by_seed_percentage_points": binding_deltas,
        "binding_aggregate_delta_percentage_points": sum(binding_deltas.values())
        / len(binding_deltas),
        "challenge_audit_sha256_by_split": {
            split: _json_hash(audit) for split, audit in challenge_audits.items()
        },
        "source_hashed_leakage_certificate_sha256": _json_hash(leakage_certificate),
        "b4_isomorphism": binding_isomorphism,
    }
    return gate, controls, binding_results


def _mediator_gate(
    results: Mapping[str, Mapping[str, Any]], seeds: Sequence[int]
) -> dict[str, Any]:
    f1 = {
        str(seed): {
            stratum: results[str(seed)]["metrics"][stratum]["development"][
                "persistent_three_label_macro_f1"
            ]
            for stratum in STRATA
        }
        for seed in seeds
    }
    checks = {
        "every_seed_every_stratum_persistent_f1_at_least_0_80": all(
            value >= 0.80 for values in f1.values() for value in values.values()
        ),
        "each_stratum_aggregate_persistent_f1_at_least_0_85": all(
            sum(f1[str(seed)][stratum] for seed in seeds) / len(seeds) >= 0.85
            for stratum in STRATA
        ),
        "matcher_gradient_exactly_zero": all(
            result["matcher_gradients_zero"] for result in results.values()
        ),
        "matcher_state_unchanged": all(
            result["matcher_unchanged"] for result in results.values()
        ),
        "exact64": all(
            result["exact64_execution_audit"]["passed"] for result in results.values()
        ),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL_MEDIATOR_RECOVERY",
        "passed": all(checks.values()),
        "checks": checks,
        "persistent_f1_by_seed_and_stratum": f1,
    }


def _local_row_logits(
    matcher: InvariantPartialOTMatcher, batch: QueryAnchorBatch
) -> Tensor:
    regions = _matching_regions(batch)
    edge, prior_null, _ = matcher.compute_utilities(regions)
    compatible = regions.prior_valid[:, :, None] & regions.current_valid[:, None, :]
    compatible = compatible & (
        regions.prior_anatomy[:, :, None] == regions.current_anatomy[:, None, :]
    )
    edge = edge.masked_fill(~compatible, -torch.inf)
    return torch.cat((edge, prior_null.unsqueeze(-1)), dim=-1)


def _local_supervision_loss(
    matcher: InvariantPartialOTMatcher, batch: QueryAnchorBatch
) -> Tensor:
    row_logits = _local_row_logits(matcher, batch)
    oracle = batch.oracle.plan.transport
    prior_count = batch.regions.prior_features.shape[1]
    current_count = batch.regions.current_features.shape[1]
    row_targets = oracle[:, :prior_count, :].argmax(dim=-1)
    prior_valid = batch.regions.prior_valid
    row_loss = F.cross_entropy(
        row_logits[prior_valid], row_targets[prior_valid], reduction="mean"
    )
    # Keep the fifth scalar in the matched optimizer without introducing any
    # column normalization or competition.  It receives an independent unary
    # birth-rate target only.
    oracle_birth = oracle[:, prior_count, :current_count]
    _, effective_birth = matcher.effective_null_utilities()
    birth_logits = effective_birth.expand_as(oracle_birth)
    birth_loss = F.binary_cross_entropy_with_logits(
        birth_logits[batch.regions.current_valid],
        oracle_birth[batch.regions.current_valid],
    )
    return 0.5 * (row_loss + birth_loss)


def _local_row_output(
    matcher: InvariantPartialOTMatcher, batch: QueryAnchorBatch
) -> dict[str, Tensor]:
    row_logits = _local_row_logits(matcher, batch)
    row_probabilities = torch.softmax(row_logits, dim=-1)
    row_choice = row_logits.argmax(dim=-1)
    batch_size, prior_count = row_choice.shape
    current_count = batch.regions.current_features.shape[1]
    birth_mask = torch.zeros(
        (batch_size, current_count), dtype=torch.bool, device=row_logits.device
    )
    for case in range(batch_size):
        selected: set[int] = set()
        for prior in range(prior_count):
            if not bool(batch.regions.prior_valid[case, prior]):
                continue
            current = int(row_choice[case, prior])
            if current < current_count and bool(
                batch.regions.current_valid[case, current]
            ):
                selected.add(current)
        for current in range(current_count):
            birth_mask[case, current] = bool(
                batch.regions.current_valid[case, current] and current not in selected
            )
    return {
        "row_logits": row_logits,
        "row_probabilities": row_probabilities,
        "row_top1": row_choice,
        "birth_mask": birth_mask,
    }


def _local_row_metrics(
    batch: QueryAnchorBatch, output: Mapping[str, Tensor]
) -> dict[str, Any]:
    prior_count = batch.regions.prior_features.shape[1]
    current_count = batch.regions.current_features.shape[1]
    target = batch.oracle.plan.transport[:, :prior_count, :].argmax(dim=-1)
    valid = batch.regions.prior_valid
    predicted = output["row_top1"]
    row_top1 = float((predicted[valid] == target[valid]).float().mean())
    duplicate_rows = 0
    selected_rows = 0
    for case in range(predicted.shape[0]):
        choices = predicted[case][valid[case]]
        real = choices[choices < current_count]
        duplicate_rows += int(real.numel() - real.unique().numel())
        selected_rows += int(real.numel())
    return {
        "row_top1_accuracy": row_top1,
        "row_top1_actual": target[valid].detach().cpu().tolist(),
        "row_top1_predicted": predicted[valid].detach().cpu().tolist(),
        "row_top1_correct_count": int((predicted[valid] == target[valid]).sum()),
        "row_top1_support_count": int(valid.sum()),
        "duplicate_current_rows": duplicate_rows,
        "selected_real_rows": selected_rows,
        "duplicate_current_rate": duplicate_rows / selected_rows
        if selected_rows
        else 0.0,
        "row_probability_sha256": _tensor_hash(output["row_probabilities"]),
        "row_top1_sha256": _tensor_hash(predicted),
        "birth_mask_sha256": _tensor_hash(output["birth_mask"]),
    }


def _local_query_contract(
    batch: QueryAnchorBatch, output: Mapping[str, Tensor]
) -> QueryTokenContract:
    regions = batch.regions
    batch_size, prior_count, _ = regions.prior_features.shape
    current_count = regions.current_features.shape[1]
    tokens = regions.prior_features.new_zeros((batch_size, TOKEN_BUDGET, QUERY_RAW_DIM))
    prior_states = regions.prior_features[..., 1]
    current_states = regions.current_features[..., 1]
    row_probabilities = output["row_probabilities"]
    for case in range(batch_size):
        payload = tokens[case, QUERY_RELATION_SLOT]
        payload[0] = 1.0
        prior_hits = torch.nonzero(batch.prior_query_marker[case]).flatten()
        if len(prior_hits) == 1:
            prior = int(prior_hits.item())
            real = row_probabilities[case, prior, :current_count]
            payload[1] = prior_states[case, prior]
            payload[2] = (real * current_states[case]).sum()
            payload[3] = real.sum()
            payload[4] = row_probabilities[case, prior, current_count]
        else:
            current = int(torch.nonzero(batch.current_query_marker[case]).item())
            payload[2] = current_states[case, current]
            payload[5] = output["birth_mask"][case, current].to(tokens.dtype)
    token_types = torch.cat(
        (
            torch.zeros(GLOBAL_TOKENS, dtype=torch.long),
            torch.ones(ENTITY_TOKENS, dtype=torch.long),
            torch.full((RELATION_TOKENS,), 2, dtype=torch.long),
            torch.full((RESERVED_TOKENS,), 3, dtype=torch.long),
        )
    ).to(tokens.device)
    contract = QueryTokenContract(
        tokens=tokens,
        valid_mask=torch.ones(
            batch_size, TOKEN_BUDGET, dtype=torch.bool, device=tokens.device
        ),
        attention_mask=torch.ones(
            batch_size, TOKEN_BUDGET, dtype=torch.long, device=tokens.device
        ),
        token_types=token_types,
        position_ids=torch.arange(TOKEN_BUDGET, dtype=torch.long, device=tokens.device)
        .expand(3, batch_size, -1)
        .clone(),
        query_relation_slot=torch.full(
            (batch_size,), QUERY_RELATION_SLOT, dtype=torch.long, device=tokens.device
        ),
        neutral_embedding=torch.zeros(
            QUERY_RAW_DIM, dtype=tokens.dtype, device=tokens.device
        ),
    )
    contract.validate()
    return contract


def _train_local_baseline(
    *, seed: int, strata: Mapping[str, Mapping[str, QueryAnchorBatch]], steps: int
) -> dict[str, Any]:
    matcher = _new_matcher(seed)
    initialization = _initialization_evidence(seed, matcher)
    optimizer = torch.optim.AdamW(
        matcher.parameters(), lr=TRANSPORT_LEARNING_RATE, weight_decay=0.0
    )
    finite_gradient_steps = 0
    nonzero_gradient_steps = 0
    losses: list[float] = []
    for _ in range(steps):
        optimizer.zero_grad(set_to_none=True)
        loss = torch.stack(
            [_local_supervision_loss(matcher, strata[name]["train"]) for name in STRATA]
        ).mean()
        loss.backward()
        gradients = [parameter.grad for parameter in matcher.parameters()]
        finite = all(
            gradient is not None and bool(torch.isfinite(gradient).all())
            for gradient in gradients
        )
        nonzero = any(
            gradient is not None and bool(gradient.ne(0).any())
            for gradient in gradients
        )
        finite_gradient_steps += int(finite)
        nonzero_gradient_steps += int(nonzero)
        torch.nn.utils.clip_grad_norm_(matcher.parameters(), GRADIENT_CLIP_NORM)
        optimizer.step()
        losses.append(float(loss.detach()))
    final_state = _state_hash(matcher)
    for parameter in matcher.parameters():
        parameter.requires_grad_(False)
        parameter.grad = None
    matcher.eval()
    frozen_state = _state_hash(matcher)
    evaluations: dict[str, Any] = {}
    outputs: dict[str, dict[str, Mapping[str, Tensor]]] = {}
    with torch.inference_mode():
        for stratum in STRATA:
            evaluations[stratum] = {}
            outputs[stratum] = {}
            for split in ("development",):
                output = _local_row_output(matcher, strata[stratum][split])
                outputs[stratum][split] = output
                evaluations[stratum][split] = _local_row_metrics(
                    strata[stratum][split], output
                )
    return {
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "matcher": matcher,
        "local_outputs": outputs,
        "seed": int(seed),
        "initialization": initialization,
        "initial_state_sha256": initialization["runtime_initial_state_sha256"],
        "final_state_sha256": final_state,
        "frozen_state_sha256": frozen_state,
        "state_unchanged_by_freeze": final_state == frozen_state,
        "optimizer_only_matcher": True,
        "trainable_parameter_names": sorted(
            name for name, _ in matcher.named_parameters()
        ),
        "optimizer_parameter_names": sorted(
            name for name, _ in matcher.named_parameters()
        ),
        "registered_gradient_steps": steps,
        "finite_gradient_steps": finite_gradient_steps,
        "nonzero_gradient_steps": nonzero_gradient_steps,
        "all_gradients_finite": finite_gradient_steps == steps,
        "initial_loss": losses[0] if losses else None,
        "final_loss": losses[-1] if losses else None,
        "evaluations": evaluations,
        "allocator": "pure_row_local_softmax_with_private_death",
        "calls_global_solver": False,
        "column_normalization_used": False,
        "column_competition_used": False,
    }


def _r4_fixed_assignment_baseline_plans(
    batch: QueryAnchorBatch,
) -> tuple[MatchPlan, MatchPlan, str]:
    """Build fixed equal-view partial-OT baselines on the R4 support contract."""

    matcher = _new_matcher()
    for parameter in matcher.parameters():
        parameter.requires_grad_(False)
    visible = _matching_regions(batch)
    with torch.no_grad():
        soft = matcher.soft_plan(visible)
        hard = matcher.hard_plan(visible)
    soft.validate(visible)
    hard.validate(visible)
    contract_hash = _json_hash(
        {
            "kind": "r4_fixed_equal_view_cosine_partial_ot",
            "visible_prior_sha256": _tensor_hash(visible.prior_features),
            "visible_current_sha256": _tensor_hash(visible.current_features),
            "prior_valid_sha256": _tensor_hash(visible.prior_valid),
            "current_valid_sha256": _tensor_hash(visible.current_valid),
            "prior_anatomy_sha256": _tensor_hash(visible.prior_anatomy),
            "current_anatomy_sha256": _tensor_hash(visible.current_anatomy),
            "identity_views": [list(view) for view in IDENTITY_VIEW_SLICES],
            "view_weights": [0.5, 0.5],
            "residual": 0.0,
            "prior_null_utility": 0.0,
            "current_null_utility": 0.0,
            "temperature": SINKHORN_TEMPERATURE,
            "iterations": SINKHORN_ITERATIONS,
            "feasibility_tolerance": FEASIBILITY_TOLERANCE,
        }
    )
    return hard, soft, contract_hash


def _baseline_gate(
    *,
    strata: Mapping[str, Mapping[str, QueryAnchorBatch]],
    adapter: nn.Module,
    oracle_readouts: Mapping[str, Mapping[str, Any]],
    transport_results: Mapping[str, Mapping[str, Any]],
    local_results: Mapping[str, Mapping[str, Any]],
    seeds: Sequence[int],
) -> tuple[dict[str, Any], dict[str, Any]]:
    plans: dict[str, Any] = {}
    assignment_metrics: dict[str, Any] = {}
    for stratum in STRATA:
        batch = strata[stratum]["development"]
        hungarian, sinkhorn, contract_hash = _r4_fixed_assignment_baseline_plans(batch)
        plans[stratum] = {"hungarian": hungarian, "sinkhorn": sinkhorn}
        assignment_metrics[stratum] = {
            "contract_sha256": contract_hash,
            "hungarian": _transport_metrics(batch, hungarian, hungarian),
            "sinkhorn": _transport_metrics(batch, sinkhorn, hungarian),
        }

    fixed_seed_hashes: dict[str, Any] = {stratum: {} for stratum in STRATA}
    for stratum in STRATA:
        for seed in seeds:
            hard, soft, contract_hash = _r4_fixed_assignment_baseline_plans(
                strata[stratum]["development"]
            )
            fixed_seed_hashes[stratum][str(seed)] = {
                "hungarian": _tensor_hash(hard.transport),
                "sinkhorn": _tensor_hash(soft.transport),
                "contract": contract_hash,
            }
    fixed_seed_invariant = all(
        all(
            len({values[name] for values in by_seed.values()}) == 1
            for name in ("hungarian", "sinkhorn", "contract")
        )
        for by_seed in fixed_seed_hashes.values()
    )

    readout_results: dict[str, Any] = {}
    for seed in seeds:
        key = str(seed)
        projector = oracle_readouts[key]["model"]
        common_readout_sha256 = _state_hash(projector)
        readout_results[key] = {}
        for stratum in STRATA:
            readout_results[key][stratum] = {}
            matcher = transport_results[key]["matcher"]
            with torch.inference_mode():
                main_plan = matcher.soft_plan(
                    _matching_regions(strata[stratum]["development"])
                )
            for name in EXACT64_METHOD_ORDER:
                if name == "local_independent":
                    scored = _score_local_frozen_readout(
                        projector=projector,
                        adapter=adapter,
                        batch=strata[stratum]["development"],
                        local_output=local_results[key]["local_outputs"][stratum][
                            "development"
                        ],
                        phase=f"baseline_{stratum}_{name}",
                    )
                else:
                    plan = main_plan if name == "main" else plans[stratum][name]
                    scored = _score_frozen_readout(
                        projector=projector,
                        adapter=adapter,
                        batch=strata[stratum]["development"],
                        plan=plan,
                        phase=f"baseline_{stratum}_{name}",
                    )
                scored["common_oracle_readout_sha256"] = common_readout_sha256
                readout_results[key][stratum][name] = scored

    main_clean = {
        str(seed): transport_results[str(seed)]["evaluations"]["clean"]["development"][
            "hard_all_endpoint_assignment_accuracy"
        ]
        for seed in seeds
    }
    main_challenge = {
        str(seed): transport_results[str(seed)]["evaluations"]["challenge"][
            "development"
        ]["hard_all_endpoint_assignment_accuracy"]
        for seed in seeds
    }
    main_challenge_row = {
        str(seed): transport_results[str(seed)]["evaluations"]["challenge"][
            "development"
        ]["row_top1_accuracy"]
        for seed in seeds
    }
    local_challenge = {
        str(seed): local_results[str(seed)]["evaluations"]["challenge"]["development"][
            "row_top1_accuracy"
        ]
        for seed in seeds
    }
    clean_reference = assignment_metrics["clean"]["hungarian"][
        "hard_all_endpoint_assignment_accuracy"
    ]
    challenge_reference = max(
        assignment_metrics["challenge"][name]["hard_all_endpoint_assignment_accuracy"]
        for name in ("hungarian", "sinkhorn")
    )
    checks = {
        "clean_every_seed_within_0_10_hungarian": all(
            value >= clean_reference - 0.10 for value in main_clean.values()
        ),
        "clean_aggregate_within_0_05_hungarian": sum(main_clean.values())
        / len(main_clean)
        >= clean_reference - 0.05,
        "challenge_every_seed_improves_best_fixed_by_0_20": all(
            value >= challenge_reference + 0.20 for value in main_challenge.values()
        ),
        "matched_local_has_no_column_competition": all(
            local_results[str(seed)]["column_normalization_used"] is False
            and local_results[str(seed)]["column_competition_used"] is False
            and local_results[str(seed)]["calls_global_solver"] is False
            for seed in seeds
        ),
        "challenge_every_seed_improves_matched_local_row_top1_by_0_20": all(
            main_challenge_row[str(seed)] >= local_challenge[str(seed)] + 0.20
            for seed in seeds
        ),
        "common_oracle_readout_shared_per_seed": all(
            len(
                {
                    result["common_oracle_readout_sha256"]
                    for stratum_results in readout_results[str(seed)].values()
                    for result in stratum_results.values()
                }
            )
            == 1
            for seed in seeds
        ),
        "baseline_readouts_exact64_and_frozen": all(
            result["passed"]
            for seed_results in readout_results.values()
            for stratum_results in seed_results.values()
            for result in stratum_results.values()
        ),
        "baseline_plans_seed_invariant_observed": fixed_seed_invariant,
        "matched_local_parameters_optimizer_and_updates_equal": all(
            local_results[str(seed)]["registered_gradient_steps"]
            == transport_results[str(seed)]["registered_gradient_steps"]
            and local_results[str(seed)]["optimizer_parameter_names"]
            == transport_results[str(seed)]["optimizer_parameter_names"]
            for seed in seeds
        ),
    }
    gate = {
        "status": "PASS" if all(checks.values()) else "FAIL_FAIR_BASELINE",
        "passed": all(checks.values()),
        "checks": checks,
        "clean_hungarian_reference": clean_reference,
        "challenge_best_fixed_reference": challenge_reference,
        "main_clean_by_seed": main_clean,
        "main_challenge_by_seed": main_challenge,
        "main_challenge_row_top1_by_seed": main_challenge_row,
        "matched_local_challenge_by_seed": local_challenge,
        "assignment_metrics": assignment_metrics,
        "plan_sha256": {
            stratum: {
                name: _tensor_hash(plan.transport)
                for name, plan in stratum_plans.items()
            }
            for stratum, stratum_plans in plans.items()
        },
        "fixed_seed_invariance_evidence": fixed_seed_hashes,
        "fixed_seed_invariance_map_sha256": _json_hash(fixed_seed_hashes),
        "exact64_method_order": list(EXACT64_METHOD_ORDER),
    }
    return gate, readout_results


def _bridge_gate(
    *,
    oracle_readouts: Mapping[str, Mapping[str, Any]],
    mediator_results: Mapping[str, Mapping[str, Any]],
    baseline_results: Mapping[str, Any],
    exact64_method_order: Sequence[str],
) -> dict[str, Any]:
    checks = {
        "oracle_readout_exact64": all(
            result["exact64_execution_audit"]["passed"]
            for result in oracle_readouts.values()
        ),
        "mediator_exact64": all(
            result["exact64_execution_audit"]["passed"]
            for result in mediator_results.values()
        ),
        "baseline_exact64": all(
            result["passed"]
            for seed_results in baseline_results.values()
            for stratum_results in seed_results.values()
            for result in stratum_results.values()
        ),
        "baseline_method_order_exact": all(
            set(stratum_results) == set(EXACT64_METHOD_ORDER)
            for seed_results in baseline_results.values()
            for stratum_results in seed_results.values()
        )
        and list(exact64_method_order) == list(EXACT64_METHOD_ORDER),
        "common_oracle_readout_shared": all(
            len(
                {
                    result.get("common_oracle_readout_sha256")
                    for stratum_results in seed_results.values()
                    for result in stratum_results.values()
                }
            )
            == 1
            for seed_results in baseline_results.values()
        ),
        "no_formal_test": True,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL_EXACT64_BRIDGE",
        "passed": all(checks.values()),
        "checks": checks,
    }


GATE_ORDER = (
    "resolution_freeze",
    "structural_input",
    "fixture_identifiability",
    "transport_competence",
    "anti_equivalence",
    "mediator_recovery",
    "fair_baseline",
    "exact64_bridge",
    "independent_reproduction",
)


def _strip_runner_objects(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _strip_runner_objects(item)
            for key, item in value.items()
            if key not in {"model", "matcher", "projector", "plans", "local_outputs"}
        }
    if isinstance(value, list):
        return [_strip_runner_objects(item) for item in value]
    return value


def _gate_record(name: str, gate: Mapping[str, Any]) -> dict[str, Any]:
    return {"name": name, "status": gate.get("status"), "passed": gate.get("passed")}


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _normalized_argv(args: argparse.Namespace) -> dict[str, Any]:
    if args.smoke:
        mode = "smoke"
    elif args.dry_run:
        mode = "dry_run"
    else:
        mode = "registered"
    return {
        "mode": mode,
        "steps": int(args.steps),
        "seeds": [int(seed) for seed in args.seeds],
        "device": args.device,
        "dry_run": bool(args.dry_run),
        "smoke": bool(args.smoke),
    }


def _expected_output_leaf(args: argparse.Namespace) -> str:
    leaves = IMPLEMENTED_OUTPUT_LEAVES
    if args.dry_run:
        return str(leaves["dry_run"])
    if args.smoke:
        return str(leaves["smoke"])
    if os.environ.get("SLURM_JOB_ID") == "4161":
        return str(leaves["registered_slurm4161"])
    return str(leaves["registered_local"])


def _output_root_contract(args: argparse.Namespace) -> dict[str, Any]:
    workspace = WORKSPACE.resolve()
    expected_parent = (workspace / "artifacts" / "calibration").resolve()
    raw_requested = Path(getattr(args, "_raw_run_dir", args.run_dir))
    requested = args.run_dir.resolve()
    reproduction_leaves = {
        IMPLEMENTED_OUTPUT_LEAVES["reproduction_local"],
        IMPLEMENTED_OUTPUT_LEAVES["reproduction_slurm4161"],
    }
    reproduction_child_leaves = IMPLEMENTED_REPRODUCTION_CHILD_LEAVES
    is_reproduction_child = bool(
        requested.name in reproduction_child_leaves
        and requested.parent.name in reproduction_leaves
        and requested.parent.parent.resolve() == expected_parent
    )
    if is_reproduction_child:
        expected_leaf = requested.name
        expected_parent_for_run = requested.parent.resolve()
        expected = (expected_parent_for_run / expected_leaf).resolve()
        expected_lexical = (
            WORKSPACE
            / "artifacts"
            / "calibration"
            / requested.parent.name
            / requested.name
        )
    else:
        expected_leaf = _expected_output_leaf(args)
        expected_parent_for_run = expected_parent
        expected = (expected_parent_for_run / expected_leaf).resolve()
        expected_lexical = WORKSPACE / "artifacts" / "calibration" / expected_leaf
    try:
        requested.relative_to(workspace)
        inside_workspace = True
    except ValueError:
        inside_workspace = False
    checks = {
        "raw_path_absolute": raw_requested.is_absolute(),
        "raw_path_has_no_dot_segments": all(
            part not in {"", ".", ".."} for part in raw_requested.parts[1:]
        ),
        "raw_path_lexically_exact_including_case": str(raw_requested)
        == str(expected_lexical),
        "inside_resolved_workspace": inside_workspace,
        "plain_workspace_ancestor_chain": _path_is_plain_workspace_descendant(
            raw_requested
        ),
        "parent_exact": requested.parent.resolve() == expected_parent_for_run,
        "leaf_exact": requested.name == expected_leaf,
        "resolved_path_exact": requested == expected,
        "output_root_absent": not requested.exists(),
        "parent_is_directory": expected_parent_for_run.is_dir(),
        "parent_writable": expected_parent_for_run.is_dir()
        and os.access(expected_parent_for_run, os.W_OK),
        "parent_not_symlink": not (
            workspace / "artifacts" / "calibration"
        ).is_symlink(),
        "reproduction_parent_not_symlink": not is_reproduction_child
        or not requested.parent.is_symlink(),
        "registered_reproduction_child_topology": not is_reproduction_child
        or (
            requested.parent.name in reproduction_leaves
            and requested.name in reproduction_child_leaves
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "workspace": str(workspace),
        "expected_parent": str(expected_parent_for_run),
        "expected_leaf": expected_leaf,
        "expected_output_root": str(expected),
        "requested_output_root": str(requested),
        "raw_requested_output_root": str(raw_requested),
        "expected_lexical_output_root": str(expected_lexical),
        "reproduction_child": is_reproduction_child,
    }


def _entry_evidence(
    args: argparse.Namespace, raw_argv: Sequence[str]
) -> dict[str, Any]:
    run_dir = args.run_dir.resolve()
    parent = run_dir.parent
    output_contract = _output_root_contract(args)
    return {
        "raw_argv": list(raw_argv),
        "normalized_argv_semantic_fields": _normalized_argv(args),
        "absolute_output_root": str(run_dir),
        "output_root_existed_at_entry": run_dir.exists(),
        "output_parent": str(parent),
        "output_parent_is_directory": parent.is_dir(),
        "output_parent_writable": parent.is_dir() and os.access(parent, os.W_OK),
        "output_root_contract": output_contract,
        "output_root_contract_passed": output_contract["passed"],
        "captured_utc": _utc_now(),
    }


def _finish_provenance(
    provenance: Mapping[str, Any], *, start: float
) -> dict[str, Any]:
    return {
        **provenance,
        "end_utc": _utc_now(),
        "monotonic_elapsed_seconds": time.perf_counter() - start,
    }


def _stopped_summary(
    *,
    base: Mapping[str, Any],
    fields: Mapping[str, Any],
    gate_trace: Sequence[Mapping[str, Any]],
    stopped_at: str,
    start: float,
) -> dict[str, Any]:
    index = GATE_ORDER.index(stopped_at)
    provenance = _finish_provenance(base["provenance"], start=start)
    return {
        **base,
        **fields,
        "provenance": provenance,
        "status": _stop_status(stopped_at),
        "completed_gates": list(gate_trace),
        "stopped_at_gate": stopped_at,
        "not_run_gates": list(GATE_ORDER[index + 1 :]),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    torch.use_deterministic_algorithms(True)
    torch.set_deterministic_debug_mode("error")
    if torch.get_num_threads() != 1 or torch.get_num_interop_threads() != 1:
        raise RuntimeError("registered R10 requires torch intra-op=1 and inter-op=1")
    if args.steps <= 0:
        raise ValueError("steps must be positive")
    seeds = tuple(int(seed) for seed in args.seeds)
    if args.smoke and len(seeds) != 1:
        raise ValueError("R10 smoke requires exactly one trainable seed")
    if not args.smoke and seeds != TRAINABLE_SEEDS:
        raise ValueError(f"registered R10 runs require seeds {TRAINABLE_SEEDS}")
    if not args.smoke and not args.dry_run and args.steps != REGISTERED_STEPS:
        raise ValueError(
            f"registered R10 runs require exactly {REGISTERED_STEPS} steps"
        )
    actual_steps = 1 if args.smoke else args.steps
    enforce_gates = not args.smoke
    start = time.perf_counter()
    utc_start = _utc_now()
    entry = getattr(args, "_entry_evidence", None)
    if entry is None:
        entry = _entry_evidence(args, getattr(args, "_raw_argv", ()))
    preflight_bundle = getattr(args, "_preflight_bundle", None)
    if isinstance(preflight_bundle, Mapping):
        source_manifest = copy.deepcopy(preflight_bundle["source_manifest"])
        config = copy.deepcopy(preflight_bundle["config"])
        runtime_environment = copy.deepcopy(preflight_bundle["runtime_environment"])
        frozen_resolution = copy.deepcopy(preflight_bundle["resolution_gate"])
    else:
        source_manifest = _source_manifest()
        config = _registered_config(
            seeds=seeds,
            actual_steps=actual_steps,
            smoke=bool(args.smoke),
            dry_run=bool(args.dry_run),
        )
        runtime_environment = _runtime_environment()
        frozen_resolution = None
    provenance = {
        "start_utc": utc_start,
        "end_utc": None,
        "monotonic_elapsed_seconds": None,
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
        "process_uuid": str(getattr(args, "_transaction_uuid", uuid.uuid4())),
        "hostname": platform.node(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "slurm_step_id": os.environ.get("SLURM_STEP_ID"),
        "output_root_absolute": str(args.run_dir.resolve()),
        "raw_argv": list(getattr(args, "_raw_argv", ())),
        "normalized_argv_semantic_fields": _normalized_argv(args),
        "runner_path": str(Path(__file__).resolve()),
        "runner_sha256": _file_hash(Path(__file__).resolve()),
        "cwd": str(Path.cwd().resolve()),
        "output_root_entry_evidence": {
            key: copy.deepcopy(value)
            for key, value in entry.items()
            if key not in {"captured_utc", "raw_argv"}
        },
    }
    base = {
        "summary_schema_version": SUMMARY_SCHEMA_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "evidence_class": EVIDENCE_CLASS,
        "config": config,
        "config_sha256": _json_hash(config),
        "source_manifest": source_manifest,
        "runtime_environment": runtime_environment,
        "provenance": provenance,
        "execution_request": {
            "python_executable": str(Path(sys.executable).resolve()),
            "runner_path": str(Path(__file__).resolve()),
            "cwd": str(Path.cwd().resolve()),
            "parsed_arguments": {
                **_normalized_argv(args),
            },
        },
        "gate_order": list(GATE_ORDER),
        "formal_test_used": False,
        "formal_test_status": "SEALED",
        "formal_data_authorization": "HOLD",
        "formal_claim_allowed": False,
        "formal_ablation_claim_allowed": False,
        "full_method_claim_allowed": False,
        "data_access_ledger": [],
    }
    fields: dict[str, Any] = {}
    gate_trace: list[dict[str, Any]] = []
    args._failure_gate_trace = gate_trace

    resolution = frozen_resolution or _resolution_gate(
        config,
        source_manifest,
        runtime_environment=runtime_environment,
        entry_evidence=entry,
    )
    fields["resolution_freeze_gate"] = resolution
    gate_trace.append(_gate_record("resolution_freeze", resolution))
    if not resolution["passed"]:
        return _stopped_summary(
            base=base,
            fields=fields,
            gate_trace=gate_trace,
            stopped_at="resolution_freeze",
            start=start,
        )

    accessor = _R6SplitAccessor()
    args._failure_accessor = accessor
    audit_batches, audit_raw = accessor.audit(
        gate="structural_input",
        split="literal_audit_fixture",
        purpose="structural_microfixtures_and_full_chain_counterfactuals",
    )
    strata = {stratum: {"audit_fixture": audit_batches[stratum]} for stratum in STRATA}
    raw_clean = {"audit_fixture": audit_raw["clean"]}
    raw_challenge = {"audit_fixture": audit_raw["challenge"]}
    split_manifests = _r4_split_manifest(strata, raw_clean, raw_challenge)
    base["split_manifests"] = split_manifests
    base["data_access_ledger"] = accessor.ledger
    adapter = _fixed_adapter()

    structural = _structural_gate(strata, raw_clean, raw_challenge, adapter)
    fields["structural_input_gate"] = structural
    gate_trace.append(_gate_record("structural_input", structural))
    if not structural["passed"]:
        return _stopped_summary(
            base=base,
            fields=fields,
            gate_trace=gate_trace,
            stopped_at="structural_input",
            start=start,
        )

    audit_batches, audit_raw = accessor.audit(
        gate="fixture_identifiability",
        split="frozen_fixture_audit",
        purpose="independent_fixture_development_certificate",
    )
    dry_fixture = _fixture_authority_dry_run_gate(raw_audit=audit_raw)
    fields["fixture_identifiability_gate"] = dry_fixture
    gate_trace.append(_gate_record("fixture_identifiability", dry_fixture))
    if not dry_fixture["passed"]:
        return _stopped_summary(
            base=base,
            fields=fields,
            gate_trace=gate_trace,
            stopped_at="fixture_identifiability",
            start=start,
        )
    if args.dry_run:
        access_gate = _dry_run_access_ledger_gate(
            base["data_access_ledger"], base["split_manifests"]
        )
        fields["dry_run_data_access_gate"] = access_gate
        return {
            **base,
            **fields,
            "provenance": _finish_provenance(base["provenance"], start=start),
            "status": FROZEN_R6_REGISTRY["status_vocabulary"]["dry_run_success"]
            if dry_fixture["passed"] and access_gate["passed"]
            else _stop_status("premature_data_access"),
            "training_allowed": False,
            "completed_gates": gate_trace,
            "stopped_at_gate": None,
            "not_run_gates": list(GATE_ORDER[3:]),
        }
    # Gate 3 is the first registered-split boundary.  Materialize only train
    # here; later development splits are still unavailable.
    train_batches: dict[str, QueryAnchorBatch] = {}
    train_raw: dict[str, R5CleanBatch | R5ChallengeBatch] = {}
    for stratum in STRATA:
        train_batches[stratum], train_raw[stratum] = accessor.registered(
            gate="transport_competence",
            stratum=stratum,
            split="train",
            purpose="transport_training",
        )
    strata = {stratum: {"train": train_batches[stratum]} for stratum in STRATA}
    train_manifests = _r4_split_manifest(
        {stratum: {"train": train_batches[stratum]} for stratum in STRATA},
        {"train": train_raw["clean"]},
        {"train": train_raw["challenge"]},
    )
    base["split_manifests"] = {
        stratum: {
            "audit_fixture": split_manifests[stratum]["audit_fixture"],
            "train": train_manifests[stratum]["train"],
        }
        for stratum in STRATA
    }
    transport_results: dict[str, Any] = {}
    for seed in seeds:
        transport_results[str(seed)] = _train_transport(
            seed=seed, strata=strata, steps=actual_steps
        )
    raw_clean: dict[str, R5CleanBatch] = {"train": train_raw["clean"]}  # type: ignore[dict-item]
    raw_challenge: dict[str, R5ChallengeBatch] = {"train": train_raw["challenge"]}  # type: ignore[dict-item]
    for stratum in STRATA:
        batch, raw = accessor.registered(
            gate="transport_competence",
            stratum=stratum,
            split="inner_development",
            purpose="post_checkpoint_transport_model_selection_audit",
        )
        strata[stratum]["inner_development"] = batch
        if stratum == "clean":
            raw_clean["inner_development"] = raw  # type: ignore[assignment]
        else:
            raw_challenge["inner_development"] = raw  # type: ignore[assignment]
    clean_development, clean_development_raw = accessor.registered(
        gate="transport_competence",
        stratum="clean",
        split="development",
        purpose="post_checkpoint_clean_transport_gate",
    )
    strata["clean"]["development"] = clean_development
    raw_clean["development"] = clean_development_raw  # type: ignore[assignment]
    _evaluate_transport_results(
        transport_results,
        {
            "clean": {
                "inner_development": strata["clean"]["inner_development"],
                "development": strata["clean"]["development"],
            },
            "challenge": {
                "inner_development": strata["challenge"]["inner_development"]
            },
        },
    )
    clean_gate, challenge_gate = _transport_gates(transport_results, seeds)
    base["split_manifests"] = _r4_split_manifest(strata, raw_clean, raw_challenge)
    fields.update(
        {
            "transport_competence_gate": clean_gate,
            "transport_results": _strip_runner_objects(transport_results),
        }
    )
    gate_trace.append(_gate_record("transport_competence", clean_gate))
    if enforce_gates and not clean_gate["passed"]:
        return _stopped_summary(
            base=base,
            fields=fields,
            gate_trace=gate_trace,
            stopped_at="transport_competence",
            start=start,
        )

    challenge_development, challenge_development_raw = accessor.registered(
        gate="anti_equivalence",
        stratum="challenge",
        split="development",
        purpose="post_gate3_challenge_transport_gate",
    )
    strata["challenge"]["development"] = challenge_development
    raw_challenge["development"] = challenge_development_raw  # type: ignore[assignment]
    _evaluate_transport_results(
        transport_results,
        {"challenge": {"development": challenge_development}},
    )
    _, challenge_gate = _transport_gates(transport_results, seeds)
    base["split_manifests"] = _r4_split_manifest(strata, raw_clean, raw_challenge)
    fields["transport_results"] = _strip_runner_objects(transport_results)
    fields["anti_equivalence_gate"] = challenge_gate
    gate_trace.append(_gate_record("anti_equivalence", challenge_gate))
    if enforce_gates and not challenge_gate["passed"]:
        return _stopped_summary(
            base=base,
            fields=fields,
            gate_trace=gate_trace,
            stopped_at="anti_equivalence",
            start=start,
        )

    for stratum in STRATA:
        for split in ("train", "development"):
            accessor.registered(
                gate="mediator_recovery",
                stratum=stratum,
                split=split,
                purpose="common_oracle_and_mediator_readout",
            )
    oracle_plan_bank = _oracle_plans(strata)
    oracle_readouts: dict[str, Any] = {}
    for seed in seeds:
        oracle_readouts[str(seed)] = _fit_readout(
            adapter=adapter,
            seed=seed,
            strata=strata,
            plans=oracle_plan_bank,
            steps=actual_steps,
            phase_prefix="oracle_readout",
        )
    fixture_competence, controls, binding_results = _fixture_gate(
        strata=strata,
        raw_challenge=raw_challenge,
        adapter=adapter,
        oracle_readouts=oracle_readouts,
        seeds=seeds,
        steps=actual_steps,
        enforce_competence=enforce_gates,
    )
    fields.update(
        {
            "common_oracle_readout_results": _strip_runner_objects(oracle_readouts),
            "marginal_controls": controls,
            "binding_results": binding_results,
            "post_transport_fixture_competence": fixture_competence,
        }
    )
    if enforce_gates and not fixture_competence["passed"]:
        failed_mediator = {
            "status": "FAIL_MEDIATOR_RECOVERY",
            "passed": False,
            "checks": {"post_transport_fixture_competence": False},
            "supporting_fixture_competence": fixture_competence,
        }
        fields["mediator_recovery_gate"] = failed_mediator
        gate_trace.append(_gate_record("mediator_recovery", failed_mediator))
        return _stopped_summary(
            base=base,
            fields=fields,
            gate_trace=gate_trace,
            stopped_at="mediator_recovery",
            start=start,
        )

    mediator_results: dict[str, Any] = {}
    for seed in seeds:
        key = str(seed)
        matcher = transport_results[key]["matcher"]
        plans = _frozen_matcher_plans(matcher, strata)
        mediator_results[key] = _fit_readout(
            adapter=adapter,
            seed=seed,
            strata=strata,
            plans=plans,
            steps=actual_steps,
            phase_prefix="mediator_readout",
            frozen_matcher=matcher,
        )
    mediator_gate = _mediator_gate(mediator_results, seeds)
    mediator_gate = {
        **mediator_gate,
        "checks": {
            **mediator_gate["checks"],
            "post_transport_fixture_competence": fixture_competence["passed"],
        },
    }
    mediator_gate["passed"] = all(mediator_gate["checks"].values())
    mediator_gate["status"] = (
        "PASS" if mediator_gate["passed"] else "FAIL_MEDIATOR_RECOVERY"
    )
    fields.update(
        {
            "mediator_recovery_gate": mediator_gate,
            "mediator_results": _strip_runner_objects(mediator_results),
        }
    )
    gate_trace.append(_gate_record("mediator_recovery", mediator_gate))
    if enforce_gates and not mediator_gate["passed"]:
        return _stopped_summary(
            base=base,
            fields=fields,
            gate_trace=gate_trace,
            stopped_at="mediator_recovery",
            start=start,
        )

    for stratum in STRATA:
        for split in ("train", "development"):
            accessor.registered(
                gate="fair_baseline",
                stratum=stratum,
                split=split,
                purpose="matched_local_and_fair_baseline",
            )
    local_results = {
        str(seed): _train_local_baseline(seed=seed, strata=strata, steps=actual_steps)
        for seed in seeds
    }
    baseline_gate, baseline_results = _baseline_gate(
        strata=strata,
        adapter=adapter,
        oracle_readouts=oracle_readouts,
        transport_results=transport_results,
        local_results=local_results,
        seeds=seeds,
    )
    fields.update(
        {
            "fair_baseline_gate": baseline_gate,
            "baseline_results": baseline_results,
            "matched_local_results": _strip_runner_objects(local_results),
        }
    )
    gate_trace.append(_gate_record("fair_baseline", baseline_gate))
    if enforce_gates and not baseline_gate["passed"]:
        return _stopped_summary(
            base=base,
            fields=fields,
            gate_trace=gate_trace,
            stopped_at="fair_baseline",
            start=start,
        )

    bridge_gate = _bridge_gate(
        oracle_readouts=oracle_readouts,
        mediator_results=mediator_results,
        baseline_results=baseline_results,
        exact64_method_order=baseline_gate.get("exact64_method_order", ()),
    )
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(61_607)
        exact64_counterfactual_projector = RelationProjector(
            input_dim=75, hidden_size=8
        )
    exact64_counterfactual = run_r6_counterfactual_audits(
        strata["clean"]["development"],
        R6ChainHooks(
            matching_regions=_matching_regions,
            token_regions=lambda value: value.regions,
            matcher=transport_results[str(seeds[0])]["matcher"],
            allocator=DeterministicGlobalAllocator(),
            projector=exact64_counterfactual_projector,
            adapter=adapter,
            prompt_factory=query_prompt,
        ),
    )
    validate_r6_counterfactual_audit(exact64_counterfactual)
    exact64_counterfactual_hash_exact = exact64_counterfactual.get(
        "report_sha256"
    ) == _json_hash(
        {
            key: value
            for key, value in exact64_counterfactual.items()
            if key != "report_sha256"
        }
    )
    bridge_gate = {
        **bridge_gate,
        "checks": {
            **bridge_gate["checks"],
            "r6_counterfactual_repeated_at_exact64": exact64_counterfactual.get(
                "passed"
            )
            is True,
            "r6_counterfactual_hash_exact": exact64_counterfactual_hash_exact,
        },
        "r6_full_chain_counterfactual": exact64_counterfactual,
    }
    bridge_gate["passed"] = all(bridge_gate["checks"].values())
    bridge_gate["status"] = "PASS" if bridge_gate["passed"] else "FAIL_EXACT64_BRIDGE"
    fields["exact64_bridge_gate"] = bridge_gate
    gate_trace.append(_gate_record("exact64_bridge", bridge_gate))
    if enforce_gates and not bridge_gate["passed"]:
        return _stopped_summary(
            base=base,
            fields=fields,
            gate_trace=gate_trace,
            stopped_at="exact64_bridge",
            start=start,
        )

    terminal = {
        **base,
        **fields,
        "provenance": _finish_provenance(base["provenance"], start=start),
        "status": FROZEN_R6_REGISTRY["status_vocabulary"]["smoke_success"]
        if args.smoke
        else PENDING_STATUS,
        "completed_gates": gate_trace,
        "stopped_at_gate": None,
        "not_run_gates": ["independent_reproduction"],
        "independent_process_reproduction_required": not args.smoke,
    }
    phase_authorization = getattr(args, "_phase_authorization", None)
    if isinstance(phase_authorization, Mapping):
        terminal["phase_authorization"] = copy.deepcopy(phase_authorization)
    return terminal


def _sha256_like(value: Any) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _readout_result_eligible(result: Any, *, phase_prefix: str) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    if not isinstance(result, Mapping):
        return {
            "passed": False,
            "errors": [
                {"path": "$", "expected": "object", "observed": type(result).__name__}
            ],
        }
    expected_keys = {
        "adapter_after_sha256",
        "adapter_before_sha256",
        "adapter_unchanged",
        "all_gradients_finite",
        "exact64_execution_audit",
        "execution_kind",
        "final_loss",
        "final_train_state_sha256",
        "finite_gradient_steps",
        "frozen_state_sha256",
        "initial_loss",
        "initial_state_sha256",
        "matcher_after_sha256",
        "matcher_before_sha256",
        "matcher_gradients_zero",
        "matcher_gradient_non_none_count",
        "matcher_gradient_nonzero_count",
        "matcher_unchanged",
        "metrics",
        "optimizer_only_projector",
        "optimizer_parameter_names",
        "plan_sha256",
        "projector_state_unchanged_by_freeze",
        "registered_gradient_steps",
        "result_schema_version",
        "trainable_parameter_names",
    }
    errors.extend(_validate_exact_keys(result, expected_keys, path="$"))
    for path in _validate_finite_tree(result):
        errors.append(
            {"path": path, "expected": "finite number", "observed": "nonfinite"}
        )
    trace = result.get("exact64_execution_audit")
    expected = {
        f"{phase_prefix}_training_{stratum}": REGISTERED_STEPS for stratum in STRATA
    }
    expected.update(
        {
            f"{phase_prefix}_final_{stratum}_{split}": 1
            for stratum in STRATA
            for split in ("train", "development")
        }
    )
    valid = bool(
        isinstance(trace, Mapping)
        and result.get("result_schema_version") == RESULT_SCHEMA_VERSION
        and trace.get("passed") is True
        and trace.get("observed_adapter_score_calls") == expected
        and trace.get("expected_adapter_score_calls") == expected
        and trace.get("observed_total_adapter_score_calls") == sum(expected.values())
        and result.get("execution_kind") == phase_prefix
        and result.get("adapter_unchanged") is True
        and result.get("projector_state_unchanged_by_freeze") is True
        and result.get("optimizer_only_projector") is True
        and result.get("all_gradients_finite") is True
        and result.get("finite_gradient_steps") == REGISTERED_STEPS
        and _sha256_like(result.get("initial_state_sha256"))
        and _sha256_like(result.get("final_train_state_sha256"))
        and _sha256_like(result.get("frozen_state_sha256"))
    )
    if not valid:
        errors.append(
            {
                "path": "$",
                "expected": f"eligible {phase_prefix} result",
                "observed": "contract violation",
            }
        )
    return {"passed": not errors, "errors": errors}


def _transport_result_eligible(result: Any) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    if not isinstance(result, Mapping):
        return {
            "passed": False,
            "errors": [
                {"path": "$", "expected": "object", "observed": type(result).__name__}
            ],
        }
    expected_keys = {
        "all_gradients_finite",
        "effective_null_utilities",
        "evaluations",
        "final_loss",
        "final_state_sha256",
        "finite_gradient_steps",
        "frozen_state_sha256",
        "initial_loss",
        "initial_state_sha256",
        "initialization",
        "matcher_changed",
        "nonzero_gradient_steps",
        "normalized_view_weights",
        "optimizer_only_matcher",
        "optimizer_parameter_names",
        "registered_gradient_steps",
        "residual_coefficient",
        "result_schema_version",
        "seed",
        "state_unchanged_by_freeze",
        "trainable_parameter_names",
    }
    errors.extend(_validate_exact_keys(result, expected_keys, path="$"))
    for path in _validate_finite_tree(result):
        errors.append(
            {"path": path, "expected": "finite number", "observed": "nonfinite"}
        )
    evaluations = result.get("evaluations")
    expected_names = {
        "current_null_utility",
        "prior_null_utility",
        "residual_coefficient",
        "view_weight_logits",
    }
    initialization = result.get("initialization")
    valid = bool(
        result.get("result_schema_version") == RESULT_SCHEMA_VERSION
        and result.get("seed") in TRAINABLE_SEEDS
        and isinstance(result.get("initialization"), Mapping)
        and result["initialization"].get("seed") == result.get("seed")
        and result["initialization"].get("std") == INITIALIZATION_STD
        and result["initialization"].get("schema_version")
        == FROZEN_R6_REGISTRY["schema_versions"]["initialization"]
        and result["initialization"].get("passed") is True
        and all(result["initialization"].get("checks", {}).values())
        and result.get("initial_state_sha256")
        == result["initialization"].get("runtime_initial_state_sha256")
        and result.get("optimizer_only_matcher") is True
        and set(result.get("optimizer_parameter_names", ())) == expected_names
        and set(result.get("trainable_parameter_names", ())) == expected_names
        and result.get("all_gradients_finite") is True
        and result.get("finite_gradient_steps") == REGISTERED_STEPS
        and result.get("registered_gradient_steps") == REGISTERED_STEPS
        and result.get("nonzero_gradient_steps", 0) > 0
        and result.get("matcher_changed") is True
        and result.get("state_unchanged_by_freeze") is True
        and _sha256_like(result.get("initial_state_sha256"))
        and _sha256_like(result.get("final_state_sha256"))
        and _sha256_like(result.get("frozen_state_sha256"))
        and isinstance(evaluations, Mapping)
        and set(evaluations) == set(STRATA)
        and all(
            isinstance(evaluations[stratum], Mapping)
            and set(evaluations[stratum]) == {"inner_development", "development"}
            and all(
                isinstance(evaluations[stratum][split].get("null_metrics"), Mapping)
                and (
                    stratum != "clean"
                    or evaluations[stratum][split]["null_metrics"].get(
                        "positive_support_both"
                    )
                    is True
                )
                for split in ("inner_development", "development")
            )
            for stratum in STRATA
        )
    )
    if isinstance(initialization, Mapping):
        expected_init_keys = (
            set(
                _initialization_evidence(
                    int(result.get("seed", -1)),
                    _new_matcher(int(result.get("seed", -1))),
                )
            )
            if result.get("seed") in TRAINABLE_SEEDS
            else set()
        )
        if expected_init_keys:
            errors.extend(
                _validate_exact_keys(
                    initialization, expected_init_keys, path="$.initialization"
                )
            )
    if not valid:
        errors.append(
            {
                "path": "$",
                "expected": "eligible transport result",
                "observed": "contract violation",
            }
        )
    return {"passed": not errors, "errors": errors}


def _local_result_eligible(result: Any) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    if not isinstance(result, Mapping):
        return {
            "passed": False,
            "errors": [
                {"path": "$", "expected": "object", "observed": type(result).__name__}
            ],
        }
    expected_keys = {
        "all_gradients_finite",
        "allocator",
        "calls_global_solver",
        "column_competition_used",
        "column_normalization_used",
        "evaluations",
        "final_loss",
        "final_state_sha256",
        "finite_gradient_steps",
        "frozen_state_sha256",
        "initial_loss",
        "initial_state_sha256",
        "initialization",
        "nonzero_gradient_steps",
        "optimizer_only_matcher",
        "optimizer_parameter_names",
        "registered_gradient_steps",
        "result_schema_version",
        "seed",
        "state_unchanged_by_freeze",
        "trainable_parameter_names",
    }
    errors.extend(_validate_exact_keys(result, expected_keys, path="$"))
    for path in _validate_finite_tree(result):
        errors.append(
            {"path": path, "expected": "finite number", "observed": "nonfinite"}
        )
    evaluations = result.get("evaluations")
    initialization = result.get("initialization")
    expected_names = {
        "current_null_utility",
        "prior_null_utility",
        "residual_coefficient",
        "view_weight_logits",
    }
    valid = bool(
        result.get("result_schema_version") == RESULT_SCHEMA_VERSION
        and result.get("allocator") == "pure_row_local_softmax_with_private_death"
        and result.get("calls_global_solver") is False
        and result.get("column_normalization_used") is False
        and result.get("column_competition_used") is False
        and isinstance(initialization, Mapping)
        and initialization.get("passed") is True
        and all(initialization.get("checks", {}).values())
        and result.get("initial_state_sha256")
        == initialization.get("runtime_initial_state_sha256")
        and set(result.get("optimizer_parameter_names", ())) == expected_names
        and set(result.get("trainable_parameter_names", ())) == expected_names
        and result.get("registered_gradient_steps") == REGISTERED_STEPS
        and result.get("finite_gradient_steps") == REGISTERED_STEPS
        and result.get("all_gradients_finite") is True
        and result.get("state_unchanged_by_freeze") is True
        and isinstance(evaluations, Mapping)
        and set(evaluations) == set(STRATA)
        and all(
            set(evaluations[stratum]) == {"development"}
            and "row_top1_accuracy" in evaluations[stratum]["development"]
            for stratum in STRATA
        )
    )
    if not valid:
        errors.append(
            {
                "path": "$",
                "expected": "eligible matched-local result",
                "observed": "contract violation",
            }
        )
    return {"passed": not errors, "errors": errors}


def _registered_split_manifest_authority(value: Any) -> bool:
    if not isinstance(value, Mapping) or set(value) != set(STRATA):
        return False
    for stratum in STRATA:
        split_map = value.get(stratum)
        if not isinstance(split_map, Mapping) or set(split_map) != set(SPLIT_NAMES):
            return False
        expected = FROZEN_R5_REGISTRY["fixture_hashes"][stratum]
        for split in SPLIT_NAMES:
            manifest = split_map.get(split)
            if not isinstance(manifest, Mapping):
                return False
            evidence = manifest.get("fixture_hash_evidence")
            if not isinstance(evidence, Mapping):
                return False
            if evidence.get("visible") != expected[f"{split}_visible"]:
                return False
            if evidence.get("hidden_oracle") != expected[f"{split}_oracle"]:
                return False
            if (
                stratum == "challenge"
                and evidence.get("full_fixture") != expected[f"{split}_full"]
            ):
                return False
    return True


def _registered_reproduction_eligibility(summary: Mapping[str, Any]) -> dict[str, Any]:
    expected_config = _registered_config(
        seeds=TRAINABLE_SEEDS,
        actual_steps=REGISTERED_STEPS,
        smoke=False,
        dry_run=False,
    )
    try:
        expected_source = _source_manifest()
    except (OSError, ValueError, RuntimeError) as error:
        return {
            "passed": False,
            "checks": {"current_authority_materializable": False},
            "authority_error_type": type(error).__name__,
        }
    environment = summary.get("runtime_environment")
    provenance = summary.get("provenance")
    oracle = summary.get("common_oracle_readout_results")
    transport = summary.get("transport_results")
    mediator = summary.get("mediator_results")
    local = summary.get("matched_local_results")
    strict_summary_validation = _strict_summary_validation(summary)
    gates = {name: summary.get(f"{name}_gate") for name in GATE_ORDER[:8]}
    complete_gate_records = all(isinstance(gate, Mapping) for gate in gates.values())
    expected_gate_trace = (
        [_gate_record(name, gates[name]) for name in GATE_ORDER[:8]]
        if complete_gate_records
        else None
    )
    expected_summary_keys = {
        "summary_schema_version",
        "protocol_version",
        "evidence_class",
        "config",
        "config_sha256",
        "source_manifest",
        "split_manifests",
        "runtime_environment",
        "provenance",
        "execution_request",
        "gate_order",
        "formal_test_used",
        "formal_test_status",
        "formal_data_authorization",
        "formal_claim_allowed",
        "formal_ablation_claim_allowed",
        "full_method_claim_allowed",
        "data_access_ledger",
        "resolution_freeze_gate",
        "structural_input_gate",
        "fixture_identifiability_gate",
        "common_oracle_readout_results",
        "marginal_controls",
        "binding_results",
        "post_transport_fixture_competence",
        "transport_competence_gate",
        "transport_results",
        "anti_equivalence_gate",
        "mediator_recovery_gate",
        "mediator_results",
        "fair_baseline_gate",
        "baseline_results",
        "matched_local_results",
        "exact64_bridge_gate",
        "status",
        "completed_gates",
        "stopped_at_gate",
        "not_run_gates",
        "independent_process_reproduction_required",
        "phase_authorization",
    }
    oracle_validations = {
        str(seed): _readout_result_eligible(
            oracle.get(str(seed)) if isinstance(oracle, Mapping) else None,
            phase_prefix="oracle_readout",
        )
        for seed in TRAINABLE_SEEDS
    }
    transport_validations = {
        str(seed): _transport_result_eligible(
            transport.get(str(seed)) if isinstance(transport, Mapping) else None
        )
        for seed in TRAINABLE_SEEDS
    }
    local_validations = {
        str(seed): _local_result_eligible(
            local.get(str(seed)) if isinstance(local, Mapping) else None
        )
        for seed in TRAINABLE_SEEDS
    }
    mediator_validations = {
        str(seed): _readout_result_eligible(
            mediator.get(str(seed)) if isinstance(mediator, Mapping) else None,
            phase_prefix="mediator_readout",
        )
        for seed in TRAINABLE_SEEDS
    }
    finite_errors = _validate_finite_tree(summary)
    checks = {
        "summary_keys_exact": set(summary) == expected_summary_keys,
        "summary_tree_finite": not finite_errors,
        "strict_summary_validation": strict_summary_validation["passed"],
        "phase_authorization_valid": _phase_authorization_evidence_valid(summary),
        "summary_schema_exact": summary.get("summary_schema_version")
        == SUMMARY_SCHEMA_VERSION,
        "awaiting_reproduction_status": summary.get("status") == PENDING_STATUS,
        "protocol_exact": summary.get("protocol_version") == PROTOCOL_VERSION,
        "evidence_class_exact": summary.get("evidence_class") == EVIDENCE_CLASS,
        "config_exact": summary.get("config") == expected_config,
        "config_hash_exact": summary.get("config_sha256")
        == _json_hash(expected_config),
        "source_manifest_authority_exact": _source_manifest_authority_matches_expected(
            summary.get("source_manifest"), expected_source
        ),
        "split_manifests_authority_exact": _registered_split_manifest_authority(
            summary.get("split_manifests")
        ),
        "gate_order_exact": summary.get("gate_order") == list(GATE_ORDER),
        "gates_0_to_7_explicit_pass": all(
            isinstance(gate, Mapping) and gate.get("passed") is True
            for gate in gates.values()
        ),
        "gate_trace_exact": complete_gate_records
        and summary.get("completed_gates") == expected_gate_trace,
        "no_stopped_gate": summary.get("stopped_at_gate") is None,
        "only_reproduction_not_run": summary.get("not_run_gates")
        == ["independent_reproduction"],
        "oracle_readout_once_and_complete": isinstance(oracle, Mapping)
        and set(oracle) == {str(seed) for seed in TRAINABLE_SEEDS}
        and all(validation["passed"] for validation in oracle_validations.values()),
        "transport_complete": isinstance(transport, Mapping)
        and set(transport) == {str(seed) for seed in TRAINABLE_SEEDS}
        and all(validation["passed"] for validation in transport_validations.values()),
        "transport_initial_hashes_distinct": isinstance(transport, Mapping)
        and set(transport) == {str(seed) for seed in TRAINABLE_SEEDS}
        and len(
            {
                transport[str(seed)].get("initialization", {}).get("state_sha256")
                for seed in TRAINABLE_SEEDS
            }
        )
        == len(TRAINABLE_SEEDS),
        "matched_local_complete": isinstance(local, Mapping)
        and set(local) == {str(seed) for seed in TRAINABLE_SEEDS}
        and all(validation["passed"] for validation in local_validations.values()),
        "mediator_complete_and_matcher_frozen": isinstance(mediator, Mapping)
        and set(mediator) == {str(seed) for seed in TRAINABLE_SEEDS}
        and all(
            mediator_validations[str(seed)]["passed"]
            and mediator[str(seed)].get("matcher_unchanged") is True
            and mediator[str(seed)].get("matcher_gradients_zero") is True
            for seed in TRAINABLE_SEEDS
        ),
        "post_transport_fixture_competence_explicit_pass": isinstance(
            summary.get("post_transport_fixture_competence"), Mapping
        )
        and summary["post_transport_fixture_competence"].get("passed") is True,
        "marginal_controls_present": isinstance(
            summary.get("marginal_controls"), Mapping
        )
        and set(summary["marginal_controls"])
        == {str(seed) for seed in TRAINABLE_SEEDS},
        "binding_results_present": isinstance(summary.get("binding_results"), Mapping)
        and set(summary["binding_results"]) == {str(seed) for seed in TRAINABLE_SEEDS},
        "baseline_results_present": isinstance(
            summary.get("baseline_results"), Mapping
        ),
        "formal_test_sealed": summary.get("formal_test_used") is False
        and summary.get("formal_test_status") == "SEALED",
        "formal_claim_closed": summary.get("formal_claim_allowed") is False
        and summary.get("formal_ablation_claim_allowed") is False
        and summary.get("full_method_claim_allowed") is False,
        "formal_data_hold": summary.get("formal_data_authorization") == "HOLD",
        "deterministic_environment": isinstance(environment, Mapping)
        and environment.get("deterministic_algorithms_enabled") is True
        and environment.get("pythonhashseed") == "0"
        and environment.get("omp_num_threads") == "1"
        and environment.get("mkl_num_threads") == "1",
        "interop_locale_timezone_debug_environment": isinstance(environment, Mapping)
        and environment.get("torch_num_threads") == 1
        and environment.get("torch_num_interop_threads") == 1
        and isinstance(environment.get("deterministic_debug_mode"), int)
        and _sha256_like(environment.get("torch_build_sha256"))
        and isinstance(environment.get("locale_lc_all"), str)
        and isinstance(environment.get("locale_preferred_encoding"), str)
        and isinstance(environment.get("timezone_name"), str)
        and isinstance(environment.get("timezone_offset"), str),
        "process_identity_present": isinstance(provenance, Mapping)
        and isinstance(provenance.get("pid"), int)
        and not isinstance(provenance.get("pid"), bool)
        and provenance.get("pid", 0) > 0
        and _valid_uuid(provenance.get("process_uuid")),
        "reproduction_required": summary.get(
            "independent_process_reproduction_required"
        )
        is True,
    }
    validation_errors = {
        "summary_nonfinite_paths": finite_errors,
        "oracle": oracle_validations,
        "transport": transport_validations,
        "matched_local": local_validations,
        "mediator": mediator_validations,
        "strict_summary": strict_summary_validation,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "validation_errors": validation_errors,
    }


_CANONICAL_REPRODUCTION_VOLATILE_EXCLUSION_PATHS = (
    "/provenance/start_utc",
    "/provenance/end_utc",
    "/provenance/monotonic_elapsed_seconds",
    "/provenance/pid",
    "/provenance/process_uuid",
    "/provenance/output_root_absolute",
    "/provenance/raw_argv",
    "/provenance/output_root_entry_evidence/output_root_contract/expected_leaf",
    "/phase_authorization",
    "/source_manifest/observed_workspace_imports",
)


def _canonical_reproduction_exclusion_paths() -> tuple[str, ...]:
    """Reopen the exact frozen projection contract without permissive fallback."""

    registry = FROZEN_R6_REGISTRY.get("reproduction_contract")
    paths = (
        registry.get("volatile_exclusion_paths")
        if isinstance(registry, Mapping)
        else None
    )
    if (
        not isinstance(paths, list)
        or any(type(pointer) is not str for pointer in paths)
        or tuple(paths) != _CANONICAL_REPRODUCTION_VOLATILE_EXCLUSION_PATHS
        or len(paths) != len(set(paths))
    ):
        raise ValueError(
            "canonical reproduction volatile exclusion contract is not exact"
        )
    return tuple(paths)


def _canonical_reproduction_payload(summary: Mapping[str, Any]) -> dict[str, Any]:
    expected_exclusions = _canonical_reproduction_exclusion_paths()
    payload = copy.deepcopy(dict(summary))
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("canonical reproduction requires provenance object")
    run_root_value = provenance.get("output_root_absolute")
    if not isinstance(run_root_value, str):
        raise ValueError("canonical reproduction requires output_root_absolute")
    run_root = Path(run_root_value).resolve()

    def normalize_paths(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {key: normalize_paths(item) for key, item in value.items()}
        if isinstance(value, list):
            return [normalize_paths(item) for item in value]
        if isinstance(value, str):
            candidate = Path(value)
            if candidate.is_absolute():
                try:
                    return candidate.resolve().relative_to(run_root).as_posix() or "."
                except (OSError, ValueError):
                    return value
        return value

    payload = normalize_paths(payload)
    for pointer in expected_exclusions:
        tokens = [
            token.replace("~1", "/").replace("~0", "~")
            for token in pointer.split("/")[1:]
        ]
        target: Any = payload
        for token in tokens[:-1]:
            if not isinstance(target, dict) or token not in target:
                raise ValueError(f"canonical reproduction missing {pointer}")
            target = target[token]
        if not tokens or not isinstance(target, dict) or tokens[-1] not in target:
            raise ValueError(f"canonical reproduction missing {pointer}")
        target.pop(tokens[-1])
    json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return payload


def _mismatch_paths(left: Any, right: Any, path: str = "") -> list[str]:
    if type(left) is not type(right):
        return [path]
    if isinstance(left, Mapping):
        result: list[str] = []
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                escaped = str(key).replace("~", "~0").replace("/", "~1")
                result.append(f"{path}/{escaped}")
            else:
                escaped = str(key).replace("~", "~0").replace("/", "~1")
                result.extend(
                    _mismatch_paths(left[key], right[key], f"{path}/{escaped}")
                )
        return result
    if isinstance(left, list):
        if len(left) != len(right):
            return [path]
        result = []
        for index, (left_item, right_item) in enumerate(zip(left, right, strict=True)):
            result.extend(_mismatch_paths(left_item, right_item, f"{path}/{index}"))
        return result
    return [] if left == right else [path]


def _valid_uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        return False
    return parsed.version == 4 and str(parsed) == value.lower()


def _compare_independent_reproduction(
    primary: Mapping[str, Any],
    replica: Mapping[str, Any],
    *,
    primary_returncode: int,
    replica_returncode: int,
    primary_expected_pid: int,
    replica_expected_pid: int,
) -> dict[str, Any]:
    primary_eligibility = _registered_reproduction_eligibility(primary)
    replica_eligibility = _registered_reproduction_eligibility(replica)
    if not primary_eligibility["passed"] or not replica_eligibility["passed"]:
        raise ValueError("canonical comparison requires two strictly eligible payloads")
    primary_payload = _canonical_reproduction_payload(primary)
    replica_payload = _canonical_reproduction_payload(replica)
    primary_blob = json.dumps(
        primary_payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    replica_blob = json.dumps(
        replica_payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    primary_sha = hashlib.sha256(primary_blob).hexdigest()
    replica_sha = hashlib.sha256(replica_blob).hexdigest()
    mismatches = _mismatch_paths(primary_payload, replica_payload)
    primary_identity = primary.get("provenance", {})
    replica_identity = replica.get("provenance", {})
    checks = {
        "primary_process_exit_zero": primary_returncode == 0,
        "replica_process_exit_zero": replica_returncode == 0,
        "canonical_payload_exact": not mismatches,
        "canonical_sha256_exact": primary_sha == replica_sha,
        "primary_registered_payload_eligible": primary_eligibility["passed"],
        "replica_registered_payload_eligible": replica_eligibility["passed"],
        "valid_process_uuids": _valid_uuid(primary_identity.get("process_uuid"))
        and _valid_uuid(replica_identity.get("process_uuid")),
        "independent_process_uuids": primary_identity.get("process_uuid")
        != replica_identity.get("process_uuid"),
        "primary_pid_matches_launcher": primary_identity.get("pid")
        == primary_expected_pid,
        "replica_pid_matches_launcher": replica_identity.get("pid")
        == replica_expected_pid,
        "independent_process_pids": primary_identity.get("pid")
        != replica_identity.get("pid"),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "passed": all(checks.values()),
        "checks": checks,
        "primary_canonical_sha256": primary_sha,
        "replica_canonical_sha256": replica_sha,
        "mismatch_count": len(mismatches),
        "mismatch_paths": mismatches,
        "primary_process_returncode": int(primary_returncode),
        "replica_process_returncode": int(replica_returncode),
        "primary_launcher_pid": int(primary_expected_pid),
        "replica_launcher_pid": int(replica_expected_pid),
        "primary_eligibility": primary_eligibility,
        "replica_eligibility": replica_eligibility,
        "comparison_excludes_only": copy.deepcopy(
            list(_canonical_reproduction_exclusion_paths())
        ),
    }


_SUMMARY_BASE_KEYS = {
    "summary_schema_version",
    "protocol_version",
    "evidence_class",
    "config",
    "config_sha256",
    "source_manifest",
    "runtime_environment",
    "provenance",
    "execution_request",
    "gate_order",
    "formal_test_used",
    "formal_test_status",
    "formal_data_authorization",
    "formal_claim_allowed",
    "formal_ablation_claim_allowed",
    "full_method_claim_allowed",
    "data_access_ledger",
}
_GATE_OUTPUT_KEYS = {
    "resolution_freeze": {"resolution_freeze_gate"},
    "structural_input": {"structural_input_gate"},
    "fixture_identifiability": {"fixture_identifiability_gate"},
    "transport_competence": {"transport_competence_gate", "transport_results"},
    "anti_equivalence": {"anti_equivalence_gate"},
    "mediator_recovery": {
        "common_oracle_readout_results",
        "marginal_controls",
        "binding_results",
        "post_transport_fixture_competence",
        "mediator_recovery_gate",
        "mediator_results",
    },
    "fair_baseline": {
        "fair_baseline_gate",
        "baseline_results",
        "matched_local_results",
    },
    "exact64_bridge": {"exact64_bridge_gate"},
}

_GATE_STATUS_CONTRACT = {
    "resolution_freeze": ("PASS", "FAIL_RESOLUTION_FREEZE"),
    "structural_input": ("PASS", "FAIL_STRUCTURAL_INPUT"),
    "fixture_identifiability": (
        "DRY_RUN_FIXTURE_AUTHORITY_VALIDATED",
        "FAIL_FIXTURE_AUTHORITY",
    ),
    "transport_competence": ("PASS", "FAIL_TRANSPORT_COMPETENCE"),
    "anti_equivalence": ("PASS", "FAIL_ANTI_EQUIVALENCE"),
    "mediator_recovery": ("PASS", "FAIL_MEDIATOR_RECOVERY"),
    "fair_baseline": ("PASS", "FAIL_FAIR_BASELINE"),
    "exact64_bridge": ("PASS", "FAIL_EXACT64_BRIDGE"),
}

_ACCESS_PURPOSE_BY_GATE = {
    "structural_input": "structural_microfixtures_and_full_chain_counterfactuals",
    "fixture_identifiability": "independent_fixture_development_certificate",
    "transport_competence": {
        ("clean", "train"): "transport_training",
        ("challenge", "train"): "transport_training",
        (
            "clean",
            "inner_development",
        ): "post_checkpoint_transport_model_selection_audit",
        (
            "challenge",
            "inner_development",
        ): "post_checkpoint_transport_model_selection_audit",
        ("clean", "development"): "post_checkpoint_clean_transport_gate",
    },
    "anti_equivalence": "post_gate3_challenge_transport_gate",
    "mediator_recovery": "common_oracle_and_mediator_readout",
    "fair_baseline": "matched_local_and_fair_baseline",
}


def _expected_access_ledger_prefix(
    completed_gate_names: Sequence[str],
    split_manifests: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Rebuild the exact authorized data prefix from frozen authority."""

    expected: list[dict[str, Any]] = []
    for gate_name in completed_gate_names:
        accesses = _R6SplitAccessor._ACCESS_SEQUENCE.get(gate_name, ())
        for stratum, split in accesses:
            if split in {"literal_audit_fixture", "frozen_fixture_audit"}:
                content_hash = FROZEN_R5_REGISTRY["fixture_hashes"][stratum][
                    "fixture_development_visible"
                ]
                cache_hit = gate_name == "fixture_identifiability"
            else:
                manifest = split_manifests.get(stratum, {}).get(split, {})
                content_hash = (
                    manifest.get("fixture_hash_evidence", {}).get("visible")
                    if isinstance(manifest, Mapping)
                    else None
                )
                cache_hit = gate_name in {"mediator_recovery", "fair_baseline"}
            purpose_contract = _ACCESS_PURPOSE_BY_GATE[gate_name]
            purpose = (
                purpose_contract[(stratum, split)]
                if isinstance(purpose_contract, Mapping)
                else purpose_contract
            )
            expected.append(
                _access_ledger_entry(
                    gate=gate_name,
                    stratum=stratum,
                    split=split,
                    name=f"{stratum}_{split}",
                    purpose=str(purpose),
                    content_hash=str(content_hash),
                    cache_hit=cache_hit,
                )
            )
    return expected


def _strict_summary_validation(summary: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []

    try:
        semantic_metric_certificate = validate_r6_metric_evidence(summary)
    except R6ValidationError as error:
        semantic_metric_certificate = None
        errors.extend(
            {
                "pointer": issue.pointer,
                "rule": issue.rule,
                "observed_type": type(issue.observed_value).__name__,
                "observed_value": repr(issue.observed_value)[:300],
                "source": "independent_semantic_metric_validator",
            }
            for issue in error.issues
        )

    native_reports = []
    structural_gate = summary.get("structural_input_gate")
    if isinstance(structural_gate, Mapping):
        gate1 = structural_gate.get("r6_gate1_evidence")
        if isinstance(gate1, Mapping):
            native_reports.extend(
                (
                    (
                        "/structural_input_gate/r6_gate1_evidence/structural_microcases",
                        gate1.get("structural_microcases"),
                        validate_r6_structural_audit,
                    ),
                    (
                        "/structural_input_gate/r6_gate1_evidence/full_chain_counterfactual",
                        gate1.get("full_chain_counterfactual"),
                        validate_r6_counterfactual_audit,
                    ),
                )
            )
    bridge_gate = summary.get("exact64_bridge_gate")
    if isinstance(bridge_gate, Mapping):
        native_reports.append(
            (
                "/exact64_bridge_gate/r6_full_chain_counterfactual",
                bridge_gate.get("r6_full_chain_counterfactual"),
                validate_r6_counterfactual_audit,
            )
        )
    for pointer, report, validator in native_reports:
        if report is None:
            continue
        try:
            validator(report)
        except (KeyError, TypeError, ValueError) as error:
            errors.append(
                {
                    "pointer": pointer,
                    "rule": f"native {validator.__name__} pass",
                    "observed_type": type(error).__name__,
                    "observed_value": _safe_exception_message(error)[:300],
                    "source": "native_loaded_report_validator",
                }
            )

    def require(condition: bool, pointer: str, rule: str, observed: Any) -> None:
        if not condition:
            errors.append(
                {
                    "pointer": pointer,
                    "rule": rule,
                    "observed_type": type(observed).__name__,
                    "observed_value": repr(observed)[:300],
                }
            )

    status = summary.get("status")
    completed = summary.get("completed_gates")
    require(isinstance(status, str), "/status", "string", status)
    require(isinstance(completed, list), "/completed_gates", "array", completed)
    require(not _validate_finite_tree(summary), "", "all numbers finite", summary)
    require(
        summary.get("protocol_version") == PROTOCOL_VERSION,
        "/protocol_version",
        "exact R10 protocol",
        summary.get("protocol_version"),
    )
    require(
        summary.get("config_sha256") == _json_hash(summary.get("config")),
        "/config_sha256",
        "recomputed config SHA-256",
        summary.get("config_sha256"),
    )
    source = summary.get("source_manifest")
    require(
        _source_manifest_authority_valid(source),
        "/source_manifest/source_manifest_authority_sha256",
        "exact context-invariant source authority and closed observation subset",
        (
            source.get("source_manifest_authority_sha256")
            if isinstance(source, Mapping)
            else source
        ),
    )
    provenance = summary.get("provenance")
    require(isinstance(provenance, Mapping), "/provenance", "object", provenance)
    if isinstance(provenance, Mapping):
        require(
            is_utc_z_timestamp(provenance.get("start_utc")),
            "/provenance/start_utc",
            "UTC timestamp with literal Z",
            provenance.get("start_utc"),
        )
        require(
            is_utc_z_timestamp(provenance.get("end_utc")),
            "/provenance/end_utc",
            "UTC timestamp with literal Z",
            provenance.get("end_utc"),
        )
        require(
            is_uuid4(provenance.get("process_uuid")),
            "/provenance/process_uuid",
            "UUID version 4",
            provenance.get("process_uuid"),
        )
        elapsed = provenance.get("monotonic_elapsed_seconds")
        require(
            isinstance(elapsed, (int, float))
            and not isinstance(elapsed, bool)
            and elapsed >= 0,
            "/provenance/monotonic_elapsed_seconds",
            "nonnegative finite number",
            elapsed,
        )
    for field in (
        "formal_test_used",
        "formal_claim_allowed",
        "formal_ablation_claim_allowed",
        "full_method_claim_allowed",
    ):
        require(
            summary.get(field) is False,
            f"/{field}",
            "literal false",
            summary.get(field),
        )
    config_mode = (
        summary.get("config") if isinstance(summary.get("config"), Mapping) else {}
    )
    is_dry_run_summary = config_mode.get("dry_run") is True
    is_authorized_success = status in {
        FROZEN_R6_REGISTRY["status_vocabulary"]["smoke_success"],
        PENDING_STATUS,
    }
    require(
        ("phase_authorization" not in summary)
        if is_dry_run_summary
        else (
            not is_authorized_success or _phase_authorization_evidence_valid(summary)
        ),
        "/phase_authorization",
        "dry-run forbids authorization evidence and successful smoke/registered summaries bind a valid persisted claim",
        summary.get("phase_authorization"),
    )

    if isinstance(completed, list):
        names = [
            record.get("name") for record in completed if isinstance(record, Mapping)
        ]
        require(
            len(names) == len(completed),
            "/completed_gates",
            "every record is an object",
            completed,
        )
    else:
        names = []
    completed_records = completed if isinstance(completed, list) else []

    recomputed_trace: list[dict[str, Any]] = []
    for gate_name in names:
        gate_field = f"{gate_name}_gate"
        gate = summary.get(gate_field)
        require(
            isinstance(gate, Mapping),
            f"/{gate_field}",
            "gate object",
            gate,
        )
        if not isinstance(gate, Mapping):
            continue
        checks = gate.get("checks")
        require(
            isinstance(checks, Mapping) and bool(checks),
            f"/{gate_field}/checks",
            "nonempty checks object",
            checks,
        )
        checks_are_booleans = isinstance(checks, Mapping) and all(
            type(value) is bool for value in checks.values()
        )
        require(
            checks_are_booleans,
            f"/{gate_field}/checks",
            "all stored checks are literal booleans",
            checks,
        )
        recomputed_passed = bool(
            checks_are_booleans and all(value is True for value in checks.values())
        )
        require(
            gate.get("passed") is recomputed_passed,
            f"/{gate_field}/passed",
            "recomputed conjunction of checks",
            gate.get("passed"),
        )
        status_contract = _GATE_STATUS_CONTRACT.get(gate_name)
        require(
            status_contract is not None,
            f"/{gate_field}/status",
            "registered gate status contract",
            gate.get("status"),
        )
        if status_contract is not None:
            expected_gate_status = status_contract[0 if recomputed_passed else 1]
            require(
                gate.get("status") == expected_gate_status,
                f"/{gate_field}/status",
                f"recomputed gate status {expected_gate_status}",
                gate.get("status"),
            )
        recomputed_trace.append(_gate_record(gate_name, gate))
    require(
        completed == recomputed_trace,
        "/completed_gates",
        "trace exactly recomputed from gate payloads",
        completed,
    )
    if status != _stop_status("premature_data_access"):
        expected_access_prefix = _expected_access_ledger_prefix(
            names,
            summary.get("split_manifests", {})
            if isinstance(summary.get("split_manifests"), Mapping)
            else {},
        )
        require(
            summary.get("data_access_ledger") == expected_access_prefix,
            "/data_access_ledger",
            "exact recomputed authorized gate prefix",
            summary.get("data_access_ledger"),
        )

    if status == FROZEN_R6_REGISTRY["status_vocabulary"][
        "dry_run_success"
    ] or status == _stop_status("premature_data_access"):
        expected_keys = (
            _SUMMARY_BASE_KEYS
            | {
                "split_manifests",
                "dry_run_data_access_gate",
                "status",
                "training_allowed",
                "completed_gates",
                "stopped_at_gate",
                "not_run_gates",
            }
            | _GATE_OUTPUT_KEYS["resolution_freeze"]
            | _GATE_OUTPUT_KEYS["structural_input"]
            | _GATE_OUTPUT_KEYS["fixture_identifiability"]
        )
        require(
            names == list(GATE_ORDER[:3]),
            "/completed_gates",
            "exact Gates 0-2 prefix",
            names,
        )
        access_validation = _dry_run_access_ledger_gate(
            summary.get("data_access_ledger", []), summary.get("split_manifests", {})
        )
        expected_status = (
            FROZEN_R6_REGISTRY["status_vocabulary"]["dry_run_success"]
            if access_validation["passed"]
            and all(record.get("passed") is True for record in completed_records)
            else _stop_status("premature_data_access")
        )
        require(
            status == expected_status, "/status", "recomputed dry-run status", status
        )
        require(
            summary.get("training_allowed") is False,
            "/training_allowed",
            "literal false",
            summary.get("training_allowed"),
        )
        require(
            summary.get("stopped_at_gate") is None,
            "/stopped_at_gate",
            "literal null for dry-run terminal family",
            summary.get("stopped_at_gate"),
        )
        require(
            summary.get("not_run_gates") == list(GATE_ORDER[3:]),
            "/not_run_gates",
            "exact Gates 3-8 suffix",
            summary.get("not_run_gates"),
        )
        require(
            summary.get("dry_run_data_access_gate") == access_validation,
            "/dry_run_data_access_gate",
            "independently recomputed access gate",
            summary.get("dry_run_data_access_gate"),
        )
        if status == _stop_status("premature_data_access"):
            require(
                all(record.get("passed") is True for record in completed_records)
                and access_validation["passed"] is False,
                "/status",
                "premature-access stop requires Gates 0-2 pass and access audit fail",
                status,
            )
    elif isinstance(status, str) and status.startswith(SCIENTIFIC_STOP_PREFIX):
        stopped_at = summary.get("stopped_at_gate")
        require(
            stopped_at in GATE_ORDER, "/stopped_at_gate", "registered gate", stopped_at
        )
        index = GATE_ORDER.index(stopped_at) if stopped_at in GATE_ORDER else 0
        expected_keys = _SUMMARY_BASE_KEYS | {
            "status",
            "completed_gates",
            "stopped_at_gate",
            "not_run_gates",
        }
        if index >= 1:
            expected_keys.add("split_manifests")
        for gate in GATE_ORDER[: index + 1]:
            expected_keys |= _GATE_OUTPUT_KEYS.get(gate, set())
        if stopped_at == "mediator_recovery" and "mediator_results" not in summary:
            expected_keys.discard("mediator_results")
        require(
            names == list(GATE_ORDER[: index + 1]),
            "/completed_gates",
            "first-failure gate prefix",
            names,
        )
        require(
            bool(completed_records)
            and all(record.get("passed") is True for record in completed_records[:-1])
            and completed_records[-1].get("passed") is False,
            "/completed_gates",
            "earlier gates pass and final completed gate is first failure",
            completed,
        )
        require(
            status == _stop_status(str(stopped_at)),
            "/status",
            "recomputed stop status",
            status,
        )
        require(
            summary.get("not_run_gates") == list(GATE_ORDER[index + 1 :]),
            "/not_run_gates",
            "exact later-gate suffix",
            summary.get("not_run_gates"),
        )
    else:
        expected_keys = _SUMMARY_BASE_KEYS | {
            "split_manifests",
            "status",
            "completed_gates",
            "stopped_at_gate",
            "not_run_gates",
            "independent_process_reproduction_required",
            "phase_authorization",
        }
        for gate in GATE_ORDER[:8]:
            expected_keys |= _GATE_OUTPUT_KEYS.get(gate, set())
        require(
            names == list(GATE_ORDER[:8]), "/completed_gates", "exact Gates 0-7", names
        )
        if status == PENDING_STATUS:
            require(
                all(record.get("passed") is True for record in completed_records),
                "/completed_gates",
                "all registered gates pass",
                completed,
            )
        else:
            require(
                status == FROZEN_R6_REGISTRY["status_vocabulary"]["smoke_success"],
                "/status",
                "registered pending or smoke status",
                status,
            )
    require(
        set(summary) == expected_keys,
        "",
        "exact top-level key set for terminal family",
        sorted(set(summary) ^ expected_keys),
    )
    return {
        "passed": not errors,
        "errors": errors,
        "semantic_metric_certificate": semantic_metric_certificate,
    }


def _serialize_json_bytes(payload: Mapping[str, Any]) -> bytes:
    """Serialize one finite JSON artifact in the production wire format."""

    rendered = json.dumps(
        payload,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
    return (rendered + "\n").encode("utf-8")


def _atomic_write_bytes_new(path: Path, payload: bytes) -> None:
    """Durably publish exact bytes without overwriting prior evidence."""

    if not isinstance(payload, bytes):
        raise TypeError("atomic evidence payload must be bytes")
    target_snapshot = _workspace_path_snapshot(path, require_exists=False)
    if target_snapshot["target_exists"]:
        raise FileExistsError(f"refusing to overwrite evidence artifact: {path}")
    parent_snapshot = _workspace_path_snapshot(
        path.parent, require_exists=True, require_directory=True
    )
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    temporary_snapshot = _workspace_path_snapshot(temporary, require_exists=False)
    if temporary_snapshot["target_exists"]:
        raise FileExistsError(
            f"temporary evidence artifact already exists: {temporary}"
        )
    # This is intentionally adjacent to O_EXCL: path validation alone is not a
    # sufficient authorization boundary when a Windows directory can be replaced.
    _revalidate_workspace_path_snapshot(parent_snapshot)
    _revalidate_workspace_path_snapshot(temporary_snapshot)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(temporary_snapshot["raw_path"], flags, 0o600)
    try:
        temporary_created = _workspace_path_snapshot(
            temporary, require_exists=True, require_regular_file=True
        )
        opened = os.fstat(descriptor)
        if (
            _workspace_metadata_identity(opened)
            != tuple(temporary_created["components"])[-1][1][:4]
        ):
            raise ValueError(
                "opened temporary evidence file differs from safe snapshot"
            )
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        # Size/timestamps change because this transaction just wrote the file;
        # directory/file identity and reparse state must nevertheless remain fixed.
        _revalidate_workspace_path_snapshot(temporary_created, identity_only=True)
        _revalidate_workspace_path_snapshot(parent_snapshot, identity_only=True)
        os.link(temporary, path)
        published = _workspace_path_snapshot(
            path, require_exists=True, require_regular_file=True
        )
        if (
            tuple(published["components"])[-1][1][:4]
            != tuple(temporary_created["components"])[-1][1][:4]
        ):
            raise ValueError("published evidence path differs from created file")
        temporary.unlink()
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _atomic_write_json_new(path: Path, payload: Mapping[str, Any]) -> None:
    """Durably publish a JSON artifact without overwriting prior evidence."""

    _atomic_write_bytes_new(path, _serialize_json_bytes(payload))


def _authorization_canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    """Return the compact, byte-stable encoding fixed by the R10 authority."""

    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _authorization_self_hash(payload: Mapping[str, Any], field: str) -> str:
    projection = dict(payload)
    projection.pop(field, None)
    return hashlib.sha256(_authorization_canonical_bytes(projection)).hexdigest()


def _authorization_value_exact(observed: Any, expected: Any) -> bool:
    """Compare fixed authorization values without Python numeric coercion."""

    if type(observed) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(observed) == set(expected) and all(
            _authorization_value_exact(observed[key], value)
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(observed) == len(expected) and all(
            _authorization_value_exact(value, expected[index])
            for index, value in enumerate(observed)
        )
    return observed == expected


def _authorization_snapshot(path: Path) -> tuple[bytes, dict[str, Any], str]:
    """Read one immutable authority artifact without following a link."""

    target_snapshot = _workspace_path_snapshot(
        path, require_exists=True, require_regular_file=True
    )
    parent_snapshot = _workspace_path_snapshot(
        path.parent, require_exists=True, require_directory=True
    )
    _revalidate_workspace_path_snapshot(target_snapshot)
    _revalidate_workspace_path_snapshot(parent_snapshot)
    raw = _native_read_existing_child(
        parent_snapshot["raw_path"], Path(target_snapshot["raw_path"]).name
    )
    _revalidate_workspace_path_snapshot(target_snapshot)
    _revalidate_workspace_path_snapshot(parent_snapshot)
    decoded = json.loads(raw.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError(f"authorization artifact must contain a JSON object: {path}")
    return raw, decoded, hashlib.sha256(raw).hexdigest()


def _relative_authorization_path(path: Path) -> str:
    snapshot = _workspace_path_snapshot(path, require_exists=True)
    return snapshot["resolved_path"].relative_to(WORKSPACE.resolve()).as_posix()


def _pre_root_authorization_target_relative(path: Path) -> str:
    """Derive an absent output leaf's fixed registry path without weakening safety."""

    target_snapshot = _workspace_path_snapshot(path, require_exists=False)
    if target_snapshot["target_exists"]:
        raise ValueError(f"pre-root authorization target already exists: {path}")
    raw_path = Path(target_snapshot["raw_path"])
    parent_snapshot = _workspace_path_snapshot(
        raw_path.parent, require_exists=True, require_directory=True
    )
    _revalidate_workspace_path_snapshot(target_snapshot)
    _revalidate_workspace_path_snapshot(parent_snapshot)
    return raw_path.relative_to(WORKSPACE.absolute()).as_posix()


def _phase_authorization_mode(args: argparse.Namespace) -> str:
    if args.dry_run:
        return "dry_run"
    reproduction_leaves = {
        IMPLEMENTED_OUTPUT_LEAVES["reproduction_local"],
        IMPLEMENTED_OUTPUT_LEAVES["reproduction_slurm4161"],
    }
    if (
        args.run_dir.name in IMPLEMENTED_REPRODUCTION_CHILD_LEAVES
        and args.run_dir.parent.name in reproduction_leaves
    ):
        return "independent_reproduction"
    if args.smoke:
        return "smoke"
    if os.environ.get("SLURM_JOB_ID") == "4161":
        return "registered_slurm4161"
    return "registered_local"


def _materializer_provenance_matches_frozen_contract(
    provenance: Any, *, materializer_id: Any
) -> bool:
    """Require an external audit receipt to name one frozen materializer exactly."""

    phase_contract = FROZEN_R6_REGISTRY["phase_authorization_contract"]
    materializers = phase_contract.get("external_materializers")
    if not isinstance(materializer_id, str) or not isinstance(materializers, Mapping):
        return False
    specification = materializers.get(materializer_id)
    if not isinstance(specification, Mapping):
        return False
    relative_path = specification.get("relative_path")
    file_sha256 = specification.get("sha256")
    invocation = specification.get("invocation")
    if (
        not isinstance(relative_path, str)
        or not _sha256_like(file_sha256)
        or not isinstance(invocation, Mapping)
        or invocation.get("argv0_must_resolve_to_materializer_relative_path")
        is not True
        or not isinstance(invocation.get("working_directory_relative"), str)
        or not isinstance(invocation.get("argv_tail"), list)
    ):
        return False
    expected = {
        "materializer_id": materializer_id,
        "relative_path": relative_path,
        "sha256": file_sha256,
        "invocation": {
            "working_directory_relative": invocation["working_directory_relative"],
            "argv0_relative_path": relative_path,
            "argv_tail": invocation["argv_tail"],
        },
    }
    return _authorization_value_exact(provenance, expected)


def _issuing_materializer_id(specification: Mapping[str, Any]) -> str | None:
    """Return the sole R24 reproduction materializer key, rejecting aliases."""

    if "issuer_materializer_id" in specification:
        return None
    value = specification.get("issuing_materializer_id")
    return value if isinstance(value, str) else None


def _validate_prerequisite_audit(
    audit: Mapping[str, Any], specification: Mapping[str, Any]
) -> bool:
    phase_contract = FROZEN_R6_REGISTRY["phase_authorization_contract"]
    audit_contract = next(
        (
            candidate
            for key, candidate in phase_contract.items()
            if key.endswith("_postrun_audit_contract")
            and isinstance(candidate, Mapping)
            and candidate.get("schema_version")
            == specification["prerequisite_audit_schema_version"]
        ),
        None,
    )
    if not isinstance(audit_contract, Mapping):
        return False
    self_field = str(specification["prerequisite_audit_self_hash_field"])
    checks = audit.get("checks")
    failed_checks = audit.get("failed_checks")
    evidence = audit.get("evidence")
    return (
        set(audit) == set(audit_contract["required_exact_top_level_keys"])
        and audit.get("schema_version")
        == specification["prerequisite_audit_schema_version"]
        and audit.get("verdict") == specification["prerequisite_audit_verdict"]
        and audit.get("passed") is True
        and isinstance(checks, Mapping)
        and set(checks) == set(audit_contract["required_exact_check_keys"])
        and all(value is True for value in checks.values())
        and failed_checks == []
        and isinstance(evidence, Mapping)
        and _materializer_provenance_matches_frozen_contract(
            evidence.get("materializer_provenance"),
            materializer_id=audit_contract.get("materializer_id"),
        )
        and audit.get(self_field) == _authorization_self_hash(audit, self_field)
    )


def _phase_authorization_failure(reason: str) -> RuntimeError:
    return RuntimeError(f"{PROTOCOL_VERSION} phase authorization denied: {reason}")


def _phase_authorization_specification(
    contract: Mapping[str, Any], certificate_type: str
) -> tuple[Mapping[str, Any], Mapping[str, Any] | None]:
    """Resolve one fixed certificate type without a permissive fallback."""

    reproduction = contract.get("reproduction_authorization")
    if isinstance(reproduction, Mapping):
        child_certificates = reproduction.get("child_certificates")
        if isinstance(child_certificates, Mapping):
            for child_specification in child_certificates.values():
                if (
                    isinstance(child_specification, Mapping)
                    and child_specification.get("certificate_type") == certificate_type
                ):
                    return reproduction, child_specification
    specification = contract.get(certificate_type)
    if isinstance(specification, Mapping):
        return specification, None
    raise _phase_authorization_failure("certificate type has no frozen specification")


def _write_phase_claim(path: Path, payload: Mapping[str, Any]) -> bytes:
    """Claim a certificate exactly once using the authority-mandated O_EXCL write."""

    encoded = _authorization_canonical_bytes(payload)
    try:
        target_snapshot = _workspace_path_snapshot(path, require_exists=False)
        if target_snapshot["target_exists"]:
            raise FileExistsError(path)
        parent_snapshot = _workspace_path_snapshot(
            path.parent, require_exists=True, require_directory=True
        )
        # Keep this immediately before the mandated O_EXCL open.  A later
        # reparse/parent swap is detected by the opened file and parent checks.
        _revalidate_workspace_path_snapshot(target_snapshot)
        _revalidate_workspace_path_snapshot(parent_snapshot)
    except ValueError as error:
        raise _phase_authorization_failure(
            "claim parent is not a safe workspace path"
        ) from error
    try:
        _native_create_new_child(
            parent_snapshot["raw_path"],
            Path(target_snapshot["raw_path"]).name,
            directory=False,
            payload=encoded,
        )
        # Native creation is closed before returning; do not re-enter the
        # path-based snapshot layer here.  R11 post-create receipt validation
        # must be performed from a verified native parent/leaf handle.
        _revalidate_workspace_path_snapshot(parent_snapshot, identity_only=True)
    except Exception:
        raise
    return encoded


def _phase_authorize(
    args: argparse.Namespace,
    *,
    process_uuid: str,
    source_manifest: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Perform the frozen pre-root phase guard and consume one certificate."""

    contract = FROZEN_R6_REGISTRY["phase_authorization_contract"]
    mode = _phase_authorization_mode(args)
    runner_guard = contract["runner_guard"]
    closed_set = runner_guard["phase_authorization_mode_closed_set"]
    required_modes = runner_guard["phase_authorization_required_modes"]
    if mode not in closed_set or mode not in required_modes:
        raise _phase_authorization_failure(
            f"frozen authority does not require a certificate for {mode}"
        )
    if (
        FROZEN_R6_REGISTRY.get("authority_state")
        != IMPLEMENTED_STATUS_VOCABULARY["protocol_frozen"]
        or FROZEN_R6_REGISTRY.get("freeze_requirements", {}).get(
            "implementation_hashes_frozen"
        )
        is not True
    ):
        raise _phase_authorization_failure("frozen authority is not final frozen")
    is_reproduction = mode == "independent_reproduction"
    target_child_leaf: str | None = None
    if is_reproduction:
        specification = contract["reproduction_authorization"]
        target_child_leaf = args.run_dir.name
        child_certificates = specification.get("child_certificates")
        certificate_type_map = contract["runner_guard"][
            "independent_reproduction_child_certificate_type_map"
        ]
        if (
            target_child_leaf not in specification.get("target_child_leaf_names", ())
            or not isinstance(child_certificates, Mapping)
            or not isinstance(child_certificates.get(target_child_leaf), Mapping)
            or certificate_type_map.get(target_child_leaf)
            != child_certificates[target_child_leaf].get("certificate_type")
        ):
            raise _phase_authorization_failure(
                "reproduction child leaf is not registered"
            )
        child_specification = child_certificates[target_child_leaf]
        certificate_type = child_specification["certificate_type"]
        certificate_schema_version = child_specification["schema_version"]
        certificate_path = WORKSPACE / str(child_specification["relative_path"])
        required_keys = specification["child_certificate_required_exact_top_level_keys"]
        expected_check_keys = specification[
            "child_certificate_required_exact_check_keys"
        ]
    else:
        certificate_type = runner_guard.get(f"{mode}_requires_certificate_type")
        if not isinstance(certificate_type, str):
            raise _phase_authorization_failure(
                f"frozen authority has no certificate route for {mode}"
            )
        specification, child_specification = _phase_authorization_specification(
            contract, certificate_type
        )
        if child_specification is not None:
            raise _phase_authorization_failure(
                "ordinary phase cannot select a reproduction child certificate"
            )
        certificate_schema_version = specification.get("schema_version")
        certificate_path = WORKSPACE / str(specification.get("relative_path"))
        required_keys = specification.get("required_exact_top_level_keys")
        expected_check_keys = specification.get("required_exact_check_keys")
    if not isinstance(specification, Mapping):
        raise _phase_authorization_failure("certificate specification missing")
    if not isinstance(certificate_schema_version, str):
        raise _phase_authorization_failure("certificate schema version missing")
    try:
        certificate_raw, certificate, certificate_file_sha256 = _authorization_snapshot(
            certificate_path
        )
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise _phase_authorization_failure(
            f"certificate snapshot failed: {type(error).__name__}"
        ) from error
    if certificate_raw != _authorization_canonical_bytes(certificate):
        raise _phase_authorization_failure(
            "certificate persisted bytes are not canonical"
        )
    if not isinstance(required_keys, list) or set(certificate) != set(required_keys):
        raise _phase_authorization_failure("certificate top-level keys are not exact")
    certificate_id = certificate.get(contract["certificate_id_field"])
    phase_nonce = certificate.get(contract["phase_nonce_field"])
    if (
        not is_uuid4(certificate_id)
        or not isinstance(phase_nonce, str)
        or not _sha256_like(phase_nonce)
    ):
        raise _phase_authorization_failure("certificate ID or nonce is invalid")
    expected_target_relative = _pre_root_authorization_target_relative(args.run_dir)
    checks = certificate.get("checks")
    formal_flags = specification["formal_claim_flags_expected"]
    if not _source_manifest_authority_valid(source_manifest):
        raise _phase_authorization_failure("source manifest authority is invalid")
    source_hash = source_manifest.get("source_manifest_authority_sha256")
    target_steps = 1 if args.smoke else int(args.steps)
    if (
        [int(seed) for seed in args.seeds] != specification["target_seeds"]
        or target_steps != specification["target_steps"]
        or args.device != specification["target_device"]
    ):
        raise _phase_authorization_failure("CLI target differs from frozen authority")
    target_output_root_relative = (
        child_specification["target_output_root_relative"]
        if is_reproduction and child_specification is not None
        else specification["target_output_root_relative"]
    )
    if expected_target_relative != target_output_root_relative:
        raise _phase_authorization_failure(
            "target output root differs from frozen authority"
        )
    expected_values = {
        "schema_version": certificate_schema_version,
        "certificate_type": certificate_type,
        "protocol_id": PROTOCOL_VERSION,
        "protocol_sha256": R10_PROTOCOL_SHA256,
        "registry_sha256": _json_hash(FROZEN_R6_REGISTRY),
        "source_manifest_authority_sha256": source_hash,
        "target_phase": specification["target_phase"],
        "target_seeds": specification["target_seeds"],
        "target_steps": specification["target_steps"],
        "target_device": args.device,
        "prerequisite_summary_path": specification["prerequisite_summary_path"],
        "prerequisite_audit_path": specification["prerequisite_audit_path"],
        "prerequisite_audit_verdict": specification["prerequisite_audit_verdict"],
        "prerequisite_audit_passed": True,
        "formal_data_authorization": specification[
            "formal_data_authorization_expected"
        ],
        "formal_test_used": specification["formal_test_used_expected"],
        "formal_claim_flags": formal_flags,
        "authorized": True,
        "authorization_status": specification["authorization_status"],
    }
    if is_reproduction:
        expected_values.update(
            {
                "target_output_parent_relative": specification[
                    "target_output_parent_relative"
                ],
                "target_child_leaf": target_child_leaf,
                "target_output_root_relative": target_output_root_relative,
            }
        )
    else:
        expected_values["target_output_root_relative"] = target_output_root_relative
    if any(
        not _authorization_value_exact(certificate.get(key), value)
        for key, value in expected_values.items()
    ):
        raise _phase_authorization_failure("certificate fixed authority fields differ")
    if not _materializer_provenance_matches_frozen_contract(
        certificate.get("materializer_provenance"),
        materializer_id=_issuing_materializer_id(specification),
    ):
        raise _phase_authorization_failure(
            "certificate materializer provenance differs from frozen authority"
        )
    if (
        not isinstance(checks, Mapping)
        or set(checks) != set(expected_check_keys or ())
        or not all(value is True for value in checks.values())
    ):
        raise _phase_authorization_failure(
            "certificate checks are not exact all-true booleans"
        )
    self_field = str(contract["certificate_self_hash_field"])
    if certificate.get(self_field) != _authorization_self_hash(certificate, self_field):
        raise _phase_authorization_failure("certificate self hash mismatch")
    if not is_utc_z_timestamp(certificate.get("issued_utc")):
        raise _phase_authorization_failure("certificate issue time is not UTC Z")
    prerequisite_summary_path = WORKSPACE / str(
        specification["prerequisite_summary_path"]
    )
    prerequisite_audit_path = WORKSPACE / str(specification["prerequisite_audit_path"])
    try:
        prerequisite_summary_raw, prerequisite_summary, prerequisite_summary_sha256 = (
            _authorization_snapshot(prerequisite_summary_path)
        )
        prerequisite_audit_raw, prerequisite_audit, prerequisite_audit_sha256 = (
            _authorization_snapshot(prerequisite_audit_path)
        )
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise _phase_authorization_failure(
            f"prerequisite snapshot failed: {type(error).__name__}"
        ) from error
    if (
        certificate.get("prerequisite_summary_sha256") != prerequisite_summary_sha256
        or certificate.get("prerequisite_audit_file_sha256")
        != prerequisite_audit_sha256
        or certificate.get("prerequisite_audit_self_sha256")
        != prerequisite_audit.get(specification["prerequisite_audit_self_hash_field"])
        or prerequisite_summary.get("status")
        != specification["prerequisite_summary_status"]
        or (
            not is_reproduction
            and not _strict_summary_validation(prerequisite_summary)["passed"]
        )
        or not _validate_prerequisite_audit(prerequisite_audit, specification)
    ):
        raise _phase_authorization_failure(
            "prerequisite summary or audit does not validate"
        )
    pre_root_absent = not args.run_dir.exists()
    certificate_absence_check = (
        "target_output_root_absent_at_certificate_issuance"
        if is_reproduction
        else "target_output_root_absent"
    )
    if not pre_root_absent or checks.get(certificate_absence_check) is not True:
        raise _phase_authorization_failure(
            "target output root is not absent at pre-root snapshot"
        )
    claims_root = WORKSPACE / str(contract["claims_subdirectory_relative"])
    try:
        claims_snapshot = _workspace_path_snapshot(claims_root, require_exists=False)
        if claims_snapshot["target_exists"]:
            _workspace_path_snapshot(
                claims_root, require_exists=True, require_directory=True
            )
        else:
            _safe_workspace_mkdir_new(claims_root)
    except (OSError, ValueError) as error:
        raise _phase_authorization_failure(
            "claims root is not a safe workspace path"
        ) from error
    claim_suffix = f".{target_child_leaf}" if is_reproduction else ""
    claim_path = claims_root / (
        f"{certificate_type}.{certificate_id}.{phase_nonce}{claim_suffix}.claim.json"
    )
    claim = {
        "schema_version": contract["claim_schema_version"],
        "certificate_type": certificate_type,
        "certificate_id": certificate_id,
        "phase_nonce": phase_nonce,
        "process_uuid": process_uuid,
        "target_phase": specification["target_phase"],
        "target_output_root_relative": expected_target_relative,
        "certificate_path": _relative_authorization_path(certificate_path),
        "certificate_file_sha256": certificate_file_sha256,
        "certificate_self_sha256": certificate[self_field],
        "protocol_sha256": R10_PROTOCOL_SHA256,
        "registry_sha256": _json_hash(FROZEN_R6_REGISTRY),
        "source_manifest_authority_sha256": source_hash,
        "pre_root_target_absent": True,
        "claimed_utc": _utc_now(),
    }
    if is_reproduction:
        claim["target_child_leaf"] = target_child_leaf
    claim_self_field = str(contract["claim_self_hash_field"])
    claim[claim_self_field] = _authorization_self_hash(claim, claim_self_field)
    if set(claim) != set(contract["claim_required_exact_top_level_keys"]):
        raise _phase_authorization_failure(
            "claim schema does not match frozen authority"
        )
    try:
        claim_raw = _write_phase_claim(claim_path, claim)
    except FileExistsError as error:
        raise _phase_authorization_failure(
            "certificate claim already exists"
        ) from error
    claim_file_sha256 = hashlib.sha256(claim_raw).hexdigest()
    receipt = {
        "certificate_type": certificate_type,
        "certificate_path": _relative_authorization_path(certificate_path),
        "certificate_file_sha256": certificate_file_sha256,
        "certificate_self_sha256": certificate[self_field],
        "certificate_id": certificate_id,
        "phase_nonce": phase_nonce,
        "claim_path": _relative_authorization_path(claim_path),
        "claim_file_sha256": claim_file_sha256,
        "claim_self_sha256": claim[claim_self_field],
        "claim_process_uuid": process_uuid,
        "protocol_sha256": R10_PROTOCOL_SHA256,
        "registry_sha256": _json_hash(FROZEN_R6_REGISTRY),
        "source_manifest_authority_sha256": source_hash,
        "materializer_provenance": copy.deepcopy(
            certificate["materializer_provenance"]
        ),
        "target_phase": specification["target_phase"],
        "target_output_root_relative": expected_target_relative,
        "target_seeds": [int(seed) for seed in args.seeds],
        "target_steps": 1 if args.smoke else int(args.steps),
        "target_device": args.device,
        "prerequisite_summary_sha256": hashlib.sha256(
            prerequisite_summary_raw
        ).hexdigest(),
        "prerequisite_audit_file_sha256": hashlib.sha256(
            prerequisite_audit_raw
        ).hexdigest(),
        "prerequisite_audit_self_sha256": prerequisite_audit[
            specification["prerequisite_audit_self_hash_field"]
        ],
        "formal_data_authorization": specification[
            "formal_data_authorization_expected"
        ],
        "formal_test_used": specification["formal_test_used_expected"],
        "formal_claim_flags": copy.deepcopy(formal_flags),
        "pre_root_target_absent_snapshot": True,
        "authorized": True,
        "authorization_status": specification["authorization_status"],
    }
    if is_reproduction:
        receipt["target_child_leaf"] = target_child_leaf
    return receipt


def _phase_authorization_evidence_valid(summary: Mapping[str, Any]) -> bool:
    """Validate persisted claim binding without rechecking live root absence."""

    evidence = summary.get("phase_authorization")
    config = summary.get("config")
    if not isinstance(evidence, Mapping) or not isinstance(config, Mapping):
        return False
    contract = FROZEN_R6_REGISTRY["phase_authorization_contract"]
    required = contract["runner_guard"][
        "summary_authorization_evidence_required_fields"
    ]
    if set(evidence) != set(required):
        return False
    certificate_type = evidence.get("certificate_type")
    if not isinstance(certificate_type, str):
        return False
    reproduction_specification = contract.get("reproduction_authorization")
    child_specification: Mapping[str, Any] | None = None
    if isinstance(reproduction_specification, Mapping):
        child_certificates = reproduction_specification.get("child_certificates")
        if isinstance(child_certificates, Mapping):
            for child_leaf, candidate in child_certificates.items():
                if (
                    isinstance(child_leaf, str)
                    and isinstance(candidate, Mapping)
                    and candidate.get("certificate_type") == certificate_type
                ):
                    child_specification = candidate
                    break
    is_reproduction = child_specification is not None
    specification = (
        reproduction_specification
        if is_reproduction
        else contract.get(certificate_type)
    )
    if not isinstance(specification, Mapping):
        return False
    required_certificate_keys = (
        specification.get("child_certificate_required_exact_top_level_keys")
        if is_reproduction
        else specification.get("required_exact_top_level_keys")
    )
    required_certificate_check_keys = (
        specification.get("child_certificate_required_exact_check_keys")
        if is_reproduction
        else specification.get("required_exact_check_keys")
    )
    claim_path = WORKSPACE / str(evidence.get("claim_path"))
    try:
        claim_raw, claim, claim_hash = _authorization_snapshot(claim_path)
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return False
    claim_self_field = str(contract["claim_self_hash_field"])
    provenance = summary.get("provenance")
    certificate_path = WORKSPACE / str(evidence.get("certificate_path"))
    if (
        claim_raw != _authorization_canonical_bytes(claim)
        or claim_hash != evidence.get("claim_file_sha256")
        or claim.get(claim_self_field) != evidence.get("claim_self_sha256")
        or claim.get(claim_self_field)
        != _authorization_self_hash(claim, claim_self_field)
        or set(claim) != set(contract["claim_required_exact_top_level_keys"])
        or not is_uuid4(claim.get("process_uuid"))
        or not isinstance(provenance, Mapping)
        or claim.get("process_uuid") != provenance.get("process_uuid")
        or not is_uuid4(claim.get("certificate_id"))
        or not _sha256_like(claim.get("phase_nonce"))
        or not is_utc_z_timestamp(claim.get("claimed_utc"))
    ):
        return False
    try:
        certificate_raw, certificate, certificate_hash = _authorization_snapshot(
            certificate_path
        )
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return False
    certificate_self_field = str(contract["certificate_self_hash_field"])
    certificate_checks = certificate.get("checks")
    expected_certificate_values = {
        "schema_version": (
            child_specification["schema_version"]
            if is_reproduction and child_specification is not None
            else specification["schema_version"]
        ),
        "certificate_type": certificate_type,
        "protocol_id": PROTOCOL_VERSION,
        "protocol_sha256": R10_PROTOCOL_SHA256,
        "registry_sha256": _json_hash(FROZEN_R6_REGISTRY),
        "source_manifest_authority_sha256": evidence.get(
            "source_manifest_authority_sha256"
        ),
        "target_phase": specification["target_phase"],
        "target_seeds": specification["target_seeds"],
        "target_steps": specification["target_steps"],
        "target_device": specification["target_device"],
        "prerequisite_summary_path": specification["prerequisite_summary_path"],
        "prerequisite_summary_sha256": evidence.get("prerequisite_summary_sha256"),
        "prerequisite_audit_path": specification["prerequisite_audit_path"],
        "prerequisite_audit_file_sha256": evidence.get(
            "prerequisite_audit_file_sha256"
        ),
        "prerequisite_audit_self_sha256": evidence.get(
            "prerequisite_audit_self_sha256"
        ),
        "prerequisite_audit_verdict": specification["prerequisite_audit_verdict"],
        "prerequisite_audit_passed": True,
        "formal_data_authorization": specification[
            "formal_data_authorization_expected"
        ],
        "formal_test_used": specification["formal_test_used_expected"],
        "formal_claim_flags": specification["formal_claim_flags_expected"],
        "authorized": True,
        "authorization_status": specification["authorization_status"],
    }
    if is_reproduction:
        expected_certificate_values.update(
            {
                "target_output_parent_relative": specification[
                    "target_output_parent_relative"
                ],
                "target_child_leaf": evidence.get("target_child_leaf"),
                "target_output_root_relative": child_specification[
                    "target_output_root_relative"
                ],
            }
        )
    else:
        expected_certificate_values["target_output_root_relative"] = specification[
            "target_output_root_relative"
        ]
    if (
        certificate_raw != _authorization_canonical_bytes(certificate)
        or certificate_hash != evidence.get("certificate_file_sha256")
        or certificate.get(certificate_self_field)
        != evidence.get("certificate_self_sha256")
        or certificate.get(certificate_self_field)
        != _authorization_self_hash(certificate, certificate_self_field)
        or not isinstance(required_certificate_keys, list)
        or set(certificate) != set(required_certificate_keys)
        or any(
            not _authorization_value_exact(certificate.get(key), value)
            for key, value in expected_certificate_values.items()
        )
        or not is_uuid4(certificate.get(contract["certificate_id_field"]))
        or not _sha256_like(certificate.get(contract["phase_nonce_field"]))
        or not is_utc_z_timestamp(certificate.get("issued_utc"))
        or not isinstance(certificate_checks, Mapping)
        or not isinstance(required_certificate_check_keys, list)
        or set(certificate_checks) != set(required_certificate_check_keys)
        or not all(value is True for value in certificate_checks.values())
        or not _authorization_value_exact(
            certificate.get("materializer_provenance"),
            evidence.get("materializer_provenance"),
        )
    ):
        return False
    child_suffix = f".{evidence.get('target_child_leaf')}" if is_reproduction else ""
    expected_claim_path = (
        f"{contract['claims_subdirectory_relative']}/"
        f"{certificate_type}.{evidence.get('certificate_id')}."
        f"{evidence.get('phase_nonce')}{child_suffix}.claim.json"
    )
    expected_target_output_root_relative = (
        child_specification["target_output_root_relative"]
        if is_reproduction and child_specification is not None
        else specification["target_output_root_relative"]
    )
    expected_claim_values = {
        "schema_version": contract["claim_schema_version"],
        "certificate_type": certificate_type,
        "certificate_id": evidence.get("certificate_id"),
        "phase_nonce": evidence.get("phase_nonce"),
        "process_uuid": evidence.get("claim_process_uuid"),
        "target_phase": specification["target_phase"],
        # A reproduction certificate is bound to one child leaf.  The parent
        # reproduction contract deliberately has no executable root of its
        # own, so validation must never fall back to a shared parent target.
        "target_output_root_relative": expected_target_output_root_relative,
        "certificate_path": (
            child_specification["relative_path"]
            if is_reproduction and child_specification is not None
            else specification["relative_path"]
        ),
        "certificate_file_sha256": evidence.get("certificate_file_sha256"),
        "certificate_self_sha256": evidence.get("certificate_self_sha256"),
        "protocol_sha256": R10_PROTOCOL_SHA256,
        "registry_sha256": _json_hash(FROZEN_R6_REGISTRY),
        "source_manifest_authority_sha256": evidence.get(
            "source_manifest_authority_sha256"
        ),
        "pre_root_target_absent": True,
    }
    if is_reproduction:
        expected_claim_values["target_child_leaf"] = evidence.get("target_child_leaf")
    expected = {
        **expected_claim_values,
    }
    try:
        _, prerequisite_summary, prerequisite_summary_hash = _authorization_snapshot(
            WORKSPACE / str(specification["prerequisite_summary_path"])
        )
        _, prerequisite_audit, prerequisite_audit_hash = _authorization_snapshot(
            WORKSPACE / str(specification["prerequisite_audit_path"])
        )
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return False
    return (
        evidence.get("claim_path") == expected_claim_path
        and all(
            _authorization_value_exact(claim.get(key), value)
            for key, value in expected.items()
        )
        and evidence.get("certificate_type")
        == (
            child_specification["certificate_type"]
            if is_reproduction and child_specification is not None
            else specification["certificate_type"]
        )
        and evidence.get("target_phase") == specification["target_phase"]
        and (
            not is_reproduction
            or (
                evidence.get("target_child_leaf")
                in specification["target_child_leaf_names"]
                and child_specification is not None
                and certificate_type == child_specification["certificate_type"]
                and evidence.get("certificate_path")
                == child_specification["relative_path"]
            )
        )
        and (
            is_reproduction
            or evidence.get("certificate_path") == specification["relative_path"]
        )
        and _materializer_provenance_matches_frozen_contract(
            evidence.get("materializer_provenance"),
            materializer_id=_issuing_materializer_id(specification),
        )
        and is_uuid4(evidence.get("certificate_id"))
        and _sha256_like(evidence.get("phase_nonce"))
        and _sha256_like(evidence.get("certificate_file_sha256"))
        and _sha256_like(evidence.get("certificate_self_sha256"))
        and _sha256_like(evidence.get("claim_file_sha256"))
        and _sha256_like(evidence.get("claim_self_sha256"))
        and evidence.get("claim_process_uuid") == provenance.get("process_uuid")
        and evidence.get("target_seeds") == config.get("trainable_seeds")
        and evidence.get("target_steps") == config.get("actual_steps")
        and evidence.get("target_device") == config.get("device")
        and _authorization_source_manifest_hash_matches(evidence, summary)
        and evidence.get("protocol_sha256") == R10_PROTOCOL_SHA256
        and evidence.get("registry_sha256") == _json_hash(FROZEN_R6_REGISTRY)
        and evidence.get("authorized") is True
        and evidence.get("authorization_status")
        == specification["authorization_status"]
        and evidence.get("formal_data_authorization")
        == specification["formal_data_authorization_expected"]
        and evidence.get("formal_test_used")
        == specification["formal_test_used_expected"]
        and evidence.get("formal_claim_flags")
        == specification["formal_claim_flags_expected"]
        and evidence.get("pre_root_target_absent_snapshot") is True
        and certificate.get(contract["certificate_id_field"])
        == evidence.get("certificate_id")
        and certificate.get(contract["phase_nonce_field"])
        == evidence.get("phase_nonce")
        and certificate.get("prerequisite_summary_sha256") == prerequisite_summary_hash
        and certificate.get("prerequisite_audit_file_sha256") == prerequisite_audit_hash
        and certificate.get("prerequisite_audit_self_sha256")
        == prerequisite_audit.get(specification["prerequisite_audit_self_hash_field"])
        and evidence.get("prerequisite_summary_sha256") == prerequisite_summary_hash
        and evidence.get("prerequisite_audit_file_sha256") == prerequisite_audit_hash
        and evidence.get("prerequisite_audit_self_sha256")
        == prerequisite_audit.get(specification["prerequisite_audit_self_hash_field"])
        and prerequisite_summary.get("status")
        == specification["prerequisite_summary_status"]
        and (
            is_reproduction
            or _strict_summary_validation(prerequisite_summary)["passed"]
        )
        and _validate_prerequisite_audit(prerequisite_audit, specification)
    )


def _authorization_source_manifest_hash_matches(
    evidence: Mapping[str, Any], summary: Mapping[str, Any]
) -> bool:
    """Bind authorization evidence to the context-invariant source authority."""

    source_manifest = summary.get("source_manifest")
    return (
        _source_manifest_authority_valid(source_manifest)
        and _sha256_like(evidence.get("source_manifest_authority_sha256"))
        and evidence.get("source_manifest_authority_sha256")
        == source_manifest.get("source_manifest_authority_sha256")
    )


def _final_publication_authority_recheck(
    preflight_source: Mapping[str, Any],
) -> None:
    """Fail closed if closed source or frozen protocol drifts before publishing."""

    final_source = _source_manifest()
    if not _authorization_value_exact(final_source, preflight_source):
        raise RuntimeError("R10 source/import manifest drifted before publication")
    protocol_raw = _safe_workspace_read_bytes(WORKSPACE / _R10_PROTOCOL_RELATIVE_PATH)
    if hashlib.sha256(protocol_raw).hexdigest() != R10_PROTOCOL_SHA256:
        raise RuntimeError("R10 protocol hash drifted before publication")
    try:
        protocol_text = protocol_raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RuntimeError("R10 protocol snapshot is not UTF-8") from error
    if _json_hash(_first_json_object_text(protocol_text, label="R10")) != _json_hash(
        FROZEN_R6_REGISTRY
    ):
        raise RuntimeError("R10 protocol registry drifted before publication")


def _phase_authorization_prepublication_recheck(summary: Mapping[str, Any]) -> None:
    """Recheck only the pre-claim file bindings; root absence is deliberately excluded."""

    evidence = summary.get("phase_authorization")
    if not isinstance(evidence, Mapping):
        return
    contract = FROZEN_R6_REGISTRY["phase_authorization_contract"]
    certificate_type = evidence.get("certificate_type")
    if not isinstance(certificate_type, str):
        raise RuntimeError("R10 phase authorization receipt lacks certificate type")
    try:
        specification, _child_specification = _phase_authorization_specification(
            contract, certificate_type
        )
    except RuntimeError as error:
        raise RuntimeError(
            "R10 phase authorization receipt has no frozen certificate route"
        ) from error
    certificate_path = WORKSPACE / str(evidence["certificate_path"])
    audit_path = WORKSPACE / str(specification["prerequisite_audit_path"])
    summary_path = WORKSPACE / str(specification["prerequisite_summary_path"])
    _, certificate, certificate_hash = _authorization_snapshot(certificate_path)
    _, audit, audit_hash = _authorization_snapshot(audit_path)
    _, _, prerequisite_summary_hash = _authorization_snapshot(summary_path)
    certificate_self_field = str(contract["certificate_self_hash_field"])
    audit_self_field = str(specification["prerequisite_audit_self_hash_field"])
    protocol_raw = _safe_workspace_read_bytes(R10_PROTOCOL_PATH)
    protocol_hash = hashlib.sha256(protocol_raw).hexdigest()
    try:
        protocol_text = protocol_raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RuntimeError("R10 protocol snapshot is not UTF-8") from error
    registry_hash = _json_hash(_first_json_object_text(protocol_text, label="R10"))
    checks = {
        "certificate_hash": certificate_hash == evidence["certificate_file_sha256"],
        "certificate_self_hash": certificate.get(certificate_self_field)
        == evidence["certificate_self_sha256"],
        "audit_hash": audit_hash == evidence["prerequisite_audit_file_sha256"],
        "audit_self_hash": audit.get(audit_self_field)
        == evidence["prerequisite_audit_self_sha256"],
        "prerequisite_summary_hash": prerequisite_summary_hash
        == evidence["prerequisite_summary_sha256"],
        "protocol_hash": protocol_hash == evidence["protocol_sha256"],
        "registry_hash": registry_hash == evidence["registry_sha256"],
        "source_manifest_valid": _source_manifest_authority_valid(
            summary.get("source_manifest")
        ),
        "source_hash": summary.get("source_manifest", {}).get(
            "source_manifest_authority_sha256"
        )
        == evidence["source_manifest_authority_sha256"],
        "certificate_materializer_provenance": _materializer_provenance_matches_frozen_contract(
            certificate.get("materializer_provenance"),
            materializer_id=_issuing_materializer_id(specification),
        ),
        "audit_materializer_provenance": _validate_prerequisite_audit(
            audit,
            specification,
        ),
        "receipt_materializer_provenance": _authorization_value_exact(
            evidence.get("materializer_provenance"),
            certificate.get("materializer_provenance"),
        ),
    }
    if not all(checks.values()):
        raise RuntimeError("R10 phase authorization binding drifted before publication")


def _pre_root_failure_path(*, stage: str, process_uuid: str) -> Path:
    contract = FROZEN_R6_REGISTRY["atomic_failure_contract"]
    if (
        contract["pre_output_root_failure_parent"]
        != IMPLEMENTED_PRE_ROOT_FAILURE_PARENT
    ):
        raise RuntimeError("R10 pre-root failure parent does not match implementation")
    lexical_parent = WORKSPACE / IMPLEMENTED_PRE_ROOT_FAILURE_PARENT
    parent_snapshot = _workspace_path_snapshot(lexical_parent, require_exists=False)
    if not parent_snapshot["target_exists"]:
        _safe_workspace_mkdir_new(lexical_parent)
    parent_snapshot = _workspace_path_snapshot(
        lexical_parent, require_exists=True, require_directory=True
    )
    parent = parent_snapshot["resolved_path"]
    expected_parent = (WORKSPACE / "artifacts" / "calibration").resolve()
    if parent.parent != expected_parent:
        raise RuntimeError("R10 pre-root failure parent escapes calibration root")
    _revalidate_workspace_path_snapshot(parent_snapshot)
    return parent / f"{stage}.{process_uuid}.failure.json"


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    transaction_start = _utc_now()
    transaction_uuid = str(uuid.uuid4())
    stage = "argument_resolution"
    args: argparse.Namespace | None = None
    entry_evidence: Mapping[str, Any] | None = None
    preflight_environment: Mapping[str, Any] | None = None
    preflight_source: Mapping[str, Any] | None = None
    preflight_config: Mapping[str, Any] | None = None
    preflight_gate: Mapping[str, Any] | None = None
    summary: Mapping[str, Any] | None = None
    output_root_created = False
    summary_path: Path | None = None
    try:
        args = build_parser().parse_args(raw_argv)
        args._raw_run_dir = args.run_dir
        args.run_dir = args.run_dir.resolve()
        args._raw_argv = list(raw_argv)

        stage = "output_root_validation"
        args._entry_evidence = _entry_evidence(args, raw_argv)
        entry_evidence = args._entry_evidence
        if args._entry_evidence["output_root_existed_at_entry"]:
            raise FileExistsError(
                f"R10 output root already exists; refusing overwrite: {args.run_dir}"
            )
        if not args._entry_evidence["output_root_contract_passed"]:
            raise ValueError(
                "R10 output-root contract failed: "
                + json.dumps(
                    args._entry_evidence["output_root_contract"], sort_keys=True
                )
            )

        # Gate 0 is evaluated before creating the output root.  The same frozen
        # evidence is passed into ``run`` so directory creation cannot make the
        # preflight evidence tautologically true.
        stage = "authority_capture"
        torch.use_deterministic_algorithms(True)
        torch.set_deterministic_debug_mode("error")
        preflight_environment = _runtime_environment()
        preflight_source = _source_manifest()
        preflight_config = _registered_config(
            seeds=tuple(int(seed) for seed in args.seeds),
            actual_steps=1 if args.smoke else int(args.steps),
            smoke=bool(args.smoke),
            dry_run=bool(args.dry_run),
        )
        mutable_preflight_gate = _resolution_gate(
            preflight_config,
            preflight_source,
            runtime_environment=preflight_environment,
            entry_evidence=args._entry_evidence,
        )
        preflight_source_after = _source_manifest()
        mutable_preflight_gate["checks"]["source_manifest_stable_across_resolution"] = (
            preflight_source_after == preflight_source
        )
        mutable_preflight_gate["passed"] = all(
            mutable_preflight_gate["checks"].values()
        )
        mutable_preflight_gate["status"] = (
            "PASS" if mutable_preflight_gate["passed"] else "FAIL_RESOLUTION_FREEZE"
        )
        preflight_gate = mutable_preflight_gate
        if not mutable_preflight_gate["passed"]:
            stop_payload = {
                "failure_schema_version": FROZEN_R6_REGISTRY["schema_versions"][
                    "failure"
                ],
                "protocol_version": PROTOCOL_VERSION,
                "evidence_class": EVIDENCE_CLASS,
                "stage": "authority_capture",
                "status": _stop_status("resolution_freeze"),
                "process_uuid": transaction_uuid,
                "pid": os.getpid(),
                "utc_start": transaction_start,
                "utc_end": _utc_now(),
                "raw_argv": raw_argv,
                "entry_evidence": entry_evidence,
                "preflight_resolution_gate": preflight_gate,
                "formal_test_used": False,
                "formal_claim_allowed": False,
                "formal_ablation_claim_allowed": False,
                "full_method_claim_allowed": False,
                "formal_data_authorization": "HOLD",
            }
            try:
                _atomic_write_json_new(
                    _pre_root_failure_path(
                        stage="authority_capture", process_uuid=transaction_uuid
                    ),
                    stop_payload,
                )
            except Exception as publication_error:
                print(
                    "R10 secondary pre-root publication failure: "
                    f"{type(publication_error).__name__}: {publication_error}",
                    file=sys.stderr,
                )
            print(json.dumps(stop_payload, sort_keys=True), file=sys.stderr)
            return 4
        args._preflight_bundle = {
            "source_manifest": preflight_source,
            "config": preflight_config,
            "runtime_environment": preflight_environment,
            "resolution_gate": preflight_gate,
        }

        # R12 dry runs are authorized exclusively by the frozen resolution gate
        # above.  They must not enter the reproduction certificate/claim path.
        # Every other mode remains routed through the pre-root phase guard, which
        # only admits the registered independent-reproduction children.
        if _phase_authorization_mode(args) == "dry_run":
            args._phase_authorization = None
        else:
            stage = "phase_authorization"
            args._transaction_uuid = transaction_uuid
            args._phase_authorization = _phase_authorize(
                args,
                process_uuid=transaction_uuid,
                source_manifest=preflight_source,
            )

        stage = "output_root_creation"
        _safe_workspace_mkdir_new(args.run_dir)
        output_root_created = True

        stage = "gate_execution"
        summary = run(args)
        strict_validation = _strict_summary_validation(summary)
        if not strict_validation["passed"]:
            raise RuntimeError(
                "R10 strict summary validation failed: "
                + json.dumps(strict_validation["errors"], sort_keys=True)
            )
        final_source = _source_manifest()
        if final_source != preflight_source:
            raise RuntimeError(
                "R10 source/import manifest drifted during gate execution"
            )
        _phase_authorization_prepublication_recheck(summary)

        stage = "summary_postserialization_validation"
        summary_bytes = _serialize_json_bytes(summary)
        serialized_summary = json.loads(summary_bytes)
        serialized_strict_validation = _strict_summary_validation(serialized_summary)
        if not serialized_strict_validation["passed"]:
            raise RuntimeError(
                "R10 postserialized summary validation failed: "
                + json.dumps(
                    serialized_strict_validation["errors"],
                    sort_keys=True,
                    allow_nan=False,
                )
            )

        _final_publication_authority_recheck(preflight_source)

        stage = "summary_write"
        summary_path = args.run_dir / "summary.json"
        _atomic_write_bytes_new(summary_path, summary_bytes)
    except Exception as error:  # fail closed and preserve original traceback
        try:
            original_traceback = traceback.format_exc()
        except Exception as traceback_error:
            original_traceback = (
                f"traceback capture failed with {type(traceback_error).__name__}; "
                f"original exception type={type(error).__name__}"
            )
        if stage in {"argument_resolution", "output_root_validation"}:
            source_manifest = None
            source_error = "not attempted before authority_capture"
        else:
            try:
                source_manifest = _source_manifest()
                source_error = None
            except Exception as manifest_error:
                source_manifest = None
                source_error = f"{type(manifest_error).__name__}: {manifest_error}"
        run_dir = (
            args.run_dir if args is not None and hasattr(args, "run_dir") else None
        )
        try:
            runner_sha256 = _file_hash(Path(__file__).resolve())
            runner_hash_capture_error = None
        except Exception as capture_error:
            runner_sha256 = None
            runner_hash_capture_error = (
                f"{type(capture_error).__name__}: {capture_error}"
            )
        failure_gate_trace = (
            copy.deepcopy(getattr(args, "_failure_gate_trace", None))
            if args is not None
            else None
        )
        failure_accessor = (
            getattr(args, "_failure_accessor", None) if args is not None else None
        )
        failure_access_ledger = (
            copy.deepcopy(failure_accessor.ledger)
            if isinstance(failure_accessor, _R6SplitAccessor)
            else None
        )
        failure = {
            "failure_schema_version": FROZEN_R6_REGISTRY["schema_versions"]["failure"],
            "summary_schema_version": SUMMARY_SCHEMA_VERSION,
            "resolver_schema_version": RESOLVER_SCHEMA_VERSION,
            "protocol_version": PROTOCOL_VERSION,
            "evidence_class": EVIDENCE_CLASS,
            "stage": stage,
            "status": (
                IMPLEMENTED_STATUS_VOCABULARY["phase_authorization_failure"]
                if stage == "phase_authorization"
                else IMPLEMENTED_STATUS_VOCABULARY["technical_failure"]
            ),
            "attempt": run_dir.name if isinstance(run_dir, Path) else None,
            "process_uuid": transaction_uuid,
            "utc_start": transaction_start,
            "utc_end": _utc_now(),
            "command": [
                str(Path(sys.executable).resolve()),
                str(Path(__file__).resolve()),
                *raw_argv,
            ],
            "raw_argv": raw_argv,
            "normalized_argv_semantic_fields": _normalized_argv(args)
            if args is not None
            else None,
            "runner_sha256": runner_sha256,
            "runner_hash_capture_error": runner_hash_capture_error,
            "cwd": str(Path.cwd().resolve()),
            "pid": os.getpid(),
            "parent_pid": os.getppid(),
            "hostname": platform.node(),
            "entry_evidence": entry_evidence,
            "preflight_resolution_gate": preflight_gate,
            "runtime_environment": preflight_environment,
            "exception_type": type(error).__name__,
            "exception_message": _safe_exception_message(error),
            "traceback": original_traceback,
            "source_manifest_at_failure": source_manifest,
            "source_manifest_capture_error": source_error,
            "completed_gates_at_failure": summary.get("completed_gates")
            if isinstance(summary, Mapping)
            else failure_gate_trace,
            "data_access_ledger_at_failure": summary.get("data_access_ledger")
            if isinstance(summary, Mapping)
            else failure_access_ledger,
            "summary_written": bool(
                summary_path is not None and summary_path.is_file()
            ),
            "formal_test_used": False,
            "formal_claim_allowed": False,
            "formal_ablation_claim_allowed": False,
            "full_method_claim_allowed": False,
            "formal_data_authorization": "HOLD",
            "evidence_interpretation": "technical failure only; no method claim",
        }
        try:
            failure_path = (
                run_dir / "failure.json"
                if output_root_created and isinstance(run_dir, Path)
                else _pre_root_failure_path(stage=stage, process_uuid=transaction_uuid)
            )
            _atomic_write_json_new(failure_path, failure)
        except Exception as publication_error:
            print(
                "R10 secondary failure-artifact publication error: "
                f"{type(publication_error).__name__}: {publication_error}",
                file=sys.stderr,
            )
        try:
            print(json.dumps(failure, allow_nan=False, sort_keys=True), file=sys.stderr)
        except Exception as render_error:
            try:
                print(
                    f"{IMPLEMENTED_STATUS_VOCABULARY['technical_failure']} "
                    f"stage={stage} exception={type(error).__name__} "
                    f"render_error={type(render_error).__name__}",
                    file=sys.stderr,
                )
            except Exception:
                pass
        if output_root_created and isinstance(run_dir, Path):
            print(f"RESULT_DIR={run_dir}")
        return 4

    assert args is not None and summary is not None
    print(json.dumps(summary, sort_keys=True))
    print(f"RESULT_DIR={args.run_dir}")
    if summary["status"] in {
        IMPLEMENTED_STATUS_VOCABULARY["dry_run_success"],
        IMPLEMENTED_STATUS_VOCABULARY["smoke_success"],
        PENDING_STATUS,
    }:
        return 0
    if summary["status"] == _stop_status("structural_input"):
        return 2
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
