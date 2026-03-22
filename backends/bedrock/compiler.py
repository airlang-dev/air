"""Bedrock Flow Backend compiler components."""

from dataclasses import dataclass, field


@dataclass
class CompilerConfig:
    default_model_id: str = "amazon.nova-lite-v1:0"
    region: str = "us-east-1"
    account_id: str = "123456789012"
    assets_dir: str | None = None

    def sdk_arn(self, instruction: str) -> str:
        """Return the ARN for an AIR SDK Lambda function."""
        return f"arn:aws:lambda:{self.region}:{self.account_id}:function:air-sdk-{instruction}"

    def tool_arn(self, tool_name: str) -> str:
        """Return a placeholder ARN for a user-supplied tool Lambda."""
        return f"arn:aws:lambda:{self.region}:{self.account_id}:function:{tool_name}"


class WarningCollector:
    def __init__(self):
        self._warnings: list[str] = []

    def warn(self, message: str) -> None:
        self._warnings.append(message)

    def warnings(self) -> list[str]:
        return list(self._warnings)

    def has_warnings(self) -> bool:
        return bool(self._warnings)


class CompilationError(Exception):
    pass


import json as _json
import re as _re

from backends.bedrock.naming import NodeNamer
from backends.bedrock.type_map import air_type_to_bedrock


def _make_params_inject_node(node_name: str, params: dict, input_var: str) -> dict:
    """Create an InlineCode node that injects params into the data payload."""
    params_json = _json.dumps(params).replace("'", "\\'")
    code = (
        f"import json\n"
        f"params = json.loads('{params_json}')\n"
        f"output = {{**locals(), '__params__': params}}\n"
        f"del output['json']\n"
        f"output"
    )
    return {
        "name": node_name,
        "type": "InlineCode",
        "inputs": [{"name": input_var, "type": "Object", "expression": f"$.data.{input_var}"}],
        "outputs": [{"name": "output", "type": "Object"}],
        "configuration": {
            "inlineCode": {
                "code": code,
                "language": "Python_3_12"
            }
        }
    }


