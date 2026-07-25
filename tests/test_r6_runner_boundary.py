from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import sys
import uuid

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))

import scripts.run_query_anchor_r4 as r6  # noqa: E402


def _stop_status(reason: str) -> str:
    prefix = r6.R10_REGISTRY["status_vocabulary"]["scientific_stop_prefix"]
    return f"{prefix}{reason.upper()}"


def _pre_root_failure_parent(output_parent: Path) -> Path:
    registered = Path(
        r6.R10_REGISTRY["atomic_failure_contract"]["pre_output_root_failure_parent"]
    )
    return output_parent.parent.parent / registered


@pytest.fixture
def writable_workspace() -> Path:
    root = WORKSPACE / "tmp" / "r6_boundary" / uuid.uuid4().hex
    root.mkdir(parents=True)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _closed_manifest() -> dict[str, object]:
    authority_payload: dict[str, object] = {
        "schema_version": r6.IMPLEMENTED_SCHEMA_VERSIONS["source_manifest"],
        "allowlist": list(r6.SOURCE_ALLOWLIST),
        "files": {
            relative: r6.hashlib.sha256((WORKSPACE / relative).read_bytes()).hexdigest()
            for relative in r6.SOURCE_ALLOWLIST
        },
    }
    return {
        **authority_payload,
        "source_manifest_authority_sha256": r6._json_hash(authority_payload),
        "observed_workspace_imports": [],
    }


def _write_self_hashed_smoke_certificate(
    workspace: Path, source_manifest_authority_sha256: str
) -> tuple[Path, dict[str, object]]:
    contract = r6.FROZEN_R6_REGISTRY["phase_authorization_contract"]
    specification = contract["smoke_authorization"]
    certificate = {
        "schema_version": specification["schema_version"],
        "certificate_type": "smoke_authorization",
        "certificate_id": str(uuid.uuid4()),
        "phase_nonce": "a" * 64,
        "protocol_id": r6.PROTOCOL_VERSION,
        "protocol_sha256": r6.R10_PROTOCOL_SHA256,
        "registry_sha256": r6._json_hash(r6.FROZEN_R6_REGISTRY),
        "source_manifest_authority_sha256": source_manifest_authority_sha256,
        "materializer_provenance": {},
        "target_phase": specification["target_phase"],
        "target_output_root_relative": specification["target_output_root_relative"],
        "target_seeds": [17],
        "target_steps": 1,
        "target_device": specification["target_device"],
        "prerequisite_summary_path": specification["prerequisite_summary_path"],
        "prerequisite_summary_sha256": "b" * 64,
        "prerequisite_audit_path": specification["prerequisite_audit_path"],
        "prerequisite_audit_file_sha256": "c" * 64,
        "prerequisite_audit_self_sha256": "d" * 64,
        "prerequisite_audit_verdict": specification["prerequisite_audit_verdict"],
        "prerequisite_audit_passed": True,
        "formal_data_authorization": specification[
            "formal_data_authorization_expected"
        ],
        "formal_test_used": specification["formal_test_used_expected"],
        "formal_claim_flags": copy.deepcopy(
            specification["formal_claim_flags_expected"]
        ),
        "checks": {key: True for key in specification["required_exact_check_keys"]},
        "authorized": True,
        "authorization_status": specification["authorization_status"],
        "issued_utc": "2026-07-23T00:00:00Z",
    }
    self_field = contract["certificate_self_hash_field"]
    certificate[self_field] = r6._authorization_self_hash(certificate, self_field)
    certificate_path = workspace / str(specification["relative_path"])
    certificate_path.parent.mkdir(parents=True)
    certificate_path.write_bytes(r6._authorization_canonical_bytes(certificate))
    return certificate_path, certificate


