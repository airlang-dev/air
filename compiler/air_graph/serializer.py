"""AIR Graph serializer for v0.2.

Converts AirGraphWorkflow to JSON and validates against the v0.2 schema.
"""

import json
import os

import jsonschema

from air_graph.schema import AIR_GRAPH_VERSION

_SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "spec",
    f"v{AIR_GRAPH_VERSION}",
    "air_graph.schema.json",
)


def serialize_output(output):
    result = {"name": output.name}
    if output.type:
        result["type"] = output.type
    return result


def serialize_operation(op):
    return {
        "type": op.type,
        "inputs": op.inputs,
        "outputs": [serialize_output(o) for o in op.outputs],
        "params": op.params if op.params else {},
    }


def serialize_condition(condition):
    result = {"kind": condition.kind}
    if condition.name is not None:
        result["name"] = condition.name
    if condition.value is not None:
        result["value"] = condition.value
    if condition.is_list:
        result["is_list"] = condition.is_list
    return result


def serialize_edge(edge):
    result = {"target": edge.target}
    if edge.condition:
        result["condition"] = serialize_condition(edge.condition)
    return result


def serialize_node(node):
    result = {
        "operations": [serialize_operation(op) for op in node.operations],
        "terminal": node.terminal,
    }
    if node.route_variable is not None:
        result["route_variable"] = node.route_variable
    if node.edges:
        result["edges"] = [serialize_edge(e) for e in node.edges]
    return result


def serialize_param(param):
    return {"name": param.name, "type": param.type}


def serialize_air_graph(workflow) -> dict:
    result = {
        "air_graph_version": AIR_GRAPH_VERSION,
        "workflow": workflow.name,
        "entry": workflow.entry,
        "nodes": {n.name: serialize_node(n) for n in workflow.nodes},
    }
    if workflow.params:
        result["params"] = [serialize_param(p) for p in workflow.params]
    return result


def validate_air_graph(data):
    with open(_SCHEMA_PATH) as f:
        schema = json.load(f)
    jsonschema.validate(instance=data, schema=schema)

    entry = data["entry"]
    if entry not in data["nodes"]:
        raise ValueError(f"error: entry node '{entry}' does not exist")


def write_airc(workflow, output_file):
    data = serialize_air_graph(workflow)
    validate_air_graph(data)

    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    print(f"[ok] AIR Graph written to {output_file}")
