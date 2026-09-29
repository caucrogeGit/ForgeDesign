"""Analyse syntaxique en mémoire uniquement : aucun loader, rendu ou fichier."""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Literal

from jinja2 import Environment, TemplateSyntaxError, nodes

from forge_design.limits import (
    MAX_SYNTAX_MESSAGE_LENGTH,
    MAX_TEMPLATE_BLOCKS,
    MAX_TEMPLATE_JINJA_TOKENS,
    MAX_TEMPLATE_REFERENCES,
    MAX_TEMPLATE_STRUCTURE_CHARS,
    MAX_TEMPLATE_STRUCTURE_NODES,
)

_END_RAW = re.compile(r"\{%[-+]?\s*endraw\s*[-+]?%\}")

ReferenceKind = Literal["extends", "include", "import", "from-import"]


@dataclass(frozen=True)
class TemplateSyntaxInfo:
    status: Literal["valid", "invalid", "unreadable"]
    line: int | None = None
    message: str | None = None


@dataclass(frozen=True)
class TemplateReference:
    kind: ReferenceKind
    path: str | None
    dynamic: bool
    line: int


@dataclass(frozen=True)
class TemplateBlock:
    name: str
    line: int


@dataclass(frozen=True)
class HtmlElement:
    tag: str
    line: int
    depth: int


@dataclass(frozen=True)
class TemplateStructureIssue:
    code: str
    message: str


@dataclass(frozen=True)
class TemplateStructure:
    syntax: TemplateSyntaxInfo
    dependencies: tuple[TemplateReference, ...] = ()
    blocks: tuple[TemplateBlock, ...] = ()
    html_elements: tuple[HtmlElement, ...] = ()
    issues: tuple[TemplateStructureIssue, ...] = ()
    partial: bool = False
    truncated: bool = False


def parse_template(source: str) -> tuple[TemplateSyntaxInfo, nodes.Template | None]:
    """Primitive historique Route Explorer, sans compilation ni résolution."""
    try:
        return TemplateSyntaxInfo("valid"), Environment(loader=None).parse(source)
    except TemplateSyntaxError as error:
        return TemplateSyntaxInfo(
            "invalid",
            error.lineno,
            " ".join((error.message or "Syntaxe Jinja invalide.").split())[
                :MAX_SYNTAX_MESSAGE_LENGTH
            ],
        ), None
    except RecursionError:
        return TemplateSyntaxInfo("unreadable"), None


def iter_template_nodes(tree: nodes.Template) -> Iterator[nodes.Node]:
    # Pile d'itérateurs : pas de récursion ni copie de toutes les fratries.
    pending: list[Iterator[nodes.Node]] = [iter((tree,))]
    while pending:
        node = next(pending[-1], None)
        if node is None:
            pending.pop()
            continue
        yield node
        pending.append(node.iter_child_nodes())


def iter_template_references(tree: nodes.Template) -> Iterator[TemplateReference]:
    for node in iter_template_nodes(tree):
        kind: ReferenceKind
        if isinstance(node, nodes.Extends):
            kind = "extends"
        elif isinstance(node, nodes.Include):
            kind = "include"
        elif isinstance(node, nodes.Import):
            kind = "import"
        elif isinstance(node, nodes.FromImport):
            kind = "from-import"
        else:
            continue
        expression = node.template
        candidates = (
            expression.items
            if isinstance(node, nodes.Include) and isinstance(expression, nodes.List)
            else [expression]
        )
        # Convention historique : liste mixte ou vide = une référence dynamique.
        if candidates and all(
            isinstance(candidate, nodes.Const) and isinstance(candidate.value, str)
            for candidate in candidates
        ):
            for candidate in candidates:
                assert isinstance(candidate, nodes.Const)
                assert isinstance(candidate.value, str)
                yield TemplateReference(kind, candidate.value, False, node.lineno)
        else:
            yield TemplateReference(kind, None, True, node.lineno)


def mask_jinja(source: str) -> tuple[str, bool]:
    """Masque lexical linéaire, conservant caractères de ligne et taille.

    Chaînes, échappements, délimiteurs imbriqués et raw sont reconnus. Une zone
    non terminée masque le reste : résultat partiel, sans inventer de tags Jinja.
    Ce scanner ne valide pas la grammaire et n'évalue aucune expression.
    """
    output = list(source)
    index = 0
    raw = False
    while index < len(source) - 1:
        if raw:
            closing = _END_RAW.search(source, index)
            if closing is None:
                return "".join(output), True
            start, stop = closing.start(), closing.end()
            for offset in range(start, stop):
                if source[offset] not in "\r\n":
                    output[offset] = " "
            index, raw = stop, False
            continue
        opener = source[index : index + 2]
        if opener not in {"{{", "{%", "{#"}:
            index += 1
            continue
        start = index
        ender = {"{{": "}}", "{%": "%}", "{#": "#}"}[opener]
        index += 2
        quote = ""
        brackets: list[str] = []
        while index < len(source):
            char = source[index]
            if opener != "{#":
                if quote:
                    if char == "\\":
                        index += 2
                        continue
                    if char == quote:
                        quote = ""
                elif char in {"'", '"'}:
                    quote = char
                elif not brackets and source.startswith(ender, index):
                    break
                elif char in "([{":
                    brackets.append(char)
                elif char in ")]}":
                    if brackets:
                        brackets.pop()
            elif source.startswith(ender, index):
                break
            index += 1
        complete = index < len(source)
        stop = min(index + 2, len(source))
        directive = source[start + 2 : index].strip().strip("+-").strip()
        for offset in range(start, stop):
            if source[offset] not in "\r\n":
                output[offset] = " "
        if not complete:
            return "".join(output), True
        if opener == "{%":
            if directive == "raw":
                raw = True
            elif directive == "endraw":
                raw = False
        index = stop
    return "".join(output), raw


