"""Interface en ligne de commande minimale de Forge Design."""

import argparse
import errno
import sys
from collections.abc import Sequence

from forge_design import __version__


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="forge-design")
    parser.add_argument(
        "--version", action="version", version=f"Forge Design {__version__}"
    )
    parser.parse_args(argv)
    # Garder --version et --help indépendants du chargement du backend Web.
    from forge_design.web.server import DEFAULT_HOST, DEFAULT_PORT, run_server

    print(f"Forge Design {__version__}", flush=True)
    print(f"http://{DEFAULT_HOST}:{DEFAULT_PORT}", flush=True)
    try:
        run_server(host=DEFAULT_HOST, port=DEFAULT_PORT)
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
