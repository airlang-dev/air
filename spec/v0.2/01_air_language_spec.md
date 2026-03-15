# AIR Language Specification v0.2

## 1. Overview

**AIR** is a language for describing AI workflows in a structured, portable, and governed form.

AIR programs define how:

* language models generate content
* structured information is extracted
* claims are verified
* decisions are made
* multi-participant interactions are coordinated
* humans or automated systems intervene when necessary

AIR is a compiled language. The AIR compiler lowers AIR programs into an AIR Graph, a portable execution graph serialized as `.airc`. AIR Graphs can be executed by multiple runtimes, including the AIR Agent VM and external backends such as LangGraph, Dify, Amazon Bedrock, Azure AI Foundry, and Oracle Agent Spec.

AIR stack:

```
AIR Source (.air)
        ↓
   AIR Compiler
        ↓
   AIR Graph (.airc)
        ↓
┌───────────────┬───────────────┬───────────────┐
│ AIR Agent VM  │  LangGraph    │  Agent Spec   │
│ (reference)   │  Backend      │  Backend      │
└───────────────┴───────────────┴───────────────┘
        ↓
   LLMs / Tools / Decision Providers
```

---

# 2. Terminology

### AIR Program

A file containing one or more workflows. File extension: `.air`.

### AIR Workflow

The executable unit of AIR. A workflow defines nodes, control flow, data flow, failure handling, and return types.

### AIR Graph

The portable intermediate representation produced by the AIR compiler. Serialized as JSON in `.airc` files. Runtime adapters consume AIR Graph to execute workflows on target platforms.

### AIR Agent VM

The reference runtime that executes AIR Graph directly.

---

# 3. Design Principles

### Deterministic Orchestration

AI models are nondeterministic. AIR ensures orchestration logic is deterministic.

### Explicit Stochastic Operations

Three instructions are nondeterministic:

```
llm
decide
session
```

All other instructions are deterministic.

### Governance by Construction

Model outputs must be verified before influencing control flow.

Typical pipeline:

```
generate → extract → verify → gate → route
```

### Governance Modes

AIR supports two governance modes declared at the program level.

```
@air 0.2 [mode=normal]   — governance primitives available, not required
@air 0.2 [mode=strict]   — governance primitives mandatory on every llm→route path
```

In strict mode, the compiler rejects any workflow where an LLM output influences a route without passing through a verify → gate chain.

Normal mode is the default.

### Portability

AIR workflows compile to different orchestration platforms through runtime adapters.

### Auditability

All reasoning, verification, and decisions are explicitly represented.

---

# 4. Program Structure

An AIR program declares a language version, optional governance mode, and one or more workflows.

```air
@air 0.2

workflow Fact_Checked_Publish(content: Message) -> Artifact | Fault:

    node analyze [max=3]:
        ...
```

Workflows accept typed input parameters and declare their return types. The return type defines all allowed terminal outputs.

---

# 5. Workflow Definition

A workflow is the primary execution unit.

Syntax:

```
workflow Name(param: Type, ...) -> ReturnTypes:
```

Examples:

```air
workflow Fact_Checked_Publish(content: Message) -> Artifact | Fault:

workflow Parley(task: Message, members: Participants, protocol: Protocol) -> Artifact | Fault:

workflow SimpleChat(prompt: Message) -> Artifact:
```

Workflows without input parameters are valid for entry-point workflows triggered by events or schedules:

```air
workflow DailyReport -> Artifact | Fault:
```

---

# 6. Nodes

Nodes are the building blocks of an AIR workflow. Each node is a named block containing instructions.

```air
node analyze [max=3]:
    summary = llm(summarize, content)
    claims = transform(summary) as Claim[] via llm(extract_claims)
    validate(claims, summary)
```

### Node Parameters

Nodes may declare input parameters. Every piece of data that crosses a node boundary must be passed explicitly.

```air
node validate(claims, summary):
    ...
```

When routing to a node, arguments are passed at the call site:

```air
route outcome:
    PROCEED: publish(summary, outcome)
    ESCALATE: review(summary)
```

### Node Modifiers

Nodes support modifiers in square brackets.

```
[max=N]     — maximum visits before Fault (bounded execution)
[fallback]  — catches unhandled Faults (at most one per workflow)
```

