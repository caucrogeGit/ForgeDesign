"""Sélection de la route de preview réelle (FD-REALPREVIEW-004 et -008), sans I/O."""

from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from forge_design.forge.routes import (
    HandlerInfo,
    RouteInfo,
    RoutesResult,
    TemplateResolution,
)
from forge_design.real_preview.route_selection import (
    REASON_DUPLICATE,
    REASON_DYNAMIC,
    REASON_HANDLER,
    REASON_MISSING,
    REASON_NO_CONTRACT_TEMPLATE,
    REASON_NONE,
    REASON_PROTECTED,
    REASON_SEVERAL,
    REASON_TEMPLATE_AMBIGUOUS,
    REASON_TEMPLATE_DYNAMIC,
    REASON_TEMPLATE_NONE,
    REASON_UNCERTAIN,
    REASON_UNCHECKED,
    REASON_UNKNOWN_ROUTE,
    REASON_UNVERIFIED,
    RealPreviewRouteSelection,
    is_static_route_path,
    method_refusal,
    route_preview_refusal,
    route_preview_selection,
    select_real_preview_route,
    select_route_for_preview,
)

TEMPLATE = "mvc/views/contacts/list.html"
GENERAL_WARNINGS = (
    "Lecture statique des routes explicitement branchées ; la liste peut être "
    "partielle.",
    "Ligne 23 : déclaration non interprétée.",
)


def route(
    path: str = "/contacts",
    *,
    method: str = "GET",
    public: bool = True,
    template: str | None = "contacts/list.html",
    status: Any = "found",
    presence: Any = "present",
    verification: Any = "found",
    handler: bool = True,
    dynamic_handler: bool = False,
) -> RouteInfo:
    info = (
        HandlerInfo(
            "ContactsController.index",
            verification=verification,
            template=TemplateResolution(
                status=status, path=template, presence=presence
            ),
        )
        if handler
        else None
    )
    return RouteInfo(
        method, path, None, public, handler=info, handler_dynamic=dynamic_handler
    )


def select(*routes: RouteInfo, template: str = TEMPLATE) -> RealPreviewRouteSelection:
    return select_real_preview_route(template, RoutesResult(routes, GENERAL_WARNINGS))


def test_unique_public_route_available() -> None:
    assert select(route()) == RealPreviewRouteSelection(True, "/contacts", None)


def test_root_route_available() -> None:
    assert select(route("/")).path == "/"


def test_general_warnings_do_not_block() -> None:
    other = route("/charte", template="pages/charte.html")
    assert select(route(), other).available


@pytest.mark.parametrize(
    ("routes", "reason"),
    [
        ((), REASON_NONE),
        ((route(public=False),), REASON_PROTECTED),
        ((route(), route("/contacts/liste")), REASON_SEVERAL),
        ((route(), route("/contacts/liste", public=False)), REASON_SEVERAL),
        ((route("/contacts/{id}"),), REASON_DYNAMIC),
        ((route("/contacts/{id}"), route("/contacts")), REASON_SEVERAL),
        ((route(method="POST"),), REASON_NONE),
        ((route(handler=False),), REASON_UNCERTAIN),
        ((route(dynamic_handler=True, handler=False),), REASON_UNCERTAIN),
        ((route(verification="method-missing"),), REASON_UNCERTAIN),
        ((route(verification="class-missing"),), REASON_UNCERTAIN),
        ((route(status="dynamic", template=None),), REASON_UNCERTAIN),
        ((route(status="ambiguous", template=None),), REASON_UNCERTAIN),
        ((route(template="contacts/show.html"),), REASON_NONE),
        ((route(status="none", template=None),), REASON_NONE),
        ((route(presence="missing"),), REASON_MISSING),
        ((route(presence="invalid-path"),), REASON_MISSING),
        # Une autre route GET au template indéterminable pourrait rendre celui-ci.
        ((route(), route("/autre", status="dynamic", template=None)), REASON_UNCERTAIN),
        ((route(), route("/autre", handler=False)), REASON_UNCERTAIN),
    ],
)
def test_unavailable(routes: tuple[RouteInfo, ...], reason: str) -> None:
    selection = select(*routes)
    assert selection == RealPreviewRouteSelection(False, None, reason)


