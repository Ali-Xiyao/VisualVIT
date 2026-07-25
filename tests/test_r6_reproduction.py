from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))

from scripts import run_query_anchor_r4_reproduction as reproduction  # noqa: E402


def _registry_status(name: str) -> str:
    return str(reproduction.R10_REGISTRY["status_vocabulary"][name])


def _scientific_stop(suffix: str) -> str:
    return f"{_registry_status('scientific_stop_prefix')}{suffix}"


def _failure_artifact_name() -> str:
    return str(
        reproduction.R10_REGISTRY["atomic_failure_contract"]["failure_artifact_name"]
    )


def _pre_root_failure_parent(workspace: Path) -> Path:
    relative = reproduction.R10_REGISTRY["atomic_failure_contract"][
        "pre_output_root_failure_parent"
    ]
    return workspace / str(relative)


def _pre_root_failure_glob() -> str:
    template = str(
        reproduction.R10_REGISTRY["atomic_failure_contract"]["pre_output_root_filename"]
    )
    return template.replace("<stage>", "*").replace("<process_uuid>", "*")


def _output_root_parent(workspace: Path) -> Path:
    relative = reproduction.R10_REGISTRY["output_root_contract"][
        "workspace_relative_parent"
    ]
    return workspace / str(relative)


def _args(run_dir: Path):
    return reproduction.build_parser().parse_args(["--run-dir", str(run_dir)])


def _write_fake_child_artifacts(
    args,
    name: str,
    *,
    status: str,
    returncode: int,
    pid: int,
):
    child_dir = args.run_dir / name
    child_dir.mkdir(parents=True)
    summary = {
        "status": status,
        "provenance": {
            "process_identity": {
                "pid": pid,
                "instance_uuid": (
                    "11111111-1111-4111-8111-111111111111"
                    if name == "process_a"
                    else "22222222-2222-4222-8222-222222222222"
                ),
            }
        },
    }
    summary_path = child_dir / "summary.json"
    raw_summary = json.dumps(summary).encode("utf-8")
    summary_path.write_bytes(raw_summary)
    (args.run_dir / f"{name}.stdout.log").write_text("stdout", encoding="utf-8")
    (args.run_dir / f"{name}.stderr.log").write_text("stderr", encoding="utf-8")
    process = subprocess.CompletedProcess(["runner", name], returncode, "", "")
    return process, summary, summary_path, hashlib.sha256(raw_summary).hexdigest(), pid


def _freeze_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = copy.deepcopy(reproduction.R24_REGISTRY)
    registry["authority_state"] = reproduction.FROZEN_AUTHORITY_STATUS
    registry["freeze_requirements"]["implementation_hashes_frozen"] = True
    registry["freeze_requirements"]["dry_run_authorized"] = True
    monkeypatch.setattr(reproduction, "R24_REGISTRY", registry)
    monkeypatch.setattr(
        reproduction,
        "_issue_and_validate_reproduction_authority",
        lambda _args: {
            "process_a": {"certificate_id": "a", "phase_nonce": "a"},
            "process_b": {"certificate_id": "b", "phase_nonce": "b"},
        },
    )


def _comparison_gate(*, passed: bool) -> dict:
    mismatch_paths = [] if passed else ["/transport_results/17/state_sha256"]
    primary_sha = "1" * 64
    replica_sha = primary_sha if passed else "2" * 64
    checks = {
        "primary_process_exit_zero": True,
        "replica_process_exit_zero": True,
        "canonical_payload_exact": passed,
        "canonical_sha256_exact": passed,
        "primary_registered_payload_eligible": True,
        "replica_registered_payload_eligible": True,
        "valid_process_uuids": True,
        "independent_process_uuids": True,
        "primary_pid_matches_launcher": True,
        "replica_pid_matches_launcher": True,
        "independent_process_pids": True,
    }
    return {
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "checks": checks,
        "primary_canonical_sha256": primary_sha,
        "replica_canonical_sha256": replica_sha,
        "mismatch_count": len(mismatch_paths),
        "mismatch_paths": mismatch_paths,
        "primary_process_returncode": 0,
        "replica_process_returncode": 0,
        "primary_launcher_pid": 101,
        "replica_launcher_pid": 202,
        "primary_eligibility": {"passed": True},
        "replica_eligibility": {"passed": True},
        "comparison_excludes_only": list(
            reproduction.R10_REGISTRY["reproduction_contract"][
                "volatile_exclusion_paths"
            ]
        ),
    }


def test_protocol_specific_launcher_contracts_are_registry_derived() -> None:
    registry = reproduction.R10_REGISTRY
    atomic = registry["atomic_failure_contract"]
    output = registry["output_root_contract"]

    assert reproduction.SCIENTIFIC_STOP_PREFIX == _registry_status(
        "scientific_stop_prefix"
    )
    assert reproduction.FAILURE_ARTIFACT_NAME == atomic["failure_artifact_name"]
    assert reproduction.PRE_OUTPUT_ROOT_FAILURE_PARENT == Path(
        atomic["pre_output_root_failure_parent"]
    )
    assert (
        reproduction.PRE_OUTPUT_ROOT_FAILURE_FILENAME
        == atomic["pre_output_root_filename"]
    )
    assert reproduction.OUTPUT_ROOT_PARENT == Path(output["workspace_relative_parent"])


