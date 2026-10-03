"""Catalogue Circuit V1 : huit types fermés, contrats explicites, immutabilité."""

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any

import pytest

import forge_design.circuit.catalog as catalog_module
from forge_design.circuit import (
    CIRCUIT_CATALOG,
    CircuitCatalog,
    CircuitComponentDefinition,
    CircuitPropertyDefinition,
    CircuitTerminalDefinition,
)

TYPES = [
    "resistor",
    "dc-source",
    "switch",
    "lamp",
    "led",
    "diode",
    "potentiometer",
    "ground",
]

# (borne, rôle, polarité, direction) par type, dans l'ordre du contrat.
TERMINALS: dict[str, list[tuple[str, str, str, str]]] = {
    "resistor": [("t1", "passive", "none", "W"), ("t2", "passive", "none", "E")],
    "dc-source": [
        ("positive", "source-positive", "positive", "N"),
        ("negative", "source-negative", "negative", "S"),
    ],
    "switch": [("t1", "passive", "none", "W"), ("t2", "passive", "none", "E")],
    "lamp": [("t1", "passive", "none", "W"), ("t2", "passive", "none", "E")],
    "led": [
        ("anode", "anode", "positive", "W"),
        ("cathode", "cathode", "negative", "E"),
    ],
    "diode": [
        ("anode", "anode", "positive", "W"),
        ("cathode", "cathode", "negative", "E"),
    ],
    "potentiometer": [
        ("end1", "passive", "none", "W"),
        ("wiper", "wiper", "none", "N"),
        ("end2", "passive", "none", "E"),
    ],
    "ground": [("ref", "reference", "none", "N")],
}

# (nom, type, unité, minimum, maximum, requise pour la préparation)
PROPERTIES: dict[str, list[tuple[Any, ...]]] = {
    "resistor": [
        ("resistance", "number", "ohm", 0, None, True),
        ("rated_power", "number", "watt", 0, None, False),
    ],
    "dc-source": [
        ("voltage", "number", "volt", None, None, True),
        ("internal_resistance", "number", "ohm", 0, None, False),
    ],
    "switch": [("closed", "boolean", None, None, None, True)],
    "lamp": [
        ("rated_voltage", "number", "volt", 0, None, True),
        ("rated_power", "number", "watt", 0, None, True),
    ],
    "led": [
        ("forward_voltage", "number", "volt", 0, None, True),
        ("nominal_current", "number", "ampere", 0, None, False),
        ("color", "string", None, None, None, False),
    ],
    "diode": [
        ("forward_voltage", "number", "volt", 0, None, True),
        ("max_current", "number", "ampere", 0, None, False),
    ],
    "potentiometer": [
        ("resistance", "number", "ohm", 0, None, True),
        ("position", "number", "ratio", 0, 1, True),
    ],
    "ground": [],
}


def test_exactly_eight_types_in_order() -> None:
    assert CIRCUIT_CATALOG.type_ids == tuple(TYPES)
    assert CIRCUIT_CATALOG.get("junction") is None
    assert CIRCUIT_CATALOG.get("placeholder") is None


@pytest.mark.parametrize("type_id", TYPES)
def test_terminal_contracts(type_id: str) -> None:
    definition = CIRCUIT_CATALOG.get(type_id)
    assert definition is not None and definition.id == type_id
    assert [
        (t.id, t.role, t.polarity, t.direction) for t in definition.terminals
    ] == TERMINALS[type_id]
    for terminal in definition.terminals:
        assert definition.terminal(terminal.id) is terminal
    assert definition.terminal("absent") is None


@pytest.mark.parametrize("type_id", TYPES)
def test_property_contracts(type_id: str) -> None:
    definition = CIRCUIT_CATALOG.get(type_id)
    assert definition is not None
    assert [
        (
            p.name,
            p.value_type,
            p.unit,
            p.minimum,
            p.maximum,
            p.required_for_readiness,
        )
        for p in definition.properties
    ] == PROPERTIES[type_id]


def test_classification_and_symmetry() -> None:
    kinds = {d.id: (d.domain_kind, d.symmetric) for d in CIRCUIT_CATALOG.definitions}
    assert kinds == {
        "resistor": ("resistor", True),
        "dc-source": ("dc-voltage-source", False),
        "switch": ("switch", True),
        "lamp": ("lamp", True),
        "led": ("led", False),
        "diode": ("diode", False),
        "potentiometer": ("potentiometer", False),
        "ground": ("ground-reference", False),
    }


def test_ground_is_a_reference_not_a_source() -> None:
    ground = CIRCUIT_CATALOG.get("ground")
    assert ground is not None
    assert ground.properties == ()
    assert [t.role for t in ground.terminals] == ["reference"]
    assert all(
        t.role not in {"source-positive", "source-negative"} for t in ground.terminals
    )


