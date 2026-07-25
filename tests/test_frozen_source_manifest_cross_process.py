from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap
import uuid

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))

from scripts import run_query_anchor_r4 as runner  # noqa: E402


def _manifest_from_fresh_process(
    *, launcher_context: bool, workspace: Path = WORKSPACE
) -> dict[str, object]:
    imports = (
        "from scripts import run_query_anchor_r4_reproduction as launcher; "
        "runner = launcher.r24_runner; "
        if launcher_context
        else "from scripts import run_query_anchor_r4 as runner; "
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json; "
                f"{imports}"
                "print(json.dumps(runner._source_manifest(), "
                "allow_nan=False, ensure_ascii=True, "
                "separators=(',', ':'), sort_keys=True))"
            ),
        ],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _copy_complete_allowlist_workspace(destination: Path) -> None:
    for relative in runner.SOURCE_ALLOWLIST:
        source = WORKSPACE / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    r23_base = Path("refine-logs/CALIBRATION_PROTOCOL_R23_2026-07-24.md")
    r23_target = destination / r23_base
    r23_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(WORKSPACE / r23_base, r23_target)
    # R25's base_dependency points at R24; the allowlist tracks R25 (the live
    # authority) but the isolated workspace also needs R24 for
    # _load_r25_candidate_registry's base-hash validation.
    r24_base = Path("refine-logs/CALIBRATION_PROTOCOL_R24_2026-07-24.md")
    r24_target = destination / r24_base
    r24_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(WORKSPACE / r24_base, r24_target)


def _write_frozen_r24_test_authority(workspace: Path) -> None:
    # R25 is the live authority.  The child process imports run_query_anchor_r4,
    # which loads R25 at module init and validates the R24 base protocol hash.
    # The modified authority must therefore be written as the R25 protocol file,
    # leaving the R24 base file (copied unmodified by the allowlist) intact so
    # _load_r25_candidate_registry's base-hash validation passes.
    registry = copy.deepcopy(runner.R25_REGISTRY)
    registry["authority_state"] = registry["status_vocabulary"]["protocol_frozen"]
    registry["freeze_requirements"]["implementation_hashes_frozen"] = True
    registry["freeze_requirements"]["dry_run_authorized"] = True
    registry["freeze_requirements"][
        "external_materializer_hashes_prebound_and_live_verified"
    ] = True

    materializer_path = workspace / ".tmp" / "audit_r24_registered.py"
    materializer_path.parent.mkdir(parents=True, exist_ok=True)
    materializer_path.write_text(
        "# isolated frozen R25 test materializer\n", encoding="utf-8"
    )
    materializer = registry["phase_authorization_contract"]["external_materializers"][
        "registered_reproduction_authorizer"
    ]
    materializer["sha256"] = hashlib.sha256(materializer_path.read_bytes()).hexdigest()

    protocol_path = workspace / "refine-logs" / "CALIBRATION_PROTOCOL_R25_2026-07-25.md"
    protocol_path.write_text(
        "# Isolated frozen R25 cross-process eligibility authority\n\n"
        "```json\n" + json.dumps(registry, indent=2, sort_keys=True) + "\n```\n",
        encoding="utf-8",
    )


def _fresh_launcher_authority_match(
    workspace: Path, expected_manifest_path: Path
) -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json, sys; "
                "from pathlib import Path; "
                "from scripts import run_query_anchor_r4_reproduction as launcher; "
                "runner = launcher.r24_runner; "
                "expected = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')); "
                "observed = runner._source_manifest(); "
                "print(json.dumps({"
                "'matches': runner._source_manifest_authority_matches_expected("
                "expected, observed), "
                "'observed': observed"
                "}, sort_keys=True))"
            ),
            str(expected_manifest_path),
        ],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _rebind_authority(manifest: dict[str, object]) -> None:
    manifest["source_manifest_authority_sha256"] = runner._json_hash(
        runner._source_manifest_authority_payload(manifest)
    )


