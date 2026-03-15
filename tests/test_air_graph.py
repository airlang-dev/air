"""Tests for the AIR Graph builder and serializer (v0.2)."""

import json
import pytest

from helpers import build_fixture
from ast_builder import ASTBuilder
from cfg_builder import build_cfg
from air_graph.builder import build_air_graph
from air_graph.serializer import serialize_air_graph, validate_air_graph
from air_graph.schema import AirGraphWorkflow, AirGraphNode, AirGraphOperation


def build_graph(parser, fixture_name: str) -> AirGraphWorkflow:
    program = build_fixture(parser, fixture_name)
    w = program.workflows[0]
    cfg = build_cfg(w)
    return build_air_graph(cfg, w.name)


def build_and_serialize(parser, fixture_name: str) -> dict:
    graph = build_graph(parser, fixture_name)
    return serialize_air_graph(graph)


# ---------------------------------------------------------------------------
# Basic structure
# ---------------------------------------------------------------------------

class TestBasicStructure:

    def test_workflow_name_and_entry(self, parser):
        graph = build_graph(parser, "basic")
        assert graph.name == "W"
        assert graph.entry == "start"

    def test_all_nodes_present(self, parser):
        graph = build_graph(parser, "nodes")
        names = {n.name for n in graph.nodes}
        assert names == {"start", "publish", "retry", "discuss", "recovery"}

    def test_terminal_node(self, parser):
        graph = build_graph(parser, "basic")
        start = next(n for n in graph.nodes if n.name == "start")
        assert start.terminal is True
        assert start.edges == []


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

class TestOperations:

    def test_llm_operation(self, parser):
        graph = build_graph(parser, "llm")
        node = next(n for n in graph.nodes if n.name == "two_args")
        llm_ops = [op for op in node.operations if op.type == "llm"]
        assert len(llm_ops) == 1
        assert llm_ops[0].params["prompt"] == "summarize"
        assert llm_ops[0].outputs[0].name == "result"
        assert llm_ops[0].outputs[0].type == "Message"

    def test_tool_operation(self, parser):
        graph = build_graph(parser, "tool")
        node = next(n for n in graph.nodes if n.name == "assigned")
        tool_ops = [op for op in node.operations if op.type == "tool"]
        assert len(tool_ops) == 1
        assert tool_ops[0].params["name"] == "fetch_docs"

    def test_bare_tool_operation(self, parser):
        """Bare tool(...) without assignment should still produce an operation."""
        graph = build_graph(parser, "tool")
        node = next(n for n in graph.nodes if n.name == "bare")
        tool_ops = [op for op in node.operations if op.type == "tool"]
        assert len(tool_ops) == 1
        assert tool_ops[0].outputs == []

    def test_verify_operation(self, parser):
        graph = build_graph(parser, "governance")
        node = next(n for n in graph.nodes if n.name == "verify_node")
        ops = [op for op in node.operations if op.type == "verify"]
        assert len(ops) == 1

    def test_aggregate_operation(self, parser):
        graph = build_graph(parser, "governance")
        node = next(n for n in graph.nodes if n.name == "aggregate_node")
        ops = [op for op in node.operations if op.type == "aggregate"]
        assert len(ops) == 1
        assert ops[0].params["strategy"] == "majority"

    def test_gate_operation(self, parser):
        graph = build_graph(parser, "governance")
        node = next(n for n in graph.nodes if n.name == "gate_simple")
        ops = [op for op in node.operations if op.type == "gate"]
        assert len(ops) == 1

    def test_gate_nested_aggregate(self, parser):
        """gate(aggregate(...)) should flatten into aggregate + gate operations."""
        graph = build_graph(parser, "governance")
        node = next(n for n in graph.nodes if n.name == "gate_nested")
        types = [op.type for op in node.operations]
        assert "aggregate" in types
        assert "gate" in types
        agg_idx = types.index("aggregate")
        gate_idx = types.index("gate")
        assert agg_idx < gate_idx
        # Gate's input should reference the aggregate's synthetic output
        gate_op = node.operations[gate_idx]
        agg_op = node.operations[agg_idx]
        assert gate_op.inputs[0] == agg_op.outputs[0].name

    def test_decide_operation(self, parser):
        graph = build_graph(parser, "decide_session")
        node = next(n for n in graph.nodes if n.name == "decide_node")
        ops = [op for op in node.operations if op.type == "decide"]
        assert len(ops) == 1
        assert ops[0].params["provider"] == "human_reviewer"

    def test_session_operation(self, parser):
        graph = build_graph(parser, "decide_session")
        node = next(n for n in graph.nodes if n.name == "session_node")
        ops = [op for op in node.operations if op.type == "session"]
        assert len(ops) == 1

    def test_transform_operation(self, parser):
        graph = build_graph(parser, "transform")
        node = next(n for n in graph.nodes if n.name == "with_via")
        ops = [op for op in node.operations if op.type == "transform"]
        assert len(ops) == 1
        assert "Claim[]" in ops[0].params.get("target_type", "")
        assert ops[0].params.get("via") == "extract_claims"

    def test_transform_func_operation(self, parser):
        graph = build_graph(parser, "transform")
        node = next(n for n in graph.nodes if n.name == "with_func")
        ops = [op for op in node.operations if op.type == "transform"]
        assert len(ops) == 1
        assert ops[0].params.get("target_type") == "Features"
        assert ops[0].params.get("via_func") == "extract_features"
        assert "via" not in ops[0].params

    def test_map_operation(self, parser):
        graph = build_graph(parser, "map")
        node = next(n for n in graph.nodes if n.name == "process")
        ops = [op for op in node.operations if op.type == "map"]
        assert len(ops) == 1
        assert ops[0].params["workflow"] == "Inner"
        assert ops[0].inputs == ["items"]
        assert "concurrency" not in ops[0].params
        assert "on_error" not in ops[0].params

    def test_map_operation_with_modifiers(self, parser):
        graph = build_graph(parser, "map")
        node = next(n for n in graph.nodes if n.name == "process_with_opts")
        ops = [op for op in node.operations if op.type == "map"]
        assert len(ops) == 1
        assert ops[0].params["workflow"] == "Inner"
        assert ops[0].params["concurrency"] == 10
        assert ops[0].params["on_error"] == "skip"

    def test_return_operation(self, parser):
        graph = build_graph(parser, "basic")
        start = next(n for n in graph.nodes if n.name == "start")
        ret_ops = [op for op in start.operations if op.type == "return"]
        assert len(ret_ops) == 1


