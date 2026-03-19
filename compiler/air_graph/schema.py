from dataclasses import dataclass, field
from typing import Any, Optional

AIR_GRAPH_VERSION = "0.2"


@dataclass
class AirGraphCondition:
    kind: str  # "type", "enum", "bool", "else"
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
    inputs: list[str] = field(default_factory=list)
    outputs: list[AirGraphOutput] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class AirGraphEdge:
    target: str
    condition: Optional[AirGraphCondition] = None


@dataclass
class AirGraphNode:
    name: str
    operations: list[AirGraphOperation] = field(default_factory=list)
    route_variable: Optional[str] = None
    edges: list[AirGraphEdge] = field(default_factory=list)
    terminal: bool = False


@dataclass
class AirGraphParam:
    name: str
    type: str


@dataclass
class AirGraphWorkflow:
    name: str
    entry: str
    params: list[AirGraphParam] = field(default_factory=list)
    nodes: list[AirGraphNode] = field(default_factory=list)

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
                    elif cond.kind == "bool":
                        label = cond.value
                    elif cond.kind == "else":
                        label = "else"
                    else:
                        label = str(cond)
                    lines.append(f"  -> {edge.target}  [{label}]")
                else:
                    lines.append(f"  -> {edge.target}")
            lines.append("")
        return "\n".join(lines)
