"""Génération interne des boutons HTMX depuis une action déclarée par le contrat.

L'URL vient exclusivement de ViewAction.path ; aucune route n'est déduite ni
vérifiée. Seules quelques props HTMX déclaratives sont émises, valeurs opaques
échappées ; aucun script, CDN, jeton CSRF ni runtime HTMX n'est produit.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Never, Protocol

from forge_design.contracts.models import ViewAction
from forge_design.design.models import DesignNode, PageRoot

Location = tuple[str | int, ...]

# Méthode du contrat → attribut HTMX ; les autres verbes sont reportés.
_METHOD_ATTRIBUTES: Mapping[str, str] = {"GET": "hx-get", "POST": "hx-post"}
# Ordre d'émission fixe, indépendant de l'ordre des props du Design.
_HTMX_PROPS = ("hx-target", "hx-swap", "hx-confirm")
# Pas encore de représentation Design pour le libellé (convention de la preview).
BUTTON_LABEL = "Action"


class ButtonWriter(Protocol):
    def issue(self, code: str, location: Location) -> None: ...
    def stop(self, code: str, location: Location) -> Never: ...
    def line(self, content: str, depth: int, path: Location) -> None: ...
    def escaped(self, value: str, path: Location) -> str: ...


@dataclass(frozen=True)
class ButtonPlan:
    """Attributs déjà échappés, dans l'ordre d'émission."""

    attributes: tuple[tuple[str, str], ...]


def prepare_button(
    node: DesignNode | PageRoot,
    path: Location,
    actions: Mapping[str, ViewAction],
    writer: ButtonWriter,
) -> ButtonPlan | None:
    """Tout vérifier avant émission ; None (bouton omis) après diagnostic.

    Les bindings ont déjà été validés : une action inconnue a arrêté la
    génération en amont (generate.invalid_binding).
    """
    if node.binding is None:
        writer.issue("button_missing_action", (*path, "binding"))
        return None
    action = actions[node.binding]
    attribute = _METHOD_ATTRIBUTES.get(action.method)
    if attribute is None:
        writer.issue("unsupported_action_method", (*path, "binding"))
        return None
    if action.method == "POST" and action.csrf is True:
        # Aucun jeton ni nom de champ connu : ne pas perdre l'exigence du contrat.
        writer.issue("unsupported_csrf", (*path, "binding"))
        return None
    props = node.props or {}
    classes: str | None = None
    valid = True
    for key, value in props.items():
        location = (*path, "props", key)
        if key == "class" and isinstance(value, str):
            classes = writer.escaped(value, location)
        elif key in _HTMX_PROPS:
            if not isinstance(value, str) or not value:
                writer.issue("invalid_htmx_prop", location)
                valid = False
        else:
            # tag compris : un bouton reste un bouton ; aucun attribut arbitraire.
            writer.issue("unsupported_prop", location)
    if not valid:
        return None
    attributes: list[tuple[str, str]] = [("type", "button")]
    if classes is not None:
        attributes.append(("class", classes))
    attributes.append((attribute, writer.escaped(action.path, (*path, "binding"))))
    for key in _HTMX_PROPS:
        value = props.get(key)
        if isinstance(value, str):
            attributes.append((key, writer.escaped(value, (*path, "props", key))))
    return ButtonPlan(tuple(attributes))


def render_button(
    plan: ButtonPlan, depth: int, path: Location, writer: ButtonWriter
) -> None:
    """Une ligne, dans le budget commun du générateur."""
    attributes = "".join(f' {name}="{value}"' for name, value in plan.attributes)
    writer.line("<button" + attributes + ">" + BUTTON_LABEL + "</button>", depth, path)
