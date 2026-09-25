"""Interface en ligne de commande minimale de Forge Design."""

import argparse
from collections.abc import Sequence

from forge_design import __version__


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="forge-design")
    parser.add_argument(
        "--version", action="version", version=f"Forge Design {__version__}"
    )
    parser.parse_args(argv)
    parser.print_help()
    return 0
