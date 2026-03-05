def llm_adapter(prompt):
    return f"[LLM:{prompt}]"


def transform_adapter(value, extractor):
    return ["claim"]


def verify_adapter(value, rule):
    return "PASS"


def decision_adapter(provider, value):
    return ("approved", "PROCEED")
