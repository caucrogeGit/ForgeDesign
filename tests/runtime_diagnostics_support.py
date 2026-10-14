"""Projets Forge dont ``.venv/bin/python`` est un faux interpréteur (FD-RUNTIME-001).

Le faux interpréteur est un vrai exécutable : le runner le lance par son vrai
chemin (Popen, nouvelle session, tubes), sans patcher subprocess. Son
comportement est choisi par le fichier ``fake-doctor-mode`` à la racine, lu dans
le dossier courant du processus (donc la racine canonique transmise par cwd).
"""

import os
import site
import subprocess
import sys
from pathlib import Path

HOSTILE = "<script>alert(1)</script> <img src=x onerror=alert(2)> & \"quotes\" 'é' ✓"

FAKE_DOCTOR = r"""
import json, os, subprocess, sys, time
mode = open("fake-doctor-mode", encoding="utf-8").read().strip()
if mode == "argv":
    seen = {"argv": sys.argv[1:], "cwd": os.getcwd(), "env": sorted(os.environ)}
    print(json.dumps(seen))
elif mode == "ok":
    print("Forge doctor — faux\n  [OK]    Python\n0 avertissement(s), 0 erreur(s).")
elif mode == "fail":
    print("  [FAIL]  Structure MVC")
    print("trace simulée", file=sys.stderr)
    sys.exit(1)
elif mode == "code3":
    sys.exit(3)
elif mode == "hostile":
    print(HOSTILE + " \x1b[31mrouge\x1b[0m \x1b]0;titre\x07fin\x00nul")
    print(HOSTILE, file=sys.stderr)
elif mode == "secret":
    print("password=hunter2 api_key: k3y-777 visible")
    print("DB_PASSWORD=hunter3 vers mysql://roger:hunter4@db.local/app", end=" ")
    print("API_TOKEN=abc999")
    print("Authorization: Bearer t0ken-999", file=sys.stderr)
    print("HTTP_AUTHORIZATION=Basic t0ken-998 token_count=3", file=sys.stderr)
elif mode == "big":
    sys.stdout.write("o" * (1024 * 1024)); sys.stdout.flush()
    sys.stderr.write("e" * (1024 * 1024)); sys.stderr.flush()
elif mode == "sleep":
    time.sleep(30)
elif mode in ("child", "orphan"):
    child = subprocess.Popen(["sleep", "60"])
    open("fake-child-pid", "w").write(str(child.pid))
    if mode == "child":
        time.sleep(30)
"""


def fake_interpreter(root: Path, mode: str) -> Path:
    """Poser ``.venv/bin/python`` (script exécutable) et le mode demandé."""
    bin_dir = root / ".venv" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    doctor = root.parent / f"{root.name}-fake-doctor.py"
    doctor.write_text(f"HOSTILE = {HOSTILE!r}\n" + FAKE_DOCTOR, encoding="utf-8")
    python = bin_dir / "python"
    python.write_text(f'#!/bin/sh\nexec {sys.executable} -S {doctor} "$@"\n')
    python.chmod(0o755)
    (root / "fake-doctor-mode").write_text(mode)
    return python


def forge_project(root: Path, mode: str | None = "ok") -> Path:
    """Squelette Forge minimal ; faux interpréteur si ``mode`` n'est pas None."""
    root.mkdir(parents=True)
    for name in ("app.py", "bootstrap.py", "config.py"):
        (root / name).write_text("raise AssertionError('never execute')")
    (root / "mvc/routes").mkdir(parents=True)
    (root / "requirements.txt").write_text("forge-mvc==1.0.0rc9")
    if mode is not None:
        fake_interpreter(root, mode)
    return root.resolve()


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # Un zombie n'est plus actif.
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as stat:
            return stat.read().split()[2] != "Z"
    except OSError:
        return False


def make_linked_venv(venv: Path) -> Path:
    """Venv sans pip relié au forge-mvc installé ici (vrai CLI Forge)."""
    subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", str(venv)],
        check=True,
        timeout=60,
    )
    target = next(venv.glob("lib/python*/site-packages"))
    (target / "forge_mvc.pth").write_text("\n".join(site.getsitepackages()) + "\n")
    return venv
