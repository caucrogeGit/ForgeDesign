"""Frontières du moteur générique (FD-ARCH-001).

Gardes de l'audit architectural, en complément de test_modules_contract.py :
exports publics revus, direction des dépendances au niveau des paquets, pile
Web Forge MVC, code de module limité au document et au payload, GraphicScene
jamais persistée, et un second domaine témoin (« flowchart-like », sans aucun
rapport avec Circuit) qui déclare une ressource, la projette, pose un calque,
déclare une action et modifie sa ressource par le seul contrat public.
"""

import ast
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import pytest
from flow_witness import (
    RENAME_STEP,
    FlowCodec,
    FlowDocument,
    broken_flow_module,
    flow_bytes,
    flow_editor_config,
    flow_module,
    flow_scene,
)
from module_support import RENAME, activation, witness_module
from test_module_editor import editor_block
from test_web_module_actions import opened, post
from test_web_modules import CORE_NAV, navigation, serving
from test_web_recent_projects import call, project

import forge_design.modules as modules_api
import forge_design.specialized as specialized_api
from forge_design.app import create_tool_registry
from forge_design.modules import (
    ModuleAction,
    ModuleActionPayload,
    ModuleActionResult,
    ModuleDescriptor,
    ResourceBinding,
)
from forge_design.modules.host import ModuleHost

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "forge_design"
FLOW_PATH = "mvc/flow/demo.flow.json"

# Contrat public revu (FD-ARCH-001) : tout ajout ou retrait est une décision.
MODULES_PUBLIC = {
    # Pour les modules : descripteur, liaison, assets, actions.
    "MODULE_API_VERSION",
    "ModuleDescriptor",
    "ResourceBinding",
    "ModuleAsset",
    "ModuleAction",
    "ModuleActionPayload",
    "ModuleActionPayloadError",
    "ModuleActionRefused",
    "ModuleActionResult",
    "ActionHandler",
    "MAX_MODULE_ACTIONS",
    "MAX_MODULE_ACTION_BYTES",
    "MAX_MODULE_ACTION_FIELDS",
    "MAX_MODULE_ACTION_KEY_CHARS",
    "MAX_MODULE_ACTION_TEXT_CHARS",
    "MAX_SAFE_INTEGER",
    "RESERVED_ACTION_FIELDS",
    # Côté hôte (activation, diagnostics, conventions d'URL et d'attribut).
    "SUPPORTED_MODULE_API_VERSIONS",
    "DESCRIPTOR_ATTRIBUTE",
    "MODULE_URL_PREFIX",
    "ASSET_MEDIA_TYPES",
    "ActiveModule",
    "ModuleActivation",
    "ModuleDiagnostic",
    "activate_modules",
}
SPECIALIZED_PUBLIC = {
    "MAX_SPECIALIZED_ISSUES",
    "MAX_SPECIALIZED_LOCATION_DEPTH",
    "PLATFORM_CAPABILITIES",
    "ErrorCategory",
    "InvalidSpecializedResourceError",
    "OptionalDependency",
    "PlatformCapability",
    "SpecializedCapability",
    "SpecializedCapabilityError",
    "SpecializedFormatError",
    "SpecializedIssue",
    "SpecializedReadResult",
    "SpecializedResourceCodec",
    "SpecializedResourceConflictError",
    "SpecializedResourceError",
    "SpecializedResourceListing",
    "SpecializedResourceHistoryError",
    "SpecializedResourceRef",
    "SpecializedResourceRefusedError",
    "SpecializedResourceRevision",
    "SpecializedResourceType",
    "SpecializedToolDefinition",
    "SpecializedValidationResult",
    "SpecializedWriteResult",
    "UiEntry",
    "UnsupportedSpecializedVersionError",
    "list_specialized_resources",
    "loads_strict_json",
    "read_specialized_resource",
    "write_specialized_resource",
}
# Dépendances autorisées du paquet distribué : bibliothèque standard, Forge MVC
# (paquets « core » et « integrations » de la distribution forge-mvc), Jinja (et
# markupsafe), pydantic, packaging. Rien d'autre.
THIRD_PARTY = {"core", "integrations", "jinja2", "markupsafe", "pydantic", "packaging"}
PARALLEL_WEB = {
    "flask",
    "fastapi",
    "starlette",
    "django",
    "bottle",
    "aiohttp",
    "tornado",
}


