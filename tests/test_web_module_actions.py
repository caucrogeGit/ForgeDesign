"""Actions de modules par HTTP (FD-EDIT-001) : POST exact, PRG, statuts, gardes."""

import json
import re
from html import unescape
from http.client import HTTPConnection
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import pytest
from module_support import (
    RENAME,
    activation,
    rename_title,
    witness_module,
    write_resource,
)
from test_module_actions import StrictCodec, action, history, title_of
from test_web_modules import resource, serving
from test_web_recent_projects import call, project

from forge_design.modules import (
    MAX_MODULE_ACTION_BYTES,
    ModuleActionPayload,
    ModuleActionResult,
)
from forge_design.web.server import ForgeDesignServer

ACTION = "/modules/witness/actions/rename-title"


def post(
    server: ForgeDesignServer,
    url: str,
    fields: list[tuple[str, str]] | str,
    *,
    origin: str | None = "local",
    site: str | None = "same-origin",
    content_type: str = "application/x-www-form-urlencoded",
    method: str = "POST",
) -> tuple[int, str, dict[str, str]]:
    headers = {"Content-Type": content_type}
    if origin is not None:
        headers["Origin"] = (
            f"http://127.0.0.1:{server.server_port}" if origin == "local" else origin
        )
    if site is not None:
        headers["Sec-Fetch-Site"] = site
    body = fields if isinstance(fields, str) else urlencode(fields)
    conn = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        conn.request(method, url, body.encode(), headers)
        response = conn.getresponse()
        return response.status, response.read().decode(), dict(response.getheaders())
    finally:
        conn.close()


def token(server: ForgeDesignServer, path: str) -> str:
    status, html, _ = call(server, resource("witness", path))
    assert status == 200
    match = re.search(r'data-revision-token="([0-9a-f]{64})"', html)
    assert match is not None
    return match.group(1)


def envelope(path: str, revision: str, **payload: str) -> list[tuple[str, str]]:
    return [("type", "document"), ("path", path), ("revision", revision)] + list(
        payload.items()
    )


def opened(server: ForgeDesignServer, root: Path) -> None:
    assert call(server, "/inspector", method="POST", value=str(root))[0] == 200


def setup(tmp_path: Path, title: str = "Avant") -> tuple[Path, str]:
    root = project(tmp_path / "projet").resolve()
    return root, write_resource(root, "witness", "demo", title=title)


def witness(**options: Any) -> Any:
    return activation(("pkg_witness", witness_module(actions=(RENAME,), **options)))


def test_nominal_post_redirect_get(tmp_path: Path) -> None:
    root, path = setup(tmp_path)
    with serving(tmp_path, witness()) as app:
        opened(app, root)
        revision = token(app, path)
        status, body, headers = post(
            app, ACTION, envelope(path, revision, title="Après")
        )
        assert status == 303 and body == ""
        location = headers["Location"]
        assert location == resource("witness", path, notice="saved")
        status, html, _ = call(app, location)
        assert status == 200 and "Modification enregistrée." in html
        assert "Après" in html and title_of(root, path) == "Après"
        assert token(app, path) != revision
        assert [line["action"] for line in history(root)] == [
            "write_specialized_resource"
        ]
        # Même intention, même document : aucune écriture, notice distincte.
        status, _, headers = post(
            app, ACTION, envelope(path, token(app, path), title="Après")
        )
        assert status == 303 and headers["Location"].endswith("notice=unchanged")
        assert "Aucune modification." in call(app, headers["Location"])[1]
        assert len(history(root)) == 1


def test_conflict_keeps_the_other_write(tmp_path: Path) -> None:
    root, path = setup(tmp_path)
    with serving(tmp_path, witness()) as app:
        opened(app, root)
        revision = token(app, path)
        write_resource(root, "witness", "demo", title="Autre onglet")
        status, html, _ = post(app, ACTION, envelope(path, revision, title="Après"))
        assert status == 409 and "rechargez" in html
        assert title_of(root, path) == "Autre onglet" and history(root) == []
        assert unescape(resource("witness", path)) in unescape(html)