Example:

```air
node analyze [max=3]:
    ...

node recovery [fallback]:
    tool(notify_ops, Fault.reason)
    return Fault(reason=Fault.reason)
```

### Entry Point

The first node in a workflow is the entry point.

### Naming Convention

Node names are imperative verbs describing the workflow step. Node names must not collide with instruction keywords.

Reserved instruction keywords:

```
llm, tool, transform, verify, aggregate, gate,
decide, session, route, return, unreachable, parallel
```

---

# 7. Variables

AIR uses **single assignment semantics (SSA)**.

Variables cannot be reassigned within a node.

Valid:

```air
summary = llm(summarize, content)
claims = transform(summary) as Claim[] via llm(extract_claims)
```

Invalid:

```air
summary = llm(summarize, content)
summary = llm(other_prompt, content)
```

### SSA Across Node Visits

When a node is visited multiple times (via bounded back-edges), each visit creates fresh SSA bindings. The compiler resolves variable versions internally.

Workflow input parameters are available to all nodes implicitly. Node-produced values flow explicitly through node parameters.

---

# 8. Instruction Categories

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

### Interaction

```
session
```

### Orchestration

```
route
parallel
```

### Terminators

```
return
unreachable
```

---

# 9. LLM Instruction

Invokes a language model.

```air
result = llm(prompt, input)
result = llm(prompt, input1, input2, ...)
```

The first argument is always a **prompt asset reference**. Remaining arguments are input data from the workflow.

Example:

```air
summary = llm(summarize, content)
```

Return type:

```
Message
```

### Model Binding

The prompt asset determines which model executes the call. Each prompt asset may specify a `model` field that binds it to a specific LLM provider and model. If no model is specified, the runtime uses its default model.

```yaml
# prompts/summarize.yaml
model: claude-sonnet
template: summarize.md
```

AIR source never references models directly. Model selection is always mediated through prompt assets. This keeps AIR programs model-agnostic — the same workflow can target different models by changing prompt asset configuration, without modifying AIR source.

### Cross-Model Patterns

To run the same instructions on different models, create separate prompt assets that share a template but bind to different models.

```yaml
# prompts/detect_ai_claude.yaml
model: claude-sonnet
template: detect_ai_content.md

# prompts/detect_ai_gpt.yaml
model: gpt-4o
template: detect_ai_content.md
```

The `template` field references a shared template file. This avoids duplicating prompt text when only the model differs.

These prompt assets are then used in AIR source like any other:

```air
parallel:
    check_claude = llm(detect_ai_claude, article)
    check_gpt = llm(detect_ai_gpt, article)
```

Each call invokes the same prompt template on a different model. The results can be cross-checked:

```air
parallel:
    check_claude = llm(detect_ai_claude, article)
    check_gpt = llm(detect_ai_gpt, article)

consensus = aggregate([check_claude, check_gpt], unanimous)
```

### Conversational Prompts

In multi-turn patterns (Section 29), prompt assets like `claude`, `gpt`, `gemini` are conversational prompt assets — each specifies a model and a system prompt or persona:

```yaml
# prompts/claude.yaml
model: claude-sonnet
template: conversational_agent.md

# prompts/gpt.yaml
model: gpt-4o
template: conversational_agent.md
```

The AIR source reads naturally as model names, but they are prompt assets:

```air
r1 = llm(claude, history)
r2 = llm(gpt, [history, r1])
```

### Transport Failures

Transport failures (timeouts, rate limits, provider outages) are handled by the runtime. AIR only observes the semantic output. The `llm` instruction never produces `Fault` — it is stochastic and always returns `Message`.

---

# 10. Tool Instruction

Invokes an external deterministic capability.

```air
result = tool(tool_name, inputs...)
```

Example:

```air
docs = tool(fetch_product_docs, product_id)
```

Return type:

```
Artifact | Fault
```

A tool invocation can fail semantically (API error, database unavailable, file not found, permission denied). The runtime retries transient failures according to its configured policy. After retries are exhausted, failure produces Fault.

Tool faults follow standard fault precedence (see Section 20).

---

# 11. Transform Instruction

Converts a value into a target type. Three forms are supported, each with a different execution model.

