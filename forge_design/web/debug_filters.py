"""Parsing des filtres GET avant toute lecture du journal."""

from core.http.request import Request

from forge_design.tools.debug_filters import DebugFilter


def parse_debug_filters(request: Request) -> DebugFilter:
    for key, values in request.params.items():
        if key not in {"q", "level", "category", "order"}:
            raise ValueError("Paramètre de filtre inconnu.")
        if len(values) != 1:
            raise ValueError("Une seule valeur est autorisée par filtre.")
    # Request élimine les valeurs vides : elles équivalent à une absence.
    return DebugFilter(
        query=request.query("q"),
        level=request.query("level", "all"),
        category=request.query("category", "all"),
        order=request.query("order", "newest"),
    )
