# Gate 3: GitHub issue recovery

Gate 3 adds a pinned GitHub issue-creation connector with a host-agent-written,
persistent verifier. It does one POST, records the authorization before sending,
and never resends an uncertain action. Recovery uses GET listings, including closed
issues, with bounded pagination. It requires a unique exact action marker, original
payload hash, approved repository and creator, and exact title/body.

The marker is an HTML comment appended before the initial write. This is limited
positive evidence: an approved author could copy the marker and content. Approval
must acknowledge that correlation assumes no copying or editing during recovery.
Missing, deleted, altered, inaccessible, conflicting, or incomplete evidence cannot
prove failure. Neither the adapter nor the generated expression concludes failure.

The adapter rejects off-origin pagination before sending credentials. It stops after
10 pages, rejects repeated issue IDs, excludes pull requests, and fails closed when
completion evidence is unavailable. Pagination is not a snapshot; concurrent changes
can cause uncertainty. HTTP responses are limited to 64 KiB and requests have a
five-second timeout; a large page can therefore block recovery safely.

## Operator preparation

Have the host agent inspect the official [issue API](https://docs.github.com/en/rest/issues/issues)
and [pagination documentation](https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api).
Pin repository, creator login, API version, and observable expectations. Creation
requires issue write permission; recovery requires issue read access. Private
repositories need authenticated access. Use dedicated disposable resources for tests.
Ask the user only for missing intent or assumptions; use selectable options and
free text in the harness. No separate discovery report is needed.

Gate 3's operator CLI packages completed answers; automatic interviews and install
remain gate 4. An interview JSON file has these contract inputs:

```json
{
  "expected_behavior": "Create one issue with the requested title and body under the approved author",
  "sandbox": "Dedicated repository: owner/repository",
  "unknown_policy": "Keep uncertain actions blocked",
  "marker_assumption": "Accepted: no copied or edited markers during recovery"
}
```

Use answers actually supplied by the user. Do not synthesize acceptance of recovery
assumptions for a production connector. The demonstration uses scripted test answers
and approvals in the sandbox authorized by the user.

```sh
python3 -m causalrun github-build --repository owner/repository --author creator-login \
  --interview answers.json --verifier examples/verify_github_issue.py --output connector.json
python3 -m causalrun --db /operator-owned/runtime.sqlite register connector.json
python3 -m causalrun --db /operator-owned/runtime.sqlite validate CONNECTOR_DIGEST
python3 -m causalrun --db /operator-owned/runtime.sqlite approve CONNECTOR_DIGEST
```

Validation uses a disposable local GitHub-shaped HTTP provider, never the artifact's
live repository. Approval pins implementation, artifact, and validation digests.
The ordinary `/v1/actions` and `/verify` API accepts this connector without provider
URL or credential overrides. The generated expression has no network or secret access.

The runtime accepts a separate `CAUSALRUN_RECEIPT_TOKEN`. For this GitHub profile,
if it is absent, recovery reuses the server's write token for GET requests only.
This limits the executed operation, not the token's privileges. The live run uses
local GitHub CLI authentication in memory. A separately scoped read credential is
preferable for deployment. Never put tokens in interview files or agent messages.

## Acceptance traceability

| Requirement | Evidence |
| --- | --- |
| Find an exact correlated issue | Controlled `matching_issue`; live normal and lost-response timelines |
| Pagination and incomplete listing | Controlled two-page case; 10-page budget and full-page-without-next tests |
| Conflicting markers | Controlled duplicate-marker validation; runtime remains IN_DOUBT |
| Permission failure | Controlled denied reads; runtime wrong-token schedule blocks |
| Delayed/no match and deleted/altered evidence | Controlled no-match/deleted/altered cases; live removes marker, blocks, restores marker, and recovers |
| Unknown blocks repeat | Controlled and live repeated actions retain identity with one creation POST per action |
| Durable result | Controlled and live recovered result returns without another provider lookup/write |
| Generated predicate must pass validation | Always-true source fails negative cases and cannot be approved |
| Actual sandbox writes and cleanup | Live evidence records provider IDs/URLs, two POSTs, and read-back-confirmed closure |

Results and failed runs are under [results/gate-3](results/gate-3/README.md).
The deletion case is a controlled fixture only; the live run tests editing, not
GitHub deletion. Response loss is simulated by discarding a received real GitHub
response after creation, not by disrupting GitHub's network. These results cover
this issue operation under the declared assumptions, not arbitrary API certainty.

OpenCode installation, first-use interception, and stronger operator isolation
remain gate 4. A terminal approval is not proof of a human when the agent can access
the operator shell/database. Arbitrary shell writes remain outside the chosen scope.
