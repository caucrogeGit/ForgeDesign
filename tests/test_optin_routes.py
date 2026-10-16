"""ACC-002 : registre vide prouvé, erreurs réelles et inspection sans exécution."""

import os
from pathlib import Path

import pytest
from test_project_health import healthy, summary

from forge_design.forge.routes import read_routes
from forge_design.limits import MAX_SOURCE_BYTES

REGISTRY = '''"""Registre éditable du projet."""
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.http.router import Router
BACKEND: str | None = None
ENABLED_OPTINS: dict[str, str] = {}
def register_optins(router: Router) -> None:
    """Aucune route d'opt-in."""
    return None
'''
IMPORT = "from optins.registry import register_optins\n"
CALL = "register_optins(router)\n"


def nominal(tmp_path: Path) -> Path:
    root = healthy(tmp_path / "project")
    (root / "optins").mkdir()
    (root / "optins/registry.py").write_text(REGISTRY)
    routes = root / "mvc/routes/__init__.py"
    routes.write_text(
        "from core.http.router import Router\n" + IMPORT + routes.read_text() + CALL
    )
    return root


def assert_attention(root: Path) -> None:
    assert len(read_routes(root).warnings) > 1
    assert summary(root).section("routes").status == "attention"


def test_empty_registry_is_statically_resolved(tmp_path: Path) -> None:
    root = nominal(tmp_path)
    result = read_routes(root)
    assert len(result.routes) == 1
    assert len(result.warnings) == 1  # La limite générale de lecture statique reste.
    assert summary(root).section("routes").status == "ok"


@pytest.mark.parametrize(
    "old,new",
    [
        (CALL, ""),
        (CALL, "register_optins(other_router)\n"),
        (CALL, "register_optins(router=router)\n"),
        (CALL, "if enabled:\n    register_optins(router)\n"),
        (CALL, CALL + CALL),
        (IMPORT, ""),
        (IMPORT, "from elsewhere import register_optins\n"),
        (IMPORT, "from optins.registry import register_optins as register\n"),
        (CALL, "router = other\n" + CALL),
        (CALL, "from elsewhere import router\n" + CALL),
        (CALL, "from elsewhere import register_optins\n" + CALL),
        (CALL, "from elsewhere import *\n" + CALL),
        (CALL, "del register_optins\n" + CALL),
        (CALL, "register_optins = other\n" + CALL),
        ("from core.http.router import Router\n", "from other import Router\n"),
        ("router = Router()\n", CALL + "router = Router()\n"),
    ],
)
def test_missing_or_ambiguous_wiring_warns(tmp_path: Path, old: str, new: str) -> None:
    root = nominal(tmp_path)
    path = root / "mvc/routes/__init__.py"
    path.write_text(path.read_text().replace(old, new))
    assert_attention(root)


@pytest.mark.parametrize(
    "source",
    [
        REGISTRY.replace("return None", "return register_routes(router)"),
        REGISTRY.replace("= {}", '= {"iot": "route"}'),
        REGISTRY.replace("= {}", "= discover()"),
        REGISTRY.replace("= None", '= "sqlite"'),
        REGISTRY.replace("def register_optins", "@decorate\ndef register_optins"),
        REGISTRY.replace("router: Router", "router: Router = factory()"),
        REGISTRY + "register_optins = other\n",
        REGISTRY + 'raise AssertionError("do not execute registry")\n',
        "def register_optins(:\n",
        "# missing function\n",
    ],
)
def test_active_custom_or_invalid_registry_remains_partial(
    tmp_path: Path, source: str
) -> None:
    root = nominal(tmp_path)
    (root / "optins/registry.py").write_text(source)
    assert_attention(root)


@pytest.mark.parametrize(
    "kind", ["missing", "file-link", "dir-link", "fifo", "large", "encoding"]
)
def test_registry_read_boundary(tmp_path: Path, kind: str) -> None:
    root = nominal(tmp_path)
    path = root / "optins/registry.py"
    if kind == "large":
        path.write_text(REGISTRY + "#" * MAX_SOURCE_BYTES)
    elif kind == "encoding":
        path.write_bytes(b"\xff")
    elif kind == "dir-link":
        (root / "optins").rename(tmp_path / "outside")
        (root / "optins").symlink_to(tmp_path / "outside", target_is_directory=True)
    else:
        path.unlink()
        if kind == "file-link":
            outside = tmp_path / "outside.py"
            outside.write_text(REGISTRY)
            path.symlink_to(outside)
        elif kind == "fifo":
            os.mkfifo(path)
    assert_attention(root)


def test_no_import_or_project_write(tmp_path: Path) -> None:
    root = nominal(tmp_path)
    marker = tmp_path / "executed"
    hostile = f"from pathlib import Path\nPath({str(marker)!r}).touch()\n"
    for name in ("optins/__init__.py", "mvc/controllers/__init__.py"):
        (root / name).write_text(hostile)
    controller = root / "mvc/controllers/home.py"
    controller.write_text(hostile + controller.read_text())
    before = {
        p: (p.read_bytes(), p.stat().st_mtime_ns)
        for p in root.rglob("*")
        if p.is_file()
    }
    assert len(read_routes(root).warnings) == 1
    assert summary(root).section("routes").status == "ok"
    assert not marker.exists()
    assert {
        p: (p.read_bytes(), p.stat().st_mtime_ns)
        for p in root.rglob("*")
        if p.is_file()
    } == before


def test_legacy_without_optins_keeps_existing_diagnostic(tmp_path: Path) -> None:
    root = healthy(tmp_path / "legacy")
    assert len(read_routes(root).warnings) == 1
    assert summary(root).section("routes").status == "ok"


def test_hostile_registry_is_not_executed(tmp_path: Path) -> None:
    root = nominal(tmp_path)
    marker = tmp_path / "registry-executed"
    path = root / "optins/registry.py"
    path.write_text(REGISTRY + f'open({str(marker)!r}, "w").write("executed")\n')
    assert_attention(root)
    assert not marker.exists()
    assert len(read_routes(root).routes) == 1


def test_other_dynamic_declarations_keep_attention(tmp_path: Path) -> None:
    root = nominal(tmp_path)
    path = root / "mvc/routes/__init__.py"
    path.write_text(path.read_text() + 'router.add("GET", "/dynamic", factory())\n')
    assert_attention(root)
    assert any("handler dynamique" in w for w in read_routes(root).warnings)
