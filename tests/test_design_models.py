"""Validation en mémoire des designs et concordance des contraintes normatives."""

import builtins
import json
from importlib.resources import files
from pathlib import Path
from typing import Any, cast, get_args

import pytest
from pydantic import BaseModel, ValidationError

from forge_design.design import (
    DesignFile,
    DesignNode,
    DesignNodeType,
    PageRoot,
    TableColumn,
)

BASE: dict[str, Any] = {
    "version": "0.1",
    "view": "home",
    "source_contract": "home.view.json",
    "root": {"type": "page", "children": []},
}


@pytest.mark.parametrize("fixture", ["minimal", "contacts-list", "conditional"])
@pytest.mark.parametrize("as_json", [False, True])
def test_fixtures_round_trip(fixture: str, as_json: bool) -> None:
    text = (
        Path(__file__).parent / "fixtures/design" / (fixture + ".design.json")
    ).read_text()
    data = json.loads(text)
    model = (
        DesignFile.model_validate_json(text)
        if as_json
        else DesignFile.model_validate(data)
    )
    assert model.model_dump(exclude_unset=True) == data
    assert json.loads(model.model_dump_json(exclude_unset=True)) == data
    assert DesignFile.model_validate(model.model_dump(exclude_unset=True)) == model
    if fixture == "contacts-list":
        assert model.root.children[0].children is not None
        assert model.root.children[0].children[0].binding == "page_title"
        assert model.root.children[1].binding == "contacts"
        assert model.root.children[1].columns is not None
        assert model.root.children[1].columns[2].label == "Téléphone"


@pytest.mark.parametrize("node_type", get_args(DesignNodeType))
def test_all_types_and_omission(node_type: str) -> None:
    node = DesignNode.model_validate({"type": node_type})
    assert node.binding is node.props is node.columns is node.children is None
    assert node.model_dump(exclude_unset=True) == {"type": node_type}


def test_generic_structure_and_explicit_empties() -> None:
    node: dict[str, Any] = {
        "type": "button",
        "children": [{"type": "page"}],
        "props": {},
        "columns": [],
    }
    assert DesignNode.model_validate(node).model_dump(exclude_unset=True) == node
    page: dict[str, Any] = {
        "type": "page",
        "children": [],
        "binding": "x",
        "props": {},
        "columns": [{"label": "L", "binding": "x"}],
    }
    assert PageRoot.model_validate(page).model_dump(exclude_unset=True) == page
    section = {
        "type": "section",
        "columns": [{"label": "L", "binding": "x"}],
        "children": [],
    }
    assert DesignNode.model_validate(section).model_dump(exclude_unset=True) == section


@pytest.mark.parametrize("value", ["", "true", True, False, 12, 0, 0.5, 1.0])
@pytest.mark.parametrize("as_json", [False, True])
def test_prop_types_preserved(value: object, as_json: bool) -> None:
    data = {"type": "text", "props": {"x": value}}
    node = (
        DesignNode.model_validate_json(json.dumps(data))
        if as_json
        else DesignNode.model_validate(data)
    )
    assert node.props is not None
    assert type(node.props["x"]) is type(value) and node.props["x"] == value


@pytest.mark.parametrize(
    "path",
    [
        "home/index.view.json",
        "contacts/list.view.json",
        "dossier avec espace/vue.view.json",
        "équipe/élément.view.json",
        "emoji/😀.view.json",
        ".hidden/a.view.json",
        "env/a.view.json",
    ],
)
def test_reference_valid_structure_only(path: str) -> None:
    assert (
        DesignFile.model_validate(BASE | {"source_contract": path}).source_contract
        == path
    )


@pytest.mark.parametrize(
    "path",
    [
        "/a.view.json",
        "mvc/views/a.view.json",
        "a//b.view.json",
        "a/../b.view.json",
        "a/./b.view.json",
        "a\\b.view.json",
        "C:a.view.json",
        "a.json",
        ".view.json",
        "a/.view.json",
        "a.view.json\n",
        "a\rb.view.json",
    ],
)
@pytest.mark.parametrize("as_json", [False, True])
def test_reference_exclusions(path: str, as_json: bool) -> None:
    data = BASE | {"source_contract": path}
    with pytest.raises(ValidationError):
        if as_json:
            DesignFile.model_validate_json(json.dumps(data))
        else:
            DesignFile.model_validate(data)


