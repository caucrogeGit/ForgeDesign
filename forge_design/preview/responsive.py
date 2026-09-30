"""Enveloppes de largeur indicative, sans navigateur ni interprétation CSS."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from forge_design.design.models import DesignFile
from forge_design.preview.render import PreviewRenderIssue, render_preview

PreviewViewportMode = Literal["desktop", "tablet", "mobile"]


@dataclass(frozen=True)
class PreviewViewport:
    mode: PreviewViewportMode
    width_px: int


PREVIEW_VIEWPORTS: Mapping[PreviewViewportMode, PreviewViewport] = MappingProxyType(
    {
        "desktop": PreviewViewport("desktop", 1440),
        "tablet": PreviewViewport("tablet", 768),
        "mobile": PreviewViewport("mobile", 390),
    }
)


@dataclass(frozen=True)
class ResponsivePreviewResult:
    mode: PreviewViewportMode
    width_px: int
    html: str
    issues: tuple[PreviewRenderIssue, ...]
    complete: bool


def preview_viewport(mode: PreviewViewportMode) -> PreviewViewport:
    """Retourner un preset interne ; refuser tout mode runtime inconnu."""
    if mode not in ("desktop", "tablet", "mobile"):
        raise ValueError("Mode de preview inconnu : desktop, tablet ou mobile attendu.")
    return PREVIEW_VIEWPORTS[mode]


def wrap_preview_html(html: str, *, mode: PreviewViewportMode) -> str:
    """Envelopper un fragment contrôlé, sans l'assainir ni le réinterpréter."""
    viewport = preview_viewport(mode)
    return (
        f'<div data-forge-design-responsive="{viewport.mode}" '
        f'data-forge-design-width="{viewport.width_px}" '
        f'style="width:{viewport.width_px}px;max-width:100%;margin:0 auto;">'
        + html
        + "</div>"
    )


def render_responsive_preview(
    design: DesignFile,
    data: Mapping[str, object],
    *,
    mode: PreviewViewportMode,
) -> ResponsivePreviewResult:
    """Composer une fois le renderer local avec un preset validé."""
    viewport = preview_viewport(mode)
    rendered = render_preview(design, data)
    return ResponsivePreviewResult(
        mode=viewport.mode,
        width_px=viewport.width_px,
        html=wrap_preview_html(rendered.html, mode=viewport.mode),
        issues=rendered.issues,
        complete=rendered.complete,
    )
