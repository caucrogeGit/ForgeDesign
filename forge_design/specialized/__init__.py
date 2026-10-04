"""Socle des ressources d'outils spécialisés (FD-SPECIALIZED-002).

Déclarations gelées du contrat FD-SPECIALIZED-001 et hôte de lecture/écriture
contrôlée, inventaire confiné (FD-MODULES-002). Aucun outil, registre, UI,
runtime ni export n'est fourni ici.
"""

# API publique des modules externes (FD-MODULES-003) : un codec spécialisé
# n'importe jamais forge_design.json_strict ni forge_design.limits directement.
from forge_design.json_strict import loads_strict_json
from forge_design.limits import MAX_SPECIALIZED_ISSUES, MAX_SPECIALIZED_LOCATION_DEPTH
from forge_design.specialized.listing import (
    SpecializedResourceListing,
    list_specialized_resources,
)
from forge_design.specialized.models import (
    PLATFORM_CAPABILITIES,
    ErrorCategory,
    OptionalDependency,
    PlatformCapability,
    SpecializedCapability,
    SpecializedIssue,
    SpecializedResourceType,
    SpecializedToolDefinition,
    SpecializedValidationResult,
    UiEntry,
)
from forge_design.specialized.resource import (
    InvalidSpecializedResourceError,
    SpecializedCapabilityError,
    SpecializedFormatError,
    SpecializedReadResult,
    SpecializedResourceCodec,
    SpecializedResourceConflictError,
    SpecializedResourceError,
    SpecializedResourceHistoryError,
    SpecializedResourceRef,
    SpecializedResourceRefusedError,
    SpecializedResourceRevision,
    SpecializedWriteResult,
    UnsupportedSpecializedVersionError,
    read_specialized_resource,
    write_specialized_resource,
)

__all__ = [
    "MAX_SPECIALIZED_ISSUES",
    "MAX_SPECIALIZED_LOCATION_DEPTH",
    "PLATFORM_CAPABILITIES",
    "ErrorCategory",
    "InvalidSpecializedResourceError",
    "OptionalDependency",
    "PlatformCapability",
    "SpecializedCapability",
    "SpecializedCapabilityError",
    "SpecializedFormatError",
    "SpecializedIssue",
    "SpecializedReadResult",
    "SpecializedResourceCodec",
    "SpecializedResourceConflictError",
    "SpecializedResourceError",
    "SpecializedResourceListing",
    "SpecializedResourceHistoryError",
    "SpecializedResourceRef",
    "SpecializedResourceRefusedError",
    "SpecializedResourceRevision",
    "SpecializedResourceType",
    "SpecializedToolDefinition",
    "SpecializedValidationResult",
    "SpecializedWriteResult",
    "UiEntry",
    "UnsupportedSpecializedVersionError",
    "list_specialized_resources",
    "loads_strict_json",
    "read_specialized_resource",
    "write_specialized_resource",
]
