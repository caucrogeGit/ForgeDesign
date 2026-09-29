"""Projection pure et bornée, primitives partagées avec Route Explorer."""

import builtins
import os
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from jinja2 import Environment, Template

from forge_design.forge import template_structure as module
from forge_design.forge import templates
from forge_design.forge.template_structure import (
    HtmlElement,
    TemplateBlock,
    TemplateReference,
    analyze_template_structure,
    mask_jinja,
)
from forge_design.limits import (
    MAX_SOURCE_BYTES,
    MAX_SYNTAX_MESSAGE_LENGTH,
    MAX_TEMPLATE_BLOCKS,
    MAX_TEMPLATE_REFERENCES,
    MAX_TEMPLATE_STRUCTURE_NODES,
)
from forge_design.platform.tool_registry import ToolRegistry


@pytest.mark.parametrize("source", ["", "texte simple", "{{ unknown() }}"])
def test_empty_and_text(source: str) -> None:
    result = analyze_template_structure(source)
    assert result.syntax.status == "valid"
    assert not result.dependencies and not result.blocks and not result.html_elements
    assert not result.partial and not result.truncated and not result.issues


def test_references_blocks_order() -> None:
    source = """{% extends "base" %}{% include ["b", "a"] ignore missing %}
{% import "forms" as forms %}{% from "ui" import card, button %}
{% block first %}{% block nested %}{% endblock %}{% endblock %}
{% block first %}{% endblock %}
{% if condition %}{% include selected %}{% else %}{% include "fallback" %}{% endif %}
{% extends layout %}{% include ["literal", dynamic] %}{% include [] %}"""
    result = analyze_template_structure(source)
    assert result.syntax.status == "valid"
    assert [(r.kind, r.path, r.dynamic, r.line) for r in result.dependencies] == [
        ("extends", "base", False, 1),
        ("include", "b", False, 1),
        ("include", "a", False, 1),
        ("import", "forms", False, 2),
        ("from-import", "ui", False, 2),
        ("include", None, True, 5),
        ("include", "fallback", False, 5),
        ("extends", None, True, 6),
        ("include", None, True, 6),
        ("include", None, True, 6),
    ]
    assert result.blocks == (
        TemplateBlock("first", 3),
        TemplateBlock("nested", 3),
        TemplateBlock("first", 4),
    )
    assert result == analyze_template_structure(source)
    for value in (result, result.syntax, result.dependencies[0], result.blocks[0]):
        with pytest.raises(FrozenInstanceError):
            setattr(value, "line", 99)


def test_html_tolerance() -> None:
    result = analyze_template_structure("""<!DOCTYPE html><!-- ignored -->
<HTML><head><meta><link/><title>x</title></head>
<body><section><div><span></div><BR><img><input><custom />
<script>let s = "<fake>";</script><style>.x { content: "<fake>"; }</style>
</section></body></HTML></unknown><footer>""")
    assert result.syntax.status == "valid"
    assert [(e.tag, e.depth) for e in result.html_elements] == [
        ("html", 0),
        ("head", 1),
        ("meta", 2),
        ("link", 2),
        ("title", 2),
        ("body", 1),
        ("section", 2),
        ("div", 3),
        ("span", 4),
        ("br", 3),
        ("img", 3),
        ("input", 3),
        ("custom", 3),
        ("script", 3),
        ("style", 3),
        ("footer", 0),
    ]
    assert result.html_elements[0].line == 2
    assert not result.partial  # Aucune validation HTML revendiquée.
    with pytest.raises(FrozenInstanceError):
        setattr(result.html_elements[0], "tag", "other")


@pytest.mark.parametrize(
    "jinja",
    [
        '{% set x = "<fake>" %}',
        '{{ "<fake>" }}',
        "{# <fake> #}",
        '{{ "}}<fake>" }}',
        '{% set x = "%}<fake>" %}',
        '{{ {"key": "<fake>"}}}',
        '{{ "escaped\\"<fake>" }}',
        '{%- set x = "<fake>" -%}',
        "{% if\n condition\n%}{% endif %}",
    ],
)
def test_mask_quotes_brackets_and_lines(jinja: str) -> None:
    source = (
        jinja + '\n<div class="{{ css }}">{% if user %}<span>x</span>{% endif %}</div>'
    )
    masked, partial = mask_jinja(source)
    assert not partial and len(masked) == len(source)
    assert masked.count("\n") == source.count("\n")
    result = analyze_template_structure(source)
    assert result.syntax.status == "valid"
    assert result.html_elements == (
        HtmlElement("div", jinja.count("\n") + 2, 0),
        HtmlElement("span", jinja.count("\n") + 2, 1),
    )


def test_raw_and_crlf() -> None:
    source = '{% raw %}\r\n<real>{{ "<literal>" }}{% not jinja %}{% endraw %}\n<after>'
    masked, partial = mask_jinja(source)
    assert not partial and masked.count("\n") == 2 and "\r\n" in masked
    result = analyze_template_structure(source)
    assert [e.tag for e in result.html_elements] == ["real", "literal", "after"]
    assert result.html_elements[-1].line == 3


