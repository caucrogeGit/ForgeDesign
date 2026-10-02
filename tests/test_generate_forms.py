"""Formulaires HTML/HTMX générés : action du contrat, champs, échappement."""

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
from forge_design.design import validate_design_nesting
from forge_design.design.models import DesignFile
from forge_design.generate import actions, forms, generate_simple_template, simple
from forge_design.limits import MAX_GENERATED_TEMPLATE_CHARS

ACTIONS = {
    "create_contact": {"method": "POST", "path": "/contacts", "csrf": False},
    "store": {"method": "POST", "path": "/contacts"},
    "store_csrf": {"method": "POST", "path": "/contacts", "csrf": True},
    "search": {"method": "GET", "path": "/search"},
    "search_csrf": {"method": "GET", "path": "/search", "csrf": True},
    "update": {"method": "PUT", "path": "/contacts/1"},
    "patch": {"method": "PATCH", "path": "/contacts/1"},
    "destroy": {"method": "DELETE", "path": "/contacts/1"},
    "head": {"method": "HEAD", "path": "/contacts"},
    "delete_one": {"method": "GET", "path": "/contacts/1/delete"},
}
EMAIL = {
    "name": "email",
    "input_type": "email",
    "label": "Adresse e-mail",
    "required": True,
}


def field(definition: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    node: dict[str, Any] = {"type": "field", **extra}
    if definition is not None:
        node["field"] = definition
    return node


def form(*children: dict[str, Any], **extra: Any) -> dict[str, Any]:
    node: dict[str, Any] = {"type": "form", **extra}
    if children:
        node["children"] = list(children)
    return node


def page(*blocks: dict[str, Any]) -> DesignFile:
    model = design([{"type": "section", "children": list(blocks)}])
    assert validate_design_nesting(model).valid
    return model


def make_contract(
    action_map: dict[str, Any] | None = None, context: dict[str, Any] | None = None
) -> ViewContract:
    return contract(
        context or {}, actions=ACTIONS if action_map is None else action_map
    )


def generate(
    *blocks: dict[str, Any], contract_model: ViewContract | None = None
) -> simple.TemplateGenerationResult:
    return generate_simple_template(page(*blocks), contract_model or make_contract())


def codes(result: simple.TemplateGenerationResult) -> list[str]:
    return [issue.code.removeprefix("generate.") for issue in result.issues]


def lines(result: simple.TemplateGenerationResult) -> list[str]:
    return [line.strip() for line in result.template.splitlines()]


# Critère de fin et méthodes.


def test_end_criterion_exact() -> None:
    result = generate(
        form(
            field(EMAIL),
            binding="create_contact",
            props={"class": "space-y-4", "hx-target": "#content"},
        )
    )
    assert result.complete and result.issues == ()
    assert result.template == (
        "<section>\n"
        '  <form action="/contacts" method="post" class="space-y-4"'
        ' hx-post="/contacts" hx-target="#content">\n'
        '    <label>Adresse e-mail<input type="email" name="email" required>'
        "</label>\n"
        "  </form>\n"
        "</section>\n"
    )
    Environment().parse(result.template)


@pytest.mark.parametrize("binding", ["search", "search_csrf"])
def test_get(binding: str) -> None:
    result = generate(form(field({"name": "q", "input_type": "text"}), binding=binding))
    assert result.complete
    assert lines(result)[1] == '<form action="/search" method="get" hx-get="/search">'


@pytest.mark.parametrize("binding", ["create_contact", "store"])
def test_post(binding: str) -> None:
    result = generate(form(field(EMAIL), binding=binding))
    assert result.complete
    assert lines(result)[1] == (
        '<form action="/contacts" method="post" hx-post="/contacts">'
    )


def test_same_url_for_action_and_htmx() -> None:
    c = make_contract({"create_contact": {"method": "POST", "path": "/a/b?x=1&y=2"}})
    result = generate(form(field(EMAIL), binding="create_contact"), contract_model=c)
    opening = lines(result)[1]
    assert 'action="/a/b?x=1&amp;y=2"' in opening
    assert 'hx-post="/a/b?x=1&amp;y=2"' in opening


def test_form_props_fixed_order() -> None:
    props = {
        "hx-confirm": "Créer ?",
        "hx-swap": "outerHTML",
        "hx-target": "#content",
        "class": "space-y-4",
    }
    result = generate(form(field(EMAIL), binding="store", props=props))
    assert lines(result)[1] == (
        '<form action="/contacts" method="post" class="space-y-4" hx-post="/contacts"'
        ' hx-target="#content" hx-swap="outerHTML" hx-confirm="Créer ?">'
    )


def test_empty_form() -> None:
    result = generate(form(binding="search"))
    assert result.complete
    assert lines(result)[1] == (
        '<form action="/search" method="get" hx-get="/search"></form>'
    )


# Binding et omissions.


def test_missing_action_omits_form_and_fields() -> None:
    result = generate(form(field(EMAIL)), {"type": "text"})
    assert codes(result) == ["form_missing_action"]
    assert not result.complete
    assert "<form" not in result.template and "<input" not in result.template
    assert "email" not in result.template and "<p></p>" in result.template


def test_unknown_action_blocks_everything() -> None:
    result = generate(form(field(EMAIL), binding="unknown"))
    assert codes(result) == ["invalid_binding"] and result.template == ""


@pytest.mark.parametrize("binding", ["update", "patch", "destroy", "head"])
def test_unsupported_methods(binding: str) -> None:
    result = generate(form(field(EMAIL), binding=binding))
    assert codes(result) == ["unsupported_action_method"]
    assert "<form" not in result.template and "<input" not in result.template


def test_post_csrf_true_refused() -> None:
    result = generate(form(field(EMAIL), binding="store_csrf"))
    assert codes(result) == ["unsupported_csrf"]
    assert "<form" not in result.template and "<input" not in result.template


# Champs.


@pytest.mark.parametrize(
    "input_type", ["text", "email", "password", "number", "date", "checkbox"]
)
def test_input_types(input_type: str) -> None:
    result = generate(
        form(field({"name": "x", "input_type": input_type}), binding="store")
    )
    assert lines(result)[2] == f'<input type="{input_type}" name="x">'


def test_checkbox_without_invented_value() -> None:
    result = generate(
        form(field({"name": "active", "input_type": "checkbox"}), binding="store")
    )
    assert lines(result)[2] == '<input type="checkbox" name="active">'
    assert "value" not in result.template and "hidden" not in result.template


def test_label_absent_no_empty_label() -> None:
    result = generate(
        form(field({"name": "email", "input_type": "email"}), binding="store")
    )
    assert lines(result)[2] == '<input type="email" name="email">'
    assert "<label" not in result.template


@pytest.mark.parametrize(
    ("required", "expected"),
    [(True, " required"), (False, ""), (None, "")],
)
def test_required(required: bool | None, expected: str) -> None:
    definition: dict[str, Any] = {"name": "n", "input_type": "text"}
    if required is not None:
        definition["required"] = required
    result = generate(form(field(definition), binding="store"))
    assert lines(result)[2] == f'<input type="text" name="n"{expected}>'


@pytest.mark.parametrize("name", ["contact.email", "items[0].name", "é"])
def test_opaque_names(name: str) -> None:
    result = generate(
        form(field({"name": name, "input_type": "text"}), binding="store")
    )
    assert f'name="{name}"' in lines(result)[2]


def test_no_invented_attributes() -> None:
    result = generate(
        form(
            field({"name": "n", "input_type": "number"}),
            field({"name": "p", "input_type": "password"}),
            field({"name": "d", "input_type": "date"}),
            binding="store",
        )
    )
    for token in ("id=", "for=", "min=", "max=", "step=", "autocomplete", "value="):
        assert token not in result.template
    assert "placeholder" not in result.template


def test_field_class_and_unknown_props() -> None:
    result = generate(
        form(
            field(
                {"name": "name", "input_type": "text"},
                props={"placeholder": "Nom", "class": "w-full rounded", "min": 1},
            ),
            binding="store",
        )
    )
    assert codes(result) == ["unsupported_prop", "unsupported_prop"]
    assert lines(result)[2] == '<input type="text" name="name" class="w-full rounded">'
    assert "placeholder" not in result.template and "Nom" not in result.template


def test_field_non_string_class_ignored() -> None:
    result = generate(
        form(
            field({"name": "n", "input_type": "text"}, props={"class": 3}),
            binding="store",
        )
    )
    assert codes(result) == ["unsupported_prop"]
    assert lines(result)[2] == '<input type="text" name="n">'


# Props du formulaire.


@pytest.mark.parametrize(
    "key", ["style", "onclick", "hx-trigger", "hx-vals", "hx-headers", "tag", "id"]
)
def test_form_unknown_prop(key: str) -> None:
    result = generate(
        form(field(EMAIL), binding="store", props={key: "x()", "hx-target": "#c"})
    )
    assert codes(result) == ["unsupported_prop"]
    assert lines(result)[1] == (
        '<form action="/contacts" method="post" hx-post="/contacts" hx-target="#c">'
    )
    assert "x()" not in result.template


@pytest.mark.parametrize(("key", "value"), [("hx-target", ""), ("hx-swap", False)])
def test_form_invalid_htmx_prop(key: str, value: Any) -> None:
    result = generate(form(field(EMAIL), binding="store", props={key: value}))
    assert codes(result) == ["invalid_htmx_prop"]
    assert "<form" not in result.template and "<input" not in result.template


# Validation form_fields réutilisée.


@pytest.mark.parametrize(
    ("block", "code"),
    [
        (form(field(), binding="store"), "invalid_field"),
        (form(field(EMAIL), field(EMAIL), binding="store"), "duplicate_field_name"),
        (form(field(EMAIL), binding="store", field=EMAIL), "invalid_field"),
    ],
)
def test_field_validation_blocks(block: dict[str, Any], code: str) -> None:
    result = generate(block)
    assert codes(result) == [code] and result.template == ""


def test_field_validation_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    from forge_design.design.form_fields import (
        FormFieldIssue,
        FormFieldValidationResult,
    )

    marker = FormFieldIssue("design.field.analysis_truncated", "limite", ("root",))

    def truncated(model: DesignFile) -> FormFieldValidationResult:
        return FormFieldValidationResult(False, (marker,), truncated=True)

    monkeypatch.setattr(simple, "validate_form_fields", truncated)
    result = generate(form(field(EMAIL), binding="store"))
    assert codes(result) == ["analysis_truncated"] and result.template == ""


def test_uses_existing_validator(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []
    real = simple.validate_form_fields

    def spy(model: DesignFile) -> Any:
        calls.append(model)
        return real(model)

    monkeypatch.setattr(simple, "validate_form_fields", spy)
    generate(form(field(EMAIL), binding="store"))
    assert len(calls) == 1
    names = set(vars(forms))
    assert not names & {"missing_definition", "duplicate_name", "validate_form_fields"}


# Échappement.


@pytest.mark.parametrize(
    "hostile",
    ['"><script>alert(1)</script>', "{{ secret }}", "{% include 'x' %}", "a\nb"],
)
def test_hostile_values_escaped(hostile: str) -> None:
    c = make_contract({"store": {"method": "POST", "path": hostile}})
    result = generate(
        form(
            field({"name": hostile, "input_type": "text", "label": hostile}),
            binding="store",
            props={"hx-target": hostile, "hx-confirm": hostile, "class": hostile},
        ),
        contract_model=c,
    )
    assert result.complete
    assert "<script>" not in result.template
    for token in ("{{", "{%", "{#"):
        assert token not in result.template
    assert len(result.template.splitlines()) == 5
    tree = Environment().parse(result.template)
    assert not list(tree.find_all((nodes.Name, nodes.Getattr, nodes.Include)))


# Conditions.


def test_form_visible_if() -> None:
    c = make_contract(context={"can_create": {"type": "boolean"}})
    result = generate(
        form(field(EMAIL), binding="store", visible_if="can_create"), contract_model=c
    )
    assert lines(result)[1:5] == [
        "{% if can_create %}",
        '<form action="/contacts" method="post" hx-post="/contacts">',
        '<label>Adresse e-mail<input type="email" name="email" required></label>',
        "</form>",
    ]
    assert lines(result)[5] == "{% endif %}"


def test_field_visible_if() -> None:
    c = make_contract(context={"show": {"type": "boolean"}})
    result = generate(
        form(
            field({"name": "n", "input_type": "text"}, visible_if="show"),
            binding="store",
        ),
        contract_model=c,
    )
    assert lines(result)[2:5] == [
        "{% if show %}",
        '<input type="text" name="n">',
        "{% endif %}",
    ]


def test_omitted_form_leaves_no_empty_condition() -> None:
    c = make_contract(context={"show": {"type": "boolean"}})
    result = generate(form(field(EMAIL), visible_if="show"), contract_model=c)
    assert codes(result) == ["form_missing_action"] and "{% if" not in result.template


# Boutons enfants et absence de submit.


def test_button_child_keeps_own_action() -> None:
    result = generate(
        form(field(EMAIL), {"type": "button", "binding": "delete_one"}, binding="store")
    )
    assert result.complete
    assert lines(result)[3] == (
        '<button type="button" hx-get="/contacts/1/delete">Action</button>'
    )
    assert 'type="submit"' not in result.template
    assert "Envoyer" not in result.template


def test_no_implicit_submit() -> None:
    result = generate(form(field(EMAIL), binding="store"))
    assert "submit" not in result.template and "<button" not in result.template


def test_alert_child_still_unsupported() -> None:
    result = generate(form(field(EMAIL), {"type": "alert"}, binding="store"))
    assert codes(result) == ["unsupported_block"]
    assert "<form" in result.template and "alert" not in result.template


# Budget.


def test_output_budget_shared() -> None:
    def build(label: str) -> simple.TemplateGenerationResult:
        definition = {"name": "n", "input_type": "text", "label": label}
        return generate(form(field(definition), binding="store"))

    base = build("x")
    exact = "x" * (MAX_GENERATED_TEMPLATE_CHARS - len(base.template) + 1)
    fits = build(exact)
    assert fits.complete and len(fits.template) == MAX_GENERATED_TEMPLATE_CHARS
    over = build(exact + "x")
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
    result = generate(form(field(EMAIL), binding="store"))
    monkeypatch.undo()
    assert result.complete


def test_deterministic_and_non_mutating() -> None:
    model = page(form(field(EMAIL), binding="store", props={"class": "x"}))
    c = make_contract()
    before = (copy.deepcopy(model.model_dump()), copy.deepcopy(c.model_dump()))
    assert generate_simple_template(model, c) == generate_simple_template(model, c)
    assert (model.model_dump(), c.model_dump()) == before


def test_no_script_or_runtime() -> None:
    result = generate(form(field(EMAIL), binding="store"))
    for token in ("<script", "unpkg", "htmx.org", "csrf", "token"):
        assert token not in result.template.lower()


def test_shared_interaction_policy() -> None:
    assert actions.METHOD_ATTRIBUTES == {"GET": "hx-get", "POST": "hx-post"}
    assert actions.HTMX_PROPS == ("hx-target", "hx-swap", "hx-confirm")
    assert not set(vars(forms)) & {"os", "open", "Path"}


def test_preview_unchanged() -> None:
    from forge_design.preview import generate_preview_data, render_preview

    model = page(form(field(EMAIL), binding="store", props={"hx-target": "#c"}))
    c = make_contract()
    html = render_preview(model, generate_preview_data(c).data).html
    # FD-INTERACT-006 : champ rendu, formulaire toujours sans action ni HTMX.
    assert '<input data-forge-design-type="field" type="email"' in html
    assert "hx-" not in html and "action=" not in html and "method=" not in html
