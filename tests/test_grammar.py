"""Tests for the AIR Lark grammar.

Tests parse .air fixtures and check parse tree structure.
Negative tests (reject invalid syntax) use inline snippets.
"""

import pytest
from lark import Lark, Tree, UnexpectedInput

from helpers import load_fixture, EXAMPLES_DIR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse(parser: Lark, src: str) -> Tree:
    return parser.parse(src)


def find_rule(tree: Tree, rule: str) -> Tree | None:
    """Return first subtree matching *rule*, or None."""
    for sub in tree.iter_subtrees():
        if sub.data == rule:
            return sub
    return None


def find_all_rules(tree: Tree, rule: str) -> list[Tree]:
    return [sub for sub in tree.iter_subtrees() if sub.data == rule]


# ---------------------------------------------------------------------------
# Example files
# ---------------------------------------------------------------------------

class TestExampleFiles:
    """All v0.2 example .air files parse without error."""

    @pytest.mark.parametrize("filename", [
        "FactCheckedPublish.air",
        "MultiModelChat.air",
        "KitchenSink.air",
    ])
    def test_example_parses(self, parser, filename):
        src = (EXAMPLES_DIR / filename).read_text()
        tree = parse(parser, src)
        assert tree.data == "start"


# ---------------------------------------------------------------------------
# Version declaration
# ---------------------------------------------------------------------------

class TestVersionDecl:

    def test_basic_version(self, parser):
        tree = parse(parser, load_fixture("basic"))
        vd = find_rule(tree, "version_decl")
        assert vd is not None
        assert find_rule(tree, "mode_decl") is None

    def test_strict_mode(self, parser):
        tree = parse(parser, load_fixture("basic_strict"))
        md = find_rule(tree, "mode_decl")
        assert md is not None

    def test_normal_mode(self, parser):
        src = """
@air 0.2 [mode=normal]

workflow W -> Artifact:
    node start:
        return Artifact(status="ok")
"""
        tree = parse(parser, src)
        assert find_rule(tree, "mode_decl") is not None


# ---------------------------------------------------------------------------
# Workflow declaration
# ---------------------------------------------------------------------------

class TestWorkflowDecl:

    def test_with_params(self, parser):
        tree = parse(parser, load_fixture("workflow_params"))
        wp = find_rule(tree, "workflow_params")
        assert wp is not None
        params = find_all_rules(tree, "param")
        assert len(params) == 2

    def test_without_params(self, parser):
        tree = parse(parser, load_fixture("workflow_no_params"))
        assert find_rule(tree, "workflow_params") is None

    def test_union_return_type(self, parser):
        tree = parse(parser, load_fixture("workflow_params"))
        rt = find_rule(tree, "return_type")
        types = find_all_rules(rt, "type_name")
        assert len(types) == 2


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

class TestNodes:

    def test_basic_node(self, parser):
        tree = parse(parser, load_fixture("basic"))
        assert find_rule(tree, "node_decl") is not None

    def test_node_with_params(self, parser):
        tree = parse(parser, load_fixture("nodes"))
        assert find_rule(tree, "node_params") is not None

    def test_node_max_modifier(self, parser):
        tree = parse(parser, load_fixture("nodes"))
        assert find_rule(tree, "max_modifier") is not None

    def test_node_fallback_modifier(self, parser):
        tree = parse(parser, load_fixture("nodes"))
        assert find_rule(tree, "fallback_modifier") is not None

    def test_node_params_and_max(self, parser):
        tree = parse(parser, load_fixture("nodes"))
        # discuss(history) [max=10] has both
        assert find_rule(tree, "node_params") is not None
        assert find_rule(tree, "max_modifier") is not None


# ---------------------------------------------------------------------------
# Instructions
# ---------------------------------------------------------------------------

class TestLlmCall:

    def test_llm_call(self, parser):
        tree = parse(parser, load_fixture("llm"))
        assert find_rule(tree, "llm_call") is not None

    def test_llm_list_arg(self, parser):
        tree = parse(parser, load_fixture("llm"))
        assert find_rule(tree, "list_literal") is not None


