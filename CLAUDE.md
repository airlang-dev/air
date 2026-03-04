# AIR Language Compiler

## Project Overview

**AIR** (Agentic Intermediate Representation) is a domain-specific language for describing AI agent workflows in a structured, portable, and governed manner. It acts as an IR layer between high-level orchestration intent and agent VM execution — analogous to how LLVM IR sits between source code and machine code.

**Status: Work in progress — v0.1.0 alpha**

## Directory Structure

```
air/
├── spec/
│   ├── 01_air_language_spec_v0_1_0.md   # Language semantics & design rationale
│   ├── 02_air_ast_spec_v0_1_0.md        # AST node definitions
│   ├── 03_air_cfg_spec_v0_1_0.md        # CFG construction spec (not yet implemented)
│   ├── air.ebnf                         # Formal EBNF grammar
│   └── air.lark                         # Lark parser grammar (executable)
├── compiler/
│   ├── validate_air.py                  # Main entry point — parse + validate + print AST
│   ├── air_ast.py                       # AST dataclass definitions
│   ├── ast_builder.py                   # Lark parse tree → AIR AST
│   └── semantic_check.py               # Semantic validation (SSA, labels, routes)
└── examples/
    └── aurora.air                       # Reference workflow demonstrating all features
```

## Running the Compiler

```bash
cd /Users/et/Projects/air
python compiler/validate_air.py
```

This will:
1. Load the Lark grammar from `spec/air.lark`
2. Parse `examples/aurora.air`
3. Run semantic checks (SSA, label uniqueness, route exhaustiveness)
4. Build and pretty-print the AST

## Language Design

### Core Paradigm
- **SSA (Single Static Assignment)**: variables cannot be reassigned
- **Basic blocks with explicit labels**: no implicit control flow
- **Deterministic orchestration** with explicitly marked stochastic ops (`llm`, `decide`)
- **First-class fault handling**: failures are values, not exceptions

### Program Structure
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
| Routing | `route(value) { pattern -> label }` | — |
| Parallel | `parallel { statements }` | — |
| Loop | `loop name [max=N] { ... }` | — |

### Built-in Types
`Message`, `Artifact`, `Fault`, `Verdict`, `Consensus`, `Outcome`, `Evidence`, `Claim[]`

### Fault Semantics
Only three operations produce `Fault`:
- `transform via llm` — schema validation failure after retries
- `tool` — semantic operation failure after retries
- `loop` — iteration limit exceeded

`llm` and `decide` are stochastic and never produce `Fault` (transport failures handled by runtime).

### Route Exhaustiveness
Routes on `Outcome` values must cover: `PROCEED`, `RETRY`, `ESCALATE`, `HALT` (or use `default`).

## Compiler Architecture

```
AIR source (.air)
      ↓
  Lark parser (air.lark)
      ↓
  Parse tree
      ↓
  ast_builder.py → AIR AST (air_ast.py)
      ↓
  semantic_check.py → validated AST
      ↓
  [TODO] CFG builder (spec: 03_air_cfg_spec_v0_1_0.md)
      ↓
  [TODO] EGIR (Execution Graph IR)
      ↓
  [TODO] Agent VM
```

## What Is Implemented vs TODO

### Implemented
- [x] Full language spec (3 documents + 2 grammar formats)
- [x] Lark grammar covering all language constructs
- [x] AST dataclass definitions
- [x] Parse tree → AST builder
- [x] Semantic validation: SSA, label uniqueness, route exhaustiveness, variable existence
- [x] Aurora reference example

### TODO
- [ ] CFG builder (spec exists in `03_air_cfg_spec_v0_1_0.md`)
- [ ] Type system validation (type coupling rules, Section 22 of language spec)
- [ ] Reachability / dead code analysis
- [ ] EGIR compilation
- [ ] Agent VM runtime integration
- [ ] Error messages with source locations
- [ ] CLI tooling

## Key Files to Read First

1. [spec/01_air_language_spec_v0_1_0.md](spec/01_air_language_spec_v0_1_0.md) — start here for language semantics
2. [examples/aurora.air](examples/aurora.air) — reference workflow showing all major patterns
3. [compiler/validate_air.py](compiler/validate_air.py) — main entry point
4. [compiler/air_ast.py](compiler/air_ast.py) — AST node structure

## Dependencies

- Python 3.14 (`.venv` present)
- `lark` — parser library
- `black` — code formatter

Activate venv: `source .venv/bin/activate`
