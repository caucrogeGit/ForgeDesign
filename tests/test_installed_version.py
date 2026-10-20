"""Version forge-mvc installée dans .venv, confirmée par le commit déclaré
(FD-FORGE-005) : lecture confinée, sans lien suivi, sans exécution."""

import json
import os
from pathlib import Path

import pytest

from forge_design.forge.installed_version import read_installed_forge

COMMIT = "1af6301dbd4d33e09e9803a2a727036e9efe4509"


def install(
    root: Path,
    *,
    version: str = "1.0.0rc9",
    name: str = "forge-mvc",
    python: str = "python3.13",
    commit: str | None = COMMIT,
    direct_url: str | None = None,
) -> Path:
    """Arborescence pip réaliste ; retourne le dossier dist-info."""
    dist_info = root / f".venv/lib/{python}/site-packages/forge_mvc-{version}.dist-info"
    dist_info.mkdir(parents=True)
    (dist_info / "METADATA").write_text(
        f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n\n"
        "Version: 9.9.9 dans la description, ignorée.\n"
    )
    if direct_url is not None:
        (dist_info / "direct_url.json").write_text(direct_url)
    elif commit is not None:
        data = {
            "url": "https://github.com/caucrogeGit/Forge.git",
            "vcs_info": {"commit_id": commit, "vcs": "git"},
        }
        (dist_info / "direct_url.json").write_text(json.dumps(data))
    (dist_info / "RECORD").write_text("ne doit pas être lu")
    return dist_info


@pytest.mark.parametrize("declared", [COMMIT, COMMIT[:7]])
def test_match(tmp_path: Path, declared: str) -> None:
    install(tmp_path)
    other = tmp_path / ".venv/lib/python3.13/site-packages/jinja2-3.1.6.dist-info"
    other.mkdir()
    result = read_installed_forge(tmp_path.resolve(), declared)
    assert (result.status, result.version, result.detail) == ("match", "1.0.0rc9", "")


def test_version_is_normalised(tmp_path: Path) -> None:
    install(tmp_path, version="1.0.0RC9", name="Forge_MVC")
    assert read_installed_forge(tmp_path, COMMIT).version == "1.0.0rc9"


@pytest.mark.parametrize(
    ("options", "detail"),
    [
        ({"commit": "0" * 40}, "diffère du commit déclaré"),
        ({"commit": None}, "installé sans commit Git"),
        ({"direct_url": '{"url": "file:///src", "dir_info": {}}'}, "diffère"),
        ({"direct_url": '{"vcs_info": {"commit_id": "1af6301"}}'}, "diffère"),
        ({"direct_url": "[]"}, "diffère"),
    ],
)
def test_mismatch(tmp_path: Path, options: dict[str, str | None], detail: str) -> None:
    install(tmp_path, **options)  # pyright: ignore[reportArgumentType]
    result = read_installed_forge(tmp_path, COMMIT)
    assert result.status == "mismatch" and result.version is None
    assert detail in result.detail


def test_absent(tmp_path: Path) -> None:
    def status() -> tuple[str, str]:
        result = read_installed_forge(tmp_path, COMMIT)
        assert result.version is None
        return result.status, result.detail

    assert status() == ("absent", "Environnement .venv absent.")
    (tmp_path / ".venv").mkdir()
    assert status() == ("absent", "Environnement .venv sans dossier lib.")
    (tmp_path / ".venv/lib/python3.13/site-packages").mkdir(parents=True)
    (tmp_path / ".venv/lib/python3.12").mkdir()
    (tmp_path / ".venv/lib/pythonX").mkdir()
    assert status() == ("absent", "forge-mvc n'est pas installé dans .venv.")


@pytest.mark.parametrize("second", ["python3.12", "same"])
def test_several_installations(tmp_path: Path, second: str) -> None:
    install(tmp_path)
    if second == "same":
        install(tmp_path, version="1.0.0")
    else:
        install(tmp_path, python=second)
    result = read_installed_forge(tmp_path, COMMIT)
    assert result.status == "unreadable"
    assert result.detail == "Plusieurs installations de forge-mvc dans .venv."