def test_frozen_source_authority_survives_distinct_valid_import_domains(
    tmp_path: Path,
) -> None:
    child_manifest = _manifest_from_fresh_process(launcher_context=False)
    launcher_manifest = _manifest_from_fresh_process(launcher_context=True)

    assert runner._source_manifest_authority_valid(child_manifest)
    assert runner._source_manifest_authority_valid(launcher_manifest)
    assert (
        child_manifest["observed_workspace_imports"]
        != launcher_manifest["observed_workspace_imports"]
    )
    launcher_path = "scripts/run_query_anchor_r4_reproduction.py"
    assert launcher_path not in child_manifest["observed_workspace_imports"]
    assert launcher_path in launcher_manifest["observed_workspace_imports"]
    assert (
        child_manifest["source_manifest_authority_sha256"]
        == launcher_manifest["source_manifest_authority_sha256"]
    )

    persisted = tmp_path / "child-summary-source-manifest.json"
    persisted.write_text(
        json.dumps(
            child_manifest,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    reopened_child_manifest = json.loads(persisted.read_text(encoding="utf-8"))
    assert runner._source_manifest_authority_matches_expected(
        reopened_child_manifest,
        launcher_manifest,
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "stale_child_file",
        "allowlist_byte_drift",
        "legacy_authority_field",
        "wrong_authority_sha256",
        "unexpected_workspace_import",
        "live_expected_file_drift",
    ],
)
def test_frozen_source_authority_rejects_cross_process_drift(mutation: str) -> None:
    child_manifest = _manifest_from_fresh_process(launcher_context=False)
    launcher_manifest = _manifest_from_fresh_process(launcher_context=True)
    observed = copy.deepcopy(child_manifest)
    expected = copy.deepcopy(launcher_manifest)

    if mutation == "stale_child_file":
        path = next(iter(observed["files"]))
        observed["files"][path] = "f" * 64
        _rebind_authority(observed)
        assert runner._source_manifest_authority_valid(observed)
    elif mutation == "allowlist_byte_drift":
        observed["allowlist"][0] = observed["allowlist"][0] + ".stale"
        _rebind_authority(observed)
    elif mutation == "legacy_authority_field":
        observed["source_manifest_sha256"] = observed.pop(
            "source_manifest_authority_sha256"
        )
    elif mutation == "wrong_authority_sha256":
        observed["source_manifest_authority_sha256"] = "0" * 64
    elif mutation == "unexpected_workspace_import":
        observed["observed_workspace_imports"] = sorted(
            [*observed["observed_workspace_imports"], "tests/unregistered_probe.py"]
        )
    elif mutation == "live_expected_file_drift":
        path = next(iter(expected["files"]))
        expected["files"][path] = "e" * 64
        _rebind_authority(expected)
        assert runner._source_manifest_authority_valid(expected)
    else:  # pragma: no cover - exhaustive parametrization guard
        raise AssertionError(mutation)

    assert not runner._source_manifest_authority_matches_expected(observed, expected)


def test_fresh_child_summary_passes_real_fresh_launcher_eligibility(
    request: pytest.FixtureRequest,
) -> None:
    for _attempt in range(100):
        workspace = WORKSPACE / ".tmp" / uuid.uuid4().hex[:4]
        try:
            workspace.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            continue
        break
    else:  # pragma: no cover - UUID collision exhaustion guard
        raise RuntimeError("could not allocate a short isolated R24 workspace")
    request.addfinalizer(lambda: shutil.rmtree(workspace, ignore_errors=True))
    _copy_complete_allowlist_workspace(workspace)
    _write_frozen_r24_test_authority(workspace)

    r23_summary = (
        WORKSPACE
        / "artifacts"
        / "calibration"
        / "capes_ci_qptm_r23_reproduction_local_20260724_v1"
        / "process_a"
        / "summary.json"
    )
    shutil.copy2(r23_summary, workspace / "r23-process-a-summary.json")
    specification = runner.R24_REGISTRY["phase_authorization_contract"][
        "reproduction_authorization"
    ]
    prerequisite_summary_source = WORKSPACE / specification["prerequisite_summary_path"]
    prerequisite_summary_target = workspace / specification["prerequisite_summary_path"]
    prerequisite_summary_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(prerequisite_summary_source, prerequisite_summary_target)

    persisted_summary = workspace / "persisted-r24-child-summary.json"
    persisted_replica = workspace / "persisted-r24-replica-summary.json"
    child_program = textwrap.dedent(
        """
        import copy
        import hashlib
        import json
        from pathlib import Path
        import sys

        from scripts import run_query_anchor_r4 as runner

        workspace = Path.cwd()
        source_manifest = runner._source_manifest()
        summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        registry = runner.FROZEN_R6_REGISTRY
        schema_replacements = {
            old: registry["schema_versions"][name]
            for name, old in runner.R23_REGISTRY["schema_versions"].items()
            if name in registry["schema_versions"]
            and old != registry["schema_versions"][name]
        }

        def migrate_schema_values(value):
            if isinstance(value, dict):
                return {
                    key: migrate_schema_values(item)
                    for key, item in value.items()
                }
            if isinstance(value, list):
                return [migrate_schema_values(item) for item in value]
            return schema_replacements.get(value, value)

        summary = migrate_schema_values(summary)
        contract = registry["phase_authorization_contract"]
        specification = contract["reproduction_authorization"]
        materializer_id = "registered_reproduction_authorizer"
        materializer = contract["external_materializers"][materializer_id]
        provenance = {
            "materializer_id": materializer_id,
            "relative_path": materializer["relative_path"],
            "sha256": materializer["sha256"],
            "invocation": {
                "working_directory_relative": materializer["invocation"][
                    "working_directory_relative"
                ],
                "argv0_relative_path": materializer["relative_path"],
                "argv_tail": materializer["invocation"]["argv_tail"],
            },
        }

        audit_contract = contract["registered_postrun_audit_contract"]
        audit = {
            "schema_version": audit_contract["schema_version"],
            "run_dir": (
                "artifacts/calibration/"
                "capes_ci_qptm_r14_registered_local_20260723_v1"
            ),
            "passed": True,
            "verdict": specification["prerequisite_audit_verdict"],
            "checks": {
                key: True for key in audit_contract["required_exact_check_keys"]
            },
            "failed_checks": [],
            "evidence": {"materializer_provenance": copy.deepcopy(provenance)},
            audit_contract["self_hash_field"]: None,
        }
        audit[audit_contract["self_hash_field"]] = (
            runner._authorization_self_hash(
                audit, audit_contract["self_hash_field"]
            )
        )
        audit_path = workspace / specification["prerequisite_audit_path"]
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit_path.write_bytes(runner._authorization_canonical_bytes(audit))

        prerequisite_summary_path = (
            workspace / specification["prerequisite_summary_path"]
        )
        prerequisite_summary_sha256 = hashlib.sha256(
            prerequisite_summary_path.read_bytes()
        ).hexdigest()
        assert (
            prerequisite_summary_sha256
            == specification["prerequisite_summary_sha256"]
        )
        audit_file_sha256 = hashlib.sha256(audit_path.read_bytes()).hexdigest()
        child = specification["child_certificates"]["process_a"]
        certificate = {
            "schema_version": child["schema_version"],
            "certificate_type": child["certificate_type"],
            "certificate_id": "11111111-1111-4111-8111-111111111111",
            "phase_nonce": "a" * 64,
            "protocol_id": registry["protocol_id"],
            "protocol_sha256": runner.R10_PROTOCOL_SHA256,
            "registry_sha256": runner._json_hash(registry),
            "source_manifest_authority_sha256": source_manifest[
                "source_manifest_authority_sha256"
            ],
            "materializer_provenance": copy.deepcopy(provenance),
            "target_phase": specification["target_phase"],
            "target_output_parent_relative": specification[
                "target_output_parent_relative"
            ],
            "target_child_leaf": "process_a",
            "target_output_root_relative": child[
                "target_output_root_relative"
            ],
            "target_seeds": specification["target_seeds"],
            "target_steps": specification["target_steps"],
            "target_device": specification["target_device"],
            "prerequisite_summary_path": specification[
                "prerequisite_summary_path"
            ],
            "prerequisite_summary_sha256": prerequisite_summary_sha256,
            "prerequisite_audit_path": specification[
                "prerequisite_audit_path"
            ],
            "prerequisite_audit_file_sha256": audit_file_sha256,
            "prerequisite_audit_self_sha256": audit[
                specification["prerequisite_audit_self_hash_field"]
            ],
            "prerequisite_audit_verdict": specification[
                "prerequisite_audit_verdict"
            ],
            "prerequisite_audit_passed": True,
            "formal_data_authorization": specification[
                "formal_data_authorization_expected"
            ],
            "formal_test_used": specification["formal_test_used_expected"],
            "formal_claim_flags": specification[
                "formal_claim_flags_expected"
            ],
            "checks": {
                key: True
                for key in specification[
                    "child_certificate_required_exact_check_keys"
                ]
            },
            "authorized": True,
            "authorization_status": specification["authorization_status"],
            "issued_utc": "2026-07-23T12:00:00.000000Z",
            contract["certificate_self_hash_field"]: None,
        }
        certificate[contract["certificate_self_hash_field"]] = (
            runner._authorization_self_hash(
                certificate, contract["certificate_self_hash_field"]
            )
        )
        certificate_path = workspace / child["relative_path"]
        certificate_path.parent.mkdir(parents=True, exist_ok=True)
        certificate_path.write_bytes(
            runner._authorization_canonical_bytes(certificate)
        )

        parent = workspace / specification["target_output_parent_relative"]
        parent.mkdir(parents=True, exist_ok=False)
        args = runner.build_parser().parse_args(
            [
                "--run-dir",
                str(parent / "process_a"),
                "--steps",
                str(specification["target_steps"]),
                "--seeds",
                *(str(seed) for seed in specification["target_seeds"]),
                "--device",
                specification["target_device"],
            ]
        )
        process_uuid = "33333333-3333-4333-8333-333333333333"
        try:
            receipt = runner._phase_authorize(
                args,
                process_uuid=process_uuid,
                source_manifest=source_manifest,
            )
        except Exception as error:
            print(
                json.dumps(
                    {
                        "setup_error_type": type(error).__name__,
                        "setup_error": str(error),
                    },
                    sort_keys=True,
                )
            )
            raise SystemExit(0)

        replica_source_manifest = copy.deepcopy(source_manifest)
        replica_source_manifest["observed_workspace_imports"] = sorted(
            {
                *replica_source_manifest["observed_workspace_imports"],
                "scripts/run_query_anchor_r4_reproduction.py",
            }
        )
        assert runner._source_manifest_authority_valid(replica_source_manifest)
        replica_child = specification["child_certificates"]["process_b"]
        replica_certificate = copy.deepcopy(certificate)
        replica_certificate.update(
            {
                "schema_version": replica_child["schema_version"],
                "certificate_type": replica_child["certificate_type"],
                "certificate_id": "22222222-2222-4222-8222-222222222222",
                "phase_nonce": "b" * 64,
                "target_child_leaf": "process_b",
                "target_output_root_relative": replica_child[
                    "target_output_root_relative"
                ],
                contract["certificate_self_hash_field"]: None,
            }
        )
        replica_certificate[contract["certificate_self_hash_field"]] = (
            runner._authorization_self_hash(
                replica_certificate,
                contract["certificate_self_hash_field"],
            )
        )
        replica_certificate_path = workspace / replica_child["relative_path"]
        replica_certificate_path.write_bytes(
            runner._authorization_canonical_bytes(replica_certificate)
        )
        replica_args = runner.build_parser().parse_args(
            [
                "--run-dir",
                str(parent / "process_b"),
                "--steps",
                str(specification["target_steps"]),
                "--seeds",
                *(str(seed) for seed in specification["target_seeds"]),
                "--device",
                specification["target_device"],
            ]
        )
        replica_process_uuid = "44444444-4444-4444-8444-444444444444"
        replica_receipt = runner._phase_authorize(
            replica_args,
            process_uuid=replica_process_uuid,
            source_manifest=replica_source_manifest,
        )

        config = runner._registered_config(
            seeds=runner.TRAINABLE_SEEDS,
            actual_steps=runner.REGISTERED_STEPS,
            smoke=False,
            dry_run=False,
        )
        summary["summary_schema_version"] = runner.SUMMARY_SCHEMA_VERSION
        summary["protocol_version"] = runner.PROTOCOL_VERSION
        summary["config"] = config
        summary["config_sha256"] = runner._json_hash(config)
        summary["source_manifest"] = source_manifest
        summary["provenance"]["process_uuid"] = process_uuid
        summary["phase_authorization"] = receipt
        original_output_root = summary["provenance"]["output_root_absolute"]
        primary_output_root = str(parent / "process_a")

        def replace_root(value, old_root, new_root):
            if isinstance(value, dict):
                return {
                    key: replace_root(item, old_root, new_root)
                    for key, item in value.items()
                }
            if isinstance(value, list):
                return [
                    replace_root(item, old_root, new_root) for item in value
                ]
            if isinstance(value, str):
                return value.replace(old_root, new_root)
            return value

        summary = replace_root(
            summary,
            original_output_root,
            primary_output_root,
        )
        replica_summary = replace_root(
            copy.deepcopy(summary),
            primary_output_root,
            str(parent / "process_b"),
        )
        replica_summary["source_manifest"] = replica_source_manifest
        replica_summary["provenance"]["process_uuid"] = replica_process_uuid
        replica_summary["provenance"]["pid"] = 202
        replica_summary["provenance"]["start_utc"] = (
            "2026-07-23T12:01:00.000000Z"
        )
        replica_summary["provenance"]["end_utc"] = (
            "2026-07-23T12:02:00.000000Z"
        )
        replica_summary["provenance"]["monotonic_elapsed_seconds"] = 60.0
        replica_summary["phase_authorization"] = replica_receipt

        phase_valid = runner._phase_authorization_evidence_valid(summary)
        replica_phase_valid = runner._phase_authorization_evidence_valid(
            replica_summary
        )
        strict = runner._strict_summary_validation(summary)
        replica_strict = runner._strict_summary_validation(replica_summary)
        Path(sys.argv[2]).write_text(
            json.dumps(
                summary,
                allow_nan=False,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        Path(sys.argv[3]).write_text(
            json.dumps(
                replica_summary,
                allow_nan=False,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "phase_authorization_valid": phase_valid,
                    "replica_phase_authorization_valid": replica_phase_valid,
                    "strict_validation": strict,
                    "replica_strict_validation": replica_strict,
                    "observed_workspace_imports": source_manifest[
                        "observed_workspace_imports"
                    ],
                    "replica_observed_workspace_imports": (
                        replica_source_manifest["observed_workspace_imports"]
                    ),
                },
                sort_keys=True,
            )
        )
        """
    )
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            child_program,
            str(workspace / "r23-process-a-summary.json"),
            str(persisted_summary),
            str(persisted_replica),
        ],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    )
    child_result = json.loads(child.stdout)
    assert "setup_error" not in child_result, child_result
    assert child_result["phase_authorization_valid"] is True
    assert child_result["replica_phase_authorization_valid"] is True
    assert child_result["strict_validation"]["passed"] is True, child_result[
        "strict_validation"
    ]
    assert child_result["replica_strict_validation"]["passed"] is True, child_result[
        "replica_strict_validation"
    ]
    primary_summary = json.loads(persisted_summary.read_text(encoding="utf-8"))
    replica_summary = json.loads(persisted_replica.read_text(encoding="utf-8"))
    assert (
        primary_summary["source_manifest"]["observed_workspace_imports"]
        != replica_summary["source_manifest"]["observed_workspace_imports"]
    )
    assert (
        primary_summary["source_manifest"]["source_manifest_authority_sha256"]
        == replica_summary["source_manifest"]["source_manifest_authority_sha256"]
    )
    assert primary_summary["phase_authorization"]["target_child_leaf"] == "process_a"
    assert replica_summary["phase_authorization"]["target_child_leaf"] == "process_b"

    launcher_program = textwrap.dedent(
        """
        import copy
        import json
        from pathlib import Path
        import sys

        from scripts import run_query_anchor_r4_reproduction as launcher

        runner = launcher.r24_runner
        summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        replica = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        eligibility = runner._registered_reproduction_eligibility(summary)
        replica_eligibility = runner._registered_reproduction_eligibility(
            replica
        )
        comparison = runner._compare_independent_reproduction(
            summary,
            replica,
            primary_returncode=0,
            replica_returncode=0,
            primary_expected_pid=summary["provenance"]["pid"],
            replica_expected_pid=replica["provenance"]["pid"],
        )
        wrong_authority = copy.deepcopy(replica)
        wrong_authority["source_manifest"][
            "source_manifest_authority_sha256"
        ] = "0" * 64
        wrong_authority_eligibility = (
            runner._registered_reproduction_eligibility(wrong_authority)
        )
        wrong_files = copy.deepcopy(replica)
        drift_path = next(iter(wrong_files["source_manifest"]["files"]))
        wrong_files["source_manifest"]["files"][drift_path] = "f" * 64
        wrong_files["source_manifest"][
            "source_manifest_authority_sha256"
        ] = runner._json_hash(
            runner._source_manifest_authority_payload(
                wrong_files["source_manifest"]
            )
        )
        wrong_files_eligibility = runner._registered_reproduction_eligibility(
            wrong_files
        )
        live_source = runner._source_manifest()
        print(
            json.dumps(
                {
                    "eligibility": eligibility,
                    "replica_eligibility": replica_eligibility,
                    "comparison": comparison,
                    "wrong_authority_eligibility": (
                        wrong_authority_eligibility
                    ),
                    "wrong_files_eligibility": wrong_files_eligibility,
                    "live_observed_workspace_imports": live_source[
                        "observed_workspace_imports"
                    ],
                },
                sort_keys=True,
            )
        )
        """
    )
    launcher = subprocess.run(
        [
            sys.executable,
            "-c",
            launcher_program,
            str(persisted_summary),
            str(persisted_replica),
        ],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    )
    launcher_result = json.loads(launcher.stdout)
    assert (
        child_result["observed_workspace_imports"]
        != launcher_result["live_observed_workspace_imports"]
    )
    assert launcher_result["eligibility"]["checks"]["source_manifest_authority_exact"]
    assert launcher_result["eligibility"]["checks"]["phase_authorization_valid"]
    assert launcher_result["eligibility"]["checks"]["strict_summary_validation"]
    assert launcher_result["eligibility"]["passed"] is True
    assert launcher_result["replica_eligibility"]["passed"] is True
    assert launcher_result["comparison"]["passed"] is True
    assert launcher_result["comparison"]["checks"]["canonical_payload_exact"]
    assert launcher_result["comparison"]["checks"]["canonical_sha256_exact"]
    assert launcher_result["comparison"]["mismatch_paths"] == []
    assert launcher_result["comparison"]["comparison_excludes_only"][-2:] == [
        "/phase_authorization",
        "/source_manifest/observed_workspace_imports",
    ]
    assert (
        "/source_manifest/source_manifest_authority_sha256"
        not in launcher_result["comparison"]["comparison_excludes_only"]
    )
    assert (
        "/source_manifest/files"
        not in launcher_result["comparison"]["comparison_excludes_only"]
    )
    assert (
        launcher_result["wrong_authority_eligibility"]["checks"][
            "source_manifest_authority_exact"
        ]
        is False
    )
    assert launcher_result["wrong_authority_eligibility"]["passed"] is False
    assert (
        launcher_result["wrong_files_eligibility"]["checks"][
            "source_manifest_authority_exact"
        ]
        is False
    )
    assert launcher_result["wrong_files_eligibility"]["passed"] is False


def test_fresh_launcher_rejects_actual_allowlisted_file_byte_drift(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "isolated-r24-live-drift"
    _copy_complete_allowlist_workspace(workspace)
    expected = _manifest_from_fresh_process(
        launcher_context=True,
        workspace=workspace,
    )
    expected_path = workspace / "expected-source-manifest.json"
    expected_path.write_text(
        json.dumps(expected, sort_keys=True),
        encoding="utf-8",
    )

    governed_path = workspace / "reports" / "r5_runner_gate_spec_2026-07-22.md"
    governed_path.write_bytes(
        governed_path.read_bytes() + b"\nR24 isolated live-byte drift sentinel\n"
    )
    result = _fresh_launcher_authority_match(workspace, expected_path)

    assert (
        result["observed"]["files"]["reports/r5_runner_gate_spec_2026-07-22.md"]
        != expected["files"]["reports/r5_runner_gate_spec_2026-07-22.md"]
    )
    assert (
        result["observed"]["source_manifest_authority_sha256"]
        != expected["source_manifest_authority_sha256"]
    )
    assert result["matches"] is False
