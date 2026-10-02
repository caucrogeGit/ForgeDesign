"""Application Forge locale et inspection explicite via le Tool."""

import signal
import threading
from collections.abc import Callable, Generator, Iterable
from contextlib import contextmanager
from importlib.resources import files
from typing import Any
from wsgiref.simple_server import WSGIServer, make_server

from core.app.application import Application
from core.app.wsgi import create_wsgi_app
from core.http.request import Request
from core.http.response import Response
from core.http.router import Router

from forge_design.app import create_tool_registry
from forge_design.current_project import CurrentProjectContext
from forge_design.project_selector import ProjectSelector
from forge_design.recent_projects import RecentProjects
from forge_design.web.debug import show_debug
from forge_design.web.debug_detail import show_debug_detail
from forge_design.web.editor import editor_action, show_editor
from forge_design.web.editor_preview import show_editor_preview
from forge_design.web.entities import show_entities
from forge_design.web.inspector import (
    inspect_submission,
    refresh_project,
    show_inspector,
)
from forge_design.web.real_preview import (
    RealPreviewPanel,
    RealPreviewRuntime,
    real_preview_action,
)
from forge_design.web.recent_projects import recent_action, show_home
from forge_design.web.routes import show_routes
from forge_design.web.security import is_local_action
from forge_design.web.source import show_source
from forge_design.web.template_viewer import (
    show_template,
    show_template_tree,
    show_templates,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def _style(request: Request) -> Response:
    css = files("forge_design.web").joinpath("static/shell.css")
    return Response(body=css.read_bytes(), content_type="text/css; charset=utf-8")


def _graph_script(request: Request) -> Response:
    script = files("forge_design.web").joinpath("static/route-graph.js")
    return Response(
        body=script.read_bytes(), content_type="text/javascript; charset=utf-8"
    )


def _editor_preview_style(request: Request) -> Response:
    css = files("forge_design.web").joinpath("static/editor-preview.css")
    return Response(body=css.read_bytes(), content_type="text/css; charset=utf-8")


def _entity_graph_script(request: Request) -> Response:
    script = files("forge_design.web").joinpath("static/entity-graph.js")
    return Response(
        body=script.read_bytes(), content_type="text/javascript; charset=utf-8"
    )


WsgiApp = Callable[[dict[str, Any], Callable[..., Any]], Iterable[bytes]]


def _require_local_host(app: WsgiApp, server: WSGIServer) -> WsgiApp:
    """Refuser tout Host autre que l'adresse d'écoute exacte (DNS rebinding).

    Une page d'origine étrangère rebindée sur 127.0.0.1 garde son propre Host :
    sans ce contrôle, elle lirait les réponses GET comme une page same-origin.
    """

    def guarded(
        environ: dict[str, Any], start_response: Callable[..., Any]
    ) -> Iterable[bytes]:
        port = server.server_port
        host = environ.get("HTTP_HOST")
        # Sur le port 80, les navigateurs omettent le port dans Host.
        if host != f"{DEFAULT_HOST}:{port}" and not (
            port == 80 and host == DEFAULT_HOST
        ):
            body = "Hôte de requête non autorisé.".encode()
            start_response(
                "400 Bad Request",
                [
                    ("Content-Type", "text/plain; charset=utf-8"),
                    ("Content-Length", str(len(body))),
                    ("Cache-Control", "no-store"),
                ],
            )
            return [body]
        return app(environ, start_response)

    return guarded


def create_application(
    *,
    recent_projects: RecentProjects | None = None,
    real_preview: RealPreviewRuntime | None = None,
) -> Application:
    """Créer l'application Forge avec ses seules routes publiques explicites.

    Aucun chargement de config.py, bootstrap.py ou mvc du répertoire courant.
    Les middlewares Forge par défaut restent en place ; le shell est public.
    Sans runtime fourni, la preview réelle reste désactivée : son origine
    d'encadrement n'est connue qu'après le bind (create_server).
    """
    registry = create_tool_registry()
    context = CurrentProjectContext()
    store = recent_projects if recent_projects is not None else RecentProjects()
    runtime = real_preview if real_preview is not None else RealPreviewRuntime()
    panel = RealPreviewPanel(runtime, registry)

    # Un autre projet valide ne devient courant qu'après l'arrêt de la preview.
    selector = ProjectSelector(registry, context, store, before_change=runtime.stop)

    def index(request: Request) -> Response:
        return show_home(request, context, store, registry)

    def show(request: Request) -> Response:
        return show_inspector(request, context)

    def close(request: Request) -> Response:
        if not is_local_action(request):
            return Response.html("Origine de la requête non autorisée.", status=403)
        # Arrêter la preview de ce projet avant de le fermer, jamais l'inverse.
        if not runtime.stop():
            return show_home(
                request,
                context,
                store,
                registry,
                error=(
                    "La preview réelle n'a pas pu être arrêtée : "
                    "le projet courant est conservé."
                ),
                status=409,
            )
        context.clear()
        return index(request)

    def inspect(request: Request) -> Response:
        return inspect_submission(request, selector, context)

    def refresh(request: Request) -> Response:
        return refresh_project(request, registry, context, release=runtime.stop)

    def routes(request: Request) -> Response:
        return show_routes(request, context, registry)

    def entities(request: Request) -> Response:
        return show_entities(request, context, registry)

    def debug(request: Request) -> Response:
        return show_debug(request, context, registry)

    def debug_detail(request: Request) -> Response:
        return show_debug_detail(request, context, registry)

    def templates(request: Request) -> Response:
        return show_templates(request, context, registry)

    def template(request: Request) -> Response:
        return show_template(request, context)

    def template_tree(request: Request) -> Response:
        return show_template_tree(request, context)

    def source(request: Request) -> Response:
        return show_source(request, context)

    def editor(request: Request) -> Response:
        return show_editor(request, context, real_preview=panel)

    def editor_preview(request: Request) -> Response:
        return show_editor_preview(request, context)

    def editor_post(request: Request) -> Response:
        return editor_action(request, context)

    def real_preview_start(request: Request) -> Response:
        return real_preview_action(request, context, registry, runtime, stop=False)

    def real_preview_stop(request: Request) -> Response:
        return real_preview_action(request, context, registry, runtime, stop=True)

    def open_recent(request: Request) -> Response:
        return recent_action(request, context, registry, store, selector=selector)

    def remove_recent(request: Request) -> Response:
        return recent_action(
            request, context, registry, store, selector=selector, remove=True
        )

    router = Router()
    router.add("GET", "/", index, public=True, no_store=True)
    router.add("GET", "/shell.css", _style, public=True)
    router.add("GET", "/route-graph.js", _graph_script, public=True)
    router.add("GET", "/entity-graph.js", _entity_graph_script, public=True)
    router.add("GET", "/inspector", show, public=True, no_store=True)
    # Ces actions runtime sans session exigent une origine locale exacte.
    router.add("POST", "/inspector", inspect, public=True, csrf=False, no_store=True)
    router.add("POST", "/project/close", close, public=True, csrf=False, no_store=True)
    router.add(
        "POST", "/project/refresh", refresh, public=True, csrf=False, no_store=True
    )
    router.add(
        "POST",
        "/project/open-recent",
        open_recent,
        public=True,
        csrf=False,
        no_store=True,
    )
    router.add(
        "POST",
        "/project/recent/remove",
        remove_recent,
        public=True,
        csrf=False,
        no_store=True,
    )
    router.add("GET", "/routes", routes, public=True, no_store=True)
    router.add("GET", "/entities", entities, public=True, no_store=True)
    router.add("GET", "/debug", debug, public=True, no_store=True)
    router.add("GET", "/debug/event", debug_detail, public=True, no_store=True)
    router.add("GET", "/source", source, public=True, no_store=True)
    router.add("GET", "/templates", templates, public=True, no_store=True)
    router.add("GET", "/templates/view", template, public=True, no_store=True)
    router.add("GET", "/templates/tree", template_tree, public=True, no_store=True)
    router.add("GET", "/editor", editor, public=True, no_store=True)
    # Document encadré par l'éditeur : CSP et X-Frame-Options propres à la réponse.
    router.add("GET", "/editor/preview", editor_preview, public=True, no_store=True)
    router.add("GET", "/editor-preview.css", _editor_preview_style, public=True)
    # Mutations du .design.json : même contrôle d'origine locale exacte.
    router.add(
        "POST", "/editor/action", editor_post, public=True, csrf=False, no_store=True
    )
    # Preview réelle : seules mutations du runtime, jamais par GET.
    router.add(
        "POST",
        "/editor/real-preview/start",
        real_preview_start,
        public=True,
        csrf=False,
        no_store=True,
    )
    router.add(
        "POST",
        "/editor/real-preview/stop",
        real_preview_stop,
        public=True,
        csrf=False,
        no_store=True,
    )
    return Application(router, api_routes_module=None)


class ForgeDesignServer(WSGIServer):
    """Écoute Forge Design et runtime de preview réelle qu'elle possède.

    server_close() (donc la sortie d'un bloc with) ferme d'abord le runtime :
    proxy, puis runner.
    """

    real_preview: RealPreviewRuntime | None = None

    def server_close(self) -> None:
        try:
            if self.real_preview is not None:
                self.real_preview.close()
        finally:
            super().server_close()


def create_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    recent_projects: RecentProjects | None = None,
    real_preview: RealPreviewRuntime | None = None,
) -> ForgeDesignServer:
    """Ouvrir l'écoute locale servant exclusivement l'adaptateur WSGI Forge.

    Seul 127.0.0.1 est accepté ; 0 demande un port éphémère. Toute requête dont
    le Host diffère de l'adresse d'écoute est refusée en 400. Les erreurs de bind
    restent des OSError, sans repli. Fermer avec with ; pour arrêter une boucle
    dans un autre thread, appeler shutdown puis join avant de quitter le bloc.
    La fermeture arrête aussi la preview réelle (server.real_preview) ; un
    runtime peut être fourni explicitement (tests), sinon il est créé ici.
    """
    if host != DEFAULT_HOST:
        raise ValueError("Seul l'hôte local 127.0.0.1 est autorisé.")
    if isinstance(port, bool) or not 0 <= port <= 65535:
        raise ValueError("Le port doit être compris entre 0 et 65535.")
    runtime = real_preview if real_preview is not None else RealPreviewRuntime()
    application = create_application(
        recent_projects=recent_projects, real_preview=runtime
    )
    wsgi_app = create_wsgi_app(application)
    server = make_server(host, port, wsgi_app, server_class=ForgeDesignServer)
    server.real_preview = runtime
    # Le port effectif (0 → éphémère) n'est connu qu'après le bind : il fixe
    # l'origine d'encadrement du proxy, jamais l'en-tête Host d'une requête.
    runtime.bind_editor_origin(f"http://{DEFAULT_HOST}:{server.server_port}")
    server.set_app(_require_local_host(wsgi_app, server))
    return server


