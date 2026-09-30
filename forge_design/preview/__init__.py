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
from forge_design.preview.responsive import (
    PREVIEW_VIEWPORTS,
    PreviewViewport,
    PreviewViewportMode,
    ResponsivePreviewResult,
    preview_viewport,
    render_responsive_preview,
    wrap_preview_html,
)

__all__ = [
    "PreviewDataIssue",
    "PreviewDataResult",
    "generate_preview_data",
    "PreviewRenderIssue",
    "PreviewRenderResult",
    "render_preview",
    "PREVIEW_VIEWPORTS",
    "PreviewViewport",
    "PreviewViewportMode",
    "ResponsivePreviewResult",
    "preview_viewport",
    "render_responsive_preview",
    "wrap_preview_html",
]
