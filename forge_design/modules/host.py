"""Hôte des modules spécialisés activés (FD-MODULES-002).

Construit une fois par application à partir d'une ModuleActivation (durée de vie
de l'application). Le projet courant n'est pas retenu : chaque opération reçoit
la racine du moment, ce qui suit les changements de projet sans réactivation.

L'hôte inventorie et lit les ressources par le contrat spécialisé
(list/read_specialized_resource) avec le codec du module, appelle sa projection
Graphics en isolant ses échecs, et sert ses assets déclarés, lus et vérifiés à
la construction. Un module ne reçoit jamais de racine de projet, de chemin
système, de Router ni de Request.

FD-EDIT-001 : l'hôte expose aussi les actions déclarées dont la capacité et
``save`` sont réellement disponibles, et les exécute selon un cycle fermé :
lecture, contrôle du jeton de révision, handler pur du module, comparaison des
encodages (no-op), puis write_specialized_resource (validation bloquante,
conflit, publication atomique, historique). Le résultat est un code d'issue ;
le statut HTTP est décidé par la couche Web du cœur.

FD-GRAPHICS-EDIT-001 : si le type a une action exposée, une scène et un
``editor_script``, la vue porte un contexte d'édition inerte (URL du script,
type, chemin, jeton, URLs des actions exposées du type, configuration du
module). Tout est calculé par l'hôte ; la configuration du module est isolée et
bornée comme la projection.
"""

import hmac
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

from forge_design.forge.project_root import (
    ProjectRootNotDirectoryError,
    ProjectRootNotFoundError,
    ProjectRootResolutionError,
)
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.modules.actions import (
    ModuleAction,
    ModuleActionPayload,
    ModuleActionPayloadError,
    ModuleActionRefused,
    bounded_message,
    is_action_result,
    is_revision_token,
    revision_token,
)
from forge_design.modules.activation import (
    ActiveModule,
    ModuleActivation,
    ModuleDiagnostic,
)
from forge_design.modules.descriptor import ModuleAsset
from forge_design.specialized import (
    InvalidSpecializedResourceError,
    SpecializedIssue,
    SpecializedReadResult,
    SpecializedResourceConflictError,
    SpecializedResourceError,
    SpecializedResourceHistoryError,
    SpecializedResourceListing,
    SpecializedResourceRefusedError,
    SpecializedResourceRevision,
    SpecializedResourceType,
    UnsupportedSpecializedVersionError,
    list_specialized_resources,
    read_specialized_resource,
    write_specialized_resource,
)
from forge_design.specialized.models import is_kebab_case

# Une GraphicScene projetée par un module est bornée avant transport ; sa forme
# exacte est validée par le vrai validateScene du Graphic Core dans le navigateur.
MAX_MODULE_SCENE_BYTES = 8 * 1024 * 1024
# Configuration d'édition d'un module : données de travail du script, pas une scène.
MAX_MODULE_EDITOR_CONFIG_BYTES = 1024 * 1024

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
    # Jeton public de la révision lue, seulement si le type a des actions exposées.
    revision_token: str | None = None
    # Contexte du script d'édition (JSON inerte), ou message borné si indisponible.
    editor: Mapping[str, Any] | None = None
    editor_error: str | None = None


ActionOutcomeCode = Literal[
    "saved",
    "unchanged",
    "payload-invalid",
    "type-mismatch",
    "resource-not-found",
    "resource-refused",
    "resource-unusable",
    "conflict",
    "refused",
    "invalid-resource",
    "module-error",
    "write-failed",
]


