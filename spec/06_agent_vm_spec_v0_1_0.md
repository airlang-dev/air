# Agent Virtual Machine
Version: 0.1.0

## 1. Purpose

The Agent Virtual Machine (AVM) executes AIR workflows compiled into EGIR.

Pipeline:

AIR source → AST → CFG → EGIR → Agent VM

The AVM interprets the EGIR execution graph and orchestrates:

- LLM calls
- verification rules
- aggregation
- decisions
- routing

The AVM guarantees deterministic execution of the workflow structure
even though underlying model calls may be nondeterministic.

---

## 2. Execution Model

The AVM executes EGIR nodes sequentially according to graph edges.

Execution begins at the **entry node** and continues until a **terminal node** is reached.

Execution cycle:

```

load node
execute operations
evaluate routing
follow edge
repeat

```

---

## 3. Runtime State

The AVM maintains a workflow execution state.

```

ExecutionState {
variables: Map<String, Value>
current_node: String
trace: List<ExecutionEvent>
}

```

Fields:

| Field | Description |
|------|-------------|
| variables | runtime variable store |
| current_node | node currently executing |
| trace | execution log |

Variables persist across nodes.

---

## 4. Node Execution

Each node executes its operations in order.

Example node:

```

ExecNode('verification')
verify
verify
verify
aggregate
gate

```

Execution order is deterministic.

Pseudo-code:

```

for op in node.operations:
execute(op)

```

---

## 5. Operation Execution

### LLM

```

Operation(type="llm")

```

Behavior:

```

result = llm_adapter(prompt)
state.variables[output] = result

```

Adapters abstract the actual model provider.

---

### Transform

```

Operation(type="transform")

```

Behavior:

```

result = extraction_model(input)
state.variables[output] = result

```

Schema validation must occur before storing the result.

If validation fails, a `Fault` value is produced.

---

### Verify

```

Operation(type="verify")

```

Behavior:

```

(verdict, evidence) = rule_engine(input)
state.variables[output] = verdict

```

Evidence may optionally be stored.

---

### Aggregate

```

Operation(type="aggregate")

```

Behavior:

```

consensus = aggregation_strategy(inputs)
state.variables[output] = consensus

```

---

### Gate

```

Operation(type="gate")

```

Behavior:

```

outcome = verdict_mapping(input)
state.variables[output] = outcome

```

Outcome values:

```

PROCEED
ESCALATE
RETRY
HALT

```

---

### Decide

Represents external decision providers (human, policy engine).

```

Operation(type="decide")

```

Behavior:

```

(message, outcome) = decision_provider(input)
state.variables[outputs] = values

```

The VM waits until a decision is returned.

---

### Return

```

Operation(type="return")

```

Behavior:

```

terminate execution
return artifact or fault

```

---

## 6. Routing

After operations complete, the VM evaluates node edges.

Example:

```

-> publish [PROCEED]
-> review  [ESCALATE]

```

Routing algorithm:

```

value = state.variables[route_variable]

for edge in node.edges:
if edge.condition == value:
next_node = edge.target

```

---

## 7. Loop Execution

Loops are represented as self-edges.

Example:

```

regenerate → regenerate [continue]

```

The VM simply follows the edge.

Loop limits are enforced by counters defined in the EGIR metadata.

If the limit is exceeded:

```

produce Fault(reason="loop limit exceeded")

```

---

## 8. Parallel Execution

Parallel instructions are executed concurrently.

```

parallel {
verify(...)
verify(...)
}

```

The VM may schedule operations concurrently.

All operations must complete before proceeding.

---

## 9. Fault Handling

Faults propagate as values.

If an operation produces a Fault:

```

route(Fault)

```

Fault routing follows the same mechanism as Outcome routing.

If no route matches, the workflow terminates with the Fault.

---

## 10. Execution Trace

The AVM records execution events.

```

ExecutionEvent {
node
operation
inputs
outputs
timestamp
}

```

This provides observability and debugging.

---

## 11. Determinism Guarantees

The AVM guarantees:

- deterministic control flow
- deterministic variable assignment
- deterministic routing

Nondeterminism exists only inside external operations
(LLM calls, human decisions).

---

## 12. Safety Guarantees

The AVM assumes the compiler ensured:

- no dead-end cycles
- reachable terminal nodes
- valid routing
- variable existence

Therefore execution cannot enter an undefined state.

---

## 13. Runtime Architecture

Typical deployment architecture:

```

Agent VM
│
├─ LLM adapters
├─ Tool adapters
├─ Rule engine
├─ Decision providers
└─ Trace storage

```

The VM is platform-independent.

Backends (LangGraph, Bedrock, Dify) may compile EGIR into
native runtime constructs.

---

## 14. Future Extensions

Planned features:

- distributed execution
- persistent workflow state
- checkpointing
- streaming operations
- dynamic node scaling
