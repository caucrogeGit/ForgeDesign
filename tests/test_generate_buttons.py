"""Boutons HTMX générés : action du contrat, props en liste blanche, échappement."""

import builtins
import copy
import os
import socket
import subprocess
from typing import Any

import pytest
from jinja2 import Environment, nodes
from test_design_bindings import contract, design

from forge_design.contracts.models import ViewContract
from forge_design.design.models import DesignFile
from forge_design.generate import buttons, generate_simple_template, simple
from forge_design.limits import MAX_GENERATED_TEMPLATE_CHARS

ACTIONS = {
    "create": {"method": "GET", "path": "/contacts/create"},
    "store": {"method": "POST", "path": "/contacts"},
    "store_open": {"method": "POST", "path": "/contacts", "csrf": False},
    "store_csrf": {"method": "POST", "path": "/contacts", "csrf": True},
    "show_csrf": {"method": "GET", "path": "/contacts/1", "csrf": True},
    "update": {"method": "PUT", "path": "/contacts/1"},
    "patch": {"method": "PATCH", "path": "/contacts/1"},
    "destroy": {"method": "DELETE", "path": "/contacts/1"},
    "head": {"method": "HEAD", "path": "/contacts"},
}


def with_button(button: dict[str, Any], **container: Any) -> DesignFile:
    holder = {"type": "container", "children": [button], **container}
    return design([{"type": "section", "children": [holder]}])


def make_contract(
    actions: dict[str, Any] | None = None, context: dict[str, Any] | None = None
) -> ViewContract:
    return contract(context or {}, actions=ACTIONS if actions is None else actions)


def generate(
    button: dict[str, Any], contract_model: ViewContract | None = None
) -> simple.TemplateGenerationResult:
    return generate_simple_template(
        with_button(button), contract_model or make_contract()
    )


def button_line(result: simple.TemplateGenerationResult) -> str:
    (line,) = [
        line.strip() for line in result.template.splitlines() if "<button" in line
    ]
    return line


def codes(result: simple.TemplateGenerationResult) -> list[str]:
    return [issue.code.removeprefix("generate.") for issue in result.issues]


# Nominal.


def test_get_exact_template() -> None:
    result = generate({"type": "button", "binding": "create"})
    assert result.complete and result.issues == ()
    assert result.template == (
        "<section>\n"
        "  <div>\n"
        '    <button type="button" hx-get="/contacts/create">Action</button>\n'
        "  </div>\n"
        "</section>\n"
    )
    Environment().parse(result.template)


@pytest.mark.parametrize("binding", ["store", "store_open"])
def test_post(binding: str) -> None:
    result = generate({"type": "button", "binding": binding})
    assert result.complete
    assert button_line(result) == (
        '<button type="button" hx-post="/contacts">Action</button>'
    )


def test_get_with_csrf_true_generated_without_token() -> None:
    result = generate({"type": "button", "binding": "show_csrf"})
    assert result.complete
    assert button_line(result) == (
        '<button type="button" hx-get="/contacts/1">Action</button>'
    )


def test_full_props_fixed_order() -> None:
    props = {
        "hx-confirm": "Confirmer ?",
        "hx-swap": "outerHTML",
        "class": "px-4 py-2 rounded",
        "hx-target": "#main",
    }
    result = generate({"type": "button", "binding": "create", "props": props})
    assert result.complete
    assert button_line(result) == (
        '<button type="button" class="px-4 py-2 rounded" hx-get="/contacts/create"'
        ' hx-target="#main" hx-swap="outerHTML" hx-confirm="Confirmer ?">'
        "Action</button>"
    )


def test_end_criterion() -> None:
    props = {"class": "px-4 py-2", "hx-target": "#content", "hx-swap": "outerHTML"}
    result = generate({"type": "button", "binding": "create", "props": props})
    assert button_line(result) == (
        '<button type="button" class="px-4 py-2" hx-get="/contacts/create"'
        ' hx-target="#content" hx-swap="outerHTML">Action</button>'
    )


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("hx-target", "#content"),
        ("hx-target", "closest tr"),
        ("hx-target", "this"),
        ("hx-swap", "innerHTML"),
        ("hx-swap", "beforeend swap:1s"),
        ("hx-swap", "none"),
        ("hx-confirm", "Supprimer « tout » ?"),
    ],
)
def test_htmx_props_opaque(key: str, value: str) -> None:
    result = generate({"type": "button", "binding": "create", "props": {key: value}})
    assert result.complete
    assert f' {key}="{value}"' in button_line(result).replace("&#x27;", "'")


