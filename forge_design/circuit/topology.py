"""Topologie électrique dérivée d'un CircuitDocument et du catalogue.

Transformation pure : seuls comptent les composants (types et bornes du
catalogue), les connexions, les jonctions et les références de masse. Positions,
rotations, routes, annotations, références visibles et ordre des collections
n'ont aucun effet. Union-find en O((V + E) α) ; aucun parcours quadratique.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from forge_design.circuit.catalog import CircuitCatalog
from forge_design.circuit.models import (
    CircuitDocument,
    JunctionEndpoint,
    TerminalEndpoint,
)
from forge_design.specialized import SpecializedIssue


@dataclass(frozen=True, order=True)
class TerminalRef:
    """Borne d'instance : (component_id, terminal_id), sans identité persistée."""

    component_id: str
    terminal_id: str


@dataclass(frozen=True, order=True)
class JunctionRef:
    junction_id: str


NetMember = TerminalRef | JunctionRef


@dataclass(frozen=True)
class ConnectionRef:
    """Connexion électrique valide (extrémités résolues, distinctes).

    Non orientée : a et b sont en ordre canonique, pas dans l'ordre du document.
    """

    id: str
    a: NetMember
    b: NetMember


@dataclass(frozen=True)
class CircuitNet:
    """Réseau dérivé ; key est calculée à partir des membres triés.

    reference : le réseau contient une borne de rôle « reference » (masse). Une
    référence ne génère ni tension ni énergie.
    """

    key: str
    terminals: tuple[TerminalRef, ...]
    junctions: tuple[JunctionRef, ...]
    reference: bool


@dataclass(frozen=True)
class CircuitTopology:
    terminals: tuple[TerminalRef, ...]
    junctions: tuple[JunctionRef, ...]
    connections: tuple[ConnectionRef, ...]
    nets: tuple[CircuitNet, ...]
    _net_by_member: Mapping[NetMember, CircuitNet] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        index = MappingProxyType(
            {
                member: net
                for net in self.nets
                for member in (*net.terminals, *net.junctions)
            }
        )
        object.__setattr__(self, "_net_by_member", index)

    def net_of(self, member: NetMember) -> CircuitNet | None:
        return self._net_by_member.get(member)


def _sort_key(member: NetMember) -> tuple[str, ...]:
    if isinstance(member, TerminalRef):
        return ("terminal", member.component_id, member.terminal_id)
    return ("junction", member.junction_id)


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[NetMember, NetMember] = {}

    def add(self, member: NetMember) -> None:
        self.parent.setdefault(member, member)

    def find(self, member: NetMember) -> NetMember:
        root = member
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[member] != root:
            self.parent[member], member = root, self.parent[member]
        return root

    def union(self, a: NetMember, b: NetMember) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            # Racine déterministe, indépendante de l'ordre des collections.
            low, high = sorted((ra, rb), key=_sort_key)
            self.parent[high] = low


@dataclass(frozen=True)
class TopologyAnalysis:
    """Topologie et diagnostics du niveau « topology » d'une même passe."""

    topology: CircuitTopology
    issues: tuple[SpecializedIssue, ...]
    connected: frozenset[TerminalRef]
    reference_roles: frozenset[TerminalRef]


def _topology_issue(
    code: str, severity: str, message: str, *location: str | int
) -> SpecializedIssue:
    return SpecializedIssue(
        f"circuit.{code}",
        severity,  # type: ignore[arg-type]
        message,
        "topology",
        location,
    )


