"""Matrice des choix, sélection validée, pureté et absence de choix implicite."""

import builtins
import copy
import os
import socket
import subprocess
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest
from test_templates import make_views

import forge_design.safewrite as safewrite
from forge_design.safewrite import (
    SafeWriteDecision,
    SafeWriteDecisionOptions,
    TemplateChangeResult,
    TemplateRevision,
    TemplateSnapshot,
    decision_options,
    detect_template_change,
    detection,
    has_write_conflict,
    select_safe_write_choice,
    snapshot_template,
)
from forge_design.safewrite import decision as decision_module

PATH = "mvc/views/contacts/list.html"
REVISION = TemplateRevision(3, 10, "a" * 64, 1, 2, 20)
OTHER = TemplateRevision(4, 11, "b" * 64, 1, 3, 21)
PRESENT = TemplateSnapshot(PATH, True, REVISION)
ABSENT = TemplateSnapshot(PATH, False, None)

CHANGES = {
    "unchanged": TemplateChangeResult(PATH, "unchanged", PRESENT, PRESENT),
    "modified": TemplateChangeResult(
        PATH, "modified", PRESENT, TemplateSnapshot(PATH, True, OTHER)
    ),
    "created": TemplateChangeResult(PATH, "created", ABSENT, PRESENT),
    "deleted": TemplateChangeResult(PATH, "deleted", PRESENT, ABSENT),
}
CONFLICTS = ("modified", "created", "deleted")
CONFLICT_CHOICES = ("cancel", "regenerate", "save_as", "mark_manual")


# Matrice.


def test_unchanged_options() -> None:
    assert decision_options(CHANGES["unchanged"]) == SafeWriteDecisionOptions(
        PATH, "unchanged", ("proceed", "cancel")
    )


@pytest.mark.parametrize("status", CONFLICTS)
def test_conflict_options(status: str) -> None:
    options = decision_options(CHANGES[status])
    assert options == SafeWriteDecisionOptions(PATH, status, CONFLICT_CHOICES)  # type: ignore[arg-type]
    assert "proceed" not in options.choices


@pytest.mark.parametrize(
    ("status", "conflict"),
    [("unchanged", False), ("modified", True), ("created", True), ("deleted", True)],
)
def test_has_write_conflict(status: str, conflict: bool) -> None:
    assert has_write_conflict(CHANGES[status]) is conflict


def test_no_destructive_vocabulary() -> None:
    every = {c for change in CHANGES.values() for c in decision_options(change).choices}
    assert every == {"proceed", "cancel", "regenerate", "save_as", "mark_manual"}


# Sélection.


@pytest.mark.parametrize("choice", ["proceed", "cancel"])
def test_unchanged_selection(choice: Any) -> None:
    assert select_safe_write_choice(CHANGES["unchanged"], choice) == (
        SafeWriteDecision(PATH, "unchanged", choice)
    )


@pytest.mark.parametrize("choice", CONFLICT_CHOICES)
@pytest.mark.parametrize("status", CONFLICTS)
def test_conflict_selection(status: str, choice: Any) -> None:
    decision = select_safe_write_choice(CHANGES[status], choice)
    assert decision == SafeWriteDecision(PATH, status, choice)  # type: ignore[arg-type]


@pytest.mark.parametrize("status", CONFLICTS)
def test_proceed_refused_on_conflict(status: str) -> None:
    with pytest.raises(ValueError):
        select_safe_write_choice(CHANGES[status], "proceed")


@pytest.mark.parametrize("choice", ["regenerate", "save_as", "mark_manual"])
def test_conflict_choices_refused_when_unchanged(choice: Any) -> None:
    with pytest.raises(ValueError):
        select_safe_write_choice(CHANGES["unchanged"], choice)


@pytest.mark.parametrize(
    "choice",
    [
        "overwrite",
        "yes",
        "force",
        "continue",
        "ignore_conflict",
        "replace_anyway",
        "",
        "PROCEED",
        " proceed",
        None,
        0,
        ("proceed",),
        b"proceed",
    ],
)
@pytest.mark.parametrize("status", ["unchanged", *CONFLICTS])
def test_unknown_choice_refused(status: str, choice: Any) -> None:
    with pytest.raises(ValueError):
        select_safe_write_choice(CHANGES[status], choice)


