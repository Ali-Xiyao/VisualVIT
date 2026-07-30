# Data boundary

This directory contains small tracked reference metadata and the pinned
CheXTemporal annotation package only. It does not contain credentialed chest
X-ray images, runtime feature/token caches, checkpoints, or prediction
payloads.

`data/official/chextemporal_81fd9cdd/` includes gold annotation files that
remain under the project quarantine boundary. Their presence in the tracked
source package is not authorization to inspect outcome rows, tune a model,
choose a threshold, or select a narrative.

Large or credentialed inputs remain outside Git under the local dataset/runtime
roots documented in the frozen configs and reports.
