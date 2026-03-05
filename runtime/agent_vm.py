from runtime.adapters import llm_adapter, transform_adapter, verify_adapter, decision_adapter


def execute_workflow(data):
    nodes = data["nodes"]
    current = data["entry"]
    state = {"variables": {}, "trace": []}

    while True:
        node = nodes[current]
        print(f"\n[VM] node={current}")

        result = _execute_operations(node["operations"], state, current)
        if result is not None:
            _print_summary(state)
            return result

        if node.get("terminal"):
            _print_summary(state)
            return None

        route_var = node["route_variable"]
        if route_var not in state["variables"]:
            raise RuntimeError(
                f"VM error: route variable '{route_var}' not defined at node '{current}'"
            )
        value = state["variables"][route_var]
        current = _resolve_edge(value, node["edges"], current, nodes)


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

        if op_type == "llm":
            value = llm_adapter(params["prompt"])
            _trace("llm", params["prompt"], out_names)
            _store(variables, out_names, value)

        elif op_type == "transform":
            input_val = variables[inputs[0]]
            via = params.get("via", "transform")
            value = transform_adapter(input_val, via)
            _trace("transform", via, out_names)
            _store(variables, out_names, value)

        elif op_type == "verify":
            input_val = variables[inputs[0]]
            rule = params["rule"]
            value = verify_adapter(input_val, rule)
            _trace("verify", rule, out_names)
            _store(variables, out_names, value)

        elif op_type == "aggregate":
            values = [variables[i] for i in inputs]
            strategy = params["strategy"]
            if strategy == "majority":
                pass_count = sum(1 for v in values if v == "PASS")
                value = "PASS" if pass_count > len(values) / 2 else "FAIL"
            else:
                value = "PASS"
            _trace("aggregate", strategy, out_names)
            _store(variables, out_names, value)

        elif op_type == "gate":
            input_val = variables[inputs[0]]
            value = "PROCEED" if input_val == "PASS" else "ESCALATE"
            _trace("gate", input_val, out_names)
            _store(variables, out_names, value)

        elif op_type == "decide":
            input_val = variables[inputs[0]] if inputs else None
            provider = params["provider"]
            msg, outcome = decision_adapter(provider, input_val)
            _trace("decide", provider, out_names)
            if len(out_names) >= 2:
                variables[out_names[0]] = msg
                variables[out_names[1]] = outcome
            elif len(out_names) == 1:
                variables[out_names[0]] = outcome

        elif op_type == "return":
            ret_type = params.get("type", "Artifact")
            fields = params.get("fields", {})
            resolved = {k: variables.get(v, v) for k, v in fields.items()}
            print(f"[VM] return {ret_type}")
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

        elif op_type == "tool":
            name = params["name"]
            _trace("tool", name, out_names)
            _store(variables, out_names, f"[TOOL:{name}]")

        state["trace"].append({
            "node": node_id, "operation": op_type,
            "inputs": inputs, "outputs": out_names, "params": params,
        })

    return None


def _store(variables, out_names, value):
    if out_names:
        variables[out_names[0]] = value


def _trace(op_type, detail, out_names):
    out = out_names[0] if out_names else ""
    print(f"[VM] {op_type} {detail} -> {out}")


def _print_summary(state):
    count = len(state["trace"])
    print(f"\n[VM] execution complete")
    print(f"[VM] operations executed: {count}")


def _resolve_edge(value, edges, current_node, nodes):
    target = None

    for edge in edges:
        cond = edge.get("condition")
        if cond is None:
            target = edge["target"]
            break

        kind = cond["kind"]

        if kind == "enum" and cond.get("value") == value:
            target = edge["target"]
            break

        if kind == "type":
            is_list = cond.get("is_list", False)
            if is_list and isinstance(value, list):
                target = edge["target"]
                break
            elif not is_list and not isinstance(value, list):
                target = edge["target"]
                break

    # "continue" fallback
    if target is None:
        for edge in edges:
            cond = edge.get("condition")
            if cond and cond["kind"] == "continue":
                target = edge["target"]
                break

    if target is None:
        raise RuntimeError(
            f"no matching edge for value {value!r} in node '{current_node}'"
        )

    if target not in nodes:
        raise RuntimeError(
            f"VM error: invalid edge target '{target}' from node '{current_node}'"
        )

    return target
