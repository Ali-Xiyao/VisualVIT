import torch

from scripts.cache_r37_block8_tokens import (
    contiguous_part_bounds,
    forward_to_block8,
    visual_state_dict,
)


class AddOne(torch.nn.Module):
    def forward(self, value):
        return value + 1


class DummyEncoder(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.patch_embed = torch.nn.Identity()
        self.patch_drop = torch.nn.Identity()
        self.norm_pre = torch.nn.Identity()
        self.blocks = torch.nn.ModuleList(AddOne() for _ in range(12))

    def _pos_embed(self, value):
        return value


def test_forward_stops_after_exactly_eight_blocks():
    value = torch.zeros(2, 197, 768)
    observed = forward_to_block8(DummyEncoder(), value)
    assert torch.equal(observed, torch.full_like(value, 8))


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


def test_contiguous_parts_cover_inventory_without_overlap():
    assert contiguous_part_bounds(5, 0, 2) == (0, 2)
    assert contiguous_part_bounds(5, 1, 2) == (2, 5)
