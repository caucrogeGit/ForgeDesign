"""Adaptation des paramètres GET aux critères indépendants du protocole."""

from typing import cast

from core.http.request import Request

from forge_design.tools.route_filters import RouteFilter, SeverityFilter, Visibility


def parse_route_filter(request: Request) -> RouteFilter:
    diagnostics = request.query("diagnostics", "all")
    if diagnostics not in {"all", "only"}:
        raise ValueError("Filtre de diagnostics invalide.")
    # Les valeurs littérales sont validées par le modèle, avant utilisation.
    return RouteFilter(
        query=request.query("q"),
        method=request.query("method"),
        visibility=cast(Visibility, request.query("visibility", "all")),
        severity=cast(SeverityFilter, request.query("severity", "all")),
        diagnostics_only=diagnostics == "only",
    )
