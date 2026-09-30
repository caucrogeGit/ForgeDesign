"""Génération simple : contrats, Jinja sûr et absence d'I/O."""

import builtins
import copy
import os
import socket
import subprocess
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest
from jinja2 import Environment, nodes
from test_design_bindings import contract, design
from test_preview_render import Parsed

from forge_design.generate import generate_simple_template, simple
from forge_design.limits import MAX_DESIGN_ISSUES, MAX_DESIGN_NODES


def section(children: list[Any] | None = None, **extra: Any) -> dict[str, Any]:
    return {"type": "section", "children": children or [], **extra}


def codes(result: simple.TemplateGenerationResult) -> list[str]:
    return [issue.code.removeprefix("generate.") for issue in result.issues]


def test_empty_and_roadmap() -> None:
    empty = generate_simple_template(design([]), contract())
    assert empty == simple.TemplateGenerationResult("", (), True)
    model = design(
        [
            section(
                [
                    {
                        "type": "text",
                        "binding": "page_title",
                        "props": {"tag": "h1", "class": "text-3xl font-bold"},
                    }
                ],
                props={"class": "max-w-5xl mx-auto py-8"},
            )
        ]
    )
    c = contract({"page_title": {"type": "string"}})
    result = generate_simple_template(model, c)
    assert result.complete and result.issues == ()
    assert result.template == (
        '<section class="max-w-5xl mx-auto py-8">\n'
        '  <h1 class="text-3xl font-bold">{{ page_title }}</h1>\n'
        "</section>\n"
    )
    Environment().parse(result.template)
    assert result == generate_simple_template(model, c)
    assert not any(
        token in result.template
        for token in (
            "{% extends",
            "{% block",
            "{% endblock",
            "data-forge-design-",
            "style=",
        )
    )


@pytest.mark.parametrize(
    "kind,tag",
    [
        ("section", "section"),
        ("container", "div"),
        ("grid", "div"),
        ("card", "article"),
        ("title", "h2"),
        ("text", "p"),
    ],
)
def test_mapping(kind: str, tag: str) -> None:
    node: dict[str, Any] = {"type": kind}
    children = (
        [node]
        if kind == "section"
        else [
            section(
                [{"type": "card", "children": [node]}] if kind == "title" else [node]
            )
        ]
    )
    result = generate_simple_template(design(children), contract())
    assert result.complete and f"<{tag}></{tag}>\n" in result.template
    assert result.template.endswith("\n") and not result.template.endswith("\n\n")
    Environment().parse(result.template)


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
def test_whitelist(tag: str) -> None:
    result = generate_simple_template(design([section(props={"tag": tag})]), contract())
    assert result.complete and result.template == f"<{tag}></{tag}>\n"
    Environment().parse(result.template)


@pytest.mark.parametrize(
    "props,code",
    [
        ({"tag": "script"}, "invalid_tag"),
        ({"tag": "img onerror=x"}, "invalid_tag"),
        ({"tag": 42}, "unsupported_prop"),
        ({"class": True}, "unsupported_prop"),
        ({"style": "color:red"}, "unsupported_prop"),
    ],
)
def test_invalid_props(props: dict[str, Any], code: str) -> None:
    result = generate_simple_template(design([section(props=props)]), contract())
    assert codes(result) == [code] and not result.complete
    assert result.template == "<section></section>\n"


def test_attribute_html_and_jinja_escaping() -> None:
    hostile = 'x" onclick="alert(1) {{ evil }} {% include "evil" %} {# hide #}\n&'
    result = generate_simple_template(
        design([section(props={"class": hostile})]), contract()
    )
    assert result.complete
    assert Parsed(result.template).tags[0] == ("section", {"class": hostile})
    tree = Environment().parse(result.template)
    assert not list(tree.find_all(nodes.Name))
    assert not list(tree.find_all(nodes.Include))
    assert result.template.count("\n") == 1


@pytest.mark.parametrize(
    "name",
    [
        "page-title",
        "page title",
        "contact.email",
        'x }}{% include "evil" %}{{ y',
        "foo | safe",
        "x\n",
        "é",
        "true",
        "False",
        "none",
        "not",
    ],
)
def test_unsupported_binding_syntax(name: str) -> None:
    result = generate_simple_template(
        design([section([{"type": "text", "binding": name}])]),
        contract({name: {"type": "string"}}),
    )
    assert codes(result) == ["unsupported_binding_syntax"]
    assert result.template == "<section>\n  <p></p>\n</section>\n"


@pytest.mark.parametrize("context", [{}, {"x": {"type": "boolean"}}])
def test_invalid_binding_is_global(context: dict[str, Any]) -> None:
    result = generate_simple_template(
        design([section([{"type": "text", "binding": "x"}]), section()]),
        contract(context),
    )
    assert not result.complete and result.template == ""
    assert codes(result) == ["invalid_binding"]
    assert result.issues[0].location == (
        "root",
        "children",
        0,
        "children",
        0,
        "binding",
    )


