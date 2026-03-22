"""CFG builder for AIR v0.2.

Converts a Workflow AST into a control flow graph (CFG).
Each workflow Node becomes a CFGNode. Edges come from routes and node calls.
"""

from air_ast import (
    Workflow,
    Node,
    Route,
    Return,
    NodeCall,
    Parallel,
    Unreachable,
    EnumPattern,
    TypePattern,
    ElsePattern,
    BoolPattern,
    LLMCall,
    ToolCall,
    Session,
)
from cfg import CFG, CFGNode, CFGEdge


def _pattern_str(pattern) -> str:
    if isinstance(pattern, EnumPattern):
        return pattern.value
    if isinstance(pattern, TypePattern):
        return f"{pattern.name}[]" if pattern.is_list else pattern.name
    if isinstance(pattern, ElsePattern):
        return "else"
    if isinstance(pattern, BoolPattern):
        return "true" if pattern.value else "false"
    return str(pattern)


def _collect_edges(body: list) -> list[CFGEdge]:
    """Extract CFG edges from a node's body."""
    edges = []
    for inst in body:
        if isinstance(inst, Route):
            for case in inst.cases:
                if isinstance(case.target, str):
                    edges.append(
                        CFGEdge(
                            target=case.target,
                            condition=_pattern_str(case.pattern),
                        )
                    )
                elif isinstance(case.target, NodeCall):
                    edges.append(
                        CFGEdge(
                            target=case.target.name,
                            condition=_pattern_str(case.pattern),
                        )
                    )
                elif isinstance(case.target, Return):
                    # Inline return — no edge, handled by _has_return
                    pass
        elif isinstance(inst, NodeCall):
            edges.append(CFGEdge(target=inst.name))
    return edges


def _has_return(body: list) -> bool:
    """Check if a body contains any return path."""
    for inst in body:
        if isinstance(inst, (Return, Unreachable)):
            return True
        if isinstance(inst, Route):
            for case in inst.cases:
                if isinstance(case.target, Return):
                    return True
    return False


def build_cfg(workflow: Workflow) -> CFG:
    cfg = CFG()

    if not workflow.nodes:
        raise ValueError("CFG error: workflow has no nodes")

    cfg.entry = workflow.nodes[0].name

    for node in workflow.nodes:
        cfg_node = CFGNode(
            label=node.name,
            instructions=list(node.body),
            terminal=_has_return(node.body),
            edges=_collect_edges(node.body),
            max_visits=node.max_visits,
        )
        cfg.nodes[node.name] = cfg_node

    # Validate: all edge targets must reference existing nodes
    for label, node in cfg.nodes.items():
        for edge in node.edges:
            if edge.target not in cfg.nodes:
                raise ValueError(
                    f"CFG error: edge from '{label}' to unknown node '{edge.target}'"
                )

    # Detect unreachable nodes via BFS from entry
    reachable = set()
    queue = [cfg.entry]
    while queue:
        current = queue.pop()
        if current in reachable:
            continue
        reachable.add(current)
        for edge in cfg.nodes[current].edges:
            if edge.target not in reachable:
                queue.append(edge.target)

    for label in cfg.nodes:
        if label not in reachable:
            print(f"warning: unreachable node '{label}'")

    return cfg
