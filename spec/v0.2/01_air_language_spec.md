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

### Composition

```
map
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

# 16a. Map Instruction

Applies a workflow to each element of a collection, collecting results into an array.

```air
results = map(collection, WorkflowName)
results = map(collection, WorkflowName) [concurrency=10, on_error=skip]
```

The first argument is a collection (`T[]`). The second argument is a workflow name. The named workflow must accept a single input parameter of type `T` and return `R | Fault`.

`map` requires that its input is a collection, not a union type. If the input variable might be `Fault`, the caller must route before calling `map`:

```air
articles = tool(load_data, path)

route articles:
    Fault: handle_failure
    else: process(articles)

node process(articles):
    results = map(articles, AnalyzeArticle)
```

### Semantics

`map` invokes the named workflow once per element in the input collection. Each invocation is independent — it receives one element, executes the full sub-workflow, and returns a result. The runtime collects all results into an array.

```
for each item in collection:
    invoke WorkflowName(item)
    collect result
   ↓
results: R[]
```

The sub-workflow is a normal AIR workflow. It is independently compilable, testable, and executable. `map` is the only construct that crosses workflow boundaries.

### Type Rules

The return type of `map` depends on the error policy:

```
Sub-workflow returns: R | Fault

on_error=skip:    map returns R[]           (faults filtered out)
on_error=halt:    map returns R[] | Fault   (first fault stops execution)
on_error=collect: map returns (R | Fault)[] (all results preserved)
```

Default error policy is `halt`.

### Error Policies

#### halt (default)

Execution stops on the first item that produces `Fault`. The `map` expression produces that `Fault`. Items that completed successfully before the failure are discarded — the caller receives only the Fault.

```air
// stops on first failure — result is R[] or Fault
results = map(articles, AnalyzeArticle)
```

This is the safest default. The caller must handle the `Fault` via route or fallback. Use `halt` when any individual failure invalidates the entire batch (e.g., a mandatory preprocessing step).

#### skip

Faulted items are logged by the runtime and excluded from the result array. Execution continues with remaining items. The result array contains only successes, preserving their relative order from the input. The result may be shorter than the input (or empty if all items fault).

```air
// continues past failures — result is always R[]
results = map(articles, AnalyzeArticle) [on_error=skip]
```

If the input has 434 items and 12 fault, the result contains 422 items. The caller cannot determine which input items faulted — use `collect` if that information is needed.

#### collect

All items are processed regardless of individual failures. Each position in the result array is either `R` (success) or `Fault` (failure). The result array has the same length as the input and preserves positional correspondence: `results[i]` is the outcome for `collection[i]`.

```air
// all results preserved — result is (R | Fault)[]
results = map(articles, AnalyzeArticle) [on_error=collect]
```

Use `collect` when the caller needs to know which specific items failed and why. The caller can process successes and failures separately using `transform via func`.

### Ordering

With `on_error=halt` and `on_error=collect`, the result array preserves positional correspondence with the input: `results[i]` is the outcome for `collection[i]`.

With `on_error=skip`, faulted items are removed. The result preserves relative order of successes but is shorter than the input. Positional correspondence is not guaranteed.

### Concurrency

The `concurrency` modifier is a hint to the runtime. It suggests the maximum number of sub-workflow invocations to execute in parallel.

```air
results = map(articles, AnalyzeArticle) [concurrency=10, on_error=skip]
```

If omitted, the runtime chooses a default. The runtime may execute fewer concurrent invocations than requested (due to rate limits, resource constraints, or provider quotas). The runtime must never execute more than the specified concurrency.

`concurrency=1` forces serial execution. This is not equivalent to a bounded node with `[max=N]` — bounded nodes express retry logic for a single item, while `map` with `concurrency=1` expresses sequential iteration over a collection.

### Blocking Sub-Workflows

Sub-workflows may contain blocking operations (`decide`, `session`) that require human interaction or extended multi-participant coordination. A sub-workflow invocation that blocks occupies one concurrency slot until it completes. Other items continue processing in the remaining slots.

```air
// With concurrency=10: if item #47 blocks on a decide, the runtime
// continues processing items #48–#56 in the other 9 slots.
// When the decide for #47 completes, its slot becomes available.
results = map(articles, ReviewArticle) [concurrency=10, on_error=skip]
```

The runtime must not abandon a blocked sub-workflow. A sub-workflow that enters `decide` or `session` remains in progress until the provider responds. AIR does not impose timeouts on sub-workflow execution — timeout policies are a runtime concern.

### Empty Input

`map` over an empty collection produces an empty result array. No sub-workflow invocations occur.

```air
results = map([], AnalyzeArticle)       // results is R[] with length 0
results = map([], AnalyzeArticle) [on_error=halt]   // still R[] (no items to fault)
```

This is not a `Fault`. An empty input is a valid input.

### Nested Map

A sub-workflow invoked by `map` may itself contain `map`. This enables hierarchical batch processing.

```air
workflow ProcessCategory(category: Category) -> CategoryResult | Fault:
    node process:
        results = map(category.articles, AnalyzeArticle) [on_error=skip]
        summary = llm(summarize_category, results)
        return CategoryResult(summary=summary, results=results)

