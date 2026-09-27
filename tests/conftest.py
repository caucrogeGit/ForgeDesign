"""Toutes les applications de test utilisent une configuration utilisateur isolée."""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_user_config(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Path:
    directory = tmp_path_factory.mktemp("user-config")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(directory))
    return directory
