# Documentation

Start with [installation](install-opencode.md) and [the local API test](test-opencode.md).

| Task | Document |
| --- | --- |
| Use another harness | [MCP setup](install-mcp.md) |
| Understand the tools | [Harness API](harness-api.md) |
| Write a result check | [Agent workflow](agent-workflow.md) |
| Add an HTTP/JSON API | [Custom write rules](http-json.md) |
| Read the output rules | [Clear language](language.md) |
| Check the full live-agent flow | [Functional test](functional-test.md) |
| Run the manual HTTP demo | [CLI demo](cli-demo.md) |
| Work on the code | [Development](development.md) |

## Test evidence

The result files are historical evidence. Keep them unchanged when the code changes.
They include failed attempts, limits, commands, versions, and execution hashes.

| Work | Evidence |
| --- | --- |
| Write contracts | [Gate 1](gate-1.md) |
| Stored result checks | [Gate 2](gate-2.md) |
| GitHub issue recovery | [Gate 3](gate-3.md) |
| OpenCode installation | [Gate 4](gate-4.md) |
| Shared harness API | [Gate 5](gate-5.md) |
| Selective questions | [Results](results/selective-questions/README.md) |
| Short output and session startup | [Results](results/usability/README.md) |
| Generic requests and boundaries | [HTTP gate A](results/http-gate-a/README.md) |
| Generic recovery and process crashes | [HTTP gate B](results/http-gate-b/README.md) |
| Generic OpenCode and MCP use | [HTTP gate C](results/http-gate-c/README.md) |
| Generic live GitHub write and recovery | [HTTP gate D](results/http-gate-d/README.md) |

See [SPEC.md](../SPEC.md) for the contract and [the gate matrix](milestones.md) for the implementation history.
