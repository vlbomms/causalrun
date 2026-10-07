# causalrun

Help your coding agent avoid duplicate API writes after a crash or a lost response.

You ask your agent to create a GitHub issue. GitHub creates it, but the response
never reaches the agent. Sending the request again could create a second issue.

causalrun saves the action before it sends the request. If the result is unclear,
it checks GitHub for evidence of that action. It can recover the result without
creating another issue. If the evidence is missing, it stops and reports an
unknown result.

## Why use causalrun?

- **Avoid sending the same write twice.** Repeat an action with the same key to
  get its saved record. causalrun does not send that write again.
- **Check what happened after an interruption.** Use a saved result check to look
  for evidence in the target application.
- **Review the check before the write.** Your agent builds the check from API
  docs. causalrun tests it, then asks you to approve the rule.
- **Keep setup small.** Actions and results stay in local SQLite. You do not need
  Docker, a cloud service, or a second AI model.

Works with OpenCode. Other agent tools can connect through
[MCP](docs/install-mcp.md). Built-in rules cover GitHub issue creation and a local
test API. For other HTTP/JSON APIs, your agent can prepare a
[custom write rule](docs/http-json.md). Protection applies to writes sent through
causalrun.

## Install

You need Python 3.10+ and OpenCode on macOS or Linux.

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

## Create an issue

Ask your agent:

> Create an issue in OWNER/REPO titled "Test issue" with body "Test from OpenCode."

Replace `OWNER/REPO` with a repository you can use for tests.

The installer adds a `causalrun` skill. It guides the agent to use causalrun and
choose the action key. You do not need to name the tool. Skills guide the agent;
they do not intercept shell commands.

For explicit routing, use:

> Use causalrun_write to create an issue in OWNER/REPO titled "Test issue" with
> body "Test from OpenCode." Use action key "test/issue-001". Do not use gh or
> shell commands to create it.

Check that the agent calls causalrun tools. If a direct write already occurred,
inspect its result before starting another action.

The agent reads the API docs and prepares a result check. It asks what success
means only when the request and docs leave that unclear. For GitHub tests, it
also asks for consent to use the repository and add an action marker to the issue.

causalrun tests the check before it permits the write. Read the short summary and
the full review file before you approve the rule. An unchanged approved rule can
be used again. Normal output shows the result and the next step.

To return to the action in a new session, ask:

> Use causalrun to get the result for action key "test/issue-001" in OWNER/REPO.
> If it is unknown, check whether the issue was created. Do not create a new issue.

Keep the same key for the same action. A new key means a new action. Changing the
payload under an existing key is rejected. Ask for details to see the saved
receipt and timeline.

## How it works

1. Your agent writes a result check for the supported API operation.
2. causalrun tests the check. You review and approve the write rule.
3. causalrun saves the action and sends the write once.
4. It saves the result. After an unclear outcome, a check can read application
   evidence and confirm success without another write.

## Limits

This is an early project. Custom rules support JSON writes and GET evidence reads,
with bearer tokens, API-key headers, or no authentication. SOAP, file uploads,
request signing, and OAuth refresh are not supported. It does not restore an
agent's full task after a crash.

Tests check supplied examples. They do not prove a third-party API's guarantees.

Missing evidence leaves the result unknown (`IN_DOUBT`). It does not prove that
the write failed. Recovery depends on the application's evidence and access to
it. Do not use a new action key to repeat an uncertain write.

The OpenCode plugin starts causalrun in new sessions and tells the agent to use
it. Other tools and shell scripts can bypass the plugin. It does not intercept
every external API write.

Status messages use short templates. The agent receives plain-language writing
rules, but full ASD-STE100 conformance of model replies is not certified.

## More information

- [Install, update, and remove the plugin](docs/install-opencode.md)
- [Try the local API](docs/test-opencode.md)
- [Run the full functional test](docs/functional-test.md)
- [Use MCP with another harness](docs/install-mcp.md)
- [Set up another HTTP/JSON API](docs/http-json.md)
- [Install the skill in an existing setup](docs/install-skill.md)
- [Documentation and test evidence](docs/README.md)

The installer copies its runtime outside the checkout. Your data stays in the
state directory. No public package or release has been published.
