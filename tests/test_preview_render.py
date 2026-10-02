"""Fragments de preview : structure, sécurité, diagnostics et bornes."""

import builtins
import copy
import os
import socket
import subprocess
from dataclasses import FrozenInstanceError
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest
from test_design_bindings import contract, design

from forge_design.design import (
    DesignFile,
    DesignNode,
    bindings,
    conditional_bindings,
    io,
    nesting,
    table_bindings,
)
from forge_design.limits import (
    MAX_DESIGN_DEPTH,
    MAX_DESIGN_ISSUES,
    MAX_DESIGN_NODES,
    MAX_TABLE_COLUMNS,
)
from forge_design.preview import data as generator
from forge_design.preview import generate_preview_data, render, render_preview


class Parsed(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.stack: list[str] = []
        self.text: list[str] = []
        self.feed(html)
        assert self.stack == []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))
        # Élément vide HTML (input) : jamais de balise fermante.
        if tag not in {"input"}:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        assert self.stack.pop() == tag

    def handle_data(self, data: str) -> None:
        self.text.append(data)


def codes(result: Any) -> list[str]:
    return [i.code.removeprefix("preview.") for i in result.issues]


def fixture(name: str) -> DesignFile:
    return DesignFile.model_validate_json(
        (
            Path(__file__).parent / "fixtures/design" / (name + ".design.json")
        ).read_text()
    )


def table(**extra: Any) -> dict[str, Any]:
    return {
        "type": "table",
        "binding": "contacts",
        "columns": [
            {"label": "Nom", "binding": "nom"},
            {"label": "Email", "binding": "email"},
        ],
        **extra,
    }


def test_minimal_stable() -> None:
    result = render_preview(fixture("minimal"), {})
    assert result.complete and result.issues == ()
    assert (
        result.html
        == '<div data-forge-design-type="page" data-forge-design-preview="page"></div>'
    )


@pytest.mark.parametrize(
    "kind,tag",
    [
        ("page", "div"),
        ("section", "section"),
        ("container", "div"),
        ("grid", "div"),
        ("card", "article"),
        ("title", "h2"),
        ("text", "p"),
        ("button", "button"),
        ("table", "table"),
        ("form", "form"),
        # field : <input> depuis FieldDefinition (tests FD-INTERACT-006 dédiés).
        ("alert", "div"),
        ("empty_state", "div"),
    ],
)
def test_block_mapping(kind: str, tag: str) -> None:
    result = render_preview(design([{"type": kind}]), {})
    assert result.complete
    parsed = Parsed(result.html)
    assert parsed.tags[1][0] == tag
    assert parsed.tags[1][1]["data-forge-design-type"] == kind
    if kind == "button":
        assert parsed.tags[1][1]["type"] == "button" and "Action" in parsed.text
    if kind == "empty_state":
        assert "Aucune donnée" in parsed.text
    assert all(
        "action" not in attrs and "method" not in attrs and "href" not in attrs
        for _, attrs in parsed.tags
    )


@pytest.mark.parametrize(
    "tag",
    [
        "div",
        "section",
        "article",
        "header",
        "footer",
        "main",
        "aside",
        "p",
        "span",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    ],
)
def test_safe_tags(tag: str) -> None:
    result = render_preview(design([{"type": "text", "props": {"tag": tag}}]), {})
    assert result.complete and Parsed(result.html).tags[1][0] == tag


@pytest.mark.parametrize(
    "props,code",
    [
        ({"tag": "script"}, "invalid_tag"),
        ({"tag": "img onerror=alert(1)"}, "invalid_tag"),
        ({"tag": 42}, "unsupported_prop"),
        ({"class": True}, "unsupported_prop"),
        ({"class": 42}, "unsupported_prop"),
        ({"onclick": "x"}, "unsupported_prop"),
        ({"style": "display:grid"}, "unsupported_prop"),
    ],
)
def test_bad_props(props: dict[str, Any], code: str) -> None:
    result = render_preview(design([{"type": "text", "props": props}]), {})
    assert not result.complete and codes(result) == [code]
    assert Parsed(result.html).tags[1] == ("p", {"data-forge-design-type": "text"})
    assert result.issues[0].location[:3] == ("root", "children", 0)


