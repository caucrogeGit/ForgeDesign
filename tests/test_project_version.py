"""Contrat de lecture de version déclarée, sans exécution du projet."""

import os
from pathlib import Path

import pytest

from forge_design.forge.project_root import ProjectRootNotFoundError
from forge_design.forge.project_version import NotForgeProjectError, read_forge_version


@pytest.fixture
def project(tmp_path: Path) -> Path:
    for name in ("app.py", "bootstrap.py", "config.py"):
        (tmp_path / name).write_text("raise AssertionError('must not execute')")
    (tmp_path / "mvc/routes").mkdir(parents=True)
    return tmp_path


@pytest.mark.parametrize("version", ["1.0.0rc9", "2.5.0", "1.2.dev3", "1!2.0+local"])
def test_version(project: Path, version: str) -> None:
    (project / "requirements.txt").write_text(f"forge-mvc=={version}\n")
    result = read_forge_version(project)
    assert result.status == "found"
    assert result.version == version
    assert result.source == "requirements.txt"
    assert result.details == ()


def test_missing_source(project: Path) -> None:
    result = read_forge_version(project)
    assert result.status == "absent"
    assert result.version is None and result.source is None


@pytest.mark.parametrize(
    "content", ["", "# forge-mvc==1.0\n", "jinja2==3.1.6", "forge-mvc-entities==1.0"]
)
def test_no_declaration(project: Path, content: str) -> None:
    (project / "requirements.txt").write_text(content)
    result = read_forge_version(project)
    assert result.status == "absent"
    assert result.version is None and result.source == "requirements.txt"


@pytest.mark.parametrize(
    "content",
    ["forge-mvc==invalid", "forge-mvc=1.0", "forge-mvc==", "forge-mvc==1.0; broken"],
)
def test_invalid_format(project: Path, content: str) -> None:
    (project / "requirements.txt").write_text(content)
    result = read_forge_version(project)
    assert result.status == "unreadable"
    assert result.version is None
    assert result.details == ("Ligne 1 : déclaration Forge invalide.",)


@pytest.mark.parametrize(
    "content",
    [
        "forge-mvc>=1.0",
        "forge-mvc",
        "forge-mvc==1.*",
        "forge-mvc===custom",
        'forge-mvc==1.0; python_version >= "3.12"',
        "forge-mvc @ git+https://example.invalid/Forge.git@abcdef",
        "forge-mvc==1.0\nforge-mvc>=2.0",
    ],
)
def test_no_unique_unconditional_version(project: Path, content: str) -> None:
    (project / "requirements.txt").write_text(content)
    result = read_forge_version(project)
    assert result.status == "absent" and result.version is None
    assert result.source == "requirements.txt" and result.details


@pytest.mark.parametrize(
    "content",
    [
        "forge-mvc==1.0rc9\nforge-mvc==1.0rc9",
        "forge-mvc==1.0rc9\nForge_MVC==1.0RC9",
        "\ufeff  Forge.MVC[all] == 1.0rc9  # comment\n",
        "forge-mvc==1.0rc9,==1.0.0rc9",
    ],
)
def test_consistent_declarations(project: Path, content: str) -> None:
    (project / "requirements.txt").write_text(content, encoding="utf-8")
    result = read_forge_version(project)
    assert result.status == "found" and result.version is not None
    assert result == read_forge_version(project)


@pytest.mark.parametrize(
    "content",
    [
        "forge-mvc==1.0\nforge-mvc==2.0",
        "forge-mvc==1.0,==2.0",
    ],
)
def test_conflicting_declarations(project: Path, content: str) -> None:
    (project / "requirements.txt").write_text(content)
    result = read_forge_version(project)
    assert result.status == "conflict" and result.version is None
    assert result.source == "requirements.txt" and result.details


