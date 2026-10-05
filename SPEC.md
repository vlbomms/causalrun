# causalrun: generated recovery connectors

Version 0.9 — short output and automatic session startup — October 4, 2026

## Problem and solution

After an agent loses the response to an external write, it needs application-specific
evidence to determine what happened and whether another send is safe. causalrun
helps the developer's agent discover, generate, and validate a persistent verifier
before the write, then enforces approved recovery rules using durable action records.

This is the active specification. At the user's request, the previous runtime,
archive, deployments, and evidence were removed from the checkout. Git history
retains that work. Gates 1 and 2 are implemented with Python and SQLite for the controlled receipt
profile. See [gate 1 evidence](docs/gate-1.md) and [gate 2 evidence](docs/gate-2.md).
Gate 3 adds a GitHub issue connector under explicit marker assumptions; see [gate 3 evidence](docs/gate-3.md). Gate 4 adds native installation and first-use setup for the tested OpenCode version; see [gate 4 evidence](docs/gate-4.md).
Gate 5 adds a standard-library MCP adapter and shared connector reuse with Codex,
plus a recorded mechanical setup comparison; see [gate 5 evidence](docs/gate-5.md).
Human development time and live model generation quality remain unmeasured.

## Decisions agreed with the user

- Start with connector generation during development, followed by ordinary execution.
- First applications: a controlled API with transactional receipts and GitHub issues.
- Infer expected observable behavior from the developer's request and available
  API documentation. Ask what success means only when a material ambiguity remains;
  do not ask the developer to restate documented behavior.
- No production write is allowed until its verifier has been generated, validated,
  and approved. Controlled validation writes require dedicated sandbox targets.
- The developer approves each exact connector version once before first use.
- A connector may verify success without proving failure. Approval must acknowledge
  this limitation, and inconclusive outcomes must block automatic repeats.
- Discovery can use available documentation, source, schemas, and sandboxes. Most
  applications will be third-party services with no source or database access.
- Cover explicitly registered tools first, not arbitrary shell interception.
- OpenCode first; retain a harness-independent protocol and artifact format.
- Aim for native local installation with SQLite. Docker remains an optional route.
- Keep only the new lightweight implementation in the checkout. Do not claim
  generated verifiers are novel or reliable without comparison evidence.

## Developer workflow

The host agent first inspects available OpenAPI/Swagger specifications, WSDL,
official documentation, and API versions. It checks operation semantics,
authentication and scopes, inputs and outputs, asynchronous completion, and
recovery mechanisms. Safe read-only browser or HTTP inspection can supplement
documentation. Mutation probes require an explicitly authorized sandbox.

Discovery feeds a short interactive interview. Ask only about unresolved facts
and user intent: expected observable results, authorized test targets, available
authentication, and acceptable recovery limitations. Each question offers concise
selectable options and a free-text answer. Do not ask the user to repeat facts
already established by the API specification, and do not request secrets in chat.

Use the answers to propose the connector contract and identify correlation data
before any production dispatch. Do not create a separate discovery findings report
or require the user to review research notes. Retain only the contract, essential
supporting API references, validation evidence, and approval needed for execution.

The generation agent emits a versioned connector artifact. The validation runner
executes controlled scenarios. The developer reviews the artifact, test report, requested access, and limitations. Approval pins that exact content hash.
Any change to executable code, contract, or evidence interpretation invalidates it.

The installed tool prepares a durable action with a stable logical identity. The
runtime checks approval and validation, records authorization, then calls the
provider outside a metadata transaction. It retains the original payload, target,
connector digest, and outstanding attempts after a crash or client disconnection.

Recovery runs the pinned verifier and journals its findings. The agent receives
structured status and allowed next actions rather than making the retry decision.

## Initial implementation scope

The initial connector is declarative and fixed: a controlled value-create operation
and a receipt verifier that matches the action ID, payload hash, and expected
value. The artifact digest also includes the interpreting implementation digest.
Validation runs four checks against a disposable controlled fixture, never the
approved target. It tests this fixed implementation, not an arbitrary third-party
service or generated code. Approval therefore requires a trusted controlled target.
Only loopback HTTP targets are accepted. Gate 2 adds host-agent-written verifier
source embedded in schema version 2 artifacts. The source uses a restricted pure
Python expression language; imports, attributes, arbitrary calls, loops, and
side effects are forbidden. A separate runtime performs receipt reads using a
read-only credential. Ten fault checks validate the source in a disposable fixture.
See [the workflow](docs/agent-workflow.md); no universal correctness is certified.

## Connector contract

Each artifact includes:

- Operation name and version; validated input schema and target restrictions.
- Expected behavior: required observable result fields and comparison rules.
- Correlation mechanism: stable provider key, receipt ID, or explicitly limited marker.
- Write adapter and separate verifier entry point.
- Essential supporting API references, provider/API version, and execution assumptions;
  no separate discovery report.
- Verifier access requirements, deadlines, pagination rules, and evidence retention.
- Success predicate and, where available, a non-execution predicate.
- Permitted recovery operations and provider idempotency retention boundaries.
- Executable content digest, validation report digest, and approval record.

Schema version 3 adds the GitHub repository, creator, bounded issue adapter, and explicit marker assumptions.
Schema version 1 holds the fixed connector; version 2 embeds generated source,
adapter/authentication metadata, API version, and completed interview answers. Free-form
model judgments or confidence scores are not sufficient evidence for dispatch.

## Evidence and recovery semantics

| Finding | Meaning | Runtime action |
| --- | --- | --- |
| Confirmed success | Evidence matches this action, target, and expected result | Persist receipt; return result |
| Confirmed non-execution | Authoritative evidence says this attempt did not execute and cannot complete later | Apply the approved rules before any new authorization |
| Unknown | Missing, conflicting, inaccessible, or insufficient evidence | Retain IN_DOUBT; block unsafe repeat |

