import json

import pytest

from scripts.run_prta_gen_r40b_overfit_smoke import (
    gate_passed,
    parse_generated_object,
    validate_attempt_authority,
)


def _config():
    return {
        "attempt_order": [
            {"name": "first"},
            {"name": "second", "allowed_only_after": "STOP_FIRST"},
        ],
        "gate": {
            "final_to_initial_loss_ratio_at_most": 0.9,
            "teacher_forced_token_accuracy_at_least": 0.95,
            "generated_schema_validity": 1.0,
            "generated_finding_echo_accuracy": 1.0,
            "generated_progression_accuracy": 1.0,
        },
    }


def test_parse_generated_object_requires_exact_key_order_and_enum():
    parsed = parse_generated_object(
        '{"finding":"Edema","progression":"New"}',
        expected_keys=["finding", "progression"],
        progression_values={"Stable", "New"},
    )
    assert parsed == {"finding": "Edema", "progression": "New"}
    assert (
        parse_generated_object(
            '{"progression":"New","finding":"Edema"}',
            expected_keys=["finding", "progression"],
            progression_values={"Stable", "New"},
        )
        is None
    )
    assert (
        parse_generated_object(
            '{"finding":"Edema","progression":"Unknown"}',
            expected_keys=["finding", "progression"],
            progression_values={"Stable", "New"},
        )
        is None
    )


def test_retry_requires_exact_registered_underfit_receipt(tmp_path):
    runtime = tmp_path / "runtime"
    previous = runtime / "first"
    previous.mkdir(parents=True)
    (previous / "result.json").write_text(
        json.dumps({"status": "WRONG_STOP"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(PermissionError, match="registered underfit STOP"):
        validate_attempt_authority(
            config=_config(),
            attempt_name="second",
            runtime_root=runtime,
        )
    (previous / "result.json").write_text(
        json.dumps({"status": "STOP_FIRST"}) + "\n",
        encoding="utf-8",
    )
    assert (
        validate_attempt_authority(
            config=_config(),
            attempt_name="second",
            runtime_root=runtime,
        )["name"]
        == "second"
    )


def test_gate_requires_contract_loss_accuracy_and_generation():
    config = _config()
    assert gate_passed(
        config=config,
        initial={"mean_loss": 2.0},
        final={"mean_loss": 1.0, "token_accuracy": 0.96},
        generated={
            "schema_validity": 1.0,
            "finding_echo_accuracy": 1.0,
            "progression_accuracy": 1.0,
        },
        engineering_contract_passed=True,
    )
    assert not gate_passed(
        config=config,
        initial={"mean_loss": 2.0},
        final={"mean_loss": 1.0, "token_accuracy": 0.94},
        generated={
            "schema_validity": 1.0,
            "finding_echo_accuracy": 1.0,
            "progression_accuracy": 1.0,
        },
        engineering_contract_passed=True,
    )
