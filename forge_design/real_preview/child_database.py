"""Copie jetable de la base pour le mode analyse (FD-INSPECT-001, étape 3).

Exécuté uniquement par l'interpréteur du projet, cwd = racine du projet :
les identifiants de la base ne quittent jamais ce processus. Bibliothèque
standard seulement : le pilote `mariadb`, `dotenv` et `config` du projet sont
chargés par importlib, comme `app` dans child_bootstrap.py.

Deux usages :

- chargé par child_bootstrap.py avec --db : `redirect(nom)` avant `import
  app` force DB_NAME sur la copie, même après le `load_dotenv(override=True)`
  de config.py ; `guard_driver(nom)` après l'import refuse toute connexion
  `mariadb` vers une autre base ;
- lancé en script : `child_database.py --target <nom> [--check]` vérifie ou
  refait la copie de la base DB_NAME du projet vers <nom>, puis écrit une
  ligne JSON sur stdout.

La cible doit finir par _analyse et différer de DB_NAME : ses tables sont
supprimées à chaque copie. La base cible n'est jamais créée ici, le compte
d'administration du projet n'en a pas le droit.
"""

import importlib
import json
import os
import re
import sys
import time
import traceback
from collections.abc import Callable, Sequence
from typing import Any

SUFFIX = "_analyse"
_NAME = re.compile(r"[A-Za-z0-9_]{1,64}")

EXIT_USAGE = 2
EXIT_FAILED = 3


def valid_target(name: str) -> bool:
    return bool(_NAME.fullmatch(name)) and name.endswith(SUFFIX) and name != SUFFIX


def _quote(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


# ── Dans l'enfant de l'analyse ───────────────────────────────────────────────


def redirect(target: str) -> None:
    """DB_NAME = target, posé de nouveau après chaque load_dotenv."""
    os.environ["DB_NAME"] = target
    try:
        dotenv: Any = importlib.import_module("dotenv")
    except ImportError:
        return
    original: Callable[..., Any] = dotenv.load_dotenv

    def load_dotenv(*args: Any, **kwargs: Any) -> Any:
        try:
            return original(*args, **kwargs)
        finally:
            os.environ["DB_NAME"] = target

    dotenv.load_dotenv = load_dotenv


def guard_driver(target: str) -> None:
    """Après import app : DB_NAME intact, mariadb.connect/ConnectionPool bornés."""
    if os.environ.get("DB_NAME") != target:
        raise RuntimeError("DB_NAME a été modifié pendant l'import de l'application.")
    try:
        driver: Any = importlib.import_module("mariadb")
    except ImportError:
        return

    def bounded(function: Callable[..., Any]) -> Callable[..., Any]:
        def call(*args: Any, **kwargs: Any) -> Any:
            if args or kwargs.get("database") != target:
                raise PermissionError(
                    f"Mode analyse : connexion refusée hors de la base {target}."
                )
            return function(**kwargs)

        return call

    driver.connect = bounded(driver.connect)
    driver.ConnectionPool = bounded(driver.ConnectionPool)


# ── Script de copie ──────────────────────────────────────────────────────────


def _load_project_environment() -> None:
    """config.py du projet, comme l'application : env/example puis env/<APP_ENV>."""
    sys.path.insert(0, os.getcwd())
    importlib.import_module("config")


def _connect() -> Any:
    driver: Any = importlib.import_module("mariadb")
    return driver.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_ADMIN_LOGIN", ""),
        password=os.environ.get("DB_ADMIN_PWD", ""),
        autocommit=True,
    )


def _rows(cursor: Any, sql: str, *params: object) -> list[tuple[Any, ...]]:
    cursor.execute(sql, params)
    return list(cursor.fetchall())


def _objects(cursor: Any, schema: str) -> tuple[list[str], list[str]]:
    rows = _rows(
        cursor,
        "SELECT table_name, table_type FROM information_schema.tables"
        " WHERE table_schema = ? ORDER BY table_name",
        schema,
    )
    tables = [str(name) for name, kind in rows if kind == "BASE TABLE"]
    views = [str(name) for name, kind in rows if kind == "VIEW"]
    return tables, views


def _exists(cursor: Any, schema: str) -> bool:
    return bool(
        _rows(
            cursor,
            "SELECT 1 FROM information_schema.schemata WHERE schema_name = ?",
            schema,
        )
    )


