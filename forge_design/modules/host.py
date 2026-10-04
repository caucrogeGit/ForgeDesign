"""Hôte des modules spécialisés activés (FD-MODULES-002).

Construit une fois par application à partir d'une ModuleActivation (durée de vie
de l'application). Le projet courant n'est pas retenu : chaque opération reçoit
la racine du moment, ce qui suit les changements de projet sans réactivation.

L'hôte inventorie et lit les ressources par le contrat spécialisé
(list/read_specialized_resource) avec le codec du module, appelle sa projection
Graphics en isolant ses échecs, et sert ses assets déclarés, lus et vérifiés à
la construction. Un module ne reçoit jamais de racine de projet, de chemin
système, de Router ni de Request.
"""

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from types import MappingProxyType
from typing import Any

from forge_design.forge.project_root import (
    ProjectRootNotDirectoryError,
    ProjectRootNotFoundError,
    ProjectRootResolutionError,
)
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.modules.activation import (
    ActiveModule,
    ModuleActivation,
    ModuleDiagnostic,
)
from forge_design.modules.descriptor import ModuleAsset
from forge_design.specialized import (
    SpecializedReadResult,
    SpecializedResourceListing,
    SpecializedResourceType,
    list_specialized_resources,
    read_specialized_resource,
)
from forge_design.specialized.models import is_kebab_case

# Une GraphicScene projetée par un module est bornée avant transport ; sa forme
# exacte est validée par le vrai validateScene du Graphic Core dans le navigateur.
MAX_MODULE_SCENE_BYTES = 8 * 1024 * 1024

_LOGGER = logging.getLogger("forge_design.modules")

# Erreurs attendues de la racine de projet : elles relèvent de la page, pas du module.
_PROJECT_ERRORS: tuple[type[Exception], ...] = (
    ProjectRootNotFoundError,
    ProjectRootNotDirectoryError,
    ProjectRootResolutionError,
    NotForgeProjectError,
)


@dataclass(frozen=True)
class ModuleNavigationEntry:
    module_id: str
    label: str
    url: str


@dataclass(frozen=True)
class ModuleResourceView:
    """Lecture d'une ressource par l'hôte, puis projection éventuelle du module.

    ``read`` est None seulement si le code du module a échoué (codec) ;
    ``runtime_error`` porte alors un message borné, jamais une trace.
    """

    module: ActiveModule
    resource_type: SpecializedResourceType
    path: str
    read: SpecializedReadResult[Any] | None
    scene: Mapping[str, Any] | None
    scene_error: str | None
    runtime_error: str | None


def _runtime(module_id: str, what: str, error: Exception) -> str:
    _LOGGER.warning("Module %s : %s en échec.", module_id, what, exc_info=error)
    return f"{what} du module en échec ({type(error).__name__})."


