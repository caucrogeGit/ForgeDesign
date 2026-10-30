"""Sondes du mode analyse (FD-INSPECT-001, étape 1).

Les sondes ne sont jamais posées sur le Forge du processus pytest : les tests
unitaires visent de faux Router et module db et un Environment Jinja dédié ;
le bout en bout passe par un processus enfant sur le squelette rc9.
"""

import http.client
import json
import socket
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from jinja2 import DictLoader, Environment
from real_preview_support import make_project
from test_real_preview_controller import _imports  # pyright: ignore[reportPrivateUsage]

import forge_design.real_preview as real_preview
from forge_design.real_preview import child_bootstrap
from forge_design.real_preview import child_inspect as ci

BOOTSTRAP = Path(real_preview.__file__).with_name("child_bootstrap.py")
INSPECT = Path(real_preview.__file__).with_name("child_inspect.py")


def test_inspect_uses_only_the_standard_library() -> None:
    assert _imports(INSPECT) <= sys.stdlib_module_names


# ── Arguments ────────────────────────────────────────────────────────────────


def test_parse_arguments() -> None:
    parse = child_bootstrap.parse_arguments
    assert parse(["--port", "8080"]) == (8080, False, None)
    assert parse(["--port", "8080", "--inspect"]) == (8080, True, None)
    assert parse(["--port", "8080", "--inspect", "--db", "x_analyse"]) == (
        8080,
        True,
        "x_analyse",
    )


@pytest.mark.parametrize(
    "arguments",
    [
        ["--inspect", "--port", "8080"],
        ["--port", "8080", "--Inspect"],
        ["--port", "8080", "--inspect", "--inspect"],
        ["--port", "80", "--inspect"],
        ["--inspect"],
        ["--port", "8080", "--db", "x_analyse"],
        ["--port", "8080", "--db", "x_analyse", "--inspect"],
        ["--port", "8080", "--inspect", "--db"],
        ["--port", "8080", "--inspect", "--db", "x_analyse", "--inspect"],
    ],
)
def test_parse_arguments_refuses(arguments: list[str]) -> None:
    assert child_bootstrap.parse_arguments(arguments) is None


# ── Contexte HTML ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("html", "safe"),
    [
        ("<main>", True),
        ("<p>a < b et ", True),
        ('<a href="', False),
        ("<div class=x ", False),
        ("<title>", False),
        ("<title>x</title><p>", True),
        ("<script>", False),
        ("<SCRIPT type=module>", False),
        ("<style>", False),
        ("<textarea name=t>", False),
        ("<!-- note ", False),
        ("<!-- note --><p>", True),
    ],
)
def test_safe_context(html: str, safe: bool) -> None:
    assert ci.safe_context(html, len(html)) is safe


# ── Marqueurs ────────────────────────────────────────────────────────────────

BASE = (
    "{# layout #}\n<!DOCTYPE html>\n<html><head>"
    "<title>{% block title %}App{% endblock %}</title></head>\n"
    '<body class="b">{% block content %}{% endblock %}'
    "<footer>{% block footer %}pied{% endblock %}</footer></body></html>"
)
PAGE = (
    '{% extends "base.html" %}\n'
    "{% block title %}Page{% endblock %}\n"
    "{% block content %}<p>{% include 'part.html' %}</p>{% endblock %}"
)


def _instrument(source: str, unsafe: set[str] | None = None, wrap: bool = True) -> str:
    shape = ci.TemplateShape(source)
    return ci.instrument_source(shape, 7, unsafe_blocks=unsafe or set(), wrap=wrap)


def test_layout_is_wrapped_inside_body_and_title_untouched() -> None:
    assert _instrument(BASE) == (
        "{# layout #}\n<!DOCTYPE html>\n<html><head>"
        "<title>{% block title %}App{% endblock %}</title></head>\n"
        '<body class="b"><!--fd:t:7-->'
        "{% block content %}<!--fd:b:7:content--><!--/fd:b:7-->{% endblock %}"
        "<footer>{% block footer %}<!--fd:b:7:footer-->pied<!--/fd:b:7-->{% endblock %}"
        "</footer><!--/fd:t:7--></body></html>"
    )


