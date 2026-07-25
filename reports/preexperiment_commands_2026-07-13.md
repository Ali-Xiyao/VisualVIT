# Preexperiment Commands (2026-07-13)

All runs are `NON_CONFIRMATORY_PROXY`.

## Environment preflight

```powershell
nvidia-smi --query-gpu=index,name,driver_version,memory.total,memory.used,memory.free,utilization.gpu --format=csv,noheader,nounits
Get-PSDrive E,F,H | Select-Object Name,Used,Free
python --version
python -c "import torch, torchvision, timm, pandas, transformers; print(torch.__version__, torchvision.__version__, timm.__version__, pandas.__version__, transformers.__version__)"
```

## Tests

```powershell
python -m pytest -q -p no:cacheprovider
```

## Corrected synthetic qualification

```powershell
python scripts\run_synthetic_pilot.py --run-id pilot_synthetic_auditfix_20260713 --device cpu --train-cases 128 --dev-cases 64 --classifier-steps 180 --matcher-steps 180 --seeds 17 29 43 --output-root F:\VisualVIT_runtime\050_routeC\runs
python scripts\run_synthetic_pilot.py --run-id pilot_synthetic_auditfix_rerun_20260713 --device cpu --train-cases 128 --dev-cases 64 --classifier-steps 180 --matcher-steps 180 --seeds 17 29 43 --output-root F:\VisualVIT_runtime\050_routeC\runs
```

## BiomedCLIP smoke

```powershell
python scripts\run_encoder_smoke.py --device cuda:0 --output-root F:\VisualVIT_runtime\050_routeC\runs
```

## Qwen adapter verification

Historical raw-output runs (performed before the strict canonical adapter was added) are retained as schema FAIL. With the current parser these commands are provenance records, not a way to recreate the old parser behavior:

```powershell
python scripts\run_qwen2vl_smoke.py --run-id qwen2vl_2b_attempt2_20260713 --model-path H:\Xiyao_Wang\001_models\Qwen2-VL-2B-Instruct --device cuda:0 --max-new-tokens 16 --output-root F:\VisualVIT_runtime\050_routeC\runs
python scripts\run_qwen2vl_smoke.py --run-id qwen2vl_7b_attempt1_20260713 --model-path H:\Xiyao_Wang\001_models\Qwen2-VL-7B-Instruct --device cuda:1 --max-new-tokens 16 --output-root F:\VisualVIT_runtime\050_routeC\runs
```

Current adapter verification:

```powershell
python scripts\run_qwen2vl_smoke.py --run-id qwen2vl_2b_adapter_20260713 --model-path H:\Xiyao_Wang\001_models\Qwen2-VL-2B-Instruct --device cuda:0 --max-new-tokens 16 --output-root F:\VisualVIT_runtime\050_routeC\runs
python scripts\run_qwen2vl_smoke.py --run-id qwen2vl_7b_adapter_20260713 --model-path H:\Xiyao_Wang\001_models\Qwen2-VL-7B-Instruct --device cuda:1 --max-new-tokens 16 --output-root F:\VisualVIT_runtime\050_routeC\runs
```

## MIMIC proxy manifest and convergence-gated run

```powershell
python scripts\build_mimic_proxy_manifest.py --run-id mimic_proxy_manifest_240_20260713 --per-class 80 --train-per-class 60 --seed 20260713 --output-root F:\VisualVIT_runtime\050_routeC\data
python scripts\run_mimic_proxy_encoder_classifier.py --run-id mimic_proxy_biomedclip_convergence_gate_unitfix_20260713 --manifest F:\VisualVIT_runtime\050_routeC\data\mimic_proxy_manifest_240_20260713\proxy_manifest.csv --device cuda:0 --batch-size 32 --steps 300 --learning-rate 0.01 --seeds 17 29 43 --output-root F:\VisualVIT_runtime\050_routeC\runs
```

The MIMIC command is expected to exit with code 2 when the convergence gate fails; the summary status is the authority.

## Final verification and evidence manifest

```powershell
python -m compileall -q src scripts tests
python -m pytest -q -p no:cacheprovider
python scripts\build_preexperiment_evidence_manifest.py --include-qwen-shards
```
