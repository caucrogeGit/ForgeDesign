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
    TemplateDependency,
    read_routes,
)
from forge_design.forge.source import SourceLocation
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
        RouteInfo(
            "GET",
            "/api/items",
            "items",
            True,
            source=SourceLocation("mvc/routes/__init__.py", 4),
            handler_dynamic=True,
        ),
        RouteInfo(
            "POST",
            "/api/items",
            "items",
            True,
            source=SourceLocation("mvc/routes/__init__.py", 4),
            handler_dynamic=True,
        ),
        RouteInfo(
            "DELETE",
            "/items",
            None,
            False,
            HandlerInfo("missing_handler"),
            SourceLocation("mvc/routes/__init__.py", 5),
        ),
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
                missing_controller="mvc/controllers/contact.py"
                if reference == "Contact.list"
                else None,
            ),
            SourceLocation(str(target.relative_to(project)), 6),
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
    assert result.routes == (
        RouteInfo(
            "GET",
            "/",
            None,
            False,
            source=SourceLocation("mvc/routes/__init__.py", 2),
            handler_dynamic=True,
        ),
    )
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
    assert handler.template.presence == "not-applicable"
    assert handler.template.syntax == "not-applicable"
    assert handler.template.dependencies == ()
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
            "except Exception:\n    pass",
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
        + "\n    def unrelated(self):\n"
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
    if status != "found":
        assert handler.template.presence == "not-applicable"
        assert handler.template.syntax == "not-applicable"
        assert handler.template.dependencies == ()
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


@pytest.mark.parametrize(
    "reference,kind,expected",
    [
        ("contacts/list.html", "file", "present"),
        ("contacts/list.html", "missing", "missing"),
        ("../secret.html", "missing", "invalid-path"),
        ("/absolute.html", "missing", "invalid-path"),
        ("contacts/../../../secret", "missing", "invalid-path"),
        ("C:\\secret.html", "missing", "invalid-path"),
        ("", "missing", "invalid-path"),
        ("contacts/./list.html", "missing", "invalid-path"),
        ("contacts/list.html", "link", "invalid-path"),
        ("contacts/list.html", "parent-link", "invalid-path"),
        ("contacts/list.html", "directory", "invalid-path"),
        ("contacts/list.html", "permission", "unreadable"),
    ],
)
def test_template_presence(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
    reference: str,
    kind: str,
    expected: str,
) -> None:
    (project / "mvc/controllers").mkdir()
    (project / "mvc/controllers/home.py").write_text(
        "class HomeController:\n    def index(self):\n"
        f"        return BaseController.render({reference!r})\n"
    )
    (project / "mvc/routes/__init__.py").write_text(
        "from mvc.controllers.home import HomeController\nrouter = Router()\n"
        'router.add("GET", "/", HomeController.index)\n'
    )
    views = project / "mvc/views"
    views.mkdir()
    parent = views / "contacts"
    parent.mkdir()
    target = parent / "list.html"
    if kind == "file":
        target.write_bytes(b"invalid Jinja {{\xff")
    elif kind == "directory":
        target.mkdir()
    elif kind == "link":
        target.symlink_to(project / "config.py")
    elif kind == "parent-link":
        parent.rmdir()
        parent.symlink_to(project, target_is_directory=True)
    original = Path.lstat

    def metadata(path: Path):
        if kind == "permission" and path == target:
            raise PermissionError("denied")
        return original(path)

    monkeypatch.setattr(Path, "lstat", metadata)
    result = read_routes(project)
    handler = result.routes[0].handler
    assert handler and handler.template.path == reference
    assert handler.template.status == "found"
    assert handler.template.presence == expected
    if expected != "present":
        assert handler.template.syntax == "not-applicable"
        assert handler.template.dependencies == ()
    assert len(result.warnings) == (2 if kind == "file" else 1)