def test_child_is_not_wrapped_and_inherits_unsafe_blocks() -> None:
    assert _instrument(PAGE, unsafe={"title"}) == (
        '{% extends "base.html" %}\n'
        "{% block title %}Page{% endblock %}\n"
        "{% block content %}<!--fd:b:7:content--><p>{% include 'part.html' %}</p>"
        "<!--/fd:b:7-->{% endblock %}"
    )


def test_fragment_is_wrapped_whole() -> None:
    assert _instrument("<li>x</li>") == "<!--fd:t:7--><li>x</li><!--/fd:t:7-->"
    assert _instrument("<li>x</li>", wrap=False) == "<li>x</li>"


def test_document_without_body_is_not_wrapped() -> None:
    assert _instrument("<!doctype html><html></html>") == "<!doctype html><html></html>"


def test_dynamic_parent_marks_no_block() -> None:
    source = "{% extends layout %}{% block content %}x{% endblock %}"
    shape = ci.TemplateShape(source)
    assert shape.dynamic_extends and shape.extends is None
    assert ci.instrument_source(shape, 7, unsafe_blocks=None, wrap=True) == source


def test_required_raw_comments_and_whitespace_control() -> None:
    source = (
        "{%- block a required -%}{%- endblock -%}"
        "{# {% block faux %}{% endblock %} #}"
        "{% raw %}{% block brut %}{% endblock %}{% endraw %}"
        "{%- block b scoped -%} y {%- endblock b -%}"
    )
    shape = ci.TemplateShape(source)
    assert [block[0] for block in shape.blocks] == ["a", "b"]
    assert _instrument(source, wrap=False) == source.replace(
        "{%- block b scoped -%} y {%- endblock b -%}",
        "{%- block b scoped -%}<!--fd:b:7:b--> y <!--/fd:b:7-->{%- endblock b -%}",
    )


def test_nested_blocks_and_unsafe_include() -> None:
    source = (
        "{% block outer %}<div>{% block inner %}{% endblock %}</div>{% endblock %}"
        "<a title=\"{% include 'tip.html' %}\">"
    )
    shape = ci.TemplateShape(source)
    assert shape.unsafe_includes == {"tip.html"}
    assert _instrument(source, wrap=False) == (
        "{% block outer %}<!--fd:b:7:outer--><div>{% block inner %}"
        "<!--fd:b:7:inner--><!--/fd:b:7-->{% endblock %}</div><!--/fd:b:7-->"
        "{% endblock %}<a title=\"{% include 'tip.html' %}\">"
    )


@pytest.mark.parametrize(
    "source", ["{% block a %}", "{% endblock %}", "{% block %}{% endblock %}"]
)
def test_unbalanced_blocks_are_invalid(source: str) -> None:
    assert not ci.TemplateShape(source).valid


# ── Sondes sur de faux Forge ─────────────────────────────────────────────────


def controller_show(request: object) -> None:
    """Handler factice localisé par la sonde."""


class FakeEntry:
    method = "GET"
    pattern = "/clients/{id}"
    name = "clients-show"
    public = False
    api = False
    handler = staticmethod(controller_show)


class FakeRouter:
    def match(self, method: str, path: str) -> Any:
        return (FakeEntry(), {"id": "42"}) if path.startswith("/clients/") else None


class FakeDb:
    @staticmethod
    def _run_query(sql: str, params: Any = (), **options: Any) -> Any:
        if "boom" in sql:
            raise RuntimeError("base")
        return [{"id": 1}, {"id": 2}] if options.get("fetch") == "all" else 3


TEMPLATES = {
    "base.html": BASE,
    "page.html": PAGE,
    "part.html": "<b>{{ secret }}</b>",
    "notes.txt": "{% block content %}texte{% endblock %}",
}


@pytest.fixture
def probes() -> Iterator[tuple[Callable[..., Any], ci.TraceStore, Environment]]:
    router = type("Router", (FakeRouter,), {})
    db = type("Db", (FakeDb,), {})
    environment = Environment(loader=DictLoader(TEMPLATES), autoescape=True)
    ci.install_route_probe(router)
    ci.install_sql_probe(db)
    ci.install_template_probe(environment, ci.TemplateRegistry())
    store = ci.TraceStore(limit=3)

    def application(environ: dict[str, Any], start_response: Callable[..., Any]) -> Any:
        router().match(environ["REQUEST_METHOD"], environ["PATH_INFO"])
        router().match("GET", "/clients/autre")  # ignorée : seul le premier appel
        query = db._run_query  # pyright: ignore[reportPrivateUsage]
        query("SELECT * FROM clients WHERE id = ?", ("valeur-secrète",), fetch="all")
        query("UPDATE x SET y = 1", (), fetch=None)
        try:
            query("boom", ())
        except RuntimeError:
            pass
        body = environment.get_template(environ.get("TEMPLATE", "page.html")).render(
            secret="<i>"
        )
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [body.encode()]

    yield ci.inspect_app(application, store), store, environment


