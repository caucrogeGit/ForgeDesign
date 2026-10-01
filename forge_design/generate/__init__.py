"""Génération et diff en mémoire, journal explicite des écritures réussies."""

from forge_design.generate.diff import (
    TemplateDiffIssue,
    TemplateDiffResult,
    build_template_diff,
)
from forge_design.generate.history import (
    HISTORY_FORMAT_VERSION,
    GenerationHistoryEvent,
    HistoryAction,
    append_generation_history,
)
from forge_design.generate.simple import (
    TemplateGenerationIssue,
    TemplateGenerationResult,
    generate_simple_template,
)

__all__ = [
    "HISTORY_FORMAT_VERSION",
    "HistoryAction",
    "GenerationHistoryEvent",
    "append_generation_history",
    "TemplateDiffIssue",
    "TemplateDiffResult",
    "build_template_diff",
    "TemplateGenerationIssue",
    "TemplateGenerationResult",
    "generate_simple_template",
]
