import argparse
import os
import sys

from lark import UnexpectedInput


def main():
    parser = argparse.ArgumentParser(prog="air", description="AIR compiler")
    sub = parser.add_subparsers(dest="command")

    compile_p = sub.add_parser("compile", help="Compile AIR source to AIR Graph (.airc)")
    compile_p.add_argument("file", help="Path to .air source file")
    compile_p.add_argument("--output", "-o", help="Output path (default: build/<name>.airc)")

    backend_p = sub.add_parser("backend", help="Generate backend artifact from AIR Graph")
    backend_p.add_argument("backend_name", help="Backend name (e.g. langgraph)")
    backend_p.add_argument("air_graph_file", help="Path to AIR Graph (.airc) file")
    backend_p.add_argument("--output", "-o", help="Output path")

    args = parser.parse_args()

    if args.command == "compile":
        compile_air(args.file, args.output)
    elif args.command == "backend":
        run_backend(args.backend_name, args.air_graph_file, args.output)
    else:
        parser.print_help()
        sys.exit(1)


def compile_air(input_file, output_path):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Add compiler dir to path so internal bare imports work
    compiler_dir = os.path.dirname(os.path.abspath(__file__))
    if compiler_dir not in sys.path:
        sys.path.insert(0, compiler_dir)

    from air_parser import create_parser
    from semantic_check import check_program
    from ast_builder import ASTBuilder
    from cfg_builder import build_cfg
    from air_graph.builder import build_air_graph
    from air_graph.serializer import write_airc

    lark_parser = create_parser()

    with open(input_file) as f:
        source = f.read()

    try:
        tree = lark_parser.parse(source)
        print("[ok] Parsing successful")

        builder = ASTBuilder()
        program = builder.build(tree)
        print("[ok] AST built")

        check_program(program)
        print("[ok] Semantic validation successful")

        for wf in program.workflows:
            cfg = build_cfg(wf)
            print("[ok] CFG built")

            air_graph = build_air_graph(cfg, wf.name)
            print("[ok] AIR Graph built")

            if output_path:
                out = output_path
            else:
                os.makedirs(os.path.join(project_root, "build"), exist_ok=True)
                out = os.path.join(project_root, "build", f"{wf.name}.airc")

            write_airc(air_graph, out)

    except UnexpectedInput as e:
        print("[error] Parse error")
        print(e)
        sys.exit(1)


BACKENDS = {
    "langgraph": "backends.langgraph.backend:LangGraphBackend",
}


def run_backend(backend_name, air_graph_file, output_path):
    import json

    if backend_name not in BACKENDS:
        print(f"[error] Unknown backend: {backend_name}")
        print(f"    Available: {', '.join(BACKENDS)}")
        sys.exit(1)

    with open(air_graph_file) as f:
        air_graph = json.load(f)
    print("[ok] Loaded AIR Graph artifact")

    module_path, class_name = BACKENDS[backend_name].rsplit(":", 1)
    from importlib import import_module

    mod = import_module(module_path)
    backend_cls = getattr(mod, class_name)
    backend = backend_cls()
    print(f"[ok] Backend: {backend_name}")

    code = backend.compile(air_graph, output_path)
    out = output_path or f"build/{air_graph['workflow']}_langgraph.py"
    print(f"[ok] Generated: {out}")


if __name__ == "__main__":
    main()