def analyze_topology(
    document: CircuitDocument, catalog: CircuitCatalog
) -> TopologyAnalysis:
    """Ordre des diagnostics : connexions dans l'ordre du document (extrémité a,
    extrémité b, auto-connexion, doublon), puis jonctions dans l'ordre du document.

    Les extrémités vers un composant de type inconnu ne sont pas évaluées : la
    structure de domaine l'a déjà signalé et bloque l'écriture.
    """
    components = {component.id: component for component in document.components}
    junction_ids = {junction.id for junction in document.junctions}
    uf = _UnionFind()
    terminals: list[TerminalRef] = []
    references: set[TerminalRef] = set()
    for component in document.components:
        definition = catalog.get(component.type)
        if definition is None:
            continue
        for terminal in definition.terminals:
            ref = TerminalRef(component.id, terminal.id)
            terminals.append(ref)
            uf.add(ref)
            if terminal.role == "reference":
                references.add(ref)
    for junction_id in junction_ids:
        uf.add(JunctionRef(junction_id))

    issues: list[SpecializedIssue] = []

    def resolve(
        endpoint: TerminalEndpoint | JunctionEndpoint, index: int, side: str
    ) -> NetMember | None:
        if isinstance(endpoint, JunctionEndpoint):
            if endpoint.junction_id not in junction_ids:
                issues.append(
                    _topology_issue(
                        "junction-not-found",
                        "error",
                        f"Jonction {endpoint.junction_id} introuvable.",
                        "connections",
                        index,
                        side,
                        "junction_id",
                    )
                )
                return None
            return JunctionRef(endpoint.junction_id)
        component = components.get(endpoint.component_id)
        if component is None:
            issues.append(
                _topology_issue(
                    "component-not-found",
                    "error",
                    f"Composant {endpoint.component_id} introuvable.",
                    "connections",
                    index,
                    side,
                    "component_id",
                )
            )
            return None
        definition = catalog.get(component.type)
        if definition is None:
            return None
        if definition.terminal(endpoint.terminal_id) is None:
            issues.append(
                _topology_issue(
                    "terminal-not-found",
                    "error",
                    f"Borne « {endpoint.terminal_id} » absente du type "
                    f"{definition.id} ({component.id}).",
                    "connections",
                    index,
                    side,
                    "terminal_id",
                )
            )
            return None
        return TerminalRef(component.id, endpoint.terminal_id)

    valid: list[ConnectionRef] = []
    seen: dict[frozenset[NetMember], str] = {}
    degree: dict[JunctionRef, int] = {}
    for index, connection in enumerate(document.connections):
        a = resolve(connection.a, index, "a")
        b = resolve(connection.b, index, "b")
        if a is None or b is None:
            continue
        if a == b:
            issues.append(
                _topology_issue(
                    "self-connection",
                    "error",
                    f"La connexion {connection.id} relie une extrémité à elle-même.",
                    "connections",
                    index,
                )
            )
            continue
        pair = frozenset((a, b))
        if pair in seen:
            issues.append(
                _topology_issue(
                    "duplicate-connection",
                    "warning",
                    f"La connexion {connection.id} double {seen[pair]}.",
                    "connections",
                    index,
                )
            )
        else:
            seen[pair] = connection.id
        # Liaison non orientée : extrémités en ordre canonique.
        first, second = sorted((a, b), key=_sort_key)
        valid.append(ConnectionRef(connection.id, first, second))
        uf.union(a, b)
        for member in (a, b):
            if isinstance(member, JunctionRef):
                degree[member] = degree.get(member, 0) + 1

    for index, junction in enumerate(document.junctions):
        count = degree.get(JunctionRef(junction.id), 0)
        if count <= 1:
            issues.append(
                _topology_issue(
                    "junction-dangling",
                    "warning",
                    f"Jonction {junction.id} de degré {count}.",
                    "junctions",
                    index,
                )
            )

    # Toutes les masses forment une seule référence commune (sans source).
    ordered_references = sorted(references, key=_sort_key)
    for ref in ordered_references[1:]:
        uf.union(ordered_references[0], ref)

    groups: dict[NetMember, list[NetMember]] = {}
    for member in uf.parent:
        groups.setdefault(uf.find(member), []).append(member)
    nets = sorted(
        (_net(members, references) for members in groups.values()),
        key=lambda net: net.key,
    )
    connected = frozenset(
        member
        for connection in valid
        for member in (connection.a, connection.b)
        if isinstance(member, TerminalRef)
    )
    topology = CircuitTopology(
        tuple(sorted(terminals, key=_sort_key)),
        tuple(sorted((JunctionRef(j) for j in junction_ids), key=_sort_key)),
        tuple(sorted(valid, key=lambda connection: connection.id)),
        tuple(nets),
    )
    return TopologyAnalysis(topology, tuple(issues), connected, frozenset(references))


def _net(members: list[NetMember], references: set[TerminalRef]) -> CircuitNet:
    ordered = sorted(members, key=_sort_key)
    key = json.dumps([list(_sort_key(m)) for m in ordered], separators=(",", ":"))
    terminals = tuple(m for m in ordered if isinstance(m, TerminalRef))
    junctions = tuple(m for m in ordered if isinstance(m, JunctionRef))
    return CircuitNet(
        key, terminals, junctions, any(t in references for t in terminals)
    )


def build_circuit_topology(
    document: CircuitDocument, catalog: CircuitCatalog
) -> CircuitTopology:
    """Topologie seule ; les connexions invalides n'y participent pas."""
    return analyze_topology(document, catalog).topology
