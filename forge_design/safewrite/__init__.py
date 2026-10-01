"""Anti-écrasement : détection des modifications externes et choix explicites."""

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
]
