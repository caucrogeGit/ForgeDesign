"""Route de preview réelle, déduite de Route Explorer seul.

Aucune URL n'est inventée à partir d'un nom de vue ou d'un chemin de template.
Une route n'est retenue que si elle est GET, sans segment dynamique, publique,
unique, et si son handler vérifié rend littéralement le template attendu, déjà
présent sur disque. Toute incertitude donne « indisponible » avec une raison.

Deux questions, deux entrées :

- select_real_preview_route (éditeur, FD-REALPREVIEW-004) part d'un template :
  quelle route unique le rend ? « Partiel pertinent » : Route Explorer avertit
  toujours qu'il lit statiquement (opt-ins et déclarations non interprétées) ;
  ces avertissements généraux ne bloquent pas. En revanche, une route GET dont
  le template n'est pas déterminable (handler dynamique ou absent, méthode non
  vérifiée, rendu dynamique ou multiple) pourrait rendre le même template : la
  sélection est alors refusée plutôt que de choisir une route arbitraire ;
- route_preview_selection et select_route_for_preview (Route Explorer,
  FD-REALPREVIEW-008) partent d'une route désignée : son URL est fixée, les
  garanties portent sur elle seule (route_preview_refusal) et son identité GET
  <chemin> doit être unique dans l'inventaire. La désambiguïsation template →
  route ne s'applique pas : aucune route n'est choisie à la place d'une autre.
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
# Route désignée (FD-REALPREVIEW-008).
REASON_HANDLER = (
    "Handler non analysé (fonction, référence non résolue ou dynamique) : "
    "le template rendu n'est pas démontré."
)
REASON_UNVERIFIED = (
    "Méthode du contrôleur non vérifiée : le template rendu n'est pas démontré."
)
REASON_TEMPLATE_DYNAMIC = (
    "Template dynamique : le rendu n'est pas déterminable statiquement."
)
REASON_TEMPLATE_AMBIGUOUS = "Plusieurs templates possibles : rendu ambigu."
REASON_TEMPLATE_NONE = "Aucun template rendu détecté pour cette route."
REASON_UNCHECKED = "Présence du template non vérifiée (analyse partielle)."
REASON_UNKNOWN_ROUTE = "Route GET absente de l'inventaire du projet."
REASON_DUPLICATE = "Route GET déclarée plusieurs fois : identité ambiguë."


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


def method_refusal(method: str) -> str:
    return f"Méthode {method} : seule une route GET est prévisualisable."


def route_preview_refusal(route: RouteInfo) -> str | None:
    """Garanties portant sur la route seule ; None si elles sont toutes réunies.

    Ce sont celles que select_real_preview_route exige de la route qu'elle
    retient : GET, chemin statique, handler vérifié et non dynamique, template
    exact (« found ») et présent, route publique.
    """
    if route.method != "GET":
        return method_refusal(route.method)
    if not is_static_route_path(route.path):
        return REASON_DYNAMIC
    handler = route.handler
    if handler is None or route.handler_dynamic:
        return REASON_HANDLER
    if handler.verification != "found":
        return REASON_UNVERIFIED
    template = handler.template
    if template.status == "dynamic":
        return REASON_TEMPLATE_DYNAMIC
    if template.status == "ambiguous":
        return REASON_TEMPLATE_AMBIGUOUS
    if template.status != "found" or template.path is None:
        return REASON_TEMPLATE_NONE
    if template.presence == "not-applicable":
        return REASON_UNCHECKED
    if template.presence != "present":
        return REASON_MISSING
    if not route.public:
        return REASON_PROTECTED
    return None


def _identity(route: RouteInfo) -> tuple[object, ...]:
    """Ce qui décide de la réponse servie : visibilité, handler, template."""
    handler = route.handler
    return (
        route.public,
        route.handler_dynamic,
        None if handler is None else handler.reference,
        None if handler is None else handler.verification,
        None if handler is None else handler.template.status,
        None if handler is None else handler.template.path,
    )


def route_preview_selection(
    route: RouteInfo, routes: RoutesResult
) -> RealPreviewRouteSelection:
    """Route de l'inventaire désignée telle quelle (Route Explorer).

    Plusieurs déclarations GET <chemin> identiques (même visibilité, handler et
    template) désignent la même route, comme pour l'éditeur ; si elles
    diffèrent, l'identité est ambiguë et la route est refusée.
    """
    if route.method == "GET":
        declarations = {
            _identity(item)
            for item in routes.routes
            if item.method == "GET" and item.path == route.path
        }
        if len(declarations) > 1:
            return _unavailable(REASON_DUPLICATE)
    reason = route_preview_refusal(route)
    if reason is not None:
        return _unavailable(reason)
    return RealPreviewRouteSelection(True, route.path, None)


def select_route_for_preview(
    path: str, routes: RoutesResult
) -> RealPreviewRouteSelection:
    """Chemin reçu d'un formulaire : retrouvé dans l'inventaire, puis revalidé.

    Seule l'égalité exacte avec une route GET inventoriée compte : aucun chemin
    n'est normalisé, complété ni deviné.
    """
    matches = [
        route for route in routes.routes if route.method == "GET" and route.path == path
    ]
    if not matches:
        return _unavailable(REASON_UNKNOWN_ROUTE)
    return route_preview_selection(matches[0], routes)
