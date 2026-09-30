"""Valeurs fixes, omission explicite, pureté et indépendance des objets fictifs."""

import builtins
import json
import os
import random
import socket
import subprocess
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any, cast

import pytest

from forge_design.contracts import ViewContract
from forge_design.preview import PreviewDataResult, generate_preview_data


def contract(context: dict[str, Any], **extra: Any) -> ViewContract:
    return ViewContract.model_validate(
        {
            "name": "contacts/list",
            "template": "mvc/views/contacts/list.html",
            "context": context,
            **extra,
        }
    )


@pytest.mark.parametrize(
    "kind,value",
    [
        ("string", "Exemple"),
        ("boolean", True),
        ("integer", 42),
        ("number", 12.5),
        ("object", {}),
        ("list", [dict[str, object](), dict[str, object](), dict[str, object]()]),
    ],
)
def test_top_level(kind: str, value: object) -> None:
    result = generate_preview_data(contract({"x": {"type": kind}}))
    assert result == PreviewDataResult({"x": value}, (), True)
    assert type(result.data["x"]) is type(value)
    assert json.loads(json.dumps(result.data, allow_nan=False)) == result.data


@pytest.mark.parametrize("kind", ["object", "list"])
@pytest.mark.parametrize(
    "field_type,value",
    [
        ("string", "Exemple"),
        ("boolean", True),
        ("integer", 42),
        ("number", 12.5),
        ("email", "contact@example.test"),
        ("date", "2026-05-16"),
        ("object", {}),
        ("list", []),
    ],
)
def test_field_types(kind: str, field_type: str, value: object) -> None:
    result = generate_preview_data(
        contract({"x": {"type": kind, "fields": {"field": field_type}}})
    )
    assert result.complete and result.issues == ()
    expected = {"field": value}
    assert result.data["x"] == (
        [expected, expected, expected] if kind == "list" else expected
    )
    obj = cast(
        dict[str, object],
        cast(list[object], result.data["x"])[0] if kind == "list" else result.data["x"],
    )
    assert type(obj["field"]) is type(value)


@pytest.mark.parametrize("fields", [None, {}])
@pytest.mark.parametrize("kind", ["object", "list"])
def test_missing_and_empty_fields(kind: str, fields: dict[str, str] | None) -> None:
    result = generate_preview_data(
        contract(
            {"x": {"type": kind, **({} if fields is None else {"fields": fields})}}
        )
    )
    assert result.complete and result.issues == ()
    assert result.data["x"] == ([{}, {}, {}] if kind == "list" else {})


def test_empty_context() -> None:
    assert generate_preview_data(contract({})) == PreviewDataResult({}, (), True)


def test_roadmap_and_metadata_ignored() -> None:
    context: dict[str, Any] = {
        "page_title": {"type": "string"},
        "contacts": {
            "type": "list",
            "fields": {"nom": "string", "email": "email", "telephone": "string"},
        },
        "can_create": {"type": "boolean"},
    }
    c = contract(context)
    result = generate_preview_data(c)
    row = {"nom": "Exemple", "email": "contact@example.test", "telephone": "Exemple"}
    assert result.data == {
        "page_title": "Exemple",
        "contacts": [row, row, row],
        "can_create": True,
    }
    assert list(result.data) == list(context)
    assert result.complete
    for variable in context.values():
        variable["entity"] = "Missing"
        variable["label"] = "Autre étiquette"
    changed = contract(
        context,
        actions={
            "create": {"method": "GET", "path": "/missing"},
            "delete": {"method": "POST", "path": "/"},
        },
    )
    assert generate_preview_data(changed) == result


