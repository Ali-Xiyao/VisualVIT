from scripts import build_r32_tier_cxr_cohort as r32


def _records():
    records = []
    splits = ("train", "dev", "sealed_vlm_test")
    for index, split in enumerate(splits):
        for label_index, label in enumerate(r32.LABELS):
            records.append(
                {
                    "patient_id": f"p{index}-{label_index}",
                    "partition": split,
                    "progression": label,
                    "prior_study_id": f"ps{index}-{label_index}",
                    "current_study_id": f"cs{index}-{label_index}",
                    "prior_dicom_id": f"pi{index}-{label_index}",
                    "current_dicom_id": f"ci{index}-{label_index}",
                }
            )
    return records


def test_split_assignment_is_deterministic_and_exact(monkeypatch):
    monkeypatch.setattr(
        r32,
        "SPLIT_COUNTS",
        {"train": 4, "dev": 2, "sealed_vlm_test": 1},
    )
    patients = [f"patient{index}" for index in range(7)]
    first = r32.assign_patients(patients)
    second = r32.assign_patients(reversed(patients))
    assert first == second
    assert list(first.values()).count("train") == 4
    assert list(first.values()).count("dev") == 2
    assert list(first.values()).count("sealed_vlm_test") == 1


def test_cross_split_overlap_detects_study_or_image_leakage():
    records = _records()
    assert r32.cross_split_overlap(records, "patient_id") == 0
    records[-1]["prior_dicom_id"] = records[0]["prior_dicom_id"]
    assert r32.cross_split_overlap(records, "prior_dicom_id") == 1
