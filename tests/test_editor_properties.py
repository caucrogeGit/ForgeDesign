"""Configuration des propriétés : contrat, validation ciblée, no-op, immutabilité."""

import builtins
import os
import socket
import subprocess
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

import forge_design.editor as editor
from forge_design.app import create_tool_registry
from forge_design.contracts.models import ViewContract
from forge_design.design import (
    DesignFile,
    TableColumn,
    nesting,
    validate_design_bindings,
    validate_design_nesting,
)
from forge_design.editor import (
    DesignEditResult,
    properties,
    set_design_binding,
    set_design_props,
    set_design_visibility,
    set_table_columns,
)
from forge_design.limits import MAX_DESIGN_ISSUES, MAX_TABLE_COLUMNS

CONTRACT = ViewContract.model_validate(
    {
        "name": "contacts/list",
        "template": "mvc/views/contacts/list.html",
        "context": {
            "page_title": {"type": "string"},
            "intro": {"type": "string"},
            "can_view": {"type": "boolean"},
            "is_admin": {"type": "boolean"},
            "count": {"type": "integer"},
            "contacts": {
                "type": "list",
                "entity": "Contact",
                "fields": {"nom": "string", "email": "string", "telephone": "string"},
            },
            "items": {"type": "list"},
        },
        "actions": {"delete": {"method": "POST", "path": "/contacts/delete"}},
    }
)

SECTION = (0,)
CARD = (0, 0)
TITLE = (0, 0, 0)
TEXT = (0, 0, 1)
BUTTON = (0, 0, 2)
OTHER_CARD = (0, 1)
TABLE = (1,)
BARE_TABLE = (2,)


def design(children: list[dict[str, Any]]) -> DesignFile:
    model = DesignFile.model_validate(
        {
            "version": "0.1",
            "view": "contacts/list",
            "source_contract": "contacts/list.view.json",
            "root": {"type": "page", "children": children},
        }
    )
    # Une fixture mal imbriquée serait refusée en amont : la vérifier ici.
    assert validate_design_nesting(model).valid
    return model


def sample() -> DesignFile:
    """page / section[card[title, text, button], card] / table contacts / table."""
    return design(
        [
            {
                "type": "section",
                "props": {"class": "p-4"},
                "children": [
                    {
                        "type": "card",
                        "children": [
                            {"type": "title"},
                            {"type": "text", "binding": "intro"},
                            {"type": "button"},
                        ],
                    },
                    {"type": "card", "props": {"tag": "article"}},
                ],
            },
            {
                "type": "table",
                "binding": "contacts",
                "visible_if": "can_view",
                "props": {"class": "w-full"},
                "children": [{"type": "empty_state"}],
            },
            {"type": "table"},
        ]
    )


def in_card(*children: dict[str, Any]) -> list[dict[str, Any]]:
    card = {"type": "card", "children": [*children]}
    return [{"type": "section", "children": [card]}]


def node(model: DesignFile, path: tuple[int, ...]) -> dict[str, Any]:
    current: Any = model.model_dump(exclude_unset=True)["root"]
    for index in path:
        current = current["children"][index]
    return current


def dump(model: DesignFile) -> dict[str, Any]:
    return model.model_dump(exclude_unset=True)


def assert_refused(result: DesignEditResult, original: DesignFile, code: str) -> None:
    assert not result.changed
    assert result.affected_path is None
    assert result.design is original
    assert [issue.code for issue in result.issues] == ["editor." + code]


def assert_noop(result: DesignEditResult, original: DesignFile, path: Any) -> None:
    assert result == DesignEditResult(original, False, path, ())
    assert result.design is original


def column(label: str, binding: str) -> TableColumn:
    return TableColumn(label=label, binding=binding)


def bind(
    model: DesignFile, path: Any, binding: Any, contract: Any = CONTRACT
) -> DesignEditResult:
    return set_design_binding(model, path=path, binding=binding, contract=contract)


