"""AIR parser factory with indentation support."""

from pathlib import Path

from lark import Lark, Token
from lark.indenter import Indenter

GRAMMAR_PATH = Path(__file__).resolve().parent.parent / "spec" / "v0.2" / "air.lark"


class AirIndenter(Indenter):
    """Custom indenter that emits DEDENT before NL.

    The default Indenter emits NL then DEDENT. This causes inner blocks
    to consume the NL, leaving no separator at the outer level. By
    emitting DEDENT before NL, the NL remains available at the outer
    level as a statement/node separator.

    Order:
      INDENT:     NL then INDENT  (NL enters the block)
      same-level: NL only
      DEDENT:     DEDENT(s) then NL  (NL available at outer level)
    """

    NL_type = "_NL"
    OPEN_PAREN_types = []
    CLOSE_PAREN_types = []
    INDENT_type = "_INDENT"
    DEDENT_type = "_DEDENT"
    tab_len = 4

    def handle_NL(self, token):
        if self.paren_level > 0:
            return

        indent_str = token.rsplit("\n", 1)[1]
        indent = indent_str.count(" ") + indent_str.count("\t") * self.tab_len

        if indent > self.indent_level[-1]:
            self.indent_level.append(indent)
            yield token
            yield Token.new_borrow_pos(self.INDENT_type, indent_str, token)
        elif indent < self.indent_level[-1]:
            while indent < self.indent_level[-1]:
                self.indent_level.pop()
                yield Token.new_borrow_pos(self.DEDENT_type, indent_str, token)
            if indent != self.indent_level[-1]:
                from lark.indenter import DedentError

                raise DedentError(
                    "Unexpected dedent to column %s. Expected dedent to %s"
                    % (indent, self.indent_level[-1])
                )
            yield token
        else:
            yield token


def create_parser() -> Lark:
    grammar = GRAMMAR_PATH.read_text()
    return Lark(grammar, postlex=AirIndenter())
