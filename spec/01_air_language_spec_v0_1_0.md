# AIR Language Specification
Version: 0.1.0

## 1. Overview

**AIR** (**A**gentic **I**ntermediate **R**epresentation) is a language for describing **AI workflows** in a structured, portable, and governed form.

AIR programs define how:

* language models generate content
* structured information is extracted
* claims are verified
* decisions are made
* humans or automated systems intervene when necessary

AIR functions as an **intermediate representation for AI orchestration**, similar to how LLVM IR represents compiled programs.

AIR workflows compile into execution graphs executed by the **Agent VM** or compatible runtimes.

AIR stack:

```
DSL / Visual / NL
        ↓
   AIR Compiler
        ↓
        AIR
        ↓
       EGIR
        ↓
      Agent VM
        ↓
   LLMs / Tools / Decision Providers
```

---

# 2. Terminology

### AIR Program

A file containing one or more workflows.

### AIR Workflow

The executable unit of AIR.

A workflow defines:

* instructions
* control flow
* data flow
* failure handling
* return values

---

# 3. Design Principles

### Deterministic Orchestration

AI models are nondeterministic. AIR ensures orchestration logic is deterministic.

### Explicit Stochastic Operations

Only two instructions are nondeterministic:

```
llm
decide
```

All other instructions are deterministic.

### Governance by Construction

Model outputs must be verified before influencing control flow.

Typical pipeline:

```
generate → extract → verify → gate → route
```

### Portability

AIR workflows can compile to different orchestration platforms.

### Auditability

All reasoning, verification, and decisions are explicitly represented.

---

# 4. Program Structure

An AIR program declares a language version and one or more workflows.

```
@air 0.1

workflow Aurora_Fact_Check -> Artifact | Fault
```

The workflow return type defines allowed terminal outputs.

---

# 5. Blocks and Labels

AIR uses **basic blocks** defined by labels.

```
publish:
return Artifact(summary=summary)
```

Rules:

* labels must be unique
* labels define block entry points
* instructions within a block execute sequentially
* blocks must end with a terminator
* blocks cannot implicitly fall through

Allowed terminators:

```
route
return
unreachable
```

The first instructions in a workflow form the **entry block**.

---

# 6. Variables

AIR uses **single assignment semantics (SSA)**.

Variables cannot be reassigned.

Valid:

```
summary = llm(prompt)
claims = transform(summary, Claim[])
```

Invalid:

```
summary = llm(prompt)
summary = llm(prompt2)
```

---

## 6.1 SSA Inside Loops

Variables defined inside a loop create new SSA bindings for each iteration.

Example:

```
loop retry [max=3] {
  summary2 = llm(regenerate_summary)
  claims2 = transform(summary2, Claim[])
            via llm(extract_claims)
}
```

Compiler interpretation:

```
iteration 1: summary2_1, claims2_1
iteration 2: summary2_2, claims2_2
iteration 3: summary2_3, claims2_3
```

When control exits the loop through a route to an external label, the values from the exiting iteration become visible to subsequent blocks.

External references use the original variable name:

```
claims2
summary2
```

The compiler resolves them to the appropriate iteration internally.

This is equivalent to hidden phi-node resolution. AIR keeps the syntax simple.

---

# 7. Instruction Categories

### Operational

```
llm
tool
transform
```

### Governance

```
verify
aggregate
gate
```

### Decision

```
decide
```

### Orchestration

```
route
parallel
loop
```

### Terminators

```
return
unreachable
```

---

# 8. LLM Instruction

Invokes a language model.

```
result = llm(prompt)
```

Example:

```
summary = llm(summarize_aurora)
```

Return type:

```
Message
```

Transport failures (timeouts, rate limits) are handled by the runtime. AIR only observes the semantic output.

---

# 9. Tool Instruction

Invokes an external deterministic capability.

```
result = tool(tool_name, inputs...)
```

Example:

```
docs = tool(fetch_product_docs, product_id)
```

Return type:

```
Artifact | Fault
```

A tool invocation can fail for reasons beyond transient transport errors:

```
API error
database unavailable
file not found
permission denied
invalid query
```

