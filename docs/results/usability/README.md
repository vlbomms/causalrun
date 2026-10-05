# Short output and automatic startup

Command: `python3 -m tests.run_usability`.

## Final checks

- 65 Python tests passed. No failures, errors, or skips.
- The display test also runs seven Node assertions against real HTTP and SQLite.
  It checks short messages, default output size, full details, private review files,
  approval, and lost-response recovery. There is one provider POST and one object.
- Three actual OpenCode checks passed: first setup/write/recovery, host/service
  SIGKILL and restart, and service restart when a new session opens.
- The final session restarts a stopped service before a tool call. It uses the
  global XDG config layout. `OPENCODE_CONFIG_DIR` is unset. No project plugin exists.
- The provider SQL count remains one POST and one object after all three checks.
- The permission summary keeps the exact artifact/report hashes and review path.
  Before it approves, the test reads that full file and checks both hashes.
  Normal action outputs contain only `id`, `state`, and a short message.
- Model fixtures supply scripted calls. This is not a live model or human reading
  study. No paid inference or GitHub target writes are used.

`tests.json` saves commands, versions, and source hashes. `tests.txt` is the raw
regression output. `demonstration.json` saves tool titles, questions, approvals,
full review records, restart times, and independent SQL counts. `display.json`
saves actual output sizes. `installer.json` saves the archive and installed paths.

The initial three-test run had one failed assertion. It compared a macOS symlink
path with its resolved path. `initial-tests.json` retains the observed failure.
The final test uses resolved paths. No acceptance failures remain.

## Scope

The fixed messages use short templates. The agent receives ASD-STE100 writing
rules in each session. These controls do not certify all model replies against
all dictionary meanings or grammar rules. Code and user content are not rewritten.
Full records remain available with `details=true` and in SQLite.

The checkout install is one command: `python3 install.py`. The default install is
global for the user's OpenCode config. Custom config directories still need the
matching OpenCode configuration. Installation preserves unrelated JSON settings.
The service starts with OpenCode, not at OS login, and does not need Docker.
The startup check does not expand write interception to arbitrary shell programs.

The README now shows the normal install and use path. The manual HTTP example is
in `docs/cli-demo.md`. `docs/README.md` indexes user docs and historical evidence.
No test evidence, local database, or prior demo profile was deleted.