@pytest.mark.parametrize("status", ["conflicted", "dirty", "stale", "", None])
def test_unknown_status_refused(status: Any) -> None:
    change = TemplateChangeResult(PATH, status, PRESENT, PRESENT)
    for function in (has_write_conflict, decision_options):
        with pytest.raises(ValueError):
            function(change)
    with pytest.raises(ValueError):
        select_safe_write_choice(change, "cancel")


def test_decision_carries_no_extra_state() -> None:
    fields = set(SafeWriteDecision.__dataclass_fields__)
    assert fields == {"path", "status", "choice"}
    assert set(SafeWriteDecisionOptions.__dataclass_fields__) == {
        "path",
        "status",
        "choices",
    }


# Gel, déterminisme, non-mutation.


def test_frozen() -> None:
    options = decision_options(CHANGES["unchanged"])
    decision = select_safe_write_choice(CHANGES["unchanged"], "cancel")
    with pytest.raises(FrozenInstanceError):
        options.choices = ("proceed",)  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        decision.choice = "proceed"  # type: ignore[misc]
    assert isinstance(options.choices, tuple)


@pytest.mark.parametrize("status", ["unchanged", *CONFLICTS])
def test_deterministic_and_non_mutating(status: str) -> None:
    change = CHANGES[status]
    before = copy.deepcopy(change)
    choice = decision_options(change).choices[0]
    results = {
        (decision_options(change), select_safe_write_choice(change, choice))
        for _ in range(10)
    }
    assert len(results) == 1
    assert change == before
    assert change.expected == before.expected and change.current == before.current


# Pureté : aucun filesystem, réseau, processus ni détection secondaire.


def test_pure(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("effet de bord interdit")

    for target, name in (
        (builtins, "open"),
        (os, "open"),
        (os, "stat"),
        (Path, "read_text"),
        (Path, "write_text"),
        (Path, "read_bytes"),
        (Path, "write_bytes"),
        (socket, "socket"),
        (subprocess, "Popen"),
        (detection, "snapshot_template"),
        (detection, "detect_template_change"),
        (safewrite, "snapshot_template"),
        (safewrite, "detect_template_change"),
    ):
        monkeypatch.setattr(target, name, forbidden)
    for status, change in CHANGES.items():
        has_write_conflict(change)
        options = decision_options(change)
        for choice in options.choices:
            select_safe_write_choice(change, choice)
        assert status == options.status


def test_decision_module_does_not_know_io_diff_or_history() -> None:
    names = set(vars(decision_module))
    assert not names & {
        "snapshot_template",
        "detect_template_change",
        "build_template_diff",
        "append_generation_history",
        "os",
        "Path",
    }


# Bout en bout avec la détection réelle : aucune écriture.


def test_with_real_detection(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    target = views / "contacts/list.html"
    target.parent.mkdir()
    target.write_bytes(b"<ul></ul>\n")
    expected = snapshot_template(root, PATH)
    change = detect_template_change(root, expected)
    assert decision_options(change).choices == ("proceed", "cancel")
    assert select_safe_write_choice(change, "proceed").choice == "proceed"

    target.write_bytes(b"<ul>edited</ul>\n")
    state = target.read_bytes(), target.stat().st_mtime_ns
    change = detect_template_change(root, expected)
    assert decision_options(change).choices == CONFLICT_CHOICES
    with pytest.raises(ValueError):
        select_safe_write_choice(change, "proceed")
    for choice in CONFLICT_CHOICES:
        select_safe_write_choice(change, choice)
    assert (target.read_bytes(), target.stat().st_mtime_ns) == state
    assert not (root / ".forge-design").exists()


def test_exports() -> None:
    for name in (
        "SafeWriteChoice",
        "SafeWriteDecisionOptions",
        "SafeWriteDecision",
        "decision_options",
        "select_safe_write_choice",
        "has_write_conflict",
    ):
        assert name in safewrite.__all__ and hasattr(safewrite, name)


def test_decision_stores_canonical_choice() -> None:
    class Sneaky(str):
        pass

    decision = select_safe_write_choice(CHANGES["unchanged"], Sneaky("cancel"))  # type: ignore[arg-type]
    assert type(decision.choice) is str and decision.choice == "cancel"
