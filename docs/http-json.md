# Use an HTTP/JSON API

Use `http.json.write.v1` when the API does not have a built-in causalrun connector.
The agent defines requests and a result check. The runtime sends the approved
write once and keeps its action across sessions.

This supports JSON writes with `POST`, `PUT`, `PATCH`, or `DELETE`, and JSON
read evidence with `GET`. Authentication can use a bearer token, an API-key
header, or no token. SOAP, file uploads, request signing, OAuth refresh, cursor
pagination, and arbitrary shell writes are not supported.

## Ask OpenCode

> Use causalrun for this API write. Read its official docs first. Set up a result
> check before sending. Use the same action key if the session stops.

Include the API docs URL, the operation, and the requested values in your task.
Do not include credentials. The agent needs a stable operation `name`, exact
`target` origin, and `action_key`. Use the same three fields in later sessions.

The agent asks what success means only when the request and documentation leave
that unclear. You still review and approve each exact rule before its first write.
If the API has no usable evidence lookup, the agent must explain that limit.
Missing evidence keeps the action unknown; it does not permit another send.

## Configure credentials

Set the credential environment variables locally before starting OpenCode.
The contract stores variable names, not tokens. The service inherits them when
it starts. Restart it after changing credentials. Use separate write and read
credentials with the required permissions when the provider supports them.

GitHub authentication from `gh auth login` is also available to generic rules
through the service-owned `CAUSALRUN_GITHUB_TOKEN` reference. This token can have
write access; the reference does not make it a restricted read credential.

To update an existing installation, close OpenCode and run:

```sh
python3 install.py --stop
python3 install.py
```

Then start OpenCode again. An execution-code change invalidates old approvals.
Existing actions remain saved, but they keep their original connector binding.
Do not create a new key to work around an invalidated rule or unknown action.

## What the agent prepares

Send `operation`, `name`, and `target` to `causalrun_write` or `causalrun_lookup`.
An unapproved operation returns preparation guidance without sending a write.
Send `source`, `answers`, and `contract` to `causalrun_prepare`.

The contract declares:

- `name`, `target`, `api_version`, `expected`, and essential `sources`.
- `adapter.write` and `adapter.read`: method, path segments, query, headers,
  and accepted HTTP status codes. The write also has a JSON `body`.
- Separate `authentication.write` and `authentication.read` policies.
- `fixture.payload`, `fixture.different_payload`, and a matching evidence template.
- Recovery `limitations`, including marker assumptions or provider retention limits.

Bindings can use `{"$bind":"action_id"}` or
`{"$bind":"payload","path":["field"]}`. A text template uses
`{"$text":["literal", binding]}`. Path and query values are encoded separately.
Requests stay on the approved origin. Redirects and transport retries are disabled.

Evidence can be a JSON object or a page-number list. Optional read `pagination`
has `page` and `size` query parameter names, `page_size` (1–100), and `limit`
(1–10). A full final page leaves completeness unknown. Combined evidence is
limited to 64 KiB. Reads have deadlines and a maximum five-second socket wait.
An API's pagination can still move between requests; approval must state that limit.

A result check is one pure Python return expression. It can use `digest`,
`isinstance(value, dict)`, and `unique_match(items, "field", value)`. The last
helper returns one exact match, or `None` for missing or conflicting matches.
It does not infer failure. String addition can form an exact correlation marker.

Validation tests supplied fixtures for matching evidence, missing evidence,
wrong action ID, and wrong payload. It makes no requests to the approved target.
These checks can expose a bad result check, but cannot prove undocumented provider
behavior. Live test writes need separate authorization for a disposable target.

## Operator example

[Example contract](../examples/http-entry-contract.json) and
[result check](../examples/verify_http_entry.py) show a fictional entry API.
They are templates, not a connector for an arbitrary real service.

```sh
python3 -m causalrun http-build \
  --contract examples/http-entry-contract.json \
  --verifier examples/verify_http_entry.py \
  --output .local/http-entry.json
```

Register, validate, and approve the resulting artifact with the existing operator
CLI. OpenCode and MCP use the same workflow through their preparation tools;
MCP approval still belongs to a separate trusted terminal.

Other tools and shell scripts can bypass causalrun. It tracks external actions;
it does not restore a full agent task or prove success when the application exposes
insufficient evidence.
