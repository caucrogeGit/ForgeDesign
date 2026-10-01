"""Écriture contrôlée réelle : revalidations, publication, journal, échecs."""

import copy
import errno
import hashlib
import os
import stat
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from test_templates import make_views

from forge_design.app import create_tool_registry
from forge_design.limits import MAX_SOURCE_BYTES
from forge_design.safewrite import (
    SafeWriteDecision,
    TemplateChangeResult,
    TemplateHistoryError,
    TemplatePublication,
    TemplatePublishedError,
    TemplateRevision,
    TemplateSnapshot,
    TemplateWriteConflictError,
    TemplateWriteError,
    TemplateWriteResult,
    detect_template_change,
    select_safe_write_choice,
    snapshot_template,
    write_generated_template,
    writer,
)

PATH = "mvc/views/contacts/list.html"
STAMP = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
GENERATED = "<ul>\n  {% for c in contacts %}<li>{{ c }}</li>{% endfor %}\n</ul>\n"
LINE = (
    '{"version":1,"timestamp":"2026-10-01T12:00:00Z",'
    '"action":"generate_template","file":"mvc/views/contacts/list.html"}\n'
)


def project(tmp_path: Path, content: bytes | None = b"<p>old</p>\n") -> Path:
    root, views = make_views(tmp_path)
    (views / "contacts").mkdir()
    if content is not None:
        (root / PATH).write_bytes(content)
    return root


def approve(root: Path) -> tuple[TemplateChangeResult, SafeWriteDecision]:
    change = detect_template_change(root, snapshot_template(root, PATH))
    return change, select_safe_write_choice(change, "proceed")


def write(root: Path, generated: Any = GENERATED, **kwargs: Any) -> TemplateWriteResult:
    change, decision = approve(root)
    return write_generated_template(
        root,
        generated=generated,
        change=kwargs.pop("change", change),
        decision=kwargs.pop("decision", decision),
        timestamp=kwargs.pop("timestamp", STAMP),
    )


def history(root: Path) -> Path:
    return root / ".forge-design/history.jsonl"


def temps(root: Path) -> list[Path]:
    return list((root / "mvc/views/contacts").glob(".forge-design-write-*"))


def state(root: Path) -> tuple[bytes | None, int | None]:
    target = root / PATH
    if not target.exists():
        return None, None
    return target.read_bytes(), target.stat().st_ino


def assert_untouched(root: Path, before: tuple[bytes | None, int | None]) -> None:
    assert state(root) == before
    assert not history(root).exists()
    assert temps(root) == []


def fd_path(fd: int) -> str:
    try:
        return os.readlink(f"/proc/self/fd/{fd}")
    except OSError:
        return ""


def is_temp_fd(fd: int) -> bool:
    return ".forge-design-write-" in fd_path(fd)


# Nominal.


def test_create_nominal(tmp_path: Path) -> None:
    root = project(tmp_path, None)
    result = write(root)
    data = GENERATED.encode()
    target = root / PATH
    assert target.read_bytes() == data
    publication = result.publication
    assert publication.created and publication.path == PATH
    assert publication.size == len(data)
    assert publication.revision.digest == hashlib.sha256(data).hexdigest()
    assert publication.revision.inode == target.stat().st_ino
    assert publication.modified_ns == target.stat().st_mtime_ns
    umask = os.umask(0)
    os.umask(umask)
    assert stat.S_IMODE(target.stat().st_mode) == 0o666 & ~umask
    assert history(root).read_text(encoding="utf-8") == LINE
    assert result.history_event.file == PATH
    assert result.history_event.timestamp == "2026-10-01T12:00:00Z"
    assert temps(root) == []


def test_update_nominal_keeps_mode(tmp_path: Path) -> None:
    root = project(tmp_path)
    (root / PATH).chmod(0o640)
    old_inode = (root / PATH).stat().st_ino
    result = write(root)
    assert (root / PATH).read_bytes() == GENERATED.encode()
    assert not result.publication.created
    assert stat.S_IMODE((root / PATH).stat().st_mode) == 0o640
    assert (root / PATH).stat().st_ino != old_inode
    assert history(root).read_text(encoding="utf-8") == LINE
    assert temps(root) == []


