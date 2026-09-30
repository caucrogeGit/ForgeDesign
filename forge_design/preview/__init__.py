"""Données fictives et rendu HTML local, sans exécution du backend."""

from forge_design.preview.data import (
    PreviewDataIssue,
    PreviewDataResult,
    generate_preview_data,
)
from forge_design.preview.render import (
    PreviewRenderIssue,
    PreviewRenderResult,
    render_preview,
)

__all__ = [
    "PreviewDataIssue",
    "PreviewDataResult",
    "generate_preview_data",
    "PreviewRenderIssue",
    "PreviewRenderResult",
    "render_preview",
]