def test_class_only() -> None:
    result = generate(
        {"type": "button", "binding": "create", "props": {"class": "btn"}}
    )
    assert button_line(result).startswith('<button type="button" class="btn" hx-get=')


# Binding et méthodes.


def test_missing_binding_omits_button() -> None:
    result = generate({"type": "button"})
    assert codes(result) == ["button_missing_action"]
    assert not result.complete and "<button" not in result.template
    assert result.issues[0].location == (
        "root",
        "children",
        0,
        "children",
        0,
        "children",
        0,
        "binding",
    )
    # Le reste du template est généré.
    assert "<section>" in result.template and "<div>" in result.template


@pytest.mark.parametrize("binding", ["unknown", "page_title"])
def test_unknown_action_is_blocking(binding: str) -> None:
    c = make_contract(context={"page_title": {"type": "string"}})
    result = generate({"type": "button", "binding": binding}, c)
    assert codes(result) == ["invalid_binding"]
    assert result.template == "" and not result.complete


def test_no_actions_in_contract() -> None:
    c = contract({})
    result = generate({"type": "button", "binding": "create"}, c)
    assert codes(result) == ["invalid_binding"] and result.template == ""


@pytest.mark.parametrize("binding", ["update", "patch", "destroy", "head"])
def test_unsupported_methods(binding: str) -> None:
    result = generate({"type": "button", "binding": binding})
    assert codes(result) == ["unsupported_action_method"]
    assert "<button" not in result.template and not result.complete


def test_post_csrf_true_refused() -> None:
    result = generate({"type": "button", "binding": "store_csrf"})
    assert codes(result) == ["unsupported_csrf"]
    assert "<button" not in result.template and not result.complete


def test_mutated_contract_method_revalidated() -> None:
    c = make_contract()
    assert c.actions is not None
    c.actions["create"] = c.actions["create"].model_copy(update={"method": "get"})
    result = generate({"type": "button", "binding": "create"}, c)
    assert codes(result) == ["invalid_contract"] and result.template == ""


def test_path_from_contract_only() -> None:
    c = make_contract({"create": {"method": "GET", "path": "/autre/chemin"}})
    result = generate({"type": "button", "binding": "create"}, c)
    assert 'hx-get="/autre/chemin"' in button_line(result)
    assert "create" not in button_line(result)


# Props.


@pytest.mark.parametrize(
    "key", ["onclick", "style", "hx-trigger", "hx-post", "hx-get", "data-secret", "tag"]
)
def test_unknown_prop_ignored(key: str) -> None:
    props = {key: "alert(1)", "class": "btn"}
    result = generate({"type": "button", "binding": "create", "props": props})
    assert codes(result) == ["unsupported_prop"]
    line = button_line(result)
    assert line == (
        '<button type="button" class="btn" hx-get="/contacts/create">Action</button>'
    )
    assert "alert" not in result.template


@pytest.mark.parametrize(
    ("key", "value"),
    [("hx-target", ""), ("hx-swap", True), ("hx-confirm", 3), ("hx-target", 1.5)],
)
def test_invalid_htmx_value_omits_button(key: str, value: Any) -> None:
    result = generate({"type": "button", "binding": "create", "props": {key: value}})
    assert codes(result) == ["invalid_htmx_prop"]
    assert "<button" not in result.template


def test_non_string_class_ignored() -> None:
    result = generate({"type": "button", "binding": "create", "props": {"class": 1}})
    assert codes(result) == ["unsupported_prop"]
    assert button_line(result) == (
        '<button type="button" hx-get="/contacts/create">Action</button>'
    )


# Échappement.


@pytest.mark.parametrize(
    "hostile",
    [
        '/?x="><script>alert(1)</script>',
        "{{ secret }}",
        "{% include 'x' %}",
        "{# c #}",
        "a\nb\rc",
    ],
)
def test_hostile_values_stay_in_attributes(hostile: str) -> None:
    c = make_contract({"create": {"method": "GET", "path": hostile}})
    props = {"hx-target": hostile, "hx-confirm": hostile, "class": hostile}
    result = generate({"type": "button", "binding": "create", "props": props}, c)
    assert result.complete
    line = button_line(result)
    assert "<script>" not in result.template
    assert "{{" not in result.template and "{%" not in result.template
    assert "{#" not in result.template
    assert line.count("<button") == 1 and line.endswith(">Action</button>")
    assert len(result.template.splitlines()) == 5
    tree = Environment().parse(result.template)
    # Aucune expression ni instruction Jinja : uniquement des données statiques.
    assert not list(tree.find_all((nodes.Name, nodes.Getattr, nodes.Include)))


