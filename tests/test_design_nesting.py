"""Contrat d'imbrication v0.1, parcours et budgets indépendants de Pydantic."""

import builtins
import os
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any, get_args

import pytest

from forge_design.design import (
    ALLOWED_CHILDREN,
    DesignFile,
    DesignNestingIssue,
    DesignNestingResult,
    DesignNode,
    DesignNodeType,
    can_contain,
    validate_design_nesting,
)
from forge_design.limits import MAX_DESIGN_DEPTH, MAX_DESIGN_ISSUES, MAX_DESIGN_NODES

EXPECTED: dict[DesignNodeType, set[DesignNodeType]] = {
    "page": {"section", "table"},
    "section": {"container", "grid", "card", "form", "table", "alert", "text"},
    "container": {"grid", "card", "form", "table", "text", "button"},
    "card": {"title", "text", "form", "button", "grid"},
    "form": {"field", "button", "alert"},
    "table": {"empty_state"},
    "grid": set(),
    "title": set(),
    "text": set(),
    "button": set(),
    "field": set(),
    "alert": set(),
    "empty_state": set(),
}
INVALID = "design.nesting.child_not_allowed"
TRUNCATED = "design.nesting.analysis_truncated"


def design(children: list[Any]) -> DesignFile:
    return DesignFile.model_validate(
        {
            "version": "0.1",
            "view": "home",
            "source_contract": "home.view.json",
            "root": {"type": "page", "children": children},
        }
    )


@pytest.mark.parametrize("parent", get_args(DesignNodeType))
@pytest.mark.parametrize("child", get_args(DesignNodeType))
def test_matrix(parent: DesignNodeType, child: DesignNodeType) -> None:
    assert can_contain(parent, child) is (child in EXPECTED[parent])


def test_matrix_and_results_immutable() -> None:
    assert set(ALLOWED_CHILDREN) == set(get_args(DesignNodeType)) == set(EXPECTED)
    assert dict(ALLOWED_CHILDREN) == EXPECTED
    assert all(isinstance(values, frozenset) for values in ALLOWED_CHILDREN.values())
    with pytest.raises(TypeError):
        ALLOWED_CHILDREN["page"] = frozenset()  # type: ignore[index]
    issue = DesignNestingIssue(
        INVALID, "message", ("root", "children", 0), "page", "button"
    )
    with pytest.raises(FrozenInstanceError):
        issue.code = "changed"  # type: ignore[misc]
    result = DesignNestingResult(False, (issue,))
    with pytest.raises(FrozenInstanceError):
        result.valid = True  # type: ignore[misc]
    assert isinstance(result.issues, tuple)


@pytest.mark.parametrize("name", ["minimal", "contacts-list"])
def test_official_fixtures(name: str) -> None:
    model = DesignFile.model_validate_json(
        (
            Path(__file__).parent / "fixtures/design" / (name + ".design.json")
        ).read_text()
    )
    assert validate_design_nesting(model) == DesignNestingResult(True, ())


def test_complex_valid_and_ignored_metadata() -> None:
    model = design(
        [
            {
                "type": "section",
                "children": [
                    {
                        "type": "container",
                        "children": [
                            {
                                "type": "card",
                                "children": [
                                    {"type": "title"},
                                    {
                                        "type": "form",
                                        "children": [
                                            {"type": "field"},
                                            {"type": "button"},
                                        ],
                                    },
                                ],
                            },
                            {"type": "table", "children": [{"type": "empty_state"}]},
                        ],
                    }
                ],
            }
        ]
    )
    before = model.model_dump(exclude_unset=True)
    child = model.root.children[0]
    children = model.root.children
    assert validate_design_nesting(model) == DesignNestingResult(True, ())
    assert model.root.children is children and model.root.children[0] is child
    assert model.model_dump(exclude_unset=True) == before
    rich = design(
        [
            {
                "type": "section",
                "binding": "unresolved",
                "props": {"tag": "button"},
                "columns": [{"label": "L", "binding": "x"}],
                "children": [{"type": "text", "props": {"tag": "h1"}}],
            }
        ]
    )
    props, columns = rich.root.children[0].props, rich.root.children[0].columns
    assert validate_design_nesting(rich).valid
    assert rich.root.children[0].props is props
    assert rich.root.children[0].columns is columns


def test_errors_preorder_paths_and_determinism() -> None:
    model = design(
        [
            {
                "type": "button",
                "children": [{"type": "section", "children": [{"type": "page"}]}],
            },
            {"type": "section", "children": [{"type": "field"}]},
        ]
    )
    result = validate_design_nesting(model)
    assert not result.valid and not result.truncated
    assert [(i.path, i.parent_type, i.child_type) for i in result.issues] == [
        (("root", "children", 0), "page", "button"),
        (("root", "children", 0, "children", 0), "button", "section"),
        (("root", "children", 0, "children", 0, "children", 0), "section", "page"),
        (("root", "children", 1, "children", 0), "section", "field"),
    ]
    assert all(i.code == INVALID and i.message for i in result.issues)
    assert validate_design_nesting(model) == result


