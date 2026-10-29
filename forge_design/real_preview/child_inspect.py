"""Sondes du mode analyse, dans le processus enfant (FD-INSPECT-001).

Chargé par child_bootstrap.py, par chemin de fichier, quand il reçoit
--inspect. Bibliothèque standard seulement, comme le bootstrap : ce fichier
n'importe jamais forge_design.

Les sondes enveloppent, après l'import de l'application et avant le premier
service, quatre points de forge-mvc 1.0.0rc9 : Router.match (route trouvée),
le handler de cette route (localisé par inspect), le chargeur Jinja du
renderer (templates chargés, marqueurs insérés dans le source) et
core.database.db._run_query (requêtes SQL). Aucun fichier de Forge ni du
projet n'est modifié.

Chaque requête HTTP reçoit une trace, portée par une ContextVar (un thread
par requête), gardée en mémoire et servie en JSON par
GET /__forge_design/trace/<id>. Les valeurs des paramètres SQL et la query
string ne sont jamais enregistrées.
"""

import contextvars
import importlib
import inspect
import itertools
import json
import os
import re
import sys
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Iterable
from typing import Any, cast

TRACE_HEADER = "X-Forge-Design-Trace"
INTERNAL_PREFIX = "/__forge_design/"
TRACE_PREFIX = "/__forge_design/trace/"
MAX_TRACES = 200
MAX_SQL_CHARS = 4000
MAX_QUERIES = 500
_HTML_SUFFIXES = (".html", ".htm")

WsgiApp = Callable[[dict[str, Any], Callable[..., Any]], Iterable[bytes]]

_current: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "forge_design_trace", default=None
)


def _warn(message: str) -> None:
    print(f"Mode analyse : {message}", file=sys.stderr, flush=True)


# ── Traces ───────────────────────────────────────────────────────────────────


class TraceStore:
    """Les MAX_TRACES dernières traces, par identifiant."""

    def __init__(self, limit: int = MAX_TRACES) -> None:
        self._limit = limit
        self._traces: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._ids = itertools.count(1)

    def new(self, method: str, path: str) -> dict[str, Any]:
        trace: dict[str, Any] = {
            "id": str(next(self._ids)),
            "method": method,
            "path": path,
            "status": None,
            "content_type": None,
            "duration_ms": None,
            "route": None,
            "route_lookups": 0,
            "handler": None,
            "templates": [],
            "queries": [],
            "queries_dropped": 0,
        }
        return trace

    def add(self, trace: dict[str, Any]) -> None:
        with self._lock:
            self._traces[trace["id"]] = trace
            while len(self._traces) > self._limit:
                self._traces.popitem(last=False)

    def get(self, trace_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._traces.get(trace_id)


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)


def _project_relative(path: str | None) -> str | None:
    """Chemin relatif à la racine du projet (cwd), sinon None."""
    if not path:
        return None
    root = os.getcwd()
    absolute = os.path.realpath(path)
    if absolute == root or not absolute.startswith(root + os.sep):
        return None
    return os.path.relpath(absolute, root)


# ── Route et handler ─────────────────────────────────────────────────────────


def handler_location(handler: object) -> dict[str, Any]:
    """Nom qualifié, module, fichier relatif au projet et ligne du handler."""
    target: Any = inspect.unwrap(handler)  # pyright: ignore[reportArgumentType]
    target = getattr(target, "__func__", target)
    location: dict[str, Any] = {
        "qualname": getattr(target, "__qualname__", type(target).__name__),
        "module": getattr(target, "__module__", None),
        "file": None,
        "line": None,
    }
    try:
        location["file"] = _project_relative(inspect.getsourcefile(target))
        location["line"] = inspect.getsourcelines(target)[1]
    except (OSError, TypeError):
        pass
    return location


def _route_summary(entry: Any, params: dict[str, Any]) -> dict[str, Any]:
    methods = getattr(entry, "method", None)
    return {
        "methods": [methods] if isinstance(methods, str) else list(methods or ()),
        "pattern": getattr(entry, "pattern", None),
        "name": getattr(entry, "name", None),
        "public": bool(getattr(entry, "public", False)),
        "api": bool(getattr(entry, "api", False)),
        "params": sorted(params),
    }


def install_route_probe(router_class: Any) -> None:
    """Router.match : seul le premier appel d'une requête, celui de dispatch."""
    original = router_class.match

    def match(self: Any, method: str, path: str) -> Any:
        result = original(self, method, path)
        trace = _current.get()
        if trace is not None:
            trace["route_lookups"] += 1
            if trace["route_lookups"] == 1 and result is not None:
                entry, params = result
                trace["route"] = _route_summary(entry, params)
                trace["handler"] = handler_location(entry.handler)
        return result

    router_class.match = match


