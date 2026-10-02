"""Sélection de la route de preview réelle (FD-REALPREVIEW-004), sans I/O."""

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
    REASON_DYNAMIC,
    REASON_MISSING,
    REASON_NO_CONTRACT_TEMPLATE,
    REASON_NONE,
    REASON_PROTECTED,
    REASON_SEVERAL,
    REASON_UNCERTAIN,
    RealPreviewRouteSelection,
    is_static_route_path,
    select_real_preview_route,
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
