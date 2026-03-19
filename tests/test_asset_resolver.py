"""Tests for the AssetResolver."""

from pathlib import Path

import pytest

from runtime.asset_resolver import AssetResolver

ASSETS_DIR = Path(__file__).resolve().parent / "fixtures" / "assets"


@pytest.fixture
def resolver():
    return AssetResolver(ASSETS_DIR)


class TestResolvePrompt:

    def test_plain_markdown_prompt(self, resolver):
        asset = resolver.resolve_prompt("summarize")
        assert asset is not None
        assert "Summarize" in asset.template
        assert asset.model is None

    def test_yaml_prompt_with_model(self, resolver):
        asset = resolver.resolve_prompt("extract_claims")
        assert asset is not None
        assert "Extract all factual claims" in asset.template
        assert asset.model == "claude-sonnet-4-20250514"

    def test_unknown_prompt_returns_none(self, resolver):
        asset = resolver.resolve_prompt("nonexistent")
        assert asset is None

    def test_resolve_rule_not_implemented(self, resolver):
        with pytest.raises(NotImplementedError):
            resolver.resolve_rule("some_rule")


class TestResolveFunc:

    def test_resolves_function_from_file(self, resolver):
        """Resolves functions/{name}.py and returns the callable."""
        func = resolver.resolve_func("extract_features")
        assert callable(func)
        result = func("hello world")
        assert result["word_count"] == 2

    def test_unknown_function_returns_none(self, resolver):
        """Returns None for a function that doesn't exist."""
        func = resolver.resolve_func("nonexistent_func")
        assert func is None
