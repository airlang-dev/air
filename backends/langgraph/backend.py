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
    def compile(self, air_graph: dict, output_path: str = None) -> str:
        workflow = air_graph["workflow"]
        entry = air_graph["entry"]
        nodes = air_graph["nodes"]

        if output_path is None:
            output_path = f"build/{workflow}_langgraph.py"

        w = _CodeWriter()

        self._emit_imports(w)
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

        # Emit routing functions
        for name, node in nodes.items():
            if not node.get("terminal") and node.get("edges"):
                self._emit_route_function(w, name, node)
                w.line()
                w.line()

        # Build graph
        self._emit_graph(w, entry, nodes, workflow)

        code = w.text()

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            f.write(code)

        return code

    def _emit_imports(self, w: _CodeWriter):
        w.line("from langgraph.graph import StateGraph, END")
        w.line(
            "from runtime.adapters import ("
        )
        w.line(
            "    llm_adapter, transform_adapter, verify_adapter,"
        )
        w.line(
            "    decision_adapter, aggregate_adapter, gate_adapter"
        )
        w.line(
            ")"
        )

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

    def _emit_operation(self, w: _CodeWriter, op: dict, all_vars: set):
        op_type = op["type"]
        inputs = op.get("inputs", [])
        outputs = op.get("outputs", [])
        params = op.get("params", {})
        out_names = [o["name"] if isinstance(o, dict) else o for o in outputs]
        out = out_names[0] if out_names else None

        if op_type == "llm":
            prompt = params["prompt"]
            w.line(f'print("[TRACE] op.start type=llm prompt={prompt}")')
            w.line(f'state["{out}"] = llm_adapter("{prompt}")')
            w.line(f'print(f\'[TRACE] op.end output={out} value="{{state["{out}"]}}"\')')

        elif op_type == "transform":
            inp = inputs[0]
            via = params.get("via", "transform")
            w.line(f'print("[TRACE] op.start type=transform via={via}")')
            w.line(f'state["{out}"] = transform_adapter(state["{inp}"], "{via}")')
            w.line(f'print(f\'[TRACE] op.end output={out} value="{{state["{out}"]}}"\')')

        elif op_type == "verify":
            inp = inputs[0]
            rule = params["rule"]
            w.line(f'print("[TRACE] op.start type=verify rule={rule}")')
            w.line(f'state["{out}"] = verify_adapter(state["{inp}"], "{rule}")')
            w.line(f'print(f\'[TRACE] op.end output={out} value="{{state["{out}"]}}"\')')

        elif op_type == "aggregate":
            inputs_str = ", ".join(f'state["{i}"]' for i in inputs)
            strategy = params["strategy"]
            w.line(f'print("[TRACE] op.start type=aggregate strategy={strategy}")')
            w.line(f'state["{out}"] = aggregate_adapter([{inputs_str}], "{strategy}")')
            w.line(f'print(f\'[TRACE] op.end output={out} value="{{state["{out}"]}}"\')')

        elif op_type == "gate":
            inp = inputs[0]
            w.line(f'print("[TRACE] op.start type=gate input={inp}")')
            w.line(f'state["{out}"] = gate_adapter(state["{inp}"])')
            w.line(f'print(f\'[TRACE] op.end output={out} value="{{state["{out}"]}}"\')')

        elif op_type == "decide":
            inp = f'state["{inputs[0]}"]' if inputs else "None"
            provider = params["provider"]
            w.line(f'print("[TRACE] op.start type=decide provider={provider}")')
            if len(out_names) >= 2:
                w.line(
                    f'state["{out_names[0]}"], state["{out_names[1]}"] = '
                    f'decision_adapter("{provider}", {inp})'
                )
                w.line(f'print(f\'[TRACE] op.end output={out_names[0]} value="{{state["{out_names[0]}"]}}"\')')
                w.line(f'print(f\'[TRACE] op.end output={out_names[1]} value="{{state["{out_names[1]}"]}}"\')')
            elif out_names:
                w.line(
                    f'_, state["{out}"] = decision_adapter("{provider}", {inp})'
                )
                w.line(f'print(f\'[TRACE] op.end output={out} value="{{state["{out}"]}}"\')')

        elif op_type == "return":
            ret_type = params.get("type", "Artifact")
            fields = params.get("fields", {})
            fields_str = self._resolve_fields(fields, all_vars)
            w.line(f'print("[TRACE] op.start type=return return_type={ret_type}")')
            w.line(
                f'state["__result__"] = {{"type": "{ret_type}", "fields": {{{fields_str}}}}}'
            )
            w.line(f'print("[TRACE] return type={ret_type}")')

        elif op_type == "tool":
            tool_name = params["name"]
            w.line(f'print("[TRACE] op.start type=tool name={tool_name}")')
            w.line(f'state["{out}"] = "[TOOL:{tool_name}]"')
            w.line(f'print(f\'[TRACE] op.end output={out} value="{{state["{out}"]}}"\')')

        elif op_type == "construct":
            con_type = params.get("type", "Unknown")
            fields = params.get("fields", {})
            fields_str = self._resolve_fields(fields, all_vars)
            w.line(f'print("[TRACE] op.start type=construct construct_type={con_type}")')
            w.line(
                f'state["{out}"] = {{"type": "{con_type}", "fields": {{{fields_str}}}}}'
            )
            w.line(f'print(f\'[TRACE] op.end output={out} value="{{state["{out}"]}}"\')')

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
            elif kind == "continue":
                result.append(("__continue__", edge))
            else:
                result.append(("__default__", edge))
        return result

    def _emit_route_function(self, w: _CodeWriter, name: str, node: dict):
        route_var = node["route_variable"]
        edges = node["edges"]
        classified = self._classify_edges(edges)

        has_type = any(k.startswith("__") and k != "__continue__" and k != "__default__" for k, _ in classified)
        has_enum = any(not k.startswith("__") for k, _ in classified)
        has_continue = any(k == "__continue__" for k, _ in classified)

        w.line(f"def route_{name}(state):")
        w.indent()
        w.line(f'val = state["{route_var}"]')

        if has_type:
            for key, edge in classified:
                if key == "__is_list__":
                    w.line("if isinstance(val, list):")
                    w.indent()
                    w.line(f'print(f\'[TRACE] route variable={route_var} value={{val}} -> __is_list__\')')
                    w.line('return "__is_list__"')
                    w.dedent()
                elif key == "__not_list__":
                    w.line("if not isinstance(val, list):")
                    w.indent()
                    w.line(f'print(f\'[TRACE] route variable={route_var} value={{val}} -> __not_list__\')')
                    w.line('return "__not_list__"')
                    w.dedent()
            if has_enum:
                w.line(f'print(f\'[TRACE] route variable={route_var} value={{val}} -> {{val}}\')')
                w.line("return val")
            elif has_continue:
                w.line(f'print(f\'[TRACE] route variable={route_var} value={{val}} -> __continue__\')')
                w.line('return "__continue__"')
            else:
                w.line(f'print(f\'[TRACE] route variable={route_var} value={{val}} -> __not_list__\')')
                w.line('return "__not_list__"')
        else:
            if has_enum:
                w.line(f'print(f\'[TRACE] route variable={route_var} value={{val}} -> {{val}}\')')
                w.line("return val")
            elif has_continue:
                w.line(f'print(f\'[TRACE] route variable={route_var} value={{val}} -> __continue__\')')
                w.line('return "__continue__"')

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
            if node.get("terminal"):
                w.line(f'builder.add_edge("{name}", END)')
                continue

            edges = node.get("edges", [])
            if not edges:
                continue

            # Single unconditional edge
            if len(edges) == 1 and not edges[0].get("condition"):
                w.line(f'builder.add_edge("{name}", "{edges[0]["target"]}")')
                continue

            # Conditional edges
            classified = self._classify_edges(edges)
            edge_map = {}
            for key, edge in classified:
                edge_map[key] = edge["target"]

            map_str = ", ".join(f'"{k}": "{v}"' for k, v in edge_map.items())
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
        w.line('state = graph.invoke({})')
        w.line('print(f"[TRACE] workflow.end ops={operation_counter}")')
        w.line('print("[LangGraph] result:", state["__result__"])')
        w.dedent()
