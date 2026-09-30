"""Références conditionnelles exactes, indépendantes et bornées."""

import builtins
import os
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any, get_args

import pytest
from test_design_bindings import contract, design

from forge_design.contracts import ViewContract, reader
from forge_design.contracts.models import ViewValueType
from forge_design.design import (
    DesignFile,
    DesignNode,
    DesignNodeType,
    bindings,
    io,
    nesting,
    table_bindings,
    validate_conditional_bindings,
    validate_design_bindings,
    validate_design_nesting,
)
from forge_design.limits import MAX_DESIGN_DEPTH, MAX_DESIGN_ISSUES, MAX_DESIGN_NODES


def codes(result: Any) -> list[str]:
    return [issue.code.removeprefix("design.condition.") for issue in result.issues]


@pytest.mark.parametrize("kind", get_args(DesignNodeType))
def test_every_node_type(kind: str) -> None:
    c = contract({"can_create": {"type": "boolean"}})
    assert validate_conditional_bindings(
        design([{"type": kind, "visible_if": "can_create"}]), c
    ).valid
    assert validate_conditional_bindings(design([{"type": kind}]), contract()).valid


@pytest.mark.parametrize("kind", get_args(ViewValueType))
def test_context_types(kind: str) -> None:
    result = validate_conditional_bindings(
        design([], visible_if="x"), contract({"x": {"type": kind}})
    )
    assert result.valid is (kind == "boolean")
    assert codes(result) == ([] if kind == "boolean" else ["type_mismatch"])
    if not result.valid:
        assert result.issues[0].location == ("root", "visible_if")


@pytest.mark.parametrize(
    "key",
    [
        "true",
        "peut_créer",
        "permission.create",
        "user.can_create",
        "!can_create",
        "not can_create",
        "can_create == true",
        "can_create && is_admin",
        " x ",
        "e\u0301",
    ],
)
def test_literal_names_not_expressions(key: str) -> None:
    model = design([{"type": "text", "visible_if": key}])
    assert validate_conditional_bindings(
        model, contract({key: {"type": "boolean"}})
    ).valid
    c = contract(
        {
            "can_create": {"type": "boolean"},
            "user": {"type": "object", "fields": {"can_create": "boolean"}},
            "X": {"type": "boolean"},
            "é": {"type": "boolean"},
        }
    )
    assert codes(validate_conditional_bindings(model, c)) == ["unknown_variable"]


def test_context_namespace_and_independent_bindings() -> None:
    model = design([{"type": "button", "binding": "create", "visible_if": "create"}])
    action = {"create": {"method": "GET", "path": "/"}}
    assert validate_design_bindings(model, contract(actions=action)).valid
    assert codes(validate_conditional_bindings(model, contract(actions=action))) == [
        "unknown_variable"
    ]
    assert validate_conditional_bindings(
        model, contract({"create": {"type": "boolean"}}, actions=action)
    ).valid
    assert codes(
        validate_conditional_bindings(
            model, contract({"create": {"type": "string"}}, actions=action)
        )
    ) == ["type_mismatch"]


def test_fixture_nominal_all_validators() -> None:
    model = DesignFile.model_validate_json(
        (Path(__file__).parent / "fixtures/design/conditional.design.json").read_text()
    )
    c = contract(
        {"can_create": {"type": "boolean"}},
        actions={"create": {"method": "GET", "path": "/contacts/create"}},
    )
    assert validate_design_nesting(model).valid
    assert validate_design_bindings(model, c).valid
    assert validate_conditional_bindings(model, c).valid


def test_errors_preorder_locations_and_frozen() -> None:
    model = design(
        [
            {
                "type": "text",
                "visible_if": "title",
                "children": [
                    {"type": "button", "visible_if": "missing"},
                ],
            },
            {"type": "table", "visible_if": "title"},
        ],
        visible_if="root",
    )
    c = contract({"title": {"type": "string"}})
    result = validate_conditional_bindings(model, c)
    assert codes(result) == [
        "unknown_variable",
        "type_mismatch",
        "unknown_variable",
        "type_mismatch",
    ]
    assert [i.location for i in result.issues] == [
        ("root", "visible_if"),
        ("root", "children", 0, "visible_if"),
        ("root", "children", 0, "children", 0, "visible_if"),
        ("root", "children", 1, "visible_if"),
    ]
    assert result == validate_conditional_bindings(model, c)
    assert result.issues[0].binding == "root" and result.issues[0].node_type == "page"
    with pytest.raises(FrozenInstanceError):
        result.valid = True  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.issues[0].binding = "changed"  # type: ignore[misc]
    assert isinstance(result.issues, tuple)


