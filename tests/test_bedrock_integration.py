"""Integration tests: compile real .airc fixtures with BedrockBackend."""

import json
import re
from pathlib import Path

import pytest

from backends.bedrock.backend import BedrockBackend
from backends.bedrock.compiler import CompilationError

FIXTURES = Path(__file__).parent / "fixtures" / "compiled"
_BEDROCK_NAME_RE = re.compile(r"^[a-zA-Z]([_]?[0-9a-zA-Z]){1,50}$")


def _backend():
    return BedrockBackend(region="eu-west-1", account_id="999999999999")


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


# ── 19.1: FactCheckedPublish ───────────────────────────────────────────────────

class TestFactCheckedPublish:
    def setup_method(self):
        self.graph = _load("FactCheckedPublish.airc")
        self.flow_def, self.warnings = _backend().compile_with_warnings(
            self.graph, output_path=None
        )
        self.nodes = self.flow_def["nodes"]
        self.connections = self.flow_def["connections"]
        self.node_by_name = {n["name"]: n for n in self.nodes}

    def test_no_compilation_error(self):
        # setup_method would have raised if there was an error
        assert self.flow_def is not None

    def test_output_nodes_exist(self):
        output_nodes = [n for n in self.nodes if n["type"] == "Output"]
        assert len(output_nodes) >= 1

    def test_condition_nodes_exist(self):
        # FactCheckedPublish has conditional edges on validate and review nodes
        condition_nodes = [n for n in self.nodes if n["type"] == "Condition"]
        assert len(condition_nodes) >= 1

    def test_sdk_verify_arn_present(self):
        lambda_nodes = [n for n in self.nodes if n["type"] == "LambdaFunction"]
        arns = [
            n["configuration"]["lambdaFunction"]["lambdaArn"]
            for n in lambda_nodes
            if "lambdaFunction" in n.get("configuration", {})
        ]
        assert any("air-sdk-verify" in arn for arn in arns), (
            f"No air-sdk-verify ARN found. ARNs: {arns}"
        )

    def test_sdk_aggregate_arn_present(self):
        lambda_nodes = [n for n in self.nodes if n["type"] == "LambdaFunction"]
        arns = [
            n["configuration"]["lambdaFunction"]["lambdaArn"]
            for n in lambda_nodes
            if "lambdaFunction" in n.get("configuration", {})
        ]
        assert any("air-sdk-aggregate" in arn for arn in arns), (
            f"No air-sdk-aggregate ARN found. ARNs: {arns}"
        )

    def test_sdk_gate_arn_present(self):
        lambda_nodes = [n for n in self.nodes if n["type"] == "LambdaFunction"]
        arns = [
            n["configuration"]["lambdaFunction"]["lambdaArn"]
            for n in lambda_nodes
            if "lambdaFunction" in n.get("configuration", {})
        ]
        assert any("air-sdk-gate" in arn for arn in arns), (
            f"No air-sdk-gate ARN found. ARNs: {arns}"
        )

    def test_sdk_decide_arn_present(self):
        lambda_nodes = [n for n in self.nodes if n["type"] == "LambdaFunction"]
        arns = [
            n["configuration"]["lambdaFunction"]["lambdaArn"]
            for n in lambda_nodes
            if "lambdaFunction" in n.get("configuration", {})
        ]
        assert any("air-sdk-decide" in arn for arn in arns), (
            f"No air-sdk-decide ARN found. ARNs: {arns}"
        )

    def test_exactly_one_input_node(self):
        input_nodes = [n for n in self.nodes if n["type"] == "Input"]
        assert len(input_nodes) == 1

    def test_all_node_names_valid(self):
        for node in self.nodes:
            assert _BEDROCK_NAME_RE.match(node["name"]), (
                f"Node name {node['name']!r} does not match Bedrock regex"
            )

    def test_referential_integrity(self):
        node_names = {n["name"] for n in self.nodes}
        for conn in self.connections:
            assert conn["source"] in node_names
            assert conn["target"] in node_names

    def test_connection_names_unique(self):
        names = [c["name"] for c in self.connections]
        assert len(names) == len(set(names))

    def test_node_names_unique(self):
        names = [n["name"] for n in self.nodes]
        assert len(names) == len(set(names))


