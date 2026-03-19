"""VariableScope — manages workflow variables for the AIR Agent VM."""


class VariableScope:
    """Holds workflow variables and resolves them by name."""

    def __init__(self, variables=None):
        self._vars = dict(variables) if variables else {}

    def resolve(self, name):
        """Resolve a variable name, supporting dotted notation."""
        if "." in name:
            parts = name.split(".", 1)
            obj = self._vars[parts[0]]
            if isinstance(obj, dict):
                return obj[parts[1]]
            return getattr(obj, parts[1])
        return self._vars[name]

    def get(self, name):
        """Get a variable value, falling back to the name itself."""
        return self._vars.get(name, name)

    def store(self, out_names, value):
        """Store a value into one or more output variables."""
        if not out_names:
            return
        if isinstance(value, tuple):
            for i, v in enumerate(value):
                if i < len(out_names):
                    self._vars[out_names[i]] = v
        else:
            self._vars[out_names[0]] = value