class ModuleHost:
    """Modules exposés par une application, dans l'ordre d'activation."""

    def __init__(self, activation: ModuleActivation) -> None:
        diagnostics = list(activation.diagnostics)
        exposed: list[ActiveModule] = []
        assets: dict[tuple[str, str], tuple[bytes, str]] = {}
        for module in activation.modules:
            loaded = self._load_assets(module)
            if isinstance(loaded, ModuleDiagnostic):
                diagnostics.append(loaded)
                continue
            exposed.append(module)
            assets.update(loaded)
        self._modules = tuple(exposed)
        self._diagnostics = tuple(diagnostics)
        self._assets = MappingProxyType(assets)

    @staticmethod
    def _load_assets(
        module: ActiveModule,
    ) -> dict[tuple[str, str], tuple[bytes, str]] | ModuleDiagnostic:
        """Chaque asset déclaré doit exister ; sinon le module n'est pas exposé."""
        descriptor = module.descriptor
        loaded: dict[tuple[str, str], tuple[bytes, str]] = {}
        for asset in descriptor.assets:
            try:
                resource = files(str(descriptor.asset_package)).joinpath(asset.source)
                if not resource.is_file():
                    raise FileNotFoundError(asset.source)
                data = resource.read_bytes()
            except Exception:  # paquet ou fichier de module : jamais fatal
                return ModuleDiagnostic(
                    module.package,
                    "asset-missing",
                    f"Asset déclaré introuvable : {asset.name}.",
                )
            loaded[(descriptor.id, asset.name)] = (data, asset.media_type)
        return loaded

    def modules(self) -> tuple[ActiveModule, ...]:
        return self._modules

    def module(self, module_id: str) -> ActiveModule:
        for module in self._modules:
            if module.descriptor.id == module_id:
                return module
        raise KeyError(module_id)

    def diagnostics(self) -> tuple[ModuleDiagnostic, ...]:
        return self._diagnostics

    def navigation(self) -> tuple[ModuleNavigationEntry, ...]:
        """Modules actifs, compatibles et exposés qui déclarent une UiEntry."""
        return tuple(
            ModuleNavigationEntry(
                module.descriptor.id,
                module.descriptor.definition.ui_entry.label,
                module.descriptor.base_url,
            )
            for module in self._modules
            if module.descriptor.definition.ui_entry is not None
        )

    def assets(self, module_id: str) -> tuple[ModuleAsset, ...]:
        return self.module(module_id).descriptor.assets

    def asset(self, module_id: str, name: str) -> tuple[bytes, str]:
        """Octets et type MIME fixés par le cœur ; KeyError hors liste déclarée."""
        return self._assets[(module_id, name)]

    def resource_type(self, module_id: str, type_id: str) -> SpecializedResourceType:
        if not is_kebab_case(type_id):
            raise KeyError(type_id)
        return self.module(module_id).descriptor.definition.resource_type(type_id)

    def list_resources(
        self, module_id: str, root: Path
    ) -> tuple[tuple[SpecializedResourceType, SpecializedResourceListing], ...]:
        """Inventaire de chaque type du module dans le projet donné, sans lecture."""
        definition = self.module(module_id).descriptor.definition
        return tuple(
            (item, list_specialized_resources(root, definition, item))
            for item in definition.resource_types
        )

    def read_resource(
        self, module_id: str, type_id: str, root: Path, path: str
    ) -> ModuleResourceView:
        """Lecture par l'hôte avec le codec du module, puis projection Graphics."""
        module = self.module(module_id)
        resource_type = self.resource_type(module_id, type_id)
        binding = module.descriptor.binding(type_id)
        definition = module.descriptor.definition
        try:
            read = read_specialized_resource(
                root, definition, resource_type, path, binding.codec
            )
        except _PROJECT_ERRORS:
            raise
        except Exception as error:  # codec du module : isolé
            message = _runtime(module_id, "Décodage", error)
            return ModuleResourceView(
                module, resource_type, path, None, None, None, message
            )
        scene, scene_error = None, None
        if read.resource is not None and binding.scene is not None:
            scene, scene_error = self._project(module_id, binding.scene, read.resource)
        return ModuleResourceView(
            module, resource_type, path, read, scene, scene_error, None
        )

    @staticmethod
    def _project(
        module_id: str, projection: Any, resource: object
    ) -> tuple[Mapping[str, Any] | None, str | None]:
        """Projection du module, isolée et bornée ; copie JSON détachée du module."""
        try:
            produced = projection(resource)
        except Exception as error:
            return None, _runtime(module_id, "Projection graphique", error)
        if not isinstance(produced, Mapping):
            return None, "La projection graphique du module ne rend pas un objet."
        try:
            text = json.dumps(produced, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError, RecursionError):
            return None, "La projection graphique du module n'est pas du JSON."
        if len(text.encode("utf-8")) > MAX_MODULE_SCENE_BYTES:
            return None, "La projection graphique du module est trop volumineuse."
        return json.loads(text), None