def _call(
    app: Callable[..., Any], path: str, **extra: Any
) -> tuple[str, dict[str, str], str]:
    captured: dict[str, Any] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"], captured["headers"] = status, dict(headers)

    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": path, **extra}
    body = b"".join(app(environ, start_response)).decode()
    return captured["status"], captured["headers"], body


def test_trace_of_a_request(probes: Any) -> None:
    app, store, _ = probes
    status, headers, body = _call(app, "/clients/42")
    assert status == "200 OK"
    trace = store.get(headers[ci.TRACE_HEADER])
    assert trace is not None
    assert trace["route"] == {
        "methods": ["GET"],
        "pattern": "/clients/{id}",
        "name": "clients-show",
        "public": False,
        "api": False,
        "params": ["id"],
    }
    assert trace["handler"]["qualname"] == "controller_show"
    assert trace["handler"]["file"] == "tests/test_real_preview_inspect.py"
    assert trace["handler"]["line"] == controller_show.__code__.co_firstlineno
    assert [
        (q["sql"][:6], q["params"], q["rows"], q["error"]) for q in trace["queries"]
    ] == [
        ("SELECT", 1, 2, None),
        ("UPDATE", 0, 3, None),
        ("boom", 0, None, "RuntimeError"),
    ]
    assert "valeur-secrète" not in json.dumps(trace)
    assert [(t["name"], t["extends"], t["loads"]) for t in trace["templates"]] == [
        ("page.html", "base.html", 1),
        ("base.html", None, 1),
        ("part.html", None, 1),
    ]
    ids = {t["name"]: t["id"] for t in trace["templates"]}
    page, base, part = ids["page.html"], ids["base.html"], ids["part.html"]
    assert "<title>Page</title>" in body
    assert body.endswith(
        f'<body class="b"><!--fd:t:{base}--><!--fd:b:{page}:content-->'
        f"<p><!--fd:t:{part}--><b>&lt;i&gt;</b><!--/fd:t:{part}--></p>"
        f"<!--/fd:b:{page}--><footer><!--fd:b:{base}:footer-->pied<!--/fd:b:{base}-->"
        f"</footer><!--/fd:t:{base}--></body></html>"
    )


def test_non_html_templates_are_left_alone(probes: Any) -> None:
    app, _, _ = probes
    assert _call(app, "/x", TEMPLATE="notes.txt")[2] == "texte"


def test_no_trace_outside_a_request(probes: Any) -> None:
    _, _, environment = probes
    assert ci._current.get() is None  # pyright: ignore[reportPrivateUsage]
    environment.get_template("page.html").render(secret="")


def test_unmatched_path_has_no_route(probes: Any) -> None:
    app, store, _ = probes
    _, headers, _ = _call(app, "/ailleurs")
    trace = store.get(headers[ci.TRACE_HEADER])
    assert trace is not None and trace["route"] is None and trace["handler"] is None


def test_trace_endpoint(probes: Any) -> None:
    app, _, _ = probes
    _, headers, _ = _call(app, "/clients/1")
    trace_id = headers[ci.TRACE_HEADER]
    status, served, body = _call(app, f"/__forge_design/trace/{trace_id}")
    assert status == "200 OK" and ci.TRACE_HEADER not in served
    assert served["Cache-Control"] == "no-store"
    assert json.loads(body)["id"] == trace_id
    for path in (
        "/__forge_design/trace/999",
        "/__forge_design/trace/x",
        "/__forge_design/",
    ):
        assert _call(app, path)[0] == "404 Not Found"
    assert _call(app, f"/__forge_design/trace/{trace_id}", REQUEST_METHOD="POST")[
        0
    ] == ("404 Not Found")


def test_store_keeps_the_latest_traces(probes: Any) -> None:
    app, store, _ = probes
    ids = [_call(app, "/clients/1")[1][ci.TRACE_HEADER] for _ in range(4)]
    assert store.get(ids[0]) is None
    assert all(store.get(trace_id) is not None for trace_id in ids[1:])


