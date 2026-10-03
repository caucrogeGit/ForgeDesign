"""Identités Circuit : génération séparée de la validation lexicale.

Forme : ``<préfixe>_<jeton>``, préfixe selon le genre (c, e, j, a), jeton
base64url. Un identifiant généré porte 96 bits d'entropie
(``secrets.token_urlsafe(12)``, 16 caractères). La validation accepte un jeton
de 8 à 64 caractères base64url, pour des identités écrites à la main ou importées.
Les identités forment un espace de noms global au document.
"""

import re
import secrets
from typing import Literal

CircuitIdKind = Literal["component", "connection", "junction", "annotation"]

ID_PREFIXES: dict[CircuitIdKind, str] = {
    "component": "c",
    "connection": "e",
    "junction": "j",
    "annotation": "a",
}

_TOKEN = r"[A-Za-z0-9_-]{8,64}"
_TOKEN_BYTES = 12


def id_pattern(kind: CircuitIdKind) -> str:
    return f"^{ID_PREFIXES[kind]}_{_TOKEN}$"


def is_circuit_id(kind: CircuitIdKind, value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(id_pattern(kind), value) is not None


def _new(kind: CircuitIdKind) -> str:
    return f"{ID_PREFIXES[kind]}_{secrets.token_urlsafe(_TOKEN_BYTES)}"


def new_component_id() -> str:
    return _new("component")


def new_connection_id() -> str:
    return _new("connection")


def new_junction_id() -> str:
    return _new("junction")


def new_annotation_id() -> str:
    return _new("annotation")
