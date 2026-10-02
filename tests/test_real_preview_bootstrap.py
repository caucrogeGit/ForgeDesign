"""Bootstrap enfant de la preview réelle (FD-REALPREVIEW-002).

Le hook d'audit n'est jamais installé dans le processus pytest (il ne se
retire pas) : sa décision est testée directement, son installation dans des
processus dédiés.
"""

import socket
import subprocess
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import pytest
from real_preview_support import make_venv

import forge_design.real_preview as real_preview
from forge_design.real_preview import child_bootstrap

BOOTSTRAP = Path(real_preview.__file__).with_name("child_bootstrap.py")
APPLICATION = (
    "class _Application:\n"
    "    def dispatch(self, request):\n"
    "        raise AssertionError('non appelé')\n"
    "application = _Application()\n"
)


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def run_bootstrap(
    python: Path | str, cwd: Path, *arguments: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(python), "-I", "-u", str(BOOTSTRAP), *arguments],
        cwd=cwd,
        env={"PATH": "/usr/bin:/bin", "APP_ENV": "dev"},
        capture_output=True,
        text=True,
        timeout=30,
    )


# ── Arguments ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--port"],
        ["--port", "abc"],
        ["--port", "80"],
        ["--port", "1023"],
        ["--port", "65536"],
        ["--port", "-1"],
        ["--port", "+8080"],
        ["--port", "08080"],
        ["--port", " 8080"],
        ["--port", "8080", "--host", "0.0.0.0"],
        ["--port=8080"],
        ["--host", "8080"],
    ],
)
def test_parse_port_refuses(arguments: list[str]) -> None:
    assert child_bootstrap.parse_port(arguments) is None


@pytest.mark.parametrize("port", [1024, 8080, 65535])
def test_parse_port_accepts(port: int) -> None:
    assert child_bootstrap.parse_port(["--port", str(port)]) == port


@pytest.mark.parametrize(
    "arguments", [[], ["--port", "80"], ["--port", "8080", "extra"]]
)
def test_usage_exit_code(tmp_path: Path, arguments: list[str]) -> None:
    result = run_bootstrap(sys.executable, tmp_path, *arguments)
    assert result.returncode == child_bootstrap.EXIT_USAGE == 2
    assert "usage" in result.stderr


# ── Décision de bind et hook d'audit ─────────────────────────────────────────


@pytest.mark.parametrize(
    ("family", "address"),
    [
        (socket.AF_INET, ("127.0.0.1", 8080)),
        (socket.AF_INET, ("127.1.2.3", 0)),
        (socket.AF_INET, ("127.255.255.254", 1)),
        (socket.AF_INET6, ("::1", 8080)),
        (socket.AF_INET6, ("::1", 8080, 0, 0)),
        (socket.AF_UNIX, "/tmp/forge.sock"),
        (socket.AF_UNIX, b"\0abstract"),
    ],
)
def test_bind_allowed(family: int, address: object) -> None:
    assert child_bootstrap.bind_allowed(family, address)


@pytest.mark.parametrize(
    ("family", "address"),
    [
        (socket.AF_INET, ("0.0.0.0", 8080)),
        (socket.AF_INET, ("", 8080)),
        (socket.AF_INET, ("localhost", 8080)),
        (socket.AF_INET, (socket.gethostname(), 8080)),
        (socket.AF_INET, ("192.168.1.10", 8080)),
        (socket.AF_INET, ("10.0.0.1", 8080)),
        (socket.AF_INET, ("100.64.0.1", 8080)),
        (socket.AF_INET, ("::1", 8080)),
        (socket.AF_INET, (b"127.0.0.1", 8080)),
        (socket.AF_INET, ()),
        (socket.AF_INET, "127.0.0.1"),
        (socket.AF_INET6, ("::", 8080)),
        (socket.AF_INET6, ("", 8080)),
        (socket.AF_INET6, ("::ffff:127.0.0.1", 8080)),
        (socket.AF_INET6, ("fe80::1", 8080)),
        (socket.AF_INET6, ("127.0.0.1", 8080)),
        (socket.AF_INET6, ("localhost", 8080)),
        (getattr(socket, "AF_PACKET", 17), ("eth0", 0)),
        (None, ("127.0.0.1", 8080)),
    ],
)
def test_bind_refused(family: object, address: object) -> None:
    assert not child_bootstrap.bind_allowed(family, address)