@pytest.mark.parametrize(
    "extra,status",
    [
        ([], 400),
        ([("title", "a"), ("title", "b")], 400),
        ([("title", "a"), ("autre", "b")], 400),
        ([("title", "   ")], 400),
        # Surcharge Forge : DELETE est routé comme tel (405), jamais exécuté.
        ([("title", "a"), ("_method", "DELETE")], 405),
        ([("title", "a"), ("_method", "GET")], 400),
        ([("title", "a\x00")], 400),
    ],
)
def test_invalid_payload_is_400_without_write(
    tmp_path: Path, extra: list[tuple[str, str]], status: int
) -> None:
    root, path = setup(tmp_path)
    with serving(tmp_path, witness()) as app:
        opened(app, root)
        fields = envelope(path, token(app, path)) + extra
        assert post(app, ACTION, fields)[0] == status
        assert title_of(root, path) == "Avant" and history(root) == []


def test_envelope_is_checked(tmp_path: Path) -> None:
    root, path = setup(tmp_path)
    with serving(tmp_path, witness()) as app:
        opened(app, root)
        revision = token(app, path)
        cases: list[tuple[list[tuple[str, str]], int]] = [
            ([("path", path), ("revision", revision), ("title", "x")], 400),
            ([("type", "document"), ("revision", revision), ("title", "x")], 400),
            ([("type", "document"), ("path", path), ("title", "x")], 400),
            (envelope(path, "zz" * 32, title="x"), 400),
            (envelope(path, revision, title="x") + [("type", "document")], 400),
            (
                [
                    ("type", "autre"),
                    ("path", path),
                    ("revision", revision),
                    ("title", "x"),
                ],
                400,
            ),
            (
                envelope(
                    "mvc/witness/../witness/demo.witness.json", revision, title="x"
                ),
                400,
            ),
            (envelope("../../etc/passwd", revision, title="x"), 400),
            (envelope("mvc/witness/absent.witness.json", revision, title="x"), 404),
        ]
        for fields, expected in cases:
            assert post(app, ACTION, fields)[0] == expected, fields
        # Paramètres d'URL refusés : l'enveloppe vient du corps seulement.
        assert (
            post(app, ACTION + "?path=x", envelope(path, revision, title="x"))[0] == 400
        )
        assert title_of(root, path) == "Avant" and history(root) == []


def test_validation_failure_is_422(tmp_path: Path) -> None:
    root, path = setup(tmp_path)
    with serving(tmp_path, witness(codec=StrictCodec())) as app:
        opened(app, root)
        status, html, _ = post(
            app, ACTION, envelope(path, token(app, path), title="INTERDIT")
        )
        assert (
            status == 422 and "witness.forbidden" in html and "Titre interdit." in html
        )
        assert title_of(root, path) == "Avant" and history(root) == []


def test_business_refusal_is_422(tmp_path: Path) -> None:
    root, path = setup(tmp_path)

    def refuse(document: Any, payload: ModuleActionPayload) -> ModuleActionResult:
        from forge_design.modules import ModuleActionRefused

        raise ModuleActionRefused("Refus métier.")

    modules = activation(
        ("pkg_witness", witness_module(actions=(action(handler=refuse),)))
    )
    with serving(tmp_path, modules) as app:
        opened(app, root)
        status, html, _ = post(app, ACTION, envelope(path, token(app, path), title="x"))
        assert status == 422 and "Refus métier." in html


def test_module_exception_is_500_without_trace(tmp_path: Path) -> None:
    root, path = setup(tmp_path)

    def broken(document: Any, payload: ModuleActionPayload) -> ModuleActionResult:
        raise RuntimeError("/home/secret/chemin interne")

    modules = activation(
        ("pkg_witness", witness_module(actions=(action(handler=broken),)))
    )
    with serving(tmp_path, modules) as app:
        opened(app, root)
        status, html, _ = post(app, ACTION, envelope(path, token(app, path), title="x"))
        assert status == 500
        assert "Action du module en échec (RuntimeError)." in html
        assert "Traceback" not in html and "/home/secret" not in html
        assert title_of(root, path) == "Avant" and history(root) == []


