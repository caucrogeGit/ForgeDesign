"""Mutations structurelles en mémoire : chemins, règles, bornes, immutabilité."""

import builtins
import os
import socket
import subprocess
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

import forge_design.editor as editor
from forge_design.app import create_tool_registry
from forge_design.design import (
    DesignFile,
    DesignNode,
    PageRoot,
    nesting,
    validate_design_nesting,
)
from forge_design.editor import (
    DesignEditIssue,
    DesignEditResult,
    append_design_block,
    remove_design_block,
    structure,
)
from forge_design.limits import MAX_DESIGN_DEPTH, MAX_DESIGN_NODES


def design(children: list[dict[str, Any]] | None = None) -> DesignFile:
    return DesignFile.model_validate(
        {
            "version": "0.1",
            "view": "contacts/list",
            "source_contract": "contacts/list.view.json",
            "root": {"type": "page", "children": children or []},
        }
    )


def sample() -> DesignFile:
    """page / section[text, card[title, text], table[empty_state]] / table."""
    return design(
        [
            {
                "type": "section",
                "props": {"class": "p-4"},
                "children": [
                    {"type": "text", "binding": "intro"},
                    {
                        "type": "card",
                        "visible_if": "has_card",
                        "children": [
                            {"type": "title", "binding": "title"},
                            {"type": "text", "binding": "body"},
                        ],
                    },
                    {
                        "type": "table",
                        "binding": "contacts",
                        "columns": [{"label": "Nom", "binding": "name"}],
                        "children": [{"type": "empty_state"}],
                    },
                ],
            },
            {"type": "table", "binding": "rows"},
        ]
    )


def dump(model: DesignFile) -> dict[str, Any]:
    return model.model_dump(exclude_unset=True)


def types(model: DesignFile, path: tuple[int, ...] = ()) -> list[str]:
    node: DesignNode | PageRoot = model.root
    for index in path:
        node = (node.children or [])[index]
    return [child.type for child in node.children or []]


def allow_all(parent: str, child: str) -> bool:
    return True


def allow_all_but_page(parent: str, child: str) -> bool:
    return child != "page"


def assert_refused(result: DesignEditResult, original: DesignFile, code: str) -> None:
    assert not result.changed
    assert result.affected_path is None
    assert result.design is original
    assert [issue.code for issue in result.issues] == ["editor." + code]


# Résolution des chemins.


def test_root_path_resolves_page() -> None:
    result = append_design_block(design(), parent=(), block_type="section")
    assert result.changed and result.affected_path == (0,)
    assert result.design.root.type == "page"


@pytest.mark.parametrize(
    ("parent", "block_type", "expected"),
    [
        ((), "section", (2,)),
        ((0,), "alert", (0, 3)),
        ((0, 1), "button", (0, 1, 2)),
        ((0, 2), "empty_state", (0, 2, 1)),
    ],
)
def test_nested_paths(parent: Any, block_type: Any, expected: tuple[int, ...]) -> None:
    result = append_design_block(sample(), parent=parent, block_type=block_type)
    assert result.issues == ()
    assert result.affected_path == expected
    assert types(result.design, expected[:-1])[-1] == block_type


@pytest.mark.parametrize(
    "path", [(-1,), (999,), (0, 50), (0, 1, 0, 0), (1, 0), (0, -1)]
)
def test_path_not_found(path: tuple[int, ...]) -> None:
    original = sample()
    assert_refused(
        append_design_block(original, parent=path, block_type="text"),
        original,
        "path_not_found",
    )
    assert_refused(remove_design_block(original, path=path), original, "path_not_found")


@pytest.mark.parametrize(
    "path", [(True,), (0, False), "0", [0], (0.0,), ("0",), None, 0]
)
def test_invalid_path_types(path: Any) -> None:
    original = sample()
    assert_refused(
        append_design_block(original, parent=path, block_type="text"),
        original,
        "invalid_path",
    )
    assert_refused(remove_design_block(original, path=path), original, "invalid_path")


# Ajout.


@pytest.mark.parametrize(
    ("children", "parent", "block_type"),
    [
        ([], (), "section"),
        ([{"type": "section"}], (0,), "card"),
        ([{"type": "section", "children": [{"type": "card"}]}], (0, 0), "title"),
        ([{"type": "section", "children": [{"type": "form"}]}], (0, 0), "field"),
        ([{"type": "table"}], (0,), "empty_state"),
    ],
)
def test_append_nominal(children: Any, parent: Any, block_type: Any) -> None:
    original = design(children)
    result = append_design_block(original, parent=parent, block_type=block_type)
    assert result.changed and result.issues == ()
    assert types(result.design, parent)[-1] == block_type
    node: Any = result.design.root
    for index in result.affected_path or ():
        node = node.children[index]
    assert dump(DesignFile.model_validate(dump(result.design)))  # sérialisable
    assert node.model_dump(exclude_unset=True) == {"type": block_type}


