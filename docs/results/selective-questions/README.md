# Selective-success-question verification

Command: `python3 -m tests.run_selective_questions`.

- 62 tests passed, 0 failures/errors/skips (57 regressions plus 5 new tests).
- Clear success: actual OpenCode 1.18.34 asks Sandbox/Unknown, not Result;
  omitted expected_behavior resolves to the documented controlled predicate.
- Ambiguous success: actual OpenCode asks Result once plus Sandbox/Unknown;
  flagged missing expectations reject preparation, including through HTTP lookup.
- Two host checks per scenario passed: first setup/write/read recovery and
  SIGKILL/restart with the same key/result. Each scenario has one provider object
  and one POST; initial IN_DOUBT then COMMITTED. Four host checks passed total.
- GitHub fixture preparation also supports omitted documented expectations;
  marker and sandbox consent remain required. No GitHub target writes were made.

The runtime remains Python/SQLite with no additional dependencies. It does not
interpret arbitrary API semantics with a second model. The host agent reads docs
and request context, flags material ambiguity, and writes the verifier. Known
synchronous profiles supply documented defaults. Verifier validation and exact
operator approval still precede target dispatch. Resolved expectations in the
artifact are contract inputs, not necessarily literal user interview answers.

Actual host tests use scripted model fixtures; this verifies tool plumbing and
question counts, not live model comprehension. No paid model inference was used.
Source hashes/versions are in tests.json; full output in tests.txt; timelines,
questions, review metadata, and SQL oracle counts in demonstrations.json.
Installer details are in installer.json. Previous gate results remain historical
records for their execution digest; this code change requires renewed approval.

See [the manual live-agent test](../../test-opencode.md).
