"""Éditeur Web réel : HTTP, lecture, editor/*, write_design, sans état serveur."""

import json
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from http.client import HTTPConnection
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit
from wsgiref.simple_server import WSGIServer

import pytest
from test_web_recent_projects import call, project, running

from forge_design.app import create_tool_registry
from forge_design.recent_projects import RecentProjects
from forge_design.web import editor as web_editor
from forge_design.web.editor import format_node_path, parse_node_path

DESIGN = "contacts/list.design.json"
CONTRACT = {
    "name": "contacts/list",
    "template": "mvc/views/contacts/list.html",
    "context": {
        "page_title": {"type": "string"},
        "can_view": {"type": "boolean"},
        "contacts": {
            "type": "list",
            "entity": "Contact",
            "fields": {"nom": "string", "email": "string"},
        },
    },
    "actions": {"delete": {"method": "POST", "path": "/contacts/delete"}},
}


def design_data() -> dict[str, Any]:
    """page / section[card[title, text]] / table contacts."""
    return {
        "version": "0.1",
        "view": "contacts/list",
        "source_contract": "contacts/list.view.json",
        "root": {
            "type": "page",
            "children": [
                {
                    "type": "section",
                    "props": {"class": "p-4"},
                    "children": [
                        {
                            "type": "card",
                            "children": [
                                {"type": "title", "binding": "page_title"},
                                {"type": "text"},
                            ],
                        }
                    ],
                },
                {"type": "table", "binding": "contacts"},
            ],
        },
    }


def make_root(tmp_path: Path) -> Path:
    """Projet Forge temporaire avec Design, contrat et template témoin."""
    root = project(tmp_path / "project")
    views = root / "mvc/views/contacts"
    views.mkdir(parents=True)
    write(root, design_data())
    (views / "list.view.json").write_text(json.dumps(CONTRACT))
    (views / "list.html").write_text("<p>template intact</p>\n")
    return root


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return make_root(tmp_path)


def design_file(root: Path) -> Path:
    return root / "mvc/views" / DESIGN


def write(root: Path, data: dict[str, Any]) -> None:
    design_file(root).write_text(json.dumps(data, indent=2) + "\n")


def on_disk(root: Path) -> dict[str, Any]:
    return json.loads(design_file(root).read_text())


def snapshot(root: Path) -> tuple[bytes, int]:
    file = design_file(root)
    return file.read_bytes(), file.stat().st_mtime_ns


@contextmanager
def serving(root: Path, tmp_path: Path) -> Generator[WSGIServer, None, None]:
    """Serveur réel avec root ouvert comme projet courant."""
    with running(RecentProjects(tmp_path / "recent.json")) as server:
        assert call(server, "/inspector", method="POST", value=str(root))[0] == 200
        yield server


@pytest.fixture
def app(root: Path, tmp_path: Path) -> Iterator[WSGIServer]:
    with serving(root, tmp_path) as server:
        yield server


def request(
    server: WSGIServer,
    url: str,
    fields: Any = None,
    *,
    method: str = "POST",
    origin: str = "local",
    content_type: str = "application/x-www-form-urlencoded",
) -> tuple[int, str, dict[str, str]]:
    headers = {
        "Origin": f"http://127.0.0.1:{server.server_port}"
        if origin == "local"
        else origin,
        "Sec-Fetch-Site": "same-origin",
        "Content-Type": content_type,
    }
    conn = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        body = urlencode(fields, doseq=True) if fields is not None else ""
        conn.request(method, url, body if method == "POST" else None, headers)
        response = conn.getresponse()
        return response.status, response.read().decode(), dict(response.getheaders())
    finally:
        conn.close()


def get(server: WSGIServer, **params: str) -> tuple[int, str, dict[str, str]]:
    return request(server, "/editor?" + urlencode(params), method="GET")


def action(server: WSGIServer, **fields: str) -> tuple[int, str, dict[str, str]]:
    return request(server, "/editor/action", {"design": DESIGN, **fields})


