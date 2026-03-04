from lark import Tree, Token

OUTCOME_VALUES = {"PROCEED", "RETRY", "ESCALATE", "HALT"}


class SemanticChecker:

    def __init__(self, tree):
        self.tree = tree
        self.labels = set()
        self.variables = set()

    # --------------------------------
    # entry point
    # --------------------------------

    def run(self):
        self.collect_labels(self.tree)
        self.check_nodes(self.tree)

    # --------------------------------
    # utilities
    # --------------------------------

    def get_identifier(self, node):
        if isinstance(node, Token):
            return node.value
        if isinstance(node, Tree) and node.children:
            return self.get_identifier(node.children[0])
        return None

    def is_variable(self, name):
        return name in self.variables

    # --------------------------------
    # label collection
    # --------------------------------

    def collect_labels(self, node):

        if isinstance(node, Tree):

            if node.data == "block_label":
                label = self.get_identifier(node.children[0])
                if label:
                    self.labels.add(label)

            for child in node.children:
                self.collect_labels(child)

    # --------------------------------
    # recursive checks
    # --------------------------------

    def check_nodes(self, node):

        if isinstance(node, Tree):

            if node.data == "assignment":
                self.check_assignment(node)

            elif node.data == "route_stmt":
                self.check_route(node)

            elif node.data in {
                "llm_call",
                "verify_call",
                "gate_call",
                "aggregate_call",
                "decide_call",
                "transform_expr",
                "tool_call",
            }:
                self.check_expression_inputs(node)

            for child in node.children:
                self.check_nodes(child)

    # --------------------------------
    # SSA validation
    # --------------------------------

    def check_assignment(self, node):

        lvalue = node.children[0]

        if isinstance(lvalue, Tree):

            for child in lvalue.children:

                name = self.get_identifier(child)

                if name and name != "_":

                    if name in self.variables:
                        raise Exception(
                            f"SSA violation: variable '{name}' assigned twice"
                        )

                    self.variables.add(name)

    # --------------------------------
    # route validation
    # --------------------------------

    def check_route(self, node):

        patterns = set()

        for child in node.children:

            if not isinstance(child, Tree):
                continue

            if child.data != "route_case":
                continue

            pattern_node = child.children[0]
            target_node = child.children[1]

            pattern = self.get_identifier(pattern_node)
            target = self.get_identifier(target_node)

            if pattern:
                patterns.add(pattern)

            if target and target != "continue" and target not in self.labels:
                raise Exception(f"Unknown label '{target}' in route")

        # check outcome coverage
        if patterns.intersection(OUTCOME_VALUES):

            if "default" not in patterns:

                missing = OUTCOME_VALUES - patterns

                if missing:
                    raise Exception(f"Incomplete outcome route: missing {missing}")

    # --------------------------------
    # variable existence checks
    # --------------------------------

    def require_variable(self, name):
        if name and name not in self.variables:
            raise Exception(f"Unknown variable '{name}'")

    def check_expression_inputs(self, node):

        if node.data == "verify_call":

            # verify(variable, rule)
            var = self.get_identifier(node.children[0])
            self.require_variable(var)

        elif node.data == "transform_expr":

            # transform(variable, Type)
            var = self.get_identifier(node.children[0])
            self.require_variable(var)

        elif node.data == "gate_call":

            # gate(variable)
            var = self.get_identifier(node.children[0])
            self.require_variable(var)

        elif node.data == "aggregate_call":

            # aggregate([v1,v2,v3], strategy)
            list_node = node.children[0]

            for child in list_node.children:
                var = self.get_identifier(child)
                self.require_variable(var)

        elif node.data == "decide_call":

            # decide(provider, variable?)
            if len(node.children) > 1:
                var = self.get_identifier(node.children[1])
                self.require_variable(var)

        elif node.data == "tool_call":

            # tool(name, variable...)
            for child in node.children[1:]:
                var = self.get_identifier(child)
                self.require_variable(var)

        # llm_call intentionally ignored
