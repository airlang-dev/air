from runtime.adapters import (
    llm_adapter, transform_adapter, verify_adapter,
    decision_adapter, aggregate_adapter, gate_adapter,
    session_adapter,
)


def execute_workflow(data):
    nodes = data["nodes"]
    current = data["entry"]
    state = {"variables": {}, "trace": []}

    print(f'[TRACE] workflow.start workflow={data["workflow"]}')

    while True:
        node = nodes[current]
        print(f"[TRACE] node.enter node={current}")

        result = _execute_operations(node["operations"], state, current)
        if result is not None:
            print(f"[TRACE] workflow.end ops={len(state['trace'])}")
            return result

        if node.get("terminal") and not node.get("edges"):
            print(f"[TRACE] workflow.end ops={len(state['trace'])}")
            return None

        edges = node.get("edges", [])
        if not edges:
            print(f"[TRACE] workflow.end ops={len(state['trace'])}")
            return None

        route_var = node.get("route_variable")
        if route_var:
            value = _resolve_variable(state["variables"], route_var)
        else:
            value = None

        target, matched = _resolve_edge(value, edges, current, nodes)
        print(f"[TRACE] route variable={route_var} matched={matched} next={target}")
        current = target


def _resolve_variable(variables, name):
    """Resolve a variable name, supporting dotted notation."""
    if "." in name:
        parts = name.split(".", 1)
        obj = variables[parts[0]]
        if isinstance(obj, dict):
            return obj[parts[1]]
        return getattr(obj, parts[1])
    return variables[name]


def _output_names(outputs):
    """Extract variable names from typed output list."""
    return [o["name"] if isinstance(o, dict) else o for o in outputs]


def _execute_operations(operations, state, node_id):
    variables = state["variables"]
    for op in operations:
        op_type = op["type"]
        inputs = op["inputs"]
        outputs = op["outputs"]
        out_names = _output_names(outputs)
        params = op.get("params", {})

        _trace_op_start(op_type, params, inputs)

        if op_type == "llm":
            input_vals = [variables.get(i, i) for i in inputs]
            value = llm_adapter(params["prompt"], *input_vals)
            _store(variables, out_names, value)
            _trace_op_end(out_names, value)

        elif op_type == "transform":
            input_val = variables[inputs[0]]
            via = params.get("via", "transform")
            value = transform_adapter(input_val, via)
            _store(variables, out_names, value)
            _trace_op_end(out_names, value)

        elif op_type == "verify":
            input_val = variables[inputs[0]]
            rule = params["rule"]
            value = verify_adapter(input_val, rule)
            _store(variables, out_names, value)
            _trace_op_end(out_names, value)

        elif op_type == "aggregate":
            values = [variables[i] for i in inputs]
            strategy = params["strategy"]
            value = aggregate_adapter(values, strategy)
            _store(variables, out_names, value)
            _trace_op_end(out_names, value)

        elif op_type == "gate":
            input_val = variables[inputs[0]]
            value = gate_adapter(input_val)
            _store(variables, out_names, value)
            _trace_op_end(out_names, value)

        elif op_type == "decide":
            input_val = variables.get(inputs[0], inputs[0]) if inputs else None
            provider = params["provider"]
            msg, outcome = decision_adapter(provider, input_val)
            if len(out_names) >= 2:
                variables[out_names[0]] = msg
                variables[out_names[1]] = outcome
                _trace_op_end(out_names[:1], msg)
                _trace_op_end(out_names[1:], outcome)
            elif len(out_names) == 1:
                variables[out_names[0]] = outcome
                _trace_op_end(out_names, outcome)

        elif op_type == "session":
            input_vals = [variables.get(i, i) for i in inputs]
            value = session_adapter(*input_vals)
            _store(variables, out_names, value)
            _trace_op_end(out_names, value)

        elif op_type == "return":
            fields = params.get("fields", {})
            if fields:
                ret_type = params.get("type", "Result")
                resolved = {k: variables.get(v, v) for k, v in fields.items()}
                print(f"[TRACE] return type={ret_type}")
                state["trace"].append({
                    "node": node_id, "operation": op_type,
                    "inputs": inputs, "outputs": out_names, "params": params,
                })
                return {"type": ret_type, "fields": resolved}
            elif inputs:
                value = variables.get(inputs[0], inputs[0])
                print(f"[TRACE] return value={value}")
                state["trace"].append({
                    "node": node_id, "operation": op_type,
                    "inputs": inputs, "outputs": out_names, "params": params,
                })
                return value
            else:
                print("[TRACE] return")
                state["trace"].append({
                    "node": node_id, "operation": op_type,
                    "inputs": inputs, "outputs": out_names, "params": params,
                })
                return None

        elif op_type == "construct":
            con_type = params.get("type")
            fields = params.get("fields", {})
            if con_type and fields:
                resolved = {k: variables.get(v, v) for k, v in fields.items()}
                value = {"type": con_type, "fields": resolved}
            else:
                # List construct
                value = [variables.get(i, i) for i in inputs]
            _store(variables, out_names, value)
            _trace_op_end(out_names, value)

        elif op_type == "tool":
            name = params["name"]
            value = f"[TOOL:{name}]"
            _store(variables, out_names, value)
            if out_names:
                _trace_op_end(out_names, value)

        state["trace"].append({
            "node": node_id, "operation": op_type,
            "inputs": inputs, "outputs": out_names, "params": params,
        })

    return None


