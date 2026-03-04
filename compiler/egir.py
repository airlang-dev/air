from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Operation:
    type: str
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecEdge:
    target: str
    condition: Optional[str] = None


@dataclass
class ExecNode:
    id: str
    operations: List[Operation] = field(default_factory=list)
    edges: List[ExecEdge] = field(default_factory=list)
    terminal: bool = False


@dataclass
class EGIR:
    nodes: Dict[str, ExecNode] = field(default_factory=dict)

    def __repr__(self):
        lines = []
        for nid, node in self.nodes.items():
            lines.append(f"ExecNode({nid!r})")
            for op in node.operations:
                attrs = f"  {op.attributes}" if op.attributes else ""
                lines.append(f"  {op.type}: {op.inputs} -> {op.outputs}{attrs}")
            if node.terminal:
                lines.append("  (terminal)")
            for edge in node.edges:
                if edge.condition:
                    lines.append(f"  -> {edge.target}  [{edge.condition}]")
                else:
                    lines.append(f"  -> {edge.target}")
            lines.append("")
        return "\n".join(lines)