def _phase_authorization_evidence_summary(
    monkeypatch: pytest.MonkeyPatch, workspace: Path
):
    """Build a fully rebound smoke receipt chain for terminal-validator tests."""

    monkeypatch.setattr(r6, "WORKSPACE", workspace)
    contract = r6.FROZEN_R6_REGISTRY["phase_authorization_contract"]
    specification = contract["smoke_authorization"]
    audit_contract = contract["dryrun_postrun_audit_contract"]
    source = _closed_manifest()
    process_uuid = str(uuid.uuid4())
    certificate_id = str(uuid.uuid4())
    phase_nonce = "a" * 64
    materializer = contract["external_materializers"][
        specification["issuing_materializer_id"]
    ]
    materializer_provenance = {
        "materializer_id": specification["issuing_materializer_id"],
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
    prerequisite_summary: dict[str, object] = {
        "status": specification["prerequisite_summary_status"]
    }
    audit: dict[str, object] = {
        "schema_version": audit_contract["schema_version"],
        "run_dir": "artifacts/calibration/prerequisite",
        "passed": True,
        "verdict": specification["prerequisite_audit_verdict"],
        "checks": {key: True for key in audit_contract["required_exact_check_keys"]},
        "failed_checks": [],
        "evidence": {"materializer_provenance": materializer_provenance},
    }
    audit_self_field = specification["prerequisite_audit_self_hash_field"]
    audit[audit_self_field] = r6._authorization_self_hash(audit, audit_self_field)
    evidence: dict[str, object] = {
        "certificate_type": "smoke_authorization",
        "certificate_path": specification["relative_path"],
        "certificate_file_sha256": "",
        "certificate_self_sha256": "",
        "certificate_id": certificate_id,
        "phase_nonce": phase_nonce,
        "claim_path": (
            f"{contract['claims_subdirectory_relative']}/smoke_authorization."
            f"{certificate_id}.{phase_nonce}.claim.json"
        ),
        "claim_file_sha256": "",
        "claim_self_sha256": "",
        "claim_process_uuid": process_uuid,
        "protocol_sha256": r6.R10_PROTOCOL_SHA256,
        "registry_sha256": r6._json_hash(r6.FROZEN_R6_REGISTRY),
        "source_manifest_authority_sha256": source["source_manifest_authority_sha256"],
        "materializer_provenance": materializer_provenance,
        "target_phase": specification["target_phase"],
        "target_output_root_relative": specification["target_output_root_relative"],
        "target_seeds": copy.deepcopy(specification["target_seeds"]),
        "target_steps": specification["target_steps"],
        "target_device": specification["target_device"],
        "prerequisite_summary_sha256": "",
        "prerequisite_audit_file_sha256": "",
        "prerequisite_audit_self_sha256": "",
        "formal_data_authorization": specification[
            "formal_data_authorization_expected"
        ],
        "formal_test_used": specification["formal_test_used_expected"],
        "formal_claim_flags": copy.deepcopy(
            specification["formal_claim_flags_expected"]
        ),
        "pre_root_target_absent_snapshot": True,
        "authorized": True,
        "authorization_status": specification["authorization_status"],
    }
    certificate: dict[str, object] = {
        "schema_version": specification["schema_version"],
        "certificate_type": "smoke_authorization",
        "certificate_id": certificate_id,
        "phase_nonce": phase_nonce,
        "protocol_id": r6.PROTOCOL_VERSION,
        "protocol_sha256": r6.R10_PROTOCOL_SHA256,
        "registry_sha256": r6._json_hash(r6.FROZEN_R6_REGISTRY),
        "source_manifest_authority_sha256": source["source_manifest_authority_sha256"],
        "materializer_provenance": materializer_provenance,
        "target_phase": specification["target_phase"],
        "target_output_root_relative": specification["target_output_root_relative"],
        "target_seeds": copy.deepcopy(specification["target_seeds"]),
        "target_steps": specification["target_steps"],
        "target_device": specification["target_device"],
        "prerequisite_summary_path": specification["prerequisite_summary_path"],
        "prerequisite_summary_sha256": "",
        "prerequisite_audit_path": specification["prerequisite_audit_path"],
        "prerequisite_audit_file_sha256": "",
        "prerequisite_audit_self_sha256": "",
        "prerequisite_audit_verdict": specification["prerequisite_audit_verdict"],
        "prerequisite_audit_passed": True,
        "formal_data_authorization": specification[
            "formal_data_authorization_expected"
        ],
        "formal_test_used": specification["formal_test_used_expected"],
        "formal_claim_flags": copy.deepcopy(
            specification["formal_claim_flags_expected"]
        ),
        "checks": {key: True for key in specification["required_exact_check_keys"]},
        "authorized": True,
        "authorization_status": specification["authorization_status"],
        "issued_utc": "2026-07-23T00:00:00Z",
    }
    claim: dict[str, object] = {}

    def encoded_hash(payload: dict[str, object]) -> str:
        return r6.hashlib.sha256(r6._authorization_canonical_bytes(payload)).hexdigest()

    def rebind() -> None:
        evidence["prerequisite_summary_sha256"] = encoded_hash(prerequisite_summary)
        evidence["prerequisite_audit_file_sha256"] = encoded_hash(audit)
        evidence["prerequisite_audit_self_sha256"] = audit[audit_self_field]
        certificate["prerequisite_summary_sha256"] = evidence[
            "prerequisite_summary_sha256"
        ]
        certificate["prerequisite_audit_file_sha256"] = evidence[
            "prerequisite_audit_file_sha256"
        ]
        certificate["prerequisite_audit_self_sha256"] = evidence[
            "prerequisite_audit_self_sha256"
        ]
        certificate_self_field = contract["certificate_self_hash_field"]
        certificate[certificate_self_field] = r6._authorization_self_hash(
            certificate, certificate_self_field
        )
        evidence["certificate_self_sha256"] = certificate[certificate_self_field]
        evidence["certificate_file_sha256"] = encoded_hash(certificate)
        claim.clear()
        claim.update(
            {
                "schema_version": contract["claim_schema_version"],
                "certificate_type": "smoke_authorization",
                "certificate_id": certificate_id,
                "phase_nonce": phase_nonce,
                "process_uuid": process_uuid,
                "target_phase": specification["target_phase"],
                "target_output_root_relative": specification[
                    "target_output_root_relative"
                ],
                "certificate_path": specification["relative_path"],
                "certificate_file_sha256": evidence["certificate_file_sha256"],
                "certificate_self_sha256": evidence["certificate_self_sha256"],
                "protocol_sha256": r6.R10_PROTOCOL_SHA256,
                "registry_sha256": r6._json_hash(r6.FROZEN_R6_REGISTRY),
                "source_manifest_authority_sha256": source[
                    "source_manifest_authority_sha256"
                ],
                "pre_root_target_absent": True,
                "claimed_utc": "2026-07-23T00:00:00Z",
            }
        )
        claim_self_field = contract["claim_self_hash_field"]
        claim[claim_self_field] = r6._authorization_self_hash(claim, claim_self_field)
        evidence["claim_self_sha256"] = claim[claim_self_field]
        evidence["claim_file_sha256"] = encoded_hash(claim)

    rebind()
    snapshots = {
        specification["relative_path"]: certificate,
        evidence["claim_path"]: claim,
        specification["prerequisite_summary_path"]: prerequisite_summary,
        specification["prerequisite_audit_path"]: audit,
    }

    def snapshot(path: Path) -> tuple[bytes, dict[str, object], str]:
        relative = path.relative_to(workspace).as_posix()
        payload = snapshots[relative]
        raw = r6._authorization_canonical_bytes(payload)
        return raw, payload, r6.hashlib.sha256(raw).hexdigest()

    monkeypatch.setattr(r6, "_authorization_snapshot", snapshot)
    monkeypatch.setattr(r6, "_strict_summary_validation", lambda _: {"passed": True})
    monkeypatch.setattr(
        r6,
        "_materializer_provenance_matches_frozen_contract",
        lambda *_args, **_kwargs: True,
    )
    summary: dict[str, object] = {
        "phase_authorization": evidence,
        "config": {
            "trainable_seeds": copy.deepcopy(specification["target_seeds"]),
            "actual_steps": specification["target_steps"],
            "device": specification["target_device"],
        },
        "source_manifest": source,
        "provenance": {"process_uuid": process_uuid},
    }
    return summary, certificate, claim, prerequisite_summary, audit, rebind


def _terminal_phase_authorization_requires_full_certificate_and_claim_contract(
    monkeypatch: pytest.MonkeyPatch, writable_workspace: Path
) -> None:
    summary, certificate, claim, prerequisite_summary, audit, rebind = (
        _phase_authorization_evidence_summary(monkeypatch, writable_workspace)
    )

    specification = r6.FROZEN_R6_REGISTRY["phase_authorization_contract"][
        "smoke_authorization"
    ]
    assert set(certificate) == set(specification["required_exact_top_level_keys"])
    assert set(claim) == set(
        r6.FROZEN_R6_REGISTRY["phase_authorization_contract"][
            "claim_required_exact_top_level_keys"
        ]
    )
    evidence = summary["phase_authorization"]
    assert set(evidence) == set(
        r6.FROZEN_R6_REGISTRY["phase_authorization_contract"]["runner_guard"][
            "summary_authorization_evidence_required_fields"
        ]
    )
    claim_raw, _, claim_hash = r6._authorization_snapshot(
        writable_workspace / evidence["claim_path"]
    )
    assert claim_raw == r6._authorization_canonical_bytes(claim)
    assert claim_hash == evidence["claim_file_sha256"]
    certificate_raw, _, certificate_hash = r6._authorization_snapshot(
        writable_workspace / evidence["certificate_path"]
    )
    assert certificate_raw == r6._authorization_canonical_bytes(certificate)
    assert certificate_hash == evidence["certificate_file_sha256"]
    assert r6._validate_prerequisite_audit(audit, specification)
    assert r6._phase_authorization_evidence_valid(summary)

    certificate["checks"]["frozen_protocol_hash_matches_live"] = False
    rebind()
    assert not r6._phase_authorization_evidence_valid(summary)
    certificate["checks"]["frozen_protocol_hash_matches_live"] = True
    rebind()

    claim["schema_version"] = "forged-claim-schema"
    claim_self_field = r6.FROZEN_R6_REGISTRY["phase_authorization_contract"][
        "claim_self_hash_field"
    ]
    claim[claim_self_field] = r6._authorization_self_hash(claim, claim_self_field)
    evidence = summary["phase_authorization"]
    evidence["claim_self_sha256"] = claim[claim_self_field]
    evidence["claim_file_sha256"] = r6.hashlib.sha256(
        r6._authorization_canonical_bytes(claim)
    ).hexdigest()
    assert not r6._phase_authorization_evidence_valid(summary)
    rebind()

    prerequisite_summary["status"] = "FORGED_PREREQUISITE_STATUS"
    rebind()
    assert not r6._phase_authorization_evidence_valid(summary)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("target_steps", True),
        ("target_steps", 1.0),
        ("target_seeds", [True]),
        ("target_seeds", [17.0]),
        ("formal_test_used", 0),
        ("formal_test_used", 0.0),
        ("formal_claim_flags.formal_claim_allowed", 0),
        ("formal_claim_flags.formal_claim_allowed", 0.0),
    ],
)
def test_r11_authorization_exact_values_reject_type_aliases(
    field: str,
    replacement: object,
) -> None:
    expected: dict[str, object] = {
        "target_steps": 500,
        "target_seeds": [17, 29, 43],
        "formal_test_used": False,
        "formal_claim_flags": {"formal_claim_allowed": False},
    }
    observed = copy.deepcopy(expected)
    if "." in field:
        parent, child = field.split(".", maxsplit=1)
        assert isinstance(observed[parent], dict)
        observed[parent][child] = replacement
    else:
        observed[field] = replacement
    assert not r6._authorization_value_exact(observed, expected)


