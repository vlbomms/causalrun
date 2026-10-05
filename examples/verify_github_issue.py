# Host-agent-written positive-evidence predicate. Target/author checks run in the adapter.
def verify(action_id, payload, evidence):
    return (
        isinstance(evidence, dict)
        and 'action_id' in evidence
        and evidence['action_id'] == action_id
        and 'payload_digest' in evidence
        and evidence['payload_digest'] == digest(payload)
        and 'result' in evidence
        and isinstance(evidence['result'], dict)
        and 'title' in evidence['result']
        and evidence['result']['title'] == payload['title']
        and 'body' in evidence['result']
        and evidence['result']['body'] == payload['body']
    )