def test_r24_launcher_owns_one_synchronous_issuer_call_before_parent_creation() -> None:
    source = Path(reproduction.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    main = functions["main"]
    issuer_transaction = functions["_issue_and_validate_reproduction_authority"]

    main_calls = sorted(
        (
            node.lineno,
            (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else None
            ),
        )
        for node in ast.walk(main)
        if isinstance(node, ast.Call)
    )
    validation_lines = [
        line for line, name in main_calls if name == "_validate_output_root"
    ]
    issuer_lines = [
        line
        for line, name in main_calls
        if name == "_issue_and_validate_reproduction_authority"
    ]
    parent_create_lines = [
        line for line, name in main_calls if name == "_safe_workspace_mkdir_new"
    ]
    issuer_subprocess_calls = [
        node
        for node in ast.walk(issuer_transaction)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
        and node.func.attr == "run"
    ]

    assert len(validation_lines) == 1
    assert len(issuer_lines) == 1
    assert len(parent_create_lines) == 1
    assert validation_lines[0] < issuer_lines[0] < parent_create_lines[0]
    assert len(issuer_subprocess_calls) == 1

    phase = reproduction.R24_REGISTRY["phase_authorization_contract"]
    specification = phase["reproduction_authorization"]
    transaction = specification["launcher_owned_issuer_transaction_contract"]
    assert specification["issuer_invocation"]["relative_path"] == (
        ".tmp/audit_r24_registered.py"
    )
    assert transaction["issuer_invocation_count_exact"] == 1
    assert transaction["synchronous"] is True
    assert transaction["retry_allowed"] is False
    assert transaction["preissued_r24_audit_allowed"] is False
    assert transaction["preissued_r24_child_certificates_allowed"] is False
    assert transaction["required_precheck_order"] == [
        "target_output_parent_absent",
        "r24_authority_namespace_absent",
        "r24_registered_audit_absent",
        "r24_process_a_certificate_absent",
        "r24_process_b_certificate_absent",
    ]
    assert phase["authorization_root_relative"].startswith(
        "artifacts/calibration/.r24_"
    )
    assert specification["target_output_parent_relative"].endswith(
        "capes_ci_qptm_r24_reproduction_local_20260724_v1"
    )


def test_r24_issuer_materializer_consumer_executes_canonical_key_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ReachedPostOwnershipValidation(RuntimeError):
        pass

    def tree_state(root: Path) -> tuple[object, ...]:
        if not root.exists():
            return ("absent",)
        if root.is_file():
            return ("file", hashlib.sha256(root.read_bytes()).hexdigest())
        entries: list[tuple[str, str, str | None]] = []
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
            relative = path.relative_to(root).as_posix()
            if path.is_file():
                entries.append(
                    ("file", relative, hashlib.sha256(path.read_bytes()).hexdigest())
                )
            elif path.is_dir():
                entries.append(("directory", relative, None))
            else:
                entries.append(("other", relative, None))
        return ("directory", *entries)

    auditor_path = WORKSPACE / ".tmp" / "audit_r24_registered.py"
    runner_path = WORKSPACE / "scripts" / "run_query_anchor_r4.py"
    live_phase = reproduction.R24_REGISTRY["phase_authorization_contract"]
    live_specification = live_phase["reproduction_authorization"]
    outside_guard_roots = (
        WORKSPACE / live_phase["authorization_root_relative"],
        WORKSPACE / live_specification["target_output_parent_relative"],
    )
    outside_before = tuple(tree_state(path) for path in outside_guard_roots)

    for mutation, expected in (
        (None, ReachedPostOwnershipValidation),
        (
            lambda specification: specification.__setitem__(
                "issuer_materializer_id",
                specification.pop("issuing_materializer_id"),
            ),
            KeyError,
        ),
        (
            lambda specification: specification.pop("issuing_materializer_id"),
            KeyError,
        ),
        (
            lambda specification: specification.__setitem__(
                "issuing_materializer_id", "forged_materializer"
            ),
            RuntimeError,
        ),
    ):
        workspace = WORKSPACE / ".tmp" / f"r24-issuer-isolated-{uuid.uuid4().hex}"
        workspace.mkdir()
        original_cwd = Path.cwd()
        original_argv = list(sys.argv)
        original_sys_path = list(sys.path)
        module_name = f"r24_issuer_consumer_{uuid.uuid4().hex}"
        try:
            registry = copy.deepcopy(reproduction.R24_REGISTRY)
            registry["authority_state"] = "FROZEN_BEFORE_R25_REPRODUCTION"
            specification = registry["phase_authorization_contract"][
                "reproduction_authorization"
            ]
            if mutation is not None:
                mutation(specification)

            isolated_auditor = workspace / ".tmp" / "audit_r24_registered.py"
            isolated_auditor.parent.mkdir()
            isolated_auditor.write_bytes(auditor_path.read_bytes())
            isolated_runner = workspace / "scripts" / "run_query_anchor_r4.py"
            isolated_runner.parent.mkdir()
            isolated_runner.write_bytes(runner_path.read_bytes())
            registry["freeze_record"] = {
                "runner_sha256": hashlib.sha256(
                    isolated_runner.read_bytes()
                ).hexdigest()
            }
            materializer = registry["phase_authorization_contract"][
                "external_materializers"
            ]["registered_reproduction_authorizer"]
            materializer["sha256"] = hashlib.sha256(
                isolated_auditor.read_bytes()
            ).hexdigest()

            r24_path = (
                workspace / "refine-logs" / "CALIBRATION_PROTOCOL_R24_2026-07-24.md"
            )
            r23_path = (
                workspace / "refine-logs" / "CALIBRATION_PROTOCOL_R23_2026-07-24.md"
            )
            r21_path = (
                workspace / "refine-logs" / "CALIBRATION_PROTOCOL_R21_2026-07-23.md"
            )
            r20_path = (
                workspace / "refine-logs" / "CALIBRATION_PROTOCOL_R20_2026-07-23.md"
            )
            r14_path = (
                workspace / "refine-logs" / "CALIBRATION_PROTOCOL_R14_2026-07-23.md"
            )
            r5_path = (
                workspace / "refine-logs" / "CALIBRATION_PROTOCOL_R5_2026-07-22.md"
            )
            r24_path.parent.mkdir()
            r24_path.write_text(
                "# isolated R24\n```json\n"
                + json.dumps(registry, sort_keys=True)
                + "\n```\n",
                encoding="utf-8",
            )
            r23_path.write_bytes(
                (
                    WORKSPACE / "refine-logs/CALIBRATION_PROTOCOL_R23_2026-07-24.md"
                ).read_bytes()
            )
            r21_path.write_bytes(
                (
                    WORKSPACE / "refine-logs/CALIBRATION_PROTOCOL_R21_2026-07-23.md"
                ).read_bytes()
            )
            r20_path.write_bytes(
                (
                    WORKSPACE / "refine-logs/CALIBRATION_PROTOCOL_R20_2026-07-23.md"
                ).read_bytes()
            )
            r14_path.write_bytes(
                (
                    WORKSPACE / "refine-logs/CALIBRATION_PROTOCOL_R14_2026-07-23.md"
                ).read_bytes()
            )
            r5_path.write_bytes(
                (
                    WORKSPACE / "refine-logs/CALIBRATION_PROTOCOL_R5_2026-07-22.md"
                ).read_bytes()
            )
            summary_path = (
                workspace / "artifacts/calibration/"
                "capes_ci_qptm_r14_registered_local_20260723_v1/summary.json"
            )
            summary_path.parent.mkdir(parents=True)
            summary_path.write_text("{}", encoding="utf-8")

            module_spec = importlib.util.spec_from_file_location(
                module_name, isolated_auditor
            )
            assert module_spec is not None and module_spec.loader is not None
            auditor = importlib.util.module_from_spec(module_spec)
            sys.modules[module_name] = auditor
            module_spec.loader.exec_module(auditor)

            audit_path = (
                workspace
                / registry["phase_authorization_contract"][
                    "registered_postrun_audit_contract"
                ]["relative_path"]
            )
            real_plain = auditor.plain

            def stop_after_ownership(path: Path, *, required: bool) -> Path:
                if not required and Path(path).absolute() == audit_path.absolute():
                    raise ReachedPostOwnershipValidation()
                return real_plain(path, required=required)

            write_attempts: list[str] = []

            def forbid_authority_write(*_args, **_kwargs) -> None:
                write_attempts.append("authority_write")
                raise AssertionError(
                    "issuer attempted an authority write before sentinel"
                )

            monkeypatch.setattr(auditor, "plain", stop_after_ownership)
            monkeypatch.setattr(
                auditor,
                "clean_live_source_manifest",
                lambda _runner_sha256: {
                    "source_manifest_authority_sha256": "isolated-test-sentinel"
                },
            )
            monkeypatch.setattr(auditor, "write_new", forbid_authority_write)
            monkeypatch.setattr(
                auditor, "native_ensure_directory", forbid_authority_write
            )

            os.chdir(workspace)
            sys.argv = [str(isolated_auditor)]
            with pytest.raises(expected):
                auditor.main()
            assert write_attempts == []
            assert tuple(tree_state(path) for path in outside_guard_roots) == (
                outside_before
            )
        finally:
            os.chdir(original_cwd)
            sys.argv = original_argv
            sys.path[:] = original_sys_path
            sys.modules.pop(module_name, None)
            sys.modules.pop("r24_hash_checked_runner", None)
            shutil.rmtree(workspace)

    assert tuple(tree_state(path) for path in outside_guard_roots) == outside_before


def test_r24_all_materializer_consumers_register_one_canonical_key() -> None:
    registry = reproduction.R24_REGISTRY
    phase = registry["phase_authorization_contract"]
    specification = phase["reproduction_authorization"]
    consistency = registry["materializer_id_consistency_contract"]

    assert phase["materializer_id_consistency_contract"] == consistency
    assert consistency["canonical_registry_key"] == "issuing_materializer_id"
    assert consistency["required_consumers"] == [
        "issuer_materializer",
        "launcher_reopen",
        "runner_preclaim",
        "runner_summary_receipt",
        "runner_prepublication",
    ]
    assert consistency["alias_keys_forbidden"] == ["issuer_materializer_id"]
    assert consistency["alias_fallback_forbidden"] is True
    assert specification["issuing_materializer_id"] == consistency["canonical_value"]
    assert "issuer_materializer_id" not in specification

    assert (
        reproduction.r24_runner._issuing_materializer_id(specification)
        == (consistency["canonical_value"])
    )


@pytest.mark.parametrize(
    "mutated_field",
    [
        "source_manifest_authority_sha256",
        "materializer_provenance",
        "prerequisite_summary_sha256",
        "prerequisite_audit_file_sha256",
        "prerequisite_audit_self_sha256",
    ],
)
def test_r24_launcher_rejects_self_consistent_wrong_certificate_hashes_pre_parent(
    monkeypatch: pytest.MonkeyPatch,
    mutated_field: str,
) -> None:
    workspace = WORKSPACE / ".tmp" / f"r24-launcher-test-{uuid.uuid4().hex}"
    workspace.mkdir(parents=False, exist_ok=False)
    issuer = workspace / ".tmp" / "audit_r24_registered.py"
    issuer.parent.mkdir()
    issuer.write_text("# fixed test issuer\n", encoding="utf-8")

    registry = copy.deepcopy(reproduction.R24_REGISTRY)
    registry["authority_state"] = reproduction.FROZEN_AUTHORITY_STATUS
    registry["freeze_requirements"]["implementation_hashes_frozen"] = True
    specification = registry["phase_authorization_contract"][
        "reproduction_authorization"
    ]
    run_dir = workspace / specification["target_output_parent_relative"]
    args = reproduction.build_parser().parse_args(["--run-dir", str(run_dir)])
    args.run_dir = run_dir.resolve()

    source_manifest_authority_sha256 = "c" * 64
    prerequisite_audit_file_sha256 = "d" * 64
    prerequisite_audit_self_sha256 = "e" * 64
    prerequisite_summary = {"status": specification["prerequisite_summary_status"]}
    prerequisite_audit = {"audit_sha256": prerequisite_audit_self_sha256}
    issuer_calls: list[list[str]] = []

    def fake_run(command, **_kwargs):
        issuer_calls.append(list(command))
        return subprocess.CompletedProcess(command, 0, "", "")

    def certificate_for(leaf: str) -> dict:
        child = specification["child_certificates"][leaf]
        certificate = {
            "schema_version": child["schema_version"],
            "certificate_type": child["certificate_type"],
            "certificate_id": (
                "11111111-1111-4111-8111-111111111111"
                if leaf == "process_a"
                else "22222222-2222-4222-8222-222222222222"
            ),
            "phase_nonce": ("a" if leaf == "process_a" else "b") * 64,
            "protocol_id": registry["protocol_id"],
            "protocol_sha256": reproduction.r24_runner.R25_PROTOCOL_SHA256,
            "registry_sha256": reproduction.r24_runner._json_hash(registry),
            "source_manifest_authority_sha256": source_manifest_authority_sha256,
            "materializer_provenance": {"fixed": True},
            "target_phase": specification["target_phase"],
            "target_output_parent_relative": specification[
                "target_output_parent_relative"
            ],
            "target_child_leaf": leaf,
            "target_output_root_relative": child["target_output_root_relative"],
            "target_seeds": list(reproduction.TRAINABLE_SEEDS),
            "target_steps": reproduction.REGISTERED_STEPS,
            "target_device": "cpu",
            "prerequisite_summary_path": specification["prerequisite_summary_path"],
            "prerequisite_summary_sha256": specification["prerequisite_summary_sha256"],
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
            "checks": {
                key: True
                for key in specification["child_certificate_required_exact_check_keys"]
            },
            "authorized": True,
            "authorization_status": specification["authorization_status"],
            "issued_utc": "2026-07-23T12:00:00Z",
        }
        certificate[mutated_field] = (
            {"fixed": False} if mutated_field == "materializer_provenance" else "0" * 64
        )
        self_field = registry["phase_authorization_contract"][
            "certificate_self_hash_field"
        ]
        certificate[self_field] = reproduction.r24_runner._authorization_self_hash(
            certificate, self_field
        )
        return certificate

    certificates = {
        leaf: certificate_for(leaf) for leaf in specification["target_child_leaf_names"]
    }

    def fake_snapshot(path: Path):
        relative = path.relative_to(workspace).as_posix()
        if relative == specification["prerequisite_summary_path"]:
            return (
                b"summary",
                prerequisite_summary,
                specification["prerequisite_summary_sha256"],
            )
        if relative == specification["prerequisite_audit_path"]:
            return (
                b"audit",
                prerequisite_audit,
                prerequisite_audit_file_sha256,
            )
        for leaf, child in specification["child_certificates"].items():
            if relative == child["relative_path"]:
                certificate = certificates[leaf]
                raw = reproduction.r24_runner._authorization_canonical_bytes(
                    certificate
                )
                return raw, certificate, hashlib.sha256(raw).hexdigest()
        raise AssertionError(relative)

    monkeypatch.setattr(reproduction, "WORKSPACE", workspace)
    monkeypatch.setattr(reproduction, "R24_REGISTRY", registry)
    monkeypatch.setattr(reproduction.r24_runner, "FROZEN_R6_REGISTRY", registry)
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        reproduction,
        "_clean_runner_source_manifest_authority_sha256",
        lambda: source_manifest_authority_sha256,
    )
    monkeypatch.setattr(
        reproduction.r24_runner,
        "_authorization_snapshot",
        fake_snapshot,
    )
    monkeypatch.setattr(
        reproduction.r24_runner,
        "_validate_prerequisite_audit",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        reproduction.r24_runner,
        "_materializer_provenance_matches_frozen_contract",
        lambda provenance, *, materializer_id: provenance == {"fixed": True},
    )

    with pytest.raises(
        reproduction.LauncherStageError,
        match="child certificate is not an exact valid authority",
    ):
        reproduction._issue_and_validate_reproduction_authority(args)

    assert issuer_calls == [[sys.executable, str(issuer.resolve())]]
    assert not run_dir.exists()


