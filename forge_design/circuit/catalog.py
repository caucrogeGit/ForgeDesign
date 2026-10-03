"""Catalogue Circuit V1 : contrats explicites, fermés et immuables des composants.

Aucune sémantique n'est déduite d'un nom, d'une famille, d'un symbole ou d'un
identifiant historique : rôles, polarités, propriétés et classification sont
déclarés. Le composant n'est pas un symbole : aucun dessin ici, seulement les
métadonnées utiles à la future projection Graphics (direction des ports).
"""

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, get_args

TerminalRole = Literal[
    "passive",
    "source-positive",
    "source-negative",
    "anode",
    "cathode",
    "wiper",
    "reference",
]
Polarity = Literal["positive", "negative", "none"]
PortDirection = Literal["N", "E", "S", "W"]
PropertyValueType = Literal["number", "boolean", "string"]
PropertyUnit = Literal["ohm", "volt", "ampere", "watt", "ratio"]
DomainKind = Literal[
    "resistor",
    "dc-voltage-source",
    "switch",
    "lamp",
    "led",
    "diode",
    "potentiometer",
    "ground-reference",
]

_ROLES = frozenset(get_args(TerminalRole))
_POLARITIES = frozenset(get_args(Polarity))
_DIRECTIONS = frozenset(get_args(PortDirection))
_VALUE_TYPES = frozenset(get_args(PropertyValueType))
_UNITS = frozenset(get_args(PropertyUnit))
_KINDS = frozenset(get_args(DomainKind))
# La polarité est déclarée et doit concorder avec le rôle, jamais avec un ordre.
_ROLE_POLARITY: dict[str, str] = {
    "source-positive": "positive",
    "anode": "positive",
    "source-negative": "negative",
    "cathode": "negative",
}
_TYPE_ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
_TERMINAL_ID = re.compile(r"[a-z][a-z0-9_]*")
_PROPERTY_NAME = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*")


def _is_text(value: object, pattern: re.Pattern[str] | None = None) -> bool:
    if not isinstance(value, str):
        return False
    return bool(value.strip()) if pattern is None else bool(pattern.fullmatch(value))


def _is_bool(value: object) -> bool:
    return isinstance(value, bool)