def location(headers: dict[str, str]) -> dict[str, list[str]]:
    target = urlsplit(headers["Location"])
    assert target.path == "/editor"
    return parse_qs(target.query, keep_blank_values=True)


# Chemins HTTP.


@pytest.mark.parametrize(
    ("path", "value"), [((), ""), ((0,), "0"), ((0, 2), "0.2"), ((10, 0, 3), "10.0.3")]
)
def test_node_path_round_trip(path: tuple[int, ...], value: str) -> None:
    assert format_node_path(path) == value
    assert parse_node_path(value) == path


@pytest.mark.parametrize(
    "value",
    [
        "-1",
        "01",
        "0..1",
        "a",
        "0/1",
        "True",
        " 0",
        "0 ",
        ".",
        "0.",
        ".0",
        "١",
        "+1",
        "1e2",
    ],
)
def test_node_path_strict(value: str) -> None:
    with pytest.raises(ValueError):
        parse_node_path(value)


# GET.


def test_without_project_409(tmp_path: Path) -> None:
    with running(RecentProjects(tmp_path / "recent.json")) as server:
        status, html, headers = get(server, design=DESIGN)
        assert status == 409 and "Aucun projet ouvert." in html
        assert headers["Cache-Control"] == "no-store"


def test_tree_rendered_in_order(app: WSGIServer) -> None:
    status, html, headers = get(app, design=DESIGN)
    assert status == 200 and headers["Cache-Control"] == "no-store"
    assert 'href="/editor" aria-current="page"' in html
    order = [
        ('data-path=""', 'data-depth="0"'),
        ('data-path="0"', 'data-depth="1"'),
        ('data-path="0.0"', 'data-depth="2"'),
        ('data-path="0.0.0"', 'data-depth="3"'),
        ('data-path="0.0.1"', 'data-depth="3"'),
        ('data-path="1"', 'data-depth="1"'),
    ]
    positions = [html.index(f"{path} {depth}") for path, depth in order]
    assert positions == sorted(positions)
    assert html.count('<ul class="editor-nodes">') == html.count("</ul>") - html.count(
        "<ul>"
    )
    assert "binding : page_title" in html


def test_selected_node_and_choices(app: WSGIServer) -> None:
    html = get(app, design=DESIGN, node="0")[1]
    assert "Bloc sélectionné : section" in html
    # Enfants admissibles de section, triés ; pas de page ni de title.
    for kind in ("alert", "card", "container", "form", "grid", "table", "text"):
        assert f'<option value="{kind}">{kind}</option>' in html
    assert '<option value="title">' not in html
    # Section : seule la page peut la contenir.
    assert '<option value="">page (racine)</option>' in html
    assert "page_title (string)" in html and '<option value="can_view"' in html
    # Contrat valide : contrôles contractuels actifs.
    assert '<select id="binding" name="binding">' in html
    assert '<select id="visible-if" name="visible_if">' in html


def test_root_selected_by_default(app: WSGIServer) -> None:
    html = get(app, design=DESIGN)[1]
    assert "Bloc sélectionné : page" in html
    assert "Supprimer ce bloc" not in html and "Déplacer en dernier" not in html


def test_move_destinations_exclude_subtree(app: WSGIServer) -> None:
    html = get(app, design=DESIGN, node="0.0.1")[1]
    # text : section ou card acceptent text ; title, page et lui-même non.
    destinations = html.split('id="destination"')[1].split("</select>")[0]
    assert 'value="0"' in destinations and 'value="0.0"' in destinations
    assert 'value="0.0.1"' not in destinations and 'value=""' not in destinations


def test_design_absent_404(app: WSGIServer) -> None:
    status, html, _ = get(app, design="missing/x.design.json")
    assert status == 404 and "Design introuvable." in html


@pytest.mark.parametrize(
    "design",
    ["../x.design.json", "mvc/views/x.design.json", "x.json", "a/.b.design.json"],
)
def test_design_path_refused(app: WSGIServer, design: str) -> None:
    assert get(app, design=design)[0] == 400


