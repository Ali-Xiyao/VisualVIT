from pathlib import Path

from scripts.run_r37_formal_bundle_pipeline import (
    build_tasks,
    process_alive,
)


def _spec():
    return {
        "training": {
            "epochs": 3,
            "batch_size": 2,
            "learning_rate": 0.0001,
            "adapter_rank": 32,
        },
        "artifacts": {
            "formal_output_root": r"H:\runtime\a6",
            "transition_root": r"H:\runtime\transitions",
            "block8_cache_root": r"H:\runtime\block8",
            "text_cache": r"H:\runtime\text.pt",
            "cmcp_index": r"H:\runtime\cmcp.json",
        },
        "baseline_a0": {
            "formal_output_root": r"H:\runtime\a0",
            "epochs": 100,
            "batch_size": 16,
            "learning_rate": 0.01,
        },
    }


def test_build_tasks_freezes_two_gpu_lane_order_and_arguments():
    lanes = build_tasks(_spec(), python="python.exe")
    assert [task.key for task in lanes[0]] == [
        "a6_seed_17",
        "a6_seed_43",
        "a0_seed_17",
        "a0_seed_43",
    ]
    assert [task.key for task in lanes[1]] == ["a6_seed_29", "a0_seed_29"]
    assert {task.device for task in lanes[0]} == {0}
    assert {task.device for task in lanes[1]} == {1}
    for task in [*lanes[0], *lanes[1]]:
        command = list(task.command)
        assert "--formal" in command
        assert "--max-train-examples" in command
        assert command[command.index("--max-train-examples") + 1] == "0"
        assert command[command.index("--max-calibration-examples") + 1] == "0"
        assert str(task.output_root) == command[-1]


def test_a6_and_a0_frozen_settings_are_distinct():
    lanes = build_tasks(_spec(), python="python.exe")
    tasks = {task.key: list(task.command) for lane in lanes.values() for task in lane}
    a6 = tasks["a6_seed_17"]
    a0 = tasks["a0_seed_17"]
    assert a6[a6.index("--epochs") + 1] == "3"
    assert a6[a6.index("--batch-size") + 1] == "2"
    assert a6[a6.index("--adapter-rank") + 1] == "32"
    assert a0[a0.index("--epochs") + 1] == "100"
    assert a0[a0.index("--batch-size") + 1] == "16"
    assert "--adapter-rank" not in a0


def test_process_alive_rejects_impossible_pid():
    assert process_alive(-1) is False
    assert process_alive(999_999_999) is False


def test_output_roots_are_seed_isolated():
    lanes = build_tasks(_spec(), python="python.exe")
    roots = [task.output_root for lane in lanes.values() for task in lane]
    assert len(roots) == len(set(roots))
    assert all(isinstance(root, Path) for root in roots)
