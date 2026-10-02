"""Route de preview réelle d'un template, déduite de Route Explorer seul.

Aucune URL n'est inventée à partir d'un nom de vue ou d'un chemin de template.
Une route n'est retenue que si elle est GET, sans segment dynamique, publique,
unique, et si son handler vérifié rend littéralement le template attendu, déjà
présent sur disque. Toute incertitude donne « indisponible » avec une raison.

« Partiel pertinent » : Route Explorer avertit toujours qu'il lit statiquement
(opt-ins et déclarations non interprétées) ; ces avertissements généraux ne
bloquent pas. En revanche, une route GET dont le template n'est pas
déterminable (handler dynamique ou absent, méthode non vérifiée, rendu
dynamique ou multiple) pourrait rendre le même template : la sélection est
alors refusée plutôt que de choisir une route arbitraire.
"""

from dataclasses import dataclass

from forge_design.forge.routes import RouteInfo, RoutesResult

VIEWS_PREFIX = "mvc/views/"

REASON_NO_CONTRACT_TEMPLATE = "Template du contrat hors de mvc/views."
REASON_NONE = "Aucune route GET publique connue pour ce template."
REASON_UNCERTAIN = (
    "Une route GET a un template non déterminable : elle pourrait rendre ce "
    "template, aucune route n'est choisie."
)
REASON_DYNAMIC = "Route dynamique : aucune valeur fictive n'est utilisée."
REASON_MISSING = "Le template rendu par la route est absent du projet."
REASON_SEVERAL = "Plusieurs routes rendent ce template."
REASON_PROTECTED = "Route protégée par authentification."


@dataclass(frozen=True)
class RealPreviewRouteSelection:
    available: bool
    path: str | None
    reason: str | None


def _unavailable(reason: str) -> RealPreviewRouteSelection:
    return RealPreviewRouteSelection(False, None, reason)


def is_static_route_path(path: str) -> bool:
    """Chemin d'origine ASCII, sans paramètre {…}, requête, fragment ni blanc."""
    return (
        path.startswith("/")
        and not path.startswith("//")
        and path.isascii()
        and not any(c in path for c in "{}?#\\")
        and all(0x21 <= ord(c) < 0x7F for c in path)
    )


def _uncertain(route: RouteInfo) -> bool:
    handler = route.handler
    return (
        handler is None
        or route.handler_dynamic
        or handler.verification != "found"
        or handler.template.status in ("dynamic", "ambiguous")
    )


def select_real_preview_route(
    contract_template: str, routes: RoutesResult
) -> RealPreviewRouteSelection:
    """contract_template : ViewContract.template, sous la forme mvc/views/<chemin>."""
    if not contract_template.startswith(VIEWS_PREFIX):
        return _unavailable(REASON_NO_CONTRACT_TEMPLATE)
    expected = contract_template[len(VIEWS_PREFIX) :]
    gets = [route for route in routes.routes if route.method == "GET"]
    rendering = [
        route
        for route in gets
        if route.handler is not None
        and route.handler.verification == "found"
        and route.handler.template.status == "found"
        and route.handler.template.path == expected
    ]
    uncertain = any(_uncertain(route) for route in gets)
    if not rendering:
        return _unavailable(REASON_UNCERTAIN if uncertain else REASON_NONE)
    static = [route for route in rendering if is_static_route_path(route.path)]
    if not static:
        return _unavailable(REASON_DYNAMIC)
    paths = {route.path for route in static}
    if len(paths) > 1 or len(static) != len(rendering):
        return _unavailable(REASON_SEVERAL)
    if uncertain:
        return _unavailable(REASON_UNCERTAIN)
    route = static[0]
    assert route.handler is not None
    if route.handler.template.presence != "present":
        return _unavailable(REASON_MISSING)
    if any(not candidate.public for candidate in static):
        return _unavailable(REASON_PROTECTED)
    return RealPreviewRouteSelection(True, route.path, None)
