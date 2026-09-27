"""Recherche et sélection pures sur un résultat et ses diagnostics associés."""

from dataclasses import dataclass
from typing import Literal

from forge_design.forge.routes import RouteInfo, RoutesResult
from forge_design.tools.route_diagnostics import RouteDiagnostics

Visibility = Literal["all", "public", "protected"]
SeverityFilter = Literal["all", "error", "warning", "info"]


@dataclass(frozen=True)
class RouteFilter:
    query: str | None = None
    method: str | None = None
    visibility: Visibility = "all"
    severity: SeverityFilter = "all"
    diagnostics_only: bool = False

    def __post_init__(self) -> None:
        if self.query is not None and len(self.query) > 256:
            raise ValueError("Recherche limitée à 256 caractères.")
        if self.visibility not in {"all", "public", "protected"}:
            raise ValueError("Visibilité invalide.")
        if self.severity not in {"all", "error", "warning", "info"}:
            raise ValueError("Sévérité invalide.")
        object.__setattr__(self, "query", (self.query or "").strip() or None)
        object.__setattr__(self, "method", self.method.upper() if self.method else None)


@dataclass(frozen=True)
class FilteredRouteExplorer:
    routes: tuple[RouteInfo, ...]
    diagnostics: RouteDiagnostics
    total_routes: int


def filter_route_explorer(
    result: RoutesResult, diagnostics: RouteDiagnostics, filters: RouteFilter
) -> FilteredRouteExplorer:
    """Les indices de diagnostic se rapportent au RoutesResult original, non filtré."""
    methods = {route.method for route in result.routes}
    if filters.method is not None and filters.method not in methods:
        raise ValueError("Méthode absente de l’inventaire des routes.")
    matching_diagnostics = tuple(
        item
        for item in diagnostics.items
        if filters.severity == "all" or item.severity == filters.severity
    )
    associated = {
        index for item in matching_diagnostics for index in item.route_indices
    }
    query = (filters.query or "").casefold()
    selected: set[int] = set()
    routes: list[RouteInfo] = []
    for index, route in enumerate(result.routes):
        if filters.method is not None and route.method != filters.method:
            continue
        if filters.visibility != "all" and route.public != (
            filters.visibility == "public"
        ):
            continue
        if filters.diagnostics_only and index not in associated:
            continue
        handler = route.handler
        fields = (route.method, route.path, route.name or "")
        if handler is not None:
            fields += (
                handler.reference,
                handler.controller_file or handler.missing_controller or "",
                handler.template.path or "",
            )
        if query and not any(query in field.casefold() for field in fields):
            continue
        selected.add(index)
        routes.append(route)
    visible_diagnostics = RouteDiagnostics(
        tuple(
            item
            for item in matching_diagnostics
            if not item.route_indices
            or any(index in selected for index in item.route_indices)
        )
    )
    return FilteredRouteExplorer(tuple(routes), visible_diagnostics, len(result.routes))
