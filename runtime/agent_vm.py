"""AIR Agent VM

Loads and executes AIR Graph (.airc) workflows."""

import json
import os

from runtime.asset_resolver import AssetResolver
from runtime.config import RuntimeConfig
from runtime.workflow_runner import WorkflowRunner


class AgentVM:
    """The long-lived virtual machine environment for executing workflows."""

    def __init__(self, graph=None, asset_resolver=None, config=None):
        self._default_graph = graph
        self.asset_resolver = asset_resolver or AssetResolver(".")
        self.config = config or RuntimeConfig()
        self._cache = {}

    @property
    def _graph(self):
        return self._default_graph

    @property
    def _nodes(self):
        return self._default_graph.get("nodes", {}) if self._default_graph else {}

    @classmethod
    def load(cls, path, asset_resolver=None, config=None):
        """Initialize an AgentVM instance from a compiled workflow."""
        if asset_resolver is None:
            airc_dir = os.path.dirname(os.path.abspath(path))
            asset_resolver = AssetResolver(airc_dir)

        with open(path) as f:
            graph = json.load(f)

        vm = cls(graph, asset_resolver, config)
        vm._cache[path] = graph
        return vm

    def run_workflow(self, workflow_name, inputs=None):
        """Execute a named sub-workflow."""
        path = os.path.join(self.asset_resolver._base_dir, f"{workflow_name}.airc")
        if path not in self._cache:
            with open(path) as f:
                self._cache[path] = json.load(f)

        graph = self._cache[path]
        runner = WorkflowRunner(self, graph)
        return runner.run(inputs)

    def run(self, inputs=None):
        """Execute the primary workflow."""
        if not self._default_graph:
            raise RuntimeError("AgentVM was not initialized with a default graph.")
        runner = WorkflowRunner(self, self._default_graph)
        return runner.run(inputs)
