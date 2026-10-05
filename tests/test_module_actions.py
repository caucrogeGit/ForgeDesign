"""Actions bornées des modules (FD-EDIT-001) : contrat, payload, jeton, cycle hôte."""

import json
import logging
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from module_support import (
    RENAME,
    RecordingCodec,
    activation,
    rename_title,
    witness_module,
    write_resource,
)
from specialized_support import WitnessDocument, witness_tool, witness_type
from test_web_recent_projects import project

import forge_design.modules.host as host_module
from forge_design.modules import (
    MAX_MODULE_ACTION_FIELDS,
    MAX_MODULE_ACTION_TEXT_CHARS,
    MAX_MODULE_ACTIONS,
    MAX_SAFE_INTEGER,
    MODULE_API_VERSION,
    ModuleAction,
    ModuleActionPayload,
    ModuleActionPayloadError,
    ModuleActionRefused,
    ModuleActionResult,
    ModuleDescriptor,
    ResourceBinding,
)
from forge_design.modules.actions import bounded_message, revision_token
from forge_design.modules.host import ModuleHost
from forge_design.specialized import (
    SpecializedCapability,
    SpecializedIssue,
    SpecializedResourceError,
    SpecializedResourceHistoryError,
    SpecializedResourceRevision,
    SpecializedValidationResult,
)

REVISION = SpecializedResourceRevision(10, 1, "a" * 64, 2, 3, 4)


def handler(document: Any, payload: ModuleActionPayload) -> ModuleActionResult:
    return ModuleActionResult(document)


def action(**changes: Any) -> ModuleAction:
    values: dict[str, Any] = {
        "id": "rename-title",
        "resource_type": "document",
        "fields": ("title",),
        "handler": handler,
    }
    values.update(changes)
    return ModuleAction(**values)


# --- Contrat ModuleAction et descripteur -------------------------------------


