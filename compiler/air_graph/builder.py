"""AIR Graph builder for v0.2.

Converts a CFG (with v0.2 AST instructions) into an AIR Graph.
"""

from air_ast import (
    Assign, Constructor, Decide, DottedName, Gate, Identifier,
    LLMCall, ListLiteral, NodeCall, Parallel, Return, Route,
    Session, ToolCall, Transform, Verify, Aggregate,
    EnumPattern, TypePattern, ElsePattern, BoolPattern,
)
from cfg import CFG
from air_graph.schema import (
    AirGraphWorkflow,
    AirGraphNode,
    AirGraphEdge,
    AirGraphOperation,
    AirGraphCondition,
    AirGraphOutput,
)


def build_air_graph(cfg: CFG, workflow_name: str) -> AirGraphWorkflow:
    graph = AirGraphWorkflow(name=workflow_name, entry=cfg.entry)
    for label, cfg_node in cfg.nodes.items():
        node = AirGraphNode(
            name=label,
            terminal=cfg_node.terminal,
        )
        _convert_instructions(cfg_node.instructions, node.operations)
        node.route_variable = _find_route_variable(cfg_node.instructions)
        node.edges = _build_edges(cfg_node.instructions)
        graph.nodes.append(node)
    return graph


# ---------------------------------------------------------------------------
# Edges
# ---------------------------------------------------------------------------

def _build_edges(instructions: list) -> list[AirGraphEdge]:
    edges = []
    for inst in instructions:
        if isinstance(inst, Route):
            for case in inst.cases:
                if isinstance(case.target, Return):
                    # Inline return — no outgoing edge
                    continue
                condition = _pattern_to_condition(case.pattern)
                if isinstance(case.target, NodeCall):
                    target = case.target.name
                elif isinstance(case.target, str):
                    target = case.target
                else:
                    continue
                edges.append(AirGraphEdge(target=target, condition=condition))
        elif isinstance(inst, NodeCall):
            edges.append(AirGraphEdge(target=inst.name))
    return edges


def _pattern_to_condition(pattern) -> AirGraphCondition:
    if isinstance(pattern, EnumPattern):
        return AirGraphCondition(kind="enum", value=pattern.value)
    if isinstance(pattern, TypePattern):
        return AirGraphCondition(
            kind="type", name=pattern.name, is_list=pattern.is_list
        )
    if isinstance(pattern, ElsePattern):
        return AirGraphCondition(kind="else")
    if isinstance(pattern, BoolPattern):
        return AirGraphCondition(kind="bool", value="true" if pattern.value else "false")
    return AirGraphCondition(kind="enum", value=str(pattern))


def _find_route_variable(instructions: list) -> str | None:
    for inst in instructions:
        if isinstance(inst, Route):
            return _arg_to_str(inst.value)
    return None


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def _convert_instructions(instructions: list, ops: list):
    for inst in instructions:
        if isinstance(inst, Assign):
            op = _convert_assign(inst)
            if op:
                ops.append(op)
        elif isinstance(inst, Return):
            ops.append(_convert_return(inst))
        elif isinstance(inst, Parallel):
            _convert_instructions(inst.branches, ops)
        elif isinstance(inst, ToolCall):
            ops.append(_convert_bare_tool(inst))
        elif isinstance(inst, LLMCall):
            ops.append(_convert_bare_llm(inst))
        elif isinstance(inst, Session):
            ops.append(_convert_bare_session(inst))
        # Route and NodeCall don't produce operations


