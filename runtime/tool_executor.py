"""Tool execution for the AIR Agent VM.

Resolves and invokes deterministic tool callables. Returns Artifact or Fault.
"""


class ToolExecutor:
    """Executes tool operations by resolving named Python callables."""

    def __init__(self, asset_resolver, config):
        self._asset_resolver = asset_resolver
        self._config = config

    def execute(self, tool_name, args):
        """Resolve a tool by name and invoke it with the given args."""
        func = self._asset_resolver.resolve_tool(tool_name)
        if func is None:
            return {"type": "Fault", "message": f"Tool not found: {tool_name}"}

        try:
            return func(*args)
        except Exception as e:
            return {"type": "Fault", "message": str(e)}
