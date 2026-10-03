"""Déclarations des outils spécialisés (FD-SPECIALIZED-002).

Formes gelées et validées à la construction du contrat FD-SPECIALIZED-001
(docs/specialized-tools/specialized-tool-contract.md). Elles décrivent un outil ;
elles n'exécutent rien : aucune méthode run, open, save, render ou simulate.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal, cast, get_args

from forge_design.forge.source import unsafe_relative_path
from forge_design.limits import (
    MAX_SOURCE_PATH_LENGTH,
    MAX_SPECIALIZED_ISSUES,
    MAX_SPECIALIZED_LOCATION_DEPTH,
    MAX_SPECIALIZED_RESOURCE_BYTES,
)

# Même règle que ToolRegistry.register pour les identifiants Tool.
_KEBAB_CASE = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
_VERSION = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+-]{0,63}")

PlatformCapability = Literal[
    "create", "open", "edit", "validate", "save", "export", "interactive-runtime"
]
PLATFORM_CAPABILITIES: frozenset[str] = frozenset(get_args(PlatformCapability))

ErrorCategory = Literal[
    "resource-not-found",
    "resource-refused",
    "unsupported-version",
    "invalid-resource",
    "conflict",
    "capability-unavailable",
    "dependency-unavailable",
    "runtime-error",
]
ERROR_CATEGORIES: frozenset[str] = frozenset(get_args(ErrorCategory))

Severity = Literal["error", "warning"]
STRUCTURE_LEVEL = "structure"


def _tuple_of(value: object, kind: type) -> bool:
    """Contrôle d'exécution : les dataclasses ne vérifient pas les annotations."""
    return isinstance(value, tuple) and all(
        isinstance(item, kind) for item in cast(tuple[object, ...], value)
    )


def _frozenset_of_str(value: object) -> bool:
    return isinstance(value, frozenset) and all(
        isinstance(item, str) for item in cast(frozenset[object], value)
    )


def _is_bool(value: object) -> bool:
    return isinstance(value, bool)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_instance(value: object, kind: type) -> bool:
    return isinstance(value, kind)


def is_kebab_case(value: object) -> bool:
    return isinstance(value, str) and _KEBAB_CASE.fullmatch(value) is not None


def _require_kebab(value: object, what: str) -> None:
    if not is_kebab_case(value):
        raise ValueError(f"{what} doit être en kebab-case non vide.")


def _require_text(value: object, what: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{what} doit être une chaîne non vide.")


def _require_unique(values: Iterable[str], what: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"{what} en double : {value}")
        seen.add(value)


@dataclass(frozen=True)
class SpecializedCapability:
    """Capacité plateforme (vocabulaire fermé) ou capacité propre à un outil.

    Une capacité d'outil ne peut pas reprendre un nom du vocabulaire plateforme :
    les deux niveaux ne se confondent jamais.
    """

    id: str
    kind: Literal["platform", "tool"]

    def __post_init__(self) -> None:
        if self.kind == "platform":
            if self.id not in PLATFORM_CAPABILITIES:
                raise ValueError(f"Capacité plateforme inconnue : {self.id!r}")
        elif self.kind == "tool":
            _require_kebab(self.id, "Une capacité d'outil")
            if self.id in PLATFORM_CAPABILITIES:
                raise ValueError(f"{self.id} est une capacité plateforme.")
        else:
            raise ValueError("Nature de capacité inconnue.")

    @classmethod
    def platform(cls, capability: PlatformCapability) -> "SpecializedCapability":
        return cls(capability, "platform")

    @classmethod
    def tool(cls, capability: str) -> "SpecializedCapability":
        return cls(capability, "tool")


def _check_capabilities(capabilities: tuple[SpecializedCapability, ...]) -> None:
    if not _tuple_of(capabilities, SpecializedCapability):
        raise ValueError("Les capacités doivent former un tuple de capacités.")
    _require_unique((item.id for item in capabilities), "Capacité")


@dataclass(frozen=True)
class OptionalDependency:
    """Dépendance de capacités ; sa disponibilité est sondée ailleurs."""

    id: str
    purpose: str
    required_for: tuple[SpecializedCapability, ...]

    def __post_init__(self) -> None:
        _require_kebab(self.id, "L'identifiant de dépendance")
        _require_text(self.purpose, "Le rôle de la dépendance")
        _check_capabilities(self.required_for)
        if not self.required_for:
            raise ValueError("Une dépendance doit servir au moins une capacité.")


@dataclass(frozen=True)
class UiEntry:
    """Entrée d'interface éventuelle ; l'icône est une référence opaque."""

    label: str
    icon: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.label, "Le libellé d'entrée")
        if self.icon is not None:
            _require_text(self.icon, "L'icône")