def _resolution_stop_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> dict[str, object]:
    source = _closed_manifest()
    monkeypatch.setattr(r6, "_source_manifest", lambda: copy.deepcopy(source))
    monkeypatch.setattr(
        r6,
        "_registered_config",
        lambda **_kwargs: {"protocol_version": r6.PROTOCOL_VERSION},
    )
    monkeypatch.setattr(r6, "_runtime_environment", lambda: {})
    monkeypatch.setattr(
        r6,
        "_resolution_gate",
        lambda *_args, **_kwargs: {
            "resolver_schema_version": r6.RESOLVER_SCHEMA_VERSION,
            "status": "FAIL_RESOLUTION_FREEZE",
            "passed": False,
            "checks": {"frozen_authority": False},
        },
    )
    args = r6.build_parser().parse_args(
        ["--run-dir", str(tmp_path / "never-materialized"), "--dry-run"]
    )
    args._raw_argv = [
        "--run-dir",
        str(tmp_path / "never-materialized"),
        "--dry-run",
    ]
    summary = r6.run(args)
    assert summary["status"] == _stop_status("resolution_freeze")
    assert r6._strict_summary_validation(summary)["passed"]
    return summary


def _dry_run_ledger() -> list[dict[str, object]]:
    rows = (
        ("structural_input", "clean", "literal_audit_fixture"),
        ("structural_input", "challenge", "literal_audit_fixture"),
        ("fixture_identifiability", "clean", "frozen_fixture_audit"),
        ("fixture_identifiability", "challenge", "frozen_fixture_audit"),
    )
    return [
        r6._access_ledger_entry(
            gate=gate,
            stratum=stratum,
            split=split,
            name=f"{stratum}_{split}",
            purpose="r6_boundary_test",
            content_hash=f"{index:064x}",
            cache_hit=index >= 2,
        )
        for index, (gate, stratum, split) in enumerate(rows, start=1)
    ]


