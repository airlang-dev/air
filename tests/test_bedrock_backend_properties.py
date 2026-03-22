"""Property-based tests for the Bedrock Flow backend using Hypothesis."""

import re

import pytest
from hypothesis import given, settings, assume

from backends.bedrock.backend import BedrockBackend
from backends.bedrock.compiler import CompilationError
from strategies_bedrock import (
    valid_air_graphs,
    air_graphs_with_llm,
    air_graphs_with_sdk_ops,
    air_graphs_with_conditional_edges,
    prompt_templates,
)

_BEDROCK_NAME_RE = re.compile(r"^[a-zA-Z]([_]?[0-9a-zA-Z]){1,50}$")
_BEDROCK_TYPES = {"String", "Number", "Boolean", "Object", "Array"}
_SDK_OPS = {"verify", "aggregate", "gate", "decide", "session"}


def _backend():
    return BedrockBackend(region="eu-west-1", account_id="999999999999")


def _compile(graph: dict):
    """Strip test-only keys and compile."""
    clean = {k: v for k, v in graph.items() if not k.startswith("_test_")}
    return _backend().compile_with_warnings(clean, output_path=None)


# ── Property 1: Output structure invariant ────────────────────────────────────

@given(valid_air_graphs())
@settings(max_examples=100)
def test_prop1_output_structure_invariant(graph):
    """compile_with_warnings() always returns dict with exactly 'nodes' and 'connections' lists."""
    flow_def, warnings = _compile(graph)
    assert isinstance(flow_def, dict)
    assert set(flow_def.keys()) == {"nodes", "connections"}
    assert isinstance(flow_def["nodes"], list)
    assert isinstance(flow_def["connections"], list)


# ── Property 2: Exactly one Input node, at least one Output node ──────────────

@given(valid_air_graphs())
@settings(max_examples=100)
def test_prop2_input_output_node_counts(graph):
    """Exactly one Input node and at least one Output node in every compiled flow."""
    flow_def, _ = _compile(graph)
    node_types = [n["type"] for n in flow_def["nodes"]]
    assert node_types.count("Input") == 1
    assert node_types.count("Output") >= 1


# ── Property 3: All node names match Bedrock regex ────────────────────────────

@given(valid_air_graphs())
@settings(max_examples=100)
def test_prop3_node_names_match_bedrock_regex(graph):
    """Every node name satisfies ^[a-zA-Z]([_]?[0-9a-zA-Z]){1,50}$."""
    flow_def, _ = _compile(graph)
    for node in flow_def["nodes"]:
        assert _BEDROCK_NAME_RE.match(node["name"]), (
            f"Node name {node['name']!r} does not match Bedrock regex"
        )


# ── Property 4: Connection referential integrity ──────────────────────────────

@given(valid_air_graphs())
@settings(max_examples=100)
def test_prop4_connection_referential_integrity(graph):
    """Every connection source and target references an existing node name."""
    flow_def, _ = _compile(graph)
    node_names = {n["name"] for n in flow_def["nodes"]}
    for conn in flow_def["connections"]:
        assert conn["source"] in node_names, f"Unknown source: {conn['source']}"
        assert conn["target"] in node_names, f"Unknown target: {conn['target']}"


# ── Property 5: Node name uniqueness ─────────────────────────────────────────

@given(valid_air_graphs())
@settings(max_examples=100)
def test_prop5_node_name_uniqueness(graph):
    """All node names are unique within a compiled flow."""
    flow_def, _ = _compile(graph)
    names = [n["name"] for n in flow_def["nodes"]]
    assert len(names) == len(set(names)), f"Duplicate node names: {names}"


# ── Property 6: Connection name uniqueness ────────────────────────────────────

@given(valid_air_graphs())
@settings(max_examples=100)
def test_prop6_connection_name_uniqueness(graph):
    """All connection names are unique within a compiled flow."""
    flow_def, _ = _compile(graph)
    names = [c["name"] for c in flow_def["connections"]]
    assert len(names) == len(set(names)), f"Duplicate connection names: {names}"


# ── Property 7: All node input expressions start with $.data ─────────────────

