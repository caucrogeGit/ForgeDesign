"""Signatures, limites de lecture et diagnostic du Bridge."""

from pathlib import Path

import pytest

from forge_design.forge.project_detection import StructureEntry, detect_forge_project
from forge_design.forge.project_root import ProjectRootNotFoundError

REQUIRED_FILES = ("app.py", "config.py")
# Optionnel pour forge-mvc 1.0.0rc9 (load_bootstrap, ADR-093) : FD-FORGE-004.
BOOTSTRAP = "bootstrap.py"
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
    for name in (*REQUIRED_FILES, BOOTSTRAP):
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
@pytest.mark.parametrize("bootstrap", (True, False))
def test_required(project: Path, name: str, wrong_type: bool, bootstrap: bool) -> None:
    """Les quatre marqueurs restent obligatoires, avec ou sans bootstrap.py."""
    if not bootstrap:
        (project / BOOTSTRAP).unlink()
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


def test_structured_entries_match_the_messages(project: Path) -> None:
    """FD-PROJECT-006 : état structuré de chaque élément, messages inchangés."""
    from forge_design.forge.project_detection import OPTIONAL_MVC_DIRECTORIES

    assert OPTIONAL_MVC_DIRECTORIES == OPTIONAL
    (project / "mvc/views").mkdir()
    (project / "mvc/forms").write_text("pas un dossier")
    (project / "mvc/models").symlink_to(project / "mvc/views")
    result = detect_forge_project(project)
    assert result.entries == (
        StructureEntry("app.py", True, "present"),
        StructureEntry("bootstrap.py", False, "present", strict=True),
        StructureEntry("config.py", True, "present"),
        StructureEntry("mvc", True, "present"),
        StructureEntry("mvc/routes", True, "present"),
        StructureEntry("mvc/controllers", False, "absent"),
        StructureEntry("mvc/entities", False, "absent"),
        StructureEntry("mvc/forms", False, "invalid"),
        StructureEntry("mvc/helpers", False, "absent"),
        StructureEntry("mvc/models", False, "invalid"),
        StructureEntry("mvc/validators", False, "absent"),
        StructureEntry("mvc/views", False, "present"),
    )
    assert result.warnings == (
        "mvc/controllers : absent.",
        "mvc/entities : absent.",
        "mvc/forms : type incorrect, dossier attendu.",
        "mvc/helpers : absent.",
        "mvc/models : lien symbolique non accepté.",
        "mvc/validators : absent.",
    )
    (project / "app.py").unlink()
    (project / "mvc/routes").rmdir()
    (project / "mvc/routes").symlink_to(project / "mvc/views")
    broken = detect_forge_project(project)
    assert broken.errors == (
        "app.py : absent.",
        "mvc/routes : lien symbolique non accepté.",
    )
    assert broken.entries[0] == StructureEntry("app.py", True, "absent")
    assert broken.entries[4] == StructureEntry("mvc/routes", True, "invalid")


def test_entries_stop_when_mvc_is_invalid(project: Path) -> None:
    import shutil

    shutil.rmtree(project / "mvc")
    entries = detect_forge_project(project).entries
    assert [(entry.label, entry.state) for entry in entries][-1] == ("mvc", "absent")
    assert len(entries) == 4


# FD-FORGE-004 : bootstrap.py est optionnel (forge-mvc 1.0.0rc9, load_bootstrap,
# ADR-093) ; app.py, config.py, mvc/ et mvc/routes/ restent obligatoires.


def test_project_without_bootstrap_is_recognized(project: Path) -> None:
    (project / BOOTSTRAP).unlink()
    result = detect_forge_project(project)
    assert result.valid
    assert result.errors == ()
    # Aucun message pour cette absence : ni erreur, ni avertissement.
    assert result.warnings == tuple(f"mvc/{name} : absent." for name in OPTIONAL)
    assert "bootstrap.py : absent." not in (*result.errors, *result.warnings)
    assert result.entries[1] == StructureEntry(BOOTSTRAP, False, "absent", strict=True)
    assert [entry.label for entry in result.entries if entry.required] == [
        "app.py",
        "config.py",
        "mvc",
        "mvc/routes",
    ]


