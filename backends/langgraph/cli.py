import argparse
import json
import sys

from backends.langgraph.backend import LangGraphBackend


def main():
    parser = argparse.ArgumentParser(description="Compile EGIR to LangGraph Python")
    parser.add_argument("egir_json", help="Path to EGIR JSON file")
    parser.add_argument("--output", "-o", help="Output path (default: build/<workflow>_langgraph.py)")
    args = parser.parse_args()

    with open(args.egir_json) as f:
        egir = json.load(f)

    backend = LangGraphBackend()
    code = backend.compile(egir, args.output)

    output_path = args.output or f"build/{egir['workflow']}_langgraph.py"
    print(f"Generated {output_path}")


if __name__ == "__main__":
    main()