def test_uncertain_post_route_does_not_block() -> None:
    other = route("/contacts/delete", method="POST", handler=False)
    assert select(route(), other).available


def test_same_route_listed_twice_is_unique() -> None:
    assert select(route(), route()).available


def test_contract_template_outside_views() -> None:
    assert select(route(), template="templates/x.html").reason == (
        REASON_NO_CONTRACT_TEMPLATE
    )


def test_no_lexical_guess() -> None:
    """Un chemin qui ressemble au template ne remplace pas Route Explorer."""
    lookalike = route("/contacts/list", template="autre.html")
    assert select(lookalike).reason == REASON_NONE


@pytest.mark.parametrize(
    "path",
    ["/contacts/{id}", "//evil", "/a?b=1", "/a#f", "/a b", "/é", "/a\\b", "x", ""],
)
def test_route_path_must_be_static_origin_form(path: str) -> None:
    assert not is_static_route_path(path)
    assert not select(route(path)).available


def test_selection_is_frozen() -> None:
    selection = select(route())
    with pytest.raises(FrozenInstanceError):
        selection.path = "/admin"  # type: ignore[misc]


# ── Route désignée depuis Route Explorer (FD-REALPREVIEW-008) ────────────────


def designate(target: RouteInfo, *others: RouteInfo) -> RealPreviewRouteSelection:
    return route_preview_selection(
        target, RoutesResult((target, *others), GENERAL_WARNINGS)
    )


def by_path(path: str, *routes: RouteInfo) -> RealPreviewRouteSelection:
    return select_route_for_preview(path, RoutesResult(routes, GENERAL_WARNINGS))


def test_designated_route_eligible() -> None:
    assert designate(route()) == RealPreviewRouteSelection(True, "/contacts", None)
    assert designate(route("/")).path == "/"
    assert route_preview_refusal(route()) is None


@pytest.mark.parametrize(
    ("target", "reason"),
    [
        (route(method="POST"), method_refusal("POST")),
        (route(method="DELETE"), method_refusal("DELETE")),
        (route("/contacts/{id}"), REASON_DYNAMIC),
        (route(handler=False), REASON_HANDLER),
        (route(dynamic_handler=True), REASON_HANDLER),
        (route(verification="method-missing"), REASON_UNVERIFIED),
        (route(verification="class-missing"), REASON_UNVERIFIED),
        (route(verification="unreadable"), REASON_UNVERIFIED),
        (route(status="dynamic", template=None), REASON_TEMPLATE_DYNAMIC),
        (route(status="ambiguous", template=None), REASON_TEMPLATE_AMBIGUOUS),
        (route(status="none", template=None), REASON_TEMPLATE_NONE),
        (route(status="not-applicable", template=None), REASON_TEMPLATE_NONE),
        (route(presence="missing"), REASON_MISSING),
        (route(presence="invalid-path"), REASON_MISSING),
        (route(presence="unreadable"), REASON_MISSING),
        (route(presence="not-applicable"), REASON_UNCHECKED),
        (route(public=False), REASON_PROTECTED),
    ],
)
def test_designated_route_refused(target: RouteInfo, reason: str) -> None:
    assert designate(target) == RealPreviewRouteSelection(False, None, reason)
    assert route_preview_refusal(target) == reason


@pytest.mark.parametrize(
    "path",
    ["/contacts/{id}", "//evil", "/a?b=1", "/a#f", "/a b", "/é", "/a\\b", "x", ""],
)
def test_designated_route_path_must_be_static(path: str) -> None:
    assert designate(route(path)).available is False


def test_identical_declarations_are_one_route() -> None:
    assert designate(route(), route()).available
    assert by_path("/contacts", route(), route()).available