def test_fixed_tag_and_security_escaping() -> None:
    hostile = "<script>alert(1)</script> & \" ' < >"
    classes = 'x" onclick="alert(1)'
    model = design(
        [
            {"type": "text", "binding": "<key>", "props": {"class": classes}},
            table(columns=[{"label": hostile, "binding": "<field>"}]),
            {"type": "button", "binding": hostile, "props": {"tag": "div"}},
        ]
    )
    result = render_preview(
        model, {"<key>": hostile, "contacts": [{"<field>": hostile}]}
    )
    parsed = Parsed(result.html)
    assert codes(result) == ["unsupported_prop"]
    assert parsed.tags[1][1]["class"] == classes
    assert all("onclick" not in attrs for _, attrs in parsed.tags)
    assert not any(tag in {"script", "style", "img"} for tag, _ in parsed.tags)
    assert result.html.count(escape(hostile, quote=True)) == 3
    assert "Action" in parsed.text and parsed.text.count(hostile) == 3


@pytest.mark.parametrize(
    "value,text",
    [
        ("Exemple", "Exemple"),
        (True, "true"),
        (False, "false"),
        (42, "42"),
        (12.5, "12.5"),
    ],
)
def test_scalars(value: object, text: str) -> None:
    result = render_preview(design([{"type": "title", "binding": "x"}]), {"x": value})
    assert result.complete and Parsed(result.html).text == [text]


@pytest.mark.parametrize("value", [{}, [], None, float("nan"), float("inf")])
def test_unsupported_scalar(value: object) -> None:
    result = render_preview(design([{"type": "text", "binding": "x"}]), {"x": value})
    assert codes(result) == ["unsupported_value"] and Parsed(result.html).text == []


def test_missing_text_and_absent_binding() -> None:
    result = render_preview(
        design([{"type": "text", "binding": "x"}, {"type": "title"}]), {}
    )
    assert codes(result) == ["missing_value"]
    assert result.issues[0].location == ("root", "children", 0, "binding")


@pytest.mark.parametrize(
    "data,code,present",
    [
        ({"can_create": True}, None, True),
        ({"can_create": False}, None, False),
        ({}, "missing_condition", False),
        ({"can_create": 1}, "condition_type_mismatch", False),
        ({"can_create": "yes"}, "condition_type_mismatch", False),
        ({"can_create": []}, "condition_type_mismatch", False),
    ],
)
def test_condition_fixture(
    data: dict[str, Any], code: str | None, present: bool
) -> None:
    result = render_preview(fixture("conditional"), data)
    assert ("<button" in result.html) is present
    assert codes(result) == ([] if code is None else [code])
    Parsed(result.html)


def test_root_false_skips_children_and_issues() -> None:
    model = design(
        [{"type": "text", "binding": "missing", "props": {"bad": "x"}}],
        visible_if="literal.name",
    )
    assert render_preview(model, {"literal.name": False}).html == ""
    assert render_preview(model, {"literal.name": False}).complete
    result = render_preview(model, {})
    assert result.issues[0].location == ("root", "visible_if")


def test_contacts_nominal() -> None:
    c = contract(
        {
            "page_title": {"type": "string"},
            "contacts": {
                "type": "list",
                "fields": {"nom": "string", "email": "email", "telephone": "string"},
            },
        }
    )
    result = render_preview(fixture("contacts-list"), generate_preview_data(c).data)
    assert result.complete
    parsed = Parsed(result.html)
    assert any(tag == "header" for tag, _ in parsed.tags)
    assert result.html.split("<tbody>")[1].count("<tr>") == 3
    assert "<th>Nom</th><th>Email</th><th>Téléphone</th>" in result.html
    assert result.html.count("contact@example.test") == 3
    assert "<h1" in result.html and "Exemple" in result.html


def test_table_runtime_diagnostics_and_order() -> None:
    result = render_preview(
        design([table()]),
        {
            "contacts": [
                {"email": "second", "nom": "first"},
                {"nom": list[object]()},
                "bad",
                {"nom": False, "email": 12},
            ]
        },
    )
    assert codes(result) == ["unsupported_value", "missing_field", "row_type_mismatch"]
    assert result.issues[0].location == (
        "root",
        "children",
        0,
        "rows",
        1,
        "columns",
        0,
        "binding",
    )
    assert "<tr><td>first</td><td>second</td></tr>" in result.html
    assert "<tr><td></td><td></td></tr>" in result.html
    assert "<tr><td>false</td><td>12</td></tr>" in result.html
    Parsed(result.html)


