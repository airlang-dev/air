from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

AIR_GRAPH_VERSION = "0.1"


@dataclass
class AirGraphCondition:
    kind: str  # "type", "enum", "continue"
    name: Optional[str] = None
    value: Optional[str] = None
    is_list: bool = False


@dataclass
class AirGraphOutput:
    name: str
    type: Optional[str] = None


@dataclass
class AirGraphOperation:
    type: str
    inputs: List[str] = field(default_factory=list)
    outputs: List[AirGraphOutput] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AirGraphEdge:
    target: str
    condition: Optional[AirGraphCondition] = None


@dataclass
class AirGraphNode:
    name: str
    operations: List[AirGraphOperation] = field(default_factory=list)
    route_variable: Optional[str] = None
    edges: List[AirGraphEdge] = field(default_factory=list)
    terminal: bool = False


@dataclass
class AirGraphWorkflow:
    name: str
    entry: str
    nodes: List[AirGraphNode] = field(default_factory=list)

    def __repr__(self):
        lines = [f"AirGraphWorkflow({self.name!r}, entry={self.entry!r})\n"]
        for node in self.nodes:
            lines.append(f"AirGraphNode({node.name!r})")
            for op in node.operations:
                attrs = f"  {op.params}" if op.params else ""
                outs = [f"{o.name}:{o.type}" if o.type else o.name for o in op.outputs]
                lines.append(f"  {op.type}: {op.inputs} -> {outs}{attrs}")
            if node.route_variable:
                lines.append(f"  route: {node.route_variable}")
            if node.terminal:
                lines.append("  (terminal)")
            for edge in node.edges:
                cond = edge.condition
                if cond:
                    if cond.kind == "type":
                        label = f"{cond.name}[]" if cond.is_list else cond.name
                    elif cond.kind == "enum":
                        label = cond.value
                    else:
                        label = "continue"
                    lines.append(f"  -> {edge.target}  [{label}]")
                else:
                    lines.append(f"  -> {edge.target}")
            lines.append("")
        return "\n".join(lines)
