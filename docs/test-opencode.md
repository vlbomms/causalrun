# Try selective questions in OpenCode

The local test profile is isolated from your normal OpenCode config. From the
checkout, build/install if these directories are not already prepared:

```sh
python3 -m causalrun.installer --build .local/dist/causalrun.pyz
python3 .local/dist/causalrun.pyz --config-dir .local/opencode-manual-config --state-dir .local/opencode-manual-state
```

In terminal 1, start the disposable provider. These tokens are public demonstration
strings, not real credentials. Keep this terminal running:

```sh
cd /Users/vikasbommineni/Documents/causalrun
CAUSALRUN_PROVIDER_TOKEN=manual-provider-write-token \
CAUSALRUN_RECEIPT_TOKEN=manual-provider-read-token \
python3 -m examples.provider --db .local/manual-provider.sqlite --port 8090 --fault drop_response
```

In terminal 2, launch the tested OpenCode version with the isolated profile:

```sh
cd /Users/vikasbommineni/Documents/causalrun
OPENCODE_CONFIG_DIR="$PWD/.local/opencode-manual-config" \
CAUSALRUN_PROVIDER_TOKEN=manual-provider-write-token \
CAUSALRUN_RECEIPT_TOKEN=manual-provider-read-token \
./.local/opencode-test/node_modules/.bin/opencode
```

Select/connect your usual model. Paste this prompt:

> Use causalrun to create the value "hello from OpenCode" at http://127.0.0.1:8090.
> Use operation controlled.value.create.v1, action_key manual-demo/value-001, and
> payload {"value":"hello from OpenCode"}. Read http://127.0.0.1:8090/openapi.json
> first and infer success from that documentation and this request. Do not ask me
> to restate a clear success condition. Validation may use the disposable local
> fixture only. Keep uncertain writes blocked and request review; never resend
> them. Generate the verifier and use causalrun_prepare, omitting expected_behavior
> if the documented predicate is sufficient. Wait for my connector approval.
> After sending, show the initial action state, then use causalrun_verify to recover.
> Use causalrun_result with details=true only when I ask for the full timeline. Use only causalrun tools for
> the write; do not use curl, shell scripts, or another writer.

Read the full review file linked by the short permission prompt. Then allow the exact write rule. Expected: no success
question, no repeated questions for consent/policy already stated here, one review
prompt, initial IN_DOUBT from the deliberately dropped response, then COMMITTED
from read-only receipt evidence. The journal must preserve both stages. Model
behavior may differ; the automated host tests use scripted calls and do not prove
that your live model follows the guidance.

Ask next:

> Repeat the same causalrun_write with action_key manual-demo/value-001 and the
> identical payload, then retrieve its result. Reuse the original connector and
> action ID. Do not send another provider write.

With the provider running, check independent counts in another terminal:

```sh
python3 - <<'PY'
import sqlite3
with sqlite3.connect('.local/manual-provider.sqlite') as db:
    print('objects:', db.execute('SELECT count(*) FROM values_and_receipts').fetchone()[0])
    print('POSTs:', db.execute('SELECT count(*) FROM requests').fetchone()[0])
PY
```

Expect one object and one POST for a fresh database and this sole action. Repeating
this whole demo with the same stored action returns its durable result, so the
initial IN_DOUBT stage only occurs on the first execution. For a new demonstration
use a new intentional logical action key, not a replacement key for uncertain work;
counts will then include both actions.

To exercise genuine ambiguity without another write, ask:

> Prepare a new controlled-value connector but do not write. My success condition
> might mean storing the value or completing a downstream approval; I have not
> decided. Inspect the API, set needs_success_clarification=true, and ask only the
> unresolved question. Do not assume a completed downstream approval from a value
> receipt. Keep my earlier fixture authorization and blocked-uncertainty policy.

The agent should ask a focused clarification. If you require downstream approval,
the current value profile cannot establish that condition; stop rather than invent
an endpoint or claim the fixture validates that business requirement.

Quit OpenCode and Ctrl-C the provider when done. The local runtime may remain up:

```sh
python3 .local/dist/causalrun.pyz --stop --state-dir .local/opencode-manual-state
```