def test_design_invalid_shows_diagnostics(app: WSGIServer, root: Path) -> None:
    design_file(root).write_text('{"version": "9"}')
    status, html, _ = get(app, design=DESIGN)
    assert status == 200
    assert "Diagnostics du Design" in html and "Design non chargé" in html
    assert 'class="editor-node"' not in html and "/editor/action" not in html


def test_design_badly_nested_not_editable(app: WSGIServer, root: Path) -> None:
    data = design_data()
    data["root"]["children"].append({"type": "card"})
    write(root, data)
    html = get(app, design=DESIGN)[1]
    assert 'class="editor-node"' in html and "Diagnostics du Design" in html
    assert "/editor/action" not in html


def test_without_contract_structure_only(app: WSGIServer, root: Path) -> None:
    (root / "mvc/views/contacts/list.view.json").unlink()
    status, html, _ = get(app, design=DESIGN, node="1")
    assert status == 200 and "Contrat introuvable." in html
    assert '<select id="binding" name="binding" disabled>' in html
    assert '<select id="visible-if" name="visible_if" disabled>' in html
    assert 'name="columns" rows="6" disabled' in html
    assert '<select id="block-type" name="block_type">' in html


def test_invalid_contract_structure_only(app: WSGIServer, root: Path) -> None:
    (root / "mvc/views/contacts/list.view.json").write_text("{not json")
    html = get(app, design=DESIGN)[1]
    assert "Document JSON invalide." in html and " disabled" in html


@pytest.mark.parametrize("node", ["-1", "a", "0..1", "01", "9", "0.0.0.0"])
def test_invalid_node_400(app: WSGIServer, node: str) -> None:
    assert get(app, design=DESIGN, node=node)[0] == 400


@pytest.mark.parametrize(
    "query", ["design=a&design=b", "other=1", f"design={DESIGN}&notice=hack"]
)
def test_invalid_params_400(app: WSGIServer, query: str) -> None:
    assert request(app, "/editor?" + query, method="GET")[0] == 400


def test_no_design_shows_open_form(app: WSGIServer) -> None:
    status, html, _ = request(app, "/editor", method="GET")
    assert status == 200 and 'name="design"' in html


def test_hostile_values_escaped(app: WSGIServer, root: Path) -> None:
    data = design_data()
    hostile = '<script>alert(1)</script>"><img src=x onerror=alert(1)>'
    data["root"]["children"][0]["props"] = {hostile: hostile}
    data["root"]["children"][0]["children"][0]["children"][1]["binding"] = hostile
    write(root, data)
    html = get(app, design=DESIGN, node="0")[1]
    assert "<script>alert" not in html and "<img src=x" not in html
    assert "&lt;script&gt;" in html


# POST : sécurité et forme.


def test_foreign_origin_403(app: WSGIServer, root: Path) -> None:
    before = snapshot(root)
    status, _, _ = request(
        app,
        "/editor/action",
        {"design": DESIGN, "action": "append", "parent": "", "block_type": "section"},
        origin="http://attacker.example",
    )
    assert status == 403 and snapshot(root) == before


def test_wrong_content_type_415(app: WSGIServer, root: Path) -> None:
    before = snapshot(root)
    status = request(
        app,
        "/editor/action",
        {"design": DESIGN, "action": "remove", "path": "1"},
        content_type="text/plain",
    )[0]
    assert status == 415 and snapshot(root) == before


def test_post_without_project_409(tmp_path: Path) -> None:
    with running(RecentProjects(tmp_path / "recent.json")) as server:
        status = request(
            server,
            "/editor/action",
            {"design": DESIGN, "action": "remove", "path": "0"},
        )[0]
        assert status == 409


