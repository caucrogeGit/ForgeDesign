"""Projection et aplatissement itératifs, indépendants de toute analyse."""

import builtins
import os
from dataclasses import FrozenInstanceError
from html.parser import HTMLParser
from pathlib import Path

import pytest
from jinja2 import Environment

from forge_design.forge import template_structure, templates
from forge_design.forge.template_structure import (
    HtmlElement,
    TemplateBlock,
    TemplateReference,
    TemplateStructure,
    TemplateSyntaxInfo,
)
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.template_tree import build_template_tree, flatten_template_tree


def structure(depths: tuple[int, ...] = ()) -> TemplateStructure:
    return TemplateStructure(
        TemplateSyntaxInfo("valid"),
        html_elements=tuple(
            HtmlElement(f"tag{i}", i + 1, d) for i, d in enumerate(depths)
        ),
    )


def test_empty() -> None:
    tree = build_template_tree(structure())
    assert tree.html == tree.blocks == tree.dependencies == ()
    assert not tree.partial and not tree.truncated
    assert flatten_template_tree(tree) == ()


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("truncated", [False, True])
def test_declarations_flags_immutable(partial: bool, truncated: bool) -> None:
    source = TemplateStructure(
        TemplateSyntaxInfo("valid"),
        dependencies=(
            TemplateReference("extends", "base", False, 1),
            TemplateReference("include", None, True, 2),
            TemplateReference("include", "same", False, 3),
            TemplateReference("include", "same", False, 3),
            TemplateReference("import", "forms", False, 4),
            TemplateReference("from-import", "ui", False, 4),
        ),
        blocks=(TemplateBlock("a", 5), TemplateBlock("b", 6), TemplateBlock("a", 7)),
        html_elements=(HtmlElement("section", 8, 0),),
        partial=partial,
        truncated=truncated,
    )
    tree = build_template_tree(source)
    assert tree.dependencies is source.dependencies and tree.blocks is source.blocks
    assert tree.partial is partial and tree.truncated is truncated
    assert tree == build_template_tree(source)
    assert source.html_elements == (HtmlElement("section", 8, 0),)
    for model in (tree, tree.html[0], flatten_template_tree(tree)[0]):
        with pytest.raises(FrozenInstanceError):
            setattr(model, "line", 0)


def test_hierarchy_roots_and_order() -> None:
    tree = build_template_tree(structure((0, 1, 2, 1, 0)))
    assert [n.tag for n in tree.html] == ["tag0", "tag4"]
    assert [n.tag for n in tree.html[0].children] == ["tag1", "tag3"]
    assert tree.html[0].children[0].children[0].tag == "tag2"
    rows = flatten_template_tree(tree)
    assert [(r.tag, r.line, r.depth) for r in rows] == [
        ("tag0", 1, 0),
        ("tag1", 2, 1),
        ("tag2", 3, 2),
        ("tag3", 4, 1),
        ("tag4", 5, 0),
    ]
    assert [r.close_levels for r in rows] == [0, 0, 1, 1, 0]


@pytest.mark.parametrize(
    "depths,expected",
    [
        ((0, 3, 3, 5, 1, 0), (0, 1, 1, 2, 1, 0)),
        ((5, 6, 2, 3), (0, 1, 0, 1)),
        ((0, 1, 1), (0, 1, 1)),
    ],
)
def test_depth_jumps(depths: tuple[int, ...], expected: tuple[int, ...]) -> None:
    rows = flatten_template_tree(build_template_tree(structure(depths)))
    assert tuple(r.depth for r in rows) == expected
    assert tuple(r.tag for r in rows) == tuple(f"tag{i}" for i in range(len(depths)))


def test_negative_depth() -> None:
    with pytest.raises(ValueError, match="négative"):
        build_template_tree(structure((0, -1)))


@pytest.mark.parametrize("count", [4096, 10000])
def test_deep_iterative(count: int) -> None:
    tree = build_template_tree(structure(tuple(range(count))))
    rows = flatten_template_tree(tree)
    assert len(rows) == count and rows[-1].depth == count - 1
    assert rows[-1].close_levels == count - 1
    assert len(tree.html) == 1
    node = tree.html[0]
    for index in range(count):
        assert node.tag == f"tag{index}"
        if node.children:
            node = node.children[0]


def test_purity(monkeypatch: pytest.MonkeyPatch) -> None:
    source = structure((0, 1, 0))
    expected = build_template_tree(source)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Projection only")

    with monkeypatch.context() as guard:
        for owner, names in (
            (builtins, ("open",)),
            (os, ("open", "stat", "scandir", "listdir")),
            (Path, ("open", "read_text", "read_bytes", "stat", "iterdir")),
            (ToolRegistry, ("get",)),
            (templates, ("read_template_source",)),
            (template_structure, ("analyze_template_structure", "mask_jinja")),
            (Environment, ("__init__",)),
            (HTMLParser, ("__init__",)),
        ):
            for name in names:
                guard.setattr(owner, name, forbidden)
        assert build_template_tree(source) == expected
        assert len(flatten_template_tree(expected)) == 3
