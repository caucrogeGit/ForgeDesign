"""Composition responsive : presets, conservation du rendu et pureté."""

import builtins
import copy
import os
import socket
import subprocess
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest
from test_design_bindings import contract, design
from test_preview_render import Parsed, fixture

from forge_design.preview import (
    PREVIEW_VIEWPORTS,
    PreviewViewport,
    PreviewViewportMode,
    generate_preview_data,
    preview_viewport,
    render_preview,
    render_responsive_preview,
    responsive,
    wrap_preview_html,
)

MODES: tuple[PreviewViewportMode, ...] = ("desktop", "tablet", "mobile")


@pytest.mark.parametrize(
    "mode,width", [("desktop", 1440), ("tablet", 768), ("mobile", 390)]
)
def test_presets_and_minimal(mode: PreviewViewportMode, width: int) -> None:
    viewport = preview_viewport(mode)
    assert viewport is PREVIEW_VIEWPORTS[mode]
    assert viewport == PreviewViewport(mode, width)
    model = design([])
    fragment = render_preview(model, {}).html
    result = render_responsive_preview(model, {}, mode=mode)
    assert result.mode == mode and result.width_px == width
    assert result.complete and result.issues == ()
    parsed = Parsed(result.html)
    assert parsed.tags[0] == (
        "div",
        {
            "data-forge-design-responsive": mode,
            "data-forge-design-width": str(width),
            "style": f"width:{width}px;max-width:100%;margin:0 auto;",
        },
    )
    assert result.html.split(">", 1)[1][:-6] == fragment
    assert result.html == wrap_preview_html(fragment, mode=mode)
    assert result == render_responsive_preview(model, {}, mode=mode)


def test_presets_and_results_immutable() -> None:
    assert tuple(PREVIEW_VIEWPORTS) == MODES
    with pytest.raises(TypeError):
        PREVIEW_VIEWPORTS["mobile"] = PreviewViewport("mobile", 1)  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        preview_viewport("mobile").width_px = 1  # type: ignore[misc]
    result = render_responsive_preview(design([]), {}, mode="mobile")
    with pytest.raises(FrozenInstanceError):
        result.complete = False  # type: ignore[misc]


@pytest.mark.parametrize(
    "invalid", ["", "Desktop", "phone", '"><script>x</script>', None, []]
)
def test_invalid_mode_rejected_before_render(
    invalid: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("renderer called for invalid mode")

    monkeypatch.setattr(responsive, "render_preview", forbidden)
    for call in (
        lambda: preview_viewport(invalid),
        lambda: wrap_preview_html("fragment", mode=invalid),
        lambda: render_responsive_preview(design([]), {}, mode=invalid),
    ):
        with pytest.raises(
            ValueError,
            match="^Mode de preview inconnu : desktop, tablet ou mobile attendu.$",
        ):
            call()


@pytest.mark.parametrize("mode", MODES)
def test_contacts_and_conditions(mode: PreviewViewportMode) -> None:
    model = fixture("contacts-list")
    data = generate_preview_data(
        contract(
            {
                "page_title": {"type": "string"},
                "contacts": {
                    "type": "list",
                    "fields": {
                        "nom": "string",
                        "email": "email",
                        "telephone": "string",
                    },
                },
            }
        )
    ).data
    fragment = render_preview(model, data)
    result = render_responsive_preview(model, data, mode=mode)
    assert result.complete
    assert result.html == wrap_preview_html(fragment.html, mode=mode)
    assert result.html.split("<tbody>")[1].count("<tr>") == 3
    assert result.html.count("contact@example.test") == 3
    for visible in (True, False):
        conditional = render_responsive_preview(
            fixture("conditional"),
            {"can_create": visible},
            mode=mode,
        )
        assert conditional.complete
        assert ("<button " in conditional.html) is visible


def test_hostile_content_and_exact_fragment() -> None:
    hostile = '<script>alert(1)</script> & "'
    model = design(
        [{"type": "text", "binding": "x", "props": {"class": "md:grid-cols-2"}}]
    )
    fragment = render_preview(model, {"x": hostile})
    for mode in MODES:
        result = wrap_preview_html(fragment.html, mode=mode)
        parsed = Parsed(result)
        assert not any(tag == "script" for tag, _ in parsed.tags)
        assert parsed.text == [hostile]
        assert result.split(">", 1)[1][:-6] == fragment.html
        assert "md:grid-cols-2" in result
    # Primitive de composition, pas un assainisseur de HTML arbitraire.
    assert wrap_preview_html("", mode="mobile").endswith("></div>")


@pytest.mark.parametrize("overflow", [False, True])
def test_diagnostics_exact_and_single_composition(
    overflow: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = design([{"type": "text", "binding": "x"}])
    data: dict[str, object] = {"x": "x" * 1_000_001} if overflow else {}
    rendered = render_preview(model, data)
    assert not rendered.complete
    assert rendered.issues[0].code == (
        "preview.output_too_large" if overflow else "preview.missing_value"
    )
    calls: list[bool] = []

    def recorded(given_design: Any, given_data: Any) -> Any:
        assert given_design is model and given_data is data
        calls.append(True)
        return rendered

    monkeypatch.setattr(responsive, "render_preview", recorded)
    for mode in MODES:
        result = render_responsive_preview(model, data, mode=mode)
        assert result.issues is rendered.issues
        assert result.complete is rendered.complete
        assert result.html == wrap_preview_html(rendered.html, mode=mode)
    assert len(calls) == 3


def test_purity_and_nonmutation(monkeypatch: pytest.MonkeyPatch) -> None:
    model = fixture("contacts-list")
    data: dict[str, object] = {
        "page_title": "Test",
        "contacts": [
            {"nom": "Exemple", "email": "contact@example.test", "telephone": "Exemple"},
        ],
    }
    before = copy.deepcopy((model.model_dump(), data))
    rows = data["contacts"]
    children = model.root.children

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("external access")

    with monkeypatch.context() as patch:
        for owner, name in (
            (builtins, "open"),
            (os, "open"),
            (Path, "open"),
            (Path, "read_text"),
            (Path, "read_bytes"),
            (socket, "socket"),
            (subprocess, "run"),
        ):
            patch.setattr(owner, name, forbidden)
        for mode in MODES:
            result = render_responsive_preview(model, MappingProxyType(data), mode=mode)
            assert result == render_responsive_preview(model, data, mode=mode)
    assert before == (model.model_dump(), data)
    assert data["contacts"] is rows and model.root.children is children
