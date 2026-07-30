import json

import pytest

from scripts.run_prta_gen_r40b_overfit_smoke import (
    build_prompt_ids,
    gate_passed,
    parse_generated_object,
    progression_first_token_registry,
    result_status,
    target_ids_and_progression_mask,
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


class _BatchEncodingTokenizer:
    def apply_chat_template(self, *args, **kwargs):
        del args, kwargs
        return {"input_ids": [1, *([31] * 64), 2]}


def test_prompt_accepts_transformers_batch_encoding_shape():
    prompt = build_prompt_ids(
        _BatchEncodingTokenizer(),
        {
            "model": {
                "sentinel_token": "<placeholder>",
                "token_budget": 64,
                "placeholder_token_id": 31,
            },
            "prompt": {
                "system": "system",
                "user_prefix": "{finding}",
                "add_generation_prompt": True,
            },
        },
        finding="Edema",
    )
    assert prompt.shape == (1, 66)
    assert int(prompt.eq(31).sum()) == 64


def test_result_status_uses_new_stage_registry():
    config = {
        "result_statuses": {
            "pass": "PASS_NEW",
            "contract_stop": "STOP_CONTRACT",
            "underfit_by_attempt": {"attempt": "STOP_UNDERFIT"},
        }
    }
    assert result_status(config, "pass", "attempt") == "PASS_NEW"
    assert (
        result_status(config, "contract_stop", "attempt")
        == "STOP_CONTRACT"
    )
    assert (
        result_status(config, "underfit", "attempt") == "STOP_UNDERFIT"
    )


class _OffsetTokenizer:
    eos_token_id = 99

    def __call__(self, text, **kwargs):
        del kwargs
        return {
            "input_ids": [ord(character) for character in text],
            "offset_mapping": [
                (index, index + 1) for index in range(len(text))
            ],
        }


def test_progression_mask_selects_only_value_characters():
    text = '{"finding":"Edema","progression":"New"}'
    ids, mask = target_ids_and_progression_mask(
        _OffsetTokenizer(),
        {"target": {"append_eos": True}},
        target_text=text,
    )
    selected = [text[index] for index in range(len(text)) if mask[index]]
    assert "".join(selected) == "New"
    assert ids[-1] == 99
    assert not bool(mask[-1])


def test_progression_first_tokens_are_unique_after_shared_prefix():
    prefix, first_tokens = progression_first_token_registry(
        _OffsetTokenizer(),
        {
            "target": {
                "append_eos": True,
                "progression_values": [
                    "Stable",
                    "Improved",
                    "Worse",
                    "New",
                    "Resolved",
                ],
            }
        },
        finding="Edema",
    )
    assert prefix
    assert first_tokens == [ord("S"), ord("I"), ord("W"), ord("N"), ord("R")]
