"""air-sdk-verify Lambda handler.

Verifies an input value against a rule using an LLM.

Input event:
    {
        "input": <any>,
        "params": {"rule": "<rule text or name>", "model": "<optional model id>"}
    }

Output:
    {"verdict": "PASS"|"FAIL"|"UNCERTAIN", "evidence": {"reasoning": "...", "sources": []}}
    or {"__fault__": {"reason": "<message>"}}
"""

import re

import litellm

_DEFAULT_MODEL = "amazon.nova-lite-v1:0"

_SYSTEM_PROMPT = (
    "You are a fact-checking and rule-verification assistant. "
    "Given a rule and an input value, determine whether the input satisfies the rule. "
    "Respond with exactly one of: PASS, FAIL, or UNCERTAIN, followed by a newline and your reasoning."
)


def _parse_verdict(text: str):
    """Extract PASS/FAIL/UNCERTAIN from LLM response text."""
    upper = text.strip().upper()
    for verdict in ("PASS", "FAIL", "UNCERTAIN"):
        if upper.startswith(verdict):
            return verdict
    # Search anywhere in the response
    match = re.search(r"\b(PASS|FAIL|UNCERTAIN)\b", upper)
    if match:
        return match.group(1)
    return "UNCERTAIN"


def lambda_handler(event, context):
    try:
        input_value = event.get("input")
        if input_value is None:
            return {"__fault__": {"reason": "Missing required field: input"}}

        params = event.get("params")
        if params is None:
            return {"__fault__": {"reason": "Missing required field: params"}}

        rule = params.get("rule")
        if not rule:
            return {"__fault__": {"reason": "Missing required field: params.rule"}}

        model = params.get("model", _DEFAULT_MODEL)

        user_message = f"Rule: {rule}\n\nInput: {input_value}"

        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=512,
        )

        response_text = response.choices[0].message.content or ""
        verdict = _parse_verdict(response_text)

        # Reasoning is everything after the verdict keyword
        lines = response_text.strip().splitlines()
        reasoning = "\n".join(lines[1:]).strip() if len(lines) > 1 else response_text

        return {
            "verdict": verdict,
            "evidence": {
                "reasoning": reasoning,
                "sources": [],
            },
        }

    except Exception as exc:
        return {"__fault__": {"reason": str(exc)}}