def test_history_appends_to_existing(tmp_path: Path) -> None:
    root = project(tmp_path)
    write(root)
    write(root, timestamp=STAMP + timedelta(hours=1))
    lines = history(root).read_text(encoding="utf-8").splitlines(keepends=True)
    assert lines[0] == LINE
    assert '"timestamp":"2026-10-01T13:00:00Z"' in lines[1]
    assert len(lines) == 2


def test_timestamp_converted_and_default(tmp_path: Path) -> None:
    root = project(tmp_path)
    paris = datetime(2026, 10, 1, 14, 0, tzinfo=timezone(timedelta(hours=2)))
    assert write(root, timestamp=paris).history_event.timestamp == (
        "2026-10-01T12:00:00Z"
    )
    event = write(root, timestamp=None).history_event
    assert event.timestamp.endswith("Z")


@pytest.mark.parametrize(
    "generated",
    [
        "é 日本語 🙂\n",
        "no trailing newline",
        "crlf\r\nkept\r\n",
        "  spaces kept  \n\n",
        "nul\x00inside",
        "",
        "﻿BOM fourni par l'appelant",
    ],
)
def test_exact_bytes(tmp_path: Path, generated: str) -> None:
    root = project(tmp_path)
    write(root, generated)
    assert (root / PATH).read_bytes() == generated.encode("utf-8")


def test_symlinked_root_journal_written(tmp_path: Path) -> None:
    root = project(tmp_path)
    link = tmp_path / "link"
    link.symlink_to(root, target_is_directory=True)
    change, decision = approve(link)
    write_generated_template(
        link, generated=GENERATED, change=change, decision=decision, timestamp=STAMP
    )
    assert history(root).read_text(encoding="utf-8") == LINE


# Validation pure, avant toute I/O.