@pytest.mark.parametrize(
    ("metadata", "detail"),
    [
        (b"Name: jinja2\nVersion: 1.0\n", "incohérentes"),
        (b"Version: 1.0\n", "incohérentes"),
        (b"Name: forge-mvc\nVersion: pas une version\n", "illisibles"),
        (b"Name: forge-mvc\n", "illisibles"),
        (b"Name: forge-mvc\nVersion: \xff\n", "illisibles"),
        (b"Name: forge-mvc\nVersion: 1.0\n" + b"x" * 300_000, "trop volumineuse"),
    ],
)
def test_unreadable_metadata(tmp_path: Path, metadata: bytes, detail: str) -> None:
    (install(tmp_path) / "METADATA").write_bytes(metadata)
    result = read_installed_forge(tmp_path, COMMIT)
    assert result.status == "unreadable" and result.version is None
    assert detail in result.detail


def test_unreadable_direct_url(tmp_path: Path) -> None:
    install(tmp_path, direct_url="{pas du json")
    assert read_installed_forge(tmp_path, COMMIT).status == "unreadable"
    (tmp_path / ".venv").rename(tmp_path / "old")
    install(tmp_path, direct_url="x" * (65 * 1024))
    assert "trop volumineuse" in read_installed_forge(tmp_path, COMMIT).detail


def test_links_are_never_followed(tmp_path: Path) -> None:
    elsewhere = tmp_path / "ailleurs"
    elsewhere.mkdir()
    install(elsewhere)
    project = tmp_path / "projet"
    project.mkdir()
    # .venv lié : refusé, même s'il pointe vers une installation valide.
    (project / ".venv").symlink_to(elsewhere / ".venv")
    result = read_installed_forge(project, COMMIT)
    assert result.status == "unreadable" and "lié" in result.detail
    (project / ".venv").unlink()
    # dist-info lié : ignoré, comme absent.
    site = project / ".venv/lib/python3.13/site-packages"
    site.mkdir(parents=True)
    source = (
        elsewhere / ".venv/lib/python3.13/site-packages/forge_mvc-1.0.0rc9.dist-info"
    )
    (site / source.name).symlink_to(source)
    assert read_installed_forge(project, COMMIT).status == "absent"
    (site / source.name).unlink()
    # METADATA lié : refusé.
    dist_info = install(project)
    (dist_info / "METADATA").unlink()
    (dist_info / "METADATA").symlink_to(source / "METADATA")
    result = read_installed_forge(project, COMMIT)
    assert result.status == "unreadable" and "liée" in result.detail
    (dist_info / "METADATA").unlink()
    (dist_info / "METADATA").write_text((source / "METADATA").read_text())
    # Dossier python3.x lié : ignoré ; site-packages lié : refusé.
    (project / ".venv/lib/python3.12").symlink_to(elsewhere / ".venv/lib/python3.13")
    assert read_installed_forge(project, COMMIT).status == "match"
    site.rename(project / "site-packages-hors-venv")
    site.symlink_to(elsewhere / ".venv/lib/python3.13/site-packages")
    assert read_installed_forge(project, COMMIT).status == "unreadable"


def test_reads_only_the_two_metadata_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install(tmp_path)
    (tmp_path / "app.py").write_text("raise AssertionError('must not execute')")

    def snapshot() -> dict[str, tuple[int, bytes | None]]:
        return {
            str(p): (p.stat().st_mtime_ns, p.read_bytes() if p.is_file() else None)
            for p in tmp_path.rglob("*")
        }

    before = snapshot()
    original = os.open
    opened: list[str] = []

    def guarded(path: str, flags: int, *args: object, **kwargs: object) -> int:
        opened.append(os.fspath(path))
        return original(path, flags, *args, **kwargs)  # pyright: ignore[reportArgumentType]

    with monkeypatch.context() as patch:
        patch.setattr(os, "open", guarded)
        patch.setattr(os, "supports_dir_fd", os.supports_dir_fd | {guarded})
        result = read_installed_forge(tmp_path.resolve(), COMMIT)
    assert result.status == "match"
    files = [name for name in opened if name in {"METADATA", "direct_url.json"}]
    assert files == ["METADATA", "direct_url.json"]
    assert "RECORD" not in opened and "app.py" not in opened
    chain = [*tmp_path.resolve().parts[1:], ".venv", "lib", "python3.13"]
    chain += ["site-packages", "forge_mvc-1.0.0rc9.dist-info"]
    assert opened == [tmp_path.resolve().parts[0], *chain, *files]
    assert snapshot() == before