def _check_suffix(suffix: object) -> None:
    if (
        not isinstance(suffix, str)
        or len(suffix) < 2
        or len(suffix) > 64
        or not suffix.startswith(".")
        or suffix.startswith("..")
        or any(c in suffix for c in ("/", "\\", "\x00", ":"))
        or any(ord(c) < 0x21 or ord(c) == 0x7F for c in suffix)
    ):
        raise ValueError("Suffixe de ressource invalide.")


def _check_prefix(prefix: object) -> None:
    if (
        not isinstance(prefix, str)
        or not prefix
        or prefix.startswith("/")
        or prefix.endswith("/")
        or len(prefix) > MAX_SOURCE_PATH_LENGTH
        or unsafe_relative_path(prefix)
    ):
        raise ValueError("Espace de sources invalide.")


def _check_version(version: object) -> None:
    if not isinstance(version, str) or _VERSION.fullmatch(version) is None:
        raise ValueError(f"Version de format invalide : {version!r}")


def _check_names(names: object, what: str) -> tuple[str, ...]:
    if not isinstance(names, tuple):
        raise ValueError(f"{what} doit être un tuple de noms.")
    items = cast(tuple[object, ...], names)
    for name in items:
        _require_text(name, what)
    texts = cast(tuple[str, ...], items)
    _require_unique(texts, what)
    return texts


@dataclass(frozen=True)
class SpecializedResourceType:
    """Type de ressource éditable persistante (zone C), déclaratif.

    Le niveau de validation « structure » existe toujours et bloque toujours
    l'écriture ; les autres niveaux ne bloquent que s'ils sont déclarés.
    persistent_state et runtime_only_state nomment les éléments d'état ; un nom
    ne peut figurer dans les deux.
    """

    id: str
    format_id: str
    suffix: str
    source_prefix: str
    read_versions: frozenset[str]
    write_version: str
    editable: bool
    max_size: int
    capabilities: tuple[SpecializedCapability, ...]
    validation_levels: tuple[str, ...] = (STRUCTURE_LEVEL,)
    blocking_validation_levels: frozenset[str] = field(
        default_factory=lambda: frozenset({STRUCTURE_LEVEL})
    )
    persistent_state: tuple[str, ...] = ()
    runtime_only_state: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_kebab(self.id, "L'identifiant de type")
        _require_kebab(self.format_id, "L'identifiant de format")
        _check_suffix(self.suffix)
        _check_prefix(self.source_prefix)
        if not _frozenset_of_str(self.read_versions) or not self.read_versions:
            raise ValueError("read_versions doit être un ensemble non vide.")
        for version in self.read_versions:
            _check_version(version)
        _check_version(self.write_version)
        if self.write_version not in self.read_versions:
            raise ValueError("write_version doit appartenir à read_versions.")
        if not _is_bool(self.editable):
            raise ValueError("editable doit être un booléen.")
        if (
            not _is_int(self.max_size)
            or not 1 <= self.max_size <= MAX_SPECIALIZED_RESOURCE_BYTES
        ):
            limit = MAX_SPECIALIZED_RESOURCE_BYTES
            raise ValueError(f"max_size doit être un entier dans [1, {limit}].")
        _check_capabilities(self.capabilities)
        ids = {capability.id for capability in self.capabilities}
        if not self.editable and ids & {"create", "edit", "save"}:
            raise ValueError(
                "Un type non éditable ne déclare ni create, ni edit, ni save."
            )
        levels = _check_names(self.validation_levels, "Niveau de validation")
        for level in levels:
            _require_kebab(level, "Un niveau de validation")
        if STRUCTURE_LEVEL not in levels:
            raise ValueError("Le niveau « structure » est obligatoire.")
        if not _frozenset_of_str(self.blocking_validation_levels):
            raise ValueError("blocking_validation_levels doit être un frozenset.")
        unknown = self.blocking_validation_levels - set(levels)
        if unknown:
            raise ValueError(f"Niveau bloquant inconnu : {sorted(unknown)}")
        if STRUCTURE_LEVEL not in self.blocking_validation_levels:
            raise ValueError("Le niveau « structure » bloque toujours l'écriture.")
        persistent = _check_names(self.persistent_state, "État persistant")
        runtime = _check_names(self.runtime_only_state, "État runtime-only")
        collision = set(persistent) & set(runtime)
        if collision:
            raise ValueError(
                f"État à la fois persistant et runtime : {sorted(collision)}"
            )

    def has_capability(self, capability: PlatformCapability) -> bool:
        return SpecializedCapability.platform(capability) in self.capabilities


