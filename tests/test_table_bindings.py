"""Collections/colonnes : exactitude, projections et parcours bornés."""

import builtins
import os
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest

from forge_design.contracts import ViewContract, reader
from forge_design.contracts.models import ViewContextVariable
from forge_design.design import (
    DesignFile,
    DesignNode,
    TableColumn,
    bindings,
    io,
    nesting,
    suggest_table_columns,
    validate_design_bindings,
    validate_table_bindings,
)
from forge_design.limits import (
    MAX_DESIGN_DEPTH,
    MAX_DESIGN_ISSUES,
    MAX_DESIGN_NODES,
    MAX_TABLE_COLUMNS,
)


def contract(**variable: Any) -> ViewContract:
    return ViewContract.model_validate(
        {
            "name": "contacts",
            "template": "mvc/views/list.html",
            "context": {"contacts": {"type": "list", **variable}},
        }
    )


def design(children: list[Any]) -> DesignFile:
    return DesignFile.model_validate(
        {
            "version": "0.1",
            "view": "unrelated",
            "source_contract": "missing.view.json",
            "root": {"type": "page", "children": children},
        }
    )


def table(names: list[str], **extra: Any) -> dict[str, Any]:
    return {
        "type": "table",
        "binding": "contacts",
        "columns": [{"label": "Label " + name, "binding": name} for name in names],
        **extra,
    }


def codes(result: Any) -> list[str]:
    return [i.code.removeprefix("design.table.") for i in result.issues]


def test_official_fixture_and_nominal() -> None:
    c = contract(
        entity="Contact",
        fields={"nom": "string", "email": "email", "telephone": "string"},
    )
    # La fixture officielle conserve son text → page_title.
    data = c.model_dump(exclude_unset=True)
    data["context"]["page_title"] = {"type": "string"}
    c = ViewContract.model_validate(data)
    model = DesignFile.model_validate_json(
        (
            Path(__file__).parent / "fixtures/design/contacts-list.design.json"
        ).read_text()
    )
    assert validate_design_bindings(model, c).valid
    result = validate_table_bindings(model, c)
    assert result.valid and not result.truncated and result.issues == ()
    info = result.tables[0]
    assert info.location == ("root", "children", 1)
    assert (
        info.binding == "contacts"
        and info.entity == "Contact"
        and info.status == "resolved"
    )
    assert info.available_fields == ("nom", "email", "telephone")
    assert [(v.index, v.binding, v.field_type, v.valid) for v in info.columns] == [
        (0, "nom", "string", True),
        (1, "email", "email", True),
        (2, "telephone", "string", True),
    ]


def test_unknown_order_labels_duplicates_and_literal_fields() -> None:
    model = design(
        [
            table(
                [
                    "nom",
                    "missing",
                    "nom",
                    "other",
                    "profile.email",
                    "é",
                    "e\u0301",
                    "Nom",
                    " nom ",
                ]
            )
        ]
    )
    c = contract(
        fields={"nom": " ArbitraryType ", "profile.email": "email", "é": "telephone"}
    )
    result = validate_table_bindings(model, c)
    assert not result.valid and not result.truncated
    assert codes(result) == ["unknown_field"] * 5
    assert [i.location for i in result.issues] == [
        ("root", "children", 0, "columns", n, "binding") for n in (1, 3, 6, 7, 8)
    ]
    assert [i.column_binding for i in result.issues] == [
        "missing",
        "other",
        "e\u0301",
        "Nom",
        " nom ",
    ]
    assert all(i.table_binding == "contacts" for i in result.issues)
    assert result.tables[0].columns[0].field_type == " ArbitraryType "
    assert result.tables[0].columns[0].label == "Label nom"
    assert result.tables[0].columns[2].valid is True
    assert result.tables[0].columns[4].valid is True
    # Aucun champ déduit de "profile".
    assert codes(
        validate_table_bindings(
            design([table(["profile.email"])]), contract(fields={"profile": "object"})
        )
    ) == ["unknown_field"]


@pytest.mark.parametrize("fields", [None, {}])
@pytest.mark.parametrize("columns", [None, [], ["x", "y"]])
def test_fields_absent_vs_empty(
    fields: dict[str, str] | None, columns: list[str] | None
) -> None:
    c = contract(**({} if fields is None else {"fields": fields}))
    node = table(columns or [])
    if columns is None:
        node.pop("columns")
    result = validate_table_bindings(design([node]), c)
    assert result.valid is (not columns)
    assert result.tables[0].status == (
        "fields_unavailable" if fields is None else "resolved"
    )
    assert codes(result) == (
        []
        if not columns
        else ["fields_unavailable"]
        if fields is None
        else ["unknown_field", "unknown_field"]
    )
    if columns and fields is None:
        assert result.issues[0].location == ("root", "children", 0, "columns")
        assert all(col.valid is None for col in result.tables[0].columns)


