"""Hypothesis strategies for Bedrock backend property-based tests."""

from hypothesis import strategies as st

# ── Primitives ─────────────────────────────────────────────────────────────────

_VAR_NAMES = st.from_regex(r"[a-z][a-z0-9_]{0,10}", fullmatch=True)
_AIR_TYPES = st.sampled_from(["String", "Message", "Verdict", "Outcome", "Object", "Number"])
_NODE_NAMES = st.from_regex(r"[a-z][a-z0-9]{1,8}", fullmatch=True)


def _output(name_st=_VAR_NAMES, type_st=_AIR_TYPES):
    return st.fixed_dictionaries({"name": name_st, "type": type_st})


# ── Operations ─────────────────────────────────────────────────────────────────

def _llm_op(input_var="content"):
    return st.just({
        "type": "llm",
        "inputs": [input_var],
        "outputs": [{"name": "result", "type": "Message"}],
        "params": {"prompt": "summarize"},
    })


def _return_op(input_var="result"):
    return st.just({
        "type": "return",
        "inputs": [input_var],
        "outputs": [],
        "params": {},
    })


def _verify_op(input_var="content"):
    return st.just({
        "type": "verify",
        "inputs": [input_var],
        "outputs": [{"name": "verdict", "type": "Verdict"}],
        "params": {"rule": "some_rule"},
    })


def _gate_op(input_var="verdict"):
    return st.just({
        "type": "gate",
        "inputs": [input_var],
        "outputs": [{"name": "outcome", "type": "Outcome"}],
        "params": {},
    })


def _aggregate_op(input_vars=None):
    if input_vars is None:
        input_vars = ["v1", "v2"]
    return st.just({
        "type": "aggregate",
        "inputs": input_vars,
        "outputs": [{"name": "consensus", "type": "Consensus"}],
        "params": {"strategy": "majority"},
    })


def _decide_op(input_var="content"):
    return st.just({
        "type": "decide",
        "inputs": [input_var],
        "outputs": [{"name": "message", "type": "Message"}, {"name": "outcome", "type": "Outcome"}],
        "params": {"provider": "llm"},
    })


def _session_op():
    return st.just({
        "type": "session",
        "inputs": ["members", "protocol", "history"],
        "outputs": [{"name": "result", "type": "Object"}],
        "params": {"protocol": "discuss"},
    })


# ── Node builders ──────────────────────────────────────────────────────────────

def _terminal_node_with_ops(ops: list) -> dict:
    return {"operations": ops, "terminal": True}


def _non_terminal_node_with_ops(ops: list, target: str) -> dict:
    return {
        "operations": ops,
        "terminal": False,
        "edges": [{"target": target}],
    }


# ── Graph builders ─────────────────────────────────────────────────────────────

@st.composite
def valid_air_graphs(draw):
    """Minimal valid AIR graph: single terminal node with llm + return."""
    workflow = draw(st.from_regex(r"[A-Z][a-zA-Z0-9]{2,10}", fullmatch=True))
    return {
        "air_graph_version": "0.2",
        "workflow": workflow,
        "entry": "start",
        "nodes": {
            "start": _terminal_node_with_ops([
                {"type": "llm", "inputs": ["content"], "outputs": [{"name": "result", "type": "Message"}], "params": {"prompt": "p"}},
                {"type": "return", "inputs": ["result"], "outputs": [], "params": {}},
            ])
        },
    }


@st.composite
def air_graphs_with_llm(draw):
    """AIR graph guaranteed to contain at least one llm operation."""
    workflow = draw(st.from_regex(r"[A-Z][a-zA-Z0-9]{2,10}", fullmatch=True))
    model = draw(st.sampled_from(["amazon.nova-lite-v1:0", "gpt-4o", "claude-3-haiku-20240307"]))
    return {
        "air_graph_version": "0.2",
        "workflow": workflow,
        "entry": "start",
        "nodes": {
            "start": _terminal_node_with_ops([
                {"type": "llm", "inputs": ["content"], "outputs": [{"name": "out", "type": "Message"}], "params": {"prompt": "p"}},
                {"type": "return", "inputs": ["out"], "outputs": [], "params": {}},
            ])
        },
        "_test_model": model,  # carried for assertions, stripped before compile
    }


@st.composite
def air_graphs_with_sdk_ops(draw):
    """AIR graph with verify + gate (SDK operations)."""
    workflow = draw(st.from_regex(r"[A-Z][a-zA-Z0-9]{2,10}", fullmatch=True))
    sdk_op = draw(st.sampled_from(["verify", "gate", "aggregate", "decide"]))

    if sdk_op == "verify":
        ops = [
            {"type": "verify", "inputs": ["content"], "outputs": [{"name": "v", "type": "Verdict"}], "params": {"rule": "r"}},
            {"type": "return", "inputs": ["v"], "outputs": [], "params": {}},
        ]
    elif sdk_op == "gate":
        ops = [
            {"type": "gate", "inputs": ["verdict"], "outputs": [{"name": "outcome", "type": "Outcome"}], "params": {}},
            {"type": "return", "inputs": ["outcome"], "outputs": [], "params": {}},
        ]
    elif sdk_op == "aggregate":
        ops = [
            {"type": "aggregate", "inputs": ["v1", "v2"], "outputs": [{"name": "c", "type": "Consensus"}], "params": {"strategy": "majority"}},
            {"type": "return", "inputs": ["c"], "outputs": [], "params": {}},
        ]
    else:  # decide
        ops = [
            {"type": "decide", "inputs": ["content"], "outputs": [{"name": "msg", "type": "Message"}, {"name": "outcome", "type": "Outcome"}], "params": {"provider": "llm"}},
            {"type": "return", "inputs": ["msg"], "outputs": [], "params": {}},
        ]

    return {
        "air_graph_version": "0.2",
        "workflow": workflow,
        "entry": "start",
        "nodes": {"start": _terminal_node_with_ops(ops)},
        "_test_sdk_op": sdk_op,
    }


@st.composite
def air_graphs_with_conditional_edges(draw):
    """AIR graph with two nodes and conditional routing."""
    workflow = draw(st.from_regex(r"[A-Z][a-zA-Z0-9]{2,10}", fullmatch=True))
    return {
        "air_graph_version": "0.2",
        "workflow": workflow,
        "entry": "start",
        "nodes": {
            "start": {
                "operations": [
                    {"type": "gate", "inputs": ["verdict"], "outputs": [{"name": "outcome", "type": "Outcome"}], "params": {}},
                ],
                "terminal": False,
                "route_variable": "outcome",
                "edges": [
                    {"target": "done", "condition": {"kind": "enum", "value": "PROCEED"}},
                    {"target": "done", "condition": {"kind": "else"}},
                ],
            },
            "done": _terminal_node_with_ops([
                {"type": "return", "inputs": [], "outputs": [], "params": {}},
            ]),
        },
    }


@st.composite
def prompt_templates(draw):
    """Generate prompt template strings with zero or more {{variable}} placeholders."""
    n_vars = draw(st.integers(min_value=0, max_value=4))
    var_names = draw(st.lists(
        st.from_regex(r"[a-z][a-z0-9_]{0,8}", fullmatch=True),
        min_size=n_vars, max_size=n_vars, unique=True,
    ))
    parts = ["You are a helpful assistant."]
    for v in var_names:
        parts.append(f"Input: {{{{{v}}}}}")
    return "\n".join(parts), var_names
