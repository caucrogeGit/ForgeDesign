"""Modèles Circuit V0.1 : structure stricte, identités et conventions Graphics."""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from circuit_support import A1, E1, E2, J1, LED, R1, SAMPLE, sample, sample_document
from pydantic import ValidationError

import forge_design.circuit as circuit
from forge_design.circuit import (
    CircuitDocument,
    CircuitPoint,
    JunctionEndpoint,
    TerminalEndpoint,
    new_annotation_id,
    new_circuit_document,
    new_component_id,
    new_connection_id,
    new_junction_id,
)
from forge_design.circuit.ids import CircuitIdKind, is_circuit_id
from forge_design.circuit.limits import (
    MAX_CIRCUIT_ID_CHARS,
    MAX_CIRCUIT_PROPERTIES,
    MAX_CIRCUIT_SAFE_INTEGER,
)
from forge_design.circuit.models import first_duplicate_identity


def _validate(data: dict[str, Any]) -> CircuitDocument:
    return CircuitDocument.model_validate_json(json.dumps(data))


def _errors(data: dict[str, Any]) -> list[tuple[str, tuple[Any, ...]]]:
    with pytest.raises(ValidationError) as caught:
        _validate(data)
    return [(e["type"], tuple(e["loc"])) for e in caught.value.errors()]


def test_empty_document() -> None:
    document = new_circuit_document()
    assert document.format_version == "0.1"
    assert (document.page.width, document.page.height) == (80, 60)
    assert document.components == document.connections == ()
    assert document.junctions == document.annotations == ()
    dumped = document.model_dump(mode="json", exclude_none=True)
    assert set(dumped) == {
        "format_version",
        "page",
        "components",
        "connections",
        "junctions",
        "annotations",
    }


def test_sample_is_valid_and_frozen() -> None:
    document = sample_document()
    assert isinstance(document.components, tuple)
    assert isinstance(document.connections[0].route.points, tuple)
    with pytest.raises(ValidationError):
        document.page = document.page  # type: ignore[misc]
    with pytest.raises(ValidationError):
        document.components[0].rotation = 0  # type: ignore[misc]
    properties = document.components[0].properties
    with pytest.raises(TypeError):
        properties["resistanceOhms"] = 1  # type: ignore[index]
    assert dict(properties)["resistanceOhms"] == 220
    assert document.model_dump(mode="json", exclude_none=True) == SAMPLE


def test_python_construction_requires_tuples() -> None:
    data = sample()
    with pytest.raises(ValidationError):
        CircuitDocument.model_validate(data)


