"""Ressource Circuit V0.1 : format, identités, codec et déclarations spécialisées.

Aucun catalogue, topologie, géométrie, routage, rendu, éditeur ni simulation.
"""

from forge_design.circuit.codec import CircuitCodec
from forge_design.circuit.contract import CIRCUIT_RESOURCE_TYPE, CIRCUIT_TOOL
from forge_design.circuit.ids import (
    new_annotation_id,
    new_component_id,
    new_connection_id,
    new_junction_id,
)
from forge_design.circuit.models import (
    CircuitComponent,
    CircuitConnection,
    CircuitDocument,
    CircuitJunction,
    CircuitPage,
    CircuitPoint,
    CircuitRoute,
    CircuitTextAnnotation,
    JunctionEndpoint,
    TerminalEndpoint,
    new_circuit_document,
)

__all__ = [
    "CIRCUIT_RESOURCE_TYPE",
    "CIRCUIT_TOOL",
    "CircuitCodec",
    "CircuitComponent",
    "CircuitConnection",
    "CircuitDocument",
    "CircuitJunction",
    "CircuitPage",
    "CircuitPoint",
    "CircuitRoute",
    "CircuitTextAnnotation",
    "JunctionEndpoint",
    "TerminalEndpoint",
    "new_annotation_id",
    "new_circuit_document",
    "new_component_id",
    "new_connection_id",
    "new_junction_id",
]
