# Use the same connector in another harness

The MCP adapter shares OpenCode's existing state, verifier, validation, approval,
actions, and receipts. A second harness does not need a second model inside causalrun.
Tested hosts: OpenCode 1.18.34 and Codex CLI 0.159.0-alpha.12.1, using local scripted
model fixtures. This demonstrates integration; live model behavior is not evaluated.

## Existing standalone installation

Use `python3 install.py` for the checkout install. Build a standalone archive with
`python3 -m causalrun.installer --build .local/dist/causalrun.pyz` when needed. Configure
an MCP stdio server with an absolute Python executable and arguments:

```json
{
  "command": "/absolute/path/to/python3",
  "args": ["/absolute/path/to/causalrun.pyz", "--mcp", "--state-dir", "/absolute/path/to/causalrun-state"]
}
```

Use the exact state directory from the OpenCode install. Keep the archive available;
`--mcp` launches its installed runtime copy. Configure authentication locally, never
in the model prompt. Existing bindings reuse the current service's provider profile.

For Codex CLI, register the stdio command:

```sh
codex mcp add causalrun -- python3 /absolute/path/to/causalrun.pyz --mcp --state-dir /absolute/path/to/causalrun-state
```

Keep the host's normal tool permission policy. Codex may request permission for
`causalrun_write` even when causalrun's connector already has operator approval.
These are separate checks. The disposable automated demonstration explicitly sets
that tool's host approval mode to `approve`; it does not modify user configuration.
See the official [MCP setup](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
and [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).

## MCP without OpenCode

A checkout also works without installing the OpenCode plugin. Configure the stdio
server's working directory to the checkout, command `python3`, and arguments:

```text
-m causalrun.mcp --state /absolute/path/to/causalrun-state
```

The service starts on first use. No Node dependency is needed for this path.
For a newly prepared connector, review the full artifact and fixture results in a
separate trusted terminal, then type its exact digest:

```sh
python3 -m causalrun.native review --state /absolute/path/to/causalrun-state --digest DIGEST
```

For an installed archive, the equivalent command is:

```sh
python3 /absolute/path/to/causalrun.pyz --review DIGEST --state-dir /absolute/path/to/causalrun-state
```

A rejected review returns a nonzero exit status. There is no agent approval tool.
After review, reuse the original action key across hosts. Read `causalrun_result`
after a lost response and use `causalrun_verify` for inconclusive evidence. Do not
replace an uncertain action with a new key.

See [the API and boundary](harness-api.md). Ordinary writes from other tools remain
outside MCP mediation; this adapter does not automatically intercept all Codex tools.
No public installer release has been published. The documented build is reproducible
from the checkout and requires Python 3.10+ on macOS/Linux.
