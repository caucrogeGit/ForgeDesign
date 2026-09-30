"""Génération de templates en mémoire, sans écriture projet."""

from forge_design.generate.diff import (
    TemplateDiffIssue,
    TemplateDiffResult,
    build_template_diff,
)
from forge_design.generate.simple import (
    TemplateGenerationIssue,
    TemplateGenerationResult,
    generate_simple_template,
)

__all__ = [
    "TemplateDiffIssue",
    "TemplateDiffResult",
    "build_template_diff",
    "TemplateGenerationIssue",
    "TemplateGenerationResult",
    "generate_simple_template",
]
