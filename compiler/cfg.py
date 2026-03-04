from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CFGEdge:
    target: str
    condition: Optional[str] = None


@dataclass
class CFGNode:
    label: str
    instructions: list = field(default_factory=list)
    edges: List[CFGEdge] = field(default_factory=list)
    terminal: bool = False


@dataclass
class CFG:
    nodes: Dict[str, CFGNode] = field(default_factory=dict)

    def __repr__(self):
        lines = []
        for label, node in self.nodes.items():
            lines.append(label)
            if node.terminal:
                lines.append("  (terminal)")
            for edge in node.edges:
                if edge.condition:
                    lines.append(f"  -> {edge.target}  [{edge.condition}]")
                else:
                    lines.append(f"  -> {edge.target}")
            lines.append("")
        return "\n".join(lines)