def test_append_keeps_order() -> None:
    result = append_design_block(sample(), parent=(0,), block_type="text")
    assert types(result.design, (0,)) == ["text", "card", "table", "text"]
    assert result.affected_path == (0, 3)


@pytest.mark.parametrize(
    ("children", "parent", "block_type"),
    [
        ([], (), "card"),
        ([{"type": "section", "children": [{"type": "card"}]}], (0, 0, 0), "text"),
        ([{"type": "table"}], (0,), "text"),
        ([{"type": "section", "children": [{"type": "grid"}]}], (0, 0), "card"),
    ],
)
def test_append_forbidden(children: Any, parent: Any, block_type: Any) -> None:
    original = design(children)
    if parent == (0, 0, 0):
        original = append_design_block(
            original, parent=(0, 0), block_type="title"
        ).design
    result = append_design_block(original, parent=parent, block_type=block_type)
    assert_refused(result, original, "child_not_allowed")


@pytest.mark.parametrize(
    "leaf", ["title", "text", "button", "field", "alert", "empty_state", "grid"]
)
def test_valid_leaves_refuse_children(leaf: str) -> None:
    holders = {
        "title": ([{"type": "section", "children": [{"type": "card"}]}], (0, 0)),
        "text": ([{"type": "section"}], (0,)),
        "button": ([{"type": "section", "children": [{"type": "card"}]}], (0, 0)),
        "field": ([{"type": "section", "children": [{"type": "form"}]}], (0, 0)),
        "alert": ([{"type": "section"}], (0,)),
        "empty_state": ([{"type": "table"}], (0,)),
        "grid": ([{"type": "section"}], (0,)),
    }
    children, parent = holders[leaf]
    holder = append_design_block(design(children), parent=parent, block_type=leaf)  # type: ignore[arg-type]
    assert holder.changed
    leaf_path = holder.affected_path or ()
    for child in ("text", "title", "button", "field", "card", "empty_state"):
        result = append_design_block(holder.design, parent=leaf_path, block_type=child)  # type: ignore[arg-type]
        assert_refused(result, holder.design, "child_not_allowed")


def test_page_never_insertable() -> None:
    original = design([{"type": "section"}])
    for parent in ((), (0,)):
        assert_refused(
            append_design_block(original, parent=parent, block_type="page"),
            original,
            "root_type_not_insertable",
        )


@pytest.mark.parametrize("block_type", ["unknown", "", None, 1, "Section"])
def test_unknown_block_type(block_type: Any) -> None:
    original = design()
    assert_refused(
        append_design_block(original, parent=(), block_type=block_type),
        original,
        "unknown_block_type",
    )


def test_new_block_has_no_invented_fields() -> None:
    result = append_design_block(design(), parent=(), block_type="table")
    assert dump(result.design)["root"]["children"] == [{"type": "table"}]


def test_append_to_leaf_without_children_key() -> None:
    original = design([{"type": "table"}])
    assert "children" not in dump(original)["root"]["children"][0]
    result = append_design_block(original, parent=(0,), block_type="empty_state")
    assert dump(result.design)["root"]["children"][0] == {
        "type": "table",
        "children": [{"type": "empty_state"}],
    }


# Suppression.


def test_remove_leaf() -> None:
    result = remove_design_block(sample(), path=(0, 0))
    assert result.changed and result.issues == ()
    assert types(result.design, (0,)) == ["card", "table"]
    assert result.affected_path == (0,)


def test_remove_container_with_descendants() -> None:
    result = remove_design_block(sample(), path=(0, 1))
    assert types(result.design, (0,)) == ["text", "table"]
    flat = str(dump(result.design))
    assert "has_card" not in flat and "'title'" not in flat and "body" not in flat
    assert result.affected_path == (0,)


def test_remove_first_shifts_siblings() -> None:
    original = sample()
    result = remove_design_block(original, path=(0,))
    assert types(result.design) == ["table"]
    assert result.affected_path == ()
    assert dump(result.design)["root"]["children"][0] == {
        "type": "table",
        "binding": "rows",
    }


def test_remove_last() -> None:
    result = remove_design_block(sample(), path=(0, 2))
    assert types(result.design, (0,)) == ["text", "card"]


