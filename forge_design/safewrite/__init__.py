"""Anti-écrasement : détection, choix explicite et écriture contrôlée."""

from forge_design.safewrite.decision import (
    SafeWriteChoice,
    SafeWriteDecision,
    SafeWriteDecisionOptions,
    decision_options,
    has_write_conflict,
    select_safe_write_choice,
)
from forge_design.safewrite.detection import (
    TemplateChangeResult,
    TemplateChangeStatus,
    TemplateRevision,
    TemplateSnapshot,
    TemplateSnapshotError,
    compare_template_snapshots,
    detect_template_change,
    snapshot_template,
)
from forge_design.safewrite.writer import (
    TemplateHistoryError,
    TemplatePublication,
    TemplatePublishedError,
    TemplateWriteConflictError,
    TemplateWriteError,
    TemplateWriteResult,
    write_generated_template,
)

__all__ = [
    "TemplateRevision",
    "TemplateSnapshot",
    "TemplateChangeStatus",
    "TemplateChangeResult",
    "TemplateSnapshotError",
    "compare_template_snapshots",
    "snapshot_template",
    "detect_template_change",
    "SafeWriteChoice",
    "SafeWriteDecisionOptions",
    "SafeWriteDecision",
    "decision_options",
    "select_safe_write_choice",
    "has_write_conflict",
    "TemplatePublication",
    "TemplateWriteResult",
    "TemplateWriteError",
    "TemplateWriteConflictError",
    "TemplatePublishedError",
    "TemplateHistoryError",
    "write_generated_template",
]
