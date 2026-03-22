import json
import os

import jsonschema

from backends.base_backend import Backend
from backends.bedrock.compiler import (
    CompilerConfig, WarningCollector, CompilationError,
    NodeCompiler, EdgeCompiler, LoopCompiler,
)
from backends.bedrock.naming import NodeNamer
from backends.bedrock.asset_resolver import CompileTimeAssetResolver


_DEFAULT_REGION = "us-east-1"
_DEFAULT_ACCOUNT_ID = "123456789012"


def _load_schema() -> dict:
    """Load the AIR Graph JSON schema from spec/v0.2/."""
    schema_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "spec", "v0.2", "air_graph.schema.json"
    )
    with open(schema_path) as f:
        return json.load(f)


class BedrockBackend(Backend):
    def __init__(
        self,
        default_model_id: str = "amazon.nova-lite-v1:0",
        region: str = _DEFAULT_REGION,
        account_id: str = _DEFAULT_ACCOUNT_ID,
        assets_dir: str | None = None,
    ):
        self._default_model_id = default_model_id
        self._region = region
        self._account_id = account_id
        self._assets_dir = assets_dir
        # Collect init-time warnings (default region/account_id)
        self._init_warnings: list[str] = []
        if region == _DEFAULT_REGION:
            self._init_warnings.append(
                "WARNING: using default region 'us-east-1'. "
                "Supply --region with your real AWS region before deploying."
            )
        if account_id == _DEFAULT_ACCOUNT_ID:
            self._init_warnings.append(
                "WARNING: using default account_id '123456789012'. "
                "Supply --account-id with your real AWS account ID before deploying."
            )

    def compile_with_warnings(
        self,
        air_graph: dict,
        output_path: str | None = None,
    ) -> tuple[dict, list[str]]:
        """Compile AIR Graph to Bedrock Flow definition.

        Returns (flow_definition, warnings).
        Raises CompilationError on hard failures.
        """
        warnings = WarningCollector()

        # Replay init warnings
        for w in self._init_warnings:
            warnings.warn(w)

        # Phase 1: Validate input
        try:
            schema = _load_schema()
            jsonschema.validate(air_graph, schema)
        except jsonschema.ValidationError as e:
            raise CompilationError(f"Invalid AIR Graph: {e.message}") from e

        config = CompilerConfig(
            default_model_id=self._default_model_id,
            region=self._region,
            account_id=self._account_id,
            assets_dir=self._assets_dir,
        )

        asset_resolver = None
        if self._assets_dir:
            asset_resolver = CompileTimeAssetResolver(self._assets_dir)

        namer = NodeNamer()
        node_compiler = NodeCompiler(config, warnings, asset_resolver)
        edge_compiler = EdgeCompiler(config, warnings)

        # Phase 2: Build FlowInputNode
        flow_input_node = {
            "name": "FlowInputNode",
            "type": "Input",
            "inputs": [],
            "outputs": [{"name": "document", "type": "Object"}],
            "configuration": {}
        }
        namer._used.add("FlowInputNode")

        all_nodes: list[dict] = [flow_input_node]
        all_connections: list[dict] = []

        air_nodes = air_graph.get("nodes", {})
        entry = air_graph.get("entry", "")

        # Track first/last Bedrock node per AIR node
        air_node_to_first_bedrock: dict[str, str] = {}
        air_node_to_last_bedrock: dict[str, str] = {}

        # Phase 3: Compile each AIR node
        for air_node_name, air_node in air_nodes.items():
            nodes, conns = node_compiler.compile_node(air_node_name, air_node, namer)
            if nodes:
                # Track first and last non-Output node
                air_node_to_first_bedrock[air_node_name] = nodes[0]["name"]
                # Last non-Output node (for edge compilation)
                non_output = [n for n in nodes if n["type"] != "Output"]
                if non_output:
                    air_node_to_last_bedrock[air_node_name] = non_output[-1]["name"]
                else:
                    air_node_to_last_bedrock[air_node_name] = nodes[-1]["name"]
            all_nodes.extend(nodes)
            all_connections.extend(conns)

        # Phase 4: Connect FlowInputNode to entry node
        if entry in air_node_to_first_bedrock:
            entry_first = air_node_to_first_bedrock[entry]
            conn_name = namer.connection_name("FlowInputNode", entry_first)
            all_connections.append({
                "name": conn_name,
                "type": "Data",
                "source": "FlowInputNode",
                "target": entry_first,
                "configuration": {
                    "data": {
                        "sourceOutput": "document",
                        "targetInput": "document"
                    }
                }
            })

        # Phase 5: Compile edges
        for air_node_name, air_node in air_nodes.items():
            last_node = air_node_to_last_bedrock.get(air_node_name)
            if not last_node:
                continue
            extra_nodes, conns = edge_compiler.compile_edges(
                air_node,
                last_node,
                air_node_to_first_bedrock,
                namer,
                air_node_name=air_node_name,
            )
            all_nodes.extend(extra_nodes)
            all_connections.extend(conns)

        # Phase 6: Validate output
        node_names = [n["name"] for n in all_nodes]

        # Node count limit
        if len(all_nodes) > 40:
            raise CompilationError(
                f"Compiled flow has {len(all_nodes)} nodes, exceeding the Bedrock limit of 40. "
                "Refactor the workflow to reduce node count."
            )

        # Connection count warning
        if len(all_connections) > 20:
            warnings.warn(
                f"Flow has {len(all_connections)} connections, which may exceed AWS limits. "
                "Validate with: aws bedrock-agent validate-flow-definition"
            )

        # Referential integrity
        node_name_set = set(node_names)
        for conn in all_connections:
            if conn["source"] not in node_name_set:
                raise CompilationError(
                    f"Connection '{conn['name']}' references unknown source node '{conn['source']}'"
                )
            if conn["target"] not in node_name_set:
                raise CompilationError(
                    f"Connection '{conn['name']}' references unknown target node '{conn['target']}'"
                )

        # Name uniqueness
        if len(node_names) != len(node_name_set):
            dupes = [n for n in node_names if node_names.count(n) > 1]
            raise CompilationError(f"Duplicate node names: {set(dupes)}")

        conn_names = [c["name"] for c in all_connections]
        if len(conn_names) != len(set(conn_names)):
            dupes = [n for n in conn_names if conn_names.count(n) > 1]
            raise CompilationError(f"Duplicate connection names: {set(dupes)}")

        # Exactly one Input, at least one Output
        input_nodes = [n for n in all_nodes if n["type"] == "Input"]
        output_nodes = [n for n in all_nodes if n["type"] == "Output"]
        if len(input_nodes) != 1:
            raise CompilationError(f"Expected exactly 1 Input node, got {len(input_nodes)}")
        if len(output_nodes) < 1:
            raise CompilationError("Expected at least 1 Output node")

        flow_def = {"nodes": all_nodes, "connections": all_connections}

        # Phase 7: Serialize if output_path provided
        if output_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(flow_def, f, indent=2)

        return flow_def, warnings.warnings()

    def compile(
        self,
        air_graph: dict,
        output_path: str | None = None,
    ) -> dict:
        """Compile AIR Graph to Bedrock Flow definition dict.

        Implements the Backend interface. Warnings are discarded (use
        compile_with_warnings() for programmatic access to warnings).
        """
        workflow = air_graph.get("workflow", "workflow")
        if output_path is None:
            output_path = f"build/{workflow}_bedrock.json"

        flow_def, _ = self.compile_with_warnings(air_graph, output_path)
        return flow_def
