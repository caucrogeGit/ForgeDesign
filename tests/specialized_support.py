"""Outil témoin de FD-SPECIALIZED-002 : interne aux tests, jamais livré.

Il n'est ni exporté par forge_design, ni enregistré, ni visible dans l'UI.
Son espace de sources (mvc/resources/witness, *.witness.json) n'existe que dans
les projets temporaires des tests et n'est pas réservé par Forge Design.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from forge_design.json_strict import loads_strict_json
from forge_design.specialized import (
    SpecializedCapability,
    SpecializedFormatError,
    SpecializedIssue,
    SpecializedResourceType,
    SpecializedToolDefinition,
    SpecializedValidationResult,
)

WITNESS_PREFIX = "mvc/resources/witness"
WITNESS_SUFFIX = ".witness.json"
WITNESS_PATH = WITNESS_PREFIX + "/note" + WITNESS_SUFFIX
WITNESS_FIELDS = ("format_version", "title", "content")

CAPABILITIES = tuple(
    SpecializedCapability.platform(name)
    for name in ("create", "open", "edit", "validate", "save")
)


def witness_type(**changes: object) -> SpecializedResourceType:
    values: dict[str, object] = {
        "id": "document",
        "format_id": "witness-json",
        "suffix": WITNESS_SUFFIX,
        "source_prefix": WITNESS_PREFIX,
        "read_versions": frozenset({"0.1"}),
        "write_version": "0.1",
        "editable": True,
        "max_size": 64 * 1024,
        "capabilities": CAPABILITIES,
        "validation_levels": ("structure", "content"),
        "blocking_validation_levels": frozenset({"structure"}),
        "persistent_state": ("title", "content"),
        "runtime_only_state": ("selected_tab",),
    }
    values.update(changes)
    return SpecializedResourceType(**values)  # type: ignore[arg-type]


def witness_tool(
    resource_type: SpecializedResourceType | None = None, **changes: object
) -> SpecializedToolDefinition:
    values: dict[str, object] = {
        "id": "witness",
        "name": "Témoin de test FD-SPECIALIZED-002",
        "description": "Outil témoin interne aux tests, non livré.",
        "resource_types": (resource_type or witness_type(),),
        "capabilities": CAPABILITIES,
        "optional_dependencies": (),
        "ui_entry": None,
    }
    values.update(changes)
    return SpecializedToolDefinition(**values)  # type: ignore[arg-type]


@dataclass(frozen=True)
class WitnessDocument:
    """État persistant du témoin : exactement title et content."""

    title: str
    content: str


@dataclass
class WitnessSession:
    """Harnais d'édition : selected_tab est un état runtime-only, jamais persisté."""

    document: WitnessDocument
    selected_tab: int = 0


def _structure(code: str, message: str, *location: str | int) -> SpecializedIssue:
    return SpecializedIssue(f"witness.{code}", "error", message, "structure", location)


class WitnessCodec:
    """Codec du témoin : octets et mémoire seulement, compteurs pour les tests."""

    def __init__(self, written_version: str = "0.1") -> None:
        self.written_version = written_version
        self.detect_calls = 0
        self.decode_calls = 0

    def detect_version(self, data: bytes) -> str | None:
        self.detect_calls += 1
        try:
            parsed = loads_strict_json(data.decode("utf-8"))
        except (UnicodeError, ValueError, RecursionError):
            return None
        if isinstance(parsed, dict):
            version = parsed.get("format_version")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            if isinstance(version, str):
                return version
        return None

    def decode(self, data: bytes) -> WitnessDocument:
        self.decode_calls += 1
        try:
            parsed = loads_strict_json(data.decode("utf-8"))
        except (UnicodeError, ValueError, RecursionError):
            raise SpecializedFormatError(
                (_structure("invalid-json", "JSON invalide."),)
            ) from None
        if not isinstance(parsed, dict):
            raise SpecializedFormatError((_structure("not-object", "Objet attendu."),))
        document: dict[str, object] = parsed  # pyright: ignore[reportUnknownVariableType]
        issues = [
            _structure("unknown-field", "Champ inconnu.", key)
            for key in document
            if key not in WITNESS_FIELDS
        ]
        for key in ("title", "content"):
            if not isinstance(document.get(key), str):
                issues.append(_structure("invalid-field", "Chaîne attendue.", key))
        if issues:
            raise SpecializedFormatError(tuple(issues))
        return WitnessDocument(str(document["title"]), str(document["content"]))

    def encode(self, resource: WitnessDocument) -> bytes:
        payload = {
            "format_version": self.written_version,
            "title": resource.title,
            "content": resource.content,
        }
        return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode()

    def validate(self, resource: WitnessDocument) -> SpecializedValidationResult:
        issues: list[SpecializedIssue] = []
        for key in ("title", "content"):
            if not isinstance(getattr(resource, key), str):
                issues.append(_structure("invalid-field", "Chaîne attendue.", key))
        title: object = getattr(resource, "title")
        if isinstance(title, str) and not title.strip():
            issues.append(
                SpecializedIssue(
                    "witness.empty-title",
                    "warning",
                    "Titre vide.",
                    "content",
                    ("title",),
                )
            )
        return SpecializedValidationResult.bounded(issues)


def make_project(root: Path, *, witness_dir: bool = True) -> Path:
    """Signatures Forge minimales ; l'espace témoin est créé explicitement."""
    root.mkdir(parents=True)
    for name in ("app.py", "config.py", "bootstrap.py"):
        (root / name).write_text("raise AssertionError('never execute')")
    (root / "mvc/routes").mkdir(parents=True)
    if witness_dir:
        (root / WITNESS_PREFIX).mkdir(parents=True)
    return root.resolve()


def witness_bytes(
    title: str = "Exemple", content: str = "Texte", version: str = "0.1"
) -> bytes:
    return (
        json.dumps(
            {"format_version": version, "title": title, "content": content},
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    ).encode()
