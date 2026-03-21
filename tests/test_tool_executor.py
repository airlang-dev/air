"""Tests for ToolExecutor."""

import pytest
from unittest.mock import MagicMock

from runtime.tool_executor import ToolExecutor
from runtime.config import RuntimeConfig


@pytest.fixture
def asset_resolver():
    mock = MagicMock()
    return mock


class TestToolExecutor:

    def test_executes_tool_and_returns_result(self, asset_resolver):
        """Tool resolves by name and returns the callable's result."""

        def fetch_docs(product_id):
            return {"title": "Widget Manual", "pages": 42}

        asset_resolver.resolve_tool.return_value = fetch_docs

        executor = ToolExecutor(asset_resolver, RuntimeConfig())
        result = executor.execute("fetch_docs", ["prod_123"])

        assert result == {"title": "Widget Manual", "pages": 42}
        asset_resolver.resolve_tool.assert_called_once_with("fetch_docs")

    def test_passes_multiple_args(self, asset_resolver):
        """Multiple input args are passed positionally to the tool callable."""

        def search(query, limit):
            return [f"result_{i}" for i in range(limit)]

        asset_resolver.resolve_tool.return_value = search

        executor = ToolExecutor(asset_resolver, RuntimeConfig())
        result = executor.execute("search", ["ai agents", 3])

        assert result == ["result_0", "result_1", "result_2"]

    def test_returns_fault_on_exception(self, asset_resolver):
        """Tool exceptions are caught and returned as Fault."""

        def failing_tool(x):
            raise ConnectionError("Database unavailable")

        asset_resolver.resolve_tool.return_value = failing_tool

        executor = ToolExecutor(asset_resolver, RuntimeConfig())
        result = executor.execute("failing_tool", ["arg"])

        assert result["type"] == "Fault"
        assert "Database unavailable" in result["message"]

    def test_returns_fault_when_tool_not_found(self, asset_resolver):
        """Missing tool returns Fault instead of crashing."""
        asset_resolver.resolve_tool.return_value = None

        executor = ToolExecutor(asset_resolver, RuntimeConfig())
        result = executor.execute("nonexistent_tool", [])

        assert result["type"] == "Fault"
        assert "nonexistent_tool" in result["message"]

    def test_tool_with_no_args(self, asset_resolver):
        """Tool can be called with zero arguments."""

        def get_timestamp():
            return "2026-03-21T17:00:00Z"

        asset_resolver.resolve_tool.return_value = get_timestamp

        executor = ToolExecutor(asset_resolver, RuntimeConfig())
        result = executor.execute("get_timestamp", [])

        assert result == "2026-03-21T17:00:00Z"
