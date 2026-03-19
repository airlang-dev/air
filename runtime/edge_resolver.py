"""EdgeResolver — resolves which edge to follow in an AIR Graph node."""


class EdgeResolver:
    """Resolves the target node from a list of conditional edges."""

    @staticmethod
    def resolve(value, edges):
        """Return (target, matched) for the first matching edge."""
        target = None
        matched = None

        for edge in edges:
            cond = edge.get("condition")
            if cond is None:
                return edge["target"], "unconditional"

            kind = cond["kind"]

            if kind == "enum" and cond.get("value") == value:
                return edge["target"], cond["value"]

            if kind == "bool":
                bool_val = (
                    bool(value) if cond["value"] == "true" else not bool(value)
                )
                if bool_val:
                    return edge["target"], cond["value"]

            if kind == "type":
                is_list = cond.get("is_list", False)
                if is_list and isinstance(value, list):
                    return edge["target"], f"{cond['name']}[]"
                elif not is_list and not isinstance(value, list):
                    return edge["target"], cond.get("name", "type")

        # "else" fallback
        for edge in edges:
            cond = edge.get("condition")
            if cond and cond["kind"] == "else":
                return edge["target"], "else"

        raise RuntimeError(f"no matching edge for value {value!r}")
