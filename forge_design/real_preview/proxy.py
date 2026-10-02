"""Proxy local de la preview réelle (FD-REALPREVIEW-003).

Listener dédié sur 127.0.0.1:<port proxy>, origine distincte de Forge Design
et du runner. Seuls GET et HEAD passent. /static/ est servi depuis
<projet>/static par lecture confinée ; tout autre chemin est relayé, sans
suivre de redirection, vers http://127.0.0.1:<port du runner> uniquement. Le
port vient exclusivement de controller.status() : aucune requête ne choisit
sa destination.

Les corps HTML, CSS et JS ne sont jamais réécrits. Seuls les en-têtes
d'encadrement changent : X-Frame-Options est retiré et frame-ancestors est
remplacé par l'origine de l'éditeur. Le proxy ne démarre ni n'arrête jamais
le runner, ne lance aucun processus et n'écrit rien.
"""

import math
import mimetypes
import os
import re
import socket
import time
import urllib.parse
from collections.abc import Iterable
from dataclasses import dataclass
from http import HTTPStatus
from http.client import HTTPConnection, HTTPException
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from stat import S_ISDIR, S_ISREG
from typing import Any

from forge_design.forge.filesystem import open_directory
from forge_design.forge.source import unsafe_relative_path
from forge_design.limits import MAX_SOURCE_PATH_LENGTH
from forge_design.real_preview.controller import RealPreviewController

HOST = "127.0.0.1"
MAX_REAL_PREVIEW_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_REAL_PREVIEW_STATIC_BYTES = 8 * 1024 * 1024
MAX_REAL_PREVIEW_QUERY_LENGTH = 8192
_MAX_CONFIG_BYTES = 64 * 1024 * 1024
_MAX_SECONDS = 3600.0
_CHUNK = 64 * 1024
_MAX_DISCARDED_BODY = 1024 * 1024
_CLIENT_TIMEOUT = 15.0
_ALLOWED_METHODS = "GET, HEAD"
_STATIC_PREFIX = "/static/"
_ORIGIN = re.compile(r"http://127\.0\.0\.1:([1-9][0-9]{0,4})")
_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "proxy-connection",
        "te",
        "trailer",
        "trailers",
        "transfer-encoding",
        "upgrade",
    }
)
# Accept-Encoding n'est pas relayé : la cible répond sans compression et le
# corps reste opaque. Authorization ne l'est pas non plus (routes publiques).
_FORWARDED_REQUEST_HEADERS = (
    "Accept",
    "Accept-Language",
    "User-Agent",
    "Cookie",
    "Referer",
    "Origin",
    "Cache-Control",
    "Pragma",
    "If-None-Match",
    "If-Modified-Since",
    "HX-Request",
    "HX-Target",
    "HX-Trigger",
    "HX-Trigger-Name",
    "HX-Current-URL",
    "HX-Boosted",
    "HX-History-Restore-Request",
    "HX-Prompt",
)
# Types déterministes : seule la table intégrée, sans /etc/mime.types.
_MIME = mimetypes.MimeTypes(filenames=())


def validate_frame_ancestor_origin(origin: object) -> str:
    """Exactement http://127.0.0.1:<port 1-65535>, sans chemin ni joker."""
    match = _ORIGIN.fullmatch(origin) if isinstance(origin, str) else None
    if match is None or int(match.group(1)) > 65535:
        raise ValueError("Origine d'encadrement attendue : http://127.0.0.1:<port>.")
    return match.group(0)


def rewrite_frame_ancestors(policies: Iterable[str], origin: str) -> list[str]:
    """Remplacer frame-ancestors dans chaque politique CSP active, rien d'autre.

    Découpage de la spécification CSP : liste de politiques séparées par des
    virgules, directives séparées par des points-virgules ; le nom d'une
    directive est son premier mot, sans casse. Les autres directives restent
    dans leur ordre. Plusieurs en-têtes restent séparés (cumulatifs). Si aucune
    politique ne contient frame-ancestors, une politique supplémentaire
    « frame-ancestors <origin> » est ajoutée.
    """
    validate_frame_ancestor_origin(origin)
    replacement = f"frame-ancestors {origin}"
    rewritten: list[str] = []
    found = False
    for header in policies:
        serialized: list[str] = []
        for policy in header.split(","):
            directives: list[str] = []
            for directive in policy.split(";"):
                text = directive.strip()
                if not text:
                    continue
                if text.split(None, 1)[0].lower() == "frame-ancestors":
                    found = True
                    text = replacement
                directives.append(text)
            serialized.append("; ".join(directives))
        rewritten.append(", ".join(serialized))
    if not found:
        rewritten.append(replacement)
    return rewritten


