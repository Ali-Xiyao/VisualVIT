# R8 freeze, dry-run, and seed17 smoke audit

## Frozen verification

- Pre-freeze full suite: `350 passed in 116.14s`.
- Post-freeze full suite: `350 passed in 109.16s`.
- Focused runner/validator/launcher suite: `140 passed in 63.71s`.
- Scoped Ruff, format, and py_compile: PASS.
- Three pre-freeze observations were identical: `89dac883359d07b24bb3ec94fce835d91ccb8d52dcfe06e1f66b294c1197809f`.
- Freeze checks: all 30 PASS.
- Three post-freeze Gate-0 processes: `73/73 PASS` each.
- Frozen R8 protocol SHA-256: `9f360cc11ed50275482d419629205374bc83febe96f31dc73e93bc45c30f6291`.
- Frozen registry SHA-256: `2a7129f670e5362fbdb8b8613707d39f51359606d7190e846b62777381595479`.
- Frozen source manifest SHA-256: `1a7046bd9b83c10446a5f0b55bf48f5de533a16b7b0dfd882102e70b12fbdc59`.

## R8 dry-run

- Status: `DRY_RUN_VALIDATED_R8`.
- Child return code: `0`; elapsed `8.968000000008033` seconds.
- Summary SHA-256: `4189dde95cb5f65b4cb750882d16edeed4df14aacf24e46ed4b08d86f985d84a`.
- Post-run audit file SHA-256: `d0d7070a9c46774b2aa2c963d2241d5c1469c476834cc0cbf005dbdfd110fd04`.
- Audit self-hash: `82d921e339bcbbbb8b9871bf2ee1b3392be149bc1fc83b8c10acd4bde7a9f585`.
- Audit verdict: `PASS_R8_DRY_RUN_POSTRUN_AUDIT`, all `42/42` checks PASS.
- Access ledger: exactly four registered fixture-only rows; no training, registered split, real data, or formal test access.

## R8 seed17 one-step smoke

- The attempt is an immutable technical diagnostic, not eligible smoke evidence, because the frozen R8 prose authorized only the dry-run and no machine-verifiable smoke authorization certificate existed.
- Child return code: `4`; elapsed `27.875` seconds.
- Failure status: `TECHNICAL_FAILURE_R8_UNHANDLED_EXCEPTION`.
- Failure stage: `summary_postserialization_validation`.
- `failure.json` SHA-256: `c9dcac95d20855794e2fc7251c339802b6e378f9bc6009f058ed98992a07d59f`.
- No `summary.json` was published; formal test remained unused, formal data remained `HOLD`, and the 18-row ledger was synthetic-only.
- Supervisor result/stdout/stderr SHA-256 values are `5705c7c3ee2d0d2292fd1733e6c20eb135be557aa8159fa17e52195da75d4815`, `35f642bd793b82cc074d86af96f8874a30404ceb91e8afd453b339479d6139b5`, and `d14887bd3e358606413e0deac0ddb054d6cbb2793569980d0589e28a35249de1`.

The only strict errors were the derived `baseline_method_order_exact`, Gate-7 `passed`, and Gate-7 `status` fields. In memory, baseline methods were inserted as `main, local_independent, hungarian, sinkhorn`. Exact-once JSON publication uses `sort_keys=true`, so the persisted object iterates as `hungarian, local_independent, main, sinkhorn`. The independent validator incorrectly treated mapping iteration order as semantic. Every exact-64 leaf audit passed; this is not an exact-64 execution or scientific-method failure.

## R9 requirement

R9 must preserve R8 scientific settings and make the explicit `exact64_method_order` array the sole order authority. Baseline result mappings must be validated by exact key set only. R9 must also preregister machine-verifiable phase authorization certificates: a passing dry-run audit authorizes smoke, and a passing smoke audit authorizes registered-local execution. R8 artifacts and protocol remain immutable; R8 roots must not be reused.