@pytest.mark.parametrize("case", ["absent", "missing", "type", "empty", "full"])
def test_table_empty_state(case: str) -> None:
    node = table(children=[{"type": "empty_state"}])
    data: dict[str, object] = {}
    if case == "absent":
        node.pop("binding")
    elif case == "type":
        data["contacts"] = {}
    elif case == "empty":
        data["contacts"] = []
    elif case == "full":
        data["contacts"] = [{"nom": "x", "email": "y"}]
    result = render_preview(design([node]), data)
    assert ("Aucune donnée" in result.html) is (case != "full")
    if case != "full":
        assert '</table><div data-forge-design-type="empty_state">' in result.html
    assert codes(result) == (
        ["missing_value"]
        if case == "missing"
        else ["table_type_mismatch"]
        if case == "type"
        else []
    )
    Parsed(result.html)


@pytest.mark.parametrize("surplus", [0, 1])
def test_node_limits(surplus: int) -> None:
    result = render_preview(
        # Feuille neutre : un field sans définition est désormais diagnostiqué.
        design([{"type": "alert"}] * (MAX_DESIGN_NODES - 1 + surplus)),
        {},
    )
    assert result.complete is (not surplus)
    assert codes(result) == (["analysis_truncated"] if surplus else [])
    Parsed(result.html)


@pytest.mark.parametrize("surplus", [0, 1])
def test_depth_limits(surplus: int) -> None:
    model = design([])
    children = model.root.children
    for _ in range(MAX_DESIGN_DEPTH + surplus):
        node = DesignNode(type="container", children=[])
        children.append(node)
        assert node.children is not None
        children = node.children
    result = render_preview(model, {})
    assert result.complete is (not surplus)
    Parsed(result.html)


@pytest.mark.parametrize("surplus", [0, 1])
def test_issue_limits(surplus: int) -> None:
    result = render_preview(
        design([{"type": "text", "binding": "x"}] * (MAX_DESIGN_ISSUES + surplus)), {}
    )
    assert len(result.issues) == MAX_DESIGN_ISSUES
    assert codes(result)[-1] == ("analysis_truncated" if surplus else "missing_value")
    Parsed(result.html)


@pytest.mark.parametrize("surplus", [0, 1])
def test_columns_limits(surplus: int) -> None:
    result = render_preview(
        design(
            [
                table(
                    columns=[{"label": "L", "binding": "x"}]
                    * (MAX_TABLE_COLUMNS + surplus)
                )
            ]
        ),
        {"contacts": []},
    )
    assert result.complete is (not surplus)
    Parsed(result.html)


def test_output_exact_and_overflow(monkeypatch: pytest.MonkeyPatch) -> None:
    model = design([{"type": "text", "binding": "x"}])
    baseline = render_preview(model, {"x": "<&"})
    monkeypatch.setattr(render, "MAX_PREVIEW_HTML_CHARS", len(baseline.html))
    assert render_preview(model, {"x": "<&"}) == baseline
    monkeypatch.setattr(render, "MAX_PREVIEW_HTML_CHARS", len(baseline.html) - 1)
    result = render_preview(model, {"x": "<&"})
    assert (
        result.html == '<div data-forge-design-preview-error="output-too-large"></div>'
    )
    assert codes(result) == ["output_too_large"] and not result.complete
    Parsed(result.html)
    assert codes(render_preview(model, {"x": "x" * 10000})) == ["output_too_large"]


def test_rows_without_columns_are_output_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(render, "MAX_PREVIEW_HTML_CHARS", 1000)
    result = render_preview(
        design([table(columns=[])]), {"contacts": [dict[str, object]()] * 10000}
    )
    assert codes(result) == ["output_too_large"]


def test_cycle_shared_and_hidden() -> None:
    model = design([])
    node = DesignNode(type="text", binding="x", children=[])
    model.root.children.extend([node, node])
    assert [i.location for i in render_preview(model, {}).issues] == [
        ("root", "children", n, "binding") for n in (0, 1)
    ]
    assert node.children is not None
    node.children.append(node)
    result = render_preview(model, {"x": "ok"})
    assert codes(result) == ["analysis_truncated"]
    Parsed(result.html)


