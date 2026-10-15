"""Preview réelle sans bytecode (FD-REALPREVIEW-007, ACC-003).

Vrai contrôleur, vrai bootstrap, vrai squelette Forge rc9 : le projet importe
app.py, bootstrap.py, config.py, mvc/controllers, mvc/routes et optins, les
zones où ACC-003 voyait apparaître des __pycache__. L'instantané couvre tout
le projet, __pycache__ et .venv compris. Le témoin sans -B prouve que la sonde
voit le défaut qu'elle prétend exclure.
"""

import importlib.util
import os
import py_compile
from collections.abc import Callable, Iterator
from http.client import HTTPConnection
from pathlib import Path

import pytest
from real_preview_support import (
    make_project,
    processes_mentioning,
    tree_changes,
    tree_snapshot,
    wait_until_dead,
)

import forge_design.real_preview.controller as runner
from forge_design.real_preview import RealPreviewController

pytestmark = pytest.mark.skipif(os.name != "posix", reason="preview réelle POSIX")

BOOTSTRAP = Path(runner.__file__).with_name("child_bootstrap.py")
# Zones importées par le squelette rc9, observées par ACC-003.
IMPORTED_ZONES = (
    "__pycache__",
    "mvc/controllers/__pycache__",
    "mvc/routes/__pycache__",
    "optins/__pycache__",
)


def real_project(path: Path) -> Path:
    return make_project(path).resolve()


@pytest.fixture
def controller(tmp_path: Path) -> Iterator[RealPreviewController]:
    preview = RealPreviewController()
    yield preview
    preview.stop()
    assert wait_until_dead(processes_mentioning(str(tmp_path))) == []


def get(port: int, path: str = "/") -> int:
    connection = HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        connection.request("GET", path, headers={"Host": f"127.0.0.1:{port}"})
        response = connection.getresponse()
        response.read()
        return response.status
    finally:
        connection.close()


def cmdline(pid: int) -> list[str]:
    return Path(f"/proc/{pid}/cmdline").read_bytes().decode().split("\0")[:-1]


def run_preview(preview: RealPreviewController, root: Path) -> list[str]:
    """start → running → GET / → stop ; changements observés pendant running."""
    before = tree_snapshot(root)
    status = preview.start(root)
    assert status.state == "running", status.error
    assert status.port is not None
    assert get(status.port) == 200
    during = tree_changes(before, tree_snapshot(root))
    assert preview.stop().state == "stopped"
    assert processes_mentioning(str(root)) == []
    return during


def without_b(monkeypatch: pytest.MonkeyPatch) -> None:
    """Même lancement, -B retiré : le défaut d'avant FD-REALPREVIEW-007."""
    spawn: Callable[..., object] = runner._spawn  # pyright: ignore[reportPrivateUsage]

    def legacy(command: list[str], cwd: Path, env: dict[str, str]) -> object:
        return spawn([arg for arg in command if arg != "-B"], cwd, env)

    monkeypatch.setattr(runner, "_spawn", legacy)


def compile_into_cache(source: Path) -> Path:
    cache = Path(importlib.util.cache_from_source(str(source)))
    py_compile.compile(str(source), cfile=str(cache), doraise=True)
    return cache


def preexisting_caches(root: Path) -> dict[str, Path]:
    """À jour (app.py), périmé (config.py modifié après) et non importé."""
    fresh = compile_into_cache(root / "app.py")
    stale = compile_into_cache(root / "config.py")
    config = root / "config.py"
    config.write_text(config.read_text() + "\n# modifié après compilation\n")
    unused = root / "optins" / "jamais_importe.py"
    unused.write_text("VALUE = 1\n")
    orphan = compile_into_cache(unused)
    return {"fresh": fresh, "stale": stale, "unused": orphan}


# ── Témoin : la sonde voit le défaut ────────────────────────────────────────


def test_witness_without_b_writes_bytecode_and_rewrites_stale_cache(
    tmp_path: Path, controller: RealPreviewController, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = real_project(tmp_path / "p")
    caches = preexisting_caches(root)
    stale_before = caches["stale"].read_bytes()
    without_b(monkeypatch)
    during = run_preview(controller, root)
    for zone in IMPORTED_ZONES:
        assert any(change.startswith(f"+ {zone}/") for change in during), zone
    assert any(change.endswith(".pyc") for change in during)
    # Sans -B, Python réécrit aussi le cache périmé.
    assert caches["stale"].read_bytes() != stale_before


# ── Garantie FD-REALPREVIEW-007 ─────────────────────────────────────────────


def test_real_child_argv_is_explicit(
    tmp_path: Path, controller: RealPreviewController
) -> None:
    root = real_project(tmp_path / "p")
    status = controller.start(root)
    assert status.state == "running", status.error
    assert status.pid is not None
    assert cmdline(status.pid) == [
        str(root / ".venv" / "bin" / "python"),
        "-I",
        "-B",
        "-u",
        str(BOOTSTRAP),
        "--port",
        str(status.port),
    ]
    # La politique est dans l'argv, pas dans l'environnement.
    environ = Path(f"/proc/{status.pid}/environ").read_bytes().split(b"\0")
    assert not any(item.startswith(b"PYTHONDONTWRITEBYTECODE=") for item in environ)


def test_preview_leaves_project_identical_during_and_after(
    tmp_path: Path, controller: RealPreviewController
) -> None:
    root = real_project(tmp_path / "p")
    before = tree_snapshot(root)
    assert run_preview(controller, root) == []
    assert tree_changes(before, tree_snapshot(root)) == []
    assert not list(root.rglob("__pycache__")) and not list(root.rglob("*.pyc"))


def test_restart_writes_no_bytecode(
    tmp_path: Path, controller: RealPreviewController
) -> None:
    root = real_project(tmp_path / "p")
    before = tree_snapshot(root)
    assert run_preview(controller, root) == []
    assert run_preview(controller, root) == []
    assert tree_changes(before, tree_snapshot(root)) == []


def test_preexisting_bytecode_is_neither_removed_nor_modified(
    tmp_path: Path, controller: RealPreviewController
) -> None:
    root = real_project(tmp_path / "p")
    caches = preexisting_caches(root)
    before = tree_snapshot(root)
    assert run_preview(controller, root) == []
    assert tree_changes(before, tree_snapshot(root)) == []
    for cache in caches.values():
        assert cache.is_file()