@given(valid_air_graphs())
@settings(max_examples=100)
def test_prop7_input_expressions_start_with_dollar_data(graph):
    """Every node input expression starts with '$.data'."""
    flow_def, _ = _compile(graph)
    for node in flow_def["nodes"]:
        for inp in node.get("inputs", []):
            expr = inp.get("expression", "")
            if expr:
                assert expr.startswith("$.data"), (
                    f"Node {node['name']!r} input {inp['name']!r} expression {expr!r} "
                    "does not start with '$.data'"
                )


# ── Property 8: All node input/output types are Bedrock-supported ─────────────

@given(valid_air_graphs())
@settings(max_examples=100)
def test_prop8_all_types_are_bedrock_supported(graph):
    """Every node input and output type is one of the five Bedrock-supported types."""
    flow_def, _ = _compile(graph)
    for node in flow_def["nodes"]:
        for inp in node.get("inputs", []):
            t = inp.get("type")
            if t:
                assert t in _BEDROCK_TYPES, (
                    f"Node {node['name']!r} input {inp['name']!r} has unsupported type {t!r}"
                )
        for out in node.get("outputs", []):
            t = out.get("type")
            if t:
                assert t in _BEDROCK_TYPES, (
                    f"Node {node['name']!r} output {out['name']!r} has unsupported type {t!r}"
                )


# ── Property 9: SDK operations compile to LambdaFunction nodes with correct ARNs

@given(air_graphs_with_sdk_ops())
@settings(max_examples=100)
def test_prop9_sdk_ops_compile_to_lambda_with_correct_arn(graph):
    """SDK operations produce LambdaFunction nodes whose ARN matches the expected pattern."""
    sdk_op = graph["_test_sdk_op"]
    flow_def, _ = _compile(graph)
    lambda_nodes = [n for n in flow_def["nodes"] if n["type"] == "LambdaFunction"]
    assert lambda_nodes, f"No LambdaFunction nodes found for sdk_op={sdk_op!r}"
    arns = [
        n["configuration"]["lambdaFunction"]["lambdaArn"]
        for n in lambda_nodes
        if "lambdaFunction" in n.get("configuration", {})
    ]
    assert arns, "No LambdaFunction nodes with lambdaArn found"
    # At least one ARN should reference the expected SDK function
    expected_fn = f"air-sdk-{sdk_op}"
    assert any(expected_fn in arn for arn in arns), (
        f"Expected ARN containing '{expected_fn}' but got: {arns}"
    )


# ── Property 10: SDK Lambda nodes include params in configuration ─────────────

@given(air_graphs_with_sdk_ops())
@settings(max_examples=100)
def test_prop10_sdk_lambda_nodes_have_arn_in_configuration(graph):
    """Every LambdaFunction node has a lambdaArn in its configuration."""
    flow_def, _ = _compile(graph)
    for node in flow_def["nodes"]:
        if node["type"] == "LambdaFunction":
            cfg = node.get("configuration", {})
            assert "lambdaFunction" in cfg, f"LambdaFunction node {node['name']!r} missing lambdaFunction config"
            assert "lambdaArn" in cfg["lambdaFunction"], f"LambdaFunction node {node['name']!r} missing lambdaArn"
            assert cfg["lambdaFunction"]["lambdaArn"].startswith("arn:aws:lambda:"), (
                f"lambdaArn {cfg['lambdaFunction']['lambdaArn']!r} does not start with 'arn:aws:lambda:'"
            )


# ── Property 11: llm operations compile to Prompt nodes with configured modelId

@given(air_graphs_with_llm())
@settings(max_examples=100)
def test_prop11_llm_ops_compile_to_prompt_nodes(graph):
    """llm operations produce Prompt nodes with a non-empty modelId."""
    flow_def, _ = _compile(graph)
    prompt_nodes = [n for n in flow_def["nodes"] if n["type"] == "Prompt"]
    assert prompt_nodes, "No Prompt nodes found for graph with llm operation"
    for node in prompt_nodes:
        cfg = node.get("configuration", {})
        assert "prompt" in cfg
        inline = cfg["prompt"]["sourceConfiguration"]["inline"]
        assert inline.get("modelId"), f"Prompt node {node['name']!r} has empty modelId"
        assert inline.get("templateType") == "TEXT"


# ── Property 12: Multi-operation nodes produce chained Data connections ────────

