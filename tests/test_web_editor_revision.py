"""Vue d'éditeur périmée refusée (FD-EDITOR-007, ACC-004).

Chaque page d'éditeur transporte la révision du design affiché ; une action
soumise depuis une vue périmée reçoit 409 avant toute interprétation, sans
mutation ni écriture. Les formulaires sont relus dans la page comme le ferait
un navigateur : le test soumet exactement les champs affichés.
"""

import hashlib
import io
import json
import os
import re
import shutil
import threading
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from wsgiref.simple_server import WSGIServer

import pytest
from test_web_editor import (
    DESIGN,
    design_file,
    displayed_revision,
    get,
    make_root,
    request,
    serving,
)

from forge_design.design.io import read_design
from forge_design.web import editor as web_editor
from forge_design.web.editor import STALE_DESIGN_MESSAGE, design_revision_token

# Texte du contrat, figé ici (et non importé) : une régression du message échoue.
STALE = (
    "Le design a été modifié depuis l’affichage de cette page. "
    "Rechargez l’éditeur avant de recommencer."
)


def test_message_matches_the_contract() -> None:
    assert STALE_DESIGN_MESSAGE == STALE


def displayed_form(server: WSGIServer, action: str, node: str = "") -> dict[str, str]:
    """Champs du formulaire d'action affiché pour le bloc sélectionné."""
    status, html, _ = get(server, design=DESIGN, node=node)
    assert status == 200
    for form in re.findall(r'<form action="/editor/action".*?</form>', html, re.S):
        fields = {
            name: unescape(value)
            for name, value in re.findall(
                r'<input type="hidden" name="([^"]+)" value="([^"]*)"', form
            )
        }
        if fields.get("action") == action:
            return fields
    raise AssertionError(f"formulaire {action} absent")


def digest(root: Path) -> str:
    return hashlib.sha256(design_file(root).read_bytes()).hexdigest()


def kinds(root: Path) -> list[str]:
    data = json.loads(design_file(root).read_text())
    return [child["type"] for child in data["root"]["children"]]


def test_acc_004_two_tabs_never_touch_the_wrong_block(tmp_path: Path) -> None:
    """Reproduction d'ACC-004 : [section, table, section], onglet B supprime le
    bloc 0, onglet A (vue périmée) soumet la suppression du bloc 1 (« table »)."""
    root = make_root(tmp_path)
    with serving(root, tmp_path) as app:
        append = displayed_form(app, "append")
        append["block_type"] = "section"
        assert request(app, "/editor/action", append)[0] == 303
        assert kinds(root) == ["section", "table", "section"]
        # Onglet A : la « table » est sélectionnée, son formulaire est affiché.
        stale = displayed_form(app, "remove", node="1")
        # Onglet B : vue fraîche, suppression du bloc 0.
        fresh = displayed_form(app, "remove", node="0")
        assert request(app, "/editor/action", fresh)[0] == 303
        assert kinds(root) == ["table", "section"]
        after_b = digest(root)
        # Onglet A soumet sa vue périmée.
        status, html, _ = request(app, "/editor/action", stale)
    assert status == 409, "la vue périmée ne doit pas être acceptée"
    assert STALE in unescape(html)
    assert kinds(root) == ["table", "section"]
    assert digest(root) == after_b


def external_edit(root: Path) -> None:
    """Modification externe valide : un bloc ajouté en tête par un autre outil."""
    data = json.loads(design_file(root).read_text())
    data["root"]["children"].insert(0, {"type": "section", "children": []})
    design_file(root).write_text(json.dumps(data, indent=2) + "\n")


# Champs bien formés pour chaque action exposée : la garde de révision précède
# toute interprétation, la valeur exacte importe peu.
ACTIONS: dict[str, dict[str, str]] = {
    "append": {"parent": "", "block_type": "section"},
    "remove": {"path": "1"},
    "move": {"path": "1", "destination": "0"},
    "binding": {"path": "1", "binding": ""},
    "visibility": {"path": "1", "visible_if": ""},
    "props": {"path": "1", "props": "{}"},
    "columns": {"path": "1", "columns": "[]"},
    "tailwind_set": {"path": "1", "classes": "p-4"},
    "tailwind_add": {"path": "1", "class_token": "p-4"},
    "tailwind_remove": {"path": "1", "class_token": "p-4"},
}


