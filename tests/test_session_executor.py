"""Tests for SessionExecutor."""

import pytest
from unittest.mock import MagicMock, patch, call

from runtime.session_executor import SessionExecutor
from runtime.config import RuntimeConfig


@pytest.fixture
def protocol():
    return {
        "name": "parley_v1",
        "turn_order": "round_robin",
        "moves": ["DISCUSS", "PROPOSE", "AGREE", "COUNTER"],
        "resolution": {
            "strategy": "unanimous",
            "outcomes": {
                "AGREE": "PROCEED",
                "COUNTER": "RETRY",
            },
            "default": "ESCALATE",
        },
    }


@pytest.fixture
def members():
    return [
        {"role": "Analyst", "model": "gpt-4", "prompt": "You analyze risks"},
        {"role": "Reviewer", "model": "gpt-4", "prompt": "You review proposals"},
    ]


@pytest.fixture
def asset_resolver(protocol):
    mock = MagicMock()
    mock.resolve_protocol.return_value = protocol
    return mock


def _mock_llm_response(content):
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


class TestSessionExecutor:

    @patch("runtime.session_executor.call_llm")
    def test_round_robin_unanimous_agree(self, mock_call_llm, asset_resolver, members):
        mock_call_llm.side_effect = [
            "AGREE: Looks good to me",
            "AGREE: I concur with the analysis",
        ]

        config = RuntimeConfig()
        executor = SessionExecutor(asset_resolver, config)
        outcome, history = executor.execute(members, "parley_v1", [])

        assert outcome == "PROCEED"
        assert len(history) == 2
        assert history[0]["role"] == "Analyst"
        assert "Looks good to me" in history[0]["content"]
        assert history[1]["role"] == "Reviewer"
        assert "I concur" in history[1]["content"]

    @patch("runtime.session_executor.call_llm")
    def test_round_robin_mixed_moves(self, mock_call_llm, asset_resolver, members):
        mock_call_llm.side_effect = [
            "AGREE: This is fine",
            "COUNTER: I disagree with the approach",
        ]

        config = RuntimeConfig()
        executor = SessionExecutor(asset_resolver, config)
        outcome, history = executor.execute(members, "parley_v1", [])

        assert outcome == "ESCALATE"
        assert len(history) == 2

    @patch("runtime.session_executor.call_llm")
    def test_round_robin_all_counter(self, mock_call_llm, asset_resolver, members):
        mock_call_llm.side_effect = [
            "COUNTER: Too risky",
            "COUNTER: Agreed, too risky",
        ]

        config = RuntimeConfig()
        executor = SessionExecutor(asset_resolver, config)
        outcome, history = executor.execute(members, "parley_v1", [])

        assert outcome == "RETRY"
        assert len(history) == 2

    @patch("runtime.session_executor.call_llm")
    def test_serial_history_accumulation(self, mock_call_llm, asset_resolver, members):
        """Each member sees the cumulative history from previous members."""
        mock_call_llm.side_effect = [
            "DISCUSS: Initial thoughts",
            "AGREE: Building on those thoughts",
        ]

        config = RuntimeConfig()
        executor = SessionExecutor(asset_resolver, config)
        executor.execute(members, "parley_v1", [])

        first_call_messages = mock_call_llm.call_args_list[0]
        second_call_messages = mock_call_llm.call_args_list[1]

        first_history = first_call_messages[1]["messages"]
        second_history = second_call_messages[1]["messages"]

        assert len(second_history) > len(first_history)

    @patch("runtime.session_executor.call_llm")
    def test_non_decisive_moves_ignored_in_resolution(
        self, mock_call_llm, asset_resolver, members
    ):
        """Moves not in outcomes map are non-decisive and ignored."""
        mock_call_llm.side_effect = [
            "DISCUSS: Just sharing thoughts",
            "AGREE: I approve",
        ]

        config = RuntimeConfig()
        executor = SessionExecutor(asset_resolver, config)
        outcome, history = executor.execute(members, "parley_v1", [])

        assert outcome == "PROCEED"

    @patch("runtime.session_executor.call_llm")
    def test_existing_history_preserved(self, mock_call_llm, asset_resolver, members):
        """Pre-existing history is passed to members and preserved in output."""
        existing = [{"role": "system", "content": "Prior context"}]
        mock_call_llm.side_effect = [
            "AGREE: Understood",
            "AGREE: Confirmed",
        ]

        config = RuntimeConfig()
        executor = SessionExecutor(asset_resolver, config)
        outcome, history = executor.execute(members, "parley_v1", existing)

        assert len(history) == 3
        assert history[0] == existing[0]
