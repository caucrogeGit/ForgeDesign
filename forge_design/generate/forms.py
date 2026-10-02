"""Génération interne des formulaires HTML/HTMX et de leurs champs.

Le formulaire porte à la fois action/method (HTML natif, dégradation sans
HTMX) et hx-get/hx-post, depuis la même ViewAction.path. Les champs viennent
exclusivement de FieldDefinition : aucun id, value, placeholder ni bouton de
soumission n'est inventé.
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

FormWriter = InteractionWriter


@dataclass(frozen=True)
class FormPlan:
    """Attributs de la balise ouvrante, déjà échappés, dans l'ordre d'émission."""

    attributes: tuple[Attribute, ...]


@dataclass(frozen=True)
class FieldPlan:
    input_attributes: tuple[Attribute, ...]
    label: str | None


def prepare_form(
    node: DesignNode | PageRoot,
    path: Location,
    actions: Mapping[str, ViewAction],
    writer: FormWriter,
) -> FormPlan | None:
    """Préparer la balise entière avant émission ; None : formulaire omis."""
    interaction = prepare_interaction(
        node, path, actions, writer, missing_code="form_missing_action"
    )
    if interaction is None:
        return None
    attributes: list[Attribute] = [
        ("action", interaction.path),
        ("method", interaction.method.lower()),
    ]
    if interaction.classes is not None:
        attributes.append(("class", interaction.classes))
    attributes.append((interaction.htmx_attribute, interaction.path))
    attributes.extend(interaction.htmx)
    return FormPlan(tuple(attributes))


def render_form_open(
    plan: FormPlan, depth: int, path: Location, writer: FormWriter, *, empty: bool
) -> None:
    opening = "<form" + render_attributes(plan.attributes) + ">"
    writer.line(opening + "</form>" if empty else opening, depth, path)


def render_form_close(depth: int, path: Location, writer: FormWriter) -> None:
    writer.line("</form>", depth, path)


def prepare_field(
    node: DesignNode | PageRoot, path: Location, writer: FormWriter
) -> FieldPlan:
    """Définition déjà validée (validate_form_fields) ; seule class est une prop.

    Une prop visuelle invalide est signalée et ignorée sans bloquer le champ.
    """
    definition = node.field
    assert definition is not None
    location = (*path, "field")
    classes: str | None = None
    for key, value in (node.props or {}).items():
        prop_location = (*path, "props", key)
        if key == "class" and isinstance(value, str):
            classes = writer.escaped(value, prop_location)
        else:
            writer.issue("unsupported_prop", prop_location)
    # input_type appartient à la liste fermée FieldInputType, revalidée en amont.
    attributes: list[Attribute] = [
        ("type", definition.input_type),
        ("name", writer.escaped(definition.name, (*location, "name"))),
    ]
    if classes is not None:
        attributes.append(("class", classes))
    if definition.required is True:
        attributes.append(("required", None))
    label = (
        None
        if definition.label is None
        else writer.escaped(definition.label, (*location, "label"))
    )
    return FieldPlan(tuple(attributes), label)


def render_field(
    plan: FieldPlan, depth: int, path: Location, writer: FormWriter
) -> None:
    """Libellé englobant : pas d'id ni de for à inventer."""
    control = "<input" + render_attributes(plan.input_attributes) + ">"
    if plan.label is not None:
        control = "<label>" + plan.label + control + "</label>"
    writer.line(control, depth, path)