def _copy_table(cursor: Any, source: str, target: str, table: str) -> int:
    columns = [
        str(name)
        for name, generated in _rows(
            cursor,
            "SELECT column_name, generation_expression IS NOT NULL"
            " AND generation_expression <> '' FROM information_schema.columns"
            " WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position",
            source,
            table,
        )
        if not generated
    ]
    names = ", ".join(_quote(column) for column in columns)
    cursor.execute(
        f"CREATE TABLE {_quote(target)}.{_quote(table)}"
        f" LIKE {_quote(source)}.{_quote(table)}"
    )
    cursor.execute(
        f"INSERT INTO {_quote(target)}.{_quote(table)} ({names})"
        f" SELECT {names} FROM {_quote(source)}.{_quote(table)}"
    )
    return int(cursor.rowcount)


def _copy_views(cursor: Any, source: str, target: str, views: list[str]) -> None:
    """Définitions de la source, schéma réécrit ; ordre trouvé par essais."""
    definitions: dict[str, str] = {}
    for view in views:
        (definition,) = _rows(
            cursor,
            "SELECT view_definition FROM information_schema.views"
            " WHERE table_schema = ? AND table_name = ?",
            source,
            view,
        )[0]
        definitions[view] = str(definition).replace(
            _quote(source) + ".", _quote(target) + "."
        )
    pending = list(views)
    while pending:
        failed: list[str] = []
        error: Exception | None = None
        for view in pending:
            try:
                cursor.execute(
                    f"CREATE VIEW {_quote(target)}.{_quote(view)}"
                    f" AS {definitions[view]}"
                )
            except Exception as caught:
                failed.append(view)
                error = caught
        if len(failed) == len(pending):
            raise RuntimeError(f"vues impossibles à recréer : {failed}") from error
        pending = failed


def _source(target: str) -> str | None:
    source = os.environ.get("DB_NAME", "")
    if not source:
        return None
    if source == target:
        raise RuntimeError(f"DB_NAME désigne déjà {target}.")
    return source


def check(target: str) -> dict[str, object]:
    source = _source(target)
    if source is None:
        return {"status": "none"}
    connection = _connect()
    try:
        cursor = connection.cursor()
        if not _exists(cursor, target):
            return {"status": "missing", "source": source, "target": target}
        tables, views = _objects(cursor, target)
    finally:
        connection.close()
    status = "ready" if tables else "empty"
    return {
        "status": status,
        "source": source,
        "target": target,
        "tables": len(tables),
        "views": len(views),
    }


def copy(target: str) -> dict[str, object]:
    source = _source(target)
    if source is None:
        return {"status": "none"}
    started = time.monotonic()
    connection = _connect()
    try:
        cursor = connection.cursor()
        if not _exists(cursor, target):
            return {"status": "missing", "source": source, "target": target}
        cursor.execute("SET SESSION foreign_key_checks = 0")
        old_tables, old_views = _objects(cursor, target)
        for view in old_views:
            cursor.execute(f"DROP VIEW {_quote(target)}.{_quote(view)}")
        for table in old_tables:
            cursor.execute(f"DROP TABLE {_quote(target)}.{_quote(table)}")
        tables, views = _objects(cursor, source)
        rows = sum(_copy_table(cursor, source, target, table) for table in tables)
        _copy_views(cursor, source, target, views)
    finally:
        connection.close()
    return {
        "status": "ready",
        "source": source,
        "target": target,
        "tables": len(tables),
        "views": len(views),
        "rows": rows,
        "seconds": round(time.monotonic() - started, 2),
    }


def parse_arguments(arguments: Sequence[str]) -> tuple[str, bool] | None:
    """--target <nom>, suivi ou non de --check."""
    checking = len(arguments) == 3 and arguments[2] == "--check"
    head = arguments[:2] if checking else arguments
    if len(head) != 2 or head[0] != "--target" or not valid_target(head[1]):
        return None
    return head[1], checking


def main(arguments: Sequence[str] | None = None) -> int:
    parsed = parse_arguments(sys.argv[1:] if arguments is None else arguments)
    if parsed is None:
        print(
            f"usage : child_database.py --target <nom{SUFFIX}> [--check]",
            file=sys.stderr,
        )
        return EXIT_USAGE
    target, checking = parsed
    try:
        _load_project_environment()
        result = check(target) if checking else copy(target)
    except Exception as error:
        traceback.print_exc()
        print(f"Base d'analyse : {error}", file=sys.stderr, flush=True)
        return EXIT_FAILED
    print(json.dumps(result), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
