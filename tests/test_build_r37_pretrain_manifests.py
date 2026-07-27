from pathlib import Path

import pandas as pd

from scripts.build_r37_pretrain_manifests import (
    build_forbidden_registry,
    build_pair_records,
    image_path,
    mimic_patient_id,
    patient_partition,
    report_path,
    select_one_frontal_per_study,
)


def test_patient_partition_is_deterministic_and_patient_level():
    assert patient_partition("p100") == patient_partition("p100")
    assert patient_partition("p100") in {"pretrain", "internal_calibration"}
    assert mimic_patient_id("100") == mimic_patient_id("p100")


def test_mimic_paths_follow_official_layout():
    root = Path("dataset")
    assert image_path(root, 10001234, 555, "abc") == (
        root / "p10/p10001234/s555/abc.jpg"
    )
    assert report_path(root, 10001234, 555) == (
        root / "p10/p10001234/s555.txt"
    )


def test_selects_pa_before_ap_and_official_train_only():
    metadata = pd.DataFrame(
        [
            {
                "dicom_id": "ap",
                "subject_id": "100",
                "study_id": "10",
                "ViewPosition": "AP",
                "StudyDate": 20200101,
                "StudyTime": 100000,
            },
            {
                "dicom_id": "pa",
                "subject_id": "100",
                "study_id": "10",
                "ViewPosition": "PA",
                "StudyDate": 20200101,
                "StudyTime": 100000,
            },
            {
                "dicom_id": "test",
                "subject_id": "200",
                "study_id": "20",
                "ViewPosition": "PA",
                "StudyDate": 20200101,
                "StudyTime": 100000,
            },
        ]
    )
    split = pd.DataFrame(
        [
            {
                "dicom_id": "ap",
                "subject_id": "100",
                "study_id": "10",
                "split": "train",
            },
            {
                "dicom_id": "pa",
                "subject_id": "100",
                "study_id": "10",
                "split": "train",
            },
            {
                "dicom_id": "test",
                "subject_id": "200",
                "study_id": "20",
                "split": "test",
            },
        ]
    )
    selected = select_one_frontal_per_study(metadata, split)
    assert selected["dicom_id"].tolist() == ["pa"]


def test_pair_builder_excludes_forbidden_and_same_day(tmp_path):
    studies = pd.DataFrame(
        [
            {
                "dicom_id": "a",
                "subject_id": "100",
                "study_id": "1",
                "ViewPosition": "PA",
                "StudyDate": 20200101,
                "StudyTime": 100000,
                "split": "train",
            },
            {
                "dicom_id": "b",
                "subject_id": "100",
                "study_id": "2",
                "ViewPosition": "PA",
                "StudyDate": 20200102,
                "StudyTime": 100000,
                "split": "train",
            },
            {
                "dicom_id": "c",
                "subject_id": "200",
                "study_id": "3",
                "ViewPosition": "AP",
                "StudyDate": 20200101,
                "StudyTime": 100000,
                "split": "train",
            },
            {
                "dicom_id": "d",
                "subject_id": "200",
                "study_id": "4",
                "ViewPosition": "AP",
                "StudyDate": 20200101,
                "StudyTime": 120000,
                "split": "train",
            },
        ]
    )
    rows, diagnostics = build_pair_records(
        studies,
        forbidden_patients={mimic_patient_id("100")},
        image_root=tmp_path,
        report_root=tmp_path,
        check_paths=False,
    )
    assert rows == []
    assert diagnostics["excluded_frontal_study_rows"] == 2
    assert diagnostics["same_or_nonpositive_date_pairs"] == 1


def test_registry_projects_only_ids_and_refuses_sealed_label_path(tmp_path):
    train_dev = tmp_path / "train_dev.json"
    sealed = tmp_path / "sealed.json"
    gold = tmp_path / "gold.json"
    train_dev.write_text(
        "["
        + ",".join(
            [
                f'{{"patient_id":"p{index}","partition":"train","progression":"X"}}'
                for index in range(1574)
            ]
            + [
                f'{{"patient_id":"p{2000 + index}","partition":"dev","progression":"Y"}}'
                for index in range(300)
            ]
        )
        + "]",
        encoding="utf-8",
    )
    sealed.write_text(
        "["
        + ",".join(
            f'{{"patient_id":"p{3000 + index}","partition":"sealed_vlm_test"}}'
            for index in range(483)
        )
        + "]",
        encoding="utf-8",
    )
    gold.write_text(
        '{"patient_ids":["p9999"],"patient_count":1}', encoding="utf-8"
    )
    registry, forbidden = build_forbidden_registry(
        train_dev_path=train_dev,
        sealed_manifest_path=sealed,
        gold_manifest_path=gold,
    )
    assert registry["outcome_fields_read"] == []
    assert registry["sealed_label_file_opened"] is False
    assert len(forbidden) == 1574 + 300 + 483 + 1
