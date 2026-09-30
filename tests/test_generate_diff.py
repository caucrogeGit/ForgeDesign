"""Diff textuel pur : métriques sémantiques, fins de ligne et budget."""

import builtins
import os
import socket
import subprocess
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest

from forge_design.generate import (
    TemplateDiffIssue,
    TemplateDiffResult,
    build_template_diff,
    diff,
)

TARGET = "mvc/views/contacts/list.html"
ORIGIN = "contacts/list.design.json"


def compare(current: str, generated: str) -> TemplateDiffResult:
    return build_template_diff(
        target=TARGET, origin=ORIGIN, current=current, generated=generated
    )


@pytest.mark.parametrize("text", ["", "same", "same\n", "é\r\n日本語\n😀"])
def test_identical(text: str) -> None:
    result = compare(text, text)
    assert result == TemplateDiffResult(
        TARGET, ORIGIN, text, text, "", False, 0, 0, 0, (), True
    )


@pytest.mark.parametrize(
    "current,generated,expected",
    [
        ("a\n", "a\nb\n", (1, 0, 0)),
        ("a\nb\n", "a\n", (0, 1, 0)),
        ("old\n", "new\n", (0, 0, 1)),
        ("old\n", "new1\nnew2\nnew3\n", (2, 0, 1)),
        ("old1\nold2\nold3\n", "new\n", (0, 2, 1)),
        ("", "a\nb\n", (2, 0, 0)),
        ("a\nb\n", "", (0, 2, 0)),
        ("\n", "", (0, 1, 0)),
        ("", "\n", (1, 0, 0)),
    ],
)
def test_metrics(current: str, generated: str, expected: tuple[int, int, int]) -> None:
    result = compare(current, generated)
    assert result.changed and result.complete and result.issues == ()
    assert (result.added_lines, result.removed_lines, result.modified_lines) == expected
    assert result.current == current and result.generated == generated


def test_exact_unified_diff() -> None:
    result = compare(
        "<section>\n  <h1>Contacts</h1>\n</section>\n",
        "<section>\n  <h1>{{ page_title }}</h1>\n</section>\n",
    )
    assert result.unified_diff == (
        "--- mvc/views/contacts/list.html\n"
        "+++ mvc/views/contacts/list.html.generated\n"
        "@@ -1,3 +1,3 @@\n"
        " <section>\n"
        "-  <h1>Contacts</h1>\n"
        "+  <h1>{{ page_title }}</h1>\n"
        " </section>\n"
    )
    assert result.origin == ORIGIN and ORIGIN not in result.unified_diff


def test_independent_edits() -> None:
    result = compare(
        "delete\na\nb\nc\nd\ne\nf\nold\ng\nh\ni\nj\nk\nl\n",
        "a\nb\nc\nd\ne\nf\nnew\ng\nh\ni\nj\nk\nl\ninsert\n",
    )
    assert (result.added_lines, result.removed_lines, result.modified_lines) == (
        1,
        1,
        1,
    )
    independent = compare("delete\na\nb\nc\n", "a\nb\nc\ninsert\n")
    assert (
        independent.added_lines,
        independent.removed_lines,
        independent.modified_lines,
    ) == (1, 1, 0)


@pytest.mark.parametrize(
    "current,generated,body",
    [
        ("a", "a\n", "-a\n\\ No newline at end of file\n+a\n"),
        ("a\n", "a", "-a\n+a\n\\ No newline at end of file\n"),
        (
            "a",
            "b",
            "-a\n\\ No newline at end of file\n+b\n\\ No newline at end of file\n",
        ),
    ],
)
def test_final_lf(current: str, generated: str, body: str) -> None:
    result = compare(current, generated)
    assert result.unified_diff.endswith(body)
    assert result.current == current and result.generated == generated
    assert result.changed
    assert result.modified_lines == (
        0 if current.rstrip("\n") == generated.rstrip("\n") else 1
    )


@pytest.mark.parametrize(
    "old,new", [("a\r\n", "a\n"), ("a\r", "a\n"), ("a\r\nb", "a\r\nc")]
)
def test_line_separators(old: str, new: str) -> None:
    result = compare(old, new)
    assert result.current == old and result.generated == new
    assert result.changed and result.unified_diff
    if old.splitlines() == new.splitlines():
        assert (result.added_lines, result.removed_lines, result.modified_lines) == (
            0,
            0,
            0,
        )
    assert "\r" in result.unified_diff


def test_unicode_hostile_and_header_like_content() -> None:
    text = 'é 日本語 😀 <script> {% include "evil" %} {{ x }} \x1b[31m\n'
    result = compare("", text)
    assert "+" + text in result.unified_diff and result.added_lines == 1
    assert "&lt;" not in result.unified_diff
    result = compare("--- old\n", "+++ new\n")
    assert (
        result.modified_lines == 1 and result.added_lines == result.removed_lines == 0
    )
    assert "---- old\n++++ new\n" in result.unified_diff


@pytest.mark.parametrize("field", ["target", "origin"])
@pytest.mark.parametrize("invalid", ["", None, 42, []])
def test_empty_metadata(field: str, invalid: Any) -> None:
    kwargs: dict[str, Any] = {
        "target": TARGET,
        "origin": ORIGIN,
        "current": "",
        "generated": "",
    }
    kwargs[field] = invalid
    with pytest.raises(ValueError):
        build_template_diff(**kwargs)


def test_descriptive_metadata_preserved() -> None:
    result = build_template_diff(
        target="../../etc/passwd",
        origin=" custom origin\n ",
        current="",
        generated="x\n",
    )
    assert result.target == "../../etc/passwd" and result.origin == " custom origin\n "
    assert result.unified_diff.startswith(
        "--- ../../etc/passwd\n+++ ../../etc/passwd.generated\n"
    )


def test_exact_limit_and_surplus(monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = compare("old", "new")
    monkeypatch.setattr(diff, "MAX_TEMPLATE_DIFF_CHARS", len(baseline.unified_diff))
    assert compare("old", "new") == baseline
    monkeypatch.setattr(diff, "MAX_TEMPLATE_DIFF_CHARS", len(baseline.unified_diff) - 1)
    result = compare("old", "new")
    assert result.unified_diff == "" and not result.complete and result.changed
    assert (
        result.modified_lines == 1
        and result.current == "old"
        and result.generated == "new"
    )
    assert result.issues[0].code == "diff.output_too_large"


def test_large_diff_and_identical_short_circuit() -> None:
    text = "x" * 1_000_001
    assert compare(text, text).complete
    result = compare("", text)
    assert not result.complete and result.added_lines == 1 and result.unified_diff == ""


def test_purity_determinism_and_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("external access")

    with monkeypatch.context() as patch:
        for owner, name in (
            (builtins, "open"),
            (os, "open"),
            (os, "replace"),
            (Path, "open"),
            (Path, "read_text"),
            (Path, "write_text"),
            (Path, "exists"),
            (Path, "stat"),
            (Path, "resolve"),
            (Path, "absolute"),
            (socket, "socket"),
            (subprocess, "run"),
        ):
            patch.setattr(owner, name, forbidden)
        result = compare("old\n", "new\n")
        assert result == compare("old\n", "new\n")
    with pytest.raises(FrozenInstanceError):
        result.complete = False  # type: ignore[misc]
    issue = TemplateDiffIssue("diff.output_too_large", "message")
    with pytest.raises(FrozenInstanceError):
        issue.code = "changed"  # type: ignore[misc]