# Conditions.


def test_visible_if_wraps_button() -> None:
    c = make_contract(context={"can_create": {"type": "boolean"}})
    button = {"type": "button", "binding": "create", "visible_if": "can_create"}
    result = generate(button, c)
    assert result.complete
    assert result.template == (
        "<section>\n"
        "  <div>\n"
        "    {% if can_create %}\n"
        '      <button type="button" hx-get="/contacts/create">Action</button>\n'
        "    {% endif %}\n"
        "  </div>\n"
        "</section>\n"
    )


def test_omitted_button_leaves_no_empty_condition() -> None:
    c = make_contract(context={"can_create": {"type": "boolean"}})
    button = {"type": "button", "binding": "update", "visible_if": "can_create"}
    result = generate(button, c)
    assert codes(result) == ["unsupported_action_method"]
    assert "{% if" not in result.template


@pytest.mark.parametrize("condition", ["missing", "title"])
def test_invalid_condition_keeps_historic_diagnostics(condition: str) -> None:
    c = make_contract(context={"title": {"type": "string"}})
    button = {"type": "button", "binding": "create", "visible_if": condition}
    result = generate(button, c)
    assert codes(result) == ["invalid_condition"] and result.template == ""


# Budget.


def test_output_budget_shared() -> None:
    base = generate({"type": "button", "binding": "create"})
    fixed = len(base.template) - len("/contacts/create")
    exact = "/" + "x" * (MAX_GENERATED_TEMPLATE_CHARS - fixed - 1)
    c = make_contract({"create": {"method": "GET", "path": exact}})
    fits = generate({"type": "button", "binding": "create"}, c)
    assert fits.complete and len(fits.template) == MAX_GENERATED_TEMPLATE_CHARS
    c = make_contract({"create": {"method": "GET", "path": exact + "x"}})
    over = generate({"type": "button", "binding": "create"}, c)
    assert codes(over) == ["output_too_large"] and over.template == ""


# Pureté, déterminisme, non-mutation, périmètre.


