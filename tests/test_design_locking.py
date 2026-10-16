"""FD-EDITOR-008 : refus, pannes, montage réel, durée de vie des verrous."""

import errno
import fcntl
import multiprocessing
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from test_web_editor import (
    DESIGN,
    design_file,
    displayed_revision,
    make_root,
    request,
    serving,
)

from forge_design.design import io, locking
from forge_design.design.io import DesignLockError, design_mutation


def save(root: Path) -> None:
    read = io.read_design(root, DESIGN)
    assert read.design is not None
    io.write_design(root, DESIGN, read.design, expected_revision=read.revision)


def post(app: Any, revision: str) -> tuple[int, str, dict[str, str]]:
    return request(
        app,
        "/editor/action",
        {
            "design": DESIGN,
            "revision": revision,
            "action": "props",
            "path": "0",
            "props": '{"class":"changed"}',
        },
    )


def test_lock_inode_persists_and_get_never_creates_it(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    with serving(root, tmp_path) as app:
        revision = displayed_revision(app)
        assert not (root / ".forge-design").exists()
        assert post(app, revision)[0] == 303
    lock = next((root / ".forge-design/locks").iterdir())
    before = lock.stat()
    save(root)
    assert lock.stat().st_ino == before.st_ino
    assert lock.read_bytes() == b"" and lock.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "fault", ["directory-link", "file-link", "hardlink", "permissions", "foreign-owner"]
)
def test_unsafe_metadata_is_refused_without_design_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    root = make_root(tmp_path)
    save(root)
    directory = root / ".forge-design/locks"
    lock = next(directory.iterdir())
    if fault == "directory-link":
        directory.rename(root / "old-locks")
        directory.symlink_to(root / "old-locks", target_is_directory=True)
    elif fault == "file-link":
        lock.unlink()
        lock.symlink_to(design_file(root))
    elif fault == "hardlink":
        os.link(lock, directory / "alias")
    elif fault == "permissions":
        lock.chmod(0o666)
    else:
        monkeypatch.setattr(locking.os, "geteuid", lambda: os.getuid() + 1)
    before = design_file(root).read_bytes()
    with pytest.raises(DesignLockError):
        save(root)
    assert design_file(root).read_bytes() == before


def test_target_mount_is_checked_not_source_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_root(tmp_path)
    original = locking.filesystem_type
    seen: list[str] = []

    def mount(fd: int) -> str:
        target = os.readlink(f"/proc/self/fd/{fd}")
        seen.append(target)
        if target == str(design_file(root)):
            raise locking.LockUnavailable("Montage cible non qualifié")
        return original(fd)

    monkeypatch.setattr(locking, "filesystem_type", mount)
    before = design_file(root).read_bytes()
    with serving(root, tmp_path) as app:
        status, _, headers = post(app, displayed_revision(app))
    assert status == 503 and headers["Cache-Control"] == "no-store"
    assert str(root) in seen and str(design_file(root)) in seen
    assert design_file(root).read_bytes() == before


