"""Tests for AggregateExecutor and GateExecutor."""

from runtime.aggregate_executor import AggregateExecutor
from runtime.gate_executor import GateExecutor


class TestAggregateExecutor:

    def setup_method(self):
        self.executor = AggregateExecutor()

    def test_unanimous_all_pass(self):
        result = self.executor.execute(["PASS", "PASS", "PASS"], "unanimous")
        assert result["verdict"] == "PASS"
        assert result["verdicts"] == ["PASS", "PASS", "PASS"]

    def test_unanimous_any_fail(self):
        result = self.executor.execute(["PASS", "FAIL", "PASS"], "unanimous")
        assert result["verdict"] == "FAIL"

    def test_unanimous_uncertain_no_fail(self):
        result = self.executor.execute(["PASS", "UNCERTAIN", "PASS"], "unanimous")
        assert result["verdict"] == "UNCERTAIN"

    def test_unanimous_fail_takes_priority_over_uncertain(self):
        result = self.executor.execute(["FAIL", "UNCERTAIN", "PASS"], "unanimous")
        assert result["verdict"] == "FAIL"

    def test_majority_pass(self):
        result = self.executor.execute(["PASS", "PASS", "FAIL"], "majority")
        assert result["verdict"] == "PASS"

    def test_majority_fail(self):
        result = self.executor.execute(["FAIL", "FAIL", "PASS"], "majority")
        assert result["verdict"] == "FAIL"

    def test_majority_tie_is_uncertain(self):
        result = self.executor.execute(["PASS", "FAIL", "UNCERTAIN"], "majority")
        assert result["verdict"] == "UNCERTAIN"

    def test_returns_consensus_dict(self):
        result = self.executor.execute(["PASS", "FAIL"], "majority")
        assert "verdict" in result
        assert "verdicts" in result
        assert result["verdicts"] == ["PASS", "FAIL"]


class TestGateExecutor:

    def setup_method(self):
        self.executor = GateExecutor()

    def test_pass_to_proceed(self):
        assert self.executor.execute("PASS") == "PROCEED"

    def test_fail_to_escalate(self):
        assert self.executor.execute("FAIL") == "ESCALATE"

    def test_uncertain_to_retry(self):
        assert self.executor.execute("UNCERTAIN") == "RETRY"

    def test_consensus_dict_pass(self):
        assert (
            self.executor.execute({"verdict": "PASS", "verdicts": ["PASS", "PASS"]})
            == "PROCEED"
        )

    def test_consensus_dict_fail(self):
        assert (
            self.executor.execute({"verdict": "FAIL", "verdicts": ["FAIL", "PASS"]})
            == "ESCALATE"
        )

    def test_consensus_dict_uncertain(self):
        assert (
            self.executor.execute(
                {"verdict": "UNCERTAIN", "verdicts": ["PASS", "UNCERTAIN"]}
            )
            == "RETRY"
        )
