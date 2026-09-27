"""Consolidation pure des faits statiques, sans découverte ni verdict runtime."""

from dataclasses import dataclass, replace
from typing import Literal

from forge_design.forge.routes import (
    RoutesResult,
    TemplateDependency,
    TemplateResolution,
)
from forge_design.forge.source import SourceLocation, SourceReadError, source_parts

DiagnosticSeverity = Literal["info", "warning", "error"]


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: DiagnosticSeverity
    message: str
    source: SourceLocation | None = None
    subject: str | None = None
    source_available: bool = False
    route_indices: tuple[int, ...] = ()


@dataclass(frozen=True)
class RouteDiagnostics:
    items: tuple[Diagnostic, ...] = ()

    @property
    def error_count(self) -> int:
        return sum(item.severity == "error" for item in self.items)

    @property
    def warning_count(self) -> int:
        return sum(item.severity == "warning" for item in self.items)

    @property
    def info_count(self) -> int:
        return sum(item.severity == "info" for item in self.items)


def build_route_diagnostics(result: RoutesResult) -> RouteDiagnostics:
    """Première occurrence conservée ; aucun texte de warning n'est interprété."""
    items: list[Diagnostic] = []
    seen: dict[tuple[str, str | None, SourceLocation | None], int] = {}
    owners: list[dict[int, None]] = []
    closure_items: dict[int, None] | None = None
    cycles: set[tuple[tuple[str, str, str], ...]] = set()
    closures: dict[str, tuple[int, ...]] = {}

    def add(
        code: str,
        severity: DiagnosticSeverity,
        message: str,
        source: SourceLocation | None,
        subject: str | None,
        available: bool = True,
        *,
        shared: bool = False,
        global_diagnostic: bool = False,
    ) -> None:
        key = code, subject, None if shared else source
        index = seen.get(key)
        if index is None:
            index = len(items)
            seen[key] = index
            owners.append({})
        if not global_diagnostic:
            owners[index][route_index] = None
            if closure_items is not None:
                closure_items[index] = None
        if index < len(items):
            return
        navigable = available and source is not None
        if source is not None:
            try:
                source_parts(source.path)
            except SourceReadError:
                navigable = False
        items.append(Diagnostic(code, severity, message, source, subject, navigable))

    def template_fact(
        value: TemplateResolution | TemplateDependency,
        source: SourceLocation | None,
        available: bool,
    ) -> None:
        dependent = isinstance(value, TemplateDependency)
        prefix = "template.dependency_" if dependent else "template."
        label = "Dépendance template" if dependent else "Template"
        subject = value.path
        if value.presence == "missing":
            suffix, severity, detail = "missing", "error", "absent"
        elif value.presence == "invalid-path":
            suffix, severity, detail = "invalid_path", "error", "chemin refusé"
        elif value.presence == "unreadable" or value.syntax == "unreadable":
            suffix, severity, detail = "unreadable", "warning", "non vérifiable"
        elif value.syntax == "invalid":
            suffix, severity, detail = (
                "syntax_invalid",
                "error",
                "syntaxe Jinja invalide",
            )
        else:
            return
        message = f"{label} : {detail} — {subject}."
        if value.syntax == "invalid":
            if value.syntax_line is not None:
                message += f" Ligne {value.syntax_line}."
            if value.syntax_message:
                message += f" {value.syntax_message}"
            if not dependent and source is not None:
                source = SourceLocation(source.path, value.syntax_line)
        # Les erreurs de fichier partagé ne dépendent pas de leur route appelante.
        # Les dépendances manquantes gardent en revanche chaque déclaration source.
        add(
            prefix + suffix,
            "error" if severity == "error" else "warning",
            message,
            source,
            subject,
            available,
            shared=not dependent or suffix in {"syntax_invalid", "unreadable"},
        )

    def dependencies(values: tuple[TemplateDependency, ...]) -> None:
        for value in values:
            if not value.dynamic and value.path is not None:
                template_fact(value, value.source, value.source is not None)

    for route_index, route in enumerate(result.routes):
        handler = route.handler
        if handler is None:
            if route.handler_dynamic:
                add(
                    "handler.dynamic",
                    "warning",
                    "Handler dynamique non résolu.",
                    route.source,
                    f"{route.method} {route.path}",
                )
            continue
        controller_source = handler.class_source or (
            SourceLocation(handler.controller_file) if handler.controller_file else None
        )
        if handler.missing_controller is not None:
            add(
                "controller.missing",
                "error",
                f"Contrôleur importé absent : {handler.missing_controller}.",
                route.source,
                handler.missing_controller,
            )
        elif handler.verification in {
            "class-missing",
            "method-missing",
            "ambiguous",
            "unreadable",
        }:
            code, severity, description = {
                "class-missing": ("class_missing", "error", "Classe absente"),
                "method-missing": ("method_missing", "error", "Méthode absente"),
                "ambiguous": ("ambiguous", "warning", "Contrôleur ambigu"),
                "unreadable": ("unreadable", "warning", "Contrôleur non vérifiable"),
            }[handler.verification]
            add(
                "controller." + code,
                "error" if severity == "error" else "warning",
                f"{description} : {handler.reference}"
                f" ({handler.controller_file or 'fichier non résolu'}).",
                controller_source or route.source,
                handler.reference,
            )
        template = handler.template
        declaration = handler.method_source or controller_source or route.source
        if template.status in {"dynamic", "ambiguous"}:
            add(
                "template." + template.status,
                "warning",
                "Template dynamique non résolu."
                if template.status == "dynamic"
                else "Plusieurs templates possibles ; résolution ambiguë.",
                declaration,
                handler.reference,
            )
        elif template.status == "found":
            source = template.source if template.presence == "present" else declaration
            template_fact(template, source, source is not None)
        dependencies(template.dependencies)
        closure = template.dependency_graph
        if closure is None:
            continue
        if closure.root in closures:
            for index in closures[closure.root]:
                owners[index][route_index] = None
            continue
        closure_items = {}
        for node in closure.templates:
            dependencies(node.dependencies)
        closures[closure.root] = tuple(closure_items)
        closure_items = None
        sources = {node.path: node.source for node in closure.templates}
        for cycle in closure.cycles:
            if cycle.key in cycles:
                continue
            cycles.add(cycle.key)
            # Les lignes et chemins sont ceux des relations déjà diagnostiquées.
            source = None
            if cycle.edges:
                first = cycle.edges[0]
                known = sources.get(first.source)
                if known is not None:
                    source = SourceLocation(known.path, first.line)
            add(
                "template.cycle",
                "error",
                "Cycle Jinja détecté : " + " → ".join(cycle.paths) + ".",
                source,
                repr(cycle.key),
                global_diagnostic=True,
            )
        if closure.truncated:
            add(
                "template.analysis_truncated",
                "warning",
                f"Analyse partielle de {closure.root} : limite atteinte.",
                template.source,
                closure.root,
                template.presence == "present",
                shared=True,
                global_diagnostic=True,
            )
    if result.warnings:
        # Les limites historiques n'ont pas toutes un équivalent typé. Un résumé
        # renvoie à leur affichage intégral, sans reclasser les messages du Bridge.
        add(
            "route.partial",
            "warning",
            "Le Bridge signale des limites ou anomalies ; consulter les "
            "avertissements détaillés conservés sur cette page.",
            None,
            result.source,
            global_diagnostic=True,
        )
    return RouteDiagnostics(
        tuple(
            replace(item, route_indices=tuple(owners[index]))
            for index, item in enumerate(items)
        )
    )
