"""Routage orthogonal par couloirs horizontaux partagés, géométrie seule.

Primitive commune aux layouts serveur (Route Explorer, Entity Explorer) : elle
ne connaît ni graphe métier, ni HTTP, ni Jinja. Une connexion monte de sa
source vers un couloir horizontal situé au-dessus des nœuds, le parcourt, puis
descend vers sa cible. Plusieurs connexions partagent un couloir lorsque leurs
parcours horizontaux sont disjoints d'au moins ``gap`` unités.

Ce n'est pas le routeur orthogonal interactif complet : pas d'obstacles, de
ports, de grille, d'A* ni de réparation après déplacement.
"""

import heapq
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

Point = tuple[int, int]

DEFAULT_LANE_SPACING = 24
DEFAULT_LANE_ORIGIN = 30
DEFAULT_LANE_GAP = 20
DEFAULT_STUB = 20
LABEL_OFFSET = 5


@dataclass(frozen=True)
class HorizontalSpan:
    """Parcours horizontal demandé par une connexion (identité opaque)."""

    edge_id: str
    start: int
    end: int

    @property
    def left(self) -> int:
        return min(self.start, self.end)

    @property
    def right(self) -> int:
        return max(self.start, self.end)


@dataclass(frozen=True)
class LanePlan:
    """Couloir attribué à chaque connexion et ordonnée de chaque couloir.

    Les couloirs s'empilent de bas en haut : le couloir 0, qui reçoit les
    parcours commençant le plus à gauche, est le plus proche des nœuds. Sur les
    graphes mesurés (FD-GRAPHICS-005), cet ordre réduit les croisements ; ce
    n'est pas une garantie de planarité.
    """

    indices: Mapping[str, int]
    count: int
    spacing: int
    origin: int

    def y(self, edge_id: str) -> int:
        return self.origin + (self.count - 1 - self.indices[edge_id]) * self.spacing

    @property
    def band_bottom(self) -> int:
        """Ordonnée sous le dernier couloir : les nœuds se placent en dessous."""
        return self.origin + self.count * self.spacing


def allocate_horizontal_lanes(
    spans: Sequence[HorizontalSpan],
    *,
    spacing: int = DEFAULT_LANE_SPACING,
    origin: int = DEFAULT_LANE_ORIGIN,
    gap: int = DEFAULT_LANE_GAP,
) -> LanePlan:
    """Partition d'intervalles déterministe, O(E log E), nombre de couloirs minimal.

    Tri stable par (gauche, droite, ordre d'entrée) ; chaque parcours reçoit le
    plus petit couloir libre, libéré lorsque le parcours précédent s'achève au
    moins ``gap`` unités avant. Deux parcours qui se touchent ou se chevauchent
    (dont deux connexions parallèles) n'ont jamais le même couloir. Le nombre de
    couloirs est le chevauchement maximal, borne inférieure atteinte.
    """
    if spacing <= 0 or gap <= 0:
        raise ValueError("spacing et gap doivent être strictement positifs.")
    identities = [span.edge_id for span in spans]
    if len(set(identities)) != len(identities):
        raise ValueError("Identité de connexion dupliquée.")
    ordered = sorted(
        range(len(spans)), key=lambda i: (spans[i].left, spans[i].right, i)
    )
    busy: list[tuple[int, int]] = []  # (abscisse de libération, couloir)
    free: list[int] = []
    indices: dict[str, int] = {}
    count = 0
    for position in ordered:
        span = spans[position]
        while busy and busy[0][0] <= span.left:
            heapq.heappush(free, heapq.heappop(busy)[1])
        if free:
            lane = heapq.heappop(free)
        else:
            lane = count
            count += 1
        indices[span.edge_id] = lane
        heapq.heappush(busy, (span.right + gap, lane))
    return LanePlan(MappingProxyType(indices), count, spacing, origin)


def route_via_horizontal_lane(
    source: Point, target: Point, lane_y: int, *, stub: int = DEFAULT_STUB
) -> tuple[Point, ...]:
    """Polyligne orthogonale : sortie à droite, couloir, entrée à gauche."""
    (sx, sy), (tx, ty) = source, target
    return (
        (sx, sy),
        (sx + stub, sy),
        (sx + stub, lane_y),
        (tx - stub, lane_y),
        (tx - stub, ty),
        (tx, ty),
    )


def lane_label_position(points: Sequence[Point]) -> Point:
    """Milieu du segment de couloir, juste au-dessus de lui."""
    (x1, y), (x2, _) = points[2], points[3]
    return (x1 + x2) // 2, y - LABEL_OFFSET


def svg_path(points: Sequence[Point]) -> str:
    """Forme SVG H/V d'une polyligne orthogonale (repli serveur)."""
    (x, y) = points[0]
    parts = [f"M {x} {y}"]
    for (_, previous_y), (next_x, next_y) in zip(points, points[1:], strict=False):
        parts.append(f"H {next_x}" if previous_y == next_y else f"V {next_y}")
    return " ".join(parts)
