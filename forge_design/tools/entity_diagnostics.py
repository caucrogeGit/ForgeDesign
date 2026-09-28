"""Projection pure des anomalies du Bridge, sans nouvelle validation."""

from dataclasses import dataclass
from typing import Literal

from forge_design.forge.entities import EntitiesResult, EntityIssue
from forge_design.forge.source import SourceLocation

DiagnosticSeverity = Literal["info", "warning", "error"]


@dataclass(frozen=True)
class EntityDiagnostic:
    code: str
    severity: DiagnosticSeverity
    message: str
    source: SourceLocation | None = None
    subject: str | None = None
    relation_index: int | None = None


@dataclass(frozen=True)
class EntityDiagnostics:
    items: tuple[EntityDiagnostic, ...] = ()

    @property
    def error_count(self) -> int:
        return sum(item.severity == "error" for item in self.items)

    @property
    def warning_count(self) -> int:
        return sum(item.severity == "warning" for item in self.items)

    @property
    def info_count(self) -> int:
        return sum(item.severity == "info" for item in self.items)


def build_entity_diagnostics(result: EntitiesResult) -> EntityDiagnostics:
    """Conserve chaque occurrence, erreurs puis avertissements dans leur ordre."""
    groups: tuple[tuple[DiagnosticSeverity, tuple[EntityIssue, ...]], ...] = (
        ("error", result.errors),
        ("warning", result.warnings),
    )
    return EntityDiagnostics(
        tuple(
            EntityDiagnostic(
                code=issue.code,
                severity=severity,
                message=issue.message,
                source=issue.source,
                subject=(
                    f"relations[{issue.source_index}]"
                    if issue.source_index is not None
                    else issue.source.path
                    if issue.source is not None
                    else None
                ),
                relation_index=issue.source_index,
            )
            for severity, issues in groups
            for issue in issues
        )
    )