@pytest.mark.parametrize(
    "fields",
    [
        {"action": "remove", "path": "1", "props": "{}"},  # deux actions
        {"action": "binding", "path": "0", "binding": "x", "visible_if": "y"},
        {"action": "remove"},  # champ manquant
        {"action": "explode", "path": "0"},
        {"path": "0"},
        {"action": "remove", "path": ["0", "1"]},  # champ dupliqué
        # JSON valide au-delà de la borne : refusé par la limite, pas par le parseur.
        {
            "action": "props",
            "path": "0",
            "props": json.dumps({"class": "x" * (64 * 1024)}),
        },
    ],
)
def test_malformed_actions_400(app: WSGIServer, root: Path, fields: Any) -> None:
    before = snapshot(root)
    assert request(app, "/editor/action", {"design": DESIGN, **fields})[0] == 400
    assert snapshot(root) == before


# Mutations nominales et refus.


def test_append_saves_and_redirects(app: WSGIServer, root: Path) -> None:
    status, _, headers = action(app, action="append", parent="0", block_type="text")
    assert status == 303
    assert location(headers) == {
        "design": [DESIGN],
        "node": ["0.1"],
        "notice": ["saved"],
    }
    assert on_disk(root)["root"]["children"][0]["children"][1] == {"type": "text"}
    html = get(app, design=DESIGN, node="0.1")[1]
    assert "Modification enregistrée." not in html  # sans notice
    assert 'data-path="0.1"' in html
    saved = get(app, design=DESIGN, node="0.1", notice="saved")[1]
    assert "Modification enregistrée." in saved


@pytest.mark.parametrize("block_type", ["card", "page", "unknown"])
def test_append_refused_file_unchanged(
    app: WSGIServer, root: Path, block_type: str
) -> None:
    before = snapshot(root)
    status, html, _ = action(app, action="append", parent="", block_type=block_type)
    assert status == 422 and "Modification refusée." in html
    assert snapshot(root) == before


def test_remove(app: WSGIServer, root: Path) -> None:
    status, _, headers = action(app, action="remove", path="0.0")
    assert status == 303 and location(headers)["node"] == ["0"]
    assert on_disk(root)["root"]["children"][0] == {
        "type": "section",
        "props": {"class": "p-4"},
    }
    before = snapshot(root)
    assert action(app, action="remove", path="")[0] == 422
    assert snapshot(root) == before


def test_move(app: WSGIServer, root: Path) -> None:
    status, _, headers = action(app, action="move", path="0.0.1", destination="0")
    assert status == 303 and location(headers)["node"] == ["0.1"]
    assert on_disk(root)["root"]["children"][0]["children"][1] == {"type": "text"}
    before = snapshot(root)
    assert action(app, action="move", path="0.0", destination="")[0] == 422
    assert action(app, action="move", path="0", destination="0.0")[0] == 422
    assert snapshot(root) == before


def test_binding(app: WSGIServer, root: Path) -> None:
    assert action(app, action="binding", path="0.0.1", binding="page_title")[0] == 303
    text = on_disk(root)["root"]["children"][0]["children"][0]["children"][1]
    assert text == {"type": "text", "binding": "page_title"}
    before = snapshot(root)
    assert action(app, action="binding", path="0.0.1", binding="can_view")[0] == 422
    assert snapshot(root) == before
    assert action(app, action="binding", path="0.0.1", binding="")[0] == 303
    text = on_disk(root)["root"]["children"][0]["children"][0]["children"][1]
    assert text == {"type": "text"}


def test_contract_actions_refused_without_contract(app: WSGIServer, root: Path) -> None:
    (root / "mvc/views/contacts/list.view.json").unlink()
    before = snapshot(root)
    for fields in (
        {"action": "binding", "path": "0.0.1", "binding": "page_title"},
        {"action": "visibility", "path": "0", "visible_if": "can_view"},
        {"action": "columns", "path": "1", "columns": "[]"},
    ):
        status, html, _ = action(app, **fields)
        assert status == 409 and "Contrat indisponible" in html
    assert snapshot(root) == before
    assert action(app, action="props", path="0", props='{"class": "x"}')[0] == 303


