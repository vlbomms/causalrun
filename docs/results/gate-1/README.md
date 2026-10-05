# Gate 1 recorded results

Command: `python3 -m tests.run_gate1`

- Final suite: 17 passed, 0 failed, 0 errors, 0 skipped.
- Separate-process demonstration: 8 steps passed, 0 failed.
- Approved target: 1 domain object, 1 provider POST; no extra write after restart/read/replay.
- Validation fixture: 4 checks passed; 1 sandbox object and 2 idempotent POSTs.
- Initial run: 12 passed, 2 failed; retained in `initial-test-run.json`.

`tests.json` records versions, time, elapsed duration, and all source hashes.
`tests.txt` records each test outcome. `demonstration.json` contains the exact
artifact, action ID, approval step, rejection statuses, provider counts, and durable
journal. Temporary databases were isolated and removed after each run. No real
third-party targets, model calls, or OpenCode installation were used.

The operator confirmation was exercised through a real CLI pseudo-terminal with
disposable test approvals. This tests the interactive path; it does not establish
human identity or isolation from an unrestricted same-user shell.
