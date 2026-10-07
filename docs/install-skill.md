# Install the causalrun skill

The skill tells your agent to use causalrun for external API writes. You can ask
for the action normally. The plugin or MCP runtime must still be available.
The skill alone cannot save actions, validate rules, or prevent shell writes.

## Existing OpenCode setup

From the causalrun checkout, run:

```sh
python3 install.py --skill-only
```

Restart OpenCode. This command adds only the skill. It does not replace the runtime,
stop the service, or change your JSON settings. The default destination is
`~/.config/opencode/skills/causalrun/SKILL.md`.

For a new installation, use `python3 install.py`. It now installs the plugin,
runtime, and skill together. A built `.pyz` installer supports `--skill-only` too.
The same `--config-dir`, `OPENCODE_CONFIG_DIR`, and XDG overrides apply.
The installer refuses to overwrite an unrelated skill with the same name.

## Other harnesses or manual copying

The portable skill is [skills/causalrun/SKILL.md](../skills/causalrun/SKILL.md).
Copy its folder into the harness's skill directory, and configure
[causalrun MCP](install-mcp.md). The instructions use the shared causalrun tools.
Only OpenCode discovery and loading are tested here; other harnesses may use
different skill paths and discovery settings.

For project-only OpenCode discovery, copy the folder to
`.opencode/skills/causalrun/`. Do not overwrite an existing user-owned skill.
For global manual installation, use `~/.config/opencode/skills/causalrun/`.
See [OpenCode's skill documentation](https://docs.opencode.ai/docs/skills/).

## Check it

Run `opencode debug skill` and check that `causalrun` appears. If it is missing,
check the installation path and skill permissions. Restart after installation.

In a fresh OpenCode session, ask:

> Create an issue in vlbomms/tempo titled "causalrun skill test" with body
> "Test of an ordinary request."

Use your own authorized test repository if you are not this project's owner.
The agent should load the skill when needed and use causalrun tools. A new rule
still needs user review and approval. Clear success requirements need no extra
question. Direct `gh issue create` or another external write means this routing
check failed; the issue was not protected by causalrun.

Skill instructions do not guarantee model selection. They guide the agent, while
the plugin blocks known direct structured write tools and the runtime gates
dispatch. Arbitrary shell scripts remain a bypass.
