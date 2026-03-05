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
)
from cfg import CFG
from egir.schema import EgirWorkflow, EgirNode, EgirEdge, EgirOperation


def build_egir(cfg: CFG, workflow_name: str) -> EgirWorkflow:
    entry = next(iter(cfg.nodes))
    egir = EgirWorkflow(name=workflow_name, entry=entry)
    for label, cfg_node in cfg.nodes.items():
        node = EgirNode(
            name=label,
            edges=[
                EgirEdge(target=e.target, condition=e.condition)
                for e in cfg_node.edges
            ],
            terminal=cfg_node.terminal,
        )
        _convert_instructions(cfg_node.instructions, node.operations)
        node.route_variable = _find_route_variable(cfg_node.instructions)
        egir.nodes.append(node)
    return egir


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


def _convert_assign(inst: Assign) -> EgirOperation | None:
    expr = inst.value
    outputs = [t for t in inst.targets if t != "_"]

    if isinstance(expr, LLMCall):
        return EgirOperation(
            type="llm",
            inputs=[],
            outputs=outputs,
            params={"prompt": expr.prompt},
        )
    elif isinstance(expr, ToolCall):
        return EgirOperation(
            type="tool",
            inputs=list(expr.args),
            outputs=outputs,
            params={"name": expr.name},
        )
    elif isinstance(expr, Transform):
        params = {"target_type": expr.target_type.name}
        if expr.target_type.is_list:
            params["target_type"] += "[]"
        if expr.via:
            params["via"] = expr.via.prompt
        return EgirOperation(
            type="transform",
            inputs=[expr.input],
            outputs=outputs,
            params=params,
        )
    elif isinstance(expr, Verify):
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
            outputs=outputs,
            params={"strategy": expr.strategy},
        )
    elif isinstance(expr, Gate):
        return EgirOperation(
            type="gate",
            inputs=[expr.input],
            outputs=outputs,
        )
    elif isinstance(expr, Decide):
        params = {"provider": expr.provider}
        inputs = [expr.input] if expr.input else []
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
            outputs=outputs,
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
