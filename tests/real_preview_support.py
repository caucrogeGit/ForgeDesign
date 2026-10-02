"""Projets Forge synthétiques pour les tests de preview réelle.

Le squelette vient de forge-mvc 1.0.0rc9 installé ; le venv du projet est un
venv léger (pyvenv.cfg, lien vers l'interpréteur de base, fichier .pth vers
les site-packages de Forge Design) : aucun venv complet n'est créé par test.
Aucun projet réel ni env/dev utilisateur n'est jamais lu.
"""

import importlib.metadata
import os
import shutil
import sys
import time
from collections.abc import Sequence
from pathlib import Path

_SKELETON_ITEMS = (
    "app.py",
    "bootstrap.py",
    "config.py",
    "env",
    "mvc",
    "optins",
    "static",
)


def forge_site_packages() -> Path:
    return Path(str(importlib.metadata.distribution("forge-mvc").locate_file("")))


def make_venv(root: Path, extra_paths: Sequence[Path] = ()) -> Path:
    """<root>/.venv/bin/python lié à l'interpréteur de base, Forge rc9 visible."""
    base = Path(os.path.realpath(sys.executable))
    venv = root / ".venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "python").symlink_to(base)
    version = ".".join(str(part) for part in sys.version_info[:3])
    (venv / "pyvenv.cfg").write_text(
        f"home = {base.parent}\ninclude-system-site-packages = false\n"
        f"version = {version}\n"
    )
    major, minor = sys.version_info[:2]
    site = venv / "lib" / f"python{major}.{minor}" / "site-packages"
    site.mkdir(parents=True)
    paths = [*extra_paths, forge_site_packages()]
    (site / "forge-design-tests.pth").write_text("".join(f"{p}\n" for p in paths))
    return venv / "bin" / "python"


def make_project(
    root: Path, *, app_prefix: str = "", env_dev: str | None = None
) -> Path:
    """Squelette Forge rc9 réel ; app_prefix s'exécute au début de l'import de app."""
    skeleton = forge_site_packages() / "skeleton" / "data"
    root.mkdir(parents=True, exist_ok=True)
    ignore = shutil.ignore_patterns("__pycache__")
    for name in _SKELETON_ITEMS:
        source = skeleton / name
        if source.is_dir():
            shutil.copytree(source, root / name, ignore=ignore)
        else:
            shutil.copy2(source, root / name)
    if app_prefix:
        app = root / "app.py"
        app.write_text(app_prefix + "\n" + app.read_text(encoding="utf-8"))
    if env_dev is not None:
        (root / "env" / "dev").write_text(env_dev)
    make_venv(root)
    return root


def _alive(pid: int) -> bool:
    try:
        status = Path(f"/proc/{pid}/status").read_text()
    except OSError:
        return False
    return "\nState:\tZ" not in status


def processes_mentioning(marker: str) -> list[int]:
    """PID vivants (hors zombies) dont la ligne de commande contient marker."""
    found: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            command = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        if marker.encode() in command and _alive(int(entry.name)):
            found.append(int(entry.name))
    return found


def wait_until_dead(pids: Sequence[int], timeout: float = 3.0) -> list[int]:
    deadline = time.monotonic() + timeout
    while (
        alive := [pid for pid in pids if _alive(pid)]
    ) and time.monotonic() < deadline:
        time.sleep(0.05)
    return alive


def listening_sockets() -> dict[int, list[tuple[str, int]]]:
    """Inode → [(adresse hex, port)] des sockets TCP en écoute (IPv4 et IPv6)."""
    result: dict[int, list[tuple[str, int]]] = {}
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            lines = Path(table).read_text().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            fields = line.split()
            if fields[3] != "0A":
                continue
            address, port = fields[1].split(":")
            result.setdefault(int(fields[9]), []).append((address, int(port, 16)))
    return result


def own_socket_inodes() -> set[int]:
    inodes: set[int] = set()
    for fd in Path("/proc/self/fd").iterdir():
        try:
            target = os.readlink(fd)
        except OSError:
            continue
        if target.startswith("socket:["):
            inodes.add(int(target[8:-1]))
    return inodes