def test_present_bootstrap_is_shown_as_optional(project: Path) -> None:
    result = detect_forge_project(project)
    assert result.valid and result.errors == ()
    assert result.entries[1] == StructureEntry(BOOTSTRAP, False, "present", strict=True)
    assert result == detect_forge_project(project)


@pytest.mark.parametrize(
    ("kind", "message"),
    (
        ("directory", "bootstrap.py : type incorrect, fichier ordinaire attendu."),
        ("fifo", "bootstrap.py : type incorrect, fichier ordinaire attendu."),
        ("outside", "bootstrap.py : lien symbolique non accepté."),
        ("missing", "bootstrap.py : lien symbolique non accepté."),
        ("self", "bootstrap.py : lien symbolique non accepté."),
        ("inside", "bootstrap.py : lien symbolique non accepté."),
    ),
)
def test_invalid_bootstrap_is_still_refused(
    project: Path,
    tmp_path_factory: pytest.TempPathFactory,
    kind: str,
    message: str,
) -> None:
    """Optionnel quand il manque, jamais un faux fichier ordinaire quand il existe."""
    import os

    target = project / BOOTSTRAP
    target.unlink()
    if kind == "directory":
        target.mkdir()
    elif kind == "fifo":
        os.mkfifo(target)
    else:
        outside = tmp_path_factory.mktemp("outside") / "bootstrap.py"
        outside.touch()
        destinations = {
            "outside": outside,
            "missing": project / "missing.py",
            "self": target,
            "inside": project / "config.py",
        }
        target.symlink_to(destinations[kind])
    result = detect_forge_project(project)
    assert not result.valid
    assert result.errors == (message,)
    assert result.entries[1] == StructureEntry(BOOTSTRAP, False, "invalid", strict=True)


def test_unverifiable_bootstrap_is_refused(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Path.lstat

    def denied(path: Path) -> object:
        if path == project / BOOTSTRAP:
            raise PermissionError
        return original(path)

    monkeypatch.setattr(Path, "lstat", denied)
    result = detect_forge_project(project)
    assert not result.valid
    assert result.errors == ("bootstrap.py : impossible de vérifier le type.",)


@pytest.mark.parametrize("bootstrap", (True, False))
def test_same_stat_calls_without_content_access(
    project: Path, monkeypatch: pytest.MonkeyPatch, bootstrap: bool
) -> None:
    """Aucun parcours ni lecture ajoutés : un lstat par élément, présent ou non."""
    if not bootstrap:
        (project / BOOTSTRAP).unlink()
    original = Path.lstat
    calls: list[Path] = []

    def counted(path: Path) -> object:
        calls.append(path)
        return original(path)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Content access or traversal forbidden")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", counted)
        patch.setattr(Path, "open", forbidden)
        patch.setattr(Path, "iterdir", forbidden)
        patch.setattr(Path, "rglob", forbidden)
        result = detect_forge_project(project)
    assert result.valid
    checked = [path for path in calls if path.is_relative_to(project.resolve())]
    assert len(checked) == len(result.entries) == 12
    assert project.resolve() / BOOTSTRAP in checked


def test_real_forge_skeleton_without_bootstrap(tmp_path: Path) -> None:
    """Squelette réellement installé (forge-mvc 1.0.0rc9), avec puis sans bootstrap."""
    import shutil
    from importlib.util import find_spec

    spec = find_spec("skeleton")
    assert spec is not None and spec.submodule_search_locations
    source = Path(next(iter(spec.submodule_search_locations))) / "data"
    assert (source / BOOTSTRAP).is_file()
    copy = tmp_path / "squelette"
    shutil.copytree(source, copy, symlinks=True)
    assert detect_forge_project(copy).valid
    (copy / BOOTSTRAP).unlink()
    result = detect_forge_project(copy)
    assert result.valid and result.errors == ()
    assert result.entries[1] == StructureEntry(BOOTSTRAP, False, "absent", strict=True)
