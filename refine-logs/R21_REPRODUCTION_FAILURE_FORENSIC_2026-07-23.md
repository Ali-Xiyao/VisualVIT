# R21 Reproduction Failure Forensic Record

Date: `2026-07-23`

Disposition: `IMMUTABLE_INELIGIBLE_FORENSIC_EVIDENCE_ONLY`

## 1. Authoritative verdict

R21 terminated as a technical launcher failure:

- status: `TECHNICAL_FAILURE_R21_REPRODUCTION_LAUNCHER`
- stage: `child_eligibility`
- exception type: `LauncherStageError`
- exception message: `child pending payload failed strict recursive eligibility`
- failure timestamp: `2026-07-23T14:40:03.911661Z`
- `formal_data_authorization`: `HOLD`
- `formal_test_status`: `SEALED`
- `formal_claim_allowed`: `false`
- `formal_ablation_claim_allowed`: `false`
- `full_method_claim_allowed`: `false`

Process A exited zero and produced a strict-valid pending summary whose Gates 0--7
were explicit PASS. It nevertheless failed the launcher's recursive eligibility
check because `source_manifest_authority_exact=false`. Therefore Process A is
not an eligible independent reproduction and supports no scientific,
reproduction, ablation, formal-data, or full-method conclusion.

Process B was never launched. Its certificate was issued as part of the
mandatory one-shot pair, but there is no Process-B claim, output directory,
summary, stdout, or stderr evidence. Absence of Process B must not be filled in,
retrospectively inferred, or relabelled as a scientific stop.

## 2. Exact root cause

The failure is a source-manifest execution-domain mismatch, not source-file
drift and not a model, metric, Gate, dataset, or optimizer failure.

The child runner, issuer certificates, Process-A claim, and Process-A summary
all bind the same source-manifest SHA-256:

`32f291fed243441a909de5353db2853c1396afa926e794b5fab360a879f934b6`

That child-runner manifest contains:

- exactly 38 allowlisted paths;
- exactly the same 38 keys in `files`;
- the frozen SHA-256 for every one of those 38 files;
- 19 `observed_workspace_imports`, all within the frozen allowlist.

The launcher called the runner's `_registered_reproduction_eligibility()`.
That function recomputed `_source_manifest()` inside the already-imported
launcher process and treated the complete launcher-context manifest as the
expected child authority. The launcher context has the same 38-path allowlist
and the same 38 file hashes, but it has 20 observed workspace imports because
it additionally imports:

`scripts/run_query_anchor_r4_reproduction.py`

The resulting launcher-context expected manifest SHA-256 is:

`831d07e58acaa1eb4d4d01856e6086e1aedd3ddf2564155b84c849aea4305eb2`

Thus the complete manifest hashes differ solely because
`observed_workspace_imports` is intentionally process-context-sensitive:

| Manifest domain | File entries | Observed imports | SHA-256 |
|---|---:|---:|---|
| clean child runner / certificate / claim / summary | 38 | 19 | `32f291fed243441a909de5353db2853c1396afa926e794b5fab360a879f934b6` |
| launcher-import context recomputation | 38 | 20 | `831d07e58acaa1eb4d4d01856e6086e1aedd3ddf2564155b84c849aea4305eb2` |

The allowlist and `files` mappings are equal. No governed source file changed.
The erroneous comparison was complete-child-manifest SHA versus
complete-launcher-manifest SHA.

## 3. Why pre-freeze checks did not catch it

R21 Gate 0 imported only `scripts/run_query_anchor_r4.py` in a standalone
runner process. It checked source-manifest self-consistency, exact allowlist and
file keys, live file hashes, and the protocol hash, but never imported the
reproduction launcher or exercised the launcher-context eligibility call.
Consequently Gate 0 observed the same 19-import manifest later produced by the
child and correctly passed it.

The static and unit test surface also masked this cross-process boundary:

1. Runner tests captured a fresh source manifest in a subprocess that imported
   only the runner and then monkeypatched `_source_manifest()` to return that
   runner-only manifest.