workflow ProcessAll(categories: Category[]) -> Artifact | Fault:
    node process:
        results = map(categories, ProcessCategory) [concurrency=5, on_error=skip]
        return Artifact(categories=results)
```

Each level of nesting has its own concurrency and error policy. The outer `map` controls how many categories run in parallel. Each `ProcessCategory` invocation controls how many articles within that category run in parallel. The runtime manages the total resource usage across all nesting levels.

### Governance Modes

In `[mode=normal]`, `map` has no additional governance requirements. The sub-workflow's own governance mode applies to its internal execution.

In `[mode=strict]`, the strict mode constraint applies to each workflow independently. The compiler validates each workflow's governance in isolation:

- If the sub-workflow is declared `[mode=strict]`, its internal LLM→route paths must pass through verify→gate chains.
- If the sub-workflow is declared `[mode=normal]` (or has no mode), it is not subject to strict governance even if the calling workflow is strict.
- The calling workflow's strict mode does not propagate into the sub-workflow.

This means a strict outer workflow can invoke a normal sub-workflow via `map`. Governance mode is a property of the workflow declaration, not a transitive constraint.

### Interaction with Fault Handling

`map` with `on_error=halt` produces `R[] | Fault`. This follows standard fault precedence (Section 20):

```air
results = map(articles, AnalyzeArticle)

route results:
    Fault: handle_failure
    else: process(results)
```

`map` with `on_error=skip` never produces `Fault`. The result is always `R[]`, which may be empty. If the caller needs to distinguish "all items faulted" from "no input items", check the collection length before calling `map`.

### Example

```air
@air 0.2

workflow AnalyzeOne(article: Article) -> Score | Fault:
    node score:
        features = transform(article) as Features via func(extract_features)
        assessment = llm(evaluate_quality, features)
        result = transform(assessment) as Score via llm(extract_score)
        return result

workflow ScoreAll(articles: Article[]) -> Artifact | Fault:
    node process:
        scores = map(articles, AnalyzeOne) [concurrency=20, on_error=skip]
        report = llm(summarize_scores, scores)
        return Artifact(report=report, scores=scores)
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

# 22. Structured Values and Collections

### Constructors

Structured values are constructed with named fields:

```air
Artifact(status="verified", summary=summary, verification=outcome)
Fault(reason="Verification failed")
```

The type name must match a type in the workflow's return type declaration or a schema-defined type (Section 23). Fields may be string literals or variable references.

### Array Types

The syntax `T[]` denotes an array of type `T`. `T` may be any built-in type, any primitive, or any user-defined type (see Section 22b for type categories).

Valid array types:

```
Message[]       — array of LLM responses
Claim[]         — array of schema-defined type
Verdict[]       — array of verification results
Evidence[]      — array of supporting evidence
Article[]       — array of schema-defined input type
Number[]        — array of numbers
Fault[]         — array of faults (e.g., collected from partial failure)
```

Array types are valid in:

- **Workflow input parameters**: `workflow Pipeline(articles: Article[]) -> Artifact`
- **Node parameters**: `node process(items: Claim[]):`
- **Transform targets**: `transform(text) as Number[]`
- **Instruction return types**: `session` returns a result where `.history` is `Message[]`
- **Aggregate inputs**: `aggregate([v1, v2, v3], majority)` operates on `Verdict[]`

