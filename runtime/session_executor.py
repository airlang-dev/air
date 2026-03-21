"""Session execution for the AIR Agent VM.

Orchestrates multi-participant, multi-turn interactions governed by a protocol.
"""

from runtime.llm_utils import call_llm


class SessionExecutor:
    """Executes a session operation via round-robin LLM calls and deterministic resolution."""

    def __init__(self, asset_resolver, config):
        self._asset_resolver = asset_resolver
        self._config = config

    def execute(self, members, protocol_name, history):
        """Run a round-robin session and return (outcome, history)."""
        protocol = self._asset_resolver.resolve_protocol(protocol_name)
        history = list(history)
        moves = []

        for member in members:
            system_prompt = self._build_system_prompt(member, protocol)
            model = member.get("model") or self._config.default_model

            messages = [{"role": "system", "content": system_prompt}] + history
            response = call_llm(model=model, messages=messages, config=self._config)

            move, content = self._parse_move(response, protocol)
            moves.append(move)
            history.append({"role": "assistant", "content": f"[{member['role']}] {response}"})

        outcome = self._resolve(moves, protocol)
        return outcome, history

    def _build_system_prompt(self, member, protocol):
        lines = []
        lines.append(f"You are {member['role']}.")
        if member.get("prompt"):
            lines.append(member["prompt"])
        lines.append(f"Protocol: {protocol['name']}")
        lines.append(f"Legal moves: {', '.join(protocol['moves'])}")
        lines.append("Respond with MOVE: your content")
        return "\n".join(lines)

    def _parse_move(self, response, protocol):
        moves = protocol["moves"]
        if ":" in response:
            prefix, content = response.split(":", 1)
            prefix = prefix.strip()
            if prefix in moves:
                return prefix, content.strip()
        for move in moves:
            for token in response.split():
                cleaned = token.strip(".:,;!?")
                if cleaned == move:
                    return move, response
        return None, response

    def _resolve(self, moves, protocol):
        resolution = protocol.get("resolution", {})
        outcomes_map = resolution.get("outcomes", {})
        default = resolution.get("default", "ESCALATE")

        decisive = [outcomes_map[m] for m in moves if m in outcomes_map]

        if not decisive:
            return default

        if len(set(decisive)) == 1:
            return decisive[0]

        return default
