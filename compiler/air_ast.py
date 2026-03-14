from dataclasses import dataclass, field
from typing import Optional, Union


# -----------------------------
# Types
# -----------------------------


@dataclass
class Type:
    name: str
    is_list: bool = False


# -----------------------------
# Values (used in args, fields)
# -----------------------------


@dataclass
class Identifier:
    """A bare name: summary, claims, Fault."""
    name: str


@dataclass
class DottedName:
    """A dotted access: result.consensus, Fault.reason."""
    object: str
    attribute: str


@dataclass
class ListLiteral:
    """A list expression: [history, r1, r2]."""
    items: list["Arg"]


# An argument in a function call or list
Arg = Union[Identifier, DottedName, ListLiteral]


# A value in a constructor field
Value = Union[Identifier, DottedName, str, ListLiteral]


# -----------------------------
# Core Program
# -----------------------------


@dataclass
class Param:
    """Workflow input parameter: name: Type."""
    name: str
    type: Type


@dataclass
class Program:
    version: str
    mode: Optional[str]
    workflows: list["Workflow"]


@dataclass
class Workflow:
    name: str
    params: list[Param]
    return_types: list[Type]
    nodes: list["Node"]


@dataclass
class Node:
    name: str
    params: list[str] = field(default_factory=list)
    max_visits: Optional[int] = None
    is_fallback: bool = False
    body: list["Instruction"] = field(default_factory=list)


# -----------------------------
# Instructions
# -----------------------------


class Instruction:
    pass


@dataclass
class Assign(Instruction):
    targets: list[str]
    value: "Expression"


@dataclass
class Route(Instruction):
    value: Arg
    cases: list["RouteCase"]


@dataclass
class NodeCall(Instruction):
    """Unconditional transition: validate(claims, summary)."""
    name: str
    args: list[Arg] = field(default_factory=list)


@dataclass
class RouteCase:
    pattern: "Pattern"
    target: Union[NodeCall, "Return", str]


@dataclass
class Parallel(Instruction):
    branches: list[Instruction]
    partial: bool = False


@dataclass
class Return(Instruction):
    value: "Expression"


class Unreachable(Instruction):
    pass


# -----------------------------
# Patterns
# -----------------------------


class Pattern:
    pass


@dataclass
class EnumPattern(Pattern):
    value: str


@dataclass
class TypePattern(Pattern):
    name: str
    is_list: bool = False


class ElsePattern(Pattern):
    pass


@dataclass
class BoolPattern(Pattern):
    value: bool


# -----------------------------
# Expressions
# -----------------------------


class Expression:
    pass


@dataclass
class LLMCall(Expression):
    prompt: str
    args: list[Arg] = field(default_factory=list)


@dataclass
class ToolCall(Expression):
    name: str
    args: list[Arg] = field(default_factory=list)


@dataclass
class Transform(Expression):
    input: Arg
    target_type: Type
    via: Optional[LLMCall] = None


@dataclass
class Verify(Expression):
    input: Arg
    rule: Arg


@dataclass
class Aggregate(Expression):
    inputs: list[Arg]
    strategy: str


@dataclass
class Gate(Expression):
    input: "Expression"


@dataclass
class Decide(Expression):
    provider: str
    args: list[Arg] = field(default_factory=list)


@dataclass
class Session(Expression):
    args: list[Arg] = field(default_factory=list)


@dataclass
class Constructor(Expression):
    type_name: str
    fields: dict[str, Value]
