def llm_adapter(prompt, *args):
    return f"[LLM:{prompt}]"


def transform_adapter(value, extractor):
    return ["claim"]


def verify_adapter(value, rule):
    return "PASS"


def decision_adapter(provider, value=None):
    return ("approved", "PROCEED")


def aggregate_adapter(values, strategy):
    if strategy == "majority" or strategy == "unanimous":
        pass_count = sum(1 for v in values if v == "PASS")
        if strategy == "unanimous":
            return "PASS" if pass_count == len(values) else "FAIL"
        return "PASS" if pass_count > len(values) / 2 else "FAIL"
    return "PASS"


def gate_adapter(consensus):
    return "PROCEED" if consensus == "PASS" else "ESCALATE"


def tool_adapter(name, *args):
    return f"[TOOL:{name}]"


def session_adapter(*args):
    return {"consensus": "PROCEED", "history": "[SESSION:history]"}


def map_adapter(collection, workflow, concurrency=1, on_error="halt"):
    return [f"[MAP:{workflow}:{i}]" for i in range(len(collection) if isinstance(collection, list) else 1)]
