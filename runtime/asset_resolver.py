"""Asset resolution for the AIR Agent VM.

Resolves asset names (prompts, rules, schemas) to their content
from a project's assets directory.
"""

import importlib.util
import os
from dataclasses import dataclass

import yaml


@dataclass
class PromptAsset:
    """A resolved prompt asset with template text and optional model binding."""

    template: str
    model: str | None = None


@dataclass
class RuleAsset:
    """A resolved rule asset with template text and optional model binding."""

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

    def resolve_func(self, name):
        """Resolve a function name to a callable.

        Looks for functions/{name}.py and returns the callable named {name},
        or None if not found.
        """
        func_path = os.path.join(self._base_dir, "functions", f"{name}.py")
        if not os.path.exists(func_path):
            return None

        spec = importlib.util.spec_from_file_location(name, func_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        return getattr(module, name, None)

    def resolve_rule(self, name):
        """Resolve a rule name to a RuleAsset.

        Looks for rules/{name}.yaml (structured) or rules/{name}.md (plain).
        """
        rules_dir = os.path.join(self._base_dir, "rules")

        yaml_path = os.path.join(rules_dir, f"{name}.yaml")
        if os.path.exists(yaml_path):
            return self._load_yaml_rule(yaml_path)

        md_path = os.path.join(rules_dir, f"{name}.md")
        if os.path.exists(md_path):
            return self._load_plain_rule(md_path)

        return None

    def resolve_protocol(self, name):
        """Resolve a protocol name to a dictionary.

        Looks for protocols/{name}.yaml.
        """
        protocol_path = os.path.join(self._base_dir, "protocols", f"{name}.yaml")
        if os.path.exists(protocol_path):
            with open(protocol_path) as f:
                return yaml.safe_load(f)
        return None

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

    def _load_yaml_rule(self, path):
        with open(path) as f:
            data = yaml.safe_load(f)
        return RuleAsset(
            template=data.get("template", ""),
            model=data.get("model"),
        )

    def _load_plain_rule(self, path):
        with open(path) as f:
            template = f.read()
        return RuleAsset(template=template)
