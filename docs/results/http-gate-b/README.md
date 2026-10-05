# HTTP/JSON gate B evidence

Command: `python3 -m tests.run_http_gate_b`.

88 tests passed, including seven new recovery tests. Zero failures, errors, or
skips. The two normal demonstrations also passed with two writes and two objects.

- [Tests, versions, source hashes](tests.json)
- [Full output](tests.txt)
- [Normal action timelines](demonstration.json)
- [Fault schedules and action timelines](schedules.json)

Acceptance traceability:

| Requirement | Actual check |
| --- | --- |
| Commit with lost response | One write/object; missing, wrong, and unavailable reads stay unknown; fourth read confirms |
| Delayed evidence | Hidden committed object stays unknown until exposed; repeat key never sends |
| Invalid immediate result | Wrong action ID in response blocks confirmation; later read confirms |
| Conflict handling | Two exact marker matches fail the pure unique-match predicate |
| Bounded pagination | Three items over two pages succeed; reaching page cap rejects partial evidence |
| Process durability | Exit 71 before authorization commit, after authorization commit, after provider commit, and after receipt commit |
| Repeats | Pre-commit crash leaves no action; post-authorization crash with no send leaves unknown and blocks replacement; post-provider crash recovers by read; post-receipt crash returns saved result |

Gate B passes its declared controlled scope. This is not live third-party fault
injection, human approval validation, or proof that a paginated service is a stable
snapshot. Positive marker evidence depends on the approved application assumptions.
No failed run occurred. The initial focused run passed seven tests before this full run.
