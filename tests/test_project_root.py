"""Contrat de canonisation de la racine, sans fixture métier Forge."""

from pathlib import Path

import pytest

from forge_design.forge.project_root import (
    ProjectRootNotDirectoryError,
    ProjectRootNotFoundError,
    ProjectRootResolutionError,
    resolve_project_root,
)


def test_absolute_directory(tmp_path: Path) -> None:
    assert resolve_project_root(tmp_path) == tmp_path.resolve()


def test_relative_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "project").mkdir()
    monkeypatch.chdir(tmp_path)
    assert resolve_project_root("project") == (tmp_path / "project").resolve()


def test_parent_components(tmp_path: Path) -> None:
    (tmp_path / "child").mkdir()
    assert resolve_project_root(tmp_path / "child" / "..") == tmp_path.resolve()


def test_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(ProjectRootNotFoundError, match="n'existe pas"):
        resolve_project_root(tmp_path / "missing")


def test_file_rejected(tmp_path: Path) -> None:
    target = tmp_path / "file"
    target.touch()
    with pytest.raises(ProjectRootNotDirectoryError, match="pas un dossier"):
        resolve_project_root(target)


def test_file_as_parent_rejected(tmp_path: Path) -> None:
    target = tmp_path / "file"
    target.touch()
    with pytest.raises(ProjectRootNotDirectoryError):
        resolve_project_root(target / "child")


def test_root_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    root = resolve_project_root(link)
    assert root == target.resolve()
    assert root.is_absolute()
    assert not root.is_symlink()
    assert resolve_project_root(root) == root
    assert resolve_project_root(str(link)) == root
    assert list(target.iterdir()) == []


def test_dangling_symlink(tmp_path: Path) -> None:
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "missing")
    with pytest.raises(ProjectRootNotFoundError):
        resolve_project_root(link)


def test_symlink_loop(tmp_path: Path) -> None:
    link = tmp_path / "loop"
    link.symlink_to(link)
    with pytest.raises(ProjectRootResolutionError):
        resolve_project_root(link)


@pytest.mark.parametrize("path", ["", "invalid\x00path"])
def test_invalid_path(path: str) -> None:
    with pytest.raises(ProjectRootResolutionError):
        resolve_project_root(path)


def test_permission_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(self: Path, strict: bool = False) -> Path:
        raise PermissionError("access denied")

    monkeypatch.setattr(Path, "resolve", denied)
    with pytest.raises(ProjectRootResolutionError):
        resolve_project_root(tmp_path)
