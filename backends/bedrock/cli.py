import argparse
import json
import sys

from backends.bedrock.backend import BedrockBackend
from backends.bedrock.compiler import CompilationError


def main():
    parser = argparse.ArgumentParser(
        description="Compile AIR Graph to AWS Bedrock Flow JSON"
    )
    parser.add_argument("air_graph_json", help="Path to AIR Graph (.airc) file")
    parser.add_argument(
        "--output", "-o",
        help="Output path (default: build/<workflow>_bedrock.json)"
    )
    parser.add_argument(
        "--model",
        default="amazon.nova-lite-v1:0",
        help="Default foundation model ID (default: amazon.nova-lite-v1:0)"
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region for SDK ARNs (default: us-east-1)"
    )
    parser.add_argument(
        "--account-id",
        default="123456789012",
        help="AWS account ID for SDK ARNs (default: 123456789012)"
    )
    parser.add_argument(
        "--assets",
        help="Path to assets directory for prompt resolution"
    )
    args = parser.parse_args()

    with open(args.air_graph_json) as f:
        air_graph = json.load(f)

    backend = BedrockBackend(
        default_model_id=args.model,
        region=args.region,
        account_id=args.account_id,
        assets_dir=args.assets,
    )

    output_path = args.output or f"build/{air_graph.get('workflow', 'workflow')}_bedrock.json"

    try:
        flow_def, warnings = backend.compile_with_warnings(air_graph, output_path)
    except CompilationError as e:
        print(f"[error] Compilation failed: {e}", file=sys.stderr)
        sys.exit(1)

    if warnings:
        for w in warnings:
            print(f"[warning] {w}", file=sys.stderr)
    else:
        print(f"[ok] Compiled cleanly: {output_path}")

    print(f"[ok] Generated: {output_path}")


if __name__ == "__main__":
    main()
