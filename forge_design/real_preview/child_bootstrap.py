"""Bootstrap enfant de la preview réelle (FD-REALPREVIEW-001A, FD-REALPREVIEW-002).

Exécuté uniquement dans le processus enfant, par l'interpréteur du projet :

    <projet>/.venv/bin/python -I -B -u child_bootstrap.py --port <port>

avec cwd = racine canonique du projet. Bibliothèque standard seulement : ce
fichier n'importe jamais forge_design, qui n'est pas installé chez le projet.

Ordre normatif : arguments, garde d'audit socket.bind, compatibilité Forge,
import app (config.py, env/dev, bootstrap.py), create_wsgi_app, sondes du
mode analyse avec --inspect (child_inspect.py, FD-INSPECT-001), garde Host,
bind 127.0.0.1:<port>, serve_forever. L'hôte est une constante et le port un
argument : aucune configuration du projet ne peut les modifier.

La garde d'audit refuse un bind non loopback avant l'appel système, dans ce
processus seulement ; code natif, ctypes et sous-processus restent hors de
portée. Ce n'est pas une sandbox.
"""

import errno
import importlib
import importlib.metadata
import importlib.util
import ipaddress
import os
import socket
import socketserver
import sys
import traceback
from collections.abc import Callable, Iterable, Sequence
from typing import Any
from wsgiref.simple_server import WSGIServer, make_server

HOST = "127.0.0.1"
SUPPORTED_FORGE_VERSION = "1.0.0rc9"
MIN_PORT = 1024
MAX_PORT = 65535

EXIT_USAGE = 2
EXIT_INCOMPATIBLE = 3
EXIT_PORT_IN_USE = 4
EXIT_IMPORT = 5
# Hors contrat FD-REALPREVIEW-001A : bind impossible pour une autre raison.
EXIT_BIND = 6

_IPV6_LOOPBACK = ipaddress.IPv6Address("::1")
_BAD_REQUEST = b"Bad Request\n"

WsgiApp = Callable[[dict[str, Any], Callable[..., Any]], Iterable[bytes]]


def parse_port(arguments: Sequence[str]) -> int | None:
    """Exactement --port <entier décimal canonique>, dans [1024, 65535]."""
    if len(arguments) != 2 or arguments[0] != "--port":
        return None
    text = arguments[1]
    if not (text.isascii() and text.isdigit()) or str(int(text)) != text:
        return None
    port = int(text)
    return port if MIN_PORT <= port <= MAX_PORT else None


def parse_arguments(arguments: Sequence[str]) -> tuple[int, bool] | None:
    """--port <port>, suivi ou non de --inspect (mode analyse, FD-INSPECT-001)."""
    inspect = len(arguments) == 3 and arguments[2] == "--inspect"
    port = parse_port(arguments[:2] if inspect else arguments)
    return None if port is None else (port, inspect)


def _load_inspect() -> Any:
    """child_inspect.py voisin, chargé par chemin (-I : dossier hors sys.path)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "child_inspect.py")
    spec = importlib.util.spec_from_file_location("_forge_design_inspect", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bind_allowed(family: object, address: object) -> bool:
    """Seules les IP littérales 127.0.0.0/8 et ::1 ; sockets Unix libres.

    Les noms (localhost, nom de machine), l'adresse vide, 0.0.0.0, :: et toute
    autre famille réseau sont refusés.
    """
    if family == getattr(socket, "AF_UNIX", object()):
        return True
    if family not in (socket.AF_INET, socket.AF_INET6):
        return False
    if not isinstance(address, tuple) or not address:
        return False
    host: object = address[0]  # pyright: ignore[reportUnknownVariableType]
    if not isinstance(host, str):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    if family == socket.AF_INET:
        return ip.version == 4 and ip.is_loopback
    return ip == _IPV6_LOOPBACK


def audit_hook(event: str, arguments: tuple[Any, ...]) -> None:
    """Hook d'audit : l'événement socket.bind précède l'appel système."""
    if event != "socket.bind":
        return
    sock, address = arguments
    if not bind_allowed(getattr(sock, "family", None), address):
        raise PermissionError(
            f"Preview réelle : bind refusé sur {address!r} (loopback uniquement)."
        )