def _roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


# Exports.


def test_public_exports_are_a_reviewed_snapshot() -> None:
    assert set(modules_api.__all__) == MODULES_PUBLIC
    assert set(specialized_api.__all__) == SPECIALIZED_PUBLIC
    for api, names in (
        (modules_api, MODULES_PUBLIC),
        (specialized_api, SPECIALIZED_PUBLIC),
    ):
        assert len(api.__all__) == len(names), "aucun doublon"
        for name in names:
            assert hasattr(api, name), name


# Direction des dépendances.


def test_core_depends_only_on_stdlib_and_declared_packages() -> None:
    """Forge ← Forge Design ← modules : jamais un module, jamais une autre pile Web."""
    allowed = (
        set(sys.stdlib_module_names) | THIRD_PARTY | {"forge_design", "__future__"}
    )
    for path in sorted(PACKAGE.rglob("*.py")):
        roots = _roots(path)
        assert roots <= allowed, (path, roots - allowed)
        assert not roots & PARALLEL_WEB, path
        assert not any(name.startswith("forge_design_") for name in roots), path


def test_web_layer_dogfoods_forge_mvc() -> None:
    """Application, Router, Request, Response, Jinja et create_wsgi_app de Forge."""
    server = (PACKAGE / "web/server.py").read_text(encoding="utf-8")
    for needed in (
        "from core.app.application import Application",
        "from core.app.wsgi import create_wsgi_app",
        "from core.http.request import Request",
        "from core.http.response import Response",
        "from core.http.router import Router",
    ):
        assert needed in server, needed
    rendering = (PACKAGE / "web/rendering.py").read_text(encoding="utf-8")
    assert "from integrations.jinja2.renderer import" in rendering


def test_flow_witness_is_never_shipped() -> None:
    import tomllib

    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert not [p for p in config["tool"]["setuptools"]["packages"] if "flow" in p]
    assert not (PACKAGE / "flow_witness").exists()


# Second domaine : un module « flowchart-like » par le seul contrat public.


def _flow_host(*packages: tuple[str, ModuleDescriptor]) -> ModuleHost:
    return ModuleHost(activation(*packages))


def _flow_project(tmp_path: Path) -> Path:
    root = project(tmp_path / "projet").resolve()
    (root / "mvc/flow").mkdir(parents=True)
    (root / FLOW_PATH).write_bytes(flow_bytes())
    return root


def test_second_domain_declares_projects_edits_and_reloads(tmp_path: Path) -> None:
    root = _flow_project(tmp_path)
    host = _flow_host(("pkg_flow", flow_module()))
    view = host.read_resource("flow", "flow", root, FLOW_PATH)
    assert view.scene is not None and view.revision_token is not None
    assert [node["id"] for node in view.scene["nodes"]] == ["start", "check", "end"]
    assert [edge["id"] for edge in view.scene["edges"]] == ["start-check"]
    assert view.editor is not None
    assert view.editor["script"] == "/modules/flow/assets/flow-editor.js"
    assert view.editor["actions"] == {
        "rename-step": "/modules/flow/actions/rename-step"
    }
    assert view.editor["config"] == {
        "renameAction": "rename-step",
        "steps": ["start", "check", "end"],
    }
    outcome = host.execute_action(
        "flow",
        "rename-step",
        root,
        "flow",
        FLOW_PATH,
        view.revision_token,
        {"step": "check", "label": "Vérifier ✓"},
    )
    assert outcome.code == "saved"
    reloaded = host.read_resource("flow", "flow", root, FLOW_PATH)
    assert reloaded.scene is not None
    assert reloaded.scene["nodes"][1]["label"] == "Vérifier ✓"
    # Aucun module spécialisé importé par le cœur pour y parvenir.
    assert not [name for name in sys.modules if name.startswith("forge_design_circuit")]


