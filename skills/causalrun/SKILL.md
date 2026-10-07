---
name: causalrun
description: Use causalrun for external API writes requested in ordinary development tasks, such as creating GitHub issues or changing third-party application data. Prepare or reuse a saved result check before sending, and recover uncertain actions without duplicate writes. Excludes read-only API requests and local code edits.
metadata:
  managed-by: causalrun
  compatibility: OpenCode with the causalrun plugin, or an agent harness with causalrun MCP tools
---

# External API writes

Route external API writes through causalrun without asking the user to name this
skill, choose a durability mode, or supply protocol fields. This skill guides tool
selection. The plugin and runtime supply approval checks and saved action records.

If causalrun tools are unavailable, explain that the runtime integration is needed
before you can protect the write. Do not claim protection from this skill alone.
Do not use a shell command or another tool as a fallback for a blocked write.

## Choose and keep the action

Use the built-in GitHub issue or controlled value profile when it fits. Otherwise,
use `http.json.write.v1` with a stable operation name and the exact API origin.
Supported custom rules use JSON mutations and GET evidence. Unsupported transport
or insufficient recovery evidence needs a short explanation before proceeding.

Choose the action key yourself for each new logical write. Keep the operation,
rule name, target, key, and original payload in the tool results and session context.
After an interruption, reuse that identity. A similar title or payload alone does
not prove that two requests are the same action. Ask whether it is a new action
only when the user's intent is unclear. Never invent a replacement key to get past
an unknown result or an invalidated approval.
Recover the original action ID from prior tool results. If that reference is
unavailable, ask for it before attempting a continuation.

## Prepare only when needed

Use `causalrun_lookup` when available, or `causalrun_write` to obtain preparation
guidance without sending an unapproved write. Reuse an approved matching rule.

For a new rule, read official API docs or OpenAPI/Swagger specifications first.
Check authentication, permissions, request fields, completion semantics, and a
read-only evidence lookup. Use safe reads to fill gaps. Live mutation probes need
separate authorization for a disposable target.

Infer success from the user's task and the docs. Ask a short question only when a
material ambiguity remains. Reuse consent already given. Never fabricate answers,
marker consent, target authorization, or provider guarantees.

Write the pure `verify(action_id, payload, evidence)` result check. Follow the
preparation guidance for supported helpers, bindings, and contract fields.
For generic APIs, supply the declarative `contract` and store inferred success in
`contract.expected`. Credentials are local environment references, never values
in the contract or chat. Declare marker assumptions and evidence limits.

Call `causalrun_prepare`. Failed validation blocks dispatch. The user must review
and approve the exact rule before its first write. In OpenCode, use its rule review
prompt. With MCP, provide the separate operator review command. Never approve your
own rule, run that operator command yourself, or weaken approval permissions.

## Send and recover

Call `causalrun_write` with the saved identity and payload. `COMMITTED` means the
approved result check accepted evidence. `IN_DOUBT` means the outcome is unknown.
Use `causalrun_verify` for read-only recovery. Use `causalrun_result` to retrieve
a recorded outcome without another provider call. Missing evidence does not prove
failure. A repeat of the same action returns its record and does not resend it.

Give the user the result first, in at most three short sentences. Include the
created object's link when available. Keep keys, schemas, source, hashes, and test
logs out of normal replies. Show them when the user asks for details. If the result
is unknown, state the next safe step: check again or review the saved action.
