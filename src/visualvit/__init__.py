"""VisualVIT Route C qualification package."""

from .schemas import (
    AllocationPlan,
    MatchPlan,
    ProjectedTokenBundle,
    RegionBatch,
    RelationCandidates,
    TokenBundle,
)
from .matching import (
    NullAwareMatchGraph,
    ProjectedCosineMatcher,
    anatomy_compatible_derangement,
    oracle_plan_from_entity_ids,
)
from .allocator import DeterministicGlobalAllocator
from .tokenizer import (
    assemble_capes_ci_tokens,
    assemble_fixed_budget_tokens,
    build_soft_relation_candidates,
)
from .projector import RelationProjector
from .qwen_adapter import (
    FrozenVLMAdapter,
    PROGRESSION_LABELS,
    QwenRelationAdapter,
)
from .baselines import (
    BalancedSinkhornBaseline,
    DevelopmentFrozenThreshold,
    HungarianRejectBaseline,
)
from .data_qualification import (
    MANIFEST_SCHEMA_VERSION,
    qualify_longitudinal_assets,
    write_audit_json,
)
from .statistics import (
    LABEL_ORDER,
    PredictionRow,
    evaluate_formal_statistics,
    weighted_macro_f1,
)

__all__ = [
    "AllocationPlan",
    "MatchPlan",
    "ProjectedTokenBundle",
    "RegionBatch",
    "RelationCandidates",
    "TokenBundle",
    "NullAwareMatchGraph",
    "ProjectedCosineMatcher",
    "DeterministicGlobalAllocator",
    "anatomy_compatible_derangement",
    "oracle_plan_from_entity_ids",
    "assemble_capes_ci_tokens",
    "assemble_fixed_budget_tokens",
    "build_soft_relation_candidates",
    "RelationProjector",
    "FrozenVLMAdapter",
    "QwenRelationAdapter",
    "PROGRESSION_LABELS",
    "BalancedSinkhornBaseline",
    "DevelopmentFrozenThreshold",
    "HungarianRejectBaseline",
    "MANIFEST_SCHEMA_VERSION",
    "qualify_longitudinal_assets",
    "write_audit_json",
    "LABEL_ORDER",
    "PredictionRow",
    "evaluate_formal_statistics",
    "weighted_macro_f1",
]
