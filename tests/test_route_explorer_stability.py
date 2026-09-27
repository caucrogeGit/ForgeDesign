"""Chaînes complètes contrôlées, invariants et absence d'effets sur le projet."""

import builtins
import importlib
import os
import subprocess
from pathlib import Path

import pytest

from forge_design.forge.routes import read_routes
from forge_design.forge.source import SourceReadError, read_project_source
from forge_design.tools.route_diagnostics import build_route_diagnostics
from forge_design.tools.route_filters import RouteFilter, filter_route_explorer
from forge_design.tools.route_graph import build_route_graph
from forge_design.web.route_graph_layout import layout_route_graph


def make_project(root: Path, variant: str) -> Path:
    """Formes du squelette 73a956e et extensions applicatives contrôlées."""
    files = {
        "app.py": 'raise AssertionError("app executed")',
        "config.py": 'raise AssertionError("config executed")',
        "bootstrap.py": 'raise AssertionError("bootstrap executed")',
        "requirements.txt": "forge-mvc==1.0.0rc9",
        "mvc/routes/__init__.py": """from core.http.router import Router
from mvc.controllers.home_controller import HomeController
from optins.registry import register_optins
router = Router()
with router.group("", public=True) as public:
    public.add("GET", "/", HomeController.index, name="home-index")
    public.add("GET", "/charte", HomeController.charte, name="home-charte")
register_optins(router)
raise AssertionError("routes executed")
""",
        "mvc/controllers/home_controller.py": """
raise AssertionError("controller executed")
class HomeController(BaseController):
    @staticmethod
    def index(request):
        return BaseController.render("home/index.html", request=request)
    @staticmethod
    def charte(request):
        return BaseController.render("pages/charte.html", request=request)
""",
        "mvc/views/home/index.html": "{{ must_not_execute() }}",
        "mvc/views/pages/charte.html": "<h1>Charte</h1>",
    }
    if variant != "minimal":
        files[
            "mvc/routes/__init__.py"
        ] += """from mvc.routes.contact_routes import register_contact_routes
from mvc.routes.user_routes import register_user_routes
register_contact_routes(router)
register_user_routes(router)
"""
        files[
            "mvc/routes/contact_routes.py"
        ] = """raise AssertionError("module executed")
from mvc.controllers.contact_controller import ContactController
from mvc.controllers.missing_controller import MissingController
from mvc.controllers.pivot.contact import PivotController
def register_contact_routes(router):
    with router.group("/contact", public=True) as public:
        public.add("GET", "/list", ContactController.list)
    router.add("POST", "/contact/create", ContactController.create)
"""
        files[
            "mvc/routes/user_routes.py"
        ] = """from mvc.controllers.user_controller import UserController
def register_user_routes(router):
    router.add("GET", "/users", UserController.index)
    router.add("GET", "/factory", factory())
"""
        files[
            "mvc/controllers/contact_controller.py"
        ] = """raise AssertionError("controller executed")
class ContactController:
    def list(self): return BaseController.render("contacts/list.html")
    def create(self): return BaseController.render("contacts/create.html")
    def invalid(self): return BaseController.render("invalid.html")
    def absent(self): return BaseController.render("missing.html")
"""
        files["mvc/controllers/user_controller.py"] = """class UserController:
    def index(self): return BaseController.render(compute_template())
"""
        files.update(
            {
                "mvc/views/contacts/list.html": '{% extends "base.html" %}'
                '{% include "contacts/_table.html" %}',
                "mvc/views/contacts/create.html": "{{ must_not_execute() }}",
                "mvc/views/contacts/_table.html": '{% include "macros/forms.html" %}',
                "mvc/views/base.html": '{% extends "layouts/site.html" %}',
                "mvc/views/layouts/site.html": '{% include "base.html" %}',
                "mvc/views/macros/forms.html": "{{ unknown | unknown_filter }}",
            }
        )
    if variant == "broken":
        files[
            "mvc/routes/contact_routes.py"
        ] += """    router.add("GET", "/absent-controller", MissingController.index)
    router.add("GET", "/absent-method", ContactController.missing)
    router.add("GET", "/absent-template", ContactController.absent)
    router.add("GET", "/invalid-template", ContactController.invalid)
"""
        files["mvc/views/invalid.html"] = "{% if broken %}"
        files["mvc/views/contacts/list.html"] += (
            '{% include "absent-dependency.html" %}'
        )
    if variant == "unsupported":
        files["mvc/routes/__init__.py"] += """import mvc.routes.unfollowed as routes
routes.register_unfollowed_routes(router)
from mvc.routes.unfollowed import register_unfollowed_routes as alias
alias(router)
from mvc.routes.nested.unfollowed import register_nested_routes
register_nested_routes(router)
module = __import__("mvc.routes.unfollowed")
if enabled:
    router.add("GET", "/not-invented", handler)
"""
        files["mvc/routes/contact_routes.py"] += (
            '    router.add("GET", "/pivot", PivotController.index)\n'
        )
        files["mvc/routes/unfollowed.py"] = "not Python: must not read"
        files["mvc/controllers/pivot/contact.py"] = "not Python: must not read"
    for name, content in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