Nested arrays (`T[][]`) are not supported. AIR operates on flat collections. If a workflow needs nested structure, use a schema-defined type that contains an array field.

### Collection Literals

Square brackets construct a collection:

```air
[v1, v2, v3]
```

Collection literals may appear in:

- **Assignment**: `updated = [history, r1, r2, r3]`
- **Instruction arguments**: `aggregate([v1, v2, v3], majority)`
- **LLM input**: `llm(gpt, [history, r1])`

### Concatenation Semantics

When a collection literal contains a mix of arrays and single values, the result is a **flat concatenation** — array elements are spread, single values are appended.

```air
// history is Message[], r1/r2/r3 are Message
updated = [history, r1, r2, r3]
// result: Message[] containing all elements of history followed by r1, r2, r3
```

This is always flattening concatenation, never nesting. The result type is `T[]` where `T` is the element type of the array operands (or the type of the scalar operands). All operands must be type-compatible — mixing `Message` and `Verdict` in a single literal is a type error.

Concatenation examples:

```
[a, b, c]           — creates T[] from three T values
[list, item]         — appends item to list (flat)
[list1, list2]       — concatenates two lists (flat)
[list, a, b]         — appends a and b to list (flat)
```

### Empty Collections

An empty collection is expressed with empty brackets:

```air
results = []
```

