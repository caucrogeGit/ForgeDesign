"""Circuit : ressource V0.1, catalogue et domaine V1, topologie et validation.

Aucune géométrie, routage, rendu, éditeur ni simulation.
"""

from forge_design.circuit.catalog import (
    CIRCUIT_CATALOG,
    CircuitCatalog,
    CircuitComponentDefinition,
    CircuitPropertyDefinition,
    CircuitTerminalDefinition,
)
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
from forge_design.circuit.topology import (
    CircuitNet,
    CircuitTopology,
    ConnectionRef,
    JunctionRef,
    TerminalRef,
    build_circuit_topology,
)
from forge_design.circuit.validation import validate_circuit

__all__ = [
    "CIRCUIT_CATALOG",
    "CIRCUIT_RESOURCE_TYPE",
    "CIRCUIT_TOOL",
    "CircuitCatalog",
    "CircuitCodec",
    "CircuitComponentDefinition",
    "CircuitNet",
    "CircuitPropertyDefinition",
    "CircuitTerminalDefinition",
    "CircuitTopology",
    "ConnectionRef",
    "JunctionRef",
    "TerminalRef",
    "build_circuit_topology",
    "validate_circuit",
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
