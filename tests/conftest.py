"""Shared fixtures for AIR tests."""

import pytest
from lark import Lark

from air_parser import create_parser


@pytest.fixture(scope="session")
def parser() -> Lark:
    return create_parser()
