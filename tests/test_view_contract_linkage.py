"""Liens déclaratifs, ambiguïtés, incertitude et observations sécurisées."""

import builtins
import json
import os
import socket
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any

import pytest
from test_templates import make_views

from forge_design.contracts import ViewContract, analyze_view_contract_links, linkage
from forge_design.contracts.reader import ViewContractReadResult


def contract(views: Path, path: str, target: str, name: str = "logical") -> None:
    file = views / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(
        json.dumps({"name": name, "template": "mvc/views/" + target, "context": {}})
    )


def test_explicit_link_and_no_filename_guess(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    (views / "target.jinja").write_text("{% broken {{ danger() }}")
    (views / "manual").touch()
    (views / "future.design.json").touch()
    contract(views, "different/abc.view.json", "target.jinja", "not-the-filename")
    result = analyze_view_contract_links(root)
    assert [(t.template_path, t.status) for t in result.templates] == [
        ("manual", "without-contract"),
        ("target.jinja", "linked"),
    ]
    assert result.templates[1].contract_paths == ("different/abc.view.json",)
    assert result.contracts[0].contract_name == "not-the-filename"
    assert result.issues == result.contract_issues == result.template_issues == ()
    assert result.contracts_complete and not result.truncated
    assert result == analyze_view_contract_links(root)
    for obj in (result, result.templates[0], result.contracts[0]):
        with pytest.raises(FrozenInstanceError):
            setattr(obj, "status", "changed")


@pytest.mark.parametrize("bad", ['{"name":', "{}"])
def test_invalid_contract_not_associated(tmp_path: Path, bad: str) -> None:
    root, views = make_views(tmp_path)
    (views / "a.html").touch()
    (views / "a.view.json").write_text(bad)
    result = analyze_view_contract_links(root)
    assert result.templates[0].status == "without-contract"
    assert result.contracts[0].status == "contract-invalid"
    assert result.contracts[0].declared_template is None
    assert result.contract_issues[0].code == (
        "contract.json_invalid" if bad.startswith('{"') else "contract.validation_error"
    )
    assert not result.issues


@pytest.mark.parametrize(
    "target",
    [
        "../secret",
        "env/a",
        ".hidden/a",
        "private.key",
        "foo.view.json",
        "foo.design.json",
    ],
)
def test_invalid_target_without_inspection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    root, views = make_views(tmp_path)
    contract(views, "a.view.json", target)

    def forbidden(*args: object) -> Any:
        raise AssertionError("invalid target inspected")

    monkeypatch.setattr(linkage, "inspect_project_source", forbidden)
    result = analyze_view_contract_links(root)
    assert result.contracts[0].status == "template-invalid-path"
    assert result.contracts[0].template_path is None
    assert result.issues[0].code == "contract.link.invalid-template-path"


def test_synthetic_outside_views(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, views = make_views(tmp_path)
    contract(views, "a.view.json", "x")
    model = ViewContract.model_construct(
        name="x", template="mvc/controllers/a.py", context={}
    )

    def synthetic(*args: object) -> ViewContractReadResult:
        return ViewContractReadResult("a.view.json", 1, 1, model, ())

    monkeypatch.setattr(linkage, "read_view_contract", synthetic)
    assert (
        analyze_view_contract_links(root).contracts[0].status == "template-invalid-path"
    )


@pytest.mark.parametrize(
    "same_name,same_target", [(True, False), (False, True), (True, True)]
)
def test_duplicate_dimensions(
    tmp_path: Path, same_name: bool, same_target: bool
) -> None:
    root, views = make_views(tmp_path)
    for path in ("a", "b"):
        (views / path).touch()
    contract(views, "a.view.json", "a", "one")
    contract(
        views, "b.view.json", "a" if same_target else "b", "one" if same_name else "two"
    )
    result = analyze_view_contract_links(root)
    codes = [i.code for i in result.issues]
    assert codes.count("contract.link.duplicate-name") == 2 * int(same_name)
    assert codes.count("contract.link.multiple-contracts") == 2 * int(same_target)
    assert all(c.status == "linked" for c in result.contracts)
    assert result.templates[0].status == ("ambiguous" if same_target else "linked")
    assert len(result.contracts) == 2


def test_missing_refresh_and_contract_changes(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    contract(views, "a.view.json", "target")
    assert analyze_view_contract_links(root).contracts[0].status == "template-missing"
    (views / "target").touch()
    assert analyze_view_contract_links(root).contracts[0].status == "linked"
    contract(views, "a.view.json", "new", "changed")
    result = analyze_view_contract_links(root)
    assert result.contracts[0].contract_name == "changed"
    assert result.contracts[0].status == "template-missing"
    assert result.templates[0].status == "without-contract"
    (views / "a.view.json").write_text("{}")
    assert analyze_view_contract_links(root).contracts[0].status == "contract-invalid"
    (views / "a.view.json").unlink()
    assert analyze_view_contract_links(root).templates[0].status == "without-contract"


@pytest.mark.parametrize(
    "kind", ["file-link", "parent-link", "directory", "fifo", "socket", "oversize"]
)
def test_unreadable_targets(tmp_path: Path, kind: str) -> None:
    root, views = make_views(tmp_path)
    target = views / "target"
    relative = "target"
    sock = None
    if kind == "file-link":
        (views / "real").touch()
        target.symlink_to(views / "real")
    elif kind == "parent-link":
        (views / "real").mkdir()
        (views / "real/file").touch()
        target.symlink_to(views / "real")
        relative += "/file"
    elif kind == "directory":
        target.mkdir()
    elif kind == "fifo":
        os.mkfifo(target)
    elif kind == "socket":
        sock = socket.socket(socket.AF_UNIX)
        sock.bind(str(target))
    else:
        target.write_bytes(b"x" * (1024 * 1024 + 1))
    try:
        contract(views, "a.view.json", relative)
        result = analyze_view_contract_links(root)
        assert result.contracts[0].status == "template-unreadable"
        assert result.issues[0].code == "contract.link.template-unreadable"
        assert relative not in [t.template_path for t in result.templates]
    finally:
        if sock is not None:
            sock.close()


def test_views_symlink(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    saved = views.with_name("saved")
    views.rename(saved)
    views.symlink_to(saved)
    result = analyze_view_contract_links(root)
    assert result.templates == result.contracts == ()
    assert result.template_issues and result.contract_issues
    assert not result.contracts_complete


@pytest.mark.parametrize("change", ["delete", "symlink"])
def test_target_race_after_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    root, views = make_views(tmp_path)
    target = views / "target"
    target.touch()
    contract(views, "a.view.json", "target")
    original = linkage.inspect_project_source

    def inspect(root: Path, path: str):
        target.unlink()
        if change == "symlink":
            target.symlink_to(views / "a.view.json")
        return original(root, path)

    monkeypatch.setattr(linkage, "inspect_project_source", inspect)
    result = analyze_view_contract_links(root)
    assert result.contracts[0].status == (
        "template-missing" if change == "delete" else "template-unreadable"
    )
    assert not result.templates


def test_contract_disappears_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, views = make_views(tmp_path)
    (views / "target").touch()
    contract(views, "a.view.json", "target")
    original = linkage.read_view_contract

    def read(root: Path, path: str):
        (views / path).unlink()
        return original(root, path)

    monkeypatch.setattr(linkage, "read_view_contract", read)
    result = analyze_view_contract_links(root)
    assert result.templates[0].status == "unknown"
    assert result.contracts[0].status == "contract-invalid"
    assert result.contract_issues[0].code == "contract.unreadable"


@pytest.mark.parametrize("which", ["templates", "contracts"])
def test_upstream_truncation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, which: str
) -> None:
    root, views = make_views(tmp_path)
    (views / "target").touch()
    (views / "manual").touch()
    contract(views, "a.view.json", "target")
    if which == "templates":
        original = linkage.read_templates

        def partial_templates(root: Path):
            return replace(original(root), templates=(), truncated=True)

        monkeypatch.setattr(linkage, "read_templates", partial_templates)
    else:
        original_contracts = linkage.read_view_contracts

        def partial_contracts(root: Path):
            return replace(original_contracts(root), truncated=True)

        monkeypatch.setattr(linkage, "read_view_contracts", partial_contracts)
    result = analyze_view_contract_links(root)
    assert result.truncated and result.contracts[0].status == "linked"
    if which == "templates":
        assert result.templates[0].template_path == "target"
        assert result.templates[0].status == "linked"
    else:
        assert all(t.status == "unknown" for t in result.templates)
    assert result.issues[-1].code == "contract.link.analysis-truncated"


def test_inspect_unique_target_no_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, views = make_views(tmp_path)
    (views / "target").write_bytes(b"\xff")
    contract(views, "a.view.json", "target", "a")
    contract(views, "b.view.json", "target", "b")
    original = linkage.inspect_project_source
    calls: list[str] = []

    def inspect(root: Path, path: str):
        calls.append(path)
        return original(root, path)

    monkeypatch.setattr(linkage, "inspect_project_source", inspect)
    result = analyze_view_contract_links(root)
    assert calls == ["mvc/views/target"]
    assert result.templates[0].status == "ambiguous"


def test_issue_limit_and_pure_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, views = make_views(tmp_path)
    (views / "target").touch()
    for name in ("a", "b"):
        contract(views, name + ".view.json", "target")
    monkeypatch.setattr(linkage, "MAX_VIEW_CONTRACT_LINK_ISSUES", 4)
    result = analyze_view_contract_links(root)
    assert len(result.issues) == 4 and not result.truncated
    monkeypatch.setattr(linkage, "MAX_VIEW_CONTRACT_LINK_ISSUES", 3)
    limited = analyze_view_contract_links(root)
    assert len(limited.issues) == 3 and limited.truncated
    assert limited.issues[-1].code == "contract.link.analysis-truncated"

    def forbidden(*args: object, **kwargs: object) -> Any:
        raise AssertionError("projection did I/O")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    projected = linkage._project_links(  # pyright: ignore[reportPrivateUsage]
        ("target",), result.contracts, (), (), truncated=False, contracts_complete=True
    )
    assert projected == limited


def test_non_write_unicode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, views = make_views(tmp_path)
    config = tmp_path / "xdg"
    config.mkdir()
    (config / "state").write_text("unchanged")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    (root / "mvc/controllers").mkdir()
    (root / "mvc/controllers/a.py").write_text("raise AssertionError('never execute')")
    for i, name in enumerate(("é", "e\u0301", "😀 +&%#?")):
        (views / name).touch()
        contract(views, f"{i}.view.json", name, name)

    def snapshot():
        return {
            str(p): (p.read_bytes(), p.stat().st_size, p.stat().st_mtime_ns)
            for base in (root, config)
            for p in base.rglob("*")
            if p.is_file()
        }

    before = snapshot()
    result = analyze_view_contract_links(root)
    assert len(result.templates) == 3 and all(
        t.status == "linked" for t in result.templates
    )
    assert snapshot() == before