def _store(variables, out_names, value):
    if out_names:
        variables[out_names[0]] = value


def _trace_op_start(op_type, params, inputs):
    parts = [f"[TRACE] op.start type={op_type}"]
    if op_type == "llm":
        parts.append(f"prompt={params['prompt']}")
    elif op_type == "transform":
        parts.append(f"via={params.get('via', 'transform')}")
    elif op_type == "verify":
        parts.append(f"rule={params['rule']}")
    elif op_type == "aggregate":
        parts.append(f"strategy={params['strategy']}")
    elif op_type == "gate":
        parts.append(f"input={inputs[0]}")
    elif op_type == "decide":
        parts.append(f"provider={params['provider']}")
    elif op_type == "session":
        pass
    elif op_type == "tool":
        parts.append(f"name={params['name']}")
    elif op_type == "return":
        parts.append(f"return_type={params.get('type', 'Result')}")
    elif op_type == "construct":
        parts.append(f"construct_type={params.get('type', 'list')}")
    print(" ".join(parts))


def _trace_op_end(out_names, value):
    out = out_names[0] if out_names else ""
    print(f'[TRACE] op.end output={out} value="{value}"')


def _resolve_edge(value, edges, current_node, nodes):
    target = None
    matched = None

    for edge in edges:
        cond = edge.get("condition")
        if cond is None:
            target = edge["target"]
            matched = "unconditional"
            break

        kind = cond["kind"]

        if kind == "enum" and cond.get("value") == value:
            target = edge["target"]
            matched = cond["value"]
            break

        if kind == "bool":
            bool_val = bool(value) if cond["value"] == "true" else not bool(value)
            if bool_val:
                target = edge["target"]
                matched = cond["value"]
                break

        if kind == "type":
            is_list = cond.get("is_list", False)
            if is_list and isinstance(value, list):
                target = edge["target"]
                matched = f"{cond['name']}[]"
                break
            elif not is_list and not isinstance(value, list):
                target = edge["target"]
                matched = cond.get("name", "type")
                break

    # "else" fallback
    if target is None:
        for edge in edges:
            cond = edge.get("condition")
            if cond and cond["kind"] == "else":
                target = edge["target"]
                matched = "else"
                break

    if target is None:
        raise RuntimeError(
            f"no matching edge for value {value!r} in node '{current_node}'"
        )

    if target not in nodes:
        raise RuntimeError(
            f"VM error: invalid edge target '{target}' from node '{current_node}'"
        )

    return target, matched