def show(model: DesignFile, path: Any, condition: Any) -> DesignEditResult:
    return set_design_visibility(
        model, path=path, visible_if=condition, contract=CONTRACT
    )


def cols(model: DesignFile, path: Any, columns: Any) -> DesignEditResult:
    return set_table_columns(model, path=path, columns=columns, contract=CONTRACT)


# Binding.


@pytest.mark.parametrize(
    ("path", "binding"),
    [
        (TITLE, "page_title"),
        (TEXT, "page_title"),
        (TABLE, "items"),
        (BUTTON, "delete"),
    ],
)
def test_binding_valid(path: tuple[int, ...], binding: str) -> None:
    result = bind(sample(), path, binding)
    assert result.changed and result.issues == () and result.affected_path == path
    assert node(result.design, path)["binding"] == binding


@pytest.mark.parametrize(
    ("path", "binding"),
    [
        (TITLE, "missing"),  # variable inconnue
        (TITLE, "can_view"),  # title → boolean
        (TEXT, "contacts"),  # text → list
        (TABLE, "page_title"),  # table → string
        (BUTTON, "unknown_action"),
        (BUTTON, "page_title"),  # button attend une action
    ],
)
def test_binding_invalid(path: tuple[int, ...], binding: str) -> None:
    original = sample()
    result = bind(original, path, binding)
    assert_refused(result, original, "invalid_binding")
    assert result.issues[0].path == path


@pytest.mark.parametrize("path", [SECTION, CARD, ()])
def test_binding_not_supported(path: tuple[int, ...]) -> None:
    original = sample()
    assert_refused(bind(original, path, "intro"), original, "binding_not_supported")


@pytest.mark.parametrize("binding", ["", 1, b"intro", ["intro"]])
def test_binding_bad_values(binding: Any) -> None:
    original = sample()
    result = bind(original, TEXT, binding)
    assert_refused(result, original, "invalid_binding")
    assert result.issues[0].path == TEXT


def test_binding_clear() -> None:
    result = bind(sample(), TEXT, None)
    assert result.changed and "binding" not in node(result.design, TEXT)


def test_binding_clear_on_unsupported_type_repairs() -> None:
    # Pydantic accepte un binding sur section ; le validateur le signale.
    broken = design([{"type": "section", "binding": "intro"}])
    assert not validate_design_bindings(broken, CONTRACT).valid
    result = bind(broken, (0,), None)
    assert result.changed and node(result.design, (0,)) == {"type": "section"}


def test_binding_noop() -> None:
    original = sample()
    assert_noop(bind(original, TEXT, "intro"), original, TEXT)
    assert_noop(bind(original, TITLE, None), original, TITLE)


def test_binding_str_subclass_normalized() -> None:
    class Sneaky(str):
        pass

    result = bind(sample(), TITLE, Sneaky("page_title"))
    assert type(node(result.design, TITLE)["binding"]) is str


# visible_if.


@pytest.mark.parametrize("path", [SECTION, TITLE, TABLE, CARD, ()])
def test_visibility_valid(path: tuple[int, ...]) -> None:
    result = show(sample(), path, "is_admin")
    assert result.changed and node(result.design, path)["visible_if"] == "is_admin"


@pytest.mark.parametrize("condition", ["page_title", "missing", "count", "contacts"])
def test_visibility_invalid(condition: str) -> None:
    original = sample()
    assert_refused(show(original, SECTION, condition), original, "invalid_condition")


@pytest.mark.parametrize("condition", ["", 0, True])
def test_visibility_bad_values(condition: Any) -> None:
    original = sample()
    assert_refused(show(original, SECTION, condition), original, "invalid_condition")


def test_visibility_clear_and_noop() -> None:
    original = sample()
    cleared = show(original, TABLE, None)
    assert cleared.changed and "visible_if" not in node(cleared.design, TABLE)
    assert_noop(show(original, TABLE, "can_view"), original, TABLE)


# Props.


