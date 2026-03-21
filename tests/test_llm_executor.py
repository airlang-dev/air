"""Tests for LLMExecutor."""

from pathlib import Path
from unittest.mock import patch, MagicMock

from runtime.asset_resolver import AssetResolver
from runtime.config import RuntimeConfig
from runtime.llm_executor import LLMExecutor

ASSETS_DIR = Path(__file__).resolve().parent / "fixtures" / "assets"
RESOLVER = AssetResolver(ASSETS_DIR)


def _mock_litellm_response(content):
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


class TestLLMExecutor:

    def test_calls_litellm_with_resolved_prompt(self):
        """Resolves prompt asset and calls litellm with template + inputs."""
        executor = LLMExecutor(RESOLVER, RuntimeConfig())

        with patch("runtime.llm_utils.litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_litellm_response(
                "Here are the claims..."
            )
            result = executor.execute("extract_claims", ["Some article text"])

        assert result == "Here are the claims..."
        mock_completion.assert_called_once()
        call_str = str(mock_completion.call_args)
        assert "Extract all factual claims" in call_str
        assert "Some article text" in call_str

    def test_uses_model_from_prompt_asset(self):
        """The model specified in the prompt asset is passed to litellm."""
        executor = LLMExecutor(RESOLVER, RuntimeConfig())

        with patch("runtime.llm_utils.litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_litellm_response("result")
            executor.execute("extract_claims", ["text"])

        call_kwargs = mock_completion.call_args
        assert call_kwargs.kwargs.get("model") == "claude-sonnet-4-20250514"

    def test_falls_back_to_config_default_model(self):
        """Uses config default_model when prompt asset has no model."""
        executor = LLMExecutor(RESOLVER, RuntimeConfig(default_model="gpt-4o"))

        with patch("runtime.llm_utils.litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_litellm_response("summary")
            executor.execute("summarize", ["Some content"])

        call_kwargs = mock_completion.call_args
        assert call_kwargs.kwargs.get("model") == "gpt-4o"

    def test_appends_multiple_inputs(self):
        """Multiple input values are appended to the prompt template."""
        executor = LLMExecutor(RESOLVER, RuntimeConfig())

        with patch("runtime.llm_utils.litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_litellm_response("result")
            executor.execute("extract_claims", ["input one", "input two"])

        call_kwargs = mock_completion.call_args
        messages = call_kwargs.kwargs.get("messages")
        user_content = messages[0]["content"]
        assert "input one" in user_content
        assert "input two" in user_content

    def test_returns_response_content(self):
        """Returns the string content from the LLM response."""
        executor = LLMExecutor(RESOLVER, RuntimeConfig())

        with patch("runtime.llm_utils.litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_litellm_response(
                '["claim1", "claim2"]'
            )
            result = executor.execute("extract_claims", ["text"])

        assert result == '["claim1", "claim2"]'
