# AIR Control Flow Graph Specification
Version: 0.1.0

## 1. Purpose

The Control Flow Graph (CFG) is the intermediate representation that converts
structured AIR workflows into an explicit graph of execution nodes.

AIR source → AST → CFG → EGIR → Agent VM

The CFG represents control flow explicitly using nodes and edges.

Each workflow block becomes a node, and control flow constructs
(`route`, `loop`, `return`) create edges between nodes.

The CFG does not execute anything. It is purely a structural representation
of control flow.

---

## 2. CFG Model

### 2.1 CFG

A CFG represents the control flow of a single workflow.

```

CFG {
nodes: Map<String, CFGNode>
}

```

Each key in the map is the node label.

---

### 2.2 CFGNode

Each workflow block corresponds to exactly one CFG node.

```

CFGNode {
label: String
instructions: List<Instruction>
edges: List<CFGEdge>
terminal: Boolean
}

```

Fields:

| Field | Description |
|------|-------------|
| label | block label |
| instructions | AST instructions from the block |
| edges | outgoing control flow edges |
| terminal | true if node ends execution |

---

### 2.3 CFGEdge

Edges represent control flow transitions.

```

CFGEdge {
target: String
condition: Optional<String>
}

```

Fields:

| Field | Description |
|------|-------------|
| target | label of destination node |
| condition | optional routing condition |

Example:

```

verification → publish     [PROCEED]
verification → review      [ESCALATE]
verification → regenerate  [RETRY]
verification → abort       [HALT]

```

---

## 3. Node Construction

Each `Block` in the AIR AST becomes one CFGNode.

Example AST:

```

Block(label="verification")

```

Becomes:

```

CFGNode(label="verification")

```

Instructions from the block are copied into the node unchanged.

---

## 4. Control Flow Rules

Control flow edges are derived from specific instructions.

---

### 4.1 Route

A `route` instruction creates edges for each route case.

Example:

```

route(outcome) {
PROCEED  -> publish
ESCALATE -> review
RETRY    -> regenerate
HALT     -> abort
}

```

Produces edges:

```

verification → publish     [PROCEED]
verification → review      [ESCALATE]
verification → regenerate  [RETRY]
verification → abort       [HALT]

```

The edge condition is the string representation of the route pattern.

---

### 4.2 Return

A `return` instruction terminates execution.

Example:

```

return Artifact(...)

```

Effects:

```

node.terminal = true
node.edges = []

```

Terminal nodes must not have outgoing edges.

---

### 4.3 Loop

A `loop` instruction remains inside the node as a normal instruction.

However, routes that target `continue` create a self-edge.

Example:

```

route(claims2) {
Claim[] -> verification_retry
Fault   -> continue
}

```

Produces edges:

```

regenerate → verification_retry
regenerate → regenerate   [continue]

```

---

### 4.4 Parallel

Parallel blocks do not affect control flow.

Example:

```

parallel {
verify(...)
verify(...)
}

```

All instructions remain inside the same CFG node.

No additional nodes or edges are created.

---

## 5. Graph Validation

After building the CFG the compiler must validate:

### 5.1 Target existence

Every edge target must reference an existing node.

If not:

```

error: Unknown CFG target

```

---

### 5.2 Terminal nodes

Nodes marked as terminal must have zero outgoing edges.

---

### 5.3 Entry node

The workflow entry block must exist and must be the first node.

---

## 6. Expected CFG for Aurora Example

The Aurora workflow should produce a graph similar to:

```

entry
├─ regenerate
└─ verification

verification
├─ publish
├─ review
├─ regenerate
└─ abort

regenerate
└─ verification_retry

verification_retry
├─ publish_retry
├─ review
└─ abort

review
├─ publish
├─ abort
└─ regenerate

```

---

## 7. Compiler Stage

The CFG builder is the first stage that converts AIR into
an executable control-flow graph.

Pipeline:

```

AIR source
↓
Parser
↓
AST
↓
CFG Builder
↓
CFG

```

The CFG will later be lowered into EGIR.
