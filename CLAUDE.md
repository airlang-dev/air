# AIR Language Compiler

## Project Overview

**AIR** (Agentic Intermediate Representation) is a domain-specific language for describing AI agent workflows in a structured, portable, and governed manner. It acts as an IR layer between high-level orchestration intent and agent VM execution — analogous to how LLVM IR sits between source code and machine code.

**Status: Work in progress — v0.2 spec written, compiler implements v0.1**

## Directory Structure

```
air/
├── spec/
│   ├── 01_air_language_spec_v0_1_0.md     # Language spec v0.1
│   ├── 01_air_language_spec_v0_2_0.md     # Language spec v0.2 (latest)
│   ├── 02_air_ast_spec_v0_1_0.md          # AST node definitions
│   ├── 03_air_cfg_spec_v0_1_0.md          # CFG construction spec
│   ├── 04_air_graph_spec_v0_1_0.md        # AIR Graph spec
│   ├── 05_air_graph_json_schema_v0_1_0.md # JSON schema for .airc artifacts
│   ├── 06_agent_vm_spec_v0_1_0.md         # Agent VM spec
│   ├── air.ebnf                           # Formal EBNF grammar
│   ├── air.lark                           # Lark parser grammar (executable)
│   └── air_graph.schema.json             # JSON schema definition
├── compiler/
│   ├── cli.py                             # CLI entry point (`air compile`, `air backend`)
│   ├── validate_air.py                    # Dev tool — parse + validate + print AST
│   ├── air_ast.py                         # AST dataclass definitions
│   ├── ast_builder.py                     # Lark parse tree -> AIR AST
│   ├── semantic_check.py                  # Semantic validation (SSA, labels, routes)
│   ├── cfg.py                             # CFG dataclasses (CFGNode, CFGEdge, CFG)
│   ├── cfg_builder.py                     # AST -> CFG construction
│   └── air_graph/
│       ├── schema.py                      # AIR Graph dataclasses
│       ├── builder.py                     # CFG -> AIR Graph
│       └── serializer.py                  # AIR Graph -> .airc JSON artifact
├── backends/
│   ├── base_backend.py                    # Backend interface
│   └── langgraph/
│       ├── backend.py                     # LangGraph code generator
│       ├── cli.py                         # Standalone LangGraph CLI
│       └── __main__.py
├── runtime/
│   ├── agent_vm.py                        # Reference Agent VM executor
│   ├── adapters.py                        # Mock runtime adapters
│   └── run_workflow.py                    # Runner: python runtime/run_workflow.py <file.airc>
└── examples/
    ├── v0.1/
    │   ├── example_1.air                  # Aurora Fact Check (full feature demo)
    │   ├── example_2.air                  # Loop backedge test
    │   ├── example_3.air                  # Dead end test
    │   ├── example_4.air                  # Unreachable block test
    │   ├── example_5.air                  # Unknown target test
    │   ├── example_6.air                  # Terminal node test
    │   └── example_7.air                  # Undefined variable test
    └── v0.2/
        ├── FactCheckedPublish.air
        └── MultiModelChat.air
```

## CLI Usage

The compiler is installed as the `air` command via pyproject.toml.

```bash
source .venv/bin/activate

# Compile AIR source to AIR Graph artifact (.airc)
air compile examples/v0.1/example_1.air                # -> build/aurora_fact_check.airc
air compile examples/v0.1/example_1.air -o out.airc   # custom output path

# Generate backend code from .airc artifact
air backend langgraph build/aurora_fact_check.airc     # -> build/aurora_fact_check_langgraph.py
air backend langgraph build/aurora_fact_check.airc -o out.py

# Dev tool — parse + validate + print AST (no artifact output)
python compiler/validate_air.py

# Run a compiled workflow on the reference Agent VM
python runtime/run_workflow.py build/aurora_fact_check.airc
```

## Compiler Pipeline

```
AIR source (.air)
      |
  Lark parser (spec/air.lark)
      |
  Parse tree
      |
  semantic_check.py --- validates SSA, labels, routes, variables
      |
  ast_builder.py --- typed AST (air_ast.py dataclasses)
      |
  cfg_builder.py --- control flow graph (cfg.py dataclasses)
      |
  air_graph/builder.py --- AIR Graph (air_graph/schema.py)
      |
  air_graph/serializer.py --- .airc JSON artifact (validated against schema)
      |
  backends/<name>/backend.py --- executable code (e.g. LangGraph Python)
      |
  runtime/agent_vm.py or LangGraph runtime --- execution
```

## Language Design

