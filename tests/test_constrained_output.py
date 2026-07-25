import pytest

from visualvit.constrained_output import parse_progression_output


@pytest.mark.parametrize(
    ("raw", "canonical", "literal"),
    [
        ("improved", "ANSWER: improved", False),
        ("ANSWER: stable", "ANSWER: stable", True),
        ("  resolved  ", "ANSWER: resolved", False),
    ],
)
def test_strict_progression_adapter(raw, canonical, literal):
    parsed = parse_progression_output(raw)
    assert parsed.canonical == canonical
    assert parsed.literal_prefix_compliance is literal


@pytest.mark.parametrize(
    "raw",
    [
        "The answer is stable.",
        "ANSWER: unknown",
        "stable\nBecause...",
        "ANSWER:\nnew",
        "ANSWER:new",
        "ANSWER:\tnew",
        "",
        "new or resolved",
    ],
)
def test_strict_progression_adapter_rejects_explanations(raw):
    with pytest.raises(ValueError):
        parse_progression_output(raw)