The runtime may retry transient failures according to its configured retry policy. After retries are exhausted, failure produces:

```
Fault(reason="tool invocation failed")
```

Tool faults follow standard fault precedence (see Section 18).

Example with fault routing:

```
docs = tool(fetch_product_docs, product_id)

route(docs) {
  Artifact -> verification
  Fault    -> abort
}
```

---

# 10. Transform Instruction

Performs deterministic type conversion.

```
value = transform(input, TargetType)
```

Example:

```
numbers = transform(text, Number[])
```

Type signature:

```
transform(T, U) → U
```

---

## 10.1 LLM-Assisted Transform

When inference is required, transform may call an LLM.

```
claims = transform(summary, Claim[])
         via llm(extract_claims)
```

Execution model:

```
LLM extraction
   ↓
schema validation
   ↓
success → Claim[]
failure → retry
```

After bounded retries, failure produces:

```
Fault
```

Type signature:

```
transform(... via llm(...)) → U | Fault
```

The retry limit is a runtime configuration, not a language-level setting. The language requires only that retries are bounded.

---

# 11. Verify Instruction

Evaluates claims against verification rules.

```
verdict, evidence = verify(input, rule)
```

Example:

```
verdict, evidence = verify(claims, product_existence)
```

Evidence may be discarded:

```
verdict, _ = verify(claims, product_existence)
```

Verdict values:

```
PASS
FAIL
UNCERTAIN
```

---

# 12. Aggregate Instruction

Combines multiple verification results.

```
consensus = aggregate([values], strategy)
```

Example:

```
consensus = aggregate([v1, v2, v3], majority)
```

Built-in strategies:

```
unanimous
majority
union
```

### Strategy Semantics

#### unanimous

All verdicts must agree.

```
all PASS      → PASS
any FAIL      → FAIL
any UNCERTAIN → UNCERTAIN
```

#### majority

The majority verdict wins.

```
majority PASS → PASS
majority FAIL → FAIL
otherwise     → UNCERTAIN
```

#### union

Combines all evidence and preserves the full verdict distribution. The resulting Consensus contains all individual verdicts and evidence without reduction.

```
verdicts: [PASS, FAIL, PASS]
evidence: [e1, e2, e3]
```

Return type:

```
Consensus
```

Consensus structure:

```
Consensus {
  verdicts: Verdict[]
  evidence: Evidence[]
}
```

---

# 13. Gate Instruction

Converts verification outcomes into workflow outcomes.

```
gate(Verdict | Consensus) → Outcome
```

Outcome values:

```
Outcome {
  PROCEED
  RETRY
  ESCALATE
  HALT
}
```

Mapping for a single Verdict:

```
PASS      → PROCEED
FAIL      → ESCALATE
UNCERTAIN → RETRY
```

Mapping for Consensus:

Gate applies **conservative evaluation**. A single failure in a consensus overrides multiple successes.

```
any FAIL      → ESCALATE
any UNCERTAIN → RETRY
otherwise     → PROCEED
```

Example:

```
PASS PASS FAIL → ESCALATE
```

This design prioritizes safety in verification workflows.

---

# 14. Decide Instruction

Obtains a decision from an external decision provider.

```
message, outcome = decide(provider, input...)
```

Example:

```
msg, outcome = decide(human_reviewer, summary)
```

Return values:

```
Message?, Outcome
```

The Message is optional. Some providers may return only an Outcome.

Examples:

```
_, outcome = decide(risk_policy, claims)
msg, outcome = decide(human_reviewer, summary)
```

The provider may represent:

* a human reviewer
* an AI reviewer
* a policy engine
* an algorithmic decision system

Providers are defined as external assets.

Transport or availability failures of the provider are handled entirely by the runtime. AIR never observes them. If a provider fails to respond, the runtime resolves the situation according to its configured policy (timeout, fallback outcome, escalation, or workflow abort).

---

# 15. Route Instruction

Performs conditional branching.

```
route(value) {
  pattern -> label
}
```

Patterns are evaluated top-to-bottom. The first matching pattern is selected.

Example:

