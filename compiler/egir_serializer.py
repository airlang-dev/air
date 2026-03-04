import json
import os

import jsonschema

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "spec", "egir.schema.json")


def serialize_operation(op):
    return {
        "type": op.type,
        "inputs": op.inputs,
        "outputs": op.outputs,
        "params": op.params if op.params else {},
    }


def serialize_edge(edge):
    return {"condition": edge.condition, "target": edge.target}


def serialize_node(node):
    result = {
        "operations": [serialize_operation(op) for op in node.operations],
    }
    if not node.terminal:
        result["route_variable"] = node.route_variable
        result["edges"] = [serialize_edge(e) for e in node.edges]
    result["terminal"] = node.terminal
    return result


def serialize_workflow(workflow):
    return {
        "workflow": workflow.name,
        "entry": workflow.entry,
        "nodes": {n.name: serialize_node(n) for n in workflow.nodes},
    }


def validate_egir(data):
    with open(_SCHEMA_PATH) as f:
        schema = json.load(f)
    jsonschema.validate(instance=data, schema=schema)

    entry = data["entry"]
    if entry not in data["nodes"]:
        raise ValueError(f"error: entry node '{entry}' does not exist")

    for name, node in data["nodes"].items():
        if node.get("terminal") and node.get("edges"):
            raise ValueError(
                f"error: terminal node '{name}' cannot have outgoing edges"
            )


def write_egir_json(workflow, output_file):
    data = serialize_workflow(workflow)
    validate_egir(data)

    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    print(f"[✓] EGIR JSON written to {output_file}")
