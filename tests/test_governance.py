"""Tests for aggregate and gate governance logic."""

from runtime.governance import aggregate, gate


class TestAggregate:

    def test_unanimous_all_pass(self):
        result = aggregate(["PASS", "PASS", "PASS"], "unanimous")
        assert result["verdict"] == "PASS"
        assert result["verdicts"] == ["PASS", "PASS", "PASS"]

    def test_unanimous_any_fail(self):
        result = aggregate(["PASS", "FAIL", "PASS"], "unanimous")
        assert result["verdict"] == "FAIL"

    def test_unanimous_uncertain_no_fail(self):
        result = aggregate(["PASS", "UNCERTAIN", "PASS"], "unanimous")
        assert result["verdict"] == "UNCERTAIN"

    def test_unanimous_fail_takes_priority_over_uncertain(self):
        result = aggregate(["FAIL", "UNCERTAIN", "PASS"], "unanimous")
        assert result["verdict"] == "FAIL"

    def test_majority_pass(self):
        result = aggregate(["PASS", "PASS", "FAIL"], "majority")
        assert result["verdict"] == "PASS"

    def test_majority_fail(self):
        result = aggregate(["FAIL", "FAIL", "PASS"], "majority")
        assert result["verdict"] == "FAIL"

    def test_majority_tie_is_uncertain(self):
        result = aggregate(["PASS", "FAIL", "UNCERTAIN"], "majority")
        assert result["verdict"] == "UNCERTAIN"

    def test_returns_consensus_dict(self):
        result = aggregate(["PASS", "FAIL"], "majority")
        assert "verdict" in result
        assert "verdicts" in result
        assert result["verdicts"] == ["PASS", "FAIL"]


class TestGate:

    def test_pass_to_proceed(self):
        assert gate("PASS") == "PROCEED"

    def test_fail_to_escalate(self):
        assert gate("FAIL") == "ESCALATE"

    def test_uncertain_to_retry(self):
        assert gate("UNCERTAIN") == "RETRY"

    def test_consensus_dict_pass(self):
        assert gate({"verdict": "PASS", "verdicts": ["PASS", "PASS"]}) == "PROCEED"

    def test_consensus_dict_fail(self):
        assert gate({"verdict": "FAIL", "verdicts": ["FAIL", "PASS"]}) == "ESCALATE"

    def test_consensus_dict_uncertain(self):
        assert gate({"verdict": "UNCERTAIN", "verdicts": ["PASS", "UNCERTAIN"]}) == "RETRY"
