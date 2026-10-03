"""Validation complète : préparation électrique, blocage de l'écriture, bornage."""

from pathlib import Path
from typing import Any

import pytest
from circuit_support import (
    BAT,
    CIRCUIT,
    GND,
    RES,
    circuit,
    circuit_document,
    component,
    make_project,
    terminal,
)

from forge_design.circuit import (
    CIRCUIT_RESOURCE_TYPE,
    CIRCUIT_TOOL,
    CircuitCodec,
    CircuitDocument,
    validate_circuit,
)
from forge_design.limits import MAX_SPECIALIZED_ISSUES
from forge_design.specialized import (
    InvalidSpecializedResourceError,
    read_specialized_resource,
    write_specialized_resource,
)

PATH = "mvc/circuit/led/simple.circuit.json"


def _issues(data: dict[str, Any]) -> list[tuple[str, str, str, tuple[Any, ...]]]:
    result = validate_circuit(circuit_document(data))
    return [(i.code, i.level, i.severity, i.location) for i in result.issues]


def _readiness(data: dict[str, Any]) -> list[tuple[str, tuple[Any, ...]]]:
    return [
        (code, location)
        for code, level, severity, location in _issues(data)
        if level == "electrical-readiness" and severity == "warning"
    ]


def test_complete_circuit_has_no_diagnostic() -> None:
    assert _issues(CIRCUIT) == []


def test_empty_document_has_no_diagnostic() -> None:
    assert _issues(circuit(components=[], connections=[], junctions=[])) == []


def test_resistor_without_value() -> None:
    data = circuit()
    del data["components"][2]["properties"]["resistance"]
    assert _readiness(data) == [
        ("circuit.missing-property", ("components", 2, "properties", "resistance"))
    ]


def test_optional_property_absence_is_silent() -> None:
    data = circuit()
    del data["components"][2]["properties"]["rated_power"]
    del data["components"][3]["properties"]["color"]
    assert _issues(data) == []


def test_switch_state_is_required_not_defaulted() -> None:
    data = circuit()
    data["components"][1]["properties"] = {}
    assert _readiness(data) == [
        ("circuit.missing-property", ("components", 1, "properties", "closed"))
    ]
    assert dict(circuit_document(data).components[1].properties) == {}


def test_open_switch_is_a_valid_design_state() -> None:
    data = circuit()
    data["components"][1]["properties"]["closed"] = False
    assert _issues(data) == []


def test_potentiometer_position_is_required() -> None:
    data = circuit()
    data["components"].append(
        component("c_potentio01", "potentiometer", {"resistance": 1000.0})
    )
    readiness = _readiness(data)
    assert readiness[0] == (
        "circuit.missing-property",
        ("components", 5, "properties", "position"),
    )
    assert readiness[1:] == [("circuit.unconnected-terminal", ("components", 5))] * 3


def test_unconnected_terminal() -> None:
    data = circuit()
    data["connections"] = [c for c in data["connections"] if c["id"] != "e_wire000003"]
    assert _readiness(data) == [
        ("circuit.unconnected-terminal", ("components", 2)),
        ("circuit.unconnected-terminal", ("components", 3)),
    ]


def test_missing_ground() -> None:
    data = circuit()
    data["components"] = [c for c in data["components"] if c["id"] != GND]
    data["connections"] = [c for c in data["connections"] if c["id"] != "e_wire000006"]
    assert _readiness(data) == [("circuit.missing-ground", ())]


def test_shorted_source() -> None:
    data = circuit()
    data["connections"].append(
        {
            "id": "e_short00001",
            "a": terminal(BAT, "positive"),
            "b": terminal(GND, "ref"),
            "route": {"mode": "orthogonal", "points": []},
        }
    )
    assert _readiness(data) == [("circuit.source-shorted", ("components", 0))]


def test_led_orientation_is_not_judged() -> None:
    data = circuit()
    led = data["connections"][2]
    led["b"]["terminal_id"] = "cathode"
    data["connections"][3]["a"]["terminal_id"] = "anode"
    assert _issues(data) == []