class OperationCompiler:
    def __init__(self, config: CompilerConfig, warnings: WarningCollector, asset_resolver=None):
        self.config = config
        self.warnings = warnings
        self.asset_resolver = asset_resolver

    def compile_op(self, op: dict, air_node_name: str, op_index: int, namer: NodeNamer) -> list[dict]:
        op_type = op.get("type", "")
        dispatch = {
            "llm": self._compile_llm,
            "verify": self._compile_verify,
            "aggregate": self._compile_aggregate,
            "gate": self._compile_gate,
            "decide": self._compile_decide,
            "session": self._compile_session,
            "tool": self._compile_tool,
            "transform": self._compile_transform,
            "return": self._compile_return,
            "construct": self._compile_construct,
            "parallel": self._compile_parallel,
            "map": self._compile_map,
        }
        handler = dispatch.get(op_type)
        if handler:
            return handler(op, air_node_name, op_index, namer)
        self.warnings.warn(f"Unknown operation '{op_type}' in node '{air_node_name}'; skipping.")
        return []

    def _compile_llm(self, op, air_node_name, op_index, namer):
        params = op.get("params", {})
        prompt_name = params.get("prompt", "")
        inputs = op.get("inputs", [])

        model_id = self.config.default_model_id
        template = "{{input}}"

        if self.asset_resolver and prompt_name:
            asset = self.asset_resolver.resolve_prompt(prompt_name)
            if asset:
                template = asset.template
                if asset.model:
                    model_id = asset.model
            else:
                self.warnings.warn(
                    f"llm op in '{air_node_name}': prompt asset '{prompt_name}' not found; "
                    f"using placeholder template. Supply --assets to resolve."
                )
        elif prompt_name:
            self.warnings.warn(
                f"llm op in '{air_node_name}': no --assets provided; "
                f"using placeholder template '{{{{input}}}}'."
            )

        placeholders = list(dict.fromkeys(_re.findall(r'\{\{(\w+)\}\}', template)))
        input_variables = [{"name": p} for p in placeholders]

        node_inputs = []
        for inp in inputs:
            node_inputs.append({
                "name": inp,
                "type": "String",
                "expression": f"$.data.{inp}"
            })

        node_name = namer.node_name(air_node_name, "llm")

        node = {
            "name": node_name,
            "type": "Prompt",
            "inputs": node_inputs,
            "outputs": [{"name": "modelCompletion", "type": "String"}],
            "configuration": {
                "prompt": {
                    "sourceConfiguration": {
                        "inline": {
                            "modelId": model_id,
                            "templateType": "TEXT",
                            "templateConfiguration": {
                                "text": {
                                    "text": template,
                                    "inputVariables": input_variables
                                }
                            }
                        }
                    }
                }
            }
        }
        return [node]

    def _compile_verify(self, op, air_node_name, op_index, namer):
        params = op.get("params", {})
        rule = params.get("rule", "rule")
        inputs = op.get("inputs", [])
        outputs = op.get("outputs", [])

        node_outputs = [{"name": "verdict", "type": "String"}]
        second_output_name = (outputs[1]["name"] if isinstance(outputs[1], dict) else outputs[1]) if len(outputs) > 1 else "_"
        if len(outputs) > 1 and second_output_name != "_":
            node_outputs.append({"name": "evidence", "type": "Object"})

        node_name = namer.node_name(air_node_name, f"verify_{rule}")

        inject_name = namer.node_name(air_node_name, f"verify_{rule}_params")
        inject_node = _make_params_inject_node(inject_name, params, inputs[0] if inputs else "input")

        node = {
            "name": node_name,
            "type": "LambdaFunction",
            "inputs": [
                {"name": "input", "type": "Object", "expression": f"$.data.{inputs[0]}" if inputs else "$.data"},
                {"name": "params", "type": "Object", "expression": "$.data.__params__"}
            ],
            "outputs": node_outputs,
            "configuration": {
                "lambdaFunction": {
                    "lambdaArn": self.config.sdk_arn("verify")
                }
            }
        }
        return [inject_node, node]

    def _compile_aggregate(self, op, air_node_name, op_index, namer):
        params = op.get("params", {})
        inputs = op.get("inputs", [])

        assemble_name = namer.node_name(air_node_name, "aggregate_prep")
        verdicts_code = "import json\n"
        verdicts_code += f"verdicts = [{', '.join(inputs)}]\n"
        verdicts_code += f"params = json.loads('{_json.dumps(params)}')\n"
        verdicts_code += "output = {**{k: v for k, v in locals().items() if k not in ('json', 'output')}, '__params__': params, '__verdicts__': verdicts}\n"
        verdicts_code += "output"

        assemble_inputs = [{"name": inp, "type": "String", "expression": f"$.data.{inp}"} for inp in inputs]
        assemble_node = {
            "name": assemble_name,
            "type": "InlineCode",
            "inputs": assemble_inputs,
            "outputs": [{"name": "output", "type": "Object"}],
            "configuration": {
                "inlineCode": {
                    "code": verdicts_code,
                    "language": "Python_3_12"
                }
            }
        }

        node_name = namer.node_name(air_node_name, "aggregate")
        node = {
            "name": node_name,
            "type": "LambdaFunction",
            "inputs": [
                {"name": "verdicts", "type": "Array", "expression": "$.data.__verdicts__"},
                {"name": "params", "type": "Object", "expression": "$.data.__params__"}
            ],
            "outputs": [{"name": "consensus", "type": "Object"}],
            "configuration": {
                "lambdaFunction": {
                    "lambdaArn": self.config.sdk_arn("aggregate")
                }
            }
        }
        return [assemble_node, node]

    def _compile_gate(self, op, air_node_name, op_index, namer):
        inputs = op.get("inputs", [])
        input_expr = f"$.data.{inputs[0]}" if inputs else "$.data"
        node_name = namer.node_name(air_node_name, "gate")
        node = {
            "name": node_name,
            "type": "LambdaFunction",
            "inputs": [{"name": "input", "type": "Object", "expression": input_expr}],
            "outputs": [{"name": "outcome", "type": "String"}],
            "configuration": {
                "lambdaFunction": {"lambdaArn": self.config.sdk_arn("gate")}
            }
        }
        return [node]

    def _compile_decide(self, op, air_node_name, op_index, namer):
        params = op.get("params", {})
        inputs = op.get("inputs", [])
        input_expr = f"$.data.{inputs[0]}" if inputs else "$.data"

        inject_name = namer.node_name(air_node_name, "decide_params")
        inject_node = _make_params_inject_node(inject_name, params, inputs[0] if inputs else "input")

        node_name = namer.node_name(air_node_name, "decide")
        node = {
            "name": node_name,
            "type": "LambdaFunction",
            "inputs": [
                {"name": "input", "type": "String", "expression": input_expr},
                {"name": "params", "type": "Object", "expression": "$.data.__params__"}
            ],
            "outputs": [
                {"name": "message", "type": "String"},
                {"name": "outcome", "type": "String"}
            ],
            "configuration": {
                "lambdaFunction": {"lambdaArn": self.config.sdk_arn("decide")}
            }
        }
        return [inject_node, node]

    def _compile_session(self, op, air_node_name, op_index, namer):
        params = op.get("params", {})
        inputs = op.get("inputs", [])

        inject_name = namer.node_name(air_node_name, "session_params")
        inject_node = _make_params_inject_node(inject_name, params, inputs[0] if inputs else "members")

        node_name = namer.node_name(air_node_name, "session")
        node = {
            "name": node_name,
            "type": "LambdaFunction",
            "inputs": [
                {"name": "members", "type": "Array", "expression": f"$.data.{inputs[0]}" if len(inputs) > 0 else "$.data.members"},
                {"name": "protocol", "type": "String", "expression": f"$.data.{inputs[1]}" if len(inputs) > 1 else "$.data.protocol"},
                {"name": "history", "type": "Array", "expression": f"$.data.{inputs[2]}" if len(inputs) > 2 else "$.data.history"},
                {"name": "params", "type": "Object", "expression": "$.data.__params__"}
            ],
            "outputs": [{"name": "result", "type": "Object"}],
            "configuration": {
                "lambdaFunction": {"lambdaArn": self.config.sdk_arn("session")}
            }
        }
        return [inject_node, node]

    def _compile_tool(self, op, air_node_name, op_index, namer):
        params = op.get("params", {})
        tool_name = params.get("name", "unknown_tool")
        inputs = op.get("inputs", [])

        self.warnings.warn(
            f"tool '{tool_name}' in '{air_node_name}': replace placeholder ARN "
            f"'{self.config.tool_arn(tool_name)}' with your deployed Lambda ARN before deploying."
        )

        node_name = namer.node_name(air_node_name, f"tool_{tool_name}")
        node = {
            "name": node_name,
            "type": "LambdaFunction",
            "inputs": [{"name": "input", "type": "Object", "expression": "$.data"}],
            "outputs": [{"name": "result", "type": "Object"}],
            "configuration": {
                "lambdaFunction": {"lambdaArn": self.config.tool_arn(tool_name)}
            }
        }
        return [node]

    def _compile_transform(self, op, air_node_name, op_index, namer):
        params = op.get("params", {})
        inputs = op.get("inputs", [])
        via = params.get("via")
        via_func = params.get("via_func")
        target_type = params.get("target_type", "String")

        if via:
            llm_op = {"op": "llm", "inputs": inputs, "outputs": op.get("outputs", []),
                      "output_types": op.get("output_types", []), "params": {"prompt": via}}
            prompt_nodes = self._compile_llm(llm_op, air_node_name, op_index, namer)
            validate_name = namer.node_name(air_node_name, "transform_validate")
            validate_node = {
                "name": validate_name,
                "type": "InlineCode",
                "inputs": [{"name": "modelCompletion", "type": "String", "expression": "$.data.modelCompletion"}],
                "outputs": [{"name": "result", "type": air_type_to_bedrock(target_type)}],
                "configuration": {
                    "inlineCode": {
                        "code": f"# Schema validation/coercion to {target_type}\nresult = modelCompletion\nresult",
                        "language": "Python_3_12"
                    }
                }
            }
            return prompt_nodes + [validate_node]
        elif via_func:
            self.warnings.warn(
                f"transform via_func '{via_func}' in '{air_node_name}': replace placeholder ARN "
                f"'{self.config.tool_arn(via_func)}' with your deployed Lambda ARN before deploying."
            )
            node_name = namer.node_name(air_node_name, "transform_func")
            input_expr = f"$.data.{inputs[0]}" if inputs else "$.data"
            node = {
                "name": node_name,
                "type": "LambdaFunction",
                "inputs": [{"name": "input", "type": "Object", "expression": input_expr}],
                "outputs": [{"name": "result", "type": air_type_to_bedrock(target_type)}],
                "configuration": {
                    "lambdaFunction": {"lambdaArn": self.config.tool_arn(via_func)}
                }
            }
            return [node]
        else:
            node_name = namer.node_name(air_node_name, "transform")
            input_expr = f"$.data.{inputs[0]}" if inputs else "$.data"
            node = {
                "name": node_name,
                "type": "InlineCode",
                "inputs": [{"name": inputs[0] if inputs else "input", "type": "String", "expression": input_expr}],
                "outputs": [{"name": "result", "type": air_type_to_bedrock(target_type)}],
                "configuration": {
                    "inlineCode": {
                        "code": f"# Coerce to {target_type}\nresult = {inputs[0] if inputs else 'input'}\nresult",
                        "language": "Python_3_12"
                    }
                }
            }
            return [node]

    def _compile_return(self, op, air_node_name, op_index, namer):
        params = op.get("params", {})
        inputs = op.get("inputs", [])
        fields = params.get("fields", {})
        ret_type = params.get("type")

        node_name = namer.node_name(air_node_name, "return")

        if ret_type and fields:
            code = f"import json\nresult = {{'type': '{ret_type}', 'fields': {{{', '.join(f'\"{k}\": {v}' for k, v in fields.items())}}}}} \nresult"
        elif inputs:
            code = f"result = {inputs[0]}\nresult"
        else:
            code = "result = {}\nresult"

        node_inputs = [{"name": inp, "type": "String", "expression": f"$.data.{inp}"} for inp in inputs]

        node = {
            "name": node_name,
            "type": "InlineCode",
            "inputs": node_inputs,
            "outputs": [{"name": "result", "type": "Object"}],
            "configuration": {
                "inlineCode": {
                    "code": code,
                    "language": "Python_3_12"
                }
            }
        }
        return [node]

    def _compile_construct(self, op, air_node_name, op_index, namer):
        params = op.get("params", {})
        inputs = op.get("inputs", [])
        construct_type = params.get("type")
        fields = params.get("fields", {})

        node_name = namer.node_name(air_node_name, "construct")
        node_inputs = [{"name": inp, "type": "Object", "expression": f"$.data.{inp}"} for inp in inputs]

        if construct_type and fields:
            field_assignments = ", ".join(f'"{k}": {v}' for k, v in fields.items())
            code = f"result = {{'type': '{construct_type}', 'fields': {{{field_assignments}}}}}\nresult"
        else:
            items = ", ".join(inputs)
            code = f"result = [{items}]\nresult"

        node = {
            "name": node_name,
            "type": "InlineCode",
            "inputs": node_inputs,
            "outputs": [{"name": "result", "type": "Object"}],
            "configuration": {
                "inlineCode": {
                    "code": code,
                    "language": "Python_3_12"
                }
            }
        }
        return [node]

    def _compile_map(self, op, air_node_name, op_index, namer):
        params = op.get("params", {})
        inputs = op.get("inputs", [])
        sub_workflow = params.get("workflow", "SubWorkflow")

        iter_name = namer.node_name(air_node_name, "iter")
        collect_name = namer.node_name(air_node_name, "collect")

        input_expr = f"$.data.{inputs[0]}" if inputs else "$.data"

        iter_node = {
            "name": iter_name,
            "type": "Iterator",
            "inputs": [{"name": "array", "type": "Array", "expression": input_expr}],
            "outputs": [{"name": "arrayItem", "type": "Object"}, {"name": "arraySize", "type": "Number"}],
            "configuration": {}
        }
        collect_node = {
            "name": collect_name,
            "type": "Collector",
            "inputs": [{"name": "arrayItem", "type": "Object", "expression": "$.data.arrayItem"}],
            "outputs": [{"name": "collectedArray", "type": "Array"}],
            "configuration": {}
        }
        return [iter_node, collect_node]

    def _compile_parallel(self, op, air_node_name, op_index, namer):
        self.warnings.warn(
            f"parallel block in node '{air_node_name}': Bedrock Flows do not support true parallelism; "
            f"branches will execute sequentially in declaration order."
        )
        branches = op.get("branches", [])
        nodes = []
        for i, branch in enumerate(branches):
            for branch_op in branch.get("operations", []):
                nodes.extend(self.compile_op(branch_op, air_node_name, op_index + i, namer))
        return nodes


