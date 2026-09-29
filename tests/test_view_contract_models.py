"""Validation réelle en mémoire et concordance avec le schéma normatif."""

import builtins
import copy
import json
from importlib.resources import files
from pathlib import Path
from typing import Any, cast, get_args

import pytest
from pydantic import ValidationError

from forge_design.contracts import (
    ViewAction,
    ViewContextVariable,
    ViewContract,
    ViewValueType,
)

FIXTURES = Path(__file__).parent / "fixtures/contracts"
BASE: dict[str, Any] = {"name": "home/index", "template": "mvc/views/a", "context": {}}


@pytest.mark.parametrize("name", ["minimal", "contacts-list"])
def test_official_fixtures_round_trip(name: str) -> None:
    text = (FIXTURES / f"{name}.view.json").read_text()
    data = json.loads(text)
    for model in (
        ViewContract.model_validate(data),
        ViewContract.model_validate_json(text),
    ):
        assert model.model_dump(exclude_unset=True) == data
        dumped = model.model_dump_json(exclude_unset=True)
        assert json.loads(dumped) == data
        assert ViewContract.model_validate_json(dumped) == model
        if name == "minimal":
            assert model.actions is None and "actions" not in model.model_fields_set
        else:
            assert model.context["page_title"].type == "string"
            assert model.context["page_title"].label == "Titre de page"
            assert model.context["contacts"].entity == "Contact"
            assert model.context["contacts"].fields == {
                "nom": "string",
                "email": "email",
                "telephone": "string",
            }
            assert model.context["can_create"].type == "boolean"
            assert model.actions is not None
            assert model.actions["create"].method == "GET"
            assert model.actions["create"].csrf is None
            assert model.actions["save"].method == "POST"
            assert model.actions["save"].csrf is True


@pytest.mark.parametrize("value_type", get_args(ViewValueType))
def test_six_types(value_type: str) -> None:
    model = ViewContextVariable.model_validate({"type": value_type})
    assert model.type == value_type
    assert model.label is model.entity is model.fields is None
    assert model.model_dump(exclude_unset=True) == {"type": value_type}


def test_declarative_values_without_cross_validation() -> None:
    data = {
        "name": " ",
        "template": "mvc/views/../secret.html",
        "context": {
            "user-name": {"type": "object", "entity": "Inconnue", "label": ""},
            " ": {"type": "string", "fields": {" ": "email"}},
            "😀": {"type": "list"},
        },
        "actions": {" ": {"method": "FOO", "path": "relative/{id}", "csrf": False}},
    }
    assert ViewContract.model_validate(data).model_dump(exclude_unset=True) == data
    model = ViewContract.model_validate(BASE | {"actions": {}})
    assert model.actions == {} and "actions" in model.model_fields_set


@pytest.mark.parametrize("length", [1, 256, 257])
def test_unicode_name_boundary(length: int) -> None:
    data = BASE | {"name": "😀" * length}
    if length <= 256:
        assert ViewContract.model_validate(data).name == data["name"]
    else:
        with pytest.raises(ValidationError):
            ViewContract.model_validate(data)


def test_unicode_no_normalization() -> None:
    data = BASE | {
        "name": "é e\u0301",
        "context": {
            "é": {
                "type": "object",
                "entity": "Entité😀",
                "fields": {"e\u0301": "libre"},
            },
            "e\u0301": {"type": "number"},
        },
    }
    assert ViewContract.model_validate(data).model_dump(exclude_unset=True) == data


@pytest.mark.parametrize(
    "path,valid",
    [
        ("mvc/views/a", True),
        ("mvc/views/a.html", True),
        ("mvc/views/", False),
        ("x/mvc/views/a.html", False),
        ("mvc/views/\na", False),
        ("mvc/views/" + "😀" * (4096 - 10), True),
        ("mvc/views/" + "😀" * (4097 - 10), False),
    ],
)
def test_template_pattern_and_length(path: str, valid: bool) -> None:
    if valid:
        assert ViewContract.model_validate(BASE | {"template": path}).template == path
    else:
        with pytest.raises(ValidationError):
            ViewContract.model_validate(BASE | {"template": path})


@pytest.mark.parametrize(
    "method", ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD", "FOO"]
)
def test_method_vocabulary_open(method: str) -> None:
    assert ViewAction(method=method, path="x").method == method


@pytest.mark.parametrize(
    "method",
    ["", "get", "Get", "GET-POST", "GET1", " GET", "GET ", "É", "ＧＥＴ", "GET\n"],
)
def test_method_ascii_pattern(method: str) -> None:
    with pytest.raises(ValidationError):
        ViewAction(method=method, path="x")


