"""Gate execution for the AIR Agent VM.

Converts a Verdict or Consensus into an Outcome for routing.
"""

VERDICT_TO_OUTCOME = {
    "PASS": "PROCEED",
    "FAIL": "ESCALATE",
    "UNCERTAIN": "RETRY",
}


class GateExecutor:
    """Executes gate operations, mapping Verdict/Consensus to Outcome."""

    def execute(self, input_val):
        """Convert a Verdict string or Consensus dict to an Outcome string.

        Returns: "PROCEED", "ESCALATE", "RETRY", or "HALT"
        """
        if isinstance(input_val, dict):
            verdict = input_val.get("verdict", "UNCERTAIN")
        else:
            verdict = input_val

        return VERDICT_TO_OUTCOME.get(verdict, "RETRY")