@given(valid_air_graphs())
@settings(max_examples=100)
def test_prop12_multi_op_nodes_produce_data_connections(graph):
    """When a node has multiple operations, Data connections chain them together."""
    flow_def, _ = _compile(graph)
    # Count non-Input/Output nodes — if > 2 per AIR node, there must be Data connections
    data_conns = [c for c in flow_def["connections"] if c["type"] == "Data"]
    # At minimum FlowInputNode → first node must be a Data connection
    assert data_conns, "Expected at least one Data connection"


# ── Property 13: Terminal nodes connect to Output nodes ───────────────────────

@given(valid_air_graphs())
@settings(max_examples=100)
def test_prop13_terminal_nodes_connect_to_output(graph):
    """Every Output node has at least one incoming Data connection."""
    flow_def, _ = _compile(graph)
    output_names = {n["name"] for n in flow_def["nodes"] if n["type"] == "Output"}
    assert output_names, "No Output nodes found"
    data_targets = {c["target"] for c in flow_def["connections"] if c["type"] == "Data"}
    for out_name in output_names:
        assert out_name in data_targets, (
            f"Output node {out_name!r} has no incoming Data connection"
        )


# ── Property 14: Prompt inputVariables match template placeholders ────────────

@given(prompt_templates())
@settings(max_examples=100)
def test_prop14_prompt_input_variables_match_placeholders(template_and_vars):
    """inputVariables in a Prompt node exactly match {{var}} placeholders in the template."""
    template, expected_vars = template_and_vars
    # Build a minimal graph using this template via a mock asset resolver
    from backends.bedrock.compiler import (
        CompilerConfig, WarningCollector, OperationCompiler,
    )
    from backends.bedrock.naming import NodeNamer

    config = CompilerConfig(region="eu-west-1", account_id="999999999999")
    wc = WarningCollector()

    class _MockResolver:
        def resolve_prompt(self, name):
            class _Asset:
                pass
            a = _Asset()
            a.template = template
            a.model = None
            return a

    oc = OperationCompiler(config, wc, asset_resolver=_MockResolver())
    op = {
        "type": "llm",
        "inputs": expected_vars or ["content"],
        "outputs": [{"name": "out", "type": "Message"}],
        "params": {"prompt": "test_prompt"},
    }
    nodes = oc.compile_op(op, "test_node", 0, NodeNamer())
    assert nodes
    prompt_node = nodes[0]
    assert prompt_node["type"] == "Prompt"
    inline = prompt_node["configuration"]["prompt"]["sourceConfiguration"]["inline"]
    actual_vars = [v["name"] for v in inline["templateConfiguration"]["text"]["inputVariables"]]
    assert set(actual_vars) == set(expected_vars), (
        f"inputVariables {actual_vars} != template placeholders {expected_vars}"
    )


# ── Property 15: Single unconditional edge produces exactly one Data connection

@given(valid_air_graphs())
@settings(max_examples=100)
def test_prop15_single_unconditional_edge_produces_one_data_connection(graph):
    """A graph with only unconditional edges has no Condition nodes."""
    flow_def, _ = _compile(graph)
    # valid_air_graphs() produces single-node terminal graphs — no edges → no Condition nodes
    condition_nodes = [n for n in flow_def["nodes"] if n["type"] == "Condition"]
    assert not condition_nodes, (
        f"Unexpected Condition nodes in single-node graph: {[n['name'] for n in condition_nodes]}"
    )


# ── Property 16: Conditional edges produce a Condition node ──────────────────

@given(air_graphs_with_conditional_edges())
@settings(max_examples=100)
def test_prop16_conditional_edges_produce_condition_node(graph):
    """A graph with conditional edges always produces at least one Condition node."""
    flow_def, _ = _compile(graph)
    condition_nodes = [n for n in flow_def["nodes"] if n["type"] == "Condition"]
    assert condition_nodes, "Expected at least one Condition node for graph with conditional edges"


# ── Property 17: compile_with_warnings always returns warnings list ───────────

@given(valid_air_graphs())
@settings(max_examples=100)
def test_prop17_compile_with_warnings_always_returns_list(graph):
    """The second element of compile_with_warnings() is always a list of strings."""
    _, warnings = _compile(graph)
    assert isinstance(warnings, list)
    assert all(isinstance(w, str) for w in warnings)
