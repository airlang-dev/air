"""Tests for the AST builder (Lark parse tree -> AIR AST)."""

import pytest

from air_ast import (
    Aggregate, Assign, BoolPattern, Constructor, Decide, DottedName,
    ElsePattern, EnumPattern, Gate, Identifier, LLMCall, ListLiteral,
    Node, NodeCall, Parallel, Param, Program, Return, Route, RouteCase,
    Session, ToolCall, Transform, Type, TypePattern, Unreachable, Verify,
)
from ast_builder import ASTBuilder
from helpers import load_fixture, build_fixture, find_node, EXAMPLES_DIR


def build(parser, src: str) -> Program:
    tree = parser.parse(src)
    return ASTBuilder().build(tree)


# ---------------------------------------------------------------------------
# Example files — smoke test
# ---------------------------------------------------------------------------

class TestExampleFiles:

    @pytest.mark.parametrize("filename", [
        "FactCheckedPublish.air",
        "MultiModelChat.air",
        "KitchenSink.air",
    ])
    def test_example_builds(self, parser, filename):
        src = (EXAMPLES_DIR / filename).read_text()
        program = build(parser, src)
        assert len(program.workflows) >= 1


# ---------------------------------------------------------------------------
# Program-level
# ---------------------------------------------------------------------------

class TestProgram:

    def test_version_and_mode(self, parser):
        p = build_fixture(parser, "basic_strict")
        assert p.version == "0.2"
        assert p.mode == "strict"

    def test_version_no_mode(self, parser):
        p = build_fixture(parser, "basic")
        assert p.version == "0.2"
        assert p.mode is None


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------

class TestWorkflow:

    def test_workflow_params(self, parser):
        p = build_fixture(parser, "workflow_params")
        w = p.workflows[0]
        assert w.name == "Check"
        assert w.params == [
            Param("content", Type("Message")),
            Param("tags", Type("Claim", is_list=True)),
        ]
        assert w.return_types == [Type("Artifact"), Type("Fault")]

    def test_workflow_no_params(self, parser):
        p = build_fixture(parser, "workflow_no_params")
        w = p.workflows[0]
        assert w.name == "DailyReport"
        assert w.params == []


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

class TestNodes:

    def test_basic_node(self, parser):
        p = build_fixture(parser, "nodes")
        n = find_node(p, "start")
        assert n.params == []
        assert n.max_visits is None
        assert n.is_fallback is False

    def test_node_with_params(self, parser):
        n = find_node(build_fixture(parser, "nodes"), "publish")
        assert n.params == ["summary", "outcome"]

    def test_node_max(self, parser):
        n = find_node(build_fixture(parser, "nodes"), "retry")
        assert n.max_visits == 5

    def test_node_fallback(self, parser):
        n = find_node(build_fixture(parser, "nodes"), "recovery")
        assert n.is_fallback is True

    def test_node_params_and_max(self, parser):
        n = find_node(build_fixture(parser, "nodes"), "discuss")
        assert n.params == ["history"]
        assert n.max_visits == 10


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

class TestLLM:

    def test_llm_two_args(self, parser):
        n = find_node(build_fixture(parser, "llm"), "two_args")
        assign = n.body[0]
        assert isinstance(assign, Assign)
        llm = assign.value
        assert isinstance(llm, LLMCall)
        assert llm.prompt == "summarize"
        assert llm.args == [Identifier("content")]

    def test_llm_list_arg(self, parser):
        n = find_node(build_fixture(parser, "llm"), "list_arg")
        llm = n.body[0].value
        assert isinstance(llm.args[0], ListLiteral)
        assert llm.args[0].items == [Identifier("history"), Identifier("r1")]


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

class TestTool:

    def test_tool_call(self, parser):
        n = find_node(build_fixture(parser, "tool"), "assigned")
        tc = n.body[0].value
        assert isinstance(tc, ToolCall)
        assert tc.name == "fetch_docs"
        assert tc.args == [Identifier("product_id")]


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------

class TestTransform:

    def test_transform_with_via(self, parser):
        n = find_node(build_fixture(parser, "transform"), "with_via")
        t = n.body[0].value
        assert isinstance(t, Transform)
        assert t.input == Identifier("summary")
        assert t.target_type == Type("Claim", is_list=True)
        assert isinstance(t.via, LLMCall)
        assert t.via.prompt == "extract_claims"

    def test_transform_without_via(self, parser):
        n = find_node(build_fixture(parser, "transform"), "without_via")
        t = n.body[0].value
        assert isinstance(t, Transform)
        assert t.via is None


# ---------------------------------------------------------------------------
# Verify, Aggregate, Gate
# ---------------------------------------------------------------------------

class TestGovernance:

    def test_verify(self, parser):
        n = find_node(build_fixture(parser, "governance"), "verify_node")
        v = n.body[0].value
        assert isinstance(v, Verify)
        assert v.input == Identifier("claims")
        assert v.rule == Identifier("product_existence")

    def test_aggregate(self, parser):
        n = find_node(build_fixture(parser, "governance"), "aggregate_node")
        a = n.body[0].value
        assert isinstance(a, Aggregate)
        assert a.inputs == [Identifier("v1"), Identifier("v2"), Identifier("v3")]
        assert a.strategy == "majority"

    def test_gate_simple(self, parser):
        n = find_node(build_fixture(parser, "governance"), "gate_simple")
        g = n.body[0].value
        assert isinstance(g, Gate)
        assert isinstance(g.input, Identifier)

    def test_gate_nested(self, parser):
        n = find_node(build_fixture(parser, "governance"), "gate_nested")
        g = n.body[0].value
        assert isinstance(g, Gate)
        assert isinstance(g.input, Aggregate)


