"""Actions bornées des modules spécialisés (FD-EDIT-001).

Une action est une transformation métier pure, déclarée par un module pour un
de ses types de ressources : ``handler(document, payload) -> ModuleActionResult``.
Elle ne reçoit ni Request, ni Response, ni Router, ni racine de projet, ni
chemin, ni hôte : seulement le document décodé par l'hôte et un payload déjà
borné. Lecture, révision, validation, écriture atomique, historique et statut
HTTP appartiennent au cœur.

Payload V1 : champs texte d'un formulaire ``application/x-www-form-urlencoded``,
liste exacte déclarée par l'action. Les conversions typées (entier sûr, nombre
fini, booléen) sont faites par le cœur à la demande du handler ; ``null`` n'a
pas de représentation et les valeurs imbriquées n'existent pas.
"""

import hashlib
import json
import math
import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, get_args

from forge_design.specialized import PlatformCapability, SpecializedResourceRevision
from forge_design.specialized.models import is_kebab_case

MAX_MODULE_ACTIONS = 32
MAX_MODULE_ACTION_ID_CHARS = 48
# Corps HTTP d'une action, bien en deçà de la limite générale de Forge (1 Mio).
MAX_MODULE_ACTION_BYTES = 16 * 1024
MAX_MODULE_ACTION_FIELDS = 16
MAX_MODULE_ACTION_KEY_CHARS = 32
MAX_MODULE_ACTION_TEXT_CHARS = 1024
# Message d'erreur d'un module, affiché comme texte.
MAX_MODULE_ACTION_MESSAGE_CHARS = 200
# Entiers sûrs (IEEE 754, comme le JSON du Graphic Core).
MAX_SAFE_INTEGER = 2**53 - 1

# Champs de l'enveloppe, lus par l'hôte ; jamais transmis au module.
RESERVED_ACTION_FIELDS = frozenset({"type", "path", "revision", "_method"})

_FIELD = re.compile(r"[a-z][a-z0-9_-]*")
_INTEGER = re.compile(r"-?(?:0|[1-9][0-9]*)")
_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
_TOKEN = re.compile(r"[0-9a-f]{64}")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _is_instance(value: object, kind: type) -> bool:
    return isinstance(value, kind)


class ModuleActionPayloadError(ValueError):
    """Payload refusé par le module (forme ou valeur) : 400 côté hôte."""


class ModuleActionRefused(ValueError):
    """Intention métier refusée sur ce document (ex. élément absent) : 422."""


def bounded_message(error: Exception) -> str:
    """Message d'un module : une ligne de texte, sans contrôle, tronquée."""
    text = " ".join(_CONTROL.sub(" ", str(error)).split())
    if len(text) > MAX_MODULE_ACTION_MESSAGE_CHARS:
        text = text[: MAX_MODULE_ACTION_MESSAGE_CHARS - 1] + "…"
    return text


def is_action_field(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= MAX_MODULE_ACTION_KEY_CHARS
        and _FIELD.fullmatch(value) is not None
        and value not in RESERVED_ACTION_FIELDS
    )


def is_revision_token(value: object) -> bool:
    return isinstance(value, str) and _TOKEN.fullmatch(value) is not None


def check_action_text(value: str) -> None:
    """Valeur de champ acceptable par l'hôte (longueur, aucun caractère de contrôle)."""
    if len(value) > MAX_MODULE_ACTION_TEXT_CHARS:
        raise ValueError("Valeur de champ trop longue.")
    if _CONTROL.search(value):
        raise ValueError("Caractère de contrôle refusé dans un champ.")


