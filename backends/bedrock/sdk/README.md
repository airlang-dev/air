# AIR SDK Lambdas for Bedrock Flows

Five Lambda functions that implement AIR instruction semantics on AWS Lambda (Python 3.12). The Bedrock Flow backend compiles AIR `verify`, `aggregate`, `gate`, `decide`, and `session` operations into `LambdaFunction` nodes that invoke these functions.

## Prerequisites

- AWS CLI configured with appropriate credentials
- An IAM role named `air-sdk-lambda-role` with `AWSLambdaBasicExecutionRole` + any additional permissions (SNS/DynamoDB for `air-sdk-decide`)
- Python 3.12 and `pip` available locally

## Deployment

```bash
# Package all Lambdas into dist/*.zip
make package

# Deploy to us-east-1 (default)
make deploy

# Deploy to a specific region
make deploy REGION=eu-west-1
```

Each function is created or updated in-place. The Makefile detects whether the function already exists and calls `create-function` or `update-function-code` accordingly.

---

## Functions

### `air-sdk-gate`

Maps a verdict or Consensus object to a routing outcome.

**Input**
```json
{"input": "PASS"}
```
or
```json
{"input": {"verdict": "FAIL", "votes": {...}, "strategy": "majority"}}
```

**Output**
```json
{"outcome": "PROCEED"}
```

| Verdict | Outcome |
|---------|---------|
| PASS | PROCEED |
| FAIL | ESCALATE |
| UNCERTAIN | RETRY |

**Dependencies:** none

---

### `air-sdk-aggregate`

Aggregates a list of verdicts using a configurable strategy.

**Input**
```json
{
  "verdicts": ["PASS", "FAIL", "PASS"],
  "params": {"strategy": "majority"}
}
```

**Output**
```json
{
  "consensus": {
    "verdict": "PASS",
    "votes": {"PASS": 2, "FAIL": 1, "UNCERTAIN": 0},
    "strategy": "majority"
  }
}
```

| Strategy | Behaviour |
|----------|-----------|
| `unanimous` | PASS only if all PASS; FAIL if any FAIL; else UNCERTAIN |
| `majority` | PASS/FAIL if strictly more than half; else UNCERTAIN |
| `union` | PASS if any PASS; FAIL only if all FAIL; else UNCERTAIN |

**Dependencies:** none

---

### `air-sdk-verify`

Verifies an input value against a rule using an LLM.

**Input**
```json
{
  "input": "The product SKU-123 exists in the catalog.",
  "params": {"rule": "product_existence", "model": "amazon.nova-lite-v1:0"}
}
```

**Output**
```json
{
  "verdict": "PASS",
  "evidence": {"reasoning": "The claim is verifiable...", "sources": []}
}
```

**Dependencies:** `litellm`

**Environment variables:** any API key required by the chosen model (e.g. `OPENAI_API_KEY`).

---

### `air-sdk-decide`

Dispatches a decision to a human reviewer or LLM provider.

**Input**
```json
{
  "input": "Draft article content...",
  "params": {"provider": "human_reviewer", "timeout_seconds": 300}
}
```
or
```json
{
  "input": "Draft article content...",
  "params": {"provider": "llm", "model": "amazon.nova-lite-v1:0"}
}
```

**Output**
```json
{"message": "Content looks good.", "outcome": "PROCEED"}
```

**Human reviewer infrastructure** (optional): set `DECISION_TOPIC_ARN` and `DECISION_TABLE_NAME` environment variables. The function publishes to SNS and polls DynamoDB for a response. Without these, it falls back to `ESCALATE`.

**Dependencies:** `litellm`, `boto3`

---

### `air-sdk-session`

Runs a multi-turn LLM conversation among participants following a protocol.

**Input**
```json
{
  "members": [
    {"name": "Reviewer", "role": "fact-checker", "model": "amazon.nova-lite-v1:0"},
    {"name": "Editor",   "role": "editor",       "model": "amazon.nova-lite-v1:0"}
  ],
  "protocol": "Each participant reviews the content and votes PASS or FAIL.",
  "history": [{"role": "user", "content": "Review this article: ..."}],
  "params": {"max_turns": 4}
}
```

**Output**
```json
{
  "result": {
    "consensus": "PASS",
    "history": [{"role": "assistant", "content": "[Reviewer]: PASS — ..."}]
  }
}
```

**Dependencies:** `litellm`

---

## Error Handling

All functions return a `__fault__` object on error:

```json
{"__fault__": {"reason": "Missing required field: input"}}
```

The Bedrock Flow compiler maps `$.data.__fault__ != null` as the Fault routing condition, so faults are automatically routed to error-handling nodes in the flow.