# ── SQL ──────────────────────────────────────────────────────────────────────


def _row_count(result: Any, fetch: str | None) -> int | None:
    if fetch == "all":
        return len(cast("list[object]", result)) if isinstance(result, list) else None
    if fetch == "one":
        return 0 if result is None else 1
    if fetch is None and isinstance(result, int):
        return result
    return None


def install_sql_probe(db_module: Any) -> None:
    """core.database.db._run_query : texte, durée, lignes ; jamais les valeurs."""
    original = db_module._run_query  # pyright: ignore[reportPrivateUsage]

    def run_query(sql: str, params: Any = (), **options: Any) -> Any:
        trace = _current.get()
        if trace is None:
            return original(sql, params, **options)
        fetch = options.get("fetch")
        record: dict[str, Any] = {
            "sql": sql[:MAX_SQL_CHARS],
            "truncated": len(sql) > MAX_SQL_CHARS,
            "params": len(params) if hasattr(params, "__len__") else None,
            "fetch": fetch,
            "in_transaction": options.get("tx") is not None,
            "duration_ms": None,
            "rows": None,
            "error": None,
        }
        started = time.perf_counter()
        try:
            result = original(sql, params, **options)
        except BaseException as error:
            record["error"] = type(error).__name__
            raise
        else:
            record["rows"] = _row_count(result, fetch)
            return result
        finally:
            record["duration_ms"] = _elapsed_ms(started)
            if len(trace["queries"]) < MAX_QUERIES:
                trace["queries"].append(record)
            else:
                trace["queries_dropped"] += 1

    db_module._run_query = run_query  # pyright: ignore[reportPrivateUsage]


# ── Templates et marqueurs ───────────────────────────────────────────────────

# Commentaire, section raw, balise {% %} ou expression {{ }} : le contenu de
# raw est rendu tel quel mais ne porte jamais de marqueur.
_TOKEN = re.compile(
    r"\{#.*?#\}"
    r"|\{%[-+]?\s*raw\s*[-+]?%\}.*?\{%[-+]?\s*endraw\s*[-+]?%\}"
    r"|\{%.*?%\}"
    r"|\{\{.*?\}\}",
    re.S,
)
_TAG_INNER = re.compile(r"\{%[-+]?(.*?)[-+]?%\}", re.S)
_BLOCK = re.compile(r"block\s+(\w+)((?:\s+\w+)*)\s*$")
_EXTENDS = re.compile(r"""extends\s+(?:"([^"]+)"|'([^']+)'|(.+))$""", re.S)
_INCLUDE = re.compile(r"""include\s+(?:"([^"]+)"|'([^']+)')""")
_RAW_TEXT = ("title", "script", "style", "textarea")
_BODY_OPEN = re.compile(r"<body\b[^>]*>", re.I)
_BODY_CLOSE = re.compile(r"</body\s*>", re.I)
_DOCUMENT = re.compile(r"<!doctype|<html\b", re.I)
_TAG_START = re.compile(r"<[A-Za-z/!]")


def safe_context(html: str, position: int) -> bool:
    """Un commentaire HTML inséré ici serait-il un nœud du DOM ?

    Faux dans une balise ouverte (attribut compris), dans un commentaire HTML
    et dans title, script, style ou textarea, où il deviendrait du texte ou
    casserait le contenu. `html` est le source, constructions Jinja blanchies.
    """
    before = html[:position]
    last_open = max((m.start() for m in _TAG_START.finditer(before)), default=-1)
    if last_open > before.rfind(">"):
        return False
    if before.rfind("<!--") > before.rfind("-->"):
        return False
    lower = before.lower()
    for name in _RAW_TEXT:
        opened = max(
            (m.start() for m in re.finditer(rf"<{name}[\s>]", lower)), default=-1
        )
        if opened > lower.rfind(f"</{name}"):
            return False
    return True