def test_gate_zero_failure_does_not_create_output_root(
    monkeypatch: pytest.MonkeyPatch, writable_workspace: Path
) -> None:
    workspace = writable_workspace / "workspace"
    output_parent = workspace / "artifacts" / "calibration"
    output_parent.mkdir(parents=True)
    monkeypatch.setattr(r6, "WORKSPACE", workspace)

    source = _closed_manifest()
    monkeypatch.setattr(r6, "_source_manifest", lambda: copy.deepcopy(source))
    monkeypatch.setattr(r6, "_runtime_environment", lambda: {})
    monkeypatch.setattr(r6, "_registered_config", lambda **_kwargs: {})
    monkeypatch.setattr(
        r6,
        "_resolution_gate",
        lambda *_args, **_kwargs: {
            "status": "FAIL_RESOLUTION_FREEZE",
            "passed": False,
            "checks": {"frozen_authority": False},
        },
    )
    run_dir = (
        output_parent
        / r6.R10_REGISTRY["output_root_contract"]["phase_leaf_names"]["dry_run"]
    )
    exit_code = r6.main(["--run-dir", str(run_dir), "--dry-run"])

    assert exit_code == 4
    assert not run_dir.exists()
    failure_parent = _pre_root_failure_parent(output_parent)
    failures = list(failure_parent.glob("authority_capture.*.failure.json"))
    assert len(failures) == 1