# ── Bout en bout : squelette Forge rc9 servi par le bootstrap ────────────────


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _get(port: int, path: str) -> tuple[http.client.HTTPResponse, str]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    connection.putrequest("GET", path, skip_host=True)
    connection.putheader("Host", f"127.0.0.1:{port}")
    connection.endheaders()
    response = connection.getresponse()
    return response, response.read().decode()


@pytest.fixture
def serve(tmp_path: Path) -> Iterator[Callable[..., int]]:
    children: list[subprocess.Popen[str]] = []

    def start(*flags: str) -> int:
        root = make_project(tmp_path / f"projet{len(children)}")
        port = _free_port()
        child = subprocess.Popen(
            [
                str(root / ".venv/bin/python"),
                "-I",
                "-B",
                "-u",
                str(BOOTSTRAP),
                "--port",
                str(port),
                *flags,
            ],
            cwd=root,
            env={"PATH": "/usr/bin:/bin", "APP_ENV": "dev"},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        children.append(child)
        assert child.stdout is not None
        for line in child.stdout:
            if "écoute sur" in line:
                return port
            assert "Mode analyse" not in line, line
        pytest.fail(f"enfant arrêté : {child.wait()}")

    yield start
    for child in children:
        child.terminate()
        child.wait(timeout=10)


def test_real_trace_on_the_skeleton(serve: Callable[..., int]) -> None:
    port = serve("--inspect")
    response, body = _get(port, "/")
    assert response.status == 200
    _, raw = _get(port, f"/__forge_design/trace/{response.getheader(ci.TRACE_HEADER)}")
    trace = json.loads(raw)
    assert trace["route"]["pattern"] == "/" and trace["route"]["name"] == "home-index"
    assert trace["handler"] == {
        "qualname": "HomeController.index",
        "module": "mvc.controllers.home_controller",
        "file": "mvc/controllers/home_controller.py",
        "line": trace["handler"]["line"],
    }
    templates = {t["name"]: t for t in trace["templates"]}
    assert templates["home/index.html"]["file"] == "mvc/views/home/index.html"
    assert templates["home/index.html"]["extends"] == "layouts/base.html"
    assert "layouts/base.html" in templates
    page, base = (
        templates["home/index.html"]["id"],
        templates["layouts/base.html"]["id"],
    )
    assert f"<!--fd:b:{page}:content-->" in body and f"<!--fd:t:{base}-->" in body
    title = body[body.index("<title>") : body.index("</title>")]
    assert "fd:" not in title


def test_without_inspect_nothing_changes(serve: Callable[..., int]) -> None:
    port = serve()
    response, body = _get(port, "/")
    assert response.status == 200 and response.getheader(ci.TRACE_HEADER) is None
    assert "fd:" not in body
    assert _get(port, "/__forge_design/trace/1")[0].status == 404


def test_db_option_wins_over_env_dev(tmp_path: Path) -> None:
    """env/dev pose DB_NAME avec override=True : la copie d'analyse l'emporte."""
    root = make_project(tmp_path / "projet", env_dev="DB_NAME=reelle\n")
    seen = tmp_path / "db_name.txt"
    with (root / "app.py").open("a", encoding="utf-8") as app:
        app.write(
            "\nimport os as _os\n"
            f"open({str(seen)!r}, 'w').write(_os.environ.get('DB_NAME', ''))\n"
        )
    command = [str(root / ".venv/bin/python"), "-I", "-B", "-u", str(BOOTSTRAP)]
    env = {"PATH": "/usr/bin:/bin", "APP_ENV": "dev"}
    port = str(_free_port())
    invalid = subprocess.run(
        [*command, "--port", port, "--inspect", "--db", "reelle"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert invalid.returncode == child_bootstrap.EXIT_USAGE
    assert "base d'analyse invalide" in invalid.stderr and not seen.exists()
    child = subprocess.Popen(
        [*command, "--port", port, "--inspect", "--db", "projet_analyse"],
        cwd=root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        assert child.stdout is not None
        for line in child.stdout:
            if "écoute sur" in line:
                break
        else:
            pytest.fail(f"enfant arrêté : {child.wait()}")
        assert seen.read_text() == "projet_analyse"
        assert _get(int(port), "/")[0].status == 200
    finally:
        child.terminate()
        child.wait(timeout=10)
