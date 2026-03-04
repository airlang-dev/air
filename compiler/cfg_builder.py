from air_ast import (
    Workflow,
    Route,
    Return,
    Loop,
    Parallel,
    EnumPattern,
    TypePattern,
    DefaultPattern,
)
from cfg import CFG, CFGNode, CFGEdge


def _pattern_str(pattern) -> str:
    if isinstance(pattern, EnumPattern):
        return pattern.value
    if isinstance(pattern, TypePattern):
        return f"{pattern.name}[]" if pattern.is_list else pattern.name
    if isinstance(pattern, DefaultPattern):
        return "default"
    return str(pattern)


def _collect_edges(instructions: list, node_label: str) -> list[CFGEdge]:
    """Extract CFG edges from a list of instructions."""
    edges = []
    for inst in instructions:
        if isinstance(inst, Route):
            for case in inst.cases:
                if case.target == "continue":
                    edges.append(CFGEdge(target=node_label, condition="continue"))
                else:
                    edges.append(
                        CFGEdge(
                            target=case.target, condition=_pattern_str(case.pattern)
                        )
                    )
        elif isinstance(inst, Loop):
            edges.extend(_collect_edges(inst.body, node_label))
        elif isinstance(inst, Parallel):
            edges.extend(_collect_edges(inst.branches, node_label))
    return edges


def _is_terminal(instructions: list) -> bool:
    """Check if a block ends with a return instruction."""
    for inst in instructions:
        if isinstance(inst, Return):
            return True
        if isinstance(inst, Loop):
            if _is_terminal(inst.body):
                return True
        if isinstance(inst, Parallel):
            if _is_terminal(inst.branches):
                return True
    return False


def build_cfg(workflow: Workflow) -> CFG:
    cfg = CFG()

    # Build nodes from all blocks
    all_blocks = list(workflow.blocks)
    if workflow.fault_handler:
        all_blocks.append(workflow.fault_handler)

    for block in all_blocks:
        node = CFGNode(
            label=block.label,
            instructions=list(block.instructions),
        )
        node.terminal = _is_terminal(block.instructions)
        if node.terminal:
            node.edges = []
        else:
            node.edges = _collect_edges(block.instructions, block.label)
        cfg.nodes[block.label] = node

    # Validate: all edge targets must reference existing nodes
    for label, node in cfg.nodes.items():
        for edge in node.edges:
            if edge.target not in cfg.nodes:
                raise ValueError(f"CFG error: unknown target '{edge.target}'")

    # Validate: terminal nodes must have zero edges
    for label, node in cfg.nodes.items():
        if node.terminal and node.edges:
            raise ValueError(f"CFG error: terminal node '{label}' has outgoing edges")

    # Validate: entry node must exist and be first
    if not cfg.nodes:
        raise ValueError("CFG error: no nodes in graph")
    first_label = next(iter(cfg.nodes))
    if first_label != "entry":
        raise ValueError(f"CFG error: first node must be 'entry', got '{first_label}'")

    # Detect unreachable blocks via BFS from entry
    reachable = set()
    queue = ["entry"]
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
            print(f"warning: unreachable block '{label}'")

    # Detect dead-end blocks (reachable but no path to any terminal node)
    # Step 1: Build reverse graph
    reverse = {label: [] for label in cfg.nodes}
    for label, node in cfg.nodes.items():
        for edge in node.edges:
            reverse[edge.target].append(label)

    # Step 2: BFS backwards from all terminal nodes
    terminating = set()
    queue = [label for label, node in cfg.nodes.items() if node.terminal]
    while queue:
        current = queue.pop()
        if current in terminating:
            continue
        terminating.add(current)
        for predecessor in reverse[current]:
            if predecessor not in terminating:
                queue.append(predecessor)

    # Step 3: Dead ends = reachable but not terminating
    dead_ends = [
        label for label in cfg.nodes if label in reachable and label not in terminating
    ]
    if dead_ends:
        for label in dead_ends:
            print(f"error: dead-end block '{label}'")
        raise ValueError("CFG error: dead-end blocks detected")

    return cfg
