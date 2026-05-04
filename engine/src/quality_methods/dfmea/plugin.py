from __future__ import annotations

from importlib.resources import files

from quality_core.plugins.contracts import (
    BuiltinPlugin,
    PluginCollection,
    PluginSingleton,
)

PLUGIN_ID = "dfmea"
PLUGIN_VERSION = "dfmea.ai/v1"
DOMAIN_KEY = "dfmea"
DOMAIN_ROOT = "dfmea"


def get_plugin() -> BuiltinPlugin:
    return BuiltinPlugin(
        plugin_id=PLUGIN_ID,
        version=PLUGIN_VERSION,
        domain_key=DOMAIN_KEY,
        domain_root=DOMAIN_ROOT,
        snapshot_root=files("quality_methods.dfmea").joinpath("schemas"),
        singletons=(
            PluginSingleton(
                kind="DfmeaAnalysis",
                resource_id="DFMEA",
                file="dfmea.yaml",
                schema="dfmea-analysis.schema.json",
            ),
        ),
        collections=(
            PluginCollection(
                kind="StructureNode",
                directory="structure",
                file_name="{id}.yaml",
                id_prefix="SYS|SUB|COMP",
                schema="structure-node.schema.json",
                title_field="metadata.title",
            ),
            PluginCollection(
                kind="Function",
                directory="functions",
                file_name="{id}.yaml",
                id_prefix="FN",
                schema="function.schema.json",
                title_field="metadata.title",
            ),
            PluginCollection(
                kind="Requirement",
                directory="requirements",
                file_name="{id}.yaml",
                id_prefix="REQ",
                schema="requirement.schema.json",
                title_field="metadata.title",
            ),
            PluginCollection(
                kind="Characteristic",
                directory="characteristics",
                file_name="{id}.yaml",
                id_prefix="CHAR",
                schema="characteristic.schema.json",
                title_field="metadata.title",
            ),
            PluginCollection(
                kind="FailureMode",
                directory="failure-modes",
                file_name="{id}.yaml",
                id_prefix="FM",
                schema="failure-mode.schema.json",
                title_field="metadata.title",
            ),
            PluginCollection(
                kind="FailureEffect",
                directory="effects",
                file_name="{id}.yaml",
                id_prefix="FE",
                schema="failure-effect.schema.json",
                title_field="metadata.title",
            ),
            PluginCollection(
                kind="FailureCause",
                directory="causes",
                file_name="{id}.yaml",
                id_prefix="FC",
                schema="failure-cause.schema.json",
                title_field="metadata.title",
            ),
            PluginCollection(
                kind="Action",
                directory="actions",
                file_name="{id}.yaml",
                id_prefix="ACT",
                schema="action.schema.json",
                title_field="spec.description",
            ),
        ),
    )
