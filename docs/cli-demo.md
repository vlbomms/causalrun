# Manual HTTP demo

This path is for runtime development. For normal use, install the OpenCode plugin.

## Run the demo

Run these commands from the checkout. They use disposable public demonstration
tokens; use your own secrets outside this demo.

Start the controlled application in one terminal:

```sh
mkdir -p .local
CAUSALRUN_PROVIDER_TOKEN=demo-provider-token-only \
  python3 -m examples.provider --db .local/provider.sqlite --port 8090
```

In an operator terminal, create and validate its connector:

```sh
python3 -m causalrun artifact --target http://127.0.0.1:8090 > .local/connector.json
python3 -m causalrun register .local/connector.json
```

Copy the returned `connector_digest` into `DIGEST`:

```sh
DIGEST=PASTE_RETURNED_DIGEST
python3 -m causalrun validate "$DIGEST"
python3 -m causalrun approve "$DIGEST"
```

Approval displays the artifact, validation report, and limitations. Type the full
digest in the interactive terminal only after reviewing them. There is no
noninteractive approval flag or agent-facing approval endpoint. Validation writes
to a temporary fixture, not to the configured target. Generated connectors
for the controlled API require a separate `CAUSALRUN_RECEIPT_TOKEN` configured on both the service and
controlled provider; see the agent workflow.

Start the runtime in that operator terminal:

```sh
CAUSALRUN_AGENT_TOKEN=demo-agent-token-only \
CAUSALRUN_PROVIDER_TOKEN=demo-provider-token-only \
  python3 -m causalrun serve --port 8080
```

From a client terminal, submit one action using only the agent token. Substitute
the actual digest below:

```sh
curl --fail-with-body http://127.0.0.1:8080/v1/actions \
  -H 'Authorization: Bearer demo-agent-token-only' \
  -H 'Content-Type: application/json' \
  --data '{"connector_digest":"PASTE_RETURNED_DIGEST","action_key":"first-value","payload":{"value":"hello"}}'
```

Copy the returned action ID to inspect its receipt and timeline:

```sh
curl --fail-with-body http://127.0.0.1:8080/v1/actions/PASTE_ACTION_ID \
  -H 'Authorization: Bearer demo-agent-token-only'
```

Submitting the same key/payload again returns the same record without another
provider write. A changed payload is rejected. Do not invent a new key to bypass
an uncertain action. Connector changes require new validation and approval; they
cannot replace an existing action under the same operation/target/key.