@pytest.mark.parametrize("field,limit", [("view", 256), ("source_contract", 4096)])
@pytest.mark.parametrize("extra", [0, 1])
def test_unicode_boundaries(field: str, limit: int, extra: int) -> None:
    value = (
        "😀" * (limit + extra)
        if field == "view"
        else "😀" * (limit + extra - len(".view.json")) + ".view.json"
    )
    if extra:
        with pytest.raises(ValidationError):
            DesignFile.model_validate(BASE | {field: value})
    else:
        assert (
            DesignFile.model_validate(BASE | {field: value}).model_dump()[field]
            == value
        )


def test_unicode_and_spaces_unchanged() -> None:
    data = BASE | {
        "view": " é e\u0301 ",
        "root": {
            "type": "page",
            "children": [
                {
                    "type": "text",
                    "binding": "é😀",
                    "props": {"e\u0301": ""},
                    "columns": [{"label": "Étiquette😀", "binding": "e\u0301"}],
                }
            ],
        },
    }
    assert DesignFile.model_validate(data).model_dump(exclude_unset=True) == data


root_invalid: list[object] = [[], None]
root_invalid += [{k: v for k, v in BASE.items() if k != missing} for missing in BASE]
root_invalid += [
    BASE | {k: v}
    for k, v in [
        ("version", 0.1),
        ("version", "0.2"),
        ("view", ""),
        ("view", 123),
        ("source_contract", ""),
        ("source_contract", 123),
        ("root", list[object]()),
        ("metadata", "x"),
    ]
]
node_invalid: list[object] = [{}, {"type": "image"}]
node_invalid += [
    {"type": "text", k: v}
    for k, v in [
        ("binding", ""),
        ("binding", None),
        ("binding", 123),
        ("props", None),
        ("props", list[object]()),
        ("columns", None),
        ("columns", dict[str, object]()),
        ("children", None),
        ("children", dict[str, object]()),
        ("id", "x"),
    ]
]
node_invalid += [
    {"type": "text", "props": {"x": v}}
    for v in [None, dict[str, object](), list[object](), float("nan"), float("inf")]
]
node_invalid += [{"type": "text", "props": {"": "x"}}]
page_invalid: list[object] = [
    {"children": []},
    {"type": "text", "children": []},
    {"type": "page"},
    {"type": "page", "children": {}},
    {"type": "page", "children": [], "extra": True},
]
column_invalid: list[object] = [
    None,
    {},
    {"label": "L"},
    {"binding": "x"},
    {"label": "", "binding": "x"},
    {"label": "L", "binding": ""},
    {"label": None, "binding": "x"},
    {"label": 123, "binding": "x"},
    {"label": "L", "binding": "x", "width": 10},
]


@pytest.mark.parametrize(
    "model,data",
    [(DesignFile, d) for d in root_invalid]
    + [(DesignNode, d) for d in node_invalid]
    + [(PageRoot, d) for d in page_invalid]
    + [(TableColumn, d) for d in column_invalid],
)
@pytest.mark.parametrize("as_json", [False, True])
def test_invalid_instances(model: type[BaseModel], data: object, as_json: bool) -> None:
    with pytest.raises(ValidationError):
        if as_json:
            model.model_validate_json(json.dumps(data))
        else:
            model.model_validate(data)


def test_python_coercions_rejected() -> None:
    with pytest.raises(ValidationError):
        DesignFile.model_validate(BASE | {"source_contract": b"a.view.json"})
    with pytest.raises(ValidationError):
        DesignNode.model_validate({"type": "text", "props": {1: "x"}})
    with pytest.raises(ValidationError):
        DesignNode.model_validate({"type": "text", "children": ()})


def test_error_locations() -> None:
    data = BASE | {
        "root": {
            "type": "page",
            "children": [
                {"type": "unknown"},
                {"type": "table", "columns": [{"label": "L"}]},
            ],
        }
    }
    with pytest.raises(ValidationError) as caught:
        DesignFile.model_validate(data)
    assert {(e["loc"], e["type"]) for e in caught.value.errors()} == {
        (("root", "children", 0, "type"), "literal_error"),
        (("root", "children", 1, "columns", 0, "binding"), "missing"),
    }
    with pytest.raises(ValidationError) as broken:
        DesignFile.model_validate_json("{")
    assert broken.value.errors()[0]["type"] == "json_invalid"