### Schema Coercion

```air
value = transform(input) as TargetType
```

The runtime attempts automatic type conversion using the target type's schema definition. Suitable for mechanical conversions where no interpretation is required.

Example:

```air
numbers = transform(text) as Number[]
config = transform(raw_json) as AppConfig
```

Execution model:

```
parse input against target schema
   ↓
success → T
failure → Fault
```

Type signature:

```
transform(input) as T → T | Fault
```

Schema coercion is deterministic. It never invokes an LLM. Conversion failures (malformed input, type mismatch, schema validation error) produce `Fault`.

### LLM-Assisted Transform

When interpretation or extraction is required, transform invokes an LLM with a prompt asset.

```air
claims = transform(summary) as Claim[] via llm(extract_claims)
```

The LLM generates output guided by the prompt. The runtime validates the output against the target type's schema. If validation fails, the runtime retries (bounded by runtime configuration). If retries are exhausted, the result is `Fault`.

Execution model:

```
LLM extraction (guided by prompt asset)
   ↓
schema validation against T
   ↓
success → T
failure → retry (bounded by runtime configuration)
   ↓
retries exhausted → Fault
```

Type signature:

```
transform(input) as T via llm(prompt) → T | Fault
```

### Function-Assisted Transform

When conversion requires domain logic but not LLM inference, transform invokes a function asset — a deterministic function registered with the project.

```air
features = transform(article) as Features via func(extract_features)
```

The function asset receives the input value, performs computation, and returns a value that the runtime validates against the target type's schema.

Example — extracting structural features from a markdown article:

```air
features = transform(article) as Features via func(extract_features)
```

Where `extract_features` is a function asset in the project's `functions/` directory that parses the article and produces a `Features` struct (word count, heading count, code block count, link count, etc.).

Execution model:

```
function execution (deterministic)
   ↓
schema validation against T
   ↓
success → T
failure → Fault
```

Type signature:

```
transform(input) as T via func(function_asset) → T | Fault
```

Function-assisted transform is deterministic. It never invokes an LLM. The function asset is a named reference resolved at compile time (see Section 23). The runtime is responsible for loading and executing the function. Failures — exceptions raised by the function or schema validation errors — produce `Fault`.

### Transform Summary

| Form | Syntax | Execution | Use Case |
|------|--------|-----------|----------|
| Schema coercion | `transform(x) as T` | parse/coerce | Mechanical conversion (JSON→struct, string→number) |
| LLM-assisted | `transform(x) as T via llm(p)` | LLM + validate | Extraction requiring interpretation |
| Function-assisted | `transform(x) as T via func(f)` | function + validate | Domain logic without LLM (parsing, computation, formatting) |

All three forms produce `T | Fault`. All three validate the result against the target type's schema.

---

# 12. Verify Instruction

Evaluates input against a verification rule.

```air
verdict, evidence = verify(input, rule)
```

Example:

```air
verdict, evidence = verify(claims, product_existence)
```

Evidence may be discarded:

```air
verdict, _ = verify(claims, product_existence)
```

Verdict values:

```
PASS
FAIL
UNCERTAIN
```

### Enforcement Modes

Enforcement behavior is defined in the rule asset, not in the AIR source. The AIR source does not change based on enforcement mode. The compiler reads the rule asset to determine enforcement behavior.

Three enforcement modes:

```
block    — Fault on FAIL, halt pipeline (default)
warn     — inject warning into context, continue execution
observe  — log only, continue execution
```

Example rule asset:

```yaml
# rules/product_existence.rule
check: existence
target: product_names
enforcement: block
```

```yaml
# rules/style_guide.rule
check: consistency
target: writing_style
enforcement: warn
```

The `verify` call in AIR is always the same:

```air
v1 = verify(claims, product_existence)
v2 = verify(claims, style_guide)
```

The enforcement mode is a property of the rule, not the instruction.

---

# 13. Aggregate Instruction

Combines multiple verification results.

```air
consensus = aggregate([values], strategy)
```

Example:

```air
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

Combines all evidence and preserves the full verdict distribution without reduction.

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

# 14. Gate Instruction

Converts verification outcomes into workflow outcomes.

```
gate(Verdict | Consensus) → Outcome
```

Outcome values:

```
PROCEED
RETRY
ESCALATE
HALT
```

Mapping for a single Verdict:

```
PASS      → PROCEED
FAIL      → ESCALATE
UNCERTAIN → RETRY
```

Mapping for Consensus:

Gate applies conservative evaluation. A single failure in a consensus overrides multiple successes.

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

# 15. Decide Instruction

Obtains a decision from an external decision provider.

```air
message, outcome = decide(provider, input...)
```

Example:

```air
msg, outcome = decide(human_reviewer, summary)
```

Return values:

```
Message?, Outcome
```

The Message is optional. Some providers may return only an Outcome.

Examples:

```air
_, outcome = decide(risk_policy, claims)
msg, outcome = decide(human_reviewer, summary)
```

The provider may represent a human reviewer, an AI reviewer, a policy engine, or an algorithmic decision system. Providers are defined as external assets.

Transport or availability failures are handled entirely by the runtime. AIR never observes them.

---

# 16. Session Instruction

Executes a multi-participant, multi-turn interaction governed by a protocol.

```air
result = session(members, protocol, history)
```

Example:

```air
result = session(members, parley_v1, history)
```

Return value:

```
result.consensus — Outcome (PROCEED | RETRY | ESCALATE | HALT)
result.history   — Message[] (full interaction transcript)
```

The `session` instruction is stochastic — it involves multiple LLM calls and optional human intervention.

### Members

Members are passed as a workflow parameter or referenced as an asset. Each member has a model, a role, and an optional prompt.

### Protocols

Protocols are external assets that define the rules of the interaction. The compiler validates that the protocol asset exists. The runtime interprets the protocol content.

A protocol typically defines:

```
legal moves      — what responses are valid
turn order       — who speaks when
move rules       — constraints on move sequences
response format  — expected structure of responses
```

Different protocol types serve different interaction patterns:

```
debate       — adversarial, moves, consensus
brainstorm   — generative, phases, no criticism
code review  — sequential, approve/reject
approval     — hierarchical, sign-off stages
```

The protocol format is a runtime concern, not a language concern. Different runtimes may support different protocol formats. The AIR compiler does not interpret protocol content.

Example protocol asset:

```yaml
# protocols/parley_v1.yaml
name: parley_v1

moves:
  - DISCUSS
  - PROPOSE
  - AGREE
  - COUNTER
  - QUESTION

turn_order: round_robin

move_rules:
  PROPOSE: requires_previous DISCUSS
  AGREE: must_reference PROPOSE
  COUNTER: must_include argument

response_format: "MOVE: content"
```

---

# 17. Route Instruction

Performs conditional branching.

```air
route value:
    pattern: target
```

Example:

```air
route outcome:
    PROCEED: publish(summary, outcome)
    ESCALATE: review(summary)
    RETRY: analyze
    HALT: abort
```

Patterns may match:

* enum values (PROCEED, HALT, etc.)
* types (Fault)
* `else` (default, matches anything not explicitly matched)

### Type Narrowing

Route patterns narrow union types by matching the runtime type.

```air
route claims:
    Fault: analyze
    else: validate(claims, summary)
```

`else` matches the success case in a union type. The compiler infers the narrowed type.

### Unconditional Transitions

When routing to a single target with no conditions, use a bare node call:

```air
node analyze [max=3]:
    summary = llm(summarize, content)
    claims = transform(summary) as Claim[] via llm(extract_claims)
    validate(claims, summary)
```

The last line is an unconditional transition to the `validate` node.

### Exhaustiveness

Routes must be exhaustive. Valid if all cases are covered or `else` exists. A non-exhaustive route is a compile error.

---

# 18. Parallel Block

Executes instructions concurrently.

```air
parallel:
    v1 = verify(claims, product_existence)
    v2 = verify(claims, link_validation)
    v3 = verify(claims, compute_claim)
```

Rules:

* variables must be distinct
* execution continues after all branches finish
* variables produced inside a parallel block become visible after the block completes

### Partial Failure

By default, a parallel block is strict: any fault in any branch faults the entire block.

To allow partial success:

```air
parallel [partial]:
    docs = tool(fetch_product_docs, product_id)
    reviews = tool(fetch_reviews, product_id)
    pricing = tool(fetch_pricing, product_id)
