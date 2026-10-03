"""Codec Circuit V0.1 : JSON strict, issues circuit.*, encodage canonique."""

import json
from typing import Any

import pytest
from circuit_support import (
    R1,
    SAMPLE,
    circuit_document,
    sample,
    sample_document,
    to_bytes,
    unchecked,
)

from forge_design.circuit import CircuitCodec, CircuitDocument, new_circuit_document
from forge_design.circuit.limits import (
    MAX_CIRCUIT_ANNOTATIONS,
    MAX_CIRCUIT_COMPONENTS,
    MAX_CIRCUIT_CONNECTIONS,
    MAX_CIRCUIT_JUNCTIONS,
    MAX_CIRCUIT_PAGE_UNITS,
    MAX_CIRCUIT_ROUTE_POINTS,
    MAX_CIRCUIT_TEXT_CHARS,
)
from forge_design.limits import MAX_SPECIALIZED_ISSUES
from forge_design.specialized import SpecializedFormatError, SpecializedIssue

CODEC = CircuitCodec()


def _issues(data: bytes) -> tuple[SpecializedIssue, ...]:
    with pytest.raises(SpecializedFormatError) as caught:
        CODEC.decode(data)
    issues = caught.value.issues
    assert all(i.level == "structure" and i.severity == "error" for i in issues)
    return issues


def _codes(data: bytes) -> set[str]:
    return {issue.code for issue in _issues(data)}


def test_nominal_round_trip() -> None:
    document = circuit_document()
    encoded = CODEC.encode(document)
    assert CODEC.detect_version(encoded) == "0.1"
    decoded = CODEC.decode(encoded)
    assert decoded == document
    assert CODEC.encode(decoded) == encoded
    assert CODEC.validate(decoded).issues == ()


def test_canonical_bytes() -> None:
    encoded = CODEC.encode(sample_document())
    expected = json.dumps(SAMPLE, ensure_ascii=False, indent=2) + "\n"
    assert encoded == expected.encode("utf-8")
    assert encoded.endswith(b"}\n") and b"\r" not in encoded
    assert CODEC.encode(sample_document()) == encoded
    empty = CODEC.encode(new_circuit_document())
    assert empty == CODEC.encode(new_circuit_document())
    assert json.loads(empty)["page"] == {"width": 80, "height": 60}


def test_unicode_preserved_without_normalization() -> None:
    data = sample()
    decomposed = "Résistance µ Ω"
    data["components"][0]["properties"]["label"] = decomposed
    encoded = CODEC.encode(CODEC.decode(to_bytes(data)))
    assert decomposed.encode() in encoded
    assert CODEC.decode(encoded).components[0].properties["label"] == decomposed
    assert "Résistance".encode() in CODEC.encode(sample_document())


def test_collection_order_is_preserved() -> None:
    data = sample()
    data["components"].reverse()
    encoded = CODEC.encode(CODEC.decode(to_bytes(data)))
    assert [c["id"] for c in json.loads(encoded)["components"]] == [
        c["id"] for c in data["components"]
    ]


@pytest.mark.parametrize(
    ("payload", "version"),
    [
        (b'{"format_version": "0.1"}', "0.1"),
        (b'{"format_version": "9.9", "x": [}', None),
        (b'{"format_version": "9.9"}', "9.9"),
        (b'{"format_version": 0.1}', None),
        (b'{"page": {}}', None),
        (b"[]", None),
        (b"\xff", None),
        (b'{"format_version": "0.1", "format_version": "0.2"}', None),
        (b'{"format_version": NaN}', None),
    ],
)
def test_detect_version_reads_only_the_version(
    payload: bytes, version: str | None
) -> None:
    assert CODEC.detect_version(payload) == version


def test_detect_version_does_not_validate_the_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> Any:
        raise AssertionError("validation métier pendant detect_version")

    encoded = CODEC.encode(sample_document())
    monkeypatch.setattr(CircuitDocument, "model_validate", forbidden)
    monkeypatch.setattr(CircuitDocument, "model_validate_json", forbidden)
    assert CODEC.detect_version(encoded) == "0.1"


def test_missing_version_decode_refused() -> None:
    data = {k: v for k, v in sample().items() if k != "format_version"}
    [issue] = _issues(to_bytes(data))
    assert issue.code == "circuit.validation-error"
    assert issue.location == ("format_version",)


def test_unknown_version_decode_refused() -> None:
    assert _codes(to_bytes(sample(format_version="0.2"))) == {
        "circuit.validation-error"
    }


@pytest.mark.parametrize(
    "payload",
    [
        b"\xff\xfe",
        b"{",
        b'{"format_version": "0.1", "format_version": "0.1"}',
        b'{"format_version": "0.1", "page": {"width": NaN, "height": 1}}',
        b'{"format_version": "0.1", "page": {"width": Infinity, "height": 1}}',
        b"[" * 100000,
    ],
)
def test_json_invalid(payload: bytes) -> None:
    [issue] = _issues(payload)
    assert issue.code == "circuit.json-invalid" and issue.location == ()


def test_extra_field_refused_with_location() -> None:
    data = sample(viewport={"zoom": 2})
    [issue] = _issues(to_bytes(data))
    assert issue.code == "circuit.validation-error"
    assert issue.location == ("viewport",)