def post(app: WSGIServer, action: str, revision: str | None) -> tuple[int, str]:
    fields = {"design": DESIGN, "action": action, **ACTIONS[action]}
    if revision is not None:
        fields["revision"] = revision
    status, html, _ = request(app, "/editor/action", fields)
    return status, html


def test_every_action_is_known_and_each_form_carries_the_displayed_revision(
    tmp_path: Path,
) -> None:
    root = make_root(tmp_path)
    assert set(ACTIONS) == set(web_editor._ACTION_FIELDS)  # pyright: ignore[reportPrivateUsage]
    with serving(root, tmp_path) as app:
        _, html, headers = get(app, design=DESIGN, node="1")
    forms = re.findall(r'<form action="/editor/action".*?</form>', html, re.S)
    expected = design_revision_token(DESIGN, read_design(root, DESIGN))
    assert expected is not None and len(forms) >= 10
    for form in forms:
        assert re.findall(r'name="revision" value="([^"]*)"', form) == [expected], form[
            :200
        ]
    # Formulaires qui ne mutent pas le design : sans révision.
    for other in re.findall(
        r'<form (?:method="post" action="/editor/real-preview/[a-z]+"'
        r'|action="/editor" method="get").*?</form>',
        html,
        re.S,
    ):
        assert 'name="revision"' not in other
    assert headers["Cache-Control"] == "no-store"
    # Opaque : ni l'empreinte du contenu, ni la taille, ni des dates en clair.
    stat = design_file(root).stat()
    assert expected != hashlib.sha256(design_file(root).read_bytes()).hexdigest()
    # Le mtime en nanosecondes (19 chiffres) n'apparaît nulle part ; le jeton est
    # un condensat de 64 hexadécimaux (périphérique et inode, courts, ne sont pas
    # cherchés en clair : leurs chiffres se retrouvent par hasard dans un hexadécimal).
    assert str(stat.st_mtime_ns) not in html
    assert re.fullmatch(r"[0-9a-f]{64}", expected)


@pytest.mark.parametrize("action", list(ACTIONS))
def test_every_action_refuses_a_stale_view_without_writing(
    tmp_path: Path, action: str
) -> None:
    root = make_root(tmp_path)
    with serving(root, tmp_path) as app:
        revision = displayed_revision(app)
        external_edit(root)
        before = design_file(root).read_bytes()
        status, html = post(app, action, revision)
    assert status == 409, action
    assert STALE in unescape(html)
    assert design_file(root).read_bytes() == before


@pytest.mark.parametrize("action", list(ACTIONS))
def test_every_action_accepts_the_current_revision(tmp_path: Path, action: str) -> None:
    root = make_root(tmp_path)
    with serving(root, tmp_path) as app:
        status, _ = post(app, action, displayed_revision(app))
    # La garde laisse passer ; l'action elle-même peut être refusée (422).
    assert status in {303, 422}, (action, status)