The type of an empty collection is inferred from context (the variable's usage in subsequent instructions). An empty collection may be used as an initial value before a `map` operation (Section 16a) or as a base case.

### Routing on Collections

Collections may be used as route values. Type-based routing distinguishes collections from scalar values:

```air
route claims:
    Fault: handle_error
    else: process(claims)
```

Here `claims` is either `Claim[]` (success) or `Fault` (failure). The type-based route dispatches accordingly.

Routing on collection emptiness is not directly supported. To branch on whether a collection is empty, use a `transform` to convert to a boolean or a type that can be routed on:

```air
has_items = transform(results) as bool via func(is_nonempty)
route has_items:
    true: process(results)
    false: handle_empty
```

### Collections and Instructions

How each instruction interacts with collections:

| Instruction | Collection behavior |
|-------------|-------------------|
| `llm` | May receive `T[]` as input (e.g., conversation history) |
| `tool` | May receive or return `T[]` |
| `transform` | May target `T[]` (e.g., `transform(text) as Claim[]`) |
| `verify` | Receives single input, returns single `Verdict` + `Evidence` |
| `aggregate` | Receives `Verdict[]` (via literal `[v1, v2, v3]`), returns `Consensus` |
| `gate` | Receives single `Verdict` or `Consensus`, returns `Outcome` |
| `session` | Returns result containing `Message[]` in `.history` |
| `return` | May return a value containing `T[]` fields |

---

# 22b. Type System

AIR has two categories of types: built-in types and user-defined types.

### Built-In Types

These types are intrinsic to the AIR language. They do not require schema definitions.

```
Message       — LLM output (opaque text/structured content)
Artifact      — successful workflow output (has named fields)
Fault         — failure value (has reason field)
Verdict       — verification result (PASS, FAIL, UNCERTAIN)
Evidence      — supporting data from verification
Consensus     — aggregated verification result
Outcome       — gate/decide output (PROCEED, RETRY, ESCALATE, HALT)
```

### Primitive Types

Three primitive types are built-in for use in transforms and route conditions:

```
bool          — true or false
Number        — numeric value (integer or floating-point)
string        — text value
```

Primitives do not require schema definitions. They are valid as transform targets:

```air
count = transform(text) as Number
done = transform(history) as bool via llm(check_done)
```

### User-Defined Types

Any type not in the built-in or primitive lists is a **user-defined type**. User-defined types are defined by schema assets in the project's `schemas/` directory (see Section 23).

The schema file name determines the type name:

```
schemas/article.schema.json       → Article
schemas/features.schema.json      → Features
schemas/analysis_result.schema.json → AnalysisResult
schemas/claim.schema.json         → Claim
```

The type name is derived from the file name by converting to PascalCase. The convention is to name schema files in snake_case and reference them in PascalCase in AIR source.

### Type Resolution

The compiler resolves every type reference in AIR source:

1. Check if the name matches a built-in type or primitive
2. Check if a schema asset exists with that name
3. If neither, emit a compile error

Type references appear in:

| Context | Example | Compiler check |
|---------|---------|----------------|
| Workflow input parameter | `article: Article` | Schema exists |
| Workflow return type | `-> AnalysisResult \| Fault` | Schema exists |
| Transform target | `transform(x) as Features` | Schema exists |
| Array type | `Article[]` | Element type resolves |
| Constructor | `AnalysisResult(...)` | Schema exists, fields valid |
| Map sub-workflow input | `map(articles, Analyze)` | Element type matches sub-workflow param type |

### Field Access

Dotted access on a variable (`result.consensus`, `article.markdown`) is validated against the type's schema. The compiler checks that the referenced field exists in the schema's `properties`.

For built-in types with known structure:

```
Fault.reason        — always valid (Fault has a reason field)
Consensus.verdicts  — always valid (Consensus has verdicts and evidence)
```

For user-defined types, the compiler checks the schema:

```air
// valid if schemas/article.schema.json has a "title" property
title = transform(article.title) as string
```

If a variable's type cannot be statically determined (e.g., it flows through a generic instruction), the compiler allows dotted access without field validation. The runtime validates at execution time.

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

A schema asset defines a **named type**. The file name (without extension) becomes the type name. A schema file in `schemas/article.schema.json` defines the type `Article`.

Schema assets are the bridge between AIR's type system and external data structures. Every non-built-in type referenced in AIR source must resolve to a schema asset.

Schema assets are JSON Schema files. The compiler uses them for:

- **Existence checking**: every type reference must resolve to a built-in type or a schema file
- **Field validation**: dotted access (`article.markdown`) is checked against the schema's properties
- **Transform validation**: `transform(x) as Features` requires `schemas/features.schema.json` to exist
- **Map type checking**: `map(articles, AnalyzeArticle)` where `articles` is `Article[]` and `AnalyzeArticle` accepts `Article` — the compiler checks that the element type matches the sub-workflow's input type by name

Example — `schemas/article.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Article",
  "type": "object",
  "required": ["id", "title", "markdown"],
  "properties": {
    "id": { "type": "string" },
    "title": { "type": "string" },
    "markdown": { "type": "string" },
    "author": { "type": "string" },
    "published_at": { "type": "string", "format": "date-time" },
    "tags": {
      "type": "array",
      "items": { "type": "string" }
    },
    "word_count": { "type": "integer" }
  }
}
```

This schema defines the type `Article`. It can be used in AIR source as:

```air
workflow AnalyzeArticle(article: Article) -> AnalysisResult | Fault:
    node extract:
        features = transform(article) as Features via func(extract_features)
```

The runtime uses the schema for validation when values enter or leave the workflow (input deserialization, transform output validation, return value validation).

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
| session            | members, protocol, history | result (Outcome + Message[])  |
| map                | T[], workflow              | R[] or R[] \| Fault           |
| route              | Outcome or union types     | control flow                  |
| return             | Artifact \| Fault          | terminator                    |

The compiler enforces these rules during static analysis.

`T` in `transform` rows may be a scalar type or an array type (`T[]`). See Section 22 for collection semantics.

`Verdict[]` in the `aggregate` row is constructed from a collection literal (e.g., `[v1, v2, v3]`) — see Section 22 for concatenation rules.

`map` return type depends on error policy: `R[]` with `on_error=skip`, `R[] | Fault` with `on_error=halt` (default), `(R | Fault)[]` with `on_error=collect`. See Section 16a.

`T` and `R` in the table may be built-in types, primitives, or user-defined types (schema assets). All type references are resolved as described in Section 22b.

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

# 29a. Example: Batch Analysis Pipeline

Two workflows demonstrating `map` for data-dependent iteration. The outer workflow processes a collection of articles through a per-item analysis workflow, computes aggregate statistics, and produces a final report.

Project structure:

```
aideas/
├── workflows/
│   ├── analyze_article.air
│   └── batch_analysis.air
├── prompts/
│   ├── evaluate_quality.md
│   ├── detect_ai_claude.yaml        # model: claude-sonnet, template: detect_ai.md
│   ├── detect_ai_gpt.yaml           # model: gpt-4o, template: detect_ai.md
│   ├── detect_ai.md                 # shared AI detection template
│   └── generate_report.md
├── rules/
│   └── ai_detection_consistency.rule
├── schemas/
│   ├── article.schema.json
│   ├── features.schema.json
│   ├── analysis_result.schema.json
│   └── statistics.schema.json
└── functions/
    ├── extract_features.py           # word count, heading count, code blocks, links
    └── is_nonempty.py
```

### Workflow 1: AnalyzeArticle

Processes a single article — extracts features, runs parallel AI detection on two models, cross-checks consistency, gates the result, and returns a scored analysis.

```air
@air 0.2 [mode=strict]

workflow AnalyzeArticle(article: Article) -> AnalysisResult | Fault:

    node extract:
        features = transform(article) as Features via func(extract_features)

        route features:
            Fault: abort
            else: detect(article, features)

    node detect(article, features):
        parallel:
            check_claude = llm(detect_ai_claude, article)
            check_gpt = llm(detect_ai_gpt, article)

        verdict, evidence = verify([check_claude, check_gpt], ai_detection_consistency)
        outcome = gate(verdict)

        route outcome:
            PROCEED: score(features, evidence)
            ESCALATE: score(features, evidence)
            RETRY: detect(article, features)
            HALT: abort

    node score(features, evidence):
        quality = llm(evaluate_quality, features)
        assessment = transform(quality) as Score via llm(extract_score)

        route assessment:
            Fault: abort
            else: done(features, evidence, assessment)

    node done(features, evidence, assessment):
        return AnalysisResult(
            features=features,
            ai_detection=evidence,
            quality_score=assessment
        )

    node abort:
        return Fault(reason="Analysis failed")
```

### Workflow 2: BatchAnalysis

Orchestrates the batch — maps `AnalyzeArticle` across all articles, computes aggregate statistics, generates a report, and verifies the report's claims before returning.

```air
@air 0.2 [mode=strict]

workflow BatchAnalysis(articles: Article[]) -> Artifact | Fault:

    node analyze:
        results = map(articles, AnalyzeArticle) [concurrency=20, on_error=skip]

        has_results = transform(results) as bool via func(is_nonempty)

        route has_results:
            true: compute(results)
            false: abort

    node compute(results):
        stats = tool(compute_statistics, results)

        route stats:
            Fault: abort
            else: report(results, stats)

    node report(results, stats):
        narrative = llm(generate_report, results, stats)
        claims = transform(narrative) as Claim[] via llm(extract_claims)

        route claims:
            Fault: publish(results, stats, narrative)
            else: validate(results, stats, narrative, claims)

    node validate(results, stats, narrative, claims):
        verdict, evidence = verify(claims, statistical_accuracy)
        outcome = gate(verdict)

        route outcome:
            PROCEED: publish(results, stats, narrative)
            ESCALATE: publish(results, stats, narrative)
            RETRY: report(results, stats)
            HALT: abort

    node publish(results, stats, narrative):
        return Artifact(
            article_count=results,
            statistics=stats,
            report=narrative
        )

    node abort:
        return Fault(reason="Pipeline failed")
```

### Key patterns demonstrated

- **`map` with `on_error=skip`** — tolerates individual article failures, produces partial results
- **`concurrency=20`** — runtime hint for parallel sub-workflow execution
- **Cross-model verification** — same AI detection prompt on Claude and GPT via separate prompt assets
- **Strict governance** — both workflows enforce verify→gate on every LLM→route path
- **Workflow composition** — `BatchAnalysis` invokes `AnalyzeArticle` via `map`, each independently compilable
- **Emptiness check** — `transform via func(is_nonempty)` to route on whether `map` produced any results

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

* symbol resolution — all assets, node references, and workflow references exist
* type resolution — every type reference resolves to a built-in type, primitive, or schema asset (Section 22b)
* SSA validation — variables assigned once per node scope
* type checking — instruction inputs match type coupling rules
* exhaustive routing — all route patterns cover all cases
* bounded cycles — every back-edge targets a node with [max=N]
* fault coverage — all possible Faults are handled (route, fallback, return type, or compile error)
* governance enforcement (strict mode) — every llm→route path passes through verify → gate
* map validation — sub-workflow exists, is independently compilable, accepts exactly one input parameter, input collection element type matches sub-workflow input type, and sub-workflow declares a return type

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