@pytest.mark.parametrize(
    "case,status",
    [
        ("absent", "no_binding"),
        ("unknown", "unresolved_variable"),
        ("string", "type_mismatch"),
        ("object", "type_mismatch"),
        ("boolean", "type_mismatch"),
    ],
)
def test_no_cascade(case: str, status: str) -> None:
    node = table(["x", "y"])
    if case == "absent":
        node.pop("binding")
    elif case == "unknown":
        node["binding"] = "missing"
    c = contract(
        type=case if case not in {"absent", "unknown"} else "list",
        fields={"x": "string"},
    )
    model = design([node])
    result = validate_table_bindings(model, c)
    assert result.valid and result.issues == ()
    assert result.tables[0].status == status
    assert result.tables[0].available_fields == ()
    assert all(
        col.valid is None and col.field_type is None for col in result.tables[0].columns
    )
    assert validate_design_bindings(model, c).valid is (case == "absent")


@pytest.mark.parametrize(
    "children,expected",
    [
        ([], False),
        ([{"type": "empty_state"}], True),
        ([{"type": "empty_state"}, {"type": "empty_state"}], True),
        ([{"type": "section", "children": [{"type": "empty_state"}]}], False),
    ],
)
def test_empty_state_direct_only(children: list[Any], expected: bool) -> None:
    result = validate_table_bindings(design([table([], children=children)]), contract())
    assert result.valid and result.tables[0].has_empty_state is expected


def test_nested_shared_and_non_table_columns() -> None:
    model = design(
        [
            {
                "type": "section",
                "columns": [{"label": "L", "binding": "ignored"}],
                "children": [table(["x"])],
            }
        ]
    )
    shared = model.root.children[0].children
    assert shared is not None
    model.root.children.append(shared[0])
    result = validate_table_bindings(model, contract(fields={"x": "string"}))
    assert result.valid
    assert [i.location for i in result.tables] == [
        ("root", "children", 0, "children", 0),
        ("root", "children", 1),
    ]
    assert result.tables[0].available_fields is result.tables[1].available_fields


@pytest.mark.parametrize(
    "fields", [None, {}, {"z": "custom", "a": "email", "created_at": "date"}]
)
def test_suggestions(fields: dict[str, str] | None) -> None:
    variable = ViewContextVariable.model_validate(
        {
            "type": "list",
            "entity": "Unresolved",
            **({} if fields is None else {"fields": fields}),
        }
    )
    before = variable.model_dump(exclude_unset=True)
    result = suggest_table_columns(variable)
    assert [(c.binding, c.field_type, c.label) for c in result] == [
        (key, value, key) for key, value in (fields or {}).items()
    ]
    assert isinstance(result, tuple) and before == variable.model_dump(
        exclude_unset=True
    )
    if result:
        with pytest.raises(FrozenInstanceError):
            result[0].label = "changed"  # type: ignore[misc]


@pytest.mark.parametrize("kind", ["string", "boolean", "integer", "number", "object"])
def test_suggestions_non_list(kind: str) -> None:
    with pytest.raises(ValueError):
        suggest_table_columns(ViewContextVariable.model_validate({"type": kind}))


@pytest.mark.parametrize("surplus", [0, 1])
@pytest.mark.parametrize("resolved", [True, False])
def test_columns_limit(surplus: int, resolved: bool) -> None:
    node = table(["x"] * (MAX_TABLE_COLUMNS + surplus))
    if not resolved:
        node.pop("binding")
    result = validate_table_bindings(design([node]), contract(fields={"x": "string"}))
    assert result.valid is (not surplus) and result.truncated is bool(surplus)
    assert len(result.tables[0].columns) == MAX_TABLE_COLUMNS
    if surplus:
        assert codes(result) == ["analysis_truncated"]
        assert result.issues[-1].location == (
            "root",
            "children",
            0,
            "columns",
            MAX_TABLE_COLUMNS,
            "binding",
        )


@pytest.mark.parametrize("surplus", [0, 1])
def test_issue_limit_across_tables(surplus: int) -> None:
    nodes = [table(["x"] * MAX_DESIGN_ISSUES), table(["extra"] if surplus else [])]
    result = validate_table_bindings(design(nodes), contract(fields={}))
    assert len(result.issues) == MAX_DESIGN_ISSUES and result.truncated is bool(surplus)
    assert codes(result) == ["unknown_field"] * (MAX_DESIGN_ISSUES - 1) + [
        "analysis_truncated" if surplus else "unknown_field"
    ]


