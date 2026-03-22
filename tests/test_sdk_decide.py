"""Unit tests for air-sdk-decide Lambda handler."""

from unittest.mock import MagicMock, patch

import pytest


def _make_llm_response(text: str):
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _call_llm(input_val, provider="llm", model=None, llm_text="PROCEED\nLooks good."):
    params = {"provider": provider}
    if model:
        params["model"] = model
    event = {"input": input_val, "params": params}
    import backends.bedrock.sdk.air_sdk_decide.handler as mod
    with patch.object(mod, "litellm") as mock_litellm:
        mock_litellm.completion.return_value = _make_llm_response(llm_text)
        result = mod.lambda_handler(event, None)
    return result


# ── LLM provider ───────────────────────────────────────────────────────────────

class TestLLMProvider:
    def test_proceed_outcome(self):
        r = _call_llm("some content", llm_text="PROCEED\nAll good.")
        assert r["outcome"] == "PROCEED"

    def test_escalate_outcome(self):
        r = _call_llm("some content", llm_text="ESCALATE\nNeeds review.")
        assert r["outcome"] == "ESCALATE"

    def test_retry_outcome(self):
        r = _call_llm("some content", llm_text="RETRY\nTry again.")
        assert r["outcome"] == "RETRY"

    def test_halt_outcome(self):
        r = _call_llm("some content", llm_text="HALT\nStop processing.")
        assert r["outcome"] == "HALT"

    def test_message_included(self):
        r = _call_llm("x", llm_text="PROCEED\nDetailed reasoning here.")
        assert "message" in r
        assert isinstance(r["message"], str)

    def test_outcome_in_middle_of_response(self):
        r = _call_llm("x", llm_text="After review: PROCEED because it's fine.")
        assert r["outcome"] == "PROCEED"

    def test_model_id_as_provider(self):
        """Provider can be a model ID directly."""
        r = _call_llm("x", provider="amazon.nova-lite-v1:0", llm_text="PROCEED\nOK.")
        assert r["outcome"] == "PROCEED"


# ── Human reviewer provider ────────────────────────────────────────────────────

class TestHumanReviewer:
    def test_no_infra_escalates(self):
        """Without DECISION_TOPIC_ARN/DECISION_TABLE_NAME, falls back to ESCALATE."""
        import backends.bedrock.sdk.air_sdk_decide.handler as mod
        import os
        env = {k: v for k, v in os.environ.items()
               if k not in ("DECISION_TOPIC_ARN", "DECISION_TABLE_NAME")}
        with patch.dict(os.environ, env, clear=True):
            r = mod.lambda_handler({"input": "x", "params": {"provider": "human_reviewer"}}, None)
        assert r["outcome"] == "ESCALATE"
        assert "message" in r


# ── Error cases ────────────────────────────────────────────────────────────────

def test_missing_input_returns_fault():
    import backends.bedrock.sdk.air_sdk_decide.handler as mod
    r = mod.lambda_handler({"params": {"provider": "llm"}}, None)
    assert "__fault__" in r

def test_missing_params_returns_fault():
    import backends.bedrock.sdk.air_sdk_decide.handler as mod
    r = mod.lambda_handler({"input": "x"}, None)
    assert "__fault__" in r

def test_missing_provider_returns_fault():
    import backends.bedrock.sdk.air_sdk_decide.handler as mod
    r = mod.lambda_handler({"input": "x", "params": {}}, None)
    assert "__fault__" in r
    assert "provider" in r["__fault__"]["reason"]

def test_litellm_exception_returns_fault():
    import backends.bedrock.sdk.air_sdk_decide.handler as mod
    with patch.object(mod, "litellm") as mock_litellm:
        mock_litellm.completion.side_effect = RuntimeError("LLM down")
        r = mod.lambda_handler({"input": "x", "params": {"provider": "llm"}}, None)
    assert "__fault__" in r
    assert "LLM down" in r["__fault__"]["reason"]