```

In partial mode, faulted branches produce Fault values. Successful branches produce their normal values. All variables are available after the block. The topology author handles each result individually using standard route constructs.

```
parallel:            — strict, any fault fails the block
parallel [partial]:  — partial, faults become individual values
```

---

# 19. Bounded Nodes

AIR does not have a loop construct. Retries and iteration are expressed as bounded back-edges between nodes.

A node with `[max=N]` can be visited at most N times. After N visits, the node produces Fault.

```air
node analyze [max=3]:
    summary = llm(summarize, content)
    claims = transform(summary) as Claim[] via llm(extract_claims)

    route claims:
        Fault: analyze
        else: validate(claims, summary)
```

`Fault: analyze` routes back to the same node — a retry. After 3 visits, the Fault follows normal fault precedence.

Bounded back-edges may also cross nodes:

```air
node validate(claims, summary):
    ...
    route outcome:
        RETRY: analyze
```

The compiler checks that every back-edge targets a node with a `[max=N]` declaration. Unbounded cycles are a compile error.

### Visit Limit Exceeded

If the maximum visit count is exceeded, the node produces:

```
Fault(reason="max visits exceeded")
```

This Fault follows normal fault precedence (see Section 20).

### SSA Across Visits

Each visit to a bounded node creates fresh SSA bindings. The compiler resolves variable versions internally.

---

# 20. Fault Handling

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
transform via llm  — schema validation failure after retries
tool               — semantic operation failure after retries
bounded node       — max visit count exceeded
```

### Fault Precedence

```
1  explicit route
2  [fallback] node
3  automatic propagation (if Fault is in workflow return type)
4  compile error
```

If a Fault is explicitly routed, the fallback node is not triggered for that Fault.

If no explicit route exists and a `[fallback]` node is defined, unhandled Faults route there.

If no fallback node exists and the workflow declares Fault in its return type, unhandled Faults propagate as the workflow return value automatically.

If none of the above apply, the compiler emits an error.

### Fallback Node

A workflow may have at most one node marked `[fallback]`. It catches unhandled Faults and may contain full logic including tool calls, decide instructions, and routing.

```air
node recovery [fallback]:
    tool(notify_ops, Fault.reason)
    msg, outcome = decide(incident_manager, Fault)

    route outcome:
        RETRY: analyze
        HALT: return Fault(reason=Fault.reason)
```

### Design Rationale

In AI workflows, failure is expected, not exceptional. LLMs produce malformed output regularly. Tools fail regularly. These are normal operating conditions of stochastic systems. AIR treats failure as first-class data flow. The topology author decides the failure strategy, not the runtime.

---

# 21. Failure Boundary

AIR distinguishes two categories of external operations.

### Stochastic Operations

```
llm
decide
session
```

These produce best-effort answers. If the provider fails (timeout, rate limit, unavailability), the runtime is responsible for retry, wait, fallback, or workflow abort. AIR sees only the successful result.

### Deterministic Operations

```
tool
```

These represent semantic operations with a defined success condition. Failure must be observable in AIR:

```
tool(...) → Artifact | Fault
```

### Resulting Rule

```
Operations that can fail semantically expose Fault in their type signature.
Stochastic operations do not expose transport failures to AIR.
```

---

# 22. Structured Values

Lists:

```air
[v1, v2, v3]
updated = [history, r1, r2, r3]
```

Structured values:

```air
Artifact(status="verified", summary=summary, verification=outcome)
Fault(reason="Verification failed")
```

---

# 23. Assets

AIR workflows reference external assets. The compiler validates that referenced assets exist. The runtime interprets their content.

Asset types:

```
prompts     — LLM prompt templates
rules       — verification rules (including enforcement mode)
schemas     — structured type definitions
providers   — decision provider configurations
protocols   — session interaction rules
functions   — deterministic transform functions
```

### Prompt Assets

Referenced by `llm()` and `transform() ... via llm()`. A prompt asset configures an LLM invocation.

A prompt asset may be a plain text file (the template itself) or a structured file with metadata:

```yaml
# prompts/summarize.yaml
model: claude-sonnet          # optional — runtime default if omitted
template: summarize.md        # references a shared template file
```

