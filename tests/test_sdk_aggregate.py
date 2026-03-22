"""Unit tests for air-sdk-aggregate Lambda handler."""

import pytest
from backends.bedrock.sdk.air_sdk_aggregate.handler import lambda_handler


def _call(verdicts, strategy):
    return lambda_handler({"verdicts": verdicts, "params": {"strategy": strategy}}, None)


# ── unanimous ──────────────────────────────────────────────────────────────────

class TestUnanimous:
    def test_all_pass(self):
        assert _call(["PASS", "PASS", "PASS"], "unanimous")["consensus"]["verdict"] == "PASS"

    def test_any_fail(self):
        assert _call(["PASS", "FAIL", "PASS"], "unanimous")["consensus"]["verdict"] == "FAIL"

    def test_any_uncertain(self):
        assert _call(["PASS", "UNCERTAIN"], "unanimous")["consensus"]["verdict"] == "UNCERTAIN"

    def test_fail_beats_uncertain(self):
        assert _call(["UNCERTAIN", "FAIL"], "unanimous")["consensus"]["verdict"] == "FAIL"

    def test_single_pass(self):
        assert _call(["PASS"], "unanimous")["consensus"]["verdict"] == "PASS"


# ── majority ───────────────────────────────────────────────────────────────────

class TestMajority:
    def test_majority_pass(self):
        assert _call(["PASS", "PASS", "FAIL"], "majority")["consensus"]["verdict"] == "PASS"

    def test_majority_fail(self):
        assert _call(["FAIL", "FAIL", "PASS"], "majority")["consensus"]["verdict"] == "FAIL"

    def test_tie_is_uncertain(self):
        assert _call(["PASS", "FAIL"], "majority")["consensus"]["verdict"] == "UNCERTAIN"

    def test_empty_is_uncertain(self):
        assert _call([], "majority")["consensus"]["verdict"] == "UNCERTAIN"

    def test_votes_included_in_response(self):
        r = _call(["PASS", "PASS", "FAIL"], "majority")
        assert "votes" in r["consensus"]
        assert r["consensus"]["votes"]["PASS"] == 2
        assert r["consensus"]["votes"]["FAIL"] == 1

    def test_strategy_included_in_response(self):
        r = _call(["PASS"], "majority")
        assert r["consensus"]["strategy"] == "majority"


# ── union ──────────────────────────────────────────────────────────────────────

class TestUnion:
    def test_any_pass_wins(self):
        assert _call(["PASS", "FAIL", "FAIL"], "union")["consensus"]["verdict"] == "PASS"

    def test_all_fail(self):
        assert _call(["FAIL", "FAIL"], "union")["consensus"]["verdict"] == "FAIL"

    def test_mixed_no_pass_is_uncertain(self):
        assert _call(["FAIL", "UNCERTAIN"], "union")["consensus"]["verdict"] == "UNCERTAIN"

    def test_single_uncertain(self):
        assert _call(["UNCERTAIN"], "union")["consensus"]["verdict"] == "UNCERTAIN"


# ── error cases ────────────────────────────────────────────────────────────────

def test_missing_verdicts_returns_fault():
    r = lambda_handler({"params": {"strategy": "majority"}}, None)
    assert "__fault__" in r

def test_missing_params_returns_fault():
    r = lambda_handler({"verdicts": ["PASS"]}, None)
    assert "__fault__" in r

def test_missing_strategy_returns_fault():
    r = lambda_handler({"verdicts": ["PASS"], "params": {}}, None)
    assert "__fault__" in r

def test_unknown_strategy_returns_fault():
    r = _call(["PASS"], "bogus_strategy")
    assert "__fault__" in r

def test_non_list_verdicts_returns_fault():
    r = lambda_handler({"verdicts": "PASS", "params": {"strategy": "majority"}}, None)
    assert "__fault__" in r
