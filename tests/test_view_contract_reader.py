"""Lecture réelle, séparation inventaire/détail, bornes et confinement."""

import json
import os
import socket
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest
from test_templates import make_views
from test_web_recent_projects import project

from forge_design.contracts import (
    ViewContract,
    read_view_contract,
    read_view_contracts,
    reader,
    view_contract_source,
)
from forge_design.forge.project_root import ProjectRootNotFoundError
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.forge.source import SourceReadError
from forge_design.limits import MAX_SOURCE_BYTES

DATA: dict[str, Any] = {"name": "a", "template": "mvc/views/../missing", "context": {}}
TEXT = json.dumps(DATA)
FIXTURES = Path(__file__).parent / "fixtures/contracts"


def test_roots_and_absent(tmp_path: Path) -> None:
    def detail(root: Path) -> object:
        return read_view_contract(root, "a.view.json")

    for function in (read_view_contracts, detail):
        with pytest.raises(ProjectRootNotFoundError):
            function(tmp_path / "absent")
        with pytest.raises(NotForgeProjectError):
            function(tmp_path)
    root = project(tmp_path / "project")
    assert not read_view_contracts(root).source_present
    (root / "mvc/views").mkdir()
    result = read_view_contracts(root)
    assert result.source_present and result.contracts == result.issues == ()
    with pytest.raises(FileNotFoundError):
        read_view_contract(root, "absent.view.json")


def test_inventory_metadata_and_no_parsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, views = make_views(tmp_path)
    names = ("z.view.json", "a/b.view.json", "é.view.json", "foo.key.view.json")
    for name in names:
        file = views / name
        file.parent.mkdir(exist_ok=True)
        file.write_bytes(b"\xff")
    for name in (
        "foo.json",
        "foo.design.json",
        "foo.view.JSON",
        "foo.view.json.bak",
        ".view.json",
        ".hidden.view.json",
    ):
        (views / name).touch()
    (root / "mvc/templates").mkdir()
    (root / "mvc/templates/other.view.json").touch()

    def forbidden(*args: object, **kwargs: object) -> Any:
        raise AssertionError("inventory parsed/read content")

    monkeypatch.setattr(json, "loads", forbidden)
    monkeypatch.setattr(ViewContract, "model_validate", forbidden)
    monkeypatch.setattr(os, "fdopen", forbidden)
    result = read_view_contracts(root)
    assert [i.path for i in result.contracts] == sorted(names)
    assert result.issues == () and not result.truncated
    for item in result.contracts:
        stat = (views / item.path).stat()
        assert (item.size, item.modified_ns) == (stat.st_size, stat.st_mtime_ns)
    with pytest.raises(FrozenInstanceError):
        setattr(result, "truncated", True)
    with pytest.raises(FrozenInstanceError):
        setattr(result.contracts[0], "size", 4)


@pytest.mark.parametrize("fixture", ["minimal", "contacts-list"])
def test_official_fixtures_no_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fixture: str
) -> None:
    root, views = make_views(tmp_path)
    raw = (FIXTURES / f"{fixture}.view.json").read_bytes()
    (views / "a.view.json").write_bytes(raw)

    def forbidden(*args: object, **kwargs: object) -> Any:
        raise AssertionError("detail scanned")

    monkeypatch.setattr(reader, "read_view_contracts", forbidden)
    monkeypatch.setattr(os, "scandir", forbidden)
    result = read_view_contract(root, "a.view.json")
    assert result.contract is not None and result.issues == ()
    assert result.contract.model_dump(exclude_unset=True) == json.loads(raw)
    assert result.size == len(raw)
    with pytest.raises(FrozenInstanceError):
        setattr(result, "contract", None)


@pytest.mark.parametrize(
    "raw",
    [
        b"\xef\xbb\xbf" + TEXT.encode(),
        (TEXT + " " * (MAX_SOURCE_BYTES - len(TEXT))).encode(),
    ],
)
def test_bom_and_exact_size(tmp_path: Path, raw: bytes) -> None:
    root, views = make_views(tmp_path)
    (views / "a.view.json").write_bytes(raw)
    assert read_view_contract(root, "a.view.json").contract is not None


@pytest.mark.parametrize(
    "raw", [b"\xff", TEXT.encode("utf-16"), b" " * (MAX_SOURCE_BYTES + 1)]
)
def test_unreadable_bytes(tmp_path: Path, raw: bytes) -> None:
    root, views = make_views(tmp_path)
    (views / "a.view.json").write_bytes(raw)
    result = read_view_contract(root, "a.view.json")
    assert result.contract is result.size is result.modified_ns is None
    assert result.issues[0].code == "contract.unreadable"


