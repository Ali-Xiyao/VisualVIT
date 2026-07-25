import torch

from visualvit.synthetic import order_swap_label


def test_order_swap_label_is_involution():
    labels = torch.tensor([0, 1, 2, 3, 4])
    swapped = order_swap_label(labels)
    assert swapped.tolist() == [0, 2, 1, 4, 3]
    assert torch.equal(order_swap_label(swapped), labels)