@pytest.mark.parametrize("kind", ["object", "list"])
def test_unknown_fields_once_in_order(kind: str) -> None:
    fields = {
        "z": "money",
        "ok": "string",
        "uuid": "uuid",
        "custom": "custom",
        "日本語": "未定義",
        "case": "String",
        "space": " email ",
    }
    result = generate_preview_data(
        contract({"nom_prénom": {"type": kind, "fields": fields}})
    )
    assert not result.complete
    assert result.data["nom_prénom"] == (
        [{"ok": "Exemple"}] * 3 if kind == "list" else {"ok": "Exemple"}
    )
    assert [i.location for i in result.issues] == [
        ("context", "nom_prénom", "fields", k) for k in fields if k != "ok"
    ]
    assert all(i.code == "preview.unsupported_field_type" for i in result.issues)


def test_unicode_order_and_all_unknown_parent_preserved() -> None:
    c = contract(
        {
            "日本語": {
                "type": "object",
                "fields": {
                    "z": "string",
                    "étiquette": "email",
                    "e\u0301": "date",
                    "a": "boolean",
                },
            },
            "nom_prénom": {"type": "list", "fields": {"x": "unknown"}},
        }
    )
    result = generate_preview_data(c)
    assert list(result.data) == ["日本語", "nom_prénom"]
    assert list(cast(dict[str, object], result.data["日本語"])) == [
        "z",
        "étiquette",
        "e\u0301",
        "a",
    ]
    assert result.data["nom_prénom"] == [{}, {}, {}]


def test_independent_containers_and_calls() -> None:
    c = contract(
        {
            "a": {"type": "list", "fields": {"obj": "object", "items": "list"}},
            "b": {"type": "object"},
            "c": {"type": "object"},
        }
    )
    first = generate_preview_data(c)
    second = generate_preview_data(c)
    rows = cast(list[dict[str, Any]], first.data["a"])
    assert (
        rows[0] == rows[1] == rows[2]
        and rows[0] is not rows[1]
        and rows[1] is not rows[2]
    )
    assert rows[0]["obj"] is not rows[1]["obj"]
    assert rows[0]["items"] is not rows[1]["items"]
    assert first.data["b"] is not first.data["c"]
    rows[0]["obj"]["changed"] = True
    rows[0]["items"].append("changed")
    assert rows[1] == rows[2] == {"obj": {}, "items": []}
    assert second == generate_preview_data(c)
    assert cast(list[dict[str, Any]], second.data["a"])[0] == {"obj": {}, "items": []}


def test_scalar_fields_ignored() -> None:
    result = generate_preview_data(
        contract({"x": {"type": "string", "fields": {"unrelated": "unknown"}}})
    )
    assert result == PreviewDataResult({"x": "Exemple"}, (), True)


def test_purity_nonmutation_determinism_and_frozen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    c = contract(
        {"contacts": {"type": "list", "fields": {"date": "date", "x": "unknown"}}},
        actions={"create": {"method": "GET", "path": "/"}},
    )
    before = c.model_dump(exclude_unset=True)
    refs = c.context, c.context["contacts"], c.context["contacts"].fields, c.actions

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("unexpected effect")

    with monkeypatch.context() as p:
        p.setattr(builtins, "open", forbidden)
        for name in ("open", "stat", "listdir", "scandir"):
            p.setattr(os, name, forbidden)
        for name in ("open", "read_text", "read_bytes"):
            p.setattr(Path, name, forbidden)
        p.setattr(socket, "socket", forbidden)
        p.setattr(subprocess, "run", forbidden)
        p.setattr(subprocess, "Popen", forbidden)
        p.setattr(random, "random", forbidden)
        p.setattr(ViewContract, "model_dump", forbidden)
        result = generate_preview_data(c)
        assert result == generate_preview_data(c)
    assert before == c.model_dump(exclude_unset=True)
    after = c.context, c.context["contacts"], c.context["contacts"].fields, c.actions
    assert all(a is b for a, b in zip(refs, after, strict=True))
    with pytest.raises(FrozenInstanceError):
        result.complete = True  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.issues[0].code = "changed"  # type: ignore[misc]
    result.data["mutable"] = True
    assert result.data["mutable"] is True
