# Gate 4 recorded evidence

Recorded on October 4, 2026. The final `tests.json`, `tests.txt`, and
`demonstration.json` contain actual results and complete host messages/approval
metadata. Source hashes bind the interpreted runtime, fixture, and test driver.

Reproduce on macOS/Linux with Node/npm available for the test host:

```sh
npm install --prefix .local/opencode-test --no-audit --no-fund \
  opencode-ai@1.18.34 @opencode-ai/plugin@1.18.34
python3 -m tests.run_gate4
```

The user-facing installer needs Python and an existing OpenCode host; Node/npm here
install the pinned test host locally, not additional Python runtime dependencies.
No global OpenCode configuration was changed by the demonstration.

Final acceptance: **46 tests passed, zero failures/errors/skips**, and
**two actual OpenCode demonstrations passed**. The final JSON counters are the
authority for these results. `installer.json` records the built archive size/hash
and implementation digest; all regression source hashes were checked after packaging. The host first
holds direct and unprepared writes, reads the actual provider OpenAPI, issues a
three-question request, validates saved source, and requests exact connector
permission. Socket closure after a real local commit must produce IN_DOUBT; a
receipt GET must confirm it without another POST. After SIGKILL of both OpenCode
and the runtime, the same persisted host session/action/approval must remain usable.
Independent provider SQL supplies object and creation-write counts.

The final demonstration recorded one configured-provider object and one creation POST;
validation uses separate disposable fixtures, with their counts in permission
metadata. Do not combine these scopes or describe the scripted source as model
inference. All model calls target the local scripted HTTP provider; no paid inference
service is used. Actual OpenCode native questions/permissions are answered by test
code, not a human participant. Arbitrary shell interception is not tested or claimed.

Preserved attempts:

- `initial-demonstration-1.json`: failed before any model/tool call because the
  test driver treated OpenCode's warning line as its listening URL.
- `initial-demonstration-2.json`: failed before tool calls because the driver tried
  to decode an empty prompt-admission response as JSON.
- `pre-hardening-demonstration.json`: two install/restart passes before credential
  routing was tightened. It did **not** drop the response; do not use it as recovery
  fault evidence.
- `pre-followup-tests.*` / `pre-followup-demonstration.json`: 44 tests and two basic
  host demos passed, again before explicit fault-state assertions exposed the setup
  mistake. These prove their recorded normal behavior, not lost-response recovery.
- `followup-tests.*`: eight tests passed (two new checks plus six imported repeat
  cases). The driver was then adjusted to avoid rediscovering imported test classes.
- `pre-guide-tests.*`: 46 tests passed before first-use guidance was expanded.
- `initial-demonstration-3.json`: failed the new explicit IN_DOUBT assertion. The
  fixture used an unused `drop_response` attribute and passed the read token into
  the positional fault-mode argument. Corrected to `fault_mode='drop_response'`
  and the named `receipt_token` argument. No runtime safety violation was observed;
  the intended fault had not actually been injected in earlier host runs.

The final passing run supersedes these partial attempts; all are retained.
See [gate 4 traceability](../../gate-4.md) and [installation](../../install-opencode.md).
