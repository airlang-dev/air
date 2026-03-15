from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CFGEdge:
    target: str
    condition: Optional[str] = None


@dataclass
class CFGNode:
    label: str
    instructions: list = field(default_factory=list)
    edges: list[CFGEdge] = field(default_factory=list)
    terminal: bool = False


@dataclass
class CFG:
    entry: str = ""
    nodes: dict[str, CFGNode] = field(default_factory=dict)

    def __repr__(self):
        lines = []
        for label, node in self.nodes.items():
            prefix = "* " if label == self.entry else "  "
            lines.append(f"{prefix}{label}")
            if node.terminal:
                lines.append("    (terminal)")
            for edge in node.edges:
                if edge.condition:
                    lines.append(f"    -> {edge.target}  [{edge.condition}]")
                else:
                    lines.append(f"    -> {edge.target}")
            lines.append("")
        return "\n".join(lines)