def host_guard(application: WsgiApp, port: int) -> WsgiApp:
    """Tout Host autre que 127.0.0.1:<port> : 400, sans appeler l'application."""
    expected = f"{HOST}:{port}"

    def guarded(
        environ: dict[str, Any], start_response: Callable[..., Any]
    ) -> Iterable[bytes]:
        if environ.get("HTTP_HOST") != expected:
            start_response(
                "400 Bad Request",
                [
                    ("Content-Type", "text/plain; charset=utf-8"),
                    ("Cache-Control", "no-store"),
                    ("Content-Length", str(len(_BAD_REQUEST))),
                ],
            )
            return [_BAD_REQUEST]
        return application(environ, start_response)

    return guarded


class PreviewServer(socketserver.ThreadingMixIn, WSGIServer):
    """Un thread par requête ; jamais de partage d'un port déjà utilisé."""

    daemon_threads = True
    allow_reuse_address = False
    allow_reuse_port = False


def _error(message: str) -> None:
    print(f"Preview réelle : {message}", file=sys.stderr, flush=True)


def _load_wsgi_factory() -> Callable[..., Any] | None:
    """Vérifier Forge avant que la racine du projet ne soit dans sys.path."""
    try:
        version = importlib.metadata.version("forge-mvc")
    except importlib.metadata.PackageNotFoundError:
        version = None
    if version != SUPPORTED_FORGE_VERSION:
        required = SUPPORTED_FORGE_VERSION
        _error(f"forge-mvc {version!r} non supporté ({required} requis).")
        return None
    try:
        module = importlib.import_module("core.app.wsgi")
    except Exception:
        traceback.print_exc()
        _error("core.app.wsgi introuvable.")
        return None
    factory = getattr(module, "create_wsgi_app", None)
    if not callable(factory):
        _error("core.app.wsgi.create_wsgi_app introuvable.")
        return None
    return factory


def main(arguments: Sequence[str] | None = None) -> int:
    parsed = parse_arguments(sys.argv[1:] if arguments is None else arguments)
    if parsed is None:
        _error("usage : child_bootstrap.py --port <1024-65535> [--inspect]")
        return EXIT_USAGE
    port, inspect = parsed
    # Avant tout code Forge ou projet.
    sys.addaudithook(audit_hook)
    factory = _load_wsgi_factory()
    if factory is None:
        return EXIT_INCOMPATIBLE
    sys.path.insert(0, os.getcwd())
    try:
        project = importlib.import_module("app")
    except (Exception, SystemExit):
        traceback.print_exc()
        _error("import du projet impossible.")
        return EXIT_IMPORT
    application = getattr(project, "application", None)
    if not callable(getattr(application, "dispatch", None)):
        _error("app.application.dispatch introuvable.")
        return EXIT_INCOMPATIBLE
    try:
        wsgi_app = factory(application)
    except Exception:
        traceback.print_exc()
        _error("create_wsgi_app a échoué.")
        return EXIT_INCOMPATIBLE
    if inspect:
        try:
            wsgi_app = _load_inspect().install(wsgi_app)
        except Exception:
            traceback.print_exc()
            _error("sondes du mode analyse impossibles à poser.")
            return EXIT_INCOMPATIBLE
    try:
        server = make_server(
            HOST, port, host_guard(wsgi_app, port), server_class=PreviewServer
        )
    except OSError as error:
        if error.errno == errno.EADDRINUSE:
            _error(f"port {port} occupé.")
            return EXIT_PORT_IN_USE
        traceback.print_exc()
        _error("bind impossible.")
        return EXIT_BIND
    print(f"Preview réelle : écoute sur http://{HOST}:{port}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
