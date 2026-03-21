"""Runtime validation for AIR graphs."""


def validate_graph(graph, config):
    """Validate a graph against the provided runtime configuration constraints."""
    has_human = hasattr(config, "human_callback") and config.human_callback is not None
    if has_human:
        return

    wf_name = graph.get("workflow", "Unknown")
    for node_id, node in graph.get("nodes", {}).items():
        for op in node.get("operations", []):
            if op.get("type") == "decide":
                provider = op.get("params", {}).get("provider", "")
                if provider.startswith("human"):
                    raise RuntimeError(
                        f"Workflow '{wf_name}' requires a human_callback "
                        f"for provider '{provider}' in node '{node_id}'"
                    )