def test_null_refused() -> None:
    data = sample()
    data["components"][0]["reference"] = None
    issues = _issues(to_bytes(data))
    assert {i.location for i in issues} == {("components", 0, "reference")}


def test_union_tags_are_not_locations() -> None:
    data = sample()
    data["connections"][1]["b"]["component_id"] = "x"
    [issue] = _issues(to_bytes(data))
    assert issue.code == "circuit.identity-invalid"
    assert issue.location == ("connections", 1, "b", "component_id")
    data = sample()
    data["components"][0]["properties"]["label"] = None
    locations = {i.location for i in _issues(to_bytes(data))}
    assert locations == {("components", 0, "properties", "label")}


def test_identity_codes() -> None:
    data = sample()
    data["junctions"][0]["id"] = "c_junction01"
    [issue] = _issues(to_bytes(data))
    assert issue.code == "circuit.identity-invalid"
    assert issue.location == ("junctions", 0, "id")
    data = sample()
    data["annotations"][0]["id"] = data["annotations"][0]["id"]
    data["components"][1]["id"] = R1
    [issue] = _issues(to_bytes(data))
    assert issue.code == "circuit.identity-duplicate"
    assert issue.location == ("components", 1, "id")
    assert R1 in issue.message


def _component(index: int) -> dict[str, Any]:
    return {
        "id": f"c_{index:08d}",
        "type": "placeholder",
        "position": {"x": 0, "y": 0},
        "rotation": 0,
        "properties": {},
    }


def _connection(index: int) -> dict[str, Any]:
    endpoint = {"kind": "junction", "junction_id": "j_00000000"}
    return {
        "id": f"e_{index:08d}",
        "a": endpoint,
        "b": endpoint,
        "route": {"mode": "orthogonal", "points": []},
    }


def _junction(index: int) -> dict[str, Any]:
    return {"id": f"j_{index:08d}", "position": {"x": 0, "y": 0}}


def _annotation(index: int) -> dict[str, Any]:
    return {
        "id": f"a_{index:08d}",
        "kind": "text",
        "position": {"x": 0, "y": 0},
        "text": "t",
    }


@pytest.mark.parametrize(
    ("collection", "factory", "limit"),
    [
        ("components", _component, MAX_CIRCUIT_COMPONENTS),
        ("connections", _connection, MAX_CIRCUIT_CONNECTIONS),
        ("junctions", _junction, MAX_CIRCUIT_JUNCTIONS),
        ("annotations", _annotation, MAX_CIRCUIT_ANNOTATIONS),
    ],
)
def test_collection_limits(collection: str, factory: Any, limit: int) -> None:
    data = sample(components=[], connections=[], junctions=[], annotations=[])
    data[collection] = [factory(i) for i in range(limit)]
    assert len(getattr(CODEC.decode(to_bytes(data)), collection)) == limit
    data[collection].append(factory(limit))
    [issue] = _issues(to_bytes(data))
    assert issue.code == "circuit.limit-exceeded"
    assert issue.location == (collection,)


def test_route_points_and_text_limits() -> None:
    data = sample()
    route = data["connections"][0]["route"]
    route["points"] = [{"x": 1, "y": 1}] * MAX_CIRCUIT_ROUTE_POINTS
    CODEC.decode(to_bytes(data))
    route["points"].append({"x": 1, "y": 1})
    assert _codes(to_bytes(data)) == {"circuit.limit-exceeded"}
    data = sample()
    data["annotations"][0]["text"] = "é" * MAX_CIRCUIT_TEXT_CHARS
    CODEC.decode(to_bytes(data))
    data["annotations"][0]["text"] += "é"
    assert _codes(to_bytes(data)) == {"circuit.limit-exceeded"}


def test_coordinate_upper_bound_is_a_limit() -> None:
    data = sample(page={"width": MAX_CIRCUIT_PAGE_UNITS, "height": 1})
    CODEC.decode(to_bytes(data))
    data["page"]["width"] += 1
    assert _codes(to_bytes(data)) == {"circuit.limit-exceeded"}
    data["page"]["width"] = 0
    assert _codes(to_bytes(data)) == {"circuit.validation-error"}


def test_issues_are_bounded() -> None:
    data = sample(components=[], connections=[], junctions=[], annotations=[])
    data["annotations"] = [
        {"id": "bad", "kind": "text", "position": {"x": -1, "y": -1}, "text": ""}
        for _ in range(1000)
    ]
    assert len(_issues(to_bytes(data))) == MAX_SPECIALIZED_ISSUES + 1


def test_validate_reports_structure_of_constructed_model() -> None:
    broken = CircuitDocument.model_construct(
        format_version="0.1",
        page=sample_document().page,
        components=(),
        connections=(),
        junctions=(),
        annotations=(),
        extra_state=1,
    )
    assert CODEC.validate(unchecked()).issues == ()
    duplicated = unchecked(junctions=sample_document().junctions * 2)
    [issue] = CODEC.validate(duplicated).issues
    assert issue.code == "circuit.identity-duplicate"
    assert CODEC.validate(broken).issues == ()  # champ hors modèle ignoré au dump