@pytest.mark.parametrize("surplus", [0, 1])
def test_nodes_budget(surplus: int) -> None:
    model = design([{"type": "section"} for _ in range(MAX_DESIGN_NODES - 1 + surplus)])
    result = validate_design_nesting(model)
    assert result.valid is (not surplus)
    assert result.truncated is bool(surplus)
    if surplus:
        assert len(result.issues) == 1
        assert result.issues[0].code == TRUNCATED
        assert result.issues[0].path == ("root", "children", MAX_DESIGN_NODES - 1)


@pytest.mark.parametrize("surplus", [0, 1])
def test_depth_budget(surplus: int) -> None:
    # Assemblage itératif via listes mutables pour isoler la borne de cette analyse
    # de la limite récursive du validateur Pydantic. Aucun model_construct produit.
    model = design([])
    children = model.root.children
    for _ in range(MAX_DESIGN_DEPTH + surplus):
        node = DesignNode(type="section", children=[])
        children.append(node)
        assert node.children is not None
        children = node.children
    result = validate_design_nesting(model)
    assert result.truncated is bool(surplus)
    assert not result.valid  # section → section est volontairement invalide.
    assert sum(i.code == TRUNCATED for i in result.issues) == surplus
    assert len(result.issues[-1].path) == 1 + 2 * (MAX_DESIGN_DEPTH + surplus)


@pytest.mark.parametrize("surplus", [0, 1])
def test_issue_budget(surplus: int) -> None:
    model = design([{"type": "button"} for _ in range(MAX_DESIGN_ISSUES + surplus)])
    result = validate_design_nesting(model)
    assert not result.valid and result.truncated is bool(surplus)
    assert len(result.issues) == MAX_DESIGN_ISSUES
    assert [i.code for i in result.issues] == (
        [INVALID] * (MAX_DESIGN_ISSUES - 1) + [TRUNCATED if surplus else INVALID]
    )
    assert result.issues[-1].path == (
        "root",
        "children",
        MAX_DESIGN_ISSUES - 1 + surplus,
    )


def test_full_issue_budget_then_node_truncation() -> None:
    model = design(
        [{"type": "button"} for _ in range(MAX_DESIGN_ISSUES)]
        + [{"type": "section"} for _ in range(MAX_DESIGN_NODES - MAX_DESIGN_ISSUES)]
    )
    result = validate_design_nesting(model)
    assert result.truncated and len(result.issues) == MAX_DESIGN_ISSUES
    assert result.issues[-1].code == TRUNCATED
    assert result.issues[-1].path == ("root", "children", MAX_DESIGN_NODES - 1)


def test_cycle_after_mutation_is_bounded() -> None:
    model = design([{"type": "section", "children": []}])
    node = model.root.children[0]
    assert node.children is not None
    node.children.append(node)
    result = validate_design_nesting(model)
    assert result.truncated and not result.valid
    assert result.issues[-1].code == TRUNCATED


def test_purity_and_no_dump(monkeypatch: pytest.MonkeyPatch) -> None:
    model = design([{"type": "section"}])

    def forbidden(*args: object, **kwargs: object) -> Any:
        raise AssertionError("unexpected side effect or full copy")

    monkeypatch.setattr(builtins, "open", forbidden)
    for name in ("open", "stat", "listdir", "scandir"):
        monkeypatch.setattr(os, name, forbidden)
    for name in ("open", "read_text", "read_bytes", "stat"):
        monkeypatch.setattr(Path, name, forbidden)
    monkeypatch.setattr(DesignFile, "model_dump", forbidden)
    monkeypatch.setattr(DesignNode, "model_dump", forbidden)
    assert validate_design_nesting(model).valid


def test_broad_children_are_consumed_lazily() -> None:
    class CountedChildren(list[DesignNode]):
        consumed = 0

        def __iter__(self):
            for node in super().__iter__():
                self.consumed += 1
                if self.consumed > MAX_DESIGN_NODES:
                    raise AssertionError("entire breadth consumed")
                yield node

    model = design([{"type": "section", "children": []}])
    section = model.root.children[0]
    children = CountedChildren([DesignNode(type="text")] * (MAX_DESIGN_NODES * 2))
    # Conteneur instrumenté : seul ce test contourne le gel pour observer le parcours.
    object.__setattr__(section, "children", children)
    result = validate_design_nesting(model)
    assert result.truncated and not result.valid
    assert children.consumed == MAX_DESIGN_NODES - 1
    assert result.issues[-1].path == (
        "root",
        "children",
        0,
        "children",
        MAX_DESIGN_NODES - 2,
    )


def test_shared_node_is_checked_at_each_path() -> None:
    model = design([])
    button = DesignNode(type="button")
    model.root.children.extend([button, button])
    result = validate_design_nesting(model)
    assert [issue.path for issue in result.issues] == [
        ("root", "children", 0),
        ("root", "children", 1),
    ]
    assert not result.truncated


def test_exact_issue_budget_with_valid_remainder() -> None:
    model = design(
        [{"type": "button"} for _ in range(MAX_DESIGN_ISSUES)] + [{"type": "section"}]
    )
    result = validate_design_nesting(model)
    assert len(result.issues) == MAX_DESIGN_ISSUES and not result.truncated
    assert all(issue.code == INVALID for issue in result.issues)
