def verify(action_id, payload, evidence):
    return isinstance(evidence, dict) and isinstance(evidence["entry"], dict) and evidence["entry"]["client_id"] == action_id and evidence["entry"]["value"] == payload["value"]
