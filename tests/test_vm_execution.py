"""Tests for AgentVM execution."""

from pathlib import Path
from unittest.mock import patch, MagicMock

from runtime.agent_vm import AgentVM
from runtime.asset_resolver import AssetResolver

COMPILED_DIR = Path(__file__).resolve().parent / "fixtures" / "compiled"
ASSETS_DIR = Path(__file__).resolve().parent / "fixtures" / "assets"
RESOLVER = AssetResolver(ASSETS_DIR)


def _mock_litellm_response(content):
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


class TestLLMExecution:

    def test_llm_calls_litellm(self):
        """The VM calls litellm.completion() with resolved prompt."""
        vm = AgentVM.load(COMPILED_DIR / "SimpleLLM.airc", RESOLVER)

        with patch("runtime.llm_executor.litellm.completion") as mock_completion:
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
        vm = AgentVM.load(COMPILED_DIR / "SimpleLLM.airc", RESOLVER)

        # Use extract_claims which has model: claude-sonnet-4-20250514
        vm._graph["nodes"]["start"]["operations"][0]["params"]["prompt"] = (
            "extract_claims"
        )

        with patch("runtime.llm_executor.litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_litellm_response(
                "Claims extracted."
            )
            vm.run(inputs={"content": "Some text"})

        call_kwargs = mock_completion.call_args
        assert call_kwargs.kwargs.get("model") == "claude-sonnet-4-20250514"


class TestTransformExecution:

    def test_llm_transform_end_to_end(self):
        """LLM transform calls litellm through the VM."""
        vm = AgentVM.load(COMPILED_DIR / "TransformLLM.airc", RESOLVER)

        with patch("runtime.transform_executor.litellm.completion") as mock:
            mock.return_value = _mock_litellm_response('["claim1", "claim2"]')
            result = vm.run(inputs={"article": "Some article text"})

        assert result == '["claim1", "claim2"]'
        mock.assert_called_once()

    def test_func_transform_end_to_end(self):
        """Function transform resolves and executes through the VM."""
        vm = AgentVM.load(COMPILED_DIR / "TransformFunc.airc", RESOLVER)

        result = vm.run(inputs={"text": "hello world"})

        assert result["type"] == "Features"
        assert result["word_count"] == 2

    def test_schema_coercion_end_to_end(self):
        """Schema coercion parses JSON through the VM."""
        vm = AgentVM.load(COMPILED_DIR / "TransformCoerce.airc", RESOLVER)

        result = vm.run(inputs={"data": "[1, 2, 3]"})

        assert result == [1, 2, 3]


class TestGovernanceExecution:

    def test_verify_via_llm(self):
        """Verify calls litellm with resolved rule through the VM."""
        vm = AgentVM.load(COMPILED_DIR / "SimpleVerify.airc", RESOLVER)

        with patch("runtime.verify_executor.litellm.completion") as mock:
            mock.return_value = _mock_litellm_response(
                "PASS\n\nAll products are valid."
            )
            result = vm.run(inputs={"claims": "product A exists"})

        assert result == "PASS"
        mock.assert_called_once()

    def test_verify_with_evidence(self):
        """Verify with two outputs stores both verdict and evidence."""
        vm = AgentVM.load(COMPILED_DIR / "VerifyEvidence.airc", RESOLVER)

        with patch("runtime.verify_executor.litellm.completion") as mock:
            mock.return_value = _mock_litellm_response(
                "FAIL\n\nProduct XYZ-9000 not found."
            )
            result = vm.run(inputs={"claims": "XYZ-9000 is great"})

        assert result["fields"]["verdict"] == "FAIL"
        assert "XYZ-9000 not found" in result["fields"]["evidence"]

    def test_governance_chain_proceed(self):
        """Full chain: verify→aggregate→gate routes to PROCEED."""
        vm = AgentVM.load(COMPILED_DIR / "GovernanceChain.airc", RESOLVER)

        with patch("runtime.verify_executor.litellm.completion") as mock:
            mock.return_value = _mock_litellm_response("PASS\n\nLooks good.")
            result = vm.run(inputs={"claims": "valid claims"})

        assert result == "PROCEED"

    def test_governance_chain_escalate(self):
        """Full chain: FAIL verdicts route to ESCALATE."""
        vm = AgentVM.load(COMPILED_DIR / "GovernanceChain.airc", RESOLVER)

        with patch("runtime.verify_executor.litellm.completion") as mock:
            mock.return_value = _mock_litellm_response("FAIL\n\nBad claims.")
            result = vm.run(inputs={"claims": "bad claims"})

        assert result == "ESCALATE"
