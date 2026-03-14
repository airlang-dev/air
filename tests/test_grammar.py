"""Tests for the AIR Lark grammar.

Each test parses a minimal snippet exercising one grammar construct,
then checks the resulting parse tree structure.
"""

from pathlib import Path

import pytest
from lark import Lark, Tree, UnexpectedInput

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples" / "v0.2"


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
        src = """
@air 0.2

workflow W -> Artifact:
    node start:
        return Artifact(status="ok")
"""
        tree = parse(parser, src)
        vd = find_rule(tree, "version_decl")
        assert vd is not None
        assert find_rule(tree, "mode_decl") is None

    def test_strict_mode(self, parser):
        src = """
@air 0.2 [mode=strict]

workflow W -> Artifact:
    node start:
        return Artifact(status="ok")
"""
        tree = parse(parser, src)
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
        src = """
@air 0.2

workflow Check(content: Message, flag: bool) -> Artifact | Fault:
    node start:
        return Artifact(status="ok")
"""
        tree = parse(parser, src)
        wp = find_rule(tree, "workflow_params")
        assert wp is not None
        params = find_all_rules(tree, "param")
        assert len(params) == 2

    def test_without_params(self, parser):
        src = """
@air 0.2

workflow DailyReport -> Artifact:
    node start:
        return Artifact(status="ok")
"""
        tree = parse(parser, src)
        assert find_rule(tree, "workflow_params") is None

    def test_union_return_type(self, parser):
        src = """
@air 0.2

workflow W -> Artifact | Fault:
    node start:
        return Artifact(status="ok")
"""
        tree = parse(parser, src)
        rt = find_rule(tree, "return_type")
        types = find_all_rules(rt, "type_name")
        assert len(types) == 2


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

class TestNodes:

    def test_basic_node(self, parser):
        src = """
@air 0.2

workflow W -> Artifact:
    node start:
        return Artifact(status="ok")
"""
        tree = parse(parser, src)
        nd = find_rule(tree, "node_decl")
        assert nd is not None

    def test_node_with_params(self, parser):
        src = """
@air 0.2

workflow W -> Artifact:
    node publish(summary, outcome):
        return Artifact(status="ok")
"""
        tree = parse(parser, src)
        np = find_rule(tree, "node_params")
        assert np is not None

    def test_node_max_modifier(self, parser):
        src = """
@air 0.2

workflow W -> Artifact:
    node retry [max=5]:
        return Artifact(status="ok")
"""
        tree = parse(parser, src)
        assert find_rule(tree, "max_modifier") is not None

    def test_node_fallback_modifier(self, parser):
        src = """
@air 0.2

workflow W -> Artifact | Fault:
    node start:
        return Artifact(status="ok")

    node recovery [fallback]:
        return Fault(reason="failed")
"""
        tree = parse(parser, src)
        assert find_rule(tree, "fallback_modifier") is not None

    def test_node_params_and_max(self, parser):
        src = """
@air 0.2

workflow W -> Artifact:
    node discuss(history) [max=10]:
        return Artifact(status="ok")
"""
        tree = parse(parser, src)
        assert find_rule(tree, "node_params") is not None
        assert find_rule(tree, "max_modifier") is not None


# ---------------------------------------------------------------------------
# Instructions
# ---------------------------------------------------------------------------

class TestLlmCall:

    def test_llm_single_arg(self, parser):
        src = """
@air 0.2

workflow W -> Artifact:
    node start:
        result = llm(summarize, content)
        return Artifact(summary=result)
"""
        tree = parse(parser, src)
        assert find_rule(tree, "llm_call") is not None

    def test_llm_list_arg(self, parser):
        src = """
@air 0.2

workflow W -> Artifact:
    node start:
        result = llm(gpt, [history, r1])
        return Artifact(summary=result)
"""
        tree = parse(parser, src)
        assert find_rule(tree, "list_literal") is not None


class TestToolCall:

    def test_tool(self, parser):
        src = """
@air 0.2

workflow W -> Artifact | Fault:
    node start:
        docs = tool(fetch_docs, product_id)
        return Artifact(data=docs)
"""
        tree = parse(parser, src)
        assert find_rule(tree, "tool_call") is not None

    def test_bare_tool_call(self, parser):
        """Bare tool(...) parses as node_call at grammar level;
        the AST builder disambiguates by keyword name."""
        src = """
@air 0.2

workflow W -> Artifact | Fault:
    node start:
        tool(notify_ops, Fault.reason)
        return Fault(reason="failed")
"""
        tree = parse(parser, src)
        # Parses as node_call since "tool" is a valid IDENTIFIER
        assert find_rule(tree, "node_call") is not None


