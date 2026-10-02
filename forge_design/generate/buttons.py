"""Génération interne des boutons : action autonome ou soumission du form parent.

Bouton d'action (binding) : URL issue exclusivement de ViewAction.path, avec la
politique commune de generate/actions.py. Bouton submit (submit) : type="submit"
et libellé explicite, sans action propre ; le form parent porte l'interaction.
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

# Libellé des seuls boutons d'action : le Design ne les nomme pas encore
# (convention de la preview). Un submit utilise toujours son propre libellé.
BUTTON_LABEL = "Action"
ButtonWriter = InteractionWriter


@dataclass(frozen=True)
class ButtonPlan:
    """Attributs et libellé déjà échappés, dans l'ordre d'émission."""

    attributes: tuple[Attribute, ...]
    label: str


def prepare_button(
    node: DesignNode | PageRoot,
    path: Location,
    actions: Mapping[str, ViewAction],
    writer: ButtonWriter,
) -> ButtonPlan | None:
    """Tout vérifier avant émission ; None (bouton omis) après diagnostic.

    Position et exclusivité d'un submit sont garanties en amont par
    validate_submit_buttons.
    """
    if node.submit is not None:
        return _prepare_submit(node, path, writer)
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
    return ButtonPlan(tuple(attributes), BUTTON_LABEL)


def _prepare_submit(
    node: DesignNode | PageRoot, path: Location, writer: ButtonWriter
) -> ButtonPlan:
    """type="submit", class et libellé ; ni hx-*, ni action, ni name/value.

    Le form parent porte l'interaction : une prop HTMX sur le submit créerait une
    seconde action implicite. Une prop refusée est signalée sans omettre le bouton.
    """
    assert node.submit is not None
    classes: str | None = None
    for key, value in (node.props or {}).items():
        location = (*path, "props", key)
        if key == "class" and isinstance(value, str):
            classes = writer.escaped(value, location)
        else:
            writer.issue("unsupported_prop", location)
    attributes: list[Attribute] = [("type", "submit")]
    if classes is not None:
        attributes.append(("class", classes))
    label = writer.escaped(node.submit.label, (*path, "submit", "label"))
    return ButtonPlan(tuple(attributes), label)


def render_button(
    plan: ButtonPlan, depth: int, path: Location, writer: ButtonWriter
) -> None:
    """Une ligne, dans le budget commun du générateur."""
    attributes = render_attributes(plan.attributes)
    writer.line("<button" + attributes + ">" + plan.label + "</button>", depth, path)
