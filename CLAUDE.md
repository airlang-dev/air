# AIR

**AIR** (Agentic Intermediate Representation) is a project for describing, compiling, and executing AI agent workflows in a structured, portable, and governed manner. Write in AIR, run anywhere.

```
AIR
├── AIR Language    — the .air source language
├── AIR Compiler    — parses and compiles .air to .airc
├── AIR Graph       — the portable IR (.airc files)
├── AIR Agent VM    — the reference runtime
├── AIR Backends    — LangGraph, Agent Spec, Dify, etc.
└── AIR Assets      — prompts, rules, schemas, providers, protocols
```

**Status: v0.2 — AIR Language, Compiler, Graph, Agent VM, and LangGraph backend fully implemented.**

## CLI Usage

```bash
source .venv/bin/activate

air compile examples/v0.2/FactCheckedPublish.air       # -> build/FactCheckedPublish.airc
air compile examples/v0.2/KitchenSink.air -o out.airc  # custom output path
air backend langgraph build/FactCheckedPublish.airc     # -> build/FactCheckedPublish_langgraph.py
python runtime/run_workflow.py build/FactCheckedPublish.airc
python -m pytest tests/ -v
```

## AIR Compiler Pipeline

```
AIR source (.air)
  → Lark parser (spec/v0.2/air.lark + air_parser.py AirIndenter)
  → Parse tree
  → ast_builder.py → typed AST (air_ast.py dataclasses)
  → semantic_check.py → validates SSA, node names, routes, variables
  → cfg_builder.py → control flow graph (cfg.py dataclasses)
  → air_graph/builder.py → AIR Graph (air_graph/schema.py)
  → air_graph/serializer.py → .airc JSON artifact (validated against schema)
  → backends/<name>/backend.py → executable code (e.g. LangGraph Python)
  → runtime/agent_vm.py or LangGraph runtime → execution
```

## AIR Language Design (v0.2)

### Core Paradigm
- **SSA (Single Static Assignment)**: variables cannot be reassigned within a node
- **Nodes with explicit names**: no implicit control flow
- **Deterministic orchestration** with explicitly marked stochastic ops (`llm`, `decide`, `session`)
- **First-class fault handling**: failures are values, not exceptions

### Instructions
| Category | Instruction | Returns |
|----------|------------|---------|
| Stochastic | `llm(prompt, args...)` | `Message` |
| Stochastic | `session(members, protocol, history)` | result with `.consensus` |
| Deterministic | `tool(name, args...)` | `Artifact \| Fault` |
| Composition | `map(collection, Workflow) [concurrency=N, on_error=X]` | `Type[]` |
| Extraction | `transform(value) as Type via llm(prompt)` | `Type \| Fault` |
| Extraction | `transform(value) as Type via func(name)` | `Type` |
| Governance | `verify(input, rule)` | `Verdict + Evidence` |
| Aggregation | `aggregate([verdicts], strategy)` | `Consensus` |
| Gate | `gate(verdict\|consensus)` | `Outcome` |
| Decision | `decide(provider, input?)` | `Message? + Outcome` |
| Routing | `route value:` + indented cases | -- |
| Parallel | `parallel:` / `parallel [partial]:` | -- |

### Built-in Types
`Message`, `Artifact`, `Fault`, `Verdict`, `Consensus`, `Outcome`, `Evidence`, `Claim[]`

## Adding a New Language Construct

When adding a new instruction or expression type, touch these files in order:

1. **Test fixture** — `tests/fixtures/<name>.air` — valid .air file exercising the construct
2. **Grammar** — `spec/v0.2/air.lark` — add rule, wire into expression alternatives
3. **AST dataclass** — `compiler/air_ast.py` — new `@dataclass` extending `Expression`
4. **AST builder** — `compiler/ast_builder.py` — `_build_<name>()` method + dispatch in `_build_expression()`
5. **Semantic check** — `compiler/semantic_check.py` — validation in `_check_expression_refs()`
6. **CFG builder** — `compiler/cfg_builder.py` — usually no change (expressions don't create edges)
7. **AIR Graph builder** — `compiler/air_graph/builder.py` — emit `AirGraphOperation` in `_convert_assign()`
8. **JSON schema** — `spec/v0.2/air_graph.schema.json` — add to operation type enum
9. **LangGraph backend** — `backends/langgraph/backend.py` — code generation for the operation type
10. **Agent VM** — `runtime/agent_vm.py` — execution handler + import adapter
11. **Adapters** — `runtime/adapters.py` — mock adapter function
12. **Tests** — add cases to `test_grammar.py`, `test_ast_builder.py`, `test_semantic_check.py`, `test_air_graph.py`, `test_langgraph_backend.py`

## Gotchas and Non-Obvious Constraints

- **AirIndenter emits `_DEDENT` before `_NL`** (reversed from Lark's default) so `_NL` remains available as a statement separator at the outer block level. See `compiler/air_parser.py`.
- **Multi-line constructors don't parse.** The grammar doesn't support newlines inside constructor field lists — flatten to single line.
- **Keywords are reserved via Lark terminal priority**, not the semantic checker. Writing `"map"` in a grammar rule auto-creates a terminal that takes priority over `IDENTIFIER`. This means `map`, `func`, `llm`, etc. cannot be used as node names without any explicit check.
- **Bracket modifiers are scoped to their construct**, not global keywords. `concurrency`/`on_error` are map modifiers; `max`/`fallback` are node modifiers. They live in separate grammar rules.
- **No type checking exists.** Types are parsed and stored in the AST but never validated. No type coupling, no field access validation, no collection homogeneity. This is a full-pipeline feature touching every stage — don't try to add it piecemeal.
- **No asset resolution.** Prompts, rules, schemas, providers, func names are all treated as opaque strings. The runtime resolves them by name.
- **No cross-file workflow references.** `map(items, Workflow)` only validates against workflows in the same .air file. A cross-file compilation model doesn't exist.
- **No governance enforcement.** `[mode=strict]` is parsed and stored but the compiler doesn't enforce the verify→gate chain requirement.
- **Bare statements** — `tool(...)`, `llm(...)`, `session(...)` as bare statements (no assignment) are parsed as their respective call types at the grammar level, not as `node_call`. The AST builder handles them directly.

## Testing

Tests use shared `.air` fixture files in `tests/fixtures/`. Fixtures must be semantically valid (variables declared as workflow params). Test helpers in `tests/helpers.py`:
- `load_fixture(name)` — load fixture source by name
- `build_fixture(parser, name)` — parse + build AST from fixture
- `find_node(program, node_name)` — locate a node by name

pytest is configured in `pyproject.toml` with `pythonpath = ["tests", "compiler"]`.

## TODO

- [ ] Type system validation (type coupling rules, Section 22 of language spec)
- [ ] Governance enforcement (`[mode=strict]` verify→gate chain)
- [ ] Reachability / dead code analysis
- [ ] Error messages with source locations
- [ ] Cross-file workflow references
- [ ] AIR Assets — asset manifest, resolution, and validation

## Key Files to Read First

1. `spec/v0.2/01_air_language_spec.md` — AIR Language semantics
2. `compiler/air_ast.py` — AST node structure
3. `compiler/ast_builder.py` — parse tree → AST
4. `examples/v0.2/KitchenSink.air` — comprehensive example
5. `backends/langgraph/backend.py` — code generation

## Dependencies

- Python 3.12+ (`.venv` present)
- `lark` — parser library
- `pytest` — testing
- `jsonschema` — .airc artifact validation
