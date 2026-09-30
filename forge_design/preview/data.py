"""Contexte fictif déterministe issu d'un contrat déjà validé, sans I/O."""

from dataclasses import dataclass
from types import MappingProxyType

from forge_design.contracts.models import ViewContract

_SCALARS = MappingProxyType(
    {
        "string": "Exemple",
        "boolean": True,
        "integer": 42,
        "number": 12.5,
        "email": "contact@example.test",
        "date": "2026-05-16",
    }
)
_FIELD_TYPES = frozenset((*_SCALARS, "object", "list"))


@dataclass(frozen=True)
class PreviewDataIssue:
    code: str
    message: str
    location: tuple[str | int, ...]


@dataclass(frozen=True)
class PreviewDataResult:
    data: dict[str, object]
    issues: tuple[PreviewDataIssue, ...]
    complete: bool


def _fake_value_for_type(type_name: str) -> object:
    if type_name == "object":
        return {}
    if type_name == "list":
        return []
    return _SCALARS[type_name]


def generate_preview_data(contract: ViewContract) -> PreviewDataResult:
    """Préserver l'ordre et les entrées ; produire des conteneurs tous distincts.

    Les fields décrivent une seule couche, sans résolution récursive d'entité.
    Les scalaires top-level ignorent fields ; object/list seuls le consomment.
    """
    data: dict[str, object] = {}
    issues: list[PreviewDataIssue] = []
    for name, variable in contract.context.items():
        if variable.type not in {"object", "list"}:
            data[name] = _fake_value_for_type(variable.type)
            continue
        objects: list[dict[str, object]] = [
            {} for _ in range(3 if variable.type == "list" else 1)
        ]
        if variable.fields is not None:
            for field, type_name in variable.fields.items():
                if type_name not in _FIELD_TYPES:
                    issues.append(
                        PreviewDataIssue(
                            "preview.unsupported_field_type",
                            "Type de champ non supporté pour les données fictives.",
                            ("context", name, "fields", field),
                        )
                    )
                    continue
                for item in objects:
                    item[field] = _fake_value_for_type(type_name)
        data[name] = objects if variable.type == "list" else objects[0]
    return PreviewDataResult(data, tuple(issues), complete=not issues)
