import { execFile } from "node:child_process";
import { promisify } from "node:util";
const run = promisify(execFile);

const workflow = `Use ASD-STE100 writing rules for user-facing explanations.
Use short sentences, active voice, and one term for each item.
Use no more than 20 words in an instruction. Use no more than 25 words in a description.
Give the result first. Then give the next step, if one is necessary.
Use no more than three sentences for a normal causalrun update.
Do not show source code, hashes, JSON records, or test schedules unless the user asks for details.
Keep code, API names, paths, and user content unchanged.
Call a connector a write rule. Call a verifier a result check.
COMMITTED means the write is confirmed. IN_DOUBT means the result is unknown.
Before a write, read official API docs or OpenAPI, Swagger, or WSDL files.
Check the request fields, authentication, permissions, and result checks. Use safe reads only.
Use the docs and the user's request to find the required result.
Do not ask what success means when it is clear.
Omit answers.expected_behavior to use documented_success.
For http.json.write.v1, infer expected behavior from the request and docs, then put it in contract.expected.
Use a stable name and exact target origin. Send the declarative contract with causalrun_prepare.
Use environment secret names. Never put secret values in the contract or chat.
Declare correlation and its limits. Do not infer failed execution from missing evidence.
If the required result is unclear, set needs_success_clarification=true. Ask one question and supply the user's answer.
Ask only for missing consent or intent. Use consent already given in this conversation.
Write a pure Python verify(action_id, payload, evidence) expression. Do not use imports, network calls, or side effects.
Call causalrun_prepare. Read its short review to the user. Keep the full review file available.
The user must review the rule before approval. Do not approve your own permissions.
Use the same action_key and payload after a retry or restart.
Never use a new key or a direct write to bypass an unknown result.
A false result check means unknown. It does not prove failure.
Shell scripts and other tools can bypass this plugin.`;

export const messages = {
  PREPARATION_REQUIRED: "The write is blocked. Set up a result check first.",
  VALIDATION_FAILED: "The result check failed its tests. The write is blocked.",
  APPROVED: "The write rule is approved.",
  COMMITTED: "The write is confirmed.",
  IN_DOUBT: "The result is unknown. Do not send the write again.",
};

export function actionSummary(action) {
  return { id: action.id, state: action.state, message: messages[action.state] || "Check the saved result." };
}

function display(value, title = value.message) {
  return { title, output: JSON.stringify(value) };
}

function reviewSummary(review) {
  const artifact = review.artifact;
  return {
    connector_digest: review.connector_digest, report_digest: review.report_digest,
    write: artifact.operation, target: artifact.repository || artifact.target,
    result: typeof artifact.expected === "string" ? artifact.expected : artifact.expected.description,
    tests: `${review.validation.passed} passed. ${review.validation.failed} failed.`,
    limits: artifact.schema_version === 4 ? artifact.limitations.join(". ") : artifact.schema_version === 3
      ? "A copied or changed marker can give incorrect evidence. The search has a limit. Missing evidence does not prove failure."
      : "Missing evidence does not prove failure.",
    review_file: review.review_file,
    instruction: "Read the full review file before you allow this write rule.",
  };
}