```
route(outcome) {
  PROCEED  -> publish
  ESCALATE -> review
}
```

Patterns may match:

* enum values
* types
* default

Route patterns narrow union types by matching the runtime type.

Example:

```
route(claims) {
  Claim[] -> verify
  Fault   -> retry
}
```

---

## 15.1 Exhaustiveness

Routes must be exhaustive.

Valid if:

```
all cases are covered
or
default exists
```

A non-exhaustive route without a default is a compile error.

---

# 16. Parallel Block

Executes instructions concurrently.

```
parallel {

  v1, _ = verify(claims, product_existence)
  v2, _ = verify(claims, link_validation)

}
```

Parallel blocks are deterministic because each branch produces distinct variables.

Rules:

* variables must be distinct
* execution continues after all branches finish
* variables produced inside a parallel block become visible after the block completes

---

# 17. Loop Construct

Loops must be bounded.

```
loop name [max=N] {
  statements
}
```

Example:

```
loop retry_generation [max=2] {

  summary2 = llm(regenerate_summary)

  claims2 = transform(summary2, Claim[])
            via llm(extract_claims)

  route(claims2) {
    Claim[] -> verification_retry
    Fault   -> continue
  }

}
```

Rules:

```
max is mandatory
```

### Implicit Control Target

A loop defines one implicit control target:

```
continue — restart the next iteration of the loop
```

Loops do not define an implicit break target. To exit a loop, control must route to a label outside the loop block.

### Loop Exit

A loop exits via one of:

* a route to an external label
* a return statement
* loop limit Fault

There is no implicit "after loop" position.

### Iteration Model

```
iteration++
execute loop body
continue → next iteration
route to external label → exit loop
return → terminate workflow
iteration > max → Fault
```

### Loop Limit Exceeded

If the maximum iteration count is exceeded, the loop produces:

```
Fault(reason="loop limit exceeded")
```

This Fault follows normal fault precedence (see Section 18).

### SSA in Loops

Variables defined inside a loop follow the rules in Section 6.1. Each iteration creates fresh bindings. The exiting iteration's values become visible to subsequent blocks.

---

# 18. Fault Handling

`Fault` is a value, not an exception. It flows through the workflow explicitly and must be handled like any other typed value.

### Fault Structure

```
Fault {
  reason: string
}
```

### Fault Sources

Three operations can produce Faults:

```
transform via llm — schema validation failure after retries
tool              — semantic operation failure after retries
loop              — iteration limit exceeded
```

### Fault Precedence

```
1  explicit route
2  workflow fault_handler
3  compile error
```

If a Fault is explicitly routed, the `fault_handler` is not triggered for that Fault.

If a Fault is not explicitly routed and no `fault_handler` is defined, the compiler emits an error.

### Workflow Fault Handler

Example:

```
fault_handler {
  return Fault(reason=Fault.reason)
}
```

The `fault_handler` catches any Fault that is not explicitly routed by a `route` statement. It serves as a workflow-level default.

### Example: Explicit Fault Routing

```
claims = transform(summary, Claim[])
         via llm(extract_claims)

route(claims) {
  Claim[] -> verification
  Fault   -> return Fault(reason="Extraction failed")
}
```

### Design Rationale

In AI workflows, failure is expected, not exceptional. LLMs produce malformed output regularly. Tools fail regularly. These are normal operating conditions of stochastic systems. AIR treats failure as first-class data flow, not as an emergency exit. The topology author decides the failure strategy, not the runtime.

---

# 19. Failure Boundary

AIR distinguishes two categories of external operations.

### Stochastic Operations

```
llm
decide
```

These produce best-effort answers, not guaranteed correctness. If the provider fails (timeout, rate limit, unavailability), the runtime is responsible for retry, wait, fallback, or workflow abort. AIR sees only the successful result.

### Deterministic Operations

```
tool
```

These represent semantic operations with a defined success condition. Failure means the requested operation cannot produce a valid artifact. Therefore failure must be observable in AIR:

```
tool(...) → Artifact | Fault
```

### Resulting Rule

```
Operations that can fail semantically expose Fault in their type signature.
Operations that represent stochastic generation or decision
do not expose transport failures to AIR.
```