def test_presence_cache_and_restricted_content(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    (project / "mvc/controllers").mkdir()
    controller = project / "mvc/controllers/home.py"
    controller.write_text(
        "class HomeController:\n    def index(self):\n"
        '        return BaseController.render("home.html")\n'
    )
    source = project / "mvc/routes/__init__.py"
    source.write_text(
        "from mvc.controllers.home import HomeController\nrouter = Router()\n"
        'router.add("GET", "/", HomeController.index)\n'
        'router.add("POST", "/", HomeController.index)\n'
    )
    (project / "mvc/views").mkdir()
    target = project / "mvc/views/home.html"
    target.write_bytes(b"{{ invalid Jinja\xff")
    snapshot = {
        p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (source, controller, target)
    }
    original_stat, original_open = Path.lstat, os.open
    checked: list[Path] = []

    def metadata(path: Path):
        checked.append(path)
        return original_stat(path)

    def opened(path: Path, flags: int) -> int:
        assert path in (source, controller, target)
        return original_open(path, flags)

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("template read or scan")

    with monkeypatch.context() as guarded:
        guarded.setattr(Path, "lstat", metadata)
        guarded.setattr(os, "open", opened)
        for name in ("open", "iterdir", "glob", "rglob"):
            guarded.setattr(Path, name, forbidden)
        result = read_routes(project)
        assert checked.count(target) == 2
        assert all(
            r.handler and r.handler.template.presence == "present"
            for r in result.routes
        )
        read_routes(project)
        assert checked.count(target) == 4
    assert snapshot == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in snapshot}


@pytest.mark.parametrize(
    "content,status",
    [
        (b"{{ utilisateur.nom }}", "valid"),
        (b'{% extends "absent.html" %}{% block body %}ok{% endblock %}', "valid"),
        (b'{% include "absent.html" %}', "valid"),
        (b"{% include template_name %}", "valid"),
        (b'{% import "absent.html" as macros %}', "valid"),
        (b"{{ value|filtre_inconnu }}", "valid"),
        (b"<div><span></div><script>invalid JS</script>", "valid"),
        (b"\xef\xbb\xbf{{ title }}", "valid"),
        (b"{% if title %}\nhello", "invalid"),
        (b"{{ value", "invalid"),
        (b"\xff", "unreadable"),
        (b"x" * (1024 * 1024 + 1), "unreadable"),
    ],
)
def test_jinja_syntax(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
    content: bytes,
    status: str,
) -> None:
    import os

    from jinja2 import Environment, Template, nodes

    from forge_design.forge import routes as bridge

    (project / "mvc/controllers").mkdir()
    controller = project / "mvc/controllers/home.py"
    controller.write_text(
        'raise RuntimeError("never import")\nclass HomeController:\n'
        '    def index(self): return BaseController.render("home.html")\n'
    )
    source = project / "mvc/routes/__init__.py"
    source.write_text(
        "from mvc.controllers.home import HomeController\nrouter = Router()\n"
        'router.add("GET", "/", HomeController.index)\n'
        'router.add("POST", "/", HomeController.index)\n'
    )
    (project / "mvc/views").mkdir()
    target = project / "mvc/views/home.html"
    target.write_bytes(content)
    snapshot = {
        p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (source, controller, target)
    }
    original_open, original_parse = os.open, Environment.parse
    original_extract = bridge._template_dependencies  # pyright: ignore[reportPrivateUsage]
    extractions: list[nodes.Template] = []

    def extracted(tree: nodes.Template) -> tuple[TemplateDependency, ...]:
        extractions.append(tree)
        return original_extract(tree)

    reads: list[Path] = []
    parses: list[str] = []

    def opened(path: Path, flags: int) -> int:
        assert path in snapshot
        reads.append(path)
        return original_open(path, flags)

    def parsed(environment: Environment, text: str):
        assert environment.loader is None and not environment.extensions
        parses.append(text)
        return original_parse(environment, text)

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("scan, dependency loading, compilation or rendering")

    with monkeypatch.context() as guarded:
        guarded.setattr(os, "open", opened)
        guarded.setattr(Environment, "parse", parsed)
        guarded.setattr(bridge, "_template_dependencies", extracted)
        for name in ("get_template", "compile", "from_string"):
            guarded.setattr(Environment, name, forbidden)
        for name in ("render", "render_async"):
            guarded.setattr(Template, name, forbidden)
        for name in ("open", "iterdir", "glob", "rglob"):
            guarded.setattr(Path, name, forbidden)
        for attempt in (1, 2):
            result = read_routes(project)
            assert len(extractions) == (attempt if status == "valid" else 0)
            assert reads.count(target) == attempt
            assert len(parses) == (0 if status == "unreadable" else attempt)
            for route in result.routes:
                assert route.handler is not None
                template = route.handler.template
                assert template.presence == "present" and template.syntax == status
                if status == "invalid":
                    assert template.syntax_line and template.syntax_message
            assert len(result.warnings) == (1 if status == "valid" else 2)
    assert snapshot == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in snapshot}