@pytest.mark.parametrize(
    "source",
    [
        "<div>\n{% if\n<fake>",
        "<section>\n{% unknown %}<p>",
        '<section>{{ "unterminated<fake>',
        "<div>{% raw %}<p>",
    ],
)
def test_invalid_partial(source: str) -> None:
    result = analyze_template_structure(source)
    assert result.syntax.status == "invalid" and result.partial
    assert result.syntax.line is not None
    assert len(result.syntax.message or "") <= MAX_SYNTAX_MESSAGE_LENGTH
    assert result.html_elements[0].depth == 0
    assert "fake" not in [e.tag for e in result.html_elements]
    assert {i.code for i in result.issues} == {
        "template.syntax_invalid",
        "template.html_partial",
    }


@pytest.mark.parametrize("kind", ["references", "blocks", "html"])
@pytest.mark.parametrize("extra", [0, 1])
def test_limits(kind: str, extra: int) -> None:
    count = {
        "references": MAX_TEMPLATE_REFERENCES,
        "blocks": MAX_TEMPLATE_BLOCKS,
        "html": MAX_TEMPLATE_STRUCTURE_NODES,
    }[kind]
    source = {
        "references": '{% include "missing" %}',
        "blocks": "{% block same %}{% endblock %}",
        "html": "<div></div>",
    }[kind] * (count + extra)
    result = analyze_template_structure(source)
    values = {
        "references": result.dependencies,
        "blocks": result.blocks,
        "html": result.html_elements,
    }[kind]
    assert len(values) == count and result.truncated == bool(extra)
    assert result.partial == bool(extra)
    assert any(i.code == "template.structure_truncated" for i in result.issues) == bool(
        extra
    )


def test_include_list_limit() -> None:
    source = "{% include [" + ",".join('"x"' for _ in range(513)) + "] %}"
    result = analyze_template_structure(source)
    assert len(result.dependencies) == 512 and result.truncated


def test_pathological_and_token_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    result = analyze_template_structure("{% if x %}" * 10000)
    assert result.syntax.status == "unreadable" and result.truncated
    result = analyze_template_structure("{{ " + "(" * 3000 + "x" + ")" * 3000 + " }}")
    assert result.syntax.status == "unreadable" and result.partial
    result = analyze_template_structure("x" * (MAX_SOURCE_BYTES + 1))
    assert result.syntax.status == "unreadable" and result.truncated

    def recurse(*args: object, **kwargs: object) -> None:
        raise RecursionError

    monkeypatch.setattr(Environment, "parse", recurse)
    result = analyze_template_structure("<div>")
    assert result.syntax.status == "unreadable"
    assert result.html_elements == (HtmlElement("div", 1, 0),)


def test_purity(monkeypatch: pytest.MonkeyPatch) -> None:
    source = (
        '{% include "absent" %}{% block a %}<div>{{ unknown() }}</div>{% endblock %}'
    )
    expected = analyze_template_structure(source)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("No I/O, rendering, compilation or project access")

    with monkeypatch.context() as guard:
        for owner, names in (
            (builtins, ("open",)),
            (os, ("open", "stat", "listdir", "scandir")),
            (Path, ("open", "read_text", "read_bytes", "stat", "iterdir")),
            (ToolRegistry, ("get",)),
            (templates, ("read_template_source",)),
            (Environment, ("get_template", "from_string", "compile")),
            (Template, ("render", "generate", "stream")),
        ):
            for name in names:
                guard.setattr(owner, name, forbidden)
        assert analyze_template_structure(source) == expected
    assert expected.dependencies == (TemplateReference("include", "absent", False, 1),)
    text = Path(module.__file__).read_text()
    assert "from pathlib" not in text and "import os" not in text
    assert "forge_design.forge.source" not in text


def test_numeric_literal_limit_and_syntax_message() -> None:
    result = analyze_template_structure("{{ " + "9" * 5000 + " }}")
    assert result.syntax.status == "unreadable" and result.truncated
    invalid = analyze_template_structure("{% " + "unknown" * 100 + " %}")
    assert invalid.syntax.status == "invalid"
    assert len(invalid.syntax.message or "") == MAX_SYNTAX_MESSAGE_LENGTH


def test_many_raw_sections_and_unfinished_markup() -> None:
    source = '{% raw %}{{ "<literal>" }}{% odd %}{% endraw %}\n' * 100
    result = analyze_template_structure(source)
    assert result.syntax.status == "valid" and not result.partial
    assert len(result.html_elements) == 100
    assert result.html_elements[-1].line == 100
    # HTMLParser tolérant : une balise inachevée ne devient pas une validation.
    assert not analyze_template_structure("<unfinished").html_elements