def _convert_assign(inst: Assign) -> AirGraphOperation | None:
    expr = inst.value
    raw = [t for t in inst.targets if t != "_"]

    if isinstance(expr, LLMCall):
        return AirGraphOperation(
            type="llm",
            inputs=[_arg_to_str(a) for a in expr.args],
            outputs=_typed_outputs(raw, "Message"),
            params={"prompt": expr.prompt},
        )
    if isinstance(expr, ToolCall):
        return AirGraphOperation(
            type="tool",
            inputs=[_arg_to_str(a) for a in expr.args],
            outputs=_typed_outputs(raw, "Artifact"),
            params={"name": expr.name},
        )
    if isinstance(expr, Transform):
        target_type_str = expr.target_type.name
        if expr.target_type.is_list:
            target_type_str += "[]"
        params = {"target_type": target_type_str}
        if expr.via:
            params["via"] = expr.via.prompt
        return AirGraphOperation(
            type="transform",
            inputs=[_arg_to_str(expr.input)],
            outputs=_typed_outputs(raw, target_type_str),
            params=params,
        )
    if isinstance(expr, Verify):
        outputs = []
        for i, name in enumerate(raw):
            outputs.append(AirGraphOutput(
                name=name, type="Verdict" if i == 0 else "Evidence"
            ))
        return AirGraphOperation(
            type="verify",
            inputs=[_arg_to_str(expr.input)],
            outputs=outputs,
            params={"rule": _arg_to_str(expr.rule)},
        )
    if isinstance(expr, Aggregate):
        return AirGraphOperation(
            type="aggregate",
            inputs=[_arg_to_str(a) for a in expr.inputs],
            outputs=_typed_outputs(raw, "Consensus"),
            params={"strategy": expr.strategy},
        )
    if isinstance(expr, Gate):
        return AirGraphOperation(
            type="gate",
            inputs=[_arg_to_str(expr.input)],
            outputs=_typed_outputs(raw, "Outcome"),
        )
    if isinstance(expr, Decide):
        inputs = [_arg_to_str(a) for a in expr.args]
        outputs = []
        for i, name in enumerate(raw):
            outputs.append(AirGraphOutput(
                name=name, type="Message" if i == 0 else "Outcome"
            ))
        return AirGraphOperation(
            type="decide",
            inputs=inputs,
            outputs=outputs,
            params={"provider": expr.provider},
        )
    if isinstance(expr, Session):
        return AirGraphOperation(
            type="session",
            inputs=[_arg_to_str(a) for a in expr.args],
            outputs=_typed_outputs(raw, "Session"),
        )
    if isinstance(expr, Constructor):
        return AirGraphOperation(
            type="construct",
            inputs=[],
            outputs=_typed_outputs(raw, expr.type_name),
            params={"type": expr.type_name, "fields": _serialize_fields(expr.fields)},
        )
    if isinstance(expr, ListLiteral):
        return AirGraphOperation(
            type="construct",
            inputs=[_arg_to_str(item) for item in expr.items],
            outputs=_typed_outputs(raw, "list"),
        )
    return None


def _convert_bare_tool(inst: ToolCall) -> AirGraphOperation:
    return AirGraphOperation(
        type="tool",
        inputs=[_arg_to_str(a) for a in inst.args],
        outputs=[],
        params={"name": inst.name},
    )


def _convert_bare_llm(inst: LLMCall) -> AirGraphOperation:
    return AirGraphOperation(
        type="llm",
        inputs=[_arg_to_str(a) for a in inst.args],
        outputs=[],
        params={"prompt": inst.prompt},
    )


def _convert_bare_session(inst: Session) -> AirGraphOperation:
    return AirGraphOperation(
        type="session",
        inputs=[_arg_to_str(a) for a in inst.args],
        outputs=[],
    )


def _convert_return(inst: Return) -> AirGraphOperation:
    if isinstance(inst.value, Constructor):
        return AirGraphOperation(
            type="return",
            inputs=[],
            outputs=[],
            params={"type": inst.value.type_name,
                    "fields": _serialize_fields(inst.value.fields)},
        )
    if isinstance(inst.value, Identifier):
        return AirGraphOperation(
            type="return",
            inputs=[inst.value.name],
            outputs=[],
        )
    return AirGraphOperation(type="return", inputs=[], outputs=[])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _arg_to_str(arg) -> str:
    """Convert an AST arg/expression to a string for serialization."""
    if isinstance(arg, Identifier):
        return arg.name
    if isinstance(arg, DottedName):
        return f"{arg.object}.{arg.attribute}"
    if isinstance(arg, str):
        return arg
    if isinstance(arg, ListLiteral):
        items = ", ".join(_arg_to_str(i) for i in arg.items)
        return f"[{items}]"
    return str(arg)


def _typed_outputs(names: list[str], type_name: str) -> list[AirGraphOutput]:
    return [AirGraphOutput(name=n, type=type_name) for n in names]


def _serialize_fields(fields: dict) -> dict:
    """Convert constructor fields to serializable form."""
    result = {}
    for key, val in fields.items():
        result[key] = _arg_to_str(val) if not isinstance(val, str) else val
    return result
