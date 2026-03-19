"""Runtime configuration for AIR Agent VM."""

import os
from dataclasses import dataclass, field

import yaml


DEFAULT_MODEL = "claude-sonnet-4-20250514"
CONFIG_FILENAME = "air.config.yaml"


@dataclass
class RuntimeConfig:
    """Runtime settings for the AIR Agent VM."""

    default_model: str = DEFAULT_MODEL
    assets_dir: str = "assets"

    @classmethod
    def from_file(cls, path):
        """Load config from a YAML file. Returns defaults if file doesn't exist."""
        if not os.path.exists(path):
            return cls()
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls(
            default_model=data.get("default_model", DEFAULT_MODEL),
            assets_dir=data.get("assets_dir", "assets"),
        )