@pytest.mark.parametrize(
    "directive",
    [
        "-r .env",
        "--requirement=env/dev",
        "-c constraints.txt",
        "-e .",
        "forge-mvc==1.0 \\",
    ],
)
def test_no_indirection(project: Path, directive: str) -> None:
    (project / "requirements.txt").write_text(directive)
    assert read_forge_version(project).status == "unreadable"


@pytest.mark.parametrize("kind", ["directory", "symlink", "dangling", "fifo"])
def test_unsafe_source(
    project: Path, kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = project / "requirements.txt"
    if kind == "directory":
        source.mkdir()
    elif kind == "fifo":
        os.mkfifo(source)
    else:
        target = project / ".env"
        if kind == "symlink":
            target.write_text("secret")
        source.symlink_to(target)

    def forbidden(*args: object, **kwargs: object) -> int:
        raise AssertionError("Unsafe source must not be opened")

    monkeypatch.setattr(os, "open", forbidden)
    assert read_forge_version(project).status == "unreadable"


def test_permission_error(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (project / "requirements.txt").touch()

    def denied(*args: object, **kwargs: object) -> int:
        raise PermissionError

    monkeypatch.setattr(os, "open", denied)
    assert read_forge_version(project).status == "unreadable"


@pytest.mark.parametrize("content", [b"\xff", b"x" * (1024 * 1024 + 1)])
def test_encoding_and_size(project: Path, content: bytes) -> None:
    (project / "requirements.txt").write_bytes(content)
    assert read_forge_version(project).status == "unreadable"


def test_root_validation(tmp_path: Path) -> None:
    with pytest.raises(NotForgeProjectError):
        read_forge_version(tmp_path)
    with pytest.raises(ProjectRootNotFoundError):
        read_forge_version(tmp_path / "missing")


def test_only_source_read_and_no_mutation(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = project / "requirements.txt"
    source.write_text("forge-mvc==1.0.0rc9")
    (project / "pyproject.toml").write_text('[project]\nversion = "9.9.9"')
    (project / ".env").write_text("secret")
    (project / "env").mkdir()
    (project / "env/dev").write_text("secret")

    def snapshot() -> dict[str, tuple[int, bytes | None]]:
        return {
            str(p): (p.stat().st_mtime_ns, p.read_bytes() if p.is_file() else None)
            for p in project.rglob("*")
        }

    before = snapshot()
    original = os.open
    opened: list[str] = []

    def guarded(path: str | os.PathLike[str], flags: int) -> int:
        assert Path(path) == source
        opened.append(str(path))
        return original(path, flags)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Unexpected content read or traversal")

    with monkeypatch.context() as patch:
        patch.setattr(os, "open", guarded)
        patch.setattr(Path, "open", forbidden)
        patch.setattr(Path, "rglob", forbidden)
        patch.setattr(Path, "iterdir", forbidden)
        result = read_forge_version(project)
    assert result.version == "1.0.0rc9"
    assert opened == [str(source)]
    assert snapshot() == before


def test_source_replaced_before_open(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = project / "requirements.txt"
    source.write_text("forge-mvc==1.0")
    replacement = project / "replacement"
    replacement.write_text("forge-mvc==2.0")
    original = os.open

    def replaced(path: str | os.PathLike[str], flags: int) -> int:
        replacement.replace(source)
        return original(path, flags)

    monkeypatch.setattr(os, "open", replaced)
    result = read_forge_version(project)
    assert result.status == "unreadable" and result.version is None
    assert result.details == ("Source modifiée pendant l'accès.",)


def test_root_symlink(project: Path) -> None:
    (project / "requirements.txt").write_text("forge-mvc==1.0rc9")
    alias = project / "alias"
    alias.symlink_to(project, target_is_directory=True)
    assert read_forge_version(alias) == read_forge_version(project)


def test_invalid_declaration_takes_precedence(project: Path) -> None:
    (project / "requirements.txt").write_text(
        "forge-mvc==1.0\nforge-mvc==2.0\nforge-mvc==invalid"
    )
    result = read_forge_version(project)
    assert result.status == "unreadable" and result.version is None