@pytest.fixture
def no_io(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("I/O avant validation")

    for name in ("detect_template_change", "snapshot_template", "open_directory"):
        monkeypatch.setattr(writer, name, forbidden)
    monkeypatch.setattr(writer, "append_generation_history", forbidden)


REV = TemplateRevision(3, 10, "a" * 64, 1, 2, 20)
PRESENT = TemplateSnapshot(PATH, True, REV)
ABSENT = TemplateSnapshot(PATH, False, None)
OTHER = TemplateSnapshot(PATH, True, TemplateRevision(3, 10, "b" * 64, 1, 2, 20))
ELSEWHERE = TemplateSnapshot("mvc/views/x.html", True, REV)
UNCHANGED = TemplateChangeResult(PATH, "unchanged", PRESENT, PRESENT)
PROCEED = SafeWriteDecision(PATH, "unchanged", "proceed")


def call(change: Any = UNCHANGED, decision: Any = PROCEED, **kwargs: Any) -> Any:
    return write_generated_template(
        Path("/nonexistent"),
        generated=kwargs.pop("generated", GENERATED),
        change=change,
        decision=decision,
        timestamp=kwargs.pop("timestamp", STAMP),
    )


@pytest.mark.usefixtures("no_io")
@pytest.mark.parametrize("choice", ["cancel", "regenerate", "save_as", "mark_manual"])
def test_non_proceed_refused(choice: Any) -> None:
    with pytest.raises(ValueError, match="proceed"):
        call(decision=SafeWriteDecision(PATH, "unchanged", choice))


@pytest.mark.usefixtures("no_io")
@pytest.mark.parametrize(
    "change",
    [
        TemplateChangeResult(PATH, "modified", PRESENT, OTHER),
        TemplateChangeResult(PATH, "created", ABSENT, PRESENT),
        TemplateChangeResult(PATH, "deleted", PRESENT, ABSENT),
    ],
)
def test_conflict_with_forged_proceed(change: TemplateChangeResult) -> None:
    with pytest.raises(ValueError):
        call(change, SafeWriteDecision(PATH, change.status, "proceed"))


@pytest.mark.usefixtures("no_io")
@pytest.mark.parametrize(
    ("change", "decision"),
    [
        (UNCHANGED, SafeWriteDecision("mvc/views/other.html", "unchanged", "proceed")),
        (UNCHANGED, SafeWriteDecision(PATH, "modified", "proceed")),
        (
            TemplateChangeResult(
                PATH,
                "unchanged",
                TemplateSnapshot("mvc/views/x.html", True, REV),
                PRESENT,
            ),
            PROCEED,
        ),
        (
            TemplateChangeResult(
                PATH,
                "unchanged",
                PRESENT,
                TemplateSnapshot("mvc/views/x.html", True, REV),
            ),
            PROCEED,
        ),
        (TemplateChangeResult(PATH, "unchanged", PRESENT, OTHER), PROCEED),
        (TemplateChangeResult(PATH, "unchanged", ABSENT, PRESENT), PROCEED),
        (TemplateChangeResult(PATH, "unchanged", PRESENT, ABSENT), PROCEED),
        (object(), PROCEED),
        (UNCHANGED, object()),
    ],
)
def test_inconsistent_inputs(change: Any, decision: Any) -> None:
    with pytest.raises(ValueError):
        call(change, decision)


@pytest.mark.usefixtures("no_io")
@pytest.mark.parametrize("generated", [b"bytes", None, 12, ["x"], "\ud800 surrogate"])
def test_generated_type_and_encoding(generated: Any) -> None:
    with pytest.raises(ValueError):
        call(generated=generated)


@pytest.mark.usefixtures("no_io")
@pytest.mark.parametrize("timestamp", [datetime(2026, 10, 1, 12, 0), "2026", 0])
def test_bad_timestamp_refused_before_publication(timestamp: Any) -> None:
    with pytest.raises(ValueError):
        call(timestamp=timestamp)


@pytest.mark.usefixtures("no_io")
@pytest.mark.parametrize("path", ["mvc/views/a\tb.html", "mvc/views/a\x7fb.html"])
def test_unjournalizable_path_refused_before_publication(path: str) -> None:
    snapshot = TemplateSnapshot(path, False, None)
    change = TemplateChangeResult(path, "unchanged", snapshot, snapshot)
    with pytest.raises(ValueError, match="journal"):
        call(change, SafeWriteDecision(path, "unchanged", "proceed"))


def test_str_subclass_encoded_as_plain_str(tmp_path: Path) -> None:
    class Sneaky(str):
        def encode(self, *args: Any, **kwargs: Any) -> bytes:  # type: ignore[override]
            return b"hijacked"

    root = project(tmp_path)
    write(root, Sneaky("réel"))
    assert (root / PATH).read_bytes() == "réel".encode()


def test_size_limit(tmp_path: Path) -> None:
    root = project(tmp_path)
    write(root, "é" * (MAX_SOURCE_BYTES // 2))
    assert len((root / PATH).read_bytes()) == MAX_SOURCE_BYTES
    before = state(root)
    lines = history(root).read_bytes()
    with pytest.raises(ValueError):
        write(root, "x" * (MAX_SOURCE_BYTES + 1))
    assert state(root) == before and history(root).read_bytes() == lines
    assert temps(root) == []


def test_inputs_not_mutated(tmp_path: Path) -> None:
    root = project(tmp_path)
    change, decision = approve(root)
    generated = GENERATED
    before = copy.deepcopy((change, decision, generated))
    write_generated_template(
        root, generated=generated, change=change, decision=decision, timestamp=STAMP
    )
    assert (change, decision, generated) == before


# Revalidation et conflits : rien publié, aucun journal.


def test_modified_before_first_revalidation(tmp_path: Path) -> None:
    root = project(tmp_path)
    change, decision = approve(root)
    (root / PATH).write_bytes(b"<p>external</p>\n")
    before = state(root)
    with pytest.raises(TemplateWriteConflictError):
        write_generated_template(
            root, generated=GENERATED, change=change, decision=decision
        )
    assert_untouched(root, before)


def test_created_before_first_revalidation(tmp_path: Path) -> None:
    root = project(tmp_path, None)
    change, decision = approve(root)
    (root / PATH).write_bytes(b"external")
    before = state(root)
    with pytest.raises(TemplateWriteConflictError):
        write_generated_template(
            root, generated=GENERATED, change=change, decision=decision
        )
    assert_untouched(root, before)


def test_same_bytes_replacement_refused(tmp_path: Path) -> None:
    root = project(tmp_path)
    change, decision = approve(root)
    keep = tmp_path / "keep"
    os.link(root / PATH, keep)
    replacement = root / "mvc/views/contacts/repl"
    replacement.write_bytes((root / PATH).read_bytes())
    os.replace(replacement, root / PATH)
    before = state(root)
    with pytest.raises(TemplateWriteConflictError):
        write_generated_template(
            root, generated=GENERATED, change=change, decision=decision
        )
    assert_untouched(root, before)


def mutate_after_first_check(
    monkeypatch: pytest.MonkeyPatch, mutation: Any, on_call: int = 1
) -> None:
    """Muter la cible après le n-ième contrôle in-dir réussi."""
    original = writer._check_current  # pyright: ignore[reportPrivateUsage]
    calls = 0

    def wrapped(*args: Any) -> None:
        nonlocal calls
        original(*args)
        calls += 1
        if calls == on_call:
            mutation()

    monkeypatch.setattr(writer, "_check_current", wrapped)


@pytest.mark.parametrize("mutation", ["content", "delete", "chmod"])
def test_changed_between_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    root = project(tmp_path)
    target = root / PATH

    def mutate() -> None:
        if mutation == "content":
            target.write_bytes(b"<p>concurrent</p>\n")
        elif mutation == "delete":
            target.unlink()
        else:
            # Souvent dans le même tick d'horloge : ctime inchangé.
            target.chmod(0o600)

    mutate_after_first_check(monkeypatch, mutate)
    with pytest.raises(TemplateWriteConflictError):
        write(root)
    assert not history(root).exists()
    assert temps(root) == []
    assert not target.exists() or target.read_bytes() != GENERATED.encode()


def test_created_between_checks_link_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path, None)
    target = root / PATH
    # Après le second contrôle : seul os.link peut encore refuser.
    mutate_after_first_check(
        monkeypatch, lambda: target.write_bytes(b"external"), on_call=2
    )
    with pytest.raises(TemplateWriteConflictError, match="apparue"):
        write(root)
    assert target.read_bytes() == b"external"
    assert not history(root).exists()
    assert temps(root) == []


@pytest.mark.parametrize("kind", ["symlink", "fifo", "directory", "parent_symlink"])
def test_unsafe_target_after_decision(tmp_path: Path, kind: str) -> None:
    root = project(tmp_path, None)
    change, decision = approve(root)
    target = root / PATH
    outside = tmp_path / "outside"
    outside.mkdir()
    if kind == "symlink":
        target.symlink_to(outside / "x.html")
    elif kind == "fifo":
        os.mkfifo(target)
    elif kind == "directory":
        target.mkdir()
    else:
        (root / "mvc/views/contacts").rmdir()
        (root / "mvc/views/contacts").symlink_to(outside, target_is_directory=True)
    with pytest.raises(TemplateWriteConflictError):
        write_generated_template(
            root, generated=GENERATED, change=change, decision=decision
        )
    assert list(outside.iterdir()) == []
    assert not history(root).exists()


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignore les permissions")
def test_permission_denied(tmp_path: Path) -> None:
    root = project(tmp_path)
    directory = root / "mvc/views/contacts"
    directory.chmod(0o555)
    try:
        before = state(root)
        with pytest.raises(TemplateWriteError) as error:
            write(root)
        assert not isinstance(error.value, TemplatePublishedError)
        assert state(root) == before and not history(root).exists()
    finally:
        directory.chmod(0o755)


# Temporaire et publication.


def test_temp_collision_left_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path)

    def fixed(nbytes: int) -> str:
        return "f" * 32

    monkeypatch.setattr(writer.secrets, "token_hex", fixed)
    collision = root / "mvc/views/contacts" / (".forge-design-write-" + "f" * 32)
    collision.write_bytes(b"not ours")
    before = state(root)
    with pytest.raises(TemplateWriteError) as error:
        write(root)
    assert not isinstance(error.value, TemplatePublishedError)
    assert collision.read_bytes() == b"not ours"
    assert state(root) == before and not history(root).exists()


def test_temp_replaced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project(tmp_path)
    original = writer._fill_temp  # pyright: ignore[reportPrivateUsage]

    def raced(*args: Any) -> os.stat_result:
        prepared = original(*args)
        (temp,) = temps(root)
        replacement = temp.with_name("other")
        replacement.write_bytes(b"swapped")
        os.replace(replacement, temp)
        return prepared

    monkeypatch.setattr(writer, "_fill_temp", raced)
    before = state(root)
    with pytest.raises(TemplateWriteError, match="Temporaire"):
        write(root)
    assert_untouched(root, before)


def test_short_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project(tmp_path)
    original = os.write
    sizes: list[int] = []

    def partial(fd: int, data: Any) -> int:
        if is_temp_fd(fd):
            sizes.append(original(fd, bytes(data[:7])))
            return sizes[-1]
        return original(fd, data)

    monkeypatch.setattr(writer.os, "write", partial)
    generated = "é" * 50
    write(root, generated)
    assert (root / PATH).read_bytes() == generated.encode()
    assert len(sizes) > 1


def test_zero_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project(tmp_path)
    original = os.write

    def zero(fd: int, data: bytes) -> int:
        return 0 if is_temp_fd(fd) else original(fd, data)

    monkeypatch.setattr(writer.os, "write", zero)
    before = state(root)
    with pytest.raises(TemplateWriteError):
        write(root)
    assert_untouched(root, before)


def test_temp_fsync_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project(tmp_path)
    original = os.fsync

    def failing(fd: int) -> None:
        if is_temp_fd(fd):
            raise OSError(errno.EIO, "fsync")
        original(fd)

    monkeypatch.setattr(writer.os, "fsync", failing)
    before = state(root)
    with pytest.raises(TemplateWriteError) as error:
        write(root)
    assert not isinstance(error.value, TemplatePublishedError)
    assert_untouched(root, before)


def test_replace_error_keeps_old(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path)

    def failing(*args: Any, **kwargs: Any) -> None:
        raise OSError(errno.EIO, "replace")

    monkeypatch.setattr(writer.os, "replace", failing)
    before = state(root)
    with pytest.raises(TemplateWriteError) as error:
        write(root)
    assert not isinstance(error.value, TemplatePublishedError)
    assert_untouched(root, before)


def test_link_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project(tmp_path, None)

    def failing(*args: Any, **kwargs: Any) -> None:
        raise OSError(errno.EIO, "link")

    # Remplacer os.link le retire de supports_dir_fd : forcer le garde.
    monkeypatch.setattr(writer, "_secure_write_available", lambda: True)
    monkeypatch.setattr(writer.os, "link", failing)
    with pytest.raises(TemplateWriteError) as error:
        write(root)
    assert not isinstance(error.value, TemplatePublishedError)
    assert_untouched(root, (None, None))


# Après publication : jamais présenté comme « rien écrit ».


def test_directory_fsync_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project(tmp_path)
    original = os.fsync

    def failing(fd: int) -> None:
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError(errno.EIO, "fsync dir")
        original(fd)

    monkeypatch.setattr(writer.os, "fsync", failing)
    with pytest.raises(TemplatePublishedError) as error:
        write(root)
    assert not isinstance(error.value, TemplateHistoryError)
    assert isinstance(error.value.publication, TemplatePublication)
    assert (root / PATH).read_bytes() == GENERATED.encode()
    assert not history(root).exists()
    assert temps(root) == []


def test_mutation_right_after_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path)
    original = writer.snapshot_template

    def raced(root_path: Path, path: str) -> TemplateSnapshot:
        (root / PATH).write_bytes(b"<p>tiers</p>\n")
        return original(root_path, path)

    monkeypatch.setattr(writer, "snapshot_template", raced)
    with pytest.raises(TemplatePublishedError, match="relire") as error:
        write(root)
    assert not isinstance(error.value, TemplateWriteConflictError)
    assert error.value.publication is None
    assert (root / PATH).read_bytes() == b"<p>tiers</p>\n"
    assert not history(root).exists()


