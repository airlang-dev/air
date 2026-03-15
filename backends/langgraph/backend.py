import json
import os

from backends.base_backend import Backend


class _CodeWriter:
    def __init__(self):
        self._lines = []
        self._indent = 0

    def line(self, text=""):
        if text:
            self._lines.append("    " * self._indent + text)
        else:
            self._lines.append("")
        return self

    def indent(self):
        self._indent += 1
        return self

    def dedent(self):
        self._indent -= 1
        return self

    def text(self):
        return "\n".join(self._lines) + "\n"


class LangGraphBackend(Backend):
    def generate(self, air_graph: dict) -> str:
        workflow = air_graph["workflow"]
        entry = air_graph["entry"]
        nodes = air_graph["nodes"]

        w = _CodeWriter()

        self._emit_imports(w, nodes)
        w.line()
        w.line()

        # Collect all variable names produced across the workflow
        all_vars = set()
        for node in nodes.values():
            for op in node.get("operations", []):
                for o in op.get("outputs", []):
                    all_vars.add(o["name"] if isinstance(o, dict) else o)

        w.line("operation_counter = 0")
        w.line()
        w.line()
        # Emit node functions
        for name, node in nodes.items():
            self._emit_node_function(w, name, node, all_vars)
            w.line()
            w.line()

        # Emit routing functions — nodes with edges need route functions
        # (even if also terminal, e.g. inline return in route)
        for name, node in nodes.items():
            if node.get("edges"):
                self._emit_route_function(w, name, node)
                w.line()
                w.line()

        # Build graph
        self._emit_graph(w, entry, nodes, workflow)

        return w.text()

    def compile(self, air_graph: dict, output_path: str = None) -> str:
        workflow = air_graph["workflow"]
        if output_path is None:
            output_path = f"build/{workflow}_langgraph.py"

        code = self.generate(air_graph)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            f.write(code)

        return code

    def _emit_imports(self, w: _CodeWriter, nodes: dict):
        w.line("from langgraph.graph import StateGraph, END")

        # Determine which adapters are needed
        adapters = set()
        for node in nodes.values():
            for op in node.get("operations", []):
                op_type = op["type"]
                if op_type == "llm":
                    adapters.add("llm_adapter")
                elif op_type == "transform":
                    adapters.add("transform_adapter")
                elif op_type == "verify":
                    adapters.add("verify_adapter")
                elif op_type == "aggregate":
                    adapters.add("aggregate_adapter")
                elif op_type == "gate":
                    adapters.add("gate_adapter")
                elif op_type == "decide":
                    adapters.add("decision_adapter")
                elif op_type == "session":
                    adapters.add("session_adapter")
                elif op_type == "tool":
                    adapters.add("tool_adapter")
                elif op_type == "map":
                    adapters.add("map_adapter")

        if adapters:
            adapter_list = ", ".join(sorted(adapters))
            w.line(f"from runtime.adapters import {adapter_list}")

    def _emit_node_function(self, w: _CodeWriter, name: str, node: dict, all_vars: set):
        w.line(f"def {name}(state):")
        w.indent()

        ops = node.get("operations", [])
        if not ops:
            w.line("pass")
            w.dedent()
            return

        w.line("global operation_counter")
        w.line(f'print("[TRACE] node.enter node={name}")')
        for op in ops:
            self._emit_operation(w, op, all_vars)
            w.line("operation_counter += 1")

        w.line("return state")
        w.dedent()

    def _resolve_fields(self, fields: dict, all_vars: set) -> str:
        parts = []
        for k, v in fields.items():
            if v in all_vars:
                parts.append(f'"{k}": state["{v}"]')
            else:
                parts.append(f'"{k}": "{v}"')
        return ", ".join(parts)

    def _resolve_input(self, inp: str, all_vars: set) -> str:
        """Resolve an input reference to a Python expression."""
        if "." in inp:
            # Dotted name: result.consensus -> state["result"]["consensus"]
            parts = inp.split(".", 1)
            return f'state["{parts[0]}"]["{parts[1]}"]'
        if inp in all_vars:
            return f'state["{inp}"]'
        return f'"{inp}"'

    def _emit_operation(self, w: _CodeWriter, op: dict, all_vars: set):
        op_type = op["type"]
        inputs = op.get("inputs", [])
        outputs = op.get("outputs", [])
        params = op.get("params", {})
        out_names = [o["name"] if isinstance(o, dict) else o for o in outputs]
        out = out_names[0] if out_names else None

        if op_type == "llm":
            prompt = params["prompt"]
            args_str = ", ".join(self._resolve_input(i, all_vars) for i in inputs)
            w.line(f'print("[TRACE] op.start type=llm prompt={prompt}")')
            if out:
                w.line(f'state["{out}"] = llm_adapter("{prompt}", {args_str})')
                w.line(
                    f'print(f\'[TRACE] op.end output={out} value="{{state["{out}"]}}"\')'
                )
            else:
                w.line(f'llm_adapter("{prompt}", {args_str})')

        elif op_type == "transform":
            inp = inputs[0]
            via = params.get("via", "transform")
            w.line(f'print("[TRACE] op.start type=transform via={via}")')
            if out:
                w.line(
                    f'state["{out}"] = transform_adapter({self._resolve_input(inp, all_vars)}, "{via}")'
                )
                w.line(
                    f'print(f\'[TRACE] op.end output={out} value="{{state["{out}"]}}"\')'
                )
            else:
                w.line(
                    f'transform_adapter({self._resolve_input(inp, all_vars)}, "{via}")'
                )

        elif op_type == "verify":
            inp = inputs[0]
            rule = params["rule"]
            w.line(f'print("[TRACE] op.start type=verify rule={rule}")')
            if out:
                w.line(
                    f'state["{out}"] = verify_adapter({self._resolve_input(inp, all_vars)}, "{rule}")'
                )
                w.line(
                    f'print(f\'[TRACE] op.end output={out} value="{{state["{out}"]}}"\')'
                )
            else:
                w.line(
                    f'verify_adapter({self._resolve_input(inp, all_vars)}, "{rule}")'
                )

        elif op_type == "aggregate":
            inputs_str = ", ".join(self._resolve_input(i, all_vars) for i in inputs)
            strategy = params["strategy"]
            w.line(f'print("[TRACE] op.start type=aggregate strategy={strategy}")')
            if out:
                w.line(
                    f'state["{out}"] = aggregate_adapter([{inputs_str}], "{strategy}")'
                )
                w.line(
                    f'print(f\'[TRACE] op.end output={out} value="{{state["{out}"]}}"\')'
                )
            else:
                w.line(f'aggregate_adapter([{inputs_str}], "{strategy}")')

        elif op_type == "gate":
            inp = inputs[0]
            w.line(f'print("[TRACE] op.start type=gate input={inp}")')
            if out:
                w.line(
                    f'state["{out}"] = gate_adapter({self._resolve_input(inp, all_vars)})'
                )
                w.line(
                    f'print(f\'[TRACE] op.end output={out} value="{{state["{out}"]}}"\')'
                )
            else:
                w.line(f"gate_adapter({self._resolve_input(inp, all_vars)})")

        elif op_type == "decide":
            inp = self._resolve_input(inputs[0], all_vars) if inputs else "None"
            provider = params["provider"]
            w.line(f'print("[TRACE] op.start type=decide provider={provider}")')
            if len(out_names) >= 2:
                w.line(
                    f'state["{out_names[0]}"], state["{out_names[1]}"] = '
                    f'decision_adapter("{provider}", {inp})'
                )
                w.line(
                    f'print(f\'[TRACE] op.end output={out_names[0]} value="{{state["{out_names[0]}"]}}"\')'
                )
                w.line(
                    f'print(f\'[TRACE] op.end output={out_names[1]} value="{{state["{out_names[1]}"]}}"\')'
                )
            elif out_names:
                w.line(f'_, state["{out}"] = decision_adapter("{provider}", {inp})')
                w.line(
                    f'print(f\'[TRACE] op.end output={out} value="{{state["{out}"]}}"\')'
                )
            else:
                w.line(f'decision_adapter("{provider}", {inp})')

        elif op_type == "session":
            args_str = ", ".join(self._resolve_input(i, all_vars) for i in inputs)
            w.line(f'print("[TRACE] op.start type=session")')
            if out:
                w.line(f'state["{out}"] = session_adapter({args_str})')
                w.line(
                    f'print(f\'[TRACE] op.end output={out} value="{{state["{out}"]}}"\')'
                )
            else:
                w.line(f"session_adapter({args_str})")

        elif op_type == "return":
            fields = params.get("fields", {})
            if fields:
                ret_type = params.get("type", "Result")
                fields_str = self._resolve_fields(fields, all_vars)
                w.line(f'print("[TRACE] op.start type=return return_type={ret_type}")')
                w.line(
                    f'state["__result__"] = {{"type": "{ret_type}", "fields": {{{fields_str}}}}}'
                )
            elif inputs:
                inp = inputs[0]
                w.line(f'print("[TRACE] op.start type=return input={inp}")')
                w.line(f'state["__result__"] = {self._resolve_input(inp, all_vars)}')
            else:
                w.line(f'print("[TRACE] op.start type=return")')
                w.line(f'state["__result__"] = None')
            w.line(f'print("[TRACE] return")')

        elif op_type == "tool":
            tool_name = params["name"]
            w.line(f'print("[TRACE] op.start type=tool name={tool_name}")')
            if out:
                w.line(f'state["{out}"] = "[TOOL:{tool_name}]"')
                w.line(
                    f'print(f\'[TRACE] op.end output={out} value="{{state["{out}"]}}"\')'
                )
            else:
                w.line(f'_ = "[TOOL:{tool_name}]"')

        elif op_type == "map":
            collection = inputs[0] if inputs else "[]"
            wf = params.get("workflow", "Unknown")
            concurrency = params.get("concurrency")
            on_error = params.get("on_error")
            mod_parts = []
            if concurrency:
                mod_parts.append(f"concurrency={concurrency}")
            if on_error:
                mod_parts.append(f'on_error="{on_error}"')
            mod_str = ", ".join(mod_parts)
            w.line(f'print("[TRACE] op.start type=map workflow={wf}")')
            call_args = f'{self._resolve_input(collection, all_vars)}, "{wf}"'
            if mod_str:
                call_args += f", {mod_str}"
            if out:
                w.line(f'state["{out}"] = map_adapter({call_args})')
                w.line(
                    f'print(f\'[TRACE] op.end output={out} value="{{state["{out}"]}}"\')'
                )
            else:
                w.line(f"map_adapter({call_args})")

        elif op_type == "construct":
            con_type = params.get("type")
            fields = params.get("fields", {})
            if con_type and fields:
                fields_str = self._resolve_fields(fields, all_vars)
                w.line(
                    f'print("[TRACE] op.start type=construct construct_type={con_type}")'
                )
                if out:
                    w.line(
                        f'state["{out}"] = {{"type": "{con_type}", "fields": {{{fields_str}}}}}'
                    )
                    w.line(
                        f'print(f\'[TRACE] op.end output={out} value="{{state["{out}"]}}"\')'
                    )
            else:
                # List construct — inputs are items
                inputs_str = ", ".join(self._resolve_input(i, all_vars) for i in inputs)
                w.line(f'print("[TRACE] op.start type=construct list")')
                if out:
                    w.line(f'state["{out}"] = [{inputs_str}]')
                    w.line(
                        f'print(f\'[TRACE] op.end output={out} value="{{state["{out}"]}}"\')'
                    )

    def _classify_edges(self, edges):
        """Classify edges and assign routing keys. Returns list of (key, edge) pairs."""
        result = []
        for edge in edges:
            cond = edge.get("condition", {})
            kind = cond.get("kind")
            if kind == "enum":
                result.append((cond.get("value", "default"), edge))
            elif kind == "type":
                key = "__is_list__" if cond.get("is_list", False) else "__not_list__"
                result.append((key, edge))
            elif kind == "bool":
                result.append((cond.get("value", "true"), edge))
            elif kind == "else":
                result.append(("__else__", edge))
            else:
                result.append(("__default__", edge))
        return result

    def _resolve_route_var(self, route_var: str) -> str:
        """Generate Python expression for reading a route variable from state."""
        if "." in route_var:
            parts = route_var.split(".", 1)
            return f'state["{parts[0]}"]["{parts[1]}"]'
        return f'state["{route_var}"]'

    def _emit_route_function(self, w: _CodeWriter, name: str, node: dict):
        route_var = node.get("route_variable")
        edges = node.get("edges", [])

        # Single unconditional edge — no route function needed
        if len(edges) == 1 and not edges[0].get("condition"):
            return

        classified = self._classify_edges(edges)

        has_type = any(k in ("__is_list__", "__not_list__") for k, _ in classified)
        has_else = any(k == "__else__" for k, _ in classified)

        w.line(f"def route_{name}(state):")
        w.indent()

        if route_var:
            w.line(f"val = {self._resolve_route_var(route_var)}")
        else:
            w.line("val = None")

        if has_type:
            for key, edge in classified:
                if key == "__is_list__":
                    w.line("if isinstance(val, list):")
                    w.indent()
                    w.line(
                        f"print(f'[TRACE] route variable={route_var} value={{val}} -> __is_list__')"
                    )
                    w.line('return "__is_list__"')
                    w.dedent()
                elif key == "__not_list__":
                    w.line("if not isinstance(val, list):")
                    w.indent()
                    w.line(
                        f"print(f'[TRACE] route variable={route_var} value={{val}} -> __not_list__')"
                    )
                    w.line('return "__not_list__"')
                    w.dedent()

        # Emit bool checks
        bool_edges = [(k, e) for k, e in classified if k in ("true", "false")]
        if bool_edges:
            for key, edge in bool_edges:
                if key == "true":
                    w.line("if val:")
                    w.indent()
                    w.line(
                        f"print(f'[TRACE] route variable={route_var} value={{val}} -> true')"
                    )
                    w.line('return "true"')
                    w.dedent()
                elif key == "false":
                    w.line("if not val:")
                    w.indent()
                    w.line(
                        f"print(f'[TRACE] route variable={route_var} value={{val}} -> false')"
                    )
                    w.line('return "false"')
                    w.dedent()

        # Enum edges: return the value directly
        enum_edges = [
            (k, e)
            for k, e in classified
            if k
            not in (
                "__is_list__",
                "__not_list__",
                "__else__",
                "__default__",
                "true",
                "false",
            )
        ]
        if enum_edges:
            w.line(
                f"print(f'[TRACE] route variable={route_var} value={{val}} -> {{val}}')"
            )
            w.line("return val")
        elif has_else:
            w.line(
                f"print(f'[TRACE] route variable={route_var} value={{val}} -> __else__')"
            )
            w.line('return "__else__"')

        w.dedent()

    def _emit_graph(self, w: _CodeWriter, entry: str, nodes: dict, workflow: str):
        w.line("builder = StateGraph(dict)")
        w.line()

        # Add nodes
        for name in nodes:
            w.line(f'builder.add_node("{name}", {name})')
        w.line()

        w.line(f'builder.set_entry_point("{entry}")')
        w.line()

        # Add edges
        for name, node in nodes.items():
            edges = node.get("edges", [])
            is_terminal = node.get("terminal", False)

            if is_terminal and not edges:
                # Pure terminal — goes to END
                w.line(f'builder.add_edge("{name}", END)')
                continue

            if not edges:
                continue

            # Single unconditional edge
            if len(edges) == 1 and not edges[0].get("condition"):
                target = edges[0]["target"]
                if is_terminal:
                    # Terminal with unconditional edge — edge to END
                    w.line(f'builder.add_edge("{name}", END)')
                else:
                    w.line(f'builder.add_edge("{name}", "{target}")')
                continue

            # Conditional edges
            classified = self._classify_edges(edges)
            edge_map = {}
            for key, edge in classified:
                edge_map[key] = edge["target"]

            # If terminal, add END as a possible destination
            if is_terminal:
                edge_map["__end__"] = "END"

            map_parts = []
            for k, v in edge_map.items():
                if v == "END":
                    map_parts.append(f'"{k}": END')
                else:
                    map_parts.append(f'"{k}": "{v}"')
            map_str = ", ".join(map_parts)

            w.line(f"builder.add_conditional_edges(")
            w.indent()
            w.line(f'"{name}",')
            w.line(f"route_{name},")
            w.line(f"{{{map_str}}},")
            w.dedent()
            w.line(")")
            w.line()

        w.line("graph = builder.compile()")
        w.line()
        w.line()
        w.line('if __name__ == "__main__":')
        w.indent()
        w.line(f'print("[TRACE] workflow.start workflow={workflow}")')
        w.line("state = graph.invoke({})")
        w.line('print(f"[TRACE] workflow.end ops={operation_counter}")')
        w.line('print("[LangGraph] result:", state.get("__result__"))')
        w.dedent()