@pytest.mark.parametrize("surplus", [0, 1])
def test_nodes_limit(surplus: int) -> None:
    result = validate_conditional_bindings(
        design([{"type": "text"}] * (MAX_DESIGN_NODES - 1 + surplus)), contract()
    )
    assert result.valid is (not surplus) and result.truncated is bool(surplus)
    if surplus:
        assert codes(result) == ["analysis_truncated"]
        assert result.issues[0].binding is None
        assert result.issues[0].location == ("root", "children", MAX_DESIGN_NODES - 1)


@pytest.mark.parametrize("surplus", [0, 1])
def test_depth_limit(surplus: int) -> None:
    model = design([])
    children = model.root.children
    for _ in range(MAX_DESIGN_DEPTH + surplus):
        node = DesignNode(type="text", children=[])
        children.append(node)
        assert node.children is not None
        children = node.children
    result = validate_conditional_bindings(model, contract())
    assert result.valid is (not surplus) and result.truncated is bool(surplus)


@pytest.mark.parametrize("surplus", [0, 1])
def test_issue_limit(surplus: int) -> None:
    result = validate_conditional_bindings(
        design(
            [{"type": "text", "visible_if": "missing"}] * (MAX_DESIGN_ISSUES + surplus)
            + [{"type": "text"}]
        ),
        contract(),
    )
    assert not result.valid and result.truncated is bool(surplus)
    assert len(result.issues) == MAX_DESIGN_ISSUES
    assert codes(result) == ["unknown_variable"] * (MAX_DESIGN_ISSUES - 1) + [
        "analysis_truncated" if surplus else "unknown_variable"
    ]


def test_shared_cycle_and_combined_limits() -> None:
    model = design([])
    node = DesignNode(type="text", visible_if="missing", children=[])
    model.root.children.extend([node, node])
    result = validate_conditional_bindings(model, contract())
    assert [i.location for i in result.issues] == [
        ("root", "children", i, "visible_if") for i in range(2)
    ]
    assert node.children is not None
    node.children.append(node)
    assert validate_conditional_bindings(model, contract()).truncated
    model = design(
        [{"type": "text", "visible_if": "x"}] * MAX_DESIGN_ISSUES
        + [{"type": "text"}] * (MAX_DESIGN_NODES - MAX_DESIGN_ISSUES)
    )
    result = validate_conditional_bindings(model, contract())
    assert (
        result.truncated
        and len(result.issues) == MAX_DESIGN_ISSUES
        and codes(result)[-1] == "analysis_truncated"
    )


def test_purity_ignored_metadata_nonmutation(monkeypatch: pytest.MonkeyPatch) -> None:
    model = design(
        [
            {
                "type": "table",
                "binding": "missing",
                "visible_if": "ok",
                "props": {"visible_if": "unknown"},
                "columns": [{"label": "L", "binding": "missing"}],
            }
        ]
    )
    c = contract({"ok": {"type": "boolean"}})
    before = model.model_dump(exclude_unset=True), c.model_dump(exclude_unset=True)
    refs = (
        model.root.children,
        model.root.children[0],
        model.root.children[0].props,
        model.root.children[0].columns,
        c.context,
        c.actions,
    )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("unexpected dependency")

    with monkeypatch.context() as p:
        p.setattr(builtins, "open", forbidden)
        for name in ("open", "stat", "listdir", "scandir"):
            p.setattr(os, name, forbidden)
        for name in ("open", "read_text", "read_bytes"):
            p.setattr(Path, name, forbidden)
        p.setattr(io, "read_design", forbidden)
        p.setattr(reader, "read_view_contract", forbidden)
        p.setattr(nesting, "validate_design_nesting", forbidden)
        p.setattr(bindings, "validate_design_bindings", forbidden)
        p.setattr(table_bindings, "validate_table_bindings", forbidden)
        p.setattr(DesignFile, "model_dump", forbidden)
        p.setattr(ViewContract, "model_dump", forbidden)
        assert validate_conditional_bindings(model, c).valid
    assert before == (
        model.model_dump(exclude_unset=True),
        c.model_dump(exclude_unset=True),
    )
    after = (
        model.root.children,
        model.root.children[0],
        model.root.children[0].props,
        model.root.children[0].columns,
        c.context,
        c.actions,
    )
    assert all(a is b for a, b in zip(refs, after, strict=True))
    assert validate_conditional_bindings(
        design([{"type": "text", "props": {"visible_if": "unknown"}}]), contract()
    ).valid


def test_lazy_breadth() -> None:
    class Children(list[DesignNode]):
        consumed = 0

        def __iter__(self):
            for node in super().__iter__():
                self.consumed += 1
                if self.consumed > MAX_DESIGN_NODES:
                    raise AssertionError("unbounded breadth")
                yield node

    model = design([])
    children = Children([DesignNode(type="text")] * (MAX_DESIGN_NODES * 2))
    object.__setattr__(model.root, "children", children)
    assert validate_conditional_bindings(model, contract()).truncated
    assert children.consumed == MAX_DESIGN_NODES