class TestTransform:

    def test_transform_with_via(self, parser):
        src = """
@air 0.2

workflow W -> Artifact:
    node start:
        claims = transform(summary) as Claim[] via llm(extract_claims)
        return Artifact(data=claims)
"""
        tree = parse(parser, src)
        te = find_rule(tree, "transform_expr")
        assert te is not None
        assert find_rule(te, "llm_call") is not None
        assert find_rule(te, "array_suffix") is not None

    def test_transform_without_via(self, parser):
        src = """
@air 0.2

workflow W -> Artifact:
    node start:
        numbers = transform(text) as Number[]
        return Artifact(data=numbers)
"""
        tree = parse(parser, src)
        te = find_rule(tree, "transform_expr")
        assert te is not None
        # No llm_call child in the transform
        assert find_rule(te, "llm_call") is None


class TestVerify:

    def test_verify(self, parser):
        src = """
@air 0.2

workflow W -> Artifact:
    node start:
        v1 = verify(claims, product_existence)
        return Artifact(v=v1)
"""
        tree = parse(parser, src)
        assert find_rule(tree, "verify_call") is not None


class TestAggregate:

    def test_aggregate(self, parser):
        src = """
@air 0.2

workflow W -> Artifact:
    node start:
        c = aggregate([v1, v2, v3], majority)
        return Artifact(c=c)
"""
        tree = parse(parser, src)
        assert find_rule(tree, "aggregate_call") is not None
        assert find_rule(tree, "list_literal") is not None


class TestGate:

    def test_gate_simple(self, parser):
        src = """
@air 0.2

workflow W -> Artifact:
    node start:
        outcome = gate(consensus)
        return Artifact(o=outcome)
"""
        tree = parse(parser, src)
        assert find_rule(tree, "gate_call") is not None

    def test_gate_nested_aggregate(self, parser):
        src = """
@air 0.2

workflow W -> Artifact:
    node start:
        outcome = gate(aggregate([v1, v2], majority))
        return Artifact(o=outcome)
"""
        tree = parse(parser, src)
        gc = find_rule(tree, "gate_call")
        assert find_rule(gc, "aggregate_call") is not None


class TestDecide:

    def test_decide(self, parser):
        src = """
@air 0.2

workflow W -> Artifact | Fault:
    node start:
        msg, outcome = decide(human_reviewer, summary)
        return Artifact(status="ok")
"""
        tree = parse(parser, src)
        assert find_rule(tree, "decide_call") is not None
        lv = find_rule(tree, "lvalue")
        assert len(lv.children) == 2  # msg, outcome

    def test_decide_discard_message(self, parser):
        src = """
@air 0.2

workflow W -> Artifact | Fault:
    node start:
        _, outcome = decide(risk_policy, claims)
        return Artifact(status="ok")
"""
        tree = parse(parser, src)
        assert find_rule(tree, "decide_call") is not None


class TestSession:

    def test_session(self, parser):
        src = """
@air 0.2

workflow W(members: Participants, protocol: Protocol) -> Artifact:
    node start:
        result = session(members, protocol, history)
        return Artifact(data=result)
"""
        tree = parse(parser, src)
        assert find_rule(tree, "session_call") is not None


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