def test_purity_nonmutation_and_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    model = design([table()])
    data: dict[str, object] = {"contacts": [{"nom": "x", "email": "y"}]}
    before = model.model_dump(exclude_unset=True), copy.deepcopy(data)
    refs = model.root.children, model.root.children[0].columns, data["contacts"]

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("unexpected dependency")

    with monkeypatch.context() as p:
        p.setattr(builtins, "open", forbidden)
        p.setattr(os, "open", forbidden)
        p.setattr(Path, "read_text", forbidden)
        p.setattr(Path, "open", forbidden)
        p.setattr(socket, "socket", forbidden)
        p.setattr(subprocess, "run", forbidden)
        p.setattr(io, "read_design", forbidden)
        p.setattr(nesting, "validate_design_nesting", forbidden)
        p.setattr(bindings, "validate_design_bindings", forbidden)
        p.setattr(table_bindings, "validate_table_bindings", forbidden)
        p.setattr(conditional_bindings, "validate_conditional_bindings", forbidden)
        p.setattr(generator, "generate_preview_data", forbidden)
        result = render_preview(model, MappingProxyType(data))
        assert result == render_preview(model, data)
    assert before == (model.model_dump(exclude_unset=True), data)
    assert (
        refs[0] is model.root.children
        and refs[1] is model.root.children[0].columns
        and refs[2] is data["contacts"]
    )
    with pytest.raises(FrozenInstanceError):
        result.complete = False  # type: ignore[misc]


# Formulaires — FD-INTERACT-006.

EMAIL = {
    "name": "email",
    "input_type": "email",
    "label": "Adresse e-mail",
    "required": True,
}


def in_form(*children: dict[str, Any], **form_extra: Any) -> Any:
    holder = {"type": "form", "children": list(children), **form_extra}
    return design([{"type": "section", "children": [holder]}])


