class Backend:
    """Base interface for EGIR execution backends.

    Backends consume a serialized EGIR artifact (dict) and produce
    execution results. All backends must implement the compile method.
    """

    def compile(self, egir: dict):
        raise NotImplementedError
