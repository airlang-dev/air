"""Shared fixtures for AIR tests."""

from pathlib import Path

import pytest
from lark import Lark

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def parser() -> Lark:
    grammar = (ROOT / "spec" / "v0.2" / "air.lark").read_text()
    return Lark(grammar)