def snapshot(root: Path) -> dict[str, tuple[int, bytes, int]]:
    return {
        str(path.relative_to(root)): (
            path.stat().st_size,
            path.read_bytes(),
            path.stat().st_mtime_ns,
        )
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize("variant", ["minimal", "rich", "broken", "unsupported"])
def test_complete_static_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variant: str
) -> None:
    root = make_project(tmp_path, variant)
    for name in (
        ".env",
        ".env.prod",
        "env/prod",
        ".git/config",
        "private.pem",
        "private.key",
        ".ssh/id_ed25519",
    ):
        secret = root / name
        secret.parent.mkdir(parents=True, exist_ok=True)
        secret.write_text("SECRET NEVER READ")
    before = snapshot(root)
    allowed = {
        root / name
        for name in before
        if name.startswith(("mvc/routes/", "mvc/controllers/", "mvc/views/"))
        and "unfollowed" not in name
        and "/pivot/" not in name
    }
    # Jinja charge paresseusement son module de diagnostic au premier échec.
    importlib.import_module("jinja2.debug")
    real_open = os.open

    def checked_open(path: str | bytes | Path, flags: int, mode: int = 0o777) -> int:
        assert not isinstance(path, bytes)
        assert Path(path) in allowed
        return real_open(path, flags, mode)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Exécution, import dynamique ou scan interdit")

    with monkeypatch.context() as guard:
        guard.setattr(os, "open", checked_open)
        for obj, name in (
            (builtins, "exec"),
            (builtins, "eval"),
            (importlib, "import_module"),
            (subprocess, "run"),
            (Path, "open"),
            (Path, "iterdir"),
            (Path, "rglob"),
        ):
            guard.setattr(obj, name, forbidden)
        result = read_routes(root)
        diagnostics = build_route_diagnostics(result)
        graph = build_route_graph(result)
        layout = layout_route_graph(graph)
        assert graph == build_route_graph(result)
        assert layout == layout_route_graph(graph)
    assert snapshot(root) == before
    assert [r.path for r in result.routes[:2]] == ["/", "/charte"]
    assert all(r.public for r in result.routes[:2])
    assert any("opt-ins" in w for w in result.warnings)
    ids = {n.id for n in graph.nodes}
    assert all(e.source in ids and e.target in ids for e in graph.edges)
    for route in result.routes:
        assert route.source and not Path(route.source.path).is_absolute()
        if route.handler is None:
            assert route.handler_dynamic
            continue
        template = route.handler.template
        if template.status != "found":
            assert template.path is None
        if template.presence == "missing":
            assert template.syntax == "not-applicable"
        closure = template.dependency_graph
        if closure:
            known = {
                (n.path, d.path, d.kind)
                for n in closure.templates
                for d in n.dependencies
                if not d.dynamic
            }
            assert all(
                (e.source, e.target, e.kind) in known
                for c in closure.cycles
                for e in c.edges
            )
    codes = {d.code for d in diagnostics.items}
    if variant == "minimal":
        assert codes == {"route.partial"}
        assert [r.handler.template.path for r in result.routes if r.handler] == [
            "home/index.html",
            "pages/charte.html",
        ]
    else:
        assert {"handler.dynamic", "template.dynamic", "template.cycle"} <= codes
        assert any(n.label == "macros/forms.html" for n in graph.nodes)
        selected = filter_route_explorer(
            result,
            diagnostics,
            RouteFilter(query="CONTACT", method="get", visibility="public"),
        )
        assert [r.path for r in selected.routes] == ["/contact/list"]
        assert result.routes == read_routes(root).routes
    if variant == "broken":
        assert {
            "controller.missing",
            "controller.method_missing",
            "template.missing",
            "template.syntax_invalid",
            "template.dependency_missing",
        } <= codes
    if variant == "unsupported":
        assert "/not-invented" not in {r.path for r in result.routes}
        pivot = next(r for r in result.routes if r.path == "/pivot")
        assert pivot.handler and pivot.handler.controller_file is None
        assert len(result.warnings) > 4


@pytest.mark.parametrize(
    "reference",
    [
        ".env",
        ".env.prod",
        ".git/config",
        ".ssh/id_ed25519",
        "env/prod",
        "private.pem",
        "private.KEY",
        "keys/id_rsa",
        "keys/id_ed25519",
    ],
)
def test_sensitive_view_never_inspected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reference: str
) -> None:
    root = make_project(tmp_path, "minimal")
    target = root / "mvc/views" / reference
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("SECRET NEVER READ")
    (root / "mvc/views/home/index.html").write_text('{% include "' + reference + '" %}')
    controller = root / "mvc/controllers/home_controller.py"
    controller.write_text(
        controller.read_text().replace("pages/charte.html", reference)
    )
    real_lstat = Path.lstat

    def checked_lstat(path: Path) -> os.stat_result:
        assert (
            path != target
            and path not in target.parents[0 : len(target.parts) - len(root.parts) - 3]
        )
        return real_lstat(path)

    with monkeypatch.context() as guard:
        guard.setattr(Path, "lstat", checked_lstat)
        result = read_routes(root)
        with pytest.raises(SourceReadError, match="Chemin source refusé"):
            read_project_source(root, "mvc/views/" + reference)
    home, charte = (r.handler for r in result.routes)
    assert home and charte
    assert home.template.dependencies[0].presence == "invalid-path"
    assert home.template.dependencies[0].syntax == "not-applicable"
    assert charte.template.presence == "invalid-path"
    assert charte.template.source is None
