from air_ast import (
    Assign,
    LLMCall,
    ToolCall,
    Transform,
    Verify,
    Aggregate,
    Gate,
    Decide,
    Return,
    Parallel,
    Loop,
    Route,
    Variable,
    Constructor,
    EnumPattern,
    TypePattern,
    DefaultPattern,
)
from cfg import CFG
from egir.schema import (
    EgirWorkflow,
    EgirNode,
    EgirEdge,
    EgirOperation,
    EgirCondition,
    EgirOutput,
)


def build_egir(cfg: CFG, workflow_name: str) -> EgirWorkflow:
    entry = next(iter(cfg.nodes))
    egir = EgirWorkflow(name=workflow_name, entry=entry)
    for label, cfg_node in cfg.nodes.items():
        node = EgirNode(
            name=label,
            terminal=cfg_node.terminal,
        )
        _convert_instructions(cfg_node.instructions, node.operations)
        node.route_variable = _find_route_variable(cfg_node.instructions)
        node.edges = _build_edges(cfg_node.instructions, label)
        egir.nodes.append(node)
    return egir


def _build_edges(instructions: list, node_label: str) -> list[EgirEdge]:
    edges = []
    for inst in instructions:
        if isinstance(inst, Route):
            for case in inst.cases:
                condition = _pattern_to_condition(case.pattern)
                if case.target == "continue":
                    target = node_label
                    condition = EgirCondition(kind="continue")
                else:
                    target = case.target
                edges.append(EgirEdge(target=target, condition=condition))
        elif isinstance(inst, Loop):
            edges.extend(_build_edges(inst.body, node_label))
        elif isinstance(inst, Parallel):
            edges.extend(_build_edges(inst.branches, node_label))
    return edges


def _pattern_to_condition(pattern) -> EgirCondition:
    if isinstance(pattern, EnumPattern):
        return EgirCondition(kind="enum", name="Signal", value=pattern.value)
    elif isinstance(pattern, TypePattern):
        return EgirCondition(
            kind="type", name=pattern.name, is_list=pattern.is_list
        )
    elif isinstance(pattern, DefaultPattern):
        return EgirCondition(kind="enum", name="default", value="default")
    return EgirCondition(kind="enum", value=str(pattern))


def _find_route_variable(instructions: list) -> str | None:
    for inst in instructions:
        if isinstance(inst, Route):
            return inst.value
        elif isinstance(inst, Loop):
            result = _find_route_variable(inst.body)
            if result:
                return result
        elif isinstance(inst, Parallel):
            result = _find_route_variable(inst.branches)
            if result:
                return result
    return None


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
        elif isinstance(inst, Loop):
            _convert_instructions(inst.body, ops)


def _typed_outputs(names: list[str], type_name: str) -> list[EgirOutput]:
    return [EgirOutput(name=n, type=type_name) for n in names]


def _convert_assign(inst: Assign) -> EgirOperation | None:
    expr = inst.value
    raw = [t for t in inst.targets if t != "_"]

    if isinstance(expr, LLMCall):
        return EgirOperation(
            type="llm",
            inputs=[],
            outputs=_typed_outputs(raw, "Message"),
            params={"prompt": expr.prompt},
        )
    elif isinstance(expr, ToolCall):
        return EgirOperation(
            type="tool",
            inputs=list(expr.args),
            outputs=_typed_outputs(raw, "Artifact"),
            params={"name": expr.name},
        )
    elif isinstance(expr, Transform):
        params = {"target_type": expr.target_type.name}
        if expr.target_type.is_list:
            params["target_type"] += "[]"
            out_type = f"{expr.target_type.name}[]"
        else:
            out_type = expr.target_type.name
        if expr.via:
            params["via"] = expr.via.prompt
        return EgirOperation(
            type="transform",
            inputs=[expr.input],
            outputs=_typed_outputs(raw, out_type),
            params=params,
        )
    elif isinstance(expr, Verify):
        outputs = []
        for i, name in enumerate(raw):
            outputs.append(EgirOutput(
                name=name, type="Verdict" if i == 0 else "Evidence"
            ))
        return EgirOperation(
            type="verify",
            inputs=[expr.input],
            outputs=outputs,
            params={"rule": expr.rule},
        )
    elif isinstance(expr, Aggregate):
        return EgirOperation(
            type="aggregate",
            inputs=list(expr.inputs),
            outputs=_typed_outputs(raw, "Consensus"),
            params={"strategy": expr.strategy},
        )
    elif isinstance(expr, Gate):
        return EgirOperation(
            type="gate",
            inputs=[expr.input],
            outputs=_typed_outputs(raw, "Outcome"),
        )
    elif isinstance(expr, Decide):
        params = {"provider": expr.provider}
        inputs = [expr.input] if expr.input else []
        outputs = []
        for i, name in enumerate(raw):
            outputs.append(EgirOutput(
                name=name, type="Message" if i == 0 else "Outcome"
            ))
        return EgirOperation(
            type="decide",
            inputs=inputs,
            outputs=outputs,
            params=params,
        )
    elif isinstance(expr, Constructor):
        return EgirOperation(
            type="construct",
            inputs=[],
            outputs=_typed_outputs(raw, expr.type_name),
            params={"type": expr.type_name, "fields": expr.fields},
        )
    return None


def _convert_return(inst: Return) -> EgirOperation:
    if isinstance(inst.value, Variable):
        return EgirOperation(
            type="return",
            inputs=[inst.value.name],
            outputs=[],
        )
    if isinstance(inst.value, Constructor):
        return EgirOperation(
            type="return",
            inputs=[],
            outputs=[],
            params={"type": inst.value.type_name, "fields": inst.value.fields},
        )
    return EgirOperation(type="return", inputs=[], outputs=[])