def test_module_code_receives_only_the_document_and_the_payload(tmp_path: Path) -> None:
    """Frontière réelle : arguments effectivement passés par l'hôte au code du
    module (projection, configuration d'édition, handler) — jamais racine, chemin,
    Request, Router ni Application."""
    seen: dict[str, tuple[tuple[Any, ...], dict[str, Any]]] = {}

    def spy(name: str, target: Any) -> Any:
        def call(*args: Any, **kwargs: Any) -> Any:
            seen[name] = (args, kwargs)
            return target(*args, **kwargs)

        return call

    base = flow_module()
    action = ModuleAction(
        "rename-step", "flow", ("step", "label"), spy("handler", RENAME_STEP.handler)
    )
    binding = ResourceBinding(
        "flow",
        FlowCodec(),
        spy("scene", flow_scene),
        editor_script="flow-editor.js",
        editor_config=spy("config", flow_editor_config),
    )
    descriptor = ModuleDescriptor(
        definition=base.definition,
        version=base.version,
        api_version=base.api_version,
        bindings=(binding,),
        asset_package=base.asset_package,
        assets=base.assets,
        actions=(action,),
    )
    root = _flow_project(tmp_path)
    host = _flow_host(("pkg_flow", descriptor))
    view = host.read_resource("flow", "flow", root, FLOW_PATH)
    assert view.revision_token is not None
    host.execute_action(
        "flow",
        "rename-step",
        root,
        "flow",
        FLOW_PATH,
        view.revision_token,
        {"step": "end", "label": "Terminé"},
    )
    for name in ("scene", "config"):
        args, kwargs = seen[name]
        assert kwargs == {} and len(args) == 1 and isinstance(args[0], FlowDocument), (
            name
        )
    args, kwargs = seen["handler"]
    assert kwargs == {} and len(args) == 2
    assert isinstance(args[0], FlowDocument) and isinstance(
        args[1], ModuleActionPayload
    )
    assert set(args[1]) == {"step", "label"}, "seuls les champs déclarés"
    for value in (*args, *args[1].values()):
        assert not isinstance(value, Path)
        assert str(root) not in str(value)


def test_graphic_scene_is_never_persisted(tmp_path: Path) -> None:
    """GraphicScene = projection runtime : lire n'écrit rien, et un handler qui
    rendrait une scène au lieu du document ne peut pas la faire enregistrer."""
    root = _flow_project(tmp_path)

    def files() -> dict[str, bytes]:
        return {
            str(p.relative_to(root)): p.read_bytes()
            for p in root.rglob("*")
            if p.is_file()
        }

    before = files()
    host = _flow_host(("pkg_flow", flow_module()))
    view = host.read_resource("flow", "flow", root, FLOW_PATH)
    assert view.scene is not None and view.revision_token is not None
    assert files() == before, "lecture et projection n'écrivent rien"

    def to_scene(
        document: FlowDocument, payload: ModuleActionPayload
    ) -> ModuleActionResult:
        return ModuleActionResult(flow_scene(document))

    scene_action = ModuleAction("rename-step", "flow", ("step", "label"), to_scene)
    base = flow_module()
    descriptor = ModuleDescriptor(
        definition=base.definition,
        version=base.version,
        api_version=base.api_version,
        bindings=base.bindings,
        asset_package=base.asset_package,
        assets=base.assets,
        actions=(scene_action,),
    )
    host = _flow_host(("pkg_flow", descriptor))
    outcome = host.execute_action(
        "flow",
        "rename-step",
        root,
        "flow",
        FLOW_PATH,
        view.revision_token,
        {"step": "end", "label": "X"},
    )
    assert outcome.code == "module-error"
    assert files() == before, "aucune écriture, aucun historique"


# Plusieurs modules à la fois, dont un script d'éditeur défaillant.


def _flow_resource(module_id: str, path: str) -> str:
    return f"/modules/{module_id}/resource?" + urlencode({"type": "flow", "path": path})


