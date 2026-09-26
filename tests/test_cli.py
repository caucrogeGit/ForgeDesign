"""Vérifications de l'entrée installée et de l'appel Python."""

import errno
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


def test_main_without_arguments(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from forge_design.web import server

    calls: list[tuple[str, int]] = []

    def run(host: str, port: int) -> None:
        calls.append((host, port))

    monkeypatch.setattr(server, "run_server", run)
    assert main([]) == 0
    output = capsys.readouterr()
    assert output.out == f"Forge Design {__version__}\nhttp://127.0.0.1:8765\n"
    assert calls == [("127.0.0.1", 8765)]
    assert output.err == ""


def test_main_rejects_unknown_argument(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--unknown"])
    assert error.value.code == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "--unknown" in output.err


@pytest.mark.parametrize(
    "error",
    [KeyboardInterrupt(), OSError(errno.EADDRINUSE, "busy"), PermissionError("denied")],
)
def test_server_exit(
    error: BaseException,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from forge_design.web import server

    def fail(host: str, port: int) -> None:
        raise error

    monkeypatch.setattr(server, "run_server", fail)
    assert main([]) == (0 if isinstance(error, KeyboardInterrupt) else 1)
    output = capsys.readouterr()
    assert "Traceback" not in output.err
    if isinstance(error, OSError):
        assert ("occupé" if error.errno == errno.EADDRINUSE else "denied") in output.err


def test_unexpected_error_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    from forge_design.web import server

    def fail(host: str, port: int) -> None:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(server, "run_server", fail)
    with pytest.raises(RuntimeError, match="unexpected"):
        main([])


def test_startup_has_no_business_or_browser_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import webbrowser

    from forge_design.tools import project_inspector
    from forge_design.web import server

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("Effet interdit au démarrage")

    monkeypatch.setattr(project_inspector.ProjectInspectorTool, "run", forbidden)
    monkeypatch.setattr(project_inspector, "inspect_project", forbidden)
    monkeypatch.setattr(webbrowser, "open", forbidden)
    monkeypatch.setattr(webbrowser, "open_new", forbidden)
    monkeypatch.setattr(webbrowser, "open_new_tab", forbidden)

    class FakeServer:
        closed = False

        def __enter__(self) -> "FakeServer":
            return self

        def __exit__(self, *args: object) -> None:
            self.closed = True

        def serve_forever(self) -> None:
            raise KeyboardInterrupt

    instance = FakeServer()

    def create(host: str, port: int) -> FakeServer:
        assert (host, port) == ("127.0.0.1", 8765)
        server.create_application()
        return instance

    monkeypatch.setattr(server, "create_server", create)
    assert main([]) == 0
    assert instance.closed
