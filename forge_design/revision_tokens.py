"""Jeton public opaque d'une révision de fichier (moteur générique).

Partagé par les actions de modules (FD-EDIT-001) et l'éditeur structurel
(FD-EDITOR-007) : un périmètre (suite de chaînes choisie par l'appelant) et une
révision **complète** — contenu, taille, dates, identité du fichier — donnent un
condensat de 64 hexadécimaux. Le navigateur ne voit ni périphérique, ni inode,
ni date, et ne reconstruit jamais une révision : le serveur recalcule le jeton
de la révision courante et compare. Aucune sémantique métier ici.
"""

import hashlib
import json
import re
from collections.abc import Sequence
from typing import Protocol

_TOKEN = re.compile(r"[0-9a-f]{64}")


class FullRevision(Protocol):
    """Révision complète d'un fichier lu de façon sûre."""

    @property
    def size(self) -> int: ...

    @property
    def modified_ns(self) -> int: ...

    @property
    def digest(self) -> str: ...

    @property
    def device(self) -> int: ...

    @property
    def inode(self) -> int: ...

    @property
    def changed_ns(self) -> int: ...


def revision_token(scope: Sequence[str], revision: FullRevision) -> str:
    """Condensat de la révision complète, lié au périmètre donné."""
    fields: list[object] = [
        *scope,
        revision.size,
        revision.modified_ns,
        revision.digest,
        revision.device,
        revision.inode,
        revision.changed_ns,
    ]
    encoded = json.dumps(fields, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def is_revision_token(value: object) -> bool:
    """Forme d'un jeton (64 hexadécimaux minuscules) ; ne dit rien de sa validité."""
    return isinstance(value, str) and _TOKEN.fullmatch(value) is not None
