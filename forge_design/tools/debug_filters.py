"""Projection pure de la liste runtime, sur les seuls textes déjà masqués."""

from dataclasses import dataclass
from datetime import datetime

from forge_design.forge.debug_errors import DebugError, DebugErrorsResult, DebugIssue
from forge_design.limits import MAX_FILTER_QUERY_LENGTH

LEVELS = ("all", "ERROR", "WARNING", "INFO", "CRITICAL")
CATEGORIES = (
    "all",
    "runtime",
    "controller",
    "routing",
    "template",
    "database",
    "configuration",
    "http",
    "unknown",
)


@dataclass(frozen=True)
class DebugFilter:
    query: str | None = None
    level: str = "all"
    category: str = "all"
    order: str = "newest"

    def __post_init__(self) -> None:
        if self.query is not None and len(self.query) > MAX_FILTER_QUERY_LENGTH:
            raise ValueError("Recherche limitée à 256 caractères.")
        query = (self.query or "").strip().casefold() or None
        if query is not None and len(query) > MAX_FILTER_QUERY_LENGTH:
            raise ValueError("Recherche normalisée limitée à 256 caractères.")
        if self.level not in LEVELS:
            raise ValueError("Niveau invalide.")
        if self.category not in CATEGORIES:
            raise ValueError("Catégorie invalide.")
        if self.order not in ("newest", "oldest"):
            raise ValueError("Ordre invalide.")
        object.__setattr__(self, "query", query)


@dataclass(frozen=True)
class DebugFilteredView:
    events: tuple[DebugError, ...]
    issues: tuple[DebugIssue, ...]
    total_events: int


def _timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.utcoffset() is not None else None
    except (ValueError, OverflowError):
        return None


def _matches(event: DebugError, query: str | None) -> bool:
    if query is None:
        return True
    values = (
        event.id,
        event.exception_type,
        event.message,
        event.route,
        event.controller,
        event.template,
        event.hint,
        event.correlation_id,
    )
    if event.request is not None:
        values += (event.request.method, event.request.path)
    return any(query in value.casefold() for value in values if value is not None)


def filter_debug_events(
    result: DebugErrorsResult, filters: DebugFilter
) -> DebugFilteredView:
    """Tri stable des dates zonées, puis dates non interprétables en ordre physique."""
    dated: list[tuple[datetime, DebugError]] = []
    undated: list[DebugError] = []
    for event in result.events:
        if filters.level != "all" and event.level != filters.level:
            continue
        if filters.category != "all" and event.category != filters.category:
            continue
        if not _matches(event, filters.query):
            continue
        timestamp = _timestamp(event.timestamp)
        if timestamp is None:
            undated.append(event)
        else:
            dated.append((timestamp, event))
    dated.sort(key=lambda item: item[0], reverse=filters.order == "newest")
    return DebugFilteredView(
        tuple(event for _, event in dated) + tuple(undated),
        result.issues,
        len(result.events),
    )
