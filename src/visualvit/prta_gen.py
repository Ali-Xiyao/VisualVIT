from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import re
from typing import Iterable, Mapping, Sequence

import torch
from torch import Tensor, nn
import torch.nn.functional as F


PROGRESSION_CLASSES = ("Stable", "Improved", "Worse", "New", "Resolved")
LATERALITY_CLASSES = (
    "Left",
    "Right",
    "Bilateral",
    "Midline",
    "Unspecified",
)
ANATOMY_CLASSES = (
    "Upper lung",
    "Middle lung",
    "Lower lung",
    "Hilar",
    "Pleural",
    "Cardiac silhouette",
    "Mediastinal",
    "Diffuse",
    "Unspecified",
)
DEGREE_CLASSES = ("Minimal", "Mild", "Moderate", "Marked", "Unspecified")

_FINDING_SURFACES: dict[str, tuple[str, ...]] = {
    "Atelectasis": (r"\batelecta(?:sis|tic)\b",),
    "Cardiomegaly": (r"\bcardiomegaly\b",),
    "Consolidation": (r"\bconsolidation\b",),
    "Edema": (r"\b(?:pulmonary |interstitial )?edema\b",),
    "Enlarged Cardiomediastinum": (
        r"\benlarged cardiomediastinal silhouette\b",
        r"\bcardiomediastinal enlargement\b",
    ),
    "Fracture": (r"\bfracture[sd]?\b",),
    "Lung Lesion": (
        r"\b(?:nodule|nodules|mass|masses)\b",
    ),
    "Lung Opacity": (
        r"\b(?:opacity|opacities|infiltrate|infiltrates)\b",
    ),
    "Pleural Effusion": (r"\b(?:pleural )?effusion[sd]?\b",),
    "Pleural Other": (
        r"\bpleural (?:thickening|scar|scarring)\b",
    ),
    "Pneumonia": (r"\bpneumonia\b",),
    "Pneumothorax": (r"\bpneumothora(?:x|ces)\b",),
}

_LATERALITY_PATTERNS: dict[str, tuple[str, ...]] = {
    "Left": (r"\bleft(?:-sided)?\b",),
    "Right": (r"\bright(?:-sided)?\b",),
    "Bilateral": (
        r"\bbilateral(?:ly)?\b",
        r"\bbibasilar\b",
        r"\bboth (?:lungs?|sides?|hemithoraces)\b",
    ),
    "Midline": (r"\bmidline\b", r"\bcentral(?:ly)?\b"),
}

_ANATOMY_PATTERNS: dict[str, tuple[str, ...]] = {
    "Upper lung": (
        r"\bupper (?:lung|lobe|zone|field)s?\b",
        r"\bupper(?=\s+(?:and|or)\s+lower (?:lung|lobe|zone|field)s?\b)",
        r"\bap(?:ex|ices|ical)\b",
    ),
    "Middle lung": (
        r"\bmiddle (?:lung|lobe|zone|field)s?\b",
        r"\blingula\b",
    ),
    "Lower lung": (
        r"\blower (?:lung|lobe|zone|field)s?\b",
        r"\b(?:lung )?bases?\b",
        r"\bbasilar\b",
    ),
    "Hilar": (r"\bhila(?:r|um)\b", r"\bperihilar\b"),
    "Pleural": (
        r"\bpleural space\b",
        r"\bcostophrenic (?:angle|sulcus)\b",
    ),
    "Cardiac silhouette": (
        r"\bcardiac silhouette\b",
        r"\bheart size\b",
    ),
    "Mediastinal": (r"\bmediastin(?:al|um)\b",),
    "Diffuse": (
        r"\bdiffuse(?:ly)?\b",
        r"\bthroughout (?:both |the )?lungs?\b",
    ),
}

_DEGREE_PATTERNS: dict[str, tuple[str, ...]] = {
    "Minimal": (r"\btrace\b", r"\bminimal(?:ly)?\b", r"\btiny\b"),
    "Mild": (r"\bmild(?:ly)?\b", r"\bslight(?:ly)?\b", r"\bsmall\b"),
    "Moderate": (r"\bmoderate(?:ly)?\b",),
    "Marked": (
        r"\bmarked(?:ly)?\b",
        r"\bsevere(?:ly)?\b",
        r"\blarge\b",
        r"\bsubstantial(?:ly)?\b",
    ),
}