def test_level_order_is_structure_topology_readiness() -> None:
    data = circuit()
    data["components"][2]["properties"] = {"resistance": "1k"}
    data["connections"][0]["a"]["component_id"] = "c_unknown001"
    data["components"][3]["properties"].pop("forward_voltage")
    levels = [level for _, level, _, _ in _issues(data)]
    assert levels == sorted(
        levels, key=["structure", "topology", "electrical-readiness"].index
    )
    assert levels[0] == "structure" and "topology" in levels


def test_diagnostics_are_bounded_and_truncated() -> None:
    components = [component(f"c_r{i:09d}", "resistor", {}) for i in range(400)]
    data = circuit(components=components, connections=[], junctions=[])
    result = validate_circuit(circuit_document(data))
    assert len(result.issues) == MAX_SPECIALIZED_ISSUES and result.truncated


def test_codec_validate_uses_domain_validator() -> None:
    data = circuit()
    data["components"][2]["properties"]["voltage"] = 1.0
    [issue] = CircuitCodec().validate(circuit_document(data)).issues
    assert issue.code == "circuit.unknown-property" and issue.level == "structure"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return make_project(tmp_path / "projet")


def _write(root: Path, document: CircuitDocument) -> Any:
    return write_specialized_resource(
        root,
        CIRCUIT_TOOL,
        CIRCUIT_RESOURCE_TYPE,
        PATH,
        document,
        CircuitCodec(),
        expected_revision=None,
    )


def test_incomplete_schematic_is_saved(root: Path) -> None:
    data = circuit()
    del data["components"][2]["properties"]["resistance"]
    data["components"].append(component("c_lonely0001", "lamp", {}))
    document = circuit_document(data)
    assert _write(root, document).created
    result = read_specialized_resource(
        root, CIRCUIT_TOOL, CIRCUIT_RESOURCE_TYPE, PATH, CircuitCodec()
    )
    assert result.error is None and result.resource == document
    assert {i.level for i in result.issues} == {"electrical-readiness"}


@pytest.mark.parametrize(
    ("in_properties", "key", "value"),
    [
        (False, "type", "transistor"),
        (True, "resistance", "1k"),
        (True, "voltage", 3.0),
    ],
)
def test_structure_error_blocks_write(
    root: Path, in_properties: bool, key: str, value: object
) -> None:
    data = circuit()
    resistor = data["components"][2]
    (resistor["properties"] if in_properties else resistor)[key] = value
    with pytest.raises(InvalidSpecializedResourceError) as caught:
        _write(root, circuit_document(data))
    assert {i.level for i in caught.value.issues if i.severity == "error"} == {
        "structure"
    }
    assert not (root / PATH).exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [("component_id", "c_unknown001"), ("terminal_id", "anode")],
)
def test_topology_error_blocks_write(root: Path, field: str, value: str) -> None:
    data = circuit()
    data["connections"][1]["a"][field] = value
    with pytest.raises(InvalidSpecializedResourceError) as caught:
        _write(root, circuit_document(data))
    assert [i.level for i in caught.value.issues if i.severity == "error"] == [
        "topology"
    ]
    assert not (root / PATH).exists()


def test_topology_warning_does_not_block_write(root: Path) -> None:
    data = circuit()
    data["connections"].append(
        {
            "id": "e_dup000001",
            "a": terminal(RES, "t2"),
            "b": terminal("c_ledlamp001", "anode"),
            "route": {"mode": "orthogonal", "points": []},
        }
    )
    assert _write(root, circuit_document(data)).created


def test_read_reports_blocking_domain_error(root: Path) -> None:
    data = circuit()
    data["components"][2]["type"] = "transistor"
    (root / PATH).write_bytes(CircuitCodec().encode(circuit_document(data)))
    result = read_specialized_resource(
        root, CIRCUIT_TOOL, CIRCUIT_RESOURCE_TYPE, PATH, CircuitCodec()
    )
    assert result.error == "invalid-resource"
    assert result.resource is not None
    assert result.issues[0].code == "circuit.unknown-component-type"
