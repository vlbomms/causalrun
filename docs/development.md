# Development

The runtime uses Python's standard library. The OpenCode adapter uses the host SDK.
Do not add a second model, database server, or container service for local tests.

Install the pinned test host:

```sh
npm install --prefix .local/opencode-test --no-audit --no-fund opencode-ai@1.18.34 @opencode-ai/plugin@1.18.34
```

Run the full current test suite and actual host demo:

```sh
python3 -m tests.run_usability
```

The model fixture supplies scripted tool calls. It does not measure live model
quality. Provider writes use temporary local targets. The tests do not create new
GitHub issues. Independent SQL counts check for duplicate writes.

Build a standalone installer when you need one:

```sh
mkdir -p .local/dist
python3 -m causalrun.installer --build .local/dist/causalrun.pyz
```

The checkout installer is `python3 install.py`. Use `--json` for scripts.
Tests, docs, local profiles, and model fixtures do not ship in the runtime archive.
The ignored `.local/` directory contains test hosts, test data, and local artifacts.
Do not delete it to clean source code while you still need those records.