A provider-supported idempotent repeat can be permitted without proving the first
attempt failed, but only within its validated contract and retention window. It
keeps the same logical action identity and payload. Read-based verification and
write-based idempotent recovery must be separate, explicitly permitted operations.

Existence of a similar object is insufficient. Markers can be copied, altered, or
removed; reads can be delayed or incomplete. A missing result is not failure proof.
Tests can falsify a contract but cannot establish guarantees absent from the provider.

For the controlled application, store the receipt, payload hash, and application
change in the same transaction. For GitHub, establish limited positive evidence
under an explicit marker/target assumption. No-match, ambiguous matches, or altered
markers cannot authorize an unsafe repeat. Do not promise arbitrary API certainty.

## Validation and approval

Validate normal success, rejection before execution, success with a lost response,
delayed completion, verifier failure, incomplete listings, conflicting matches,
crashes around persistence, and repeated recovery. Check both false success and
false failure against an independent oracle in controlled tests.

Generated code runs against dedicated test resources first. Read-only verifier
credentials, bounded execution, restricted destinations, and secret filtering are
target requirements; broad discovery access does not imply unrestricted saved code.
An approval is scoped to an exact connector digest and configured target/credential
scope. The runtime rejects missing, outdated, or incompatible validation/approval.

Gate 1 exposes only the gated path. Registration, validation, and interactive
approval use a separate local operator CLI. The agent API has no approval endpoint.
A terminal prompt is not proof of a human: an agent with operator filesystem/shell
access could invoke it. Deploy the operator CLI and database outside the agent
security boundary. Gate 4 adds lightweight OpenCode tool mediation and installation, with the same unrestricted-shell limitation.

## Automatic installation and first-use workflow

The product must be installable by a new OpenCode user without manual cloning,
CLI orchestration, or copying tool files. Installation configures the plugin and
local runtime. A self-contained Python zipapp installer is built and tested locally. No npm package or public release is published yet.

The plugin mediates supported external-write tools before dispatch. On the first
use of an unknown operation, it holds the write, invokes the host agent's discovery
and selective interview workflow, packages and validates the verifier, and presents
the exact connector for trusted user approval. No production send occurs during
this setup. Cancellation, missing sandbox authorization, or failed validation leaves
the write blocked. Later matching actions reuse the approved connector automatically.
Changes to its scope or code still require fresh validation and approval.

Users should ask for the business action normally; they should not need to remember
a preparation command or durability mode switch. The harness adapter owns stable
logical action keys and keeps them across pauses and restarts. Approval must still
come from the user, not automatically from the generation agent.

OpenCode documents plugin loading and a `tool.execute.before` hook. This is an
integration point for supported tools, not a universal network interception layer.
A shell command can execute arbitrary code whose HTTP method is invisible at the
tool boundary. Do not claim to capture every write with command-string matching.
A lightweight plugin's scope and bypasses must be explicit. Guaranteeing coverage
of arbitrary scripts requires restricted execution/egress and a separate acceptance
suite. The user selected lightweight protection for registered API tools; arbitrary shell and network interception is deferred.

## Installation and harness boundary

A skill or repository instructions guide the host agent. A native runtime supplies
persistent state independently of the model/session. Proposed setup initializes SQLite, starts a local runtime, adds the OpenCode
plugin without overwriting configuration, and exercises a harmless health check.
Its first-use workflow must automatically prepare protected writes as described above.

The local zipapp installer configures the plugin and private runtime; no public package or release is published yet. Gate 1 runs directly from
a checkout with Python 3.10+ and standard-library SQLite; there are no package
dependencies. Gate 4 adds native packaging, automatic service startup, and host/service restart tests. Keep modules small and avoid a general storage framework.

The first adapter exposes connector preparation, validation, approval review,
registered execution, result inspection, and reconciliation. Approval must originate
from a trusted user interface, not a model-provided boolean. Installation instructions
must explain access boundaries and keep provider/operator secrets out of model output.

Other harnesses reuse the versioned artifact and HTTP/JSON protocol through adapters.
A future MCP adapter can expose the same operations. Full conversation/process
checkpointing, speculative agents, GPU serving, arbitrary shell protection, and a
hosted multi-tenant service are outside the new initial product scope.

## Evaluation

Compare manual and agent-assisted connector development on the same operations and
source material. Record elapsed time, human corrections, model/version, source
snapshots, and assistance used. Report false conclusions, unknown outcomes, blocked
repeats, provider writes, and recovery latency separately. Preserve failed runs.

Begin with the controlled API and GitHub. Small results support only these operations;
they do not establish generality, production scale, or research novelty.

## Implementation

Proceed through [the new milestone gates](docs/milestones.md). Keep the runtime
narrow: immutable contracts, gated dispatch, receipt checks, and action journals.
Do not add branches, checkpoints, infrastructure orchestration, or a workflow
engine. Record working demonstrations before expanding scope.

## User output and installation

Run `python3 install.py` once for the user's OpenCode config. The global plugin
starts the service at load and checks it when each new session opens. No separate
terminal service command or Docker process is required.

OpenCode shows short fixed status messages and gives the agent STE writing rules.
Normal action outputs keep only the ID, state, and message. Full receipts and
journals remain available with `details=true`. Operator review uses a short summary
and an exact private review file, bound to artifact and report hashes. This does
not certify every model reply against the complete ASD-STE100 dictionary.

See [the recorded checks](docs/results/usability/README.md): 65 tests and three
actual OpenCode startup/recovery checks passed for this execution version.
