"""air-sdk-session Lambda handler.

Executes a multi-turn LLM conversation among participants following a protocol.

Input event:
    {
        "members": [{"name": "...", "role": "...", "model": "..."}],
        "protocol": "<protocol text describing conversation rules>",
        "history": [{"role": "...", "content": "..."}],
        "params": {"max_turns": <int, default 6>, "model": "<default model>"}
    }

Output:
    {"result": {"consensus": "PASS"|"FAIL"|"UNCERTAIN", "history": [...]}}
    or {"__fault__": {"reason": "<message>"}}
"""

import re

import litellm

_DEFAULT_MODEL = "amazon.nova-lite-v1:0"
_DEFAULT_MAX_TURNS = 6


def _extract_consensus(history: list[dict]) -> str:
    """Scan the last few messages for a consensus verdict."""
    for msg in reversed(history[-4:]):
        content = (msg.get("content") or "").upper()
        for verdict in ("PASS", "FAIL", "UNCERTAIN"):
            if re.search(rf"\b{verdict}\b", content):
                return verdict
    return "UNCERTAIN"


def lambda_handler(event, context):
    try:
        members = event.get("members")
        if members is None:
            return {"__fault__": {"reason": "Missing required field: members"}}
        if not isinstance(members, list) or len(members) == 0:
            return {"__fault__": {"reason": "Field 'members' must be a non-empty array"}}

        protocol = event.get("protocol")
        if protocol is None:
            return {"__fault__": {"reason": "Missing required field: protocol"}}

        history = event.get("history")
        if history is None:
            return {"__fault__": {"reason": "Missing required field: history"}}
        if not isinstance(history, list):
            return {"__fault__": {"reason": "Field 'history' must be an array"}}

        params = event.get("params") or {}
        max_turns = int(params.get("max_turns", _DEFAULT_MAX_TURNS))
        default_model = params.get("model", _DEFAULT_MODEL)

        # Build conversation history (mutable copy)
        conv_history = list(history)

        # System prompt encodes the protocol and participant roles
        member_descriptions = "\n".join(
            f"- {m.get('name', 'Participant')}: {m.get('role', 'participant')}"
            for m in members
        )
        system_prompt = (
            f"Protocol: {protocol}\n\n"
            f"Participants:\n{member_descriptions}\n\n"
            "Conduct a structured discussion following the protocol. "
            "When consensus is reached, state PASS, FAIL, or UNCERTAIN clearly."
        )

        # Run multi-turn conversation
        for turn in range(max_turns):
            member = members[turn % len(members)]
            model = member.get("model", default_model)
            member_name = member.get("name", f"Participant{turn + 1}")

            messages = [{"role": "system", "content": system_prompt}] + conv_history

            response = litellm.completion(
                model=model,
                messages=messages,
                max_tokens=512,
            )
            content = response.choices[0].message.content or ""

            conv_history.append({
                "role": "assistant",
                "content": f"[{member_name}]: {content}",
            })

            # Early exit if consensus reached
            upper = content.upper()
            if re.search(r"\b(PASS|FAIL|UNCERTAIN)\b", upper) and turn >= len(members) - 1:
                break

        consensus = _extract_consensus(conv_history)

        return {
            "result": {
                "consensus": consensus,
                "history": conv_history,
            }
        }

    except Exception as exc:
        return {"__fault__": {"reason": str(exc)}}
