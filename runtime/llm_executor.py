"""LLM execution for the AIR Agent VM.

Resolves prompt assets and calls litellm for real LLM completions.
"""

import litellm


class LLMExecutor:
    """Executes LLM operations via prompt asset resolution and litellm."""

    def __init__(self, asset_resolver, config):
        self._asset_resolver = asset_resolver
        self._config = config

    def execute(self, prompt_name, input_vals):
        """Resolve prompt and call litellm. Returns response content string."""
        asset = self._asset_resolver.resolve_prompt(prompt_name)
        model = asset.model or self._config.default_model
        user_content = asset.template
        for val in input_vals:
            user_content += f"\n\n{val}"

        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": user_content}],
        )
        return response.choices[0].message.content
