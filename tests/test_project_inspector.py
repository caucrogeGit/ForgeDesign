"""Composition réelle du Bridge sur des projets temporaires locaux."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from forge_design.forge.project_detection import detect_forge_project
from forge_design.forge.project_root import (
    ProjectRootNotDirectoryError,
    ProjectRootNotFoundError,
    ProjectRootResolutionError,
)
from forge_design.forge.project_version import read_forge_version
from forge_design.tools import project_inspector
from forge_design.tools.project_inspector import inspect_project


@pytest.fixture
def project(tmp_path: Path) -> Path:
    for name in ("app.py", "bootstrap.py", "config.py"):
        (tmp_path / name).write_text("raise AssertionError('must not execute')")
    for name in (
        "routes",
        "controllers",
        "entities",
        "forms",
        "helpers",
        "models",
        "validators",
        "views",
    ):
        (tmp_path / "mvc" / name).mkdir(parents=True)
    (tmp_path / "requirements.txt").write_text("forge-mvc==1.0.0rc9")
    return tmp_path


def test_valid_version(project: Path) -> None:
    result = inspect_project(project)
    assert result.root == project.resolve()
    assert result.valid
    assert result.forge_version == "1.0.0rc9"
    assert result.forge_version_source == "requirements.txt"
    assert result.errors == result.warnings == ()
    assert result == inspect_project(project)
    with pytest.raises(FrozenInstanceError):
        setattr(result, "valid", False)


@pytest.mark.parametrize("content", [None, "jinja2==3.1.6", "forge-mvc>=1.0"])
def test_version_absent(project: Path, content: str | None) -> None:
    source = project / "requirements.txt"
    if content is None:
        source.unlink()
    else:
        source.write_text(content)
    result = inspect_project(project)
    version = read_forge_version(project)
    assert result.valid and result.errors == ()
    assert result.forge_version is None
    assert result.forge_version_source == version.source
    assert (
        result.warnings
        == ("Version Forge absente ou indéterminable.",) + version.details
    )


def test_structure_warnings(project: Path) -> None:
    (project / "mvc/views").rmdir()
    result = inspect_project(project)
    assert result.valid and result.forge_version == "1.0.0rc9"
    assert result.errors == ()
    assert result.warnings == detect_forge_project(project).warnings


def test_invalid_structure_skips_version(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (project / "app.py").unlink()
    (project / "mvc/views").rmdir()

    def forbidden(root: Path) -> None:
        raise AssertionError("Version must not be read for an invalid project")

    monkeypatch.setattr(project_inspector, "read_forge_version", forbidden)
    result = inspect_project(project)
    structure = detect_forge_project(project)
    assert not result.valid
    assert result.root == project.resolve()
    assert result.forge_version is result.forge_version_source is None
    assert result.errors == structure.errors
    assert result.warnings == structure.warnings


def test_missing_root(tmp_path: Path) -> None:
    with pytest.raises(ProjectRootNotFoundError):
        inspect_project(tmp_path / "missing")


def test_file_root(tmp_path: Path) -> None:
    target = tmp_path / "file"
    target.touch()
    with pytest.raises(ProjectRootNotDirectoryError):
        inspect_project(target)


def test_impossible_resolution() -> None:
    with pytest.raises(ProjectRootResolutionError):
        inspect_project("")


@pytest.mark.parametrize(
    "content, message",
    [
        (
            "forge-mvc==1.0\nforge-mvc==2.0",
            "Déclarations de version Forge contradictoires.",
        ),
        ("forge-mvc==invalid", "Version Forge illisible."),
    ],
)
def test_version_problem(project: Path, content: str, message: str) -> None:
    (project / "requirements.txt").write_text(content)
    (project / "mvc/views").rmdir()
    result = inspect_project(project)
    assert result.valid and result.errors == ()
    assert result.forge_version is None
    assert result.forge_version_source == "requirements.txt"
    assert result.warnings == (
        detect_forge_project(project).warnings
        + (message,)
        + read_forge_version(project).details
    )


def test_canonical_root(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    alias = project / "alias"
    alias.symlink_to(project, target_is_directory=True)
    monkeypatch.chdir(project)
    assert inspect_project("./mvc/..").root == project.resolve()
    assert inspect_project(alias) == inspect_project(project)


def test_no_compatibility_decision(project: Path) -> None:
    (project / "requirements.txt").write_text("forge-mvc==99.0.0")
    result = inspect_project(project)
    assert result.valid and result.forge_version == "99.0.0"
    assert result.errors == result.warnings == ()


def test_no_modification(project: Path) -> None:
    (project / ".env").write_text("fake secret")

    def snapshot() -> dict[str, tuple[int, int, bytes | None]]:
        return {
            str(p.relative_to(project)): (
                p.stat().st_mode,
                p.stat().st_mtime_ns,
                p.read_bytes() if p.is_file() else None,
            )
            for p in project.rglob("*")
        }

    before = snapshot()
    inspect_project(project)
    assert snapshot() == before
    assert not (project / ".forge-design").exists()


def test_unexpected_bridge_error_propagated(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(root: Path) -> None:
        raise RuntimeError("bridge failure")

    monkeypatch.setattr(project_inspector, "read_forge_version", broken)
    with pytest.raises(RuntimeError, match="bridge failure"):
        inspect_project(project)


def test_unreadable_version_source(project: Path) -> None:
    source = project / "requirements.txt"
    source.unlink()
    source.mkdir()
    result = inspect_project(project)
    assert result.valid and result.errors == ()
    assert result.forge_version is None
    assert result.forge_version_source == "requirements.txt"
    assert (
        result.warnings
        == ("Version Forge illisible.",) + read_forge_version(project).details
    )
