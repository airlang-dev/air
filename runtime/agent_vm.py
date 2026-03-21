"""AIR Agent VM

Loads and executes AIR Graph (.airc) workflows."""

import os

from runtime.asset_resolver import AssetResolver
from runtime.config import RuntimeConfig
from runtime.workflow_loader import WorkflowLoader
from runtime.workflow_runner import WorkflowRunner


class AgentVM:
    """The long-lived virtual machine environment for executing workflows."""

    def __init__(self, asset_resolver=None, config=None):
        self.asset_resolver = asset_resolver or AssetResolver(".")
        self.config = config or RuntimeConfig()
        self._default_graph = None
        self._cache = {}

    @property
    def workflow_name(self):
        return (
            self._default_graph.get("workflow", "Unknown")
            if self._default_graph
            else "None"
        )

    def load(self, workflow_source):
        """Load and build the runtime workflow graph.

        Args:
            workflow_source: A compiled workflow string path OR a raw dictionary.
        """
        loader = WorkflowLoader(self.asset_resolver, self.config)
        self._default_graph, self._cache = loader.build(workflow_source)

    def get_workflow(self, name):
        """Retrieve a fully loaded and validated sub-workflow from cache."""
        if name not in self._cache:
            raise RuntimeError(
                f"Workflow '{name}' not found. Was it referenced statically?"
            )
        return self._cache[name]

    def run(self, inputs=None):
        """Execute the primary workflow."""
        if not self._default_graph:
            raise RuntimeError("AgentVM was not initialized with a default graph.")
        runner = WorkflowRunner(self, self._default_graph)
        return runner.run(inputs)