def test_same_bytes_swap_right_after_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path)
    original = writer.snapshot_template
    kept: list[Path] = []

    def raced(root_path: Path, path: str) -> TemplateSnapshot:
        keep = tmp_path / "kept"
        os.link(root / PATH, keep)
        kept.append(keep)
        swap = root / "mvc/views/contacts/swap"
        swap.write_bytes(GENERATED.encode())
        os.replace(swap, root / PATH)
        return original(root_path, path)

    monkeypatch.setattr(writer, "snapshot_template", raced)
    with pytest.raises(TemplatePublishedError):
        write(root)
    assert not history(root).exists()


def journal_failure(root: Path, kind: str, monkeypatch: pytest.MonkeyPatch) -> None:
    if kind == "symlink":
        elsewhere = root.parent / "elsewhere"
        elsewhere.mkdir()
        (root / ".forge-design").symlink_to(elsewhere, target_is_directory=True)
    elif kind == "permission":
        (root / ".forge-design").mkdir(mode=0o500)
    else:
        original_append = writer.append_generation_history

        def fsync_failing(*args: Any, **kwargs: Any) -> Any:
            def failing(fd: int) -> None:
                raise OSError(errno.EIO, "fsync")

            monkeypatch.setattr(writer.os, "fsync", failing)
            return original_append(*args, **kwargs)

        monkeypatch.setattr(writer, "append_generation_history", fsync_failing)