@pytest.mark.parametrize(
    "text",
    [
        "",
        '{"name":',
        '{"x":1,}',
        "//comment\n{}",
        "/*comment*/{}",
        "NaN",
        "Infinity",
        "-Infinity",
        '{"x":NaN}',
        '{"name":"a","name":"b"}',
        '{"context":{"x":{},"x":{}}}',
        '{"fields":{"a":"x","a":"y"}}',
        '{"actions":{"a":{},"a":{}}}',
        '{"actions":{"a":{"method":"GET","method":"POST"}}}',
        "9" * 10000,
        "[" * 10000 + "0" + "]" * 10000,
    ],
)
def test_json_failures(tmp_path: Path, text: str) -> None:
    root, views = make_views(tmp_path)
    (views / "a.view.json").write_text(text)
    result = read_view_contract(root, "a.view.json")
    assert result.contract is None and result.size == len(text.encode())
    assert [i.code for i in result.issues] == ["contract.json_invalid"]


@pytest.mark.parametrize(
    "data",
    [
        [],
        "hello",
        42,
        {},
        DATA | {"actions": None},
        DATA | {"metadata": dict[str, object]()},
        DATA | {"actions": {"save": {"method": "POST", "path": "x", "csrf": 1}}},
    ],
)
def test_validation_failures(tmp_path: Path, data: object) -> None:
    root, views = make_views(tmp_path)
    (views / "a.view.json").write_text(json.dumps(data))
    result = read_view_contract(root, "a.view.json")
    assert result.contract is None and result.issues
    assert all(
        i.code == "contract.validation_error" and i.path == "a.view.json"
        for i in result.issues
    )


def test_locations_order_and_validation_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, views = make_views(tmp_path)
    file = views / "a.view.json"
    data = DATA | {
        "context": {"contacts": {"type": "unknown"}},
        "actions": {"save": {"method": "GET", "path": "x", "csrf": 1}},
    }
    file.write_text(json.dumps(data))
    result = read_view_contract(root, file.name)
    assert [i.location for i in result.issues] == [
        ("context", "contacts", "type"),
        ("actions", "save", "csrf"),
    ]
    with pytest.raises(FrozenInstanceError):
        setattr(result.issues[0], "code", "changed")
    monkeypatch.setattr(reader, "MAX_VIEW_CONTRACT_VALIDATION_ISSUES", 2)
    assert len(read_view_contract(root, file.name).issues) == 2
    file.write_text(json.dumps(data | {"extra": 1}))
    result = read_view_contract(root, file.name)
    assert len(result.issues) == 2
    assert [i.code for i in result.issues] == [
        "contract.validation_error",
        "contract.analysis_truncated",
    ]


@pytest.mark.parametrize(
    "path",
    [
        "../x.view.json",
        "../../etc/passwd.view.json",
        "a/../../../x.view.json",
        "/x.view.json",
        ".hidden/x.view.json",
        "foo\\bar.view.json",
        "foo:bar.view.json",
        "a\x00.view.json",
        "x.json",
        "x.html",
        ".view.json",
        "env/a.view.json",
        ".env/a.view.json",
        "private.key/a.view.json",
        "private.pem/a.view.json",
        "ID_RSA_backup.view.json",
    ],
)
def test_lexical_before_project(tmp_path: Path, path: str) -> None:
    assert view_contract_source(path) is None
    with pytest.raises(SourceReadError):
        read_view_contract(tmp_path / "nonexistent", path)


def test_unicode_refresh_non_execution_non_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, views = make_views(tmp_path)
    config = tmp_path / "xdg"
    config.mkdir()
    (config / "state").write_text("unchanged")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    (root / "mvc/controllers").mkdir()
    (root / "mvc/controllers/hostile.py").write_text(
        "raise AssertionError('never import')"
    )
    names = ("é.view.json", "e\u0301.view.json", "😀 ß +&%#?.view.json")
    for name in names:
        (views / name).write_text(TEXT)

    def snapshot() -> dict[str, tuple[bytes, int, int]]:
        return {
            str(p): (p.read_bytes(), p.stat().st_size, p.stat().st_mtime_ns)
            for base in (root, config)
            for p in base.rglob("*")
            if p.is_file()
        }

    before = snapshot()
    assert {i.path for i in read_view_contracts(root).contracts} == set(names)
    for name in names:
        assert read_view_contract(root, name).contract is not None
    assert snapshot() == before
    file = views / names[0]
    file.write_text(json.dumps(DATA | {"name": "new", "actions": {}}))
    changed = read_view_contract(root, file.name)
    assert changed.contract is not None and changed.contract.name == "new"
    assert changed.contract.actions == {}
    file.unlink()
    with pytest.raises(FileNotFoundError):
        read_view_contract(root, file.name)
    assert file.name not in {i.path for i in read_view_contracts(root).contracts}