def test_visibility(app: WSGIServer, root: Path) -> None:
    assert action(app, action="visibility", path="0", visible_if="can_view")[0] == 303
    assert on_disk(root)["root"]["children"][0]["visible_if"] == "can_view"
    before = snapshot(root)
    assert action(app, action="visibility", path="0", visible_if="page_title")[0] == 422
    assert snapshot(root) == before


def test_props(app: WSGIServer, root: Path) -> None:
    props = '{"class": "max-w-5xl", "data-x": 3, "hidden": true}'
    assert action(app, action="props", path="0", props=props)[0] == 303
    assert on_disk(root)["root"]["children"][0]["props"] == {
        "class": "max-w-5xl",
        "data-x": 3,
        "hidden": True,
    }
    before = snapshot(root)
    for bad in ("{not json", "[1]", '"text"', '{"a": NaN}', '{"a": 1, "a": 2}'):
        assert action(app, action="props", path="0", props=bad)[0] == 400
    assert action(app, action="props", path="0", props='{"a": [1]}')[0] == 422
    assert snapshot(root) == before
    assert action(app, action="props", path="0", props="")[0] == 303
    assert "props" not in on_disk(root)["root"]["children"][0]


def test_columns(app: WSGIServer, root: Path) -> None:
    columns = (
        '[{"label": "Nom", "binding": "nom"}, {"label": "Email", "binding": "email"}]'
    )
    assert action(app, action="columns", path="1", columns=columns)[0] == 303
    assert on_disk(root)["root"]["children"][1]["columns"] == json.loads(columns)
    before = snapshot(root)
    unknown = '[{"label": "Âge", "binding": "age"}]'
    assert action(app, action="columns", path="1", columns=unknown)[0] == 422
    for bad in ("{bad", '{"label": "x"}', '[{"label": "x"}]', "[1]"):
        assert action(app, action="columns", path="1", columns=bad)[0] == 400
    assert snapshot(root) == before
    assert action(app, action="columns", path="1", columns="[]")[0] == 303
    assert on_disk(root)["root"]["children"][1]["columns"] == []
    assert action(app, action="columns", path="1", columns="")[0] == 303
    assert "columns" not in on_disk(root)["root"]["children"][1]


