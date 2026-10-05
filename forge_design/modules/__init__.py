"""Contrat des modules spécialisés externes (FD-MODULES-001).

Descripteur déclaratif et activation explicite, sans découverte ni câblage Web :
l'hôte (routes /modules/<id>/, assets, pages) viendra avec FD-MODULES-002.
Voir docs/modules/module-architecture.md. Ce paquet n'importe aucun module
spécialisé : il ne connaît que ceux qu'on lui nomme.

FD-EDIT-001 : actions bornées (ModuleAction et son payload), seule API qu'un
module importe pour déclarer une mutation ; voir docs/modules/module-actions.md.
"""

from forge_design.modules.actions import (
    MAX_MODULE_ACTION_BYTES,
    MAX_MODULE_ACTION_FIELDS,
    MAX_MODULE_ACTION_KEY_CHARS,
    MAX_MODULE_ACTION_TEXT_CHARS,
    MAX_MODULE_ACTIONS,
    MAX_SAFE_INTEGER,
    RESERVED_ACTION_FIELDS,
    ActionHandler,
    ModuleAction,
    ModuleActionPayload,
    ModuleActionPayloadError,
    ModuleActionRefused,
    ModuleActionResult,
)
from forge_design.modules.activation import (
    DESCRIPTOR_ATTRIBUTE,
    ActiveModule,
    ModuleActivation,
    ModuleDiagnostic,
    activate_modules,
)
from forge_design.modules.descriptor import (
    ASSET_MEDIA_TYPES,
    MODULE_API_VERSION,
    MODULE_URL_PREFIX,
    SUPPORTED_MODULE_API_VERSIONS,
    ModuleAsset,
    ModuleDescriptor,
    ResourceBinding,
)

__all__ = [
    "ASSET_MEDIA_TYPES",
    "DESCRIPTOR_ATTRIBUTE",
    "MAX_MODULE_ACTIONS",
    "MAX_MODULE_ACTION_BYTES",
    "MAX_MODULE_ACTION_FIELDS",
    "MAX_MODULE_ACTION_KEY_CHARS",
    "MAX_MODULE_ACTION_TEXT_CHARS",
    "MAX_SAFE_INTEGER",
    "MODULE_API_VERSION",
    "MODULE_URL_PREFIX",
    "RESERVED_ACTION_FIELDS",
    "SUPPORTED_MODULE_API_VERSIONS",
    "ActionHandler",
    "ActiveModule",
    "ModuleAction",
    "ModuleActionPayload",
    "ModuleActionPayloadError",
    "ModuleActionRefused",
    "ModuleActionResult",
    "ModuleActivation",
    "ModuleAsset",
    "ModuleDescriptor",
    "ModuleDiagnostic",
    "ResourceBinding",
    "activate_modules",
]
