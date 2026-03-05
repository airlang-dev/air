import argparse
import os
import sys

from lark import Lark, UnexpectedInput


def main():
    parser = argparse.ArgumentParser(prog="air", description="AIR compiler")
    sub = parser.add_subparsers(dest="command")

    compile_p = sub.add_parser("compile", help="Compile AIR source to EGIR JSON")
    compile_p.add_argument("file", help="Path to .air source file")
    compile_p.add_argument("--output", "-o", help="Output path (default: build/<name>.egir.json)")

    backend_p = sub.add_parser("backend", help="Generate backend artifact from EGIR")
    backend_p.add_argument("backend_name", help="Backend name (e.g. langgraph)")
    backend_p.add_argument("egir_file", help="Path to EGIR JSON file")
    backend_p.add_argument("--output", "-o", help="Output path")

    args = parser.parse_args()

    if args.command == "compile":
        compile_air(args.file, args.output)
    elif args.command == "backend":
        run_backend(args.backend_name, args.egir_file, args.output)
    else:
        parser.print_help()
        sys.exit(1)


def compile_air(input_file, output_path):
    # Resolve paths relative to project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    grammar_path = os.path.join(project_root, "spec", "air.lark")

    with open(grammar_path) as f:
        grammar = f.read()

    lark_parser = Lark(grammar, start="start")

    with open(input_file) as f:
        source = f.read()

    try:
        tree = lark_parser.parse(source)
        print("[✓] Parsing successful")

        # Add compiler dir to path so internal bare imports work
        compiler_dir = os.path.dirname(os.path.abspath(__file__))
        if compiler_dir not in sys.path:
            sys.path.insert(0, compiler_dir)

        from semantic_check import SemanticChecker
        from ast_builder import ASTBuilder
        from cfg_builder import build_cfg
        from egir.builder import build_egir
        from egir.serializer import write_egir_json

        checker = SemanticChecker(tree)
        checker.run()
        print("[✓] Semantic validation successful")

        builder = ASTBuilder()
        program = builder.build(tree)

        for wf in program.workflows:
            cfg = build_cfg(wf)
            print("[✓] CFG built")

            egir = build_egir(cfg, wf.name)
            print("[✓] EGIR built")

            if output_path:
                out = output_path
            else:
                os.makedirs(os.path.join(project_root, "build"), exist_ok=True)
                out = os.path.join(project_root, "build", f"{wf.name}.egir.json")

            write_egir_json(egir, out)
            print(f"[✓] Artifact written: {out}")

    except UnexpectedInput as e:
        print("[✗] Parse error")
        print(e)
        sys.exit(1)


BACKENDS = {
    "langgraph": "backends.langgraph.backend:LangGraphBackend",
}


def run_backend(backend_name, egir_file, output_path):
    import json

    if backend_name not in BACKENDS:
        print(f"[✗] Unknown backend: {backend_name}")
        print(f"    Available: {', '.join(BACKENDS)}")
        sys.exit(1)

    with open(egir_file) as f:
        egir = json.load(f)
    print("[✓] Loaded EGIR artifact")

    module_path, class_name = BACKENDS[backend_name].rsplit(":", 1)
    from importlib import import_module

    mod = import_module(module_path)
    backend_cls = getattr(mod, class_name)
    backend = backend_cls()
    print(f"[✓] Backend: {backend_name}")

    code = backend.compile(egir, output_path)
    out = output_path or f"build/{egir['workflow']}_langgraph.py"
    print(f"[✓] Generated: {out}")


if __name__ == "__main__":
    main()
