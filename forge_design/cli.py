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
    parser.add_argument(
        "--module",
        action="append",
        default=[],
        metavar="PACKAGE",
        help="Activer un module spécialisé installé (paquet Python, répétable).",
    )
    args = parser.parse_args(argv)
    # Garder --version et --help indépendants des modules et du backend Web.
    from forge_design.modules import activate_modules

    try:
        # Seuls les paquets nommés ici sont importés, jamais depuis un projet.
        modules = activate_modules(tuple(args.module))
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    for diagnostic in modules.diagnostics:
        print(
            f"Module {diagnostic.package} non chargé ({diagnostic.code}) : "
            f"{diagnostic.message}",
            file=sys.stderr,
        )
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
        run_server(
            host=DEFAULT_HOST, port=DEFAULT_PORT, on_ready=ready, modules=modules
        )
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
