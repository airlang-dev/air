"""Thin compile-time wrapper around runtime.asset_resolver.AssetResolver."""

from runtime.asset_resolver import AssetResolver, PromptAsset


class CompileTimeAssetResolver:
    """Wraps AssetResolver for compile-time prompt resolution."""

    def __init__(self, assets_dir: str) -> None:
        self._resolver = AssetResolver(assets_dir)

    def resolve_prompt(self, name: str) -> PromptAsset | None:
        """Resolve a prompt asset by name. Returns None if not found."""
        return self._resolver.resolve_prompt(name)