class NodeCompiler:
    def __init__(self, config: CompilerConfig, warnings: WarningCollector, asset_resolver=None):
        self.config = config
        self.warnings = warnings
        self.op_compiler = OperationCompiler(config, warnings, asset_resolver)

    def compile_node(
        self,
        air_node_name: str,
        air_node: dict,
        namer: NodeNamer,
    ) -> tuple[list[dict], list[dict]]:
        """Returns (nodes, connections) for one AIR node.

        Multiple operations → multiple chained Bedrock nodes.
        Terminal node → appends an Output node at the end.
        """
        operations = air_node.get("operations", [])
        terminal = air_node.get("terminal", False)

        all_nodes = []
        connections = []

        for i, op in enumerate(operations):
            op_nodes = self.op_compiler.compile_op(op, air_node_name, i, namer)

            # Chain: connect previous last node to this first node
            if all_nodes and op_nodes:
                prev_last = all_nodes[-1]["name"]
                curr_first = op_nodes[0]["name"]
                conn_name = namer.connection_name(prev_last, curr_first)
                connections.append({
                    "name": conn_name,
                    "type": "Data",
                    "source": prev_last,
                    "target": curr_first,
                    "configuration": {
                        "data": {
                            "sourceOutput": "document",
                            "targetInput": "document"
                        }
                    }
                })

            all_nodes.extend(op_nodes)

        # Append Output node for terminal AIR nodes
        if terminal and all_nodes:
            out_name = namer.node_name(air_node_name, "out")
            out_node = {
                "name": out_name,
                "type": "Output",
                "inputs": [{"name": "document", "type": "Object", "expression": "$.data"}],
                "outputs": [],
                "configuration": {}
            }
            # Connect last op node to Output
            last_op_node = all_nodes[-1]["name"]
            conn_name = namer.connection_name(last_op_node, out_name)
            connections.append({
                "name": conn_name,
                "type": "Data",
                "source": last_op_node,
                "target": out_name,
                "configuration": {
                    "data": {
                        "sourceOutput": "document",
                        "targetInput": "document"
                    }
                }
            })
            all_nodes.append(out_node)

        return all_nodes, connections


