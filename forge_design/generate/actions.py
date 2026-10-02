"""Interaction contrôlée commune aux boutons et formulaires générés.

Une action du contrat (ViewAction) donne une URL et un verbe HTMX ; quelques
props HTMX déclaratives sont émises, valeurs opaques échappées. Aucun script,
CDN, jeton CSRF ni runtime HTMX ; aucune route déduite ou vérifiée.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Never, Protocol

from forge_design.contracts.models import ViewAction
from forge_design.design.models import DesignNode, PageRoot

Location = tuple[str | int, ...]
# Valeur None : attribut booléen (required), émis sans valeur.
Attribute = tuple[str, str | None]

# Méthode du contrat → attribut HTMX ; les autres verbes sont reportés.
METHOD_ATTRIBUTES: Mapping[str, str] = {"GET": "hx-get", "POST": "hx-post"}
# Ordre d'émission fixe, indépendant de l'ordre des props du Design.
HTMX_PROPS = ("hx-target", "hx-swap", "hx-confirm")


class InteractionWriter(Protocol):
    def issue(self, code: str, location: Location) -> None: ...
    def stop(self, code: str, location: Location) -> Never: ...
    def line(self, content: str, depth: int, path: Location) -> None: ...
    def escaped(self, value: str, path: Location) -> str: ...


@dataclass(frozen=True)
class Interaction:
    """Action validée et props déjà échappées, prêtes à émettre."""

    method: str
    htmx_attribute: str
    path: str
    classes: str | None
    htmx: tuple[tuple[str, str], ...]


def prepare_interaction(
    node: DesignNode | PageRoot,
    path: Location,
    actions: Mapping[str, ViewAction],
    writer: InteractionWriter,
    *,
    missing_code: str,
) -> Interaction | None:
    """Tout vérifier avant émission ; None (bloc omis) après diagnostic.

    Les bindings ont déjà été validés : une action inconnue a arrêté la
    génération en amont (generate.invalid_binding).
    """
    if node.binding is None:
        writer.issue(missing_code, (*path, "binding"))
        return None
    action = actions[node.binding]
    attribute = METHOD_ATTRIBUTES.get(action.method)
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
        elif key in HTMX_PROPS:
            if not isinstance(value, str) or not value:
                writer.issue("invalid_htmx_prop", location)
                valid = False
        else:
            # tag compris ; aucune prop ne devient un attribut arbitraire.
            writer.issue("unsupported_prop", location)
    if not valid:
        return None
    htmx = tuple(
        (key, writer.escaped(value, (*path, "props", key)))
        for key in HTMX_PROPS
        if isinstance(value := props.get(key), str)
    )
    return Interaction(
        action.method,
        attribute,
        writer.escaped(action.path, (*path, "binding")),
        classes,
        htmx,
    )


def render_attributes(attributes: tuple[Attribute, ...]) -> str:
    """Valeurs déjà échappées ; None donne un attribut booléen."""
    return "".join(
        f" {name}" if value is None else f' {name}="{value}"'
        for name, value in attributes
    )
