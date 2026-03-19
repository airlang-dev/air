"""Tests for the VariableScope."""

from runtime.variable_scope import VariableScope


class TestResolve:

    def test_simple_variable(self):
        resolver = VariableScope({"name": "Alice"})
        assert resolver.resolve("name") == "Alice"

    def test_dotted_variable_dict(self):
        resolver = VariableScope({"result": {"status": "approved"}})
        assert resolver.resolve("result.status") == "approved"

    def test_dotted_variable_object(self):
        class Obj:
            status = "rejected"

        resolver = VariableScope({"result": Obj()})
        assert resolver.resolve("result.status") == "rejected"


class TestGet:

    def test_get_returns_value_if_exists(self):
        resolver = VariableScope({"x": 42})
        assert resolver.get("x") == 42

    def test_get_returns_name_as_fallback(self):
        resolver = VariableScope({})
        assert resolver.get("missing") == "missing"


class TestStore:

    def test_store_single_value(self):
        resolver = VariableScope({})
        resolver.store(["summary"], "hello")
        assert resolver.resolve("summary") == "hello"

    def test_store_tuple_unpacks(self):
        resolver = VariableScope({})
        resolver.store(["msg", "outcome"], ("message", "approve"))
        assert resolver.resolve("msg") == "message"
        assert resolver.resolve("outcome") == "approve"

    def test_store_empty_names_is_noop(self):
        resolver = VariableScope({})
        resolver.store([], "value")
        assert resolver._vars == {}