Fields:

- **`model`** (optional): LLM provider and model identifier. If omitted, the runtime uses its configured default model.
- **`template`**: The prompt template, either inline or as a reference to a `.md` file. Templates may use variable interpolation for input data.

When multiple prompt assets need the same instructions but different models, they reference a shared template file. This avoids duplicating prompt text and makes model selection a configuration concern rather than a source concern.

### Rule Assets

Referenced by `verify()`. Define verification criteria and optionally an enforcement mode.

### Schema Assets

Define structured types used in workflow signatures, transform targets, and collection type parameters.

### Provider Assets

Referenced by `decide()`. Configure decision providers (human review queues, automated escalation systems).

### Protocol Assets

Referenced by `session()`. Define interaction rules for multi-participant sessions.

### Function Assets

Referenced by `transform() ... via func()`. Contain deterministic functions that transform input values. Function assets are opaque to the compiler — it validates only that the referenced asset exists. The runtime is responsible for loading and executing the function.

Function assets may be implemented in any language supported by the runtime (e.g., Python, JavaScript, WASM). The runtime must ensure that function execution is deterministic and side-effect-free.

Example usage:

```air
llm(summarize, content)
verify(claims, product_existence)
decide(human_reviewer, summary)
session(members, parley_v1, history)
transform(article) as Features via func(extract_features)
```

Example project structure:

```
project/
├── workflows/
│   └── fact_check.air
├── prompts/
│   ├── summarize.md                 # plain template (uses runtime default model)
│   ├── extract_claims.md
│   ├── detect_ai_claude.yaml        # structured: model + shared template
│   ├── detect_ai_gpt.yaml           # structured: model + shared template
│   └── detect_ai_content.md         # shared template referenced by both
├── rules/
│   ├── product_existence.rule
│   └── style_guide.rule
├── schemas/
│   ├── claim.schema.json
│   └── features.schema.json
├── providers/
│   └── human_reviewer.yaml
├── protocols/
│   └── parley_v1.yaml
└── functions/
    └── extract_features.py
```

---

# 24. Data Flow

AIR uses explicit data passing between nodes. There is no shared state.

### Workflow Inputs

Workflow input parameters are available to all nodes implicitly.

```air
workflow Parley(task: Message, members: Participants, protocol: Protocol) -> Artifact | Fault:
```

`task`, `members`, and `protocol` are accessible from any node.

### Node Parameters

Node-produced values flow between nodes through explicit parameters.

```air
node analyze [max=3]:
    summary = llm(summarize, content)
    claims = transform(summary) as Claim[] via llm(extract_claims)
    validate(claims, summary)          // passes both values

node validate(claims, summary):       // declares what it receives
    ...
    route outcome:
        PROCEED: publish(summary, outcome)
```

If a node needs a value, it must receive it as a parameter. If a node produces a value another node needs, it must pass it through a route or transition.

### Runtime Context

Model configurations, API keys, and runtime settings are implicit context managed by the runtime. They do not appear in AIR source.

### Summary

```
Workflow inputs     → implicit, available to all nodes
Node outputs        → explicit, passed through parameters
Runtime context     → implicit, managed by runtime
```

---

# 25. Type Coupling Rules

Instruction typing contracts:

| Instruction        | Consumes                   | Produces                      |
| ------------------ | -------------------------- | ----------------------------- |
| llm                | prompt, input              | Message                       |
| tool               | tool_name, inputs          | Artifact \| Fault             |
| transform          | input                      | T \| Fault                    |
| transform via llm  | input, prompt              | T \| Fault                    |
| transform via func | input, function            | T \| Fault                    |
| verify             | input, rule                | Verdict, Evidence             |
| aggregate          | Verdict[], strategy        | Consensus                     |
| gate               | Verdict \| Consensus       | Outcome                       |
| decide             | provider, inputs           | Message?, Outcome             |
| session            | members, protocol, history | result (Outcome + Message[]) |
| route              | Outcome or union types     | control flow                  |
| return             | Artifact \| Fault          | terminator                    |

The compiler enforces these rules during static analysis.

---

# 26. Control Flow Summary

AIR has three control flow mechanisms:

