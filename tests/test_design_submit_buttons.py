"""Boutons de soumission : modèle, validation, éditeur, persistance, compatibilité."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_design_bindings import contract, design
from test_templates import make_views
from test_web_editor import action, make_root, on_disk, serving, write

from forge_design.design import (
    DesignFile,
    SubmitDefinition,
    read_design,
    validate_design_bindings,
    validate_design_nesting,
    validate_form_fields,
    validate_submit_buttons,
    write_design,
)
from forge_design.design.submit_buttons import SubmitButtonIssue
from forge_design.editor import (
    DesignEditResult,
    append_design_block,
    move_design_block,
    remove_design_block,
    set_design_props,
    set_design_visibility,
    set_submit_definition,
)
from forge_design.generate import generate_simple_template
from forge_design.limits import MAX_DESIGN_ISSUES, MAX_DESIGN_NODES
from forge_design.preview import generate_preview_data, render_preview

SAVE = {"label": "Enregistrer"}
EMAIL = {"name": "email", "input_type": "email"}
ACTIONS = {
    "create_contact": {"method": "POST", "path": "/contacts"},
    "cancel": {"method": "GET", "path": "/contacts"},
}


def submit(label: str = "Enregistrer", **extra: Any) -> dict[str, Any]:
    return {"type": "button", "submit": {"label": label}, **extra}


def form(*children: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {"type": "form", "children": list(children), **extra}


def page(*blocks: dict[str, Any]) -> DesignFile:
    model = design([{"type": "section", "children": list(blocks)}])
    assert validate_design_nesting(model).valid
    return model


def codes(issues: tuple[SubmitButtonIssue, ...]) -> list[str]:
    return [issue.code.removeprefix("design.submit.") for issue in issues]


def node_at(model: DesignFile, path: tuple[int, ...]) -> Any:
    node: Any = model.model_dump(exclude_unset=True)["root"]
    for index in path:
        node = node["children"][index]
    return node


# Modèle.


def test_submit_definition_nominal() -> None:
    value = SubmitDefinition.model_validate(SAVE)
    assert value.model_dump(exclude_unset=True) == SAVE


@pytest.mark.parametrize(
    "data",
    [
        {"label": ""},
        {"label": None},
        {},
        {"label": "Ok", "name": "go"},
        {"label": "Ok", "value": "1"},
        {"label": "Ok", "formaction": "/x"},
        {"label": 3},
    ],
)
def test_submit_definition_invalid(data: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SubmitDefinition.model_validate(data)


def test_submit_null_refused_on_node() -> None:
    data = page(form(submit())).model_dump(exclude_unset=True)
    data["root"]["children"][0]["children"][0]["children"][0]["submit"] = None
    with pytest.raises(ValidationError):
        DesignFile.model_validate(data)


def test_frozen() -> None:
    value = SubmitDefinition.model_validate(SAVE)
    with pytest.raises(ValidationError):
        value.label = "x"  # type: ignore[misc]


def test_round_trip_json() -> None:
    model = page(form({"type": "field", "field": EMAIL}, submit(), binding="x"))
    dumped = model.model_dump(exclude_unset=True)
    assert DesignFile.model_validate_json(json.dumps(dumped)) == model


# Validation sémantique.


def test_submit_direct_child_of_form() -> None:
    assert validate_submit_buttons(page(form(submit()))).valid


@pytest.mark.parametrize("holder", ["container", "card"])
def test_submit_outside_form(holder: str) -> None:
    model = page({"type": holder, "children": [submit()]})
    result = validate_submit_buttons(model)
    assert codes(result.issues) == ["outside_form"]
    assert result.issues[0].location[-1] == "submit"


@pytest.mark.parametrize(
    "block",
    [
        {"type": "text", "submit": SAVE},
        {"type": "form", "submit": SAVE},
        {"type": "section", "submit": SAVE},
    ],
)
def test_unsupported_definition(block: dict[str, Any]) -> None:
    result = validate_submit_buttons(design([{"type": "section", "children": [block]}]))
    if block["type"] == "section":
        result = validate_submit_buttons(design([block]))
    assert codes(result.issues) == ["unsupported_definition"]


def test_unsupported_on_page_root() -> None:
    result = validate_submit_buttons(design([], submit=SAVE))
    assert codes(result.issues) == ["unsupported_definition"]
    assert result.issues[0].location == ("root", "submit")


def test_conflicting_action() -> None:
    result = validate_submit_buttons(page(form(submit(binding="save"))))
    assert codes(result.issues) == ["conflicting_action"]


def test_conflicting_and_outside() -> None:
    model = page({"type": "container", "children": [submit(binding="save")]})
    assert codes(validate_submit_buttons(model).issues) == [
        "conflicting_action",
        "outside_form",
    ]


def test_action_and_empty_buttons_ignored() -> None:
    model = page(
        form({"type": "button", "binding": "cancel"}, {"type": "button"}),
        {"type": "container", "children": [{"type": "button", "binding": "x"}]},
    )
    assert validate_submit_buttons(model).valid


def test_several_submits_and_forms() -> None:
    model = page(
        form(submit("Enregistrer"), submit("Enregistrer et fermer")),
        form(submit("Créer")),
    )
    assert validate_submit_buttons(model).valid


def test_truncation_by_issues() -> None:
    buttons = [submit(binding="x") for _ in range(MAX_DESIGN_ISSUES + 5)]
    result = validate_submit_buttons(page(form(*buttons)))
    assert result.truncated and len(result.issues) == MAX_DESIGN_ISSUES
    assert codes(result.issues)[-1] == "analysis_truncated"


def test_truncation_by_nodes() -> None:
    buttons = [submit() for _ in range(MAX_DESIGN_NODES)]
    model = design([{"type": "section", "children": [form(*buttons)]}])
    result = validate_submit_buttons(model)
    assert result.truncated and codes(result.issues) == ["analysis_truncated"]


def test_pure_and_deterministic() -> None:
    model = page({"type": "container", "children": [submit(binding="x")]})
    before = model.model_dump()
    assert validate_submit_buttons(model) == validate_submit_buttons(model)
    assert model.model_dump() == before


# Bindings : sémantique inchangée.


def test_bindings_action_button_still_valid() -> None:
    model = page(
        form({"type": "button", "binding": "cancel"}, binding="create_contact")
    )
    assert validate_design_bindings(model, contract({}, actions=ACTIONS)).valid


def test_bindings_submit_without_binding_not_reported() -> None:
    model = page(form(submit(), binding="create_contact"))
    assert validate_design_bindings(model, contract({}, actions=ACTIONS)).valid
    assert validate_form_fields(model).valid


# Éditeur.

BUTTON = (0, 0, 1)


def editable() -> DesignFile:
    return page(
        form(
            {"type": "field", "field": EMAIL},
            {"type": "button", "props": {"class": "btn"}, "visible_if": "show"},
            {"type": "button", "binding": "cancel"},
            binding="create_contact",
        ),
        {"type": "container", "children": [{"type": "button"}]},
    )


def assert_refused(result: DesignEditResult, original: DesignFile, code: str) -> None:
    assert not result.changed and result.affected_path is None
    assert result.design is original
    assert [issue.code for issue in result.issues] == ["editor." + code]


def test_set_nominal_preserves_other_properties() -> None:
    original = editable()
    result = set_submit_definition(
        original, path=BUTTON, submit=SubmitDefinition.model_validate(SAVE)
    )
    assert result.changed and result.affected_path == BUTTON
    assert node_at(result.design, BUTTON) == {
        "type": "button",
        "visible_if": "show",
        "props": {"class": "btn"},
        "submit": SAVE,
    }
    for other in ((0, 0, 0), (0, 0, 2), (0, 1)):
        assert node_at(result.design, other) == node_at(original, other)


def test_clear_and_noop() -> None:
    original = editable()
    with_submit = set_submit_definition(
        original, path=BUTTON, submit=SubmitDefinition.model_validate(SAVE)
    ).design
    same = set_submit_definition(
        with_submit, path=BUTTON, submit=SubmitDefinition.model_validate(SAVE)
    )
    assert same == DesignEditResult(with_submit, False, BUTTON, ())
    cleared = set_submit_definition(with_submit, path=BUTTON, submit=None)
    assert cleared.changed and "submit" not in node_at(cleared.design, BUTTON)
    nothing = set_submit_definition(original, path=BUTTON, submit=None)
    assert nothing == DesignEditResult(original, False, BUTTON, ())


@pytest.mark.parametrize("path", [(0,), (0, 0), (0, 0, 0), ()])
def test_not_a_button(path: tuple[int, ...]) -> None:
    original = editable()
    result = set_submit_definition(
        original, path=path, submit=SubmitDefinition.model_validate(SAVE)
    )
    assert_refused(result, original, "submit_not_supported")


def test_conflicting_action_refused() -> None:
    original = editable()
    result = set_submit_definition(
        original, path=(0, 0, 2), submit=SubmitDefinition.model_validate(SAVE)
    )
    assert_refused(result, original, "submit_conflicting_action")


def test_outside_form_refused() -> None:
    original = editable()
    result = set_submit_definition(
        original, path=(0, 1, 0), submit=SubmitDefinition.model_validate(SAVE)
    )
    assert_refused(result, original, "submit_outside_form")


@pytest.mark.parametrize("value", [SAVE, "Enregistrer", 3])
def test_invalid_value(value: Any) -> None:
    original = editable()
    result = set_submit_definition(original, path=BUTTON, submit=value)
    assert_refused(result, original, "invalid_submit")


def test_progressive_correction() -> None:
    # Submits invalides ailleurs : la correction locale reste possible.
    broken = page(
        form(submit(binding="x"), {"type": "button"}),
        {"type": "container", "children": [submit()]},
    )
    assert not validate_submit_buttons(broken).valid
    added = set_submit_definition(
        broken, path=(0, 0, 1), submit=SubmitDefinition.model_validate(SAVE)
    )
    assert added.changed
    repaired = set_submit_definition(broken, path=(0, 1, 0), submit=None)
    assert repaired.changed
    unsupported = design([{"type": "section", "submit": SAVE}])
    cleared = set_submit_definition(unsupported, path=(0,), submit=None)
    assert cleared.changed and validate_submit_buttons(cleared.design).valid


def test_caller_object_not_shared() -> None:
    definition = SubmitDefinition.model_validate(SAVE)
    result = set_submit_definition(editable(), path=BUTTON, submit=definition)
    stored: Any = result.design.root.children[0]
    stored = stored.children[0].children[1].submit
    assert stored == definition and stored is not definition


# Préservation par les autres opérations.


def with_submit() -> DesignFile:
    return set_submit_definition(
        editable(), path=BUTTON, submit=SubmitDefinition.model_validate(SAVE)
    ).design


def test_property_operations_keep_submit() -> None:
    model = with_submit()
    c = contract({"show": {"type": "boolean"}}, actions=ACTIONS)
    for result in (
        set_design_props(model, path=BUTTON, props={"class": "x"}),
        set_design_props(model, path=BUTTON, props=None),
        set_design_visibility(model, path=BUTTON, visible_if=None, contract=c),
    ):
        assert result.changed and node_at(result.design, BUTTON)["submit"] == SAVE


def test_structural_operations_keep_submit() -> None:
    model = with_submit()
    appended = append_design_block(model, parent=(0, 0), block_type="field")
    assert node_at(appended.design, BUTTON)["submit"] == SAVE
    removed = remove_design_block(model, path=(0, 0, 0))
    assert node_at(removed.design, (0, 0, 0))["submit"] == SAVE
    moved = move_design_block(model, source=BUTTON, destination=(0, 0))
    assert moved.affected_path is not None
    assert node_at(moved.design, moved.affected_path)["submit"] == SAVE
    # Déplacé hors du form : nesting le permet, le validateur le signale après coup.
    outside = move_design_block(model, source=BUTTON, destination=(0, 1))
    assert outside.changed and outside.affected_path is not None
    assert node_at(outside.design, outside.affected_path)["submit"] == SAVE
    assert codes(validate_submit_buttons(outside.design).issues) == ["outside_form"]


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
                                {"type": "button", "submit": SAVE},
                            ],
                        }
                    ],
                }
            ],
        },
    }


def test_web_mutations_keep_submit(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    write(root, web_design())

    def button() -> Any:
        return on_disk(root)["root"]["children"][0]["children"][0]["children"][-1]

    with serving(root, tmp_path) as app:
        for fields in (
            {"action": "props", "path": "0.0.1", "props": '{"class": "btn"}'},
            {"action": "tailwind_add", "path": "0.0.1", "class_token": "px-4"},
            {"action": "tailwind_remove", "path": "0.0.1", "class_token": "btn"},
            {"action": "visibility", "path": "0.0.1", "visible_if": "can_view"},
            {"action": "append", "parent": "0.0", "block_type": "field"},
            {"action": "remove", "path": "0.0.2"},
        ):
            assert action(app, **fields)[0] == 303, fields
    assert button()["submit"] == SAVE
    assert button()["props"] == {"class": "px-4"}


# Persistance.


def test_read_write_keep_submit(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    # write_design ne crée aucun dossier parent (FD-DESIGN-004).
    (views / "x").mkdir()
    model = page(form({"type": "field", "field": EMAIL}, submit(), binding="create"))
    written = write_design(root, "x/new.design.json", model, expected_revision=None)
    read = read_design(root, "x/new.design.json")
    assert read.design == model and read.issues == ()
    assert read.design is not None
    assert node_at(read.design, (0, 0, 1))["submit"] == SAVE
    saved = json.loads((root / "mvc/views/x/new.design.json").read_text())
    assert saved["root"]["children"][0]["children"][0]["children"][1] == submit()
    assert written.revision == read.revision


# Génération et preview reportées.


def test_generation_now_emits_submit() -> None:
    # Limite levée par FD-INTERACT-005 : le submit est généré.
    model = page(
        form({"type": "field", "field": EMAIL}, submit(), binding="create_contact")
    )
    result = generate_simple_template(model, contract({}, actions=ACTIONS))
    assert result.complete and result.issues == ()
    assert '<button type="submit">Enregistrer</button>' in result.template


def test_preview_unchanged() -> None:
    model = page(form(submit(), binding="create_contact"))
    c = contract({}, actions=ACTIONS)
    html = render_preview(model, generate_preview_data(c).data).html
    assert 'type="submit"' not in html and "Enregistrer" not in html


def test_inputs_not_mutated() -> None:
    model = editable()
    before = copy.deepcopy(model.model_dump())
    set_submit_definition(
        model, path=BUTTON, submit=SubmitDefinition.model_validate(SAVE)
    )
    assert model.model_dump() == before


def test_form_ancestor_is_not_enough() -> None:
    # Imbrication invalide construite à dessein : le validateur exige le parent
    # direct, indépendamment de nesting.
    model = design(
        [
            {
                "type": "section",
                "children": [form({"type": "container", "children": [submit()]})],
            }
        ]
    )
    assert not validate_design_nesting(model).valid
    assert codes(validate_submit_buttons(model).issues) == ["outside_form"]


def test_parent_error_does_not_block_child_edit() -> None:
    broken = page(form({"type": "button"}, submit=SAVE))
    assert codes(validate_submit_buttons(broken).issues) == ["unsupported_definition"]
    result = set_submit_definition(
        broken, path=(0, 0, 0), submit=SubmitDefinition.model_validate(SAVE)
    )
    assert result.changed


def test_duck_typed_submit_refused() -> None:
    class LooksLikeSubmit:
        def model_dump(self, **kwargs: Any) -> dict[str, Any]:
            return dict(SAVE)

    original = editable()
    result = set_submit_definition(
        original,
        path=BUTTON,
        submit=LooksLikeSubmit(),  # type: ignore[arg-type]
    )
    assert_refused(result, original, "invalid_submit")