@pytest.mark.parametrize(
    "props",
    [
        {"class": "max-w-5xl"},
        {"tag": "section"},
        {"s": "x", "b": True, "i": 3, "f": 1.5, "zero": 0, "neg": -2.25},
        {"data-role": "hero", "aria-label": "Titre"},
        {},
    ],
)
def test_props_valid(props: dict[str, Any]) -> None:
    result = set_design_props(sample(), path=TITLE, props=props)
    assert result.changed
    assert node(result.design, TITLE)["props"] == props


def test_props_empty_mapping_stays_empty() -> None:
    result = set_design_props(sample(), path=TITLE, props={})
    assert node(result.design, TITLE) == {"type": "title", "props": {}}


@pytest.mark.parametrize(
    "props",
    [
        {"": "x"},
        {"a": None},
        {"a": [1]},
        {"a": {"b": 1}},
        {"a": float("nan")},
        {"a": float("inf")},
        {1: "x"},
        "class=x",
        [("a", "b")],
    ],
)
def test_props_invalid(props: Any) -> None:
    original = sample()
    assert_refused(
        set_design_props(original, path=SECTION, props=props),
        original,
        "invalid_props",
    )


def test_props_clear_and_noop() -> None:
    original = sample()
    cleared = set_design_props(original, path=SECTION, props=None)
    assert "props" not in node(cleared.design, SECTION)
    same = set_design_props(original, path=SECTION, props={"class": "p-4"})
    assert_noop(same, original, SECTION)
    assert_noop(set_design_props(original, path=TITLE, props=None), original, TITLE)


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ({"n": 1}, {"n": True}),
        ({"n": 1}, {"n": 1.0}),
        ({"n": True}, {"n": 1}),
        ({"a": "x", "b": "y"}, {"b": "y", "a": "x"}),
    ],
)
def test_props_strict_change_detection(
    before: dict[str, Any], after: dict[str, Any]
) -> None:
    # Égaux en Python, distincts dans le JSON : pas un no-op.
    start = set_design_props(sample(), path=SECTION, props=before).design
    result = set_design_props(start, path=SECTION, props=after)
    assert result.changed
    stored = node(result.design, SECTION)["props"]
    assert list(stored.items()) == list(after.items())
    assert [type(v) for v in stored.values()] == [type(v) for v in after.values()]


def test_props_copy_independent() -> None:
    props: dict[str, Any] = {"class": "a"}
    result = set_design_props(sample(), path=SECTION, props=props)
    props["class"] = "b"
    props["extra"] = 1
    assert node(result.design, SECTION)["props"] == {"class": "a"}


# Colonnes.


def test_columns_valid_ordered() -> None:
    columns = (
        column("Nom", "nom"),
        column("Email", "email"),
        column("Tél", "telephone"),
    )
    result = cols(sample(), TABLE, columns)
    assert result.changed and result.affected_path == TABLE
    assert node(result.design, TABLE)["columns"] == [
        {"label": "Nom", "binding": "nom"},
        {"label": "Email", "binding": "email"},
        {"label": "Tél", "binding": "telephone"},
    ]


def test_columns_unknown_field() -> None:
    original = sample()
    result = cols(original, TABLE, [column("Nom", "nom"), column("Âge", "age")])
    assert_refused(result, original, "invalid_table_column")


@pytest.mark.parametrize("columns", [[column("Nom", "nom")], []])
def test_columns_without_table_binding(columns: list[TableColumn]) -> None:
    original = sample()
    result = cols(original, BARE_TABLE, columns)
    assert_refused(result, original, "invalid_table_binding")


@pytest.mark.parametrize("binding", ["page_title", "missing"])
def test_columns_binding_not_list(binding: str) -> None:
    original = design([{"type": "table", "binding": binding}])
    result = cols(original, (0,), [column("Nom", "nom")])
    assert_refused(result, original, "invalid_table_binding")