def test_remove_only_child_omits_children_key() -> None:
    original = design([{"type": "table"}])
    added = append_design_block(original, parent=(0,), block_type="empty_state")
    removed = remove_design_block(added.design, path=(0, 0))
    assert dump(removed.design) == dump(original)
    emptied = remove_design_block(design([{"type": "section"}]), path=(0,))
    assert dump(emptied.design)["root"]["children"] == []


def test_remove_root_refused() -> None:
    original = sample()
    assert_refused(
        remove_design_block(original, path=()), original, "root_not_removable"
    )


def test_other_nodes_untouched() -> None:
    before = dump(sample())
    after = dump(remove_design_block(sample(), path=(0, 0)).design)
    section_before = before["root"]["children"][0]
    section_after = after["root"]["children"][0]
    assert section_after["props"] == section_before["props"]
    assert section_after["children"] == section_before["children"][1:]
    assert after["root"]["children"][1] == before["root"]["children"][1]
    for key in ("version", "view", "source_contract"):
        assert after[key] == before[key]


# Validité, règles, bornes.


def test_results_are_valid_and_nested() -> None:
    model = design()
    for parent, block_type in [
        ((), "section"),
        ((0,), "card"),
        ((0, 0), "form"),
        ((0, 0, 0), "field"),
        ((), "table"),
        ((1,), "empty_state"),
    ]:
        result = append_design_block(model, parent=parent, block_type=block_type)  # type: ignore[arg-type]
        assert result.changed
        model = result.design
        assert DesignFile.model_validate(dump(model)) == model
        assert validate_design_nesting(model).valid


