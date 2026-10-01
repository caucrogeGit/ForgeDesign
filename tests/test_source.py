"""Lecture source confinée et localisations extraites des AST existants."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from forge_design.forge.routes import (
    HandlerInfo,
    RouteInfo,
    TemplateDependency,
    read_routes,
)
from forge_design.forge.source import (
    SourceLocation,
    SourceReadError,
    read_project_source,
)


@pytest.mark.parametrize(
    "path",
    [
        "mvc/routes/contact.py",
        "mvc/controllers/contact.py",
        "mvc/views/nested/page.html",
    ],
)
def test_source_read_allowed(tmp_path: Path, path: str) -> None:
    target = tmp_path / path
    target.parent.mkdir(parents=True)
    target.write_bytes(b"\xef\xbb\xbf<script>never execute</script>\n")
    before = target.read_bytes(), target.stat().st_mtime_ns
    assert read_project_source(tmp_path, path) == "<script>never execute</script>\n"
    assert before == (target.read_bytes(), target.stat().st_mtime_ns)
    target.unlink()
    with pytest.raises(FileNotFoundError):
        read_project_source(tmp_path, path)


@pytest.mark.parametrize(
    "path",
    [
        "../secret",
        "/etc/passwd",
        ".env",
        "env/prod",
        ".git/config",
        "mvc/views/../../config.py",
        "mvc/views/../x",
        "mvc/views//x",
        "mvc/views/./x",
        "mvc/views/\\x",
        "mvc/views/C:x",
        "mvc/views/a\x00",
        "mvc/views/.env",
        "mvc/routes/file.txt",
        "mvc/controllers/nested/a.py",
    ],
)
def test_source_rejects_path(
    tmp_path: Path, path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Aucun accès pour un chemin refusé")

    monkeypatch.setattr(os, "open", forbidden)
    with pytest.raises(SourceReadError, match="Chemin source refusé"):
        read_project_source(tmp_path, path)


@pytest.mark.parametrize(
    "case", ["link", "parent-link", "directory", "large", "encoding"]
)
def test_source_rejects_file(tmp_path: Path, case: str) -> None:
    directory = tmp_path / "mvc/views"
    directory.mkdir(parents=True)
    target = directory / "a.html"
    outside = tmp_path / "secret"
    outside.write_text("never read")
    if case == "link":
        target.symlink_to(outside)
    elif case == "parent-link":
        directory.rmdir()
        directory.symlink_to(tmp_path, target_is_directory=True)
        target = tmp_path / "a.html"
        target.write_text("never read")
    elif case == "directory":
        target.mkdir()
    elif case == "large":
        target.write_bytes(b"x" * (1024 * 1024 + 1))
    else:
        target.write_bytes(b"\xff")
    with pytest.raises(SourceReadError):
        read_project_source(tmp_path, "mvc/views/a.html")
    assert outside.read_text() == "never read"


@pytest.mark.parametrize("async_method", [False, True])
def test_source_locations(tmp_path: Path, async_method: bool) -> None:
    for name in ("app.py", "bootstrap.py", "config.py"):
        (tmp_path / name).write_text("raise RuntimeError('never execute')")
    for name in ("routes", "controllers", "views"):
        (tmp_path / "mvc" / name).mkdir(parents=True)
    (tmp_path / "mvc/routes/__init__.py").write_text(
        'router = Router()\nrouter.add("GET", "/", health)\n'
        "from mvc.routes.contact_routes import register_contact_routes\n"
        "register_contact_routes(router)\n"
    )
    (tmp_path / "mvc/routes/contact_routes.py").write_text(
        "from mvc.controllers.contact import Contact\n"
        "def register_contact_routes(router):\n"
        '    router.add("GET", "/contact", Contact.list)\n'
        '    router.add("GET", "/missing", Contact.missing)\n'
    )
    (tmp_path / "mvc/controllers/contact.py").write_text(
        "\nclass Contact:\n    @staticmethod\n    "
        + ("async " if async_method else "")
        + 'def list():\n        return BaseController.render("a.html")\n'
    )
    (tmp_path / "mvc/views/a.html").write_text('\n{% include "b.html" %}')
    (tmp_path / "mvc/views/b.html").write_text('\n\n{% include "missing.html" %}')
    result = read_routes(tmp_path)
    assert result.routes[0].source == SourceLocation("mvc/routes/__init__.py", 2)
    assert result.routes[1].source == SourceLocation("mvc/routes/contact_routes.py", 3)
    handler = result.routes[1].handler
    assert handler and handler.class_source == SourceLocation(
        "mvc/controllers/contact.py", 2
    )
    assert handler.method_source == SourceLocation("mvc/controllers/contact.py", 4)
    assert handler.template.source == SourceLocation("mvc/views/a.html")
    assert handler.template.dependencies[0].source == SourceLocation(
        "mvc/views/a.html", 2
    )
    graph = handler.template.dependency_graph
    assert graph
    assert graph.templates[1].dependencies[0].source == SourceLocation(
        "mvc/views/b.html", 3
    )
    assert graph.templates[2].source == SourceLocation("mvc/views/missing.html")
    assert graph.templates[2].presence == "missing"
    missing = result.routes[2].handler
    assert (
        missing
        and missing.method_source is None
        and missing.class_source == handler.class_source
    )
    with pytest.raises(FrozenInstanceError):
        setattr(handler.method_source, "line", 9)
    assert RouteInfo("GET", "/", None, True).source is None
    assert HandlerInfo("handler").method_source is None
    assert TemplateDependency("include", "a", False, 1).source is None
    (tmp_path / "mvc/views/a.html").unlink()
    absent = read_routes(tmp_path).routes[1].handler
    assert absent and absent.template.presence == "missing"
    assert absent.template.source == SourceLocation("mvc/views/a.html")
    (tmp_path / "mvc/controllers/contact.py").write_text("class Other: pass")
    absent_class = read_routes(tmp_path).routes[1].handler
    assert absent_class and absent_class.verification == "class-missing"
    assert absent_class.controller_file == "mvc/controllers/contact.py"
    assert absent_class.class_source is None and absent_class.method_source is None
