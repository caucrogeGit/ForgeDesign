"""Cliquet ADR-002 (style de SéquenCiel) appliqué à l'interface de Forge Design.

Règles vérifiées sur le texte affiché, jamais sur le code : pas de tiret
cadratin (règle 4), pas de point-virgule à l'écran (règle 7 bis), espace
insécable devant « : ; ? ! » et dans les guillemets (règle 3), une phrase par
ligne (règle 7), aides en noir italique après leur formulaire (règles 11, 12).
"""

import ast
import re
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

import pytest
from test_web_recent_projects import call, project, running

import forge_design
from forge_design.recent_projects import RecentProjects
from forge_design.web.typography import NBSP, french_typography

PACKAGE = Path(forge_design.__file__).parent
TEMPLATES = PACKAGE / "web/templates"
VERBATIM = {"pre", "code", "kbd", "samp", "script", "style", "textarea", "title"}
VOID = {"br", "hr", "img", "input", "meta", "link", "source", "wbr", "area", "col"}
BLOCKS = {"p", "li", "dt", "dd", "td", "th", "h1", "h2", "h3", "h4", "summary"} | {
    "label",
    "caption",
    "legend",
    "button",
    "div",
    "section",
    "ul",
    "ol",
}
# Deux-points de ponctuation française (espace insécable devant), pas « 10:00 ».
FRENCH_COLON = re.compile(r"[\s\u00a0]:")
# Point-virgule de prose : entre deux mots, hors type MIME et en-tête CSP.
PROSE_SEMICOLON = re.compile(r"[a-zà-ÿ»)] ?; (?!charset=)[a-zà-ÿ]", re.I)


def _template_text(source: str) -> str:
    for pattern in (
        r"\{#.*?#\}",
        r"\{%.*?%\}",
        r"\{\{.*?\}\}",
        r"<(pre|code|kbd|samp)\b.*?</\1>",
        r"<!--.*?-->",
        r"<[^>]*>",
    ):
        source = re.sub(pattern, " ", source, flags=re.S)
    return unescape(source)


@pytest.mark.parametrize(
    "path", sorted(TEMPLATES.glob("*.html")), ids=lambda path: path.name
)
def test_template_text_has_no_em_dash_nor_semicolon(path: Path) -> None:
    text = _template_text(path.read_text(encoding="utf-8"))
    assert "—" not in text
    assert ";" not in text


def test_preview_frame_spaces_are_already_non_breaking() -> None:
    # Le cadre d'aperçu est rendu sans french_typography (le Design reste tel
    # quel) : son propre texte porte donc lui-même ses espaces insécables.
    text = _template_text((TEMPLATES / "preview_frame.html").read_text("utf-8"))
    assert not re.search(r"[ \t][:;?!]", text)
    source = (PACKAGE / "web/editor_preview.py").read_text(encoding="utf-8")
    errors = re.findall(r'error="([^"]*)"', source)
    assert errors and not any(re.search(r" [:;?!]", item) for item in errors)


def test_script_messages_are_typographic() -> None:
    # Textes posés par les scripts (statut des graphes, annonces des modules,
    # nom de la minicarte) : ils ne passent pas par render_page. Les exceptions
    # destinées au développeur (throw) ne s'affichent pas.
    shown = re.compile(r"textContent =|announce\(|return `")
    literal = re.compile(r"`[^`]*`|\"[^\"]*\"")
    found: list[str] = []
    for path in sorted((PACKAGE / "web/static").rglob("*.js")):
        for number, line in enumerate(path.read_text("utf-8").splitlines(), 1):
            if not shown.search(line) or "throw " in line:
                continue
            texts = literal.findall(re.sub(r"\$\{[^}]*\}", "x", line))
            if any("—" in text or re.search(r" [:;?!]|;", text) for text in texts):
                found.append(f"{path.name}:{number}")
    assert found == []


