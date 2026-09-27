"""Parcours Jinja borné, sans rendu ni accès aux chemins refusés."""

from pathlib import Path

import pytest

from forge_design.forge import routes as bridge
from forge_design.forge.routes import read_routes


@pytest.fixture
def project(tmp_path: Path) -> Path:
    for name in ("app.py", "bootstrap.py", "config.py"):
        (tmp_path / name).write_text("raise RuntimeError('no execution')")
    (tmp_path / "mvc/routes").mkdir(parents=True)
    (tmp_path / "mvc/controllers").mkdir()
    (tmp_path / "mvc/views").mkdir()
    (tmp_path / "mvc/routes/__init__.py").write_text(
        "from mvc.controllers.home import Home\nrouter = Router()\n"
        'router.add("GET", "/", Home.index)\n'
    )
    (tmp_path / "mvc/controllers/home.py").write_text(
        'class Home:\n    def index(self): return BaseController.render("a.html")\n'
    )
    return tmp_path


def closure(project: Path):
    result = read_routes(project)
    handler = result.routes[0].handler
    assert handler and handler.template.dependency_graph
    return handler.template.dependency_graph, result


@pytest.mark.parametrize("length", [3, 4, 11])
def test_chain_depth(
    project: Path, length: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    views = project / "mvc/views"
    names = ["a.html"] + [f"{i}.html" for i in range(1, length)]
    for i, name in enumerate(names):
        (views / name).write_text(
            '{% extends "' + names[i + 1] + '" %}' if i + 1 < length else "ok"
        )
    original_stat = Path.lstat

    def bounded_stat(path: Path):
        assert path not in {views / name for name in names[9:]}
        return original_stat(path)

    with monkeypatch.context() as guard:
        guard.setattr(Path, "lstat", bounded_stat)
        graph, result = closure(project)
    assert [n.path for n in graph.templates] == names[:9]
    assert graph.truncated == (length > 9)
    assert sum("Profondeur maximale" in w for w in result.warnings) == (length > 9)
    if length > 9:
        assert graph.templates[-1].dependencies[0].path == names[9]
        assert graph.templates[-1].dependencies[0].presence == "not-applicable"


def test_diamond_cycle_and_cache(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from jinja2 import Environment, Template, nodes

    views = project / "mvc/views"
    contents = {
        "a.html": '{% include "b.html" %}{% include "c.html" %}',
        "b.html": '{% extends "d.html" %}',
        "c.html": '{% from "d.html" import item %}',
        "d.html": '{% import "a.html" as a %}',
    }
    for name, content in contents.items():
        (views / name).write_text(content)
    snapshot = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in views.iterdir()}
    read = bridge._read_source  # pyright: ignore[reportPrivateUsage]
    extract = bridge._template_dependencies  # pyright: ignore[reportPrivateUsage]
    parse = Environment.parse
    reads: list[Path] = []
    parses: list[str] = []
    extractions: list[nodes.Template] = []

    def reading(path: Path) -> str:
        if path.parent == views:
            assert path in snapshot
            reads.append(path)
        return read(path)

    def parsing(env: Environment, source: str):
        assert env.loader is None
        parses.append(source)
        return parse(env, source)

    def extracting(tree: nodes.Template):
        extractions.append(tree)
        return extract(tree)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("scan, loader ou rendu")

    with monkeypatch.context() as guard:
        guard.setattr(bridge, "_read_source", reading)
        guard.setattr(bridge, "_template_dependencies", extracting)
        guard.setattr(Environment, "parse", parsing)
        for name in ("get_template", "from_string", "compile"):
            guard.setattr(Environment, name, forbidden)
        guard.setattr(Template, "render", forbidden)
        for name in ("iterdir", "glob", "rglob", "open"):
            guard.setattr(Path, name, forbidden)
        for attempt in (1, 2):
            graph, result = closure(project)
            assert [n.path for n in graph.templates] == list(contents)
            assert [d.path for d in graph.templates[0].dependencies] == [
                "b.html",
                "c.html",
            ]
            assert graph.templates[-1].dependencies[0].path == "a.html"
            assert not graph.truncated
            assert not any("cycle" in w for w in result.warnings)
            assert len(reads) == len(parses) == len(extractions) == 4 * attempt
            assert all(reads.count(p) == attempt for p in snapshot)
    assert snapshot == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in snapshot}


def test_terminal_dependencies(project: Path) -> None:
    views = project / "mvc/views"
    (views / "a.html").write_text('{% include "nested.html" %}')
    (views / "nested.html").write_text(
        '{% include "missing.html" %}{% include "invalid.html" %}'
        '{% include dynamic %}{% include "../secret.html" %}'
        '{% include "linked.html" %}'
    )
    (views / "invalid.html").write_text('{% include "forbidden.html" %}{% if x %}')
    (views / "linked.html").symlink_to(project / "config.py")
    graph, _ = closure(project)
    assert [n.path for n in graph.templates] == [
        "a.html",
        "nested.html",
        "missing.html",
        "invalid.html",
        "../secret.html",
        "linked.html",
    ]
    assert all(not n.dependencies for n in graph.templates[2:])
    assert graph.templates[3].syntax == "invalid"
    assert graph.templates[-1].presence == "invalid-path"
    assert graph.templates[1].dependencies[2].dynamic


def test_global_limit(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bridge, "MAX_VISITED_TEMPLATES", 3)
    views = project / "mvc/views"
    (views / "a.html").write_text('{% include ["b", "c", "d", "e"] %}')
    for name in ("b", "c", "d", "e"):
        (views / name).write_text("ok")
    original_stat = Path.lstat

    def bounded_stat(path: Path):
        assert path not in {views / "d", views / "e"}
        return original_stat(path)

    with monkeypatch.context() as guard:
        guard.setattr(Path, "lstat", bounded_stat)
        graph, result = closure(project)
    assert [n.path for n in graph.templates] == ["a.html", "b", "c"]
    assert [d.path for d in graph.templates[0].dependencies] == ["b", "c", "d", "e"]
    assert graph.truncated
    assert sum("Limite globale" in w for w in result.warnings) == 1
