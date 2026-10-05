import assert from 'node:assert/strict';
import { readFileSync, statSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { createPlugin, actionSummary, messages } from '../adapters/opencode/plugin.mjs';
const [root, state, python, target] = process.argv.slice(2);
const { tool } = await import(pathToFileURL(root + '/.local/opencode-test/node_modules/@opencode-ai/plugin/dist/tool.js'));
const plugin = await createPlugin({}, tool, { runtime: root, state, python });
let checks = 0;
for (const message of Object.values(messages)) {
  for (const sentence of message.split(/[.!?]/).filter(s => s.trim())) {
    assert.ok(sentence.trim().split(/\s+/).length <= 20, sentence);
  }
}
checks++;
assert.deepEqual(Object.keys(actionSummary({id:'original',state:'IN_DOUBT',receipt:{secret:'hidden'},events:[]})), ['id','state','message']);
checks++;
const system = { system: [] };
await plugin['experimental.chat.system.transform']({}, system);
assert.match(system.system[0], /ASD-STE100/);
assert.match(system.system[0], /three sentences/);
checks++;
const common = { operation:'controlled.value.create.v1', target };
const inputs = { ...common, api_version:'1', source:readFileSync(root + '/examples/verify_value.py','utf8'),
  answers:{sandbox:'Yes, only the disposable fixture',unknown_policy:'Keep blocked and request review'} };
const bad = await plugin.tool.causalrun_prepare.execute({...inputs, source:'def verify(action_id, payload, evidence):\n    return True\n'}, {});
assert.equal(JSON.parse(bad.output).status, 'VALIDATION_FAILED');
assert.ok(bad.output.length < 700);
assert.ok(!bad.output.includes('artifact'));
checks++;
let approval;
const context = {
  sessionID:'display-test', metadata() {},
  async ask(request) {
    approval = request.metadata;
    assert.ok(!('artifact' in approval));
    const full = JSON.parse(readFileSync(approval.review_file, 'utf8'));
    assert.equal(full.connector_digest, approval.connector_digest);
    assert.equal(full.report_digest, approval.report_digest);
    assert.equal(full.artifact.verifier.source, inputs.source);
    assert.equal(full.validation.failed, 0);
    assert.equal(statSync(approval.review_file).mode & 0o777, 0o600);
    await plugin.event({event:{type:'permission.asked', properties:{...request,sessionID:this.sessionID}}});
  },
};
const approved = await plugin.tool.causalrun_prepare.execute(inputs, context);
assert.equal(JSON.parse(approved.output).status,'APPROVED');
assert.ok(approval.review_file);
checks++;
const write = {...common,action_key:'display-original',payload:{value:'display value'}};
const first = JSON.parse((await plugin.tool.causalrun_write.execute(write)).output);
assert.equal(first.state,'IN_DOUBT');
assert.ok(!('events' in first) && !('receipt' in first));
const same = JSON.parse((await plugin.tool.causalrun_write.execute(write)).output);
assert.equal(same.id, first.id);
checks++;
const verified = await plugin.tool.causalrun_verify.execute({action_id:first.id});
assert.equal(JSON.parse(verified.output).state,'COMMITTED');
assert.equal(verified.title, 'The write is confirmed.');
const summary = await plugin.tool.causalrun_result.execute({action_id:first.id});
assert.ok(summary.output.length < 200);
const details = JSON.parse((await plugin.tool.causalrun_result.execute({action_id:first.id,details:true})).output);
assert.equal(details.receipt.result.value,'display value');
assert.ok(details.events.length >= 2);
checks++;
console.log(JSON.stringify({passed:checks, compact_bytes:summary.output.length, full_bytes:JSON.stringify(details).length}));
