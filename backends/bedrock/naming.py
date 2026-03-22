"""Node and connection name generation for Bedrock Flow.

Bedrock name regex: ^[a-zA-Z]([_]?[0-9a-zA-Z]){1,50}$
"""

import re


class NodeNamer:
    """Generates unique Bedrock-compliant node and connection names."""

    def __init__(self) -> None:
        self._used: set[str] = set()

    def node_name(self, air_node_name: str, suffix: str = "") -> str:
        """Produce a unique, regex-compliant Bedrock node name."""
        base = self.sanitize(air_node_name)
        if suffix:
            candidate = self.sanitize(base + "_" + suffix.lstrip("_"))
        else:
            candidate = base
        return self._unique(candidate)

    def connection_name(self, source: str, target: str) -> str:
        """Produce a unique connection name from source+target node names."""
        candidate = self.sanitize(source + "_to_" + target)
        return self._unique(candidate)

    def sanitize(self, name: str) -> str:
        """Replace invalid chars, ensure starts with letter, truncate to 51 chars."""
        # Replace any non-alphanumeric (except underscore) with underscore
        s = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        # Collapse consecutive underscores
        s = re.sub(r"_+", "_", s)
        # Strip leading/trailing underscores
        s = s.strip("_")
        # Ensure starts with a letter
        if not s or not s[0].isalpha():
            s = "N" + s
        # Truncate: first char + up to 50 more = 51 total
        s = s[:51]
        # Remove trailing underscore after truncation
        s = s.rstrip("_")
        if not s:
            s = "Node"
        return s

    def _unique(self, candidate: str) -> str:
        """Append integer counter if name already used."""
        if candidate not in self._used:
            self._used.add(candidate)
            return candidate
        counter = 2
        while True:
            suffixed = self.sanitize(candidate[:47]) + f"_{counter}"
            if suffixed not in self._used:
                self._used.add(suffixed)
                return suffixed
            counter += 1
