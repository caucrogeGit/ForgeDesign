"""Chaîne applicative statique d'une route (FD-ROUTES-021), pour Route Explorer.

Couche adjacente, pure et sans lecture : elle compose ce que Route Explorer a déjà
établi (RoutesResult, RouteDiagnostics) et la liaison contrats ↔ templates
(analyze_view_contract_links, avec l'inventaire de Template Viewer déjà lu), puis
indexe par chemin de template. Aucune convention de nom n'est inventée : une
route n'atteint un contrat que par un template qu'elle rend réellement
(route → template → contrat).

Niveaux de confiance du template, sans pourcentage :

- ``exact`` : un seul ``render`` littéral ;
- ``multiple`` : plusieurs littéraux, tous possibles ;
- ``partial`` : des littéraux et au moins un rendu non déterminable ;
- ``unknown`` : rendu non déterminable statiquement (jamais « aucun template ») ;
- ``none`` : aucun rendu détecté (pas une preuve d'absence de template) ;
- ``not-applicable`` : méthode non résolue, rien à analyser.

Une incertitude statique ne devient jamais une erreur : les sévérités sont
celles de build_route_diagnostics ; une anomalie de contrat vaut avertissement,
une route sans contrat n'est qu'un état (le contrat est optionnel). Un contrat
invalide n'a pas de cible lisible : il reste un diagnostic global de la section
des contrats, jamais rattaché à une route.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from forge_design.contracts.linkage import (
    TemplateLinkStatus,
    ViewContractLinksResult,
)
from forge_design.contracts.reader import view_contract_source
from forge_design.forge.routes import (
    RouteInfo,
    RoutesResult,
    TemplatePresenceStatus,
)
from forge_design.forge.source import SourceLocation, SourceReadError, source_parts
from forge_design.tools.route_diagnostics import DiagnosticSeverity, RouteDiagnostics

Confidence = Literal[
    "exact", "multiple", "partial", "unknown", "none", "not-applicable"
]
ChainState = Literal["complete", "partial", "problematic"]
HandlerKind = Literal["controller-method", "function", "unresolved", "dynamic"]
ControllerState = Literal[
    "resolved",
    "file-missing",
    "class-missing",
    "method-missing",
    "ambiguous",
    "unreadable",
    "not-applicable",
]
Origin = Literal["route", "handler", "controller", "template", "dependency", "contract"]
ContractState = Literal[
    "linked", "ambiguous", "without-contract", "unknown", "not-applicable"
]

# Ordre d'affichage : de la déclaration de route jusqu'au contrat.
ORIGINS: tuple[Origin, ...] = (
    "route",
    "handler",
    "controller",
    "template",
    "dependency",
    "contract",
)
_VERIFICATION_STATES: dict[str, ControllerState] = {
    "found": "resolved",
    "class-missing": "class-missing",
    "method-missing": "method-missing",
    "ambiguous": "ambiguous",
    "unreadable": "unreadable",
}


@dataclass(frozen=True)
class LinkedDiagnostic:
    code: str
    severity: DiagnosticSeverity
    message: str
    origin: Origin
    source: SourceLocation | None = None
    source_available: bool = False
    subject: str | None = None


@dataclass(frozen=True)
class TemplateLink:
    """Template rendu (exact ou candidat) et son contrat de vue éventuel."""

    path: str
    presence: TemplatePresenceStatus
    source: SourceLocation | None
    contract_state: ContractState
    contracts: tuple[str, ...] = ()


@dataclass(frozen=True)
class RouteLinkage:
    index: int
    route: RouteInfo
    handler_kind: HandlerKind
    controller_state: ControllerState
    confidence: Confidence
    templates: tuple[TemplateLink, ...]
    diagnostics: tuple[LinkedDiagnostic, ...]
    state: ChainState


@dataclass(frozen=True)
class ContractsOverview:
    """Section « Contrats de vue » de la page : disponibilité et diagnostics
    globaux (contrats invalides non associables, anomalies hors routes)."""

    available: bool
    reason: str | None = None
    total: int = 0
    invalid: int = 0
    complete: bool = True
    diagnostics: tuple[LinkedDiagnostic, ...] = ()


@dataclass(frozen=True)
class RouteLinkageReport:
    routes: tuple[RouteLinkage, ...]
    contracts: ContractsOverview

    def select(self, routes: Iterable[RouteInfo]) -> tuple[RouteLinkage, ...]:
        """Chaînes des routes affichées (filtres), dans l'ordre de la page."""
        wanted = {id(route) for route in routes}
        return tuple(item for item in self.routes if id(item.route) in wanted)


def origin_of(code: str) -> Origin:
    """Origine d'un diagnostic, dérivée de son code (préfixe stable)."""
    if code.startswith("template.dependency_"):
        return "dependency"
    prefix = code.split(".", 1)[0]
    if prefix in ORIGINS:
        return prefix  # pyright: ignore[reportReturnType]
    raise ValueError(f"Origine inconnue pour le code {code!r}.")


def _navigable(source: SourceLocation | None) -> bool:
    if source is None:
        return False
    try:
        source_parts(source.path)
    except SourceReadError:
        return False
    return True


def _handler_kind(route: RouteInfo) -> HandlerKind:
    handler = route.handler
    if handler is None:
        return "dynamic" if route.handler_dynamic else "unresolved"
    if "." not in handler.reference:
        return "function"
    if (
        handler.controller_file is None
        and handler.missing_controller is None
        and handler.verification == "not-applicable"
    ):
        return "unresolved"
    return "controller-method"


