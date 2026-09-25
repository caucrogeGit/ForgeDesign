"""Contrat d'import et de version du paquet installé."""

from importlib.metadata import version

import forge_design


def test_import_and_distribution_version() -> None:
    assert forge_design.__version__ == "0.1.0.dev0"
    assert version("forge-design") == forge_design.__version__
