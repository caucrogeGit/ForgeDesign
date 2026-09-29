"""Déclarations du schéma et exemples ; aucun moteur de validation d'instances."""

import json
import re
import tomllib
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest

from forge_design.app import create_tool_registry

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/contracts"


@pytest.fixture
def schema() -> dict[str, Any]:
    return json.loads(
        files("forge_design.contracts")
        .joinpath("view_contract.schema.json")
        .read_text(encoding="utf-8")
    )


def test_schema_dialect_and_root(schema: dict[str, Any]) -> None:
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["title"] == "Forge Design View Contract"
    assert schema["description"]
    assert "$id" not in schema
    assert schema["type"] == "object"
    assert schema["required"] == ["name", "template", "context"]
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {"name", "template", "context", "actions"}
    assert set(schema["$defs"]) == {"ContextVariable", "ViewAction"}
    # Contre-exemple racine non objet : contrainte déclarée, pas validation.
    non_object_example: list[object] = []
    assert not isinstance(non_object_example, dict)


def test_names_and_template_bounds(schema: dict[str, Any]) -> None:
    props = schema["properties"]
    assert props["name"] == {"type": "string", "minLength": 1, "maxLength": 256}
    assert props["template"]["type"] == "string"
    assert props["template"]["minLength"] == 1
    assert props["template"]["maxLength"] == 4096
    assert props["template"]["pattern"] == "^mvc/views/.+"


def test_maps_and_empty_objects_are_declared(schema: dict[str, Any]) -> None:
    for name, definition in (("context", "ContextVariable"), ("actions", "ViewAction")):
        assert schema["properties"][name] == {
            "type": "object",
            "propertyNames": {"minLength": 1},
            "additionalProperties": {"$ref": f"#/$defs/{definition}"},
        }
    assert "actions" not in schema["required"]


def test_context_vocabulary_and_fields(schema: dict[str, Any]) -> None:
    variable = schema["$defs"]["ContextVariable"]
    assert variable["type"] == "object"
    assert variable["required"] == ["type"]
    props = variable["properties"]
    assert props["type"] == {
        "type": "string",
        "enum": ["string", "boolean", "integer", "number", "object", "list"],
    }
    assert props["label"] == {"type": "string"}
    assert props["entity"] == {"type": "string", "minLength": 1}
    assert props["fields"] == {
        "type": "object",
        "propertyNames": {"minLength": 1},
        "additionalProperties": {"type": "string", "minLength": 1},
    }
    assert set(variable) == {"type", "required", "additionalProperties", "properties"}
    unknown_type_example = {"type": "email"}
    assert unknown_type_example["type"] not in props["type"]["enum"]


def test_action_requires_method_path_and_boolean_csrf(schema: dict[str, Any]) -> None:
    action = schema["$defs"]["ViewAction"]
    assert action["type"] == "object"
    assert action["required"] == ["method", "path"]
    assert action["properties"] == {
        "method": {"type": "string", "minLength": 1, "pattern": "^[A-Z]+$"},
        "path": {"type": "string", "minLength": 1},
        "csrf": {"type": "boolean"},
    }
    assert "csrf" not in action["required"]
    non_boolean_example = {"method": "POST", "path": "/contacts", "csrf": "true"}
    assert not isinstance(non_boolean_example["csrf"], bool)


@pytest.mark.parametrize(
    "definition,missing,example",
    [
        (None, "name", {"template": "mvc/views/a.html", "context": {}}),
        (None, "template", {"name": "a", "context": {}}),
        (None, "context", {"name": "a", "template": "mvc/views/a.html"}),
        ("ContextVariable", "type", {"label": "Sans type"}),
        ("ViewAction", "method", {"path": "/contacts"}),
        ("ViewAction", "path", {"method": "GET"}),
    ],
)
def test_required_declaration_for_missing_field_examples(
    schema: dict[str, Any],
    definition: str | None,
    missing: str,
    example: dict[str, object],
) -> None:
    declaration = schema if definition is None else schema["$defs"][definition]
    assert missing in declaration["required"] and missing not in example


@pytest.mark.parametrize(
    "definition,allowed,example",
    [
        (None, {"name", "template", "context", "actions"}, {"metadata": {}}),
        ("ContextVariable", {"type", "label", "entity", "fields"}, {"visible_if": "x"}),
        ("ViewAction", {"method", "path", "csrf"}, {"callback": "run"}),
    ],
)
def test_strict_property_declaration_for_unknown_field_examples(
    schema: dict[str, Any],
    definition: str | None,
    allowed: set[str],
    example: dict[str, object],
) -> None:
    declaration = schema if definition is None else schema["$defs"][definition]
    assert declaration["additionalProperties"] is False
    assert set(declaration["properties"]) == allowed
    assert set(example).isdisjoint(allowed)


def test_documentary_examples_and_targeted_vocabulary(schema: dict[str, Any]) -> None:
    minimal = json.loads((FIXTURES / "minimal.view.json").read_text())
    contacts = json.loads((FIXTURES / "contacts-list.view.json").read_text())
    assert minimal == {
        "name": "home/index",
        "template": "mvc/views/home/index.html",
        "context": {},
    }
    assert contacts["name"] == "contacts/list"
    assert contacts["template"] == "mvc/views/contacts/list.html"
    assert set(contacts) == set(schema["properties"])
    context = contacts["context"]
    assert {v["type"] for v in context.values()} == {"string", "list", "boolean"}
    assert {v["type"] for v in context.values()} <= set(
        schema["$defs"]["ContextVariable"]["properties"]["type"]["enum"]
    )
    assert context["contacts"]["entity"] == "Contact"
    assert context["contacts"]["fields"] == {
        "nom": "string",
        "email": "email",
        "telephone": "string",
    }
    assert context["page_title"]["label"] == "Titre de page"
    assert context["can_create"]["label"] == "Peut créer un contact"
    assert contacts["actions"] == {
        "create": {"method": "GET", "path": "/contacts/create"},
        "save": {"method": "POST", "path": "/contacts", "csrf": True},
    }
    doc = (ROOT / "docs/contracts/view-contract.md").read_text()
    blocks = re.findall(r"```json\n(.*?)\n```", doc, re.DOTALL)
    assert [json.loads(block) for block in blocks] == [minimal, contacts]


def test_package_declaration_and_unchanged_tools() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert "forge_design.contracts" in config["tool"]["setuptools"]["packages"]
    assert config["tool"]["setuptools"]["package-data"]["forge_design.contracts"] == [
        "view_contract.schema.json"
    ]
    assert config["project"]["dependencies"] == [
        "packaging>=24.0",
        "forge-mvc==1.0.0rc9",
        "jinja2==3.1.6",
    ]
    assert [tool.id for tool in create_tool_registry().list()] == [
        "project-inspector",
        "route-explorer",
        "entity-explorer",
        "debug-center",
        "template-viewer",
    ]
