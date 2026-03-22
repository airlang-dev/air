"""Unit tests for air-sdk-gate Lambda handler."""

import pytest
from backends.bedrock.sdk.air_sdk_gate.handler import lambda_handler


# ── Verdict → Outcome mappings ─────────────────────────────────────────────────

@pytest.mark.parametrize("verdict,expected", [
    ("PASS",      "PROCEED"),
    ("FAIL",      "ESCALATE"),
    ("UNCERTAIN", "RETRY"),
    ("pass",      "PROCEED"),   # case-insensitive
    ("fail",      "ESCALATE"),
    ("uncertain", "RETRY"),
    # Already-mapped outcomes pass through
    ("PROCEED",  "PROCEED"),
    ("ESCALATE", "ESCALATE"),
    ("RETRY",    "RETRY"),
    ("HALT",     "HALT"),
])
def test_verdict_to_outcome(verdict, expected):
    result = lambda_handler({"input": verdict}, None)
    assert result == {"outcome": expected}


# ── Consensus object input ─────────────────────────────────────────────────────

def test_consensus_object_pass():
    result = lambda_handler({"input": {"verdict": "PASS", "votes": {"PASS": 2, "FAIL": 0, "UNCERTAIN": 0}, "strategy": "majority"}}, None)
    assert result == {"outcome": "PROCEED"}


def test_consensus_object_fail():
    result = lambda_handler({"input": {"verdict": "FAIL", "votes": {}, "strategy": "unanimous"}}, None)
    assert result == {"outcome": "ESCALATE"}


def test_consensus_object_uncertain():
    result = lambda_handler({"input": {"verdict": "UNCERTAIN"}}, None)
    assert result == {"outcome": "RETRY"}


def test_consensus_object_missing_verdict_returns_fault():
    result = lambda_handler({"input": {}}, None)
    assert "__fault__" in result
    assert "reason" in result["__fault__"]


# ── Missing / invalid input ────────────────────────────────────────────────────

def test_missing_input_key_returns_fault():
    result = lambda_handler({}, None)
    assert "__fault__" in result


def test_none_input_returns_fault():
    result = lambda_handler({"input": None}, None)
    assert "__fault__" in result


def test_unknown_verdict_returns_fault():
    result = lambda_handler({"input": "BOGUS"}, None)
    assert "__fault__" in result
    assert "BOGUS" in result["__fault__"]["reason"]
