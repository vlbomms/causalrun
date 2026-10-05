# Host-agent-written verifier for examples/openapi.json.
# digest is supplied by causalrun's restricted expression runner.
def verify(action_id, payload, evidence):
    return (
        isinstance(evidence, dict)
        and 'action_id' in evidence
        and evidence['action_id'] == action_id
        and 'payload_digest' in evidence
        and evidence['payload_digest'] == digest(payload)
        and 'result' in evidence
        and isinstance(evidence['result'], dict)
        and 'value' in evidence['result']
        and evidence['result']['value'] == payload['value']
    )
