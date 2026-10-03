"""Structure de domaine : types connus et propriétés autorisées par le catalogue.

Complète la validation du format (Pydantic) sans la modifier : un document
décodable peut être structurellement invalide pour le domaine. Fonction pure,
aucune mutation du document.
"""

from collections.abc import Iterator

from forge_design.circuit.catalog import CircuitCatalog
from forge_design.circuit.models import CircuitDocument
from forge_design.specialized import SpecializedIssue


def _structure(code: str, message: str, *location: str | int) -> SpecializedIssue:
    return SpecializedIssue(f"circuit.{code}", "error", message, "structure", location)


def domain_structure_issues(
    document: CircuitDocument, catalog: CircuitCatalog
) -> Iterator[SpecializedIssue]:
    """Ordre : composants dans l'ordre du document, puis propriétés du document."""
    for index, component in enumerate(document.components):
        definition = catalog.get(component.type)
        if definition is None:
            yield _structure(
                "unknown-component-type",
                f"Type inconnu « {component.type} » pour {component.id}.",
                "components",
                index,
                "type",
            )
            continue
        for name, value in component.properties.items():
            location = ("components", index, "properties", name)
            allowed = definition.property_definition(name)
            if allowed is None:
                yield _structure(
                    "unknown-property",
                    f"Propriété « {name} » non autorisée pour {definition.id} "
                    f"({component.id}).",
                    *location,
                )
            elif not allowed.accepts(value):
                yield _structure(
                    "invalid-property",
                    f"Valeur invalide pour « {name} » de {component.id} : "
                    f"{allowed.value_type} attendu"
                    + _bounds(allowed.minimum, allowed.maximum)
                    + ".",
                    *location,
                )


def _bounds(minimum: float | None, maximum: float | None) -> str:
    if minimum is None and maximum is None:
        return ""
    low = "-∞" if minimum is None else f"{minimum:g}"
    high = "+∞" if maximum is None else f"{maximum:g}"
    return f" dans [{low}, {high}]"
