# CAPES-CI v1 Survival Results

Date: 2026-07-19  
Evidence class: `SURVIVAL_NON_CONFIRMATORY`  
Formal claim allowed: no

## Result

Gates S010–S070 pass. The local learned path, server CPU/GPU implementation and real frozen Qwen3-VL exact-64 interface are executable and independently reproducible. This still does not establish the paper claims on legal real gold data.

## Static and unit verification

```text
python -m pytest -q -p no:cacheprovider  -> 76 passed
python -m compileall -q src scripts tests -> PASS
ruff check src tests                     -> PASS
ruff format --check src tests            -> PASS
```

Coverage added:

- backward-compatible observation and method schemas;
- fractional two-sided-null mass accounting and finite gradients;
- anatomy/padding masks and permutation equivariance;
- globally optimal deterministic optional hardening on enumerated micro-cases;
- deterministic 28-slot allocation for N=0/1/28/29/58/>100;
- top-27 plus mass/provenance-preserving overflow;
- soft relation candidates that never read gold entity IDs;
- exact 4/28/28/4 token assembly and B4 shared allocation/entity stream;
- projector neutral filling and metadata boundaries;
- exactly 64 placeholder replacements, all physical masks, 3-axis text positions;
- five-label normalized likelihood, frozen LM gradient isolation, and pixel/image rejection;
- integrated CAPESCIModel state round-trip.

## S050 balanced five-label overfit

Two independent Python processes ran the same locked configuration:

```text
seed=2401
data_seed=3401
cases_per_class=3
original cases=15
time-reversed cases=15
total=30
steps=500
learning_rate=0.02
device=CPU
```

Both runs independently returned:

| Metric | Value |
|---|---:|
| Initial accuracy | 0.20 |
| Final accuracy | 1.00 |
| Original-order accuracy | 1.00 |
| Time-reversed mapped-label accuracy | 1.00 |
| Initial loss | 1.8778347969 |
| Final evaluation loss | 0.5332376361 |
| Oracle-vs-deranged mean absolute logit change | 0.1972738206 |
| Oracle-vs-null-deleted mean absolute logit change | 0.1365451813 |
| Model state SHA256 | `03235d9e730493c2d09453419615de44e99532b5e5bf953df9e6d3dd0f835a07` |

The reproduction verifier passed all checks: both runs PASS, configs equal, targets/predictions equal, all non-time metrics exactly equal, and state hashes equal.

Artifacts:

- `artifacts/survival/s050_20260719_a/summary.json`
- `artifacts/survival/s050_20260719_a/model_state.pt`
- `artifacts/survival/s050_20260719_b/summary.json`
- `artifacts/survival/s050_20260719_b/model_state.pt`
- `artifacts/survival/s050_repro_20260719.json`

### S051 current-adapter contract refresh

After the Qwen adapter began forcing `use_cache=False` and `logits_to_keep=0`, the synthetic toy LM signature was updated to enforce the same contract. Two fresh seed-17 processes then independently returned 100% original/reversed accuracy, exact non-time metrics and the same model-state SHA256:

`41ec423af8e348a7a5bfc68f1e1b3ff30fbaec4e3097773042b202713d7b25a3`

Artifacts:

- `artifacts/survival/s051_current_contract_20260719_seed17/`
- `artifacts/survival/s051_current_contract_20260719_seed17_repro/`
- `artifacts/survival/s051_current_contract_repro_20260719.json`

## S060 SHA-verified server CPU/GPU regression

- Focused source archive: 35 files; SHA256 `38556ba097cf6a5fe422b87b0e2fafb6334918a58d966fc83926ebb65530e7cf`.
- Remote source verification: 35/35 entries match, zero failures.
- Login-node CPU: 75 passed, one CUDA-only test skipped.
- `4161 / gpu01 / A800 80GB` GPU child step: 76/76 passed.
- After exit, parent 4161 remained RUNNING and the only remaining step was `4161.batch`.

Artifacts:

- `artifacts/survival/s060_server_20260719/summary.json`
- `artifacts/survival/s060_server_20260719/cpu_pytest.log`
- `artifacts/survival/s060_server_20260719/gpu_pytest.log`

## S070 real Qwen3-VL 4B exact-64 smoke

The first attempt failed closed after model loading because FP32 synthetic relation features were passed to a BF16 projector. The failed JSON/log are preserved. The dtype contract was corrected, the focused source was rebuilt under archive SHA256 `21d8559a3804f874d1eb77490ba9cb13476b40694c2567ab04c3a2f5e372ece9`, and the same seed was rerun.

Both fresh-process runs then passed with exact equality on all registered non-runtime fields:

| Check | Result |
|---|---:|
| Model | Qwen3-VL-4B-Instruct |
| Model parameters / trainable | 4,437,815,808 / 0 |
| Physical token layout | 4/28/28/4 = 64 |
| Placeholder | `<|fim_pad|>` / 151662 |
| Pixel/image/video inputs | none |
| Position IDs | equal `[3,B,L]` axes |
| Five label scores | finite |
| Relation intervention mean absolute score change | 0.0991658196 |
| Peak CUDA allocated/reserved | 9.027 / 9.085 GB |
| Independent-process registered-field mismatches | 0 |

After both child steps exited, parent 4161 remained RUNNING and only `4161.batch` remained.

Artifacts:

- `artifacts/survival/s070_qwen3vl_20260719/summary.json`
- `artifacts/survival/s070_qwen3vl_20260719/attempt1_fail/`
- `artifacts/survival/s070_qwen3vl_20260719/attempt2_pass/`
- `artifacts/survival/s070_qwen3vl_20260719/repro_pass/`
- `artifacts/survival/s070_qwen3vl_20260719/repro_comparison.json`

## Gate interpretation

Passed:

- the complete learned-soft matcher -> allocator -> 64-token -> projector -> frozen toy causal-LM likelihood path trains;
- original and time-reversed label maps can both be learned;
- assignment and null interventions actually change VLM logits;
- VLM parameters stay frozen and no pixel/image path is available;
- deterministic independent-process reproduction is exact.

Not yet passed:

- legal real gold data/lineage qualification;
- real B4 oracle gap, learned Recovery, main baselines or ablations;
- formal multi-seed paper evidence.

Current verdict: `GO_DATA_QUALIFICATION_AND_REAL_TRAINDEV_PILOT_PREPARATION + NO_GO_FORMAL_TEST_OR_MAIN_CLAIM`.