# ---------------------------------------------------------------------------
# Edges and routing
# ---------------------------------------------------------------------------

class TestEdges:

    def test_unconditional_edge(self, parser):
        graph = build_graph(parser, "transition")
        start = next(n for n in graph.nodes if n.name == "start")
        assert len(start.edges) == 1
        assert start.edges[0].target == "publish"
        assert start.edges[0].condition is None

    def test_route_edges_with_conditions(self, parser):
        graph = build_graph(parser, "route")
        node = next(n for n in graph.nodes if n.name == "outcome_route")
        assert len(node.edges) == 4
        conditions = {e.condition.value for e in node.edges if e.condition}
        assert "PROCEED" in conditions
        assert "HALT" in conditions

    def test_route_variable(self, parser):
        graph = build_graph(parser, "route")
        node = next(n for n in graph.nodes if n.name == "outcome_route")
        assert node.route_variable == "outcome"

    def test_dotted_route_variable(self, parser):
        graph = build_graph(parser, "route")
        node = next(n for n in graph.nodes if n.name == "dotted_route")
        assert node.route_variable == "result.consensus"

    def test_else_condition(self, parser):
        graph = build_graph(parser, "route")
        node = next(n for n in graph.nodes if n.name == "else_route")
        else_edges = [e for e in node.edges if e.condition and e.condition.kind == "else"]
        assert len(else_edges) == 1

    def test_bool_condition(self, parser):
        graph = build_graph(parser, "route")
        node = next(n for n in graph.nodes if n.name == "bool_route")
        bool_edges = [e for e in node.edges if e.condition and e.condition.kind == "bool"]
        assert len(bool_edges) == 2

    def test_inline_return_mixed_terminal(self, parser):
        """Node with inline return in route is terminal AND has edges."""
        graph = build_graph(parser, "route")
        node = next(n for n in graph.nodes if n.name == "inline_return_route")
        assert node.terminal is True
        assert len(node.edges) >= 1  # at least PROCEED -> publish


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestSerialization:

    def test_serialization_structure(self, parser):
        data = build_and_serialize(parser, "basic")
        assert data["air_graph_version"] == "0.2"
        assert data["workflow"] == "W"
        assert data["entry"] == "start"
        assert "start" in data["nodes"]

    def test_serialized_node_has_operations(self, parser):
        data = build_and_serialize(parser, "basic")
        node = data["nodes"]["start"]
        assert "operations" in node
        assert "terminal" in node
        assert node["terminal"] is True

    def test_serialized_edges(self, parser):
        data = build_and_serialize(parser, "route")
        node = data["nodes"]["outcome_route"]
        assert "edges" in node
        assert len(node["edges"]) == 4

    def test_serialized_condition(self, parser):
        data = build_and_serialize(parser, "route")
        node = data["nodes"]["outcome_route"]
        conditions = [e["condition"] for e in node["edges"] if "condition" in e]
        kinds = {c["kind"] for c in conditions}
        assert "enum" in kinds


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestSchemaValidation:

    @pytest.mark.parametrize("fixture", [
        "basic",
        "transition",
        "llm",
        "tool",
        "transform",
        "governance",
        "decide_session",
        "route",
        "parallel",
        "return_fields",
        "list_assignment",
        "map",
    ])
    def test_fixture_validates(self, parser, fixture):
        data = build_and_serialize(parser, fixture)
        validate_air_graph(data)  # should not raise