@pytest.mark.parametrize("kind", ["symlink", "permission", "fsync"])
def test_history_failure_after_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    if kind == "permission" and os.geteuid() == 0:
        pytest.skip("root ignore les permissions")
    root = project(tmp_path)
    journal_failure(root, kind, monkeypatch)
    calls = 0
    inner = writer.append_generation_history

    def counting(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return inner(*args, **kwargs)

    monkeypatch.setattr(writer, "append_generation_history", counting)
    try:
        with pytest.raises(TemplateHistoryError) as error:
            write(root)
    finally:
        if kind == "permission":
            (root / ".forge-design").chmod(0o700)
    publication = error.value.publication
    assert isinstance(publication, TemplatePublication)
    assert publication.path == PATH and not publication.created
    assert (root / PATH).read_bytes() == GENERATED.encode()
    assert publication.revision.digest == hashlib.sha256(GENERATED.encode()).hexdigest()
    assert calls == 1
    assert temps(root) == []


# Hardlinks, périmètre.


def test_hardlink_keeps_old_inode(tmp_path: Path) -> None:
    root = project(tmp_path)
    other = tmp_path / "other-link.html"
    os.link(root / PATH, other)
    write(root)
    assert (root / PATH).read_bytes() == GENERATED.encode()
    assert other.read_bytes() == b"<p>old</p>\n"


def test_exception_hierarchy() -> None:
    assert issubclass(TemplateWriteConflictError, TemplateWriteError)
    assert issubclass(TemplatePublishedError, TemplateWriteError)
    assert issubclass(TemplateHistoryError, TemplatePublishedError)
    assert not issubclass(TemplatePublishedError, TemplateWriteConflictError)
    assert issubclass(TemplateWriteError, RuntimeError)


def test_writer_does_not_generate_or_diff() -> None:
    names = set(vars(writer))
    assert not names & {"build_template_diff", "generate_simple_template"}


def test_tool_registry_unchanged() -> None:
    assert len(create_tool_registry().list()) == 5


def test_in_place_same_size_edit_right_after_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path)
    original = writer.snapshot_template

    def raced(root_path: Path, path: str) -> TemplateSnapshot:
        # Même inode, même taille : seul le digest révèle la modification.
        with (root / PATH).open("r+b") as stream:
            stream.write(b"X")
        return original(root_path, path)

    monkeypatch.setattr(writer, "snapshot_template", raced)
    with pytest.raises(TemplatePublishedError):
        write(root)
    assert len((root / PATH).read_bytes()) == len(GENERATED.encode())
    assert not history(root).exists()