@dataclass(frozen=True)
class ExplicitGenerativeTarget:
    finding: str
    progression: str
    laterality: str
    anatomy: str
    degree: str
    evidence: str
    quality_tier: str
    literal_laterality: bool
    literal_anatomy: bool
    literal_degree: bool

    def to_dict(self) -> dict[str, str | bool]:
        return asdict(self)


def _mask_finding_surface(sentence: str, finding: str) -> str:
    masked = sentence
    for pattern in _FINDING_SURFACES.get(finding, ()):
        masked = re.sub(pattern, " ", masked, flags=re.I)
    return " ".join(masked.split())


def _literal_class(
    text: str,
    patterns: Mapping[str, Sequence[str]],
    *,
    unspecified: str = "Unspecified",
) -> str:
    matched = {
        label
        for label, label_patterns in patterns.items()
        if any(re.search(pattern, text, flags=re.I) for pattern in label_patterns)
    }
    return next(iter(matched)) if len(matched) == 1 else unspecified


def extract_explicit_generative_target(
    annotation: Mapping[str, object],
) -> ExplicitGenerativeTarget:
    """Extract only fields literally supported by the source comparison sentence.

    The finding surface is masked before location/degree extraction so a term
    such as ``Pleural Effusion`` cannot manufacture a ``Pleural`` anatomy label.
    Missing or conflicting labels fail closed to ``Unspecified``.
    """

    finding = str(annotation["finding"]).strip()
    progression = str(annotation["label"]).strip().title()
    sentence = " ".join(str(annotation.get("sentence", "")).split())
    if progression not in PROGRESSION_CLASSES:
        raise ValueError(f"unsupported progression label: {progression!r}")
    if not sentence:
        raise ValueError("generative target requires a non-empty source sentence")

    evidence_text = _mask_finding_surface(sentence, finding)
    laterality = _literal_class(evidence_text, _LATERALITY_PATTERNS)
    anatomy = _literal_class(evidence_text, _ANATOMY_PATTERNS)
    degree = _literal_class(evidence_text, _DEGREE_PATTERNS)
    literal_laterality = laterality != "Unspecified"
    literal_anatomy = anatomy != "Unspecified"
    literal_degree = degree != "Unspecified"
    if literal_laterality or literal_anatomy:
        quality_tier = "A"
    elif literal_degree:
        quality_tier = "B"
    else:
        quality_tier = "C"
    return ExplicitGenerativeTarget(
        finding=finding,
        progression=progression,
        laterality=laterality,
        anatomy=anatomy,
        degree=degree,
        evidence=sentence,
        quality_tier=quality_tier,
        literal_laterality=literal_laterality,
        literal_anatomy=literal_anatomy,
        literal_degree=literal_degree,
    )


def format_structured_target(
    target: ExplicitGenerativeTarget,
    *,
    unlocked_fields: Iterable[str],
    include_evidence: bool,
) -> str:
    """Format a strict XML target without inventing unavailable fields."""

    unlocked = frozenset(unlocked_fields)
    allowed = {"progression", "laterality", "anatomy", "degree"}
    unknown = unlocked - allowed
    if unknown:
        raise ValueError(f"unknown unlocked fields: {sorted(unknown)}")
    values = {
        "progression": target.progression,
        "laterality": target.laterality,
        "anatomy": target.anatomy,
        "degree": target.degree,
    }
    parts = [f"<finding>{target.finding}</finding>"]
    for field in ("progression", "laterality", "anatomy", "degree"):
        if field not in unlocked:
            continue
        value = values[field]
        if value == "Unspecified":
            continue
        parts.append(f"<{field}>{value}</{field}>")
    if include_evidence:
        if target.quality_tier != "A":
            raise PermissionError("evidence output requires a Tier-A source target")
        parts.append(f"<evidence>{target.evidence}</evidence>")
    return "\n".join(parts)


