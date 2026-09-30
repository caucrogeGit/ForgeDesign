"""Assertions du schéma normatif ; aucun moteur de validation JSON Schema."""

import json
import re
import tomllib
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest

from forge_design.app import create_tool_registry

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def schema() -> dict[str, Any]:
    return json.loads(
        files("forge_design.design").joinpath("design.schema.json").read_text()
    )


def test_root_and_version_declarations(schema: dict[str, Any]) -> None:
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "$id" not in schema
    assert schema["title"] == "Forge Design Design File"
    assert schema["type"] == "object" and schema["additionalProperties"] is False
    assert schema["required"] == ["version", "view", "source_contract", "root"]
    assert set(schema["properties"]) == set(schema["required"])
    assert schema["properties"]["version"] == {"type": "string", "const": "0.1"}
    assert schema["properties"]["view"] == {
        "type": "string",
        "minLength": 1,
        "maxLength": 256,
    }
    assert set(schema["$defs"]) == {
        "DesignNode",
        "PageRoot",
        "TableColumn",
        "PropValue",
    }


def test_node_and_root_composition(schema: dict[str, Any]) -> None:
    assert schema["properties"]["root"] == {"$ref": "#/$defs/PageRoot"}
    assert schema["$defs"]["PageRoot"] == {
        "allOf": [
            {"$ref": "#/$defs/DesignNode"},
            {
                "type": "object",
                "required": ["children"],
                "properties": {"type": {"const": "page"}},
            },
        ]
    }
    node = schema["$defs"]["DesignNode"]
    assert node["type"] == "object" and node["additionalProperties"] is False
    assert node["required"] == ["type"]
    assert set(node["properties"]) == {
        "type",
        "binding",
        "visible_if",
        "props",
        "columns",
        "children",
    }
    assert node["properties"]["type"] == {
        "type": "string",
        "enum": [
            "page",
            "section",
            "container",
            "grid",
            "card",
            "title",
            "text",
            "button",
            "table",
            "form",
            "field",
            "alert",
            "empty_state",
        ],
    }
    assert node["properties"]["children"] == {
        "type": "array",
        "items": {"$ref": "#/$defs/DesignNode"},
    }
    assert node["properties"]["binding"] == {"type": "string", "minLength": 1}


def test_props_and_columns_declarations(schema: dict[str, Any]) -> None:
    props = schema["$defs"]["DesignNode"]["properties"]
    assert props["props"] == {
        "type": "object",
        "propertyNames": {"minLength": 1},
        "additionalProperties": {"$ref": "#/$defs/PropValue"},
    }
    assert schema["$defs"]["PropValue"] == {
        "type": ["string", "boolean", "integer", "number"]
    }
    assert props["columns"] == {
        "type": "array",
        "items": {"$ref": "#/$defs/TableColumn"},
    }
    assert schema["$defs"]["TableColumn"] == {
        "type": "object",
        "required": ["label", "binding"],
        "additionalProperties": False,
        "properties": {
            "label": {"type": "string", "minLength": 1},
            "binding": {"type": "string", "minLength": 1},
        },
    }


@pytest.mark.parametrize(
    "path,pattern_matches",
    [
        ("contacts/list.view.json", True),
        ("é 😀/a.view.json", True),
        ("/absolute.view.json", False),
        ("C:\\a.view.json", False),
        ("C:/a.view.json", False),
        ("a//b.view.json", False),
        ("a.view.JSON", False),
        ("a.json", False),
        ("a.view.json.bak", False),
    ],
)
def test_source_contract_segment_pattern(
    schema: dict[str, Any], path: str, pattern_matches: bool
) -> None:
    field = schema["properties"]["source_contract"]
    assert field["type"] == "string" and field["minLength"] == 1
    assert field["maxLength"] == 4096
    # Test du motif isolé, pas validation d'une instance de document.
    assert bool(re.search(field["pattern"], path)) == pattern_matches


@pytest.mark.parametrize(
    "path,index",
    [
        ("../a.view.json", 0),
        ("a/../b.view.json", 0),
        ("./a.view.json", 0),
        ("mvc/views/a.view.json", 1),
        (".view.json", 2),
        ("a/.view.json", 2),
        ("a.view.json\n", 3),
    ],
)
def test_source_contract_exclusion_patterns(
    schema: dict[str, Any], path: str, index: int
) -> None:
    exclusions = schema["properties"]["source_contract"]["not"]["anyOf"]
    assert len(exclusions) == 4
    assert re.search(exclusions[index]["pattern"], path)


