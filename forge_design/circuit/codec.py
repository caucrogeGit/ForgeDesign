"""Codec de la ressource Circuit V0.1 : octets ↔ CircuitDocument, sans filesystem.

Le JSON est contrôlé strictement (UTF-8, clés uniques, constantes non standard
refusées) avant la validation Pydantic en mode JSON. La détection de version, la
vérification stricte et la validation analysent chacune le texte : jusqu'à trois
analyses d'une ressource bornée à quelques Mio, sans modifier le contrat
spécialisé.
"""

import json
from collections.abc import Iterator

from pydantic import ValidationError
from pydantic_core import ErrorDetails, PydanticSerializationError

from forge_design.circuit.models import CircuitDocument
from forge_design.json_strict import loads_strict_json
from forge_design.limits import MAX_SPECIALIZED_ISSUES, MAX_SPECIALIZED_LOCATION_DEPTH
from forge_design.specialized import (
    SpecializedFormatError,
    SpecializedIssue,
    SpecializedValidationResult,
)

_IDENTITY_FIELDS = frozenset({"id", "component_id", "junction_id"})
_LIMIT_TYPES = frozenset({"too_long", "string_too_long", "less_than_equal"})
_MESSAGES = {
    "circuit.json-invalid": "JSON invalide",
    "circuit.validation-error": "Structure invalide",
    "circuit.identity-invalid": "Identité invalide",
    "circuit.identity-duplicate": "Identité dupliquée",
    "circuit.limit-exceeded": "Limite dépassée",
}


def _issue(
    code: str, detail: str, location: tuple[str | int, ...] = ()
) -> SpecializedIssue:
    return SpecializedIssue(
        code,
        "error",
        f"{_MESSAGES[code]} : {detail}",
        "structure",
        location[:MAX_SPECIALIZED_LOCATION_DEPTH],
    )


def _location(data: object, loc: tuple[str | int, ...]) -> tuple[str | int, ...]:
    """Chemin réel dans le document : les étiquettes d'union de Pydantic sont omises."""
    path: list[str | int] = []
    current = data
    for position, element in enumerate(loc):
        last = position == len(loc) - 1
        if isinstance(current, dict) and isinstance(element, str):
            if element in current:
                path.append(element)
                current = current[element]  # pyright: ignore[reportUnknownVariableType]
            elif last:
                path.append(element)
        elif (
            isinstance(current, list)
            and isinstance(element, int)
            and 0 <= element < len(current)  # pyright: ignore[reportUnknownArgumentType]
        ):
            path.append(element)
            current = current[element]  # pyright: ignore[reportUnknownVariableType]
    return tuple(path)


def _code(error: ErrorDetails, location: tuple[str | int, ...]) -> str:
    if error["type"] == "circuit_identity_duplicate":
        return "circuit.identity-duplicate"
    if location and location[-1] in _IDENTITY_FIELDS:
        return "circuit.identity-invalid"
    if error["type"] in _LIMIT_TYPES:
        return "circuit.limit-exceeded"
    return "circuit.validation-error"


def _issues(error: ValidationError, data: object) -> Iterator[SpecializedIssue]:
    for detail in error.errors(include_url=False, include_input=False):
        location = _location(data, tuple(detail["loc"]))
        if detail["type"] == "circuit_identity_duplicate":
            context = detail.get("ctx") or {}
            location = (str(context["collection"]), int(context["index"]), "id")
        yield _issue(_code(detail, location), detail["msg"], location)


def _bounded(issues: Iterator[SpecializedIssue]) -> tuple[SpecializedIssue, ...]:
    # Une issue de plus que le plafond signale la troncature au socle.
    result: list[SpecializedIssue] = []
    for issue in issues:
        result.append(issue)
        if len(result) > MAX_SPECIALIZED_ISSUES:
            break
    return tuple(result)


def _strict_json(data: bytes) -> tuple[str, object]:
    text = data.decode("utf-8")
    return text, loads_strict_json(text)


class CircuitCodec:
    """Implémente SpecializedResourceCodec[CircuitDocument]."""

    def detect_version(self, data: bytes) -> str | None:
        # Lecture du seul champ format_version, sans validation métier.
        try:
            _, parsed = _strict_json(data)
        except (UnicodeError, ValueError, RecursionError):
            return None
        if isinstance(parsed, dict):
            version = parsed.get("format_version")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            if isinstance(version, str):
                return version
        return None

    def decode(self, data: bytes) -> CircuitDocument:
        try:
            text, parsed = _strict_json(data)
        except UnicodeError:
            raise SpecializedFormatError(
                (_issue("circuit.json-invalid", "UTF-8 attendu."),)
            ) from None
        except (ValueError, RecursionError) as error:
            raise SpecializedFormatError(
                (_issue("circuit.json-invalid", str(error) or "JSON illisible."),)
            ) from None
        try:
            return CircuitDocument.model_validate_json(text)
        except ValidationError as error:
            raise SpecializedFormatError(_bounded(_issues(error, parsed))) from None

    def encode(self, resource: CircuitDocument) -> bytes:
        """Sérialisation canonique : ordre des champs du modèle et des collections."""
        payload = resource.model_dump(mode="json", exclude_none=True)
        text = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
        return (text + "\n").encode("utf-8")

    def validate(self, resource: CircuitDocument) -> SpecializedValidationResult:
        """Niveau structure seulement : revalide une copie sérialisée du modèle."""
        try:
            text = resource.model_dump_json(exclude_none=True)
        except (PydanticSerializationError, AttributeError, TypeError, ValueError):
            return SpecializedValidationResult.bounded(
                (_issue("circuit.validation-error", "Document non sérialisable."),)
            )
        try:
            CircuitDocument.model_validate_json(text)
        except ValidationError as error:
            return SpecializedValidationResult.bounded(_issues(error, json.loads(text)))
        return SpecializedValidationResult(())
