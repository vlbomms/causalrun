# Generated recovery connector implementation gates

This is the sole active roadmap. The previous code and results were removed from
the checkout at the user's request; Git history retains them. Gate 1 evidence is
recorded in [gate-1.md](gate-1.md): 17 tests and 8 demonstration steps passed;
0 final failures. Gate 1 passes for its declared controlled-connector scope.
Gate 2 passes for the controlled host-agent workflow: [30 tests and 5 process
demonstrations](gate-2.md), with 0 final failures. Gate 3 passes its limited issue-creation scope: [36 regression tests and two live demonstrations](gate-3.md), with failed runs retained and all four test issues closed. Gate 4 passes its declared plugin scope: [46 tests and two real OpenCode demonstrations](gate-4.md), using a scripted local model, with zero final failures. Gate 5 passes its declared MCP reuse and mechanical comparison scope: [57 tests, three actual-host checks, and six paired trials](gate-5.md), with zero final failures. Human productivity and live generation quality remain unmeasured.

| Gate | Implementation | Required demonstration and evidence |
| --- | --- | --- |
| 1. Contract and preflight | Versioned connector artifact, declared expectations, validation/approval records, gated dispatch; controlled receipt API | Reject writes with missing verifier, validation, or approval; reject changed artifact/target scope; approve through trusted user input; perform one accepted write and retrieve its receipt |
| 2. Generated verifier and recovery | API discovery, selective interview with options/free text, generated connector contract, independent validation runner, durable verifier binding | Demonstrate discovery-to-interview without a separate findings report; generate a controlled-API verifier; lose a response after commit and recover; crash around recording; delay completion; inject misleading/missing evidence; show no false success/failure or unsafe repeats in declared schedules |
| 3. Third-party limits | GitHub issue connector generation and validation; positive evidence matching and explicit uncertainty | Find a correlated created issue; handle pagination, conflicting markers, permission failure, delayed/no matches, and deleted/altered evidence; uncertain cases block repeats; record actual sandbox writes and cleanup |
| 4. Native installation and OpenCode | Installable OpenCode plugin, automatic runtime setup, first-use discovery/interview/validation/approval, connector reuse, SQLite crash durability | Fresh install without Docker or manual CLI preparation; actual OpenCode detects supported writes and blocks first use until discovery/validation/user approval; subsequent use reuses approved connector; kill/restart host and service; retain records and approvals; prevent unapproved adapter sends; record any direct-tool bypass limits |
| 5. Reuse and usefulness | Stable harness API, second lightweight harness adapter, manual-vs-assisted evaluation | Use the same connector in both harnesses; compare development effort and corrections under a recorded protocol; report fault results, unknown/blocked counts, and limitations; publish reproducible setup |

Use Python standard-library SQLite and ordinary transactions; let the host agent
do generation. Gate 1 needs no database server or container runtime.
Keep dependencies minimal. A contract can support positive verification while leaving
failure unknown; tests must not turn that limitation into an invented guarantee.

After each gate, record commands, versions, source/artifact digests, schedules,
actual counts, failures, timelines, and acceptance traceability under `docs/results/`.
Failed checks block advancement. No new gate inherits the old benchmark's acceptance.

Gate 1 is a fresh Python/SQLite implementation. Packaging and OS service setup
belong in gate 4. No public installer or OpenCode certification is implied by this plan.
