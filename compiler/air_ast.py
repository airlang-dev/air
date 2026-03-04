from dataclasses import dataclass
from typing import List, Optional, Dict, Any

# -----------------------------
# Types
# -----------------------------


@dataclass
class Type:
    name: str
    is_list: bool = False


# -----------------------------
# Core Program
# -----------------------------


@dataclass
class Program:
    workflows: List["Workflow"]


@dataclass
class Workflow:
    name: str
    return_types: List[Type]
    blocks: List["Block"]
    fault_handler: Optional["Block"]


@dataclass
class Block:
    label: str
    instructions: List["Instruction"]


# -----------------------------
# Instructions
# -----------------------------


class Instruction:
    pass


@dataclass
class Assign(Instruction):
    targets: List[str]
    value: "Expression"


@dataclass
class Route(Instruction):
    value: str
    cases: List["RouteCase"]


@dataclass
class RouteCase:
    pattern: "Pattern"
    target: str


@dataclass
class Parallel(Instruction):
    branches: List[Instruction]


@dataclass
class Loop(Instruction):
    name: str
    max_iterations: int
    body: List[Instruction]


@dataclass
class Return(Instruction):
    value: "Expression"


class Continue(Instruction):
    pass


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


class TypePattern:
    def __init__(self, name, is_list=False):
        self.name = name
        self.is_list = is_list

    def __repr__(self):
        if self.is_list:
            return f"TypePattern(name='{self.name}', is_list=True)"
        return f"TypePattern(name='{self.name}', is_list=False)"


class DefaultPattern(Pattern):
    pass


# -----------------------------
# Expressions
# -----------------------------


class Expression:
    pass


@dataclass
class Variable(Expression):
    name: str


@dataclass
class LLMCall(Expression):
    prompt: str


@dataclass
class ToolCall(Expression):
    name: str
    args: List[str]


@dataclass
class Transform(Expression):
    input: str
    target_type: Type
    via: Optional[LLMCall]


@dataclass
class Verify(Expression):
    input: str
    rule: str


@dataclass
class Aggregate(Expression):
    inputs: List[str]
    strategy: str


@dataclass
class Gate(Expression):
    input: str


@dataclass
class Decide(Expression):
    provider: str
    input: Optional[str]


@dataclass
class Constructor(Expression):
    type_name: str
    fields: Dict[str, Any]
