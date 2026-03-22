"""air-sdk-decide Lambda handler.

Dispatches a decision to a human reviewer (via SNS/DynamoDB polling) or an LLM provider.

Input event:
    {
        "input": <any>,
        "params": {
            "provider": "human_reviewer" | "llm" | "<model_id>",
            "model": "<optional model id for llm provider>",
            "timeout_seconds": <optional int, default 300>
        }
    }

Output:
    {"message": "<reasoning>", "outcome": "PROCEED"|"ESCALATE"|"RETRY"|"HALT"}
    or {"__fault__": {"reason": "<message>"}}
"""

import json
import os
import re
import time
import uuid

import litellm

_DEFAULT_MODEL = "amazon.nova-lite-v1:0"
_VALID_OUTCOMES = {"PROCEED", "ESCALATE", "RETRY", "HALT"}

_LLM_SYSTEM = (
    "You are a decision-making assistant. Given an input, decide the appropriate outcome. "
    "Respond with exactly one of: PROCEED, ESCALATE, RETRY, or HALT, followed by a newline "
    "and your reasoning."
)


def _parse_outcome(text: str) -> tuple[str, str]:
    """Return (outcome, message) from LLM response."""
    upper = text.strip().upper()
    for outcome in _VALID_OUTCOMES:
        if upper.startswith(outcome):
            lines = text.strip().splitlines()
            message = "\n".join(lines[1:]).strip() if len(lines) > 1 else text.strip()
            return outcome, message
    match = re.search(r"\b(PROCEED|ESCALATE|RETRY|HALT)\b", upper)
    if match:
        outcome = match.group(1)
        message = text.strip()
        return outcome, message
    return "ESCALATE", text.strip()


def _decide_llm(input_value, params: dict) -> dict:
    model = params.get("model", _DEFAULT_MODEL)
    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": _LLM_SYSTEM},
            {"role": "user", "content": f"Input: {input_value}"},
        ],
        max_tokens=512,
    )
    text = response.choices[0].message.content or ""
    outcome, message = _parse_outcome(text)
    return {"message": message, "outcome": outcome}


def _decide_human(input_value, params: dict) -> dict:
    """Human reviewer via SNS publish + DynamoDB polling.

    Requires env vars: DECISION_TOPIC_ARN, DECISION_TABLE_NAME.
    Falls back to ESCALATE if infrastructure not configured.
    """
    topic_arn = os.environ.get("DECISION_TOPIC_ARN")
    table_name = os.environ.get("DECISION_TABLE_NAME")

    if not topic_arn or not table_name:
        # Infrastructure not configured — escalate for human review via other means
        return {
            "message": "Human reviewer infrastructure not configured; escalating.",
            "outcome": "ESCALATE",
        }

    try:
        import boto3

        sns = boto3.client("sns")
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        decision_id = str(uuid.uuid4())
        timeout = int(params.get("timeout_seconds", 300))

        # Publish decision request
        sns.publish(
            TopicArn=topic_arn,
            Message=json.dumps({"decision_id": decision_id, "input": str(input_value)}),
            Subject="AIR Decision Required",
        )

        # Poll DynamoDB for response
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = table.get_item(Key={"decision_id": decision_id})
            item = resp.get("Item")
            if item and item.get("outcome"):
                outcome = item["outcome"].upper()
                if outcome not in _VALID_OUTCOMES:
                    outcome = "ESCALATE"
                return {"message": item.get("message", ""), "outcome": outcome}
            time.sleep(5)

        return {"message": "Decision timed out waiting for human reviewer.", "outcome": "ESCALATE"}

    except Exception as exc:
        return {"__fault__": {"reason": f"Human reviewer dispatch failed: {exc}"}}


def lambda_handler(event, context):
    try:
        input_value = event.get("input")
        if input_value is None:
            return {"__fault__": {"reason": "Missing required field: input"}}

        params = event.get("params")
        if params is None:
            return {"__fault__": {"reason": "Missing required field: params"}}

        provider = params.get("provider")
        if not provider:
            return {"__fault__": {"reason": "Missing required field: params.provider"}}

        if provider == "human_reviewer":
            result = _decide_human(input_value, params)
        else:
            # provider is "llm" or a model ID
            if provider != "llm":
                params = {**params, "model": provider}
            result = _decide_llm(input_value, params)

        return result

    except Exception as exc:
        return {"__fault__": {"reason": str(exc)}}
