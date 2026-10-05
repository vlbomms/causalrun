# Gate 2: host-agent generation and recovery

Gate 2 uses the existing developer agent rather than an embedded model service.
The host agent inspects the controlled OpenAPI description, collects user intent,
and writes the pure verifier. causalrun embeds, validates, and approves that source.

Final result: **30 tests and 5 separate-process demonstrations passed; 0 failures**.
Gate 2 passes for the controlled receipt profile and host-agent generation workflow.
Four process schedules complete; the authorized-unsent schedule stays safely blocked.

## Acceptance traceability

| Criterion | Implementation | Evidence |
| --- | --- | --- |
| API discovery and selective interview | `discovery.py`, CLI `discover`/`interview` | OpenAPI/Swagger/ref/WSDL tests; actual PTY choices plus free text in demos |
| No separate findings report | Discovery is stdout-only; interview stores contract inputs | Demo discards discovery output; retains only answers and connector/source |
| Generate a controlled verifier | Host agent wrote `examples/verify_value.py`; `build` embeds source | Demo builds/registers source, then deletes input source/artifact files |
| Bind durable actions to exact verifier | Full artifact in SQLite; source/code/report hashes | Altered source rejected; old action cannot move to another connector version |
| Lost response after provider commit | Controlled socket disconnect after actual transaction | Runtime returns uncertainty; receipt verification commits with one provider POST |
| Crash around recording | Test-only exit at four protocol boundaries | Separate runtime/provider processes, SQLite recovery, stable replay, read-only recovery |
| Delayed completion | Hold POST before transaction, inspect, then release | Recorded pre/post timelines and independent provider counts |
| Missing/misleading evidence | Controlled missing/wrong ID/hash/value/error receipt responses | Each action stays blocked until valid evidence is restored |
| Validation detects incorrect generation | Inject always-true and always-false source | Validation failures retained; approval and target dispatch rejected |
| No known false conclusions or unsafe repeats | Independent SQL values/counts against observed runtime outcomes | Exact controlled scenarios and counts recorded; no general guarantee inferred |

## Reproduce

```sh
python3 -m tests.run_gate2
```

The runner includes all gate 1 regression tests. It records source hashes, versions,
commands, test output, five separate-process demonstrations, six threaded-runtime
fault timelines, and deliberately rejected verifier reports under
[results/gate-2](results/gate-2/README.md).

The five process schedules are: provider response loss; exit before authorization
commits; exit after authorization but before send; exit after provider commit but
before receipt recording; and exit after receipt recording. The authorized-unsent
case intentionally stays blocked with zero writes. Before-authorization rollback
permits one subsequent safe initial send. Other committed cases recover or reuse
receipts without replacement sends.

## Limits

- The initial generated source was written by Codex in this chat after inspecting
  the controlled API description. The CLI packages it; it does not invoke AI.
- Interactive demonstrations use a real pseudo-terminal with scripted user answers
  and approvals. No live OpenCode session or general question-UI integration is tested.
- Only the controlled value/receipt profile is supported. Arbitrary provider
  recovery, SOAP execution, YAML parsing, and GitHub generation remain outside scope.
- The pure verifier can confirm success or return unknown; it cannot conclude failure.
  Reported zero false failures reflects that restriction, not universal failure detection.
- A finite test suite can reject bad checks but cannot prove an arbitrary verifier.
- The approved target must be trusted to implement the controlled receipt contract.
  Validation never tests a production target by silently sending writes.
- Operator commands and database access require a separate trust boundary. The
  terminal prompt alone does not authenticate a human against a same-user agent.
- Source/interpreter changes invalidate existing approvals. New source is never
  substituted into an outstanding action during recovery.

See [the agent workflow](agent-workflow.md) for discovery, interview, and code constraints.
