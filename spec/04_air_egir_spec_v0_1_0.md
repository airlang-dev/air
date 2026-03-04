# AIR Execution Graph Intermediate Representation Specification
Version: 0.1.0

## 1. Purpose

The Execution Graph Intermediate Representation (EGIR) is the runtime-ready
representation of an AIR workflow.

Pipeline:

AIR source → AST → CFG → EGIR → Agent VM

CFG expresses control flow.

EGIR expresses executable operations and data flow.

The Agent VM executes EGIR nodes.

---

## 2. EGIR Model

EGIR is a directed graph composed of execution nodes and edges.

```

EGIR {
  nodes: Map<String, ExecNode>
}

```

Each node corresponds to a workflow block.

Edges represent control flow transitions.

---

## 3. ExecNode

```

ExecNode {
  id: String
  operations: List<Operation>
  edges: List<ExecEdge>
  terminal: Boolean
}

```

Fields:

| Field | Description |
|------|-------------|
| id | node identifier (block label) |
| operations | executable operations |
| edges | outgoing execution edges |
| terminal | whether the node terminates execution |

Operations are derived from AST instructions.

---

## 4. ExecEdge

```

ExecEdge {
  target: String
  condition: Optional<String>
}

```

Fields:

| Field | Description |
|------|-------------|
| target | destination node |
| condition | routing condition |

Edges correspond directly to CFG edges.

---

## 5. Operation Model

Each executable instruction becomes an Operation.

```

Operation {
  type: OperationType
  inputs: List<String>
  outputs: List<String>
  attributes: Map<String, Any>
}

```

---

## 6. Operation Types

### LLM

Represents a language model call.

```

Operation {
  type: "llm"
  inputs: []
  outputs: ["summary"]
  attributes: { prompt: "summarize_aurora" }
}

```

---

### Transform

Represents structured extraction or transformation.

```

Operation {
  type: "transform"
  inputs: ["summary"]
  outputs: ["claims"]
  attributes: {
    target_type: "Claim[]",
    via: "extract_claims"
  }
}

```

---

### Verify

Represents a verification rule.

```

Operation {
  type: "verify"
  inputs: ["claims"]
  outputs: ["verdict", "evidence"]
  attributes: { rule: "product_existence" }
}

```

---

### Aggregate

Represents consensus aggregation.

```

Operation {
  type: "aggregate"
  inputs: ["v1", "v2", "v3"]
  outputs: ["consensus"]
  attributes: { strategy: "majority" }
}

```

---

### Gate

Maps consensus/verdict to Outcome.

```

Operation {
  type: "gate"
  inputs: ["consensus"]
  outputs: ["outcome"]
}

```

---

### Decide

Represents external decision providers.

```

Operation {
  type: "decide"
  inputs: ["summary"]
  outputs: ["message", "outcome"]
  attributes: { provider: "human_reviewer" }
}

```

---

### Return

Marks terminal execution.

```

Operation {
  type: "return"
  inputs: []
  outputs: []
  attributes: { type: "Artifact" }
}

```

---

## 7. Mapping From CFG

Each CFG node becomes an ExecNode.

Operations are produced by translating AST instructions.

CFG edges become ExecEdges.

Example:

CFG:

```

verification
-> publish [PROCEED]
-> review  [ESCALATE]

```

EGIR:

```

ExecNode("verification")
edges:
publish [PROCEED]
review  [ESCALATE]

```

---

## 8. Execution Semantics

The Agent VM executes EGIR as follows:

1. Start at entry node.
2. Execute node operations sequentially.
3. Evaluate route condition.
4. Follow matching edge.
5. Continue until terminal node.

---

## 9. Parallel Semantics

Parallel blocks produce multiple operations inside a node.

Execution engines may schedule them concurrently.

---

## 10. Guarantees

EGIR assumes CFG validation has already ensured:

- no unreachable nodes
- no unknown targets
- no dead-end cycles
- terminal correctness

Therefore EGIR is safe for execution.
