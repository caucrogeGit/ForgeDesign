"""Diagnostics purs sur la fermeture connue, sans découverte de templates."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from forge_design.forge.routes import (
        TemplateDependencyGraph,
        TemplateDependencyKind,
    )


@dataclass(frozen=True)
class TemplateCycleEdge:
    source: str
    target: str
    kind: TemplateDependencyKind
    line: int


@dataclass(frozen=True)
class TemplateCycle:
    edges: tuple[TemplateCycleEdge, ...]

    @property
    def paths(self) -> tuple[str, ...]:
        """Chemin fermé explicitement, y compris pour un auto-cycle."""
        if not self.edges:
            return ()
        return tuple(edge.source for edge in self.edges) + (self.edges[-1].target,)

    @property
    def key(self) -> tuple[tuple[str, str, str], ...]:
        """Identité orientée, indépendante des lignes de déclarations dupliquées."""
        return tuple((edge.source, edge.target, edge.kind) for edge in self.edges)


def detect_template_cycles(graph: TemplateDependencyGraph) -> tuple[TemplateCycle, ...]:
    """Cycles témoins des arêtes de retour DFS, sans énumération exhaustive.

    Ordre des nœuds/déclarations conservé. Rotation vers la source minimale,
    sans inversion. Les déclarations identiques gardent leur première ligne.
    """
    known = {node.path for node in graph.templates}
    adjacency: dict[str, list[TemplateCycleEdge]] = {}
    for node in graph.templates:
        edges: dict[tuple[str, str], TemplateCycleEdge] = {}
        for dependency in node.dependencies:
            if dependency.dynamic or dependency.path not in known:
                continue
            assert dependency.path is not None
            edges.setdefault(
                (dependency.path, dependency.kind),
                TemplateCycleEdge(
                    node.path, dependency.path, dependency.kind, dependency.line
                ),
            )
        adjacency[node.path] = list(edges.values())
    visited: set[str] = set()
    active: dict[str, int] = {}
    tree_edges: list[TemplateCycleEdge] = []
    cycles: dict[tuple[tuple[str, str, str], ...], TemplateCycle] = {}
    for start in adjacency:
        if start in visited:
            continue
        active[start] = 0
        stack: list[tuple[str, Iterator[TemplateCycleEdge]]] = [
            (start, iter(adjacency[start]))
        ]
        while stack:
            current, outgoing = stack[-1]
            edge = next(outgoing, None)
            if edge is None:
                stack.pop()
                del active[current]
                visited.add(current)
                if tree_edges:
                    tree_edges.pop()
                continue
            if edge.target in active:
                ring = tree_edges[active[edge.target] :] + [edge]
                first = min(range(len(ring)), key=lambda index: ring[index].source)
                cycle = TemplateCycle(tuple(ring[first:] + ring[:first]))
                cycles.setdefault(cycle.key, cycle)
            elif edge.target not in visited:
                active[edge.target] = len(stack)
                tree_edges.append(edge)
                stack.append((edge.target, iter(adjacency[edge.target])))
    return tuple(cycles.values())
