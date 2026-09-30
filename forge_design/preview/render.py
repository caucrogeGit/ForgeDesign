"""Rendu HTML de preview en mémoire, sans template, script ou accès projet."""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from html import escape
from typing import cast

from forge_design.design.models import DesignFile, DesignNode, PageRoot
from forge_design.limits import (
    MAX_DESIGN_DEPTH,
    MAX_DESIGN_ISSUES,
    MAX_DESIGN_NODES,
    MAX_PREVIEW_HTML_CHARS,
    MAX_TABLE_COLUMNS,
)

_TAGS = {
    "page": "div",
    "section": "section",
    "container": "div",
    "grid": "div",
    "card": "article",
    "title": "h2",
    "text": "p",
    "button": "button",
    "table": "table",
    "form": "form",
    "field": "div",
    "alert": "div",
    "empty_state": "div",
}
_SAFE_TAGS = frozenset(
    {
        "div",
        "section",
        "article",
        "header",
        "footer",
        "main",
        "aside",
        "p",
        "span",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    }
)
_CUSTOM_TAG_BLOCKS = frozenset(
    {"page", "section", "container", "grid", "card", "title", "text"}
)
_MISSING = object()


@dataclass(frozen=True)
class PreviewRenderIssue:
    code: str
    message: str
    location: tuple[str | int, ...]


@dataclass(frozen=True)
class PreviewRenderResult:
    html: str
    issues: tuple[PreviewRenderIssue, ...]
    complete: bool


