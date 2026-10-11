"""Inventaire des migrations : entrées directes, noms et tailles seulement, aucun
contenu SQL ouvert ni exécuté, aucun lien suivi."""

import builtins
import os
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from test_web_recent_projects import project

import forge_design.forge.migrations as module
from forge_design.forge.migrations import (
    MigrationInfo,
    MigrationsResult,
    read_migrations,
)
from forge_design.forge.project_root import ProjectRootNotFoundError
from forge_design.forge.project_version import NotForgeProjectError


def folder(tmp_path: Path) -> tuple[Path, Path]:
    root = project(tmp_path / "projet").resolve()
    migrations = root / "mvc/migrations"
    migrations.mkdir()
    return root, migrations


def test_absent_folder_is_not_an_anomaly(tmp_path: Path) -> None:
    root = project(tmp_path / "projet")
    assert read_migrations(root) == MigrationsResult((), (), False, False)


def test_empty_folder(tmp_path: Path) -> None:
    root, _ = folder(tmp_path)
    assert read_migrations(root) == MigrationsResult((), (), True, False)


def test_inventory_names_sizes_and_issues(tmp_path: Path) -> None:
    root, migrations = folder(tmp_path)
    (migrations / "20260102120000_second.sql").write_text("SELECT 2;")
    (migrations / "20260101120000_first.sql").write_text("SELECT 1;")
    (migrations / "2026_bad.sql").write_text("SELECT 3;")
    (migrations / "20260103120000_empty.sql").touch()
    (migrations / "README.md").write_text("ignoré")
    (migrations / "archive").mkdir()
    (migrations / "archive/20250101120000_old.sql").write_text(
        "non lu : pas de récursion"
    )
    result = read_migrations(root)
    assert result.migrations == (
        MigrationInfo("20260101120000_first.sql", 9),
        MigrationInfo("20260102120000_second.sql", 9),
        MigrationInfo("20260103120000_empty.sql", 0),
        MigrationInfo("2026_bad.sql", 9),
    )
    assert [(issue.code, issue.name) for issue in result.issues] == [
        ("migration.empty", "20260103120000_empty.sql"),
        ("migration.name_invalid", "2026_bad.sql"),
    ]
    assert result.source_present and not result.truncated
    with pytest.raises(FrozenInstanceError):
        result.truncated = True  # pyright: ignore[reportAttributeAccessIssue]


@pytest.mark.parametrize(
    "name",
    [
        "20260101120000_.sql",
        "2026010112000_short.sql",
        "20260101120000-dash.sql",
        "20260101120000_with space.sql",
        "20260101120000_é.sql",
        "20260101120000_name.SQL.sql.bak.sql",
    ],
)
def test_naming_convention(tmp_path: Path, name: str) -> None:
    root, migrations = folder(tmp_path)
    (migrations / name).write_text("x")
    codes = [issue.code for issue in read_migrations(root).issues]
    assert codes == ["migration.name_invalid"]


def test_links_are_never_followed(tmp_path: Path) -> None:
    root, migrations = folder(tmp_path)
    outside = tmp_path / "outside.sql"
    outside.write_text("DROP TABLE secret;")
    (migrations / "20260101120000_link.sql").symlink_to(outside)
    (migrations / "20260101120001_dir.sql").mkdir()
    result = read_migrations(root)
    assert result.migrations == ()
    assert [(issue.code, issue.message) for issue in result.issues] == [
        ("migration.not_regular", "Migration ignorée : lien symbolique."),
        ("migration.not_regular", "Migration ignorée : entrée non ordinaire."),
    ]


def test_linked_or_invalid_folder_is_reported(tmp_path: Path) -> None:
    root = project(tmp_path / "projet").resolve()
    target = tmp_path / "elsewhere"
    target.mkdir()
    (target / "20260101120000_x.sql").write_text("x")
    (root / "mvc/migrations").symlink_to(target)
    result = read_migrations(root)
    assert result.migrations == () and result.source_present
    assert [issue.code for issue in result.issues] == ["migration.unreadable"]
    (root / "mvc/migrations").unlink()
    (root / "mvc/migrations").write_text("pas un dossier")
    assert [i.code for i in read_migrations(root).issues] == ["migration.unreadable"]


def test_no_sql_content_is_opened(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, migrations = folder(tmp_path)
    secret = migrations / "20260101120000_locked.sql"
    secret.write_text("SELECT secret;")
    secret.chmod(0)
    opened: list[str] = []
    real_open = os.open

    def watched(path: object, *args: object, **kwargs: object) -> int:
        opened.append(str(path))
        return real_open(path, *args, **kwargs)  # type: ignore[arg-type]

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("aucun fichier ouvert par open()")

    monkeypatch.setattr(os, "open", watched)
    monkeypatch.setattr(builtins, "open", forbidden)
    try:
        result = read_migrations(root)
    finally:
        secret.chmod(0o600)
    assert result.migrations == (MigrationInfo("20260101120000_locked.sql", 14),)
    assert not any(path.endswith(".sql") for path in opened)


def test_inventory_is_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, migrations = folder(tmp_path)
    for index in range(5):
        (migrations / f"2026010112000{index}_m.sql").write_text("x")
    monkeypatch.setattr(module, "MAX_MIGRATION_DIRECTORY_ENTRIES", 3)
    result = read_migrations(root)
    assert result.truncated and len(result.migrations) == 3
    assert result.issues[-1].code == "migration.analysis_truncated"


def test_root_errors(tmp_path: Path) -> None:
    with pytest.raises(NotForgeProjectError):
        read_migrations(tmp_path)
    with pytest.raises(ProjectRootNotFoundError):
        read_migrations(tmp_path / "absent")


def test_nothing_is_written(tmp_path: Path) -> None:
    root, migrations = folder(tmp_path)
    (migrations / "20260101120000_x.sql").write_text("x")
    before = {p: p.stat().st_mtime_ns for p in root.rglob("*")}
    read_migrations(root)
    assert {p: p.stat().st_mtime_ns for p in root.rglob("*")} == before
