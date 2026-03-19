"""Tests for the VM Tracer."""

from runtime.tracer import Tracer


class TestWorkflowLifecycle:

    def test_workflow_start(self, capsys):
        tracer = Tracer()
        tracer.workflow_start("MyWorkflow")

        output = capsys.readouterr().out
        assert "[TRACE] workflow.start workflow=MyWorkflow" in output

    def test_workflow_end(self, capsys):
        tracer = Tracer()
        tracer.record("n", "llm", [], [], {})
        tracer.record("n", "verify", [], [], {})
        tracer.workflow_end()

        output = capsys.readouterr().out
        assert "[TRACE] workflow.end ops=2" in output

    def test_node_enter(self, capsys):
        tracer = Tracer()
        tracer.node_enter("check_facts")

        output = capsys.readouterr().out
        assert "[TRACE] node.enter node=check_facts" in output

    def test_route(self, capsys):
        tracer = Tracer()
        tracer.route("outcome", "approve", "publish")

        output = capsys.readouterr().out
        assert "variable=outcome" in output
        assert "matched=approve" in output
        assert "next=publish" in output


class TestOpTracing:

    def test_op_start_llm(self, capsys):
        tracer = Tracer()
        tracer.op_start("llm", {"prompt": "summarize"}, ["content"])

        output = capsys.readouterr().out
        assert "type=llm" in output
        assert "prompt=summarize" in output

    def test_op_start_verify(self, capsys):
        tracer = Tracer()
        tracer.op_start("verify", {"rule": "no_profanity"}, ["text"])

        output = capsys.readouterr().out
        assert "type=verify" in output
        assert "rule=no_profanity" in output

    def test_op_start_tool(self, capsys):
        tracer = Tracer()
        tracer.op_start("tool", {"name": "web_search"}, [])

        output = capsys.readouterr().out
        assert "type=tool" in output
        assert "name=web_search" in output

    def test_op_end(self, capsys):
        tracer = Tracer()
        tracer.op_end(["summary"], "A short summary.")

        output = capsys.readouterr().out
        assert "output=summary" in output
        assert "A short summary." in output

    def test_op_end_no_outputs(self, capsys):
        tracer = Tracer()
        tracer.op_end([], "value")

        output = capsys.readouterr().out
        assert "output=" in output

    def test_return_with_type(self, capsys):
        tracer = Tracer()
        tracer.return_value(type_name="PublishResult")

        output = capsys.readouterr().out
        assert "return type=PublishResult" in output

    def test_return_with_value(self, capsys):
        tracer = Tracer()
        tracer.return_value(value="done")

        output = capsys.readouterr().out
        assert "return value=done" in output

    def test_return_bare(self, capsys):
        tracer = Tracer()
        tracer.return_value()

        output = capsys.readouterr().out
        assert "[TRACE] return" in output


class TestRecord:

    def test_record_appends_to_entries(self):
        tracer = Tracer()
        tracer.record("start", "llm", ["content"], ["summary"], {"prompt": "summarize"})

        assert len(tracer.entries) == 1
        assert tracer.entries[0] == {
            "node": "start",
            "operation": "llm",
            "inputs": ["content"],
            "outputs": ["summary"],
            "params": {"prompt": "summarize"},
        }

    def test_multiple_records(self):
        tracer = Tracer()
        tracer.record("n1", "llm", [], [], {})
        tracer.record("n2", "verify", [], [], {})

        assert len(tracer.entries) == 2