class EdgeCompiler:
    def __init__(self, config: CompilerConfig, warnings: WarningCollector):
        self.config = config
        self.warnings = warnings

    def compile_edges(
        self,
        air_node: dict,
        last_bedrock_node_name: str,
        air_node_to_first_bedrock: dict,
        namer: NodeNamer,
        air_node_name: str = "",
    ) -> tuple[list[dict], list[dict]]:
        """Returns (extra_nodes, connections).

        extra_nodes: Condition nodes inserted for conditional routing.
        connections: Bedrock connection dicts.
        """
        edges = air_node.get("edges", [])
        if not edges:
            return [], []

        # Check if any edge has a condition
        has_conditions = any(e.get("condition") is not None for e in edges)

        if not has_conditions:
            # Single unconditional edge (task 5.1)
            edge = edges[0]
            target_node_name = edge["target"]
            target_first = air_node_to_first_bedrock.get(target_node_name)
            if not target_first:
                return [], []
            conn_name = namer.connection_name(last_bedrock_node_name, target_first)
            conn = {
                "name": conn_name,
                "type": "Data",
                "source": last_bedrock_node_name,
                "target": target_first,
                "configuration": {
                    "data": {
                        "sourceOutput": "document",
                        "targetInput": "document"
                    }
                }
            }
            return [], [conn]

        # Conditional edges (task 5.2)
        route_var = air_node.get("route_variable", "outcome")
        cond_node_name = namer.node_name(air_node_name, "route")

        conditions = []
        cond_outputs = []
        connections = []

        for edge in edges:
            condition = edge.get("condition", {})
            target = edge["target"]
            target_first = air_node_to_first_bedrock.get(target)
            if not target_first:
                continue

            kind = condition.get("kind", "else") if condition else "else"
            value = condition.get("value", "") if condition else ""
            name_val = condition.get("name", "") if condition else ""

            # Generate condition name (output branch name)
            if kind == "enum":
                branch_name = str(value)
                expr = f'$.data.{route_var} == "{value}"'
            elif kind == "type" and name_val == "Fault":
                branch_name = "Fault"
                expr = "$.data.__fault__ != null"
            elif kind == "bool" and str(value).lower() == "true":
                branch_name = "true"
                expr = f"$.data.{route_var} == true"
            elif kind == "bool" and str(value).lower() == "false":
                branch_name = "false"
                expr = f"$.data.{route_var} == false"
            else:
                # else / catch-all — must be last
                branch_name = "else"
                expr = "true"

            conditions.append({"name": branch_name, "expression": expr})
            cond_outputs.append({"name": branch_name})

            # Conditional connection from Condition node to target
            conn_name = namer.connection_name(cond_node_name, target_first)
            connections.append({
                "name": conn_name,
                "type": "Conditional",
                "source": cond_node_name,
                "target": target_first,
                "configuration": {
                    "conditional": {
                        "condition": branch_name
                    }
                }
            })

        # Sort: put "else" last
        conditions = [c for c in conditions if c["name"] != "else"] + \
                     [c for c in conditions if c["name"] == "else"]
        cond_outputs = [o for o in cond_outputs if o["name"] != "else"] + \
                       [o for o in cond_outputs if o["name"] == "else"]

        cond_node = {
            "name": cond_node_name,
            "type": "Condition",
            "inputs": [{"name": route_var, "type": "String", "expression": f"$.data.{route_var}"}],
            "outputs": cond_outputs,
            "configuration": {
                "condition": {
                    "conditions": conditions
                }
            }
        }

        # Data connection from last op node to Condition node
        data_conn_name = namer.connection_name(last_bedrock_node_name, cond_node_name)
        data_conn = {
            "name": data_conn_name,
            "type": "Data",
            "source": last_bedrock_node_name,
            "target": cond_node_name,
            "configuration": {
                "data": {
                    "sourceOutput": "document",
                    "targetInput": "document"
                }
            }
        }

        return [cond_node], [data_conn] + connections


