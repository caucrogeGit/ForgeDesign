"""Déclarations spécialisées de Circuit V0.1 : descriptives, jamais enregistrées.

Seules les capacités réellement disponibles sont déclarées (pas d'edit tant
qu'aucun éditeur n'existe). Les trois niveaux de validation sont implémentés
(FD-CIRCUIT-003) ; structure et topology bloquent l'écriture.
"""

from forge_design.circuit.limits import MAX_CIRCUIT_RESOURCE_BYTES
from forge_design.circuit.models import FORMAT_VERSION
from forge_design.circuit.validation import CIRCUIT_VALIDATION_LEVELS
from forge_design.specialized import (
    SpecializedCapability,
    SpecializedResourceType,
    SpecializedToolDefinition,
)

CIRCUIT_SOURCE_PREFIX = "mvc/circuit"
CIRCUIT_SUFFIX = ".circuit.json"

_CAPABILITIES = tuple(
    SpecializedCapability.platform(name)
    for name in ("create", "open", "validate", "save")
)

CIRCUIT_RESOURCE_TYPE = SpecializedResourceType(
    id="schematic",
    format_id="circuit-json",
    suffix=CIRCUIT_SUFFIX,
    source_prefix=CIRCUIT_SOURCE_PREFIX,
    read_versions=frozenset({FORMAT_VERSION}),
    write_version=FORMAT_VERSION,
    editable=True,
    max_size=MAX_CIRCUIT_RESOURCE_BYTES,
    capabilities=_CAPABILITIES,
    validation_levels=CIRCUIT_VALIDATION_LEVELS,
    # La préparation électrique n'émet que des avertissements et ne bloque pas.
    blocking_validation_levels=frozenset({"structure", "topology"}),
    persistent_state=("page", "components", "connections", "junctions", "annotations"),
    runtime_only_state=("selection", "viewport", "history", "dirty", "simulation"),
)

CIRCUIT_TOOL = SpecializedToolDefinition(
    id="circuit",
    name="Circuit",
    description="Schémas électriques exacts, versionnés dans les sources du projet.",
    resource_types=(CIRCUIT_RESOURCE_TYPE,),
    capabilities=_CAPABILITIES,
    optional_dependencies=(),
    ui_entry=None,
)
