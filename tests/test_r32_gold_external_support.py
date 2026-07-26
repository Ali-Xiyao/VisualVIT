from scripts.audit_r32_gold_external_support import conservative_mde_pp


def test_power_audit_is_conservative_and_shrinks_with_sample_size():
    assert conservative_mde_pp(0) is None
    assert conservative_mde_pp(16) > 30
    assert conservative_mde_pp(100) < conservative_mde_pp(16)
