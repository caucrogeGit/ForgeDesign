"""Sélection pure des données affichées, sans modifier les faits du Bridge."""

from dataclasses import dataclass
from typing import Literal

from forge_design.forge.entities import (
    EntitiesResult,
    EntityFieldInfo,
    EntityInfo,
    RelationInfo,
)
from forge_design.limits import MAX_FILTER_QUERY_LENGTH
from forge_design.tools.entity_diagnostics import EntityDiagnostics

ItemType = Literal["all", "entity", "relation"]
RelationType = Literal["all", "many_to_one", "many_to_many"]
SeverityFilter = Literal["all", "error", "warning", "info"]


@dataclass(frozen=True)
class EntityFilter:
    query: str | None = None
    item_type: ItemType = "all"
    relation_type: RelationType = "all"
    severity: SeverityFilter = "all"
    diagnostics_only: bool = False

    def __post_init__(self) -> None:
        if self.query is not None and len(self.query) > MAX_FILTER_QUERY_LENGTH:
            raise ValueError(
                f"Recherche limitée à {MAX_FILTER_QUERY_LENGTH} caractères."
            )
        if self.item_type not in {"all", "entity", "relation"}:
            raise ValueError("Type d’élément invalide.")
        if self.relation_type not in {"all", "many_to_one", "many_to_many"}:
            raise ValueError("Type de relation invalide.")
        if self.severity not in {"all", "error", "warning", "info"}:
            raise ValueError("Sévérité invalide.")
        object.__setattr__(self, "query", (self.query or "").strip().casefold() or None)


@dataclass(frozen=True)
class EntityFilteredView:
    entities: tuple[EntityInfo, ...]
    relations: tuple[RelationInfo, ...]
    diagnostics: EntityDiagnostics
    graph_entities: tuple[EntityInfo, ...]
    total_entities: int
    total_relations: int


def _field_text(field: EntityFieldInfo) -> tuple[str, ...]:
    return field.name, field.type, field.references or ""


def _relation_text(relation: RelationInfo) -> tuple[str, ...]:
    values = (
        relation.from_entity,
        relation.to_entity,
        relation.name,
        relation.inverse_name or "",
    )
    if relation.many_to_one is not None:
        values += (relation.many_to_one.foreign_key,)
    if relation.many_to_many is not None:
        many = relation.many_to_many
        values += (many.pivot_table, many.from_key, many.to_key)
        values += tuple(
            text for field in many.pivot_fields for text in _field_text(field)
        )
    return values


def filter_entities(
    result: EntitiesResult, diagnostics: EntityDiagnostics, filters: EntityFilter
) -> EntityFilteredView:
    """Garde l'ordre et les occurrences ; diagnostics filtrés par sévérité seule."""
    visible_diagnostics = EntityDiagnostics(
        tuple(
            item
            for item in diagnostics.items
            if filters.severity == "all" or item.severity == filters.severity
        )
    )
    paths = {
        item.source.path
        for item in visible_diagnostics.items
        if item.source is not None
    }
    indices = {
        item.relation_index
        for item in visible_diagnostics.items
        if item.relation_index is not None
    }
    query = filters.query or ""
    selected = {
        index
        for index, entity in enumerate(result.entities)
        if filters.item_type != "relation"
        and (not filters.diagnostics_only or entity.source.path in paths)
        and any(
            query in text.casefold()
            for text in (
                entity.name,
                entity.table,
                *(text for field in entity.fields for text in _field_text(field)),
            )
        )
    }
    relations = tuple(
        relation
        for relation in result.relations
        if filters.item_type != "entity"
        and (filters.relation_type == "all" or relation.type == filters.relation_type)
        and (not filters.diagnostics_only or relation.source_index in indices)
        and any(query in text.casefold() for text in _relation_text(relation))
    )
    # Même convention que le graphe : la première occurrence d'un nom est
    # l'extrémité officielle. Ne pas ajouter tous les homonymes comme supports.
    names: dict[str, int] = {}
    for index, entity in enumerate(result.entities):
        names.setdefault(entity.name, index)
    graph_indices = set(selected)
    for relation in relations:
        for name in (relation.from_entity, relation.to_entity):
            if name in names:
                graph_indices.add(names[name])
    return EntityFilteredView(
        tuple(entity for i, entity in enumerate(result.entities) if i in selected),
        relations,
        visible_diagnostics,
        tuple(entity for i, entity in enumerate(result.entities) if i in graph_indices),
        len(result.entities),
        len(result.relations),
    )
