# Execution Graph Intermediate Representation
Version: 0.1.0

## 1. Purpose

EGIR (Execution Graph Intermediate Representation) is the executable form of an AIR workflow.

Compilation pipeline:

AIR source → AST → CFG → EGIR → Agent VM

EGIR converts the structured AIR workflow into a flat execution graph suitable for runtime interpretation.

The Agent VM executes EGIR nodes sequentially according to routing edges.

---

# 2. Design Goals

EGIR must be:

• deterministic
• minimal
• executable without additional inference
• independent of frontend syntax

All runtime information required for execution must be present in the graph.

The runtime must never infer missing semantics.

---

# 3. Workflow Structure

An EGIR workflow is a directed graph.

```

EGIRWorkflow

```

Fields:

| Field | Type | Description |
|------|------|-------------|
| name | string | workflow name |
| nodes | Map<string, ExecNode> | node table |
| entry | string | entry node name |

---

# 4. Execution Node

Each node represents a block of operations followed by routing.

```

ExecNode

```

Fields:

| Field | Type | Description |
|------|------|-------------|
| name | string | node identifier |
| operations | Operation[] | ordered list of operations |
| route_variable | string | variable used for routing |
| edges | Edge[] | outgoing control-flow edges |
| terminal | boolean | whether node terminates execution |

---

# 5. Edge

Edges define control flow transitions between nodes.

```

Edge

```

Fields:

| Field | Type | Description |
|------|------|-------------|
| condition | string | routing condition |
| target | string | destination node |

Examples:

```

PROCEED
ESCALATE
RETRY
HALT
Fault
Claim[]
continue

```

---

# 6. Operation

Operations are executable instructions.

```

Operation

```

Fields:

| Field | Type | Description |
|------|------|-------------|
| type | string | operation type |
| inputs | string[] | input variables |
| outputs | string[] | output variables |
| params | map | operation parameters |

---

# 7. Operation Types

Supported operations in EGIR v0.1:

| Operation | Description |
|----------|-------------|
| llm | language model invocation |
| transform | LLM-based extraction |
| verify | rule-based verification |
| aggregate | consensus computation |
| gate | verdict → outcome mapping |
| decide | external decision provider |
| return | workflow termination |

---

# 8. Example Node

Example EGIR node generated from AIR:

```

ExecNode("verification")

operations:
verify ["claims"] -> ["v1"] {rule: "product_existence"}
verify ["claims"] -> ["v2"] {rule: "link_validation"}
verify ["claims"] -> ["v3"] {rule: "compute_claim"}
aggregate ["v1","v2","v3"] -> ["consensus"] {strategy: "majority"}
gate ["consensus"] -> ["outcome"]

route_variable: "outcome"

edges:
PROCEED  → publish
ESCALATE → review
RETRY    → regenerate
HALT     → abort

```

---

# 9. Routing Semantics

Routing uses the node's `route_variable`.

```

value = variables[node.route_variable]

```

Edge selection:

```

for edge in node.edges:
if edge.condition == value:
next_node = edge.target

```

The runtime must not infer routing variables.

The variable must always be explicitly defined in the node.

---

# 10. Loop Representation

Loops are represented as self-edges.

Example:

```

Edge:
condition = "continue"
target = "regenerate"

```

This creates a loop back-edge.

Loop limits are enforced using metadata attached to nodes.

---

# 11. Terminal Nodes

Nodes that contain a `return` operation are terminal.

```

terminal = true

```

Terminal nodes must not have outgoing edges.

---

# 12. Example Workflow Graph

Simplified EGIR:

```

entry
→ verification [Claim[]]
→ regenerate   [Fault]

verification
→ publish  [PROCEED]
→ review   [ESCALATE]
→ regenerate [RETRY]
→ abort [HALT]

publish
(terminal)

abort
(terminal)

```

---

# 13. Runtime Responsibilities

The Agent VM must:

• execute node operations sequentially
• maintain variable store
• evaluate routing conditions
• follow edges
• terminate on return

The runtime must not modify graph structure.

---

# 14. Compiler Responsibilities

The compiler must ensure EGIR is valid.

Validation includes:

• no unreachable nodes
• no dead-end cycles
• correct routing variables
• valid edge targets
• terminal nodes have no outgoing edges

EGIR must be executable without additional semantic analysis.

---

# 15. Future Extensions

Future EGIR versions may support:

• distributed execution
• streaming outputs
• dynamic node scaling
• checkpointing
• typed variable storage