class ModuleActionPayload(Mapping[str, str]):
    """Champs d'une action, déjà bornés par l'hôte ; lecture typée stricte.

    Chaque accesseur lève ModuleActionPayloadError (400) si le champ est absent
    ou mal formé : le module n'analyse jamais un corps HTTP.
    """

    def __init__(self, fields: Mapping[str, str]) -> None:
        if len(fields) > MAX_MODULE_ACTION_FIELDS:
            raise ValueError("Trop de champs d'action.")
        for key, value in fields.items():
            # Contrôle d'exécution : les annotations ne sont pas vérifiées.
            if not is_action_field(key) or not _is_instance(value, str):
                raise ValueError("Champ d'action invalide.")
            check_action_text(value)
        self._fields: Mapping[str, str] = MappingProxyType(dict(fields))

    def __getitem__(self, key: str) -> str:
        return self._fields[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._fields)

    def __len__(self) -> int:
        return len(self._fields)

    def __repr__(self) -> str:
        return f"ModuleActionPayload({dict(self._fields)!r})"

    def _value(self, key: str) -> str:
        try:
            return self._fields[key]
        except KeyError:
            raise ModuleActionPayloadError(f"Champ absent : {key}.") from None

    def text(
        self, key: str, *, max_chars: int | None = None, empty: bool = True
    ) -> str:
        value = self._value(key)
        if not empty and not value.strip():
            raise ModuleActionPayloadError(f"Champ vide : {key}.")
        if max_chars is not None and len(value) > max_chars:
            raise ModuleActionPayloadError(f"Champ trop long : {key}.")
        return value

    def integer(
        self,
        key: str,
        *,
        minimum: int = -MAX_SAFE_INTEGER,
        maximum: int = MAX_SAFE_INTEGER,
    ) -> int:
        value = self._value(key)
        if not _INTEGER.fullmatch(value) or len(value) > 17:
            raise ModuleActionPayloadError(f"Entier attendu : {key}.")
        number = int(value)
        if (
            not max(minimum, -MAX_SAFE_INTEGER)
            <= number
            <= min(maximum, MAX_SAFE_INTEGER)
        ):
            raise ModuleActionPayloadError(f"Entier hors bornes : {key}.")
        return number

    def number(self, key: str) -> float:
        value = self._value(key)
        if not _NUMBER.fullmatch(value):
            raise ModuleActionPayloadError(f"Nombre attendu : {key}.")
        number = float(value)
        if not math.isfinite(number):
            raise ModuleActionPayloadError(f"Nombre fini attendu : {key}.")
        return number

    def boolean(self, key: str) -> bool:
        value = self._value(key)
        if value not in {"true", "false"}:
            raise ModuleActionPayloadError(f"Booléen attendu (true/false) : {key}.")
        return value == "true"


@dataclass(frozen=True)
class ModuleActionResult:
    """Résultat d'une action : la nouvelle ressource, jamais une réponse HTTP."""

    resource: Any


ActionHandler = Callable[[Any, ModuleActionPayload], ModuleActionResult]


def is_action_result(value: object) -> bool:
    """Contrôle d'exécution du retour d'un handler de module."""
    return isinstance(value, ModuleActionResult)


@dataclass(frozen=True)
class ModuleAction:
    """Mutation métier bornée d'un type de ressource du module.

    ``fields`` est la liste exacte des champs du payload (ni plus, ni moins) ;
    ``capability`` est la capacité plateforme exigée, en plus de ``save``.
    """

    id: str
    resource_type: str
    fields: tuple[str, ...]
    handler: ActionHandler
    capability: PlatformCapability = "edit"

    def __post_init__(self) -> None:
        if not is_kebab_case(self.id) or len(self.id) > MAX_MODULE_ACTION_ID_CHARS:
            raise ValueError(f"Identifiant d'action invalide : {self.id!r}")
        if not is_kebab_case(self.resource_type):
            raise ValueError("Le type de ressource de l'action est requis.")
        if (
            not _is_instance(self.fields, tuple)
            or len(self.fields) > MAX_MODULE_ACTION_FIELDS
        ):
            raise ValueError(
                f"fields : tuple d'au plus {MAX_MODULE_ACTION_FIELDS} noms."
            )
        if not all(is_action_field(name) for name in self.fields):
            raise ValueError("Nom de champ d'action invalide ou réservé.")
        if len(set(self.fields)) != len(self.fields):
            raise ValueError("Champ d'action dupliqué.")
        if not callable(self.handler):
            raise ValueError("Le handler d'action doit être appelable.")
        if self.capability not in get_args(PlatformCapability):
            raise ValueError(f"Capacité plateforme inconnue : {self.capability!r}")


def revision_token(
    module_id: str, type_id: str, path: str, revision: SpecializedResourceRevision
) -> str:
    """Jeton public opaque d'une révision lue par l'hôte.

    Condensat de la révision complète (contenu, taille, dates, identité du
    fichier) liée au module, au type et au chemin : le navigateur ne voit ni
    périphérique ni inode et ne reconstruit jamais une révision. Le serveur
    recalcule le jeton de la révision courante et compare.
    """
    fields = [
        module_id,
        type_id,
        path,
        revision.size,
        revision.modified_ns,
        revision.digest,
        revision.device,
        revision.inode,
        revision.changed_ns,
    ]
    encoded = json.dumps(fields, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
