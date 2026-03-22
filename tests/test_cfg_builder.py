"""Tests for the v0.2 CFG builder (AST -> control flow graph)."""

import pytest

from helpers import build_fixture, find_node
from ast_builder import ASTBuilder
from cfg_builder import build_cfg
from cfg import CFG, CFGNode, CFGEdge


def build_cfg_from_src(parser, src: str) -> CFG:
    tree = parser.parse(src)
    program = ASTBuilder().build(tree)
    return build_cfg(program.workflows[0])


def build_cfg_from_fixture(parser, name: str) -> CFG:
    from helpers import build_fixture

    program = build_fixture(parser, name)
    return build_cfg(program.workflows[0])


# ---------------------------------------------------------------------------
# Basic structure
# ---------------------------------------------------------------------------


class TestBasicStructure:

    def test_single_node(self, parser):
        cfg = build_cfg_from_fixture(parser, "basic")
        assert cfg.entry == "start"
        assert len(cfg.nodes) == 1
        assert "start" in cfg.nodes
        assert cfg.nodes["start"].terminal is True
        assert cfg.nodes["start"].edges == []

    def test_entry_is_first_node(self, parser):
        cfg = build_cfg_from_fixture(parser, "transition")
        assert cfg.entry == "start"

    def test_all_nodes_present(self, parser):
        cfg = build_cfg_from_fixture(parser, "nodes")
        assert set(cfg.nodes.keys()) == {
            "start",
            "publish",
            "retry",
            "discuss",
            "recovery",
        }


# ---------------------------------------------------------------------------
# Edges from node calls (unconditional transitions)
# ---------------------------------------------------------------------------


class TestNodeCallEdges:

    def test_unconditional_transition(self, parser):
        cfg = build_cfg_from_fixture(parser, "transition")
        start = cfg.nodes["start"]
        assert start.terminal is False
        assert len(start.edges) == 1
        assert start.edges[0].target == "publish"
        assert start.edges[0].condition is None

    def test_target_node_is_terminal(self, parser):
        cfg = build_cfg_from_fixture(parser, "transition")
        publish = cfg.nodes["publish"]
        assert publish.terminal is True
        assert publish.edges == []


# ---------------------------------------------------------------------------
# Edges from routes
# ---------------------------------------------------------------------------


class TestRouteEdges:

    def test_outcome_route_edges(self, parser):
        cfg = build_cfg_from_fixture(parser, "route")
        node = cfg.nodes["outcome_route"]
        assert node.terminal is False
        targets = {e.target for e in node.edges}
        assert "publish" in targets
        assert "abort" in targets
        assert "outcome_route" in targets  # RETRY self-loop

    def test_route_conditions(self, parser):
        cfg = build_cfg_from_fixture(parser, "route")
        node = cfg.nodes["outcome_route"]
        conditions = {e.condition for e in node.edges}
        assert "PROCEED" in conditions
        assert "ESCALATE" in conditions
        assert "RETRY" in conditions
        assert "HALT" in conditions

    def test_else_pattern_edge(self, parser):
        cfg = build_cfg_from_fixture(parser, "route")
        node = cfg.nodes["else_route"]
        conditions = {e.condition for e in node.edges}
        assert "else" in conditions

    def test_bool_pattern_edges(self, parser):
        cfg = build_cfg_from_fixture(parser, "route")
        node = cfg.nodes["bool_route"]
        conditions = {e.condition for e in node.edges}
        assert "true" in conditions
        assert "false" in conditions

    def test_inline_return_route(self, parser):
        """Route with inline return: node is terminal AND has edges."""
        cfg = build_cfg_from_fixture(parser, "route")
        node = cfg.nodes["inline_return_route"]
        assert node.terminal is True
        # Edge for PROCEED -> publish
        assert any(e.target == "publish" for e in node.edges)
        # No edge for HALT (inline return)

    def test_route_target_with_args(self, parser):
        """Route target with args: publish(summary, outcome)."""
        cfg = build_cfg_from_fixture(parser, "route")
        node = cfg.nodes["args_route"]
        assert any(e.target == "publish" for e in node.edges)

    def test_dotted_route_value(self, parser):
        """Route on dotted name: route result.consensus."""
        cfg = build_cfg_from_fixture(parser, "route")
        node = cfg.nodes["dotted_route"]
        assert len(node.edges) >= 2


# ---------------------------------------------------------------------------
# Terminal nodes
# ---------------------------------------------------------------------------


class TestTerminalNodes:

    def test_return_is_terminal(self, parser):
        cfg = build_cfg_from_fixture(parser, "basic")
        assert cfg.nodes["start"].terminal is True

    def test_route_only_is_not_terminal(self, parser):
        cfg = build_cfg_from_fixture(parser, "route")
        assert cfg.nodes["outcome_route"].terminal is False

    def test_fallback_node(self, parser):
        cfg = build_cfg_from_fixture(parser, "nodes")
        assert cfg.nodes["recovery"].terminal is True


# ---------------------------------------------------------------------------
# Parallel blocks
# ---------------------------------------------------------------------------


class TestParallelCFG:

    def test_parallel_no_extra_edges(self, parser):
        """Parallel blocks don't add CFG edges (they're intra-node)."""
        cfg = build_cfg_from_fixture(parser, "parallel")
        strict = cfg.nodes["strict"]
        assert strict.terminal is True
        assert strict.edges == []


# ---------------------------------------------------------------------------
# Reachability
# ---------------------------------------------------------------------------


class TestReachability:

    def test_unreachable_node_warning(self, parser, capsys):
        src = """
@air 0.2

workflow W -> Artifact:
    node start:
        return Artifact(status="ok")

    node orphan:
        return Artifact(status="orphan")
"""
        cfg = build_cfg_from_src(parser, src)
        captured = capsys.readouterr()
        assert "unreachable" in captured.out.lower()
        assert "orphan" in captured.out


# ---------------------------------------------------------------------------
# Edge target validation
# ---------------------------------------------------------------------------


class TestEdgeValidation:

    def test_all_edge_targets_exist(self, parser):
        """All fixtures should produce valid CFGs with no broken edges."""
        for name in ["basic", "transition", "route", "parallel", "nodes"]:
            cfg = build_cfg_from_fixture(parser, name)
            for label, node in cfg.nodes.items():
                for edge in node.edges:
                    assert (
                        edge.target in cfg.nodes
                    ), f"Edge from {label} to unknown {edge.target}"


# ---------------------------------------------------------------------------
# Max visits (bounded loops)
# ---------------------------------------------------------------------------


class TestMaxVisits:

    def test_max_visits_propagated(self, parser):
        """Node with [max=N] should have max_visits set on the CFGNode."""
        cfg = build_cfg_from_fixture(parser, "max_visits")
        assert cfg.nodes["analyze"].max_visits == 3

    def test_max_visits_none_by_default(self, parser):
        """Nodes without [max=N] should have max_visits=None."""
        cfg = build_cfg_from_fixture(parser, "max_visits")
        assert cfg.nodes["validate"].max_visits is None
        assert cfg.nodes["done"].max_visits is None
        assert cfg.nodes["abort"].max_visits is None

    def test_max_visits_back_edge_present(self, parser):
        """Node with max_visits should still have its back-edge to itself."""
        cfg = build_cfg_from_fixture(parser, "max_visits")
        analyze = cfg.nodes["analyze"]
        targets = {e.target for e in analyze.edges}
        assert "analyze" in targets  # self-referencing back-edge on Fault

