"""Schéma normatif Circuit V0.1 : déclarations et concordance avec Pydantic."""

import json
import tomllib
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

import pytest

from forge_design.circuit import CircuitDocument
from forge_design.circuit.ids import CircuitIdKind, id_pattern
from forge_design.circuit.limits import (
    MAX_CIRCUIT_ANNOTATIONS,
    MAX_CIRCUIT_COMPONENTS,
    MAX_CIRCUIT_CONNECTIONS,
    MAX_CIRCUIT_JUNCTIONS,
    MAX_CIRCUIT_PAGE_UNITS,
    MAX_CIRCUIT_PROPERTIES,
    MAX_CIRCUIT_ROUTE_POINTS,
)

ROOT = Path(__file__).resolve().parents[1]
ROOT_FIELDS = [
    "format_version",
    "page",
    "components",
    "connections",
    "junctions",
    "annotations",
]


@pytest.fixture
def schema() -> dict[str, Any]:
    return json.loads(
        files("forge_design.circuit").joinpath("circuit.schema.json").read_text()
    )


def test_dialect_and_strict_root(schema: dict[str, Any]) -> None:
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "$id" not in schema
    assert schema["title"] == "Forge Design Circuit Resource"
    assert schema["type"] == "object" and schema["additionalProperties"] is False
    assert schema["required"] == ROOT_FIELDS
    assert list(schema["properties"]) == ROOT_FIELDS
    assert schema["properties"]["format_version"] == {"const": "0.1", "type": "string"}


def test_collections_are_bounded(schema: dict[str, Any]) -> None:
    expected = {
        "components": ("CircuitComponent", MAX_CIRCUIT_COMPONENTS),
        "connections": ("CircuitConnection", MAX_CIRCUIT_CONNECTIONS),
        "junctions": ("CircuitJunction", MAX_CIRCUIT_JUNCTIONS),
        "annotations": ("CircuitTextAnnotation", MAX_CIRCUIT_ANNOTATIONS),
    }
    for name, (definition, limit) in expected.items():
        assert schema["properties"][name] == {
            "items": {"$ref": f"#/$defs/{definition}"},
            "maxItems": limit,
            "type": "array",
        }


def test_every_object_forbids_extra_fields(schema: dict[str, Any]) -> None:
    for name, definition in schema["$defs"].items():
        if name == "CircuitEndpoint":
            assert [b["$ref"] for b in definition["oneOf"]] == [
                "#/$defs/TerminalEndpoint",
                "#/$defs/JunctionEndpoint",
            ]
            continue
        assert definition["type"] == "object", name
        assert definition["additionalProperties"] is False, name
        assert set(definition["required"]) <= set(definition["properties"]), name


def test_page_point_and_rotation(schema: dict[str, Any]) -> None:
    defs = schema["$defs"]
    for axis in ("x", "y"):
        assert defs["CircuitPoint"]["properties"][axis] == {
            "maximum": MAX_CIRCUIT_PAGE_UNITS,
            "minimum": 0,
            "type": "integer",
        }
    for side in ("width", "height"):
        assert defs["CircuitPage"]["properties"][side] == {
            "maximum": MAX_CIRCUIT_PAGE_UNITS,
            "minimum": 1,
            "type": "integer",
        }
    rotation = defs["CircuitComponent"]["properties"]["rotation"]
    assert rotation == {"enum": [0, 90, 180, 270], "type": "integer"}


def test_identity_patterns_by_kind(schema: dict[str, Any]) -> None:
    defs = schema["$defs"]
    pairs: dict[tuple[str, str], CircuitIdKind] = {
        ("CircuitComponent", "id"): "component",
        ("CircuitConnection", "id"): "connection",
        ("CircuitJunction", "id"): "junction",
        ("CircuitTextAnnotation", "id"): "annotation",
        ("TerminalEndpoint", "component_id"): "component",
        ("JunctionEndpoint", "junction_id"): "junction",
    }
    for (definition, field), kind in pairs.items():
        assert defs[definition]["properties"][field]["pattern"] == id_pattern(kind)


def test_component_has_no_terminals_and_reference_is_omissible(
    schema: dict[str, Any],
) -> None:
    component = schema["$defs"]["CircuitComponent"]
    assert list(component["properties"]) == [
        "id",
        "type",
        "reference",
        "position",
        "rotation",
        "properties",
    ]
    assert "reference" not in component["required"]
    assert "anyOf" not in component["properties"]["reference"]
    properties = component["properties"]["properties"]
    assert properties["additionalProperties"] is False
    assert properties["maxProperties"] == MAX_CIRCUIT_PROPERTIES
    (values,) = properties["patternProperties"].values()
    assert [branch["type"] for branch in values["anyOf"]] == [
        "string",
        "boolean",
        "integer",
        "number",
    ]


def test_route_and_endpoints(schema: dict[str, Any]) -> None:
    defs = schema["$defs"]
    route = defs["CircuitRoute"]
    assert list(route["properties"]) == ["mode", "points"]
    assert route["properties"]["mode"] == {"const": "orthogonal", "type": "string"}
    assert route["properties"]["points"]["maxItems"] == MAX_CIRCUIT_ROUTE_POINTS
    connection = defs["CircuitConnection"]
    assert list(connection["properties"]) == ["id", "a", "b", "route"]
    for side in ("a", "b"):
        assert connection["properties"][side] == {"$ref": "#/$defs/CircuitEndpoint"}
    assert list(defs["CircuitJunction"]["properties"]) == ["id", "position"]
    assert defs["TerminalEndpoint"]["properties"]["kind"]["const"] == "terminal"
    assert defs["JunctionEndpoint"]["properties"]["kind"]["const"] == "junction"


def test_no_runtime_or_derived_state_declared(schema: dict[str, Any]) -> None:
    text = json.dumps(schema["properties"]) + json.dumps(
        {k: v["properties"] for k, v in schema["$defs"].items() if "properties" in v}
    )
    for forbidden in (
        "net",
        "terminals",
        "selection",
        "viewport",
        "zoom",
        "history",
        "dirty",
        "simulation",
        "voltage",
        "current",
        "student",
    ):
        assert f'"{forbidden}"' not in text, forbidden


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: _clean(v)
            for k, v in cast(dict[str, Any], value).items()
            if k not in {"title", "description", "$schema", "discriminator"}
        }
    if isinstance(value, list):
        return [_clean(v) for v in cast(list[Any], value)]
    return value


def test_schema_concordance(schema: dict[str, Any]) -> None:
    generated = _clean(CircuitDocument.model_json_schema())
    normative = _clean(schema)
    defs = normative.pop("$defs")
    endpoint = defs.pop("CircuitEndpoint")
    generated_defs = generated.pop("$defs")
    assert generated == normative
    for side in ("a", "b"):
        generated_defs["CircuitConnection"]["properties"][side] = {
            "$ref": "#/$defs/CircuitEndpoint"
        }
    assert generated_defs == defs
    connection = _clean(CircuitDocument.model_json_schema())["$defs"]
    assert connection["CircuitConnection"]["properties"]["a"] == {
        "oneOf": endpoint["oneOf"]
    }


def test_packaging_declares_schema_and_no_dependency() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    setuptools = project["tool"]["setuptools"]
    assert "forge_design.circuit" in setuptools["packages"]
    assert setuptools["package-data"]["forge_design.circuit"] == ["circuit.schema.json"]
    dependencies = " ".join(project["project"]["dependencies"]).lower()
    assert "jsonschema" not in dependencies and "uuid" not in dependencies