class TemplateShape:
    """Ce que l'instrumentation doit savoir d'un template, sans l'exécuter."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.extends: str | None = None
        self.dynamic_extends = False
        # (nom, fin de la balise ouvrante, début de endblock, sûr, required)
        self.blocks: list[tuple[str, int, int, bool, bool]] = []
        self.unsafe_blocks: set[str] = set()
        self.unsafe_includes: set[str] = set()
        self.valid = True
        self._scan()

    def _scan(self) -> None:
        tokens = list(_TOKEN.finditer(self.source))
        html = list(self.source)
        for token in tokens:
            html[token.start() : token.end()] = " " * (token.end() - token.start())
        blanked = "".join(html)
        stack: list[tuple[str, int, bool, bool]] = []
        for token in tokens:
            inner_match = _TAG_INNER.fullmatch(token.group())
            if inner_match is None:
                continue
            inner = inner_match.group(1).strip()
            keyword = inner.split(None, 1)[0] if inner else ""
            if keyword == "extends" and self.extends is None:
                found = _EXTENDS.match(inner)
                literal = found and (found.group(1) or found.group(2))
                if literal:
                    self.extends = literal
                else:
                    self.dynamic_extends = True
            elif keyword == "block":
                found = _BLOCK.match(inner)
                if found is None:
                    self.valid = False
                    return
                safe = safe_context(blanked, token.start())
                required = "required" in found.group(2).split()
                stack.append((found.group(1), token.end(), safe, required))
                if not safe:
                    self.unsafe_blocks.add(found.group(1))
            elif keyword == "endblock":
                if not stack:
                    self.valid = False
                    return
                name, opened, safe, required = stack.pop()
                self.blocks.append((name, opened, token.start(), safe, required))
            elif keyword == "include":
                found = _INCLUDE.match(inner)
                if found and not safe_context(blanked, token.start()):
                    self.unsafe_includes.add(found.group(1) or found.group(2))
        if stack:
            self.valid = False


def instrument_source(
    shape: TemplateShape,
    template_id: int,
    *,
    unsafe_blocks: set[str] | None,
    wrap: bool,
) -> str:
    """Source avec marqueurs de template et de blocs.

    `unsafe_blocks` vaut None quand aucun bloc ne doit être marqué (parent
    dynamique). Un template qui étend un autre n'est jamais enveloppé : sa
    sortie hors blocs n'est pas celle de la page.
    """
    source = shape.source
    insertions: list[tuple[int, int, str]] = []
    order = itertools.count()
    if wrap and shape.extends is None and not shape.dynamic_extends:
        opening = _BODY_OPEN.search(source)
        closing = _BODY_CLOSE.search(source)
        if opening is not None and closing is not None:
            start, end = opening.end(), closing.start()
        elif _DOCUMENT.search(source) is None:
            start, end = 0, len(source)
        else:
            start = end = -1
        if 0 <= start <= end:
            insertions.append((start, next(order), f"<!--fd:t:{template_id}-->"))
    else:
        start = end = -1
    if unsafe_blocks is not None:
        for name, opened, closed, safe, required in shape.blocks:
            if not safe or required or name in unsafe_blocks:
                continue
            insertions.append(
                (opened, next(order), f"<!--fd:b:{template_id}:{name}-->")
            )
            insertions.append((closed, next(order), f"<!--/fd:b:{template_id}-->"))
    if 0 <= start <= end:
        insertions.append((end, next(order), f"<!--/fd:t:{template_id}-->"))
    # Au même point (bloc vide), l'ordre d'insertion : ouverture puis fermeture.
    insertions.sort(key=lambda item: (item[0], item[1]))
    parts: list[str] = []
    cursor = 0
    for position, _, marker in insertions:
        parts.append(source[cursor:position])
        parts.append(marker)
        cursor = position
    parts.append(source[cursor:])
    return "".join(parts)


class TemplateRegistry:
    """Identifiant stable par nom de template, pour la durée du processus."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._ids: dict[str, int] = {}
        self.info: dict[int, dict[str, Any]] = {}
        self._shapes: dict[str, TemplateShape | None] = {}
        self.unsafe_fragments: set[str] = set()

    def id_for(self, name: str) -> int:
        with self._lock:
            if name not in self._ids:
                self._ids[name] = len(self._ids) + 1
            return self._ids[name]

    def known(self, name: str) -> int | None:
        with self._lock:
            return self._ids.get(name)

    def shape(
        self, name: str, source_of: Callable[[str], str | None]
    ) -> TemplateShape | None:
        with self._lock:
            if name not in self._shapes:
                source = source_of(name)
                self._shapes[name] = None if source is None else TemplateShape(source)
            return self._shapes[name]

    def inherited_unsafe(
        self, shape: TemplateShape, source_of: Callable[[str], str | None]
    ) -> set[str] | None:
        """Blocs non sûrs dans toute la chaîne extends ; None si indécidable."""
        unsafe = set(shape.unsafe_blocks)
        seen: set[str] = set()
        current = shape
        while current.extends is not None or current.dynamic_extends:
            if current.dynamic_extends or current.extends in seen:
                return None
            seen.add(current.extends)  # pyright: ignore[reportArgumentType]
            parent = self.shape(current.extends, source_of)  # pyright: ignore[reportArgumentType]
            if parent is None or not parent.valid:
                return None
            unsafe |= parent.unsafe_blocks
            current = parent
        return unsafe