class _Socket:
    def __init__(self, family: int) -> None:
        self.family = family


def test_audit_hook_decision_without_installation() -> None:
    hook = child_bootstrap.audit_hook
    assert hook("socket.bind", (_Socket(socket.AF_INET), ("127.0.0.1", 1))) is None
    with pytest.raises(PermissionError, match="loopback uniquement"):
        hook("socket.bind", (_Socket(socket.AF_INET), ("0.0.0.0", 1)))
    with pytest.raises(PermissionError):
        hook("socket.bind", (_Socket(socket.AF_INET6), ("::", 1)))
    # Les autres événements ne sont pas examinés.
    assert hook("socket.connect", (_Socket(socket.AF_INET), ("8.8.8.8", 53))) is None
    assert hook("open", ("/etc/hosts", "r", 0)) is None


_HOOK_PROGRAM = """
import importlib.util, socket, sys
spec = importlib.util.spec_from_file_location("child_bootstrap", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sys.addaudithook(module.audit_hook)
for family, host in ((socket.AF_INET, "0.0.0.0"), (socket.AF_INET, "192.0.2.1"),
                     (socket.AF_INET6, "::"), (socket.AF_INET, "localhost")):
    s = socket.socket(family, socket.SOCK_STREAM)
    try:
        s.bind((host, 0))
        print("BOUND", host, s.getsockname()[:2])
    except PermissionError:
        # Port 0 : un bind réel aurait attribué un port non nul.
        print("REFUSED", host, s.getsockname()[:2])
    s.close()
s = socket.socket()
s.bind(("127.0.0.1", 0))
print("LOOPBACK", s.getsockname()[1] > 0)
s.close()
"""


def test_installed_hook_refuses_before_system_call(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-c", _HOOK_PROGRAM, str(BOOTSTRAP)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "REFUSED 0.0.0.0 ('0.0.0.0', 0)",
        "REFUSED 192.0.2.1 ('0.0.0.0', 0)",
        "REFUSED :: ('::', 0)",
        "REFUSED localhost ('0.0.0.0', 0)",
        "LOOPBACK True",
    ]


# ── Garde Host ───────────────────────────────────────────────────────────────


def _call(
    application: Callable[[dict[str, Any], Callable[..., Any]], Iterable[bytes]],
    environ: dict[str, Any],
) -> tuple[str, list[tuple[str, str]], bytes]:
    captured: list[Any] = []

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured.extend((status, headers))

    body = b"".join(application(environ, start_response))
    return captured[0], captured[1], body


def _target() -> tuple[
    list[dict[str, Any]],
    Callable[[dict[str, Any], Callable[..., Any]], Iterable[bytes]],
]:
    calls: list[dict[str, Any]] = []

    def target(
        environ: dict[str, Any], start_response: Callable[..., Any]
    ) -> Iterable[bytes]:
        calls.append(environ)
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [b"cible"]

    return calls, target


def test_host_guard_passes_exact_host() -> None:
    calls, target = _target()
    guarded = child_bootstrap.host_guard(target, 40123)
    status, _, body = _call(guarded, {"HTTP_HOST": "127.0.0.1:40123"})
    assert (status, body, len(calls)) == ("200 OK", b"cible", 1)