class LoopCompiler:
    def __init__(self, config: CompilerConfig, warnings: WarningCollector):
        self.config = config
        self.warnings = warnings

    def compile_loop(
        self,
        loop_entry_air_node: str,
        max_visits: int,
        inner_nodes: list[dict],
        inner_connections: list[dict],
        namer: NodeNamer,
    ) -> tuple[list[dict], list[dict]]:
        """Wraps inner_nodes/connections in Loop/LoopInput/LoopController structure.

        Returns (loop_nodes, loop_connections).
        """
        loop_name = namer.node_name(loop_entry_air_node, "loop")
        loop_in_name = namer.node_name(loop_entry_air_node, "loop_in")
        loop_ctrl_name = namer.node_name(loop_entry_air_node, "loop_ctrl")

        loop_node = {
            "name": loop_name,
            "type": "Loop",
            "inputs": [{"name": "loopInput", "type": "Object", "expression": "$.data"}],
            "outputs": [{"name": "loopOutput", "type": "Object"}],
            "configuration": {}
        }

        loop_in_node = {
            "name": loop_in_name,
            "type": "LoopInput",
            "inputs": [{"name": "loopInput", "type": "Object", "expression": "$.data.loopInput"}],
            "outputs": [{"name": "loopInput", "type": "Object"}],
            "configuration": {}
        }

        loop_ctrl_node = {
            "name": loop_ctrl_name,
            "type": "LoopController",
            "inputs": [{"name": "loopInput", "type": "Object", "expression": "$.data"}],
            "outputs": [
                {"name": "continueLoop"},
                {"name": "exitLoop"}
            ],
            "configuration": {
                "loopController": {
                    "maxIterations": max_visits,
                    "continueCondition": "$.data.__fault__ != null",
                    "overflowFault": {"reason": "max visits exceeded"}
                }
            }
        }

        loop_nodes = [loop_node, loop_in_node] + inner_nodes + [loop_ctrl_node]

        loop_conns = []

        # loop → loop_in
        loop_conns.append({
            "name": namer.connection_name(loop_name, loop_in_name),
            "type": "Data",
            "source": loop_name,
            "target": loop_in_name,
            "configuration": {"data": {"sourceOutput": "loopInput", "targetInput": "loopInput"}}
        })

        # loop_in → first inner node
        if inner_nodes:
            first_inner = inner_nodes[0]["name"]
            loop_conns.append({
                "name": namer.connection_name(loop_in_name, first_inner),
                "type": "Data",
                "source": loop_in_name,
                "target": first_inner,
                "configuration": {"data": {"sourceOutput": "loopInput", "targetInput": "document"}}
            })

        # last inner node → loop_ctrl
        if inner_nodes:
            last_inner = inner_nodes[-1]["name"]
            loop_conns.append({
                "name": namer.connection_name(last_inner, loop_ctrl_name),
                "type": "Data",
                "source": last_inner,
                "target": loop_ctrl_name,
                "configuration": {"data": {"sourceOutput": "document", "targetInput": "loopInput"}}
            })

        # loop_ctrl → loop (continue)
        loop_conns.append({
            "name": namer.connection_name(loop_ctrl_name, loop_name),
            "type": "Conditional",
            "source": loop_ctrl_name,
            "target": loop_name,
            "configuration": {"conditional": {"condition": "continueLoop"}}
        })

        loop_conns.extend(inner_connections)

        return loop_nodes, loop_conns