@dataclass(frozen=True)
class SpecializedToolDefinition:
    """Déclaration descriptive d'un outil spécialisé ; n'est pas un Tool.

    Chaque type de ressource ne déclare que des capacités de l'outil ; chaque
    dépendance optionnelle sert des capacités de l'outil.
    """

    id: str
    name: str
    description: str
    resource_types: tuple[SpecializedResourceType, ...]
    capabilities: tuple[SpecializedCapability, ...]
    optional_dependencies: tuple[OptionalDependency, ...] = ()
    ui_entry: UiEntry | None = None

    def __post_init__(self) -> None:
        _require_kebab(self.id, "L'identifiant d'outil")
        _require_text(self.name, "Le nom d'outil")
        _require_text(self.description, "La description d'outil")
        if not _tuple_of(self.resource_types, SpecializedResourceType):
            raise ValueError(
                "resource_types doit contenir des SpecializedResourceType."
            )
        if not self.resource_types:
            raise ValueError("Un outil déclare au moins un type de ressource.")
        _require_unique((item.id for item in self.resource_types), "Type de ressource")
        _check_capabilities(self.capabilities)
        offered = set(self.capabilities)
        for resource_type in self.resource_types:
            missing = set(resource_type.capabilities) - offered
            if missing:
                raise ValueError(
                    f"{resource_type.id} déclare des capacités absentes de l'outil."
                )
        if not _tuple_of(self.optional_dependencies, OptionalDependency):
            raise ValueError("optional_dependencies doit être un tuple de dépendances.")
        _require_unique((item.id for item in self.optional_dependencies), "Dépendance")
        for dependency in self.optional_dependencies:
            if not set(dependency.required_for) <= offered:
                raise ValueError(
                    f"{dependency.id} sert une capacité absente de l'outil."
                )
        if self.ui_entry is not None and not _is_instance(self.ui_entry, UiEntry):
            raise ValueError("ui_entry doit être une UiEntry ou None.")

    def resource_type(self, resource_type_id: str) -> SpecializedResourceType:
        for resource_type in self.resource_types:
            if resource_type.id == resource_type_id:
                return resource_type
        raise KeyError(resource_type_id)


def _check_location(location: object) -> None:
    if not isinstance(location, tuple):
        raise ValueError("La location doit être un tuple.")
    parts = cast(tuple[object, ...], location)
    if len(parts) > MAX_SPECIALIZED_LOCATION_DEPTH or not all(
        isinstance(part, str | int) and not isinstance(part, bool) for part in parts
    ):
        raise ValueError("La location doit être un tuple borné de str ou int.")


def is_issue_code(code: object) -> bool:
    """Catégorie plateforme connue, ou code qualifié <outil>.<code> en kebab-case."""
    if not isinstance(code, str):
        return False
    if code in ERROR_CATEGORIES:
        return True
    tool, separator, rest = code.partition(".")
    return bool(separator) and is_kebab_case(tool) and is_kebab_case(rest)


@dataclass(frozen=True)
class SpecializedIssue:
    """Diagnostic structuré ; level est le niveau de validation qui l'a produit."""

    code: str
    severity: Severity
    message: str
    level: str = STRUCTURE_LEVEL
    location: tuple[str | int, ...] = ()

    def __post_init__(self) -> None:
        if not is_issue_code(self.code):
            raise ValueError(f"Code d'issue non qualifié : {self.code!r}")
        if self.severity not in ("error", "warning"):
            raise ValueError("severity doit valoir error ou warning.")
        _require_text(self.message, "Le message")
        _require_kebab(self.level, "Le niveau d'une issue")
        _check_location(self.location)


@dataclass(frozen=True)
class SpecializedValidationResult:
    """Issues bornées ; truncated signale des diagnostics non conservés."""

    issues: tuple[SpecializedIssue, ...] = ()
    truncated: bool = False

    def __post_init__(self) -> None:
        if not _tuple_of(self.issues, SpecializedIssue):
            raise ValueError("issues doit être un tuple de SpecializedIssue.")
        if len(self.issues) > MAX_SPECIALIZED_ISSUES:
            raise ValueError("Trop d'issues : utiliser bounded().")

    @classmethod
    def bounded(
        cls, issues: Iterable[SpecializedIssue]
    ) -> "SpecializedValidationResult":
        """Conserver au plus MAX_SPECIALIZED_ISSUES issues, sans lire au-delà."""
        kept: list[SpecializedIssue] = []
        for issue in issues:
            if len(kept) == MAX_SPECIALIZED_ISSUES:
                return cls(tuple(kept), truncated=True)
            kept.append(issue)
        return cls(tuple(kept))

    def blocking(
        self, resource_type: SpecializedResourceType
    ) -> tuple[SpecializedIssue, ...]:
        return tuple(
            issue
            for issue in self.issues
            if issue.severity == "error"
            and issue.level in resource_type.blocking_validation_levels
        )