@pytest.mark.parametrize("missing", ["version", "view", "source_contract", "root"])
def test_missing_field_examples_match_required_declaration(
    schema: dict[str, Any], missing: str
) -> None:
    example: dict[str, Any] = {
        "version": "0.1",
        "view": "a",
        "source_contract": "a.view.json",
        "root": {"type": "page", "children": []},
    }
    del example[missing]
    assert missing not in example and missing in schema["required"]


def test_invalid_examples_explain_declared_constraints(schema: dict[str, Any]) -> None:
    assert "0.2" != schema["properties"]["version"]["const"]
    assert (
        "section"
        != schema["$defs"]["PageRoot"]["allOf"][1]["properties"]["type"]["const"]
    )
    node = schema["$defs"]["DesignNode"]
    assert "unknown" not in node["properties"]["type"]["enum"]
    assert (
        "metadata" not in schema["properties"]
        and schema["additionalProperties"] is False
    )
    assert (
        "visible_unless" not in node["properties"]
        and node["additionalProperties"] is False
    )
    assert len("") < node["properties"]["binding"]["minLength"]
    assert {"object", "array", "null"}.isdisjoint(schema["$defs"]["PropValue"]["type"])
    column = schema["$defs"]["TableColumn"]
    example = {"label": "Nom"}
    assert "binding" not in example and "binding" in column["required"]
    assert (
        "extra" not in column["properties"] and column["additionalProperties"] is False
    )


def test_official_examples_and_documentation(schema: dict[str, Any]) -> None:
    fixture_dir = ROOT / "tests/fixtures/design"
    minimal = json.loads((fixture_dir / "minimal.design.json").read_text())
    contacts = json.loads((fixture_dir / "contacts-list.design.json").read_text())
    assert minimal == {
        "version": "0.1",
        "view": "home/index",
        "source_contract": "home/index.view.json",
        "root": {"type": "page", "children": []},
    }
    assert contacts["version"] == "0.1" and contacts["view"] == "contacts/list"
    assert contacts["source_contract"] == "contacts/list.view.json"
    assert set(contacts) == set(schema["required"])
    root = contacts["root"]
    assert root["type"] == "page"
    section, table = root["children"]
    assert section["type"] == "section"
    assert section["props"] == {"tag": "header", "class": "max-w-5xl mx-auto py-8"}
    assert section["children"] == [
        {
            "type": "text",
            "binding": "page_title",
            "props": {"tag": "h1", "class": "text-3xl font-bold"},
        }
    ]
    assert table == {
        "type": "table",
        "binding": "contacts",
        "props": {"class": "w-full border border-slate-200"},
        "columns": [
            {"label": "Nom", "binding": "nom"},
            {"label": "Email", "binding": "email"},
            {"label": "Téléphone", "binding": "telephone"},
        ],
    }
    doc = (ROOT / "docs/design/design-json.md").read_text()
    blocks = re.findall(r"```json\n(.*?)\n```", doc, re.DOTALL)
    assert [json.loads(block) for block in blocks] == [minimal, contacts]


def test_packaging_and_no_new_dependency_or_tool() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert "forge_design.design" in config["tool"]["setuptools"]["packages"]
    assert config["tool"]["setuptools"]["package-data"]["forge_design.design"] == [
        "design.schema.json"
    ]
    assert config["project"]["dependencies"] == [
        "packaging>=24.0",
        "forge-mvc==1.0.0rc9",
        "jinja2==3.1.6",
        "pydantic>=2,<3",
    ]
    assert [t.id for t in create_tool_registry().list()] == [
        "project-inspector",
        "route-explorer",
        "entity-explorer",
        "debug-center",
        "template-viewer",
    ]


def test_visible_if_additive_declaration(schema: dict[str, Any]) -> None:
    node = schema["$defs"]["DesignNode"]
    assert node["properties"]["visible_if"] == {"type": "string", "minLength": 1}
    assert "visible_if" not in node["required"]
    assert schema["properties"]["version"]["const"] == "0.1"
