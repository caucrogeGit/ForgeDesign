"""Génération interne des tables depuis la projection de validation existante."""

from typing import Never, Protocol

from forge_design.design.models import DesignNode, PageRoot
from forge_design.design.table_bindings import TableBindingInfo
from forge_design.generate.control_flow import (
    is_safe_jinja_identifier,
    jinja_condition,
    render_jinja_loop,
)

Location = tuple[str | int, ...]


class TableWriter(Protocol):
    def issue(self, code: str, location: Location) -> None: ...
    def stop(self, code: str, location: Location) -> Never: ...
    def line(self, content: str, depth: int, path: Location) -> None: ...
    def escaped(self, value: str, path: Location) -> str: ...
    def check_size(self, size: int, path: Location) -> None: ...


def prepare_table(
    node: DesignNode | PageRoot,
    info: TableBindingInfo,
    writer: TableWriter,
) -> bool:
    """Vérifier les contraintes de génération sans résoudre à nouveau le contrat."""
    path = info.location
    if info.status == "no_binding":
        writer.issue("table_missing_binding", (*path, "binding"))
        return False
    if info.status in {"unresolved_variable", "type_mismatch"}:
        writer.issue("invalid_table_binding", (*path, "binding"))
        return False
    if info.status == "fields_unavailable" and info.columns:
        writer.issue("invalid_table_binding", (*path, "columns"))
        return False
    assert info.binding is not None
    if not is_safe_jinja_identifier(info.binding):
        writer.issue("unsupported_binding_syntax", (*path, "binding"))
        return False
    valid = True
    for column in info.columns:
        location = (*path, "columns", column.index, "binding")
        if column.valid is False:
            writer.issue("invalid_table_column", location)
            valid = False
        elif not is_safe_jinja_identifier(column.binding):
            writer.issue("unsupported_field_syntax", location)
            valid = False
    if info.has_empty_state:
        children = node.children or []
        # Nesting validé : tous les enfants directs sont des empty_state.
        if len(children) > 1:
            writer.issue("multiple_empty_states", (*path, "children"))
            valid = False
        elif children[0].visible_if is not None:
            writer.issue(
                "unsupported_empty_state_condition",
                (*path, "children", 0, "visible_if"),
            )
            valid = False
    return valid


def class_attribute(
    node: DesignNode | PageRoot, path: Location, writer: TableWriter
) -> str:
    result = ""
    for key, value in (node.props or {}).items():
        location = (*path, "props", key)
        if key == "class" and isinstance(value, str):
            result = ' class="' + writer.escaped(value, location) + '"'
        else:
            writer.issue("unsupported_prop", location)
    return result


def render_table(
    node: DesignNode | PageRoot,
    info: TableBindingInfo,
    depth: int,
    writer: TableWriter,
) -> None:
    """Émettre une table préparée ; tous les caractères passent par le budget commun."""
    path = info.location
    assert info.binding is not None
    outer_depth = depth
    if info.has_empty_state:
        writer.line(jinja_condition(info.binding), depth, path)
        depth += 1
    classes = class_attribute(node, path, writer)
    writer.line("<table" + classes + ">", depth, path)
    writer.line("<thead>", depth + 1, path)
    writer.line("<tr>", depth + 2, path)
    for column in info.columns:
        location = (*path, "columns", column.index, "label")
        label = writer.escaped(column.label, location)
        writer.line("<th>" + label + "</th>", depth + 3, location)
    writer.line("</tr>", depth + 2, path)
    writer.line("</thead>", depth + 1, path)
    writer.line("<tbody>", depth + 1, path)
    body = ["<tr>"]
    size = len(body[0])
    for column in info.columns:
        location = (*path, "columns", column.index, "binding")
        size += len(column.binding) + len("  <td>{{ item. }}</td>")
        writer.check_size(size, location)
        body.append("  <td>{{ item." + column.binding + " }}</td>")
    body.append("</tr>")
    for line in render_jinja_loop(
        collection=info.binding, item="item", body=tuple(body)
    ):
        writer.line(line, depth + 2, path)
    writer.line("</tbody>", depth + 1, path)
    writer.line("</table>", depth, path)
    if info.has_empty_state:
        writer.line("{% else %}", outer_depth, path)
        assert node.children
        child = node.children[0]
        location = (*path, "children", 0)
        classes = class_attribute(child, location, writer)
        writer.line("<div" + classes + ">Aucune donnée</div>", depth, location)
        writer.line("{% endif %}", outer_depth, path)
