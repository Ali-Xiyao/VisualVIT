import torch
from torch import nn

from visualvit.audit import audit_b4_isomorphism, training_convergence_pass
from visualvit.matching import anatomy_compatible_derangement
from visualvit.synthetic import make_synthetic_batch
from visualvit.tokenizer import assemble_fixed_budget_tokens


def _model(input_dim: int) -> nn.Module:
    return nn.Sequential(nn.Linear(input_dim, 32), nn.GELU(), nn.Linear(32, 5))


def test_b4_is_assignment_only():
    synthetic = make_synthetic_batch(num_cases=4, seed=19)
    oracle = synthetic.oracle
    deranged = anatomy_compatible_derangement(synthetic.regions, oracle, seed=17)
    bundle_a = assemble_fixed_budget_tokens(synthetic.regions, deranged)
    bundle_b = assemble_fixed_budget_tokens(synthetic.regions, oracle)

    torch.manual_seed(101)
    model_a = _model(bundle_a.tokens.shape[-1])
    torch.manual_seed(101)
    model_b = _model(bundle_b.tokens.shape[-1])
    report = audit_b4_isomorphism(
        synthetic.regions,
        synthetic.regions,
        deranged,
        oracle,
        bundle_a,
        bundle_b,
        model_a,
        model_b,
    )
    assert report["pass"], report


def test_b4_audit_rejects_input_mutation():
    synthetic = make_synthetic_batch(num_cases=2, seed=23)
    mutated = make_synthetic_batch(num_cases=2, seed=23).regions
    mutated.prior_features = mutated.prior_features.clone()
    mutated.prior_features[0, 0, 0] += 0.25
    oracle = synthetic.oracle
    deranged = anatomy_compatible_derangement(synthetic.regions, oracle, seed=17)
    bundle_a = assemble_fixed_budget_tokens(synthetic.regions, deranged)
    # The second bundle is deliberately built from the original input so the
    # independent input checksum is the only failing dimension.
    bundle_b = assemble_fixed_budget_tokens(synthetic.regions, oracle)
    torch.manual_seed(101)
    model_a = _model(bundle_a.tokens.shape[-1])
    torch.manual_seed(101)
    model_b = _model(bundle_b.tokens.shape[-1])
    report = audit_b4_isomorphism(
        synthetic.regions,
        mutated,
        deranged,
        oracle,
        bundle_a,
        bundle_b,
        model_a,
        model_b,
    )
    assert not report["pass"]
    assert not report["input_checksums_equal"]


def test_training_convergence_gate_rejects_either_failure_and_nonfinite():
    assert training_convergence_pass({"train_macro_f1": 0.95, "final_loss": 0.20})
    assert not training_convergence_pass({"train_macro_f1": 0.9499, "final_loss": 0.10})
    assert not training_convergence_pass({"train_macro_f1": 0.99, "final_loss": 0.2001})
    assert not training_convergence_pass(
        {"train_macro_f1": float("nan"), "final_loss": 0.10}
    )
