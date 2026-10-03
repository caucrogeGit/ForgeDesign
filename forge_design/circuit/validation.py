"""Validation Circuit V1 : structure de domaine, topologie, préparation électrique.

Ordre déterministe des diagnostics : niveau « structure » (domaine), puis
« topology », puis « electrical-readiness » ; dans chaque niveau, ordre du
document puis ordre des règles. Bornage et troncature : SpecializedValidationResult.
La préparation électrique n'émet que des avertissements : elle ne bloque jamais
l'écriture. Validité ≠ simulabilité.
"""

from collections.abc import Iterator
from itertools import chain

from forge_design.circuit.catalog import CIRCUIT_CATALOG, CircuitCatalog
from forge_design.circuit.domain import domain_structure_issues
from forge_design.circuit.models import CircuitDocument
from forge_design.circuit.topology import (
    TerminalRef,
    TopologyAnalysis,
    analyze_topology,
)
from forge_design.specialized import SpecializedIssue, SpecializedValidationResult

STRUCTURE = "structure"
TOPOLOGY = "topology"
ELECTRICAL_READINESS = "electrical-readiness"
CIRCUIT_VALIDATION_LEVELS = (STRUCTURE, TOPOLOGY, ELECTRICAL_READINESS)


def _readiness(code: str, message: str, *location: str | int) -> SpecializedIssue:
    return SpecializedIssue(
        f"circuit.{code}", "warning", message, ELECTRICAL_READINESS, location
    )


def _readiness_issues(
    document: CircuitDocument, catalog: CircuitCatalog, analysis: TopologyAnalysis
) -> Iterator[SpecializedIssue]:
    """Par composant : propriétés requises absentes, bornes non connectées, source
    court-circuitée ; puis absence de masse."""
    for index, component in enumerate(document.components):
        definition = catalog.get(component.type)
        if definition is None:
            continue
        for prop in definition.properties:
            if prop.required_for_readiness and prop.name not in component.properties:
                yield _readiness(
                    "missing-property",
                    f"« {prop.name} » non renseignée pour {component.id} : "
                    "nécessaire à une analyse électrique.",
                    "components",
                    index,
                    "properties",
                    prop.name,
                )
        for terminal in definition.terminals:
            if TerminalRef(component.id, terminal.id) not in analysis.connected:
                yield _readiness(
                    "unconnected-terminal",
                    f"Borne « {terminal.id} » de {component.id} non connectée.",
                    "components",
                    index,
                )
        roles = {terminal.role: terminal.id for terminal in definition.terminals}
        if "source-positive" in roles and "source-negative" in roles:
            positive = analysis.topology.net_of(
                TerminalRef(component.id, roles["source-positive"])
            )
            negative = analysis.topology.net_of(
                TerminalRef(component.id, roles["source-negative"])
            )
            if positive is not None and positive == negative:
                yield _readiness(
                    "source-shorted",
                    f"Les deux pôles de {component.id} sont dans le même réseau.",
                    "components",
                    index,
                )
    if document.components and not analysis.reference_roles:
        yield _readiness(
            "missing-ground",
            "Aucune masse : le schéma n'a pas de référence de réseau.",
        )


def circuit_issues(
    document: CircuitDocument, catalog: CircuitCatalog = CIRCUIT_CATALOG
) -> Iterator[SpecializedIssue]:
    analysis = analyze_topology(document, catalog)
    return chain(
        domain_structure_issues(document, catalog),
        analysis.issues,
        _readiness_issues(document, catalog, analysis),
    )


def validate_circuit(
    document: CircuitDocument, catalog: CircuitCatalog = CIRCUIT_CATALOG
) -> SpecializedValidationResult:
    """Validation pure d'un document au format valide ; ne le modifie jamais."""
    return SpecializedValidationResult.bounded(circuit_issues(document, catalog))