def test_phase_authorization_denial_is_pre_root_and_uses_dedicated_status(
    monkeypatch: pytest.MonkeyPatch, writable_workspace: Path
) -> None:
    workspace = writable_workspace / "phase-denial-workspace"
    output_parent = workspace / "artifacts" / "calibration"
    output_parent.mkdir(parents=True)
    monkeypatch.setattr(r6, "WORKSPACE", workspace)
    source = _closed_manifest()
    monkeypatch.setattr(r6, "_source_manifest", lambda: copy.deepcopy(source))
    monkeypatch.setattr(r6, "_runtime_environment", lambda: {})
    monkeypatch.setattr(r6, "_registered_config", lambda **_kwargs: {})
    monkeypatch.setattr(
        r6,
        "_resolution_gate",
        lambda *_args, **_kwargs: {
            "status": "PASS",
            "passed": True,
            "checks": {"frozen": True},
        },
    )
    monkeypatch.setattr(
        r6,
        "_phase_authorize",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            r6._phase_authorization_failure("missing certificate")
        ),
    )
    run_dir = output_parent / r6.IMPLEMENTED_OUTPUT_LEAVES["smoke"]

    assert r6.main(["--run-dir", str(run_dir), "--smoke", "--seeds", "17"]) == 4
    assert not run_dir.exists()
    failure_paths = list(
        _pre_root_failure_parent(output_parent).glob(
            "phase_authorization.*.failure.json"
        )
    )
    assert len(failure_paths) == 1
    failure = json.loads(failure_paths[0].read_text(encoding="utf-8"))
    assert (
        failure["status"]
        == r6.IMPLEMENTED_STATUS_VOCABULARY["phase_authorization_failure"]
    )
    assert failure["stage"] == "phase_authorization"


def test_wrong_output_root_is_rejected_before_source_or_run(
    monkeypatch: pytest.MonkeyPatch, writable_workspace: Path
) -> None:
    workspace = writable_workspace / "workspace"
    output_parent = workspace / "artifacts" / "calibration"
    output_parent.mkdir(parents=True)
    monkeypatch.setattr(r6, "WORKSPACE", workspace)

    def forbidden() -> object:
        raise AssertionError("source inspection occurred after output-root rejection")

    monkeypatch.setattr(r6, "_source_manifest", forbidden)
    monkeypatch.setattr(
        r6,
        "run",
        lambda _args: (_ for _ in ()).throw(
            AssertionError("runner executed after output-root rejection")
        ),
    )
    wrong_root = output_parent / "unregistered-r6-output"

    exit_code = r6.main(["--run-dir", str(wrong_root), "--dry-run"])

    assert exit_code == 4
    assert not wrong_root.exists()
    failure_parent = _pre_root_failure_parent(output_parent)
    failures = list(failure_parent.glob("output_root_validation.*.failure.json"))
    assert len(failures) == 1


def test_reproduction_child_topology_is_exact(
    monkeypatch: pytest.MonkeyPatch, writable_workspace: Path
) -> None:
    workspace = writable_workspace / "workspace"
    output_parent = workspace / "artifacts" / "calibration"
    reproduction_parent = (
        output_parent / r6.IMPLEMENTED_OUTPUT_LEAVES["reproduction_local"]
    )
    reproduction_parent.mkdir(parents=True)
    monkeypatch.setattr(r6, "WORKSPACE", workspace)

    process_a = reproduction_parent / "process_a"
    args = r6.build_parser().parse_args(["--run-dir", str(process_a)])
    assert r6._output_root_contract(args)["passed"]
    assert r6._output_root_contract(args)["reproduction_child"] is True

    process_c = reproduction_parent / "process_c"
    args.run_dir = process_c
    assert not r6._output_root_contract(args)["passed"]

    wrong_parent = output_parent / "unregistered-reproduction" / "process_a"
    wrong_parent.parent.mkdir()
    args.run_dir = wrong_parent
    assert not r6._output_root_contract(args)["passed"]


def test_dry_run_ledger_contains_no_registered_split() -> None:
    ledger = _dry_run_ledger()
    manifests = {
        "clean": {"audit_fixture": {}},
        "challenge": {"audit_fixture": {}},
    }

    gate = r6._dry_run_access_ledger_gate(ledger, manifests)

    assert gate["passed"]
    assert {entry["split"] for entry in ledger} == {
        "literal_audit_fixture",
        "frozen_fixture_audit",
    }
    assert not {"train", "inner_development", "development"}.intersection(
        entry["split"] for entry in ledger
    )
    assert all(isinstance(row, list) for row in gate["expected_prefix"])
    assert all(isinstance(row, list) for row in gate["observed_prefix"])


