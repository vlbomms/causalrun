# Gate 4: native installation and OpenCode

Gate 4 adds a self-contained Python zipapp installer, a small native service
launcher, and an OpenCode plugin. The installer copies the interpreting source,
installs one bootstrap plugin, and preserves unrelated JSON configuration. The
plugin initializes SQLite and starts the loopback runtime on demand. No Docker,
repository clone, or manual database/connector preparation is needed by the user.
See [installation and usage](install-opencode.md).

First use holds the write and returns discovery references, required question IDs,
options/free text, and the verifier's constrained input language. The host agent
uses ordinary documentation tools and OpenCode's question UI to resolve intent,
then supplies its own verifier source. Preparation validates in disposable HTTP
fixtures. The developer's permission prompt carries the exact source/artifact,
validation report, limitations, and hashes. The plugin requires an observed prompt
before recording approval; silent auto-allow cannot substitute for review.

An approved binding is reused for later writes to that provider scope. SQLite stores
original action keys, source, approval, authorization, receipts, and journals. The
service survives an OpenCode exit and restarts automatically after a crash. GitHub
identity changes and provider-profile mismatches block sends before authorization.
Stopping the service authenticates its recorded instance before trusting its PID;
installation refuses to update interpreting files while it is running.

## Acceptance traceability

| Requirement | Implementation and evidence |
| --- | --- |
| Fresh install without Docker or manual preparation | `causalrun.pyz` installs into an empty isolated profile; real OpenCode loads the plugin and starts the runtime |
| Hold an unprepared write | First `causalrun_write` returns PREPARATION_REQUIRED, with zero configured-target writes |
| Discovery, interview, generated source, approval | Real OpenCode executes schema webfetch, native question request, prepare with stored source, and native permission request; full messages and metadata recorded |
| Approved connector reuse | Later calls resolve the stored binding; one approval and one provider object/write in the final demonstration |
| Lost response and restart recovery | Final demonstration must explicitly observe IN_DOUBT before verify, then COMMITTED; kill both host and service, reuse the same action ID/key/approval |
| Unapproved sends blocked | Missing approval and bad source tests; agent capability receives 401 for native approval; silent auto-allow has zero approval/action rows |
| Supported direct-tool interception | Actual OpenCode's `http_request` write errors before tool execution; Node checks the two registered GitHub names and HTTP mutations |
| Scope/credential changes | Changed target/report rejected; provider profile mismatch and changed GitHub creator prevent authorization |
| Boundaries disclosed | Arbitrary shell, unregistered MCP names, unrestricted same-user filesystem access, and model quality remain outside enforcement/certification |

Gate 4 tests **OpenCode 1.18.34**, not an inferred plugin compatibility guarantee.
The model is a scripted local OpenAI-compatible fixture that emits known tool calls
and verifier source. The driver answers the real host's question and permission
requests. This exercises the installed host/plugin/runtime protocol with no paid
inference; it does not establish autonomous agent research quality, human usability,
or the correctness of arbitrary generated verifiers. Those evaluations belong to
gate 5. Gate 3 separately records actual GitHub writes and cleanup; gate 4's host
demonstration writes only to a local controlled provider.

Evidence, failures, commands, versions, hashes, counts, and timelines are under
[results/gate-4](results/gate-4/README.md). Stronger timeline checks exposed an early
fault-injection mistake; early install/restart passes are not lost-response evidence.
The final run requires actual socket closure after provider commit and a receipt
read that transitions the original action from IN_DOUBT to COMMITTED.

## Limits

The plugin protects its own tools and the explicitly named structured tools in the
installation guide. It does not interpret bash, recognize every SDK, or block
network egress. A skill or system instruction does not extend that coverage.
An unrestricted local agent can bypass operator controls through shell/filesystem
access; the separate tokens and private file modes protect only the provided paths.
The plugin has no polished web UI, workflow engine, scheduler, container stack, or
embedded model. It supports two narrow operation profiles.

The installer is built and tested locally; no npm package, public release, or push
has been performed. JSONC configuration, permission shorthand, Windows, and V2 plugin
APIs remain unverified/unsupported. Gate 5 remains pending; no comparison or novelty
claim follows from these integration results.
