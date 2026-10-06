"""Script d'édition des modules (FD-GRAPHICS-EDIT-001) : déclaration, contexte, page."""

import json
import logging
import re
from html import unescape
from pathlib import Path
from typing import Any

import pytest
from module_support import RENAME, activation, witness_module, write_resource
from test_module_actions import StrictCodec
from test_web_module_actions import ACTION, opened, post
from test_web_modules import resource, serving
from test_web_recent_projects import call, project

import forge_design.modules.host as host_module
from forge_design.modules import (
    MODULE_API_VERSION,
    ModuleAsset,
    ModuleDescriptor,
    ResourceBinding,
)
from forge_design.modules.host import ModuleHost

SCRIPT = ModuleAsset("witness-editor.js", "static/module-resource.js")
STYLE = ModuleAsset("witness.css", "static/shell.css")
HOSTILE = "</script><script>alert(1)</script>"


def config(document: Any) -> dict[str, Any]:
    return {"title": document.title, "step": 10, "hostile": HOSTILE}


def editing(**options: Any) -> ModuleDescriptor:
    values: dict[str, Any] = {
        "actions": (RENAME,),
        "assets": (STYLE, SCRIPT),
        "editor_script": SCRIPT.name,
        "editor_config": config,
    }
    values.update(options)
    return witness_module(**values)


def view_of(descriptor: ModuleDescriptor, tmp_path: Path, **resource: Any) -> Any:
    tmp_path.mkdir(parents=True, exist_ok=True)
    root = project(tmp_path / "projet").resolve()
    path = write_resource(root, "witness", "demo", **resource)
    host = ModuleHost(activation(("pkg_witness", descriptor)))
    return host.read_resource("witness", "document", root, path), path


def test_editor_fields_are_optional_and_api_stays_1() -> None:
    binding = ResourceBinding("document", StrictCodec())
    assert binding.editor_script is None and binding.editor_config is None
    assert editing().api_version == MODULE_API_VERSION == 1
    assert witness_module().bindings[0].editor_script is None


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"editor_script": "x.css"}, "nom d'asset .js"),
        ({"editor_script": "../x.js"}, "nom d'asset .js"),
        ({"editor_script": "Editor.js"}, "nom d'asset .js"),
        ({"editor_script": 3}, "nom d'asset .js"),
        ({"editor_config": "non"}, "appelable"),
        ({"editor_script": None}, "exige un script"),
        ({"scene": None}, "exige une projection"),
    ],
)
def test_binding_refuses_unsound_editor(changes: dict[str, Any], message: str) -> None:
    values: dict[str, Any] = {
        "resource_type": "document",
        "codec": StrictCodec(),
        "scene": config,
        "editor_script": "witness-editor.js",
        "editor_config": config,
    }
    values.update(changes)
    with pytest.raises(ValueError, match=message):
        ResourceBinding(**values)


def test_descriptor_requires_a_declared_script() -> None:
    with pytest.raises(ValueError, match="Script d'édition non déclaré"):
        editing(assets=(STYLE,))


def test_context_is_computed_by_the_host(tmp_path: Path) -> None:
    view, path = view_of(editing(), tmp_path, title="Avant")
    assert view.revision_token is not None and view.editor_error is None
    assert view.editor == {
        "script": "/modules/witness/assets/witness-editor.js",
        "type": "document",
        "path": path,
        "revision": view.revision_token,
        "actions": {"rename-title": ACTION},
        "config": {"title": "Avant", "step": 10, "hostile": HOSTILE},
    }


@pytest.mark.parametrize(
    "options",
    [
        {"actions": ()},
        {"editor_script": None, "editor_config": None},
        {"probe": lambda: {"spice": False}, "edit_dependency": True},
    ],
    ids=["read-only", "no-script", "capability-unavailable"],
)
def test_no_context_without_exposed_action_or_script(
    tmp_path: Path, options: dict[str, Any]
) -> None:
    view, _ = view_of(editing(**options), tmp_path)
    assert view.editor is None and view.editor_error is None


def test_no_context_without_scene_or_document(tmp_path: Path) -> None:
    def failing(document: Any) -> Any:
        raise RuntimeError("projection")

    view, _ = view_of(editing(scene=failing), tmp_path / "a")
    assert view.scene is None and view.editor is None
    view, _ = view_of(editing(), tmp_path / "b", raw=b"{")
    assert view.read is not None and view.read.resource is None
    assert view.editor is None and view.editor_error is None


def test_context_without_config(tmp_path: Path) -> None:
    view, _ = view_of(editing(editor_config=None), tmp_path)
    assert view.editor is not None and view.editor["config"] == {}


