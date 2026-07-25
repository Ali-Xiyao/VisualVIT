from __future__ import annotations

# ruff: noqa: E402

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import traceback
from typing import Any, Mapping
import uuid


WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))

from scripts.run_query_anchor_r4 import (
    PENDING_STATUS,
    PROTOCOL_VERSION,
    R25_REGISTRY,
    REGISTERED_STEPS,
    TRAINABLE_SEEDS,
    _compare_independent_reproduction,
    _registered_reproduction_eligibility,
    _strict_summary_validation,
)
from scripts import run_query_anchor_r4 as r24_runner

# Historical test fixtures import this module-level name directly.
r11_runner = r24_runner
r23_runner = r24_runner


# R25 is the live authority; R24_REGISTRY alias preserves historical imports.
R24_REGISTRY = R25_REGISTRY
# Compatibility only for historical direct unit fixtures.  The launcher itself
# reads the live authority exclusively, and no prior phase can be launched through it.
R10_REGISTRY = R25_REGISTRY
R23_REGISTRY = R25_REGISTRY


STATUS_VOCABULARY = R24_REGISTRY["status_vocabulary"]
ATOMIC_FAILURE_CONTRACT = R24_REGISTRY["atomic_failure_contract"]
OUTPUT_ROOT_CONTRACT = R24_REGISTRY["output_root_contract"]
REPRODUCTION_SCHEMA_VERSION = str(R24_REGISTRY["schema_versions"]["reproduction"])
EVIDENCE_CLASS = str(R24_REGISTRY["evidence_class"])
FINAL_SUCCESS_STATUS = str(STATUS_VOCABULARY["final_success"])
LAUNCHER_FAILURE_STATUS = str(STATUS_VOCABULARY["launcher_failure"])
SCIENTIFIC_STOP_PREFIX = str(STATUS_VOCABULARY["scientific_stop_prefix"])
FORMAL_DATA_STATUS = str(STATUS_VOCABULARY["formal_data"])
FORMAL_TEST_STATUS = str(STATUS_VOCABULARY["formal_test"])
FROZEN_AUTHORITY_STATUS = str(STATUS_VOCABULARY["protocol_frozen"])
FAILURE_SCHEMA_VERSION = str(R24_REGISTRY["schema_versions"]["failure"])
REGISTERED_FAILURE_STAGES = tuple(ATOMIC_FAILURE_CONTRACT["required_failure_stages"])
FAILURE_ARTIFACT_NAME = str(ATOMIC_FAILURE_CONTRACT["failure_artifact_name"])
PRE_OUTPUT_ROOT_FAILURE_PARENT = Path(
    str(ATOMIC_FAILURE_CONTRACT["pre_output_root_failure_parent"])
)
PRE_OUTPUT_ROOT_FAILURE_FILENAME = str(
    ATOMIC_FAILURE_CONTRACT["pre_output_root_filename"]
)
PRE_OUTPUT_ROOT_FAILURE_GLOB = PRE_OUTPUT_ROOT_FAILURE_FILENAME.replace(
    "<stage>", "*"
).replace("<process_uuid>", "*")
OUTPUT_ROOT_PARENT = Path(str(OUTPUT_ROOT_CONTRACT["workspace_relative_parent"]))
REPRODUCTION_LEAVES = frozenset(
    {
        OUTPUT_ROOT_CONTRACT["phase_leaf_names"]["reproduction_local"],
        OUTPUT_ROOT_CONTRACT["phase_leaf_names"]["reproduction_slurm4161"],
    }
)


class RaisingArgumentParser(argparse.ArgumentParser):
    """Keep argument failures inside the launcher's fail-closed transaction."""

    def error(self, message: str) -> None:
        raise ValueError(message)


class LauncherStageError(RuntimeError):
    """An error carrying the exact registered stage and available raw evidence."""

    def __init__(
        self,
        stage: str,
        message: str,
        *,
        evidence: Mapping[str, Any] | None = None,
    ) -> None:
        if stage not in REGISTERED_FAILURE_STAGES:
            raise ValueError(f"unregistered launcher failure stage: {stage}")
        super().__init__(message)
        self.stage = stage
        self.evidence = dict(evidence or {})


def build_parser() -> argparse.ArgumentParser:
    parser = RaisingArgumentParser(
        description=(
            f"Run two fresh sequential {PROTOCOL_VERSION} processes and certify independent "
            "reproduction only after both payloads pass strict eligibility."
        )
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=REGISTERED_STEPS)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(TRAINABLE_SEEDS))
    parser.add_argument("--device", choices=("cpu",), default="cpu")
    return parser


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _raw_file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_raw_file_sha256(path: Path) -> tuple[str | None, str | None]:
    """Capture a raw hash without allowing diagnostics to replace the real error."""

    try:
        return _raw_file_sha256(path), None
    except Exception as error:
        return None, f"{type(error).__name__}: {error}"