export async function createPlugin(ctx, tool, installation) {
  let service;
  const observedReviews = new Set();

  async function ensure() {
    const result = await run(installation.python, ["-m", "causalrun.native", "ensure", "--state", installation.state],
      { cwd: installation.runtime, timeout: 20000, maxBuffer: 65536 });
    service = JSON.parse(result.stdout);
    return service;
  }

  async function api(path, body, operator = false) {
    await ensure();
    const response = await fetch(service.url + path, {
      method: "POST", redirect: "error", signal: AbortSignal.timeout(30000),
      headers: { "Content-Type": "application/json", "Authorization": "Bearer " + (operator ? service.operator_token : service.agent_token) },
      body: JSON.stringify(body),
    });
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || "Local runtime rejected this request");
    return value;
  }

  const scopeArgs = {
    operation: tool.schema.enum(["github.issue.create.v1", "controlled.value.create.v1", "http.json.write.v1"]),
    name: tool.schema.string().optional().describe("Stable operation name for a generic HTTP/JSON API"),
    repository: tool.schema.string().optional().describe("GitHub owner/repository; never a URL override"),
    target: tool.schema.string().optional().describe("Exact HTTPS origin or controlled loopback HTTP origin"),
    needs_success_clarification: tool.schema.boolean().optional().describe("True only when the existing request and API docs leave a material success ambiguity; resolve it before preparation"),
  };

  await ensure();
  return {
    event: async ({ event }) => {
      if (event.type === "session.created") await ensure();
      if (event.type === "permission.asked" && event.properties.permission === "causalrun_approve") {
        const request = event.properties;
        observedReviews.add(request.sessionID + ":" + request.metadata.connector_digest + ":" + request.metadata.report_digest);
      }
    },
    "experimental.chat.system.transform": async (_input, output) => { output.system.push(workflow); },
    "tool.execute.before": async (input, output) => {
      // Only known, structured tool names are protected. Never parse arbitrary shell programs.
      if (["github_create_issue", "github_issue_write"].includes(input.tool)) {
        throw new Error("Use causalrun_write for issue creation. Direct GitHub mutations are held; other issue operations are unsupported.");
      }
      if (input.tool === "http_request" && ["POST", "PUT", "PATCH", "DELETE"].includes(String(output.args.method).toUpperCase())) {
        throw new Error("External API write held. Use causalrun_write for a supported operation; other operations require a new connector.");
      }
    },
    tool: {
      causalrun_write: tool({
        description: "Send an approved HTTP/JSON API write, GitHub issue, or controlled value. First use returns preparation instructions without sending. Never create a new key to retry uncertainty.",
        args: { ...scopeArgs, action_key: tool.schema.string(), payload: tool.schema.record(tool.schema.string(), tool.schema.unknown()) },
        async execute(args) {
          const prepared = await api("/native/lookup", args);
          if (!prepared.ready) return display({ status: "PREPARATION_REQUIRED", message: messages.PREPARATION_REQUIRED,
            scope: prepared.scope, discovery_sources: prepared.discovery_sources, authentication: prepared.authentication,
            questions: prepared.questions, documented_success: prepared.documented_success,
            contract_format: prepared.contract_format,
            verifier_contract: prepared.verifier_contract });
          return display(actionSummary(await api("/v1/actions", { connector_digest: prepared.connector_digest,
            action_key: args.action_key, payload: args.payload })));
        },
      }),
      causalrun_prepare: tool({
        description: "Package host-agent-written verifier and unresolved-question answers. Omit expected_behavior when documented success is clear. Validate in a disposable fixture and request exact review; never send to the configured target.",
        args: { ...scopeArgs, source: tool.schema.string(), answers: tool.schema.record(tool.schema.string(), tool.schema.string()), api_version: tool.schema.string().optional(),
          contract: tool.schema.record(tool.schema.string(), tool.schema.unknown()).optional().describe("Declarative HTTP contract from discovery; required for http.json.write.v1") },
        async execute(args, context) {
          const review = await api("/native/prepare", args);
          const summary = reviewSummary(review);
          if (review.validation.failed) return display({ status: "VALIDATION_FAILED", message: messages.VALIDATION_FAILED,
            validation: { passed: review.validation.passed, failed: review.validation.failed }, review_file: review.review_file });
          context.metadata({ title: "Check the write rule", metadata: summary });
          const key = context.sessionID + ":" + review.connector_digest + ":" + review.report_digest;
          observedReviews.delete(key);
          try {
            await context.ask({ permission: "causalrun_approve", patterns: [review.connector_digest], always: [], metadata: summary });
            // Auto-allow and --auto must not silently approve a connector. Require an actual prompt event.
            for (let attempt = 0; attempt < 20 && !observedReviews.has(key); attempt++) {
              await new Promise(resolve => setTimeout(resolve, 50));
            }
            if (!observedReviews.has(key)) throw new Error("An explicit causalrun review prompt is required. Disable auto-approval and set causalrun_approve permission to ask.");
            const approved = await api("/native/approve", { connector_digest: review.connector_digest,
              report_digest: review.report_digest, scope: review.scope }, true);
            return display({ status: "APPROVED", message: messages.APPROVED, ready: approved.ready,
              connector_digest: approved.connector_digest, review_file: review.review_file });
          } finally { observedReviews.delete(key); }
        },
      }),
      causalrun_verify: tool({
        description: "Run the original pinned read-only verifier. Missing evidence remains IN_DOUBT; no write or retry is made.",
        args: { action_id: tool.schema.string(), details: tool.schema.boolean().optional().describe("True only when the user asks for the full record") },
        async execute(args) {
          const result = await api("/v1/actions/" + encodeURIComponent(args.action_id) + "/verify", {});
          return display(args.details ? result : actionSummary(result), actionSummary(result).message);
        },
      }),
      causalrun_result: tool({
        description: "Retrieve durable action state and timeline without contacting the provider.",
        args: { action_id: tool.schema.string(), details: tool.schema.boolean().optional().describe("True only when the user asks for the full receipt and timeline") },
        async execute(args) {
          await ensure();
          const response = await fetch(service.url + "/v1/actions/" + encodeURIComponent(args.action_id), {
            headers: { Authorization: "Bearer " + service.agent_token }, redirect: "error", signal: AbortSignal.timeout(10000) });
          const result = await response.json();
          if (!response.ok) throw new Error(result.error || "Result unavailable");
          return display(args.details ? result : actionSummary(result), actionSummary(result).message);
        },
      }),
    },
  };
}
