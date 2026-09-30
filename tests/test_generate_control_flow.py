"""Conditions contractuelles et primitive interne de boucle, sans runtime Jinja."""

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

from forge_design.generate import generate_simple_template, simple
from forge_design.generate.control_flow import render_jinja_loop


def test_root_nested_classes_and_text() -> None:
    model = design(
        [
            section(
                [
                    {
                        "type": "card",
                        "visible_if": "can_edit",
                        "children": [
                            {
                                "type": "title",
                                "binding": "page_title",
                                "visible_if": "_show",
                                "props": {
                                    "tag": "h1",
                                    "class": "text-3xl font-bold",
                                },
                            }
                        ],
                    }
                ]
            )
        ],
        visible_if="can_view",
    )
    c = contract(
        {
            "can_view": {"type": "boolean"},
            "can_edit": {"type": "boolean"},
            "_show": {"type": "boolean"},
            "page_title": {"type": "string"},
        }
    )
    result = generate_simple_template(model, c)
    assert result.complete
    assert result.template == (
        "{% if can_view %}\n"
        "  <section>\n"
        "    {% if can_edit %}\n"
        "      <article>\n"
        "        {% if _show %}\n"
        '          <h1 class="text-3xl font-bold">{{ page_title }}</h1>\n'
        "        {% endif %}\n"
        "      </article>\n"
        "    {% endif %}\n"
        "  </section>\n"
        "{% endif %}\n"
    )
    tree = Environment().parse(result.template)
    assert len(list(tree.find_all(nodes.If))) == 3


@pytest.mark.parametrize(
    "kind", ["page", "section", "container", "grid", "card", "title", "text"]
)
def test_all_supported_conditions(kind: str) -> None:
    node: dict[str, Any] = {"type": kind, "visible_if": "enabled"}
    if kind == "page":
        model = design([], visible_if="enabled")
    elif kind == "section":
        model = design([node])
    elif kind == "title":
        model = design([section([{"type": "card", "children": [node]}])])
    else:
        model = design([section([node])])
    result = generate_simple_template(model, contract({"enabled": {"type": "boolean"}}))
    assert result.complete and result.template.count("{% if enabled %}") == 1
    Environment().parse(result.template)


@pytest.mark.parametrize("context", [{}, {"flag": {"type": "string"}}])
def test_invalid_condition_locations(context: dict[str, Any]) -> None:
    model = design([section([{"type": "text", "visible_if": "flag"}])])
    result = generate_simple_template(model, contract(context))
    assert result.template == "" and not result.complete
    assert codes(result) == ["invalid_condition"]
    assert result.issues[0].location == (
        "root",
        "children",
        0,
        "children",
        0,
        "visible_if",
    )


@pytest.mark.parametrize(
    "name",
    [
        "can-create",
        "permission.create",
        "can create",
        "not flag",
        "x and y",
        'x %}{% include "evil" %}',
        "foo | safe",
        "true",
        "False",
        "none",
    ],
)
def test_condition_syntax(name: str) -> None:
    result = generate_simple_template(
        design([section(visible_if=name)]),
        contract({name: {"type": "boolean"}}),
    )
    assert codes(result) == ["unsupported_condition_syntax"]
    assert result.template == "" and not result.complete
    assert result.issues[0].location == ("root", "children", 0, "visible_if")


def test_unsupported_table_remains_omitted() -> None:
    result = generate_simple_template(
        design([{"type": "table", "binding": "contacts", "visible_if": "flag"}]),
        contract({"contacts": {"type": "list"}, "flag": {"type": "boolean"}}),
    )
    assert codes(result) == ["unsupported_block"] and result.template == ""


@pytest.mark.parametrize(
    "collection,item", [("contacts", "contact"), ("users", "user")]
)
@pytest.mark.parametrize("indent", [0, 2])
@pytest.mark.parametrize(
    "body",
    [
        ("<p>{{ item_name }}</p>",),
        ("<tr>", "  <td>{{ contact.nom }}</td>", "</tr>"),
        (),
    ],
)
def test_loop_structure(
    collection: str, item: str, indent: int, body: tuple[str, ...]
) -> None:
    result = render_jinja_loop(
        collection=collection, item=item, body=body, indent=indent
    )
    assert result == (
        "  " * indent + "{% for " + item + " in " + collection + " %}",
        *("  " * (indent + 1) + line for line in body),
        "  " * indent + "{% endfor %}",
    )
    assert result == render_jinja_loop(
        collection=collection, item=item, body=body, indent=indent
    )
    parsed = Environment().parse("\n".join(result))
    assert len(list(parsed.find_all(nodes.For))) == 1


@pytest.mark.parametrize(
    "name",
    [
        "user.contacts",
        "contacts | sort",
        "contacts[:10]",
        "get_contacts()",
        "foo-bar",
        'x %}{% include "evil" %}',
        "foo | safe",
        "",
        "1name",
        "True",
        "in",
        "x\n",
    ],
)
@pytest.mark.parametrize("target", ["collection", "item"])
def test_loop_rejects_expressions(name: str, target: str) -> None:
    kwargs = {"collection": "contacts", "item": "contact", target: name}
    with pytest.raises(ValueError):
        render_jinja_loop(
            collection=kwargs["collection"], item=kwargs["item"], body=("<p></p>",)
        )


def test_loop_programming_invariants() -> None:
    with pytest.raises(ValueError):
        render_jinja_loop(collection="contacts", item="loop", body=())
    for indent in (-1, True):
        with pytest.raises(ValueError):
            render_jinja_loop(
                collection="contacts", item="contact", body=(), indent=indent
            )
    with pytest.raises(ValueError):
        render_jinja_loop(collection="contacts", item="contact", body=("a\nb",))


def test_conditions_use_existing_output_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    model = design([section()], visible_if="flag")
    c = contract({"flag": {"type": "boolean"}})
    baseline = generate_simple_template(model, c)
    monkeypatch.setattr(simple, "MAX_GENERATED_TEMPLATE_CHARS", len(baseline.template))
    assert generate_simple_template(model, c) == baseline
    monkeypatch.setattr(
        simple, "MAX_GENERATED_TEMPLATE_CHARS", len(baseline.template) - 1
    )
    result = generate_simple_template(model, c)
    assert codes(result) == ["output_too_large"] and result.template == ""


def test_purity_nonmutation_and_validator_reuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = design([section([{"type": "text", "binding": "title"}], visible_if="flag")])
    c = contract({"flag": {"type": "boolean"}, "title": {"type": "string"}})
    before = copy.deepcopy((model.model_dump(), c.model_dump()))
    original = simple.validate_conditional_bindings
    calls: list[bool] = []

    def tracked(*args: Any, **kwargs: Any) -> Any:
        calls.append(True)
        return original(*args, **kwargs)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("external access")

    monkeypatch.setattr(simple, "validate_conditional_bindings", tracked)
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
        assert render_jinja_loop(collection="contacts", item="contact", body=())
    assert len(calls) == 2
    assert before == (model.model_dump(), c.model_dump())