def test_inventory_real_file_and_entry_limits(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    for i in range(512):
        (views / f"{i:04}.view.json").touch()
    assert len(read_view_contracts(root).contracts) == 512
    assert not read_view_contracts(root).truncated
    (views / "extra.view.json").touch()
    result = read_view_contracts(root)
    assert len(result.contracts) == 512 and result.truncated
    assert result.issues[-1].code == "contract.analysis_truncated"
    (views / "extra.view.json").unlink()
    for i in range(4096 - 512):
        (views / f".ignored{i}").touch()
    assert not read_view_contracts(root).truncated
    (views / ".surplus").touch()
    assert read_view_contracts(root).truncated


def test_depth_exact_and_over(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    deep = views
    for _ in range(32):
        deep /= "d"
        deep.mkdir()
    (deep / "a.view.json").touch()
    assert len(read_view_contracts(root).contracts) == 1
    assert not read_view_contracts(root).truncated
    (deep / "over").mkdir()
    assert read_view_contracts(root).truncated


def test_inventory_issues_limit_and_local_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, views = make_views(tmp_path)
    for name in ("a.view.json", "b.view.json", "ok.view.json"):
        (views / name).touch()
    original = os.stat

    def fail(path: Any, **kwargs: Any) -> os.stat_result:
        if (
            isinstance(path, str)
            and path in {"a.view.json", "b.view.json", "c.view.json"}
            and kwargs.get("dir_fd") is not None
        ):
            raise PermissionError("denied")
        return original(path, **kwargs)

    monkeypatch.setattr(os, "stat", fail)
    monkeypatch.setattr(reader, "MAX_VIEW_CONTRACT_ISSUES", 2)
    result = read_view_contracts(root)
    assert len(result.issues) == 2 and not result.truncated
    assert [i.path for i in result.contracts] == ["ok.view.json"]
    (views / "c.view.json").touch()
    result = read_view_contracts(root)
    assert len(result.issues) == 2 and result.truncated
    assert result.issues[-1].code == "contract.analysis_truncated"


@pytest.mark.parametrize("part", ["mvc", "views", "sub", "a.view.json"])
def test_symlinks(tmp_path: Path, part: str) -> None:
    root, views = make_views(tmp_path)
    (views / "sub").mkdir()
    (views / "a.view.json").write_text(TEXT)
    file = root / "mvc" if part == "mvc" else views if part == "views" else views / part
    saved = file.with_name(file.name + "-saved")
    file.rename(saved)
    file.symlink_to(saved)
    if part == "mvc":
        with pytest.raises(NotForgeProjectError):
            read_view_contracts(root)
        with pytest.raises(NotForgeProjectError):
            read_view_contract(root, "a.view.json")
    else:
        result = read_view_contracts(root)
        assert all(i.path != part for i in result.contracts)
        path = "sub/x.view.json" if part == "sub" else "a.view.json"
        assert read_view_contract(root, path).issues[0].code == "contract.unreadable"


def test_special_files(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    os.mkfifo(views / "pipe.view.json")
    (views / "dir.view.json").mkdir()
    with socket.socket(socket.AF_UNIX) as sock:
        sock.bind(str(views / "socket.view.json"))
        assert not read_view_contracts(root).contracts
        for name in ("pipe.view.json", "dir.view.json", "socket.view.json"):
            assert (
                read_view_contract(root, name).issues[0].code == "contract.unreadable"
            )


@pytest.mark.parametrize("target", ["views", "sub", "a.view.json"])
def test_inventory_stat_open_races(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    root, views = make_views(tmp_path)
    (views / "a.view.json").write_text(TEXT)
    (views / "sub").mkdir()
    original = os.open
    replaced = False

    def race(
        path: Any, flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        nonlocal replaced
        if path == target and dir_fd is not None and not replaced:
            replaced = True
            file = views if target == "views" else views / target
            file.rename(file.with_name(file.name + "-saved"))
            if target.endswith(".json"):
                file.write_text(TEXT)
            else:
                file.mkdir()
                (file / "new.view.json").touch()
        return original(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", race)
    result = read_view_contracts(root)
    assert replaced and any(i.code == "contract.unreadable" for i in result.issues)
    assert not any(i.path.endswith("new.view.json") for i in result.contracts)


def test_detail_race_mutation_and_descriptors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, views = make_views(tmp_path)
    file = views / "a.view.json"
    file.write_text(TEXT)
    before = set(os.listdir("/proc/self/fd"))
    original = os.stat
    replaced = False

    def race(path: Any, **kwargs: Any) -> os.stat_result:
        nonlocal replaced
        stat = original(path, **kwargs)
        if path == file.name and kwargs.get("dir_fd") is not None and not replaced:
            replaced = True
            file.rename(views / "old")
            file.write_text(TEXT)
        return stat

    monkeypatch.setattr(os, "stat", race)
    assert read_view_contract(root, file.name).issues[0].code == "contract.unreadable"
    monkeypatch.undo()
    original_fstat = os.fstat
    inode = file.stat().st_ino
    calls = 0

    def mutate(fd: int) -> os.stat_result:
        nonlocal calls
        stat = original_fstat(fd)
        if stat.st_ino == inode:
            calls += 1
            if calls == 2:
                file.write_text(TEXT.replace('"a"', '"b"'))
                os.utime(file, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1000000000))
                return original_fstat(fd)
        return stat

    monkeypatch.setattr(os, "fstat", mutate)
    assert read_view_contract(root, file.name).issues[0].code == "contract.unreadable"
    monkeypatch.undo()
    assert read_view_contract(root, file.name).contract is not None
    file.unlink()
    file.symlink_to(views / "old")
    assert read_view_contract(root, file.name).issues[0].code == "contract.unreadable"
    assert set(os.listdir("/proc/self/fd")) == before
