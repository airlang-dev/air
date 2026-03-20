"""Tests for VerifyExecutor."""

from pathlib import Path
from unittest.mock import patch, MagicMock

from runtime.asset_resolver import AssetResolver
from runtime.config import RuntimeConfig
from runtime.verify_executor import VerifyExecutor

ASSETS_DIR = Path(__file__).resolve().parent / "fixtures" / "assets"
RESOLVER = AssetResolver(ASSETS_DIR)


def _mock_litellm_response(content):
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


class TestVerifyLLM:

    def test_calls_litellm_with_rule_and_input(self):
        """Verify resolves rule asset and calls litellm."""
        executor = VerifyExecutor(RESOLVER, RuntimeConfig())

        with patch(
            "runtime.verify_executor.litellm.completion"
        ) as mock_completion:
            mock_completion.return_value = _mock_litellm_response(
                "PASS\n\nAll products referenced are real."
            )
            verdict, evidence = executor.execute("some claims", "product_existence")

        assert verdict == "PASS"
        assert "All products referenced are real" in evidence
        mock_completion.assert_called_once()
        call_str = str(mock_completion.call_args)
        assert "product references" in call_str

    def test_parses_fail_verdict(self):
        """Extracts FAIL from LLM response."""
        executor = VerifyExecutor(RESOLVER, RuntimeConfig())

        with patch(
            "runtime.verify_executor.litellm.completion"
        ) as mock_completion:
            mock_completion.return_value = _mock_litellm_response(
                "FAIL\n\nThe product 'XYZ-9000' does not exist."
            )
            verdict, evidence = executor.execute("claims about XYZ-9000", "product_existence")

        assert verdict == "FAIL"

    def test_parses_uncertain_verdict(self):
        """Extracts UNCERTAIN from LLM response."""
        executor = VerifyExecutor(RESOLVER, RuntimeConfig())

        with patch(
            "runtime.verify_executor.litellm.completion"
        ) as mock_completion:
            mock_completion.return_value = _mock_litellm_response(
                "UNCERTAIN\n\nCannot confirm product availability."
            )
            verdict, _ = executor.execute("ambiguous claims", "product_existence")

        assert verdict == "UNCERTAIN"

    def test_parses_verdict_from_mixed_text(self):
        """Extracts verdict even when embedded in longer text."""
        executor = VerifyExecutor(RESOLVER, RuntimeConfig())

        with patch(
            "runtime.verify_executor.litellm.completion"
        ) as mock_completion:
            mock_completion.return_value = _mock_litellm_response(
                "After careful review, the verdict is PASS. All claims check out."
            )
            verdict, _ = executor.execute("claims", "product_existence")

        assert verdict == "PASS"

    def test_defaults_to_uncertain_on_unparseable(self):
        """Returns UNCERTAIN when verdict cannot be parsed."""
        executor = VerifyExecutor(RESOLVER, RuntimeConfig())

        with patch(
            "runtime.verify_executor.litellm.completion"
        ) as mock_completion:
            mock_completion.return_value = _mock_litellm_response(
                "I'm not sure what to make of this."
            )
            verdict, _ = executor.execute("claims", "product_existence")

        assert verdict == "UNCERTAIN"

    def test_uses_model_from_rule_asset(self):
        """The model from the rule asset is passed to litellm."""
        executor = VerifyExecutor(RESOLVER, RuntimeConfig())

        with patch(
            "runtime.verify_executor.litellm.completion"
        ) as mock_completion:
            mock_completion.return_value = _mock_litellm_response("PASS")
            executor.execute("claims", "product_existence")

        call_kwargs = mock_completion.call_args
        assert call_kwargs.kwargs.get("model") == "claude-sonnet-4-20250514"