def test_valid_action_writes_and_redirects(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    with serving(root, tmp_path) as app:
        before = design_file(root).read_bytes()
        status, _, headers = request(
            app,
            "/editor/action",
            {
                "design": DESIGN,
                "action": "append",
                "parent": "",
                "block_type": "section",
                "revision": displayed_revision(app),
            },
        )
    assert status == 303 and "notice=saved" in headers["Location"]
    assert design_file(root).read_bytes() != before


def test_conflict_page_shows_current_design_root_selection_and_reload(
    tmp_path: Path,
) -> None:
    root = make_root(tmp_path)
    with serving(root, tmp_path) as app:
        revision = displayed_revision(app)
        external_edit(root)
        status, html, headers = request(
            app,
            "/editor/action",
            {"design": DESIGN, "action": "remove", "path": "2", "revision": revision},
        )
        assert status == 409 and headers["Cache-Control"] == "no-store"
        assert "Location" not in headers
        text = unescape(html)
        assert STALE in text and "Recharger l’éditeur" in text
        assert f'href="/editor?design={DESIGN.replace("/", "%2F")}"' in html
        # Sélection racine, jamais le chemin soumis ; formulaires sur la révision
        # courante (celle que l'utilisateur voit désormais).
        assert re.findall(r'name="path" value="([^"]*)"', html)[0] == ""
        current = design_revision_token(DESIGN, read_design(root, DESIGN))
        assert set(re.findall(r'name="revision" value="([^"]*)"', html)) == {current}
        # Après rechargement, une action valide aboutit.
        assert post(app, "append", displayed_revision(app))[0] == 303


def test_identical_bytes_replacement_is_a_new_revision(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    with serving(root, tmp_path) as app:
        revision = displayed_revision(app)
        target = design_file(root)
        copy = target.with_suffix(".copy")
        shutil.copy2(target, copy)
        os.replace(copy, target)  # mêmes octets, nouvel inode
        assert post(app, "remove", revision)[0] == 409


def test_token_covers_mtime_and_content_not_only_size(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    target = design_file(root)
    with serving(root, tmp_path) as app:
        revision = displayed_revision(app)
        stat = target.stat()
        os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
        assert post(app, "remove", revision)[0] == 409  # mtime seul changé
        revision = displayed_revision(app)
        stat = target.stat()
        data = target.read_bytes()
        changed = data.replace(b'"p-4"', b'"p-5"')
        assert changed != data and len(changed) == len(data)
        target.write_bytes(changed)
        os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        assert post(app, "remove", revision)[0] == 409  # même taille, même mtime


@pytest.mark.parametrize(
    "revision",
    [None, "", "abc", "A" * 64, "0" * 63, "0" * 65, " " + "0" * 63, "g" * 64],
)
def test_missing_empty_or_malformed_revision_is_400(
    tmp_path: Path, revision: str | None
) -> None:
    root = make_root(tmp_path)
    with serving(root, tmp_path) as app:
        before = design_file(root).read_bytes()
        status, html = post(app, "remove", revision)
    assert status == 400 and "Révision du design absente ou invalide" in unescape(html)
    assert design_file(root).read_bytes() == before


def test_altered_well_formed_token_is_409(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    with serving(root, tmp_path) as app:
        revision = displayed_revision(app)
        altered = ("0" if revision[0] != "0" else "1") + revision[1:]
        before = design_file(root).read_bytes()
        status, html = post(app, "remove", altered)
    assert status == 409 and design_file(root).read_bytes() == before
    assert altered not in html and revision not in html.replace(
        f'name="revision" value="{revision}"', ""
    )


def test_stale_view_wins_over_a_no_op(tmp_path: Path) -> None:
    """Action qui serait sans effet sur le document courant : 409, jamais 303."""
    root = make_root(tmp_path)
    with serving(root, tmp_path) as app:
        revision = displayed_revision(app)
        external_edit(root)
        before = design_file(root).read_bytes()
        # Le bloc 1 courant (ancien bloc 0) porte déjà « p-4 » : ajout sans effet.
        status, _, headers = request(
            app,
            "/editor/action",
            {
                "design": DESIGN,
                "action": "tailwind_add",
                "path": "1",
                "class_token": "p-4",
                "revision": revision,
            },
        )
    assert status == 409 and "Location" not in headers
    assert design_file(root).read_bytes() == before


def test_external_edit_between_display_and_action(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    with serving(root, tmp_path) as app:
        stale = displayed_form(app, "remove", node="1")
        external_edit(root)
        after_edit = digest(root)
        assert request(app, "/editor/action", stale)[0] == 409
    assert digest(root) == after_edit


def wsgi_post(app: Any, port: int, fields: dict[str, str]) -> str:
    """Appel direct de l'application WSGI (hors serveur mono-thread)."""
    body = urlencode(fields).encode()
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/editor/action",
        "QUERY_STRING": "",
        "CONTENT_TYPE": "application/x-www-form-urlencoded",
        "CONTENT_LENGTH": str(len(body)),
        "HTTP_HOST": f"127.0.0.1:{port}",
        "HTTP_ORIGIN": f"http://127.0.0.1:{port}",
        "HTTP_SEC_FETCH_SITE": "same-origin",
        "SERVER_NAME": "127.0.0.1",
        "SERVER_PORT": str(port),
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.input": io.BytesIO(body),
        "wsgi.errors": io.StringIO(),
        "wsgi.url_scheme": "http",
        "wsgi.version": (1, 0),
        "wsgi.multithread": True,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
    }
    statuses: list[str] = []

    def write(data: bytes) -> None:
        return None

    def start_response(status: str, headers: list[Any], exc_info: Any = None) -> Any:
        statuses.append(status)
        return write

    b"".join(app(environ, start_response))
    return statuses[0]


def test_in_process_concurrency_never_corrupts_the_design(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deux appels WSGI concurrents : une publication, un conflit métier."""
    root = make_root(tmp_path)
    with serving(root, tmp_path) as server:
        revision = displayed_revision(server)
        barrier = threading.Barrier(2, timeout=10)
        app = server.get_app()
        fields = {
            "design": DESIGN,
            "action": "append",
            "parent": "",
            "block_type": "section",
            "revision": revision,
        }
        results: list[str] = []
        threads = [
            threading.Thread(
                target=lambda: results.append(
                    (barrier.wait(), wsgi_post(app, server.server_port, fields))[1]
                )
            )
            for _ in range(2)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(20)
    codes = sorted(code.split()[0] for code in results)
    assert codes == ["303", "409"], codes
    assert kinds(root) == ["section", "table", "section"]  # une seule mutation


def test_http_server_serialises_requests() -> None:
    """Hypothèse de la garantie HTTP : le serveur traite une requête à la fois,
    donc deux POST sur la même révision passent l'un après l'autre et le second
    est refusé par la garde Web (test suivant)."""
    import socketserver

    from forge_design.web.server import ForgeDesignServer

    assert not issubclass(ForgeDesignServer, socketserver.ThreadingMixIn)
    assert not issubclass(ForgeDesignServer, socketserver.ForkingMixIn)


def test_serial_posts_with_the_same_revision_second_is_stale(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    with serving(root, tmp_path) as app:
        revision = displayed_revision(app)
        assert post(app, "append", revision)[0] == 303
        once = design_file(root).read_bytes()
        assert post(app, "append", revision)[0] == 409
    assert design_file(root).read_bytes() == once


@pytest.mark.parametrize(
    "change",
    [
        {"action": "unknown"},
        {"path": "not.a.path"},
        {"action": "props", "props": "not-json"},
        {"preview": "unknown"},
        {"unexpected": "value"},
        {"action": None},
        {"path": None},
    ],
)
def test_stale_wins_before_action_validation_or_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: dict[str, str | None]
) -> None:
    root = make_root(tmp_path)
    with serving(root, tmp_path) as app:
        fields = displayed_form(app, "remove", node="1")
        external_edit(root)
        before = design_file(root).read_bytes()
        for key, value in change.items():
            if value is None:
                fields.pop(key, None)
            else:
                fields[key] = value

        def forbidden(*args: Any, **kwargs: Any) -> Any:
            pytest.fail("Une vue périmée ne doit ni appliquer ni écrire une action")

        monkeypatch.setattr(web_editor, "_apply", forbidden)
        monkeypatch.setattr(web_editor, "write_design", forbidden)
        status, html, _ = request(app, "/editor/action", fields)
        assert status == 409 and STALE in unescape(html)
        assert design_file(root).read_bytes() == before


def test_eleven_template_forms_cover_ten_actions() -> None:
    template = (Path(web_editor.__file__).parent / "templates/editor.html").read_text()
    forms = re.findall(r'<form action="/editor/action".*?</form>', template, re.S)
    assert len(forms) == 11
    actions = [re.search(r'name="action" value="([^" ]+)"', f) for f in forms]
    names = [match.group(1) for match in actions if match is not None]
    assert set(names) == set(ACTIONS)
    assert names.count("tailwind_add") == 2  # champ libre et suggestions
    for form in forms:
        assert form.count('name="revision" value="{{ revision }}"') == 1