def test_columns_fields_unavailable() -> None:
    original = design([{"type": "table", "binding": "items"}])
    result = cols(original, (0,), [column("Nom", "nom")])
    assert_refused(result, original, "invalid_table_binding")
    empty = cols(original, (0,), [])
    assert empty.changed and node(empty.design, (0,))["columns"] == []


def test_columns_empty_list_stays_distinct() -> None:
    result = cols(sample(), TABLE, [])
    assert result.changed and node(result.design, TABLE)["columns"] == []
    cleared = cols(result.design, TABLE, None)
    assert cleared.changed and "columns" not in node(cleared.design, TABLE)


@pytest.mark.parametrize("path", [OTHER_CARD, SECTION, ()])
def test_columns_not_supported(path: tuple[int, ...]) -> None:
    original = sample()
    result = cols(original, path, [column("Nom", "nom")])
    assert_refused(result, original, "columns_not_supported")


def test_columns_clear_on_non_table_is_noop_when_absent() -> None:
    original = sample()
    assert_noop(cols(original, OTHER_CARD, None), original, OTHER_CARD)


def test_columns_limit() -> None:
    exact = [column(f"C{i}", "nom") for i in range(MAX_TABLE_COLUMNS)]
    result = cols(sample(), TABLE, exact)
    assert result.changed
    assert len(node(result.design, TABLE)["columns"]) == MAX_TABLE_COLUMNS
    original = sample()
    over = cols(original, TABLE, [*exact, column("X", "nom")])
    assert_refused(over, original, "column_limit")


@pytest.mark.parametrize(
    "columns", ["nom", [{"label": "Nom", "binding": "nom"}], [None], 3]
)
def test_columns_bad_values(columns: Any) -> None:
    original = sample()
    assert_refused(cols(original, TABLE, columns), original, "invalid_table_column")


def test_columns_noop_and_copy() -> None:
    columns = [column("Nom", "nom")]
    first = cols(sample(), TABLE, columns)
    columns.append(column("Email", "email"))
    assert len(node(first.design, TABLE)["columns"]) == 1
    same = cols(first.design, TABLE, [column("Nom", "nom")])
    assert_noop(same, first.design, TABLE)


# Une opération = une propriété.


def test_binding_edit_touches_only_binding() -> None:
    before = node(sample(), TABLE)
    after = node(bind(sample(), TABLE, "items").design, TABLE)
    assert after.pop("binding") == "items"
    before.pop("binding")
    assert after == before


def test_props_edit_touches_only_props() -> None:
    original = cols(sample(), TABLE, [column("Nom", "nom")]).design
    before = node(original, TABLE)
    result = set_design_props(original, path=TABLE, props={"class": "table"})
    after = node(result.design, TABLE)
    assert after.pop("props") == {"class": "table"}
    before.pop("props")
    assert after == before


def test_other_nodes_untouched() -> None:
    before = dump(sample())
    after = dump(show(sample(), TITLE, "is_admin").design)
    title = after["root"]["children"][0]["children"][0]["children"][0]
    assert title.pop("visible_if") == "is_admin"
    assert after == before


# Erreurs préexistantes ailleurs.


def test_binding_edit_ignores_other_invalid_binding() -> None:
    original = design(
        in_card({"type": "title", "binding": "missing"}, {"type": "text"})
    )
    assert not validate_design_bindings(original, CONTRACT).valid
    result = bind(original, (0, 0, 1), "intro")
    assert result.changed and result.issues == ()


def test_visibility_edit_ignores_other_invalid_condition() -> None:
    original = design(
        [{"type": "section", "visible_if": "page_title"}, {"type": "section"}]
    )
    assert show(original, (1,), "can_view").changed


def test_columns_edit_ignores_other_invalid_table() -> None:
    invalid = [{"label": "X", "binding": "zzz"}]
    original = design(
        [
            {"type": "table", "binding": "contacts", "columns": invalid},
            {"type": "table", "binding": "contacts"},
        ]
    )
    assert cols(original, (1,), [column("Nom", "nom")]).changed


