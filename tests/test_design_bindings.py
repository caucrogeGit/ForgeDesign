"""Bindings simples : namespaces exacts, séparation des validations et bornes."""

import builtins
import os
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any, get_args

import pytest

from forge_design.contracts import ViewContract, reader
from forge_design.contracts.models import ViewValueType
from forge_design.design import (
    DesignBindingResult,
    DesignFile,
    DesignNode,
    DesignNodeType,
    io,
    nesting,
    validate_design_bindings,
)
from forge_design.limits import MAX_DESIGN_DEPTH, MAX_DESIGN_ISSUES, MAX_DESIGN_NODES


def contract(context: dict[str, Any] | None = None, **extra: Any) -> ViewContract:
    return ViewContract.model_validate(
        {
            "name": "different",
            "template": "mvc/views/unrelated.html",
            "context": context or {},
            **extra,
        }
    )


def design(children: list[Any], **root_fields: Any) -> DesignFile:
    return DesignFile.model_validate(
        {
            "version": "0.1",
            "view": "home",
            "source_contract": "unresolved.view.json",
            "root": {"type": "page", "children": children, **root_fields},
        }
    )


def codes(result: DesignBindingResult) -> list[str]:
    return [issue.code.removeprefix("design.binding.") for issue in result.issues]


@pytest.mark.parametrize("node_type", ["title", "text", "table"])
@pytest.mark.parametrize("value_type", get_args(ViewValueType))
def test_context_type_matrix(node_type: str, value_type: str) -> None:
    expected = "list" if node_type == "table" else "string"
    result = validate_design_bindings(
        design([{"type": node_type, "binding": "x"}]),
        contract({"x": {"type": value_type}}),
    )
    assert result.valid is (value_type == expected)
    assert codes(result) == ([] if result.valid else ["type_mismatch"])


@pytest.mark.parametrize("node_type", get_args(DesignNodeType))
def test_absent_binding_for_all_types(node_type: str) -> None:
    assert validate_design_bindings(
        design([{"type": node_type}]), contract()
    ) == DesignBindingResult(True, ())


@pytest.mark.parametrize(
    "node_type",
    [
        "page",
        "section",
        "container",
        "grid",
        "card",
        # form référence une action depuis FD-INTERACT-002.
        "field",
        "alert",
        "empty_state",
    ],
)
def test_unsupported(node_type: str) -> None:
    result = validate_design_bindings(
        design([{"type": node_type, "binding": "x"}]),
        contract({"x": {"type": "string"}}),
    )
    assert not result.valid and codes(result) == ["unsupported"]
    assert result.issues[0].node_type == node_type and result.issues[0].binding == "x"


@pytest.mark.parametrize("actions", [None, {}])
def test_actions_missing_or_empty(actions: dict[str, Any] | None) -> None:
    c = contract(
        {"create": {"type": "string"}},
        **({} if actions is None else {"actions": actions}),
    )
    result = validate_design_bindings(
        design([{"type": "button", "binding": "create"}]), c
    )
    assert codes(result) == ["unknown_action"]


def test_namespaces_and_ignored_action_details() -> None:
    c = contract(
        {"create": {"type": "boolean"}},
        actions={"create": {"method": "ARBITRARY", "path": "no route", "csrf": False}},
    )
    result = validate_design_bindings(
        design(
            [
                {"type": "button", "binding": "create"},
                {"type": "text", "binding": "create"},
            ]
        ),
        c,
    )
    assert codes(result) == ["type_mismatch"]
    assert result.issues[0].location == ("root", "children", 1, "binding")
    c = contract(actions={"create": {"method": "GET", "path": "/"}})
    assert codes(
        validate_design_bindings(design([{"type": "text", "binding": "create"}]), c)
    ) == ["unknown_variable"]


@pytest.mark.parametrize(
    "key",
    [
        "contact.email",
        "a/b",
        "a:b",
        "a[0]",
        " spaced ",
        "É",
        "e\u0301",
        "actions.create",
        "@create",
        "action:create",
    ],
)
def test_literal_keys(key: str) -> None:
    model = design(
        [{"type": "text", "binding": key}, {"type": "button", "binding": key}]
    )
    c = contract(
        {key: {"type": "string"}}, actions={key: {"method": "GET", "path": "/"}}
    )
    assert validate_design_bindings(model, c).valid
    assert codes(validate_design_bindings(model, contract())) == [
        "unknown_variable",
        "unknown_action",
    ]


@pytest.mark.parametrize("binding", ["x", " X ", "é", "e\u0301", "contact.email"])
def test_no_normalization_or_field_navigation(binding: str) -> None:
    c = contract(
        {
            "X": {"type": "string"},
            "É": {"type": "string"},
            "contact": {"type": "object", "fields": {"email": "string"}},
        }
    )
    assert codes(
        validate_design_bindings(design([{"type": "text", "binding": binding}]), c)
    ) == ["unknown_variable"]


def test_fixtures_and_columns_ignored() -> None:
    c = contract(
        {
            "page_title": {"type": "string"},
            "contacts": {"type": "list", "entity": "Missing", "fields": {}},
        }
    )
    for name in ("minimal", "contacts-list"):
        model = DesignFile.model_validate_json(
            (
                Path(__file__).parent / "fixtures/design" / (name + ".design.json")
            ).read_text()
        )
        assert validate_design_bindings(model, c).valid
    assert validate_design_bindings(
        design(
            [
                {
                    "type": "table",
                    "binding": "contacts",
                    "props": {"tag": "button"},
                    "columns": [{"label": "L", "binding": "does_not_exist"}],
                }
            ]
        ),
        c,
    ).valid


