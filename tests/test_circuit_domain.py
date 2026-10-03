"""Structure de domaine : types connus, propriétés autorisées, aucune mutation."""

import copy
from typing import Any

import pytest
from circuit_support import CIRCUIT, circuit, circuit_document, sample_document

from forge_design.circuit import CIRCUIT_CATALOG, validate_circuit
from forge_design.circuit.domain import domain_structure_issues


def _structure(data: dict[str, Any]) -> list[tuple[str, tuple[Any, ...]]]:
    issues = domain_structure_issues(circuit_document(data), CIRCUIT_CATALOG)
    result = [(i.code, i.location) for i in issues]
    assert all(code.startswith("circuit.") for code, _ in result)
    return result


def test_valid_circuit_has_no_structure_issue() -> None:
    assert _structure(CIRCUIT) == []


def test_unknown_type() -> None:
    data = circuit()
    data["components"][2]["type"] = "transistor"
    assert _structure(data) == [
        ("circuit.unknown-component-type", ("components", 2, "type"))
    ]


def test_format_valid_document_is_domain_invalid() -> None:
    # Format V0.1 valide (placeholder) mais structure de domaine invalide.
    result = validate_circuit(sample_document())
    codes = [(i.code, i.level, i.severity) for i in result.issues]
    assert ("circuit.unknown-component-type", "structure", "error") in codes


def test_unknown_property() -> None:
    data = circuit()
    data["components"][2]["properties"]["resistanceOhms"] = 220
    assert _structure(data) == [
        ("circuit.unknown-property", ("components", 2, "properties", "resistanceOhms"))
    ]


@pytest.mark.parametrize(
    "key", ["voltage", "current", "temperature", "simulation_state"]
)
def test_runtime_property_refused(key: str) -> None:
    # Ferme la limite documentée par FD-CIRCUIT-002 : allowlist par type.
    data = circuit()
    data["components"][2]["properties"][key] = 1.5
    assert _structure(data) == [
        ("circuit.unknown-property", ("components", 2, "properties", key))
    ]


def test_voltage_is_allowed_only_where_declared() -> None:
    data = circuit()
    assert "voltage" in data["components"][0]["properties"]
    assert _structure(data) == []


@pytest.mark.parametrize(
    ("index", "name", "value"),
    [
        (2, "resistance", "1k"),
        (2, "resistance", -1),
        (2, "resistance", True),
        (1, "closed", "true"),
        (1, "closed", 1),
        (3, "color", 2),
        (3, "forward_voltage", -0.5),
    ],
)
def test_invalid_property(index: int, name: str, value: object) -> None:
    data = circuit()
    data["components"][index]["properties"][name] = value
    assert _structure(data) == [
        ("circuit.invalid-property", ("components", index, "properties", name))
    ]


@pytest.mark.parametrize("value", [0, 0.0])
def test_zero_is_a_value(value: float) -> None:
    data = circuit()
    data["components"][2]["properties"]["resistance"] = value
    data["components"][0]["properties"]["voltage"] = value
    assert _structure(data) == []
    issues = validate_circuit(circuit_document(data)).issues
    assert not any(i.code == "circuit.missing-property" for i in issues)


def test_potentiometer_position_domain() -> None:
    data = circuit()
    data["components"].append(
        {
            "id": "c_potentio01",
            "type": "potentiometer",
            "position": {"x": 0, "y": 0},
            "rotation": 0,
            "properties": {"resistance": 10000.0, "position": 1.5},
        }
    )
    assert _structure(data) == [
        ("circuit.invalid-property", ("components", 5, "properties", "position"))
    ]


def test_issues_follow_document_order() -> None:
    data = circuit()
    data["components"][3]["type"] = "x"
    data["components"][1]["properties"]["bad"] = 1
    data["components"][1]["properties"]["closed"] = "oui"
    assert _structure(data) == [
        ("circuit.invalid-property", ("components", 1, "properties", "closed")),
        ("circuit.unknown-property", ("components", 1, "properties", "bad")),
        ("circuit.unknown-component-type", ("components", 3, "type")),
    ]


def test_validator_is_pure() -> None:
    data = circuit()
    data["components"][2]["properties"] = {}
    document = circuit_document(data)
    snapshot = copy.deepcopy(document.model_dump(mode="json"))
    first = validate_circuit(document)
    assert validate_circuit(document) == first
    assert document.model_dump(mode="json") == snapshot
    assert "resistance" not in document.components[2].properties


def test_no_property_is_invented() -> None:
    data = circuit()
    for component in data["components"]:
        component["properties"] = {}
    document = circuit_document(data)
    validate_circuit(document)
    assert all(dict(c.properties) == {} for c in document.components)
