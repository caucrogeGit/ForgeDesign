"""Génération interne des boutons HTMX depuis une action déclarée par le contrat.

L'URL vient exclusivement de ViewAction.path ; la politique commune (méthodes,
CSRF, props HTMX) est celle de generate/actions.py.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from forge_design.contracts.models import ViewAction
from forge_design.design.models import DesignNode, PageRoot
from forge_design.generate.actions import (
    Attribute,
    InteractionWriter,
    Location,
    prepare_interaction,
    render_attributes,
)

# Pas encore de représentation Design pour le libellé (convention de la preview).
BUTTON_LABEL = "Action"
ButtonWriter = InteractionWriter


@dataclass(frozen=True)
class ButtonPlan:
    """Attributs déjà échappés, dans l'ordre d'émission."""

    attributes: tuple[Attribute, ...]


def prepare_button(
    node: DesignNode | PageRoot,
    path: Location,
    actions: Mapping[str, ViewAction],
    writer: ButtonWriter,
) -> ButtonPlan | None:
    """Tout vérifier avant émission ; None (bouton omis) après diagnostic."""
    interaction = prepare_interaction(
        node, path, actions, writer, missing_code="button_missing_action"
    )
    if interaction is None:
        return None
    attributes: list[Attribute] = [("type", "button")]
    if interaction.classes is not None:
        attributes.append(("class", interaction.classes))
    attributes.append((interaction.htmx_attribute, interaction.path))
    attributes.extend(interaction.htmx)
    return ButtonPlan(tuple(attributes))


def render_button(
    plan: ButtonPlan, depth: int, path: Location, writer: ButtonWriter
) -> None:
    """Une ligne, dans le budget commun du générateur."""
    attributes = render_attributes(plan.attributes)
    writer.line("<button" + attributes + ">" + BUTTON_LABEL + "</button>", depth, path)