def _strings(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(
            node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        )
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    return [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def test_python_messages_have_no_em_dash_nor_prose_semicolon() -> None:
    found = [
        f"{path.relative_to(PACKAGE)}:{line}"
        for path in sorted(PACKAGE.rglob("*.py"))
        for line, value in _strings(path)
        if "—" in value or PROSE_SEMICOLON.search(value)
    ]
    assert found == []


def test_typography_spaces_and_sentences() -> None:
    html = french_typography(
        "<p>État : actif. Rechargez la page ! « x »</p><p>Où ? Ici ; là.</p>"
    )
    assert html == (
        f"<p>État{NBSP}: actif. <br>Rechargez la page{NBSP}! <br>«{NBSP}x{NBSP}»</p>"
        f"<p>Où{NBSP}? <br>Ici{NBSP}; là.</p>"
    )


def test_typography_keeps_code_attributes_and_controls() -> None:
    html = (
        '<title>A : b</title><a title="x : y" href="/a?b=1">Lien : ok</a>'
        "<pre>a : b. C</pre><code>x ? y</code><kbd>Ctrl : K</kbd>"
        "<button>Ouvrir. Fermer</button><summary>Avis. Suite</summary>"
        "<select><option>a : b</option></select><!-- a : b -->"
        "<script>a ? b : c</script><style>a:b</style><textarea>a : b</textarea>"
    )
    expected = html.replace("Lien : ok", f"Lien{NBSP}: ok")
    assert french_typography(html) == expected


def test_one_colon_per_sentence_is_checked_across_inline_tags() -> None:
    page = _Page()
    page.feed("<p>Erreur : <a>cycle : a</a>.</p><p>Fin.</p>")
    page.flush()
    assert page.lines == ["Erreur : cycle : a.", "Fin."]
    with pytest.raises(AssertionError):
        _check(french_typography("<ul><li>Erreur : <a>cycle : a</a>.</li></ul>"))
    _check(french_typography("<p>Erreur · cycle : a.<br>Ligne : 4.</p>"))


def test_typography_does_not_split_lowercase_or_abbreviations() -> None:
    assert french_typography("<p>v0.4.0 et 1.5 Mo. fin</p>") == (
        "<p>v0.4.0 et 1.5 Mo. fin</p>"
    )


class _Page(HTMLParser):
    """Texte affiché, découpé aux balises, avec la pile des éléments ouverts."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.texts: list[tuple[tuple[str, ...], str]] = []
        self.help: list[tuple[str, dict[str, str | None]]] = []
        self.order: list[str] = []
        # Texte de chaque bloc, coupé aux <br>, sans le code : une phrase y
        # reste entière même quand un lien ou un <strong> la traverse.
        self.lines: list[str] = []
        self._line: list[str] = []

    def flush(self) -> None:
        line = " ".join("".join(self._line).split())
        if line:
            self.lines.append(line)
        self._line = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if "help-text" in (values.get("class") or "").split():
            self.help.append((tag, values))
            self.order.append("help")
        if tag in {"form", "button", "input", "iframe"}:
            self.order.append(tag)
        if tag in BLOCKS or tag == "br":
            self.flush()
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in BLOCKS:
            self.flush()
        if tag in self.stack:
            while self.stack.pop() != tag:
                pass

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.texts.append((tuple(self.stack), data))
        if not VERBATIM.intersection(self.stack) and "option" not in self.stack:
            self._line.append(data)


def _screen(page: _Page) -> list[str]:
    return [
        text
        for stack, text in page.texts
        if not VERBATIM.intersection(stack) and "option" not in stack
    ]


def _check(html: str) -> _Page:
    page = _Page()
    page.feed(html)
    for text in _screen(page):
        assert "—" not in text, text
        assert not PROSE_SEMICOLON.search(text), text
        assert not re.search(r"[ \t][:;?!]", text), text
        assert not re.search(r"«[ \t]|[ \t]»", text), text
    for stack, text in page.texts:
        if VERBATIM.intersection(stack) or {"button", "summary"} & set(stack):
            continue
        assert not re.search(r"[.!?…] +[A-ZÀÂÇÉÈÊÎÔÙÛ«]", text), text
    page.flush()
    for line in page.lines:
        for sentence in re.split(r"(?<=[.!?…])\s+", line):
            assert len(FRENCH_COLON.findall(sentence)) <= 1, sentence
    return page


def test_rendered_pages_follow_adr_002(tmp_path: Path) -> None:
    root = project(tmp_path / "project")
    (root / "mvc/views").mkdir()
    (root / "mvc/views/page.html").write_text("<p>{{ titre }}</p>")
    with running(RecentProjects(tmp_path / "config/recent.json")) as app:
        _check(call(app, "/")[1])
        status, html, _ = call(app, "/inspector", method="POST", value=str(root))
        assert status in {200, 303}
        pages = {
            url: call(app, url)
            for url in (
                "/",
                "/inspector",
                "/routes",
                "/entities",
                "/templates",
                "/templates/view?path=page.html",
                "/debug",
                "/editor",
            )
        }
    for url, (status, html, _) in pages.items():
        assert status == 200, url
        _check(html)
    help_tags = _Page()
    help_tags.feed(pages["/inspector"][1])
    assert help_tags.help, "aide attendue sur la Vue d'ensemble"
    # Règle 11 : l'aide du chemin suit le bouton qui envoie le formulaire.
    assert help_tags.order.index("button") < help_tags.order.index("help")


def test_help_text_style_is_black_italic() -> None:
    css = (PACKAGE / "web/static/shell.css").read_text(encoding="utf-8")
    rule = re.search(r"^\.help-text,[^{]*\{([^}]*)\}", css, re.M)
    assert rule is not None
    assert "color: var(--ink);" in rule.group(1)
    assert "font-style: italic;" in rule.group(1)