def test_pure(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("effet de bord interdit")

    for target, name in (
        (builtins, "open"),
        (os, "open"),
        (socket, "socket"),
        (subprocess, "Popen"),
    ):
        monkeypatch.setattr(target, name, forbidden)
    props = {"class": "btn", "hx-target": "#x"}
    result = generate({"type": "button", "binding": "store", "props": props})
    monkeypatch.undo()
    assert result.complete


def test_deterministic_and_non_mutating() -> None:
    model = with_button(
        {"type": "button", "binding": "create", "props": {"hx-swap": "none"}}
    )
    c = make_contract()
    before = (copy.deepcopy(model.model_dump()), copy.deepcopy(c.model_dump()))
    first = generate_simple_template(model, c)
    assert first == generate_simple_template(model, c)
    assert (model.model_dump(), c.model_dump()) == before


def test_no_script_or_cdn() -> None:
    result = generate({"type": "button", "binding": "store"})
    for token in ("<script", "unpkg", "cdn", "htmx.org", "csrf"):
        assert token not in result.template.lower()


def test_module_scope() -> None:
    names = set(vars(buttons))
    assert not names & {"os", "open", "Path", "import_module", "Router"}
    assert buttons.BUTTON_LABEL == "Action"


def test_preview_stays_inert() -> None:
    from forge_design.preview import generate_preview_data, render_preview

    props = {"class": "btn", "hx-target": "#x", "hx-swap": "none", "hx-confirm": "?"}
    model = with_button({"type": "button", "binding": "store", "props": props})
    c = make_contract()
    rendered = render_preview(model, generate_preview_data(c).data)
    assert "hx-" not in rendered.html and "/contacts" not in rendered.html
    assert '<button data-forge-design-type="button"' in rendered.html
    assert "preview.unsupported_prop" in {issue.code for issue in rendered.issues}


# Boutons submit — FD-INTERACT-005.

FORM_ACTIONS = {
    "create_contact": {"method": "POST", "path": "/contacts"},
    "cancel": {"method": "GET", "path": "/contacts"},
}
EMAIL_FIELD = {"type": "field", "field": {"name": "email", "input_type": "email"}}


def save(label: str = "Enregistrer", **extra: Any) -> dict[str, Any]:
    return {"type": "button", "submit": {"label": label}, **extra}


def submit_form(
    *children: dict[str, Any], context: dict[str, Any] | None = None
) -> simple.TemplateGenerationResult:
    holder = {"type": "form", "binding": "create_contact", "children": list(children)}
    model = design([{"type": "section", "children": [holder]}])
    return generate_simple_template(
        model, contract(context or {}, actions=FORM_ACTIONS)
    )


def submit_lines(result: simple.TemplateGenerationResult) -> list[str]:
    return [line.strip() for line in result.template.splitlines() if "<button" in line]


def test_end_criterion_form_with_submit() -> None:
    result = submit_form(EMAIL_FIELD, save(props={"class": "px-4 py-2"}))
    assert result.complete and result.issues == ()
    assert result.template == (
        "<section>\n"
        '  <form action="/contacts" method="post" hx-post="/contacts">\n'
        '    <input type="email" name="email">\n'
        '    <button type="submit" class="px-4 py-2">Enregistrer</button>\n'
        "  </form>\n"
        "</section>\n"
    )
    Environment().parse(result.template)


def test_submit_minimal() -> None:
    result = submit_form(save())
    assert submit_lines(result) == ['<button type="submit">Enregistrer</button>']


def test_submit_label_never_action() -> None:
    result = submit_form(save("Créer le contact"))
    line = submit_lines(result)[0]
    assert ">Action<" not in result.template and ">Créer le contact<" in line


def test_submit_has_no_own_action() -> None:
    result = submit_form(save(props={"class": "btn"}))
    line = submit_lines(result)[0]
    for token in ("hx-", "action=", "formaction", "formmethod", "name=", "value="):
        assert token not in line


@pytest.mark.parametrize(
    "key",
    ["hx-target", "hx-swap", "hx-confirm", "onclick", "tag", "hx-post", "style"],
)
def test_submit_refused_props(key: str) -> None:
    result = submit_form(save(props={key: "x()", "class": "btn"}))
    assert codes(result) == ["unsupported_prop"]
    assert submit_lines(result) == [
        '<button type="submit" class="btn">Enregistrer</button>'
    ]
    assert "x()" not in result.template


def test_submit_non_string_class() -> None:
    result = submit_form(save(props={"class": 3}))
    assert codes(result) == ["unsupported_prop"]
    assert submit_lines(result) == ['<button type="submit">Enregistrer</button>']


@pytest.mark.parametrize(
    "hostile", ['"><script>alert(1)</script>', "{{ danger }}", "{% if x %}", "a\nb"]
)
def test_submit_hostile_label_and_class(hostile: str) -> None:
    result = submit_form(save(hostile, props={"class": hostile}))
    assert result.complete
    assert "<script>" not in result.template
    for token in ("{{", "{%"):
        assert token not in result.template
    assert len(submit_lines(result)) == 1
    tree = Environment().parse(result.template)
    assert not list(tree.find_all((nodes.Name, nodes.Getattr, nodes.If)))


def test_submit_visible_if() -> None:
    result = submit_form(
        save(visible_if="can_save"), context={"can_save": {"type": "boolean"}}
    )
    lines = [line.strip() for line in result.template.splitlines()]
    assert lines[2:5] == [
        "{% if can_save %}",
        '<button type="submit">Enregistrer</button>',
        "{% endif %}",
    ]


def test_several_submits_in_design_order() -> None:
    result = submit_form(save("Enregistrer"), save("Enregistrer et fermer"))
    assert submit_lines(result) == [
        '<button type="submit">Enregistrer</button>',
        '<button type="submit">Enregistrer et fermer</button>',
    ]


def test_action_and_submit_side_by_side() -> None:
    result = submit_form(save(), {"type": "button", "binding": "cancel"})
    assert submit_lines(result) == [
        '<button type="submit">Enregistrer</button>',
        '<button type="button" hx-get="/contacts">Action</button>',
    ]


@pytest.mark.parametrize(
    "block",
    [
        {"type": "section", "children": [{"type": "container", "children": [save()]}]},
        {"type": "section", "children": [{"type": "text", "submit": {"label": "x"}}]},
    ],
)
def test_invalid_submit_blocks_everything(block: dict[str, Any]) -> None:
    model = design([block])
    result = generate_simple_template(model, contract({}, actions=FORM_ACTIONS))
    assert codes(result) == ["invalid_submit"] and result.template == ""


def test_submit_with_binding_blocks_everything() -> None:
    result = submit_form(save(binding="cancel"))
    assert codes(result) == ["invalid_submit"] and result.template == ""


def test_submit_errors_in_prefix_order() -> None:
    holder = {"type": "container", "children": [save(binding="cancel")]}
    model = design([{"type": "section", "children": [holder]}])
    result = generate_simple_template(model, contract({}, actions=FORM_ACTIONS))
    assert codes(result) == ["invalid_submit", "invalid_submit"]


def test_submit_truncation(monkeypatch: pytest.MonkeyPatch) -> None:
    from forge_design.design.submit_buttons import (
        SubmitButtonIssue,
        SubmitButtonValidationResult,
    )

    marker = SubmitButtonIssue("design.submit.analysis_truncated", "x", ("root",))

    def truncated(model: DesignFile) -> SubmitButtonValidationResult:
        return SubmitButtonValidationResult(False, (marker,), truncated=True)

    monkeypatch.setattr(simple, "validate_submit_buttons", truncated)
    result = submit_form(save())
    assert codes(result) == ["analysis_truncated"] and result.template == ""


def test_uses_existing_submit_validator(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []
    real = simple.validate_submit_buttons

    def spy(model: DesignFile) -> Any:
        calls.append(model)
        return real(model)

    monkeypatch.setattr(simple, "validate_submit_buttons", spy)
    submit_form(save())
    assert len(calls) == 1
    assert not set(vars(buttons)) & {"outside_form", "validate_submit_buttons"}


def test_empty_button_still_missing_action() -> None:
    result = submit_form({"type": "button"})
    assert codes(result) == ["button_missing_action"]
    assert "<button" not in result.template


def test_omitted_form_hides_submit() -> None:
    holder = {"type": "form", "children": [save()]}
    model = design([{"type": "section", "children": [holder]}])
    result = generate_simple_template(model, contract({}, actions=FORM_ACTIONS))
    assert codes(result) == ["form_missing_action"]
    assert "<button" not in result.template and "Enregistrer" not in result.template


def test_submit_budget() -> None:
    base = submit_form(save("x"))
    exact = "x" * (MAX_GENERATED_TEMPLATE_CHARS - len(base.template) + 1)
    fits = submit_form(save(exact))
    assert fits.complete and len(fits.template) == MAX_GENERATED_TEMPLATE_CHARS
    over = submit_form(save(exact + "x"))
    assert codes(over) == ["output_too_large"] and over.template == ""


def test_submit_deterministic_and_non_mutating() -> None:
    holder = {"type": "form", "binding": "create_contact", "children": [save()]}
    model = design([{"type": "section", "children": [holder]}])
    c = contract({}, actions=FORM_ACTIONS)
    before = (copy.deepcopy(model.model_dump()), copy.deepcopy(c.model_dump()))
    assert generate_simple_template(model, c) == generate_simple_template(model, c)
    assert (model.model_dump(), c.model_dump()) == before


def test_submit_pure(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("effet de bord interdit")

    for target, name in (
        (builtins, "open"),
        (os, "open"),
        (socket, "socket"),
        (subprocess, "Popen"),
    ):
        monkeypatch.setattr(target, name, forbidden)
    result = submit_form(EMAIL_FIELD, save())
    monkeypatch.undo()
    assert result.complete


def test_submit_preview_aligned_but_inert() -> None:
    # FD-INTERACT-006 : la preview rend le submit, toujours sans action.
    from forge_design.preview import generate_preview_data, render_preview

    holder = {"type": "form", "binding": "create_contact", "children": [save()]}
    model = design([{"type": "section", "children": [holder]}])
    c = contract({}, actions=FORM_ACTIONS)
    html = render_preview(model, generate_preview_data(c).data).html
    assert 'type="submit">Enregistrer</button>' in html
    assert "hx-" not in html and "action=" not in html
