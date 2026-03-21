"""Tests for the WorkflowLoader."""

import json
import os
import tempfile

import pytest

from runtime.asset_resolver import AssetResolver
from runtime.config import RuntimeConfig
from runtime.workflow_loader import WorkflowLoader


def _make_graph(name, deps=None):
    """Create a minimal AIR graph dict."""
    graph = {
        "air_graph_version": "0.2",
        "workflow": name,
        "entry": "start",
        "nodes": {
            "start": {
                "operations": [],
                "edges": [],
            }
        },
    }
    if deps:
        for dep in deps:
            graph["nodes"]["start"]["operations"].append(
                {"type": "map", "params": {"workflow": dep}, "inputs": [], "output": []}
            )
    return graph


class TestSubWorkflowDiscovery:
    """Verify that the loader finds sub-workflows in the .airc file's directory."""

    def test_finds_sibling_sub_workflow(self, tmp_path):
        """Sub-workflow .airc in the same directory as the primary is discovered."""
        sub_graph = _make_graph("ProcessItem")
        main_graph = _make_graph("BatchProcess", deps=["ProcessItem"])

        main_path = tmp_path / "BatchProcess.airc"
        sub_path = tmp_path / "ProcessItem.airc"

        main_path.write_text(json.dumps(main_graph))
        sub_path.write_text(json.dumps(sub_graph))

        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        resolver = AssetResolver(str(assets_dir))
        loader = WorkflowLoader(resolver, RuntimeConfig())

        graph, cache = loader.build(str(main_path))

        assert "BatchProcess" in cache
        assert "ProcessItem" in cache

    def test_sub_workflow_not_found_returns_none(self, tmp_path):
        """Missing sub-workflow doesn't crash, just isn't cached."""
        main_graph = _make_graph("BatchProcess", deps=["MissingWorkflow"])

        main_path = tmp_path / "BatchProcess.airc"
        main_path.write_text(json.dumps(main_graph))

        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        resolver = AssetResolver(str(assets_dir))
        loader = WorkflowLoader(resolver, RuntimeConfig())

        graph, cache = loader.build(str(main_path))

        assert "BatchProcess" in cache
        assert "MissingWorkflow" not in cache

    def test_dict_input_skips_airc_dir_search(self):
        """When loading from a dict, sub-workflow file search is skipped gracefully."""
        main_graph = _make_graph("InMemory", deps=["SomeChild"])

        with tempfile.TemporaryDirectory() as tmp:
            resolver = AssetResolver(tmp)
            loader = WorkflowLoader(resolver, RuntimeConfig())

            graph, cache = loader.build(main_graph)

            assert "InMemory" in cache
            assert "SomeChild" not in cache