def test_edit_not_blocked_by_truncation_elsewhere() -> None:
    # Plus d'erreurs ailleurs que MAX_DESIGN_ISSUES : le validateur global tronque.
    count = MAX_DESIGN_ISSUES + 5
    texts = [{"type": "text", "binding": "missing"} for _ in range(count)]
    original = design([{"type": "section", "children": [*texts, {"type": "text"}]}])
    assert validate_design_bindings(original, CONTRACT).truncated
    result = bind(original, (0, count), "intro")
    assert result.changed and node(result.design, (0, count))["binding"] == "intro"


def test_analysis_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    real = properties.validate_design_bindings

    def truncated(design: DesignFile, contract: ViewContract) -> Any:
        result = real(design, contract)
        return type(result)(False, result.issues, truncated=True)

    monkeypatch.setattr(properties, "validate_design_bindings", truncated)
    original = sample()
    assert_refused(bind(original, TEXT, "page_title"), original, "analysis_truncated")


# Page racine.


def test_page_root_policy() -> None:
    original = sample()
    props = set_design_props(original, path=(), props={"class": "min-h-screen"})
    assert props.changed and props.affected_path == ()
    assert show(original, (), "can_view").changed
    assert_refused(show(original, (), "intro"), original, "invalid_condition")
    assert_refused(bind(original, (), "intro"), original, "binding_not_supported")
    assert_refused(cols(original, (), []), original, "columns_not_supported")


# Entrées invalides communes.


@pytest.mark.parametrize("path", [(9,), (0, 9), (-1,), (0, 0, 0, 0)])
def test_path_not_found(path: tuple[int, ...]) -> None:
    original = sample()
    for result in (
        bind(original, path, "intro"),
        show(original, path, "can_view"),
        set_design_props(original, path=path, props={}),
        cols(original, path, []),
    ):
        assert_refused(result, original, "path_not_found")


@pytest.mark.parametrize("path", [(True,), "0", [0], None])
def test_invalid_path(path: Any) -> None:
    original = sample()
    for result in (
        bind(original, path, None),
        show(original, path, None),
        set_design_props(original, path=path, props={}),
        cols(original, path, None),
    ):
        assert_refused(result, original, "invalid_path")


@pytest.mark.parametrize("contract", [None, {"name": "x"}, "contract"])
def test_invalid_contract(contract: Any) -> None:
    original = sample()
    result = bind(original, TEXT, "intro", contract)
    assert_refused(result, original, "invalid_contract")


def test_mutated_contract_revalidated() -> None:
    contract = CONTRACT.model_copy(deep=True)
    contract.context["page_title"] = "not a variable"  # type: ignore[assignment]
    original = sample()
    result = bind(original, TITLE, "page_title", contract)
    assert_refused(result, original, "invalid_contract")


def test_invalid_design() -> None:
    original = sample()
    original.root.children.append("not a node")  # type: ignore[arg-type]
    result = set_design_props(original, path=SECTION, props={})
    assert_refused(result, original, "invalid_design")


def test_invalid_result_never_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    real = nesting.validate_design_nesting
    calls = 0

    def second_call_fails(model: DesignFile) -> Any:
        nonlocal calls
        calls += 1
        result = real(model)
        return result if calls == 1 else type(result)(False, ())

    monkeypatch.setattr(nesting, "validate_design_nesting", second_call_fails)
    original = sample()
    result = set_design_props(original, path=SECTION, props={"class": "x"})
    assert_refused(result, original, "invalid_result")


# Immutabilité, pureté, déterminisme.


def test_inputs_never_mutated() -> None:
    original = sample()
    before = dump(original)
    contract_before = CONTRACT.model_dump()
    section = original.root.children[0]
    lists = (original.root.children, section.children)
    copies = [list(item or []) for item in lists]
    props_before = dict(section.props or {})
    bind(original, TITLE, "page_title")
    show(original, SECTION, "can_view")
    set_design_props(original, path=SECTION, props={"class": "other"})
    cols(original, TABLE, [column("Nom", "nom")])
    set_design_props(original, path=SECTION, props={"": "refused"})
    assert dump(original) == before
    assert [list(item or []) for item in lists] == copies
    assert dict(section.props or {}) == props_before
    assert CONTRACT.model_dump() == contract_before


