"""Représentation pure des relations déjà décrites par Route Explorer."""

from dataclasses import dataclass, replace
from json import dumps
from typing import Literal

from forge_design.forge.routes import (
    RoutesResult,
    TemplateDependencyGraph,
    TemplatePresenceStatus,
)

GraphNodeKind = Literal["route", "handler", "controller", "template"]
GraphEdgeKind = Literal[
    "handles", "defined-in", "renders", "extends", "includes", "imports", "from-imports"
]


@dataclass(frozen=True)
class GraphNode:
    id: str
    kind: GraphNodeKind
    label: str
    presence: TemplatePresenceStatus = "not-applicable"


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    kind: GraphEdgeKind
    in_cycle: bool = False


@dataclass(frozen=True)
class RouteGraph:
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    transitive_truncated: bool = False


def build_route_graph(result: RoutesResult) -> RouteGraph:
    """Conserver l'ordre de découverte, sans accès au projet ni analyse.

    Les identités sont syntaxiques. À identité égale, les métadonnées de la
    première occurrence sont conservées, ainsi que toutes les relations distinctes.
    """
    nodes: dict[str, GraphNode] = {}
    edges: dict[GraphEdge, None] = {}
    closures: dict[str, TemplateDependencyGraph] = {}

    def node(
        kind: GraphNodeKind,
        label: str,
        *identity: str,
        presence: TemplatePresenceStatus = "not-applicable",
    ) -> str:
        key = dumps((kind, *identity), ensure_ascii=True, separators=(",", ":"))
        nodes.setdefault(key, GraphNode(key, kind, label, presence))
        return key

    def edge(source: str, target: str, kind: GraphEdgeKind) -> None:
        edges.setdefault(GraphEdge(source, target, kind), None)

    dependency_kinds: dict[str, GraphEdgeKind] = {
        "extends": "extends",
        "include": "includes",
        "import": "imports",
        "from-import": "from-imports",
    }
    for route in result.routes:
        route_id = node(
            "route", f"{route.method} {route.path}", route.method, route.path
        )
        handler = route.handler
        if handler is None:
            continue
        handler_id = node("handler", handler.reference, handler.reference)
        edge(route_id, handler_id, "handles")
        if handler.controller_file is not None:
            controller_id = node(
                "controller", handler.controller_file, handler.controller_file
            )
            edge(handler_id, controller_id, "defined-in")
        template = handler.template
        if template.status != "found" or template.path is None:
            continue
        template_id = node(
            "template", template.path, template.path, presence=template.presence
        )
        edge(handler_id, template_id, "renders")
        if template.dependency_graph is not None:
            closures.setdefault(
                template.dependency_graph.root, template.dependency_graph
            )
        for dependency in template.dependencies:
            if dependency.dynamic or dependency.path is None:
                continue
            dependency_id = node(
                "template",
                dependency.path,
                dependency.path,
                presence=dependency.presence,
            )
            edge(template_id, dependency_id, dependency_kinds[dependency.kind])
    # Conserver le préfixe direct, puis ajouter les fermetures dans l'ordre des racines.
    cyclic: set[tuple[str, str, GraphEdgeKind]] = set()
    for closure in closures.values():
        for source in closure.templates:
            source_id = node(
                "template", source.path, source.path, presence=source.presence
            )
            for dependency in source.dependencies:
                if dependency.dynamic or dependency.path is None:
                    continue
                target_id = node(
                    "template",
                    dependency.path,
                    dependency.path,
                    presence=dependency.presence,
                )
                edge(source_id, target_id, dependency_kinds[dependency.kind])
        for cycle in closure.cycles:
            for relation in cycle.edges:
                # Les diagnostics marquent uniquement les arêtes déjà représentées.
                cyclic.add(
                    (relation.source, relation.target, dependency_kinds[relation.kind])
                )
    marked = tuple(
        replace(relation, in_cycle=True)
        if (nodes[relation.source].label, nodes[relation.target].label, relation.kind)
        in cyclic
        and nodes[relation.source].kind == nodes[relation.target].kind == "template"
        else relation
        for relation in edges
    )
    return RouteGraph(
        tuple(nodes.values()),
        marked,
        any(closure.truncated for closure in closures.values()),
    )
