"""Tests for the air CLI."""

from argparse import Namespace
from pathlib import Path
from unittest.mock import patch, MagicMock

from compiler.cli import run_workflow

COMPILED_DIR = Path(__file__).resolve().parent / "fixtures" / "compiled"
ASSETS_DIR = str(Path(__file__).resolve().parent / "fixtures" / "assets")


def _mock_litellm_response(content):
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


class TestAirRun:

    def test_run_executes_workflow(self, capsys):
        """air run should load and execute a compiled .airc file."""
        args = Namespace(
            airc_file=str(COMPILED_DIR / "SimpleLLM.airc"),
            input=["content=test article"],
            input_file=None,
            config=None,
            assets=ASSETS_DIR,
            callback="runtime.callbacks:stdin_callback",
        )
        with patch("runtime.llm_utils.litellm.completion") as mock:
            mock.return_value = _mock_litellm_response("A summary.")
            run_workflow(args)

        captured = capsys.readouterr()
        assert "[VM] result:" in captured.out
        assert "A summary." in captured.out

    def test_run_parses_multiple_inputs(self, capsys):
        args = Namespace(
            airc_file=str(COMPILED_DIR / "SimpleLLM.airc"),
            input=["content=hello", "extra=world"],
            input_file=None,
            config=None,
            assets=ASSETS_DIR,
            callback="runtime.callbacks:stdin_callback",
        )
        with patch("runtime.llm_utils.litellm.completion") as mock:
            mock.return_value = _mock_litellm_response("Result.")
            run_workflow(args)

        captured = capsys.readouterr()
        assert "[VM] result:" in captured.out