def _is_finite_number(value: object) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _tuple_of(value: object, kind: type) -> bool:
    return isinstance(value, tuple) and all(
        isinstance(item, kind)
        for item in value  # pyright: ignore[reportUnknownVariableType]
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _unique(names: list[str], what: str) -> None:
    duplicates = sorted({name for name in names if names.count(name) > 1})
    _require(not duplicates, f"{what} dupliqué : {duplicates}")


@dataclass(frozen=True)
class CircuitTerminalDefinition:
    """Borne déclarée par un type ; identité d'instance : (component_id, id)."""

    id: str
    role: TerminalRole
    polarity: Polarity
    direction: PortDirection | None

    def __post_init__(self) -> None:
        _require(
            _is_text(self.id, _TERMINAL_ID),
            f"Identifiant de borne invalide : {self.id!r}",
        )
        _require(self.role in _ROLES, f"Rôle de borne inconnu : {self.role!r}")
        _require(self.polarity in _POLARITIES, f"Polarité inconnue : {self.polarity!r}")
        _require(
            self.polarity == _ROLE_POLARITY.get(self.role, "none"),
            f"Polarité {self.polarity} incohérente avec le rôle {self.role}",
        )
        _require(
            self.direction is None or self.direction in _DIRECTIONS,
            f"Direction de port inconnue : {self.direction!r}",
        )


@dataclass(frozen=True)
class CircuitPropertyDefinition:
    """Propriété autorisée ; valeur en unité SI, absence = clé omise.

    required_for_readiness : son absence produit un avertissement de préparation
    électrique, jamais une valeur par défaut.
    """

    name: str
    value_type: PropertyValueType
    unit: PropertyUnit | None = None
    minimum: float | None = None
    maximum: float | None = None
    required_for_readiness: bool = False

    def __post_init__(self) -> None:
        _require(
            _is_text(self.name, _PROPERTY_NAME),
            f"Nom de propriété invalide : {self.name!r}",
        )
        _require(self.value_type in _VALUE_TYPES, f"Type inconnu : {self.value_type!r}")
        numeric = self.value_type == "number"
        _require(
            (self.unit in _UNITS) if numeric else self.unit is None,
            f"Unité incohérente pour {self.name} : {self.unit!r}",
        )
        for bound in (self.minimum, self.maximum):
            _require(
                bound is None or (numeric and _is_finite_number(bound)),
                f"Borne invalide pour {self.name}",
            )
        if self.minimum is not None and self.maximum is not None:
            _require(self.minimum <= self.maximum, f"Bornes inversées : {self.name}")
        _require(
            _is_bool(self.required_for_readiness),
            "required_for_readiness doit être un booléen.",
        )

    def accepts(self, value: object) -> bool:
        """Type et domaine contractuels ; aucune conversion (ni « 1k », ni chaîne)."""
        if self.value_type == "boolean":
            return isinstance(value, bool)
        if self.value_type == "string":
            return isinstance(value, str)
        if not isinstance(value, int | float) or not _is_finite_number(value):
            return False
        if self.minimum is not None and value < self.minimum:
            return False
        return self.maximum is None or value <= self.maximum


@dataclass(frozen=True)
class CircuitComponentDefinition:
    """Contrat d'un type de composant ; composant ≠ symbole."""

    id: str
    name: str
    domain_kind: DomainKind
    terminals: tuple[CircuitTerminalDefinition, ...]
    properties: tuple[CircuitPropertyDefinition, ...]
    symmetric: bool

    def __post_init__(self) -> None:
        _require(
            _is_text(self.id, _TYPE_ID),
            f"Identifiant de type invalide : {self.id!r}",
        )
        _require(_is_text(self.name), "Nom vide.")
        _require(
            self.domain_kind in _KINDS,
            f"Classification inconnue : {self.domain_kind!r}",
        )
        _require(
            _tuple_of(self.terminals, CircuitTerminalDefinition)
            and bool(self.terminals),
            f"{self.id} : bornes invalides.",
        )
        _require(
            _tuple_of(self.properties, CircuitPropertyDefinition),
            f"{self.id} : propriétés invalides.",
        )
        _unique([t.id for t in self.terminals], f"{self.id} : borne")
        _unique([p.name for p in self.properties], f"{self.id} : propriété")
        _require(_is_bool(self.symmetric), "symmetric doit être un booléen.")
        _require(
            not self.symmetric
            or (
                len(self.terminals) == 2
                and all(t.polarity == "none" for t in self.terminals)
            ),
            f"{self.id} : seul un dipôle non polarisé peut être symétrique.",
        )

    def terminal(self, terminal_id: str) -> CircuitTerminalDefinition | None:
        for terminal in self.terminals:
            if terminal.id == terminal_id:
                return terminal
        return None

    def property_definition(self, name: str) -> CircuitPropertyDefinition | None:
        for definition in self.properties:
            if definition.name == name:
                return definition
        return None


@dataclass(frozen=True)
class CircuitCatalog:
    """Catalogue fermé, construit explicitement ; aucune découverte dynamique."""

    definitions: tuple[CircuitComponentDefinition, ...]
    _by_id: Mapping[str, CircuitComponentDefinition] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        _require(
            _tuple_of(self.definitions, CircuitComponentDefinition),
            "definitions doit être un tuple de CircuitComponentDefinition.",
        )
        _unique([d.id for d in self.definitions], "Type")
        index = MappingProxyType({d.id: d for d in self.definitions})
        object.__setattr__(self, "_by_id", index)

    @property
    def type_ids(self) -> tuple[str, ...]:
        return tuple(d.id for d in self.definitions)

    def get(self, type_id: str) -> CircuitComponentDefinition | None:
        return self._by_id.get(type_id)


def _terminal(
    terminal_id: str, role: TerminalRole, direction: PortDirection | None
) -> CircuitTerminalDefinition:
    polarity: Polarity = _ROLE_POLARITY.get(role, "none")  # type: ignore[assignment]
    return CircuitTerminalDefinition(terminal_id, role, polarity, direction)


def _number(
    name: str,
    unit: PropertyUnit,
    *,
    minimum: float | None = 0,
    maximum: float | None = None,
    required: bool = False,
) -> CircuitPropertyDefinition:
    return CircuitPropertyDefinition(name, "number", unit, minimum, maximum, required)


# Directions : convention de projection future (FD-GRAPHICS-002), dipôles
# horizontaux de gauche (W) à droite (E), source verticale, curseur et masse
# vers le haut. Positions locales précises : non définies ici.
CIRCUIT_CATALOG = CircuitCatalog(
    (
        CircuitComponentDefinition(
            "resistor",
            "Résistance",
            "resistor",
            (_terminal("t1", "passive", "W"), _terminal("t2", "passive", "E")),
            (
                _number("resistance", "ohm", required=True),
                _number("rated_power", "watt"),
            ),
            symmetric=True,
        ),
        CircuitComponentDefinition(
            "dc-source",
            "Source de tension continue",
            "dc-voltage-source",
            (
                _terminal("positive", "source-positive", "N"),
                _terminal("negative", "source-negative", "S"),
            ),
            (
                # Une source peut être réglée à 0 V ou à une tension négative.
                _number("voltage", "volt", minimum=None, required=True),
                _number("internal_resistance", "ohm"),
            ),
            symmetric=False,
        ),
        CircuitComponentDefinition(
            "switch",
            "Interrupteur",
            "switch",
            (_terminal("t1", "passive", "W"), _terminal("t2", "passive", "E")),
            # État de conception persistant ; aucun défaut silencieux.
            (
                CircuitPropertyDefinition(
                    "closed", "boolean", required_for_readiness=True
                ),
            ),
            symmetric=True,
        ),
        CircuitComponentDefinition(
            "lamp",
            "Lampe",
            "lamp",
            (_terminal("t1", "passive", "W"), _terminal("t2", "passive", "E")),
            (
                _number("rated_voltage", "volt", required=True),
                _number("rated_power", "watt", required=True),
            ),
            symmetric=True,
        ),
        CircuitComponentDefinition(
            "led",
            "LED",
            "led",
            (_terminal("anode", "anode", "W"), _terminal("cathode", "cathode", "E")),
            (
                _number("forward_voltage", "volt", required=True),
                _number("nominal_current", "ampere"),
                CircuitPropertyDefinition("color", "string"),
            ),
            symmetric=False,
        ),
        CircuitComponentDefinition(
            "diode",
            "Diode",
            "diode",
            (_terminal("anode", "anode", "W"), _terminal("cathode", "cathode", "E")),
            (
                _number("forward_voltage", "volt", required=True),
                _number("max_current", "ampere"),
            ),
            symmetric=False,
        ),
        CircuitComponentDefinition(
            "potentiometer",
            "Potentiomètre",
            "potentiometer",
            (
                _terminal("end1", "passive", "W"),
                _terminal("wiper", "wiper", "N"),
                _terminal("end2", "passive", "E"),
            ),
            (
                _number("resistance", "ohm", required=True),
                # Fraction de end1 vers end2 ; nécessaire au partage du calcul.
                _number("position", "ratio", maximum=1, required=True),
            ),
            symmetric=False,
        ),
        CircuitComponentDefinition(
            "ground",
            "Masse",
            "ground-reference",
            # Référence de réseau : ne génère ni tension ni énergie.
            (_terminal("ref", "reference", "N"),),
            (),
            symmetric=False,
        ),
    )
)