# ── 19.2: SimpleLLM ───────────────────────────────────────────────────────────

class TestSimpleLLM:
    def setup_method(self):
        self.graph = _load("SimpleLLM.airc")
        self.flow_def, self.warnings = _backend().compile_with_warnings(
            self.graph, output_path=None
        )
        self.nodes = self.flow_def["nodes"]

    def test_exactly_one_prompt_node(self):
        prompt_nodes = [n for n in self.nodes if n["type"] == "Prompt"]
        assert len(prompt_nodes) == 1

    def test_prompt_node_has_template_configuration(self):
        prompt_node = next(n for n in self.nodes if n["type"] == "Prompt")
        cfg = prompt_node["configuration"]
        assert "prompt" in cfg
        src = cfg["prompt"]["sourceConfiguration"]
        assert "inline" in src
        inline = src["inline"]
        assert "modelId" in inline
        assert inline["templateType"] == "TEXT"
        assert "templateConfiguration" in inline
        text_cfg = inline["templateConfiguration"]["text"]
        assert "text" in text_cfg
        assert "inputVariables" in text_cfg

    def test_prompt_node_has_non_empty_model_id(self):
        prompt_node = next(n for n in self.nodes if n["type"] == "Prompt")
        model_id = prompt_node["configuration"]["prompt"]["sourceConfiguration"]["inline"]["modelId"]
        assert model_id and isinstance(model_id, str)

    def test_output_node_exists(self):
        output_nodes = [n for n in self.nodes if n["type"] == "Output"]
        assert len(output_nodes) >= 1

    def test_flow_input_node_exists(self):
        input_nodes = [n for n in self.nodes if n["type"] == "Input"]
        assert len(input_nodes) == 1
        assert input_nodes[0]["name"] == "FlowInputNode"

    def test_no_condition_nodes(self):
        # SimpleLLM has no conditional edges
        condition_nodes = [n for n in self.nodes if n["type"] == "Condition"]
        assert not condition_nodes


# ── 19.3: SimpleVerify ────────────────────────────────────────────────────────

class TestSimpleVerify:
    def setup_method(self):
        self.graph = _load("SimpleVerify.airc")
        self.flow_def, self.warnings = _backend().compile_with_warnings(
            self.graph, output_path=None
        )
        self.nodes = self.flow_def["nodes"]

    def test_verify_lambda_node_present(self):
        lambda_nodes = [n for n in self.nodes if n["type"] == "LambdaFunction"]
        arns = [
            n["configuration"]["lambdaFunction"]["lambdaArn"]
            for n in lambda_nodes
            if "lambdaFunction" in n.get("configuration", {})
        ]
        assert any("air-sdk-verify" in arn for arn in arns), (
            f"No air-sdk-verify ARN found. ARNs: {arns}"
        )

    def test_verify_lambda_arn_format(self):
        lambda_nodes = [n for n in self.nodes if n["type"] == "LambdaFunction"]
        verify_nodes = [
            n for n in lambda_nodes
            if "air-sdk-verify" in n.get("configuration", {}).get("lambdaFunction", {}).get("lambdaArn", "")
        ]
        assert verify_nodes
        arn = verify_nodes[0]["configuration"]["lambdaFunction"]["lambdaArn"]
        # arn:aws:lambda:{region}:{account}:function:air-sdk-verify
        assert arn.startswith("arn:aws:lambda:")
        assert arn.endswith("air-sdk-verify")

    def test_output_node_exists(self):
        output_nodes = [n for n in self.nodes if n["type"] == "Output"]
        assert len(output_nodes) >= 1

    def test_no_compilation_error(self):
        assert self.flow_def is not None

    def test_all_lambda_nodes_have_valid_arns(self):
        for node in self.nodes:
            if node["type"] == "LambdaFunction":
                arn = node.get("configuration", {}).get("lambdaFunction", {}).get("lambdaArn", "")
                assert arn.startswith("arn:aws:lambda:"), (
                    f"Node {node['name']!r} has invalid ARN: {arn!r}"
                )
