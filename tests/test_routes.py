"""Lecture statique sûre et deuxième Tool."""

from pathlib import Path

import pytest

from forge_design.forge.project_version import NotForgeProjectError
from forge_design.forge.routes import (
    HandlerInfo,
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
        RouteInfo("DELETE", "/items", None, False, HandlerInfo("missing_handler")),
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
    assert len(result.warnings) == 5
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


@pytest.mark.parametrize(
    "reference",
    ["ContactController.list", "HomeController.index", "health", "Contact.list"],
)
@pytest.mark.parametrize("branched", [False, True])
def test_handler_references(project: Path, reference: str, branched: bool) -> None:
    directory = project / "mvc/routes"
    declaration = f'    public.add("GET", "/", {reference}, name="home")\n'
    content = (
        "from mvc.controllers.contact import ContactController as Contact\n"
        'def health(request):\n    raise RuntimeError("never execute")\n'
    )
    if branched:
        (directory / "__init__.py").write_text(
            "from mvc.routes.contact_routes import register_contact_routes\n"
            "router = Router()\nregister_contact_routes(router)\n"
        )
        content += (
            "def register_contact_routes(router):\n"
            '    with router.group("", public=True) as public:\n' + "    " + declaration
        )
        target = directory / "contact_routes.py"
    else:
        content += (
            'router = Router()\nwith router.group("", public=True) as public:\n'
            + declaration
        )
        target = directory / "__init__.py"
    target.write_text(content)
    result = read_routes(project)
    assert result.routes == (
        RouteInfo(
            "GET",
            "/",
            "home",
            True,
            HandlerInfo(
                reference,
                verification="unreadable"
                if reference == "Contact.list"
                else "not-applicable",
            ),
        ),
    )


@pytest.mark.parametrize(
    "expression",
    [
        "get_handler()",
        "factory().index",
        'handlers["list"]',
        "lambda request: None",
        "partial(ContactController.list, secret)",
        "getattr(ContactController, action)",
    ],
)
def test_dynamic_handler_keeps_route(project: Path, expression: str) -> None:
    (project / "mvc/routes/__init__.py").write_text(
        f'router = Router()\nrouter.add("GET", "/", {expression})\n'
    )
    result = read_routes(project)
    assert result.routes == (RouteInfo("GET", "/", None, False),)
    assert any("handler dynamique non résolu" in warning for warning in result.warnings)
    assert all(expression not in warning for warning in result.warnings)


@pytest.mark.parametrize("branched", [False, True])
@pytest.mark.parametrize("alias", ["ContactController", "Contact"])
def test_controller_per_source(
    project: Path, branched: bool, alias: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    controllers = project / "mvc/controllers"
    controllers.mkdir()
    controller = controllers / "contact_controller.py"
    controller.write_text("not even valid python !!!")
    routes = project / "mvc/routes"
    declaration = f'router.add("GET", "/contact", {alias}.list)\n'
    source = (
        f"from mvc.controllers.contact_controller import ContactController as {alias}\n"
    )
    if branched:
        (routes / "__init__.py").write_text(
            "from mvc.controllers.wrong import ContactController\n"
            "from mvc.routes.contact_routes import register_contact_routes\n"
            "router = Router()\nregister_contact_routes(router)\n"
        )
        (routes / "contact_routes.py").write_text(
            source + "def register_contact_routes(router):\n    " + declaration
        )
    else:
        (routes / "__init__.py").write_text(
            source + "router = Router()\n" + declaration
        )
    original = os.open

    def guarded(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        assert isinstance(path, Path) and (path.parent == routes or path == controller)
        return original(path, flags, mode, dir_fd=dir_fd)

    def no_scan(*args: object, **kwargs: object) -> None:
        pytest.fail("Aucun scan autorisé")

    before = controller.stat().st_mtime_ns, controller.read_bytes()
    monkeypatch.setattr(os, "open", guarded)
    monkeypatch.setattr(Path, "iterdir", no_scan)
    result = read_routes(project)
    assert result.routes[0].handler == HandlerInfo(
        f"{alias}.list", "mvc/controllers/contact_controller.py", "unreadable"
    )
    assert before == (controller.stat().st_mtime_ns, controller.read_bytes())


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "symlink",
        "parent_link",
        "external",
        "subpackage",
        "relative",
        "simple",
        "dynamic",
        "different_source",
    ],
)
def test_controller_unresolved(project: Path, kind: str) -> None:
    controllers = project / "mvc/controllers"
    controllers.mkdir()
    target = controllers / "contact.py"
    imports = "from mvc.controllers.contact import Contact"
    reference = "Contact.list"
    if kind == "symlink":
        target.symlink_to(project / "app.py")
    elif kind == "parent_link":
        controllers.rmdir()
        controllers.symlink_to(project / "mvc/routes", target_is_directory=True)
    elif kind == "external":
        imports = "from services.contact import Contact"
    elif kind == "subpackage":
        imports = "from mvc.controllers.admin.contact import Contact"
    elif kind == "relative":
        imports = "from ..controllers.contact import Contact"
    elif kind == "simple":
        reference = "health"
    elif kind == "dynamic":
        reference = "factory()"
    source = f'{imports}\nrouter = Router()\nrouter.add("GET", "/", {reference})\n'
    if kind == "different_source":
        target.touch()
        source = (
            imports
            + "\nfrom mvc.routes.contact_routes import register_contact_routes\n"
            "router = Router()\nregister_contact_routes(router)\n"
        )
        (project / "mvc/routes/contact_routes.py").write_text(
            "def register_contact_routes(router):\n"
            '    router.add("GET", "/", Contact.list)\n'
        )
    (project / "mvc/routes/__init__.py").write_text(source)
    result = read_routes(project)
    assert len(result.routes) == 1
    handler = result.routes[0].handler
    assert handler is None or handler.controller_file is None
    if kind in ("missing", "symlink", "parent_link"):
        assert any("contrôleur" in warning for warning in result.warnings)


@pytest.mark.parametrize(
    "content,status",
    [
        ("class Original:\n    def list(self): raise RuntimeError('never')", "found"),
        ("class Original:\n    async def list(self): pass", "found"),
        ("class Original:\n    @staticmethod\n    def list(): pass", "found"),
        ("class Original:\n    @classmethod\n    def list(cls): pass", "found"),
        ("class Other: pass", "class-missing"),
        ("class Original: pass", "method-missing"),
        ("invalid !!!", "unreadable"),
        ("x" * (1024 * 1024 + 1), "unreadable"),
        ("class Original: pass\nclass Original: pass", "ambiguous"),
        (
            "class Base:\n    def list(self): pass\nclass Original(Base): pass",
            "method-missing",
        ),
    ],
)
def test_verification(project: Path, content: str, status: str) -> None:
    (project / "mvc/controllers").mkdir()
    (project / "mvc/controllers/example.py").write_text(content)
    (project / "mvc/routes/__init__.py").write_text(
        "from mvc.controllers.example import Original as Alias\n"
        'router = Router()\nrouter.add("GET", "/", Alias.list)\n'
    )
    result = read_routes(project)
    handler = result.routes[0].handler
    assert handler is not None
    assert handler.reference == "Alias.list"
    assert handler.controller_file == "mvc/controllers/example.py"
    assert handler.verification == status
    assert handler.template.status == (
        "none" if status == "found" else "not-applicable"
    )
    assert (len(result.warnings) == 1) == (status == "found")


def test_controller_cache_and_encoding(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from forge_design.forge import routes as bridge

    (project / "mvc/controllers").mkdir()
    controller = project / "mvc/controllers/example.py"
    controller.write_bytes(b"\xff")
    (project / "mvc/routes/__init__.py").write_text(
        "from mvc.controllers.example import Original\nrouter = Router()\n"
        'router.add("GET", "/", Original.list)\n'
        'router.add("POST", "/", Original.create)\n'
    )
    original = bridge._read_source  # pyright: ignore[reportPrivateUsage]
    reads: list[Path] = []

    def read(path: Path) -> str:
        reads.append(path)
        return original(path)

    monkeypatch.setattr(bridge, "_read_source", read)
    result = read_routes(project)
    assert reads.count(controller) == 1
    assert all(
        route.handler and route.handler.verification == "unreadable"
        for route in result.routes
    )
    assert len(result.warnings) == 2
    controller.write_text(
        "class Original:\n    def list(self): pass\n    def create(self): pass"
    )
    result = read_routes(project)
    assert reads.count(controller) == 2
    assert all(
        route.handler and route.handler.verification == "found"
        for route in result.routes
    )


@pytest.mark.parametrize(
    "body,status,path",
    [
        (
            'return BaseController.render("home/index.html", request=request)',
            "found",
            "home/index.html",
        ),
        (
            'return BaseController.render("contacts/form.html", context={})',
            "found",
            "contacts/form.html",
        ),
        (
            'return BaseController.render(template="auth/login.html")',
            "found",
            "auth/login.html",
        ),
        (
            'return BaseController.render(" ../literal.html ")',
            "found",
            " ../literal.html ",
        ),
        ('return Response.html("raw HTML")', "none", None),
        ('return BaseController.redirect("/")', "none", None),
        ('return other.render("unrelated.html")', "none", None),
        (
            'template = "x.html"\nreturn BaseController.render(template)',
            "dynamic",
            None,
        ),
        ('return BaseController.render(f"contacts/{mode}.html")', "dynamic", None),
        ("return BaseController.render(BASE_TEMPLATE)", "dynamic", None),
        ("return BaseController.render(get_template())", "dynamic", None),
        ("return BaseController.render(**options)", "dynamic", None),
        ("return BaseController.render(*args)", "dynamic", None),
        (
            'if condition:\n    return BaseController.render("x.html")\n'
            'return BaseController.render("x.html")',
            "found",
            "x.html",
        ),
        (
            'if condition:\n    return BaseController.render("a.html")\n'
            'return BaseController.render("b.html")',
            "ambiguous",
            None,
        ),
        (
            "if condition:\n    return BaseController.render(template)\n"
            'return BaseController.render("x.html")',
            "dynamic",
            None,
        ),
        (
            'try:\n    return BaseController.render("x.html")\n'
            'except Exception:\n    pass',
            "found",
            "x.html",
        ),
        (
            'for item in items:\n    BaseController.render("x.html")\n'
            'while condition:\n    BaseController.render("x.html")\n'
            'with resource:\n    BaseController.render("x.html")\n'
            'match value:\n    case 1:\n        BaseController.render("x.html")',
            "found",
            "x.html",
        ),
        (
            'def helper():\n    return BaseController.render("hidden.html")',
            "none",
            None,
        ),
        (
            'async def helper():\n    return BaseController.render("hidden.html")',
            "none",
            None,
        ),
        (
            'class Nested:\n    value = BaseController.render("hidden.html")',
            "none",
            None,
        ),
        ('helper = lambda: BaseController.render("hidden.html")', "none", None),
    ],
)
def test_template_resolution(
    project: Path, body: str, status: str, path: str | None
) -> None:
    from textwrap import indent

    (project / "mvc/controllers").mkdir()
    (project / "mvc/controllers/home_controller.py").write_text(
        "from core.mvc.controller.base_controller import BaseController\n"
        "raise RuntimeError('module must never execute')\n"
        "class HomeController:\n    @staticmethod\n    def index(request):\n"
        + indent(body, "        ")
        + '\n    def unrelated(self):\n'
        '        return BaseController.render("other.html")\n'
    )
    (project / "mvc/routes/__init__.py").write_text(
        "from mvc.controllers.home_controller import HomeController\n"
        'router = Router()\nrouter.add("GET", "/", HomeController.index)\n'
    )
    result = read_routes(project)
    handler = result.routes[0].handler
    assert handler is not None and handler.verification == "found"
    assert handler.template.status == status
    assert handler.template.path == path
    assert len(result.warnings) == 1


def test_template_cache_and_confined_reads(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    (project / "mvc/controllers").mkdir()
    controller = project / "mvc/controllers/home.py"
    controller.write_text(
        'raise RuntimeError("never execute")\nclass HomeController:\n'
        '    def index(self): return BaseController.render("../secret.html")\n'
    )
    source = project / "mvc/routes/__init__.py"
    source.write_text(
        "from mvc.controllers.home import HomeController\nrouter = Router()\n"
        'router.add(["GET", "POST"], "/", HomeController.index)\n'
        'router.add("GET", "/other", HomeController.index)\n'
    )
    snapshot = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (source, controller)}
    original = os.open
    reads: list[Path] = []

    def opened(path: Path, flags: int) -> int:
        assert path in snapshot
        reads.append(path)
        return original(path, flags)

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("scan or high-level read forbidden")

    with monkeypatch.context() as guarded:
        guarded.setattr(os, "open", opened)
        guarded.setattr(Path, "iterdir", forbidden)
        guarded.setattr(Path, "open", forbidden)
        result = read_routes(project)
    assert reads == [source, controller]
    assert all(
        r.handler and r.handler.template.path == "../secret.html" for r in result.routes
    )
    assert snapshot == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in snapshot}