### Core Paradigm
- **SSA (Single Static Assignment)**: variables cannot be reassigned
- **Basic blocks with explicit labels**: no implicit control flow
- **Deterministic orchestration** with explicitly marked stochastic ops (`llm`, `decide`)
- **First-class fault handling**: failures are values, not exceptions

### Program Structure (v0.1)
```
@air 0.1
workflow <name> -> <ReturnType> | <ReturnType>
  <entry-block-instructions>
  <label>:
  <block-instructions>
  ...
  fault:
  <fault-handler-instructions>
```

### v0.2 Additions
- Workflow input parameters: `workflow Name(param: Type, ...) -> ReturnTypes`
- `node` syntax (replaces implicit blocks)
- `session` stochastic operation (alongside `llm`, `decide`)
- Governance modes: `@air 0.2 [mode=normal|strict]`
  - `normal`: governance primitives optional
  - `strict`: compiler rejects workflows where LLM output routes without verify->gate chain

### Instructions
| Category | Instruction | Returns |
|----------|------------|---------|
| Stochastic | `llm(prompt)` | `Message` |
| Deterministic | `tool(name, args...)` | `Artifact \| Fault` |
| Extraction | `transform(value, Type) via llm(prompt)` | `Type \| Fault` |
| Governance | `verify(claims, rule)` | `Verdict + Evidence` |
| Aggregation | `aggregate([verdicts], strategy)` | `Consensus` |
| Gate | `gate(verdict\|consensus)` | `Outcome` |
| Decision | `decide(provider, input?)` | `Message? + Outcome` |
| Routing | `route(value) { pattern -> label }` | -- |
| Parallel | `parallel { statements }` | -- |
| Loop | `loop name [max=N] { ... }` | -- |

### Built-in Types
`Message`, `Artifact`, `Fault`, `Verdict`, `Consensus`, `Outcome`, `Evidence`, `Claim[]`

### Fault Semantics
Only three operations produce `Fault`:
- `transform via llm` -- schema validation failure after retries
- `tool` -- semantic operation failure after retries
- `loop` -- iteration limit exceeded

`llm` and `decide` are stochastic and never produce `Fault` (transport failures handled by runtime).

### Route Exhaustiveness
Routes on `Outcome` values must cover: `PROCEED`, `RETRY`, `ESCALATE`, `HALT` (or use `default`).

## Backends

Backends are pluggable via `backends/base_backend.py`. Registry in `compiler/cli.py`:

```python
BACKENDS = {
    "langgraph": "backends.langgraph.backend:LangGraphBackend",
}
```

The LangGraph backend generates a self-contained Python file with:
- `StateGraph` from langgraph
- Node functions with runtime adapter calls
- Conditional edge routing functions
- Trace logging on every operation

## What Is Implemented vs TODO

### Implemented
- [x] Full language spec v0.1 + v0.2
- [x] Lark grammar covering all v0.1 constructs
- [x] AST dataclass definitions + parse tree -> AST builder
- [x] Semantic validation: SSA, label uniqueness, route exhaustiveness, variable existence
- [x] CFG builder (AST -> control flow graph)
- [x] AIR Graph builder + serializer (CFG -> .airc JSON artifact)
- [x] JSON schema validation for .airc artifacts
- [x] CLI: `air compile` and `air backend` commands
- [x] LangGraph backend code generator
- [x] Reference Agent VM runtime with mock adapters
- [x] 7 v0.1 example workflows (feature demo + edge case tests)
- [x] 2 v0.2 example workflows (FactCheckedPublish, MultiModelChat)

### TODO
- [ ] Compiler support for v0.2 language features (grammar, AST, semantics)
- [ ] Type system validation (type coupling rules, Section 22 of language spec)
- [ ] Reachability / dead code analysis
- [ ] Error messages with source locations
- [ ] Tests

## Key Files to Read First

1. [spec/01_air_language_spec_v0_2_0.md](spec/01_air_language_spec_v0_2_0.md) -- latest language semantics
2. [examples/v0.1/example_1.air](examples/v0.1/example_1.air) -- v0.1 reference workflow
2b. [examples/v0.2/](examples/v0.2/) -- v0.2 example workflows
3. [compiler/cli.py](compiler/cli.py) -- CLI entry point
4. [compiler/air_ast.py](compiler/air_ast.py) -- AST node structure
5. [backends/langgraph/backend.py](backends/langgraph/backend.py) -- code generation

## Dependencies

- Python 3.12+ (`.venv` present, using 3.14)
- `lark` -- parser library
- `jsonschema` -- .airc artifact validation

Activate venv: `source .venv/bin/activate`
