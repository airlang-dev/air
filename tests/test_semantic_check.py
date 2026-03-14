"""Tests for the v0.2 semantic checker.

The semantic checker operates on the typed AST and validates:
1. Node name uniqueness within a workflow
2. Node names don't collide with instruction keywords
3. SSA (no variable reassignment within a node)
4. Variable existence (workflow params, node params, local assignments)
5. Route target existence (must reference valid node names)
6. Route exhaustiveness (Outcome routes need full coverage or else)
7. At most one fallback node per workflow
8. Return type validity (constructor type must be in workflow return types)
9. Every node must terminate (return, node_call, route, or unreachable)
"""

import pytest

from helpers import build_fixture
from ast_builder import ASTBuilder
from semantic_check import SemanticError, check_program


def check(parser, src: str):
    """Parse, build AST, and run semantic checks."""
    tree = parser.parse(src)
    program = ASTBuilder().build(tree)
    check_program(program)


def check_fixture(parser, name: str):
    """Run semantic checks on a fixture file."""
    program = build_fixture(parser, name)
    check_program(program)


# ---------------------------------------------------------------------------
# Valid programs — should pass all checks
# ---------------------------------------------------------------------------

class TestValidPrograms:

    @pytest.mark.parametrize("fixture", [
        "basic",
        "basic_strict",
        "workflow_params",
        "workflow_no_params",
        "nodes",
        "llm",
        "tool",
        "transform",
        "governance",
        "decide_session",
        "parallel",
        "transition",
        "return_fields",
        "list_assignment",
        "route",
    ])
    def test_fixture_passes(self, parser, fixture):
        check_fixture(parser, fixture)


# ---------------------------------------------------------------------------
# Node name uniqueness
# ---------------------------------------------------------------------------

class TestNodeNameUniqueness:

    def test_duplicate_node_names(self, parser):
        src = """
@air 0.2

workflow W -> Artifact:
    node start:
        return Artifact(status="ok")

    node start:
        return Artifact(status="ok")
"""
        with pytest.raises(SemanticError, match="Duplicate node.*start"):
            check(parser, src)


# ---------------------------------------------------------------------------
# Node names vs keywords
# ---------------------------------------------------------------------------

class TestNodeNameKeywords:

    @pytest.mark.parametrize("keyword", [
        "llm", "tool", "session", "route", "return",
        "unreachable", "parallel", "verify", "aggregate",
        "gate", "decide", "transform",
    ])
    def test_grammar_prevents_keyword_node_name(self, parser, keyword):
        """Instruction keywords can't be used as node names (grammar rejects)."""
        from lark import UnexpectedInput
        src = f"""
@air 0.2

workflow W -> Artifact:
    node {keyword}:
        return Artifact(status="ok")
"""
        with pytest.raises(UnexpectedInput):
            parser.parse(src)


# ---------------------------------------------------------------------------
# SSA violations
# ---------------------------------------------------------------------------

class TestSSA:

    def test_variable_reassigned(self, parser):
        src = """
@air 0.2

workflow W(data: Message) -> Artifact:
    node start:
        x = llm(prompt1, data)
        x = llm(prompt2, data)
        return Artifact(data=x)
"""
        with pytest.raises(SemanticError, match="SSA.*x"):
            check(parser, src)

    def test_discard_not_ssa_violation(self, parser):
        """Multiple _ assignments should be allowed."""
        src = """
@air 0.2

workflow W(data: Message) -> Artifact:
    node start:
        _, o1 = decide(provider1, data)
        _, o2 = decide(provider2, data)
        return Artifact(status="ok")
"""
        check(parser, src)  # should not raise

    def test_ssa_across_nodes_ok(self, parser):
        """Same variable name in different nodes is fine."""
        src = """
@air 0.2

workflow W(data: Message) -> Artifact:
    node start:
        x = llm(prompt, data)
        done(x)

    node done(x):
        return Artifact(data=x)
"""
        check(parser, src)

    def test_parallel_distinct_variables(self, parser):
        """Variables in parallel branches must be distinct."""
        src = """
@air 0.2

workflow W(claims: Claim[]) -> Artifact:
    node start:
        parallel:
            x = verify(claims, rule1)
            x = verify(claims, rule2)
        return Artifact(status="ok")
"""
        with pytest.raises(SemanticError, match="SSA.*x"):
            check(parser, src)


# ---------------------------------------------------------------------------
# Variable existence
# ---------------------------------------------------------------------------

class TestVariableExistence:

    def test_undefined_variable(self, parser):
        src = """
@air 0.2

workflow W -> Artifact:
    node start:
        return Artifact(data=missing)
"""
        with pytest.raises(SemanticError, match="Undefined.*missing"):
            check(parser, src)

    def test_workflow_params_visible(self, parser):
        """Workflow input params should be visible in all nodes."""
        src = """
@air 0.2

workflow W(data: Message) -> Artifact:
    node start:
        x = llm(summarize, data)
        return Artifact(data=x)
"""
        check(parser, src)  # should not raise

    def test_node_params_visible(self, parser):
        """Undefined variable in node call args is caught."""
        src = """
@air 0.2

workflow W -> Artifact:
    node start:
        done(result)

    node done(result):
        return Artifact(data=result)
"""
        with pytest.raises(SemanticError, match="Undefined.*result"):
            check(parser, src)

    def test_node_params_scoped(self, parser):
        """Node params should be visible within the node."""
        src = """
@air 0.2

workflow W(input: Message) -> Artifact:
    node start:
        summary = llm(summarize, input)
        done(summary)

    node done(summary):
        return Artifact(data=summary)
"""
        check(parser, src)  # should not raise