# ---------------------------------------------------------------------------
# Decide, Session
# ---------------------------------------------------------------------------

class TestDecideSession:

    def test_decide(self, parser):
        n = find_node(build_fixture(parser, "decide_session"), "decide_node")
        assign = n.body[0]
        assert assign.targets == ["msg", "outcome"]
        d = assign.value
        assert isinstance(d, Decide)
        assert d.provider == "human_reviewer"
        assert d.args == [Identifier("summary")]

    def test_decide_discard(self, parser):
        n = find_node(build_fixture(parser, "decide_session"), "decide_discard")
        assign = n.body[0]
        assert assign.targets == ["_", "outcome"]

    def test_session(self, parser):
        n = find_node(build_fixture(parser, "decide_session"), "session_node")
        s = n.body[0].value
        assert isinstance(s, Session)
        assert s.args == [
            Identifier("members"),
            Identifier("protocol"),
            Identifier("history"),
        ]


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

class TestRoute:

    def test_outcome_route(self, parser):
        n = find_node(build_fixture(parser, "route"), "outcome_route")
        route = n.body[1]
        assert isinstance(route, Route)
        assert route.value == Identifier("outcome")
        assert len(route.cases) == 4
        assert route.cases[0] == RouteCase(EnumPattern("PROCEED"), "publish")
        assert route.cases[3] == RouteCase(EnumPattern("HALT"), "abort")

    def test_else_pattern(self, parser):
        n = find_node(build_fixture(parser, "route"), "else_route")
        route = n.body[1]
        assert isinstance(route.cases[0].pattern, TypePattern)
        assert isinstance(route.cases[1].pattern, ElsePattern)

    def test_bool_patterns(self, parser):
        n = find_node(build_fixture(parser, "route"), "bool_route")
        route = n.body[1]
        assert isinstance(route.cases[0].pattern, BoolPattern)
        assert route.cases[0].pattern.value is True
        assert isinstance(route.cases[1].pattern, BoolPattern)
        assert route.cases[1].pattern.value is False

    def test_dotted_route_value(self, parser):
        n = find_node(build_fixture(parser, "route"), "dotted_route")
        route = n.body[1]
        assert route.value == DottedName("result", "consensus")

    def test_route_target_with_args(self, parser):
        n = find_node(build_fixture(parser, "route"), "args_route")
        route = n.body[1]
        target = route.cases[0].target
        assert isinstance(target, NodeCall)
        assert target.name == "publish"
        assert target.args == [Identifier("summary"), Identifier("outcome")]

    def test_route_inline_return(self, parser):
        n = find_node(build_fixture(parser, "route"), "inline_return_route")
        route = n.body[1]
        target = route.cases[1].target
        assert isinstance(target, Return)
        assert isinstance(target.value, Constructor)


# ---------------------------------------------------------------------------
# Node call (unconditional transition)
# ---------------------------------------------------------------------------

class TestNodeCall:

    def test_unconditional_transition(self, parser):
        n = find_node(build_fixture(parser, "transition"), "start")
        nc = n.body[1]
        assert isinstance(nc, NodeCall)
        assert nc.name == "publish"
        assert nc.args == [Identifier("summary")]


# ---------------------------------------------------------------------------
# Parallel
# ---------------------------------------------------------------------------

class TestParallel:

    def test_parallel_strict(self, parser):
        n = find_node(build_fixture(parser, "parallel"), "strict")
        p = n.body[0]
        assert isinstance(p, Parallel)
        assert p.partial is False
        assert len(p.branches) == 2

    def test_parallel_partial(self, parser):
        n = find_node(build_fixture(parser, "parallel"), "partial_node")
        p = n.body[0]
        assert isinstance(p, Parallel)
        assert p.partial is True


# ---------------------------------------------------------------------------
# Return & Constructor
# ---------------------------------------------------------------------------

class TestReturn:

    def test_return_with_fields(self, parser):
        n = find_node(build_fixture(parser, "return_fields"), "start")
        ret = n.body[0]
        assert isinstance(ret, Return)
        c = ret.value
        assert isinstance(c, Constructor)
        assert c.type_name == "Artifact"
        assert c.fields == {"status": "verified", "summary": Identifier("summary")}


# ---------------------------------------------------------------------------
# List literal as expression
# ---------------------------------------------------------------------------

class TestListExpression:

    def test_list_assignment(self, parser):
        n = find_node(build_fixture(parser, "list_assignment"), "start")
        assign = n.body[0]
        assert isinstance(assign.value, ListLiteral)
        assert len(assign.value.items) == 4


# ---------------------------------------------------------------------------
# Bare tool/llm call
# ---------------------------------------------------------------------------

class TestBareInstructionCalls:

    def test_bare_tool_becomes_tool_call(self, parser):
        """tool(...) as a bare statement should be recognized as ToolCall."""
        n = find_node(build_fixture(parser, "tool"), "bare")
        tc = n.body[0]
        assert isinstance(tc, ToolCall)
        assert tc.name == "notify_ops"
        assert tc.args == [DottedName("Fault", "reason")]
