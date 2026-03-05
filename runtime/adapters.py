def llm_adapter(prompt):
    return f"[LLM:{prompt}]"


def transform_adapter(value, extractor):
    return ["claim"]


def verify_adapter(value, rule):
    return "PASS"


def decision_adapter(provider, value):
    return ("approved", "PROCEED")


def aggregate_adapter(values, strategy):
    if strategy == "majority":
        pass_count = sum(1 for v in values if v == "PASS")
        return "PASS" if pass_count > len(values) / 2 else "FAIL"
    return "PASS"


def gate_adapter(consensus):
    return "PROCEED" if consensus == "PASS" else "ESCALATE"
