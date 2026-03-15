"""Semantic checker for AIR v0.2 AST.

Validates:
1. Node name uniqueness within a workflow
2. Node names don't collide with instruction keywords
3. SSA (no variable reassignment within a node)
4. Variable existence (workflow params, node params, local assignments)
5. Route target existence (must reference valid node names)
6. Route exhaustiveness (Outcome routes need full coverage or else)
7. At most one fallback node per workflow
8. Return type validity (constructor type must be in workflow return types)
9. Every node must terminate (return, node_call, route, or unreachable)
"""

from air_ast import (
    Aggregate, Assign, Constructor, Decide, DottedName, ElsePattern,
    EnumPattern, FuncCall, Gate, Identifier, LLMCall, ListLiteral,
    MapCall, Node, NodeCall, Parallel, Program, Return, Route,
    RouteCase, Session, ToolCall, Transform, Unreachable, Verify,
    Workflow,
)

OUTCOME_VALUES = {"PROCEED", "RETRY", "ESCALATE", "HALT"}

RESERVED_KEYWORDS = {
    "llm", "tool", "transform", "verify", "aggregate",
    "gate", "decide", "session", "map", "func",
    "route", "return", "unreachable", "parallel",
}

VALID_ON_ERROR = {"halt", "skip", "collect"}


class SemanticError(Exception):
    pass


def check_program(program: Program):
    """Run all semantic checks on a program."""
    workflow_names = {w.name for w in program.workflows}
    for workflow in program.workflows:
        _check_workflow(workflow, workflow_names)


def _check_workflow(workflow: Workflow, workflow_names: set):
    node_names = set()
    fallback_count = 0
    return_type_names = {t.name for t in workflow.return_types}

    # Workflow param names are visible to all nodes
    workflow_params = {p.name for p in workflow.params}

    # 1. Node name uniqueness + keyword check
    for node in workflow.nodes:
        if node.name in node_names:
            raise SemanticError(
                f"Duplicate node name '{node.name}' in workflow '{workflow.name}'"
            )
        node_names.add(node.name)

        if node.name in RESERVED_KEYWORDS:
            raise SemanticError(
                f"Node name '{node.name}' is a reserved keyword"
            )

        if node.is_fallback:
            fallback_count += 1

    # 7. At most one fallback
    if fallback_count > 1:
        raise SemanticError(
            f"Multiple fallback nodes in workflow '{workflow.name}'"
        )

    # Per-node checks
    for node in workflow.nodes:
        _check_node(node, node_names, workflow_params, return_type_names,
                     workflow_names)


def _check_node(node: Node, node_names: set, workflow_params: set,
                return_type_names: set, workflow_names: set):
    # Variables in scope: workflow params + node params
    defined = set(workflow_params) | set(node.params)

    # Walk body statements
    for stmt in node.body:
        _check_statement(stmt, defined, node_names, return_type_names,
                         workflow_names)

    # 9. Termination check
    if not _terminates(node.body):
        raise SemanticError(
            f"Node '{node.name}' does not terminate "
            f"(must end with return, route, node call, or unreachable)"
        )


def _check_statement(stmt, defined: set, node_names: set,
                     return_type_names: set, workflow_names: set):
    if isinstance(stmt, Assign):
        # Check RHS references first
        _check_expression_refs(stmt.value, defined, workflow_names)
        # Then define LHS (SSA check)
        for target in stmt.targets:
            if target != "_":
                if target in defined:
                    raise SemanticError(
                        f"SSA violation: variable '{target}' assigned twice"
                    )
                defined.add(target)

    elif isinstance(stmt, Return):
        _check_expression_refs(stmt.value, defined, workflow_names)
        # 8. Return type validity
        if isinstance(stmt.value, Constructor):
            if stmt.value.type_name not in return_type_names:
                raise SemanticError(
                    f"Return type '{stmt.value.type_name}' not declared "
                    f"in workflow return types"
                )

    elif isinstance(stmt, Route):
        _check_route(stmt, defined, node_names)

    elif isinstance(stmt, NodeCall):
        # Check args reference defined variables
        _check_args_refs(stmt.args, defined)
        # 5. Target must be a known node
        if stmt.name not in node_names:
            raise SemanticError(
                f"Unknown node '{stmt.name}' in node call"
            )

    elif isinstance(stmt, Parallel):
        _check_parallel(stmt, defined, node_names, return_type_names,
                         workflow_names)

    elif isinstance(stmt, Unreachable):
        pass

    # Bare instruction calls (tool, llm, session without assignment)
    elif isinstance(stmt, (ToolCall, LLMCall, Session)):
        _check_expression_refs(stmt, defined, workflow_names)


def _check_parallel(parallel: Parallel, defined: set, node_names: set,
                    return_type_names: set, workflow_names: set):
    # Variables defined in parallel branches all merge into the outer scope.
    # But within the parallel block, SSA still applies — no two branches
    # can define the same variable.
    parallel_defined = set()
    for branch in parallel.branches:
        branch_defined = set(defined)
        _check_statement(branch, branch_defined, node_names,
                         return_type_names, workflow_names)
        # Collect newly defined variables
        new_vars = branch_defined - defined
        for var in new_vars:
            if var in parallel_defined:
                raise SemanticError(
                    f"SSA violation: variable '{var}' assigned in "
                    f"multiple parallel branches"
                )
            parallel_defined.add(var)
    # Merge parallel-defined variables into outer scope
    defined.update(parallel_defined)