def exact64_summary_features(
    tokens: Tensor,
    *,
    valid_mask: Tensor | None = None,
) -> Tensor:
    """Pool the unchanged R38/R39 state, transition, and relation token groups."""

    if tokens.ndim != 3 or tokens.shape[1] != 64:
        raise ValueError("exact64 tokens must have shape [B,64,D]")
    if valid_mask is not None:
        if tuple(valid_mask.shape) != tuple(tokens.shape[:2]):
            raise ValueError("valid_mask must have shape [B,64]")
        expected = torch.ones_like(valid_mask, dtype=torch.bool)
        expected[:, 60:] = False
        if not torch.equal(valid_mask.bool(), expected):
            raise ValueError("exact64 valid mask must keep only positions 0-59")
    return torch.cat(
        (
            tokens[:, 0:20].mean(dim=1),
            tokens[:, 20:40].mean(dim=1),
            tokens[:, 40:60].mean(dim=1),
        ),
        dim=-1,
    )


def exact64_regional_moment_features(tokens: Tensor) -> Tensor:
    """Retain first/second/extreme statistics within each active token tier."""

    if tokens.ndim != 3 or tokens.shape[1] != 64:
        raise ValueError("exact64 tokens must have shape [B,64,D]")
    features = []
    for start, end in ((0, 20), (20, 40), (40, 60)):
        region = tokens[:, start:end]
        features.extend(
            (
                region.mean(dim=1),
                region.std(dim=1, unbiased=False),
                region.amax(dim=1),
            )
        )
    return torch.cat(features, dim=-1)


def exact64_regional_cosine_features(
    tokens: Tensor, *, components: int = 4
) -> Tensor:
    """Project each active 20-token tier onto fixed orthonormal position modes."""

    if tokens.ndim != 3 or tokens.shape[1] != 64:
        raise ValueError("exact64 tokens must have shape [B,64,D]")
    if not 1 <= components <= 20:
        raise ValueError("cosine components must be between 1 and 20")
    length = 20
    positions = (
        torch.arange(length, device=tokens.device, dtype=tokens.dtype) + 0.5
    )
    frequencies = torch.arange(
        components, device=tokens.device, dtype=tokens.dtype
    ).unsqueeze(1)
    weights = torch.cos(torch.pi * frequencies * positions / length)
    weights[0] *= length**-0.5
    if components > 1:
        weights[1:] *= (2.0 / length) ** 0.5
    projected = []
    for start, end in ((0, 20), (20, 40), (40, 60)):
        region = tokens[:, start:end]
        projected.append(
            torch.einsum("kl,bld->bkd", weights, region).flatten(1)
        )
    return torch.cat(projected, dim=-1)


class LinearInformationProbe(nn.Module):
    """Capacity-bounded probe for one preregistered R40A target field."""

    def __init__(self, input_width: int, class_count: int) -> None:
        super().__init__()
        if input_width <= 0 or class_count <= 1:
            raise ValueError("invalid information-probe dimensions")
        self.classifier = nn.Linear(input_width, class_count)

    def forward(self, features: Tensor) -> Tensor:
        if features.ndim != 2:
            raise ValueError("probe features must have shape [B,D]")
        return self.classifier(features)


def field_support(
    targets: Iterable[ExplicitGenerativeTarget],
    field: str,
) -> dict[str, int]:
    registries = {
        "progression": PROGRESSION_CLASSES,
        "laterality": LATERALITY_CLASSES,
        "anatomy": ANATOMY_CLASSES,
        "degree": DEGREE_CLASSES,
    }
    if field not in registries:
        raise ValueError(f"unknown target field: {field}")
    counts = Counter(str(getattr(target, field)) for target in targets)
    return {label: counts[label] for label in registries[field]}


def generative_prior_preference_loss(
    true_prior_scores: Tensor,
    counterfactual_prior_scores: Tensor,
    *,
    margin: float = 0.2,
) -> Tensor:
    """Sequence-level G-CMCP hinge loss reserved for the later R42 gate."""

    if true_prior_scores.shape != counterfactual_prior_scores.shape:
        raise ValueError("true and counterfactual sequence scores must align")
    if margin <= 0:
        raise ValueError("G-CMCP margin must be positive")
    return F.relu(
        torch.as_tensor(
            margin,
            dtype=true_prior_scores.dtype,
            device=true_prior_scores.device,
        )
        - true_prior_scores
        + counterfactual_prior_scores
    ).mean()
