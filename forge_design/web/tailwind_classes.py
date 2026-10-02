"""Édition assistée de props["class"] : tokens opaques, sans grammaire Tailwind.

Une classe est un token séparé par des blancs ASCII. Aucun préfixe (md:, hover:,
dark:…) ni valeur arbitraire ([…]) n'est interprété : Forge Design conserve la
classe telle quelle, sans garantir qu'elle existe dans le Tailwind du projet.
Ces fonctions ne touchent qu'à la clé "class" d'une copie des props ; quand la
classe ne change pas, le mapping d'origine est rendu tel quel, pour que
set_design_props constate lui-même le no-op.
"""

import re
from collections.abc import Mapping

from forge_design.design.models import PropValue

Props = Mapping[str, PropValue]

CLASS_KEY = "class"
_ASCII_BLANKS = re.compile(r"[ \t\n\r\f\v]+")

# Raccourcis courants, non normatifs : une classe absente reste autorisée.
SUGGESTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Layout", ("container", "block", "flex", "grid", "hidden")),
    ("Largeur", ("w-full", "max-w-xl", "max-w-3xl", "max-w-5xl")),
    (
        "Espacement",
        ("m-0", "mx-auto", "p-2", "p-4", "p-6", "py-4", "py-6", "py-8")
        + ("gap-2", "gap-4", "gap-6"),
    ),
    (
        "Texte",
        ("text-sm", "text-base", "text-lg", "text-xl", "text-2xl", "text-3xl")
        + ("font-medium", "font-semibold", "font-bold"),
    ),
    (
        "Couleurs",
        ("text-slate-600", "text-slate-700", "text-slate-900")
        + ("bg-white", "bg-slate-50", "bg-slate-100"),
    ),
    ("Bordures", ("border", "rounded", "rounded-lg")),
)


class ClassNotEditableError(ValueError):
    """props["class"] existe mais n'est pas une chaîne : pas de conversion."""


def parse_class_tokens(value: str) -> tuple[str, ...]:
    """Découper sur les blancs ASCII ; les blancs Unicode restent dans les tokens."""
    if "\x00" in value:
        raise ValueError("Une classe ne peut pas contenir NUL.")
    return tuple(token for token in _ASCII_BLANKS.split(value) if token)


def validate_class_token(token: str) -> str:
    """Un seul token non vide, sans blanc ASCII ni NUL ; aucune regex Tailwind."""
    if not token or parse_class_tokens(token) != (token,):
        raise ValueError("Une classe doit être un seul token sans espace.")
    return token


def current_classes(props: Props | None) -> str | None:
    """Chaîne réelle de props["class"], None si absente."""
    value = (props or {}).get(CLASS_KEY)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ClassNotEditableError("props.class n'est pas une chaîne.")
    return value


def _with_classes(props: Props | None, tokens: tuple[str, ...]) -> Props | None:
    """Copie des props où seule "class" change ; plus aucun token : clé retirée."""
    updated = dict(props or {})
    if tokens:
        # Une clé existante garde sa position ; une nouvelle est ajoutée en fin.
        updated[CLASS_KEY] = " ".join(tokens)
    else:
        updated.pop(CLASS_KEY, None)
    return updated


def set_classes(props: Props | None, value: str) -> Props | None:
    """Remplacer toute la chaîne, canonicalisée ; vide supprime la clé."""
    tokens = parse_class_tokens(value)
    current = current_classes(props)
    if tokens == parse_class_tokens(current or ""):
        return props
    return _with_classes(props, tokens)


def add_class(props: Props | None, token: str) -> Props | None:
    """Ajouter en fin si absent ; doublons historiques conservés, aucun tri."""
    validate_class_token(token)
    tokens = parse_class_tokens(current_classes(props) or "")
    if token in tokens:
        return props
    return _with_classes(props, (*tokens, token))


def remove_class(props: Props | None, token: str) -> Props | None:
    """Retirer toutes les occurrences exactes du token ; absent : inchangé."""
    validate_class_token(token)
    tokens = parse_class_tokens(current_classes(props) or "")
    if token not in tokens:
        return props
    return _with_classes(props, tuple(item for item in tokens if item != token))
