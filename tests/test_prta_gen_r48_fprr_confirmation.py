from __future__ import annotations

from scripts.aggregate_prta_gen_r48_fprr_confirmation import aggregate
from scripts.cache_prta_gen_r48_fprr_confirmation_tokens import preflight
from scripts.run_prta_gen_r48_fprr_confirmation import validate_authority


def test_r48_confirmation_entrypoints_are_importable() -> None:
    assert callable(aggregate)
    assert callable(preflight)
    assert callable(validate_authority)
