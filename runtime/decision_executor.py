"""Decision execution for the AIR Agent VM.

Evaluates an outcome and optional message using either a human callback or an AI model.
"""

import json
import litellm


class DecisionExecutor:
    """Executes a decision operation returning a (Message, Outcome) tuple."""

    def __init__(self, asset_resolver, config):
        self._asset_resolver = asset_resolver
        self._config = config

    def execute(self, provider, input_val):
        """Invoke the specified provider to return a message and outcome tuple."""
        if provider.startswith("human"):
            return self._execute_human(provider, input_val)
        return self._execute_ai(provider, input_val)

    def _execute_human(self, provider, input_val):
        callback = getattr(self._config, "human_callback", None)
        if callback:
            result = callback(provider, input_val)
            if isinstance(result, tuple):
                return result
            return None, result
        raise RuntimeError(f"No human_callback configured for provider: {provider}")

    def _execute_ai(self, provider, input_val):
        asset = self._asset_resolver.resolve_prompt(provider)
        if hasattr(asset, "template"):
            text_prompt = asset.template.format(input_val=input_val)
            model = getattr(asset, "model", None) or self._config.default_model
        else:
            text_prompt = self._default_prompt(input_val)
            model = self._config.default_model

        messages = [{"role": "user", "content": text_prompt}]
        response = litellm.completion(model=model, messages=messages)
        return self._parse_json_decision(response.choices[0].message.content)

    def _default_prompt(self, input_val):
        return f"Please decide based on input: {input_val}\n\nRespond with JSON: {{'outcome': 'PROCEED|ESCALATE|RETRY|HALT', 'message': {{'role': 'assistant', 'content': '...'}}}}"

    def _parse_json_decision(self, content):
        try:
            parsed = json.loads(content)
            return parsed.get("message"), parsed.get("outcome", "PROCEED")
        except json.JSONDecodeError:
            return None, "PROCEED"
