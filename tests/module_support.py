"""Modules témoins de FD-MODULES-002 : internes aux tests, jamais livrés.

Ils sont fournis par un importeur injecté (aucun paquet installé, aucun sys.path
modifié). Leur asset réutilise une feuille du cœur (forge_design.web,
static/shell.css) sous le nom témoin « <id>.css » : c'est un témoin, pas un
produit. Codec et projection enregistrent les types d'arguments reçus.

FD-EDIT-001 : action témoin « rename-title » (payload : title), handler pur qui
rend une nouvelle instance ; elle aussi interne aux tests.
"""

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from specialized_support import (
    WitnessCodec,
    WitnessDocument,
    witness_tool,
    witness_type,
)

from forge_design.modules import (
    DESCRIPTOR_ATTRIBUTE,
    MODULE_API_VERSION,
    ModuleAction,
    ModuleActionPayload,
    ModuleActionResult,
    ModuleActivation,
    ModuleAsset,
    ModuleDescriptor,
    ResourceBinding,
    activate_modules,
)
from forge_design.specialized import OptionalDependency, SpecializedCapability, UiEntry

ASSET_PACKAGE = "forge_design.web"
ASSET_SOURCE = "static/shell.css"
SIMULATE = SpecializedCapability.tool("simulate")


class RecordingCodec(WitnessCodec):
    """Codec témoin : octets seulement ; trace des types reçus."""

    def __init__(self, written_version: str = "0.1") -> None:
        super().__init__(written_version)
        self.received: list[type] = []

    def detect_version(self, data: bytes) -> str | None:
        self.received.append(type(data))
        return super().detect_version(data)

    def decode(self, data: bytes) -> WitnessDocument:
        self.received.append(type(data))
        return super().decode(data)


def rename_title(
    document: WitnessDocument, payload: ModuleActionPayload
) -> ModuleActionResult:
    """Action témoin : nouveau titre, nouvelle instance, aucune entrée/sortie."""
    title = payload.text("title", max_chars=200, empty=False)
    return ModuleActionResult(replace(document, title=title))


RENAME = ModuleAction("rename-title", "document", ("title",), rename_title)


def witness_scene(document: WitnessDocument) -> dict[str, Any]:
    """A → B → C ; le titre (éventuellement hostile) devient un libellé."""

    def node(identity: str, x: int, label: str) -> dict[str, Any]:
        return {
            "id": identity,
            "label": label,
            "rect": {"x": x, "y": 20, "width": 200, "height": 80},
            "lines": [label],
        }

    def edge(source: str, target: str, x: int) -> dict[str, Any]:
        return {
            "id": f"{source}-{target}",
            "source": source,
            "target": target,
            "points": [{"x": x, "y": 60}, {"x": x + 100, "y": 60}],
            "presentation": {"arrow": "end"},
        }

    return {
        "width": 940,
        "height": 120,
        "title": "Ressource témoin",
        "nodes": [
            node("A", 20, document.title),
            node("B", 370, "B"),
            node("C", 720, "C"),
        ],
        "edges": [edge("A", "B", 220), edge("B", "C", 570)],
    }


def prefix(module_id: str) -> str:
    return f"mvc/{module_id}"


def suffix(module_id: str) -> str:
    return f".{module_id}.json"


def witness_module(
    module_id: str = "witness",
    *,
    label: str | None = "Module témoin",
    scene: Callable[[Any], Any] | None = witness_scene,
    codec: Any = None,
    assets: tuple[ModuleAsset, ...] | None = None,
    api_version: int = MODULE_API_VERSION,
    probe: Callable[[], dict[str, bool]] | None = None,
    actions: tuple[ModuleAction, ...] = (),
    edit_dependency: bool = False,
) -> ModuleDescriptor:
    resource_type = witness_type(
        source_prefix=prefix(module_id), suffix=suffix(module_id)
    )
    changes: dict[str, Any] = {}
    if probe is not None:
        capabilities = (*witness_tool().capabilities, SIMULATE)
        # edit_dependency : la capacité plateforme « edit » dépend de la sonde.
        served = (SpecializedCapability.platform("edit"),) if edit_dependency else ()
        changes = {
            "capabilities": capabilities,
            "optional_dependencies": (
                OptionalDependency(
                    "spice", "Moteur de simulation", (SIMULATE, *served)
                ),
            ),
        }
    definition = witness_tool(
        resource_type,
        id=module_id,
        name=f"Témoin {module_id}",
        ui_entry=UiEntry(label) if label else None,
        **changes,
    )
    return ModuleDescriptor(
        definition=definition,
        version="0.2.0",
        api_version=api_version,
        bindings=(ResourceBinding("document", codec or RecordingCodec(), scene),),
        asset_package=ASSET_PACKAGE,
        assets=(ModuleAsset(f"{module_id}.css", ASSET_SOURCE),)
        if assets is None
        else assets,
        dependency_probe=probe,
        actions=actions,
    )


def activation(*packages: tuple[str, object]) -> ModuleActivation:
    """Activer (nom de paquet, descripteur ou exception) dans l'ordre donné."""
    known = dict(packages)

    def importer(name: str) -> object:
        value = known.get(name)
        if value is None:
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)
        if isinstance(value, Exception):
            raise value
        return SimpleNamespace(**{DESCRIPTOR_ATTRIBUTE: value})

    return activate_modules(tuple(name for name, _ in packages), importer)


def write_resource(
    root: Path,
    module_id: str,
    name: str,
    *,
    title: str = "Titre",
    content: str = "Contenu",
    version: str = "0.1",
    raw: bytes | None = None,
) -> str:
    """Écrit une ressource témoin ; renvoie son chemin relatif au projet."""
    relative = f"{prefix(module_id)}/{name}{suffix(module_id)}"
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    data = {"format_version": version, "title": title, "content": content}
    target.write_bytes(raw if raw is not None else json.dumps(data).encode())
    return relative
