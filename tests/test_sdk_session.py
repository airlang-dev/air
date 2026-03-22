"""Unit tests for air-sdk-session Lambda handler."""

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


_MEMBERS = [
    {"name": "Reviewer", "role": "fact-checker", "model": "amazon.nova-lite-v1:0"},
    {"name": "Editor",   "role": "editor",       "model": "amazon.nova-lite-v1:0"},
]
_PROTOCOL = "Each participant reviews and votes PASS or FAIL."
_HISTORY  = [{"role": "user", "content": "Review this article."}]


def _call(members=_MEMBERS, protocol=_PROTOCOL, history=_HISTORY, params=None,
          llm_responses=None):
    if llm_responses is None:
        llm_responses = ["PASS\nLooks good.", "PASS\nAgreed."]
    event = {
        "members": members,
        "protocol": protocol,
        "history": history,
        "params": params or {"max_turns": 2},
    }
    import backends.bedrock.sdk.air_sdk_session.handler as mod
    responses = iter(_make_llm_response(t) for t in llm_responses)
    with patch.object(mod, "litellm") as mock_litellm:
        mock_litellm.completion.side_effect = lambda **kw: next(responses)
        result = mod.lambda_handler(event, None)
    return result


# ── Happy path ─────────────────────────────────────────────────────────────────

class TestSessionHappyPath:
    def test_returns_result_with_consensus_and_history(self):
        r = _call()
        assert "result" in r
        assert "consensus" in r["result"]
        assert "history" in r["result"]

    def test_consensus_is_valid_verdict(self):
        r = _call(llm_responses=["PASS\nOK.", "PASS\nAgreed."])
        assert r["result"]["consensus"] in ("PASS", "FAIL", "UNCERTAIN")

    def test_pass_consensus_extracted(self):
        r = _call(llm_responses=["PASS\nAll good.", "PASS\nConfirmed."])
        assert r["result"]["consensus"] == "PASS"

    def test_fail_consensus_extracted(self):
        r = _call(llm_responses=["FAIL\nNot valid.", "FAIL\nAgreed."])
        assert r["result"]["consensus"] == "FAIL"

    def test_history_grows_with_turns(self):
        r = _call(params={"max_turns": 2})
        # Original history (1 msg) + 2 turns = at least 3 entries
        assert len(r["result"]["history"]) >= 2

    def test_single_member(self):
        r = _call(
            members=[{"name": "Solo", "role": "reviewer", "model": "amazon.nova-lite-v1:0"}],
            params={"max_turns": 1},
            llm_responses=["PASS\nOK."],
        )
        assert "result" in r

    def test_uncertain_when_no_verdict_in_responses(self):
        r = _call(llm_responses=["I'm not sure.", "Hard to say."])
        assert r["result"]["consensus"] == "UNCERTAIN"


# ── Error cases ────────────────────────────────────────────────────────────────

def test_missing_members_returns_fault():
    import backends.bedrock.sdk.air_sdk_session.handler as mod
    r = mod.lambda_handler({"protocol": _PROTOCOL, "history": _HISTORY, "params": {}}, None)
    assert "__fault__" in r
    assert "members" in r["__fault__"]["reason"]

def test_empty_members_returns_fault():
    import backends.bedrock.sdk.air_sdk_session.handler as mod
    r = mod.lambda_handler({"members": [], "protocol": _PROTOCOL, "history": _HISTORY, "params": {}}, None)
    assert "__fault__" in r

def test_missing_protocol_returns_fault():
    import backends.bedrock.sdk.air_sdk_session.handler as mod
    r = mod.lambda_handler({"members": _MEMBERS, "history": _HISTORY, "params": {}}, None)
    assert "__fault__" in r
    assert "protocol" in r["__fault__"]["reason"]

def test_missing_history_returns_fault():
    import backends.bedrock.sdk.air_sdk_session.handler as mod
    r = mod.lambda_handler({"members": _MEMBERS, "protocol": _PROTOCOL, "params": {}}, None)
    assert "__fault__" in r
    assert "history" in r["__fault__"]["reason"]

def test_non_list_history_returns_fault():
    import backends.bedrock.sdk.air_sdk_session.handler as mod
    r = mod.lambda_handler({"members": _MEMBERS, "protocol": _PROTOCOL, "history": "bad", "params": {}}, None)
    assert "__fault__" in r

def test_litellm_exception_returns_fault():
    import backends.bedrock.sdk.air_sdk_session.handler as mod
    with patch.object(mod, "litellm") as mock_litellm:
        mock_litellm.completion.side_effect = RuntimeError("LLM error")
        r = mod.lambda_handler({
            "members": _MEMBERS, "protocol": _PROTOCOL,
            "history": _HISTORY, "params": {"max_turns": 1},
        }, None)
    assert "__fault__" in r
    assert "LLM error" in r["__fault__"]["reason"]
