# Gate 1: contracts and preflight

The checkout contains only the new Python/SQLite implementation. No old runtime
code or historical results are reused to establish this gate.

## Acceptance traceability

| Acceptance criterion | Implementation | Evidence |
| --- | --- | --- |
| Versioned artifact with expected behavior and verifier | `causalrun/contracts.py` | Missing verifier and changed artifact rejected |
| Validation required before write | `validation.py`, `runtime.preflight` | Missing, failed, corrupted, and replaced validation blocked |
| Exact version approved through operator review | Local interactive `approve` command | Actual PTY CLI acceptance; noninteractive and wrong confirmation rejected |
| Agent cannot submit approval | `server.py` exposes no approval endpoint | Agent approval request rejected; provider credential rejected as agent token |
| Changes invalidate approval | Artifact/implementation/report hashes | Changed target, source notes, implementation, and validation blocked |
| One accepted write and inspectable receipt | Controlled atomic value/receipt; durable action journal | Separate-process demo: one domain object, one provider POST |
| Durable result retrieval | GET and stable action replay | Runtime process restarted; same record returned with no extra write |

The approval boundary assumes the operator CLI/database are outside the agent's
access. Interactive prompting prevents accidental pipe-based approval but does
not authenticate a human or sandbox a same-user shell. No OpenCode enforcement
or platform integration is claimed at this gate.

## Verification

Final result: **17 tests passed, 0 failed, 0 errors, 0 skipped**. The separate-process
demonstration passed all **8 steps**, with **1 domain object and 1 provider write**
on the approved target. Gate 1 passes for the fixed controlled connector and the
operator/agent access boundary described below.

Run `python3 -m tests.run_gate1` from the checkout. Full results are in
[tests.json](results/gate-1/tests.json), [test output](results/gate-1/tests.txt),
and [the demonstration](results/gate-1/demonstration.json).

The suite exercises actual HTTP and SQLite, including concurrent repeats. Validation
uses a dedicated temporary provider; its two POSTs create one sandbox object.
The approved demonstration target is separate: one POST creates one object.
It rejects missing verifier/validation/approval and changed artifact/target before
writing, then restarts the runtime and performs GET plus repeated submission.

The first run had 14 tests: 12 passed and 2 failed. The helper treated every 404 as
an absent receipt, hiding ordinary API errors. The fix limits missing-receipt
handling to explicit verifier lookups. That run is preserved in
[initial-test-run.json](results/gate-1/initial-test-run.json). Later tests add failed
validation and conflicting-receipt scenarios; consult the final report for counts.

## Declared limits

- The verifier is fixed code, not AI-generated code. Generation is gate 2.
- The controlled application exposes an authoritative receipt. Unknown outcomes
  cannot be declared failures and do not permit replacement sends.
- A crash after authorization but before sending can leave an action blocked.
- Artifact validation covers the sandbox implementation, not arbitrary target behavior.
- Only `payload.value` is supported; targets are fixed loopback HTTP origins.
- The API capability spans local approved connectors. No multi-tenant isolation,
  per-task grants, native installer, or OpenCode adapter is included.
- No power-loss, production-load, or universal exactly-once claim follows from these tests.

Do not expand scope until the recorded final checks and demo pass.
