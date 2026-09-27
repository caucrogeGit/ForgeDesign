"""Persistance bornée, atomique et indépendante des projets référencés."""

import json
import os
from pathlib import Path

import pytest

from forge_design.recent_projects import (
    MAX_RECENT_FILE_BYTES,
    RecentProject,
    RecentProjects,
    RecentProjectsError,
    recent_projects_file,
    resolve_user_config_dir,
)


def test_config_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert recent_projects_file() == tmp_path / "xdg/forge-design/recent-projects.json"

    def fake_home(cls: type[Path]) -> Path:
        return tmp_path

    monkeypatch.setattr(Path, "home", classmethod(fake_home))
    for value in ("", "relative"):
        monkeypatch.setenv("XDG_CONFIG_HOME", value)
        assert resolve_user_config_dir() == tmp_path / ".config/forge-design"
    monkeypatch.delenv("XDG_CONFIG_HOME")
    assert resolve_user_config_dir() == tmp_path / ".config/forge-design"


def test_order_limit_unicode_restart_and_remove(tmp_path: Path) -> None:
    path = tmp_path / "config/recent-projects.json"
    store = RecentProjects(path)
    assert store.list() == () and store.warning is None and not path.exists()
    roots = [tmp_path / f"projet-é-{index}" for index in range(12)]
    for root in roots:
        store.add(root)  # La primitive ne consulte pas les chemins enregistrés.
    assert not any(root.exists() for root in roots)
    assert store.list() == tuple(RecentProject(str(p)) for p in reversed(roots[2:]))
    store.add(roots[5])
    store.add(roots[5])
    assert len(store.list()) == 10 and store.list()[0].path == str(roots[5])
    other = RecentProjects(path)
    assert other.list() == store.list()
    other.remove(roots[5])
    assert len(store.list()) == 9
    before = path.read_bytes(), path.stat().st_mtime_ns
    store.remove(roots[5])
    assert before == (path.read_bytes(), path.stat().st_mtime_ns)
    assert json.loads(path.read_text())["version"] == 1
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.parametrize(
    "content",
    [
        b"not json",
        b'{"version":' + b"1" * 5000 + b',"projects":[]}',
        b'{"version":2,"projects":[]}',
        b'{"version":true,"projects":[]}',
        b'{"version":1,"projects":"wrong"}',
        b'{"version":1,"projects":["relative"]}',
        b'{"version":1,"projects":["/a/../b"]}',
        b'{"version":1,"projects":["/a","/a"]}',
        b'{"version":1,"projects":["/a"],"secret":"no"}',
        b'{"version":1,"projects":["/a\\ud800"]}',
        b"\xff",
        b"x" * (MAX_RECENT_FILE_BYTES + 1),
        json.dumps({"version": 1, "projects": [f"/p{i}" for i in range(11)]}).encode(),
    ],
)
def test_bad_file_preserved(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "recent.json"
    path.write_bytes(content)
    store = RecentProjects(path)
    assert store.list() == () and store.warning
    for operation in (store.add, store.remove):
        with pytest.raises(RecentProjectsError):
            operation(tmp_path / "project")
    assert path.read_bytes() == content
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("kind", ["file-link", "parent-link", "directory", "fifo"])
def test_refused_config_type(tmp_path: Path, kind: str) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    original = outside / "recent.json"
    original.write_text('{"version":1,"projects":[]}')
    path = tmp_path / "config/recent.json"
    if kind == "parent-link":
        path.parent.symlink_to(outside, target_is_directory=True)
    else:
        path.parent.mkdir()
        if kind == "file-link":
            path.symlink_to(original)
        elif kind == "directory":
            path.mkdir()
        else:
            os.mkfifo(path)
    store = RecentProjects(path)
    assert store.warning and store.list() == ()
    with pytest.raises(RecentProjectsError):
        store.add(tmp_path / "project")
    assert original.read_text() == '{"version":1,"projects":[]}'


def test_atomic_failure_cleanup_and_external_corruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "recent.json"
    store = RecentProjects(path)
    store.add(tmp_path / "a")
    before = path.read_bytes()
    calls: list[bytes] = []
    replace = os.replace

    def broken_replace(src: str, dst: str, *, src_dir_fd: int, dst_dir_fd: int) -> None:
        assert src_dir_fd == dst_dir_fd
        assert dst == path.name and src.endswith(".tmp")
        assert path.read_bytes() == before
        calls.append((tmp_path / src).read_bytes())
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", broken_replace)
    with pytest.raises(RecentProjectsError):
        store.add(tmp_path / "b")
    assert len(calls) == 1 and json.loads(calls[0])["projects"][0].endswith("/b")
    assert path.read_bytes() == before and list(tmp_path.iterdir()) == [path]
    monkeypatch.setattr(os, "replace", replace)
    path.write_text('{"version":99,"projects":[]}')
    with pytest.raises(RecentProjectsError):
        store.add(tmp_path / "b")
    assert path.read_text() == '{"version":99,"projects":[]}'


def test_read_does_not_validate_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "recent.json"
    path.write_text('{"version":1,"projects":["/does/not/exist"]}')
    from forge_design.tools.project_inspector import ProjectInspectorTool

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Aucune inspection au chargement")

    monkeypatch.setattr(ProjectInspectorTool, "run", forbidden)
    monkeypatch.setattr(Path, "resolve", forbidden)
    assert RecentProjects(path).list() == (RecentProject("/does/not/exist"),)


def test_never_store_inside_project(tmp_path: Path) -> None:
    store = RecentProjects(tmp_path / "project/config/recent.json")
    with pytest.raises(RecentProjectsError, match="hors des projets"):
        store.add(tmp_path / "project")
    assert not store.path.parent.exists()


def test_empty_file_list_and_frozen_model(tmp_path: Path) -> None:
    from dataclasses import FrozenInstanceError

    path = tmp_path / "recent.json"
    path.write_text('{"version":1,"projects":[]}')
    store = RecentProjects(path)
    assert store.list() == () and store.warning is None
    with pytest.raises(FrozenInstanceError):
        setattr(RecentProject("/a"), "path", "/b")


def test_unsupported_platform_is_controlled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delattr(os, "O_NOFOLLOW")
    store = RecentProjects(tmp_path / "recent.json")
    assert store.list() == () and store.warning
    with pytest.raises(RecentProjectsError, match="indisponible"):
        store.add(tmp_path / "project")


def test_permission_denied_is_controlled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "recent.json"
    path.write_text('{"version":1,"projects":[]}')

    def denied(*args: object, **kwargs: object) -> None:
        raise PermissionError("denied")

    with monkeypatch.context() as guard:
        guard.setattr(os, "stat", denied)
        store = RecentProjects(path)
        assert store.warning and store.list() == ()
        with pytest.raises(RecentProjectsError):
            store.add(tmp_path / "project")
    assert path.read_text() == '{"version":1,"projects":[]}'


def test_temporary_collision_does_not_delete_another_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uuid import UUID

    from forge_design import recent_projects

    monkeypatch.setattr(recent_projects, "uuid4", lambda: UUID(int=0))
    temporary = tmp_path / (".recent-" + "0" * 32 + ".tmp")
    temporary.write_text("existing file")
    store = RecentProjects(tmp_path / "recent.json")
    with pytest.raises(RecentProjectsError):
        store.add(tmp_path / "project")
    assert temporary.read_text() == "existing file"
    assert not store.path.exists()
