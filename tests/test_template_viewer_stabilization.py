"""Contrats transversaux, bornes et défauts reproduits de la verticale templates."""

import inspect
import os
import sys
from dataclasses import fields
from pathlib import Path
from types import FrameType
from typing import Protocol

import pytest
from test_templates import make_views
from test_web_entity_graph import SvgDocument
from test_web_recent_projects import call, running

from forge_design import limits
from forge_design.app import create_tool_registry
from forge_design.forge import routes, source, template_structure, templates
from forge_design.forge.template_structure import (
    HtmlElement,
    TemplateStructure,
    TemplateSyntaxInfo,
    analyze_template_structure,
    mask_jinja,
)
from forge_design.recent_projects import RecentProjects
from forge_design.tools import template_navigation, template_tree
from forge_design.tools.template_navigation import resolve_template_references
from forge_design.tools.template_tree import build_template_tree, flatten_template_tree
from forge_design.web.template_viewer import template_tree_url, template_url


class Trace(Protocol):
    def __call__(
        self, frame: FrameType, event: str, arg: object, /
    ) -> "Trace | None": ...


def test_public_contracts() -> None:
    for function, parameters in (
        (templates.read_templates, ("root",)),
        (templates.read_template_source, ("root", "template_path")),
        (analyze_template_structure, ("source",)),
        (build_template_tree, ("structure",)),
        (flatten_template_tree, ("tree",)),
        (template_navigation.reference_rejection, ("reference",)),
        (resolve_template_references, ("root", "references")),
    ):
        assert tuple(inspect.signature(function).parameters) == parameters
    for model in (
        templates.TemplateInfo,
        templates.TemplateIssue,
        templates.TemplatesResult,
        templates.TemplateSource,
        template_structure.TemplateSyntaxInfo,
        template_structure.TemplateReference,
        template_structure.TemplateBlock,
        template_structure.HtmlElement,
        template_structure.TemplateStructureIssue,
        template_structure.TemplateStructure,
        template_tree.TemplateHtmlNode,
        template_tree.TemplateTree,
        template_tree.TemplateTreeRow,
        template_navigation.TemplateNavigation,
    ):
        assert getattr(model, "__dataclass_params__").frozen
        assert fields(model)
    assert [t.id for t in create_tool_registry().list()] == [
        "project-inspector",
        "route-explorer",
        "entity-explorer",
        "debug-center",
        "template-viewer",
    ]
    assert (
        limits.MAX_TEMPLATE_FILES,
        limits.MAX_TEMPLATE_DIRECTORY_ENTRIES,
        limits.MAX_TEMPLATE_SCAN_DEPTH,
        limits.MAX_SOURCE_BYTES,
        limits.MAX_SOURCE_PATH_LENGTH,
        limits.MAX_TEMPLATE_STRUCTURE_CHARS,
        limits.MAX_TEMPLATE_STRUCTURE_NODES,
        limits.MAX_TEMPLATE_REFERENCES,
        limits.MAX_TEMPLATE_BLOCKS,
        limits.MAX_TEMPLATE_JINJA_TOKENS,
        limits.MAX_SYNTAX_MESSAGE_LENGTH,
    ) == (
        512,
        4096,
        32,
        1048576,
        4096,
        1048576,
        4096,
        512,
        512,
        32768,
        240,
    )


