"""Map execution for the AIR Agent VM.

Execute a sub-workflow over a collection.
"""

from concurrent.futures import ThreadPoolExecutor


class MapExecutor:
    """Executes a map operation."""

    def __init__(self, vm):
        self._vm = vm

    def execute(self, collection, workflow_name, concurrency=1, on_error="halt"):
        """Run the workflow for each item in the collection."""
        from runtime.workflow_runner import WorkflowRunner

        def _process_item(item):
            graph = self._vm.get_workflow(workflow_name)
            runner = WorkflowRunner(self._vm, graph)
            return runner.run(inputs={"item": item})

        raw_results = []
        if concurrency > 1:
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                for res in pool.map(_process_item, collection):
                    raw_results.append(res)
        else:
            for item in collection:
                res = _process_item(item)
                raw_results.append(res)
                if self._is_fault(res) and on_error == "halt":
                    return res

        results = []
        for res in raw_results:
            if self._is_fault(res):
                if on_error == "halt":
                    return res
                elif on_error == "skip":
                    continue
                elif on_error == "collect":
                    results.append(res)
            else:
                results.append(res)

        return results

    def _is_fault(self, result):
        return isinstance(result, dict) and result.get("type") == "Fault"
