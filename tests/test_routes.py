"""Lecture statique sûre et deuxième Tool."""

from pathlib import Path

import pytest

from forge_design.forge.project_version import NotForgeProjectError
from forge_design.forge.routes import (
    RouteInfo,
    RoutesResult,
    RoutesSourceMissingError,
    RoutesSourceUnreadableError,
    read_routes,
)
from forge_design.platform.tool import Tool
from forge_design.tools.route_explorer import RouteExplorerTool


@pytest.fixture
def project(tmp_path: Path) -> Path:
    for name in ("app.py", "bootstrap.py", "config.py"):
        (tmp_path / name).write_text("raise RuntimeError('never execute')")
    (tmp_path / "mvc/routes").mkdir(parents=True)
    return tmp_path


def test_static_routes_and_tool(project: Path) -> None:
    source = project / "mvc/routes/__init__.py"
    source.write_text("""from core.http.router import Router
router = Router()
with router.group("/api/", public=True) as public:
    public.add(["GET", "POST"], "/items", explode(), name="items")
router.add("DELETE", "/items", missing_handler)
register_optins(router)
""")
    before = source.read_bytes(), source.stat().st_mtime_ns
    tool: Tool[RoutesResult] = RouteExplorerTool()
    assert tool.id == "route-explorer"
    result = tool.run(project)
    assert result.routes == (
        RouteInfo("GET", "/api/items", "items", True),
        RouteInfo("POST", "/api/items", "items", True),
        RouteInfo("DELETE", "/items", None, False),
    )
    assert result == read_routes(project)
    assert result.warnings
    assert before == (source.read_bytes(), source.stat().st_mtime_ns)


def test_missing_source(project: Path) -> None:
    with pytest.raises(RoutesSourceMissingError):
        read_routes(project)


def test_unrecognized(tmp_path: Path) -> None:
    with pytest.raises(NotForgeProjectError):
        read_routes(tmp_path)


@pytest.mark.parametrize(
    "content", [b"bad syntax !!!", b"\xff", b"x" * (1024 * 1024 + 1)]
)
def test_bad_source(project: Path, content: bytes) -> None:
    (project / "mvc/routes/__init__.py").write_bytes(content)
    with pytest.raises(RoutesSourceUnreadableError):
        read_routes(project)


def test_symlink_refused(project: Path) -> None:
    (project / "mvc/routes/__init__.py").symlink_to(project / "app.py")
    with pytest.raises(RoutesSourceUnreadableError):
        read_routes(project)


def test_dynamic_routes_not_invented(project: Path) -> None:
    (project / "mvc/routes/__init__.py").write_text("""router = Router()
router.add("GET", dynamic_path(), handler)
if condition:
    router.add("POST", "/conditional", handler)
""")
    result = read_routes(project)
    assert result.routes == () and len(result.warnings) == 3


def test_explicit_branches_only(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    from forge_design.forge import routes as bridge

    directory = project / "mvc/routes"
    (
        directory / "__init__.py"
    ).write_text("""from mvc.routes.contact_routes import register_contact_routes
from mvc.routes.user_routes import register_user_routes
from mvc.routes.unused_routes import register_unused_routes
router = Router()
register_user_routes(router)
router.add("GET", "/", forbidden())
register_contact_routes(router)
register_unknown_routes(router)
""")
    (
        directory / "contact_routes.py"
    ).write_text("""raise RuntimeError("must not execute")
def register_contact_routes(router):
    with router.group("/contact", public=True) as group:
        group.add("GET", "/list", forbidden(), name="contacts")
""")
    (directory / "user_routes.py").write_text("""def register_user_routes(router):
    router.add("POST", "/users", forbidden())
""")
    (directory / "unused_routes.py").write_text("invalid syntax !!!")
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in directory.iterdir()}
    opened: list[Path] = []
    original = os.open

    def guarded(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        assert isinstance(path, Path)
        assert path.parent == directory and path.name != "unused_routes.py"
        opened.append(path)
        return original(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(bridge.os, "open", guarded)
    result = read_routes(project)
    assert [route.path for route in result.routes] == ["/", "/users", "/contact/list"]
    assert result.routes[-1].public and result.routes[-1].name == "contacts"
    assert [p.name for p in opened] == [
        "__init__.py",
        "user_routes.py",
        "contact_routes.py",
    ]
    assert len(result.warnings) == 2
    assert before == {
        p: (p.read_bytes(), p.stat().st_mtime_ns) for p in directory.iterdir()
    }


@pytest.mark.parametrize("kind", ["missing", "syntax", "link", "outside", "dynamic"])
def test_unresolved_branch(project: Path, kind: str) -> None:
    directory = project / "mvc/routes"
    imports = "from mvc.routes.contact_routes import register_contact_routes"
    call = "register_contact_routes(router)"
    if kind == "syntax":
        (directory / "contact_routes.py").write_text("invalid !!!")
    elif kind == "link":
        (directory / "contact_routes.py").symlink_to(project / "app.py")
    elif kind == "outside":
        imports = "from mvc.controllers.contact import register_contact_routes"
    elif kind == "dynamic":
        imports = "import mvc.routes.contact_routes as routes"
        call = "routes.register_contact_routes(router)"
    (directory / "__init__.py").write_text(f"{imports}\nrouter = Router()\n{call}\n")
    result = read_routes(project)
    assert result.routes == () and len(result.warnings) >= 2
