"""Tokens de classes opaques : ajout, retrait, remplacement, doublons, ordre."""

from typing import Any

import pytest

from forge_design.web import tailwind_classes
from forge_design.web.tailwind_classes import (
    SUGGESTIONS,
    ClassNotEditableError,
    add_class,
    current_classes,
    parse_class_tokens,
    remove_class,
    set_classes,
    validate_class_token,
)

FREE = (
    "w-[37px]",
    "md:grid-cols-2",
    "hover:bg-slate-100",
    "[mask-type:luminance]",
    "w-[calc(100%-2rem)]",
    "md:hover:bg-red-500",
    "dark:text-white",
    "!font-bold",
    "group-hover:underline",
)


@pytest.mark.parametrize(
    ("value", "tokens"),
    [
        ("mx-auto py-8 text-xl", ("mx-auto", "py-8", "text-xl")),
        ("mx-auto   py-8", ("mx-auto", "py-8")),
        ("  mx-auto\tpy-8\n text-xl\r\n", ("mx-auto", "py-8", "text-xl")),
        ("", ()),
        ("   ", ()),
        ("mx-auto mx-auto", ("mx-auto", "mx-auto")),
        (" ".join(FREE), FREE),
        # Blanc Unicode non ASCII : reste dans le token, aucune interprétation.
        ("a b c", ("a b", "c")),
    ],
)
def test_parse(value: str, tokens: tuple[str, ...]) -> None:
    assert parse_class_tokens(value) == tokens


def test_parse_refuses_nul() -> None:
    with pytest.raises(ValueError):
        parse_class_tokens("a\x00b")


@pytest.mark.parametrize("token", FREE)
def test_free_tokens_accepted(token: str) -> None:
    assert validate_class_token(token) == token
    assert add_class(None, token) == {"class": token}


@pytest.mark.parametrize(
    "token", ["", " ", "a b", "a\tb", "a\nb", "a\rb", "a\x00b", " a", "a "]
)
def test_invalid_tokens(token: str) -> None:
    with pytest.raises(ValueError):
        validate_class_token(token)
    with pytest.raises(ValueError):
        add_class({"class": "x"}, token)
    with pytest.raises(ValueError):
        remove_class({"class": "x"}, token)


def test_add_appends_and_keeps_other_props() -> None:
    props = {"class": "mx-auto py-8", "tag": "section", "data-test": "hero"}
    result = add_class(props, "max-w-5xl")
    assert result == {
        "class": "mx-auto py-8 max-w-5xl",
        "tag": "section",
        "data-test": "hero",
    }
    assert list(result or {}) == ["class", "tag", "data-test"]
    assert props["class"] == "mx-auto py-8"  # entrée non mutée


def test_add_new_class_key_goes_last() -> None:
    assert list(add_class({"tag": "section"}, "flex") or {}) == ["tag", "class"]


def test_add_existing_is_noop_identity() -> None:
    props = {"class": "mx-auto py-8"}
    assert add_class(props, "py-8") is props


def test_add_keeps_order_and_history_duplicates() -> None:
    assert add_class({"class": "py-8 mx-auto"}, "text-xl") == {
        "class": "py-8 mx-auto text-xl"
    }
    assert add_class({"class": "mx-auto mx-auto py-8"}, "text-xl") == {
        "class": "mx-auto mx-auto py-8 text-xl"
    }


def test_remove_all_exact_occurrences() -> None:
    props = {"class": "mx-auto py-8 mx-auto mx-auto-x", "tag": "div"}
    assert remove_class(props, "mx-auto") == {"class": "py-8 mx-auto-x", "tag": "div"}


def test_remove_absent_is_noop_identity() -> None:
    props = {"class": "py-8"}
    assert remove_class(props, "mx-auto") is props
    assert remove_class(None, "mx-auto") is None


def test_remove_last_class_keeps_mapping() -> None:
    assert remove_class({"class": "py-8"}, "py-8") == {}
    assert remove_class({"class": "py-8", "tag": "p"}, "py-8") == {"tag": "p"}


def test_set_replaces_and_canonicalizes() -> None:
    props = {"tag": "section", "class": "old", "data-x": 1}
    result = set_classes(props, "  b\ta   c  ")
    assert result == {"tag": "section", "class": "b a c", "data-x": 1}
    assert list(result or {}) == ["tag", "class", "data-x"]


def test_set_same_canonical_is_noop_identity() -> None:
    props = {"class": "a  b"}
    assert set_classes(props, "a b") is props
    assert set_classes(props, " a\tb ") is props
    assert set_classes(None, "") is None
    assert set_classes({"tag": "p"}, "   ") == {"tag": "p"}


def test_set_empty_removes_class_only() -> None:
    assert set_classes({"class": "a", "tag": "p"}, "") == {"tag": "p"}
    assert set_classes({"class": "a"}, "") == {}


def test_set_keeps_duplicates_and_order() -> None:
    assert set_classes(None, "b a b") == {"class": "b a b"}


@pytest.mark.parametrize("value", [True, 1, 1.5])
def test_non_string_class_not_editable(value: Any) -> None:
    props = {"class": value, "tag": "p"}
    with pytest.raises(ClassNotEditableError):
        current_classes(props)
    for operation in (
        lambda: add_class(props, "x"),
        lambda: remove_class(props, "x"),
        lambda: set_classes(props, "x"),
    ):
        with pytest.raises(ClassNotEditableError):
            operation()
    assert props == {"class": value, "tag": "p"}


def test_current_classes() -> None:
    assert current_classes(None) is None
    assert current_classes({}) is None
    assert current_classes({"class": "a  b"}) == "a  b"


def test_suggestions_short_and_valid() -> None:
    tokens = [token for _, items in SUGGESTIONS for token in items]
    assert 20 <= len(tokens) <= 80 and len(set(tokens)) == len(tokens)
    assert all(validate_class_token(token) == token for token in tokens)
    assert {"mx-auto", "max-w-5xl", "text-xl", "py-8"} <= set(tokens)


def test_pure_module() -> None:
    names = set(vars(tailwind_classes))
    assert not names & {"os", "open", "Path", "write_design", "read_design"}
