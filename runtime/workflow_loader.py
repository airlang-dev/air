"""Workflow loader for the AIR Agent VM."""

import json
import os

from runtime.validator import validate_graph


class WorkflowLoader:
    """Loads and recursively validates workflow dependencies into a cache."""

    def __init__(self, asset_resolver, config):
        self._asset_resolver = asset_resolver
        self._config = config

    def build(self, graph_or_path):
        """Builds and returns a validated root graph and a populated cache dictionary."""
        cache = {}
        if isinstance(graph_or_path, dict):
            graph = graph_or_path
            self._airc_dir = None
        else:
            file_path = str(graph_or_path)
            self._airc_dir = os.path.dirname(os.path.abspath(file_path))
            graph = self._read_file(path=file_path)

        wf_name = graph.get("workflow", "Unnamed")
        cache[wf_name] = graph
        self._load_dependencies(graph, cache)
        return graph, cache

    def _read_file(self, workflow_name=None, path=None):
        if not path and not workflow_name:
            raise ValueError("Must provide either an absolute path or a workflow_name")

        if path:
            if not os.path.exists(path):
                raise RuntimeError(f"Workflow file not found: {path}")
        else:
            if self._airc_dir:
                path = os.path.join(self._airc_dir, f"{workflow_name}.airc")
            if not path or not os.path.exists(path):
                path = os.path.join(self._asset_resolver._base_dir, f"{workflow_name}.airc")
            if not os.path.exists(path):
                return None

        with open(path) as f:
            return json.load(f)

    def _load_dependencies(self, graph, cache, visited=None):
        visited = visited or set()
        wf_name = graph.get("workflow", "Unknown")

        if wf_name in visited:
            return
        visited.add(wf_name)

        validate_graph(graph, self._config)

        for dep_name in self._extract_dependencies(graph):
            if dep_name in cache:
                continue

            sub_graph = self._read_file(workflow_name=dep_name)
            if sub_graph:
                cache[dep_name] = sub_graph
                self._load_dependencies(sub_graph, cache, visited)

    def _extract_dependencies(self, graph):
        for node in graph.get("nodes", {}).values():
            for op in node.get("operations", []):
                if op.get("type") == "map":
                    sub = op.get("params", {}).get("workflow")
                    if sub:
                        yield sub
