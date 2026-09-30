"""Tables générées : projection existante, structure, états vides et bornes."""

import builtins
import copy
import os
import socket
import subprocess
from pathlib import Path
from typing import Any

import pytest
from jinja2 import Environment, nodes
from test_design_bindings import contract, design
from test_generate_simple import codes, section
from test_preview_render import Parsed

from forge_design.generate import generate_simple_template, simple, tables
from forge_design.limits import MAX_TABLE_COLUMNS


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


def context() -> dict[str, Any]:
    return {
        "contacts": {"type": "list", "fields": {"nom": "string", "email": "email"}},
        "show_contacts": {"type": "boolean"},
    }


NOMINAL = """<table>
  <thead>
    <tr>
      <th>Nom</th>
      <th>Email</th>
    </tr>
  </thead>
  <tbody>
    {% for item in contacts %}
      <tr>
        <td>{{ item.nom }}</td>
        <td>{{ item.email }}</td>
      </tr>
    {% endfor %}
  </tbody>
</table>
"""


def test_nominal_and_reuse(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    loop = tables.render_jinja_loop
    validator = simple.validate_table_bindings

    def tracked_loop(**kwargs: Any) -> tuple[str, ...]:
        calls.append("loop")
        assert kwargs["collection"] == "contacts" and kwargs["item"] == "item"
        return loop(**kwargs)

    def tracked_validator(*args: Any, **kwargs: Any) -> Any:
        calls.append("validator")
        return validator(*args, **kwargs)

    monkeypatch.setattr(tables, "render_jinja_loop", tracked_loop)
    monkeypatch.setattr(simple, "validate_table_bindings", tracked_validator)
    result = generate_simple_template(design([table()]), contract(context()))
    assert result.complete and result.template == NOMINAL
    assert calls == ["validator", "loop"]
    tree = Environment().parse(result.template)
    assert len(list(tree.find_all(nodes.For))) == 1


@pytest.mark.parametrize("count", [0, 1, 2])
def test_columns_order(count: int) -> None:
    node = table()
    node["columns"] = node["columns"][:count]
    result = generate_simple_template(design([node]), contract(context()))
    assert result.complete
    assert result.template.count("<th>") == count
    assert result.template.count("<td>") == count
    Environment().parse(result.template)


def test_nested_condition_and_empty_state() -> None:
    node = table(
        visible_if="show_contacts",
        props={"class": "w-full border"},
        children=[{"type": "empty_state", "props": {"class": "py-8 text-center"}}],
    )
    result = generate_simple_template(design([section([node])]), contract(context()))
    expected_table = NOMINAL.replace("<table>", '<table class="w-full border">')
    assert result.complete
    assert result.template == (
        "<section>\n  {% if show_contacts %}\n    {% if contacts %}\n"
        + "".join("      " + line + "\n" for line in expected_table.splitlines())
        + '    {% else %}\n      <div class="py-8 text-center">Aucune donnée</div>\n'
        + "    {% endif %}\n  {% endif %}\n</section>\n"
    )
    tree = Environment().parse(result.template)
    assert len(list(tree.find_all(nodes.If))) == 2


@pytest.mark.parametrize(
    "case,code,suffix",
    [
        ("missing", "table_missing_binding", ("binding",)),
        ("unknown", "invalid_table_binding", ("binding",)),
        ("non_list", "invalid_table_binding", ("binding",)),
        ("no_fields", "invalid_table_binding", ("columns",)),
        ("unknown_field", "invalid_table_column", ("columns", 0, "binding")),
    ],
)
def test_invalid_tables_omitted_locally(
    case: str, code: str, suffix: tuple[str | int, ...]
) -> None:
    node = table()
    ctx = context()
    if case == "missing":
        del node["binding"]
    elif case == "unknown":
        del ctx["contacts"]
    elif case == "non_list":
        ctx["contacts"] = {"type": "string"}
    elif case == "no_fields":
        ctx["contacts"] = {"type": "list", "entity": "Contact"}
    else:
        node["columns"][0]["binding"] = "missing"
    result = generate_simple_template(design([node, section()]), contract(ctx))
    assert codes(result) == [code] and not result.complete
    assert result.template == "<section></section>\n"
    assert result.issues[0].location == ("root", "children", 0, *suffix)


def test_no_fields_without_columns_and_literal_item() -> None:
    node = table(binding="item", columns=[])
    result = generate_simple_template(
        design([node]), contract({"item": {"type": "list"}})
    )
    assert result.complete and "{% for item in item %}" in result.template
    Environment().parse(result.template)


@pytest.mark.parametrize("target", ["collection", "field"])
@pytest.mark.parametrize(
    "name", ["foo.bar", "foo-bar", 'x }}{% include "evil" %}', "foo | safe"]
)
def test_hostile_identifiers(target: str, name: str) -> None:
    node = table()
    ctx = context()
    if target == "collection":
        ctx[name] = ctx.pop("contacts")
        node["binding"] = name
    else:
        ctx["contacts"]["fields"][name] = "string"
        node["columns"][0]["binding"] = name
    result = generate_simple_template(design([node]), contract(ctx))
    assert codes(result) == [
        "unsupported_binding_syntax"
        if target == "collection"
        else "unsupported_field_syntax"
    ]
    assert result.template == ""


def test_hostile_labels_and_classes() -> None:
    hostile = '<script>x</script> & " {{evil}} {% include "bad" %}\r\n'
    node = table(
        columns=[{"label": hostile, "binding": "nom"}],
        props={"class": hostile},
        children=[{"type": "empty_state", "props": {"class": hostile}}],
    )
    result = generate_simple_template(design([node]), contract(context()))
    assert result.complete
    html = Parsed(result.template)
    assert any(
        tag == "table" and attrs == {"class": hostile} for tag, attrs in html.tags
    )
    assert any(tag == "div" and attrs == {"class": hostile} for tag, attrs in html.tags)
    assert hostile in html.text
    tree = Environment().parse(result.template)
    assert not list(tree.find_all(nodes.Include))
    assert not any(tag == "script" for tag, _ in html.tags)


@pytest.mark.parametrize("target", ["table", "empty"])
@pytest.mark.parametrize("props", [{"tag": "div"}, {"style": "x"}, {"class": 42}])
def test_only_class_props(target: str, props: dict[str, Any]) -> None:
    node = table()
    if target == "table":
        node["props"] = props
    else:
        node["children"] = [{"type": "empty_state", "props": props}]
    result = generate_simple_template(design([node]), contract(context()))
    assert codes(result) == ["unsupported_prop"] and "<table>" in result.template
    assert "<div>Aucune donnée</div>" in result.template if target == "empty" else True


@pytest.mark.parametrize("condition", [None, "show_contacts", "missing"])
def test_ambiguous_empty_states(condition: str | None) -> None:
    children = (
        [{"type": "empty_state"}] * 2
        if condition is None
        else [{"type": "empty_state", "visible_if": condition}]
    )
    result = generate_simple_template(
        design([table(children=children)]), contract(context())
    )
    assert codes(result) == [
        "multiple_empty_states"
        if condition is None
        else "unsupported_empty_state_condition"
    ]
    assert result.template == ""


def test_empty_outside_table_preserves_global_nesting() -> None:
    result = generate_simple_template(design([{"type": "empty_state"}]), contract())
    assert codes(result) == ["invalid_nesting"] and result.template == ""
    generator = simple._Generator()  # pyright: ignore[reportPrivateUsage]
    generator.node(design([{"type": "empty_state"}]).root.children[0], ("root",), 0)
    assert generator.issues[0].code == "generate.unsupported_block"


@pytest.mark.parametrize("surplus", [0, 1])
def test_columns_budget(surplus: int) -> None:
    node = table(
        columns=[{"label": "Nom", "binding": "nom"}] * (MAX_TABLE_COLUMNS + surplus)
    )
    result = generate_simple_template(design([node]), contract(context()))
    assert result.complete is (not surplus)
    if surplus:
        assert codes(result) == ["analysis_truncated"] and result.template == ""
    else:
        Environment().parse(result.template)


def test_output_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    model = design([table(children=[{"type": "empty_state"}])])
    c = contract(context())
    original = generate_simple_template(model, c)
    monkeypatch.setattr(simple, "MAX_GENERATED_TEMPLATE_CHARS", len(original.template))
    assert generate_simple_template(model, c) == original
    monkeypatch.setattr(
        simple, "MAX_GENERATED_TEMPLATE_CHARS", len(original.template) - 1
    )
    result = generate_simple_template(model, c)
    assert result.template == "" and codes(result) == ["output_too_large"]


def test_purity_determinism_nonmutation(monkeypatch: pytest.MonkeyPatch) -> None:
    model = design([table(children=[{"type": "empty_state"}])])
    c = contract(context())
    before = copy.deepcopy((model.model_dump(), c.model_dump()))

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("external access")

    with monkeypatch.context() as patch:
        for owner, name in (
            (builtins, "open"),
            (os, "open"),
            (Path, "open"),
            (Path, "read_text"),
            (Path, "write_text"),
            (socket, "socket"),
            (subprocess, "run"),
        ):
            patch.setattr(owner, name, forbidden)
        result = generate_simple_template(model, c)
        assert result.complete and result == generate_simple_template(model, c)
    assert before == (model.model_dump(), c.model_dump())
    Environment().parse(result.template)
