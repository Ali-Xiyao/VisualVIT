from __future__ import annotations

import json
from pathlib import Path

import pytest
import torch
from PIL import Image

from scripts import run_chextemporal_mimic_matcher_qualification as runner


def _args(protocol: Path, certificate: Path, launcher_result: Path):
    return type(
        "Args",
        (),
        {
            "r24_protocol": protocol,
            "r24_certificate": certificate,
            "r24_launcher_result": launcher_result,
        },
    )()


def test_r24_prerequisite_accepts_exact_terminal_green_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protocol = tmp_path / "protocol.md"
    certificate = tmp_path / "certificate.json"
    launcher_result = tmp_path / "launcher.json"
    protocol.write_text("frozen", encoding="utf-8")
    gate = {
        "passed": True,
        "checks": {f"check_{index}": True for index in range(11)},
        "mismatch_count": 0,
        "mismatch_paths": [],
        "primary_canonical_sha256": "a" * 64,
        "replica_canonical_sha256": "a" * 64,
        "comparison_excludes_only": runner.R24_EXPECTED_COMPARISON_EXCLUSIONS,
    }
    certificate.write_text(
        json.dumps(
            {
                "status": "PASS_R24_SYNTHETIC_ENGINEERING",
                "independent_reproduction_gate": gate,
            }
        ),
        encoding="utf-8",
    )
    launcher_result.write_text(
        json.dumps({"exit_code": 0, "retry_attempted": False}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        runner,
        "R24_PREREQUISITE_PINS",
        {
            "protocol": runner.sha256_file(protocol),
            "certificate": runner.sha256_file(certificate),
            "launcher_result": runner.sha256_file(launcher_result),
        },
    )

    ledger = runner._validate_r24_prerequisite(
        _args(protocol, certificate, launcher_result)
    )

    assert set(ledger) == {"protocol", "certificate", "launcher_result"}


@pytest.mark.parametrize("mutation", ["mismatch", "failed_check", "retried"])
def test_r24_prerequisite_mutations_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    protocol = tmp_path / "protocol.md"
    certificate = tmp_path / "certificate.json"
    launcher_result = tmp_path / "launcher.json"
    protocol.write_text("frozen", encoding="utf-8")
    gate = {
        "passed": True,
        "checks": {f"check_{index}": True for index in range(11)},
        "mismatch_count": 0,
        "mismatch_paths": [],
        "primary_canonical_sha256": "a" * 64,
        "replica_canonical_sha256": "a" * 64,
        "comparison_excludes_only": runner.R24_EXPECTED_COMPARISON_EXCLUSIONS,
    }
    if mutation == "mismatch":
        gate["mismatch_count"] = 1
        gate["mismatch_paths"] = ["/forged"]
    elif mutation == "failed_check":
        gate["checks"]["check_0"] = False
    certificate.write_text(
        json.dumps(
            {
                "status": "PASS_R24_SYNTHETIC_ENGINEERING",
                "independent_reproduction_gate": gate,
            }
        ),
        encoding="utf-8",
    )
    launcher_result.write_text(
        json.dumps({"exit_code": 0, "retry_attempted": mutation == "retried"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        runner,
        "R24_PREREQUISITE_PINS",
        {
            "protocol": runner.sha256_file(protocol),
            "certificate": runner.sha256_file(certificate),
            "launcher_result": runner.sha256_file(launcher_result),
        },
    )

    with pytest.raises(RuntimeError, match="terminally green"):
        runner._validate_r24_prerequisite(_args(protocol, certificate, launcher_result))


def test_real_region_batch_assigns_unique_cross_temporal_source_ids() -> None:
    prior_path = "prior.png"
    current_path = "current.png"
    prior_boxes = [
        {"label": "Box1", "x1": 0.0, "y1": 0.0, "x2": 10.0, "y2": 10.0},
        {"label": "Box2", "x1": 10.0, "y1": 10.0, "x2": 20.0, "y2": 20.0},
    ]
    current_boxes = [
        {"label": "Box1", "x1": 1.0, "y1": 1.0, "x2": 11.0, "y2": 11.0},
        {"label": "Box3", "x1": 20.0, "y1": 20.0, "x2": 30.0, "y2": 30.0},
    ]
    record = {
        "prior_path": prior_path,
        "current_path": current_path,
        "prior_boxes": prior_boxes,
        "current_boxes": current_boxes,
    }
    features = {runner._crop_key(prior_path, box): torch.ones(4) for box in prior_boxes}
    features.update(
        {runner._crop_key(current_path, box): torch.ones(4) for box in current_boxes}
    )

    regions = runner._region_batch(record, features, "visual_only")
    source_ids = torch.cat(
        (regions.prior_source_ids, regions.current_source_ids), dim=1
    )

    assert source_ids.tolist() == [[0, 1, 2, 3]]
    assert len(source_ids.unique()) == source_ids.numel()


@pytest.mark.parametrize("empty_side", ["prior", "current"])
def test_real_region_batch_supports_two_sided_null_endpoints(
    empty_side: str,
) -> None:
    prior_path = "prior.png"
    current_path = "current.png"
    box = {"label": "Box1", "x1": 0.0, "y1": 0.0, "x2": 10.0, "y2": 10.0}
    record = {
        "prior_path": prior_path,
        "current_path": current_path,
        "prior_boxes": [] if empty_side == "prior" else [box],
        "current_boxes": [] if empty_side == "current" else [box],
    }
    populated_path = current_path if empty_side == "prior" else prior_path
    features = {runner._crop_key(populated_path, box): torch.ones(4)}

    regions = runner._region_batch(record, features, "visual_geometry_equal")

    assert tuple(regions.prior_features.shape) == (
        1,
        len(record["prior_boxes"]),
        10,
    )
    assert tuple(regions.current_features.shape) == (
        1,
        len(record["current_boxes"]),
        10,
    )
    assert tuple(regions.prior_boxes.shape) == (
        1,
        len(record["prior_boxes"]),
        4,
    )
    assert tuple(regions.current_boxes.shape) == (
        1,
        len(record["current_boxes"]),
        4,
    )
    regions.validate()


def test_feature_repeat_uses_same_registered_batch_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image_path = tmp_path / "image.png"
    Image.new("RGB", (224, 224), color=(128, 128, 128)).save(image_path)
    boxes = [
        {
            "label": f"Box{index}",
            "x1": float(index),
            "y1": float(index),
            "x2": float(index + 20),
            "y2": float(index + 20),
        }
        for index in range(3)
    ]
    records = [
        {
            "prior_path": str(image_path),
            "current_path": str(image_path),
            "prior_boxes": boxes,
            "current_boxes": [],
        }
    ]

    class BatchShapeSensitiveEncoder(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.batch_sizes: list[int] = []

        def forward_features(self, batch: torch.Tensor) -> torch.Tensor:
            self.batch_sizes.append(len(batch))
            value = torch.full(
                (len(batch), 1, 4),
                float(len(batch)),
                dtype=batch.dtype,
                device=batch.device,
            )
            return value

    model = BatchShapeSensitiveEncoder()
    monkeypatch.setattr(torch.cuda, "reset_peak_memory_stats", lambda _device: None)
    monkeypatch.setattr(torch.cuda, "synchronize", lambda _device: None)

    _, ledger, _, repeat_difference = runner._extract_features(
        records,
        model,
        torch.device("cpu"),
        batch_size=2,
    )

    assert len(ledger) == 3
    assert model.batch_sizes == [2, 1, 2]
    assert repeat_difference == 0.0
