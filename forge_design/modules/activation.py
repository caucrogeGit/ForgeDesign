"""Activation explicite des modules spécialisés (FD-MODULES-001).

Aucune découverte : seuls les noms de paquets explicitement configurés sont
importés, dans l'ordre donné. Le paquet expose un attribut ``FORGE_DESIGN_MODULE``
de type ModuleDescriptor.

- Configuration malformée (nom invalide, doublon) : ValueError immédiate.
- Module absent, en échec à l'import, descripteur invalide, version d'API non
  supportée, identifiant ou type de ressource déjà pris : diagnostic, module
  non activé, les autres continuent.
- FD-RELEASE-001 : un module peut exiger une version de Forge Design
  (``requires_forge_design``, spécificateur PEP 440). Elle est comparée à la
  version du cœur (``forge_design.__version__``) avant toute exposition :
  incompatible → ``core-version-incompatible`` ; version du cœur illisible →
  ``core-version-unknown`` (jamais supposée compatible) ; spécificateur
  invalide → ``descriptor-invalid``. Une préversion du cœur est acceptée si elle
  est dans l'intervalle. ``Requires-Dist`` du module reste la première barrière :
  un module qui n'a pas pu être importé reste ``module-import-failed``.

Un module installé reste du code de confiance local : l'importer exécute son
code. Ce contrat évite les accès accidentels par construction ; il ne sandboxe
pas Python.
"""

import importlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

import forge_design
from forge_design.modules.descriptor import (
    SUPPORTED_MODULE_API_VERSIONS,
    ModuleDescriptor,
    is_package_name,
)

DESCRIPTOR_ATTRIBUTE = "FORGE_DESIGN_MODULE"

DiagnosticCode = Literal[
    "module-missing",
    "module-import-failed",
    "descriptor-missing",
    "descriptor-invalid",
    "api-incompatible",
    "core-version-incompatible",
    "core-version-unknown",
    "duplicate-module",
    "duplicate-resource-type",
    "dependency-probe-failed",
    "asset-missing",
]


@dataclass(frozen=True)
class ModuleDiagnostic:
    package: str
    code: DiagnosticCode
    message: str


@dataclass(frozen=True)
class ActiveModule:
    """Module activé : descripteur et capacités réellement disponibles."""

    package: str
    descriptor: ModuleDescriptor
    available_capabilities: frozenset[str]
    unavailable_dependencies: Mapping[str, str]


@dataclass(frozen=True)
class ModuleActivation:
    modules: tuple[ActiveModule, ...]
    diagnostics: tuple[ModuleDiagnostic, ...]

    def module(self, module_id: str) -> ActiveModule:
        for item in self.modules:
            if item.descriptor.id == module_id:
                return item
        raise KeyError(module_id)


Importer = Callable[[str], object]


def _check_configuration(packages: Sequence[str]) -> tuple[str, ...]:
    if isinstance(packages, str) or not all(is_package_name(p) for p in packages):
        raise ValueError("Configuration des modules : noms de paquets Python attendus.")
    names = tuple(packages)
    if len(set(names)) != len(names):
        raise ValueError("Configuration des modules : paquet listé deux fois.")
    return names


def _availability(
    descriptor: ModuleDescriptor,
) -> tuple[frozenset[str], dict[str, str], str | None]:
    """Capacités disponibles selon la sonde ; une sonde en échec rend indisponible."""
    offered = {item.id for item in descriptor.definition.capabilities}
    unavailable: dict[str, str] = {}
    failure = None
    dependencies = descriptor.definition.optional_dependencies
    if dependencies:
        try:
            probe: Mapping[str, bool] = (
                descriptor.dependency_probe() if descriptor.dependency_probe else {}
            )
            states = {item.id: probe.get(item.id) is True for item in dependencies}
        except Exception as error:  # sonde de module : jamais fatale pour l'hôte
            failure = type(error).__name__
            states = {item.id: False for item in dependencies}
        for item in dependencies:
            if not states[item.id]:
                unavailable[item.id] = item.purpose
                offered -= {capability.id for capability in item.required_for}
    return frozenset(offered), unavailable, failure


def _core_version(text: str) -> Version | None:
    try:
        return Version(text)
    except (InvalidVersion, TypeError):
        return None


