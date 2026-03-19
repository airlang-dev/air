"""Tracer — records and prints execution traces for the AIR Agent VM."""

OP_DETAIL = {
    "llm": lambda p, i: f"prompt={p['prompt']}",
    "transform": lambda p, i: f"via={p.get('via', 'transform')}",
    "verify": lambda p, i: f"rule={p['rule']}",
    "aggregate": lambda p, i: f"strategy={p['strategy']}",
    "gate": lambda p, i: f"input={i[0]}",
    "decide": lambda p, i: f"provider={p['provider']}",
    "tool": lambda p, i: f"name={p['name']}",
    "map": lambda p, i: f"workflow={p.get('workflow', 'Unknown')}",
    "return": lambda p, i: f"return_type={p.get('type', 'Result')}",
    "construct": lambda p, i: f"construct_type={p.get('type', 'list')}",
}


class Tracer:
    """Records and prints execution traces for workflow runs."""

    def __init__(self):
        self.entries = []

    def workflow_start(self, workflow_name):
        print(f"[TRACE] workflow.start workflow={workflow_name}")

    def workflow_end(self):
        print(f"[TRACE] workflow.end ops={len(self.entries)}")

    def node_enter(self, node_id):
        print(f"[TRACE] node.enter node={node_id}")

    def route(self, route_var, matched, target):
        print(f"[TRACE] route variable={route_var} matched={matched} next={target}")

    def op_start(self, op_type, params, inputs):
        parts = [f"[TRACE] op.start type={op_type}"]
        detail_fn = OP_DETAIL.get(op_type)
        if detail_fn:
            parts.append(detail_fn(params, inputs))
        print(" ".join(parts))

    def op_end(self, out_names, value):
        out = out_names[0] if out_names else ""
        print(f'[TRACE] op.end output={out} value="{value}"')

    def return_value(self, *, type_name=None, value=None):
        if type_name:
            print(f"[TRACE] return type={type_name}")
        elif value is not None:
            print(f"[TRACE] return value={value}")
        else:
            print("[TRACE] return")

    def record(self, node_id, op_type, inputs, out_names, params):
        self.entries.append(
            {
                "node": node_id,
                "operation": op_type,
                "inputs": inputs,
                "outputs": out_names,
                "params": params,
            }
        )
