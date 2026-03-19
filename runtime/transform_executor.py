"""Transform execution for the AIR Agent VM.

Handles three transform modes:
- LLM-assisted: resolves prompt asset, calls litellm
- Function-assisted: resolves Python function asset, calls it
- Schema coercion: json.loads for strings, pass-through otherwise
"""

import json

import litellm

from runtime.adapters import transform_adapter


class TransformExecutor:
    """Executes transform operations by dispatching on params."""

    def __init__(self, asset_resolver, config):
        self._asset_resolver = asset_resolver
        self._config = config

    def execute(self, input_val, params):
        """Dispatch a transform based on params keys."""
        if "via" in params:
            return self._via_llm(input_val, params["via"])
        elif "via_func" in params:
            return self._via_func(input_val, params["via_func"])
        else:
            return self._coerce(input_val, params.get("target_type"))

    def _via_llm(self, input_val, prompt_name):
        """Transform via LLM: resolve prompt, call litellm."""
        if self._asset_resolver is None:
            return transform_adapter(input_val, prompt_name)

        asset = self._asset_resolver.resolve_prompt(prompt_name)
        if asset is None:
            return transform_adapter(input_val, prompt_name)

        model = asset.model or self._config.default_model
        user_content = f"{asset.template}\n\n{input_val}"

        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": user_content}],
        )
        return response.choices[0].message.content

    def _via_func(self, input_val, func_name):
        """Transform via function: resolve and call Python function."""
        if self._asset_resolver is None:
            return transform_adapter(input_val, func_name)

        func = self._asset_resolver.resolve_func(func_name)
        if func is None:
            return {"type": "Fault", "reason": f"function '{func_name}' not found"}

        try:
            return func(input_val)
        except Exception as e:
            return {"type": "Fault", "reason": str(e)}

    def _coerce(self, input_val, target_type):
        """Schema coercion: parse JSON strings, pass through non-strings."""
        if not isinstance(input_val, str):
            return input_val

        try:
            return json.loads(input_val)
        except (json.JSONDecodeError, ValueError) as e:
            return {"type": "Fault", "reason": f"cannot coerce to {target_type}: {e}"}
