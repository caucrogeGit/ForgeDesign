"""Contrat minimal des formulaires : modèle, bindings, validation, éditeur."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_design_bindings import contract, design
from test_web_editor import action, make_root, on_disk, serving, write

from forge_design.design import (
    DesignFile,
    FieldDefinition,
    validate_design_bindings,
    validate_design_nesting,
    validate_form_fields,
)
from forge_design.design.form_fields import FormFieldIssue
from forge_design.editor import (
    DesignEditResult,
    move_design_block,
    set_design_binding,
    set_design_props,
    set_design_visibility,
    set_field_definition,
)
from forge_design.generate import generate_simple_template
from forge_design.limits import MAX_DESIGN_ISSUES, MAX_DESIGN_NODES
from forge_design.preview import generate_preview_data, render_preview

INPUT_TYPES = ("text", "email", "password", "number", "date", "checkbox")
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


def form(*fields: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {"type": "form", "children": list(fields), **extra}


def page(*forms: dict[str, Any]) -> DesignFile:
    model = design([{"type": "section", "children": list(forms)}])
    assert validate_design_nesting(model).valid
    return model


def codes(issues: tuple[FormFieldIssue, ...]) -> list[str]:
    return [issue.code.removeprefix("design.field.") for issue in issues]


ACTIONS = {"create_contact": {"method": "POST", "path": "/contacts"}}


# Modèle.


def test_minimal_and_complete() -> None:
    minimal = FieldDefinition.model_validate({"name": "email", "input_type": "email"})
    assert minimal.model_dump(exclude_unset=True) == {
        "name": "email",
        "input_type": "email",
    }
    complete = FieldDefinition.model_validate(EMAIL)
    assert complete.model_dump(exclude_unset=True) == EMAIL


@pytest.mark.parametrize("input_type", INPUT_TYPES)
def test_each_input_type(input_type: str) -> None:
    value = FieldDefinition.model_validate({"name": "x", "input_type": input_type})
    assert value.input_type == input_type


@pytest.mark.parametrize("name", ["email", "contact.email", "items[0].name", "é"])
def test_free_names(name: str) -> None:
    assert FieldDefinition.model_validate({"name": name, "input_type": "text"}).name


@pytest.mark.parametrize(
    "data",
    [
        {"name": "x", "input_type": "textarea"},
        {"name": "x", "input_type": "select"},
        {"name": "x", "input_type": "TEXT"},
        {"name": "", "input_type": "text"},
        {"name": "x"},
        {"input_type": "text"},
        {"name": None, "input_type": "text"},
        {"name": "x", "input_type": "text", "label": None},
        {"name": "x", "input_type": "text", "required": None},
        {"name": "x", "input_type": "text", "label": ""},
        {"name": "x", "input_type": "text", "required": "yes"},
        {"name": "x", "input_type": "text", "required": 1},
        {"name": "x", "input_type": "text", "value": "a"},
        {"name": "x", "input_type": "text", "placeholder": "a"},
        {"name": 3, "input_type": "text"},
    ],
)
def test_invalid_definitions(data: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        FieldDefinition.model_validate(data)


def test_required_false_distinct_from_absent() -> None:
    explicit = {"name": "x", "input_type": "checkbox", "required": False}
    assert FieldDefinition.model_validate(explicit).model_dump(exclude_unset=True) == (
        explicit
    )
    node = page(form(field(explicit))).model_dump(exclude_unset=True)
    stored = node["root"]["children"][0]["children"][0]["children"][0]
    assert stored["field"] == explicit


def test_design_round_trip_and_null_refused() -> None:
    model = page(form(field(EMAIL), binding="create_contact"))
    dumped = model.model_dump(exclude_unset=True)
    assert DesignFile.model_validate_json(json.dumps(dumped)) == model
    broken = copy.deepcopy(dumped)
    broken["root"]["children"][0]["children"][0]["children"][0]["field"] = None
    with pytest.raises(ValidationError):
        DesignFile.model_validate(broken)


def test_frozen() -> None:
    definition = FieldDefinition.model_validate(EMAIL)
    with pytest.raises(ValidationError):
        definition.name = "other"  # type: ignore[misc]


# Bindings.


def test_form_action_valid() -> None:
    model = page(form(field(EMAIL), binding="create_contact"))
    assert validate_design_bindings(model, contract({}, actions=ACTIONS)).valid


@pytest.mark.parametrize("actions", [ACTIONS, None])
def test_form_action_unknown(actions: dict[str, Any] | None) -> None:
    model = page(form(field(EMAIL), binding="unknown"))
    extra = {} if actions is None else {"actions": actions}
    result = validate_design_bindings(model, contract({}, **extra))
    assert [i.code for i in result.issues] == ["design.binding.unknown_action"]


def test_form_without_binding_not_reported() -> None:
    assert validate_design_bindings(page(form(field(EMAIL))), contract({})).valid


def test_field_binding_still_unsupported() -> None:
    model = page(form(field(EMAIL, binding="email")))
    c = contract({"email": {"type": "string"}}, actions=ACTIONS)
    result = validate_design_bindings(model, c)
    assert [i.code for i in result.issues] == ["design.binding.unsupported"]


# Validation sémantique.


def test_valid_fields() -> None:
    other = {"name": "nom", "input_type": "text"}
    result = validate_form_fields(page(form(field(EMAIL), field(other))))
    assert result.valid and result.issues == () and not result.truncated


def test_missing_definition() -> None:
    result = validate_form_fields(page(form(field())))
    assert codes(result.issues) == ["missing_definition"]
    location = ("root", "children", 0, "children", 0, "children", 0)
    assert result.issues[0].location == location


@pytest.mark.parametrize("node_type", ["text", "form", "section", "button"])
def test_unsupported_definition(node_type: str) -> None:
    if node_type == "text":
        model = design(
            [{"type": "section", "children": [{"type": "text", "field": EMAIL}]}]
        )
    elif node_type == "form":
        model = page(form(field(EMAIL), field=EMAIL))
    elif node_type == "section":
        model = design([{"type": "section", "field": EMAIL}])
    else:
        model = page(form(field(EMAIL), {"type": "button", "field": EMAIL}))
    result = validate_form_fields(model)
    assert codes(result.issues) == ["unsupported_definition"]
    assert result.issues[0].location[-1] == "field"


def test_unsupported_definition_on_page() -> None:
    model = design([], field=EMAIL)
    result = validate_form_fields(model)
    assert codes(result.issues) == ["unsupported_definition"]
    assert result.issues[0].location == ("root", "field")


def test_duplicate_name_same_form() -> None:
    other = {"name": "email", "input_type": "text"}
    result = validate_form_fields(page(form(field(EMAIL), field(other))))
    assert codes(result.issues) == ["duplicate_name"]
    assert result.issues[0].location == (
        "root",
        "children",
        0,
        "children",
        0,
        "children",
        1,
        "field",
        "name",
    )


def test_same_name_two_forms() -> None:
    assert validate_form_fields(page(form(field(EMAIL)), form(field(EMAIL)))).valid


def test_triple_duplicate_reported_twice() -> None:
    result = validate_form_fields(page(form(field(EMAIL), field(EMAIL), field(EMAIL))))
    assert codes(result.issues) == ["duplicate_name", "duplicate_name"]


def test_truncation_by_issues() -> None:
    fields = [field() for _ in range(MAX_DESIGN_ISSUES + 10)]
    result = validate_form_fields(page(form(*fields)))
    assert result.truncated and not result.valid
    assert len(result.issues) == MAX_DESIGN_ISSUES
    assert codes(result.issues)[-1] == "analysis_truncated"
    assert set(codes(result.issues)[:-1]) == {"missing_definition"}


def test_truncation_by_nodes() -> None:
    fields = [
        field({"name": f"f{i}", "input_type": "text"}) for i in range(MAX_DESIGN_NODES)
    ]
    # Au-delà de la borne, nesting est lui-même tronqué : pas de page().
    model = design([{"type": "section", "children": [form(*fields)]}])
    result = validate_form_fields(model)
    assert result.truncated and codes(result.issues) == ["analysis_truncated"]


def test_pure_and_deterministic() -> None:
    model = page(form(field(EMAIL), field(EMAIL)))
    before = model.model_dump()
    assert validate_form_fields(model) == validate_form_fields(model)
    assert model.model_dump() == before


# Génération et preview reportées.


def test_contract_now_generated() -> None:
    # Reporté par FD-INTERACT-002, généré depuis FD-INTERACT-003.
    model = page(form(field(EMAIL), binding="create_contact"))
    result = generate_simple_template(model, contract({}, actions=ACTIONS))
    assert result.complete
    assert '<form action="/contacts" method="post" hx-post="/contacts">' in (
        result.template
    )


def test_preview_renders_definition() -> None:
    # Ignorée par la preview jusqu'à FD-INTERACT-006, désormais rendue.
    model = page(form(field(EMAIL), binding="create_contact"))
    c = contract({}, actions=ACTIONS)
    html = render_preview(model, generate_preview_data(c).data).html
    assert (
        '<label>Adresse e-mail<input data-forge-design-type="field" type="email"'
        ' name="email" required></label>'
    ) in html
    assert "action=" not in html and "hx-" not in html


# Éditeur.

FIELD_PATH = (0, 0, 0)


def editable() -> DesignFile:
    return page(
        form(
            field(EMAIL, visible_if="show", props={"class": "w-full"}),
            field({"name": "nom", "input_type": "text"}),
            binding="create_contact",
        )
    )


def stored_field(model: DesignFile, path: tuple[int, ...] = FIELD_PATH) -> Any:
    node: Any = model.model_dump(exclude_unset=True)["root"]
    for index in path:
        node = node["children"][index]
    return node


def assert_refused(result: DesignEditResult, original: DesignFile, code: str) -> None:
    assert not result.changed and result.affected_path is None
    assert result.design is original
    assert [i.code for i in result.issues] == ["editor." + code]


def test_set_nominal_preserves_other_properties() -> None:
    original = editable()
    definition = FieldDefinition.model_validate(
        {"name": "courriel", "input_type": "email", "required": False}
    )
    result = set_field_definition(original, path=FIELD_PATH, field=definition)
    assert result.changed and result.affected_path == FIELD_PATH
    node = stored_field(result.design)
    assert node == {
        "type": "field",
        "visible_if": "show",
        "props": {"class": "w-full"},
        "field": {"name": "courriel", "input_type": "email", "required": False},
    }
    assert stored_field(result.design, (0, 0)) == stored_field(original, (0, 0)) | {
        "children": stored_field(result.design, (0, 0))["children"]
    }
    assert stored_field(result.design, (0, 0, 1)) == stored_field(original, (0, 0, 1))


def test_clear_and_noop() -> None:
    original = editable()
    cleared = set_field_definition(original, path=FIELD_PATH, field=None)
    assert cleared.changed and "field" not in stored_field(cleared.design)
    same = set_field_definition(
        original, path=FIELD_PATH, field=FieldDefinition.model_validate(EMAIL)
    )
    assert same == DesignEditResult(original, False, FIELD_PATH, ())
    nothing = set_field_definition(cleared.design, path=FIELD_PATH, field=None)
    assert nothing == DesignEditResult(cleared.design, False, FIELD_PATH, ())


@pytest.mark.parametrize("path", [(0,), (0, 0), ()])
def test_not_a_field(path: tuple[int, ...]) -> None:
    original = editable()
    result = set_field_definition(
        original, path=path, field=FieldDefinition.model_validate(EMAIL)
    )
    assert_refused(result, original, "field_not_supported")


def test_clear_on_non_field_repairs() -> None:
    broken = page(form(field(EMAIL), field=EMAIL))
    assert not validate_form_fields(broken).valid
    result = set_field_definition(broken, path=(0, 0), field=None)
    assert result.changed and validate_form_fields(result.design).valid


@pytest.mark.parametrize("value", [EMAIL, "email", 3])
def test_invalid_value(value: Any) -> None:
    original = editable()
    result = set_field_definition(original, path=FIELD_PATH, field=value)
    assert_refused(result, original, "invalid_field")


@pytest.mark.parametrize("order", ["before", "after"])
def test_duplicate_name_refused_whatever_order(order: str) -> None:
    original = editable()
    duplicate = FieldDefinition.model_validate({"name": "nom", "input_type": "email"})
    target = FIELD_PATH if order == "before" else (0, 0, 1)
    if order == "after":
        duplicate = FieldDefinition.model_validate(EMAIL)
    result = set_field_definition(original, path=target, field=duplicate)
    assert_refused(result, original, "duplicate_field_name")


def test_other_form_same_name_allowed() -> None:
    original = page(
        form(field(EMAIL)), form(field({"name": "nom", "input_type": "text"}))
    )
    result = set_field_definition(
        original, path=(0, 1, 0), field=FieldDefinition.model_validate(EMAIL)
    )
    assert result.changed


def test_preexisting_sibling_errors_ignored() -> None:
    original = page(form(field(), field(EMAIL), field(EMAIL)))
    result = set_field_definition(
        original,
        path=(0, 0, 0),
        field=FieldDefinition.model_validate({"name": "nom", "input_type": "text"}),
    )
    assert result.changed


def test_caller_object_not_shared() -> None:
    definition = FieldDefinition.model_validate(EMAIL)
    cleared = set_field_definition(editable(), path=FIELD_PATH, field=None).design
    result = set_field_definition(cleared, path=FIELD_PATH, field=definition)
    node: Any = result.design.root.children[0]
    stored = node.children[0].children[0].field
    assert stored == definition and stored is not definition


def test_other_mutations_keep_definition() -> None:
    c = contract({"show": {"type": "boolean"}}, actions=ACTIONS)
    original = editable()
    expected = stored_field(original)["field"]
    results = [
        set_design_props(original, path=FIELD_PATH, props={"class": "x"}),
        set_design_props(original, path=FIELD_PATH, props=None),
        set_design_visibility(original, path=FIELD_PATH, visible_if=None, contract=c),
        set_design_binding(original, path=(0, 0), binding=None, contract=c),
        move_design_block(original, source=FIELD_PATH, destination=(0, 0)),
    ]
    assert all(result.changed for result in results)
    assert stored_field(results[0].design)["field"] == expected
    assert stored_field(results[1].design)["field"] == expected
    assert stored_field(results[2].design)["field"] == expected
    assert stored_field(results[3].design)["field"] == expected
    moved = results[4].affected_path
    assert (
        moved is not None
        and stored_field(results[4].design, moved)["field"] == expected
    )


# Préservation par l'éditeur Web (mutations réelles, sauvegarde réelle).


def web_design() -> dict[str, Any]:
    return {
        "version": "0.1",
        "view": "contacts/list",
        "source_contract": "contacts/list.view.json",
        "root": {
            "type": "page",
            "children": [
                {
                    "type": "section",
                    "children": [
                        {
                            "type": "form",
                            "binding": "delete",
                            "children": [
                                {"type": "field", "field": EMAIL},
                                {
                                    "type": "field",
                                    "field": {"name": "nom", "input_type": "text"},
                                },
                            ],
                        }
                    ],
                }
            ],
        },
    }


def test_web_mutations_keep_definition(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    write(root, web_design())

    def definition() -> Any:
        return on_disk(root)["root"]["children"][0]["children"][0]["children"]

    with serving(root, tmp_path) as app:
        for fields in (
            {"action": "props", "path": "0.0.0", "props": '{"class": "w-full"}'},
            {"action": "tailwind_add", "path": "0.0.0", "class_token": "mt-2"},
            {"action": "visibility", "path": "0.0.0", "visible_if": "can_view"},
            {"action": "visibility", "path": "0.0.0", "visible_if": ""},
            {"action": "move", "path": "0.0.0", "destination": "0.0"},
            {"action": "binding", "path": "0.0", "binding": ""},
        ):
            assert action(app, **fields)[0] == 303, fields
    fields_after = definition()
    assert [child["field"] for child in fields_after] == [
        {"name": "nom", "input_type": "text"},
        EMAIL,
    ]
    assert fields_after[1]["props"] == {"class": "w-full mt-2"}


def test_duck_typed_definition_refused() -> None:
    class LooksLikeDefinition:
        def model_dump(self, **kwargs: Any) -> dict[str, Any]:
            return dict(EMAIL)

    original = editable()
    cleared = set_field_definition(original, path=FIELD_PATH, field=None).design
    result = set_field_definition(
        cleared,
        path=FIELD_PATH,
        field=LooksLikeDefinition(),  # type: ignore[arg-type]
    )
    assert_refused(result, cleared, "invalid_field")
