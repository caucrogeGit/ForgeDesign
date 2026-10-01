"""Anti-écrasement : détection des modifications externes, sans écriture."""

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
]
