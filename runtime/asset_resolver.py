"""Asset resolution for the AIR Agent VM.

Resolves asset names (prompts, rules, schemas) to their content
from a project's assets directory.
"""

import os
from dataclasses import dataclass

import yaml


@dataclass
class PromptAsset:
    """A resolved prompt asset with template text and optional model binding."""

    template: str
    model: str | None = None


class AssetResolver:
    """Resolves asset names to content from a project directory."""

    def __init__(self, base_dir):
        self._base_dir = base_dir

    def resolve_prompt(self, name):
        """Resolve a prompt name to a PromptAsset.

        Looks for prompts/{name}.yaml (structured) or prompts/{name}.md (plain).
        """
        prompts_dir = os.path.join(self._base_dir, "prompts")

        yaml_path = os.path.join(prompts_dir, f"{name}.yaml")
        if os.path.exists(yaml_path):
            return self._load_yaml_prompt(yaml_path)

        md_path = os.path.join(prompts_dir, f"{name}.md")
        if os.path.exists(md_path):
            return self._load_plain_prompt(md_path)

        return None

    def resolve_rule(self, name):
        """Resolve a rule name to content. Not implemented in Phase 1."""
        raise NotImplementedError("Rule resolution is not yet implemented")

    def _load_yaml_prompt(self, path):
        with open(path) as f:
            data = yaml.safe_load(f)
        return PromptAsset(
            template=data.get("template", ""),
            model=data.get("model"),
        )

    def _load_plain_prompt(self, path):
        with open(path) as f:
            template = f.read()
        return PromptAsset(template=template)
