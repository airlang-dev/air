from lark import Tree, Token
from air_ast import (
    Aggregate, Assign, BoolPattern, Constructor, Decide, DottedName,
    ElsePattern, EnumPattern, FuncCall, Gate, Identifier, LLMCall,
    ListLiteral, MapCall, Node, NodeCall, Parallel, Param, Program,
    Return, Route, RouteCase, Session, ToolCall, Transform, Type,
    TypePattern, Unreachable, Verify,
)

# Instruction keywords that are syntactically identical to node_call
# but should be recognized as instruction calls.
INSTRUCTION_KEYWORDS = {"tool", "llm", "session"}

# Known type names for pattern disambiguation
TYPE_NAMES = {"Message", "Artifact", "Fault", "Verdict", "Consensus",
              "Outcome", "Evidence", "Claim"}

# Known enum values for pattern disambiguation
ENUM_VALUES = {"PROCEED", "RETRY", "ESCALATE", "HALT",
               "PASS", "FAIL", "UNCERTAIN"}


class ASTBuilder:

    def build(self, tree: Tree) -> Program:
        program_node = tree.children[0]
        return self._build_program(program_node)

    # -------------------------------------------------
    # program
    # -------------------------------------------------

    def _build_program(self, node: Tree) -> Program:
        version = None
        mode = None
        workflows = []

        for child in node.children:
            if isinstance(child, Tree):
                if child.data == "version_decl":
                    version = self._token_value(child.children[0])
                    for vc in child.children:
                        if isinstance(vc, Tree) and vc.data == "mode_decl":
                            mode = self._token_value(vc.children[0])
                elif child.data == "workflow_decl":
                    workflows.append(self._build_workflow(child))

        return Program(version=version, mode=mode, workflows=workflows)

    # -------------------------------------------------
    # workflow
    # -------------------------------------------------

    def _build_workflow(self, node: Tree) -> "Workflow":
        from air_ast import Workflow

        name = None
        params = []
        return_types = []
        nodes = []

        for child in node.children:
            if isinstance(child, Token):
                if name is None:
                    name = child.value
            elif isinstance(child, Tree):
                if child.data == "workflow_params":
                    params = self._build_workflow_params(child)
                elif child.data == "return_type":
                    return_types = self._build_return_types(child)
                elif child.data == "node_decl":
                    nodes.append(self._build_node(child))

        return Workflow(name=name, params=params,
                        return_types=return_types, nodes=nodes)

    def _build_workflow_params(self, node: Tree) -> list[Param]:
        params = []
        for child in node.iter_subtrees():
            if child.data == "param":
                name = self._token_value(child.children[0])
                type_ = self._build_type(child.children[1])
                params.append(Param(name=name, type=type_))
        return params

    def _build_return_types(self, node: Tree) -> list[Type]:
        types = []
        for child in node.children:
            if isinstance(child, Tree) and child.data == "type_name":
                types.append(self._build_type(child))
        return types

    # -------------------------------------------------
    # node
    # -------------------------------------------------

    def _build_node(self, node: Tree) -> Node:
        name = None
        params = []
        max_visits = None
        is_fallback = False
        body = []

        for child in node.children:
            if isinstance(child, Token):
                if name is None:
                    name = child.value
            elif isinstance(child, Tree):
                if child.data == "node_params":
                    params = self._build_identifier_list(child)
                elif child.data == "node_modifiers":
                    for mod in child.iter_subtrees():
                        if mod.data == "max_modifier":
                            max_visits = int(self._token_value(mod.children[0]))
                        elif mod.data == "fallback_modifier":
                            is_fallback = True
                elif child.data == "statement":
                    instr = self._build_statement(child.children[0])
                    if instr is not None:
                        body.append(instr)

        return Node(name=name, params=params, max_visits=max_visits,
                    is_fallback=is_fallback, body=body)

    def _build_identifier_list(self, node: Tree) -> list[str]:
        result = []
        for child in node.iter_subtrees():
            if child.data == "identifier_list":
                for tok in child.children:
                    if isinstance(tok, Token):
                        result.append(tok.value)
        return result

    # -------------------------------------------------
    # body / statements
    # -------------------------------------------------

    def _build_statement(self, node: Tree):
        if node.data == "assignment":
            return self._build_assignment(node)
        if node.data == "route_stmt":
            return self._build_route(node)
        if node.data == "parallel_block":
            return self._build_parallel(node)
        if node.data == "return_stmt":
            return self._build_return(node)
        if node.data == "unreachable_stmt":
            return Unreachable()
        if node.data == "bare_expression":
            return self._build_bare_expression(node)
        return None

    # -------------------------------------------------
    # assignment
    # -------------------------------------------------

    def _build_assignment(self, node: Tree):
        lvalue = node.children[0]
        expr_node = node.children[1]

        targets = [self._token_value(tok) for tok in lvalue.children
                    if isinstance(tok, Token)]

        value = self._build_expression(expr_node)
        return Assign(targets=targets, value=value)

    # -------------------------------------------------
    # bare expression
    # -------------------------------------------------

    def _build_bare_expression(self, node: Tree):
        call = node.children[0]

        if call.data == "tool_call":
            return self._build_tool_call(call)
        if call.data == "llm_call":
            return self._build_llm_call(call)
        if call.data == "session_call":
            return self._build_session(call)
        if call.data == "node_call":
            name = self._token_value(call.children[0])
            args = self._build_arg_list(call) if len(call.children) > 1 else []
            return NodeCall(name=name, args=args)

        return None

    # -------------------------------------------------
    # expressions
    # -------------------------------------------------

    def _build_expression(self, node: Tree):
        # Unwrap wrapper nodes
        if node.data == "expression":
            node = node.children[0]

        if isinstance(node, Token):
            return Identifier(node.value)

        if node.data == "llm_call":
            return self._build_llm_call(node)
        if node.data == "tool_call":
            return self._build_tool_call(node)
        if node.data == "verify_call":
            return self._build_verify(node)
        if node.data == "aggregate_call":
            return self._build_aggregate(node)
        if node.data == "gate_call":
            return self._build_gate(node)
        if node.data == "decide_call":
            return self._build_decide(node)
        if node.data == "session_call":
            return self._build_session(node)
        if node.data == "transform_expr":
            return self._build_transform(node)
        if node.data == "map_call":
            return self._build_map_call(node)
        if node.data == "constructor":
            return self._build_constructor(node)
        if node.data == "list_literal":
            return self._build_list_literal(node)
        if node.data == "dotted_name":
            return self._build_dotted_name(node)

        raise Exception(f"Unknown expression: {node.data}")

    # -------------------------------------------------
    # instruction expressions
    # -------------------------------------------------

    def _build_llm_call(self, node: Tree) -> LLMCall:
        args = self._build_arg_list(node)
        prompt_arg = args[0] if args else None
        prompt = prompt_arg.name if isinstance(prompt_arg, Identifier) else str(prompt_arg)
        return LLMCall(prompt=prompt, args=args[1:])

    def _build_tool_call(self, node: Tree) -> ToolCall:
        args = self._build_arg_list(node)
        name_arg = args[0] if args else None
        name = name_arg.name if isinstance(name_arg, Identifier) else str(name_arg)
        return ToolCall(name=name, args=args[1:])

    def _build_verify(self, node: Tree) -> Verify:
        input_arg = self._build_arg(node.children[0])
        rule_arg = self._build_arg(node.children[1])
        return Verify(input=input_arg, rule=rule_arg)

    def _build_aggregate(self, node: Tree) -> Aggregate:
        list_node = None
        strategy = None
        for child in node.children:
            if isinstance(child, Tree) and child.data == "list_literal":
                list_node = child
            elif isinstance(child, Token):
                strategy = child.value
        inputs = self._build_list_literal(list_node).items if list_node else []
        return Aggregate(inputs=inputs, strategy=strategy)

    def _build_gate(self, node: Tree) -> Gate:
        inner = node.children[0]
        if isinstance(inner, Token):
            return Gate(input=Identifier(inner.value))
        expr = self._build_expression(inner)
        return Gate(input=expr)

    def _build_decide(self, node: Tree) -> Decide:
        args = self._build_arg_list(node)
        provider_arg = args[0] if args else None
        provider = provider_arg.name if isinstance(provider_arg, Identifier) else str(provider_arg)
        return Decide(provider=provider, args=args[1:])

    def _build_session(self, node: Tree) -> Session:
        args = self._build_arg_list(node)
        return Session(args=args)

    def _build_transform(self, node: Tree) -> Transform:
        input_arg = self._build_arg(node.children[0])
        target_type = None
        via = None

        for child in node.children:
            if isinstance(child, Tree):
                if child.data == "type_name":
                    target_type = self._build_type(child)
                elif child.data == "llm_call":
                    via = self._build_llm_call(child)
                elif child.data == "func_call":
                    via = self._build_func_call(child)

        return Transform(input=input_arg, target_type=target_type, via=via)

    def _build_func_call(self, node: Tree) -> FuncCall:
        name = self._token_value(node.children[0])
        return FuncCall(name=name)

    def _build_map_call(self, node: Tree) -> MapCall:
        collection = self._build_arg(node.children[0])
        workflow = self._token_value(node.children[1])
        concurrency = None
        on_error = None

        for child in node.children:
            if isinstance(child, Tree):
                if child.data == "map_modifiers":
                    for mod in child.iter_subtrees():
                        if mod.data == "concurrency_modifier":
                            concurrency = int(self._token_value(mod.children[0]))
                        elif mod.data == "on_error_modifier":
                            on_error = self._token_value(mod.children[0])

        return MapCall(collection=collection, workflow=workflow,
                       concurrency=concurrency, on_error=on_error)

    # -------------------------------------------------
    # constructor
    # -------------------------------------------------

    def _build_constructor(self, node: Tree) -> Constructor:
        type_name = None
        fields = {}

        for child in node.children:
            if isinstance(child, Tree):
                if child.data == "type_name":
                    type_name = self._build_type(child).name
                elif child.data == "field_list":
                    for field_node in child.children:
                        if isinstance(field_node, Tree) and field_node.data == "field":
                            key = self._token_value(field_node.children[0])
                            val = self._build_value(field_node.children[1])
                            fields[key] = val

        return Constructor(type_name=type_name, fields=fields)

    def _build_value(self, node):
        if isinstance(node, Token):
            if node.type == "STRING":
                return node.value[1:-1]  # strip quotes
            return Identifier(node.value)
        if isinstance(node, Tree):
            if node.data == "value":
                return self._build_value(node.children[0])
            if node.data == "dotted_name":
                return self._build_dotted_name(node)
            if node.data == "list_literal":
                return self._build_list_literal(node)
            if isinstance(node.children[0], Token):
                tok = node.children[0]
                if tok.type == "STRING":
                    return tok.value[1:-1]
                return Identifier(tok.value)
        return None

    # -------------------------------------------------
    # route
    # -------------------------------------------------

    def _build_route(self, node: Tree) -> Route:
        value = None
        cases = []

        for child in node.children:
            if isinstance(child, Tree):
                if child.data == "route_value":
                    value = self._build_route_value(child)
                elif child.data == "route_case":
                    cases.append(self._build_route_case(child))

        return Route(value=value, cases=cases)

    def _build_route_value(self, node: Tree):
        child = node.children[0]
        if isinstance(child, Token):
            return Identifier(child.value)
        if isinstance(child, Tree) and child.data == "dotted_name":
            return self._build_dotted_name(child)
        return Identifier(self._token_value(child))

    def _build_route_case(self, node: Tree) -> RouteCase:
        pattern_node = node.children[0]
        target_node = node.children[1]

        pattern = self._build_pattern(pattern_node)
        target = self._build_route_target(target_node)

        return RouteCase(pattern=pattern, target=target)

    def _build_route_target(self, node: Tree):
        if isinstance(node, Tree):
            if node.data == "route_target":
                return self._build_route_target(node.children[0])
            if node.data == "return_stmt":
                return self._build_return(node)
            if node.data == "node_call":
                name = self._token_value(node.children[0])
                args = self._build_arg_list(node) if len(node.children) > 1 else []
                return NodeCall(name=name, args=args)
        if isinstance(node, Token):
            return node.value
        return None

    # -------------------------------------------------
    # patterns
    # -------------------------------------------------

    def _build_pattern(self, node):
        if isinstance(node, Tree):
            if node.data == "else_pattern":
                return ElsePattern()
            if node.data == "true_pattern":
                return BoolPattern(True)
            if node.data == "false_pattern":
                return BoolPattern(False)
            if node.data == "name_pattern":
                val = self._token_value(node.children[0])
                return self._classify_name_pattern(val)
        return ElsePattern()

    def _classify_name_pattern(self, name: str):
        if name in ENUM_VALUES:
            return EnumPattern(name)
        if name in TYPE_NAMES:
            return TypePattern(name)
        # Could be an enum value we don't know about — treat as enum
        return EnumPattern(name)

    # -------------------------------------------------
    # parallel
    # -------------------------------------------------

    def _build_parallel(self, node: Tree) -> Parallel:
        partial = False
        branches = []

        for child in node.children:
            if isinstance(child, Tree):
                if child.data == "parallel_modifier":
                    partial = True
                elif child.data == "statement":
                    instr = self._build_statement(child.children[0])
                    if instr is not None:
                        branches.append(instr)

        return Parallel(branches=branches, partial=partial)

    # -------------------------------------------------
    # return
    # -------------------------------------------------

    def _build_return(self, node: Tree) -> Return:
        return Return(value=self._build_expression(node.children[0]))

    # -------------------------------------------------
    # shared: args, lists, dotted names
    # -------------------------------------------------

    def _build_arg_list(self, node: Tree) -> list:
        args = []
        for child in node.children:
            if isinstance(child, Tree) and child.data == "arg_list":
                for arg_node in child.children:
                    if isinstance(arg_node, Tree) and arg_node.data == "arg":
                        args.append(self._build_arg(arg_node))
        return args

    def _build_arg(self, node) -> "Arg":
        if isinstance(node, Token):
            return Identifier(node.value)
        if isinstance(node, Tree):
            if node.data == "arg":
                return self._build_arg(node.children[0])
            if node.data == "dotted_name":
                return self._build_dotted_name(node)
            if node.data == "list_literal":
                return self._build_list_literal(node)
            if isinstance(node.children[0], Token):
                return Identifier(node.children[0].value)
        return None

    def _build_list_literal(self, node: Tree) -> ListLiteral:
        items = []
        for child in node.children:
            if isinstance(child, Tree) and child.data == "arg_list":
                for arg_node in child.children:
                    if isinstance(arg_node, Tree) and arg_node.data == "arg":
                        items.append(self._build_arg(arg_node))
        return ListLiteral(items=items)

    def _build_dotted_name(self, node: Tree) -> DottedName:
        obj = self._token_value(node.children[0])
        attr = self._token_value(node.children[1])
        return DottedName(object=obj, attribute=attr)

    # -------------------------------------------------
    # types
    # -------------------------------------------------

    def _build_type(self, node: Tree) -> Type:
        name = node.children[0].value
        is_list = any(
            isinstance(c, Tree) and c.data == "array_suffix"
            for c in node.children[1:]
        )
        return Type(name=name, is_list=is_list)

    # -------------------------------------------------
    # helpers
    # -------------------------------------------------

    def _token_value(self, node) -> str:
        if isinstance(node, Token):
            return node.value
        if isinstance(node, Tree) and node.children:
            return self._token_value(node.children[0])
        return None