class _HtmlLimit(Exception):
    pass


class _HtmlStructure(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[HtmlElement] = []
        self.stack: list[str] = []
        self.positions: dict[str, list[int]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if len(self.elements) >= MAX_TEMPLATE_STRUCTURE_NODES:
            raise _HtmlLimit
        self.elements.append(HtmlElement(tag, self.getpos()[0], len(self.stack)))
        if tag not in {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }:
            self.positions.setdefault(tag, []).append(len(self.stack))
            self.stack.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        depth = len(self.stack)
        self.handle_starttag(tag, attrs)
        self._pop_to(depth)

    def _pop_to(self, depth: int) -> None:
        while len(self.stack) > depth:
            tag = self.stack.pop()
            self.positions[tag].pop()
            if not self.positions[tag]:
                del self.positions[tag]

    def handle_endtag(self, tag: str) -> None:
        positions = self.positions.get(tag)
        if positions:
            self._pop_to(positions[-1])


def analyze_template_structure(source: str) -> TemplateStructure:
    """Projeter une chaîne, sans accès projet ni résolution de dépendances."""
    issues: list[TemplateStructureIssue] = []
    truncated = False
    # Garde en caractères pour les appels synthétiques ; le lecteur borne les octets.
    if len(source) > MAX_TEMPLATE_STRUCTURE_CHARS:
        return TemplateStructure(
            TemplateSyntaxInfo("unreadable"),
            issues=(
                TemplateStructureIssue(
                    "template.structure_truncated", "Source trop longue pour l'analyse."
                ),
            ),
            partial=True,
            truncated=True,
        )
    budget_exceeded = False
    try:
        for count, _ in enumerate(Environment(loader=None).lex(source), 1):
            if count > MAX_TEMPLATE_JINJA_TOKENS:
                budget_exceeded = True
                break
    except (TemplateSyntaxError, RecursionError):
        # parse_template fournit l'état et le message syntaxiques historiques.
        pass
    if budget_exceeded:
        syntax, tree = TemplateSyntaxInfo("unreadable"), None
        truncated = True
    else:
        try:
            syntax, tree = parse_template(source)
        except (ValueError, OverflowError):
            # Limites internes Python/Jinja, p. ex. entier de milliers de chiffres.
            # Garde propre au Viewer ; contrat historique Routes inchangé.
            syntax, tree = TemplateSyntaxInfo("unreadable"), None
        truncated = syntax.status == "unreadable"
    references: list[TemplateReference] = []
    blocks: list[TemplateBlock] = []
    if tree is not None:
        for reference in iter_template_references(tree):
            if len(references) >= MAX_TEMPLATE_REFERENCES:
                truncated = True
                break
            references.append(reference)
        for node in iter_template_nodes(tree):
            if isinstance(node, nodes.Block):
                if len(blocks) >= MAX_TEMPLATE_BLOCKS:
                    truncated = True
                    break
                blocks.append(TemplateBlock(node.name, node.lineno))
    if syntax.status == "invalid":
        issues.append(
            TemplateStructureIssue(
                "template.syntax_invalid", syntax.message or "Syntaxe Jinja invalide."
            )
        )
    masked, mask_partial = mask_jinja(source)
    html = _HtmlStructure()
    try:
        # Même convention de lignes que Jinja, y compris les CR seuls.
        html.feed(masked.replace("\r\n", "\n").replace("\r", "\n"))
        html.close()
    except _HtmlLimit:
        truncated = True
    except (RecursionError, ValueError, AssertionError):
        mask_partial = True
    if mask_partial or syntax.status != "valid":
        issues.append(
            TemplateStructureIssue(
                "template.html_partial",
                "Structure HTML partielle ; aucun rendu effectué.",
            )
        )
    if truncated:
        issues.append(
            TemplateStructureIssue(
                "template.structure_truncated",
                "Limite d'analyse structurelle atteinte.",
            )
        )
    return TemplateStructure(
        syntax,
        tuple(sorted(references, key=lambda item: item.line)),
        tuple(sorted(blocks, key=lambda item: item.line)),
        tuple(html.elements),
        tuple(issues),
        syntax.status != "valid" or mask_partial or truncated,
        truncated,
    )