@dataclass(frozen=True)
class ModuleActionOutcome:
    """Issue d'une action : code fermé, message borné, jamais une trace."""

    code: ActionOutcomeCode
    message: str
    issues: tuple[SpecializedIssue, ...] = ()
    truncated: bool = False
    revision: SpecializedResourceRevision | None = None


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
        # Capability gate au démarrage : une action dont la capacité ou save est
        # indisponible (sonde) n'est jamais exposée, donc jamais routée.
        self._actions = MappingProxyType(
            {
                module.descriptor.id: tuple(
                    action
                    for action in module.descriptor.actions
                    if {action.capability, "save"} <= module.available_capabilities
                )
                for module in exposed
            }
        )

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

    def actions(self, module_id: str) -> tuple[ModuleAction, ...]:
        """Actions exposées du module (déclarées et réellement disponibles)."""
        return self._actions[self.module(module_id).descriptor.id]

    def action(self, module_id: str, action_id: str) -> ModuleAction:
        for action in self.actions(module_id):
            if action.id == action_id:
                return action
        raise KeyError(action_id)

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
        token = None
        actions = tuple(
            action
            for action in self.actions(module_id)
            if action.resource_type == type_id
        )
        if read.revision is not None and actions:
            token = revision_token(module_id, type_id, path, read.revision)
        editor, editor_error = None, None
        if token is not None and scene is not None and binding.editor_script:
            config: Mapping[str, Any] = {}
            if binding.editor_config is not None:
                config, editor_error = self._editor_config(
                    module_id, binding.editor_config, read.resource
                )
            if editor_error is None:
                descriptor = module.descriptor
                editor = {
                    "script": descriptor.asset_url(binding.editor_script),
                    "type": type_id,
                    "path": path,
                    "revision": token,
                    "actions": {
                        action.id: descriptor.action_url(action.id)
                        for action in actions
                    },
                    "config": config,
                }
        return ModuleResourceView(
            module,
            resource_type,
            path,
            read,
            scene,
            scene_error,
            None,
            token,
            editor,
            editor_error,
        )

    def execute_action(
        self,
        module_id: str,
        action_id: str,
        root: Path,
        type_id: str,
        path: str,
        token: str,
        fields: Mapping[str, str],
    ) -> ModuleActionOutcome:
        """Lire, vérifier la révision, transformer (module), puis écrire (cœur).

        KeyError si l'action n'est pas exposée ; erreurs de racine propagées.
        Le handler ne reçoit que le document décodé et le payload borné.
        """
        action = self.action(module_id, action_id)
        if type_id != action.resource_type:
            return ModuleActionOutcome(
                "type-mismatch", "Type de ressource étranger à cette action."
            )
        if set(fields) != set(action.fields):
            expected = ", ".join(action.fields) or "aucun"
            return ModuleActionOutcome(
                "payload-invalid", f"Champs attendus : {expected}."
            )
        try:
            payload = ModuleActionPayload(fields)
        except ValueError as error:
            return ModuleActionOutcome("payload-invalid", str(error))
        if not is_revision_token(token):
            return ModuleActionOutcome("payload-invalid", "Jeton de révision invalide.")
        module = self.module(module_id)
        definition = module.descriptor.definition
        resource_type = definition.resource_type(type_id)
        codec = module.descriptor.binding(type_id).codec

        def failed(what: str, error: Exception) -> ModuleActionOutcome:
            return ModuleActionOutcome("module-error", _runtime(module_id, what, error))

        try:
            read = read_specialized_resource(
                root, definition, resource_type, path, codec
            )
        except _PROJECT_ERRORS:
            raise
        except Exception as error:  # codec du module : isolé
            return failed("Décodage", error)
        if read.error == "resource-not-found":
            return ModuleActionOutcome("resource-not-found", "Ressource introuvable.")
        if read.error == "resource-refused":
            return ModuleActionOutcome(
                "resource-refused", "Chemin de ressource refusé."
            )
        if read.error is not None or read.resource is None or read.revision is None:
            return ModuleActionOutcome(
                "resource-unusable",
                "Ressource illisible, invalide ou d'une autre version : "
                "aucune action possible.",
                read.issues,
                read.truncated,
            )
        current = revision_token(module_id, type_id, path, read.revision)
        if not hmac.compare_digest(current, token):
            return ModuleActionOutcome(
                "conflict",
                "La ressource a changé depuis son affichage : rechargez-la.",
            )
        try:
            before = codec.encode(read.resource)
        except Exception as error:
            return failed("Encodage", error)
        try:
            result = action.handler(read.resource, payload)
        except ModuleActionPayloadError as error:
            return ModuleActionOutcome("payload-invalid", bounded_message(error))
        except ModuleActionRefused as error:
            return ModuleActionOutcome("refused", bounded_message(error))
        except Exception as error:  # handler du module : isolé, jamais exposé
            return failed("Action", error)
        if not is_action_result(result):
            return ModuleActionOutcome(
                "module-error", "L'action du module ne rend pas un ModuleActionResult."
            )
        try:
            if codec.encode(read.resource) != before:
                return ModuleActionOutcome(
                    "module-error", "L'action du module a modifié le document lu."
                )
            after = codec.encode(result.resource)
        except Exception as error:
            return failed("Encodage", error)
        if after == before:
            return ModuleActionOutcome("unchanged", "Aucune modification.")
        try:
            written = write_specialized_resource(
                root,
                definition,
                resource_type,
                path,
                result.resource,
                codec,
                expected_revision=read.revision,
            )
        except _PROJECT_ERRORS:
            raise
        except InvalidSpecializedResourceError as error:
            return ModuleActionOutcome(
                "invalid-resource",
                "Modification refusée par la validation bloquante.",
                error.issues,
                error.truncated,
            )
        except SpecializedResourceConflictError:
            return ModuleActionOutcome(
                "conflict",
                "La ressource a changé pendant l'action : rechargez-la.",
            )
        except SpecializedResourceRefusedError as error:
            return ModuleActionOutcome("invalid-resource", str(error))
        except UnsupportedSpecializedVersionError as error:
            return failed("Écriture", error)
        except SpecializedResourceHistoryError:
            return ModuleActionOutcome(
                "write-failed",
                "Ressource écrite, mais le journal n'a pas pu être complété.",
            )
        except SpecializedResourceError:
            return ModuleActionOutcome(
                "write-failed",
                "Sauvegarde incertaine : relisez la ressource avant de réessayer.",
            )
        except Exception as error:  # codec du module pendant l'écriture
            return failed("Écriture", error)
        return ModuleActionOutcome(
            "saved", "Modification enregistrée.", revision=written.revision
        )

    @staticmethod
    def _editor_config(
        module_id: str, configure: Any, resource: object
    ) -> tuple[Mapping[str, Any], str | None]:
        """Configuration du module, isolée et bornée ; copie JSON détachée."""
        unavailable = "Édition indisponible : "
        try:
            produced = configure(resource)
        except Exception as error:
            return {}, unavailable + _runtime(
                module_id, "Configuration d'édition", error
            )
        if not isinstance(produced, Mapping):
            return {}, unavailable + "la configuration du module n'est pas un objet."
        try:
            text = json.dumps(produced, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError, RecursionError):
            return {}, unavailable + "la configuration du module n'est pas du JSON."
        if len(text.encode("utf-8")) > MAX_MODULE_EDITOR_CONFIG_BYTES:
            return {}, unavailable + "la configuration du module est trop volumineuse."
        return json.loads(text), None

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
