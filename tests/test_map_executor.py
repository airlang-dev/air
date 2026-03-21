"""Tests for MapExecutor."""

import pytest
from unittest.mock import MagicMock

from runtime.map_executor import MapExecutor


class MockAgentVM:
    def __init__(self, should_fail_on=None):
        self._should_fail_on = should_fail_on or []

    def run_workflow(self, workflow_name, inputs=None):
        item = inputs.get("item") if inputs else None
        if item in self._should_fail_on:
            return {"type": "Fault", "reason": f"Failed on {item}"}
        return {"type": "Result", "data": f"Processed {item}"}


class TestMapExecutor:

    def test_map_sequential_all_success(self):
        vm = MockAgentVM()
        executor = MapExecutor(vm)
        
        result = executor.execute([1, 2, 3], "TestWorkflow", concurrency=1, on_error="halt")
        
        assert len(result) == 3
        assert result[0]["data"] == "Processed 1"
        assert result[1]["data"] == "Processed 2"
        assert result[2]["data"] == "Processed 3"

    def test_map_halt_on_error(self):
        vm = MockAgentVM(should_fail_on=[2])
        executor = MapExecutor(vm)
        
        result = executor.execute([1, 2, 3], "TestWorkflow", concurrency=1, on_error="halt")
        
        assert result["type"] == "Fault"
        assert "Failed on 2" in result["reason"]

    def test_map_skip_on_error(self):
        vm = MockAgentVM(should_fail_on=[2])
        executor = MapExecutor(vm)
        
        result = executor.execute([1, 2, 3], "TestWorkflow", concurrency=1, on_error="skip")
        
        assert len(result) == 2
        assert result[0]["data"] == "Processed 1"
        assert result[1]["data"] == "Processed 3"

    def test_map_collect_on_error(self):
        vm = MockAgentVM(should_fail_on=[2])
        executor = MapExecutor(vm)
        
        result = executor.execute([1, 2, 3], "TestWorkflow", concurrency=1, on_error="collect")
        
        assert len(result) == 3
        assert result[0]["type"] == "Result"
        assert result[1]["type"] == "Fault"
        assert result[2]["type"] == "Result"

    def test_map_concurrent(self):
        vm = MockAgentVM()
        executor = MapExecutor(vm)
        
        result = executor.execute([1, 2, 3, 4, 5], "TestWorkflow", concurrency=10, on_error="halt")
        
        assert len(result) == 5
