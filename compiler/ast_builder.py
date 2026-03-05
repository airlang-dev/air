from lark import Tree, Token
from air_ast import *


class ASTBuilder:

    # -------------------------------------------------
    # entry
    # -------------------------------------------------

    def build(self, tree: Tree) -> Program:

        workflows = []

        for node in tree.children:
            if isinstance(node, Tree) and node.data == "air_program":
                workflows.extend(self._build_program(node))

        return Program(workflows)

    # -------------------------------------------------
    # program
    # -------------------------------------------------

    def _build_program(self, node):

        workflows = []

        for child in node.children:
            if isinstance(child, Tree) and child.data == "workflow_decl":
                workflows.append(self._build_workflow(child))

        return workflows

    # -------------------------------------------------
    # workflow
    # -------------------------------------------------

    def _build_workflow(self, node):

        name = None
        return_types = []
        blocks = []
        fault_handler = None

        current_block = Block(label="entry", instructions=[])

        for child in node.children:

            # workflow name
            if isinstance(child, Token):
                if name is None:
                    name = child.value

            elif isinstance(child, Tree):

                if child.data == "return_type":
                    return_types = self._build_return_types(child)

                elif child.data == "workflow_body":

                    for stmt in child.children:

                        if stmt.data != "statement":
                            continue

                        node = stmt.children[0]

                        # label → new block
                        if node.data == "block_label":

                            blocks.append(current_block)

                            label = self._identifier(node.children[0])
                            current_block = Block(label=label, instructions=[])

                            continue

                        instr = self._build_statement(node)

                        if instr:
                            current_block.instructions.append(instr)

                elif child.data == "fault_handler":
                    fault_handler = self._build_fault_handler(child)

        blocks.append(current_block)

        return Workflow(
            name=name,
            return_types=return_types,
            blocks=blocks,
            fault_handler=fault_handler,
        )

    # -------------------------------------------------
    # return types
    # -------------------------------------------------

    def _build_return_types(self, node):

        types = []

        for child in node.children:
            if isinstance(child, Tree) and child.data == "type_name":
                types.append(self._build_type(child))

        return types

    # -------------------------------------------------
    # fault handler
    # -------------------------------------------------

    def _build_fault_handler(self, node):

        block = Block(label="fault_handler", instructions=[])

        for child in node.children:

            if isinstance(child, Tree) and child.data == "statement":
                instr = self._build_statement(child.children[0])
                block.instructions.append(instr)

        return block

    # -------------------------------------------------
    # statements
    # -------------------------------------------------

    def _build_statement(self, node):

        if node.data == "assignment":
            return self._build_assignment(node)

        if node.data == "route_stmt":
            return self._build_route(node)

        if node.data == "parallel_block":
            return self._build_parallel(node)

        if node.data == "loop_block":
            return self._build_loop(node)

        if node.data == "return_stmt":
            return self._build_return(node)

        if node.data == "continue_stmt":
            return Continue()

        if node.data == "unreachable_stmt":
            return Unreachable()

        return None

    # -------------------------------------------------
    # assignment
    # -------------------------------------------------

    def _build_assignment(self, node):

        lvalue = node.children[0]
        expr = node.children[1]

        targets = []

        for child in lvalue.children:
            targets.append(self._identifier(child))

        value = self._build_expression(expr)

        return Assign(targets=targets, value=value)

    # -------------------------------------------------
    # route
    # -------------------------------------------------

    def _build_route(self, node):

        value = self._identifier(node.children[0])
        cases = []

        for child in node.children:

            if isinstance(child, Tree) and child.data == "route_case":

                pattern = self._build_pattern(child.children[0])
                target = self._identifier(child.children[1])

                cases.append(RouteCase(pattern, target))

        return Route(value=value, cases=cases)

    # -------------------------------------------------
    # parallel
    # -------------------------------------------------

    def _build_parallel(self, node):

        branches = []

        for child in node.children:

            if isinstance(child, Tree) and child.data == "statement":
                instr = self._build_statement(child.children[0])
                if instr:
                    branches.append(instr)

        return Parallel(branches)

    # -------------------------------------------------
    # loop
    # -------------------------------------------------

    def _build_loop(self, node):

        name = self._identifier(node.children[0])
        max_iter = int(node.children[1].value)

        body = []

        for child in node.children:

            if isinstance(child, Tree) and child.data == "statement":
                instr = self._build_statement(child.children[0])
                if instr:
                    body.append(instr)

        return Loop(name=name, max_iterations=max_iter, body=body)

    # -------------------------------------------------
    # return
    # -------------------------------------------------

    def _build_return(self, node):

        expr = self._build_expression(node.children[0])

        return Return(expr)

    # -------------------------------------------------
    # patterns
    # -------------------------------------------------

    def _build_pattern(self, node):

        if isinstance(node, Tree) and node.data == "pattern":
            node = node.children[0]

        if isinstance(node, Token):

            val = node.value

            if val in {"PROCEED", "RETRY", "ESCALATE", "HALT"}:
                return EnumPattern(val)

            if val == "default":
                return DefaultPattern()

            if val in {"Message", "Artifact", "Fault", "Verdict", "Consensus", "Outcome", "Evidence"}:
                return TypePattern(val)

            return EnumPattern(val)

        if isinstance(node, Tree):

            if node.data == "type_name":
                t = self._build_type(node)
                return TypePattern(t.name, t.is_list)

        return DefaultPattern()

    # -------------------------------------------------
    # expressions
    # -------------------------------------------------

    def _build_expression(self, node):

        # unwrap grammar wrapper
        if node.data == "expression":
            node = node.children[0]

        if node.data == "llm_call":
            return LLMCall(prompt=self._identifier(node.children[0]))

        if node.data == "verify_call":
            return Verify(
                input=self._identifier(node.children[0]),
                rule=self._identifier(node.children[1]),
            )

        if node.data == "gate_call":
            return Gate(input=self._identifier(node.children[0]))

        if node.data == "aggregate_call":

            inputs = []

            list_node = node.children[0]

            for child in list_node.children:
                inputs.append(self._identifier(child))

            strategy = self._identifier(node.children[1])

            return Aggregate(inputs, strategy)

        if node.data == "decide_call":

            provider = self._identifier(node.children[0])
            inp = None

            if len(node.children) > 1:
                inp = self._identifier(node.children[1])

            return Decide(provider, inp)

        if node.data == "transform_expr":

            inp = self._identifier(node.children[0])
            t = self._build_type(node.children[1])
            via = None

            if len(node.children) > 2:
                via = LLMCall(self._identifier(node.children[2].children[0]))

            return Transform(inp, t, via)

        if node.data == "constructor":

            type_name = self._identifier(node.children[0])
            fields = {}

            if len(node.children) > 1:

                field_list = node.children[1]

                for field in field_list.children:
                    key = self._identifier(field.children[0])
                    value_node = field.children[1]

                    if isinstance(value_node, Tree) and value_node.data == "value":
                        value_node = value_node.children[0]

                    if isinstance(value_node, Token) and value_node.type == "STRING":
                        value = value_node.value[1:-1]  # remove quotes
                    else:
                        value = self._identifier(value_node)

                    fields[key] = value

            return Constructor(type_name, fields)

        raise Exception(f"Unknown expression: {node.data}")

    # -------------------------------------------------
    # types
    # -------------------------------------------------

    def _build_type(self, node):
        name = node.children[0].value

        is_list = False

        for child in node.children[1:]:
            if isinstance(child, Tree) and child.data == "array_suffix":
                is_list = True

        return Type(name=name, is_list=is_list)

    # -------------------------------------------------
    # helpers
    # -------------------------------------------------

    def _identifier(self, node):

        if isinstance(node, Token):
            return node.value

        if isinstance(node, Tree):
            return self._identifier(node.children[0])

        return None