@pytest.mark.parametrize(
    "point",
    [
        {"x": 1.0, "y": 0},
        {"x": True, "y": 0},
        {"x": "1", "y": 0},
        {"x": -1, "y": 0},
        {"x": 4097, "y": 0},
        {"x": 0},
        {"x": 0, "y": 0, "z": 0},
        {"x": None, "y": 0},
    ],
)
def test_point_is_strict_integer(point: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        CircuitPoint.model_validate_json(json.dumps(point))


@pytest.mark.parametrize("page", [{"width": 0, "height": 1}, {"width": 1}])
def test_page_bounds(page: dict[str, Any]) -> None:
    assert _errors(sample(page=page))


@pytest.mark.parametrize("rotation", [45, 360, -90, 90.0, True, False, "90", None])
def test_rotation_quarter_turns_only(rotation: object) -> None:
    data = sample()
    data["components"][0]["rotation"] = rotation
    assert _errors(data)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_rotation_accepted(rotation: int) -> None:
    data = sample()
    data["components"][0]["rotation"] = rotation
    assert _validate(data).components[0].rotation == rotation


@pytest.mark.parametrize(
    "value",
    [None, {"a": 1}, [1], float("nan"), "", "a\x00b", MAX_CIRCUIT_SAFE_INTEGER + 1],
)
def test_property_values_refused(value: object) -> None:
    data = sample()
    data["components"][0]["properties"] = {"k": value}
    text = json.dumps(data, allow_nan=True)
    with pytest.raises(ValidationError):
        CircuitDocument.model_validate_json(text)


@pytest.mark.parametrize(
    "value", ["Ω", True, 0, -MAX_CIRCUIT_SAFE_INTEGER, 1.5, -0.0, 1.0, "a\nb"]
)
def test_property_values_accepted(value: object) -> None:
    data = sample()
    data["components"][0]["properties"] = {"k": value}
    stored = _validate(data).components[0].properties["k"]
    assert stored == value and type(stored) is type(value)


@pytest.mark.parametrize("key", ["", "1k", "a-b", "a.b", "é", "k" * 65])
def test_property_keys_refused(key: str) -> None:
    data = sample()
    data["components"][0]["properties"] = {key: 1}
    assert _errors(data)


def test_properties_count_limit() -> None:
    data = sample()
    data["components"][0]["properties"] = {
        f"k{i}": i for i in range(MAX_CIRCUIT_PROPERTIES)
    }
    _validate(data)
    data["components"][0]["properties"]["extra"] = 1
    assert ("too_long", ("components", 0, "properties")) in _errors(data)


def test_reference_is_omitted_not_null() -> None:
    document = sample_document()
    assert document.components[1].reference is None
    dumped = document.model_dump(mode="json", exclude_none=True)
    assert "reference" not in dumped["components"][1]
    data = sample()
    data["components"][1]["reference"] = None
    assert _errors(data)
    for bad in ("", "R\t1", "R" * 33):
        data["components"][1]["reference"] = bad
        assert _errors(data)


@pytest.mark.parametrize("bad_type", ["", "Resistor", "1r", "a b", "r--x", "x" * 65])
def test_type_is_lexical_only(bad_type: str) -> None:
    data = sample()
    data["components"][0]["type"] = bad_type
    assert _errors(data)


def test_unknown_type_is_structurally_valid() -> None:
    data = sample()
    data["components"][0]["type"] = "not-yet-in-catalogue"
    _validate(data)


@pytest.mark.parametrize(
    ("path", "field"),
    [
        ((), "viewport"),
        ((), "selection"),
        ((), "history"),
        ((), "simulation"),
        ((), "dirty"),
        ((), "nets"),
        ((), "tp"),
        (("components", 0), "voltage"),
        (("components", 0), "current"),
        (("components", 0), "temperature"),
        (("components", 0), "terminals"),
        (("components", 0), "state"),
        (("connections", 0), "net"),
        (("connections", 0, "route"), "start"),
        (("connections", 0, "route"), "end"),
        (("junctions", 0), "degree"),
        (("junctions", 0), "type"),
        (("annotations", 0), "html"),
        (("page",), "zoom"),
    ],
)
def test_extra_fields_refused(path: tuple[Any, ...], field: str) -> None:
    data = sample()
    target: Any = data
    for part in path:
        target = target[part]
    target[field] = 1
    assert ("extra_forbidden", (*path, field)) in _errors(data)


def test_runtime_like_property_keys_are_format_valid() -> None:
    # Le format ne connaît pas le catalogue : l'allowlist par type (FD-CIRCUIT-003)
    # refuse ces clés au niveau domaine (tests/test_circuit_domain.py).
    data = sample()
    data["components"][0]["properties"] = {"simulation_state": "x", "voltage": 1.5}
    assert _validate(data).components[0].properties["voltage"] == 1.5


def test_endpoints_are_discriminated() -> None:
    document = sample_document()
    first = document.connections[0]
    assert isinstance(first.a, TerminalEndpoint)
    assert isinstance(first.b, JunctionEndpoint)
    data = sample()
    data["connections"][0]["a"] = {"kind": "port", "component_id": R1}
    assert _errors(data)
    data = sample()
    data["connections"][0]["a"] = {
        "kind": "junction",
        "component_id": R1,
        "terminal_id": "t1",
    }
    assert _errors(data)


@pytest.mark.parametrize("terminal", ["", "T1", "1a", "a-b", "a b", "x" * 65])
def test_terminal_id_is_lexical(terminal: str) -> None:
    data = sample()
    data["connections"][0]["a"]["terminal_id"] = terminal
    assert _errors(data)


def test_connection_has_exactly_two_endpoints() -> None:
    data = sample()
    del data["connections"][0]["b"]
    assert _errors(data)
    data = sample()
    data["connections"][0]["c"] = data["connections"][0]["a"]
    assert _errors(data)


def test_self_connection_is_structurally_representable() -> None:
    data = sample()
    data["connections"][0]["b"] = data["connections"][0]["a"]
    _validate(data)


def test_route_mode_and_points() -> None:
    data = sample()
    data["connections"][0]["route"]["mode"] = "straight"
    assert _errors(data)
    data = sample()
    data["connections"][0]["route"]["points"] = [{"x": 1.5, "y": 0}]
    assert _errors(data)
    data = sample()
    # Non orthogonal et colinéaire : validé au niveau géométrique ultérieur.
    data["connections"][0]["route"]["points"] = [
        {"x": 1, "y": 1},
        {"x": 2, "y": 3},
        {"x": 2, "y": 3},
    ]
    _validate(data)


def test_annotation_text() -> None:
    data = sample()
    data["annotations"][0]["kind"] = "shape"
    assert _errors(data)
    for bad in ("", "a\rb", "a\x07b"):
        data = sample()
        data["annotations"][0]["text"] = bad
        assert _errors(data)
    data = sample()
    data["annotations"][0]["text"] = "<b>brut</b> **non interprété**"
    assert _validate(data).annotations[0].text.startswith("<b>")


@pytest.mark.parametrize(
    ("collection", "value"),
    [
        ("components", "e_resistor01"),
        ("components", "c_short"),
        ("components", "c_" + "x" * 65),
        ("components", "c_bad token!"),
        ("components", "C_resistor01"),
        ("connections", "c_connect001"),
        ("junctions", "a_junction01"),
        ("annotations", "j_annotate01"),
    ],
)
def test_identity_format_by_kind(collection: str, value: str) -> None:
    data = sample()
    data[collection][0]["id"] = value
    assert "string_pattern_mismatch" in {
        t for t, _ in _errors(data)
    } or "string_too_long" in {t for t, _ in _errors(data)}


@pytest.mark.parametrize(
    ("side", "key", "value"),
    [("a", "component_id", J1), ("b", "junction_id", R1)],
)
def test_endpoint_identity_kind(side: str, key: str, value: str) -> None:
    data = sample()
    data["connections"][0][side][key] = value
    assert _errors(data)


def test_identity_duplicate_same_kind() -> None:
    data = sample()
    data["components"][1]["id"] = R1
    [(kind, loc)] = _errors(data)
    assert kind == "circuit_identity_duplicate" and loc == ()


def test_identity_missing_is_refused_not_generated() -> None:
    data = sample()
    del data["junctions"][0]["id"]
    assert ("missing", ("junctions", 0, "id")) in _errors(data)


def test_global_namespace_spans_collections() -> None:
    document = sample_document()
    ids = [
        item.id
        for collection in (
            document.components,
            document.connections,
            document.junctions,
            document.annotations,
        )
        for item in collection
    ]
    assert ids == [R1, LED, E1, E2, J1, A1]
    # Les préfixes rendent une collision inter-genres impossible à exprimer.
    pairs: tuple[tuple[CircuitIdKind, str], ...] = (
        ("component", "c_"),
        ("junction", "j_"),
    )
    for kind, prefix in pairs:
        assert not is_circuit_id(kind, "e_" + R1[2:])
        assert is_circuit_id(kind, prefix + "abcdefgh")


def test_identity_namespace_is_global_across_collections() -> None:
    # Les préfixes empêchent d'exprimer une collision inter-genres dans un
    # document ; la règle d'unicité reste néanmoins globale par construction.
    groups = (("components", ("x", "y")), ("junctions", ("z", "x")))
    assert first_duplicate_identity(groups) == (
        "x",
        ("components", 0),
        ("junctions", 1),
    )
    assert first_duplicate_identity((("components", ("x",)), ("a", ()))) is None
    assert first_duplicate_identity((("components", ("x", "x")),)) == (
        "x",
        ("components", 0),
        ("components", 1),
    )


def test_generated_ids() -> None:
    generators: dict[CircuitIdKind, Callable[[], str]] = {
        "component": new_component_id,
        "connection": new_connection_id,
        "junction": new_junction_id,
        "annotation": new_annotation_id,
    }
    seen: set[str] = set()
    for kind, generate in generators.items():
        for _ in range(2000):
            value = generate()
            assert is_circuit_id(kind, value)
            assert len(value) == 18 <= MAX_CIRCUIT_ID_CHARS
            assert re.fullmatch(r"[a-z]_[A-Za-z0-9_-]{16}", value)
            seen.add(value)
    assert len(seen) == 8000


def test_index_is_not_identity() -> None:
    data = sample()
    data["components"].reverse()
    reordered = _validate(data)
    assert [c.id for c in reordered.components] == [LED, R1]
    assert reordered != sample_document()


def test_public_api() -> None:
    assert set(circuit.__all__) >= {
        "CircuitDocument",
        "CircuitPage",
        "CircuitPoint",
        "CircuitComponent",
        "CircuitRoute",
        "CircuitConnection",
        "CircuitJunction",
        "CircuitTextAnnotation",
        "TerminalEndpoint",
        "JunctionEndpoint",
        "CircuitCodec",
        "CIRCUIT_TOOL",
        "CIRCUIT_RESOURCE_TYPE",
        "new_circuit_document",
        "new_component_id",
        "new_connection_id",
        "new_junction_id",
        "new_annotation_id",
        "CircuitCatalog",
        "CircuitComponentDefinition",
        "CircuitTerminalDefinition",
        "CircuitPropertyDefinition",
        "CIRCUIT_CATALOG",
        "CircuitTopology",
        "CircuitNet",
        "TerminalRef",
        "validate_circuit",
        "build_circuit_topology",
    }
    for absent in (
        "GraphicScene",
        "Node",
        "Port",
        "Edge",
        "CircuitRenderer",
        "CircuitRuntimeState",
    ):
        assert not hasattr(circuit, absent)
    assert not any(name.startswith("Simulation") for name in dir(circuit))


# Conventions Graphics : projection test-only, aucun GraphicScene produit.


@dataclass(frozen=True)
class _Node:
    id: str
    x: int
    y: int
    rotation: int


@dataclass(frozen=True)
class _Edge:
    id: str
    a: tuple[str, str]
    b: tuple[str, str]
    points: tuple[tuple[int, int], ...]


_OMNI = "*"


def _project(document: CircuitDocument) -> tuple[list[_Node], list[_Edge]]:
    nodes = [
        _Node(c.id, c.position.x, c.position.y, c.rotation) for c in document.components
    ] + [_Node(j.id, j.position.x, j.position.y, 0) for j in document.junctions]

    def port(endpoint: TerminalEndpoint | JunctionEndpoint) -> tuple[str, str]:
        if isinstance(endpoint, TerminalEndpoint):
            return endpoint.component_id, endpoint.terminal_id
        return endpoint.junction_id, _OMNI

    edges = [
        _Edge(e.id, port(e.a), port(e.b), tuple((p.x, p.y) for p in e.route.points))
        for e in document.connections
    ]
    return nodes, edges


def test_projection_reuses_identities_without_loss() -> None:
    document = sample_document()
    nodes, edges = _project(document)
    assert [n.id for n in nodes] == [R1, LED, J1]
    assert edges[0] == _Edge(E1, (R1, "t2"), (J1, _OMNI), ((15, 8),))
    assert edges[1].points == ()
    point = document.connections[0].route.points[0]
    assert point.model_dump() == {"x": 15, "y": 8}
    assert CircuitPoint.model_validate_json(point.model_dump_json()) == point


def test_route_never_duplicates_endpoints() -> None:
    route = sample_document().connections[0].route
    assert set(type(route).model_fields) == {"mode", "points"}