class TestToolCall:

    def test_tool(self, parser):
        tree = parse(parser, load_fixture("tool"))
        assert find_rule(tree, "tool_call") is not None

    def test_bare_tool_call(self, parser):
        """Bare tool(...) parses as tool_call at grammar level."""
        tree = parse(parser, load_fixture("tool"))
        tool_calls = find_all_rules(tree, "tool_call")
        assert len(tool_calls) >= 2  # assigned + bare


class TestTransform:

    def test_transform_with_via(self, parser):
        tree = parse(parser, load_fixture("transform"))
        te = find_rule(tree, "transform_expr")
        assert te is not None
        assert find_rule(te, "llm_call") is not None
        assert find_rule(te, "array_suffix") is not None

    def test_transform_without_via(self, parser):
        tree = parse(parser, load_fixture("transform"))
        transforms = find_all_rules(tree, "transform_expr")
        # Second transform (without_via node) has no llm_call
        without_via = transforms[1]
        assert find_rule(without_via, "llm_call") is None


class TestVerify:

    def test_verify(self, parser):
        tree = parse(parser, load_fixture("governance"))
        assert find_rule(tree, "verify_call") is not None


class TestAggregate:

    def test_aggregate(self, parser):
        tree = parse(parser, load_fixture("governance"))
        assert find_rule(tree, "aggregate_call") is not None
        assert find_rule(tree, "list_literal") is not None


class TestGate:

    def test_gate_simple(self, parser):
        tree = parse(parser, load_fixture("governance"))
        assert find_rule(tree, "gate_call") is not None

    def test_gate_nested_aggregate(self, parser):
        tree = parse(parser, load_fixture("governance"))
        gates = find_all_rules(tree, "gate_call")
        # gate_nested has aggregate inside
        nested = [g for g in gates if find_rule(g, "aggregate_call")]
        assert len(nested) == 1


class TestDecide:

    def test_decide(self, parser):
        tree = parse(parser, load_fixture("decide_session"))
        assert find_rule(tree, "decide_call") is not None

    def test_decide_multi_lvalue(self, parser):
        tree = parse(parser, load_fixture("decide_session"))
        lv = find_rule(tree, "lvalue")
        assert len(lv.children) == 2


class TestSession:

    def test_session(self, parser):
        tree = parse(parser, load_fixture("decide_session"))
        assert find_rule(tree, "session_call") is not None


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

class TestRoute:

    def test_outcome_route(self, parser):
        tree = parse(parser, load_fixture("route"))
        cases = find_all_rules(tree, "route_case")
        assert len(cases) >= 4

    def test_else_pattern(self, parser):
        tree = parse(parser, load_fixture("route"))
        assert find_rule(tree, "else_pattern") is not None

    def test_true_false_patterns(self, parser):
        tree = parse(parser, load_fixture("route"))
        assert find_rule(tree, "true_pattern") is not None
        assert find_rule(tree, "false_pattern") is not None

    def test_route_dotted_name(self, parser):
        tree = parse(parser, load_fixture("route"))
        rv = find_all_rules(tree, "route_value")
        dotted = [r for r in rv if find_rule(r, "dotted_name")]
        assert len(dotted) >= 1

    def test_route_target_with_args(self, parser):
        tree = parse(parser, load_fixture("route"))
        assert find_rule(tree, "node_call") is not None

    def test_route_target_inline_return(self, parser):
        tree = parse(parser, load_fixture("route"))
        # At least one return_stmt inside a route_target
        route_targets = find_all_rules(tree, "route_target")
        returns_in_routes = [t for t in route_targets if find_rule(t, "return_stmt")]
        assert len(returns_in_routes) >= 1


# ---------------------------------------------------------------------------
# Unconditional transition (node call as statement)
# ---------------------------------------------------------------------------

class TestNodeCallStatement:

    def test_unconditional_transition(self, parser):
        tree = parse(parser, load_fixture("transition"))
        assert find_rule(tree, "node_call") is not None


# ---------------------------------------------------------------------------
# Parallel
# ---------------------------------------------------------------------------

