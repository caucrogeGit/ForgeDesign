"""Choix explicites après détection, sans application ni effet de bord."""

from dataclasses import dataclass
from typing import Literal, get_args

from forge_design.safewrite.detection import TemplateChangeResult, TemplateChangeStatus

SafeWriteChoice = Literal["proceed", "cancel", "regenerate", "save_as", "mark_manual"]

# Ordre de présentation seulement : aucun choix n'est sélectionné par défaut.
# Aucun overwrite/force : un remplacement volontaire relèvera du writer.
_NO_CONFLICT_CHOICES: tuple[SafeWriteChoice, ...] = ("proceed", "cancel")
_CONFLICT_CHOICES: tuple[SafeWriteChoice, ...] = (
    "cancel",
    "regenerate",
    "save_as",
    "mark_manual",
)
_STATUSES: frozenset[str] = frozenset(get_args(TemplateChangeStatus))


@dataclass(frozen=True)
class SafeWriteDecisionOptions:
    path: str
    status: TemplateChangeStatus
    choices: tuple[SafeWriteChoice, ...]


@dataclass(frozen=True)
class SafeWriteDecision:
    """Choix daté de la détection : proceed n'autorise pas une écriture future.

    Le writer devra recontrôler la révision juste avant publication ; l'appelant
    conserve le TemplateChangeResult d'origine (expected/current).
    """

    path: str
    status: TemplateChangeStatus
    choice: SafeWriteChoice


def _status(change: TemplateChangeResult) -> TemplateChangeStatus:
    status: object = change.status
    if status not in _STATUSES:
        raise ValueError("Statut de changement inconnu.")
    return change.status


def has_write_conflict(change: TemplateChangeResult) -> bool:
    """Tout état autre que unchanged est un conflit ; aucun statut dérivé."""
    return _status(change) != "unchanged"


def decision_options(change: TemplateChangeResult) -> SafeWriteDecisionOptions:
    """Choix autorisés pour change.status ; pure, sans relecture du disque."""
    choices = _CONFLICT_CHOICES if has_write_conflict(change) else _NO_CONFLICT_CHOICES
    return SafeWriteDecisionOptions(change.path, change.status, choices)


def select_safe_write_choice(
    change: TemplateChangeResult, choice: SafeWriteChoice
) -> SafeWriteDecision:
    """Enregistrer un choix autorisé ; ValueError sinon, même typage contourné."""
    options = decision_options(change)
    if choice not in options.choices:
        raise ValueError("Choix non autorisé pour cet état du template.")
    # Conserver la valeur canonique de la matrice, jamais l'objet fourni.
    selected = options.choices[options.choices.index(choice)]
    return SafeWriteDecision(options.path, options.status, selected)
