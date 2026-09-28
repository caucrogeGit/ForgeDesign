"""Validation des paramètres GET disponibles dans la Request Forge."""

from typing import cast

from core.http.request import Request

from forge_design.tools.entity_filters import (
    EntityFilter,
    ItemType,
    RelationType,
    SeverityFilter,
)


def parse_entity_filter(request: Request) -> EntityFilter:
    for key, values in request.params.items():
        if key not in {"q", "type", "relation", "severity", "diagnostics"}:
            raise ValueError("Paramètre de filtre inconnu.")
        if len(values) != 1:
            raise ValueError("Une seule valeur est autorisée par filtre.")
    # Forge élimine les valeurs vides avant cette frontière. Une valeur vide
    # équivaut donc à une absence ; seules les répétitions conservées sont rejetées.
    diagnostics = request.query("diagnostics", "all")
    if diagnostics not in {"all", "only"}:
        raise ValueError("Filtre de diagnostics invalide.")
    return EntityFilter(
        query=request.query("q"),
        item_type=cast(ItemType, request.query("type", "all")),
        relation_type=cast(RelationType, request.query("relation", "all")),
        severity=cast(SeverityFilter, request.query("severity", "all")),
        diagnostics_only=diagnostics == "only",
    )
