from __future__ import annotations

import re
from dataclasses import dataclass

LABELS = ("new", "resolved", "worse", "improved", "stable")
LITERAL_PREFIX_PATTERN = re.compile(r"^ANSWER: (new|resolved|worse|improved|stable)$")
ADAPTER_PATTERN = re.compile(r"^(?:ANSWER: )?(new|resolved|worse|improved|stable)$")


@dataclass(frozen=True)
class ParsedProgression:
    label: str
    canonical: str
    literal_prefix_compliance: bool


def parse_progression_output(raw_output: str) -> ParsedProgression:
    """Parse only an exact allowed label, with an optional literal prefix.

    Any explanation, punctuation, multiple labels, or unknown text raises.
    This is intentionally strict and never falls back to a default class.
    """

    if "\n" in raw_output or "\r" in raw_output:
        raise ValueError(f"invalid constrained progression output: {raw_output!r}")
    stripped = raw_output.strip()
    match = ADAPTER_PATTERN.fullmatch(stripped)
    if match is None:
        raise ValueError(f"invalid constrained progression output: {raw_output!r}")
    label = match.group(1)
    canonical = f"ANSWER: {label}"
    return ParsedProgression(
        label=label,
        canonical=canonical,
        literal_prefix_compliance=(
            LITERAL_PREFIX_PATTERN.fullmatch(stripped) is not None
        ),
    )