@pytest.mark.parametrize(
    "fault", ["mountinfo", "unsupported-fs", "unsupported-os", "flock"]
)
def test_unverifiable_environment_refuses_api_and_web(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    root = make_root(tmp_path)
    if fault in {"mountinfo", "unsupported-fs"}:
        original = Path.read_text

        def read(path: Path, *args: Any, **kwargs: Any) -> str:
            if str(path) == "/proc/self/mountinfo":
                if fault == "mountinfo":
                    raise OSError("unavailable")
                return (
                    original(path)
                    .replace(" - tmpfs ", " - nfs ")
                    .replace(" - ext4 ", " - nfs ")
                )
            return original(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read)
    elif fault == "unsupported-os":
        monkeypatch.setattr(locking.sys, "platform", "unsupported")
    else:

        def unavailable(*args: Any) -> None:
            raise OSError(errno.ENOLCK, "no locks")

        monkeypatch.setattr(fcntl, "flock", unavailable)
    before = design_file(root).read_bytes()
    with pytest.raises(DesignLockError):
        save(root)
    with serving(root, tmp_path) as app:
        assert post(app, displayed_revision(app))[0] == 503
    assert design_file(root).read_bytes() == before


@pytest.mark.parametrize("exception", [RuntimeError, KeyboardInterrupt])
def test_exception_releases_lock(
    tmp_path: Path, exception: type[BaseException]
) -> None:
    root = make_root(tmp_path)
    with pytest.raises(exception):
        with design_mutation(root, DESIGN):
            raise exception("interrupted")
    save(root)


def test_timeout_is_bounded_503_and_no_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from http.client import HTTPConnection

    import test_web_editor

    def patient_connection(*args: Any, **kwargs: Any) -> HTTPConnection:
        return HTTPConnection(*args, **(kwargs | {"timeout": 8}))

    monkeypatch.setattr(test_web_editor, "HTTPConnection", patient_connection)
    root = make_root(tmp_path)
    ready, release = threading.Event(), threading.Event()

    def holder() -> None:
        with design_mutation(root, DESIGN):
            ready.set()
            assert release.wait(15)

    thread = threading.Thread(target=holder)
    with serving(root, tmp_path) as app:
        revision = displayed_revision(app)
        before = design_file(root).read_bytes()
        thread.start()
        assert ready.wait(5)
        try:
            start = time.monotonic()
            status, _, _ = post(app, revision)
            duration = time.monotonic() - start
            assert status == 503 and 5 <= duration < 7
            assert design_file(root).read_bytes() == before
        finally:
            release.set()
            thread.join(5)
        assert post(app, revision)[0] == 303


def test_independent_design_can_progress(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    other = "contacts/other.design.json"
    (root / "mvc/views" / other).write_bytes(design_file(root).read_bytes())
    done = threading.Event()

    def worker() -> None:
        read = io.read_design(root, other)
        assert read.design is not None
        io.write_design(root, other, read.design, expected_revision=read.revision)
        done.set()

    with design_mutation(root, DESIGN):
        thread = threading.Thread(target=worker)
        thread.start()
        assert done.wait(2)
        thread.join(2)


def test_replaced_lock_refused_before_nested_write(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    with design_mutation(root, DESIGN):
        lock = next((root / ".forge-design/locks").iterdir())
        lock.rename(lock.with_suffix(".old"))
        lock.touch(mode=0o600)
        before = design_file(root).read_bytes()
        with pytest.raises(DesignLockError):
            save(root)
        assert design_file(root).read_bytes() == before


@pytest.mark.parametrize(
    "failure", ["before-publication", "directory-fsync", "after-publication-change"]
)
def test_publication_failure_is_never_a_false_conflict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    root = make_root(tmp_path)
    with serving(root, tmp_path) as app:
        revision = displayed_revision(app)
        before = design_file(root).read_bytes()
        original = io.os.fsync
        count = 0

        def fsync(fd: int) -> None:
            nonlocal count
            count += 1
            if (failure == "before-publication" and count == 1) or (
                failure == "directory-fsync" and count == 2
            ):
                raise OSError("injected fsync error")
            original(fd)
            if failure == "after-publication-change" and count == 2:
                data = design_file(root).read_text().replace('"changed"', '"external"')
                design_file(root).write_text(data)

        monkeypatch.setattr(io.os, "fsync", fsync)
        status, html, _ = post(app, revision)
        assert status == 500 and "Sauvegarde incertaine" in html
        assert (design_file(root).read_bytes() == before) == (
            failure == "before-publication"
        )
        assert io.read_design(root, DESIGN).design is not None
        monkeypatch.undo()
        assert post(app, displayed_revision(app))[0] == 303


def parked_writer(root_text: str, phase: str, ready: Any) -> None:
    root = Path(root_text)
    with design_mutation(root, DESIGN):
        if phase == "after":
            save(root)
        ready.set()
        time.sleep(60)


@pytest.mark.parametrize("phase", ["before", "after"])
def test_killed_process_releases_lock(tmp_path: Path, phase: str) -> None:
    root = make_root(tmp_path)
    ctx = multiprocessing.get_context("spawn")
    ready = ctx.Event()
    child = ctx.Process(target=parked_writer, args=(str(root), phase, ready))
    child.start()
    try:
        assert ready.wait(5)
    finally:
        child.kill()
        child.join(5)
    save(root)


def test_fork_child_does_not_keep_parent_lock(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    read_fd, write_fd = os.pipe()
    pid = -1
    try:
        with design_mutation(root, DESIGN):
            pid = os.fork()
            if pid == 0:
                os.close(write_fd)
                os.read(read_fd, 1)
                os._exit(0)
        # Le fils reste vivant, mais ne possède aucun descripteur de verrou.
        os.close(read_fd)
        save(root)
    finally:
        os.close(write_fd)
        if pid > 0:
            assert os.waitpid(pid, 0)[1] == 0


def test_exec_child_does_not_keep_lock(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    with design_mutation(root, DESIGN):
        child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import sys; print('ready',flush=True); sys.stdin.read()",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            close_fds=False,
        )
        assert child.stdout is not None and child.stdout.readline() == "ready\n"
    try:
        save(root)
    finally:
        child.communicate("", timeout=5)
    assert child.returncode == 0


def test_read_compare_apply_and_replace_hold_the_same_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from forge_design.web import editor

    root = make_root(tmp_path)
    stages: list[str] = []

    def probe(stage: str) -> None:
        lock = next((root / ".forge-design/locks").iterdir())
        fd = os.open(lock, os.O_RDWR)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd)
        stages.append(stage)

    original_read = editor.read_design
    original_compare = editor.hmac.compare_digest
    original_apply = editor._apply  # pyright: ignore[reportPrivateUsage]
    original_replace = io.os.replace

    def read(*args: Any, **kwargs: Any) -> Any:
        probe("read")
        return original_read(*args, **kwargs)

    def compare(a: str, b: str) -> bool:
        probe("compare")
        return original_compare(a, b)

    def apply(*args: Any, **kwargs: Any) -> Any:
        probe("apply")
        return original_apply(*args, **kwargs)

    def replace(*args: Any, **kwargs: Any) -> None:
        probe("replace")
        original_replace(*args, **kwargs)

    with serving(root, tmp_path) as app:
        revision = displayed_revision(app)
        monkeypatch.setattr(editor, "read_design", read)
        monkeypatch.setattr(editor.hmac, "compare_digest", compare)
        monkeypatch.setattr(editor, "_apply", apply)
        monkeypatch.setattr(io.os, "replace", replace)
        assert post(app, revision)[0] == 303
    assert stages == ["read", "compare", "apply", "replace"]


def test_waiter_reloads_revision_after_lock_acquisition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_root(tmp_path)
    attempted = threading.Event()
    original = locking._acquire  # pyright: ignore[reportPrivateUsage]

    def acquire(fd: int) -> None:
        attempted.set()
        original(fd)

    with serving(root, tmp_path) as app:
        revision = displayed_revision(app)
        results: list[int] = []
        with design_mutation(root, DESIGN):
            monkeypatch.setattr(locking, "_acquire", acquire)
            thread = threading.Thread(
                target=lambda: results.append(post(app, revision)[0])
            )
            thread.start()
            assert attempted.wait(3)
            assert results == []
            save(root)  # publication sous le verrou initial, révision périmée
            after = design_file(root).read_bytes()
        thread.join(5)
        assert results == [409]
        assert design_file(root).read_bytes() == after


def test_uncooperative_prepublication_change_renders_current_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import re

    from forge_design.web.editor import design_revision_token

    root = make_root(tmp_path)
    original = io._check  # pyright: ignore[reportPrivateUsage]
    count = 0

    def check(*args: Any, **kwargs: Any) -> Any:
        nonlocal count
        count += 1
        if count == 2:
            text = design_file(root).read_text().replace('"p-4"', '"p-5"')
            design_file(root).write_text(text)
        return original(*args, **kwargs)

    with serving(root, tmp_path) as app:
        revision = displayed_revision(app)
        monkeypatch.setattr(io, "_check", check)
        status, html, headers = post(app, revision)
    assert status == 409 and headers["Cache-Control"] == "no-store"
    assert 'name="path" value=""' in html and "Recharger l’éditeur" in html
    expected = design_revision_token(DESIGN, io.read_design(root, DESIGN))
    assert set(re.findall(r'name="revision" value="([^"]+)"', html)) == {expected}
    assert '"p-5"' in design_file(root).read_text()


def test_acquisition_at_deadline_refuses_before_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_root(tmp_path)
    before = design_file(root).read_bytes()
    clock = iter([0.0, 0.0, 5.0])
    monkeypatch.setattr(locking.time, "monotonic", lambda: next(clock))
    with pytest.raises(DesignLockError):
        with design_mutation(root, DESIGN):
            pytest.fail("Aucune action après l'échéance")
    assert design_file(root).read_bytes() == before
    monkeypatch.undo()
    save(root)  # le flock acquis trop tard a été fermé