def install_template_probe(environment: Any, registry: TemplateRegistry) -> None:
    """Chargeur Jinja : marqueurs dans le source, templates chargés par requête."""
    loader = environment.loader
    original_get_source = loader.get_source

    def source_of(name: str) -> str | None:
        try:
            return original_get_source(environment, name)[0]
        except Exception:  # noqa: BLE001 — template introuvable ou illisible
            return None

    def get_source(env: Any, name: str) -> Any:
        source, filename, uptodate = original_get_source(env, name)
        template_id = registry.id_for(name)
        shape = TemplateShape(source)
        registry.info[template_id] = {
            "id": template_id,
            "name": name,
            "file": _project_relative(filename),
            "extends": shape.extends,
        }
        if not name.endswith(_HTML_SUFFIXES) or not shape.valid:
            return source, filename, uptodate
        registry.unsafe_fragments |= shape.unsafe_includes
        instrumented = instrument_source(
            shape,
            template_id,
            unsafe_blocks=registry.inherited_unsafe(shape, source_of),
            wrap=name not in registry.unsafe_fragments,
        )
        try:
            env.parse(instrumented)
        except Exception:  # noqa: BLE001 — repli sur le source d'origine
            _warn(f"marqueurs retirés de {name!r} (source non analysable).")
            return source, filename, uptodate
        return instrumented, filename, uptodate

    loader.get_source = get_source
    original_load = environment._load_template  # pyright: ignore[reportPrivateUsage]

    def load_template(name: Any, globals: Any) -> Any:
        template = original_load(name, globals)
        trace = _current.get()
        if trace is not None:
            template_name = getattr(template, "name", None)
            template_id = registry.known(template_name) if template_name else None
            loaded = trace["templates"]
            existing = next((t for t in loaded if t["id"] == template_id), None)
            if template_id is None:
                pass
            elif existing is not None:
                existing["loads"] += 1
            else:
                loaded.append({**registry.info[template_id], "loads": 1})
        return template

    environment._load_template = load_template  # pyright: ignore[reportPrivateUsage]
    cache = getattr(environment, "cache", None)
    if cache is not None:
        cache.clear()


# ── WSGI ─────────────────────────────────────────────────────────────────────


def _json_response(
    start_response: Callable[..., Any], status: str, payload: object
) -> list[bytes]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    start_response(
        status,
        [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Cache-Control", "no-store"),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]


def inspect_app(application: WsgiApp, store: TraceStore) -> WsgiApp:
    """Une trace par requête ; /__forge_design/ servi ici, jamais par l'app."""

    def traced(
        environ: dict[str, Any], start_response: Callable[..., Any]
    ) -> Iterable[bytes]:
        path = environ.get("PATH_INFO", "")
        if path.startswith(INTERNAL_PREFIX):
            trace_id = (
                path[len(TRACE_PREFIX) :] if path.startswith(TRACE_PREFIX) else ""
            )
            found = store.get(trace_id) if trace_id.isdigit() else None
            if environ.get("REQUEST_METHOD") != "GET" or found is None:
                return _json_response(
                    start_response, "404 Not Found", {"error": "trace inconnue"}
                )
            return _json_response(start_response, "200 OK", found)
        trace = store.new(environ.get("REQUEST_METHOD", ""), path)

        def start(status: str, headers: list[tuple[str, str]], *rest: Any) -> Any:
            trace["status"] = int(status.split(None, 1)[0])
            trace["content_type"] = next(
                (value for name, value in headers if name.lower() == "content-type"),
                None,
            )
            return start_response(
                status, [*headers, (TRACE_HEADER, trace["id"])], *rest
            )

        token = _current.set(trace)
        started = time.perf_counter()
        try:
            result = application(environ, start)
            try:
                body = list(result)
            finally:
                close = getattr(result, "close", None)
                if callable(close):
                    close()
        finally:
            trace["duration_ms"] = _elapsed_ms(started)
            _current.reset(token)
            store.add(trace)
        return body

    return traced


def _module(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except Exception:  # noqa: BLE001 — sonde signalée indisponible
        return None


def install(application: WsgiApp) -> WsgiApp:
    """Poser les sondes sur Forge chargé ; chaque sonde absente est signalée."""
    router = getattr(_module("core.http.router"), "Router", None)
    if router is not None and callable(getattr(router, "match", None)):
        install_route_probe(router)
    else:
        _warn("sonde de route indisponible (core.http.router.Router).")
    db = _module("core.database.db")
    if db is not None and callable(getattr(db, "_run_query", None)):
        install_sql_probe(db)
    else:
        _warn("sonde SQL indisponible (core.database.db._run_query).")
    manager = getattr(_module("core.templating.manager"), "template_manager", None)
    renderer = getattr(manager, "_renderer", None)
    environment = getattr(renderer, "_env", None)
    if environment is not None and getattr(environment, "loader", None) is not None:
        install_template_probe(environment, TemplateRegistry())
    else:
        _warn("sonde de templates indisponible (renderer Jinja2).")
    return inspect_app(application, TraceStore())
