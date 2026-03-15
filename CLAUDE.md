# AIR Language Compiler

## Project Overview

**AIR** (Agentic Intermediate Representation) is a domain-specific language for describing AI agent workflows in a structured, portable, and governed manner. It acts as an IR layer between high-level orchestration intent and agent VM execution — analogous to how LLVM IR sits between source code and machine code.

**Status: Work in progress — v0.2 grammar, parser, AST builder implemented with tests. Semantic check, CFG, and downstream pipeline still on v0.1.**

## Directory Structure

```
air/
├── spec/
│   ├── v0.1/                              # Frozen reference
│   │   ├── 01_air_language_spec.md
│   │   ├── 02_air_ast_spec.md
│   │   ├── 03_air_cfg_spec.md
│   │   ├── 04_air_graph_spec.md
│   │   ├── 05_air_graph_json_schema_spec.md
│   │   ├── 06_agent_vm_spec.md
│   │   ├── air.ebnf
│   │   ├── air.lark
│   │   └── air_graph.schema.json
│   └── v0.2/                              # Active development
│       ├── 01_air_language_spec.md
│       └── air.lark
├── compiler/
│   ├── cli.py                             # CLI entry point (`air compile`, `air backend`)
│   ├── validate_air.py                    # Dev tool — parse + validate + print AST
│   ├── air_parser.py                      # Parser factory with AirIndenter postlex
│   ├── air_ast.py                         # AST dataclass definitions (v0.2)
│   ├── ast_builder.py                     # Lark parse tree -> AIR AST (v0.2)
│   ├── semantic_check.py                  # Semantic validation (v0.2)
│   ├── cfg.py                             # CFG dataclasses (v0.2)
│   ├── cfg_builder.py                     # AST -> CFG construction (v0.2)
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
├── tests/
│   ├── conftest.py                        # Shared pytest fixtures (parser)
│   ├── helpers.py                         # Test helpers (load_fixture, build_fixture, find_node)
│   ├── test_grammar.py                    # Lark grammar tests (45 tests)
│   ├── test_ast_builder.py                # AST builder tests (36 tests)
│   └── fixtures/                          # Shared .air test fixtures
│       ├── basic.air                      # Minimal valid program
│       ├── basic_strict.air               # With [mode=strict]
│       ├── workflow_params.air            # Workflow with typed params
│       ├── workflow_no_params.air         # Workflow without params
│       ├── nodes.air                      # Node variants (params, max, fallback)
│       ├── llm.air                        # LLM call variants
│       ├── tool.air                       # Tool calls (assigned + bare)
│       ├── transform.air                  # Transform with/without via
│       ├── governance.air                 # Verify, aggregate, gate
│       ├── decide_session.air             # Decide, session
│       ├── route.air                      # All route variants
│       ├── parallel.air                   # Parallel strict + partial
│       ├── transition.air                 # Unconditional node call
│       ├── return_fields.air              # Return with constructor fields
│       └── list_assignment.air            # List literal assignment
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
        ├── MultiModelChat.air
        └── KitchenSink.air                # Comprehensive v0.2 feature demo
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

# Run tests
python -m pytest tests/ -v
```

## Compiler Pipeline

```
AIR source (.air)
      |
  Lark parser (spec/v0.2/air.lark + air_parser.py AirIndenter)
      |
  Parse tree
      |
  ast_builder.py --- typed AST (air_ast.py dataclasses)
      |
  semantic_check.py --- validates SSA, node names, routes, variables
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
- **Nodes with explicit names**: no implicit control flow
- **Deterministic orchestration** with explicitly marked stochastic ops (`llm`, `decide`, `session`)
- **First-class fault handling**: failures are values, not exceptions

### Program Structure (v0.2)
```
@air 0.2 [mode=strict]

workflow Name(param: Type) -> ReturnType | ReturnType:
    node entry_node:
        <statements>

    node other_node(param) [max=N]:
        <statements>

    node fallback_node [fallback]:
        <statements>
