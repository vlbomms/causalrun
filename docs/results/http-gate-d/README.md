# HTTP/JSON gate D evidence

Commands:

```sh
python3 -m tests.run_http_gate_d
python3 -m tests.demo_http_live --live
python3 -m tests.demo_http_live --resume docs/results/http-gate-d/live-20261005T014720Z.json
```

Final regressions: 96 tests passed; zero failures, errors, or skips. Two controlled
API shapes and four actual OpenCode/MCP host checks also passed. The host model
was scripted; live AI generation quality remains unmeasured.

The live test created [tempo issue #3](https://github.com/vlbomms/tempo/issues/3)
through a generic HTTP/JSON artifact. It did not use the built-in GitHub adapter.
The test interceptor received the real POST response, then withheld it from the
runtime. This is client-side fault injection, not an actual network outage.
The runtime retained the action as unknown.

The first independent listing assertion failed before runtime verification.
Cleanup closed that one issue. A later read-only resumption confirmed the same
saved action using the approved generic GET lookup. An independent listing found
one matching object. Repeating the key and retrieving the result caused no send.
Total observed connector calls: one creation POST and one recovery GET. Independent
oracle calls: three reads across the initial and resumed tests. Cleanup: one PATCH.
The initial repository/user configuration reads and later diagnostic reads are
separate from those connector/oracle counters.

## Files and retained failures

- [96-test output](tests.txt), [versions and source hashes](tests.json)
- [Host approval, restart, and shared action](host.json)
- [Controlled demonstration](demonstration.json), [fault schedules](schedules.json)
- [Final live recovery and counters](live.json)
- [Failed initial live run](live-20261005T014720Z.json)
- [Blocked pagination preflight](preflight-attempt-1.json): an underscore in
  `per_page` was rejected by header syntax; zero provider requests; query-name
  validation fixed and regression tested.
- [Failed first resume driver](resume-attempt-1.json): a relative report path was
  compared with an absolute repository path; zero provider requests; path resolved
  before the successful resumption.

The initial listing contents were not retained. Delayed visibility is a possible
explanation for its failed assertion, not a proven cause. The later independent
listing established one matching closed issue. No replacement issue was created.
The original failed report stays unchanged; `live.json` points to the final result.

## Acceptance traceability

| Requirement | Recorded result |
| --- | --- |
| Real authorized third-party write | One issue created in the previously authorized `vlbomms/tempo` sandbox |
| Application-specific confirmation | Exact body marker, requested title, repository, creator, and non-PR predicate; generic requests only |
| Ambiguous write response | Runtime initially IN_DOUBT after the withheld response |
| Read recovery | Original action becomes COMMITTED through the pinned GET verifier |
| No duplicate send | Same key returns the original action; oracle finds one matching issue |
| Cleanup | Only issue #3 closed; existing issues untouched |
| Mechanical regression and host use | 96 tests; two controlled shapes; four actual host checks passed |
| Limits retained | Marker assumptions, bounded non-snapshot reads, privileged token, shell bypasses, and scripted generation stated |

Gate D passes this declared scope after read-only resumption. This does not prove
universal API coverage, third-party exactly-once guarantees, or live model quality.
The failed live check and two driver/preflight failures above remain part of the
record. No paid inference or infrastructure was used.
