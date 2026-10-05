# Install in OpenCode

You need Python 3.10+ and OpenCode on macOS or Linux.
The tested host is OpenCode 1.18.34. Windows and OpenCode V2 are not verified.

## Install once

From the checkout, run:

```sh
python3 install.py
```

Then open a new OpenCode session. Use your normal model and project.
You do not need Docker, a model inside causalrun, or a service start command.

The installer adds `~/.config/opencode/plugins/causalrun.ts` and sets the rule
approval permission to `ask`. OpenCode loads global plugins at startup.
The plugin starts the service and checks it again for each new session.
See [OpenCode's plugin documentation](https://opencode.ai/docs/plugins/).

The installer copies the runtime to `~/.local/share/causalrun/runtime`.
The database stays in `~/.local/share/causalrun/runtime.sqlite`.
You can remove the checkout after installation if you do not need to develop it.

If `OPENCODE_CONFIG_DIR` is set, installation uses that directory.
Otherwise, it uses `XDG_CONFIG_HOME/opencode`, or the default path above.
Unrelated JSON settings are preserved. The installer saves the original config.
JSONC comments and permission shorthand need a separate config or a manual merge.
The installer stops with an error instead of changing them.

## Authentication

For GitHub, run `gh auth login` before you start OpenCode.
You can also set `GH_TOKEN` or `GITHUB_TOKEN` outside the conversation.
Do not put credentials in a prompt or a write rule.

The local value API is a test profile. It needs `CAUSALRUN_PROVIDER_TOKEN` and a
separate `CAUSALRUN_RECEIPT_TOKEN`. Do not set these test variables for GitHub use.
A running service keeps its provider profile. Stop it before changing credentials.

## Use

> Create an issue in OWNER/REPO with the title and body I supplied. Use causalrun.
> Read the API docs. Ask only for missing intent or consent.

The agent reads the docs and sets up a result check. Clear success conditions do
not need a question. Missing intent or consent does. Validation runs in a temporary
local fixture. You must still approve the exact rule before the first target write.

Read the short permission summary and its full review file. The file contains the
source, target, limits, and test results. Each review has its own content hashes.
Normal status output is short. Ask for details to see the receipt and timeline.

Use the same action key and payload after a lost response. A missing result does
not prove failure. An uncertain action is never sent again automatically.

## Update

Quit OpenCode. Keep the state directory, then run:

```sh
python3 install.py --stop
python3 install.py
```

Start OpenCode again. A code change requires new rule validation and approval.
Saved actions and receipts remain in the database.

For a custom install, keep the same path overrides on every command:

```sh
python3 install.py --config-dir /path/to/config --state-dir /path/to/state
```

Use `--json` when another program needs machine-readable installation output.
A standalone `.pyz` installer supports the same options.
No public release has been published.

## Remove

Quit OpenCode and stop the service with `python3 install.py --stop`.
Remove only the managed `causalrun.ts` file from your plugin directory.
Remove its `causalrun_approve` entry from your JSON permission settings.
Keep or back up the state directory if you need the saved actions and reviews.
Do not replace your whole OpenCode config with an old backup.

## Limits

The plugin handles GitHub issue creation and the local test value API.
It holds known structured write tools. Other tools, shell scripts, and network
calls can bypass it. It is not a network firewall.

The service and agent run as the same OS user. An agent with full shell access can
read local files or call operator code. Separate capabilities protect the provided
tool interface; they do not isolate an unrestricted process.

The plugin requires an actual review prompt. Silent auto-approval is rejected.
Fixed messages use short templates. Model replies receive STE writing rules but
are not certified against the full ASD-STE100 dictionary.
