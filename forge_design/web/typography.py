"""Typographie française du texte affiché (ADR-002 de SéquenCiel, adopté pour
l'interface de Forge Design, FD-UX-008).

Appliquée une fois, après le rendu d'une page de l'interface, sur les seuls nœuds
de texte : jamais sur les attributs ni sur le contenu de ``pre``, ``code``,
``kbd``, ``samp``, ``script``, ``style``, ``textarea``, ``title``, ``option`` et
``select``, qui reproduisent du code, des données du projet ou des valeurs.

- une espace insécable précède « : », « ; », « ? » et « ! », et borde l'intérieur
  des guillemets français ;
- dans un texte de plusieurs phrases, chaque phrase commence sur une nouvelle
  ligne à l'écran : un ``<br>`` suit l'espace qui sépare deux phrases.
"""

import re

NBSP = " "
_TAG = re.compile(r"(<!--.*?-->|<[^>]*>)", re.S)
_NAME = re.compile(r"</?\s*([a-zA-Z][a-zA-Z0-9-]*)")
# Éléments dont le texte n'est jamais retouché (code, données, valeurs).
_VERBATIM = frozenset(
    {"pre", "code", "kbd", "samp", "script", "style", "textarea", "title", "option"}
)
_VOID = frozenset(
    {"br", "hr", "img", "input", "meta", "link", "source", "wbr", "area", "col"}
)
_BEFORE_DOUBLE = re.compile(r"[ \t]+(?=[:;?!])")
_AFTER_OPENING = re.compile(r"«[ \t]+")
_BEFORE_CLOSING = re.compile(r"[ \t]+»")
# Fin de phrase (point, point d'exclamation ou d'interrogation, points de
# suspension), espace(s), puis une majuscule ou un guillemet ouvrant.
_SENTENCE = re.compile(r"(?<=[.!?…])( +)(?=[A-ZÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸ«])")


def _text(segment: str, *, split: bool) -> str:
    segment = _BEFORE_DOUBLE.sub(NBSP, segment)
    segment = _AFTER_OPENING.sub("«" + NBSP, segment)
    segment = _BEFORE_CLOSING.sub(NBSP + "»", segment)
    if split:
        segment = _SENTENCE.sub(r"\1<br>", segment)
    return segment


def french_typography(html: str) -> str:
    """Le HTML rendu, texte affiché corrigé, balises et attributs inchangés."""
    parts = _TAG.split(html)
    stack: list[str] = []
    out: list[str] = []
    for index, part in enumerate(parts):
        if index % 2:
            out.append(part)
            match = _NAME.match(part)
            if match is None or part.startswith("<!"):
                continue
            name = match.group(1).lower()
            if part.startswith("</"):
                if name in stack:
                    while stack and stack.pop() != name:
                        pass
            elif name not in _VOID and not part.rstrip().endswith("/>"):
                stack.append(name)
            continue
        if not part or any(name in _VERBATIM or name == "select" for name in stack):
            out.append(part)
            continue
        # Pas de <br> dans un bouton ni dans un intitulé de bloc dépliable.
        split = not any(name in {"button", "summary"} for name in stack)
        out.append(_text(part, split=split))
    return "".join(out)
