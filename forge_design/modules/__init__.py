"""Contrat des modules spécialisés externes (FD-MODULES-001).

Descripteur déclaratif et activation explicite, sans découverte ni câblage Web :
l'hôte (routes /modules/<id>/, assets, pages) viendra avec FD-MODULES-002.
Voir docs/modules/module-architecture.md. Ce paquet n'importe aucun module
spécialisé : il ne connaît que ceux qu'on lui nomme.
"""

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
    "MODULE_API_VERSION",
    "MODULE_URL_PREFIX",
    "SUPPORTED_MODULE_API_VERSIONS",
    "ActiveModule",
    "ModuleActivation",
    "ModuleAsset",
    "ModuleDescriptor",
    "ModuleDiagnostic",
    "ResourceBinding",
    "activate_modules",
]
