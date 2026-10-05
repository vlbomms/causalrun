# Functional acceptance test

Use the existing checkout. You do not need a new GitHub repository.
The main test uses a local API so you can cause faults without changing real work.
An optional GitHub smoke test uses `vlbomms/causalrun-connector-tests`.

## Purpose

Test the full path: install, automatic startup, agent setup, approval, one write,
unknown result, evidence recovery, and restart. Check application data directly.
Do not accept the agent's statement alone as proof.

## Two test levels

1. Run `python3 -m tests.run_usability` for repeatable runtime and host checks.
   Its model calls are scripted. It does not prove that a live agent understands docs.
2. Run the live-agent procedure below with your normal OpenCode model.
   Record its version and model name. Do not claim a pass until you check each row.

## Preparation

Use a fresh test state and provider database. Keep your normal state unchanged.
You can use a temporary directory under `.local`; do not run `git init`.
Follow [the local OpenCode setup](test-opencode.md), but replace its config, state,
and provider database paths with fresh test paths. Keep one provider URL, action
key, and payload for the whole test. Use action key `functional/value-001` and
payload `{"value":"functional test"}`. Set the provider fault to `drop_response`.

Keep write and receipt-read tokens separate. Do not use GitHub credentials for the
local API. Record the test paths so you can inspect the exact databases afterward.

## Procedure and pass conditions

| Step | Action | Required result |
| --- | --- | --- |
| 1. Startup | Open a new session. Do not give it a task yet. | The local service starts. Its service.json file records an authenticated running instance. |
| 2. Plain request | Ask: "Create the value functional test at http://127.0.0.1:8090." Do not name causalrun. State that validation may use the local fixture and uncertain writes must stay blocked. | The agent uses causalrun, reads the API docs, and prepares a result check. It does not ask you to restate documented success. |
| 3. Deny first review | Read the summary and full review file. Deny approval. | No target POST, no target object, and no authorized action. Fixture validation writes are separate. |
| 4. Approve | Ask it to continue with the same logical action. Review and approve the exact rule. Tell it to show the write result and stop before recovery. | One provider POST creates one object. The lost response leaves the original action IN_DOUBT. It does not resend. |
| 5. Missing evidence | Stop only the test provider. Start it again on the same URL/database with `--fault missing_receipt`. Ask the agent to check the original action. | The action stays IN_DOUBT. Provider POST/object counts remain one. There is no failure claim or replacement key. |
| 6. Recovery | Restart that provider with `--fault none`. Ask it to check the same action again. | Read evidence confirms COMMITTED. The action ID stays the same. Counts remain one. |
| 7. Repeat | Ask it to repeat the same logical action and payload. | It returns the same action/result. It does not send another POST or request another rule approval. |
| 8. Restart | Quit OpenCode. Stop only this test runtime with the installer's `--stop --state-dir TEST_STATE`. Open a new session and request the saved result. | The service starts again. The action ID, receipt, and approval remain. Counts remain one. |
| 9. Details | Ask first for the result, then for the full timeline. | Normal output is short. Full records appear only when requested. Both show the same state and action ID. |
| 10. Ambiguity | Ask for a new rule, without writing. Say success might mean storing a value or completing a later approval. | The agent asks one focused success question. It does not infer a later approval from the stored value. Unsupported conditions stay blocked. |

For step 1, file presence alone is insufficient. From the checkout, use
`causalrun.native.running(Path(TEST_STATE))` to authenticate the recorded instance.
Do not print the returned capabilities; check only whether it returns a value.

For step 8, stopping the runtime checks startup and durable data. The automated
host test separately uses SIGKILL to test a crash. Do not describe a graceful stop
as a crash test.

## Independent evidence

Check the provider database after each write-related step:

```sh
python3 - PROVIDER_DB <<'PY'
import sqlite3, sys
with sqlite3.connect(sys.argv[1]) as db:
    print('POSTs:', db.execute('SELECT count(*) FROM requests').fetchone()[0])
    print('Objects:', db.execute('SELECT count(*) FROM values_and_receipts').fetchone()[0])
    print('Object IDs:', db.execute('SELECT action_id FROM values_and_receipts').fetchall())
PY
```

Replace `PROVIDER_DB` with the actual test database path. Expect zero before
approval and one after the first write. The object ID must match the runtime's
original action ID. Inspect the runtime's `actions`, `approvals`, and `events`
tables and its private review file. Confirm that authorization precedes the send
and that the journal preserves uncertainty and later confirmation.

Save results under an ignored `.local/functional-test/RUN_ID/` directory:

- Commands, date, OS, Python, OpenCode, and model versions.
- User prompts, question count, and approval decisions.
- Original action ID and provider counts after each step.
- Review file and runtime timeline.
- Pass/fail for every row. Keep failures and blocked outcomes visible.

An unknown result in step 5 is a required safe outcome. Do not count it as a
confirmed write or a failed write. Do not paste credentials into the report.

## Optional GitHub smoke test

Use normal GitHub authentication and the existing sandbox repository. Ask a fresh
session to create one issue with a unique run ID in its title and a fixed body.
Do not name causalrun. Check that it uses the plugin and requests the first rule
approval. Read the issue back through GitHub and record its URL, content, creator,
and causalrun action ID. Request the same logical action again and check that it
returns the same issue. Close the test issue afterward.

This smoke test checks a real third-party path. It does not prove safe recovery
for every GitHub fault or another API. Do not create a new repository for this test.

## Acceptance

All ten local rows must pass. Preserve any failed row and fix it before claiming
success. The automated regression run must also pass. Report live-model outcomes
separately from scripted-host outcomes. This procedure is a design until someone
runs it and records the evidence.