def _check_route(route: Route, defined: set, node_names: set):
    # Check route value is defined
    _check_arg_ref(route.value, defined)

    patterns = set()
    has_else = False

    for case in route.cases:
        # Collect patterns for exhaustiveness
        if isinstance(case.pattern, ElsePattern):
            has_else = True
        elif isinstance(case.pattern, EnumPattern):
            patterns.add(case.pattern.value)

        # Check target
        target = case.target
        if isinstance(target, str):
            if target not in node_names:
                raise SemanticError(
                    f"Unknown node '{target}' in route target"
                )
        elif isinstance(target, NodeCall):
            if target.name not in node_names:
                raise SemanticError(
                    f"Unknown node '{target.name}' in route target"
                )
            _check_args_refs(target.args, defined)
        elif isinstance(target, Return):
            _check_expression_refs(target.value, defined)

    # 6. Route exhaustiveness for Outcome routes
    if patterns.intersection(OUTCOME_VALUES):
        if not has_else:
            missing = OUTCOME_VALUES - patterns
            if missing:
                raise SemanticError(
                    f"Incomplete outcome route: missing {missing}"
                )


def _check_expression_refs(expr, defined: set, workflow_names: set = None):
    """Check that all variable references in an expression are defined."""
    if isinstance(expr, Identifier):
        _check_var_ref(expr.name, defined)
    elif isinstance(expr, DottedName):
        _check_var_ref(expr.object, defined)
    elif isinstance(expr, ListLiteral):
        for item in expr.items:
            _check_arg_ref(item, defined)
    elif isinstance(expr, LLMCall):
        # prompt is an asset name, not a variable — don't check it
        for arg in expr.args:
            _check_arg_ref(arg, defined)
    elif isinstance(expr, ToolCall):
        # tool name is an asset name — don't check it
        for arg in expr.args:
            _check_arg_ref(arg, defined)
    elif isinstance(expr, Verify):
        _check_arg_ref(expr.input, defined)
        # rule is an asset name — don't check it
    elif isinstance(expr, Aggregate):
        for inp in expr.inputs:
            _check_arg_ref(inp, defined)
    elif isinstance(expr, Gate):
        _check_expression_refs(expr.input, defined, workflow_names)
    elif isinstance(expr, Decide):
        # provider is an asset name — don't check it
        for arg in expr.args:
            _check_arg_ref(arg, defined)
    elif isinstance(expr, Session):
        for arg in expr.args:
            _check_arg_ref(arg, defined)
    elif isinstance(expr, Transform):
        _check_arg_ref(expr.input, defined)
        if expr.via and isinstance(expr.via, LLMCall):
            _check_expression_refs(expr.via, defined, workflow_names)
        # FuncCall: func name is an asset ref — don't check it
    elif isinstance(expr, MapCall):
        _check_arg_ref(expr.collection, defined)
        # Validate workflow reference against same-file workflows
        if workflow_names is not None and expr.workflow not in workflow_names:
            raise SemanticError(
                f"Unknown workflow '{expr.workflow}' in map"
            )
        # Validate on_error value
        if expr.on_error is not None and expr.on_error not in VALID_ON_ERROR:
            raise SemanticError(
                f"Invalid on_error value '{expr.on_error}' in map "
                f"(must be one of: {', '.join(sorted(VALID_ON_ERROR))})"
            )
    elif isinstance(expr, Constructor):
        for val in expr.fields.values():
            if isinstance(val, Identifier):
                _check_var_ref(val.name, defined)
            elif isinstance(val, DottedName):
                _check_var_ref(val.object, defined)
            # string literals are fine


def _check_arg_ref(arg, defined: set):
    """Check a single argument reference."""
    if isinstance(arg, Identifier):
        _check_var_ref(arg.name, defined)
    elif isinstance(arg, DottedName):
        _check_var_ref(arg.object, defined)
    elif isinstance(arg, ListLiteral):
        for item in arg.items:
            _check_arg_ref(item, defined)


def _check_args_refs(args: list, defined: set):
    for arg in args:
        _check_arg_ref(arg, defined)


def _check_var_ref(name: str, defined: set):
    """Check that a variable name is defined, ignoring type names and assets."""
    # Type names (used in constructors, dotted access like Fault.reason)
    # and asset names (prompts, rules, providers) don't need to be defined
    # as variables. We use a simple heuristic: uppercase first letter = type/asset.
    if name[0].isupper():
        return
    if name == "_":
        return
    if name not in defined:
        raise SemanticError(f"Undefined variable '{name}'")


def _terminates(body: list) -> bool:
    """Check if a node body terminates (last statement is a terminator)."""
    if not body:
        return False

    last = body[-1]
    if isinstance(last, (Return, Route, NodeCall, Unreachable)):
        return True
    # Bare instruction calls (tool, llm, session) don't terminate
    return False
