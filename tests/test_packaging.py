"""Version de distribution du cœur (FD-RELEASE-001) : une seule source
autoritaire, ``forge_design.__version__``, lue par ``pyproject.toml``, reprise
par la métadonnée installée et par ``forge-design --version``."""

import tomllib
from importlib.metadata import requires, version
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.version import Version

import forge_design
from forge_design.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_version_has_a_single_authoritative_source() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = config["project"]
    assert "version" not in project, "aucune version écrite en double"
    assert "version" in project["dynamic"]
    assert config["tool"]["setuptools"]["dynamic"]["version"] == {
        "attr": "forge_design.__version__"
    }
    # Aucune autre copie de la version dans le code livré.
    hits = [
        path
        for path in (ROOT / "forge_design").rglob("*.py")
        if forge_design.__version__ in path.read_text(encoding="utf-8")
    ]
    assert hits == [ROOT / "forge_design/__init__.py"]


def test_version_is_pep440_and_matches_installed_metadata() -> None:
    parsed = Version(forge_design.__version__)
    assert str(parsed) == forge_design.__version__, "forme normalisée"
    assert version("forge-design") == forge_design.__version__
    # La comparaison runtime des spécificateurs repose sur packaging : dépendance
    # déclarée de la distribution.
    names = {Requirement(item).name for item in requires("forge-design") or []}
    assert "packaging" in names


def test_cli_reports_the_same_version(capsys: pytest.CaptureFixture[str]) -> None:
    try:
        main(["--version"])
    except SystemExit as exit:
        assert exit.code == 0
    assert capsys.readouterr().out == f"Forge Design {forge_design.__version__}\n"


def test_web_package_data_lists_every_template_and_asset() -> None:
    """La liste de package-data est explicite : un fichier non déclaré manque à
    la roue sans qu'aucun test sur la source ne le voie (FD-REALPREVIEW-008)."""
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = set(config["tool"]["setuptools"]["package-data"]["forge_design.web"])
    web = ROOT / "forge_design" / "web"
    present = {
        path.relative_to(web).as_posix()
        for pattern in (
            "templates/*.html",
            "static/**/*.css",
            "static/**/*.js",
            "static/**/*.woff2",
            "static/**/*.txt",
        )
        for path in web.glob(pattern)
    }
    assert sorted(present - declared) == []
    assert sorted(declared - present) == []
