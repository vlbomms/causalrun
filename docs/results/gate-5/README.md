# Recorded gate 5 evidence

Run from the checkout with Python 3.10+, macOS/Linux:

```sh
npm install --prefix .local/opencode-test --no-audit --no-fund opencode-ai@1.18.34 @opencode-ai/plugin@1.18.34
python3 -m tests.run_gate5
python3 -m tests.demo_gate5_reuse
python3 -m tests.evaluate_gate5
python3 -m causalrun.installer --build .local/dist/causalrun.pyz
```

The Codex CLI must be installed separately. Recorded version: 0.159.0-alpha.12.1.
The demonstration ignores user config/rules, uses ephemeral temporary projects and
explicit local model-provider overrides, and leaves the user's Codex configuration
unchanged. Local scripted models serve Chat Completions to actual OpenCode and
Responses SSE to actual Codex. No paid inference is performed. Test tokens are
public disposable fixture strings. None of these tests performs a GitHub write.

## Final evidence

- `tests.json` / `tests.txt`: 57 tests passed; 0 failures/errors/skips; commands,
  versions, source hashes, and actual elapsed time.
- `reuse-demonstration.json`: three checks passed; 0 failures. Fresh install,
  OpenCode discovery/questions/validation/approval, commit with response loss,
  read recovery, SIGKILL host/runtime and restart, then Codex calls the same
  connector/key. Independent SQL: one action, one approval, one provider object,
  one provider POST. Full host messages, permissions, and timeline are recorded.
- `codex-attempt.json`: final actual CLI events. Three completed MCP calls with
  original action identity and COMMITTED results. The fixture model generates a
  metadata warning because its model name is intentionally synthetic.
- `fault-schedules.json`: seven explicit schedules (five evidence faults, delayed
  commit, and packaged MCP process restart after lost response). Seven blocked
  IN_DOUBT observations, all seven subsequently confirmed when real evidence
  becomes available, seven provider POSTs total. Zero known false success/failure
  or unsafe repeats in these asserted schedules. These are not random trials or
  a guarantee for every third-party API.
- `evaluation.json`: six paired trials, all passed under `evaluation-protocol.md`.
  Every trial rejects the deliberately unsound candidate, records one supplied
  repair, and creates exactly one provider object with one POST. Counted manual
  CLI invocations: 11; assisted: 0, excluding common installation/test scaffolding.
  Both require three question answers and one approval. Exact machine timing
  medians are in the report; human authoring time is null. No live AI generation
  quality or human productivity claim follows from this scripted replay.
- `installer.json`: final artifact SHA-256, bytes, execution digest, and source
  consistency checks. The ignored local artifact is not a published release.

## Failures retained

| Record | Observed failure and correction |
| --- | --- |
| `initial-reuse-1.json`, `initial-codex-1.json` | MCP rejected Codex's optional tools/list metadata. Accept standard metadata and null cursor while keeping tool arguments strict. |
| `initial-reuse-2.json`, `initial-codex-2.json` | Fixture searched flat tool definitions; Codex advertised a namespace. Traverse namespace definitions. |
| `initial-reuse-3.json`, `initial-codex-3.json` | **Invalid early pass:** calls used dotted function names and were rejected by Codex, but the initial assertion counted requested calls. Emit the Responses namespace field and require actual completed host tool events/original action ID. This run is not acceptance evidence. |
| `initial-reuse-4.json`, `initial-codex-4.json` | Codex's own write permission policy rejected the write call. Configure explicit permission for this preapproved disposable replay only; keep ordinary installation policy unchanged. |
| `initial-review-test.json` | Preliminary suite: 9/10 passed, one failed. Wrong digest was rejected, but zipapp returned exit code 0. Preserve main's exit status; final test verifies rejection and subsequent correct interactive approval. |

`pre-final-*`, `pre-schedule-alignment-evaluation.json`, and `preliminary-tests.txt`
retain intermediate passing results before final packaging/schedule alignment.
The final files listed above control acceptance. Full prior gate evidence remains
unchanged. Marker-copy/edit risks, bounded third-party listings, missing evidence,
same-user shell bypass, and untested host versions remain explicit limitations.
