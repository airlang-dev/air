class Backend:
    """Base interface for AIR Graph execution backends.

    Backends consume a serialized AIR Graph artifact (dict) and produce
    execution results. All backends must implement the compile method.
    """

    def compile(self, air_graph: dict, output_path: str = None) -> str:
        """Compile air_graph and write to output_path. Returns the path written."""
        raise NotImplementedError