def test_real_dry_run_terminal_summary_survives_production_json_round_trip(
    monkeypatch: pytest.MonkeyPatch,
    writable_workspace: Path,
) -> None:
    run_dir = writable_workspace / "dry-summary-only"
    args = r6.build_parser().parse_args(["--run-dir", str(run_dir), "--dry-run"])
    args._raw_argv = ["--run-dir", str(run_dir), "--dry-run"]
    args._entry_evidence = {
        "captured_utc": r6._utc_now(),
        "raw_argv": list(args._raw_argv),
    }
    registry = copy.deepcopy(r6.FROZEN_R6_REGISTRY)
    structural_report = r6.run_r6_structural_audits(
        r6._new_matcher(r6.TRAINABLE_SEEDS[0])
    )
    structural_contract = registry["structural_microcase_contract"]
    structural_contract["expected_runtime_report_sha256"] = structural_report[
        "audit_sha256"
    ]
    structural_contract["expected_ordered_microcase_projection_sha256"] = (
        structural_report["ordered_microcase_projection_sha256"]
    )
    monkeypatch.setattr(r6, "FROZEN_R6_REGISTRY", registry)
    config = r6._registered_config(
        seeds=r6.TRAINABLE_SEEDS,
        actual_steps=r6.REGISTERED_STEPS,
        smoke=False,
        dry_run=True,
    )
    source_manifest = _closed_manifest()
    args._preflight_bundle = {
        "source_manifest": source_manifest,
        "config": config,
        "runtime_environment": r6._runtime_environment(),
        "resolution_gate": {
            "status": "PASS",
            "passed": True,
            "checks": {"injected_frozen_authority": True},
        },
    }

    summary = r6.run(args)
    serialized = json.dumps(summary, indent=2, sort_keys=True)
    persisted = json.loads(serialized)
    validation = r6._strict_summary_validation(persisted)

    assert persisted["status"] == r6.IMPLEMENTED_STATUS_VOCABULARY["dry_run_success"]
    assert validation["passed"], validation["errors"]
    metric_certificate = r6.validate_r6_metric_evidence(persisted)
    assert metric_certificate["validated"]

    evidence = persisted["structural_input_gate"]["r6_gate1_evidence"]
    r6.validate_r6_structural_audit(evidence["structural_microcases"])
    r6.validate_r6_counterfactual_audit(evidence["full_chain_counterfactual"])

    assert [record["name"] for record in persisted["completed_gates"]] == list(
        r6.GATE_ORDER[:3]
    )
    assert all(record["passed"] is True for record in persisted["completed_gates"])
    assert persisted["not_run_gates"] == list(r6.GATE_ORDER[3:])
    assert persisted["training_allowed"] is False
    assert persisted["stopped_at_gate"] is None
    assert persisted["dry_run_data_access_gate"]["passed"] is True
    assert persisted["formal_test_used"] is False
    assert persisted["formal_claim_allowed"] is False
    assert persisted["formal_ablation_claim_allowed"] is False
    assert persisted["full_method_claim_allowed"] is False
    assert persisted["formal_data_authorization"] == "HOLD"

    ledger_shape = [
        (entry["gate"], entry["stratum"], entry["split"])
        for entry in persisted["data_access_ledger"]
    ]
    assert ledger_shape == [
        ("structural_input", "clean", "literal_audit_fixture"),
        ("structural_input", "challenge", "literal_audit_fixture"),
        ("fixture_identifiability", "clean", "frozen_fixture_audit"),
        ("fixture_identifiability", "challenge", "frozen_fixture_audit"),
    ]
    assert not {"train", "inner_development", "development"}.intersection(
        entry["split"] for entry in persisted["data_access_ledger"]
    )


