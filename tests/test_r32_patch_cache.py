import torch

from scripts.cache_r32_patch_tokens import image_inventory, visual_state_dict


def test_inventory_deduplicates_timepoint_images():
    rows = [
        {
            "partition": "train",
            "prior_dicom_id": "a",
            "prior_path": "a.jpg",
            "current_dicom_id": "b",
            "current_path": "b.jpg",
        },
        {
            "partition": "dev",
            "prior_dicom_id": "b",
            "prior_path": "b.jpg",
            "current_dicom_id": "c",
            "current_path": "c.jpg",
        },
    ]
    assert image_inventory(rows) == [
        {"dicom_id": "a", "path": "a.jpg"},
        {"dicom_id": "b", "path": "b.jpg"},
        {"dicom_id": "c", "path": "c.jpg"},
    ]


def test_visual_state_dict_strips_only_visual_trunk():
    checkpoint = {
        **{
            f"visual.trunk.k{index}": torch.tensor(index)
            for index in range(150)
        },
        "visual.head.proj.weight": torch.tensor(1),
        "text.transformer.x": torch.tensor(2),
    }
    state = visual_state_dict(checkpoint)
    assert len(state) == 150
    assert "k0" in state
    assert all(not key.startswith("visual.") for key in state)
