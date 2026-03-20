"""Governance logic for the AIR Agent VM.

Pure functions for aggregate and gate operations.
"""

from collections import Counter


def aggregate(verdicts, strategy):
    """Combine verdicts into a Consensus dict using the given strategy.

    Returns: {"verdict": str, "verdicts": list[str]}
    """
    if strategy == "unanimous":
        if any(v == "FAIL" for v in verdicts):
            verdict = "FAIL"
        elif any(v == "UNCERTAIN" for v in verdicts):
            verdict = "UNCERTAIN"
        else:
            verdict = "PASS"
    elif strategy == "majority":
        counts = Counter(verdicts)
        top = counts.most_common()
        if len(top) > 1 and top[0][1] == top[1][1]:
            verdict = "UNCERTAIN"
        else:
            verdict = top[0][0]
    else:
        # union or unknown strategy — no reduction
        verdict = "PASS" if all(v == "PASS" for v in verdicts) else "UNCERTAIN"

    return {"verdict": verdict, "verdicts": list(verdicts)}


def gate(input_val):
    """Convert a Verdict string or Consensus dict to an Outcome string.

    Returns: "PROCEED", "ESCALATE", "RETRY", or "HALT"
    """
    verdict_map = {
        "PASS": "PROCEED",
        "FAIL": "ESCALATE",
        "UNCERTAIN": "RETRY",
    }

    if isinstance(input_val, dict):
        verdict = input_val.get("verdict", "UNCERTAIN")
    else:
        verdict = input_val

    return verdict_map.get(verdict, "RETRY")
