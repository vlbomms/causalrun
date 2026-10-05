# Gate 3 recorded results

Executed on October 4, 2026. The evidence files contain actual timestamps, versions,
connector/implementation digests, source hashes, provider IDs, and action journals.

Commands:

```sh
python3 -m tests.run_gate3
python3 -m tests.demo_gate3_live --repository vlbomms/causalrun-connector-tests
```

- Final regression: **36 passed, 0 failures, 0 errors, 0 skips**. This includes all
  30 tests from gates 1–2 and six GitHub tests.
- Final connector validation: **11 passed, 0 failures**, two controlled creation
  POSTs. The fixture is deliberately non-idempotent; a second creation POST would
  create a second issue. Its oracle state is separate from the runtime database.
- Final live run: **2 demonstrations passed, 0 failures**, exactly two creation
  POSTs, issues **13 and 14**, both closed and read back as closed. Recovery used
  the normal HTTP agent API. The normal write committed immediately. The lost
  response left IN_DOUBT; marker removal and repeated submission stayed blocked.
  After restoration, three recovery reads remained IN_DOUBT; the fourth confirmed
  success. Recorded results were then retrieved without provider lookups or writes.
- Across both live runs: **4 issue-creation POSTs**, issues **11–14**, all closed.
  Do not report the final run's two POSTs as the total cost of this gate.

Failed attempts are retained:

- `initial-tests.json` / `initial-tests.txt`: **35 passed, 1 failed**. The pagination
  budget test used a route missing the final `/issues` resource component. The
  adapter rejected it after one read; fixing the fixture URL exercised all ten pages.
- `initial-live-demonstration.json`: **1 passed, 1 failed assertion**, two creations,
  issues **11 and 12**, both closed. The initial script required immediate recovery
  after restoring the marker. A subsequent read found the issue. The final script
  records up to 20 one-second read checks rather than treating temporarily missing
  evidence as failure. The final run directly observed three uncertain reads.
  The initial run did not record an assertion line or its incomplete second timeline;
  do not interpret it as a complete trace or a proved provider consistency guarantee.

`tests.json` hashes the sources at regression time. The live helper was subsequently
changed to record bounded polling and failure locations; its final hash is in the
live report. Runtime/adapter/verifier source did not change after the passing regression.

The live test uses local GitHub CLI credentials held only in memory. The token has
write privileges; saved verifier source has no credentials/network access, and
recovery calls only GET. The developer authorized this dedicated repository in chat.
The test harness supplies contract answers and PTY approval; this is not a production
OpenCode approval demonstration. Response loss is a deliberate exception after a
real GitHub response, not a dropped network packet. Deleted evidence and conflicting
markers are controlled-fixture tests. The live tests exercise real content edits.
No arbitrary API certainty, snapshot listing, or universal interception is claimed.

See [acceptance traceability](../../gate-3.md). Gate 4 remains unimplemented.
