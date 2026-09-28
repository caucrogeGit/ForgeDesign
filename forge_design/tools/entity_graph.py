"""Projection pure des contrats d'entités en relations orientées."""

from dataclasses import dataclass
from typing import Literal

from forge_design.forge.entities import EntitiesResult, EntityInfo, RelationInfo


@dataclass(frozen=True)
class EntityGraphNode:
    id: str
    kind: Literal["entity", "pivot"]
    label: str
    table: str
    field_count: int


@dataclass(frozen=True)
class EntityGraphEdge:
    id: str
    source: str
    target: str
    kind: Literal["many_to_one", "many_to_many_from", "many_to_many_to"]
    label: str


@dataclass(frozen=True)
class EntityGraph:
    nodes: tuple[EntityGraphNode, ...] = ()
    edges: tuple[EntityGraphEdge, ...] = ()


def build_entity_graph(result: EntitiesResult) -> EntityGraph:
    """Conserve les occurrences ; un nom ambigu désigne sa première entité.

    Les identifiants sont des positions typées, indépendantes des textes projet.
    Les relations dont une extrémité manque restent dans les diagnostics initiaux.
    """
    return build_entity_graph_from_items(result.entities, result.relations)


def build_entity_graph_from_items(
    entities: tuple[EntityInfo, ...], relations: tuple[RelationInfo, ...]
) -> EntityGraph:
    """Même projection pour les tuples d'une vue filtrée, sans EntitiesResult fictif."""
    nodes: list[EntityGraphNode] = []
    edges: list[EntityGraphEdge] = []
    names: dict[str, str] = {}
    for index, entity in enumerate(entities):
        identity = f"entity:{index}"
        nodes.append(
            EntityGraphNode(
                identity, "entity", entity.name, entity.table, len(entity.fields)
            )
        )
        names.setdefault(entity.name, identity)
    for index, relation in enumerate(relations):
        source = names.get(relation.from_entity)
        target = names.get(relation.to_entity)
        if source is None or target is None:
            continue
        identity = f"relation:{index}"
        if relation.type == "many_to_one":
            edges.append(
                EntityGraphEdge(identity, source, target, "many_to_one", relation.name)
            )
        elif relation.many_to_many is not None:
            many = relation.many_to_many
            pivot = f"pivot:{index}"
            nodes.append(
                EntityGraphNode(
                    pivot,
                    "pivot",
                    many.pivot_table,
                    many.pivot_table,
                    len(many.pivot_fields),
                )
            )
            edges.extend(
                (
                    EntityGraphEdge(
                        identity + ":from",
                        source,
                        pivot,
                        "many_to_many_from",
                        relation.name,
                    ),
                    EntityGraphEdge(
                        identity + ":to", pivot, target, "many_to_many_to", ""
                    ),
                )
            )
    return EntityGraph(tuple(nodes), tuple(edges))
