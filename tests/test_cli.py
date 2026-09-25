"""Vérifications de l'entrée installée et de l'appel Python."""

import subprocess
import sysconfig
from pathlib import Path

import pytest

from forge_design import __version__
from forge_design.cli import main


def test_installed_version(tmp_path: Path) -> None:
    command = Path(sysconfig.get_path("scripts")) / "forge-design"
    result = subprocess.run(
        [str(command), "--version"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == f"Forge Design {__version__}\n"
    assert result.stderr == ""


def test_main_without_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    output = capsys.readouterr()
    assert "--version" in output.out
    assert output.err == ""


def test_main_rejects_unknown_argument(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--unknown"])
    assert error.value.code == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "--unknown" in output.err
