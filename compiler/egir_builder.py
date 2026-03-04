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
    Variable,
    Constructor,
    Instruction,
)
from cfg import CFG
from egir import EGIR, ExecNode, ExecEdge, Operation


def build_egir(cfg: CFG) -> EGIR:
    egir = EGIR()
    for label, cfg_node in cfg.nodes.items():
        exec_node = ExecNode(
            id=label,
            edges=[
                ExecEdge(target=e.target, condition=e.condition)
                for e in cfg_node.edges
            ],
            terminal=cfg_node.terminal,
        )
        _convert_instructions(cfg_node.instructions, exec_node.operations)
        egir.nodes[label] = exec_node
    return egir


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


def _convert_assign(inst: Assign) -> Operation | None:
    expr = inst.value
    outputs = [t for t in inst.targets if t != "_"]

    if isinstance(expr, LLMCall):
        return Operation(
            type="llm",
            inputs=[],
            outputs=outputs,
            attributes={"prompt": expr.prompt},
        )
    elif isinstance(expr, ToolCall):
        return Operation(
            type="tool",
            inputs=list(expr.args),
            outputs=outputs,
            attributes={"name": expr.name},
        )
    elif isinstance(expr, Transform):
        attrs = {"target_type": expr.target_type.name}
        if expr.target_type.is_list:
            attrs["target_type"] += "[]"
        if expr.via:
            attrs["via"] = expr.via.prompt
        return Operation(
            type="transform",
            inputs=[expr.input],
            outputs=outputs,
            attributes=attrs,
        )
    elif isinstance(expr, Verify):
        return Operation(
            type="verify",
            inputs=[expr.input],
            outputs=outputs,
            attributes={"rule": expr.rule},
        )
    elif isinstance(expr, Aggregate):
        return Operation(
            type="aggregate",
            inputs=list(expr.inputs),
            outputs=outputs,
            attributes={"strategy": expr.strategy},
        )
    elif isinstance(expr, Gate):
        return Operation(
            type="gate",
            inputs=[expr.input],
            outputs=outputs,
        )
    elif isinstance(expr, Decide):
        attrs = {"provider": expr.provider}
        inputs = [expr.input] if expr.input else []
        return Operation(
            type="decide",
            inputs=inputs,
            outputs=outputs,
            attributes=attrs,
        )
    elif isinstance(expr, Constructor):
        return Operation(
            type="construct",
            inputs=[],
            outputs=outputs,
            attributes={"type": expr.type_name, "fields": expr.fields},
        )
    # Variable assignments and others don't produce operations
    return None


def _convert_return(inst: Return) -> Operation:
    attrs = {}
    if isinstance(inst.value, Variable):
        return Operation(
            type="return",
            inputs=[inst.value.name],
            outputs=[],
            attributes=attrs,
        )
    return Operation(type="return", inputs=[], outputs=[], attributes=attrs)