```

### Instructions
| Category | Instruction | Returns |
|----------|------------|---------|
| Stochastic | `llm(prompt, args...)` | `Message` |
| Stochastic | `session(members, protocol, history)` | result with `.consensus` |
| Deterministic | `tool(name, args...)` | `Artifact \| Fault` |
| Extraction | `transform(value) as Type via llm(prompt)` | `Type \| Fault` |
| Governance | `verify(input, rule)` | `Verdict + Evidence` |
| Aggregation | `aggregate([verdicts], strategy)` | `Consensus` |
| Gate | `gate(verdict\|consensus)` | `Outcome` |
| Decision | `decide(provider, input?)` | `Message? + Outcome` |
| Routing | `route value:` + indented cases | -- |
| Parallel | `parallel:` / `parallel [partial]:` | -- |

### Built-in Types
`Message`, `Artifact`, `Fault`, `Verdict`, `Consensus`, `Outcome`, `Evidence`, `Claim[]`

### Fault Semantics
Only two operations produce `Fault` in v0.2:
- `transform ... via llm` -- schema validation failure after retries
- `tool` -- semantic operation failure after retries

Bounded nodes (`[max=N]`) reaching their limit transition to the fallback node.

`llm`, `decide`, and `session` are stochastic and never produce `Fault` (transport failures handled by runtime).

### Route Exhaustiveness
Routes on `Outcome` values must cover: `PROCEED`, `RETRY`, `ESCALATE`, `HALT` (or use `else`).

### Governance Modes
- `[mode=normal]` (default): governance primitives optional
- `[mode=strict]`: compiler rejects workflows where LLM output routes without verify->gate chain

## Parser Notes

The v0.2 grammar uses indentation-aware parsing via a custom `AirIndenter` postlex in `compiler/air_parser.py`. Key detail: the indenter emits `_DEDENT` tokens **before** `_NL` (reversed from Lark's default) so that `_NL` remains available as a statement separator at the outer block level.

Bare `tool(...)`, `llm(...)`, `session(...)` statements are parsed as their respective call types at the grammar level (not as `node_call`). The AST builder handles them directly.

## Semantic Check

The v0.2 semantic checker (`compiler/semantic_check.py`) operates on the typed AST and validates:
- **Node name uniqueness** within each workflow
- **SSA** — no variable reassignment within a node; workflow params count as defined (no shadowing)
- **Variable existence** — workflow params visible in all nodes, node params scoped to node, uppercase-first names treated as types/assets
- **Route target existence** — targets must reference valid node names
- **Route exhaustiveness** — Outcome routes need PROCEED/RETRY/ESCALATE/HALT or `else`
- **Fallback limit** — at most one `[fallback]` node per workflow
- **Return type validity** — constructor type must be in workflow's declared return types
- **Node termination** — every node must end with return, route, node call, or unreachable

Keyword node names (llm, tool, verify, etc.) are rejected at the grammar level — all instruction keywords create Lark terminals that take priority over IDENTIFIER.

## Testing

Tests use shared `.air` fixture files in `tests/fixtures/`. Fixtures are semantically valid (variables declared as workflow params). Test helpers in `tests/helpers.py`:
- `load_fixture(name)` — load fixture source by name
- `build_fixture(parser, name)` — parse + build AST from fixture
- `find_node(program, node_name)` — locate a node by name

pytest is configured in `pyproject.toml` with `pythonpath = ["tests", "compiler"]`.

## What Is Implemented vs TODO

### Implemented
- [x] Full language spec v0.1 + v0.2
- [x] Lark grammar v0.2 with indentation-aware parsing
- [x] AST dataclass definitions v0.2
- [x] AST builder v0.2 (parse tree -> typed AST)
- [x] Semantic check v0.2 (SSA, variable existence, routes, fallback, return types, termination)
- [x] CFG builder v0.2 (AST -> control flow graph)
- [x] Grammar tests (45) + AST builder tests (36) + semantic check tests (48) + CFG tests (18) = 147 tests
- [x] Shared test fixtures (15 .air files)
- [x] 3 v0.2 example workflows (FactCheckedPublish, MultiModelChat, KitchenSink)
- [x] v0.1 AIR Graph, serializer (not yet updated for v0.2)
- [x] v0.1 LangGraph backend code generator
- [x] v0.1 Reference Agent VM runtime with mock adapters

### TODO
- [ ] AIR Graph builder + serializer v0.2
- [ ] LangGraph backend v0.2
- [ ] Type system validation (type coupling rules, Section 22 of language spec)
- [ ] Reachability / dead code analysis
- [ ] Error messages with source locations

## Key Files to Read First

1. [spec/v0.2/01_air_language_spec.md](spec/v0.2/01_air_language_spec.md) -- latest language semantics
2. [compiler/air_ast.py](compiler/air_ast.py) -- AST node structure (v0.2)
3. [compiler/ast_builder.py](compiler/ast_builder.py) -- parse tree -> AST (v0.2)
4. [examples/v0.2/KitchenSink.air](examples/v0.2/KitchenSink.air) -- comprehensive v0.2 example
5. [compiler/cli.py](compiler/cli.py) -- CLI entry point
6. [backends/langgraph/backend.py](backends/langgraph/backend.py) -- code generation

## Dependencies

- Python 3.12+ (`.venv` present)
- `lark` -- parser library
- `pytest` -- testing
- `jsonschema` -- .airc artifact validation

Activate venv: `source .venv/bin/activate`