def test_scientific_stop_certificate_accepts_non_r6_registry_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(reproduction, "SCIENTIFIC_STOP_PREFIX", "STOP_NEXT_")
    child = {"reported_status": "STOP_NEXT_TRANSPORT_COMPETENCE"}

    certificate = reproduction._scientific_stop_certificate(
        role="replica_a", child=child
    )

    assert certificate["status"] == "STOP_NEXT_REPLICA_A_GATES_0_TO_7"
    assert certificate["stopped_child_status"] == child["reported_status"]


def test_two_fresh_children_run_sequentially_and_success_is_exact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_dir = tmp_path / "reproduction"
    run_dir.mkdir()
    args = _args(run_dir)
    calls: list[str] = []

    def fake_child(args, name):
        calls.append(name)
        return _write_fake_child_artifacts(
            args,
            name,
            status=reproduction.PENDING_STATUS,
            returncode=0,
            pid=101 if name == "process_a" else 202,
        )

    monkeypatch.setattr(reproduction, "_run_child", fake_child)
    monkeypatch.setattr(
        reproduction,
        "_registered_reproduction_eligibility",
        lambda summary: {"passed": True, "checks": {"strict": True}},
    )
    monkeypatch.setattr(
        reproduction,
        "_compare_independent_reproduction",
        lambda *args, **kwargs: _comparison_gate(passed=True),
    )

    certificate = reproduction.run(args)

    assert calls == ["process_a", "process_b"]
    assert certificate["status"] == reproduction.FINAL_SUCCESS_STATUS
    assert certificate["evidence_class"] == reproduction.EVIDENCE_CLASS
    assert certificate["fresh_process_count"] == 2
    assert certificate["sequential_order"] == ["replica_a", "replica_b"]
    assert [child["launcher_observed_pid"] for child in certificate["children"]] == [
        101,
        202,
    ]
    assert len(certificate["certificate_canonical_sha256"]) == 64


