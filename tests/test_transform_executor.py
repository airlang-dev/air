"""Tests for TransformExecutor."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from runtime.asset_resolver import AssetResolver
from runtime.config import RuntimeConfig
from runtime.transform_executor import TransformExecutor

ASSETS_DIR = Path(__file__).resolve().parent / "fixtures" / "assets"


def _mock_litellm_response(content):
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


class TestLLMTransform:

    def test_calls_litellm_with_resolved_prompt(self):
        """LLM transform resolves prompt and calls litellm."""
        resolver = AssetResolver(ASSETS_DIR)
        executor = TransformExecutor(resolver, RuntimeConfig())

        with patch(
            "runtime.transform_executor.litellm.completion"
        ) as mock_completion:
            mock_completion.return_value = _mock_litellm_response(
                '["claim1", "claim2"]'
            )
            result = executor.execute(
                "Some article text",
                {"target_type": "Claim[]", "via": "extract_claims"},
            )

        assert result == '["claim1", "claim2"]'
        mock_completion.assert_called_once()
        call_kwargs = mock_completion.call_args
        assert "Extract all factual claims" in str(call_kwargs)

    def test_uses_model_from_prompt_asset(self):
        """The model specified in the prompt asset is used."""
        resolver = AssetResolver(ASSETS_DIR)
        executor = TransformExecutor(resolver, RuntimeConfig())

        with patch(
            "runtime.transform_executor.litellm.completion"
        ) as mock_completion:
            mock_completion.return_value = _mock_litellm_response("claims")
            executor.execute(
                "text", {"target_type": "Claim[]", "via": "extract_claims"}
            )

        call_kwargs = mock_completion.call_args
        assert call_kwargs.kwargs.get("model") == "claude-sonnet-4-20250514"

    def test_falls_back_to_stub_without_resolver(self):
        """Without an asset resolver, falls back to stub adapter."""
        executor = TransformExecutor(None, RuntimeConfig())
        result = executor.execute(
            "text", {"target_type": "Claim[]", "via": "extract_claims"}
        )
        assert result == ["claim"]

    def test_falls_back_to_stub_when_prompt_not_found(self):
        """When the prompt asset doesn't exist, falls back to stub."""
        resolver = AssetResolver(ASSETS_DIR)
        executor = TransformExecutor(resolver, RuntimeConfig())
        result = executor.execute(
            "text", {"target_type": "Claim[]", "via": "nonexistent_prompt"}
        )
        assert result == ["claim"]


class TestFuncTransform:

    def test_calls_resolved_function(self):
        """Function transform resolves and calls the Python function."""
        resolver = AssetResolver(ASSETS_DIR)
        executor = TransformExecutor(resolver, RuntimeConfig())

        result = executor.execute(
            "hello world",
            {"target_type": "Features", "via_func": "extract_features"},
        )

        assert result["type"] == "Features"
        assert result["word_count"] == 2
        assert result["char_count"] == 11

    def test_returns_fault_when_function_not_found(self):
        """Returns a Fault when the function cannot be resolved."""
        resolver = AssetResolver(ASSETS_DIR)
        executor = TransformExecutor(resolver, RuntimeConfig())

        result = executor.execute(
            "text",
            {"target_type": "Features", "via_func": "nonexistent_func"},
        )

        assert result["type"] == "Fault"
        assert "not found" in result["reason"]

    def test_returns_fault_when_function_raises(self):
        """Returns a Fault when the function raises an exception."""
        resolver = AssetResolver(ASSETS_DIR)
        executor = TransformExecutor(resolver, RuntimeConfig())

        with patch.object(resolver, "resolve_func") as mock_resolve:
            mock_resolve.return_value = lambda x: 1 / 0
            result = executor.execute(
                "text",
                {"target_type": "Features", "via_func": "bad_func"},
            )

        assert result["type"] == "Fault"
        assert "division by zero" in result["reason"]

    def test_falls_back_to_stub_without_resolver(self):
        """Without an asset resolver, falls back to stub adapter."""
        executor = TransformExecutor(None, RuntimeConfig())
        result = executor.execute(
            "text",
            {"target_type": "Features", "via_func": "extract_features"},
        )
        assert result == ["claim"]


class TestSchemaCoercion:

    def test_parses_json_list(self):
        """Parses a JSON string to a list."""
        executor = TransformExecutor(None, RuntimeConfig())
        result = executor.execute("[1, 2, 3]", {"target_type": "Number[]"})
        assert result == [1, 2, 3]

    def test_parses_json_number(self):
        """Parses a JSON string to a number."""
        executor = TransformExecutor(None, RuntimeConfig())
        result = executor.execute("42", {"target_type": "Number"})
        assert result == 42

    def test_returns_fault_on_invalid_json(self):
        """Returns a Fault on invalid JSON."""
        executor = TransformExecutor(None, RuntimeConfig())
        result = executor.execute("not json", {"target_type": "Number[]"})
        assert result["type"] == "Fault"
        assert "reason" in result

    def test_passes_through_non_string(self):
        """Non-string input is returned unchanged."""
        executor = TransformExecutor(None, RuntimeConfig())
        result = executor.execute([1, 2, 3], {"target_type": "Number[]"})
        assert result == [1, 2, 3]
