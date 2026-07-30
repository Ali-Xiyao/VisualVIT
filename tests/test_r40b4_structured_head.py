import json

import pytest
import torch

from scripts.run_prta_gen_r40b4_structured_head_smoke import structured_text
from visualvit.prta_gen import ProgressionDecisionHead


def test_progression_decision_head_shape_and_parameter_budget():
    head = ProgressionDecisionHead()
    assert sum(parameter.numel() for parameter in head.parameters()) == 499973
    assert head(torch.randn(3, 3840)).shape == (3, 5)


def test_progression_decision_head_rejects_wrong_feature_width():
    with pytest.raises(ValueError, match="shape"):
        ProgressionDecisionHead()(torch.randn(2, 3839))


def test_structured_text_has_exact_two_key_schema():
    value = json.loads(structured_text("Edema", "Improved"))
    assert list(value) == ["finding", "progression"]
    assert value == {"finding": "Edema", "progression": "Improved"}