@pytest.mark.parametrize(
    "other",
    [
        route(public=False),
        route(template="contacts/show.html"),
        route(status="dynamic", template=None),
        route(handler=False),
    ],
)
def test_conflicting_declarations_are_ambiguous(other: RouteInfo) -> None:
    assert designate(route(), other).reason == REASON_DUPLICATE
    assert by_path("/contacts", route(), other).reason == REASON_DUPLICATE


def test_other_uncertain_routes_do_not_block_a_designated_route() -> None:
    """Différence assumée avec l'éditeur : l'URL est désignée, rien n'est choisi."""
    others = (
        route("/autre", status="dynamic", template=None),
        route("/fonction", handler=False),
        route("/liste", template="contacts/list.html"),
    )
    assert select(route(), *others).available is False
    assert designate(route(), *others).available


def test_post_with_same_path_does_not_conflict() -> None:
    assert by_path("/contacts", route(), route(method="POST", handler=False)).available


@pytest.mark.parametrize(
    "path",
    [
        "/inconnue",
        "/contacts/",
        "/Contacts",
        "contacts",
        "/contacts/../contacts",
        "/./contacts",
        "/etc/passwd",
        "http://127.0.0.1:1/contacts",
        "mvc/views/contacts/list.html",
        "/contacts?x=1",
    ],
)
def test_unknown_or_lookalike_path_refused(path: str) -> None:
    assert by_path(path, route()) == RealPreviewRouteSelection(
        False, None, REASON_UNKNOWN_ROUTE
    )


def test_post_only_path_is_unknown_as_get() -> None:
    assert by_path("/contacts", route(method="POST")).reason == REASON_UNKNOWN_ROUTE


def _variants() -> list[RouteInfo]:
    items: list[RouteInfo] = []
    for method in ("GET", "POST"):
        for path in ("/contacts", "/contacts/{id}"):
            for public in (True, False):
                for status, template in (
                    ("found", "contacts/list.html"),
                    ("found", "contacts/show.html"),
                    ("dynamic", None),
                ):
                    for presence in ("present", "missing"):
                        items.append(
                            route(
                                path,
                                method=method,
                                public=public,
                                status=status,
                                template=template,
                                presence=presence,
                            )
                        )
    items.append(route("/fonction", handler=False))
    return items


def _conflicting(first: RouteInfo, second: RouteInfo) -> bool:
    """Deux déclarations GET du même chemin qui ne servent pas la même réponse."""
    pair = RoutesResult((first, second), GENERAL_WARNINGS)
    return (
        first.method == second.method == "GET"
        and first.path == second.path
        and route_preview_selection(first, pair).reason == REASON_DUPLICATE
    )


def test_editor_selection_implies_route_eligibility() -> None:
    """Toute route retenue par l'éditeur satisfait les garanties de route, sauf
    déclarations GET conflictuelles du même chemin, que seul Route Explorer
    refuse (constat FD-REALPREVIEW-008, parcours éditeur inchangé)."""
    variants = _variants()
    checked = conflicts = 0
    for first in variants:
        for second in variants:
            routes = RoutesResult((first, second), GENERAL_WARNINGS)
            chosen = select_real_preview_route(TEMPLATE, routes)
            if not chosen.available:
                continue
            assert chosen.path is not None
            designated = select_route_for_preview(chosen.path, routes)
            if _conflicting(first, second):
                conflicts += 1
                assert designated.reason == REASON_DUPLICATE
                continue
            checked += 1
            assert designated.available
    assert checked > 0 and conflicts > 0


def test_editor_does_not_detect_conflicting_declarations() -> None:
    """Constat : GET /contacts déclaré deux fois avec deux templates ; l'éditeur
    retient la route pour list.html alors que Forge sert la première déclarée."""
    other = route(template="contacts/show.html")
    assert select(other, route()).available
    assert by_path("/contacts", other, route()).reason == REASON_DUPLICATE
