# AIR Abstract Syntax Tree Specification
Version: 0.1.0

This document defines the Abstract Syntax Tree (AST) representation for AIR programs.

The AST is the structured representation produced after parsing and semantic validation. It removes grammar artifacts and represents AIR programs in a form suitable for analysis and compilation.

The AST is the input for:

- type checking
- control-flow analysis
- EGIR lowering
- execution planning

---

# 1. Program

Top-level container.

Program
└── workflows: [Workflow]

AIR v0.1 typically contains a single workflow per file.

---

# 2. Workflow

Represents an AIR workflow definition.

Workflow
├── name: string
├── return_types: [Type]
├── blocks: [Block]
└── fault_handler: Block?

Example:

workflow Aurora_Fact_Check -> Artifact | Fault

---

# 3. Block

A block corresponds to a labelled sequence of instructions.

Block
├── label: string
└── instructions: [Instruction]

Example:

verification:
parallel { ... }

---

# 4. Instruction Hierarchy

Instruction (abstract)

Subtypes:

Assign
Route
Parallel
Loop
Return
Continue
Unreachable

---

# 5. Assign

Represents SSA assignment.

Assign
├── targets: [Variable]
└── value: Expression

Examples:

summary = llm(summarize_aurora)

v1, _ = verify(claims, product_existence)

---

# 6. Route

Represents control-flow branching.

Route
├── value: Variable
└── cases: [RouteCase]

RouteCase
├── pattern: Pattern
└── target: Target

Example:

route(outcome) {
PROCEED -> publish
ESCALATE -> review
}

---

# 7. Pattern

Pattern (abstract)

Subtypes:

EnumPattern
TypePattern
DefaultPattern

Example:

Fault -> regenerate

---

# 8. Parallel

Represents concurrent execution.

Parallel
└── branches: [Instruction]

Example:

parallel {
v1,_ = verify(...)
v2,_ = verify(...)
}

---

# 9. Loop

Represents bounded retry loops.

Loop
├── name: string
├── max_iterations: int
└── body: [Instruction]

Example:

loop retry_generation [max=2] { ... }

---

# 10. Return

Represents workflow termination.

Return
└── value: Expression

Example:

return Artifact(...)

---

# 11. Continue

Loop control instruction.

Continue

---

# 12. Unreachable

Indicates unreachable code path.

Unreachable

---

# 13. Expression Hierarchy

Expression (abstract)

Subtypes:

LLMCall
ToolCall
Transform
Verify
Aggregate
Gate
Decide
Constructor
Variable

---

# 14. LLMCall

LLMCall
└── prompt: Asset

Example:

llm(summarize_aurora)

---

# 15. ToolCall

ToolCall
├── name: Asset
└── args: [Variable]

---

# 16. Transform

Transform
├── input: Variable
├── target_type: Type
└── via: LLMCall?

Example:

transform(summary, Claim[]) via llm(extract_claims)

---

# 17. Verify

Verify
├── input: Variable
└── rule: Asset

Example:

verify(claims, product_existence)

---

# 18. Aggregate

Aggregate
├── inputs: [Variable]
└── strategy: Asset

Example:

aggregate([v1,v2,v3], majority)

---

# 19. Gate

Gate
└── input: Variable

---

# 20. Decide

Decide
├── provider: Asset
└── input: Variable?

Example:

decide(human_reviewer, summary)

---

# 21. Constructor

Represents structured values.

Constructor
├── type: Type
└── fields: [Field]

Field
├── name: string
└── value: Value

Example:

Artifact(
status="verified",
summary=summary
)

---

# 22. Type

Type
├── name: string
└── is_list: bool

Example:

Claim[]

---

# 23. Variable

Variable
└── name: string

---

# 24. Control Flow Semantics

Control flow is defined through:

route
continue
return

Blocks form nodes of the control-flow graph.

Routes define edges.

---

# 25. Lowering

The AST is lowered to EGIR (Execution Graph IR) for runtime execution.