def test_failing_config_is_isolated(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(document: Any) -> Any:
        raise RuntimeError("/home/secret")

    def listing(document: Any) -> Any:
        return [1]

    def not_a_number(document: Any) -> Any:
        return {"x": float("nan")}

    def a_set(document: Any) -> Any:
        return {"x": {1, 2}}

    cases: list[tuple[Any, str]] = [
        (broken, "Configuration d'édition du module en échec (RuntimeError)."),
        (listing, "la configuration du module n'est pas un objet."),
        (not_a_number, "n'est pas du JSON."),
        (a_set, "n'est pas du JSON."),
    ]
    with caplog.at_level(logging.WARNING, logger="forge_design.modules"):
        for index, (configure, message) in enumerate(cases):
            descriptor = editing(editor_config=configure)
            view, _ = view_of(descriptor, tmp_path / str(index))
            assert view.editor is None and view.scene is not None
            assert view.editor_error.startswith("Édition indisponible : ")
            assert view.editor_error.endswith(message)
            assert "secret" not in view.editor_error
    assert any(record.exc_info for record in caplog.records)


def test_config_is_bounded_and_detached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared = {"list": [1]}

    def configure(document: Any) -> Any:
        return shared

    view, _ = view_of(editing(editor_config=configure), tmp_path / "a")
    view.editor["config"]["list"].append(2)
    assert shared == {"list": [1]}
    monkeypatch.setattr(host_module, "MAX_MODULE_EDITOR_CONFIG_BYTES", 16)
    view, _ = view_of(editing(), tmp_path / "b")
    assert view.editor is None and view.editor_error is not None
    assert view.editor_error.endswith("trop volumineuse.")


def editor_block(html: str) -> dict[str, Any] | None:
    match = re.search(
        r'<script type="application/json" data-module-editor>(.*?)</script>', html
    )
    return None if match is None else json.loads(match.group(1))


def test_resource_page_carries_the_inert_context(tmp_path: Path) -> None:
    root = project(tmp_path / "projet").resolve()
    path = write_resource(root, "witness", "demo", title="Avant")
    with serving(tmp_path, activation(("pkg_witness", editing()))) as app:
        opened(app, root)
        status, html, _ = call(app, resource("witness", path))
        assert status == 200
        context = editor_block(html)
        assert context is not None and context["config"]["hostile"] == HOSTILE
        # Texte hostile échappé : il ne ferme pas le bloc.
        assert html.count("</script>") == html.count("<script")
        assert "\\u003c/script\\u003e" in html
        token = re.search(r'data-revision-token="([0-9a-f]{64})"', html)
        assert token is not None and context["revision"] == token.group(1)
        assert "data-editor-status" in html
        assert '<script type="module" src="/module-resource.js">' in html
        # Le script déclaré est servi par l'hôte, en JavaScript.
        status, body, headers = call(app, context["script"])
        assert status == 200 and body.startswith("// Ressource d'un module")
        assert headers["Content-Type"] == "text/javascript; charset=utf-8"
        # Aucun script de module sur la page du module elle-même.
        status, html, _ = call(app, "/modules/witness/")
        assert status == 200 and "witness-editor.js" not in html
        assert editor_block(html) is None
        # L'action référencée dans le contexte est la route exacte de l'hôte.
        status, _, headers = post(
            app,
            context["actions"]["rename-title"],
            [
                ("type", context["type"]),
                ("path", context["path"]),
                ("revision", context["revision"]),
                ("title", "Après"),
            ],
        )
        assert status == 303 and headers["Location"].endswith("notice=saved")


def test_read_only_and_failing_config_pages(tmp_path: Path) -> None:
    root = project(tmp_path / "projet").resolve()
    path = write_resource(root, "witness", "demo")
    read_only = editing(actions=())
    with serving(tmp_path / "a", activation(("pkg_witness", read_only))) as app:
        opened(app, root)
        status, html, _ = call(app, resource("witness", path))
        assert status == 200 and editor_block(html) is None
        assert "data-editor-status" not in html and "data-revision-token" not in html

    def broken(document: Any) -> Any:
        raise RuntimeError("config")

    failing = editing(editor_config=broken)
    with serving(tmp_path / "b", activation(("pkg_witness", failing))) as app:
        opened(app, root)
        status, html, _ = call(app, resource("witness", path))
        assert status == 200 and editor_block(html) is None
        assert "data-graphic-scene" in html
        assert "Édition indisponible : Configuration d&#39;édition" in html or (
            "Édition indisponible : Configuration d'édition" in unescape(html)
        )


def test_action_error_page_marks_its_message(tmp_path: Path) -> None:
    root = project(tmp_path / "projet").resolve()
    path = write_resource(root, "witness", "demo")
    with serving(tmp_path, activation(("pkg_witness", editing()))) as app:
        opened(app, root)
        status, html, _ = post(
            app,
            ACTION,
            [("type", "document"), ("path", path), ("revision", "b" * 64)],
        )
        assert status == 400
        assert re.search(r'<p role="alert" data-action-error>[^<]+</p>', html)
