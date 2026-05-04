from __future__ import annotations

from quality_core.cli.errors import QualityCliError
from quality_core.plugins.contracts import BuiltinPlugin


def list_builtin_plugins() -> list[BuiltinPlugin]:
    from quality_core.methods.registry import list_active_quality_methods

    return [method.plugin for method in list_active_quality_methods() if method.plugin is not None]


def builtin_plugins_by_id() -> dict[str, BuiltinPlugin]:
    return {plugin.plugin_id: plugin for plugin in list_builtin_plugins()}


def get_builtin_plugin(plugin_id: str) -> BuiltinPlugin:
    plugin = builtin_plugins_by_id().get(plugin_id)
    if plugin is None:
        raise QualityCliError(
            code="PLUGIN_NOT_FOUND",
            message=f"Built-in plugin '{plugin_id}' was not found.",
            target={"pluginId": plugin_id},
            suggestion="Run `quality plugin list` to see available built-in plugins.",
        )
    return plugin
