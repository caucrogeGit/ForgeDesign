"""Base d'analyse du mode analyse (FD-INSPECT-001, étape 3).

child_database.py est chargé tel quel (bibliothèque standard seulement) ;
dotenv et mariadb sont remplacés par des modules doubles. Aucune vraie base
n'est contactée : l'essai réel se fait sur SéquenCiel.
"""

import json
import os
import sys
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from real_preview_support import make_project
from test_real_preview_controller import _imports  # pyright: ignore[reportPrivateUsage]

from forge_design.real_preview import analysis_database as ad
from forge_design.real_preview import child_database as cd

SCRIPT = Path(cd.__file__)


def test_child_database_uses_only_the_standard_library() -> None:
    assert _imports(SCRIPT) <= sys.stdlib_module_names


@pytest.mark.parametrize(
    ("name", "valid"),
    [
        ("sequenciel_analyse", True),
        ("_analyse", False),
        ("sequenciel", False),
        ("sequenciel_analyse ", False),
        ("x`_analyse", False),
        ("a" * 56 + "_analyse", True),
        ("a" * 57 + "_analyse", False),
    ],
)
def test_valid_target(name: str, valid: bool) -> None:
    assert cd.valid_target(name) is valid


def test_parse_arguments() -> None:
    assert cd.parse_arguments(["--target", "x_analyse"]) == ("x_analyse", False)
    assert cd.parse_arguments(["--target", "x_analyse", "--check"]) == (
        "x_analyse",
        True,
    )
    for refused in (
        [],
        ["--target", "x"],
        ["--check", "--target", "x_analyse"],
        ["--target", "x_analyse", "--force"],
    ):
        assert cd.parse_arguments(refused) is None


# ── Dans l'enfant : redirection et garde du pilote ───────────────────────────


@pytest.fixture
def fake_modules(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def load_dotenv(path: str, override: bool = False) -> bool:
        if override or "DB_NAME" not in os.environ:
            os.environ["DB_NAME"] = "reelle"
        return True

    def connect(**kwargs: Any) -> str:
        calls.append(kwargs)
        return "connexion"

    def pool(**kwargs: Any) -> str:
        calls.append(kwargs)
        return "pool"

    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = load_dotenv  # type: ignore[attr-defined]
    mariadb = types.ModuleType("mariadb")
    mariadb.connect = connect  # type: ignore[attr-defined]
    mariadb.ConnectionPool = pool  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "dotenv", dotenv)
    monkeypatch.setitem(sys.modules, "mariadb", mariadb)
    monkeypatch.delenv("DB_NAME", raising=False)
    yield {"dotenv": dotenv, "mariadb": mariadb, "calls": calls}


def test_redirect_survives_load_dotenv_override(fake_modules: dict[str, Any]) -> None:
    cd.redirect("x_analyse")
    assert os.environ["DB_NAME"] == "x_analyse"
    # Comme config.py : `from dotenv import load_dotenv` après la redirection.
    from dotenv import load_dotenv  # pyright: ignore[reportMissingModuleSource]

    assert load_dotenv("env/dev", override=True) is True
    assert os.environ["DB_NAME"] == "x_analyse"


def test_guard_driver_bounds_connections(fake_modules: dict[str, Any]) -> None:
    cd.redirect("x_analyse")
    cd.guard_driver("x_analyse")
    mariadb = fake_modules["mariadb"]
    assert mariadb.ConnectionPool(database="x_analyse", user="u") == "pool"
    assert mariadb.connect(database="x_analyse") == "connexion"
    for refused in ({"database": "reelle"}, {}):
        with pytest.raises(PermissionError):
            mariadb.connect(**refused)
        with pytest.raises(PermissionError):
            mariadb.ConnectionPool(**refused)
    with pytest.raises(PermissionError):
        mariadb.connect("hote")
    assert [call.get("database") for call in fake_modules["calls"]] == [
        "x_analyse",
        "x_analyse",
    ]


def test_guard_driver_refuses_a_changed_db_name(fake_modules: dict[str, Any]) -> None:
    cd.redirect("x_analyse")
    os.environ["DB_NAME"] = "reelle"
    with pytest.raises(RuntimeError):
        cd.guard_driver("x_analyse")


def test_copy_refuses_the_source_as_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_NAME", "x_analyse")
    with pytest.raises(RuntimeError):
        cd.copy("x_analyse")
    monkeypatch.delenv("DB_NAME")
    assert cd.check("x_analyse") == {"status": "none"}


# ── Côté Forge Design ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("folder", "expected"),
    [
        ("SequenCiel", "sequenciel_analyse"),
        ("Mon projet-2", "mon_projet_2_analyse"),
        ("---", "projet_analyse"),
        ("a" * 80, "a" * 56 + "_analyse"),
    ],
)
def test_analysis_database_name(folder: str, expected: str) -> None:
    name = ad.analysis_database_name(Path("/x") / folder)
    assert name == expected and cd.valid_target(name)


def test_creation_sql_names_only_the_target() -> None:
    sql = ad.creation_sql(ad.AnalysisDatabase("missing", "x_analyse", source="reelle"))
    assert "CREATE DATABASE `x_analyse`;" in sql and "reelle" not in sql


def test_parse_reply() -> None:
    parse = ad._parse  # pyright: ignore[reportPrivateUsage]
    reply = {"status": "ready", "source": "s", "tables": 3, "rows": 9, "seconds": 1.5}
    assert parse("x_analyse", reply) == ad.AnalysisDatabase(
        "ready", "x_analyse", source="s", tables=3, rows=9, seconds=1.5
    )
    assert parse("x_analyse", {"status": "drop"}).status == "failed"
    assert parse("x_analyse", []).status == "failed"


def test_run_without_database_on_the_skeleton(tmp_path: Path) -> None:
    """Vrai processus, vrai config.py du squelette : pas de DB_NAME."""
    root = make_project(tmp_path / "Projet")
    assert ad.check_analysis_database(root) == ad.AnalysisDatabase(
        "none", "projet_analyse"
    )
    assert ad.copy_analysis_database(root).status == "none"
    assert not list(root.rglob("__pycache__"))


def test_run_reports_the_last_error_line(tmp_path: Path) -> None:
    root = make_project(tmp_path / "projet", env_dev="DB_NAME=projet_analyse\n")
    result = ad.check_analysis_database(root)
    assert result.status == "failed"
    assert result.error == "Base d'analyse : DB_NAME désigne déjà projet_analyse."


def test_run_without_interpreter(tmp_path: Path) -> None:
    result = ad.check_analysis_database(tmp_path)
    assert result.status == "failed" and "Interpréteur" in (result.error or "")


def test_script_writes_one_json_line(tmp_path: Path) -> None:
    import subprocess

    root = make_project(tmp_path / "projet")
    completed = subprocess.run(
        [str(root / ".venv/bin/python"), "-I", "-B", str(SCRIPT), "--target", "x"],
        cwd=root,
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == cd.EXIT_USAGE and completed.stdout == ""
    completed = subprocess.run(
        [
            str(root / ".venv/bin/python"),
            "-I",
            "-B",
            str(SCRIPT),
            "--target",
            "x_analyse",
        ],
        cwd=root,
        env={"PATH": "/usr/bin:/bin", "APP_ENV": "dev"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert json.loads(completed.stdout) == {"status": "none"}
