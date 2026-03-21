"""Tests for MapExecutor."""

import pytest
from unittest.mock import MagicMock, patch
from runtime.map_executor import MapExecutor


@pytest.fixture
def mock_vm():
    vm = MagicMock()
    vm.get_workflow.return_value = {"workflow": "sub_logic"}
    return vm


@patch("runtime.workflow_runner.WorkflowRunner")
def test_map_sequential(mock_runner_class, mock_vm):
    mock_runner = MagicMock()
    mock_runner.run.side_effect = lambda inputs: inputs["item"] * 2
    mock_runner_class.return_value = mock_runner

    executor = MapExecutor(mock_vm)
    results = executor.execute([1, 2, 3], "sub_logic")
    assert results == [2, 4, 6]
    assert mock_runner_class.call_count == 3


@patch("runtime.workflow_runner.WorkflowRunner")
def test_map_concurrent(mock_runner_class, mock_vm):
    mock_runner = MagicMock()
    mock_runner.run.side_effect = lambda inputs: inputs["item"] * 2
    mock_runner_class.return_value = mock_runner

    executor = MapExecutor(mock_vm)
    results = executor.execute([1, 2, 3], "sub_logic", concurrency=3)
    assert results == [2, 4, 6]


@patch("runtime.workflow_runner.WorkflowRunner")
def test_map_error_halt(mock_runner_class, mock_vm):
    fault = {"type": "Fault", "message": "Failed item"}
    mock_runner = MagicMock()
    mock_runner.run.side_effect = lambda inputs: (
        fault if inputs["item"] == 2 else inputs["item"] * 2
    )
    mock_runner_class.return_value = mock_runner

    executor = MapExecutor(mock_vm)
    results = executor.execute([1, 2, 3], "sub_logic", on_error="halt")
    assert results == fault
    assert mock_runner_class.call_count == 2


@patch("runtime.workflow_runner.WorkflowRunner")
def test_map_error_skip(mock_runner_class, mock_vm):
    fault = {"type": "Fault", "message": "Failed item"}
    mock_runner = MagicMock()
    mock_runner.run.side_effect = lambda inputs: (
        fault if inputs["item"] == 2 else inputs["item"] * 2
    )
    mock_runner_class.return_value = mock_runner

    executor = MapExecutor(mock_vm)
    results = executor.execute([1, 2, 3], "sub_logic", on_error="skip")
    assert results == [2, 6]


@patch("runtime.workflow_runner.WorkflowRunner")
def test_map_error_collect(mock_runner_class, mock_vm):
    fault = {"type": "Fault", "message": "Failed item"}
    mock_runner = MagicMock()
    mock_runner.run.side_effect = lambda inputs: (
        fault if inputs["item"] == 2 else inputs["item"] * 2
    )
    mock_runner_class.return_value = mock_runner

    executor = MapExecutor(mock_vm)
    results = executor.execute([1, 2, 3], "sub_logic", on_error="collect")
    assert results == [2, fault, 6]