def test_main_revalidates_sorted_json_round_trip_before_publishing_success(
    monkeypatch: pytest.MonkeyPatch, writable_workspace: Path
) -> None:
    workspace = writable_workspace / "serialized-roundtrip-workspace"
    output_parent = workspace / "artifacts" / "calibration"
    output_parent.mkdir(parents=True)
    monkeypatch.setattr(r6, "WORKSPACE", workspace)

    source = _closed_manifest()
    monkeypatch.setattr(r6, "_source_manifest", lambda: copy.deepcopy(source))
    monkeypatch.setattr(r6, "_runtime_environment", lambda: {})
    monkeypatch.setattr(r6, "_registered_config", lambda **_kwargs: {})
    monkeypatch.setattr(
        r6,
        "_resolution_gate",
        lambda *_args, **_kwargs: {
            "status": "PASS",
            "passed": True,
            "checks": {"frozen_authority": True},
        },
    )
    monkeypatch.setattr(r6, "_phase_authorize", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        r6, "_final_publication_authority_recheck", lambda _source: None
    )

    summary = {
        "status": r6.IMPLEMENTED_STATUS_VOCABULARY["dry_run_success"],
        "formal_claim_allowed": False,
        "serialization_order_probe": {"z": 1, "a": 2},
    }
    monkeypatch.setattr(r6, "run", lambda _args: copy.deepcopy(summary))

    observed_orders: list[list[str]] = []

    def strict_validation(candidate: dict[str, object]) -> dict[str, object]:
        order = list(candidate["serialization_order_probe"])
        observed_orders.append(order)
        passed = order == ["z", "a"]
        return {
            "passed": passed,
            "errors": []
            if passed
            else [
                {
                    "pointer": "/serialization_order_probe",
                    "rule": "serialized-roundtrip probe",
                    "observed_value": order,
                }
            ],
        }

    monkeypatch.setattr(r6, "_strict_summary_validation", strict_validation)
    run_dir = output_parent / r6.IMPLEMENTED_OUTPUT_LEAVES["dry_run"]

    exit_code = r6.main(["--run-dir", str(run_dir), "--dry-run"])

    assert exit_code == 4
    assert observed_orders == [["z", "a"], ["a", "z"]]
    assert not (run_dir / "summary.json").exists()
    failure = json.loads((run_dir / "failure.json").read_text(encoding="utf-8"))
    assert failure["status"] == r6.IMPLEMENTED_STATUS_VOCABULARY["technical_failure"]
    assert failure["stage"] == "summary_postserialization_validation"
    assert failure["exception_type"] == "RuntimeError"
    assert "postserialized summary validation failed" in failure["exception_message"]
    assert failure["summary_written"] is False
    assert failure["formal_claim_allowed"] is False


