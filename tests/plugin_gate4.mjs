import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { createPlugin } from '../adapters/opencode/plugin.mjs';
const [root, state, python, target] = process.argv.slice(2);
const { tool } = await import(pathToFileURL(root + '/.local/opencode-test/node_modules/@opencode-ai/plugin/dist/tool.js'));
const plugin = await createPlugin({}, tool, { runtime: root, state, python });
let passed = 0;
for (const name of ['github_create_issue', 'github_issue_write', 'http_request']) {
  await assert.rejects(plugin['tool.execute.before']({ tool: name }, { args: { method: 'POST' } }));
  passed++;
}
await plugin['tool.execute.before']({ tool: 'http_request' }, { args: { method: 'GET' } });
// An auto-allowed context must not produce durable approval, even after validation passes.
await assert.rejects(plugin.tool.causalrun_prepare.execute({
  operation: 'controlled.value.create.v1', target, api_version: '1',
  source: readFileSync(root + '/examples/verify_value.py', 'utf8'),
  answers: { expected_behavior: 'Exact value', sandbox: 'Yes, only the disposable fixture', unknown_policy: 'Keep blocked and request review' },
}, { sessionID: 'auto-allow-test', metadata() {}, async ask() {} }), /explicit causalrun review prompt/);
passed++;
console.log(JSON.stringify({ passed, auto_approval_rejected: true }));
