"""Tests for the air CLI."""

from argparse import Namespace
from pathlib import Path

from compiler.cli import run_workflow

COMPILED_DIR = Path(__file__).resolve().parent / "fixtures" / "compiled"


class TestAirRun:

    def test_run_executes_workflow(self, capsys):
        """air run should load and execute a compiled .airc file."""
        args = Namespace(
            airc_file=str(COMPILED_DIR / "SimpleLLM.airc"),
            input=["content=test article"],
            input_file=None,
            config=None,
            assets=None,
        )
        run_workflow(args)

        captured = capsys.readouterr()
        assert "[VM] result:" in captured.out
        assert "LLM" in captured.out

    def test_run_parses_multiple_inputs(self, capsys):
        args = Namespace(
            airc_file=str(COMPILED_DIR / "SimpleLLM.airc"),
            input=["content=hello", "extra=world"],
            input_file=None,
            config=None,
            assets=None,
        )
        run_workflow(args)

        captured = capsys.readouterr()
        assert "[VM] result:" in captured.out