@pytest.mark.parametrize(
    "source,expected",
    [
        (
            '{% extends "base.html" %}',
            (TemplateDependency("extends", "base.html", False, 1),),
        ),
        (
            '{% include "partial.html" %}',
            (TemplateDependency("include", "partial.html", False, 1),),
        ),
        (
            '{% import "macros.html" as macros %}',
            (TemplateDependency("import", "macros.html", False, 1),),
        ),
        (
            '{% from "forms.html" import field %}',
            (TemplateDependency("from-import", "forms.html", False, 1),),
        ),
        ("{% extends base %}", (TemplateDependency("extends", None, True, 1),)),
        (
            "{% include template_name %}",
            (TemplateDependency("include", None, True, 1),),
        ),
        (
            '{% include "partials/" ~ name %}',
            (TemplateDependency("include", None, True, 1),),
        ),
        (
            "{% include get_template() %}",
            (TemplateDependency("include", None, True, 1),),
        ),
        (
            '{% include ["z.html", "a.html"] %}',
            (
                TemplateDependency("include", "z.html", False, 1),
                TemplateDependency("include", "a.html", False, 1),
            ),
        ),
        (
            '{% include ["a.html", variable] %}',
            (TemplateDependency("include", None, True, 1),),
        ),
        (
            '{% include "../secret.html" %}',
            (TemplateDependency("include", "../secret.html", False, 1),),
        ),
        (
            '{% if condition %}\n{% include "a.html" %}\n'
            '{% else %}\n{% include "b.html" %}\n{% endif %}\n'
            '{% macro helper() %}{% include "a.html" %}{% endmacro %}\n'
            '{% block content %}{% include "c.html" %}{% endblock %}',
            (
                TemplateDependency("include", "a.html", False, 2),
                TemplateDependency("include", "b.html", False, 4),
                TemplateDependency("include", "a.html", False, 6),
                TemplateDependency("include", "c.html", False, 7),
            ),
        ),
    ],
)
def test_jinja_dependencies(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    expected: tuple[TemplateDependency, ...],
) -> None:
    import os

    (project / "mvc/controllers").mkdir()
    controller = project / "mvc/controllers/home.py"
    controller.write_text(
        "class HomeController:\n"
        '    def index(self): return BaseController.render("home.html")\n'
    )
    routes = project / "mvc/routes/__init__.py"
    routes.write_text(
        "from mvc.controllers.home import HomeController\nrouter = Router()\n"
        'router.add("GET", "/", HomeController.index)\n'
    )
    (project / "mvc/views").mkdir()
    template = project / "mvc/views/home.html"
    template.write_text(source)
    original = os.open

    def opened(path: Path, flags: int) -> int:
        assert path in (controller, routes, template)
        return original(path, flags)

    monkeypatch.setattr(os, "open", opened)
    result = read_routes(project)
    handler = result.routes[0].handler
    assert handler and handler.template.syntax == "valid"
    from dataclasses import replace

    assert tuple(
        replace(dependency, presence="not-applicable")
        for dependency in handler.template.dependencies
    ) == tuple(
        replace(d, source=SourceLocation("mvc/views/home.html", d.line))
        for d in expected
    )
    assert len(result.warnings) == 1


