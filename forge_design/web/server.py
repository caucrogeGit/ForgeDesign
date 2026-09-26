"""HTTP local servant une ressource HTML du paquet, sans accès aux projets."""

from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib.resources import files

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


class _Handler(BaseHTTPRequestHandler):
    # Borne l'attente d'un client inactif, notamment pendant l'arrêt.
    timeout = 2.0

    def do_GET(self) -> None:
        if self.path != "/":
            self.send_error(404)
            return
        body = files("forge_design.web").joinpath("templates/index.html").read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        """Ne pas journaliser les chemins et en-têtes fournis par les clients."""


def create_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> HTTPServer:
    """Ouvrir l'écoute locale sans lancer la boucle de traitement.

    Seul 127.0.0.1 est accepté. Le port 0 demande un port éphémère au système.
    ValueError signale un paramètre invalide ; les erreurs de bind (dont port
    occupé) restent des OSError avec leur errno. Aucun repli sur un autre port.
    L'appelant doit fermer le serveur, idéalement via un bloc with. Pour arrêter
    serve_forever depuis un autre thread : shutdown, join, puis server_close.
    """
    if host != DEFAULT_HOST:
        raise ValueError("Seul l'hôte local 127.0.0.1 est autorisé.")
    if isinstance(port, bool) or not 0 <= port <= 65535:
        raise ValueError("Le port doit être compris entre 0 et 65535.")
    return HTTPServer((host, port), _Handler)


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    """Servir dans le thread appelant jusqu'à Ctrl+C, puis libérer le socket.

    Aucune ouverture de navigateur et aucune création de thread implicite.
    Les erreurs autres que KeyboardInterrupt restent propagées après fermeture.
    """
    with create_server(host, port) as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