def test_preorder_root_locations_and_multiple_errors() -> None:
    model = design(
        [
            {
                "type": "text",
                "binding": "missing",
                "children": [
                    {"type": "button", "binding": "delete"},
                    {"type": "table", "binding": "title"},
                ],
            },
            {"type": "form", "binding": "contact_form"},
        ],
        binding="root",
    )
    c = contract({"title": {"type": "string"}})
    result = validate_design_bindings(model, c)
    assert not result.valid and not result.truncated
    assert codes(result) == [
        "unsupported",
        "unknown_variable",
        "unknown_action",
        "type_mismatch",
        # form → action (FD-INTERACT-002) : aucune action dans ce contrat.
        "unknown_action",
    ]
    assert [i.location for i in result.issues] == [
        ("root", "binding"),
        ("root", "children", 0, "binding"),
        ("root", "children", 0, "children", 0, "binding"),
        ("root", "children", 0, "children", 1, "binding"),
        ("root", "children", 1, "binding"),
    ]
    assert validate_design_bindings(model, c) == result
    with pytest.raises(FrozenInstanceError):
        result.valid = True  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.issues[0].binding = "changed"  # type: ignore[misc]
    assert isinstance(result.issues, tuple)


@pytest.mark.parametrize("surplus", [0, 1])
def test_node_limit(surplus: int) -> None:
    model = design([{"type": "text"}] * (MAX_DESIGN_NODES - 1 + surplus))
    result = validate_design_bindings(model, contract())
    assert result.valid is (not surplus) and result.truncated is bool(surplus)
    if surplus:
        assert codes(result) == ["analysis_truncated"]
        assert result.issues[0].location == ("root", "children", MAX_DESIGN_NODES - 1)
        assert result.issues[0].binding is None


@pytest.mark.parametrize("surplus", [0, 1])
def test_depth_limit(surplus: int) -> None:
    # Assemblage via listes pour ne pas tester ici la profondeur du parser Pydantic.
    model = design([])
    children = model.root.children
    for _ in range(MAX_DESIGN_DEPTH + surplus):
        node = DesignNode(type="text", children=[])
        children.append(node)
        assert node.children is not None
        children = node.children
    result = validate_design_bindings(model, contract())
    assert result.valid is (not surplus) and result.truncated is bool(surplus)
    if surplus:
        assert codes(result) == ["analysis_truncated"]
        assert len(result.issues[0].location) == 1 + 2 * (MAX_DESIGN_DEPTH + 1)


@pytest.mark.parametrize("surplus", [0, 1])
def test_issue_limit(surplus: int) -> None:
    model = design(
        [{"type": "text", "binding": "missing"}] * (MAX_DESIGN_ISSUES + surplus)
        + [{"type": "text"}]
    )
    result = validate_design_bindings(model, contract())
    assert not result.valid and result.truncated is bool(surplus)
    assert len(result.issues) == MAX_DESIGN_ISSUES
    assert codes(result) == ["unknown_variable"] * (MAX_DESIGN_ISSUES - 1) + [
        "analysis_truncated" if surplus else "unknown_variable"
    ]


def test_combined_limits() -> None:
    model = design(
        [{"type": "text", "binding": "x"}] * MAX_DESIGN_ISSUES
        + [{"type": "text"}] * (MAX_DESIGN_NODES - MAX_DESIGN_ISSUES)
    )
    result = validate_design_bindings(model, contract())
    assert result.truncated and len(result.issues) == MAX_DESIGN_ISSUES
    assert codes(result)[-1] == "analysis_truncated"


def test_shared_occurrences_and_cycle() -> None:
    model = design([])
    node = DesignNode(type="button", binding="missing", children=[])
    model.root.children.extend([node, node])
    result = validate_design_bindings(model, contract())
    assert [i.location for i in result.issues] == [
        ("root", "children", 0, "binding"),
        ("root", "children", 1, "binding"),
    ]
    assert node.children is not None
    node.children.append(node)
    result = validate_design_bindings(model, contract())
    assert (
        result.truncated
        and not result.valid
        and codes(result)[-1] == "analysis_truncated"
    )


def test_purity_nonmutation_and_independent_validators(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = design(
        [{"type": "button", "binding": "create", "props": {}, "columns": []}]
    )
    c = contract(actions={"create": {"method": "GET", "path": "/"}})
    before = (model.model_dump(exclude_unset=True), c.model_dump(exclude_unset=True))
    identities = (
        model.root.children,
        model.root.children[0],
        model.root.children[0].props,
        model.root.children[0].columns,
        c.context,
        c.actions,
    )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("unexpected dependency or full copy")

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        for name in ("open", "stat", "listdir", "scandir"):
            patch.setattr(os, name, forbidden)
        for name in ("open", "read_text", "read_bytes"):
            patch.setattr(Path, name, forbidden)
        patch.setattr(io, "read_design", forbidden)
        patch.setattr(reader, "read_view_contract", forbidden)
        patch.setattr(nesting, "validate_design_nesting", forbidden)
        patch.setattr(DesignFile, "model_dump", forbidden)
        patch.setattr(ViewContract, "model_dump", forbidden)
        assert validate_design_bindings(model, c).valid
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
    assert all(a is b for a, b in zip(identities, after, strict=True))


def test_lazy_wide_traversal() -> None:
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
    result = validate_design_bindings(model, contract())
    assert result.truncated and children.consumed == MAX_DESIGN_NODES
