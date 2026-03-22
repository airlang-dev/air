"""air-sdk-aggregate Lambda handler.

Aggregates a list of verdicts using a configurable strategy.

Input event:
    {
        "verdicts": ["PASS", "FAIL", ...],
        "params": {"strategy": "unanimous" | "majority" | "union"}
    }

Output:
    {"consensus": {"verdict": "PASS"|"FAIL"|"UNCERTAIN", "votes": {...}, "strategy": "..."}}
    or {"__fault__": {"reason": "<message>"}}
"""


def _count_votes(verdicts):
    counts = {"PASS": 0, "FAIL": 0, "UNCERTAIN": 0}
    for v in verdicts:
        key = str(v).upper()
        if key in counts:
            counts[key] += 1
        else:
            counts["UNCERTAIN"] += 1
    return counts


def _unanimous(verdicts):
    counts = _count_votes(verdicts)
    if counts["FAIL"] > 0:
        return "FAIL", counts
    if counts["UNCERTAIN"] > 0:
        return "UNCERTAIN", counts
    return "PASS", counts


def _majority(verdicts):
    counts = _count_votes(verdicts)
    total = len(verdicts)
    if total == 0:
        return "UNCERTAIN", counts
    if counts["PASS"] > total / 2:
        return "PASS", counts
    if counts["FAIL"] > total / 2:
        return "FAIL", counts
    return "UNCERTAIN", counts


def _union(verdicts):
    """Union: PASS if any PASS, FAIL only if all FAIL, else UNCERTAIN."""
    counts = _count_votes(verdicts)
    if counts["PASS"] > 0:
        return "PASS", counts
    if counts["FAIL"] == len(verdicts):
        return "FAIL", counts
    return "UNCERTAIN", counts


STRATEGIES = {
    "unanimous": _unanimous,
    "majority": _majority,
    "union": _union,
}


def lambda_handler(event, context):
    try:
        verdicts = event.get("verdicts")
        if verdicts is None:
            return {"__fault__": {"reason": "Missing required field: verdicts"}}
        if not isinstance(verdicts, list):
            return {"__fault__": {"reason": "Field 'verdicts' must be an array"}}

        params = event.get("params")
        if params is None:
            return {"__fault__": {"reason": "Missing required field: params"}}

        strategy_name = params.get("strategy")
        if not strategy_name:
            return {"__fault__": {"reason": "Missing required field: params.strategy"}}

        strategy_fn = STRATEGIES.get(strategy_name)
        if strategy_fn is None:
            return {"__fault__": {"reason": f"Unknown strategy: '{strategy_name}'. Use: unanimous, majority, union"}}

        verdict, votes = strategy_fn(verdicts)
        return {
            "consensus": {
                "verdict": verdict,
                "votes": votes,
                "strategy": strategy_name,
            }
        }

    except Exception as exc:
        return {"__fault__": {"reason": str(exc)}}