```
route            — conditional branching (multiple targets)
node_call(args)  — unconditional transition (single target)
return           — workflow termination
```

Block terminators are:

```
route
node call
return
unreachable
```

There are no hidden control paths. Every transition is explicit.

---

# 27. Example: Fact-Checked Publish

```air
@air 0.2

workflow Fact_Checked_Publish(content: Message) -> Artifact | Fault:

    node analyze [max=3]:
        summary = llm(summarize, content)
        claims = transform(summary) as Claim[] via llm(extract_claims)

        route claims:
            Fault: analyze
            else: validate(claims, summary)

    node validate(claims, summary):
        parallel:
            v1 = verify(claims, product_existence)
            v2 = verify(claims, link_validation)
            v3 = verify(claims, compute_claim)

        outcome = gate(aggregate([v1, v2, v3], majority))

        route outcome:
            PROCEED: publish(summary, outcome)
            ESCALATE: review(summary)
            RETRY: analyze
            HALT: abort

    node review(summary):
        msg, outcome = decide(human_reviewer, summary)

        route outcome:
            PROCEED: publish(summary, outcome)
            ESCALATE: abort
            RETRY: analyze
            HALT: abort

    node publish(summary, outcome):
        return Artifact(status="verified", summary=summary, verification=outcome)

    node abort:
        return Fault(reason="Verification failed")
```

---

# 28. Example: Multi-LLM Debate

```air
@air 0.2

workflow Parley(task: Message, members: Participants, protocol: Protocol) -> Artifact | Fault:

    node discuss(history) [max=10]:
        result = session(members, protocol, history)

        route result.consensus:
            PROCEED: publish(result.history)
            RETRY: discuss(result.history)
            ESCALATE: moderate(result.history)
            HALT: abort

    node moderate(history):
        msg, outcome = decide(human, history)

        route outcome:
            PROCEED: publish(history)
            RETRY: discuss(history)
            HALT: abort

    node publish(history):
        summary = llm(summarize, history)
        return Artifact(summary=summary, transcript=history)

    node abort:
        return Fault(reason="No consensus reached")
```

---

# 29. Example: Simple Multi-LLM Chat

```air
@air 0.2

workflow MultiLLMChat(task: Message) -> Artifact | Fault:

    node discuss(history) [max=10]:
        r1 = llm(claude, history)
        r2 = llm(gpt, [history, r1])
        r3 = llm(gemini, [history, r1, r2])

        updated = [history, r1, r2, r3]
        done = transform(updated) as bool via llm(check_done)

        route done:
            true: publish(updated)
            false: discuss(updated)

    node publish(history):
        summary = llm(summarize_discussion, history)
        return Artifact(summary=summary, transcript=history)
```

---

# 30. Version Declaration

AIR programs declare language version and optional governance mode.

```air
@air 0.2
@air 0.2 [mode=strict]
```

Future versions may extend the language while maintaining compatibility.

---

# 31. Compilation

The AIR compiler performs:

```
AIR source → parse → AST → semantic analysis → CFG → AIR Graph (.airc)
```

### Static Validation

The compiler performs the following checks:

* symbol resolution — all assets and node references exist
* SSA validation — variables assigned once per node scope
* type checking — instruction inputs match type coupling rules
* exhaustive routing — all route patterns cover all cases
* bounded cycles — every back-edge targets a node with [max=N]
* fault coverage — all possible Faults are handled (route, fallback, return type, or compile error)
* governance enforcement (strict mode) — every llm→route path passes through verify → gate

### AIR Graph

The compiled output is a JSON file containing:

```
workflow metadata (name, inputs, return types, mode)
nodes (id, instruction, params, outputs, max_visits, modifiers)
edges (from, to, condition)
entry point
```

The AIR Graph preserves all semantic guarantees from the source:

* type safety
* governance chains
* visit bounds
* fault precedence
* enforcement modes

Runtime adapters consume the AIR Graph. The adapter is responsible for translating AIR semantics into the target runtime while preserving these guarantees.

---

# 32. Related Specifications

Additional AIR specifications define:

* **ATS** — type system
* **EBNF** — grammar
* **AST** — compiler representation
* **AIR Graph Schema** — JSON schema for .airc files
* **AVM** — Agent VM runtime
