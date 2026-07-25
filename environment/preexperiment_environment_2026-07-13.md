# Preexperiment Environment Snapshot

**Date**: 2026-07-13  
**Evidence class**: `NON_CONFIRMATORY_PROXY`

## Runtime

- Python: 3.12.8
- Executable: `C:\Users\Admin\AppData\Local\Programs\Python\Python312\python.exe`
- PyTorch: 2.5.1+cu121
- Torchvision: 0.20.1+cu121
- CUDA toolkit visible to PyTorch: 12.1
- NVIDIA driver: 560.94
- Driver-reported CUDA upper capability: 12.6
- cuDNN: 9.1.0
- Transformers: 5.5.3
- Accelerate: 1.11.0
- timm: 1.0.24
- pandas: 2.3.3
- Pillow: 12.0.0
- qwen-vl-utils: 0.0.14
- pytest: 9.0.3

## Hardware

- GPU 0: NVIDIA GeForce RTX 3090, 24,576 MiB
- GPU 1: NVIDIA GeForce RTX 3090, 24,576 MiB
- Both devices report bf16 support.

## Storage and cache policy

- Code/specification: `E:\Xiyaowang\050_VisualVIT`
- Runtime: `F:\VisualVIT_runtime\050_routeC`
- Read-only assets: `H:\Xiyao_Wang`
- `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` for Qwen smoke.
- Experiment-specific temporary directories are under F.

## Reproducibility boundary

These runs used the system Python installation, not a newly created isolated virtual environment. Exact package versions are recorded, unit tests and synthetic metrics were independently rerun, but the environment is not yet a formal lockfile/container. This is sufficient for engineering qualification only. Before formal Phase I, create an isolated environment, export a complete lock, initialize/version the code workspace, and rerun the qualification suite.

