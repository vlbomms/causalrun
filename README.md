# causalrun

Check external writes after a lost response or a crash.

Your agent reads the API docs and writes a result check. causalrun tests the check
before it permits the write. You approve each write rule once. It saves the rule,
action, and result in SQLite.

## Install

You need Python 3.10+ and OpenCode on macOS or Linux. You do not need Docker.

Run these commands once:
```sh
git clone https://github.com/vlbomms/causalrun.git
cd causalrun
python3 install.py
```

Close OpenCode if it is open. Then start it as usual, in any project.
causalrun starts for you in each new session. No extra start command is needed.

To use GitHub, run `gh auth login` before you start OpenCode.
OpenCode 1.18.34 is the tested version.

## Use

Ask your agent:

> Create an issue in OWNER/REPO titled "Test issue" with body "Test from OpenCode."

Replace `OWNER/REPO` with your repository. You do not need to name causalrun.
The plugin tells the agent to use it for supported writes.

The agent sets up a result check before the first write. It asks for your approval.
Read the short summary and its full review file before you allow the rule.
Normal output shows the result and the next step. Ask for details to see the full
record, receipt, or timeline.

## Limits

Supported writes: GitHub issue creation and the local value API used in tests.
Missing evidence leaves the result unknown. It does not prove that the write failed.
Do not use a new action key to repeat an uncertain write.

Other tools and shell scripts can bypass the plugin. Full ASD-STE100 conformance
of model replies is not certified. Fixed status messages use short templates;
the agent receives the writing rules in each session.

## More information

- [Install, update, and remove the plugin](docs/install-opencode.md)
- [Try the local API](docs/test-opencode.md)
- [Run the full functional test](docs/functional-test.md)
- [Use MCP with another harness](docs/install-mcp.md)
- [Documentation and test evidence](docs/README.md)

The installer copies its runtime outside the checkout. Your data stays in the
state directory. No public package or release has been published.