@pytest.mark.parametrize("surplus", [0, 1])
def test_node_limit(surplus: int) -> None:
    result = validate_table_bindings(
        design([{"type": "text"}] * (MAX_DESIGN_NODES - 1 + surplus)), contract()
    )
    assert result.valid is (not surplus) and result.truncated is bool(surplus)
    assert codes(result) == (["analysis_truncated"] if surplus else [])


@pytest.mark.parametrize("surplus", [0, 1])
def test_depth_limit(surplus: int) -> None:
    model = design([])
    children = model.root.children
    for _ in range(MAX_DESIGN_DEPTH + surplus):
        node = DesignNode(type="table", children=[])
        children.append(node)
        assert node.children is not None
        children = node.children
    result = validate_table_bindings(model, contract())
    assert result.valid is (not surplus) and result.truncated is bool(surplus)
    assert len(result.tables) == MAX_DESIGN_DEPTH


def test_cycle_bounded() -> None:
    model = design([table([], children=[])])
    node = model.root.children[0]
    assert node.children is not None
    node.children.append(node)
    result = validate_table_bindings(model, contract())
    assert (
        result.truncated
        and not result.valid
        and codes(result) == ["analysis_truncated"]
    )


def test_lazy_columns_and_children() -> None:
    class Columns(list[TableColumn]):
        consumed = 0

        def __iter__(self):
            for column in super().__iter__():
                self.consumed += 1
                if self.consumed > MAX_TABLE_COLUMNS + 1:
                    raise AssertionError("all columns copied")
                yield column

    class Children(list[DesignNode]):
        consumed = 0

        def __iter__(self):
            for child in super().__iter__():
                self.consumed += 1
                if self.consumed > MAX_DESIGN_NODES:
                    raise AssertionError("unbounded empty state search")
                yield child

    model = design([table([])])
    cols = Columns([TableColumn(label="L", binding="x")] * (MAX_TABLE_COLUMNS * 2))
    object.__setattr__(model.root.children[0], "columns", cols)
    assert validate_table_bindings(model, contract(fields={"x": "string"})).truncated
    assert cols.consumed == MAX_TABLE_COLUMNS + 1
    model = design([table([])])
    children = Children(
        [DesignNode(type="text")] * (MAX_DESIGN_NODES * 2)
        + [DesignNode(type="empty_state")]
    )
    object.__setattr__(model.root.children[0], "children", children)
    result = validate_table_bindings(model, contract())
    assert result.truncated and not result.tables[0].has_empty_state
    assert children.consumed == MAX_DESIGN_NODES - 1


def test_purity_nonmutation_determinism_and_frozen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = design([table(["x", "missing"], children=[{"type": "empty_state"}])])
    c = contract(entity="Missing", fields={"x": "custom"})
    before = (model.model_dump(exclude_unset=True), c.model_dump(exclude_unset=True))
    node = model.root.children[0]
    refs = (
        model.root.children,
        node.columns,
        node.children,
        c.context,
        c.context["contacts"].fields,
    )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("unexpected dependency")

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        for name in ("open", "stat", "listdir", "scandir"):
            patch.setattr(os, name, forbidden)
        for name in ("open", "read_text", "read_bytes"):
            patch.setattr(Path, name, forbidden)
        patch.setattr(io, "read_design", forbidden)
        patch.setattr(reader, "read_view_contract", forbidden)
        patch.setattr(bindings, "validate_design_bindings", forbidden)
        patch.setattr(nesting, "validate_design_nesting", forbidden)
        result = validate_table_bindings(model, c)
        assert suggest_table_columns(c.context["contacts"])[0].binding == "x"
    assert result == validate_table_bindings(model, c)
    assert before == (
        model.model_dump(exclude_unset=True),
        c.model_dump(exclude_unset=True),
    )
    after = (
        model.root.children,
        node.columns,
        node.children,
        c.context,
        c.context["contacts"].fields,
    )
    assert all(a is b for a, b in zip(refs, after, strict=True))
    for value, attribute in [
        (result, "valid"),
        (result.tables[0], "binding"),
        (result.tables[0].columns[0], "label"),
        (result.issues[0], "code"),
    ]:
        with pytest.raises(FrozenInstanceError):
            setattr(value, attribute, None)
    assert isinstance(result.tables, tuple) and isinstance(result.issues, tuple)