def test_main_serializes_summary_once_and_publishes_the_validated_exact_bytes(
    monkeypatch: pytest.MonkeyPatch, writable_workspace: Path
) -> None:
    workspace = writable_workspace / "exact-summary-bytes-workspace"
    output_parent = workspace / "artifacts" / "calibration"
    output_parent.mkdir(parents=True)
    monkeypatch.setattr(r6, "WORKSPACE", workspace)

    source = _closed_manifest()
    monkeypatch.setattr(r6, "_source_manifest", lambda: copy.deepcopy(source))
    monkeypatch.setattr(r6, "_runtime_environment", lambda: {})
    monkeypatch.setattr(r6, "_registered_config", lambda **_kwargs: {})
    monkeypatch.setattr(
        r6,
        "_resolution_gate",
        lambda *_args, **_kwargs: {
            "status": "PASS",
            "passed": True,
            "checks": {"frozen_authority": True},
        },
    )
    monkeypatch.setattr(r6, "_phase_authorize", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        r6, "_final_publication_authority_recheck", lambda _source: None
    )

    summary = {
        "status": r6.IMPLEMENTED_STATUS_VOCABULARY["dry_run_success"],
        "formal_claim_allowed": False,
        "serialization_order_probe": {"z": "中文", "a": 2},
    }
    monkeypatch.setattr(r6, "run", lambda _args: copy.deepcopy(summary))

    observed_orders: list[list[str]] = []

    def strict_validation(candidate: dict[str, object]) -> dict[str, object]:
        observed_orders.append(list(candidate["serialization_order_probe"]))
        return {"passed": True, "errors": []}

    monkeypatch.setattr(r6, "_strict_summary_validation", strict_validation)
    production_serializer = r6._serialize_json_bytes
    serialized_payloads: list[bytes] = []

    def serialize_once(candidate: dict[str, object]) -> bytes:
        payload = production_serializer(candidate)
        serialized_payloads.append(payload)
        return payload

    monkeypatch.setattr(r6, "_serialize_json_bytes", serialize_once)
    run_dir = output_parent / r6.IMPLEMENTED_OUTPUT_LEAVES["dry_run"]

    exit_code = r6.main(["--run-dir", str(run_dir), "--dry-run"])

    expected = (
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")
    assert exit_code == 0
    assert observed_orders == [["z", "a"], ["a", "z"]]
    assert serialized_payloads == [expected]
    assert (run_dir / "summary.json").read_bytes() == expected
    assert expected.endswith(b"\n") and not expected.endswith(b"\n\n")
    assert json.loads(expected) == summary
    assert not (run_dir / "failure.json").exists()


def test_final_publication_recheck_rejects_source_drift(
    monkeypatch: pytest.MonkeyPatch, writable_workspace: Path
) -> None:
    monkeypatch.setattr(r6, "WORKSPACE", writable_workspace)
    source = _closed_manifest()
    drifted = copy.deepcopy(source)
    drifted["files"]["scripts/run_query_anchor_r4.py"] = "f" * 64
    drifted["source_manifest_authority_sha256"] = r6._json_hash(
        r6._source_manifest_authority_payload(drifted)
    )
    monkeypatch.setattr(r6, "_source_manifest", lambda: drifted)
    monkeypatch.setattr(
        r6,
        "_safe_workspace_read_bytes",
        lambda _path: r6.R9_PROTOCOL_PATH.read_bytes(),
    )

    with pytest.raises(RuntimeError, match="source/import manifest drifted"):
        r6._final_publication_authority_recheck(source)


def test_main_rejects_dotdot_before_resolving_output_path(
    monkeypatch: pytest.MonkeyPatch, writable_workspace: Path
) -> None:
    workspace = writable_workspace / "lexical-workspace"
    parent = workspace / "artifacts" / "calibration"
    parent.mkdir(parents=True)
    monkeypatch.setattr(r6, "WORKSPACE", workspace)
    leaf = r6.IMPLEMENTED_OUTPUT_LEAVES["dry_run"]
    requested = parent / "dummy" / ".." / leaf

    exit_code = r6.main(["--run-dir", str(requested), "--dry-run"])

    assert exit_code == 4
    assert not (parent / leaf).exists()
    failures = list(
        _pre_root_failure_parent(parent).glob("output_root_validation.*.failure.json")
    )
    assert len(failures) == 1


@pytest.mark.parametrize(
    "registered_split", ["train", "inner_development", "development"]
)
def test_dry_run_ledger_rejects_registered_split(registered_split: str) -> None:
    ledger = _dry_run_ledger()
    ledger[-1]["split"] = registered_split
    manifests = {
        "clean": {"audit_fixture": {}},
        "challenge": {"audit_fixture": {}},
    }

    gate = r6._dry_run_access_ledger_gate(ledger, manifests)

    assert not gate["passed"]
    assert not gate["checks"]["registered_access_prefix_exact"]


@pytest.mark.parametrize(
    ("mutation", "expected_pointer"),
    [
        ("uppercase_hash", "/config_sha256"),
        ("uuid_non_v4", "/provenance/process_uuid"),
        ("utc_non_z", "/provenance/end_utc"),
        ("bool_as_int", "/provenance/monotonic_elapsed_seconds"),
    ],
)
def test_strict_summary_rejects_malicious_scalar_encodings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mutation: str,
    expected_pointer: str,
) -> None:
    summary = copy.deepcopy(_resolution_stop_summary(monkeypatch, tmp_path))
    if mutation == "uppercase_hash":
        summary["config_sha256"] = str(summary["config_sha256"]).upper()
    elif mutation == "uuid_non_v4":
        summary["provenance"]["process_uuid"] = str(
            uuid.uuid3(uuid.NAMESPACE_DNS, "r6")
        )
    elif mutation == "utc_non_z":
        summary["provenance"]["end_utc"] = str(
            summary["provenance"]["end_utc"]
        ).replace("Z", "+00:00")
    elif mutation == "bool_as_int":
        summary["provenance"]["monotonic_elapsed_seconds"] = True
    else:  # pragma: no cover - parametrization is closed above.
        raise AssertionError(f"unknown mutation: {mutation}")

    validation = r6._strict_summary_validation(summary)

    assert not validation["passed"]
    assert expected_pointer in {error["pointer"] for error in validation["errors"]}


def test_stopped_summary_rejects_later_gate_field_leakage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    summary = copy.deepcopy(_resolution_stop_summary(monkeypatch, tmp_path))
    summary["structural_input_gate"] = {"status": "PASS", "passed": True}

    validation = r6._strict_summary_validation(summary)

    assert not validation["passed"]
    key_errors = [error for error in validation["errors"] if error["pointer"] == ""]
    assert key_errors
    assert "structural_input_gate" in key_errors[0]["observed_value"]


def test_atomic_publish_never_overwrites_existing_evidence(
    writable_workspace: Path,
) -> None:
    destination = writable_workspace / "summary.json"
    first = {"status": "FIRST", "evidence": [1, 2, 3]}
    second = {"status": "FORGED_OVERWRITE"}

    r6._atomic_write_json_new(destination, first)
    original_bytes = destination.read_bytes()

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        r6._atomic_write_json_new(destination, second)

    assert destination.read_bytes() == original_bytes
    assert "FIRST" in destination.read_text(encoding="utf-8")
    assert "FORGED_OVERWRITE" not in destination.read_text(encoding="utf-8")
    assert not list(writable_workspace.glob(".*.tmp"))


def test_atomic_json_publish_rejects_nonfinite_values_without_artifact(
    writable_workspace: Path,
) -> None:
    destination = writable_workspace / "summary.json"

    with pytest.raises(ValueError, match="Out of range float values"):
        r6._atomic_write_json_new(destination, {"metric": float("nan")})

    assert not destination.exists()
    assert not list(writable_workspace.glob(".*.tmp"))