@pytest.mark.parametrize(
    "kind,reference,setup,expected",
    [
        ("extends", "base.html", "file", "present"),
        ("extends", "base.html", "missing", "missing"),
        ("include", "parts/table.html", "file", "present"),
        ("import", "parts/macros.html", "file", "present"),
        ("from-import", "parts/macros.html", "file", "present"),
        ("include", "../secret.html", "missing", "invalid-path"),
        ("include", "/etc/passwd", "missing", "invalid-path"),
        ("include", "C:\\secret.html", "missing", "invalid-path"),
        ("include", "parts/table.html", "link", "invalid-path"),
        ("include", "parts/table.html", "parent-link", "invalid-path"),
        ("include", "parts/table.html", "directory", "invalid-path"),
        ("include", "parts/table.html", "permission", "unreadable"),
        ("include", "variable", "dynamic", "not-applicable"),
    ],
)
def test_dependency_presence(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    reference: str,
    setup: str,
    expected: str,
) -> None:
    import os

    (project / "mvc/controllers").mkdir()
    controller = project / "mvc/controllers/home.py"
    controller.write_text(
        "class HomeController:\n"
        '    def index(self): return BaseController.render("home.html")\n'
    )
    routes = project / "mvc/routes/__init__.py"
    routes.write_text(
        "from mvc.controllers.home import HomeController\nrouter = Router()\n"
        'router.add("GET", "/", HomeController.index)\n'
    )
    views = project / "mvc/views"
    (views / "parts").mkdir(parents=True)
    target = views / reference
    if setup == "file":
        target.write_bytes(b"{% include 'must-not-follow.html' %}\xff")
    elif setup == "directory":
        target.mkdir()
    elif setup == "link":
        target.symlink_to(project / "config.py")
    elif setup == "parent-link":
        (views / "parts").rmdir()
        (views / "parts").symlink_to(project, target_is_directory=True)
    expression = reference if setup == "dynamic" else repr(reference)
    declaration = {
        "extends": "{% extends " + expression + " %}",
        "include": "{% include " + expression + " %}",
        "import": "{% import " + expression + " as macros %}",
        "from-import": "{% from " + expression + " import field %}",
    }[kind]
    source = views / "home.html"
    source.write_text(declaration)
    original_open, original_stat = os.open, Path.lstat

    def opened(path: Path, flags: int) -> int:
        assert path in (controller, routes, source, target)
        return original_open(path, flags)

    def metadata(path: Path):
        if setup == "permission" and path == target:
            raise PermissionError("denied")
        if setup == "dynamic":
            assert path != target
        return original_stat(path)

    monkeypatch.setattr(os, "open", opened)
    monkeypatch.setattr(Path, "lstat", metadata)
    result = read_routes(project)
    handler = result.routes[0].handler
    assert handler and handler.template.syntax == "valid"
    (dependency,) = handler.template.dependencies
    assert dependency.kind == kind and dependency.line == 1
    assert dependency.path == (None if setup == "dynamic" else reference)
    assert dependency.dynamic == (setup == "dynamic")
    assert dependency.presence == expected
    assert dependency.syntax == ("unreadable" if setup == "file" else "not-applicable")
    assert len(result.warnings) == (2 if setup == "file" else 1)


def test_dependency_presence_shared_cache(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    from forge_design.forge import routes as bridge

    (project / "mvc/controllers").mkdir()
    controller = project / "mvc/controllers/home.py"
    controller.write_text(
        "class HomeController:\n"
        '    def one(self): return BaseController.render("one.html")\n'
        '    def two(self): return BaseController.render("two.html")\n'
    )
    routes = project / "mvc/routes/__init__.py"
    routes.write_text(
        "from mvc.controllers.home import HomeController\nrouter = Router()\n"
        'router.add("GET", "/one", HomeController.one)\n'
        'router.add("GET", "/two", HomeController.two)\n'
    )
    views = project / "mvc/views"
    views.mkdir()
    first, second, target = views / "one.html", views / "two.html", views / "base.html"
    first.write_text('{% include ["base.html", "absent.html", "two.html"] %}')
    second.write_text('{% extends "base.html" %}\n{% include "base.html" %}')
    target.write_bytes(b"invalid Jinja {{\xff")
    snapshot = {
        p: (p.read_bytes(), p.stat().st_mtime_ns)
        for p in (controller, routes, first, second, target)
    }
    original_presence = bridge._template_presence  # pyright: ignore[reportPrivateUsage]
    original_open = os.open
    checked: list[str] = []
    reads: list[Path] = []

    def presence(root: Path, reference: str):
        checked.append(reference)
        return original_presence(root, reference)

    def opened(path: Path, flags: int) -> int:
        assert path in (controller, routes, first, second, target)
        reads.append(path)
        return original_open(path, flags)

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("dependency content or scan")

    with monkeypatch.context() as guard:
        guard.setattr(bridge, "_template_presence", presence)
        guard.setattr(os, "open", opened)
        for name in ("open", "iterdir", "glob", "rglob"):
            guard.setattr(Path, name, forbidden)
        for attempt in (1, 2):
            result = read_routes(project)
            assert all(
                checked.count(name) == attempt
                for name in ("one.html", "two.html", "base.html", "absent.html")
            )
            assert all(reads.count(path) == attempt for path in (first, second, target))
            assert len(result.warnings) == 2
            first_handler, second_handler = (r.handler for r in result.routes)
            assert first_handler and second_handler
            assert [d.presence for d in first_handler.template.dependencies] == [
                "present",
                "missing",
                "present",
            ]
            assert [d.line for d in second_handler.template.dependencies] == [1, 2]
            assert len(second_handler.template.dependencies) == 2
    assert snapshot == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in snapshot}