---

# 20. Structured Values

Lists:

```
[v1, v2, v3]
```

Structured values:

```
Artifact(summary=summary)
Fault(reason="Rejected")
```

---

# 21. Assets

AIR workflows reference external assets.

Asset types:

```
prompts
rules
schemas
providers
```

Example usage:

```
llm(summarize_aurora)
verify(claims, product_existence)
decide(human_reviewer, summary)
```

Example project structure:

```
prompts/
rules/
schemas/
providers/
workflows/
```

---

# 22. Type Coupling Rules

Instruction typing contracts:

| Instruction       | Consumes               | Produces          |
| ----------------- |------------------------| ----------------- |
| llm               | prompt                 | Message           |
| tool              | inputs                 | Artifact \| Fault |
| transform         | T                      | U                 |
| transform via llm | T                      | U \| Fault        |
| verify            | Claim[]                | Verdict, Evidence |
| aggregate         | Verdict[]              | Consensus         |
| gate              | Verdict \| Consensus   | Outcome           |
| decide            | inputs                 | Message?, Outcome |
| route             | Outcome or union types | control flow      |
| return            | Artifact \| Fault      | terminator        |

The compiler enforces these rules during static analysis.

---

# 23. Control Flow Summary

AIR has three primary control flow mechanisms:

```
route    — inter-block control flow (explicit labels)
continue — intra-loop control flow (restart iteration)
return   — workflow termination
```

Block terminators are:

```
route
return
unreachable
```

`continue` is not a terminator. It is a loop control instruction that restarts the current iteration. It may only appear inside a `loop` block.

There are no hidden control paths. Everything except `continue` targets an explicitly named label.

---

# 24. Example Workflow

```air
@air 0.1

workflow Aurora_Fact_Check -> Artifact | Fault

fault_handler {
  return Fault(reason="Unhandled failure")
}

summary = llm(summarize_aurora)

claims = transform(summary, Claim[])
         via llm(extract_claims)

route(claims) {
  Fault   -> regenerate
  Claim[] -> verification
}

verification:
parallel {
  v1, _ = verify(claims, product_existence)
  v2, _ = verify(claims, link_validation)
  v3, _ = verify(claims, compute_claim)
}

consensus = aggregate([v1, v2, v3], majority)

outcome = gate(consensus)

route(outcome) {
  PROCEED  -> publish
  ESCALATE -> review
  RETRY    -> regenerate
  HALT     -> abort
}

regenerate:
loop retry_generation [max=2] {
  summary2 = llm(regenerate_summary)

  claims2 = transform(summary2, Claim[])
            via llm(extract_claims)

  route(claims2) {
    Claim[] -> verification_retry
    Fault   -> continue
  }
}

verification_retry:
parallel {
  v4, _ = verify(claims2, product_existence)
  v5, _ = verify(claims2, link_validation)
  v6, _ = verify(claims2, compute_claim)
}

consensus2 = aggregate([v4, v5, v6], majority)

outcome2 = gate(consensus2)

route(outcome2) {
  PROCEED  -> publish_retry
  ESCALATE -> review
  RETRY    -> review    // after retry, escalate rather than loop again
  HALT     -> abort
}

publish:
return Artifact(
  status="verified",
  summary=summary,
  verification=consensus
)

publish_retry:
return Artifact(
  status="verified_after_retry",
  summary=summary2,
  verification=consensus2
)

review:
msg, outcome3 = decide(human_reviewer, summary)

route(outcome3) {
  PROCEED  -> publish
  HALT     -> abort
  ESCALATE -> abort
  RETRY    -> regenerate
}

abort:
return Fault(reason="Verification failed")
```

---

# 25. Version Declaration

AIR programs declare language version.

```
@air 0.1
```

Future versions may extend the language while maintaining compatibility.

---

# 26. Related Specifications

Additional AIR specifications define:

* **AIS** — instruction semantics
* **ATS** — type system
* **EBNF** — grammar
* **AST** — compiler representation
* **EGIR** — execution graph
* **AVM** — Agent VM runtime