def test_frozen_and_mutable_containers() -> None:
    model = DesignFile.model_validate(
        BASE | {"root": {"type": "page", "children": [], "props": {}}}
    )
    with pytest.raises(ValidationError) as caught:
        model.view = "changed"
    assert caught.value.errors()[0]["type"] == "frozen_instance"
    model.root.children.append(DesignNode(type="text"))
    assert model.root.props is not None
    model.root.props["x"] = "changed"
    assert DesignFile.model_validate(model.model_dump(exclude_unset=True)) == model
    model.root.props[""] = "invalid"
    with pytest.raises(ValidationError):
        DesignFile.model_validate(model.model_dump(exclude_unset=True))
    assert BASE["root"]["children"] == []


def test_recursion_reasonable_and_cycle() -> None:
    data: dict[str, Any] = {"type": "text"}
    for _ in range(30):
        data = {"type": "container", "children": [data]}
    assert DesignNode.model_validate(data).model_dump(exclude_unset=True) == data
    cyclic: dict[str, Any] = {"type": "page"}
    cyclic["children"] = [cyclic]
    with pytest.raises(ValidationError) as caught:
        DesignNode.model_validate(cyclic)
    assert any(e["type"] == "recursion_loop" for e in caught.value.errors())


def test_schema_concordance() -> None:
    normative = json.loads(
        files("forge_design.design").joinpath("design.schema.json").read_text()
    )
    generated = DesignFile.model_json_schema()

    def clean(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                k: clean(v)
                for k, v in cast(dict[str, Any], value).items()
                if k not in {"title", "description", "$schema"}
            }
        if isinstance(value, list):
            return [clean(v) for v in cast(list[Any], value)]
        return value

    for key in ("type", "required", "additionalProperties"):
        assert generated[key] == normative[key]
    assert clean(generated["properties"]) == clean(normative["properties"])
    defs = normative["$defs"]
    actual = generated["$defs"]
    assert clean(actual["TableColumn"]) == clean(defs["TableColumn"])
    assert clean(actual["FieldDefinition"]) == clean(defs["FieldDefinition"])
    assert set(actual) == set(defs) - {"PropValue"}
    expected_node = clean(defs["DesignNode"])
    prop = expected_node["properties"]["props"]["additionalProperties"]
    assert prop == {"$ref": "#/$defs/PropValue"}
    prop.clear()
    prop["anyOf"] = [{"type": t} for t in defs["PropValue"]["type"]]
    assert clean(actual["DesignNode"]) == expected_node
    root = clean(actual["PageRoot"])
    assert root["required"] == ["type", "children"]
    expected_node["required"] = ["type", "children"]
    expected_node["properties"]["type"] = {"const": "page", "type": "string"}
    assert root == expected_node


def test_no_filesystem_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> Any:
        raise AssertionError("filesystem access")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    assert DesignFile.model_validate(BASE).view == "home"


@pytest.mark.parametrize("model", [DesignNode, PageRoot])
@pytest.mark.parametrize("as_json", [False, True])
def test_visible_if_omission_and_round_trip(
    model: type[BaseModel], as_json: bool
) -> None:
    cases: list[dict[str, Any]] = [
        {"type": "page", "children": []},
        {"type": "page", "children": [], "visible_if": " peut_créer "},
    ]
    for data in cases:
        result = (
            model.model_validate_json(json.dumps(data))
            if as_json
            else model.model_validate(data)
        )
        assert result.model_dump(exclude_unset=True) == data
        assert json.loads(result.model_dump_json(exclude_unset=True)) == data


@pytest.mark.parametrize("value", [None, "", 1, True, {}, []])
@pytest.mark.parametrize("model", [DesignNode, PageRoot])
@pytest.mark.parametrize("as_json", [False, True])
def test_visible_if_invalid(
    model: type[BaseModel], value: object, as_json: bool
) -> None:
    data: dict[str, Any] = {"type": "page", "children": [], "visible_if": value}
    with pytest.raises(ValidationError):
        if as_json:
            model.model_validate_json(json.dumps(data))
        else:
            model.model_validate(data)