def test_no_svg_or_drawciel_identifier() -> None:
    source = Path(catalog_module.__file__).read_text()
    assert "<svg" not in source
    for definition in CIRCUIT_CATALOG.definitions:
        assert "__" not in definition.id and not definition.id[0].isdigit()


def test_catalog_is_immutable() -> None:
    definition = CIRCUIT_CATALOG.definitions[0]
    with pytest.raises(FrozenInstanceError):
        definition.id = "x"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        definition.terminals[0].role = "anode"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        CIRCUIT_CATALOG.definitions = ()  # type: ignore[misc]
    with pytest.raises(TypeError):
        CIRCUIT_CATALOG._by_id["x"] = definition  # type: ignore[index]
    assert isinstance(definition.terminals, tuple)
    assert isinstance(definition.properties, tuple)


def _resistor(**changes: Any) -> CircuitComponentDefinition:
    base = CIRCUIT_CATALOG.get("resistor")
    assert base is not None
    return replace(base, **changes)


def test_duplicates_refused() -> None:
    resistor = _resistor()
    with pytest.raises(ValueError, match="Type dupliqué"):
        CircuitCatalog((resistor, resistor))
    with pytest.raises(ValueError, match="borne dupliqué"):
        _resistor(terminals=(resistor.terminals[0], resistor.terminals[0]))
    with pytest.raises(ValueError, match="propriété dupliqué"):
        _resistor(properties=(resistor.properties[0], resistor.properties[0]))


@pytest.mark.parametrize(
    "args",
    [
        ("T1", "passive", "none", "W"),
        ("t1", "free", "none", "W"),
        ("t1", "passive", "plus", "W"),
        ("t1", "anode", "none", "W"),  # polarité incohérente avec le rôle
        ("t1", "passive", "positive", "W"),
        ("t1", "source-negative", "positive", "W"),
        ("t1", "passive", "none", "NE"),
    ],
)
def test_terminal_definition_refused(args: tuple[str, str, str, str]) -> None:
    with pytest.raises(ValueError):
        CircuitTerminalDefinition(*args)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "args",
    [
        ("Resistance", "number", "ohm"),
        ("resistance", "integer", "ohm"),
        ("resistance", "number", None),
        ("resistance", "number", "kiloohm"),
        ("closed", "boolean", "ratio"),
        ("resistance", "number", "ohm", 2, 1),
        ("resistance", "number", "ohm", float("nan")),
        ("resistance", "number", "ohm", None, None, "oui"),
    ],
)
def test_property_definition_refused(args: tuple[Any, ...]) -> None:
    with pytest.raises(ValueError):
        CircuitPropertyDefinition(*args)


@pytest.mark.parametrize(
    "changes",
    [
        {"id": "Resistor"},
        {"id": "03_resistances__resistance"},
        {"name": " "},
        {"domain_kind": "transistor"},
        {"terminals": ()},
        {"terminals": [CircuitTerminalDefinition("t1", "passive", "none", "W")]},
        {"properties": [CircuitPropertyDefinition("x", "string")]},
        {"symmetric": 1},
    ],
)
def test_component_definition_refused(changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        _resistor(**changes)


def test_symmetry_requires_unpolarized_two_terminal() -> None:
    led = CIRCUIT_CATALOG.get("led")
    assert led is not None
    with pytest.raises(ValueError):
        replace(led, symmetric=True)


@pytest.mark.parametrize(
    ("type_id", "name", "value", "accepted"),
    [
        ("resistor", "resistance", 0, True),
        ("resistor", "resistance", 0.0, True),
        ("resistor", "resistance", 1000, True),
        ("resistor", "resistance", -1, False),
        ("resistor", "resistance", "1k", False),
        ("resistor", "resistance", True, False),
        ("resistor", "resistance", float("inf"), False),
        ("dc-source", "voltage", -5.0, True),
        ("dc-source", "voltage", 0, True),
        ("switch", "closed", False, True),
        ("switch", "closed", 0, False),
        ("led", "color", "rouge", True),
        ("led", "color", 1, False),
        ("potentiometer", "position", 0, True),
        ("potentiometer", "position", 1, True),
        ("potentiometer", "position", 1.01, False),
        ("potentiometer", "position", -0.01, False),
    ],
)
def test_property_acceptance(
    type_id: str, name: str, value: object, accepted: bool
) -> None:
    definition = CIRCUIT_CATALOG.get(type_id)
    assert definition is not None
    prop = definition.property_definition(name)
    assert prop is not None and prop.accepts(value) is accepted


def test_resistor_projects_to_two_unambiguous_ports() -> None:
    # Projection conceptuelle vers le Graphic Core : identités et directions seules.
    resistor = CIRCUIT_CATALOG.get("resistor")
    assert resistor is not None
    ports = {t.id: t.direction for t in resistor.terminals}
    assert ports == {"t1": "W", "t2": "E"}
