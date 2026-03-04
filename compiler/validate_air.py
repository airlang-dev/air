import os
import pprint
import sys
from lark import Lark, UnexpectedInput
from semantic_check import SemanticChecker
from ast_builder import ASTBuilder

if len(sys.argv) < 2:
    print("Usage: python compiler/validate_air.py <file.air>")
    sys.exit(1)

input_file = sys.argv[1]

with open("spec/air.lark") as f:
    grammar = f.read()

parser = Lark(grammar, start="start")

with open(input_file) as f:
    source = f.read()

try:
    tree = parser.parse(source)
    print("[✓] Parsing successful")

    checker = SemanticChecker(tree)
    checker.run()
    print("[✓] Semantic validation successful\n")

    print(tree.pretty())

    builder = ASTBuilder()
    program = builder.build(tree)
    pprint.pp(program, width=120, compact=True)

    from cfg_builder import build_cfg
    from egir_builder import build_egir
    from egir_serializer import write_egir_json

    for wf in program.workflows:
        cfg = build_cfg(wf)
        print(f"\n[✓] CFG built for workflow '{wf.name}'\n")
        print(cfg)

        egir = build_egir(cfg, wf.name)
        print(f"[✓] EGIR built for workflow '{wf.name}'\n")
        print(egir)

        base = os.path.splitext(input_file)[0]
        output_file = f"{base}.egir.json"
        write_egir_json(egir, output_file)

except UnexpectedInput as e:
    print("[✗] Parse error\n")
    print(e)
