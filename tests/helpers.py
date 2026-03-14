"""Shared test helpers for AIR tests."""

from pathlib import Path

from ast_builder import ASTBuilder
from air_ast import Program

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples" / "v0.2"


def load_fixture(name: str) -> str:
    """Load a .air fixture file by name (without extension)."""
    return (FIXTURES_DIR / f"{name}.air").read_text()


def build_fixture(parser, name: str) -> Program:
    """Parse and build AST from a fixture file."""
    tree = parser.parse(load_fixture(name))
    return ASTBuilder().build(tree)


def find_node(program: Program, node_name: str):
    """Find a node by name in the first workflow."""
    for node in program.workflows[0].nodes:
        if node.name == node_name:
            return node
    raise ValueError(f"Node {node_name!r} not found")