2. Launcher sequencing tests mocked
   `_registered_reproduction_eligibility()` as passing.
3. Authorization terminal tests exercised certificate reopen, native preclaim,
   summary receipt, JSON roundtrip, prepublication recheck, and replay
   rejection, but did not submit a complete real child summary to the real
   launcher-context `_registered_reproduction_eligibility()`.
4. No dual-context test asserted that runner-only and launcher-import
   manifests may have different import traces while retaining identical frozen
   file authority.

## 4. Immutable preservation manifest

The following evidence is immutable. It must not be deleted, overwritten,
edited, regenerated in place, or reused as R22 authority.

### 4.1 Frozen authority and governed implementation

| Evidence | SHA-256 |
|---|---|
| `refine-logs/CALIBRATION_PROTOCOL_R21_2026-07-23.md` | `693e9e887b9912fa00b532535be95e34abe41b0d15930505a457f8a781b92f1d` |
| R21 full canonical registry | `a3735022a60575477800f0395f83dc7809a11c26a59dd41a36d363939e70f04f` |
| `scripts/run_query_anchor_r4.py` | `f2a80f2a57e5d925563e96e28074d7a58174f90e9c5ebb05fd50b93e729f0ecb` |
| `scripts/run_query_anchor_r4_reproduction.py` | `3c89f00deb9a7017e536bd7b717a21b588f57728c3c46c6af387caf939154f7b` |
| `src/visualvit/r6_validation.py` | `9e18c69fc7fa96e25095516013467d9a5fb38e2e93f9523dd3aba5156d3e9cee` |
| R21 child-runner source manifest | `32f291fed243441a909de5353db2853c1396afa926e794b5fab360a879f934b6` |
| forensic launcher-context manifest recomputation | `831d07e58acaa1eb4d4d01856e6086e1aedd3ddf2564155b84c849aea4305eb2` |
| `.tmp/audit_r21_registered.py` materializer | `5e0886f0dffc224095d93d4fbb7ea85bea5301eb51a6fef3e14de75f869df6d0` |
| registered R14 prerequisite summary | `bdf1b4609593dda3833ab1e06489d50fddc0e7085d254b42a0d82a789491b8cb` |

### 4.2 One-shot R21 authorization evidence

| Evidence | Exact file SHA-256 | Embedded self SHA-256 |
|---|---|---|
| `artifacts/calibration/.r21_phase_authorizations/r14_registered_local_postrun_audit.json` | `7f6970d221a4db2deff17e1b4532ae856c21bc7039a86a27a561dafcfd0b5412` | `668314a38d3ded176e8e0ca5b6e23ad03f6e519372b7492566600294fba3f983` |
| `artifacts/calibration/.r21_phase_authorizations/reproduction_process_a_authorization.json` | `021f178fbecab1eef5f59cfc6436b635a7182cf73e53f1fd3f6d4ea1d3bccc07` | `dcd710248f128367e66baf285f87470f5a1835291d3cd15f8cb3edbbf0e1040c` |
| `artifacts/calibration/.r21_phase_authorizations/reproduction_process_b_authorization.json` | `4d859be158f903fa4a7fbf87f4025308f4fda3c5f09b8395e368981f46cd6102` | `1df648c124464b878c0362f3fe7c7747ef10e7f6b5c00268b32c7b447f916e68` |
| `artifacts/calibration/.r21_phase_authorizations/claims/reproduction_process_a_authorization.14cd55e8-1d7d-4f97-b246-9c1f8ccd3ef2.c68264fb4e3ca377fda4cdeda5ba8d77ffae2871d87241c7f4232c9a6609dce1.process_a.claim.json` | `96a1d9c9b678f3c392c420ba5bb9fd0f96e4044db6b81d263ba4f6e69df705d0` | `ab4b54178819d790c18012f163b9691f6559ee0afa04e07efc7fcfa548c12cc9` |

The R21 registered audit verdict is
`PASS_R21_REGISTERED_POSTRUN_AUDIT`; its `failed_checks` array is empty. That
audit proves the pre-existing R14 prerequisite boundary only. It does not
override the later R21 reproduction failure.

