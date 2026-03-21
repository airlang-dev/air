"""Tests for RuntimeConfig."""

import os
from pathlib import Path

from runtime.config import RuntimeConfig, DEFAULT_MODEL

ASSETS_DIR = Path(__file__).resolve().parent / "fixtures" / "assets"


class TestRuntimeConfig:

    def test_defaults_when_no_file(self, tmp_path):
        config = RuntimeConfig.from_file(tmp_path / "nonexistent.yaml")
        assert config.default_model == DEFAULT_MODEL
        assert config.assets_dir == "assets"

    def test_load_from_file(self, tmp_path):
        config_path = tmp_path / "air.config.yaml"
        config_path.write_text("default_model: gpt-4o\nassets_dir: my_assets\n")
        config = RuntimeConfig.from_file(config_path)
        assert config.default_model == "gpt-4o"
        assert config.assets_dir == "my_assets"
