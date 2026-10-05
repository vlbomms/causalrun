# Harness API v1

The HTTP `/v1` endpoints and five MCP tools share the same SQLite records. Keep
one state directory when switching harnesses. Keep the original logical action key
and payload: inventing a new key creates a different action and can duplicate a write.
Connector digest pins scope, source, execution code, expectations, and approval.
Changing an artifact or implementation requires validation and approval again.

## MCP stdio

Python 3.10+ on macOS/Linux; no Python packages or Docker required. The adapter
uses newline-delimited JSON-RPC on stdin/stdout; logs stay out of stdout. Initialize,
send `notifications/initialized`, then use `tools/list` and `tools/call`. Tool schemas
come from `tools/list`; unknown argument fields are rejected. Messages are limited
to 16 KiB. Tested protocol negotiation: 2025-11-25. Standard optional listing
metadata is accepted. Resources, prompts, streaming HTTP, and pagination are absent.

| Tool | Inputs | Behavior |
| --- | --- | --- |
| `causalrun_lookup` | `operation`, `target` or `repository` | Approved binding or discovery/authentication/interview guidance |
| `causalrun_prepare` | Scope, `source`, `answers`, controlled `api_version` | Persist and validate source in disposable fixtures; return full review and validation report |
| `causalrun_write` | Scope, `action_key`, `payload` | Hold first use or execute exact approved connector; duplicate keys never resend |
| `causalrun_verify` | `action_id` | Read provider evidence for the original obligation; persist a supported positive result |
| `causalrun_result` | `action_id` | Read saved action, receipt, and journal without a provider request |

Operations: `controlled.value.create.v1` with loopback `target`, or
`github.issue.create.v1` with `owner/repository`. `answers` and `payload` are string-valued
objects. The controlled payload has `value`; GitHub has `title` and `body`.
Omit `answers.expected_behavior` when the request and documentation establish the
profile's success predicate. `needs_success_clarification=true` adds the success
question and requires its answer before preparation; resolve it before sending a
write. An existing approval does not silently resolve newly flagged ambiguity.
Sandbox/marker authorization must still be supplied from actual user consent.

`source` is `def verify(action_id, payload, evidence)` with one pure boolean return
expression; the preparation guidance lists supported fields and language limits.
The agent must discover the actual API and obtain actual user answers before preparing.

Tools have no approval operation. Preparation returns `REVIEW_REQUIRED` or
`VALIDATION_FAILED`. A write without approval returns `PREPARATION_REQUIRED`.
Protocol errors use JSON-RPC codes -32700, -32600, -32601, or -32602.
Runtime/tool errors return `isError: true` with a credential-safe message. A failed
call does not establish that a remote write failed. Inspect the original action.

## OpenCode display

OpenCode returns a short action summary by default: `id`, `state`, and `message`.
Use `details=true` on `causalrun_result` or `causalrun_verify` for the complete
receipt and journal. The HTTP and MCP result formats remain complete.
The rule approval prompt contains a summary and a private full review file.
Its two content hashes must match the artifact and report in that file.

## HTTP

The local service binds loopback. Send `Authorization: Bearer <agent capability>`.
Provider credentials stay in the service. Request JSON objects are at most 16 KiB.

| Method/path | Body | Response |
| --- | --- | --- |
| `POST /v1/actions` | `connector_digest`, `action_key`, `payload` | Original or newly authorized action |
| `GET /v1/actions/{id}` | None | Saved action, receipt, ordered journal |
| `POST /v1/actions/{id}/verify` | `{}` | Original action after read-only evidence check |

HTTP errors: 400 invalid inputs/profile, 401 invalid capability, 404 missing action
or route, 409 contract/preflight/key conflict, 500 internal error. Do not blindly
retry writes after errors. Repeat only the exact original logical key/payload through
the runtime; an existing authorization is returned without another provider send.

An action includes `id`, `connector_digest`, `action_key`, `payload`, `state`,
`receipt`, and `events`. `COMMITTED` means the approved verifier accepted positive
evidence under its stated assumptions. `IN_DOUBT` means unresolved; missing,
misleading, inaccessible, or delayed evidence does not establish failure.
Authorization and its journal commit together before the one provider call.
Receipts and their journal commit together afterward. Provider calls are outside
transactions and transport retries are disabled.

`/native/lookup`, `/native/prepare`, and `/native/status` are local installation
helpers, not the stable HTTP action API. `/native/approve` requires a separate
operator capability and exact displayed artifact/report/scope. MCP never exposes it.
Version 1 consumers must use declared fields and states; incompatible action
semantics require a new API major version. Connector schema versions remain separate.

## Boundary

MCP mediates calls to these tools. It does not intercept another tool, shell script,
browser request, or MCP server. This is durable external-action tracking, not durable
agent reasoning or general workflow orchestration. Operator capabilities are local
files owned by the same OS user: an unrestricted agent with shell/file access can
bypass this approval separation. Run review from a trusted operator terminal and
limit the agent's capabilities when that boundary matters.