@pytest.mark.parametrize(
    "origin,site",
    [
        ("http://evil.example", "same-origin"),
        (None, "same-origin"),
        ("local", "cross-site"),
        ("null", "same-origin"),
    ],
)
def test_foreign_origin_is_403(tmp_path: Path, origin: str | None, site: str) -> None:
    root, path = setup(tmp_path)
    with serving(tmp_path, witness()) as app:
        opened(app, root)
        fields = envelope(path, token(app, path), title="Pirate")
        assert post(app, ACTION, fields, origin=origin, site=site)[0] == 403
        assert title_of(root, path) == "Avant" and history(root) == []


def test_transport_limits(tmp_path: Path) -> None:
    root, path = setup(tmp_path)
    with serving(tmp_path, witness()) as app:
        opened(app, root)
        revision = token(app, path)
        too_big = envelope(path, revision, title="x" * MAX_MODULE_ACTION_BYTES)
        assert post(app, ACTION, too_big)[0] == 413
        payload = json.dumps({"type": "document", "path": path, "revision": revision})
        assert post(app, ACTION, payload, content_type="application/json")[0] == 415
        assert post(app, ACTION, "", content_type="text/plain")[0] == 415
        assert title_of(root, path) == "Avant" and history(root) == []


def test_routes_exist_only_for_exposed_actions(tmp_path: Path) -> None:
    root, path = setup(tmp_path)
    with serving(tmp_path, witness()) as app:
        opened(app, root)
        fields = envelope(path, token(app, path), title="x")
        assert post(app, "/modules/witness/actions/inconnue", fields)[0] == 404
        assert post(app, "/modules/witness/actions/", fields)[0] == 404
        assert post(app, "/modules/witness/actions/rename-title/x", fields)[0] == 404
        assert call(app, ACTION)[0] == 405
        assert post(app, ACTION, fields, method="PUT")[0] in {404, 405}
    # Cœur sans module, module en lecture seule, capacité indisponible : aucune route.
    for modules in (
        None,
        activation(("pkg_witness", witness_module())),
        witness(probe=lambda: {"spice": False}, edit_dependency=True),
    ):
        with serving(tmp_path, modules) as app:
            opened(app, root)
            _, html, _ = call(app, resource("witness", path))
            assert "data-revision-token" not in html
            assert post(app, ACTION, envelope(path, "0" * 64, title="x"))[0] == 404
    assert title_of(root, path) == "Avant"


def test_without_project_is_409(tmp_path: Path) -> None:
    _, path = setup(tmp_path)
    with serving(tmp_path, witness()) as app:
        assert post(app, ACTION, envelope(path, "0" * 64, title="x"))[0] == 409


def test_cross_module_isolation(tmp_path: Path) -> None:
    root = project(tmp_path / "projet").resolve()
    path_a = write_resource(root, "witness", "a")
    path_b = write_resource(root, "other", "b")
    modules = activation(
        ("pkg_witness", witness_module(actions=(RENAME,))),
        (
            "pkg_other",
            witness_module(
                "other", label="Autre", actions=(action(handler=rename_title),)
            ),
        ),
    )
    with serving(tmp_path, modules) as app:
        opened(app, root)
        status, html, _ = call(app, resource("other", path_b))
        match = re.search(r'data-revision-token="([0-9a-f]{64})"', html)
        assert match is not None
        token_b = match.group(1)
        # Action de « witness » avec la ressource et le jeton de « other ».
        status, _, _ = post(app, ACTION, envelope(path_b, token_b, title="X"))
        assert status == 400 and title_of(root, path_b) == "Titre"
        # Chaque module garde son espace d'actions.
        other = "/modules/other/actions/rename-title"
        status, _, headers = post(app, other, envelope(path_b, token_b, title="B2"))
        assert status == 303 and headers["Location"].startswith("/modules/other/")
        assert title_of(root, path_b) == "B2" and title_of(root, path_a) == "Titre"


def test_resource_page_notice_is_closed(tmp_path: Path) -> None:
    root, path = setup(tmp_path)
    with serving(tmp_path, witness()) as app:
        opened(app, root)
        assert call(app, resource("witness", path, notice="saved"))[0] == 200
        status, html, _ = call(app, resource("witness", path, notice="<script>"))
        assert status == 400 and "Notice inconnue." in html
        status, html, _ = call(app, resource("witness", path))
        assert "data-action-notice" not in html
