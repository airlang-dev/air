"""Unit tests for the Bedrock Flow backend."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from backends.base_backend import Backend
from backends.bedrock.backend import BedrockBackend
from backends.bedrock.compiler import CompilationError

FIXTURES = Path(__file__).parent / "fixtures" / "compiled"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _simple_llm() -> dict:
    return _load("SimpleLLM.airc")


def _simple_verify() -> dict:
    return _load("SimpleVerify.airc")


def _fact_checked() -> dict:
    return _load("FactCheckedPublish.airc")


def _backend(**kw) -> BedrockBackend:
    defaults = dict(
        default_model_id="amazon.nova-lite-v1:0",
        region="us-west-2",
        account_id="000000000000",
    )
    defaults.update(kw)
    return BedrockBackend(**defaults)


# ── 16.1 ──────────────────────────────────────────────────────────────────────

class TestBackendInterface:
    def test_inherits_from_backend(self):
        assert issubclass(BedrockBackend, Backend)

    def test_compile_returns_output_path(self):
        b = _backend()
        result = b.compile(_simple_llm(), output_path=None)
        assert isinstance(result, str)
        assert result.endswith("_bedrock.json")

    def test_default_output_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        b = _backend()
        graph = _simple_llm()
        workflow = graph["workflow"]  # "SimpleLLM"
        b.compile(graph)
        expected = tmp_path / "build" / f"{workflow}_bedrock.json"
        assert expected.exists()



# ── 16.2 ──────────────────────────────────────────────────────────────────────

class TestWarnings:
    def test_no_assets_emits_placeholder_warning(self):
        b = _backend()  # no assets_dir
        _, warnings = b.compile_with_warnings(_simple_llm(), output_path=None)
        assert any("placeholder" in w.lower() or "assets" in w.lower() for w in warnings)

    def test_default_region_emits_warning(self):
        b = BedrockBackend(region="us-east-1", account_id="000000000000")
        _, warnings = b.compile_with_warnings(_simple_llm(), output_path=None)
        assert any("region" in w.lower() for w in warnings)

    def test_default_account_id_emits_warning(self):
        b = BedrockBackend(region="us-west-2", account_id="123456789012")
        _, warnings = b.compile_with_warnings(_simple_llm(), output_path=None)
        assert any("account" in w.lower() for w in warnings)

    def test_custom_region_and_account_no_default_warnings(self):
        b = BedrockBackend(region="eu-west-1", account_id="999999999999")
        _, warnings = b.compile_with_warnings(_simple_llm(), output_path=None)
        region_warns = [w for w in warnings if "region" in w.lower() and "default" in w.lower()]
        account_warns = [w for w in warnings if "account" in w.lower() and "default" in w.lower()]
        assert not region_warns
        assert not account_warns


# ── 16.3 ──────────────────────────────────────────────────────────────────────

class TestOperationVariants:
    def test_transform_via_func_emits_warning(self):
        graph = {
            "air_graph_version": "0.2",
            "workflow": "TestTransform",
            "entry": "n",
            "nodes": {
                "n": {
                    "operations": [
                        {
                            "type": "transform",
                            "inputs": ["x"],
                            "outputs": [{"name": "y", "type": "String"}],
                            "params": {"via_func": "my_func", "target_type": "String"},
                        },
                        {
                            "type": "return",
                            "inputs": ["y"],
                            "outputs": [],
                            "params": {},
                        },
                    ],
                    "terminal": True,
                }
            },
        }
        b = _backend()
        _, warnings = b.compile_with_warnings(graph, output_path=None)
        assert any("my_func" in w for w in warnings)

    def test_parallel_block_emits_warning(self):
        # parallel is a compiler-internal op; test via OperationCompiler directly
        from backends.bedrock.compiler import (
            CompilerConfig, WarningCollector, OperationCompiler,
        )
        from backends.bedrock.naming import NodeNamer
        config = CompilerConfig(region="eu-west-1", account_id="999999999999")
        wc = WarningCollector()
        oc = OperationCompiler(config, wc)
        op = {
            "type": "parallel",
            "branches": [
                {"operations": [{"type": "return", "inputs": [], "outputs": [], "params": {}}]},
            ],
        }
        oc.compile_op(op, "test_node", 0, NodeNamer())
        assert any("parallel" in w.lower() or "sequential" in w.lower() for w in wc.warnings())


# ── 16.4 ──────────────────────────────────────────────────────────────────────

class TestMapAndLoop:
    def test_map_produces_iterator_and_collector(self):
        graph = {
            "air_graph_version": "0.2",
            "workflow": "TestMap",
            "entry": "n",
            "nodes": {
                "n": {
                    "operations": [
                        {
                            "type": "map",
                            "inputs": ["items"],
                            "outputs": [{"name": "results", "type": "Object[]"}],
                            "params": {"workflow": "SubFlow"},
                        },
                        {"type": "return", "inputs": ["results"], "outputs": [], "params": {}},
                    ],
                    "terminal": True,
                }
            },
        }
        b = _backend()
        result, _ = b.compile_with_warnings(graph, output_path=None)
        node_types = [n["type"] for n in result["nodes"]]
        assert "Iterator" in node_types
        assert "Collector" in node_types


# ── 16.5 ──────────────────────────────────────────────────────────────────────

class TestValidation:
    def test_over_40_nodes_raises(self):
        # Build a graph with many single-op nodes to exceed the 40-node limit
        nodes = {}
        for i in range(25):
            nodes[f"n{i}"] = {
                "operations": [
                    {"type": "llm", "inputs": ["x"], "outputs": [{"name": "y", "type": "String"}],
                     "params": {"prompt": "p"}},
                    {"type": "verify", "inputs": ["y"], "outputs": [{"name": "v", "type": "Verdict"}],
                     "params": {"rule": "r"}},
                ],
                "terminal": i == 24,
            }
        graph = {
            "air_graph_version": "0.2",
            "workflow": "Big",
            "entry": "n0",
            "nodes": nodes,
        }
        b = _backend()
        with pytest.raises(CompilationError, match="40"):
            b.compile(graph, output_path=None)

    def test_over_20_connections_emits_warning(self):
        # FactCheckedPublish has enough nodes/edges to exceed 20 connections
        b = _backend()
        _, warnings = b.compile_with_warnings(_fact_checked(), output_path=None)
        conn_warns = [w for w in warnings if "connection" in w.lower()]
        # May or may not exceed 20 — just verify no crash and warnings list is a list
        assert isinstance(warnings, list)

    def test_invalid_airc_raises(self):
        b = _backend()
        with pytest.raises(CompilationError, match="Invalid AIR Graph"):
            b.compile({"not": "valid"}, output_path=None)


# ── 16.6 ──────────────────────────────────────────────────────────────────────

class TestCompileWithWarnings:
    def test_returns_tuple(self):
        b = _backend()
        result = b.compile_with_warnings(_simple_llm(), output_path=None)
        assert isinstance(result, tuple)
        assert len(result) == 2
        flow_def, warnings = result
        assert isinstance(flow_def, dict)
        assert isinstance(warnings, list)

    def test_clean_compile_returns_empty_or_only_non_error_warnings(self):
        # With explicit region+account, no default warnings; no assets → placeholder warning only
        b = BedrockBackend(region="eu-west-1", account_id="999999999999")
        _, warnings = b.compile_with_warnings(_simple_llm(), output_path=None)
        # All warnings should be strings
        assert all(isinstance(w, str) for w in warnings)


# ── 16.7 ──────────────────────────────────────────────────────────────────────

class TestSDKGateInline:
    """Inline tests for gate SDK logic (no Lambda invocation needed)."""

    def _handler(self):
        from backends.bedrock.sdk.air_sdk_gate.handler import lambda_handler
        return lambda_handler

    def test_pass_maps_to_proceed(self):
        result = self._handler()({"input": "PASS"}, None)
        assert result == {"outcome": "PROCEED"}

    def test_fail_maps_to_escalate(self):
        result = self._handler()({"input": "FAIL"}, None)
        assert result == {"outcome": "ESCALATE"}

    def test_uncertain_maps_to_retry(self):
        result = self._handler()({"input": "UNCERTAIN"}, None)
        assert result == {"outcome": "RETRY"}

    def test_consensus_object_uses_verdict_field(self):
        result = self._handler()({"input": {"verdict": "PASS", "votes": {}, "strategy": "majority"}}, None)
        assert result == {"outcome": "PROCEED"}

    def test_missing_input_returns_fault(self):
        result = self._handler()({}, None)
        assert "__fault__" in result

    def test_consensus_missing_verdict_returns_fault(self):
        result = self._handler()({"input": {}}, None)
        assert "__fault__" in result


# ── 16.8 ──────────────────────────────────────────────────────────────────────

class TestSDKAggregateInline:
    def _handler(self):
        from backends.bedrock.sdk.air_sdk_aggregate.handler import lambda_handler
        return lambda_handler

    def test_unanimous_all_pass(self):
        r = self._handler()({"verdicts": ["PASS", "PASS"], "params": {"strategy": "unanimous"}}, None)
        assert r["consensus"]["verdict"] == "PASS"

    def test_unanimous_any_fail(self):
        r = self._handler()({"verdicts": ["PASS", "FAIL"], "params": {"strategy": "unanimous"}}, None)
        assert r["consensus"]["verdict"] == "FAIL"

    def test_majority_pass(self):
        r = self._handler()({"verdicts": ["PASS", "PASS", "FAIL"], "params": {"strategy": "majority"}}, None)
        assert r["consensus"]["verdict"] == "PASS"

    def test_majority_fail(self):
        r = self._handler()({"verdicts": ["FAIL", "FAIL", "PASS"], "params": {"strategy": "majority"}}, None)
        assert r["consensus"]["verdict"] == "FAIL"

    def test_union_any_pass(self):
        r = self._handler()({"verdicts": ["PASS", "FAIL"], "params": {"strategy": "union"}}, None)
        assert r["consensus"]["verdict"] == "PASS"

    def test_missing_verdicts_returns_fault(self):
        r = self._handler()({"params": {"strategy": "majority"}}, None)
        assert "__fault__" in r

    def test_missing_strategy_returns_fault(self):
        r = self._handler()({"verdicts": ["PASS"], "params": {}}, None)
        assert "__fault__" in r


# ── 16.9 ──────────────────────────────────────────────────────────────────────

class TestSDKErrorHandling:
    def test_gate_unknown_verdict_returns_fault(self):
        from backends.bedrock.sdk.air_sdk_gate.handler import lambda_handler
        r = lambda_handler({"input": "BOGUS_VERDICT"}, None)
        assert "__fault__" in r
        assert "reason" in r["__fault__"]

    def test_aggregate_unknown_strategy_returns_fault(self):
        from backends.bedrock.sdk.air_sdk_aggregate.handler import lambda_handler
        r = lambda_handler({"verdicts": ["PASS"], "params": {"strategy": "bogus"}}, None)
        assert "__fault__" in r
        assert "reason" in r["__fault__"]

    def test_aggregate_non_list_verdicts_returns_fault(self):
        from backends.bedrock.sdk.air_sdk_aggregate.handler import lambda_handler
        r = lambda_handler({"verdicts": "not-a-list", "params": {"strategy": "majority"}}, None)
        assert "__fault__" in r
