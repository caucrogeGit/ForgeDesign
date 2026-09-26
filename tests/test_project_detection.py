"""Signatures, limites de lecture et diagnostic du Bridge."""

from pathlib import Path

import pytest

from forge_design.forge.project_detection import detect_forge_project
from forge_design.forge.project_root import ProjectRootNotFoundError

REQUIRED_FILES = ("app.py", "bootstrap.py", "config.py")
OPTIONAL = (
    "controllers",
    "entities",
    "forms",
    "helpers",
    "models",
    "validators",
    "views",
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    for name in REQUIRED_FILES:
        (tmp_path / name).touch()
    (tmp_path / "mvc/routes").mkdir(parents=True)
    return tmp_path


def test_minimal(project: Path) -> None:
    result = detect_forge_project(project)
    assert result.valid
    assert result.errors == ()
    assert result.warnings == tuple(f"mvc/{name} : absent." for name in OPTIONAL)
    assert result == detect_forge_project(project)


@pytest.mark.parametrize("name", (*REQUIRED_FILES, "mvc/routes", "mvc"))
@pytest.mark.parametrize("wrong_type", (False, True))
def test_required(project: Path, name: str, wrong_type: bool) -> None:
    target = project / name
    if name == "mvc":
        (target / "routes").rmdir()
    if target.is_dir():
        target.rmdir()
        if wrong_type:
            target.touch()
    else:
        target.unlink()
        if wrong_type:
            target.mkdir()
    result = detect_forge_project(project)
    assert not result.valid
    assert len(result.errors) == 1
    assert result.errors[0].startswith(f"{name} : ")
    assert ("type incorrect" if wrong_type else "absent") in result.errors[0]


def test_complete_and_extra(project: Path) -> None:
    for name in OPTIONAL:
        (project / "mvc" / name).mkdir()
    (project / "custom/deep").mkdir(parents=True)
    result = detect_forge_project(project)
    assert result.valid and result.errors == () and result.warnings == ()


@pytest.mark.parametrize("destination", ("outside", "missing", "self", "inside"))
@pytest.mark.parametrize("name", ("app.py", "mvc/routes", "mvc"))
def test_symlinks(
    project: Path, tmp_path_factory: pytest.TempPathFactory, destination: str, name: str
) -> None:
    target = project / name
    if name == "mvc":
        (target / "routes").rmdir()
    if target.is_dir():
        target.rmdir()
    else:
        target.unlink()
    destinations = {
        "outside": tmp_path_factory.mktemp("outside"),
        "missing": project / "missing",
        "self": target,
        "inside": project / "config.py",
    }
    target.symlink_to(destinations[destination])
    result = detect_forge_project(project)
    assert not result.valid
    assert result.errors == (f"{name} : lien symbolique non accepté.",)


def test_optional_wrong_type(project: Path) -> None:
    (project / "mvc/views").touch()
    result = detect_forge_project(project)
    assert result.valid
    assert "type incorrect" in result.warnings[-1]


def test_resolution(project: Path) -> None:
    link = project / "alias"
    link.symlink_to(project, target_is_directory=True)
    assert detect_forge_project(link) == detect_forge_project(project)
    with pytest.raises(ProjectRootNotFoundError):
        detect_forge_project(project / "missing")


def test_no_content_read_or_mutation(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (project / "app.py").write_text("raise AssertionError('must not import')")
    (project / ".env").write_text("secret")
    (project / "env").mkdir()
    (project / "env/dev").write_text("secret")

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

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Content access or traversal forbidden")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", forbidden)
        patch.setattr(Path, "iterdir", forbidden)
        patch.setattr(Path, "rglob", forbidden)
        assert detect_forge_project(project).valid
    assert snapshot() == before


def test_unreadable_signature(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = Path.lstat

    def denied(path: Path) -> object:
        if path == project / "app.py":
            raise PermissionError
        return original(path)

    monkeypatch.setattr(Path, "lstat", denied)
    result = detect_forge_project(project)
    assert result.errors == ("app.py : impossible de vérifier le type.",)