def test_three_modules_with_editors_stay_isolated(tmp_path: Path) -> None:
    root = _flow_project(tmp_path)
    (root / "mvc/flow-broken").mkdir(parents=True)
    broken_path = "mvc/flow-broken/demo.flow-broken.json"
    (root / broken_path).write_bytes(flow_bytes())
    modules = activation(
        ("pkg_witness", witness_module(actions=(RENAME,))),
        ("pkg_flow", flow_module()),
        ("pkg_broken", broken_flow_module()),
    )
    with serving(tmp_path, modules) as app:
        opened(app, root)
        status, html, _ = call(app, "/")
        core, listed = navigation(html)
        # Les modules ne deviennent pas des outils : navigation du cœur inchangée.
        assert core == CORE_NAV
        assert [href for href, _ in listed] == [
            "/modules/witness/",
            "/modules/flow/",
            "/modules/flow-broken/",
        ]
        # Chaque module ne sert que ses assets déclarés, sous son espace.
        assert call(app, "/modules/flow/assets/flow-editor.js")[0] == 200
        assert call(app, "/modules/flow-broken/assets/flow-broken.js")[0] == 200
        for url in (
            "/modules/flow-broken/assets/flow-editor.js",
            "/modules/flow/assets/flow-broken.js",
            "/modules/flow/assets/witness.css",
            "/modules/witness/assets/flow-editor.js",
            "/modules/flow/assets/../web/static/shell.css",
        ):
            assert call(app, url)[0] == 404, url
        # Contexte d'édition de chaque module : son script, ses actions.
        status, html, _ = call(app, _flow_resource("flow", FLOW_PATH))
        context = editor_block(html)
        assert status == 200 and context is not None
        assert context["script"] == "/modules/flow/assets/flow-editor.js"
        assert set(context["actions"].values()) == {"/modules/flow/actions/rename-step"}
        status, html, _ = call(app, _flow_resource("flow-broken", broken_path))
        broken = editor_block(html)
        assert status == 200 and broken is not None
        assert broken["script"] == "/modules/flow-broken/assets/flow-broken.js"
        # Scène servie dans la page : consultable même si le script échoue.
        assert "data-graphic-scene" in html and "Vérifier" in html
        # Une action d'un module n'existe pas dans l'espace d'un autre.
        envelope = [
            ("type", "flow"),
            ("path", FLOW_PATH),
            ("revision", context["revision"]),
            ("step", "check"),
            ("label", "Croisé"),
        ]
        assert post(app, "/modules/witness/actions/rename-step", envelope)[0] == 404
        status, _, _ = post(app, "/modules/flow-broken/actions/rename-step", envelope)
        assert status == 400
        assert (
            json.loads((root / FLOW_PATH).read_text())["steps"][1]["label"]
            == "Vérifier"
        )
        status, _, headers = post(app, "/modules/flow/actions/rename-step", envelope)
        assert status == 303 and headers["Location"].startswith(
            "/modules/flow/resource"
        )
    assert sorted(tool.id for tool in create_tool_registry().list()) == [
        "debug-center",
        "entity-explorer",
        "project-inspector",
        "route-explorer",
        "template-viewer",
    ]


def test_absent_capability_exposes_no_route_action_or_editor(tmp_path: Path) -> None:
    root = project(tmp_path / "projet").resolve()
    (root / "mvc/flow-ro").mkdir(parents=True)
    path = "mvc/flow-ro/demo.flow-ro.json"
    (root / path).write_bytes(flow_bytes())
    modules = activation(("pkg_ro", flow_module("flow-ro", edit=False)))
    with serving(tmp_path, modules) as app:
        opened(app, root)
        status, html, _ = call(app, _flow_resource("flow-ro", path))
        assert status == 200 and editor_block(html) is None
        assert "data-graphic-scene" in html
        assert not re.search(r'data-revision-token="[0-9a-f]{64}"', html)
        assert (
            post(app, "/modules/flow-ro/actions/rename-step", [("type", "flow")])[0]
            == 404
        )


def test_modules_never_become_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """Comportemental : le registre réellement composé par le serveur, modules
    activés, ne contient que les cinq outils du cœur."""
    import forge_design.web.server as server

    built: list[Any] = []

    def capture() -> Any:
        registry = create_tool_registry()
        built.append(registry)
        return registry

    monkeypatch.setattr(server, "create_tool_registry", capture)
    server.create_application(
        modules=activation(
            ("pkg_witness", witness_module(actions=(RENAME,))),
            ("pkg_flow", flow_module()),
        )
    )
    assert len(built) == 1
    assert [tool.id for tool in built[0].list()] == [
        "project-inspector",
        "route-explorer",
        "entity-explorer",
        "debug-center",
        "template-viewer",
    ]
