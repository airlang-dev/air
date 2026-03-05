from runtime.adapters import llm_adapter, transform_adapter, verify_adapter, decision_adapter


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

        if node.get("terminal"):
            print(f"[TRACE] workflow.end ops={len(state['trace'])}")
            return None

        route_var = node["route_variable"]
        if route_var not in state["variables"]:
            raise RuntimeError(
                f"VM error: route variable '{route_var}' not defined at node '{current}'"
            )
        value = state["variables"][route_var]
        target, matched = _resolve_edge(value, node["edges"], current, nodes)
        print(f"[TRACE] route variable={route_var} matched={matched} next={target}")
        current = target


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
            value = llm_adapter(params["prompt"])
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
            if strategy == "majority":
                pass_count = sum(1 for v in values if v == "PASS")
                value = "PASS" if pass_count > len(values) / 2 else "FAIL"
            else:
                value = "PASS"
            _store(variables, out_names, value)
            _trace_op_end(out_names, value)

        elif op_type == "gate":
            input_val = variables[inputs[0]]
            value = "PROCEED" if input_val == "PASS" else "ESCALATE"
            _store(variables, out_names, value)
            _trace_op_end(out_names, value)

        elif op_type == "decide":
            input_val = variables[inputs[0]] if inputs else None
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

        elif op_type == "return":
            ret_type = params.get("type", "Artifact")
            fields = params.get("fields", {})
            resolved = {k: variables.get(v, v) for k, v in fields.items()}
            print(f"[TRACE] return type={ret_type}")
            state["trace"].append({
                "node": node_id, "operation": op_type,
                "inputs": inputs, "outputs": out_names, "params": params,
            })
            return {"type": ret_type, "fields": resolved}

        elif op_type == "construct":
            con_type = params.get("type", "Unknown")
            fields = params.get("fields", {})
            resolved = {k: variables.get(v, v) for k, v in fields.items()}
            value = {"type": con_type, "fields": resolved}
            _store(variables, out_names, value)
            _trace_op_end(out_names, value)

        elif op_type == "tool":
            name = params["name"]
            value = f"[TOOL:{name}]"
            _store(variables, out_names, value)
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
    elif op_type == "tool":
        parts.append(f"name={params['name']}")
    elif op_type == "return":
        parts.append(f"return_type={params.get('type', 'Artifact')}")
    elif op_type == "construct":
        parts.append(f"construct_type={params.get('type', 'Unknown')}")
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

        if kind == "type":
            is_list = cond.get("is_list", False)
            if is_list and isinstance(value, list):
                target = edge["target"]
                matched = f"{cond['name']}[]" if is_list else cond["name"]
                break
            elif not is_list and not isinstance(value, list):
                target = edge["target"]
                matched = cond["name"]
                break

    # "continue" fallback
    if target is None:
        for edge in edges:
            cond = edge.get("condition")
            if cond and cond["kind"] == "continue":
                target = edge["target"]
                matched = "continue"
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
