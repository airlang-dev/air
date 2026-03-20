"""Aggregate execution for the AIR Agent VM.

Combines multiple Verdicts into a Consensus using a strategy.
"""

from collections import Counter


class AggregateExecutor:
    """Executes aggregate operations on Verdict collections."""

    def execute(self, verdicts, strategy):
        """Combine verdicts into a Consensus dict.

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