class TestRoute:

    def test_outcome_route(self, parser):
        src = """
@air 0.2

workflow W -> Artifact | Fault:
    node start:
        outcome = gate(verdict)

        route outcome:
            PROCEED: publish
            ESCALATE: abort
            RETRY: start
            HALT: abort

    node publish:
        return Artifact(status="ok")

    node abort:
        return Fault(reason="failed")
"""
        tree = parse(parser, src)
        cases = find_all_rules(tree, "route_case")
        assert len(cases) == 4

    def test_else_pattern(self, parser):
        src = """
@air 0.2

workflow W -> Artifact | Fault:
    node start:
        claims = transform(x) as Claim[] via llm(extract)

        route claims:
            Fault: start
            else: done

    node done:
        return Artifact(status="ok")
"""
        tree = parse(parser, src)
        assert find_rule(tree, "else_pattern") is not None

    def test_true_false_patterns(self, parser):
        src = """
@air 0.2

workflow W -> Artifact:
    node start:
        done = transform(x) as bool via llm(check)

        route done:
            true: publish
            false: start

    node publish:
        return Artifact(status="ok")
"""
        tree = parse(parser, src)
        assert find_rule(tree, "true_pattern") is not None
        assert find_rule(tree, "false_pattern") is not None

    def test_route_dotted_name(self, parser):
        src = """
@air 0.2

workflow W -> Artifact | Fault:
    node start:
        result = session(members, protocol, history)

        route result.consensus:
            PROCEED: done
            HALT: abort

    node done:
        return Artifact(status="ok")

    node abort:
        return Fault(reason="failed")
"""
        tree = parse(parser, src)
        rv = find_rule(tree, "route_value")
        assert find_rule(rv, "dotted_name") is not None

    def test_route_target_with_args(self, parser):
        src = """
@air 0.2

workflow W -> Artifact | Fault:
    node start:
        outcome = gate(verdict)

        route outcome:
            PROCEED: publish(summary, outcome)
            HALT: abort

    node publish(summary, outcome):
        return Artifact(status="ok")

    node abort:
        return Fault(reason="failed")
"""
        tree = parse(parser, src)
        nc = find_rule(tree, "node_call")
        assert nc is not None

    def test_route_target_inline_return(self, parser):
        src = """
@air 0.2

workflow W -> Artifact | Fault:
    node start:
        msg, outcome = decide(reviewer, data)

        route outcome:
            PROCEED: done
            HALT: return Fault(reason="rejected")

    node done:
        return Artifact(status="ok")
"""
        tree = parse(parser, src)
        rs = find_all_rules(tree, "return_stmt")
        assert len(rs) == 2  # one in route target, one in done node


# ---------------------------------------------------------------------------
# Unconditional transition (node call as statement)
# ---------------------------------------------------------------------------

class TestNodeCallStatement:

    def test_unconditional_transition(self, parser):
        src = """
@air 0.2

workflow W -> Artifact:
    node start:
        summary = llm(summarize, content)
        publish(summary)

    node publish(summary):
        return Artifact(summary=summary)
"""
        tree = parse(parser, src)
        nc = find_rule(tree, "node_call")
        assert nc is not None


# ---------------------------------------------------------------------------
# Parallel
# ---------------------------------------------------------------------------

class TestParallel:

    def test_parallel_strict(self, parser):
        src = """
@air 0.2

workflow W -> Artifact:
    node start:
        parallel:
            v1 = verify(claims, rule1)
            v2 = verify(claims, rule2)
        return Artifact(status="ok")
"""
        tree = parse(parser, src)
        pb = find_rule(tree, "parallel_block")
        assert pb is not None
        assert find_rule(pb, "parallel_modifier") is None

    def test_parallel_partial(self, parser):
        src = """
@air 0.2

workflow W -> Artifact | Fault:
    node start:
        parallel [partial]:
            docs = tool(fetch_docs, id)
            refs = tool(fetch_refs, id)
        return Artifact(status="ok")
"""
        tree = parse(parser, src)
        assert find_rule(tree, "parallel_modifier") is not None


# ---------------------------------------------------------------------------
# Return & constructors
# ---------------------------------------------------------------------------

class TestReturn:

    def test_return_artifact(self, parser):
        src = """
@air 0.2

workflow W -> Artifact:
    node start:
        return Artifact(status="verified", summary=summary)
"""
        tree = parse(parser, src)
        c = find_rule(tree, "constructor")
        fields = find_all_rules(c, "field")
        assert len(fields) == 2

    def test_return_fault(self, parser):
        src = """
@air 0.2

workflow W -> Fault:
    node start:
        return Fault(reason="failed")
"""
        tree = parse(parser, src)
        assert find_rule(tree, "constructor") is not None


# ---------------------------------------------------------------------------
# List literals & assignment
# ---------------------------------------------------------------------------

class TestListLiteral:

    def test_list_assignment(self, parser):
        src = """
@air 0.2

workflow W -> Artifact:
    node start:
        updated = [history, r1, r2, r3]
        return Artifact(data=updated)
"""
        tree = parse(parser, src)
        ll = find_rule(tree, "list_literal")
        assert ll is not None


# ---------------------------------------------------------------------------
# Dotted names
# ---------------------------------------------------------------------------

class TestDottedName:

    def test_dotted_in_arg(self, parser):
        src = """
@air 0.2

workflow W -> Fault:
    node start:
        tool(notify, Fault.reason)
        return Fault(reason=Fault.reason)
"""
        tree = parse(parser, src)
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
        # "default" is just an identifier at grammar level
        assert find_rule(tree, "name_pattern") is not None