def test_pure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def recorder(name: str) -> Any:
        def forbidden(*args: Any, **kwargs: Any) -> Any:
            calls.append(name)
            raise AssertionError("I/O interdite : " + name)

        return forbidden

    for target, name in (
        (builtins, "open"),
        (os, "open"),
        (Path, "read_text"),
        (Path, "write_text"),
        (Path, "read_bytes"),
        (Path, "write_bytes"),
        (socket, "socket"),
        (subprocess, "Popen"),
    ):
        monkeypatch.setattr(target, name, recorder(name))
    model = bind(sample(), TITLE, "page_title").design
    model = show(model, SECTION, "can_view").design
    model = set_design_props(model, path=SECTION, props={"class": "x"}).design
    changed = cols(model, TABLE, [column("Nom", "nom")]).changed
    # Restaurer avant toute assertion : pytest a besoin des I/O pour son rapport.
    monkeypatch.undo()
    assert calls == [] and changed


def test_deterministic() -> None:
    def run() -> tuple[DesignEditResult, ...]:
        return (
            bind(sample(), TITLE, "page_title"),
            bind(sample(), TITLE, "missing"),
            set_design_props(sample(), path=SECTION, props={"class": "x"}),
            cols(sample(), TABLE, [column("Nom", "nom")]),
        )

    assert run() == run()


def test_no_io_generation_or_preview_imports() -> None:
    names = set(vars(properties))
    assert not names & {
        "read_design",
        "write_design",
        "read_view_contract",
        "write_generated_template",
        "generate_simple_template",
        "build_template_diff",
        "render_preview",
        "os",
        "Path",
        "_BINDING_RULES",
    }


def test_exports_and_registry() -> None:
    for name in (
        "set_design_binding",
        "set_design_visibility",
        "set_design_props",
        "set_table_columns",
    ):
        assert name in editor.__all__ and hasattr(editor, name)
    assert len(create_tool_registry().list()) == 5


def test_end_to_end_scenario() -> None:
    def base_design() -> DesignFile:
        table = {"type": "table", "binding": "contacts"}
        return design([*in_card({"type": "title"}), table])

    base = base_design()
    r1 = bind(base, (0, 0, 0), "page_title")
    r2 = show(r1.design, (0,), "can_view")
    r3 = set_design_props(r2.design, path=(0,), props={"class": "max-w-5xl mx-auto"})
    r4 = cols(r3.design, (1,), (column("Nom", "nom"), column("Email", "email")))
    assert all(r.changed for r in (r1, r2, r3, r4))
    assert dump(r4.design)["root"] == {
        "type": "page",
        "children": [
            {
                "type": "section",
                "visible_if": "can_view",
                "props": {"class": "max-w-5xl mx-auto"},
                "children": [
                    {
                        "type": "card",
                        "children": [{"type": "title", "binding": "page_title"}],
                    }
                ],
            },
            {
                "type": "table",
                "binding": "contacts",
                "columns": [
                    {"label": "Nom", "binding": "nom"},
                    {"label": "Email", "binding": "email"},
                ],
            },
        ],
    }
    assert dump(base) == dump(base_design())


def test_props_accept_any_mapping() -> None:
    # Pydantic strict n'accepte qu'un dict : la copie dict() rend tout Mapping valide.
    original = sample()
    proxy = MappingProxyType({"class": "p-4"})
    assert_noop(
        set_design_props(original, path=SECTION, props=proxy), original, SECTION
    )
    other = set_design_props(original, path=SECTION, props=MappingProxyType({"a": 1}))
    assert other.changed and node(other.design, SECTION)["props"] == {"a": 1}
