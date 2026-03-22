"""Unit tests for air-sdk-verify Lambda handler."""

from unittest.mock import MagicMock, patch

import pytest


def _make_llm_response(text: str):
    """Build a minimal litellm-style response object."""
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _call(input_val, rule, model=None, llm_response_text="PASS\nLooks good."):
    params = {"rule": rule}
    if model:
        params["model"] = model
    event = {"input": input_val, "params": params}
    with patch("backends.bedrock.sdk.air_sdk_verify.handler.litellm") as mock_litellm:
        mock_litellm.completion.return_value = _make_llm_response(llm_response_text)
        from backends.bedrock.sdk.air_sdk_verify.handler import lambda_handler
        return lambda_handler(event, None), mock_litellm


# ── Verdict parsing ────────────────────────────────────────────────────────────

class TestVerdictParsing:
    def test_pass_verdict(self):
        result, _ = _call("some input", "some_rule", llm_response_text="PASS\nAll good.")
        assert result["verdict"] == "PASS"

    def test_fail_verdict(self):
        result, _ = _call("some input", "some_rule", llm_response_text="FAIL\nDoes not satisfy rule.")
        assert result["verdict"] == "FAIL"

    def test_uncertain_verdict(self):
        result, _ = _call("some input", "some_rule", llm_response_text="UNCERTAIN\nCannot determine.")
        assert result["verdict"] == "UNCERTAIN"

    def test_verdict_in_middle_of_response(self):
        result, _ = _call("x", "r", llm_response_text="After review: PASS because it checks out.")
        assert result["verdict"] == "PASS"

    def test_ambiguous_defaults_to_uncertain(self):
        result, _ = _call("x", "r", llm_response_text="I cannot say for sure.")
        assert result["verdict"] == "UNCERTAIN"

    def test_evidence_included(self):
        result, _ = _call("x", "r", llm_response_text="PASS\nReasoning here.")
        assert "evidence" in result
        assert "reasoning" in result["evidence"]
        assert isinstance(result["evidence"]["sources"], list)

    def test_reasoning_extracted(self):
        result, _ = _call("x", "r", llm_response_text="PASS\nDetailed reasoning.")
        assert "Detailed reasoning" in result["evidence"]["reasoning"]


# ── LLM call parameters ────────────────────────────────────────────────────────

def test_uses_default_model_when_not_specified():
    _, mock_litellm = _call("x", "r")
    call_kwargs = mock_litellm.completion.call_args
    assert call_kwargs is not None


def test_uses_specified_model():
    _, mock_litellm = _call("x", "r", model="gpt-4o")
    call_kwargs = mock_litellm.completion.call_args
    assert call_kwargs[1]["model"] == "gpt-4o" or call_kwargs[0][0] == "gpt-4o"


# ── Error cases ────────────────────────────────────────────────────────────────

def test_missing_input_returns_fault():
    from backends.bedrock.sdk.air_sdk_verify.handler import lambda_handler
    r = lambda_handler({"params": {"rule": "r"}}, None)
    assert "__fault__" in r
    assert "input" in r["__fault__"]["reason"]


def test_missing_params_returns_fault():
    from backends.bedrock.sdk.air_sdk_verify.handler import lambda_handler
    r = lambda_handler({"input": "x"}, None)
    assert "__fault__" in r


def test_missing_rule_returns_fault():
    from backends.bedrock.sdk.air_sdk_verify.handler import lambda_handler
    r = lambda_handler({"input": "x", "params": {}}, None)
    assert "__fault__" in r
    assert "rule" in r["__fault__"]["reason"]


def test_litellm_exception_returns_fault():
    import backends.bedrock.sdk.air_sdk_verify.handler as mod
    with patch.object(mod, "litellm") as mock_litellm:
        mock_litellm.completion.side_effect = RuntimeError("API error")
        r = mod.lambda_handler({"input": "x", "params": {"rule": "r"}}, None)
    assert "__fault__" in r
    assert "API error" in r["__fault__"]["reason"]
