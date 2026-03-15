"""Tests for the LangGraph backend code generator (v0.2)."""

import json
import pytest

from helpers import build_fixture
from ast_builder import ASTBuilder
from cfg_builder import build_cfg
from air_graph.builder import build_air_graph
from air_graph.serializer import serialize_air_graph
from backends.langgraph.backend import LangGraphBackend


def generate_code(parser, fixture_name: str) -> str:
    program = build_fixture(parser, fixture_name)
    w = program.workflows[0]
    cfg = build_cfg(w)
    graph = build_air_graph(cfg, w.name)
    data = serialize_air_graph(graph)
    backend = LangGraphBackend()
    return backend.generate(data)


# ---------------------------------------------------------------------------
# Basic code generation
# ---------------------------------------------------------------------------

class TestBasicGeneration:

    def test_produces_string(self, parser):
        code = generate_code(parser, "basic")
        assert isinstance(code, str)
        assert len(code) > 0

    def test_imports_present(self, parser):
        code = generate_code(parser, "basic")
        assert "from langgraph.graph import StateGraph, END" in code

    def test_adapter_imports(self, parser):
        code = generate_code(parser, "llm")
        assert "llm_adapter" in code

    def test_node_function_generated(self, parser):
        code = generate_code(parser, "basic")
        assert "def start(state):" in code

    def test_graph_builder(self, parser):
        code = generate_code(parser, "basic")
        assert "builder = StateGraph(dict)" in code
        assert 'builder.set_entry_point("start")' in code
        assert "graph = builder.compile()" in code

    def test_main_block(self, parser):
        code = generate_code(parser, "basic")
        assert 'if __name__ == "__main__":' in code


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

class TestOperations:

    def test_llm_operation(self, parser):
        code = generate_code(parser, "llm")
        assert "llm_adapter" in code

    def test_tool_operation(self, parser):
        code = generate_code(parser, "tool")
        assert "TOOL:fetch_docs" in code

    def test_bare_tool_no_output(self, parser):
        """Bare tool() without assignment should not crash."""
        code = generate_code(parser, "tool")
        assert "TOOL:notify_ops" in code

    def test_bare_llm_no_output(self, parser):
        """Bare llm() without assignment should work."""
        code = generate_code(parser, "llm")
        # The bare llm call should still invoke llm_adapter
        assert "llm_adapter" in code

    def test_verify_operation(self, parser):
        code = generate_code(parser, "governance")
        assert "verify_adapter" in code

    def test_aggregate_operation(self, parser):
        code = generate_code(parser, "governance")
        assert "aggregate_adapter" in code
        assert "majority" in code

    def test_gate_operation(self, parser):
        code = generate_code(parser, "governance")
        assert "gate_adapter" in code

    def test_decide_operation(self, parser):
        code = generate_code(parser, "decide_session")
        assert "decision_adapter" in code
        assert "human_reviewer" in code

    def test_session_operation(self, parser):
        code = generate_code(parser, "decide_session")
        assert "session_adapter" in code

    def test_transform_operation(self, parser):
        code = generate_code(parser, "transform")
        assert "transform_adapter" in code

    def test_return_operation(self, parser):
        code = generate_code(parser, "basic")
        assert "__result__" in code

    def test_return_with_input(self, parser):
        """return(variable) should reference the variable in state."""
        code = generate_code(parser, "transition")
        assert "__result__" in code

    def test_construct_operation(self, parser):
        code = generate_code(parser, "return_fields")
        assert "construct" in code.lower() or "type" in code

    def test_list_construct(self, parser):
        code = generate_code(parser, "list_assignment")
        # list construct has inputs but no type/fields params
        assert "def start(state):" in code


# ---------------------------------------------------------------------------
# Edges and routing
# ---------------------------------------------------------------------------

class TestEdges:

    def test_unconditional_edge(self, parser):
        code = generate_code(parser, "transition")
        assert 'builder.add_edge("start", "publish")' in code

    def test_terminal_node_to_end(self, parser):
        code = generate_code(parser, "basic")
        assert 'builder.add_edge("start", END)' in code

    def test_conditional_edges(self, parser):
        code = generate_code(parser, "route")
        assert "add_conditional_edges" in code

    def test_route_function_generated(self, parser):
        code = generate_code(parser, "route")
        assert "def route_outcome_route(state):" in code

    def test_enum_routing(self, parser):
        code = generate_code(parser, "route")
        # Should have enum values as routing keys
        assert "PROCEED" in code
        assert "HALT" in code

    def test_bool_routing(self, parser):
        code = generate_code(parser, "route")
        assert "def route_bool_route(state):" in code
        # Bool routes should check true/false
        assert "true" in code.lower() or "True" in code

    def test_else_routing(self, parser):
        code = generate_code(parser, "route")
        # Else conditions should produce a fallback
        assert "__else__" in code or "else" in code.lower()

    def test_dotted_route_variable(self, parser):
        code = generate_code(parser, "route")
        # Dotted variable like result.consensus should be handled
        assert "route_dotted_route" in code

    def test_mixed_terminal_and_edges(self, parser):
        """Node that is both terminal (has return) and has edges (route)."""
        code = generate_code(parser, "route")
        # inline_return_route is terminal AND has edges
        # It should still get a route function and conditional edges
        assert "route_inline_return_route" in code


# ---------------------------------------------------------------------------
# Trace logging
# ---------------------------------------------------------------------------

class TestTracing:

    def test_node_enter_trace(self, parser):
        code = generate_code(parser, "basic")
        assert "[TRACE] node.enter" in code

    def test_op_trace(self, parser):
        code = generate_code(parser, "basic")
        assert "[TRACE] op.start" in code

    def test_workflow_trace(self, parser):
        code = generate_code(parser, "basic")
        assert "[TRACE] workflow.start" in code


# ---------------------------------------------------------------------------
# All fixtures compile without error
# ---------------------------------------------------------------------------

class TestAllFixtures:

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
    ])
    def test_fixture_generates(self, parser, fixture):
        code = generate_code(parser, fixture)
        assert isinstance(code, str)
        assert "StateGraph" in code

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
    ])
    def test_fixture_is_valid_python(self, parser, fixture):
        """Generated code should be syntactically valid Python."""
        code = generate_code(parser, fixture)
        compile(code, f"<{fixture}>", "exec")