def rewrite_location(location: str, runner_port: int) -> str:
    """URL du runner (absolue ou sans schéma) → chemin relatif ; sinon intacte."""
    try:
        parts = urllib.parse.urlsplit(location)
    except ValueError:
        return location
    if parts.scheme not in ("", "http") or parts.netloc != f"{HOST}:{runner_port}":
        return location
    relative = parts.path or "/"
    if parts.query:
        relative += "?" + parts.query
    if parts.fragment:
        relative += "#" + parts.fragment
    return relative


@dataclass(frozen=True)
class RealPreviewProxyConfig:
    """Délai par requête cible et bornes de corps, validés à la construction."""

    request_timeout: float = 10.0
    max_response_bytes: int = MAX_REAL_PREVIEW_RESPONSE_BYTES
    max_static_bytes: int = MAX_REAL_PREVIEW_STATIC_BYTES

    def __post_init__(self) -> None:
        value: object = getattr(self, "request_timeout")
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
            or not 0 < value <= _MAX_SECONDS
        ):
            raise ValueError(
                f"request_timeout : nombre attendu dans ]0, {_MAX_SECONDS}]."
            )
        for name in ("max_response_bytes", "max_static_bytes"):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= _MAX_CONFIG_BYTES:
                raise ValueError(
                    f"{name} : entier attendu dans [1, {_MAX_CONFIG_BYTES}]."
                )


class _StaticRefused(Exception):
    """Fichier statique non régulier, lié, trop gros ou modifié pendant la lecture."""


def _read_static(root: Path, parts: list[str], limit: int) -> bytes:
    """<root>/static/<parts> : aucun lien suivi, fichier ordinaire, lecture bornée.

    FileNotFoundError si un segment manque ; _StaticRefused sinon.
    """
    try:
        with (
            open_directory(str(root)) as anchor,
            open_directory("static", anchor) as current,
        ):
            descriptors: list[int] = []
            try:
                directory = current
                for part in parts[:-1]:
                    directory = os.open(
                        part,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=directory,
                    )
                    descriptors.append(directory)
                    if not S_ISDIR(os.fstat(directory).st_mode):
                        raise _StaticRefused
                metadata = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
                if not S_ISREG(metadata.st_mode):
                    raise _StaticRefused
                descriptor = os.open(
                    parts[-1],
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                    dir_fd=directory,
                )
                descriptors.append(descriptor)
                opened = os.fstat(descriptor)
                if not S_ISREG(opened.st_mode) or not os.path.samestat(
                    metadata, opened
                ):
                    raise _StaticRefused
                if opened.st_size > limit:
                    raise _StaticRefused
                chunks: list[bytes] = []
                size = 0
                while size <= limit and (chunk := os.read(descriptor, _CHUNK)):
                    chunks.append(chunk)
                    size += len(chunk)
                current_stat = os.fstat(descriptor)
                if (
                    size != opened.st_size
                    or current_stat.st_size != opened.st_size
                    or current_stat.st_mtime_ns != opened.st_mtime_ns
                ):
                    raise _StaticRefused
                return b"".join(chunks)
            finally:
                for descriptor in reversed(descriptors):
                    os.close(descriptor)
    except FileNotFoundError:
        raise
    except NotADirectoryError as error:
        raise _StaticRefused from error
    except OSError as error:
        # ELOOP (lien refusé par O_NOFOLLOW), EACCES, etc.
        raise _StaticRefused from error


def _static_parts(raw_path: str) -> list[str] | None:
    """Segments relatifs à static/ ; None si le chemin est refusé."""
    relative = raw_path[len(_STATIC_PREFIX) :]
    if "%2f" in relative.lower() or "%5c" in relative.lower():
        return None
    try:
        decoded = urllib.parse.unquote(relative, errors="strict")
    except UnicodeDecodeError:
        return None
    if not decoded or unsafe_relative_path(decoded):
        return None
    return decoded.split("/")


