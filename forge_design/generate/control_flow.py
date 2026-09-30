"""Primitives internes de code Jinja contrôlé, sans contrat ni I/O."""

import re

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# Les constantes/opérateurs Jinja ne désignent pas une variable de contexte.
_RESERVED = frozenset(
    (
        "true",
        "false",
        "none",
        "True",
        "False",
        "None",
        "and",
        "or",
        "not",
        "in",
        "is",
        "if",
        "else",
        "for",
    )
)


def is_safe_jinja_identifier(name: str) -> bool:
    return _IDENTIFIER.fullmatch(name) is not None and name not in _RESERVED


def indent_line(line: str, level: int) -> str:
    if type(level) is not int or level < 0:
        raise ValueError("Le niveau d'indentation doit être un entier positif ou nul.")
    return "  " * level + line


def jinja_condition(name: str) -> str:
    if not is_safe_jinja_identifier(name):
        raise ValueError("Identifiant Jinja de condition invalide.")
    return "{% if " + name + " %}"


def render_jinja_loop(
    *,
    collection: str,
    item: str,
    body: tuple[str, ...],
    indent: int = 0,
) -> tuple[str, ...]:
    """Body : lignes générées de confiance, sans LF/CR, indentation relative."""
    if not is_safe_jinja_identifier(collection):
        raise ValueError("Identifiant Jinja de collection invalide.")
    if not is_safe_jinja_identifier(item) or item == "loop":
        raise ValueError("Identifiant Jinja local invalide.")
    if any("\n" in line or "\r" in line for line in body):
        raise ValueError("Le corps doit contenir des lignes sans séparateur.")
    opening = indent_line("{% for " + item + " in " + collection + " %}", indent)
    return (
        opening,
        *(indent_line(line, indent + 1) for line in body),
        indent_line("{% endfor %}", indent),
    )
