"""Descripteur d'un module spécialisé externe (FD-MODULES-001).

Déclaratif autant que possible : il réutilise SpecializedToolDefinition
(identité, types de ressources, capacités, dépendances optionnelles, entrée UI)
et n'y ajoute que ce dont l'hôte a besoin pour activer un module. Version du
paquet, version d'API hôte, codec et projection Graphics par type de ressource,
assets en liste fermée, sonde de dépendances optionnelles.

Un descripteur ne reçoit ni Router, ni Application, ni Request, ni racine de
projet : il ne peut ni enregistrer une route, ni lire ou écrire le projet. Les
routes et URLs d'assets sont calculées par l'hôte, sous /modules/<id>/.

FD-EDIT-001 ajoute ``actions`` (facultatif, ``()`` par défaut) : des mutations
métier pures, exécutées et persistées par l'hôte. L'ajout est additif : un
descripteur d'API 1 sans action reste valide tel quel.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, cast

from forge_design.modules.actions import MAX_MODULE_ACTIONS, ModuleAction
from forge_design.specialized import SpecializedToolDefinition

# Version d'API hôte des modules. Un module déclare la version qu'il cible ;
# l'hôte n'active que les versions supportées (pas de solveur de dépendances).
MODULE_API_VERSION = 1
SUPPORTED_MODULE_API_VERSIONS: frozenset[int] = frozenset({MODULE_API_VERSION})

MAX_MODULE_ID_CHARS = 32
MAX_MODULE_ASSETS = 32
MODULE_URL_PREFIX = "/modules"

_VERSION = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+-]{0,63}")
_ASSET_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,62}\.(js|css|svg)")
_PACKAGE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
# Types MIME fixés par l'hôte selon l'extension : le module ne les choisit pas.
ASSET_MEDIA_TYPES: Mapping[str, str] = {
    "js": "text/javascript; charset=utf-8",
    "css": "text/css; charset=utf-8",
    "svg": "image/svg+xml",
}
_CODEC_METHODS = ("detect_version", "decode", "encode", "validate")

SceneProjection = Callable[[Any], Mapping[str, Any]]
DependencyProbe = Callable[[], Mapping[str, bool]]


# Contrôles d'exécution : les dataclasses ne vérifient pas les annotations
# (même idiome que forge_design.specialized.models).
def _is_str(value: object) -> bool:
    return isinstance(value, str)


def _is_instance(value: object, kind: type) -> bool:
    return isinstance(value, kind)


def _tuple_of(value: object, kind: type) -> bool:
    return isinstance(value, tuple) and all(
        isinstance(item, kind) for item in cast(tuple[object, ...], value)
    )


def is_package_name(value: object) -> bool:
    return isinstance(value, str) and _PACKAGE.fullmatch(value) is not None


@dataclass(frozen=True)
class ModuleAsset:
    """Asset servi par l'hôte à /modules/<id>/assets/<name>, liste fermée.

    ``source`` est relatif aux ressources du paquet déclaré par le descripteur ;
    jamais absolu, jamais de segment vide, « . », « .. » ou caché.
    """

    name: str
    source: str

    def __post_init__(self) -> None:
        if not _is_str(self.name) or not _ASSET_NAME.fullmatch(self.name):
            raise ValueError(f"Nom d'asset invalide : {self.name!r}")
        if not _is_str(self.source) or not self.source:
            raise ValueError("La source d'un asset est un chemin relatif non vide.")
        parts = PurePosixPath(self.source).parts
        if (
            self.source.startswith("/")
            or "\\" in self.source
            or "\x00" in self.source
            or any(part in {"", ".", ".."} or part.startswith(".") for part in parts)
            or self.source.split("/") != list(parts)
        ):
            raise ValueError(f"Source d'asset refusée : {self.source!r}")

    @property
    def media_type(self) -> str:
        return ASSET_MEDIA_TYPES[self.name.rsplit(".", 1)[1]]


@dataclass(frozen=True)
class ResourceBinding:
    """Ce que le module fournit pour un type de ressource qu'il déclare.

    Le codec (SpecializedResourceCodec) ne voit que des octets ; la projection,
    facultative, transforme un document décodé en GraphicScene sérialisable.
    """

    resource_type: str
    codec: Any
    scene: SceneProjection | None = None

    def __post_init__(self) -> None:
        if not _is_str(self.resource_type) or not self.resource_type:
            raise ValueError("Le type de ressource lié est requis.")
        missing = [
            name
            for name in _CODEC_METHODS
            if not callable(getattr(self.codec, name, None))
        ]
        if missing:
            raise ValueError(f"Codec incomplet : {', '.join(missing)}.")
        if self.scene is not None and not callable(self.scene):
            raise ValueError("La projection Graphics doit être appelable.")


@dataclass(frozen=True)
class ModuleDescriptor:
    """Contrat d'un module spécialisé externe, version d'API 1."""

    definition: SpecializedToolDefinition
    version: str
    api_version: int
    bindings: tuple[ResourceBinding, ...]
    asset_package: str | None = None
    assets: tuple[ModuleAsset, ...] = ()
    dependency_probe: DependencyProbe | None = None
    actions: tuple[ModuleAction, ...] = ()

    def __post_init__(self) -> None:
        if not _is_instance(self.definition, SpecializedToolDefinition):
            raise ValueError("definition doit être une SpecializedToolDefinition.")
        if len(self.definition.id) > MAX_MODULE_ID_CHARS:
            raise ValueError(f"Identifiant de module trop long : {self.definition.id}")
        if not _is_str(self.version) or not _VERSION.fullmatch(self.version):
            raise ValueError(f"Version de module invalide : {self.version!r}")
        if _is_instance(self.api_version, bool) or not _is_instance(
            self.api_version, int
        ):
            raise ValueError("api_version doit être un entier.")
        if not _tuple_of(self.bindings, ResourceBinding):
            raise ValueError("bindings doit être un tuple de ResourceBinding.")
        declared = [item.id for item in self.definition.resource_types]
        bound = [item.resource_type for item in self.bindings]
        if sorted(bound) != sorted(declared) or len(set(bound)) != len(bound):
            raise ValueError(
                "Chaque type de ressource déclaré doit avoir exactement un codec."
            )
        if not _tuple_of(self.assets, ModuleAsset):
            raise ValueError("assets doit être un tuple de ModuleAsset.")
        if len(self.assets) > MAX_MODULE_ASSETS:
            raise ValueError(f"Au plus {MAX_MODULE_ASSETS} assets par module.")
        names = [item.name for item in self.assets]
        if len(set(names)) != len(names):
            raise ValueError("Nom d'asset dupliqué.")
        if self.assets and not is_package_name(self.asset_package):
            raise ValueError("Des assets exigent un paquet de ressources nommé.")
        if self.asset_package is not None and not is_package_name(self.asset_package):
            raise ValueError(f"Paquet d'assets invalide : {self.asset_package!r}")
        if self.dependency_probe is not None and not callable(self.dependency_probe):
            raise ValueError("La sonde de dépendances doit être appelable.")
        self._check_actions()

    def _check_actions(self) -> None:
        """Action : type déclaré, modifiable, offrant save et sa capacité."""
        if not _tuple_of(self.actions, ModuleAction):
            raise ValueError("actions doit être un tuple de ModuleAction.")
        if len(self.actions) > MAX_MODULE_ACTIONS:
            raise ValueError(f"Au plus {MAX_MODULE_ACTIONS} actions par module.")
        ids = [item.id for item in self.actions]
        if len(set(ids)) != len(ids):
            raise ValueError("Identifiant d'action dupliqué.")
        declared = {item.id: item for item in self.definition.resource_types}
        for action in self.actions:
            resource_type = declared.get(action.resource_type)
            if resource_type is None:
                raise ValueError(f"Action {action.id} : type de ressource non déclaré.")
            if not resource_type.editable or not resource_type.has_capability("save"):
                raise ValueError(
                    f"Action {action.id} : le type n'est pas modifiable (save)."
                )
            if not resource_type.has_capability(action.capability):
                raise ValueError(
                    f"Action {action.id} : capacité {action.capability} non déclarée."
                )

    @property
    def id(self) -> str:
        return self.definition.id

    @property
    def base_url(self) -> str:
        """Seul espace d'URL du module ; il ne peut pas en choisir d'autre."""
        return f"{MODULE_URL_PREFIX}/{self.id}/"

    def asset_url(self, name: str) -> str:
        if name not in {item.name for item in self.assets}:
            raise KeyError(name)
        return f"{self.base_url}assets/{name}"

    def action_url(self, action_id: str) -> str:
        if action_id not in {item.id for item in self.actions}:
            raise KeyError(action_id)
        return f"{self.base_url}actions/{action_id}"

    def binding(self, resource_type: str) -> ResourceBinding:
        for item in self.bindings:
            if item.resource_type == resource_type:
                return item
        raise KeyError(resource_type)