def _core_refusal(
    descriptor: ModuleDescriptor, core: str, version: Version | None
) -> tuple[DiagnosticCode, str] | None:
    """Contrainte de version du cœur : None si satisfaite ou absente."""
    requirement = descriptor.requires_forge_design
    if requirement is None:
        return None
    try:
        specifier = SpecifierSet(requirement)
    except InvalidSpecifier:
        return (
            "descriptor-invalid",
            f"requires_forge_design invalide : {requirement!r} "
            "(spécificateur PEP 440 attendu).",
        )
    if version is None:
        return (
            "core-version-unknown",
            f"Le module « {descriptor.id} » nécessite forge-design {requirement} ; "
            "version de Forge Design indéterminée.",
        )
    if not specifier.contains(version, prereleases=True):
        return (
            "core-version-incompatible",
            f"Le module « {descriptor.id} » nécessite forge-design {requirement} ; "
            f"version installée : {core}.",
        )
    return None


def activate_modules(
    packages: Sequence[str],
    importer: Importer = importlib.import_module,
    *,
    core_version: str | None = None,
) -> ModuleActivation:
    """Active, dans l'ordre configuré, les modules compatibles et valides.

    ``core_version`` : paramètre de l'hôte, pour les tests ; par défaut
    ``forge_design.__version__``. Un module ne le contrôle jamais.
    """
    core = forge_design.__version__ if core_version is None else core_version
    version = _core_version(core)
    names = _check_configuration(packages)
    active: list[ActiveModule] = []
    diagnostics: list[ModuleDiagnostic] = []
    taken_resources: dict[tuple[str, str], str] = {}

    def refuse(package: str, code: DiagnosticCode, message: str) -> None:
        diagnostics.append(ModuleDiagnostic(package, code, message))

    for package in names:
        try:
            loaded = importer(package)
        except ModuleNotFoundError as error:
            # Le paquet configuré (ou un parent) est absent ; sinon c'est une
            # dépendance interne du module qui manque : échec d'import, pas absence.
            missing = error.name or ""
            if package == missing or package.startswith(missing + "."):
                refuse(
                    package,
                    "module-missing",
                    "Module non installé ; rien n'est chargé.",
                )
            else:
                refuse(
                    package, "module-import-failed", f"ModuleNotFoundError: {missing}"
                )
            continue
        except Exception as error:  # code de module : isolé, jamais fatal pour l'hôte
            refuse(package, "module-import-failed", type(error).__name__)
            continue
        descriptor = getattr(loaded, DESCRIPTOR_ATTRIBUTE, None)
        if descriptor is None:
            refuse(package, "descriptor-missing", f"{DESCRIPTOR_ATTRIBUTE} absent.")
            continue
        if not isinstance(descriptor, ModuleDescriptor):
            refuse(package, "descriptor-invalid", "ModuleDescriptor attendu.")
            continue
        if descriptor.api_version not in SUPPORTED_MODULE_API_VERSIONS:
            supported = ", ".join(map(str, sorted(SUPPORTED_MODULE_API_VERSIONS)))
            refuse(
                package,
                "api-incompatible",
                f"API {descriptor.api_version} non supportée "
                f"(supportées : {supported}).",
            )
            continue
        refusal = _core_refusal(descriptor, core, version)
        if refusal is not None:
            refuse(package, *refusal)
            continue
        if any(item.descriptor.id == descriptor.id for item in active):
            refuse(
                package,
                "duplicate-module",
                f"Identifiant déjà actif : {descriptor.id}.",
            )
            continue
        claimed = [
            (item.source_prefix, item.suffix)
            for item in descriptor.definition.resource_types
        ]
        clash = next((key for key in claimed if key in taken_resources), None)
        if clash is not None:
            refuse(
                package,
                "duplicate-resource-type",
                f"{clash[0]}/*{clash[1]} déjà pris par {taken_resources[clash]}.",
            )
            continue
        available, unavailable, failure = _availability(descriptor)
        if failure is not None:
            refuse(package, "dependency-probe-failed", failure)
        for key in claimed:
            taken_resources[key] = descriptor.id
        active.append(
            ActiveModule(package, descriptor, available, MappingProxyType(unavailable))
        )
    return ModuleActivation(tuple(active), tuple(diagnostics))
