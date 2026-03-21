"""Execution environment for a single AIR workflow invocation."""


from runtime.aggregate_executor import AggregateExecutor
from runtime.edge_resolver import EdgeResolver
from runtime.gate_executor import GateExecutor
from runtime.llm_executor import LLMExecutor
from runtime.map_executor import MapExecutor
from runtime.decision_executor import DecisionExecutor
from runtime.tracer import Tracer
from runtime.transform_executor import TransformExecutor
from runtime.variable_scope import VariableScope
from runtime.verify_executor import VerifyExecutor


class WorkflowRunner:
    """An execution thread for a specific AIR graph."""

    def __init__(self, vm, graph):
        self.vm = vm
        self._graph = graph
        self._nodes = graph["nodes"]
        self._vars = None
        self._tracer = None

    def run(self, inputs=None):
        """Execute the workflow."""
        self._vars = VariableScope(inputs)
        self._tracer = Tracer()
        current = self._graph["entry"]

        self._tracer.workflow_start(self._graph["workflow"])

        while True:
            node = self._nodes[current]
            self._tracer.node_enter(current)

            result = self._execute_operations(node.get("operations", []), current)
            if result is not None:
                self._tracer.workflow_end()
                return result

            if node.get("terminal") and not node.get("edges"):
                self._tracer.workflow_end()
                return None

            edges = node.get("edges", [])
            if not edges:
                self._tracer.workflow_end()
                return None

            route_var = node.get("route_variable")
            value = self._vars.resolve(route_var) if route_var else None

            target, matched = EdgeResolver.resolve(value, edges)
            if target not in self._nodes:
                raise RuntimeError(
                    f"VM error: invalid edge target '{target}' from node '{current}'"
                )
            self._tracer.route(route_var, matched, target)
            current = target

    def _execute_operations(self, operations, node_id):
        for op in operations:
            op_type = op["type"]
            inputs = op["inputs"]
            out_names = self._output_names(op["outputs"])
            params = op.get("params", {})

            self._tracer.op_start(op_type, params, inputs)

            handler = getattr(self, f"_execute_{op_type}", None)
            if handler is None:
                raise RuntimeError(f"unknown operation type: {op_type}")

            result = handler(params, inputs, out_names)

            if op_type == "return":
                self._tracer.record(node_id, op_type, inputs, out_names, params)
                return result

            self._vars.store(out_names, result)
            self._tracer.op_end(out_names, result)
            self._tracer.record(node_id, op_type, inputs, out_names, params)

        return None

    def _execute_llm(self, params, inputs, out_names):
        prompt_name = params["prompt"]
        input_vals = [self._vars.get(i) for i in inputs]
        executor = LLMExecutor(self.vm.asset_resolver, self.vm.config)
        return executor.execute(prompt_name, input_vals)

    def _execute_transform(self, params, inputs, out_names):
        input_val = self._vars.resolve(inputs[0])
        executor = TransformExecutor(self.vm.asset_resolver, self.vm.config)
        return executor.execute(input_val, params)

    def _execute_verify(self, params, inputs, out_names):
        input_val = self._vars.resolve(inputs[0])
        rule_name = params["rule"]
        executor = VerifyExecutor(self.vm.asset_resolver, self.vm.config)
        return executor.execute(input_val, rule_name)

    def _execute_aggregate(self, params, inputs, out_names):
        verdicts = [self._vars.resolve(i) for i in inputs]
        strategy = params["strategy"]
        return AggregateExecutor().execute(verdicts, strategy)

    def _execute_gate(self, params, inputs, out_names):
        input_val = self._vars.resolve(inputs[0])
        return GateExecutor().execute(input_val)

    def _execute_decide(self, params, inputs, out_names):
        input_val = self._vars.get(inputs[0]) if inputs else None
        provider = params["provider"]
        executor = DecisionExecutor(self.vm.asset_resolver, self.vm.config)
        msg, outcome = executor.execute(provider, input_val)
        if len(out_names) >= 2:
            return msg, outcome
        return outcome

    def _execute_session(self, params, inputs, out_names):
        from runtime.session_executor import SessionExecutor

        members = self._vars.get(inputs[0]) if len(inputs) > 0 else []
        protocol = params.get("protocol", "")
        history = self._vars.get(inputs[2]) if len(inputs) > 2 else []

        executor = SessionExecutor(self.vm.asset_resolver, self.vm.config)
        outcome, updated_history = executor.execute(members, protocol, history)

        if len(out_names) >= 2:
            return outcome, updated_history
        return outcome

    def _execute_return(self, params, inputs, out_names):
        fields = params.get("fields", {})
        if fields:
            ret_type = params.get("type", "Result")
            resolved = {k: self._vars.get(v) for k, v in fields.items()}
            self._tracer.return_value(type_name=ret_type)
            return {"type": ret_type, "fields": resolved}
        elif inputs:
            value = self._vars.get(inputs[0])
            self._tracer.return_value(value=value)
            return value
        else:
            self._tracer.return_value()
            return None

    def _execute_construct(self, params, inputs, out_names):
        con_type = params.get("type")
        fields = params.get("fields", {})
        if con_type and fields:
            resolved = {k: self._vars.get(v) for k, v in fields.items()}
            return {"type": con_type, "fields": resolved}
        return [self._vars.get(i) for i in inputs]

    def _execute_tool(self, params, inputs, out_names):
        from runtime.tool_executor import ToolExecutor

        name = params["name"]
        input_vals = [self._vars.get(i) for i in inputs]

        executor = ToolExecutor(self.vm.asset_resolver, self.vm.config)
        return executor.execute(name, input_vals)

    def _execute_map(self, params, inputs, out_names):
        workflow = params.get("workflow", "Unknown")
        collection = self._vars.get(inputs[0]) if inputs else []
        concurrency = params.get("concurrency", 1)
        on_error = params.get("on_error", "halt")

        executor = MapExecutor(self.vm)
        return executor.execute(collection, workflow, concurrency, on_error)

    def _output_names(self, outputs):
        """Extract variable names from typed output list."""
        return [o["name"] if isinstance(o, dict) else o for o in outputs]
