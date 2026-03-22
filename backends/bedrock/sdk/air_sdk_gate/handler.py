"""air-sdk-gate Lambda handler.

Maps AIR Consensus/Verdict values to Bedrock Flow outcome strings.

Input event:
    {"input": <string verdict or Consensus object>}

Output:
    {"outcome": "PROCEED" | "ESCALATE" | "RETRY"}
    or {"__fault__": {"reason": "<message>"}}
"""

VERDICT_TO_OUTCOME = {
    "PASS": "PROCEED",
    "FAIL": "ESCALATE",
    "UNCERTAIN": "RETRY",
    # Already-mapped outcomes pass through
    "PROCEED": "PROCEED",
    "ESCALATE": "ESCALATE",
    "RETRY": "RETRY",
    "HALT": "HALT",
}


def lambda_handler(event, context):
    try:
        raw = event.get("input")
        if raw is None:
            return {"__fault__": {"reason": "Missing required field: input"}}

        # Consensus object: {"verdict": "PASS", ...}
        if isinstance(raw, dict):
            verdict = raw.get("verdict")
            if verdict is None:
                return {"__fault__": {"reason": "Consensus object missing 'verdict' field"}}
        else:
            verdict = str(raw)

        outcome = VERDICT_TO_OUTCOME.get(verdict.upper() if isinstance(verdict, str) else verdict)
        if outcome is None:
            return {"__fault__": {"reason": f"Unknown verdict value: '{verdict}'"}}

        return {"outcome": outcome}

    except Exception as exc:
        return {"__fault__": {"reason": str(exc)}}