def test_noop_never_writes(
    app: WSGIServer, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[object] = []
    monkeypatch.setattr(web_editor, "write_design", lambda *a, **k: calls.append(a))  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    before = snapshot(root)
    status, _, headers = action(
        app, action="binding", path="0.0.0", binding="page_title"
    )
    assert status == 303 and location(headers)["notice"] == ["noop"]
    assert action(app, action="move", path="1", destination="")[0] == 303
    assert calls == [] and snapshot(root) == before
    assert "Aucune modification." in get(app, design=DESIGN, notice="noop")[1]


def test_conflict_409(
    app: WSGIServer, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = web_editor.read_design

    def read_then_external_edit(project: Path, path: str) -> Any:
        result = original(project, path)
        data = design_data()
        data["view"] = "external/edit"
        write(root, data)
        return result

    monkeypatch.setattr(web_editor, "read_design", read_then_external_edit)
    status, html, _ = action(app, action="append", parent="0", block_type="text")
    assert status == 409 and "modifié depuis sa lecture" in html
    assert on_disk(root)["view"] == "external/edit"


def test_write_uses_read_revision(
    app: WSGIServer, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[object] = []
    original = web_editor.write_design

    def spy(*args: Any, **kwargs: Any) -> Any:
        seen.append(kwargs["expected_revision"])
        return original(*args, **kwargs)

    monkeypatch.setattr(web_editor, "write_design", spy)
    assert action(app, action="append", parent="0", block_type="text")[0] == 303
    assert len(seen) == 1 and seen[0] is not None


# Aucune sauvegarde explicite : seule une mutation effective écrit.


def test_save_route_removed(app: WSGIServer, root: Path) -> None:
    before = snapshot(root)
    status, _, _ = request(app, "/editor/save", {"design": DESIGN})
    assert status == 404
    assert snapshot(root) == before
    for node in ("", "0", "1"):
        assert "/editor/save" not in get(app, design=DESIGN, node=node)[1]


def test_editor_refusal_never_writes(
    app: WSGIServer, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[object] = []

    def spy(*args: Any, **kwargs: Any) -> None:
        calls.append(args)

    monkeypatch.setattr(web_editor, "write_design", spy)
    assert action(app, action="append", parent="", block_type="card")[0] == 422
    assert action(app, action="binding", path="0.0.1", binding="can_view")[0] == 422
    assert calls == []


@pytest.mark.parametrize(
    "fields",
    [
        {"action": "append", "parent": "0", "block_type": "text"},
        {"action": "props", "path": "0", "props": '{"class": "x"}'},
    ],
)
def test_effective_mutation_writes_once(
    app: WSGIServer, monkeypatch: pytest.MonkeyPatch, fields: dict[str, str]
) -> None:
    calls: list[object] = []
    original = web_editor.write_design

    def spy(*args: Any, **kwargs: Any) -> Any:
        calls.append(kwargs["expected_revision"])
        return original(*args, **kwargs)

    monkeypatch.setattr(web_editor, "write_design", spy)
    assert action(app, **fields)[0] == 303
    assert len(calls) == 1 and calls[0] is not None


# Sans état, I/O encapsulée, périmètre.


def test_stateless_two_applications(root: Path, tmp_path: Path) -> None:
    with (
        running(RecentProjects(tmp_path / "a.json")) as first,
        running(RecentProjects(tmp_path / "b.json")) as second,
    ):
        for server in (first, second):
            call(server, "/inspector", method="POST", value=str(root))
        assert action(first, action="append", parent="", block_type="table")[0] == 303
        assert 'data-path="2"' in get(second, design=DESIGN)[1]
        data = design_data()
        data["root"]["children"].pop()
        write(root, data)  # modification externe : relue par la requête suivante
        assert 'data-path="1"' not in get(first, design=DESIGN)[1]


def test_web_module_does_no_direct_io() -> None:
    names = set(vars(web_editor))
    assert not names & {"os", "open", "Path", "open_directory", "read_project_source"}
    assert {"read_design", "write_design", "read_view_contract"} <= names


def test_no_template_or_history_written(app: WSGIServer, root: Path) -> None:
    template = root / "mvc/views/contacts/list.html"
    before = template.read_bytes(), template.stat().st_mtime_ns
    action(app, action="append", parent="0", block_type="text")
    action(app, action="props", path="0", props='{"class": "x"}')
    assert (template.read_bytes(), template.stat().st_mtime_ns) == before
    assert not (root / ".forge-design").exists()
    assert sorted(p.name for p in template.parent.iterdir()) == [
        "list.design.json",
        "list.html",
        "list.view.json",
    ]


def test_post_responses_no_store(app: WSGIServer) -> None:
    headers = action(app, action="append", parent="0", block_type="text")[2]
    assert headers["Cache-Control"] == "no-store"
    assert action(app, action="remove", path="")[2]["Cache-Control"] == "no-store"


def test_registry_unchanged() -> None:
    assert len(create_tool_registry().list()) == 5


def test_move_destinations_exclude_subtree_with_wide_rules(
    app: WSGIServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    # La matrice réelle est acyclique : élargir pour rendre le filtre observable.
    def allow_all_but_page(parent: str, child: str) -> bool:
        return child != "page"

    monkeypatch.setattr(web_editor, "can_contain", allow_all_but_page)
    html = get(app, design=DESIGN, node="0")[1]
    destinations = html.split('id="destination"')[1].split("</select>")[0]
    assert 'value=""' in destinations and 'value="1"' in destinations
    for inside in ('value="0"', 'value="0.0"', 'value="0.0.0"', 'value="0.0.1"'):
        assert inside not in destinations


# Classes Tailwind — FD-EDITOR-005.

HERO = {"class": "mx-auto py-8", "tag": "section", "data-test": "hero"}


def with_section_props(root: Path, props: dict[str, Any] | None) -> None:
    data = design_data()
    section = data["root"]["children"][0]
    if props is None:
        section.pop("props")
    else:
        section["props"] = props
    write(root, data)


def section_props(root: Path) -> Any:
    return on_disk(root)["root"]["children"][0].get("props")


def test_tailwind_rendering(app: WSGIServer, root: Path) -> None:
    with_section_props(root, HERO)
    html = get(app, design=DESIGN, node="0")[1]
    assert "Classes Tailwind" in html
    assert 'name="classes" value="mx-auto py-8"' in html
    for token in ("mx-auto", "py-8"):
        assert f'<li class="class-token"><code>{token}</code>' in html
        assert f'aria-label="Retirer {token}"' in html
    # Suggestions non normatives ; celles déjà présentes sont désactivées.
    assert 'name="class_token" value="max-w-5xl">' in html
    assert 'name="class_token" value="mx-auto" disabled>' in html
    assert '<datalist id="tailwind-suggestions">' in html
    assert "style=" not in html


def test_tailwind_add(app: WSGIServer, root: Path) -> None:
    with_section_props(root, HERO)
    status, _, headers = action(
        app, action="tailwind_add", path="0", class_token="max-w-5xl"
    )
    assert status == 303 and location(headers)["node"] == ["0"]
    assert section_props(root) == {**HERO, "class": "mx-auto py-8 max-w-5xl"}
    assert list(section_props(root)) == ["class", "tag", "data-test"]
    html = get(app, design=DESIGN, node="0")[1]
    assert 'name="classes" value="mx-auto py-8 max-w-5xl"' in html


@pytest.mark.parametrize(
    "token",
    ["md:grid-cols-2", "hover:bg-slate-100", "w-[37px]", "[mask-type:luminance]"],
)
def test_tailwind_add_free_token(app: WSGIServer, root: Path, token: str) -> None:
    assert action(app, action="tailwind_add", path="0", class_token=token)[0] == 303
    assert section_props(root)["class"] == "p-4 " + token


def test_tailwind_add_on_block_without_props(app: WSGIServer, root: Path) -> None:
    assert action(app, action="tailwind_add", path="1", class_token="w-full")[0] == 303
    assert on_disk(root)["root"]["children"][1] == {
        "type": "table",
        "binding": "contacts",
        "props": {"class": "w-full"},
    }


@pytest.mark.parametrize("token", ["a b", "a\tb", "a\nb", "", "a\x00b"])
def test_tailwind_token_with_blank_400(app: WSGIServer, root: Path, token: str) -> None:
    before = snapshot(root)
    assert action(app, action="tailwind_add", path="0", class_token=token)[0] == 400
    assert action(app, action="tailwind_remove", path="0", class_token=token)[0] == 400
    assert snapshot(root) == before


def test_tailwind_remove_all_occurrences(app: WSGIServer, root: Path) -> None:
    with_section_props(root, {**HERO, "class": "mx-auto py-8 mx-auto"})
    assert (
        action(app, action="tailwind_remove", path="0", class_token="mx-auto")[0] == 303
    )
    assert section_props(root) == {**HERO, "class": "py-8"}
    html = get(app, design=DESIGN, node="0")[1]
    assert "<code>mx-auto</code>" not in html


def test_tailwind_remove_last_keeps_empty_mapping(app: WSGIServer, root: Path) -> None:
    with_section_props(root, {"class": "p-4"})
    assert action(app, action="tailwind_remove", path="0", class_token="p-4")[0] == 303
    assert section_props(root) == {}


def test_tailwind_set_only_changes_class(app: WSGIServer, root: Path) -> None:
    with_section_props(root, HERO)
    status = action(app, action="tailwind_set", path="0", classes="  b\ta  c ")[0]
    assert status == 303
    assert section_props(root) == {**HERO, "class": "b a c"}
    assert on_disk(root)["root"]["children"][1] == design_data()["root"]["children"][1]


def test_tailwind_set_clear(app: WSGIServer, root: Path) -> None:
    with_section_props(root, HERO)
    assert action(app, action="tailwind_set", path="0", classes="")[0] == 303
    assert section_props(root) == {"tag": "section", "data-test": "hero"}


@pytest.mark.parametrize(
    ("props", "fields"),
    [
        (HERO, {"action": "tailwind_set", "path": "0", "classes": "mx-auto  py-8"}),
        (HERO, {"action": "tailwind_add", "path": "0", "class_token": "py-8"}),
        (HERO, {"action": "tailwind_remove", "path": "0", "class_token": "flex"}),
        (None, {"action": "tailwind_set", "path": "0", "classes": "   "}),
        (None, {"action": "tailwind_remove", "path": "0", "class_token": "flex"}),
    ],
)
def test_tailwind_noop_never_writes(
    app: WSGIServer,
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    props: dict[str, Any] | None,
    fields: dict[str, str],
) -> None:
    with_section_props(root, props)
    calls: list[object] = []

    def spy(*args: Any, **kwargs: Any) -> None:
        calls.append(args)

    monkeypatch.setattr(web_editor, "write_design", spy)
    before = snapshot(root)
    status, _, headers = action(app, **fields)
    assert status == 303 and location(headers)["notice"] == ["noop"]
    assert calls == [] and snapshot(root) == before


@pytest.mark.parametrize("value", [True, 3])
def test_tailwind_non_string_class(app: WSGIServer, root: Path, value: Any) -> None:
    with_section_props(root, {"class": value, "tag": "section"})
    html = get(app, design=DESIGN, node="0")[1]
    assert "props.class n'est pas une chaîne" in html
    assert f"<code>{json.dumps(value)}</code>" in html
    assert 'value="tailwind_add"' not in html and 'value="tailwind_set"' not in html
    before = snapshot(root)
    for fields in (
        {"action": "tailwind_add", "path": "0", "class_token": "flex"},
        {"action": "tailwind_remove", "path": "0", "class_token": "flex"},
        {"action": "tailwind_set", "path": "0", "classes": "flex"},
    ):
        assert action(app, **fields)[0] == 422
    assert snapshot(root) == before
    fixed = '{"class": "flex", "tag": "section"}'
    assert action(app, action="props", path="0", props=fixed)[0] == 303


def test_tailwind_path_not_found(app: WSGIServer, root: Path) -> None:
    before = snapshot(root)
    status, html, _ = action(app, action="tailwind_add", path="9", class_token="flex")
    assert status == 422 and "Aucun bloc" in html
    assert snapshot(root) == before


def test_tailwind_post_security(app: WSGIServer, root: Path) -> None:
    before = snapshot(root)
    fields = {"design": DESIGN, "action": "tailwind_add", "path": "0"}
    status = request(
        app,
        "/editor/action",
        {**fields, "class_token": "flex"},
        origin="http://attacker.example",
    )[0]
    assert status == 403
    extra = {**fields, "class_token": "flex", "classes": "flex"}
    assert request(app, "/editor/action", extra)[0] == 400
    assert request(app, "/editor/action", fields)[0] == 400  # champ manquant
    assert snapshot(root) == before


def test_tailwind_conflict_409(
    app: WSGIServer, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = web_editor.read_design

    def read_then_external_edit(project: Path, path: str) -> Any:
        result = original(project, path)
        data = design_data()
        data["view"] = "external/edit"
        write(root, data)
        return result

    monkeypatch.setattr(web_editor, "read_design", read_then_external_edit)
    status, html, _ = action(app, action="tailwind_add", path="0", class_token="flex")
    assert status == 409 and "modifié depuis sa lecture" in html
    assert on_disk(root)["view"] == "external/edit"


def test_tailwind_uses_set_design_props(
    app: WSGIServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[object] = []
    original = web_editor.set_design_props

    def spy(*args: Any, **kwargs: Any) -> Any:
        calls.append(kwargs["props"])
        return original(*args, **kwargs)

    monkeypatch.setattr(web_editor, "set_design_props", spy)
    action(app, action="tailwind_add", path="0", class_token="flex")
    assert calls == [{"class": "p-4 flex"}]
