import pprint
from lark import Lark, UnexpectedInput
from semantic_check import SemanticChecker
from ast_builder import ASTBuilder

with open("spec/air.lark") as f:
    grammar = f.read()

parser = Lark(grammar, start="start")

with open("examples/example_7.air") as f:
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

    for wf in program.workflows:
        cfg = build_cfg(wf)
        print(f"\n[✓] CFG built for workflow '{wf.name}'\n")
        print(cfg)

        from egir_builder import build_egir

        egir = build_egir(cfg)
        print(f"[✓] EGIR built for workflow '{wf.name}'\n")
        print(egir)

except UnexpectedInput as e:
    print("[✗] Parse error\n")
    print(e)
