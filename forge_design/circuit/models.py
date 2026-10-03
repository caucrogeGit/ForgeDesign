"""Modèles structurels de la ressource Circuit V0.1, sans catalogue ni topologie.

Les formes ``position``, ``rotation``, extrémités et ``route`` (points
intermédiaires seulement) suivent les conventions de champs du Graphic Core ;
le document reste propriétaire de son schéma et de sa sémantique. Aucune
existence de type, de borne ou de jonction référencée n'est vérifiée ici.
"""

from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import Annotated, Literal, TypeVar

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    model_validator,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import PydanticCustomError

from forge_design.circuit.ids import CircuitIdKind, id_pattern
from forge_design.circuit.limits import (
    MAX_CIRCUIT_ANNOTATIONS,
    MAX_CIRCUIT_COMPONENTS,
    MAX_CIRCUIT_CONNECTIONS,
    MAX_CIRCUIT_ID_CHARS,
    MAX_CIRCUIT_JUNCTIONS,
    MAX_CIRCUIT_PAGE_UNITS,
    MAX_CIRCUIT_PROPERTIES,
    MAX_CIRCUIT_PROPERTY_KEY_CHARS,
    MAX_CIRCUIT_PROPERTY_TEXT_CHARS,
    MAX_CIRCUIT_REFERENCE_CHARS,
    MAX_CIRCUIT_ROUTE_POINTS,
    MAX_CIRCUIT_SAFE_INTEGER,
    MAX_CIRCUIT_TERMINAL_ID_CHARS,
    MAX_CIRCUIT_TEXT_CHARS,
    MAX_CIRCUIT_TYPE_CHARS,
)

FORMAT_VERSION = "0.1"
DEFAULT_PAGE_WIDTH = 80
DEFAULT_PAGE_HEIGHT = 60

_T = TypeVar("_T")
# Texte sur une ligne : aucun caractère de contrôle.
_LINE = r"^[^\x00-\x1f\x7f]+$"
# Texte multiligne : saut de ligne LF et tabulation seuls caractères de contrôle.
_MULTILINE = r"^[^\x00-\x08\x0b-\x1f\x7f]+$"
_TYPE = r"^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$"
_TERMINAL = r"^[a-z][a-z0-9_]*$"
_PROPERTY_KEY = r"^[A-Za-z][A-Za-z0-9_]*$"


def _reject_null(value: object) -> object:
    if value is None:
        raise ValueError("Omit the property instead of providing null")
    return value


def _omission_schema(schema: JsonSchemaValue) -> None:
    # None n'est que le défaut Python interne ; null fourni est refusé.
    schema.pop("default", None)
    for branch in schema.pop("anyOf", []):
        if branch != {"type": "null"}:
            schema.update(branch)


_Omissible = Annotated[
    _T | None, BeforeValidator(_reject_null), Field(json_schema_extra=_omission_schema)
]


def _id(kind: CircuitIdKind) -> object:
    return Field(max_length=MAX_CIRCUIT_ID_CHARS, pattern=id_pattern(kind))


_Coordinate = Annotated[int, Field(ge=0, le=MAX_CIRCUIT_PAGE_UNITS)]
_Dimension = Annotated[int, Field(ge=1, le=MAX_CIRCUIT_PAGE_UNITS)]
_SafeInt = Annotated[
    int, Field(ge=-MAX_CIRCUIT_SAFE_INTEGER, le=MAX_CIRCUIT_SAFE_INTEGER)
]
_PropertyText = Annotated[
    str,
    Field(min_length=1, max_length=MAX_CIRCUIT_PROPERTY_TEXT_CHARS, pattern=_MULTILINE),
]


def _reject_integer(value: object) -> object:
    # Un entier JSON n'est jamais converti en flottant (perte de précision au-delà
    # des entiers sûrs) ; seul un nombre décimal alimente la branche flottante.
    if isinstance(value, int):
        raise ValueError("Integer outside the safe range is not converted to float")
    return value


def _require_int(value: object) -> object:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("Rotation must be an integer")
    return value


_Decimal = Annotated[float, BeforeValidator(_reject_integer)]
PropertyValue = _PropertyText | bool | _SafeInt | _Decimal
_PropertyKey = Annotated[
    str,
    Field(
        min_length=1, max_length=MAX_CIRCUIT_PROPERTY_KEY_CHARS, pattern=_PROPERTY_KEY
    ),
]


def _freeze(value: Mapping[str, PropertyValue]) -> Mapping[str, PropertyValue]:
    return MappingProxyType(dict(value))


def _thaw(value: Mapping[str, PropertyValue]) -> dict[str, PropertyValue]:
    return dict(value)


CircuitProperties = Annotated[
    Mapping[_PropertyKey, PropertyValue],
    Field(
        max_length=MAX_CIRCUIT_PROPERTIES,
        json_schema_extra={"additionalProperties": False},
    ),
    AfterValidator(_freeze),
    PlainSerializer(_thaw),
]


class _CircuitModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, allow_inf_nan=False
    )