def _canonical_json_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fsync_parent(path: Path) -> None:
    """Best-effort directory fsync; Windows commonly rejects directory handles."""

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path.parent, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _atomic_write_bytes_new(path: Path, payload: bytes) -> None:
    """Publish a same-directory, durable artifact without overwriting evidence."""

    if path.exists():
        raise FileExistsError(f"refusing to overwrite evidence artifact: {path}")
    temporary = path.with_name(f".tmp.{os.getpid()}.{uuid.uuid4().hex}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    published = False
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        # link() is an atomic create-if-absent operation on the same filesystem.
        # Unlike replace(), it cannot silently overwrite prior evidence on POSIX.
        os.link(temporary, path)
        published = True
        _fsync_parent(path)
    finally:
        try:
            temporary.unlink()
        except OSError:
            # Cleanup evidence is secondary.  Never replace the publish result
            # or its original exception with an unlink failure.
            pass
        if not published and path.exists():
            # The target belongs to another writer or a prior run; never remove it.
            pass


def _atomic_write_json_new(path: Path, payload: Mapping[str, Any]) -> None:
    serialized = (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    _atomic_write_bytes_new(path, serialized)


def _relative_posix(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _is_symlink_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def _safe_workspace_path(path: Path, *, stage: str) -> Path:
    """Resolve a path only after rejecting escapes and reparse-point ancestors."""

    workspace = Path(os.path.abspath(os.fspath(WORKSPACE.expanduser())))
    candidate = Path(os.path.abspath(os.fspath(path.expanduser())))
    try:
        relative = candidate.relative_to(workspace)
    except ValueError as error:
        raise LauncherStageError(
            stage,
            "path is lexically outside the workspace",
            evidence={"path": str(candidate), "workspace": str(workspace)},
        ) from error

    current = workspace
    paths_to_check = [workspace]
    for component in relative.parts:
        current = current / component
        paths_to_check.append(current)
    for ancestor in paths_to_check:
        if os.path.lexists(ancestor) and _is_symlink_or_reparse(ancestor):
            raise LauncherStageError(
                stage,
                "workspace path traverses a symlink, junction, or reparse point",
                evidence={
                    "path": str(candidate),
                    "unsafe_ancestor": str(ancestor),
                },
            )

    resolved_workspace = workspace.resolve(strict=False)
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(resolved_workspace)
    except ValueError as error:
        raise LauncherStageError(
            stage,
            "resolved path is outside the workspace",
            evidence={
                "path": str(candidate),
                "resolved_path": str(resolved),
                "workspace": str(resolved_workspace),
            },
        ) from error
    return resolved


def _validate_output_root(path: Path) -> Path:
    requested = path.expanduser()
    resolved = _safe_workspace_path(requested, stage="output_root_validation")
    expected_parent = _safe_workspace_path(
        WORKSPACE / OUTPUT_ROOT_PARENT,
        stage="output_root_validation",
    )
    if resolved.parent != expected_parent:
        raise LauncherStageError(
            "output_root_validation",
            f"{PROTOCOL_VERSION} reproduction root must be a direct child of "
            f"{OUTPUT_ROOT_PARENT.as_posix()}",
            evidence={
                "requested_output_root": str(requested),
                "resolved_output_root": str(resolved),
                "expected_parent": str(expected_parent),
            },
        )
    if resolved.name not in REPRODUCTION_LEAVES:
        raise LauncherStageError(
            "output_root_validation",
            f"{PROTOCOL_VERSION} reproduction root leaf is not registered",
            evidence={
                "resolved_output_root": str(resolved),
                "registered_leaf_names": sorted(REPRODUCTION_LEAVES),
            },
        )
    if resolved.exists() or requested.is_symlink():
        raise LauncherStageError(
            "output_root_validation",
            f"{PROTOCOL_VERSION} reproduction root must not exist at CLI entry",
            evidence={
                "resolved_output_root": str(resolved),
                "exists_at_entry": resolved.exists(),
                "requested_path_is_symlink": requested.is_symlink(),
            },
        )
    return resolved


def _pre_root_failure_path(*, stage: str, process_uuid: str) -> Path:
    parent = _safe_workspace_path(
        WORKSPACE / PRE_OUTPUT_ROOT_FAILURE_PARENT,
        stage=stage,
    )
    parent.mkdir(parents=True, exist_ok=True)
    parent = _safe_workspace_path(parent, stage=stage)
    filename = PRE_OUTPUT_ROOT_FAILURE_FILENAME.replace("<stage>", stage).replace(
        "<process_uuid>", process_uuid
    )
    path = parent / filename
    return _safe_workspace_path(path, stage=stage)


def _capture_authority() -> dict[str, Any]:
    freeze = R24_REGISTRY.get("freeze_requirements")
    if not isinstance(freeze, Mapping):
        raise LauncherStageError(
            "authority_capture",
            f"{PROTOCOL_VERSION} freeze requirements are missing",
        )
    if (
        R24_REGISTRY.get("authority_state") != FROZEN_AUTHORITY_STATUS
        or freeze.get("implementation_hashes_frozen") is not True
    ):
        raise LauncherStageError(
            "authority_capture",
            f"{PROTOCOL_VERSION} reproduction is forbidden until the protocol is final-frozen",
            evidence={
                "authority_state": R24_REGISTRY.get("authority_state"),
                "implementation_hashes_frozen": freeze.get(
                    "implementation_hashes_frozen"
                ),
                "dry_run_authorized": freeze.get("dry_run_authorized"),
            },
        )
    return {
        "protocol_version": PROTOCOL_VERSION,
        "authority_state": FROZEN_AUTHORITY_STATUS,
        "reproduction_schema_version": REPRODUCTION_SCHEMA_VERSION,
        "launcher_source_sha256": _raw_file_sha256(Path(__file__).resolve()),
    }


def _clean_runner_source_manifest_authority_sha256() -> str:
    """Recompute the child runner's context-invariant source authority."""

    probe = (
        "import json; "
        "from scripts import run_query_anchor_r4 as runner; "
        "print(json.dumps(runner._source_manifest(), allow_nan=False, "
        "ensure_ascii=True, separators=(',', ':'), sort_keys=True))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise LauncherStageError(
            "authority_capture",
            "R24 clean source-manifest probe failed",
            evidence={
                "probe_returncode": completed.returncode,
                "probe_stdout_sha256": hashlib.sha256(
                    completed.stdout.encode("utf-8")
                ).hexdigest(),
                "probe_stderr_sha256": hashlib.sha256(
                    completed.stderr.encode("utf-8")
                ).hexdigest(),
            },
        )
    try:
        manifest = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise LauncherStageError(
            "authority_capture",
            "R24 clean source-manifest probe output is not JSON",
        ) from error
    if (
        not isinstance(manifest, Mapping)
        or not r24_runner._source_manifest_authority_valid(manifest)
        or completed.stdout
        != json.dumps(
            manifest,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ):
        raise LauncherStageError(
            "authority_capture",
            "R24 clean source-manifest probe output is not exact canonical evidence",
        )
    return str(manifest["source_manifest_authority_sha256"])


def _issue_and_validate_reproduction_authority(
    args: argparse.Namespace,
) -> dict[str, dict[str, Any]]:
    """Issue and reopen the two immutable R24 child certificates pre-root."""

    contract = R24_REGISTRY["phase_authorization_contract"]
    specification = contract["reproduction_authorization"]
    expected_parent = (
        WORKSPACE / specification["target_output_parent_relative"]
    ).resolve()
    if args.run_dir != expected_parent or args.run_dir.exists():
        raise LauncherStageError(
            "authority_capture",
            "R24 reproduction authority requires the exact absent registered parent",
            evidence={
                "requested_run_dir": str(args.run_dir),
                "expected_parent": str(expected_parent),
                "exists": args.run_dir.exists(),
            },
        )
    transaction = specification.get("launcher_owned_issuer_transaction_contract")
    expected_precheck_order = [
        "target_output_parent_absent",
        "r24_authority_namespace_absent",
        "r24_registered_audit_absent",
        "r24_process_a_certificate_absent",
        "r24_process_b_certificate_absent",
    ]
    if not isinstance(transaction, Mapping) or transaction != {
        "transaction_owner": "scripts/run_query_anchor_r4_reproduction.py",
        "issuer_invocation_count_exact": 1,
        "synchronous": True,
        "retry_allowed": False,
        "preissued_r24_audit_allowed": False,
        "preissued_r24_child_certificates_allowed": False,
        "required_precheck_order": expected_precheck_order,
        "issuer_invocation_after_all_prechecks": True,
        "issuer_success_and_two_certificate_reopen_before_parent_creation": True,
        "partial_issuance_or_nonzero_exit_is_terminal_no_retry": True,
        "r20_authority_namespace_is_forensic_only_and_never_read_as_r24_authority": True,
        "r21_authority_namespace_is_forensic_only_and_never_read_as_r24_authority": True,
        "r22_authority_namespace_is_forensic_only_and_never_read_as_r24_authority": True,
        "r23_authority_namespace_is_forensic_only_and_never_read_as_r24_authority": True,
    }:
        raise LauncherStageError(
            "authority_capture",
            "R24 launcher-owned issuer transaction contract is not exact",
        )
    audit_contract = contract["registered_postrun_audit_contract"]
    child_certificates = specification["child_certificates"]
    prechecks = [
        ("target_output_parent_absent", expected_parent),
        (
            "r24_authority_namespace_absent",
            _safe_workspace_path(
                WORKSPACE / str(contract["authorization_root_relative"]),
                stage="authority_capture",
            ),
        ),
        (
            "r24_registered_audit_absent",
            _safe_workspace_path(
                WORKSPACE / str(audit_contract["relative_path"]),
                stage="authority_capture",
            ),
        ),
        (
            "r24_process_a_certificate_absent",
            _safe_workspace_path(
                WORKSPACE / str(child_certificates["process_a"]["relative_path"]),
                stage="authority_capture",
            ),
        ),
        (
            "r24_process_b_certificate_absent",
            _safe_workspace_path(
                WORKSPACE / str(child_certificates["process_b"]["relative_path"]),
                stage="authority_capture",
            ),
        ),
    ]
    if [name for name, _path in prechecks] != expected_precheck_order:
        raise LauncherStageError(
            "authority_capture",
            "R24 issuer precheck order differs from frozen authority",
        )
    for name, path in prechecks:
        if os.path.lexists(path):
            raise LauncherStageError(
                "authority_capture",
                "R24 issuer requires a fresh absent authority transaction",
                evidence={"failed_precheck": name, "path": str(path)},
            )

    invocation = specification["issuer_invocation"]
    if invocation != {
        "relative_path": ".tmp/audit_r24_registered.py",
        "working_directory_relative": ".",
        "argv_tail": [],
        "called_synchronously_by": "scripts/run_query_anchor_r4_reproduction.py",
        "before_parent_creation": True,
        "before_any_child_claim_or_model_construction_or_split_access": True,
        "launcher_must_validate_returncode_zero_and_reopen_both_certificates": True,
        "launcher_owned_issuer_transaction": True,
        "issuer_invoked_exactly_once": True,
        "issuer_retry_forbidden": True,
        "preissued_r24_audit_or_child_certificates_forbidden": True,
        "launcher_absent_parent_and_authority_namespace_precheck_required": True,
        "after_absent_parent_and_authority_namespace_precheck": True,
    }:
        raise LauncherStageError(
            "authority_capture",
            "R24 issuer invocation differs from frozen authority",
        )
    issuer = _safe_workspace_path(
        WORKSPACE / str(invocation["relative_path"]),
        stage="authority_capture",
    )
    if not issuer.is_file():
        raise LauncherStageError(
            "authority_capture",
            "R24 registry-fixed issuer is not a regular file",
            evidence={"issuer": str(issuer)},
        )
    command = [sys.executable, str(issuer)]
    completed = subprocess.run(
        command,
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise LauncherStageError(
            "authority_capture",
            "R24 registered authority issuer failed",
            evidence={
                "issuer_command": command,
                "issuer_returncode": completed.returncode,
                "issuer_stdout_sha256": hashlib.sha256(
                    completed.stdout.encode("utf-8")
                ).hexdigest(),
                "issuer_stderr_sha256": hashlib.sha256(
                    completed.stderr.encode("utf-8")
                ).hexdigest(),
            },
        )

    source_manifest_authority_sha256 = _clean_runner_source_manifest_authority_sha256()
    return _validate_issued_reproduction_authority(
        args,
        source_manifest_authority_sha256=source_manifest_authority_sha256,
    )


def _validate_issued_reproduction_authority(
    args: argparse.Namespace,
    *,
    source_manifest_authority_sha256: str,
) -> dict[str, dict[str, Any]]:
    """Reopen issuer outputs and validate them before any child-side write.

    The issuer-owning wrapper calls this exactly once after a zero exit.  Keeping
    the reopen logic separate also makes the post-issuance boundary testable
    without ever invoking the one-shot issuer.
    """

    contract = R24_REGISTRY["phase_authorization_contract"]
    specification = contract["reproduction_authorization"]
    expected_parent = (
        WORKSPACE / specification["target_output_parent_relative"]
    ).resolve()
    if args.run_dir != expected_parent or args.run_dir.exists():
        raise LauncherStageError(
            "authority_capture",
            "R24 issued authority requires the exact absent registered parent",
            evidence={
                "requested_run_dir": str(args.run_dir),
                "expected_parent": str(expected_parent),
                "exists": args.run_dir.exists(),
            },
        )
    if not r24_runner._sha256_like(source_manifest_authority_sha256):
        raise LauncherStageError(
            "authority_capture",
            "R24 runner source-manifest identity is invalid",
        )
    try:
        (
            _prerequisite_summary_raw,
            prerequisite_summary,
            prerequisite_summary_sha256,
        ) = r24_runner._authorization_snapshot(
            WORKSPACE / str(specification["prerequisite_summary_path"])
        )
        (
            _prerequisite_audit_raw,
            prerequisite_audit,
            prerequisite_audit_file_sha256,
        ) = r24_runner._authorization_snapshot(
            WORKSPACE / str(specification["prerequisite_audit_path"])
        )
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise LauncherStageError(
            "authority_capture",
            "R24 prerequisite evidence snapshot failed after issuer success",
            evidence={"exception_type": type(error).__name__},
        ) from error
    prerequisite_audit_self_sha256 = prerequisite_audit.get(
        specification["prerequisite_audit_self_hash_field"]
    )
    if (
        prerequisite_summary_sha256 != specification["prerequisite_summary_sha256"]
        or prerequisite_summary.get("status")
        != specification["prerequisite_summary_status"]
        or not r24_runner._validate_prerequisite_audit(
            prerequisite_audit, specification
        )
    ):
        raise LauncherStageError(
            "authority_capture",
            "R24 prerequisite summary or freshly issued audit is not exact",
        )

    certificates: dict[str, dict[str, Any]] = {}
    required_keys = specification["child_certificate_required_exact_top_level_keys"]
    required_checks = specification["child_certificate_required_exact_check_keys"]
    for leaf in specification["target_child_leaf_names"]:
        child = specification["child_certificates"][leaf]
        path = WORKSPACE / child["relative_path"]
        try:
            raw, certificate, raw_sha256 = r24_runner._authorization_snapshot(path)
        except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
            raise LauncherStageError(
                "authority_capture",
                "R24 child certificate snapshot failed",
                evidence={
                    "target_child_leaf": leaf,
                    "exception_type": type(error).__name__,
                },
            ) from error
        expected = {
            "schema_version": child["schema_version"],
            "certificate_type": child["certificate_type"],
            "protocol_id": PROTOCOL_VERSION,
            "protocol_sha256": r24_runner.R24_PROTOCOL_SHA256,
            "registry_sha256": r24_runner._json_hash(r24_runner.FROZEN_R6_REGISTRY),
            "source_manifest_authority_sha256": source_manifest_authority_sha256,
            "target_phase": specification["target_phase"],
            "target_output_parent_relative": specification[
                "target_output_parent_relative"
            ],
            "target_child_leaf": leaf,
            "target_output_root_relative": child["target_output_root_relative"],
            "target_seeds": list(TRAINABLE_SEEDS),
            "target_steps": REGISTERED_STEPS,
            "target_device": args.device,
            "prerequisite_summary_path": specification["prerequisite_summary_path"],
            "prerequisite_summary_sha256": prerequisite_summary_sha256,
            "prerequisite_audit_path": specification["prerequisite_audit_path"],
            "prerequisite_audit_file_sha256": prerequisite_audit_file_sha256,
            "prerequisite_audit_self_sha256": prerequisite_audit_self_sha256,
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
        checks = certificate.get("checks")
        self_field = contract["certificate_self_hash_field"]
        if (
            raw != r24_runner._authorization_canonical_bytes(certificate)
            or set(certificate) != set(required_keys)
            or any(
                not r24_runner._authorization_value_exact(certificate.get(key), value)
                for key, value in expected.items()
            )
            or not r24_runner._materializer_provenance_matches_frozen_contract(
                certificate.get("materializer_provenance"),
                materializer_id=r24_runner._issuing_materializer_id(specification),
            )
            or not r24_runner.is_uuid4(certificate.get("certificate_id"))
            or not r24_runner._sha256_like(certificate.get("phase_nonce"))
            or not r24_runner.is_utc_z_timestamp(certificate.get("issued_utc"))
            or certificate.get(self_field)
            != r24_runner._authorization_self_hash(certificate, self_field)
            or not isinstance(checks, Mapping)
            or set(checks) != set(required_checks)
            or not all(value is True for value in checks.values())
        ):
            raise LauncherStageError(
                "authority_capture",
                "R24 child certificate is not an exact valid authority",
                evidence={"target_child_leaf": leaf, "certificate_sha256": raw_sha256},
            )
        certificates[leaf] = {
            "certificate_id": certificate["certificate_id"],
            "phase_nonce": certificate["phase_nonce"],
            "raw_sha256": raw_sha256,
            "path": child["relative_path"],
        }
    if (
        len({item["certificate_id"] for item in certificates.values()}) != 2
        or len({item["phase_nonce"] for item in certificates.values()}) != 2
    ):
        raise LauncherStageError(
            "authority_capture",
            "R24 child certificate pair is not independently one-shot",
            evidence={"certificate_leaves": sorted(certificates)},
        )
    claims_parent = _safe_workspace_path(
        WORKSPACE / str(contract["claims_subdirectory_relative"]),
        stage="authority_capture",
    )
    if os.path.lexists(claims_parent):
        raise LauncherStageError(
            "authority_capture",
            "R24 fresh issuer transaction unexpectedly precreated the claims namespace",
            evidence={"claims_parent": str(claims_parent)},
        )
    return certificates


def _child_command(args: argparse.Namespace, run_dir: Path) -> list[str]:
    return [
        sys.executable,
        str((WORKSPACE / "scripts" / "run_query_anchor_r4.py").resolve()),
        "--run-dir",
        str(run_dir),
        "--steps",
        str(args.steps),
        "--seeds",
        *(str(seed) for seed in args.seeds),
        "--device",
        args.device,
    ]


def _stage_error(
    stage: str,
    error: BaseException,
    evidence: Mapping[str, Any],
) -> LauncherStageError:
    return LauncherStageError(
        stage,
        str(error),
        evidence={**evidence, "underlying_exception_type": type(error).__name__},
    )


def _run_child(
    args: argparse.Namespace, name: str
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any], Path, str, int]:
    child_dir = args.run_dir / name
    environment = os.environ.copy()
    environment.update(
        {
            "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
            "MKL_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONIOENCODING": "utf-8",
            "TZ": "UTC",
        }
    )
    command = _child_command(args, child_dir)
    evidence: dict[str, Any] = {
        "child_name": name,
        "child_command": command,
        "child_run_dir": str(child_dir.resolve()),
    }
    pre_root_parent = WORKSPACE / PRE_OUTPUT_ROOT_FAILURE_PARENT
    pre_root_before = (
        {path.resolve() for path in pre_root_parent.glob(PRE_OUTPUT_ROOT_FAILURE_GLOB)}
        if pre_root_parent.is_dir()
        else set()
    )
    try:
        process = subprocess.Popen(
            command,
            cwd=WORKSPACE,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except Exception as error:
        raise _stage_error("child_launch", error, evidence) from error
    evidence["child_pid"] = process.pid
    try:
        stdout, stderr = process.communicate()
    except Exception as error:
        try:
            process.terminate()
            process.wait(timeout=5)
            evidence["child_reaped_after_communicate_failure"] = True
        except Exception:
            try:
                process.kill()
                process.wait(timeout=5)
                evidence["child_reaped_after_communicate_failure"] = True
            except Exception as reap_error:
                evidence["child_reaped_after_communicate_failure"] = False
                evidence["child_reap_error"] = (
                    f"{type(reap_error).__name__}: {reap_error}"
                )
        raise _stage_error("child_communicate", error, evidence) from error
    completed = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    evidence["child_returncode"] = process.returncode
    pre_root_after = (
        {path.resolve() for path in pre_root_parent.glob(PRE_OUTPUT_ROOT_FAILURE_GLOB)}
        if pre_root_parent.is_dir()
        else set()
    )
    matched_pre_root: list[Path] = []
    for candidate in sorted(pre_root_after - pre_root_before):
        try:
            payload = json.loads(candidate.read_bytes())
        except Exception:
            continue
        if isinstance(payload, Mapping) and payload.get("pid") == process.pid:
            matched_pre_root.append(candidate)
    evidence["child_pre_root_failures"] = [
        {
            "path": candidate.relative_to(WORKSPACE).as_posix(),
            "raw_sha256": _raw_file_sha256(candidate),
        }
        for candidate in matched_pre_root
    ]

    stdout_path = args.run_dir / f"{name}.stdout.log"
    stderr_path = args.run_dir / f"{name}.stderr.log"
    try:
        _atomic_write_bytes_new(stdout_path, stdout.encode("utf-8"))
    except Exception as error:
        raise _stage_error("stdout_write", error, evidence) from error
    evidence.update(
        {
            "child_stdout_path": _relative_posix(stdout_path, args.run_dir),
            "child_stdout_raw_sha256": _raw_file_sha256(stdout_path),
        }
    )
    try:
        _atomic_write_bytes_new(stderr_path, stderr.encode("utf-8"))
    except Exception as error:
        raise _stage_error("stderr_write", error, evidence) from error
    evidence.update(
        {
            "child_stderr_path": _relative_posix(stderr_path, args.run_dir),
            "child_stderr_raw_sha256": _raw_file_sha256(stderr_path),
        }
    )

    summary_path = child_dir / "summary.json"
    child_failure_path = child_dir / FAILURE_ARTIFACT_NAME
    if matched_pre_root:
        raise LauncherStageError(
            "child_summary_read",
            "child published pre-root failure evidence",
            evidence=evidence,
        )
    if child_failure_path.is_file():
        child_failure_sha256, child_failure_hash_error = _safe_raw_file_sha256(
            child_failure_path
        )
        child_summary_sha256, child_summary_hash_error = _safe_raw_file_sha256(
            summary_path
        )
        raise LauncherStageError(
            "child_summary_read",
            "child published technical failure evidence",
            evidence={
                **evidence,
                "child_failure_path": _relative_posix(child_failure_path, args.run_dir),
                "child_failure_raw_sha256": child_failure_sha256,
                "child_failure_hash_capture_error": child_failure_hash_error,
                "child_summary_path": (
                    _relative_posix(summary_path, args.run_dir)
                    if summary_path.is_file()
                    else None
                ),
                "child_summary_raw_sha256": child_summary_sha256,
                "child_summary_hash_capture_error": child_summary_hash_error,
            },
        )
    try:
        raw_summary = summary_path.read_bytes()
    except Exception as error:
        summary_sha256, summary_hash_error = _safe_raw_file_sha256(summary_path)
        raise _stage_error(
            "child_summary_read",
            error,
            {
                **evidence,
                "child_summary_path": _relative_posix(summary_path, args.run_dir),
                "child_summary_raw_sha256": summary_sha256,
                "child_summary_hash_capture_error": summary_hash_error,
            },
        ) from error
    summary_raw_sha256 = hashlib.sha256(raw_summary).hexdigest()
    try:
        summary = json.loads(raw_summary)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise _stage_error(
            "child_summary_parse",
            error,
            {
                **evidence,
                "child_summary_path": _relative_posix(summary_path, args.run_dir),
                "child_summary_raw_sha256": summary_raw_sha256,
            },
        ) from error
    if not isinstance(summary, dict):
        raise LauncherStageError(
            "child_summary_parse",
            "child summary root must be an object",
            evidence={
                **evidence,
                "child_summary_path": _relative_posix(summary_path, args.run_dir),
                "child_summary_raw_sha256": summary_raw_sha256,
                "child_summary_root_type": type(summary).__name__,
            },
        )
    return completed, summary, summary_path, summary_raw_sha256, process.pid


def _child_artifact_evidence(
    args: argparse.Namespace,
    name: str,
    process: subprocess.CompletedProcess[str],
    summary: Mapping[str, Any],
    summary_path: Path,
    summary_raw_sha256: str,
    pid: int,
) -> dict[str, Any]:
    child_dir = args.run_dir / name
    stdout_path = args.run_dir / f"{name}.stdout.log"
    stderr_path = args.run_dir / f"{name}.stderr.log"
    failure_path = child_dir / FAILURE_ARTIFACT_NAME
    return {
        "role": "replica_a" if name == "process_a" else "replica_b",
        "child_directory": child_dir.relative_to(args.run_dir).as_posix(),
        "command": list(process.args),
        "launcher_observed_pid": int(pid),
        "returncode": int(process.returncode),
        "reported_status": summary.get("status"),
        "summary_path": _relative_posix(summary_path, args.run_dir),
        "summary_raw_sha256": summary_raw_sha256,
        "failure_path": (
            _relative_posix(failure_path, args.run_dir)
            if failure_path.is_file()
            else None
        ),
        "failure_raw_sha256": _raw_file_sha256(failure_path),
        "stdout_path": _relative_posix(stdout_path, args.run_dir),
        "stdout_raw_sha256": _raw_file_sha256(stdout_path),
        "stderr_path": _relative_posix(stderr_path, args.run_dir),
        "stderr_raw_sha256": _raw_file_sha256(stderr_path),
    }


def _scientific_stop_certificate(
    *,
    role: str,
    child: Mapping[str, Any],
    eligibility: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "reproduction_schema_version": REPRODUCTION_SCHEMA_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "status": _scientific_stop_status(f"{role.upper()}_GATES_0_TO_7"),
        "evidence_class": EVIDENCE_CLASS,
        "formal_test_status": FORMAL_TEST_STATUS,
        "formal_data_authorization": FORMAL_DATA_STATUS,
        "formal_claim_allowed": False,
        "formal_ablation_claim_allowed": False,
        "full_method_claim_allowed": False,
        "children": [dict(child)],
        "stopped_child_status": child.get("reported_status"),
        "stopped_child_eligibility": dict(eligibility or {}),
        "replica_b_launched": role == "replica_b",
    }


def _scientific_stop_status(suffix: str) -> str:
    return f"{SCIENTIFIC_STOP_PREFIX}{suffix}"


def _validate_child_before_next(
    *,
    role: str,
    process: subprocess.CompletedProcess[str],
    summary: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    status = summary.get("status")
    if isinstance(status, str) and status.startswith(SCIENTIFIC_STOP_PREFIX):
        try:
            strict_validation = _strict_summary_validation(summary)
        except Exception as error:
            raise _stage_error("child_eligibility", error, evidence) from error
        if strict_validation.get("passed") is not True:
            raise LauncherStageError(
                "child_eligibility",
                "scientific-stop child failed strict stopped-summary validation",
                evidence={
                    **evidence,
                    "strict_stopped_summary_validation": strict_validation,
                },
            )
        stopped_at = summary.get("stopped_at_gate")
        expected_status = (
            _scientific_stop_status(str(stopped_at).upper())
            if isinstance(stopped_at, str)
            else None
        )
        expected_returncode = 2 if stopped_at == "structural_input" else 3
        if status != expected_status or process.returncode != expected_returncode:
            raise LauncherStageError(
                "child_eligibility",
                "scientific-stop child has inconsistent gate, status, or return code",
                evidence={
                    **evidence,
                    "stopped_at_gate": stopped_at,
                    "expected_status": expected_status,
                    "expected_returncode": expected_returncode,
                    "strict_stopped_summary_validation": strict_validation,
                },
            )
        return _scientific_stop_certificate(role=role, child=evidence), None
    if process.returncode != 0 or status != PENDING_STATUS:
        raise LauncherStageError(
            "child_eligibility",
            "child neither produced an exact scientific stop nor an eligible pending result",
            evidence=dict(evidence),
        )
    try:
        eligibility = _registered_reproduction_eligibility(summary)
    except Exception as error:
        raise _stage_error("child_eligibility", error, evidence) from error
    if eligibility.get("passed") is not True:
        raise LauncherStageError(
            "child_eligibility",
            "child pending payload failed strict recursive eligibility",
            evidence={**evidence, "child_eligibility": eligibility},
        )
    return None, eligibility


def _validate_comparison_gate(gate: Mapping[str, Any]) -> bool:
    registered_expected_checks = R24_REGISTRY["reproduction_contract"].get(
        "canonical_comparison_expected_check_keys"
    )
    if (
        not isinstance(registered_expected_checks, list)
        or any(type(key) is not str for key in registered_expected_checks)
        or len(registered_expected_checks) != len(set(registered_expected_checks))
    ):
        raise LauncherStageError(
            "canonical_compare",
            "registered canonical comparison check set is malformed",
        )
    expected_checks = set(registered_expected_checks)
    expected_keys = {
        "status",
        "passed",
        "checks",
        "primary_canonical_sha256",
        "replica_canonical_sha256",
        "mismatch_count",
        "mismatch_paths",
        "primary_process_returncode",
        "replica_process_returncode",
        "primary_launcher_pid",
        "replica_launcher_pid",
        "primary_eligibility",
        "replica_eligibility",
        "comparison_excludes_only",
    }
    if set(gate) != expected_keys:
        raise LauncherStageError(
            "canonical_compare",
            "canonical comparison gate has a non-exact key set",
            evidence={
                "missing_gate_keys": sorted(expected_keys - set(gate)),
                "unknown_gate_keys": sorted(set(gate) - expected_keys),
            },
        )
    checks = gate.get("checks")
    if not isinstance(checks, Mapping) or set(checks) != expected_checks:
        raise LauncherStageError(
            "canonical_compare",
            "canonical comparison checks have a non-exact key set",
            evidence={
                "observed_check_keys": sorted(checks)
                if isinstance(checks, Mapping)
                else None
            },
        )
    if not all(type(value) is bool for value in checks.values()):
        raise LauncherStageError(
            "canonical_compare",
            "canonical comparison checks must be literal booleans",
        )
    mismatch_paths = gate.get("mismatch_paths")
    mismatch_count = gate.get("mismatch_count")
    primary_sha = gate.get("primary_canonical_sha256")
    replica_sha = gate.get("replica_canonical_sha256")
    sha_valid = all(
        isinstance(value, str)
        and len(value) == 64
        and value == value.lower()
        and all(character in "0123456789abcdef" for character in value)
        for value in (primary_sha, replica_sha)
    )
    expected_exclusions = list(
        R24_REGISTRY["reproduction_contract"]["volatile_exclusion_paths"]
    )
    recomputed_pass = all(checks.values())
    consistent = (
        type(gate.get("passed")) is bool
        and gate.get("passed") is recomputed_pass
        and gate.get("status") == ("PASS" if recomputed_pass else "FAIL")
        and isinstance(mismatch_paths, list)
        and all(isinstance(path, str) for path in mismatch_paths)
        and type(mismatch_count) is int
        and mismatch_count >= 0
        and mismatch_count == len(mismatch_paths)
        and sha_valid
        and checks["canonical_sha256_exact"] is (primary_sha == replica_sha)
        and checks["canonical_payload_exact"] is (mismatch_count == 0)
        and gate.get("comparison_excludes_only") == expected_exclusions
    )
    if not consistent:
        raise LauncherStageError(
            "canonical_compare",
            "canonical comparison gate failed independent recomputation",
            evidence={
                "comparison_gate": dict(gate),
                "registered_exclusions": expected_exclusions,
                "recomputed_pass": recomputed_pass,
            },
        )
    return recomputed_pass


def run(args: argparse.Namespace) -> dict[str, Any]:
    children: list[dict[str, Any]] = []

    (
        primary_process,
        primary,
        primary_path,
        primary_raw_sha256,
        primary_pid,
    ) = _run_child(args, "process_a")
    primary_evidence = _child_artifact_evidence(
        args,
        "process_a",
        primary_process,
        primary,
        primary_path,
        primary_raw_sha256,
        primary_pid,
    )
    children.append(primary_evidence)
    stopped, primary_eligibility = _validate_child_before_next(
        role="replica_a",
        process=primary_process,
        summary=primary,
        evidence=primary_evidence,
    )
    if stopped is not None:
        return stopped

    (
        replica_process,
        replica,
        replica_path,
        replica_raw_sha256,
        replica_pid,
    ) = _run_child(args, "process_b")
    replica_evidence = _child_artifact_evidence(
        args,
        "process_b",
        replica_process,
        replica,
        replica_path,
        replica_raw_sha256,
        replica_pid,
    )
    children.append(replica_evidence)
    stopped, replica_eligibility = _validate_child_before_next(
        role="replica_b",
        process=replica_process,
        summary=replica,
        evidence=replica_evidence,
    )
    if stopped is not None:
        stopped["children"] = children
        return stopped

    try:
        gate = _compare_independent_reproduction(
            primary,
            replica,
            primary_returncode=primary_process.returncode,
            replica_returncode=replica_process.returncode,
            primary_expected_pid=primary_pid,
            replica_expected_pid=replica_pid,
        )
    except Exception as error:
        raise _stage_error(
            "canonical_compare",
            error,
            {
                "replica_a_summary_raw_sha256": primary_evidence["summary_raw_sha256"],
                "replica_b_summary_raw_sha256": replica_evidence["summary_raw_sha256"],
            },
        ) from error
    passed = _validate_comparison_gate(gate)
    gate.update(
        {
            "replica_a_summary_raw_sha256": primary_evidence["summary_raw_sha256"],
            "replica_b_summary_raw_sha256": replica_evidence["summary_raw_sha256"],
            "launcher_source_sha256": _raw_file_sha256(Path(__file__).resolve()),
        }
    )
    certificate = {
        "reproduction_schema_version": REPRODUCTION_SCHEMA_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "status": (
            FINAL_SUCCESS_STATUS
            if passed
            else _scientific_stop_status("INDEPENDENT_REPRODUCTION")
        ),
        "evidence_class": EVIDENCE_CLASS,
        "formal_test_status": FORMAL_TEST_STATUS,
        "formal_data_authorization": FORMAL_DATA_STATUS,
        "formal_claim_allowed": False,
        "formal_ablation_claim_allowed": False,
        "full_method_claim_allowed": False,
        "fresh_process_count": 2,
        "sequential_order": ["replica_a", "replica_b"],
        "children": children,
        "replica_a_eligibility": primary_eligibility,
        "replica_b_eligibility": replica_eligibility,
        "independent_reproduction_gate": gate,
    }
    certificate["certificate_canonical_sha256"] = _canonical_json_sha256(certificate)
    return certificate


def _failure_payload(
    *,
    error: BaseException,
    stage: str,
    raw_argv: list[str],
    run_dir: Path | None,
    authority: Mapping[str, Any] | None,
    instance_uuid: str | None = None,
) -> dict[str, Any]:
    attached = error.evidence if isinstance(error, LauncherStageError) else {}
    original = error.__cause__ if error.__cause__ is not None else error
    environment = {
        key: os.environ.get(key)
        for key in (
            "CUBLAS_WORKSPACE_CONFIG",
            "LC_ALL",
            "MKL_NUM_THREADS",
            "OMP_NUM_THREADS",
            "PYTHONHASHSEED",
            "TZ",
        )
    }
    launcher_source_sha256, launcher_hash_error = _safe_raw_file_sha256(
        Path(__file__).resolve()
    )
    try:
        output_root_exists = run_dir.exists() if run_dir is not None else False
    except Exception:
        output_root_exists = False
    return {
        "failure_schema_version": FAILURE_SCHEMA_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "status": LAUNCHER_FAILURE_STATUS,
        "stage": stage,
        "exception_type": type(original).__name__,
        "exception_message": str(original),
        "launcher_wrapper_exception_type": (
            type(error).__name__ if original is not error else None
        ),
        "traceback": "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        ),
        "timestamp_utc": _utc_now(),
        "command": [sys.executable, str(Path(__file__).resolve()), *raw_argv],
        "cwd": str(Path.cwd().resolve()),
        "launcher_pid": os.getpid(),
        "launcher_instance_uuid": instance_uuid or str(uuid.uuid4()),
        "output_root_absolute": str(run_dir) if run_dir is not None else None,
        "output_root_exists": output_root_exists,
        "authority_capture": dict(authority or {}),
        "environment": environment,
        "attached_evidence": attached,
        "launcher_source_sha256": launcher_source_sha256,
        "launcher_source_hash_capture_error": launcher_hash_error,
        "formal_test_status": FORMAL_TEST_STATUS,
        "formal_data_authorization": FORMAL_DATA_STATUS,
        "formal_claim_allowed": False,
        "formal_ablation_claim_allowed": False,
        "full_method_claim_allowed": False,
    }


def _fallback_failure_payload(
    *,
    error: BaseException,
    stage: str,
    raw_argv: list[str],
    run_dir: Path | None,
    payload_error: BaseException,
    instance_uuid: str,
) -> dict[str, Any]:
    """Minimal JSON-safe failure record used only if diagnostics themselves fail."""

    try:
        original = error.__cause__ if error.__cause__ is not None else error
    except Exception:
        original = error
    try:
        original_message = str(original)
    except Exception:
        original_message = "<exception stringification failed>"
    try:
        original_traceback = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
    except Exception:
        original_traceback = "<traceback formatting failed>"
    try:
        diagnostic_error = f"{type(payload_error).__name__}: {payload_error}"
    except Exception:
        diagnostic_error = type(payload_error).__name__
    return {
        "failure_schema_version": FAILURE_SCHEMA_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "status": LAUNCHER_FAILURE_STATUS,
        "stage": stage,
        "launcher_instance_uuid": instance_uuid,
        "exception_type": type(original).__name__,
        "exception_message": original_message,
        "traceback": original_traceback,
        "diagnostic_capture_error": diagnostic_error,
        "timestamp_utc": _utc_now(),
        "command": [sys.executable, str(Path(__file__).resolve()), *raw_argv],
        "output_root_absolute": str(run_dir) if run_dir is not None else None,
        "formal_test_status": FORMAL_TEST_STATUS,
        "formal_data_authorization": FORMAL_DATA_STATUS,
        "formal_claim_allowed": False,
        "formal_ablation_claim_allowed": False,
        "full_method_claim_allowed": False,
    }


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    transaction_uuid = str(uuid.uuid4())
    stage = "argument_resolution"
    run_dir: Path | None = None
    output_root_created = False
    authority: dict[str, Any] | None = None
    try:
        args = build_parser().parse_args(raw_argv)
        if args.steps != REGISTERED_STEPS or tuple(args.seeds) != TRAINABLE_SEEDS:
            raise LauncherStageError(
                "argument_resolution",
                f"{PROTOCOL_VERSION} reproduction requires exact registered steps and ordered seeds",
                evidence={"steps": args.steps, "seeds": list(args.seeds)},
            )

        stage = "authority_capture"
        authority = _capture_authority()

        stage = "output_root_validation"
        run_dir = _validate_output_root(args.run_dir)
        args.run_dir = run_dir

        stage = "authority_capture"
        issued_children = _issue_and_validate_reproduction_authority(args)

        stage = "output_root_creation"
        try:
            r24_runner._safe_workspace_mkdir_new(run_dir)
        except Exception as error:
            raise _stage_error(
                "output_root_creation",
                error,
                {"resolved_output_root": str(run_dir)},
            ) from error
        output_root_created = True

        stage = "gate_execution"
        args._issued_reproduction_children = issued_children
        certificate = run(args)

        stage = "certificate_write"
        certificate_path = run_dir / "reproduction_certificate.json"
        try:
            _atomic_write_json_new(certificate_path, certificate)
        except Exception as error:
            raise _stage_error(
                "certificate_write",
                error,
                {
                    "certificate_path": str(certificate_path),
                    "certificate_canonical_sha256": _canonical_json_sha256(certificate),
                },
            ) from error
        print(json.dumps(certificate, allow_nan=False, sort_keys=True))
        print(f"CERTIFICATE={certificate_path}")
        return 0 if certificate["status"] == FINAL_SUCCESS_STATUS else 3
    except BaseException as error:
        if isinstance(error, KeyboardInterrupt):
            raise
        failure_stage = error.stage if isinstance(error, LauncherStageError) else stage
        payload_error: str | None = None
        try:
            failure = _failure_payload(
                error=error,
                stage=failure_stage,
                raw_argv=raw_argv,
                run_dir=run_dir,
                authority=authority,
                instance_uuid=transaction_uuid,
            )
        except Exception as diagnostic_error:
            payload_error = f"{type(diagnostic_error).__name__}: {diagnostic_error}"
            failure = _fallback_failure_payload(
                error=error,
                stage=failure_stage,
                raw_argv=raw_argv,
                run_dir=run_dir,
                payload_error=diagnostic_error,
                instance_uuid=transaction_uuid,
            )
        publication_error: str | None = None
        failure_path: Path | None = None
        try:
            failure_path = (
                run_dir / FAILURE_ARTIFACT_NAME
                if output_root_created and run_dir is not None
                else _pre_root_failure_path(
                    stage=failure_stage, process_uuid=transaction_uuid
                )
            )
            try:
                _atomic_write_json_new(failure_path, failure)
            except Exception as write_error:
                publication_error = f"{type(write_error).__name__}: {write_error}"
        except Exception as path_error:
            publication_error = f"{type(path_error).__name__}: {path_error}"
        try:
            print(json.dumps(failure, allow_nan=False, sort_keys=True), file=sys.stderr)
        except Exception as render_error:
            if publication_error is None:
                publication_error = f"{type(render_error).__name__}: {render_error}"
            print(
                f"{LAUNCHER_FAILURE_STATUS} stage={failure_stage} "
                f"exception={type(error).__name__}",
                file=sys.stderr,
            )
        if payload_error is not None:
            print(f"FAILURE_PAYLOAD_CAPTURE_ERROR={payload_error}", file=sys.stderr)
        if publication_error is not None:
            print(f"FAILURE_PUBLICATION_ERROR={publication_error}", file=sys.stderr)
        if failure_path is not None and publication_error is None:
            print(f"FAILURE={failure_path}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