class TestParallel:

    def test_parallel_strict(self, parser):
        tree = parse(parser, load_fixture("parallel"))
        pb = find_rule(tree, "parallel_block")
        assert pb is not None

    def test_parallel_partial(self, parser):
        tree = parse(parser, load_fixture("parallel"))
        assert find_rule(tree, "parallel_modifier") is not None


# ---------------------------------------------------------------------------
# Return & constructors
# ---------------------------------------------------------------------------

class TestReturn:

    def test_return_with_fields(self, parser):
        tree = parse(parser, load_fixture("return_fields"))
        c = find_rule(tree, "constructor")
        fields = find_all_rules(c, "field")
        assert len(fields) == 2


# ---------------------------------------------------------------------------
# List literals & assignment
# ---------------------------------------------------------------------------

class TestListLiteral:

    def test_list_assignment(self, parser):
        tree = parse(parser, load_fixture("list_assignment"))
        assert find_rule(tree, "list_literal") is not None


# ---------------------------------------------------------------------------
# Dotted names
# ---------------------------------------------------------------------------

class TestDottedName:

    def test_dotted_in_arg(self, parser):
        tree = parse(parser, load_fixture("tool"))
        # bare node has tool(notify_ops, Fault.reason)
        dns = find_all_rules(tree, "dotted_name")
        assert len(dns) >= 1


# ---------------------------------------------------------------------------
# Multiple workflows
# ---------------------------------------------------------------------------

class TestMultipleWorkflows:

    def test_two_workflows(self, parser):
        src = """
@air 0.2

workflow A -> Artifact:
    node start:
        return Artifact(status="a")

workflow B -> Artifact:
    node start:
        return Artifact(status="b")
"""
        tree = parse(parser, src)
        wds = find_all_rules(tree, "workflow_decl")
        assert len(wds) == 2


# ---------------------------------------------------------------------------
# Negative tests — things that should NOT parse
# ---------------------------------------------------------------------------

class TestRejectInvalid:

    def test_reject_v01_bare_label(self, parser):
        """v0.1 bare labels should not parse in v0.2."""
        src = """
@air 0.2

workflow W -> Artifact:
    start:
        return Artifact(status="ok")
"""
        with pytest.raises(UnexpectedInput):
            parse(parser, src)

    def test_reject_v01_fault_handler(self, parser):
        """v0.1 fault_handler {} should not parse in v0.2."""
        src = """
@air 0.2

workflow W -> Artifact | Fault:
    fault_handler {
        return Fault(reason="failed")
    }

    node start:
        return Artifact(status="ok")
"""
        with pytest.raises(UnexpectedInput):
            parse(parser, src)

    def test_reject_v01_loop(self, parser):
        """v0.1 loop blocks should not parse in v0.2."""
        src = """
@air 0.2

workflow W -> Artifact:
    node start:
        loop retry [max=3] {
            x = llm(prompt, data)
        }
        return Artifact(status="ok")
"""
        with pytest.raises(UnexpectedInput):
            parse(parser, src)

    def test_reject_v01_route_syntax(self, parser):
        """v0.1 route(x) { } syntax should not parse in v0.2."""
        src = """
@air 0.2

workflow W -> Artifact | Fault:
    node start:
        outcome = gate(verdict)

        route(outcome) {
            PROCEED -> publish
            HALT -> abort
        }

    node publish:
        return Artifact(status="ok")

    node abort:
        return Fault(reason="failed")
"""
        with pytest.raises(UnexpectedInput):
            parse(parser, src)

    def test_default_parses_as_name_pattern(self, parser):
        """'default' is not a keyword in v0.2 — it parses as a name_pattern.
        The semantic checker would reject it if it doesn't match a valid case."""
        src = """
@air 0.2

workflow W -> Artifact | Fault:
    node start:
        x = tool(fetch, id)

        route x:
            Fault: abort
            default: done

    node done:
        return Artifact(status="ok")

    node abort:
        return Fault(reason="failed")
"""
        tree = parse(parser, src)
        assert find_rule(tree, "name_pattern") is not None