class CircuitPoint(_CircuitModel):
    """Point de grille ; même forme que le futur Point du Graphic Core."""

    x: _Coordinate
    y: _Coordinate


class CircuitPage(_CircuitModel):
    width: _Dimension
    height: _Dimension


class CircuitComponent(_CircuitModel):
    """Instance d'un type ; les bornes appartiennent au type, jamais à l'instance."""

    id: Annotated[str, _id("component")]
    type: Annotated[
        str, Field(min_length=1, max_length=MAX_CIRCUIT_TYPE_CHARS, pattern=_TYPE)
    ]
    reference: _Omissible[
        Annotated[
            str,
            Field(min_length=1, max_length=MAX_CIRCUIT_REFERENCE_CHARS, pattern=_LINE),
        ]
    ] = None
    position: CircuitPoint
    rotation: Annotated[Literal[0, 90, 180, 270], BeforeValidator(_require_int)]
    properties: CircuitProperties


class TerminalEndpoint(_CircuitModel):
    kind: Literal["terminal"]
    component_id: Annotated[str, _id("component")]
    terminal_id: Annotated[
        str,
        Field(
            min_length=1, max_length=MAX_CIRCUIT_TERMINAL_ID_CHARS, pattern=_TERMINAL
        ),
    ]


class JunctionEndpoint(_CircuitModel):
    kind: Literal["junction"]
    junction_id: Annotated[str, _id("junction")]


CircuitEndpoint = Annotated[
    TerminalEndpoint | JunctionEndpoint, Field(discriminator="kind")
]


class CircuitRoute(_CircuitModel):
    """Présentation : points intermédiaires seulement, extrémités dérivées."""

    mode: Literal["orthogonal"]
    points: Annotated[
        tuple[CircuitPoint, ...], Field(max_length=MAX_CIRCUIT_ROUTE_POINTS)
    ]


class CircuitConnection(_CircuitModel):
    id: Annotated[str, _id("connection")]
    a: CircuitEndpoint
    b: CircuitEndpoint
    route: CircuitRoute


class CircuitJunction(_CircuitModel):
    id: Annotated[str, _id("junction")]
    position: CircuitPoint


class CircuitTextAnnotation(_CircuitModel):
    id: Annotated[str, _id("annotation")]
    kind: Literal["text"]
    position: CircuitPoint
    text: Annotated[
        str, Field(min_length=1, max_length=MAX_CIRCUIT_TEXT_CHARS, pattern=_MULTILINE)
    ]


_COLLECTIONS = ("components", "connections", "junctions", "annotations")


class CircuitDocument(_CircuitModel):
    """Seule source de vérité persistante.

    L'ordre des collections est conservé mais n'est jamais une identité.
    """

    format_version: Literal["0.1"]
    page: CircuitPage
    components: Annotated[
        tuple[CircuitComponent, ...], Field(max_length=MAX_CIRCUIT_COMPONENTS)
    ]
    connections: Annotated[
        tuple[CircuitConnection, ...], Field(max_length=MAX_CIRCUIT_CONNECTIONS)
    ]
    junctions: Annotated[
        tuple[CircuitJunction, ...], Field(max_length=MAX_CIRCUIT_JUNCTIONS)
    ]
    annotations: Annotated[
        tuple[CircuitTextAnnotation, ...], Field(max_length=MAX_CIRCUIT_ANNOTATIONS)
    ]

    @model_validator(mode="after")
    def _unique_identities(self) -> "CircuitDocument":
        duplicate = first_duplicate_identity(
            (name, tuple(item.id for item in getattr(self, name)))
            for name in _COLLECTIONS
        )
        if duplicate is not None:
            identity, first, (collection, index) = duplicate
            raise PydanticCustomError(
                "circuit_identity_duplicate",
                "Identity {identity} already used at {first}",
                {
                    "identity": identity,
                    "first": f"{first[0]}[{first[1]}]",
                    "collection": collection,
                    "index": index,
                },
            )
        return self


IdentityPlace = tuple[str, int]


def first_duplicate_identity(
    groups: Iterable[tuple[str, tuple[str, ...]]],
) -> tuple[str, IdentityPlace, IdentityPlace] | None:
    """Premier doublon dans l'espace de noms global, toutes collections confondues.

    O(n) ; retourne l'identité, son premier emplacement et le doublon.
    """
    seen: dict[str, IdentityPlace] = {}
    for collection, identities in groups:
        for index, identity in enumerate(identities):
            if identity in seen:
                return identity, seen[identity], (collection, index)
            seen[identity] = (collection, index)
    return None


def new_circuit_document() -> CircuitDocument:
    """Document V0.1 vide : page par défaut, aucune donnée utilisateur ou machine."""
    return CircuitDocument(
        format_version=FORMAT_VERSION,
        page=CircuitPage(width=DEFAULT_PAGE_WIDTH, height=DEFAULT_PAGE_HEIGHT),
        components=(),
        connections=(),
        junctions=(),
        annotations=(),
    )