root_invalid: list[object] = [[], None]
root_invalid += [{k: v for k, v in BASE.items() if k != missing} for missing in BASE]
root_invalid += [
    BASE | {key: value}
    for key, value in [
        ("name", ""),
        ("name", "a" * 257),
        ("name", None),
        ("name", 123),
        ("template", ""),
        ("template", None),
        ("template", 123),
        ("context", list[object]()),
        ("context", None),
        ("context", {"": {"type": "string"}}),
        ("actions", None),
        ("actions", list[object]()),
        ("actions", {"": {"method": "GET", "path": "x"}}),
        ("metadata", {}),
    ]
]
variable_invalid: list[dict[str, Any]] = [{}, {"type": "email"}, {"type": None}]
variable_invalid += [
    {"type": "string", key: value}
    for key, value in [
        ("label", None),
        ("label", 123),
        ("entity", None),
        ("entity", ""),
        ("entity", 123),
        ("fields", None),
        ("fields", list[object]()),
        ("fields", {"": "string"}),
        ("fields", {"x": ""}),
        ("fields", {"x": 123}),
        ("fields", {"x": None}),
        ("visible_if", "x"),
    ]
]
action_invalid: list[dict[str, Any]] = [{"path": "x"}, {"method": "GET"}]
action_invalid += [
    {"method": "GET", "path": "x", key: value}
    for key, value in [
        ("method", None),
        ("method", 123),
        ("path", None),
        ("path", ""),
        ("path", 123),
        ("csrf", None),
        ("csrf", 1),
        ("csrf", 0),
        ("csrf", 1.0),
        ("csrf", "true"),
        ("callback", "run"),
    ]
]


@pytest.mark.parametrize("as_json", [False, True])
@pytest.mark.parametrize("data", root_invalid)
def test_invalid_contracts(data: object, as_json: bool) -> None:
    with pytest.raises(ValidationError):
        if as_json:
            ViewContract.model_validate_json(json.dumps(data))
        else:
            ViewContract.model_validate(data)


@pytest.mark.parametrize("as_json", [False, True])
@pytest.mark.parametrize("data", variable_invalid)
def test_invalid_variables(data: dict[str, Any], as_json: bool) -> None:
    with pytest.raises(ValidationError):
        if as_json:
            ViewContextVariable.model_validate_json(json.dumps(data))
        else:
            ViewContextVariable.model_validate(data)


@pytest.mark.parametrize("as_json", [False, True])
@pytest.mark.parametrize("data", action_invalid)
def test_invalid_actions(data: dict[str, Any], as_json: bool) -> None:
    with pytest.raises(ValidationError):
        if as_json:
            ViewAction.model_validate_json(json.dumps(data))
        else:
            ViewAction.model_validate(data)


@pytest.mark.parametrize("value", [True, 1, 1.0, b"label"])
def test_strict_string_coercions(value: object) -> None:
    with pytest.raises(ValidationError):
        ViewContextVariable.model_validate({"type": "string", "label": value})


@pytest.mark.parametrize("mapping", ["context", "actions", "fields"])
def test_dictionary_keys_must_be_strings(mapping: str) -> None:
    with pytest.raises(ValidationError):
        if mapping == "fields":
            ViewContextVariable.model_validate(
                {"type": "object", "fields": {1: "string"}}
            )
        else:
            value = (
                {"type": "string"}
                if mapping == "context"
                else {"method": "GET", "path": "x"}
            )
            ViewContract.model_validate(BASE | {mapping: {1: value}})


def test_errors_have_locations_and_codes() -> None:
    data = BASE | {
        "context": {"contacts": {"type": "email"}},
        "actions": {"save": {"method": "POST", "path": "x", "csrf": 1}},
    }
    with pytest.raises(ValidationError) as caught:
        ViewContract.model_validate(data)
    assert {(e["loc"], e["type"]) for e in caught.value.errors()} == {
        (("context", "contacts", "type"), "literal_error"),
        (("actions", "save", "csrf"), "bool_type"),
    }
    with pytest.raises(ValidationError) as malformed:
        ViewContract.model_validate_json('{"name":')
    assert malformed.value.errors()[0]["type"] == "json_invalid"


def test_frozen_attributes_but_mutable_mappings() -> None:
    data = BASE | {"context": {"x": {"type": "object", "fields": {"a": "string"}}}}
    original = copy.deepcopy(data)
    model = ViewContract.model_validate(data)
    with pytest.raises(ValidationError, match="frozen"):
        model.name = "new"
    variable = model.context["x"]
    with pytest.raises(ValidationError, match="frozen"):
        variable.label = "new"
    action = ViewAction(method="GET", path="x")
    with pytest.raises(ValidationError, match="frozen"):
        action.csrf = True
    model.context["added"] = ViewContextVariable(type="string")
    assert variable.fields is not None
    variable.fields["added"] = "email"
    assert data == original
    # Revalider un dump est la frontière après mutation d'un mapping.
    model.context[""] = ViewContextVariable(type="string")
    with pytest.raises(ValidationError):
        ViewContract.model_validate(model.model_dump(exclude_unset=True))


def test_generated_schema_matches_all_normative_constraints() -> None:
    normative = json.loads(
        files("forge_design.contracts")
        .joinpath("view_contract.schema.json")
        .read_text()
    )
    generated = ViewContract.model_json_schema()

    # Comparaison de schémas, pas moteur de validation d'instances.
    def constraints(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                k: constraints(v)
                for k, v in cast(dict[str, Any], value).items()
                if k not in {"title", "description", "$schema"}
            }
        if isinstance(value, list):
            return [constraints(v) for v in cast(list[Any], value)]
        if value == "#/$defs/ViewContextVariable":
            return "#/$defs/ContextVariable"
        return value

    generated["$defs"]["ContextVariable"] = generated["$defs"].pop(
        "ViewContextVariable"
    )
    assert constraints(generated) == constraints(normative)


def test_validation_has_no_filesystem_access(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> Any:
        raise AssertionError("filesystem access during validation")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    assert ViewContract.model_validate(BASE).name == "home/index"
    assert ViewContract.model_validate_json(json.dumps(BASE)).context == {}