@pytest.mark.parametrize(
    "content,status",
    [
        (b"{% if user %}{{ user.name }}{% endif %}", "valid"),
        (b"{% if user %}\n{{ user.name }}", "invalid"),
        (b"\xff", "unreadable"),
        (b"x" * (1024 * 1024 + 1), "unreadable"),
        (b'{% extends "never-parent.html" %}{% include "never-child.html" %}', "valid"),
        (b"{{ unknown|unknown_filter }}", "valid"),
        (b"\xef\xbb\xbf{{ unknown }}", "valid"),
    ],
)
def test_direct_dependency_syntax(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
    content: bytes,
    status: str,
) -> None:
    import os

    from jinja2 import Environment, Template, nodes

    from forge_design.forge import routes as bridge

    (project / "mvc/controllers").mkdir()
    controller = project / "mvc/controllers/home.py"
    controller.write_text(
        "class HomeController:\n"
        '    def one(self): return BaseController.render("one.html")\n'
        '    def two(self): return BaseController.render("two.html")\n'
    )
    routes = project / "mvc/routes/__init__.py"
    routes.write_text(
        "from mvc.controllers.home import HomeController\nrouter = Router()\n"
        'router.add("GET", "/one", HomeController.one)\n'
        'router.add("GET", "/two", HomeController.two)\n'
    )
    views = project / "mvc/views"
    views.mkdir()
    first, second, target = views / "one.html", views / "two.html", views / "part.html"
    first.write_text('{% include "part.html" %}{% include "part.html" %}')
    second.write_text('{% include "part.html" %}')
    target.write_bytes(content)
    snapshot = {
        p: (p.read_bytes(), p.stat().st_mtime_ns)
        for p in (controller, routes, first, second, target)
    }
    original_open, original_stat, original_parse = (
        os.open,
        Path.lstat,
        Environment.parse,
    )
    original_extract = bridge._template_dependencies  # pyright: ignore[reportPrivateUsage]
    reads: list[Path] = []
    parses: list[str] = []
    extractions: list[nodes.Template] = []

    def opened(path: Path, flags: int) -> int:
        assert path in snapshot
        reads.append(path)
        return original_open(path, flags)

    def metadata(path: Path):
        return original_stat(path)

    def parsed(environment: Environment, source: str):
        assert environment.loader is None
        parses.append(source)
        return original_parse(environment, source)

    def extracted(tree: nodes.Template):
        extractions.append(tree)
        return original_extract(tree)

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("scan, loader, compilation or rendering")

    with monkeypatch.context() as guard:
        guard.setattr(os, "open", opened)
        guard.setattr(Path, "lstat", metadata)
        guard.setattr(Environment, "parse", parsed)
        guard.setattr(bridge, "_template_dependencies", extracted)
        for name in ("get_template", "compile", "from_string"):
            guard.setattr(Environment, name, forbidden)
        for name in ("render", "render_async"):
            guard.setattr(Template, name, forbidden)
        for name in ("open", "iterdir", "glob", "rglob"):
            guard.setattr(Path, name, forbidden)
        for attempt in (1, 2):
            result = read_routes(project)
            assert reads.count(target) == attempt
            assert len(parses) == attempt * (2 if status == "unreadable" else 3)
            assert len(extractions) == attempt * (3 if status == "valid" else 2)
            assert len(result.warnings) == (1 if status == "valid" else 2)
            for route in result.routes:
                assert route.handler and route.handler.template.syntax == "valid"
                for dependency in route.handler.template.dependencies:
                    assert (
                        dependency.path == "part.html"
                        and dependency.presence == "present"
                    )
                    assert dependency.syntax == status
                    if status == "invalid":
                        assert dependency.syntax_line and dependency.syntax_message
                        assert len(dependency.syntax_message) <= 240
    assert snapshot == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in snapshot}