class _Stopped(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason


class _Renderer:
    def __init__(self, data: Mapping[str, object]) -> None:
        self.data = data
        self.parts: list[str] = []
        self.length = 0
        self.nodes = 0
        self.issues: list[PreviewRenderIssue] = []

    def stop(self, code: str, location: tuple[str | int, ...]) -> None:
        if len(self.issues) == MAX_DESIGN_ISSUES:
            self.issues.pop()
        self.issues.append(
            PreviewRenderIssue(
                "preview." + code, "Limite du rendu de preview atteinte.", location
            )
        )
        raise _Stopped(
            "output-too-large" if code == "output_too_large" else "analysis-truncated"
        )

    def issue(self, code: str, location: tuple[str | int, ...]) -> None:
        if len(self.issues) == MAX_DESIGN_ISSUES:
            self.stop("analysis_truncated", location)
        self.issues.append(
            PreviewRenderIssue(
                "preview." + code,
                "Valeur ou propriété non rendue dans la preview.",
                location,
            )
        )

    def emit(self, text: str, location: tuple[str | int, ...]) -> None:
        if self.length + len(text) > MAX_PREVIEW_HTML_CHARS:
            self.stop("output_too_large", location)
        self.parts.append(text)
        self.length += len(text)

    def escaped(self, text: str, location: tuple[str | int, ...]) -> str:
        # Éviter l'expansion d'une chaîne déjà supérieure au budget total.
        if len(text) > MAX_PREVIEW_HTML_CHARS - self.length:
            self.stop("output_too_large", location)
        return escape(text, quote=True)

    def scalar(self, value: object, location: tuple[str | int, ...]) -> str:
        if isinstance(value, bool):
            text = "true" if value else "false"
        elif isinstance(value, str):
            text = value
        elif isinstance(value, (int, float)):
            if isinstance(value, float) and not math.isfinite(value):
                self.issue("unsupported_value", location)
                return ""
            try:
                text = str(value)
            except ValueError:
                self.issue("unsupported_value", location)
                return ""
        else:
            self.issue("unsupported_value", location)
            return ""
        return self.escaped(text, location)

    def node(
        self,
        node: DesignNode | PageRoot,
        path: tuple[str | int, ...],
        depth: int,
        *,
        selected: bool = True,
    ) -> None:
        if self.nodes >= MAX_DESIGN_NODES or depth > MAX_DESIGN_DEPTH:
            self.stop("analysis_truncated", path)
        self.nodes += 1
        if not selected:
            return
        if node.visible_if is not None:
            condition = self.data.get(node.visible_if, _MISSING)
            if condition is _MISSING:
                self.issue("missing_condition", (*path, "visible_if"))
                return
            if not isinstance(condition, bool):
                self.issue("condition_type_mismatch", (*path, "visible_if"))
                return
            if condition is False:
                return
        tag = _TAGS[node.type]
        classes = None
        if node.props is not None:
            for key, value in node.props.items():
                location = (*path, "props", key)
                if key == "tag" and isinstance(value, str):
                    if value not in _SAFE_TAGS:
                        self.issue("invalid_tag", location)
                    elif node.type not in _CUSTOM_TAG_BLOCKS:
                        self.issue("unsupported_prop", location)
                    else:
                        tag = value
                elif key == "class" and isinstance(value, str):
                    classes = value
                else:
                    self.issue("unsupported_prop", location)
        self.emit("<" + tag + ' data-forge-design-type="' + node.type + '"', path)
        if path == ("root",):
            self.emit(' data-forge-design-preview="page"', path)
        if node.type == "button":
            self.emit(' type="button"', path)
        if classes is not None:
            self.emit(
                ' class="' + self.escaped(classes, (*path, "props", "class")) + '"',
                path,
            )
        self.emit(">", path)
        empty = False
        if node.type in {"text", "title"} and node.binding is not None:
            value = self.data.get(node.binding, _MISSING)
            if value is _MISSING:
                self.issue("missing_value", (*path, "binding"))
            else:
                self.emit(self.scalar(value, (*path, "binding")), path)
        elif node.type == "button":
            self.emit("Action", path)
        elif node.type == "empty_state":
            self.emit("Aucune donnée", path)
        elif node.type == "table":
            empty = self.table(node, path)
        if node.type != "table" and node.children:
            for index, child in enumerate(node.children):
                self.node(child, (*path, "children", index), depth + 1)
        self.emit("</" + tag + ">", path)
        if node.type == "table" and empty and node.children:
            # Les div d'état vide sont des frères, pas des enfants HTML de table.
            for index, child in enumerate(node.children):
                self.node(
                    child,
                    (*path, "children", index),
                    depth + 1,
                    selected=child.type == "empty_state",
                )

    def table(self, node: DesignNode | PageRoot, path: tuple[str | int, ...]) -> bool:
        rows: list[object] = []
        if node.binding is not None:
            value = self.data.get(node.binding, _MISSING)
            if value is _MISSING:
                self.issue("missing_value", (*path, "binding"))
            elif not isinstance(value, list):
                self.issue("table_type_mismatch", (*path, "binding"))
            else:
                rows = cast(list[object], value)
        self.emit("<thead><tr>", path)
        columns = node.columns or []
        for index, column in enumerate(columns):
            location = (*path, "columns", index, "label")
            if index >= MAX_TABLE_COLUMNS:
                self.stop("analysis_truncated", location)
            self.emit("<th>" + self.escaped(column.label, location) + "</th>", location)
        self.emit("</tr></thead><tbody>", path)
        for row_index, row in enumerate(rows):
            row_path = (*path, "rows", row_index)
            self.emit("<tr>", row_path)
            if not isinstance(row, dict):
                self.issue("row_type_mismatch", row_path)
            for column_index, column in enumerate(columns):
                cell_path = (*row_path, "columns", column_index, "binding")
                text = ""
                if isinstance(row, dict):
                    value = cast(dict[object, object], row).get(
                        column.binding, _MISSING
                    )
                    if value is _MISSING:
                        self.issue("missing_field", cell_path)
                    else:
                        text = self.scalar(value, cell_path)
                self.emit("<td>" + text + "</td>", cell_path)
            self.emit("</tr>", row_path)
        self.emit("</tbody>", path)
        return not rows


def render_preview(
    design: DesignFile, data: Mapping[str, object]
) -> PreviewRenderResult:
    renderer = _Renderer(data)
    try:
        renderer.node(design.root, ("root",), 0)
    except _Stopped as stopped:
        html = '<div data-forge-design-preview-error="' + stopped.reason + '"></div>'
    else:
        html = "".join(renderer.parts)
    return PreviewRenderResult(
        html, tuple(renderer.issues), complete=not renderer.issues
    )
