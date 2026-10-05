# HTTP/JSON gate A evidence

Command: `python3 -m tests.run_http_gate_a`.

81 tests passed, including 16 new generic adapter tests. Zero failures, errors,
or skips. Two controlled demonstrations passed: POST to an entry collection and
PUT to a record path. The independent fixture recorded two write requests, two
objects, and zero evidence reads. Repeating both action keys added no writes.

- [Tests, versions, and source hashes](tests.json)
- [Full test output](tests.txt)
- [Actions, validation reports, timelines, and oracle counts](demonstration.json)

Acceptance: two shapes without provider-specific runtime code; missing validation
and approval block dispatch; missing credentials leave no authorization; unsafe
origins, headers, bindings, and mutating evidence requests fail; redirects are not
followed; responses are bounded; reflected configured credentials are rejected.

Validation uses supplied pure fixtures and sends no remote validation requests.
It does not certify third-party semantics. Test approval calls the operator
function; this gate is not a human or OpenCode approval demonstration.

Gate A passes its declared scope. Recovery faults, pagination, harness use, and
live third-party acceptance belong to later gates. No failed run occurred in this
gate. The initial focused run passed 16 tests before the recorded full run.