def _controller_state(route: RouteInfo) -> ControllerState:
    handler = route.handler
    if handler is None:
        return "not-applicable"
    if handler.missing_controller is not None:
        return "file-missing"
    return _VERIFICATION_STATES.get(handler.verification, "not-applicable")


def _confidence(route: RouteInfo) -> Confidence:
    handler = route.handler
    if handler is None or handler.verification != "found":
        return "not-applicable"
    template = handler.template
    if template.status == "found":
        return "exact"
    if template.status == "ambiguous":
        return "multiple"
    if template.status == "dynamic":
        return "partial" if template.candidates else "unknown"
    if template.status == "none":
        return "none"
    return "not-applicable"


def _contract_diagnostic(
    code: str, message: str, contract: str | None, subject: str | None
) -> LinkedDiagnostic:
    # Chemins de contrats relatifs à mvc/views : même politique que la lecture.
    location = view_contract_source(contract) if contract else None
    return LinkedDiagnostic(
        code, "warning", message, "contract", location, _navigable(location), subject
    )


class _ContractIndex:
    """Index par chemin de template (relatif à mvc/views), construit une fois."""

    def __init__(self, links: ViewContractLinksResult | None) -> None:
        self.available = links is not None
        self.status: dict[str, tuple[TemplateLinkStatus, tuple[str, ...]]] = {}
        self.issues: dict[str, list[LinkedDiagnostic]] = defaultdict(list)
        self.global_issues: list[LinkedDiagnostic] = []
        self.invalid = 0
        self.total = 0
        self.complete = True
        if links is None:
            return
        self.total = len(links.contracts)
        self.complete = links.contracts_complete and not links.truncated
        for item in links.templates:
            self.status[item.template_path] = (item.status, item.contract_paths)
        owners: dict[str, list[str]] = defaultdict(list)
        for link in links.contracts:
            if link.template_path is not None:
                owners[link.contract_path].append(link.template_path)
            if link.status == "contract-invalid":
                self.invalid += 1
        for issue in links.issues:
            diagnostic = _contract_diagnostic(
                issue.code,
                issue.message,
                issue.contract_path,
                issue.contract_path or issue.template_path,
            )
            if issue.template_path is not None:
                self.issues[issue.template_path].append(diagnostic)
            else:
                self.global_issues.append(diagnostic)
        for issue in links.contract_issues:
            diagnostic = _contract_diagnostic(
                issue.code, issue.message, issue.path, issue.path
            )
            targets = owners.get(issue.path or "", [])
            for target in targets:
                self.issues[target].append(diagnostic)
            if not targets:
                # Contrat sans cible lisible (JSON ou schéma invalide) : global.
                self.global_issues.append(diagnostic)

    def link(
        self,
        path: str,
        presence: TemplatePresenceStatus,
        source: SourceLocation | None,
    ) -> TemplateLink:
        if not self.available:
            return TemplateLink(path, presence, source, "unknown")
        known = self.status.get(path)
        if known is None:
            # Template hors inventaire (absent, chemin refusé) : aucun contrat lié.
            state: ContractState = (
                "not-applicable" if presence != "present" else "unknown"
            )
            return TemplateLink(path, presence, source, state)
        status, contracts = known
        # Les statuts de liaison sont un sous-ensemble exact de ContractState.
        state = status
        return TemplateLink(path, presence, source, state, contracts)


def _route_templates(
    route: RouteInfo, index: _ContractIndex
) -> tuple[TemplateLink, ...]:
    handler = route.handler
    if handler is None or handler.verification != "found":
        return ()
    template = handler.template
    if template.status == "found" and template.path is not None:
        return (index.link(template.path, template.presence, template.source),)
    return tuple(
        index.link(item.path, item.presence, item.source)
        for item in template.candidates
    )


def build_route_linkage(
    result: RoutesResult,
    diagnostics: RouteDiagnostics,
    links: ViewContractLinksResult | None,
    *,
    contracts_reason: str | None = None,
) -> RouteLinkageReport:
    """Chaîne de chaque route du résultat complet (non filtré).

    ``diagnostics`` : build_route_diagnostics(result), dont les indices se
    rapportent à ``result.routes`` ; ``links`` : None si l'analyse des contrats
    est indisponible (``contracts_reason`` en donne la raison).
    """
    index = _ContractIndex(links)
    owned: dict[int, list[LinkedDiagnostic]] = defaultdict(list)
    for item in diagnostics.items:
        linked = LinkedDiagnostic(
            item.code,
            item.severity,
            item.message,
            origin_of(item.code),
            item.source,
            item.source_available,
            item.subject,
        )
        for route_index in item.route_indices:
            owned[route_index].append(linked)
    chains: list[RouteLinkage] = []
    for position, route in enumerate(result.routes):
        templates = _route_templates(route, index)
        found = list(owned[position])
        for template in templates:
            for diagnostic in index.issues.get(template.path, ()):
                if diagnostic not in found:
                    found.append(diagnostic)
        found.sort(key=lambda item: ORIGINS.index(item.origin))
        confidence = _confidence(route)
        if any(item.severity == "error" for item in found):
            state: ChainState = "problematic"
        elif confidence == "exact" and templates and templates[0].presence == "present":
            state = "complete"
        else:
            state = "partial"
        chains.append(
            RouteLinkage(
                position,
                route,
                _handler_kind(route),
                _controller_state(route),
                confidence,
                templates,
                tuple(found),
                state,
            )
        )
    overview = (
        ContractsOverview(
            True,
            None,
            index.total,
            index.invalid,
            index.complete,
            tuple(index.global_issues),
        )
        if links is not None
        else ContractsOverview(False, contracts_reason or "Analyse indisponible.")
    )
    return RouteLinkageReport(tuple(chains), overview)