def test_uses_existing_can_contain(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []
    original = nesting.can_contain

    def spy(parent: Any, child: Any) -> bool:
        calls.append((parent, child))
        return original(parent, child)

    monkeypatch.setattr(nesting, "can_contain", spy)
    append_design_block(design(), parent=(), block_type="section")
    assert ("page", "section") in calls
    assert "ALLOWED_CHILDREN" not in vars(structure)


def test_invalid_initial_design(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nesting, "can_contain", allow_all)
    bad = append_design_block(design(), parent=(), block_type="card").design
    monkeypatch.undo()
    assert not validate_design_nesting(bad).valid
    assert_refused(
        append_design_block(bad, parent=(), block_type="section"),
        bad,
        "invalid_design",
    )
    assert_refused(remove_design_block(bad, path=(0,)), bad, "invalid_design")


def test_mutated_input_is_revalidated() -> None:
    original = design([{"type": "section"}])
    original.root.children.append("not a node")  # type: ignore[arg-type]
    assert_refused(
        append_design_block(original, parent=(), block_type="section"),
        original,
        "invalid_design",
    )


def test_cyclic_input_refused() -> None:
    original = design([{"type": "section", "children": []}])
    section = original.root.children[0]
    assert section.children is not None
    section.children.append(section)  # cycle par mutation de liste interne
    result = remove_design_block(original, path=(0,))
    assert_refused(result, original, "invalid_design")


def test_not_a_design() -> None:
    values: tuple[object, ...] = (None, {"root": {}}, "design")
    for value in values:
        result = append_design_block(value, parent=(), block_type="section")  # type: ignore[arg-type]
        assert not result.changed
        assert [i.code for i in result.issues] == ["editor.invalid_design"]


def test_node_limit() -> None:
    # Racine comprise : MAX_DESIGN_NODES nœuds au total sont valides.
    below = design([{"type": "section"} for _ in range(MAX_DESIGN_NODES - 2)])
    result = append_design_block(below, parent=(), block_type="section")
    assert result.changed
    at_limit = result.design
    assert_refused(
        append_design_block(at_limit, parent=(), block_type="section"),
        at_limit,
        "node_limit",
    )
    removed = remove_design_block(at_limit, path=(0,))
    assert removed.changed


def chain(depth: int) -> dict[str, Any]:
    node: dict[str, Any] = {"type": "section"}
    for _ in range(depth - 1):
        node = {"type": "section", "children": [node]}
    return node


def test_depth_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    # Les règles réelles n'ont aucun cycle : élargir can_contain pour atteindre 128.
    monkeypatch.setattr(
        nesting,
        "can_contain",
        allow_all_but_page,
    )
    deep = design([chain(MAX_DESIGN_DEPTH - 1)])
    parent = (0,) * (MAX_DESIGN_DEPTH - 1)
    result = append_design_block(deep, parent=parent, block_type="section")
    assert result.changed and result.affected_path == (0,) * MAX_DESIGN_DEPTH
    deepest = result.design
    assert_refused(
        append_design_block(
            deepest, parent=(0,) * MAX_DESIGN_DEPTH, block_type="section"
        ),
        deepest,
        "depth_limit",
    )
    assert remove_design_block(deepest, path=(0,) * MAX_DESIGN_DEPTH).changed


# Immutabilité.


def test_input_never_mutated() -> None:
    original = sample()
    before = dump(original)
    root_children = original.root.children
    section_children = original.root.children[0].children
    snapshot_lists = (list(root_children), list(section_children or []))
    for operation in (
        lambda: append_design_block(original, parent=(0,), block_type="text"),
        lambda: append_design_block(original, parent=(), block_type="section"),
        lambda: remove_design_block(original, path=(0, 1)),
        lambda: remove_design_block(original, path=(0,)),
        lambda: append_design_block(original, parent=(), block_type="card"),
    ):
        operation()
        assert dump(original) == before
        assert original.root.children is root_children
        assert (list(root_children), list(section_children or [])) == snapshot_lists


def test_result_independent_from_input() -> None:
    original = sample()
    before = dump(original)
    result = append_design_block(original, parent=(0,), block_type="text").design
    result.root.children.append(DesignNode(type="section"))
    section = result.root.children[0]
    assert section.children is not None
    section.children.clear()
    assert dump(original) == before
    for new, old in zip(result.root.children, original.root.children, strict=False):
        assert new is not old
    assert result.root.children is not original.root.children


def test_frozen_results() -> None:
    result = append_design_block(design(), parent=(), block_type="section")
    with pytest.raises(FrozenInstanceError):
        result.changed = False  # type: ignore[misc]
    issue = DesignEditIssue("editor.x", "m", ())
    with pytest.raises(FrozenInstanceError):
        issue.code = "y"  # type: ignore[misc]


# Pureté, déterminisme, périmètre.


def test_pure(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("I/O interdite")

    for target, name in (
        (builtins, "open"),
        (os, "open"),
        (os, "stat"),
        (socket, "socket"),
        (subprocess, "Popen"),
    ):
        monkeypatch.setattr(target, name, forbidden)
    model = append_design_block(design(), parent=(), block_type="section").design
    model = append_design_block(model, parent=(0,), block_type="card").design
    assert remove_design_block(model, path=(0, 0)).changed
    append_design_block(model, parent=(), block_type="card")


def test_deterministic() -> None:
    for _ in range(2):
        first = append_design_block(sample(), parent=(0, 1), block_type="button")
        second = append_design_block(sample(), parent=(0, 1), block_type="button")
        assert first == second
        assert remove_design_block(sample(), path=(0, 1)) == remove_design_block(
            sample(), path=(0, 1)
        )
        assert (
            append_design_block(sample(), parent=(), block_type="card").issues
            == append_design_block(sample(), parent=(), block_type="card").issues
        )


def test_no_io_imports() -> None:
    names = set(vars(structure))
    assert not names & {
        "read_design",
        "write_design",
        "snapshot_template",
        "write_generated_template",
        "os",
        "Path",
        "open_directory",
        "generate_simple_template",
        "build_template_diff",
    }


def test_exports_and_registry() -> None:
    for name in (
        "NodePath",
        "DesignEditIssue",
        "DesignEditResult",
        "append_design_block",
        "remove_design_block",
    ):
        assert name in editor.__all__ and hasattr(editor, name)
    assert len(create_tool_registry().list()) == 5


def test_end_to_end_scenario() -> None:
    original = design()
    step1 = append_design_block(original, parent=(), block_type="section")
    step2 = append_design_block(step1.design, parent=(0,), block_type="card")
    step3 = remove_design_block(step2.design, path=(0, 0))
    assert step2.affected_path == (0, 0) and step3.affected_path == (0,)
    assert dump(step3.design)["root"]["children"] == [{"type": "section"}]
    assert dump(original)["root"]["children"] == []


def test_invalid_result_never_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    # Incohérence interne simulée : entrée valide, résultat refusé par le nesting.
    real = nesting.validate_design_nesting
    calls = 0

    def second_call_fails(model: DesignFile) -> Any:
        nonlocal calls
        calls += 1
        result = real(model)
        return result if calls == 1 else type(result)(False, ())

    monkeypatch.setattr(nesting, "validate_design_nesting", second_call_fails)
    original = sample()
    assert_refused(
        append_design_block(original, parent=(0,), block_type="text"),
        original,
        "invalid_result",
    )
    calls = 0
    assert_refused(remove_design_block(original, path=(0,)), original, "invalid_result")
