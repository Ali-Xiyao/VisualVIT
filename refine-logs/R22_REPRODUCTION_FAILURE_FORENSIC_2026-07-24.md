# R22 Reproduction Failure Forensic — 2026-07-24

## Verdict

R22 is an immutable technical failure. Both registered CPU children completed the
500-step, three-seed workload and each persisted a strict pending summary, but the
parent launcher failed closed at `canonical_compare`. No independent-reproduction
certificate was issued. Formal data remains `HOLD`, formal test remains `SEALED`,
and every formal/full-method claim flag remains false.

R22 must not be retried or patched in place. Its outputs are forensic evidence
only.

## One-shot execution

- Scheduled launcher result schema: `r22_scheduled_launcher_process_result_v1`
- Started UTC: `2026-07-23T16:14:49.8474158Z`
- Completed UTC: `2026-07-23T17:34:50.2510258Z`
- Launcher exit code: `1`
- Retry attempted: `false`
- Parent status: `TECHNICAL_FAILURE_R22_REPRODUCTION_LAUNCHER`
- Failure stage: `canonical_compare`
- Failure message: `canonical comparison checks have a non-exact key set`

## Preserved evidence

- Parent failure SHA-256:
  `58dd37444efcea295bcf7f10033800a4aacb8d27001980bba18db46bcc6dc6d1`
- Scheduled launcher result SHA-256:
  `95f03e63d1c728cc77ee9e9f6840b2b3945cf9f2b7a601be973ed819160cd1de`
- Process-A summary SHA-256:
  `ee4bd4e21686bf6893359d6025f293ce61991e853e8bacd83dc1b13d1a812fe9`
- Process-B summary SHA-256:
  `71b820d439fe14ad892939b08561a42a5be013929b295cd7df1d7b1d78bf1208`
- Process-A stdout SHA-256:
  `b0b5163f12dd0f6db108858032d29075a36f1fca1d245b2f862ee054f083e064`
- Process-B stdout SHA-256:
  `85c40d6c77b2677f7d4a978bdd83557c3f58f829cf3ff4c063696916fa2b3757`
- Both stderr logs are empty and hash to the SHA-256 of an empty file.

## Child evidence

Both child summaries report:

- `PASS_R14_GATES_0_TO_7_AWAITING_INDEPENDENT_REPRODUCTION`
- eight completed compute gates
- `independent_reproduction` as the only not-run gate
- config SHA-256
  `f111fc53bcc3704018d17832dd32c900ea8e7367b7ca671a1fe4411f9f25658d`
- source-manifest authority SHA-256
  `9933c7232710b8f07cb5dbc140c1c3170792735bcf8f620f7d9244b73d98d63a`
- `formal_claim_allowed=false`

These pending child results cannot substitute for the missing parent certificate.

## Exact root cause

The canonical comparison producer in `scripts/run_query_anchor_r4.py` emits the
boolean check `independent_process_pids`. The strict parent validator in
`scripts/run_query_anchor_r4_reproduction.py` validates the comparison check map
by exact key membership, but its `expected_checks` set omits that producer-owned
key.

Observed check keys:

1. `canonical_payload_exact`
2. `canonical_sha256_exact`
3. `independent_process_pids`
4. `independent_process_uuids`
5. `primary_pid_matches_launcher`
6. `primary_process_exit_zero`
7. `primary_registered_payload_eligible`
8. `replica_pid_matches_launcher`
9. `replica_process_exit_zero`
10. `replica_registered_payload_eligible`
11. `valid_process_uuids`

The validator expected all of the above except `independent_process_pids`. It
therefore rejected before recomputing the comparison verdict.

## Allowed next route

R23 may make one execution-control correction only: add
`independent_process_pids` to the strict validator's exact expected check set and
bind this contract through tests and a new frozen authority. R23 must retain the
R22 scientific payload, seeds `[17,29,43]`, 500 steps, CPU device, thresholds,
budgets, gate order, formal-data hold, and formal-test seal.

Before any R23 execution, require:

1. a regression proving exact acceptance of the producer's 11-key comparison;
2. mutation tests for missing, extra, and false `independent_process_pids`;
3. full relevant tests and static checks;
4. a fresh R23 protocol/registry/source freeze;
5. independent Gate-0 passes;
6. fresh credentials, claims, output root, and no-retry launcher transaction.

No model or dataset download, GPU run, Slurm child step, or formal experiment is
authorized by R22.
