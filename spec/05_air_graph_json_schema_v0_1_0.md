# AIR Graph JSON Schema
Version: 0.1.0

## Purpose

AIR Graph JSON is the serialized execution graph produced by the AIR compiler.

Pipeline:

AIR → AST → CFG → AIR Graph → **AIR Graph JSON** → Agent VM

AIR Graph JSON is the **runtime artifact** consumed by the Agent Virtual Machine.

---

# Top-Level Structure

```

AirGraphWorkflow

````

```json
{
  "workflow": "WorkflowName",
  "entry": "entry_node_name",
  "nodes": [ ExecNode ]
}
````

Fields:

| Field    | Type       | Description   |
| -------- | ---------- | ------------- |
| workflow | string     | workflow name |
| entry    | string     | entry node    |
| nodes    | ExecNode[] | node list     |

---

# ExecNode

```json
{
  "name": "verification",
  "operations": [ Operation ],
  "route_variable": "outcome",
  "edges": [ Edge ],
  "terminal": false
}
```

Fields:

| Field          | Type        | Description                       |
| -------------- | ----------- | --------------------------------- |
| name           | string      | node label                        |
| operations     | Operation[] | operations executed in this node  |
| route_variable | string      | variable used for routing         |
| edges          | Edge[]      | outgoing edges                    |
| terminal       | boolean     | whether node terminates execution |

---

# Operation

```json
{
  "type": "verify",
  "inputs": ["claims"],
  "outputs": ["v1"],
  "params": {
    "rule": "product_existence"
  }
}
```

Fields:

| Field   | Type     | Description          |
| ------- | -------- | -------------------- |
| type    | string   | operation type       |
| inputs  | string[] | variable inputs      |
| outputs | string[] | variable outputs     |
| params  | object   | operation parameters |

---

# Edge

```json
{
  "condition": "PROCEED",
  "target": "publish"
}
```

Fields:

| Field     | Type   | Description       |
| --------- | ------ | ----------------- |
| condition | string | routing condition |
| target    | string | target node       |

Conditions may be:

```
PROCEED
ESCALATE
RETRY
HALT
Fault
Claim[]
continue
```

---

# Example

```json
{
  "workflow": "Aurora_Fact_Check",
  "entry": "entry",
  "nodes": [
    {
      "name": "verification",
      "operations": [
        {
          "type": "verify",
          "inputs": ["claims"],
          "outputs": ["v1"],
          "params": { "rule": "product_existence" }
        },
        {
          "type": "aggregate",
          "inputs": ["v1","v2","v3"],
          "outputs": ["consensus"],
          "params": { "strategy": "majority" }
        },
        {
          "type": "gate",
          "inputs": ["consensus"],
          "outputs": ["outcome"],
          "params": {}
        }
      ],
      "route_variable": "outcome",
      "edges": [
        {"condition": "PROCEED", "target": "publish"},
        {"condition": "ESCALATE", "target": "review"},
        {"condition": "RETRY", "target": "regenerate"},
        {"condition": "HALT", "target": "abort"}
      ],
      "terminal": false
    }
  ]
}
```
