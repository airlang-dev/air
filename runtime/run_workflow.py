import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from runtime.agent_vm import execute_workflow


def main():
    if len(sys.argv) < 2:
        print("Usage: python runtime/run_workflow.py <workflow.airc>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path) as f:
        data = json.load(f)

    print(f"[VM] executing workflow: {data['workflow']}")
    result = execute_workflow(data)
    print(f"\n[VM] result: {result}")


if __name__ == "__main__":
    main()
