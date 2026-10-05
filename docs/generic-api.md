# Broader API support

Status: gates A–D pass their declared scope. The generic HTTP/JSON adapter works
alongside the built-in controlled and GitHub connectors. See [usage](http-json.md)
and the evidence linked below. This does not establish universal API coverage.

## Developer use

Ask the agent to perform an API operation through causalrun. The agent reads the
API specification or official docs, checks authentication, and identifies how to
find evidence after a lost response. It asks the user only about unresolved intent,
access, or recovery assumptions. Secrets remain in local configuration.

Before sending a write, the agent prepares a connector, runs its checks, and asks
the user to approve it. Later actions can reuse the same approved connector.
Each action keeps a stable key across sessions.

The first expansion targets HTTP APIs with JSON bodies and JSON evidence. It is
not a claim to support every API, SOAP operation, upload, or shell command.
An API without enough evidence can still produce an unknown result. No generic
adapter can supply evidence that the application does not expose.

## Small implementation

Add one versioned HTTP/JSON connector alongside the existing connectors. Keep
SQLite, the durable action protocol, the pure generated verifier, and the existing
OpenCode and MCP adapters. Do not add a workflow engine or execute generated
network code.

The approved artifact contains:

- Exact API origin, operation identifier, API version, and essential documentation
  links.
- Write method (`POST`, `PUT`, `PATCH`, or `DELETE`), path, JSON body bindings,
  allowed headers, and expected response statuses.
- Read-only evidence request: `GET` path and query bindings, optional bounded
  pagination, and the evidence fields passed to the verifier.
- Correlation established before the write: an application-supported client ID,
  documented provider key, or an explicitly limited marker.
- Expected result description and the generated pure success predicate.
- Authentication references for write and read access. The artifact contains
  secret names, never secret values.
- Target restrictions, evidence limits, assumptions, validation, and approval
  digests.

Use a small declarative binding format for action ID and payload fields. Encode
path and query values separately. Reject bindings that can change the approved
origin. Pin evidence origins and credential destinations explicitly; do not follow
redirects. Bound response size, request time, page count, and total evidence size.

Support bearer tokens, API-key headers, and unauthenticated APIs first. OAuth
refresh and signed requests need separate adapters. Use HTTPS for remote targets;
allow loopback HTTP for controlled tests. Local/private targets require explicit
scope approval. Never pass credentials through environment proxy settings or
include them in review files, results, or provider-error messages.

The first version sends an authorized write at most once. A provider idempotency
key can aid correlation, but does not enable automatic resend. Safe idempotent
recovery needs a separate validated rule for provider semantics and retention.
An immediate response and later evidence use the same pinned success predicate.
HTTP success alone does not prove the expected application change.

## Gates and acceptance checks

| Gate | Change | Required evidence before proceeding |
| --- | --- | --- |
| A. Generic transport and artifact | Declarative requests, bindings, authentication references, target restrictions, generated verifier integration | Two different controlled API shapes work without service-specific runtime code; reject origin escape, unsafe headers, redirects, malformed bindings, missing secrets, and unapproved writes; confirm secrets stay out of outputs |
| B. Recovery and validation | Independent fixture oracle, evidence reads, bounded pagination, durable recovery | Test commit with lost response, delayed evidence, conflicting matches, wrong payload, unavailable reads, oversized responses, and process restart; repeat keys cause no new writes; missing evidence stays unknown; record actual request/object counts |
| C. Agent and harness use | Generic lookup/prepare/write inputs in OpenCode and MCP; documentation-based setup | Fresh OpenCode session prepares an unfamiliar JSON API operation, requests approval, writes, and recovers; reuse the same action from MCP; ask about success only when unclear; show blocked unsupported APIs and shell bypass limits |
| D. Third-party proof | One user-authorized disposable target with documented correlation or a usable status lookup | Record a real write and read-based confirmation, repeat the same key without a second write, and clean up only authorized resources; report fixture fault results separately from live provider evidence |

For every gate, save commands, versions, schedules, source digests, timelines,
actual counts, and failed runs under `docs/results/`. Fixture validation tests the
connector mechanics and supplied predicates; it does not certify undocumented
third-party guarantees. Failed acceptance checks block the next gate.

## Changes to existing modules

- `contracts.py`: validate the new artifact and bind its code to approval.
- New small HTTP adapter: build approved requests and normalize JSON evidence.
- `runtime.py`: dispatch and verify through that adapter while retaining current
  transactions and action identities.
- `validation.py`: select the new controlled conformance runner.
- `generation.py`, `native.py`, `mcp.py`, and the OpenCode plugin: accept the
  generic contract and expose the same review and action workflow.

Keep the current connectors and their tests working during this expansion.
Do not advertise arbitrary API support until the relevant gates pass.

## Recorded acceptance

| Gate | Evidence | Result |
| --- | --- | --- |
| A | [81 tests and two controlled shapes](results/http-gate-a/README.md) | Passed within the declared scope |
| B | [88 tests and four process boundaries](results/http-gate-b/README.md) | Passed within the declared scope |
| C | [92 tests and four actual host checks](results/http-gate-c/README.md) | Passed with a scripted model; live AI generation quality unmeasured |
| D | [96 tests, four host checks, and one live sandbox issue](results/http-gate-d/README.md) | Passed after read-only resumption; initial failed checks retained |