@pytest.mark.parametrize(
    "changes",
    [
        {"id": "Rename"},
        {"id": "rename_title"},
        {"id": ""},
        {"id": "a" * 49},
        {"resource_type": ""},
        {"fields": ["title"]},
        {"fields": tuple(f"f{i}" for i in range(MAX_MODULE_ACTION_FIELDS + 1))},
        {"fields": ("Title",)},
        {"fields": ("a" * 33,)},
        {"fields": ("type",)},
        {"fields": ("path",)},
        {"fields": ("revision",)},
        {"fields": ("_method",)},
        {"fields": ("title", "title")},
        {"handler": "pas un appel"},
        {"capability": "simulate"},
    ],
)
def test_action_declaration_is_checked(changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        action(**changes)


def test_action_defaults() -> None:
    declared = action()
    assert declared.capability == "edit" and declared.fields == ("title",)
    assert action(fields=()).fields == ()


def descriptor(*actions: ModuleAction, **type_changes: Any) -> ModuleDescriptor:
    resource_type = witness_type(**type_changes)
    return ModuleDescriptor(
        definition=witness_tool(resource_type),
        version="1.0.0",
        api_version=MODULE_API_VERSION,
        bindings=(ResourceBinding("document", RecordingCodec()),),
        actions=actions,
    )


def test_descriptor_actions_are_optional_and_api_stays_1() -> None:
    assert MODULE_API_VERSION == 1
    plain = descriptor()
    assert plain.actions == ()
    with pytest.raises(KeyError):
        plain.action_url("rename-title")
    module = descriptor(RENAME)
    assert module.action_url("rename-title") == "/modules/witness/actions/rename-title"


def without(name: str) -> tuple[SpecializedCapability, ...]:
    return tuple(
        SpecializedCapability.platform(item)  # type: ignore[arg-type]
        for item in ("create", "open", "edit", "validate", "save")
        if item != name
    )


@pytest.mark.parametrize(
    "actions,type_changes",
    [
        ((action(resource_type="autre"),), {}),
        ((RENAME,), {"editable": False}),
        ((RENAME,), {"capabilities": without("save")}),
        ((RENAME,), {"capabilities": without("edit")}),
        ((action(capability="export"),), {}),
        ((RENAME, action(fields=())), {}),
        (tuple(action(id=f"a{i}") for i in range(MAX_MODULE_ACTIONS + 1)), {}),
    ],
)
def test_descriptor_refuses_unsound_actions(
    actions: tuple[ModuleAction, ...], type_changes: dict[str, Any]
) -> None:
    with pytest.raises(ValueError):
        descriptor(*actions, **type_changes)


def test_descriptor_refuses_non_action_items() -> None:
    with pytest.raises(ValueError):
        descriptor(object())  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ModuleDescriptor(
            definition=witness_tool(),
            version="1.0.0",
            api_version=MODULE_API_VERSION,
            bindings=(ResourceBinding("document", RecordingCodec()),),
            actions=[RENAME],  # type: ignore[arg-type]
        )


# --- Payload ------------------------------------------------------------------


def test_payload_is_a_bounded_read_only_mapping() -> None:
    payload = ModuleActionPayload({"title": "Après", "x": "12"})
    assert dict(payload) == {"title": "Après", "x": "12"} and len(payload) == 2
    assert payload["x"] == "12" and "title" in payload
    with pytest.raises(TypeError):
        payload["x"] = "13"  # type: ignore[index]
    for fields in (
        {f"f{i}": "" for i in range(MAX_MODULE_ACTION_FIELDS + 1)},
        {"type": "x"},
        {"Titre": "x"},
        {"title": "x" * (MAX_MODULE_ACTION_TEXT_CHARS + 1)},
        {"title": "a\x00b"},
        {"title": "a\x1bb"},
        {"title": 3},
    ):
        with pytest.raises(ValueError):
            ModuleActionPayload(fields)  # type: ignore[arg-type]
    # Tabulation et fins de ligne restent du texte.
    assert ModuleActionPayload({"note": "a\tb\r\nc"})["note"] == "a\tb\r\nc"


def test_payload_text() -> None:
    payload = ModuleActionPayload({"title": "  ", "name": "abc"})
    assert payload.text("title") == "  "
    with pytest.raises(ModuleActionPayloadError, match="vide"):
        payload.text("title", empty=False)
    with pytest.raises(ModuleActionPayloadError, match="trop long"):
        payload.text("name", max_chars=2)
    with pytest.raises(ModuleActionPayloadError, match="absent"):
        payload.text("missing")


@pytest.mark.parametrize("value", ["0", "-0", "12", "-12", str(MAX_SAFE_INTEGER)])
def test_payload_integer_accepts_safe_canonical_integers(value: str) -> None:
    assert ModuleActionPayload({"x": value}).integer("x") == int(value)


@pytest.mark.parametrize(
    "value",
    ["", "01", "+1", "1.0", " 1", "1 ", "1e3", "0x10", "١", str(MAX_SAFE_INTEGER + 1)],
)
def test_payload_integer_refuses_other_forms(value: str) -> None:
    with pytest.raises(ModuleActionPayloadError):
        ModuleActionPayload({"x": value}).integer("x")


def test_payload_integer_bounds() -> None:
    payload = ModuleActionPayload({"x": "5"})
    assert payload.integer("x", minimum=5, maximum=5) == 5
    with pytest.raises(ModuleActionPayloadError, match="bornes"):
        payload.integer("x", maximum=4)
    with pytest.raises(ModuleActionPayloadError, match="bornes"):
        payload.integer("x", minimum=6)


@pytest.mark.parametrize(
    "value,expected", [("1.5", 1.5), ("-2", -2.0), ("1e3", 1000.0), ("0.25E-1", 0.025)]
)
def test_payload_number(value: str, expected: float) -> None:
    assert ModuleActionPayload({"x": value}).number("x") == expected


@pytest.mark.parametrize("value", ["NaN", "inf", "-Infinity", "1e400", ".5", "1.", ""])
def test_payload_number_is_finite_and_canonical(value: str) -> None:
    with pytest.raises(ModuleActionPayloadError):
        ModuleActionPayload({"x": value}).number("x")


def test_payload_boolean_and_no_null() -> None:
    payload = ModuleActionPayload({"a": "true", "b": "false", "c": "1", "d": "null"})
    assert payload.boolean("a") is True and payload.boolean("b") is False
    for key in ("c", "d"):
        with pytest.raises(ModuleActionPayloadError):
            payload.boolean(key)


def test_bounded_message() -> None:
    assert bounded_message(ValueError("a\x00b\n  c")) == "a b c"
    long = bounded_message(ValueError("x" * 500))
    assert len(long) == 200 and long.endswith("…")


# --- Jeton de révision --------------------------------------------------------


def test_revision_token_is_opaque_and_exact() -> None:
    token = revision_token(
        "witness", "document", "mvc/witness/a.witness.json", REVISION
    )
    assert re.fullmatch(r"[0-9a-f]{64}", token)
    assert token == revision_token(
        "witness", "document", "mvc/witness/a.witness.json", REVISION
    )
    variants = [
        revision_token("autre", "document", "mvc/witness/a.witness.json", REVISION),
        revision_token("witness", "doc", "mvc/witness/a.witness.json", REVISION),
        revision_token("witness", "document", "mvc/witness/b.witness.json", REVISION),
    ]
    for field in ("size", "modified_ns", "device", "inode", "changed_ns"):
        changed = replace(REVISION, **{field: getattr(REVISION, field) + 1})
        variants.append(
            revision_token("witness", "document", "mvc/witness/a.witness.json", changed)
        )
    variants.append(
        revision_token(
            "witness",
            "document",
            "mvc/witness/a.witness.json",
            replace(REVISION, digest="b" * 64),
        )
    )
    assert token not in variants and len(set(variants)) == len(variants)
    # Ni condensat brut ni champ de révision lisible.
    assert REVISION.digest not in token


# --- Cycle hôte -----------------------------------------------------------------


class StrictCodec(RecordingCodec):
    """Témoin : un titre « INTERDIT » est une erreur bloquante (structure)."""

    def validate(self, resource: WitnessDocument) -> SpecializedValidationResult:
        result = super().validate(resource)
        if resource.title == "INTERDIT":
            issue = SpecializedIssue(
                "witness.forbidden", "error", "Titre interdit.", "structure", ("title",)
            )
            return SpecializedValidationResult.bounded((*result.issues, issue))
        return result


def make_host(*actions: ModuleAction, codec: Any = None, **options: Any) -> ModuleHost:
    module = witness_module(actions=actions or (RENAME,), codec=codec, **options)
    return ModuleHost(activation(("pkg_witness", module)))


def history(root: Path) -> list[dict[str, Any]]:
    file = root / ".forge-design/history.jsonl"
    if not file.exists():
        return []
    return [json.loads(line) for line in file.read_text().splitlines()]


def setup(tmp_path: Path, title: str = "Avant") -> tuple[Path, str]:
    root = project(tmp_path / "projet").resolve()
    return root, write_resource(root, "witness", "demo", title=title)


def token_of(host: ModuleHost, root: Path, path: str) -> str:
    view = host.read_resource("witness", "document", root, path)
    assert view.revision_token is not None
    return view.revision_token


def run(
    host: ModuleHost,
    root: Path,
    path: str,
    token: str,
    fields: dict[str, str] | None = None,
    *,
    action_id: str = "rename-title",
    type_id: str = "document",
) -> Any:
    return host.execute_action(
        "witness",
        action_id,
        root,
        type_id,
        path,
        token,
        {"title": "Après"} if fields is None else fields,
    )


def title_of(root: Path, path: str) -> str:
    return json.loads((root / path).read_text())["title"]


def test_nominal_read_transform_write(tmp_path: Path) -> None:
    root, path = setup(tmp_path)
    host = make_host()
    before = token_of(host, root, path)
    outcome = run(host, root, path, before)
    assert outcome.code == "saved" and outcome.message == "Modification enregistrée."
    assert title_of(root, path) == "Après"
    assert [line["action"] for line in history(root)] == ["write_specialized_resource"]
    assert history(root)[0]["file"] == path
    after = token_of(host, root, path)
    assert after != before and outcome.revision is not None
    assert after == revision_token("witness", "document", path, outcome.revision)
    # Le jeton consommé est désormais périmé.
    assert run(host, root, path, before, {"title": "Encore"}).code == "conflict"


def test_handler_receives_only_document_and_payload(tmp_path: Path) -> None:
    root, path = setup(tmp_path)
    received: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def spy(*args: Any, **kwargs: Any) -> ModuleActionResult:
        received.append((args, kwargs))
        return rename_title(*args)

    host = make_host(action(handler=spy))
    assert run(host, root, path, token_of(host, root, path)).code == "saved"
    # Exactement (document, payload) : ni Request, ni racine, ni chemin, ni hôte.
    ((args, kwargs),) = received
    assert kwargs == {} and len(args) == 2
    document, payload = args
    assert type(document) is WitnessDocument and document.title == "Avant"
    assert type(payload) is ModuleActionPayload and dict(payload) == {"title": "Après"}


def test_unchanged_document_is_not_written(tmp_path: Path) -> None:
    root, path = setup(tmp_path)
    host = make_host()
    token = token_of(host, root, path)
    stat = (root / path).stat()
    outcome = run(host, root, path, token, {"title": "Avant"})
    assert outcome.code == "unchanged" and history(root) == []
    assert (root / path).stat().st_mtime_ns == stat.st_mtime_ns
    assert token_of(host, root, path) == token


def test_stale_revision_is_a_conflict_without_write(tmp_path: Path) -> None:
    root, path = setup(tmp_path)
    host = make_host()
    token = token_of(host, root, path)
    write_resource(root, "witness", "demo", title="Autre onglet")
    outcome = run(host, root, path, token)
    assert outcome.code == "conflict" and title_of(root, path) == "Autre onglet"
    assert history(root) == []


def test_conflict_detected_by_the_resource_host_during_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, path = setup(tmp_path)

    def concurrent(document: Any, payload: ModuleActionPayload) -> ModuleActionResult:
        # Écriture concurrente entre la lecture de l'hôte et sa publication.
        write_resource(root, "witness", "demo", title="Concurrent")
        return rename_title(document, payload)

    host = make_host(action(handler=concurrent))
    outcome = run(host, root, path, token_of(host, root, path))
    assert outcome.code == "conflict" and title_of(root, path) == "Concurrent"
    assert history(root) == []


@pytest.mark.parametrize(
    "fields,message",
    [
        ({}, "Champs attendus : title."),
        ({"title": "a", "extra": "b"}, "Champs attendus : title."),
        ({"title": "   "}, "Champ vide : title."),
        ({"title": "x" * 201}, "Champ trop long : title."),
        ({"title": "a\x00"}, "contrôle"),
    ],
)
def test_invalid_payload(tmp_path: Path, fields: dict[str, str], message: str) -> None:
    root, path = setup(tmp_path)
    host = make_host()
    outcome = run(host, root, path, token_of(host, root, path), fields)
    assert outcome.code == "payload-invalid" and message in outcome.message
    assert title_of(root, path) == "Avant" and history(root) == []


def test_envelope_errors(tmp_path: Path) -> None:
    root, path = setup(tmp_path)
    host = make_host()
    token = token_of(host, root, path)
    assert run(host, root, path, "0" * 63).code == "payload-invalid"
    assert run(host, root, path, token.upper()).code == "payload-invalid"
    assert run(host, root, path, token, type_id="autre").code == "type-mismatch"
    missing = "mvc/witness/absent.witness.json"
    assert run(host, root, missing, token).code == "resource-not-found"
    for refused in (
        "mvc/witness/../witness/demo.witness.json",
        "../demo.witness.json",
        "/etc/passwd",
        "mvc/witness/demo.json",
    ):
        assert run(host, root, refused, token).code == "resource-refused"
    with pytest.raises(KeyError):
        run(host, root, path, token, action_id="inconnue")
    assert title_of(root, path) == "Avant" and history(root) == []


def test_unusable_resource_is_not_edited(tmp_path: Path) -> None:
    root = project(tmp_path / "projet").resolve()
    host = make_host()
    for name, raw in (("casse", b"{"), ("futur", b'{"format_version": "9.9"}')):
        path = write_resource(root, "witness", name, raw=raw)
        view = host.read_resource("witness", "document", root, path)
        assert view.read is not None and view.read.revision is not None
        token = view.revision_token
        assert token is not None
        outcome = run(host, root, path, token)
        assert outcome.code == "resource-unusable" and outcome.issues
    assert history(root) == []


def test_business_refusal_and_payload_error_from_module(tmp_path: Path) -> None:
    root, path = setup(tmp_path)

    def refuse(document: Any, payload: ModuleActionPayload) -> ModuleActionResult:
        raise ModuleActionRefused("Élément\x00 introuvable\n: x9")

    def bad_payload(document: Any, payload: ModuleActionPayload) -> ModuleActionResult:
        payload.integer("title")
        raise AssertionError("inaccessible")

    host = make_host(action(handler=refuse), action(id="numero", handler=bad_payload))
    outcome = run(host, root, path, token_of(host, root, path))
    assert outcome.code == "refused" and outcome.message == "Élément introuvable : x9"
    outcome = run(host, root, path, token_of(host, root, path), action_id="numero")
    assert outcome == host_module.ModuleActionOutcome(
        "payload-invalid", "Entier attendu : title."
    )
    assert title_of(root, path) == "Avant" and history(root) == []


def test_module_exception_is_isolated_and_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    root, path = setup(tmp_path)

    def broken(document: Any, payload: ModuleActionPayload) -> ModuleActionResult:
        raise RuntimeError("/home/secret/trace")

    def wrong(document: Any, payload: ModuleActionPayload) -> Any:
        return document

    def mutating(document: Any, payload: ModuleActionPayload) -> ModuleActionResult:
        object.__setattr__(document, "title", "Muté")
        return ModuleActionResult(document)

    host = make_host(
        action(handler=broken),
        action(id="wrong", handler=wrong),
        action(id="mutating", handler=mutating),
    )
    with caplog.at_level(logging.WARNING, logger="forge_design.modules"):
        outcome = run(host, root, path, token_of(host, root, path))
    assert outcome.code == "module-error"
    assert outcome.message == "Action du module en échec (RuntimeError)."
    assert "/home/secret" not in outcome.message
    assert any(record.exc_info for record in caplog.records)
    outcome = run(host, root, path, token_of(host, root, path), action_id="wrong")
    assert outcome.code == "module-error" and "ModuleActionResult" in outcome.message
    outcome = run(host, root, path, token_of(host, root, path), action_id="mutating")
    assert outcome.code == "module-error" and "document lu" in outcome.message
    assert title_of(root, path) == "Avant" and history(root) == []


def test_blocking_validation_prevents_write(tmp_path: Path) -> None:
    root, path = setup(tmp_path)
    host = make_host(codec=StrictCodec())
    outcome = run(host, root, path, token_of(host, root, path), {"title": "INTERDIT"})
    assert outcome.code == "invalid-resource"
    assert [issue.code for issue in outcome.issues] == ["witness.forbidden"]
    assert title_of(root, path) == "Avant" and history(root) == []
    # Un avertissement (niveau non bloquant) n'empêche pas l'écriture.
    host = make_host()
    outcome = run(host, root, path, token_of(host, root, path), {"title": "Ok"})
    assert outcome.code == "saved"


@pytest.mark.parametrize(
    "error,code",
    [
        (SpecializedResourceError("disque"), "write-failed"),
        (
            SpecializedResourceHistoryError.__new__(SpecializedResourceHistoryError),
            "write-failed",
        ),
        (RuntimeError("codec"), "module-error"),
    ],
)
def test_write_failures_are_controlled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception, code: str
) -> None:
    root, path = setup(tmp_path)
    host = make_host()
    token = token_of(host, root, path)

    def failing(*args: object, **kwargs: object) -> None:
        raise error

    monkeypatch.setattr(host_module, "write_specialized_resource", failing)
    outcome = run(host, root, path, token)
    assert outcome.code == code and "Traceback" not in outcome.message