_STOP_SIGNALS = tuple(
    getattr(signal, name) for name in ("SIGTERM", "SIGHUP") if hasattr(signal, name)
)


@contextmanager
def _stop_signals_as_interrupt() -> Generator[None, None, None]:
    """SIGTERM et SIGHUP arrêtent le service comme Ctrl+C (thread principal seul).

    Sans cela, ces signaux tuent Forge Design sans exécuter le finally : la
    preview réelle, lancée dans sa propre session, survivrait orpheline.
    Après le premier signal, les suivants sont ignorés pendant la fermeture ;
    les gestionnaires d'origine sont restaurés en sortie.
    """
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous: dict[int, Any] = {}

    def interrupt(signum: int, frame: object) -> None:
        for number in previous:
            signal.signal(number, signal.SIG_IGN)
        raise KeyboardInterrupt

    for number in _STOP_SIGNALS:
        previous[number] = signal.signal(number, interrupt)
    try:
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def run_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    on_ready: Callable[[], None] | None = None,
) -> None:
    """Servir Forge jusqu'à Ctrl+C, SIGTERM ou SIGHUP, puis fermer preview et écoute.

    La preview est fermée dans un finally : signal d'arrêt, exception ou fin
    normale.
    """
    # Signaux à l'extérieur : un second signal reste ignoré pendant la fermeture.
    with _stop_signals_as_interrupt(), create_server(host, port) as server:
        try:
            if on_ready is not None:
                on_ready()
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            if server.real_preview is not None:
                server.real_preview.close()