@pytest.mark.parametrize(
    "host",
    [
        None,
        "",
        "localhost:40123",
        "127.0.0.1",
        "127.0.0.1:40124",
        "127.0.0.1:40123.",
        "evil.example:40123",
        "0.0.0.0:40123",
        "[::1]:40123",
        "127.0.0.1:40123 ",
    ],
)
def test_host_guard_refuses(host: str | None) -> None:
    calls, target = _target()
    guarded = child_bootstrap.host_guard(target, 40123)
    environ = {} if host is None else {"HTTP_HOST": host}
    status, headers, body = _call(guarded, environ)
    assert status == "400 Bad Request"
    assert ("Content-Type", "text/plain; charset=utf-8") in headers
    assert ("Cache-Control", "no-store") in headers
    assert body == b"Bad Request\n"
    assert calls == []


def test_server_class_never_reuses_ports() -> None:
    server = child_bootstrap.PreviewServer
    assert server.daemon_threads is True
    assert server.allow_reuse_address is False
    assert server.allow_reuse_port is False


# ── Compatibilité Forge et projet ────────────────────────────────────────────


def _fake_distribution(directory: Path, version: str) -> Path:
    info = directory / f"forge_mvc-{version}.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: forge-mvc\nVersion: {version}\n"
    )
    return directory


def test_wrong_forge_version_exits_3_before_import(tmp_path: Path) -> None:
    fake = _fake_distribution(tmp_path / "fake", "9.9.9")
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text("raise SystemExit('importé à tort')\n")
    python = make_venv(project, extra_paths=[fake])
    result = run_bootstrap(python, project, "--port", str(free_port()))
    assert result.returncode == child_bootstrap.EXIT_INCOMPATIBLE == 3
    assert "'9.9.9' non supporté (1.0.0rc9 requis)" in result.stderr
    assert "importé à tort" not in result.stderr
    assert "écoute" not in result.stdout


def test_missing_wsgi_factory_exits_3(tmp_path: Path) -> None:
    fake = _fake_distribution(tmp_path / "fake", "1.0.0rc9")
    (fake / "core" / "app").mkdir(parents=True)
    for name in ("core/__init__.py", "core/app/__init__.py", "core/app/wsgi.py"):
        (fake / name).write_text("")
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text(APPLICATION)
    python = make_venv(project, extra_paths=[fake])
    result = run_bootstrap(python, project, "--port", str(free_port()))
    assert result.returncode == 3
    assert "create_wsgi_app introuvable" in result.stderr


def test_application_without_dispatch_exits_3(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("application = object()\n")
    python = make_venv(tmp_path)
    result = run_bootstrap(python, tmp_path, "--port", str(free_port()))
    assert result.returncode == 3
    assert "dispatch introuvable" in result.stderr


def test_project_cannot_shadow_forge_core(tmp_path: Path) -> None:
    """core est importé avant l'ajout de la racine : un core/ du projet est ignoré."""
    (tmp_path / "core" / "app").mkdir(parents=True)
    for name in ("core/__init__.py", "core/app/__init__.py"):
        (tmp_path / name).write_text("")
    (tmp_path / "core/app/wsgi.py").write_text("raise SystemExit('core du projet')\n")
    (tmp_path / "app.py").write_text("raise RuntimeError('import du projet atteint')\n")
    python = make_venv(tmp_path)
    result = run_bootstrap(python, tmp_path, "--port", str(free_port()))
    assert result.returncode == child_bootstrap.EXIT_IMPORT == 5
    assert "import du projet atteint" in result.stderr
    assert "core du projet" not in result.stderr


def test_busy_port_exits_4(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(APPLICATION)
    python = make_venv(tmp_path)
    with socket.socket() as holder:
        holder.bind(("127.0.0.1", 0))
        holder.listen()
        port = holder.getsockname()[1]
        result = run_bootstrap(python, tmp_path, "--port", str(port))
    assert result.returncode == child_bootstrap.EXIT_PORT_IN_USE == 4
    assert f"port {port} occupé" in result.stderr