def test_replica_b_is_not_launched_after_exact_scientific_stop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_dir = tmp_path / "reproduction"
    run_dir.mkdir()
    args = _args(run_dir)
    calls: list[str] = []

    def fake_child(args, name):
        calls.append(name)
        process, summary, summary_path, summary_raw_sha256, pid = (
            _write_fake_child_artifacts(
                args,
                name,
                status=_scientific_stop("TRANSPORT_COMPETENCE"),
                returncode=3,
                pid=101,
            )
        )
        summary["stopped_at_gate"] = "transport_competence"
        return process, summary, summary_path, summary_raw_sha256, pid

    monkeypatch.setattr(reproduction, "_run_child", fake_child)
    monkeypatch.setattr(
        reproduction,
        "_strict_summary_validation",
        lambda summary: {"passed": True, "errors": []},
    )

    certificate = reproduction.run(args)

    assert calls == ["process_a"]
    assert certificate["status"] == _scientific_stop("REPLICA_A_GATES_0_TO_7")
    assert certificate["stopped_child_status"] == _scientific_stop(
        "TRANSPORT_COMPETENCE"
    )
    assert certificate["replica_b_launched"] is False


def test_malformed_stop_is_technical_failure_and_never_certified(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_dir = tmp_path / "reproduction"
    run_dir.mkdir()
    args = _args(run_dir)

    def fake_child(args, name):
        return _write_fake_child_artifacts(
            args,
            name,
            status=_scientific_stop("TRANSPORT_COMPETENCE"),
            returncode=3,
            pid=101,
        )

    monkeypatch.setattr(reproduction, "_run_child", fake_child)

    with pytest.raises(reproduction.LauncherStageError) as captured:
        reproduction.run(args)

    assert captured.value.stage == "child_eligibility"
    assert "strict stopped-summary validation" in str(captured.value)


def test_scientific_stop_requires_gate_specific_return_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_dir = tmp_path / "reproduction"
    run_dir.mkdir()
    args = _args(run_dir)

    def fake_child(args, name):
        process, summary, summary_path, summary_raw_sha256, pid = (
            _write_fake_child_artifacts(
                args,
                name,
                status=_scientific_stop("STRUCTURAL_INPUT"),
                returncode=3,
                pid=101,
            )
        )
        summary["stopped_at_gate"] = "structural_input"
        return process, summary, summary_path, summary_raw_sha256, pid

    monkeypatch.setattr(reproduction, "_run_child", fake_child)
    monkeypatch.setattr(
        reproduction,
        "_strict_summary_validation",
        lambda summary: {"passed": True, "errors": []},
    )

    with pytest.raises(reproduction.LauncherStageError) as captured:
        reproduction.run(args)

    assert captured.value.stage == "child_eligibility"
    assert captured.value.evidence["expected_returncode"] == 2
    assert captured.value.evidence["returncode"] == 3


def test_ineligible_pending_child_is_technical_failure_not_scientific_stop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(reproduction, "WORKSPACE", tmp_path)
    monkeypatch.setattr(reproduction.r24_runner, "WORKSPACE", tmp_path)
    _freeze_authority(monkeypatch)
    run_dir = (
        _output_root_parent(tmp_path) / sorted(reproduction.REPRODUCTION_LEAVES)[0]
    )
    run_dir.parent.mkdir(parents=True)

    def fake_child(args, name):
        return _write_fake_child_artifacts(
            args,
            name,
            status=reproduction.PENDING_STATUS,
            returncode=0,
            pid=101,
        )

    monkeypatch.setattr(reproduction, "_run_child", fake_child)
    monkeypatch.setattr(
        reproduction,
        "_registered_reproduction_eligibility",
        lambda summary: {
            "passed": False,
            "errors": [{"path": "/unknown", "expected": "absent"}],
        },
    )

    exit_code = reproduction.main(["--run-dir", str(run_dir)])

    assert exit_code == 4
    failure = json.loads(
        (run_dir / _failure_artifact_name()).read_text(encoding="utf-8")
    )
    assert failure["status"] == reproduction.LAUNCHER_FAILURE_STATUS
    assert failure["stage"] == "child_eligibility"
    assert not failure["status"].startswith(reproduction.SCIENTIFIC_STOP_PREFIX)
    assert failure["attached_evidence"]["child_eligibility"]["passed"] is False
    assert not (run_dir / "reproduction_certificate.json").exists()


def test_raw_child_failure_hash_is_preserved(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_dir = tmp_path / "reproduction"
    run_dir.mkdir()
    args = _args(run_dir)
    raw_failure = (
        json.dumps(
            {"status": _registry_status("technical_failure")}, separators=(",", ":")
        )
        + "\n"
    ).encode("utf-8")

    class FakeProcess:
        pid = 731
        returncode = 4

        def communicate(self):
            child_dir = run_dir / "process_a"
            child_dir.mkdir()
            (child_dir / _failure_artifact_name()).write_bytes(raw_failure)
            return "child-out", "child-err"

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    with pytest.raises(reproduction.LauncherStageError) as captured:
        reproduction._run_child(args, "process_a")

    assert captured.value.stage == "child_summary_read"
    assert captured.value.evidence["child_failure_path"] == (
        f"process_a/{_failure_artifact_name()}"
    )
    assert (
        captured.value.evidence["child_failure_raw_sha256"]
        == hashlib.sha256(raw_failure).hexdigest()
    )
    assert captured.value.evidence["child_returncode"] == 4


def test_child_evidence_uses_bytes_parsed_before_summary_path_replacement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_dir = tmp_path / "reproduction"
    run_dir.mkdir()
    args = _args(run_dir)
    original_raw = json.dumps({"status": reproduction.PENDING_STATUS}).encode("utf-8")
    replacement_raw = json.dumps({"status": "REPLACED_AFTER_READ"}).encode("utf-8")

    class FakeProcess:
        pid = 731
        returncode = 0

        def communicate(self):
            child_dir = run_dir / "process_a"
            child_dir.mkdir()
            (child_dir / "summary.json").write_bytes(original_raw)
            return "child-out", "child-err"

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    process, summary, summary_path, summary_raw_sha256, pid = reproduction._run_child(
        args, "process_a"
    )
    summary_path.write_bytes(replacement_raw)

    evidence = reproduction._child_artifact_evidence(
        args,
        "process_a",
        process,
        summary,
        summary_path,
        summary_raw_sha256,
        pid,
    )

    assert summary["status"] == reproduction.PENDING_STATUS
    assert evidence["summary_raw_sha256"] == hashlib.sha256(original_raw).hexdigest()
    assert evidence["summary_raw_sha256"] != hashlib.sha256(replacement_raw).hexdigest()


def test_canonical_mismatch_writes_stop_certificate_and_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(reproduction, "WORKSPACE", tmp_path)
    monkeypatch.setattr(reproduction.r24_runner, "WORKSPACE", tmp_path)
    _freeze_authority(monkeypatch)
    run_dir = (
        _output_root_parent(tmp_path) / sorted(reproduction.REPRODUCTION_LEAVES)[0]
    )
    run_dir.parent.mkdir(parents=True)

    def fake_child(args, name):
        return _write_fake_child_artifacts(
            args,
            name,
            status=reproduction.PENDING_STATUS,
            returncode=0,
            pid=101 if name == "process_a" else 202,
        )

    monkeypatch.setattr(reproduction, "_run_child", fake_child)
    monkeypatch.setattr(
        reproduction,
        "_registered_reproduction_eligibility",
        lambda summary: {"passed": True, "checks": {"strict": True}},
    )
    monkeypatch.setattr(
        reproduction,
        "_compare_independent_reproduction",
        lambda *args, **kwargs: _comparison_gate(passed=False),
    )

    exit_code = reproduction.main(["--run-dir", str(run_dir)])

    assert exit_code == 3
    certificate = json.loads(
        (run_dir / "reproduction_certificate.json").read_text(encoding="utf-8")
    )
    assert certificate["status"] == _scientific_stop("INDEPENDENT_REPRODUCTION")
    assert certificate["independent_reproduction_gate"]["passed"] is False
    assert not (run_dir / _failure_artifact_name()).exists()


def test_forged_comparator_pass_is_rejected_as_technical_failure() -> None:
    gate = _comparison_gate(passed=True)
    gate["comparison_excludes_only"] = ["/extra_unregistered_volatile_field"]

    with pytest.raises(reproduction.LauncherStageError) as captured:
        reproduction._validate_comparison_gate(gate)

    assert captured.value.stage == "canonical_compare"
    assert "independent recomputation" in str(captured.value)


def test_native_comparator_exact_check_set_is_accepted() -> None:
    gate = _comparison_gate(passed=True)

    assert reproduction._validate_comparison_gate(gate) is True
    assert set(gate["checks"]) == {
        "primary_process_exit_zero",
        "replica_process_exit_zero",
        "canonical_payload_exact",
        "canonical_sha256_exact",
        "primary_registered_payload_eligible",
        "replica_registered_payload_eligible",
        "valid_process_uuids",
        "independent_process_uuids",
        "primary_pid_matches_launcher",
        "replica_pid_matches_launcher",
        "independent_process_pids",
    }


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_native_comparator_check_set_mutations_fail_closed(mutation: str) -> None:
    gate = _comparison_gate(passed=True)
    if mutation == "missing":
        del gate["checks"]["independent_process_pids"]
    else:
        gate["checks"]["unregistered_check"] = True

    with pytest.raises(reproduction.LauncherStageError) as captured:
        reproduction._validate_comparison_gate(gate)

    assert captured.value.stage == "canonical_compare"
    assert "non-exact key set" in str(captured.value)


def test_native_comparator_nonindependent_pids_is_a_scientific_gate_failure() -> None:
    gate = _comparison_gate(passed=True)
    gate["checks"]["independent_process_pids"] = False
    gate["status"] = "FAIL"
    gate["passed"] = False

    assert reproduction._validate_comparison_gate(gate) is False


def test_r24_preserved_r23_summaries_are_exact_after_one_pointer_exclusion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = reproduction.r24_runner
    run_root = (
        WORKSPACE / "artifacts/calibration/"
        "capes_ci_qptm_r23_reproduction_local_20260724_v1"
    )
    primary = json.loads(
        (run_root / "process_a/summary.json").read_text(encoding="utf-8")
    )
    replica = json.loads(
        (run_root / "process_b/summary.json").read_text(encoding="utf-8")
    )
    certificate = json.loads(
        (run_root / "reproduction_certificate.json").read_text(encoding="utf-8")
    )
    pointer = (
        "/provenance/output_root_entry_evidence/output_root_contract/expected_leaf"
    )
    r24_paths = list(
        reproduction.R24_REGISTRY["reproduction_contract"]["volatile_exclusion_paths"]
    )
    r23_paths = [path for path in r24_paths if path != pointer]

    assert r24_paths.count(pointer) == 1
    assert certificate["independent_reproduction_gate"]["primary_eligibility"]["passed"]
    assert certificate["independent_reproduction_gate"]["replica_eligibility"]["passed"]
    assert (
        primary["provenance"]["output_root_entry_evidence"]["output_root_contract"][
            "expected_leaf"
        ]
        == "process_a"
    )
    assert (
        replica["provenance"]["output_root_entry_evidence"]["output_root_contract"][
            "expected_leaf"
        ]
        == "process_b"
    )

    with monkeypatch.context() as context:
        r23_registry = copy.deepcopy(runner.FROZEN_R6_REGISTRY)
        r23_registry["reproduction_contract"]["volatile_exclusion_paths"] = r23_paths
        context.setattr(runner, "FROZEN_R6_REGISTRY", r23_registry)
        context.setattr(
            runner,
            "_CANONICAL_REPRODUCTION_VOLATILE_EXCLUSION_PATHS",
            tuple(r23_paths),
        )
        primary_r23 = runner._canonical_reproduction_payload(primary)
        replica_r23 = runner._canonical_reproduction_payload(replica)
        assert runner._mismatch_paths(primary_r23, replica_r23) == [pointer]

    primary_r24 = runner._canonical_reproduction_payload(primary)
    replica_r24 = runner._canonical_reproduction_payload(replica)
    assert runner._mismatch_paths(primary_r24, replica_r24) == []
    assert runner._json_hash(primary_r24) == runner._json_hash(replica_r24)


@pytest.mark.parametrize("mutation", ["missing_expected_leaf", "extra", "duplicate"])
def test_r24_volatile_exclusion_contract_mutations_fail_closed(
    monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    runner = reproduction.r24_runner
    registry = copy.deepcopy(runner.FROZEN_R6_REGISTRY)
    paths = list(registry["reproduction_contract"]["volatile_exclusion_paths"])
    pointer = (
        "/provenance/output_root_entry_evidence/output_root_contract/expected_leaf"
    )
    if mutation == "missing_expected_leaf":
        paths.remove(pointer)
    elif mutation == "extra":
        paths.append("/provenance/unregistered_process_field")
    else:
        paths.append(pointer)
    registry["reproduction_contract"]["volatile_exclusion_paths"] = paths
    monkeypatch.setattr(runner, "FROZEN_R6_REGISTRY", registry)

    with pytest.raises(ValueError, match="volatile exclusion contract is not exact"):
        runner._canonical_reproduction_exclusion_paths()


def test_r24_expected_leaf_must_exist_before_canonical_exclusion() -> None:
    runner = reproduction.r24_runner
    summary_path = (
        WORKSPACE / "artifacts/calibration/"
        "capes_ci_qptm_r23_reproduction_local_20260724_v1/"
        "process_a/summary.json"
    )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    del summary["provenance"]["output_root_entry_evidence"]["output_root_contract"][
        "expected_leaf"
    ]

    with pytest.raises(ValueError, match="canonical reproduction missing"):
        runner._canonical_reproduction_payload(summary)


def test_wrapped_stage_failure_keeps_original_exception_primary() -> None:
    original = OSError("raw child launch error")
    try:
        raise reproduction._stage_error(
            "child_launch", original, {"child_pid": None}
        ) from original
    except reproduction.LauncherStageError as wrapped:
        payload = reproduction._failure_payload(
            error=wrapped,
            stage=wrapped.stage,
            raw_argv=["--run-dir", "unused"],
            run_dir=None,
            authority=None,
        )

    assert payload["exception_type"] == "OSError"
    assert payload["exception_message"] == "raw child launch error"
    assert payload["launcher_wrapper_exception_type"] == "LauncherStageError"
    assert payload["attached_evidence"]["underlying_exception_type"] == "OSError"


def test_atomic_publish_refuses_to_overwrite_prior_evidence(tmp_path: Path) -> None:
    path = tmp_path / _failure_artifact_name()
    path.write_text('{"original":true}\n', encoding="utf-8")

    with pytest.raises(FileExistsError):
        reproduction._atomic_write_json_new(path, {"replacement": True})

    assert json.loads(path.read_text(encoding="utf-8")) == {"original": True}


def _single_pre_root_failure(workspace: Path) -> dict:
    failures = list(_pre_root_failure_parent(workspace).glob(_pre_root_failure_glob()))
    assert len(failures) == 1
    return json.loads(failures[0].read_text(encoding="utf-8"))


def _create_directory_reparse(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
        return
    except OSError as symlink_error:
        if os.name != "nt":
            pytest.skip(f"symlink creation unavailable: {symlink_error}")
    junction = subprocess.run(
        ["cmd", "/d", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if junction.returncode != 0:
        pytest.skip(
            "directory reparse creation unavailable: "
            f"{junction.stderr or junction.stdout}"
        )


def test_argument_failure_publishes_atomic_pre_root_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(reproduction, "WORKSPACE", tmp_path)

    exit_code = reproduction.main([])

    assert exit_code == 4
    failure = _single_pre_root_failure(tmp_path)
    assert failure["stage"] == "argument_resolution"
    assert failure["status"] == reproduction.LAUNCHER_FAILURE_STATUS


def test_authority_failure_publishes_atomic_pre_root_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(reproduction, "WORKSPACE", tmp_path)
    run_dir = (
        _output_root_parent(tmp_path) / sorted(reproduction.REPRODUCTION_LEAVES)[0]
    )
    monkeypatch.setattr(
        reproduction,
        "_capture_authority",
        lambda: (_ for _ in ()).throw(RuntimeError("authority unavailable")),
    )

    exit_code = reproduction.main(["--run-dir", str(run_dir)])

    assert exit_code == 4
    failure = _single_pre_root_failure(tmp_path)
    assert failure["stage"] == "authority_capture"
    assert failure["exception_message"] == "authority unavailable"


def test_outside_output_root_is_rejected_and_published_pre_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(reproduction, "WORKSPACE", workspace)
    _freeze_authority(monkeypatch)
    outside = tmp_path / sorted(reproduction.REPRODUCTION_LEAVES)[0]

    exit_code = reproduction.main(["--run-dir", str(outside)])

    assert exit_code == 4
    failure = _single_pre_root_failure(workspace)
    assert failure["stage"] == "output_root_validation"
    assert failure["attached_evidence"]["workspace"] == str(workspace)
    assert not outside.exists()


def test_output_root_creation_failure_publishes_pre_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(reproduction, "WORKSPACE", tmp_path)
    _freeze_authority(monkeypatch)
    run_dir = (
        _output_root_parent(tmp_path) / sorted(reproduction.REPRODUCTION_LEAVES)[0]
    )
    run_dir.parent.mkdir(parents=True)
    monkeypatch.setattr(reproduction.r11_runner, "WORKSPACE", tmp_path)
    monkeypatch.setattr(
        reproduction.r11_runner,
        "_safe_workspace_mkdir_new",
        lambda _path: (_ for _ in ()).throw(OSError("mkdir denied")),
    )

    exit_code = reproduction.main(["--run-dir", str(run_dir)])

    assert exit_code == 4
    failure = _single_pre_root_failure(tmp_path)
    assert failure["stage"] == "output_root_creation"
    assert failure["exception_message"] == "mkdir denied"


def test_r11_native_parent_creation_failure_leaves_no_reproduction_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(reproduction, "WORKSPACE", workspace)
    monkeypatch.setattr(reproduction.r11_runner, "WORKSPACE", workspace)
    _freeze_authority(monkeypatch)
    run_dir = (
        _output_root_parent(workspace) / sorted(reproduction.REPRODUCTION_LEAVES)[0]
    )
    monkeypatch.setattr(
        reproduction.r11_runner,
        "_safe_workspace_mkdir_new",
        lambda _path: (_ for _ in ()).throw(OSError("native parent create failed")),
    )

    exit_code = reproduction.main(["--run-dir", str(run_dir)])

    assert exit_code == 4
    assert not run_dir.exists()
    failure = _single_pre_root_failure(workspace)
    assert failure["stage"] == "output_root_creation"
    assert failure["exception_message"] == "native parent create failed"


def test_r11_auditor_native_failure_publishes_no_authority_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    auditor_path = WORKSPACE / ".tmp" / "audit_r11_registered.py"
    spec = importlib.util.spec_from_file_location("r11_auditor_test", auditor_path)
    assert spec is not None and spec.loader is not None
    auditor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auditor)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    destination = workspace / "artifacts" / "calibration" / ".r11" / "audit.json"
    monkeypatch.setattr(auditor, "WORKSPACE", workspace)
    monkeypatch.setattr(auditor.r11_runner, "WORKSPACE", workspace)
    monkeypatch.setattr(
        auditor.r11_runner,
        "_safe_workspace_mkdir_new",
        lambda _path: (_ for _ in ()).throw(OSError("native authority create failed")),
    )

    with pytest.raises(OSError, match="native authority create failed"):
        auditor.write_new(destination, {"fixed": True})

    assert not destination.exists()
    assert not destination.parent.exists()


def test_r11_auditor_native_read_failure_publishes_no_authority_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    auditor_path = WORKSPACE / ".tmp" / "audit_r11_registered.py"
    spec = importlib.util.spec_from_file_location("r11_auditor_read_test", auditor_path)
    assert spec is not None and spec.loader is not None
    auditor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auditor)
    workspace = tmp_path / "workspace"
    protocol = workspace / "refine-logs" / "r11.md"
    protocol.parent.mkdir(parents=True)
    protocol.write_text("```json\n{}\n```", encoding="utf-8")
    monkeypatch.setattr(auditor, "WORKSPACE", workspace)
    monkeypatch.setattr(auditor, "R11_PROTOCOL_PATH", protocol)
    monkeypatch.setattr(auditor.r11_runner, "WORKSPACE", workspace)
    monkeypatch.setattr(
        auditor.r11_runner,
        "_native_read_existing_child",
        lambda *_args: (_ for _ in ()).throw(OSError("native authority read failed")),
    )

    with pytest.raises(OSError, match="native authority read failed"):
        auditor.main()

    assert not (workspace / "artifacts").exists()


def test_output_root_rejects_symlink_or_reparse_ancestor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    _create_directory_reparse(workspace / "artifacts", outside)
    monkeypatch.setattr(reproduction, "WORKSPACE", workspace)
    requested = (
        _output_root_parent(workspace) / sorted(reproduction.REPRODUCTION_LEAVES)[0]
    )

    with pytest.raises(reproduction.LauncherStageError) as captured:
        reproduction._validate_output_root(requested)

    assert captured.value.stage == "output_root_validation"
    assert "reparse point" in str(captured.value)


def test_pre_root_path_rejects_symlink_or_reparse_ancestor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    _create_directory_reparse(workspace / "artifacts", outside)
    monkeypatch.setattr(reproduction, "WORKSPACE", workspace)

    with pytest.raises(reproduction.LauncherStageError):
        reproduction._pre_root_failure_path(
            stage="argument_resolution",
            process_uuid="11111111-1111-4111-8111-111111111111",
        )


def test_payload_capture_failure_does_not_mask_original_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(reproduction, "WORKSPACE", tmp_path)
    monkeypatch.setattr(
        reproduction,
        "_failure_payload",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("diagnostics broke")),
    )

    exit_code = reproduction.main([])

    assert exit_code == 4
    failure = _single_pre_root_failure(tmp_path)
    assert failure["stage"] == "argument_resolution"
    assert failure["exception_type"] == "ValueError"
    assert "required" in failure["exception_message"]
    assert failure["diagnostic_capture_error"] == "RuntimeError: diagnostics broke"


def test_hash_capture_failure_does_not_replace_summary_read_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_dir = tmp_path / "reproduction"
    run_dir.mkdir()
    args = _args(run_dir)

    class FakeProcess:
        pid = 731
        returncode = 4

        def communicate(self):
            return "child-out", "child-err"

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    real_hash = reproduction._raw_file_sha256

    def fail_summary_hash(path: Path):
        if path.name == "summary.json":
            raise OSError("hash failed")
        return real_hash(path)

    monkeypatch.setattr(reproduction, "_raw_file_sha256", fail_summary_hash)

    with pytest.raises(reproduction.LauncherStageError) as captured:
        reproduction._run_child(args, "process_a")

    assert captured.value.stage == "child_summary_read"
    assert isinstance(captured.value.__cause__, FileNotFoundError)
    assert captured.value.evidence["child_summary_raw_sha256"] is None
    assert captured.value.evidence["child_summary_hash_capture_error"] == (
        "OSError: hash failed"
    )


def test_atomic_cleanup_error_never_replaces_publish_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    destination = tmp_path / "evidence.json"
    monkeypatch.setattr(
        reproduction.os,
        "link",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            FileExistsError("original publish collision")
        ),
    )
    real_unlink = Path.unlink

    def failing_cleanup(path: Path, *args, **kwargs):
        if path.name.startswith(".tmp."):
            raise PermissionError("secondary cleanup failure")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", failing_cleanup)

    with pytest.raises(FileExistsError, match="original publish collision"):
        reproduction._atomic_write_bytes_new(destination, b"evidence")


def test_child_pre_root_failure_is_bound_by_pid_and_hashed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = tmp_path / "workspace"
    run_dir = _output_root_parent(workspace) / "reproduction"
    run_dir.mkdir(parents=True)
    monkeypatch.setattr(reproduction, "WORKSPACE", workspace)
    args = _args(run_dir)

    class FakeProcess:
        pid = 731
        returncode = 4

        def communicate(self):
            failure_parent = _pre_root_failure_parent(workspace)
            failure_parent.mkdir()
            filename = (
                str(
                    reproduction.R10_REGISTRY["atomic_failure_contract"][
                        "pre_output_root_filename"
                    ]
                )
                .replace("<stage>", "authority_capture")
                .replace("<process_uuid>", "fake")
            )
            (failure_parent / filename).write_text(
                json.dumps(
                    {"pid": self.pid, "status": _scientific_stop("RESOLUTION_FREEZE")}
                ),
                encoding="utf-8",
            )
            return "child-out", "child-err"

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    with pytest.raises(reproduction.LauncherStageError) as captured:
        reproduction._run_child(args, "process_a")

    assert captured.value.stage == "child_summary_read"
    failures = captured.value.evidence["child_pre_root_failures"]
    assert len(failures) == 1
    assert failures[0]["path"].endswith(
        str(
            reproduction.R10_REGISTRY["atomic_failure_contract"][
                "pre_output_root_filename"
            ]
        )
        .replace("<stage>", "authority_capture")
        .replace("<process_uuid>", "fake")
    )
    assert len(failures[0]["raw_sha256"]) == 64