### 4.3 R21 launcher and Process-A terminal evidence

| Evidence | SHA-256 |
|---|---|
| `artifacts/calibration/capes_ci_qptm_r21_reproduction_local_20260723_v1/failure.json` | `7e7e038ed4206ad705fac093c0c7d999daf6c1a3780c370935775a4f551fc627` |
| `artifacts/calibration/capes_ci_qptm_r21_reproduction_local_20260723_v1/process_a/summary.json` | `9d93e5050987e4ed58ef93db02fbcff325e93cba780a19a7fd7b6b4f33d8afd6` |
| `artifacts/calibration/capes_ci_qptm_r21_reproduction_local_20260723_v1/process_a.stdout.log` | `72757edd78d0a3b8ed1059d92c38f31d4122636d6dc64d5602347f28d6285393` |
| `artifacts/calibration/capes_ci_qptm_r21_reproduction_local_20260723_v1/process_a.stderr.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `artifacts/calibration/r21_launcher_logs/launcher_process_result.json` | `a645bf2feba97705e83a9bce97aaa1d9d463beb17ebfbb1be17406832a9afb2a` |
| `artifacts/calibration/r21_launcher_logs/launcher_stdout_stderr.log` | `57c8286bbed45ea4548c00f6a4d6c87485d81fd697678322f144493ef2496d5a` |

## 5. Minimal R22 correction

R22 must be a new, pre-registered technical protocol revision. It must not
rewrite R21 or change any scientific method, dataset, split, seed, step count,
threshold, metric, baseline, model, or formal-data boundary.

The minimal semantic correction is:

1. Define the R22 source manifest with exact top-level keys
   `schema_version`, `allowlist`, `files`,
   `source_manifest_authority_sha256`, and
   `observed_workspace_imports`.
2. Compute `source_manifest_authority_sha256` only from the canonical
   `{schema_version, allowlist, files}` payload. Keep sorted, unique
   `observed_workspace_imports` outside that authority hash and require it to
   be a subset of the frozen allowlist.
3. Bind the single explicit `source_manifest_authority_sha256` field through
   the issuer certificate, launcher reopen, child claim, receipt, summary, and
   prepublication check. R22 must reject the old ambiguous
   `source_manifest_sha256` field rather than retain an alias.
4. Keep the launcher's live source check responsible for the context-invariant
   frozen projection: exact allowlist, exact files, exact per-file hashes,
   final protocol hash, and non-protocol closed-manifest projection. Do not
   require child and launcher import observations to be equal.
5. Add a real, unmocked dual-context boundary test. It must import the runner
   alone and the launcher plus runner, prove that the two contexts have the
   same 38 file-authority entries, permit the launcher-only import-trace entry,
   and pass a certificate-bound child manifest through the real launcher
   eligibility function.
6. Add a pre-freeze Gate-0 compatibility probe for this exact dual-context
   helper. It must fail if code again compares complete child and launcher
   manifest hashes as though their import traces shared one execution domain.
7. Add negative tests for changed file hashes, changed allowlist keys,
   non-self-consistent authority SHA, authorization/summary authority mismatch,
   the legacy field name, and an observed workspace import outside the frozen
   allowlist.

## 6. Non-reuse boundary

R22 must use all-new namespaces:

- a new protocol ID and frozen protocol file;
- a new external materializer and materializer hash;
- a new phase-authorization root;
- new audit and certificate paths;
- new certificate UUIDs and nonces;
- a new claims directory;
- a new reproduction output parent;
- new failure and launcher-log paths.

R21 audit, certificates, Process-A claim, Process-A output, failure artifact,
and logs are forensic prerequisites only. They cannot authorize R22, cannot be
copied into R22 certificates, cannot be consumed again, and cannot be treated
as a completed reproduction. The unused R21 Process-B certificate is also
terminal and non-reusable because the required one-shot pair belongs solely to
the failed R21 transaction.

No R21 artifact authorizes dataset/model download, GPU or Slurm use, allocation
4161 use, formal-test access, formal-data access, or scientific claims.
