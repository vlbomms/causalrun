# Gate 5: shared connectors and a second harness

Gate 5 passes for the declared local MCP integration and mechanical workflow
comparison. It does not establish human productivity, live model generation quality,
arbitrary API correctness, or universal write interception.

## Acceptance traceability

| Requirement | Implementation | Recorded evidence |
| --- | --- | --- |
| Stable harness API | Documented HTTP action API v1 and five schema-bearing stdio MCP tools | [API contract](harness-api.md), protocol/input/real-stdio tests |
| Second lightweight adapter | Standard-library MCP, installed zipapp entry point, separate operator-terminal review | Actual Codex CLI and packaged MCP preparation/review/restart tests |
| Same connector in two hosts | Shared scope binding, exact digest/approval, original key and SQLite action | Actual OpenCode followed by Codex: one action, one approval, one provider POST/object |
| Comparison of effort and corrections | Three paired manual/assisted runs; injected bad source then one repair | Six passing trials, 11 versus 0 operator CLI commands after installation, three questions and one approval in both conditions |
| Fault and unknown outcomes | Strict adapter inputs, no approval tool, no resend, read-only recovery | Seven blocked observations followed by seven recoveries, seven provider POSTs; no failure verdicts |
| Reproducible setup | Local zipapp build, MCP/Codex configuration, commands/versions/source hashes | [Installation](install-mcp.md), [results](results/gate-5/README.md) |

The full regression suite has 57 tests: 46 existing tests and 11 new gate 5 tests.
All pass with zero failures, errors, or skips. The actual-host demonstration has
three passing checks: first OpenCode execution/recovery, host/runtime restart, and
Codex reuse. Its local model fixtures supply scripted calls, not model inference.
No paid inference or new GitHub writes were used for gate 5.

The comparison's first source candidate is deliberately wrong. Validation catches
it in all six final trials; one supplied correction passes. Assisted setup removes
manual packaging/register/validate/serve commands. It still asks the developer
three questions and requests approval once. The recorded machine timings include
host startup/restart only in the assisted condition and cannot establish human time
saved. No authoring time or real AI correction rate was measured.

MCP mediates its own tools. It does not hold writes from arbitrary Codex tools,
shell scripts, browsers, or other servers. OpenCode's earlier supported-tool hooks
remain the only automatic interception tested. Approval separation assumes a
trusted operator terminal; the same OS user's unrestricted shell can bypass it.
Third-party marker evidence retains gate 3's documented assumptions and uncertainty.

Initial interoperability, fixture, and review-exit failures are retained and
explained in the results. One early demonstration incorrectly counted requested
model calls as success while Codex rejected them; it is explicitly invalidated.
Final acceptance requires three actual completed MCP calls returning the original
action, plus independent runtime/provider SQL counts.
