# Gate 5 comparison protocol (declared before running the comparison)

This is a mechanical workflow comparison, not a human or live-model study.
Compare explicit operator CLI setup with installed OpenCode-assisted setup for
one controlled value-create operation. Both receive the same OpenAPI bytes,
expected behavior, three interview answers, and candidate verifier sources.
The scripted model fixture emits known tool calls; it does not reason or generate
new source. No participant authoring time or real-model correction rate is measured.

Run three paired trials in this fixed condition order:

1. Manual, assisted.
2. Assisted, manual.
3. Manual, assisted.

Each condition starts with a fresh database/profile and the same provider contract.
Exclude building/downloading the common installer and the test host from timing.
Count setup commands after installation; include service/host startup and restart
in elapsed machine time. These timing boundaries measure workflow overhead, not
human effort. Fixtures, model server startup, and teardown are test infrastructure,
not developer preparation commands. Record the boundaries separately.

The first supplied verifier is deliberately `return True`. It must fail validation
and must not be approved or dispatched. Supply the pinned matching verifier as the
single repair. Record that repair as an injected correction, not a developer/AI
mistake. Both paths must retain the failed validation and the corrected source.
No production-target validation writes are allowed.

Both paths must approve the exact corrected connector, perform one controlled
write whose response is lost after provider commit, observe IN_DOUBT, recover via
GET, repeat the same key without POST, retrieve the durable result, restart the
runtime, and retrieve the same action. Assisted runs additionally restart their
host, so do not present machine-time differences as an equal human latency comparison.

Record actual operator CLI invocations, native question count, approval count,
source candidates, injected corrections, total elapsed machine time, validation
failures, action states, and independent provider SQL object/write counts.
Report medians for the three repetitions without statistical significance claims.
Source files and OpenAPI bytes are hashed. Persist failed runs; do not omit them
from the comparison or substitute expected counts for observed counts.

Acceptance: all six recorded trials complete the defined workload, the bad candidate
is rejected in each, corrected validation passes, one initial provider write/object
per trial, and no repeated provider write. Missing evidence remains blocked in
separate fault schedules and is reported independently of completed outcomes.

This protocol can show which commands installation automates and whether verifier
validation/repair wiring works. It cannot establish reduced human development time,
superior model quality, arbitrary connector correctness, broad usefulness, scale,
or research novelty. Those require real participants/live generation and more APIs.
