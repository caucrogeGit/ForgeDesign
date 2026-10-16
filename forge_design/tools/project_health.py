"""Synthèse de santé du projet Forge sélectionné, pour Project Inspector.

Vue consolidée, runtime et en lecture seule : elle ne crée aucun Tool, n'écrit
rien, ne persiste rien et ne met rien en cache. Chaque domaine est lu par
l'analyse existante, obtenue par le ToolRegistry quand un Tool la porte
(project-inspector, route-explorer, entity-explorer, template-viewer,
debug-center), puis résumé avec les diagnostics existants
(build_route_diagnostics, build_entity_diagnostics, filter_debug_events).
L'inventaire des templates est lu une fois et transmis à l'analyse des contrats
de vue ; les migrations ont leur petit lecteur Forge-specific (noms et tailles).

Isolation : chaque section ne capture que les erreurs de domaine déjà traitées
par la page de son outil et devient alors « indisponible » ; toute autre
exception est un bug et remonte. Sévérités : celles des diagnostics existants ;
sans sévérité existante (templates, contrats, migrations), une anomalie vaut
« attention » ; les erreurs historiques du journal runtime ne mettent jamais le
projet en erreur ; un élément optionnel absent n'est qu'une information.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeVar

from forge_design.contracts.linkage import (
    ViewContractLinksResult,
    analyze_view_contract_links,
    is_view_template_path,
)
from forge_design.forge.debug_errors import DebugErrorsResult
from forge_design.forge.entities import EntitiesResult
from forge_design.forge.migrations import MigrationsResult, read_migrations
from forge_design.forge.project_detection import StructureEntry, detect_forge_project
from forge_design.forge.project_root import (
    ProjectRootNotDirectoryError,
    ProjectRootNotFoundError,
    ProjectRootResolutionError,
)
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.forge.routes import (
    RoutesResult,
    RoutesSourceMissingError,
    RoutesSourceUnreadableError,
)
from forge_design.forge.templates import TemplatesResult
from forge_design.limits import MAX_HEALTH_VISIBLE_DIAGNOSTICS
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.debug_filters import DebugFilter, filter_debug_events
from forge_design.tools.entity_diagnostics import build_entity_diagnostics
from forge_design.tools.project_inspector import ProjectInspection
from forge_design.tools.route_diagnostics import build_route_diagnostics

HealthStatus = Literal["ok", "attention", "erreur", "indisponible"]
Severity = Literal["error", "warning", "info"]

HEALTH_STATUSES: tuple[HealthStatus, ...] = (
    "ok",
    "attention",
    "erreur",
    "indisponible",
)

# Erreurs de racine : le projet lui-même n'est plus analysable.
_ROOT_ERRORS = (
    ProjectRootNotFoundError,
    ProjectRootNotDirectoryError,
    ProjectRootResolutionError,
)
# Erreurs de domaine traitées par les pages des outils (mêmes tuples).
_PROJECT_ERRORS = (*_ROOT_ERRORS, NotForgeProjectError)
_ROUTE_ERRORS = (
    *_PROJECT_ERRORS,
    RoutesSourceMissingError,
    RoutesSourceUnreadableError,
)
# Absence du dossier optionnel mvc/entities, signalée en avertissement par le
# lecteur d'entités : simple information dans la synthèse (optionnel absent).
_OPTIONAL_ABSENCE_CODES = frozenset({"entity.source_missing"})
_DEBUG_ERRORS = frozenset({"ERROR", "CRITICAL"})

DETAILS_URL = "/inspector#inspection-details"


@dataclass(frozen=True)
class HealthDiagnostic:
    severity: Severity
    message: str
    subject: str | None = None


@dataclass(frozen=True)
class HealthAction:
    label: str
    url: str


@dataclass(frozen=True)
class HealthSection:
    """Un domaine : état, résumé, faits, aperçu borné des diagnostics, action."""

    key: str
    title: str
    status: HealthStatus
    summary: str
    facts: tuple[tuple[str, str], ...] = ()
    diagnostics: tuple[HealthDiagnostic, ...] = ()
    diagnostic_total: int = 0
    action: HealthAction | None = None


@dataclass(frozen=True)
class ProjectHealthSummary:
    """Synthèse recalculée à chaque affichage ; jamais persistée."""

    root: Path
    name: str
    status: HealthStatus
    sections: tuple[HealthSection, ...]
    inspection: ProjectInspection | None
    structure: tuple[StructureEntry, ...]

    def section(self, key: str) -> HealthSection:
        return next(section for section in self.sections if section.key == key)


_ACTIONS = {
    "project": None,
    "forge": HealthAction("Voir le détail de l’inspection", DETAILS_URL),
    "structure": HealthAction("Voir le détail de l’inspection", DETAILS_URL),
    "routes": HealthAction("Voir les routes", "/routes"),
    "entities": HealthAction("Voir les entités", "/entities"),
    "templates": HealthAction("Voir les templates", "/templates"),
    "migrations": None,
    "diagnostics": HealthAction("Voir les diagnostics", "/debug"),
    "contracts": HealthAction("Voir les templates et leurs contrats", "/templates"),
}
_TITLES = {
    "project": "Projet",
    "forge": "Forge",
    "structure": "Structure",
    "routes": "Routes",
    "entities": "Entités",
    "templates": "Templates",
    "migrations": "Migrations",
    "diagnostics": "Diagnostics",
    "contracts": "Contrats de vue",
}
SECTION_KEYS = tuple(_TITLES)

_T = TypeVar("_T")


def _section(
    key: str,
    status: HealthStatus,
    summary: str,
    facts: Iterable[tuple[str, str]] = (),
    diagnostics: Iterable[HealthDiagnostic] = (),
) -> HealthSection:
    items = tuple(diagnostics)
    return HealthSection(
        key,
        _TITLES[key],
        status,
        summary,
        tuple(facts),
        items[:MAX_HEALTH_VISIBLE_DIAGNOSTICS],
        len(items),
        _ACTIONS[key],
    )


def _unavailable(key: str, reason: str) -> HealthSection:
    return _section(key, "indisponible", reason)


def _by_severity(items: Iterable[HealthDiagnostic]) -> HealthStatus:
    severities = {item.severity for item in items}
    if "error" in severities:
        return "erreur"
    return "attention" if "warning" in severities else "ok"


def _run(registry: ToolRegistry, tool: str, root: Path, kind: type[_T]) -> _T:
    result = registry.get(tool).run(root)
    if not isinstance(result, kind):
        raise TypeError(f"{tool} doit retourner {kind.__name__}.")
    return result


def _guarded(
    key: str,
    errors: tuple[type[Exception], ...],
    build: Callable[[], HealthSection],
) -> HealthSection:
    try:
        return build()
    except errors as error:
        return _unavailable(key, f"Analyse indisponible : {error}")


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else plural or singular + 's'}"


# --- Sections -----------------------------------------------------------------


def _project(root: Path) -> HealthSection:
    return _section(
        "project",
        "ok",
        "Projet sélectionné et accessible.",
        (("Nom", root.name or str(root)), ("Dossier", str(root))),
    )


def _forge(
    inspection: ProjectInspection, version_warnings: tuple[str, ...]
) -> HealthSection:
    facts = (
        ("Projet Forge reconnu", "oui" if inspection.valid else "non"),
        ("Version détectée", inspection.forge_version or "indéterminée"),
        ("Source de la version", inspection.forge_version_source or "indéterminée"),
        # Aucune matrice de compatibilité Forge n'existe encore : rien n'est déduit.
        (
            "Compatibilité Forge Design",
            "non évaluée (aucune règle de version définie)",
        ),
    )
    if not inspection.valid:
        return _section(
            "forge",
            "erreur",
            "Le dossier n’est plus reconnu comme projet Forge.",
            facts,
            (HealthDiagnostic("error", message) for message in inspection.errors),
        )
    found = inspection.forge_version is not None
    return _section(
        "forge",
        "ok" if found else "attention",
        f"Forge {inspection.forge_version} détecté."
        if found
        else "Projet Forge reconnu ; version indéterminée.",
        facts,
        (HealthDiagnostic("warning", message) for message in version_warnings),
    )


def _structure(entries: tuple[StructureEntry, ...]) -> HealthSection:
    required = [entry for entry in entries if entry.required]
    optional = [entry for entry in entries if not entry.required]
    diagnostics: list[HealthDiagnostic] = []
    for entry in entries:
        if entry.state == "present":
            continue
        if entry.required:
            text = "absent" if entry.state == "absent" else "invalide"
            diagnostics.append(
                HealthDiagnostic("error", f"Élément requis {text}.", entry.label)
            )
        elif entry.state == "invalid" and entry.strict:
            # Optionnel mais présent invalide : le projet n'est pas reconnu.
            diagnostics.append(
                HealthDiagnostic(
                    "error",
                    "Élément optionnel invalide (lien ou type) : projet non reconnu.",
                    entry.label,
                )
            )
        elif entry.state == "invalid":
            diagnostics.append(
                HealthDiagnostic(
                    "warning", "Élément optionnel invalide (lien ou type).", entry.label
                )
            )
        else:
            diagnostics.append(
                HealthDiagnostic("info", "Élément optionnel absent.", entry.label)
            )
    found = [entry.label for entry in optional if entry.state == "present"]
    present = sum(entry.state == "present" for entry in required)
    status = _by_severity(diagnostics)
    anomalies = sum(item.severity != "info" for item in diagnostics)
    return _section(
        "structure",
        status,
        "Squelette Forge complet."
        if status == "ok"
        else "Squelette Forge incomplet."
        if status == "erreur"
        else "Squelette Forge reconnu, avec anomalies.",
        (
            ("Éléments requis trouvés", f"{present} / {len(required)}"),
            (
                "Éléments optionnels trouvés",
                ", ".join(found) if found else "aucun",
            ),
            ("Anomalies", str(anomalies)),
        ),
        diagnostics,
    )


def _routes(result: RoutesResult) -> HealthSection:
    report = build_route_diagnostics(result)
    flagged = {index for item in report.items for index in item.route_indices}
    methods = tuple(dict.fromkeys(route.method for route in result.routes))
    # warnings[0] est toujours la mise en garde de lecture statique (read_routes
    # la retire lui-même des branchements) : seule, elle ne signale aucune
    # anomalie du projet et route.partial n'est alors qu'une information. Route
    # Explorer garde son affichage inchangé.
    standing_only = len(result.warnings) <= 1
    diagnostics = tuple(
        HealthDiagnostic(
            "info" if item.code == "route.partial" and standing_only else item.severity,
            item.message,
            item.subject,
        )
        for item in report.items
    )
    total = len(result.routes)
    return _section(
        "routes",
        _by_severity(diagnostics),
        _plural(total, "route déclarée", "routes déclarées") + ".",
        (
            ("Routes", str(total)),
            ("Méthodes HTTP", ", ".join(methods) if methods else "aucune"),
            ("Routes sans diagnostic", str(total - len(flagged))),
            ("Routes avec diagnostic", str(len(flagged))),
            ("Lecture", "statique ; liste possiblement partielle"),
            (
                "Diagnostics",
                f"{report.error_count} erreur(s), "
                f"{report.warning_count} avertissement(s), "
                f"{report.info_count} information(s)",
            ),
        ),
        diagnostics,
    )


def _entities(result: EntitiesResult) -> HealthSection:
    report = build_entity_diagnostics(result)
    diagnostics = tuple(
        HealthDiagnostic(
            "info" if item.code in _OPTIONAL_ABSENCE_CODES else item.severity,
            item.message,
            item.subject,
        )
        for item in report.items
    )
    return _section(
        "entities",
        _by_severity(diagnostics),
        f"{_plural(len(result.entities), 'entité')}, "
        f"{_plural(len(result.relations), 'relation')}.",
        (
            ("Entités", str(len(result.entities))),
            ("Relations", str(len(result.relations))),
            ("Erreurs", str(sum(item.severity == "error" for item in diagnostics))),
            (
                "Avertissements",
                str(sum(item.severity == "warning" for item in diagnostics)),
            ),
        ),
        diagnostics,
    )


def _templates(result: TemplatesResult) -> HealthSection:
    views = sum(is_view_template_path(item.path) for item in result.templates)
    diagnostics = tuple(
        HealthDiagnostic("warning", item.message, item.path or item.code)
        for item in result.issues
    )
    if not result.source_present:
        diagnostics = (
            HealthDiagnostic("info", "Dossier optionnel absent.", "mvc/views"),
        )
    return _section(
        "templates",
        _by_severity(diagnostics),
        _plural(len(result.templates), "fichier détecté", "fichiers détectés")
        + " dans mvc/views.",
        (
            ("Fichiers détectés", str(len(result.templates))),
            ("Templates de vue", str(views)),
            (
                "Métadonnées (.view.json, .design.json)",
                str(len(result.templates) - views),
            ),
            ("Inventaire", "partiel" if result.truncated else "complet"),
        ),
        diagnostics,
    )


def _contracts(result: ViewContractLinksResult) -> HealthSection:
    total = len(result.contracts)
    invalid = sum(link.status == "contract-invalid" for link in result.contracts)
    linked = sum(item.status == "linked" for item in result.templates)
    without = sum(item.status == "without-contract" for item in result.templates)
    diagnostics = (
        *(
            HealthDiagnostic("warning", item.message, item.path or item.code)
            for item in result.contract_issues
        ),
        *(
            HealthDiagnostic(
                "warning",
                item.message,
                item.contract_path or item.template_path or item.code,
            )
            for item in result.issues
        ),
    )
    return _section(
        "contracts",
        _by_severity(diagnostics),
        _plural(total, "contrat de vue", "contrats de vue") + ".",
        (
            ("Contrats", str(total)),
            ("Valides", str(total - invalid)),
            ("Invalides", str(invalid)),
            ("Templates associés", str(linked)),
            ("Templates sans contrat", str(without)),
            ("Liaison", "complète" if result.contracts_complete else "incomplète"),
        ),
        diagnostics,
    )


def _migrations(result: MigrationsResult) -> HealthSection:
    diagnostics = tuple(
        HealthDiagnostic("warning", item.message, item.name or item.code)
        for item in result.issues
    )
    if not result.source_present:
        diagnostics = (
            HealthDiagnostic("info", "Dossier optionnel absent.", "mvc/migrations"),
        )
    return _section(
        "migrations",
        _by_severity(diagnostics),
        _plural(len(result.migrations), "migration SQL", "migrations SQL")
        + " (inventaire seul, aucune exécution).",
        (
            ("Migrations", str(len(result.migrations))),
            (
                "Dossier mvc/migrations",
                "présent" if result.source_present else "absent",
            ),
            ("Analyse", "noms et tailles seulement"),
        ),
        diagnostics,
    )


def _diagnostics(result: DebugErrorsResult) -> HealthSection:
    events = filter_debug_events(result, DebugFilter()).events
    errors = sum(event.level in _DEBUG_ERRORS for event in result.events)
    warnings = sum(event.level == "WARNING" for event in result.events)
    infos = sum(event.level == "INFO" for event in result.events)
    items = (
        *(
            HealthDiagnostic(
                "error"
                if event.level in _DEBUG_ERRORS
                else "warning"
                if event.level == "WARNING"
                else "info",
                f"{event.level} · {event.exception_type} : {event.message}",
                event.timestamp,
            )
            for event in events
        ),
        *(
            HealthDiagnostic("warning", item.message, item.code)
            for item in result.issues
        ),
    )
    # Erreurs historiques du runtime : à examiner, jamais un projet « en erreur ».
    status: HealthStatus = (
        "attention" if errors or warnings or result.issues or result.truncated else "ok"
    )
    return _section(
        "diagnostics",
        status,
        "Journal runtime de développement (Debug Center)."
        if result.source_present
        else "Aucun journal runtime : aucune erreur enregistrée.",
        (
            ("Erreurs (ERROR, CRITICAL)", str(errors)),
            ("Avertissements", str(warnings)),
            ("Informations", str(infos)),
            ("Anomalies de lecture du journal", str(len(result.issues))),
        ),
        items,
    )


# --- Agrégation -----------------------------------------------------------------


def aggregate_status(
    sections: Iterable[HealthSection], *, project_available: bool = True
) -> HealthStatus:
    """erreur → projet indisponible → attention (dont section indisponible) → ok."""
    statuses = {section.status for section in sections}
    if "erreur" in statuses:
        return "erreur"
    if not project_available:
        return "indisponible"
    if statuses & {"attention", "indisponible"}:
        return "attention"
    return "ok"


def summarize_project_health(
    root: Path,
    registry: ToolRegistry,
    *,
    inspection: ProjectInspection | None = None,
) -> ProjectHealthSummary:
    """Analyser la racine sélectionnée, en lecture seule, section par section.

    ``root`` est la racine du CurrentProjectContext, jamais un chemin HTTP.
    ``inspection`` : résultat de project-inspector que l'appelant vient
    d'obtenir pour cette même racine (sélection, actualisation), réutilisé
    plutôt que relancé ; sinon l'inspection est faite ici.
    """
    try:
        if inspection is None or inspection.root != root:
            inspection = _run(registry, "project-inspector", root, ProjectInspection)
        detection = detect_forge_project(inspection.root)
    except _ROOT_ERRORS as error:
        reason = f"Projet inaccessible : {error}"
        sections = (
            _unavailable("project", reason),
            *(
                _unavailable(key, "Projet inaccessible : analyse impossible.")
                for key in SECTION_KEYS[1:]
            ),
        )
        return ProjectHealthSummary(
            root,
            root.name or str(root),
            aggregate_status(sections, project_available=False),
            sections,
            None,
            (),
        )
    canonical = inspection.root
    structure = detection.entries
    # inspect_project ajoute ses avertissements de version après ceux de la
    # structure : ils se séparent par position, jamais par le texte.
    known = len(detection.warnings)
    version_warnings = (
        inspection.warnings[known:]
        if inspection.warnings[:known] == detection.warnings
        else inspection.warnings
    )
    base = (
        _project(canonical),
        _forge(inspection, version_warnings),
        _structure(structure),
    )
    if not inspection.valid:
        reason = "Projet Forge non reconnu : analyse impossible."
        sections = (*base, *(_unavailable(key, reason) for key in SECTION_KEYS[3:]))
    else:
        templates: TemplatesResult | None = None

        def read_templates_section() -> HealthSection:
            nonlocal templates
            templates = _run(registry, "template-viewer", canonical, TemplatesResult)
            return _templates(templates)

        templates_section = _guarded(
            "templates", _PROJECT_ERRORS, read_templates_section
        )
        sections = (
            *base,
            _guarded(
                "routes",
                _ROUTE_ERRORS,
                lambda: _routes(
                    _run(registry, "route-explorer", canonical, RoutesResult)
                ),
            ),
            _guarded(
                "entities",
                _PROJECT_ERRORS,
                lambda: _entities(
                    _run(registry, "entity-explorer", canonical, EntitiesResult)
                ),
            ),
            templates_section,
            _guarded(
                "migrations",
                _PROJECT_ERRORS,
                lambda: _migrations(read_migrations(canonical)),
            ),
            _guarded(
                "diagnostics",
                _PROJECT_ERRORS,
                lambda: _diagnostics(
                    _run(registry, "debug-center", canonical, DebugErrorsResult)
                ),
            ),
            # Même inventaire que Template Viewer : mvc/views n'est pas rebalayé.
            _unavailable(
                "contracts",
                "Inventaire des templates indisponible : analyse impossible.",
            )
            if templates is None
            else _guarded(
                "contracts",
                _PROJECT_ERRORS,
                lambda: _contracts(analyze_view_contract_links(canonical, templates)),
            ),
        )
    return ProjectHealthSummary(
        canonical,
        canonical.name or str(canonical),
        aggregate_status(sections),
        sections,
        inspection,
        structure,
    )
