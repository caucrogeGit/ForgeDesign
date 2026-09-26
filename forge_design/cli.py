"""Interface en ligne de commande minimale de Forge Design."""

import argparse
import errno
import sys
import webbrowser
from collections.abc import Sequence

from forge_design import __version__


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="forge-design")
    parser.add_argument(
        "--version", action="version", version=f"Forge Design {__version__}"
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="Ne pas ouvrir le navigateur."
    )
    args = parser.parse_args(argv)
    # Garder --version et --help indépendants du chargement du backend Web.
    from forge_design.web.server import DEFAULT_HOST, DEFAULT_PORT, run_server

    def ready() -> None:
        url = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/"
        print(f"Forge Design {__version__}", flush=True)
        print(url, flush=True)
        if not args.no_browser:
            try:
                opened = webbrowser.open(url)
            except (webbrowser.Error, OSError):
                opened = False
            if not opened:
                print(
                    "Navigateur indisponible ; ouvrez l’URL manuellement.",
                    file=sys.stderr,
                )

    try:
        run_server(host=DEFAULT_HOST, port=DEFAULT_PORT, on_ready=ready)
    except KeyboardInterrupt:
        return 0
    except OSError as error:
        message = (
            f"Le port {DEFAULT_PORT} est déjà occupé."
            if error.errno == errno.EADDRINUSE
            else f"Erreur du serveur local : {error}"
        )
        print(message, file=sys.stderr)
        return 1
    return 0
