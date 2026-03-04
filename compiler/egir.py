from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Operation:
    type: str
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecEdge:
    target: str
    condition: Optional[str] = None


@dataclass
class ExecNode:
    name: str
    operations: List[Operation] = field(default_factory=list)
    route_variable: Optional[str] = None
    edges: List[ExecEdge] = field(default_factory=list)
    terminal: bool = False


@dataclass
class EGIRWorkflow:
    name: str
    entry: str
    nodes: List[ExecNode] = field(default_factory=list)

    def __repr__(self):
        lines = [f"EGIRWorkflow({self.name!r}, entry={self.entry!r})\n"]
        for node in self.nodes:
            lines.append(f"ExecNode({node.name!r})")
            for op in node.operations:
                attrs = f"  {op.params}" if op.params else ""
                lines.append(f"  {op.type}: {op.inputs} -> {op.outputs}{attrs}")
            if node.route_variable:
                lines.append(f"  route: {node.route_variable}")
            if node.terminal:
                lines.append("  (terminal)")
            for edge in node.edges:
                if edge.condition:
                    lines.append(f"  -> {edge.target}  [{edge.condition}]")
                else:
                    lines.append(f"  -> {edge.target}")
            lines.append("")
        return "\n".join(lines)