def field(definition: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    node: dict[str, Any] = {"type": "field", **extra}
    if definition is not None:
        node["field"] = definition
    return node


def save(label: str = "Enregistrer", **extra: Any) -> dict[str, Any]:
    return {"type": "button", "submit": {"label": label}, **extra}


def test_form_end_criterion() -> None:
    result = render_preview(in_form(field(EMAIL), save()), {})
    assert result.complete and result.issues == ()
    assert result.html == (
        '<div data-forge-design-type="page" data-forge-design-preview="page">'
        '<section data-forge-design-type="section">'
        '<form data-forge-design-type="form">'
        "<label>Adresse e-mail"
        '<input data-forge-design-type="field" type="email" name="email" required>'
        "</label>"
        '<button data-forge-design-type="button" type="submit">Enregistrer</button>'
        "</form></section></div>"
    )
    Parsed(result.html)


def test_form_without_action_attributes() -> None:
    props = {"class": "space-y-4", "hx-target": "#c", "hx-swap": "none"}
    model = in_form(field(EMAIL), save(), binding="create_contact", props=props)
    result = render_preview(model, {})
    for token in (
        "action=",
        "method=",
        "hx-get=",
        "hx-post=",
        "hx-target=",
        "hx-swap=",
        "hx-confirm=",
        "value=",
        "id=",
        "for=",
        "<script",
    ):
        assert token not in result.html
    assert '<form data-forge-design-type="form" class="space-y-4">' in result.html
    # Pas de diagnostic d'action manquante : la preview n'est pas le générateur.
    assert "form_missing_action" not in str(result.issues)
    assert codes(result) == ["unsupported_prop", "unsupported_prop"]


def test_field_minimal() -> None:
    result = render_preview(in_form(field({"name": "name", "input_type": "text"})), {})
    assert result.complete
    assert '<input data-forge-design-type="field" type="text" name="name">' in (
        result.html
    )
    assert "<label" not in result.html


@pytest.mark.parametrize(
    "input_type", ["text", "email", "password", "number", "date", "checkbox"]
)
def test_field_input_types(input_type: str) -> None:
    definition = {"name": "x", "input_type": input_type}
    parsed = Parsed(render_preview(in_form(field(definition)), {}).html)
    inputs = [attrs for tag, attrs in parsed.tags if tag == "input"]
    assert inputs == [
        {"data-forge-design-type": "field", "type": input_type, "name": "x"}
    ]


@pytest.mark.parametrize(
    ("required", "expected"), [(True, " required>"), (False, '"x">'), (None, '"x">')]
)
def test_field_required(required: bool | None, expected: str) -> None:
    definition: dict[str, Any] = {"name": "x", "input_type": "text"}
    if required is not None:
        definition["required"] = required
    html = render_preview(in_form(field(definition)), {}).html
    assert html.count(expected) == 1


def test_field_without_values_from_fake_data() -> None:
    definition = {"name": "page_title", "input_type": "text", "label": "Titre"}
    c = contract({"page_title": {"type": "string"}})
    html = render_preview(
        in_form(field(definition)), generate_preview_data(c).data
    ).html
    assert "Exemple" not in html and "value=" not in html


def test_field_class_on_input_and_unsupported_props() -> None:
    props = {"class": "w-full", "placeholder": "x", "tag": "span", "id": "f"}
    result = render_preview(in_form(field(EMAIL, props=props)), {})
    assert codes(result) == ["unsupported_prop"] * 3
    assert 'name="email" class="w-full" required>' in result.html
    assert "<label>Adresse e-mail<input" in result.html
    assert "placeholder" not in result.html and "<span" not in result.html


def test_field_missing_definition() -> None:
    result = render_preview(in_form(field()), {})
    assert codes(result) == ["missing_field_definition"]
    assert result.issues[0].location[-1] == "field"
    assert "<input" not in result.html and 'type="field"' not in result.html
    assert not result.complete


@pytest.mark.parametrize(
    "hostile", ['"><script>alert(1)</script>', "<img src=x onerror=alert(1)>"]
)
def test_field_hostile_name_and_label(hostile: str) -> None:
    definition = {"name": hostile, "input_type": "text", "label": hostile}
    result = render_preview(in_form(field(definition, props={"class": hostile})), {})
    assert "<script>" not in result.html and "<img" not in result.html
    parsed = Parsed(result.html)
    (attrs,) = [attrs for tag, attrs in parsed.tags if tag == "input"]
    assert attrs["name"] == hostile and attrs["class"] == hostile
    assert escape(hostile) in result.html


def test_submit_minimal_and_class() -> None:
    result = render_preview(in_form(save(props={"class": "px-4 py-2"})), {})
    assert result.complete
    assert (
        '<button data-forge-design-type="button" type="submit" class="px-4 py-2">'
        "Enregistrer</button>"
    ) in result.html
    assert ">Action<" not in result.html


@pytest.mark.parametrize(
    "key", ["hx-target", "hx-swap", "hx-confirm", "onclick", "tag"]
)
def test_submit_unsupported_props(key: str) -> None:
    result = render_preview(in_form(save(props={key: "x()"})), {})
    assert codes(result) == ["unsupported_prop"]
    assert "x()" not in result.html and 'type="submit">Enregistrer' in result.html


def test_submit_hostile_label() -> None:
    hostile = '"><script>alert(1)</script>'
    result = render_preview(in_form(save(hostile)), {})
    assert "<script>" not in result.html and escape(hostile) in result.html
    Parsed(result.html)


def test_submit_with_binding_is_invalid() -> None:
    result = render_preview(in_form(save(binding="cancel")), {})
    assert codes(result) == ["invalid_submit"]
    assert "<button" not in result.html and not result.complete


def test_action_button_unchanged() -> None:
    holder = {"type": "container", "children": [{"type": "button", "binding": "go"}]}
    result = render_preview(design([{"type": "section", "children": [holder]}]), {})
    assert '<button data-forge-design-type="button" type="button">Action</button>' in (
        result.html
    )


@pytest.mark.parametrize("visible", [True, False])
def test_field_and_submit_conditions(visible: bool) -> None:
    model = in_form(field(EMAIL, visible_if="show"), save(visible_if="show"))
    html = render_preview(model, {"show": visible}).html
    assert ("<input" in html) is visible
    assert ('type="submit"' in html) is visible
    assert "<form" in html


def test_field_condition_diagnostics_kept() -> None:
    result = render_preview(in_form(field(EMAIL, visible_if="missing")), {})
    assert codes(result) == ["missing_condition"] and "<input" not in result.html


def test_form_labels_count_in_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    long = "x" * 200
    monkeypatch.setattr(render, "MAX_PREVIEW_HTML_CHARS", 300)
    model = in_form(field({"name": "n", "input_type": "text", "label": long}))
    result = render_preview(model, {})
    assert codes(result) == ["output_too_large"]
    assert (
        result.html == '<div data-forge-design-preview-error="output-too-large"></div>'
    )
    over = render_preview(in_form(save(long)), {})
    assert codes(over) == ["output_too_large"]


def test_form_preview_pure_and_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    model = in_form(field(EMAIL), save())
    before = copy.deepcopy(model.model_dump())

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("effet de bord interdit")

    for target, name in (
        (builtins, "open"),
        (os, "open"),
        (socket, "socket"),
        (subprocess, "Popen"),
    ):
        monkeypatch.setattr(target, name, forbidden)
    first = render_preview(model, {})
    second = render_preview(model, {})
    monkeypatch.undo()
    assert first == second and model.model_dump() == before