@pytest.mark.parametrize(
    "kind", ["button", "table", "form", "field", "alert", "empty_state"]
)
def test_unsupported_branches(kind: str) -> None:
    node: dict[str, Any] = {"type": kind, "binding": "unknown"}
    if kind == "button":
        branch = section([{"type": "container", "children": [node]}])
    elif kind == "field":
        branch = section([{"type": "form", "children": [node]}])
    elif kind == "empty_state":
        branch = {"type": "table", "children": [node]}
    else:
        branch = section([node])
    result = generate_simple_template(design([branch, section()]), contract())
    assert codes(result) == ["unsupported_block"]
    assert not result.complete and result.template.endswith("<section></section>\n")
    assert "<table" not in result.template and "<button" not in result.template


@pytest.mark.parametrize("root", [True, False])
def test_conditions_generated(root: bool) -> None:
    kwargs = {"visible_if": "show"} if root else {}
    child = section(visible_if="show") if not root else section()
    result = generate_simple_template(
        design([child], **kwargs),
        contract({"show": {"type": "boolean"}}),
    )
    assert codes(result) == [] and result.complete
    assert result.template == "{% if show %}\n  <section></section>\n{% endif %}\n"


def test_invalid_nesting() -> None:
    result = generate_simple_template(design([{"type": "text"}]), contract())
    assert result.template == "" and codes(result) == ["invalid_nesting"]


def test_mutations_revalidated() -> None:
    model = design([section(props={"class": "x"})])
    props = model.root.children[0].props
    assert props is not None
    props["bad"] = []  # type: ignore[assignment]
    with pytest.warns(UserWarning):
        result = generate_simple_template(model, contract())
    assert codes(result) == ["invalid_design"] and result.template == ""
    c = contract({"x": {"type": "object", "fields": {"name": "string"}}})
    fields = c.context["x"].fields
    assert fields is not None
    fields["bad"] = []  # type: ignore[assignment]
    with pytest.warns(UserWarning):
        result = generate_simple_template(design([]), c)
    assert codes(result) == ["invalid_contract"] and result.template == ""


@pytest.mark.parametrize("surplus", [0, 1])
def test_nodes_limit(surplus: int) -> None:
    result = generate_simple_template(
        design([section()] * (MAX_DESIGN_NODES - 1 + surplus)), contract()
    )
    assert result.complete is (not surplus)
    if surplus:
        assert result.template == "" and codes(result) == ["analysis_truncated"]


@pytest.mark.parametrize("surplus", [0, 1])
def test_depth_limit(surplus: int, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(simple, "MAX_DESIGN_DEPTH", 2)
    children: list[Any] = [{"type": "container"}]
    if surplus:
        children = [{"type": "container", "children": [{"type": "text"}]}]
    result = generate_simple_template(design([section(children)]), contract())
    assert result.complete is (not surplus)
    if surplus:
        assert codes(result) == ["analysis_truncated"]


@pytest.mark.parametrize("surplus", [0, 1])
def test_issue_limit(surplus: int) -> None:
    result = generate_simple_template(
        design([section(props={"bad": "x"})] * (MAX_DESIGN_ISSUES + surplus)),
        contract(),
    )
    assert len(result.issues) == MAX_DESIGN_ISSUES
    assert codes(result)[-1] == (
        "analysis_truncated" if surplus else "unsupported_prop"
    )
    assert bool(result.template) is (not surplus)


def test_cycles_and_bad_children() -> None:
    model = design([section()])
    node = model.root.children[0]
    assert node.children is not None
    node.children.append(node)
    result = generate_simple_template(model, contract())
    assert codes(result) == ["analysis_truncated"] and result.template == ""
    node.children.clear()
    node.children.append("bad")  # type: ignore[arg-type]
    assert codes(generate_simple_template(model, contract())) == ["invalid_design"]


def test_output_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    model = design([section(props={"class": '<&"{{'})])
    baseline = generate_simple_template(model, contract())
    monkeypatch.setattr(simple, "MAX_GENERATED_TEMPLATE_CHARS", len(baseline.template))
    assert generate_simple_template(model, contract()) == baseline
    monkeypatch.setattr(
        simple, "MAX_GENERATED_TEMPLATE_CHARS", len(baseline.template) - 1
    )
    result = generate_simple_template(model, contract())
    assert result.template == "" and codes(result) == ["output_too_large"]


def test_purity_and_nonmutation(monkeypatch: pytest.MonkeyPatch) -> None:
    model = design([section([{"type": "text", "binding": "_title2"}])])
    c = contract({"_title2": {"type": "string"}})
    before = copy.deepcopy((model.model_dump(), c.model_dump()))
    refs = model.root.children, c.context

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
    assert refs[0] is model.root.children and refs[1] is c.context
    with pytest.raises(FrozenInstanceError):
        result.complete = False  # type: ignore[misc]
    Environment().parse(result.template)
