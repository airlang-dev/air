import argparse
import json
import sys

from backends.langgraph.backend import LangGraphBackend


def main():
    parser = argparse.ArgumentParser(
        description="Compile AIR Graph to LangGraph Python"
    )
    parser.add_argument("air_graph_json", help="Path to AIR Graph (.airc) file")
    parser.add_argument(
        "--output", "-o", help="Output path (default: build/<workflow>_langgraph.py)"
    )
    args = parser.parse_args()

    with open(args.air_graph_json) as f:
        air_graph = json.load(f)

    backend = LangGraphBackend()
    code = backend.compile(air_graph, args.output)

    output_path = args.output or f"build/{air_graph['workflow']}_langgraph.py"
    print(f"Generated {output_path}")


if __name__ == "__main__":
    main()
