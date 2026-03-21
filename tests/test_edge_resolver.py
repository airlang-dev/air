"""Tests for the EdgeResolver."""

import pytest

from runtime.edge_resolver import EdgeResolver


class TestUnconditionalEdge:

    def test_unconditional_edge(self):
        edges = [{"target": "next_node"}]
        target, matched = EdgeResolver.resolve(None, edges)

        assert target == "next_node"
        assert matched == "unconditional"


class TestEnumEdge:

    def test_matching_enum(self):
        edges = [
            {
                "target": "approve_node",
                "condition": {"kind": "enum", "value": "approve"},
            },
            {"target": "reject_node", "condition": {"kind": "enum", "value": "reject"}},
        ]
        target, matched = EdgeResolver.resolve("approve", edges)

        assert target == "approve_node"
        assert matched == "approve"

    def test_non_matching_enum_falls_through(self):
        edges = [
            {
                "target": "approve_node",
                "condition": {"kind": "enum", "value": "approve"},
            },
            {"target": "reject_node", "condition": {"kind": "enum", "value": "reject"}},
        ]
        target, matched = EdgeResolver.resolve("reject", edges)

        assert target == "reject_node"
        assert matched == "reject"


class TestBoolEdge:

    def test_true_condition_with_truthy_value(self):
        edges = [
            {"target": "yes_node", "condition": {"kind": "bool", "value": "true"}},
            {"target": "no_node", "condition": {"kind": "bool", "value": "false"}},
        ]
        target, matched = EdgeResolver.resolve("something truthy", edges)

        assert target == "yes_node"
        assert matched == "true"

    def test_false_condition_with_falsy_value(self):
        edges = [
            {"target": "yes_node", "condition": {"kind": "bool", "value": "true"}},
            {"target": "no_node", "condition": {"kind": "bool", "value": "false"}},
        ]
        target, matched = EdgeResolver.resolve(None, edges)

        assert target == "no_node"
        assert matched == "false"


class TestTypeEdge:

    def test_list_type_match(self):
        edges = [
            {
                "target": "list_node",
                "condition": {"kind": "type", "name": "Claim", "is_list": True},
            },
            {
                "target": "single_node",
                "condition": {"kind": "type", "name": "Claim", "is_list": False},
            },
        ]
        target, matched = EdgeResolver.resolve(["a", "b"], edges)

        assert target == "list_node"
        assert matched == "Claim[]"

    def test_non_list_type_match(self):
        edges = [
            {
                "target": "list_node",
                "condition": {"kind": "type", "name": "Claim", "is_list": True},
            },
            {
                "target": "single_node",
                "condition": {"kind": "type", "name": "Claim", "is_list": False},
            },
        ]
        target, matched = EdgeResolver.resolve({"type": "Claim", "value": "single"}, edges)

        assert target == "single_node"
        assert matched == "Claim"


class TestElseFallback:

    def test_else_when_no_enum_matches(self):
        edges = [
            {
                "target": "approve_node",
                "condition": {"kind": "enum", "value": "approve"},
            },
            {"target": "fallback_node", "condition": {"kind": "else"}},
        ]
        target, matched = EdgeResolver.resolve("unknown", edges)

        assert target == "fallback_node"
        assert matched == "else"

    def test_no_match_raises_error(self):
        edges = [
            {
                "target": "approve_node",
                "condition": {"kind": "enum", "value": "approve"},
            },
        ]
        with pytest.raises(RuntimeError, match="no matching edge"):
            EdgeResolver.resolve("unknown", edges)