class _ProxyHandler(BaseHTTPRequestHandler):
    # Un client lent ou mentant sur sa longueur ne bloque pas un thread indéfiniment.
    timeout = _CLIENT_TIMEOUT

    @property
    def proxy(self) -> "RealPreviewProxyServer":
        server = self.server
        assert isinstance(server, RealPreviewProxyServer)
        return server

    # ── Réponses produites par le proxy ──────────────────────────────────────

    def _plain(
        self, status: HTTPStatus, message: str, extra: Iterable[tuple[str, str]] = ()
    ) -> None:
        body = (message + "\n").encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            f"default-src 'none'; frame-ancestors {self.proxy.frame_ancestor_origin}",
        )
        for name, value in extra:
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    # ── Aiguillage ───────────────────────────────────────────────────────────

    def do_GET(self) -> None:
        self._dispatch()

    def do_HEAD(self) -> None:
        self._dispatch()

    def _discard_body(self) -> None:
        """Lire un corps annoncé (≤ 1 Mio) avant de le refuser.

        Fermer une connexion dont des octets restent non lus provoque un RST qui
        peut effacer la réponse chez le client. Le corps n'est jamais relayé.
        """
        length = self.headers.get("Content-Length", "").strip()
        if length.isdigit() and 0 < int(length) <= _MAX_DISCARDED_BODY:
            try:
                self.rfile.read(int(length))
            except OSError:
                pass

    def _refuse_method(self) -> None:
        self._discard_body()
        if self._host_allowed():
            self._plain(
                HTTPStatus.METHOD_NOT_ALLOWED,
                "Méthode non autorisée.",
                [("Allow", _ALLOWED_METHODS)],
            )

    def __getattr__(self, name: str) -> Any:
        # Toute autre méthode HTTP (POST, PUT, OPTIONS, CONNECT, FOO…) : 405.
        if name.startswith("do_"):
            return self._refuse_method
        raise AttributeError(name)

    def _host_allowed(self) -> bool:
        if self.headers.get_all("Host") == [f"{HOST}:{self.proxy.server_port}"]:
            return True
        self._plain(HTTPStatus.BAD_REQUEST, "Hôte de requête non autorisé.")
        return False

    def _dispatch(self) -> None:
        if not self._host_allowed():
            return
        target = self.path
        path, _, query = target.partition("?")
        if (
            not path.startswith("/")
            or len(path) > MAX_SOURCE_PATH_LENGTH
            or len(query) > MAX_REAL_PREVIEW_QUERY_LENGTH
            or not target.isascii()
            or any(ord(c) < 0x21 or ord(c) == 0x7F for c in target)
        ):
            self._plain(HTTPStatus.BAD_REQUEST, "Cible de requête refusée.")
            return
        if self.headers.get("Transfer-Encoding") is not None or self.headers.get(
            "Content-Length", "0"
        ) not in ("", "0"):
            self._discard_body()
            self._plain(HTTPStatus.BAD_REQUEST, "Corps de requête refusé.")
            return
        status = self.proxy.controller.status()
        if (
            status.state != "running"
            or status.port is None
            or status.project_root is None
        ):
            self._plain(HTTPStatus.SERVICE_UNAVAILABLE, "Preview réelle indisponible.")
            return
        if path == "/static" or path.startswith(_STATIC_PREFIX):
            self._serve_static(status.project_root, path)
        else:
            self._forward(status.port, target)

    # ── /static/ ─────────────────────────────────────────────────────────────

    def _serve_static(self, root: Path, path: str) -> None:
        parts = _static_parts(path) if path.startswith(_STATIC_PREFIX) else None
        if parts is None:
            self._plain(HTTPStatus.BAD_REQUEST, "Chemin statique refusé.")
            return
        try:
            body = _read_static(root, parts, self.proxy.config.max_static_bytes)
        except FileNotFoundError:
            self._plain(HTTPStatus.NOT_FOUND, "Fichier statique introuvable.")
            return
        except _StaticRefused:
            self._plain(HTTPStatus.FORBIDDEN, "Fichier statique refusé.")
            return
        content_type = _MIME.guess_type(parts[-1])[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    # ── Relais vers le runner ────────────────────────────────────────────────

    def _forward(self, runner_port: int, target: str) -> None:
        config = self.proxy.config
        deadline = time.monotonic() + config.request_timeout
        connection = HTTPConnection(HOST, runner_port, timeout=config.request_timeout)
        try:
            try:
                connection.putrequest(
                    self.command, target, skip_host=True, skip_accept_encoding=True
                )
                connection.putheader("Host", f"{HOST}:{runner_port}")
                for name in _FORWARDED_REQUEST_HEADERS:
                    for value in self.headers.get_all(name) or ():
                        connection.putheader(name, value)
                connection.endheaders()
                response = connection.getresponse()
                body = b""
                if self.command != "HEAD":
                    chunks: list[bytes] = []
                    size = 0
                    while chunk := response.read(_CHUNK):
                        size += len(chunk)
                        if size > config.max_response_bytes:
                            self._plain(
                                HTTPStatus.BAD_GATEWAY,
                                "Réponse de preview trop volumineuse.",
                            )
                            return
                        if time.monotonic() > deadline:
                            raise TimeoutError
                        chunks.append(chunk)
                    body = b"".join(chunks)
                    declared = response.getheader("Content-Length", "").strip()
                    if declared.isdigit() and int(declared) != len(body):
                        # http.client rend un corps partiel sans erreur : refuser.
                        raise HTTPException("corps amont incomplet")
            except (TimeoutError, socket.timeout):
                self._plain(HTTPStatus.GATEWAY_TIMEOUT, "Preview réelle sans réponse.")
                return
            except (OSError, HTTPException, ValueError):
                self._plain(HTTPStatus.BAD_GATEWAY, "Preview réelle injoignable.")
                return
            self._relay(
                response.status,
                response.reason,
                response.getheaders(),
                body,
                runner_port,
            )
        finally:
            connection.close()

    def _relay(
        self,
        status: int,
        reason: str,
        headers: list[tuple[str, str]],
        body: bytes,
        runner_port: int,
    ) -> None:
        connection_tokens = {
            token.strip().lower()
            for name, value in headers
            if name.lower() == "connection"
            for token in value.split(",")
        }
        dropped = (
            _HOP_BY_HOP | connection_tokens | {"x-frame-options", "content-length"}
        )
        policies: list[str] = []
        kept: list[tuple[str, str]] = []
        declared_length: str | None = None
        for name, value in headers:
            lower = name.lower()
            if lower == "content-length":
                declared_length = value
            if lower in dropped:
                continue
            if lower == "content-security-policy":
                policies.append(value)
                continue
            if lower == "location":
                value = rewrite_location(value, runner_port)
            kept.append((name, value))
        for policy in rewrite_frame_ancestors(
            policies, self.proxy.frame_ancestor_origin
        ):
            kept.append(("Content-Security-Policy", policy))
        self.send_response_only(status, reason)
        for name, value in kept:
            self.send_header(name, value)
        if self.command == "HEAD":
            if declared_length is not None and declared_length.strip().isdigit():
                self.send_header("Content-Length", declared_length.strip())
        elif not (100 <= status < 200 or status in (204, 304)):
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD" and body:
            self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        """Silencieux : aucune requête de preview n'est journalisée."""


class RealPreviewProxyServer(ThreadingMixIn, HTTPServer):
    """Listener du proxy ; un thread par requête, jamais de port partagé."""

    daemon_threads = True
    allow_reuse_address = False
    allow_reuse_port = False

    def __init__(
        self,
        port: int,
        controller: RealPreviewController,
        frame_ancestor_origin: str,
        config: RealPreviewProxyConfig,
    ) -> None:
        self.controller = controller
        self.frame_ancestor_origin = frame_ancestor_origin
        self.config = config
        super().__init__((HOST, port), _ProxyHandler)

    def handle_error(self, request: Any, client_address: Any) -> None:
        """Silencieux : un client qui ferme sa connexion n'est pas une erreur."""


def create_real_preview_proxy(
    controller: RealPreviewController,
    *,
    frame_ancestor_origin: str,
    host: str = HOST,
    port: int = 0,
    config: RealPreviewProxyConfig | None = None,
) -> RealPreviewProxyServer:
    """Ouvrir le listener du proxy, sans thread : appeler serve_forever().

    Seul 127.0.0.1 est accepté ; 0 demande un port éphémère. Les erreurs de
    bind restent des OSError, sans repli. Fermer avec with ; depuis un autre
    thread, shutdown() puis join avant de quitter le bloc.
    """
    if host != HOST:
        raise ValueError("Seul l'hôte local 127.0.0.1 est autorisé.")
    if isinstance(port, bool) or not 0 <= port <= 65535:
        raise ValueError("Le port doit être compris entre 0 et 65535.")
    origin = validate_frame_ancestor_origin(frame_ancestor_origin)
    return RealPreviewProxyServer(
        port,
        controller,
        origin,
        config if config is not None else RealPreviewProxyConfig(),
    )