def test_inventory_real_budgets(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    for i in range(512):
        (views / f"{i:04}").touch()
    for i in range(4096 - 512):
        (views / f".ignored{i}").touch()
    result = templates.read_templates(root)
    assert len(result.templates) == 512 and not result.truncated
    (views / "extra").touch()
    result = templates.read_templates(root)
    assert result.truncated and len(result.templates) <= 512
    assert [i.code for i in result.issues] == ["template.analysis_truncated"]


@pytest.mark.parametrize("extra", [0, 1])
def test_syntax_token_boundary(extra: int, monkeypatch: pytest.MonkeyPatch) -> None:
    text = "{{ x }}"
    from jinja2 import Environment

    count = len(tuple(Environment(loader=None).lex(text)))
    monkeypatch.setattr(template_structure, "MAX_TEMPLATE_JINJA_TOKENS", count - extra)
    result = analyze_template_structure(text)
    assert result.truncated == bool(extra) and result.partial == bool(extra)
    assert result.syntax.status == ("unreadable" if extra else "valid")
    assert len({i.code for i in result.issues}) == len(result.issues)


@pytest.mark.parametrize("ending", ["\n", "\r\n", "\r"])
def test_consistent_line_numbers(ending: str) -> None:
    text = ending.join(("<div>", "{% block second %}<span>{% endblock %}"))
    result = analyze_template_structure(text)
    assert result.blocks[0].line == result.html_elements[1].line == 2
    assert mask_jinja(text)[0].count("\n") == text.count("\n")


def test_unknown_closures_do_not_scan_depth() -> None:
    def cost(depth: int) -> int:
        parser = template_structure._HtmlStructure()  # pyright: ignore[reportPrivateUsage]
        parser.feed("<div>" * depth)
        code = parser.handle_endtag.__code__
        events = 0

        def trace(frame: FrameType, event: str, arg: object) -> Trace:
            nonlocal events
            if frame.f_code is code and event == "line":
                events += 1
            return trace

        previous = sys.gettrace()
        try:
            sys.settrace(trace)
            parser.feed("</unknown>" * 100)
        finally:
            sys.settrace(previous)
        assert len(parser.stack) == depth
        parser.feed("</div>" * depth + "<footer>")
        assert parser.elements[-1].depth == 0
        return events

    assert cost(512) <= 2 * cost(8)


@pytest.mark.parametrize(
    "text,valid,tags",
    [
        ("{% raw %}\n{% endraw %}\n{% endraw %}<p>", False, ["p"]),
        ('{% raw %}"{% endraw %}"<p>', True, ["p"]),
        ('{% set x = "\\"%}<fake>" %}\r\n<div>', True, ["div"]),
        ('{# <fake> {{ " #}<section>', True, ["section"]),
        ("{% raw %}<p>{% endraw %}" * 100, True, ["p"] * 100),
        ('<section>{{ "unclosed<fake>', False, ["section"]),
    ],
)
def test_lexical_edges(text: str, valid: bool, tags: list[str]) -> None:
    masked, _ = mask_jinja(text)
    assert len(masked) == len(text) and masked.count("\n") == text.count("\n")
    result = analyze_template_structure(text)
    assert (result.syntax.status == "valid") == valid
    assert [e.tag for e in result.html_elements] == tags
    assert result.partial == (not valid)
    assert not result.truncated


def test_partial_independent_of_issue_collection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(self: object, text: str) -> None:
        raise ValueError("parser interrupted")

    monkeypatch.setattr(template_structure._HtmlStructure, "feed", fail)  # pyright: ignore[reportPrivateUsage]
    result = analyze_template_structure("<div>")
    assert result.partial and not result.truncated and result.syntax.status == "valid"
    assert [i.code for i in result.issues] == ["template.html_partial"]


def test_chars_boundary_separate_from_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(template_structure, "MAX_TEMPLATE_STRUCTURE_CHARS", 4)
    assert not analyze_template_structure("😀" * 4).truncated
    assert analyze_template_structure("😀" * 5).truncated


@pytest.mark.parametrize(
    "name",
    [
        "env",
        "ENV",
        "Private.KEY",
        "private.pem",
        "ID_RSA_backup",
        "id_dsa",
        "id_ecdsa.pub",
        "ID_ED25519",
    ],
)
def test_policy_shared_at_depth(tmp_path: Path, name: str) -> None:
    root, views = make_views(tmp_path)
    path = "sub/" + name + "/page"
    (views / path).parent.mkdir(parents=True)
    (views / path).touch()
    assert source.template_source(path) is None
    with pytest.raises(source.SourceReadError):
        source.inspect_project_source(root, "mvc/views/" + path)
    assert not templates.read_templates(root).templates
    reference = template_structure.TemplateReference("include", path, False, 1)
    assert resolve_template_references(root, (reference,))[0].status == "invalid-path"


def test_same_size_mutation_and_descriptor_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, views = make_views(tmp_path)
    file = views / "page"
    file.write_text("AAAA")
    original = os.fstat
    file_id = file.stat().st_ino
    calls = 0
    before = set(os.listdir("/proc/self/fd"))

    def mutate(fd: int) -> os.stat_result:
        nonlocal calls
        metadata = original(fd)
        if metadata.st_ino == file_id:
            calls += 1
            if calls == 2:
                file.write_text("BBBB")
                old = metadata.st_mtime_ns
                os.utime(file, ns=(old, old + 1000000000))
                return original(fd)
        return metadata

    monkeypatch.setattr(os, "fstat", mutate)
    with pytest.raises(source.SourceReadError, match="modifiée"):
        source.read_project_source_details(root, "mvc/views/page")
    monkeypatch.undo()
    for _ in range(20):
        source.inspect_project_source(root, "mvc/views/page")
        with pytest.raises(FileNotFoundError):
            source.inspect_project_source(root, "mvc/views/missing")
    assert set(os.listdir("/proc/self/fd")) == before


def test_route_primitives_unchanged() -> None:
    text = '{% include ["a", "b"] %}{% include ["a", dynamic] %}{% extends layout %}'
    syntax, ast = template_structure.parse_template(text)
    assert syntax.status == "valid" and ast is not None
    historical = routes._template_dependencies(ast)  # pyright: ignore[reportPrivateUsage]
    current = analyze_template_structure(text).dependencies
    assert [(r.kind, r.path, r.dynamic, r.line) for r in historical] == [
        (r.kind, r.path, r.dynamic, r.line) for r in current
    ]


def test_tree_skips_and_deep() -> None:
    structure = TemplateStructure(
        TemplateSyntaxInfo("valid"),
        html_elements=tuple(
            HtmlElement(str(i), i + 1, d)
            for i, d in enumerate((5, 100, 100, 0, 1, 2, 1, 0))
        ),
    )
    assert [r.depth for r in flatten_template_tree(build_template_tree(structure))] == [
        0,
        1,
        1,
        0,
        1,
        2,
        1,
        0,
    ]
    deep = analyze_template_structure("<div>" * 4096)
    rows = flatten_template_tree(build_template_tree(deep))
    assert len(rows) == 4096 and rows[-1].close_levels == 4095


def test_unicode_binary_http_and_query_convention(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    names = ("é", "e\u0301", "ß 😀 +&%#?", "%2e%2e")
    for i, name in enumerate(names):
        (views / name).write_text(f"value {i}")
    (views / "binary").write_bytes(b"\xff")
    (views / "page").write_text('{% include "binary" %}')
    with running(RecentProjects(tmp_path / "xdg/recent.json")) as app:
        for page in ("/templates/view?path=page", "/templates/tree?path=page"):
            assert call(app, page)[0] == 409
        assert call(app, "/templates")[0] == 200
        call(app, "/inspector", method="POST", value=str(root))
        for i, name in enumerate(names):
            status, html, headers = call(app, template_url(name))
            assert status == 200 and f"value {i}" in html
            assert headers["Cache-Control"] == "no-store"
            doc = SvgDocument()
            doc.feed(html)
            assert template_tree_url(name) in [a.get("href") for _, a in doc.tags]
            assert call(app, template_tree_url(name))[0] == 200
        assert (
            'data-navigation-status="available"'
            in call(app, template_tree_url("page"))[1]
        )
        for url, code in (
            (template_url("binary"), 409),
            (template_tree_url("binary"), 409),
            ("/templates/view?path=missing", 404),
            ("/templates/tree?path=..", 400),
            ("/templates/view?path=&path=page", 200),
            ("/templates/tree?path=page&path=page", 400),
            ("/templates/view?path=&path=", 400),
            ("/source?path=mvc%2Fviews%2Fpage", 200),
        ):
            status, _, headers = call(app, url)
            assert status == code and headers["Cache-Control"] == "no-store"
        for url in ("/templates", "/templates/view", "/templates/tree"):
            assert call(app, url, method="POST")[0] == 405
