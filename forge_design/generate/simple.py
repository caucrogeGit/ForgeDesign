"""Génération HTML/Jinja simple après revalidation, sans moteur de templates."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from html import escape
from typing import Never

from pydantic import ValidationError

from forge_design.contracts.models import ViewAction, ViewContract
from forge_design.design.bindings import validate_design_bindings
from forge_design.design.conditional_bindings import validate_conditional_bindings
from forge_design.design.form_fields import validate_form_fields
from forge_design.design.models import DesignFile, DesignNode, PageRoot
from forge_design.design.nesting import validate_design_nesting
from forge_design.design.submit_buttons import validate_submit_buttons
from forge_design.design.table_bindings import TableBindingInfo, validate_table_bindings
from forge_design.generate.buttons import ButtonPlan, prepare_button, render_button
from forge_design.generate.control_flow import (
    indent_line,
    is_safe_jinja_identifier,
    jinja_condition,
)
from forge_design.generate.forms import (
    FieldPlan,
    FormPlan,
    prepare_field,
    prepare_form,
    render_field,
    render_form_close,
    render_form_open,
)
from forge_design.generate.tables import prepare_table, render_table
from forge_design.limits import (
    MAX_DESIGN_DEPTH,
    MAX_DESIGN_ISSUES,
    MAX_DESIGN_NODES,
    MAX_GENERATED_TEMPLATE_CHARS,
)

_TAGS = {
    "section": "section",
    "container": "div",
    "grid": "div",
    "card": "article",
    "title": "h2",
    "text": "p",
}
# Blocs générés par un module dédié, hors balise simple de _TAGS.
_INTERACTIVE = frozenset({"page", "table", "button", "form", "field"})
_SAFE_TAGS = frozenset(
    (
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
    )
)


@dataclass(frozen=True)
class TemplateGenerationIssue:
    code: str
    message: str
    location: tuple[str | int, ...]


@dataclass(frozen=True)
class TemplateGenerationResult:
    template: str
    issues: tuple[TemplateGenerationIssue, ...]
    complete: bool


class _Stopped(Exception):
    pass


class _Generator:
    def __init__(self) -> None:
        self.issues: list[TemplateGenerationIssue] = []
        self.lines: list[str] = []
        self.length = 0
        self.tables: dict[tuple[str | int, ...], TableBindingInfo] = {}
        self.actions: Mapping[str, ViewAction] = {}
        self.buttons: dict[tuple[str | int, ...], ButtonPlan] = {}
        self.forms: dict[tuple[str | int, ...], FormPlan] = {}
        self.fields: dict[tuple[str | int, ...], FieldPlan] = {}

    def issue(self, code: str, location: tuple[str | int, ...]) -> None:
        if len(self.issues) >= MAX_DESIGN_ISSUES:
            self.issues[-1] = TemplateGenerationIssue(
                "generate.analysis_truncated",
                "Limite de diagnostics atteinte.",
                location,
            )
            raise _Stopped
        self.issues.append(
            TemplateGenerationIssue(
                "generate." + code, "Génération limitée : " + code + ".", location
            )
        )

    def stop(self, code: str, location: tuple[str | int, ...]) -> Never:
        self.issue(code, location)
        raise _Stopped

    def preflight(self, design: DesignFile) -> None:
        # Avant model_dump : borner les arbres mutés, cycles compris.
        stack: list[tuple[Iterator[tuple[int, object]], tuple[str | int, ...], int]] = [
            (iter(enumerate((design.root,))), (), 0)
        ]
        count = 0
        while stack:
            iterator, parent, depth = stack[-1]
            entry = next(iterator, None)
            if entry is None:
                stack.pop()
                continue
            index, node = entry
            path = (*parent, "children", index) if parent else ("root",)
            if count >= MAX_DESIGN_NODES or depth > MAX_DESIGN_DEPTH:
                self.stop("analysis_truncated", path)
            count += 1
            if not isinstance(node, (DesignNode, PageRoot)):
                self.stop("invalid_design", path)
            if node.children:
                stack.append((iter(enumerate(node.children)), path, depth + 1))

    def check_size(self, size: int, path: tuple[str | int, ...]) -> None:
        if self.length + size > MAX_GENERATED_TEMPLATE_CHARS:
            self.stop("output_too_large", path)

    def escaped(self, value: str, path: tuple[str | int, ...]) -> str:
        self.check_size(len(value), path)
        return (
            escape(value, quote=True)
            .replace("{", "&#123;")
            .replace("}", "&#125;")
            .replace("\r", "&#13;")
            .replace("\n", "&#10;")
        )

    def line(self, content: str, depth: int, path: tuple[str | int, ...]) -> None:
        length = depth * 2 + len(content) + 1
        if self.length + length > MAX_GENERATED_TEMPLATE_CHARS:
            self.stop("output_too_large", path)
        self.lines.append(indent_line(content, depth) + "\n")
        self.length += length

    def node(
        self, node: DesignNode | PageRoot, path: tuple[str | int, ...], depth: int
    ) -> None:
        if node.type not in _INTERACTIVE and node.type not in _TAGS:
            self.issue("unsupported_block", path)
            return
        if node.type == "table" and not prepare_table(node, self.tables[path], self):
            return
        if node.type == "button":
            # Préparé avant toute émission, condition comprise.
            plan = prepare_button(node, path, self.actions, self)
            if plan is None:
                return
            self.buttons[path] = plan
        if node.type == "form":
            # Balise entière préparée : un formulaire omis l'est avec son sous-arbre.
            form = prepare_form(node, path, self.actions, self)
            if form is None:
                return
            self.forms[path] = form
        if node.type == "field":
            self.fields[path] = prepare_field(node, path, self)
        condition = node.visible_if
        if condition is not None:
            if not is_safe_jinja_identifier(condition):
                self.issue("unsupported_condition_syntax", (*path, "visible_if"))
                return
            self.line(jinja_condition(condition), depth, path)
            self.node_content(node, path, depth + 1)
            self.line("{% endif %}", depth, path)
        else:
            self.node_content(node, path, depth)

    def node_content(
        self, node: DesignNode | PageRoot, path: tuple[str | int, ...], depth: int
    ) -> None:
        if node.type == "table":
            render_table(node, self.tables[path], depth, self)
            return
        if node.type == "button":
            render_button(self.buttons[path], depth, path, self)
            return
        if node.type == "field":
            render_field(self.fields[path], depth, path, self)
            return
        if node.type == "form":
            children = node.children or []
            render_form_open(self.forms[path], depth, path, self, empty=not children)
            if children:
                for index, child in enumerate(children):
                    self.node(child, (*path, "children", index), depth + 1)
                render_form_close(depth, path, self)
            return
        tag = _TAGS.get(node.type, "")
        classes = ""
        for key, value in (node.props or {}).items():
            location = (*path, "props", key)
            if node.type == "page":
                self.issue("unsupported_prop", location)
            elif key == "tag" and isinstance(value, str):
                if value in _SAFE_TAGS:
                    tag = value
                else:
                    self.issue("invalid_tag", location)
            elif key == "class" and isinstance(value, str):
                safe = self.escaped(value, location)
                classes = ' class="' + safe + '"'
            else:
                self.issue("unsupported_prop", location)
        if node.type == "page":
            for index, child in enumerate(node.children or []):
                self.node(child, (*path, "children", index), depth)
            return
        if node.type in {"title", "text"}:
            text = ""
            if node.binding is not None:
                if is_safe_jinja_identifier(node.binding):
                    text = "{{ " + node.binding + " }}"
                else:
                    self.issue("unsupported_binding_syntax", (*path, "binding"))
            self.line("<" + tag + classes + ">" + text + "</" + tag + ">", depth, path)
        elif not node.children:
            self.line("<" + tag + classes + "></" + tag + ">", depth, path)
        else:
            self.line("<" + tag + classes + ">", depth, path)
            for index, child in enumerate(node.children):
                self.node(child, (*path, "children", index), depth + 1)
            self.line("</" + tag + ">", depth, path)


def generate_simple_template(
    design: DesignFile, contract: ViewContract
) -> TemplateGenerationResult:
    generator = _Generator()
    try:
        generator.preflight(design)
        try:
            design = DesignFile.model_validate(design.model_dump(exclude_unset=True))
        except (ValidationError, ValueError, RecursionError):
            generator.stop("invalid_design", ())
        try:
            contract = ViewContract.model_validate(
                contract.model_dump(exclude_unset=True)
            )
        except (ValidationError, ValueError, RecursionError):
            generator.stop("invalid_contract", ())
        nesting = validate_design_nesting(design)
        if not nesting.valid:
            for issue in nesting.issues:
                generator.issue(
                    "analysis_truncated"
                    if issue.code.endswith("analysis_truncated")
                    else "invalid_nesting",
                    issue.path,
                )
            raise _Stopped
        bindings = validate_design_bindings(design, contract)
        if bindings.truncated:
            generator.stop("analysis_truncated", bindings.issues[-1].location)
        # Binding nécessaire à la génération : texte, titre, actions bouton et form.
        invalid = [
            issue
            for issue in bindings.issues
            if issue.node_type in {"title", "text", "button", "form"}
        ]
        if invalid:
            for issue in invalid:
                generator.issue("invalid_binding", issue.location)
            raise _Stopped
        conditions = validate_conditional_bindings(design, contract)
        if conditions.truncated:
            generator.stop("analysis_truncated", conditions.issues[-1].location)
        condition_errors = [
            issue for issue in conditions.issues if issue.node_type != "empty_state"
        ]
        if condition_errors:
            for issue in condition_errors:
                generator.issue(
                    "analysis_truncated"
                    if issue.code.endswith("analysis_truncated")
                    else "invalid_condition",
                    issue.location,
                )
            raise _Stopped
        fields = validate_form_fields(design)
        if fields.truncated:
            generator.stop("analysis_truncated", fields.issues[-1].location)
        if fields.issues:
            # Validateur de design/ réutilisé, sans recopie de ses règles.
            for issue in fields.issues:
                generator.issue(
                    "duplicate_field_name"
                    if issue.code == "design.field.duplicate_name"
                    else "invalid_field",
                    issue.location,
                )
            raise _Stopped
        submits = validate_submit_buttons(design)
        if submits.truncated:
            generator.stop("analysis_truncated", submits.issues[-1].location)
        if submits.issues:
            # Validateur de design/ réutilisé : sémantique du bouton ambiguë.
            for issue in submits.issues:
                generator.issue("invalid_submit", issue.location)
            raise _Stopped
        tables = validate_table_bindings(design, contract)
        if tables.truncated:
            generator.stop("analysis_truncated", tables.issues[-1].location)
        generator.tables = {table.location: table for table in tables.tables}
        generator.actions = contract.actions or {}
        generator.node(design.root, ("root",), 0)
    except _Stopped:
        template = ""
    else:
        template = "".join(generator.lines)
    return TemplateGenerationResult(
        template, tuple(generator.issues), not generator.issues
    )
