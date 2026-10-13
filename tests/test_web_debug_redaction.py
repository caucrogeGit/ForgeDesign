"""Masquage renforcé (FD-DEBUG-006) vu par HTTP : liste, détail, recherche,
Project Inspector et sortie du diagnostic Forge ne contiennent aucune valeur."""

import re
from html import unescape
from pathlib import Path
from urllib.parse import quote

from runtime_diagnostics_support import forge_project
from test_debug_errors import encoded, journal
from test_web_modules import serving
from test_web_recent_projects import call
from test_web_runtime_diagnostics import post, section

SECRETS = ("VerySecret123", "Hunter4", "Abc999", "Xyz777", "Tok555")


def test_journal_list_detail_and_search_hide_values(tmp_path: Path) -> None:
    root = forge_project(tmp_path / "projet", "secret")
    path = journal(
        root,
        encoded(
            id="evt SERVICE_TOKEN=Tok555",
            message="DB_PASSWORD=VerySecret123 connection refused",
            hint="could not connect to mysql://roger:Hunter4@db.local/app",
            sql="SELECT 1 -- OPENAI_API_KEY=Xyz777",
            request={
                "method": "GET",
                "path": "/login",
                "query": "api_token=Abc999&page=2",
                "post_keys": [],
                "headers": [],
            },
        ),
    )
    source = path.read_bytes()
    with serving(tmp_path, None) as app:
        assert call(app, "/inspector", method="POST", value=str(root))[0] == 200
        _, inspector, _ = call(app, "/inspector")
        _, listing, _ = call(app, "/debug")
        link = re.search(r'href="(/debug/event\?[^"]+)"', listing)
        assert link is not None
        url = unescape(link.group(1))
        status, detail, _ = call(app, url)
        # Le champ de recherche réaffiche la saisie : seul le reste compte.
        searches = [
            re.sub(
                r"<form.*?</form>", "", call(app, "/debug?q=" + quote(s))[1], flags=re.S
            )
            for s in SECRETS
        ]
        _, ordinary, _ = call(app, "/debug?q=connection")
    assert status == 200
    for page in (inspector, listing, detail, url, *searches):
        for secret in SECRETS:
            assert secret not in page and secret.lower() not in page.lower()
    assert "DB_PASSWORD=[masqué] connection refused" in unescape(listing)
    assert "mysql://roger:[masqué]@db.local/app" in unescape(detail)
    assert "api_token=[masqué]&amp;page=2" in detail
    for page in searches:
        assert "Aucun événement ne correspond aux filtres." in page
    assert "1 événements affichés sur 1" in ordinary
    assert path.read_bytes() == source


def test_forge_diagnostic_output_hides_new_forms(tmp_path: Path) -> None:
    root = forge_project(tmp_path / "projet", "secret")
    with serving(tmp_path, None) as app:
        assert call(app, "/inspector", method="POST", value=str(root))[0] == 200
        status, html, _ = post(app)
    part = unescape(section(html))
    assert status == 200 and 'data-diagnostic-status="succeeded"' in part
    for secret in ("hunter", "k3y-777", "abc999", "t0ken-99"):
        assert secret not in html
    assert "DB_PASSWORD=[masqué] vers mysql://roger:[masqué]@db.local/app" in part
    assert "HTTP_AUTHORIZATION=[masqué]" in part
    assert "visible" in part
