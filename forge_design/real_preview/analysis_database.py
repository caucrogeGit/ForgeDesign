"""Base d'analyse : copie jetable de la base du projet (FD-INSPECT-001, étape 3).

Décision du porteur : en mode analyse, l'application écrit dans une copie,
sur le même serveur, recopiée à la demande ; la base réelle n'est jamais
touchée. La copie s'appelle <dossier du projet>_analyse et doit être créée
une fois par un administrateur du serveur.

Forge Design ne lit jamais env/dev : child_database.py vérifie ou refait la
copie dans un processus lancé avec l'interpréteur du projet, et ne renvoie
qu'une ligne JSON sans identifiants.
"""

import json
import re
import subprocess
from dataclasses import dataclass
from os import environ
from pathlib import Path
from typing import Literal, cast

from forge_design.forge.project_python import child_environment, project_interpreter

AnalysisDatabaseStatus = Literal["none", "missing", "empty", "ready", "failed"]

SUFFIX = "_analyse"
_CHECK_TIMEOUT = 60.0
_COPY_TIMEOUT = 600.0
_MAX_ERROR_CHARS = 500
_STATUSES = ("none", "missing", "empty", "ready")


@dataclass(frozen=True)
class AnalysisDatabase:
    """none : le projet n'a pas de DB_NAME ; missing : base cible absente."""

    status: AnalysisDatabaseStatus
    target: str
    source: str | None = None
    tables: int = 0
    rows: int | None = None
    seconds: float | None = None
    error: str | None = None


def analysis_database_name(root: Path) -> str:
    """SequenCiel → sequenciel_analyse ; 64 caractères au plus (MariaDB)."""
    stem = re.sub(r"[^a-z0-9]+", "_", root.name.lower()).strip("_") or "projet"
    return stem[: 64 - len(SUFFIX)] + SUFFIX


def creation_sql(database: AnalysisDatabase) -> str:
    """Ce qu'un administrateur du serveur doit lancer pour une base missing."""
    return (
        f"CREATE DATABASE `{database.target}`;\n"
        f"GRANT ALL PRIVILEGES ON `{database.target}`.* TO <compte DB_ADMIN_LOGIN>;\n"
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        f"`{database.target}`.* TO <compte DB_APP_LOGIN>;"
    )


def _script() -> Path:
    return Path(__file__).resolve().with_name("child_database.py")


def _failed(target: str, error: str) -> AnalysisDatabase:
    return AnalysisDatabase("failed", target, error=error[:_MAX_ERROR_CHARS])


def _run(root: Path, *, check: bool) -> AnalysisDatabase:
    target = analysis_database_name(root)
    interpreter = project_interpreter(root)
    if interpreter is None:
        return _failed(target, "Interpréteur du projet introuvable (.venv/bin/python).")
    command = [str(interpreter), "-I", "-B", str(_script()), "--target", target]
    if check:
        command.append("--check")
    environment = child_environment(environ)
    environment["APP_ENV"] = "dev"
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_CHECK_TIMEOUT if check else _COPY_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _failed(target, "Délai dépassé pendant la copie de la base.")
    except OSError as error:
        return _failed(target, f"Lancement impossible : {error.strerror or error}")
    if completed.returncode != 0:
        lines = [line for line in completed.stderr.splitlines() if line.strip()]
        return _failed(target, lines[-1] if lines else f"code {completed.returncode}")
    try:
        lines = completed.stdout.strip().splitlines()
        data = cast("dict[str, object]", json.loads(lines[-1]))
    except (IndexError, ValueError):
        return _failed(target, "Réponse illisible du script de copie.")
    return _parse(target, data)


def _parse(target: str, data: object) -> AnalysisDatabase:
    if not isinstance(data, dict):
        return _failed(target, "Réponse illisible du script de copie.")
    fields = cast("dict[str, object]", data)
    status = fields.get("status")
    if status not in _STATUSES:
        return _failed(target, "Réponse illisible du script de copie.")
    source, tables = fields.get("source"), fields.get("tables", 0)
    rows, seconds = fields.get("rows"), fields.get("seconds")
    return AnalysisDatabase(
        cast("AnalysisDatabaseStatus", status),
        target,
        source=source if isinstance(source, str) else None,
        tables=tables if type(tables) is int else 0,
        rows=rows if type(rows) is int else None,
        seconds=float(seconds) if isinstance(seconds, int | float) else None,
    )


def check_analysis_database(root: Path) -> AnalysisDatabase:
    """État de la copie, sans rien écrire."""
    return _run(root, check=True)


def copy_analysis_database(root: Path) -> AnalysisDatabase:
    """Supprime les tables de la copie puis y recopie la base DB_NAME."""
    return _run(root, check=False)