# ---------------------------------------------------------------------------
# Route target existence
# ---------------------------------------------------------------------------

class TestRouteTargets:

    def test_unknown_route_target(self, parser):
        src = """
@air 0.2

workflow W(verdict: Verdict) -> Artifact | Fault:
    node start:
        outcome = gate(verdict)

        route outcome:
            PROCEED: nonexistent
            ESCALATE: start
            RETRY: start
            HALT: start
"""
        with pytest.raises(SemanticError, match="Unknown node.*nonexistent"):
            check(parser, src)

    def test_unknown_node_call_target(self, parser):
        src = """
@air 0.2

workflow W(data: Message) -> Artifact:
    node start:
        x = llm(prompt, data)
        nonexistent(x)
"""
        with pytest.raises(SemanticError, match="Unknown node.*nonexistent"):
            check(parser, src)


# ---------------------------------------------------------------------------
# Route exhaustiveness
# ---------------------------------------------------------------------------

class TestRouteExhaustiveness:

    def test_incomplete_outcome_route(self, parser):
        src = """
@air 0.2

workflow W(verdict: Verdict) -> Artifact | Fault:
    node start:
        outcome = gate(verdict)

        route outcome:
            PROCEED: done
            HALT: abort

    node done:
        return Artifact(status="ok")

    node abort:
        return Fault(reason="failed")
"""
        with pytest.raises(SemanticError, match="[Ii]ncomplete.*route"):
            check(parser, src)

    def test_outcome_route_with_else(self, parser):
        """else covers remaining cases."""
        src = """
@air 0.2

workflow W(verdict: Verdict) -> Artifact | Fault:
    node start:
        outcome = gate(verdict)

        route outcome:
            PROCEED: done
            else: abort

    node done:
        return Artifact(status="ok")

    node abort:
        return Fault(reason="failed")
"""
        check(parser, src)  # should not raise

    def test_full_outcome_coverage(self, parser):
        src = """
@air 0.2

workflow W(verdict: Verdict) -> Artifact | Fault:
    node start:
        outcome = gate(verdict)

        route outcome:
            PROCEED: done
            RETRY: start
            ESCALATE: abort
            HALT: abort

    node done:
        return Artifact(status="ok")

    node abort:
        return Fault(reason="failed")
"""
        check(parser, src)  # should not raise


# ---------------------------------------------------------------------------
# Fallback node
# ---------------------------------------------------------------------------

class TestFallbackNode:

    def test_multiple_fallback_nodes(self, parser):
        src = """
@air 0.2

workflow W -> Artifact | Fault:
    node start:
        return Artifact(status="ok")

    node recovery1 [fallback]:
        return Fault(reason="r1")

    node recovery2 [fallback]:
        return Fault(reason="r2")
"""
        with pytest.raises(SemanticError, match="[Mm]ultiple fallback"):
            check(parser, src)

    def test_single_fallback_ok(self, parser):
        src = """
@air 0.2

workflow W -> Artifact | Fault:
    node start:
        return Artifact(status="ok")

    node recovery [fallback]:
        return Fault(reason="failed")
"""
        check(parser, src)  # should not raise


# ---------------------------------------------------------------------------
# Return type validity
# ---------------------------------------------------------------------------

class TestReturnTypes:

    def test_return_undeclared_type(self, parser):
        src = """
@air 0.2

workflow W -> Artifact:
    node start:
        return Fault(reason="bad")
"""
        with pytest.raises(SemanticError, match="[Rr]eturn type.*Fault.*not declared"):
            check(parser, src)

    def test_return_declared_type(self, parser):
        src = """
@air 0.2

workflow W -> Artifact | Fault:
    node start:
        return Fault(reason="bad")
"""
        check(parser, src)  # should not raise


# ---------------------------------------------------------------------------
# Node termination
# ---------------------------------------------------------------------------

class TestNodeTermination:

    def test_node_without_terminator(self, parser):
        src = """
@air 0.2

workflow W(data: Message) -> Artifact:
    node start:
        x = llm(prompt, data)
"""
        with pytest.raises(SemanticError, match="[Nn]ode.*start.*does not terminate"):
            check(parser, src)

    def test_route_terminates(self, parser):
        """A node ending with route is properly terminated."""
        src = """
@air 0.2

workflow W(verdict: Verdict) -> Artifact | Fault:
    node start:
        outcome = gate(verdict)

        route outcome:
            PROCEED: done
            RETRY: start
            ESCALATE: abort
            HALT: abort

    node done:
        return Artifact(status="ok")

    node abort:
        return Fault(reason="failed")
"""
        check(parser, src)  # should not raise

    def test_node_call_terminates(self, parser):
        """A node ending with unconditional node call is terminated."""
        src = """
@air 0.2

workflow W(data: Message) -> Artifact:
    node start:
        x = llm(prompt, data)
        done(x)

    node done(x):
        return Artifact(data=x)
"""
        check(parser, src)  # should not raise
