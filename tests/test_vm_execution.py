"""Tests for AgentVM execution."""

from pathlib import Path
from unittest.mock import patch, MagicMock

from runtime.agent_vm import AgentVM
from runtime.asset_resolver import AssetResolver

COMPILED_DIR = Path(__file__).resolve().parent / "fixtures" / "compiled"
ASSETS_DIR = Path(__file__).resolve().parent / "fixtures" / "assets"


def _mock_litellm_response(content):
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


def test_vm_executes_workflow():
    """The VM loads a compiled .airc, runs it with inputs,
    and returns a result."""
    vm = AgentVM.load(COMPILED_DIR / "FactCheckedPublish.airc")

    result = vm.run(inputs={"content": "Some article text"})

    assert result is not None


class TestLLMExecution:

    def test_llm_calls_litellm(self):
        """When assets are configured, the VM calls litellm.completion()
        instead of returning stub strings."""
        vm = AgentVM.load(COMPILED_DIR / "SimpleLLM.airc")
        vm.asset_resolver = AssetResolver(ASSETS_DIR)

        with patch("runtime.agent_vm.litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_litellm_response(
                "A concise summary."
            )
            result = vm.run(inputs={"content": "Some article text"})

        assert result == "A concise summary."
        mock_completion.assert_called_once()
        call_kwargs = mock_completion.call_args
        assert "summarize" not in str(call_kwargs)  # prompt name resolved to template
        assert "Summarize" in str(call_kwargs)  # actual template content used

    def test_llm_uses_model_from_prompt_asset(self):
        """The model specified in a YAML prompt asset is passed to litellm."""
        vm = AgentVM.load(COMPILED_DIR / "SimpleLLM.airc")
        vm.asset_resolver = AssetResolver(ASSETS_DIR)

        # Use extract_claims which has model: claude-sonnet-4-20250514
        vm._graph["nodes"]["start"]["operations"][0]["params"]["prompt"] = (
            "extract_claims"
        )

        with patch("runtime.agent_vm.litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_litellm_response(
                "Claims extracted."
            )
            vm.run(inputs={"content": "Some text"})

        call_kwargs = mock_completion.call_args
        assert call_kwargs.kwargs.get("model") == "claude-sonnet-4-20250514"

    def test_llm_falls_back_to_adapter_without_assets(self):
        """Without an asset resolver, the VM falls back to stub adapters."""
        vm = AgentVM.load(COMPILED_DIR / "SimpleLLM.airc")
        # No asset_resolver set — should use adapter fallback
        result = vm.run(inputs={"content": "Some article text"})

        assert result == "[LLM:summarize]"
