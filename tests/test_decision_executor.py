"""Tests for DecisionExecutor."""

import pytest
from unittest.mock import MagicMock, patch

from runtime.decision_executor import DecisionExecutor
from runtime.config import RuntimeConfig


@pytest.fixture
def asset_resolver():
    mock = MagicMock()
    mock.resolve_prompt.return_value = MagicMock(
        model="test-model", template="Policy template: {input_val}"
    )
    return mock


class TestDecisionExecutor:

    def test_decision_human_provider(self, asset_resolver):
        config = RuntimeConfig()
        config.human_callback = MagicMock(return_value="PROCEED")

        executor = DecisionExecutor(asset_resolver, config)
        msg, outcome = executor.execute(
            provider="human_reviewer", input_val={"doc": "data"}
        )

        assert outcome == "PROCEED"
        assert msg is None
        config.human_callback.assert_called_once_with("human_reviewer", {"doc": "data"})

    @patch("runtime.decision_executor.litellm.completion")
    def test_decision_ai_provider(self, mock_completion, asset_resolver):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            '{"outcome": "ESCALATE", "message": {"role": "assistant", "content": "Flagged"}}'
        )
        mock_completion.return_value = mock_response

        config = RuntimeConfig()
        executor = DecisionExecutor(asset_resolver, config)

        msg, outcome = executor.execute(
            provider="risk_policy", input_val={"risk": "high"}
        )

        assert outcome == "ESCALATE"
        assert msg["content"] == "Flagged"
        assert mock_completion.called

    def test_decision_human_provider_fails_without_callback(self, asset_resolver):
        config = RuntimeConfig()
        executor = DecisionExecutor(asset_resolver, config)

        with pytest.raises(RuntimeError, match="No human_callback configured"):
            executor.execute(provider="human_reviewer", input_val={"doc": "data"})

    def test_agent_vm_validates_human_callback_on_load(self):
        from runtime.agent_vm import AgentVM

        graph = {
            "workflow": "test_human",
            "entry": "start",
            "nodes": {
                "start": {
                    "operations": [
                        {
                            "type": "decide",
                            "inputs": ["in_var"],
                            "outputs": ["out_val"],
                            "params": {"provider": "human_reviewer"},
                        }
                    ]
                }
            },
        }
        config = RuntimeConfig()
        with pytest.raises(RuntimeError, match="requires a human_callback"):
            vm = AgentVM(config=config)
            vm.load(graph)

    def test_decision_human_provider_with_message(self, asset_resolver):
        config = RuntimeConfig()
        config.human_callback = MagicMock(
            return_value=({"role": "human", "content": "LGTM"}, "PROCEED")
        )

        executor = DecisionExecutor(asset_resolver, config)
        msg, outcome = executor.execute(
            provider="human_reviewer", input_val={"doc": "data"}
        )

        assert outcome == "PROCEED"
        assert msg["content"] == "LGTM"