def test_capability_gate_and_read_only_modules(tmp_path: Path) -> None:
    root, path = setup(tmp_path)
    unavailable = make_host(probe=lambda: {"spice": False}, edit_dependency=True)
    assert unavailable.actions("witness") == ()
    with pytest.raises(KeyError):
        unavailable.action("witness", "rename-title")
    view = unavailable.read_resource("witness", "document", root, path)
    assert view.revision_token is None
    available = make_host(probe=lambda: {"spice": True}, edit_dependency=True)
    assert available.action("witness", "rename-title") is RENAME

    # Une sonde en échec rend la capacité indisponible : aucune action.
    def failing_probe() -> dict[str, bool]:
        raise RuntimeError("sonde")

    assert make_host(probe=failing_probe, edit_dependency=True).actions("witness") == ()
    read_only = ModuleHost(activation(("pkg_witness", witness_module())))
    assert read_only.actions("witness") == ()
    view = read_only.read_resource("witness", "document", root, path)
    assert view.revision_token is None and view.read is not None


def test_actions_are_namespaced_per_module(tmp_path: Path) -> None:
    root = project(tmp_path / "projet").resolve()
    path_b = write_resource(root, "other", "b")
    rename_b = action(handler=rename_title)
    host = ModuleHost(
        activation(
            ("pkg_witness", witness_module(actions=(RENAME,))),
            ("pkg_other", witness_module("other", actions=(rename_b,))),
        )
    )
    assert host.action("witness", "rename-title") is RENAME
    assert host.action("other", "rename-title") is rename_b
    token_b = host.read_resource("other", "document", root, path_b).revision_token
    assert token_b is not None
    # Action de « witness » sur une ressource de « other » : refusée par l'hôte.
    outcome = host.execute_action(
        "witness", "rename-title", root, "document", path_b, token_b, {"title": "X"}
    )
    assert outcome.code == "resource-refused"
    assert title_of(root, path_b) == "Titre" and history(root) == []
