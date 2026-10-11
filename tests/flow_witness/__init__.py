"""Module témoin « flowchart-like » de FD-ARCH-001 : interne aux tests, jamais livré.

Preuve d'API, pas un vrai Flowchart : un domaine sans aucun rapport avec Circuit
(étapes étiquetées, liens) qui n'utilise que le contrat public du cœur —
ressource, codec, projection GraphicScene, action bornée, asset et script
d'éditeur posant un calque monde. Le paquet est importable par les tests (son
dossier est sur le chemin de pytest) et n'est pas dans la liste des paquets de la
roue. ``broken_flow_module`` déclare un script d'éditeur qui échoue : la
ressource doit rester consultable.
"""

import json
from dataclasses import dataclass, replace
from typing import Any

from forge_design.json_strict import loads_strict_json
from forge_design.modules import (
    MODULE_API_VERSION,
    ModuleAction,
    ModuleActionPayload,
    ModuleActionRefused,
    ModuleActionResult,
    ModuleAsset,
    ModuleDescriptor,
    ResourceBinding,
)
from forge_design.specialized import (
    PlatformCapability,
    SpecializedCapability,
    SpecializedFormatError,
    SpecializedIssue,
    SpecializedResourceType,
    SpecializedToolDefinition,
    SpecializedValidationResult,
    UiEntry,
)

FLOW_FIELDS = ("format_version", "steps", "links")
STEP_IDS = ("start", "check", "end")


@dataclass(frozen=True)
class FlowStep:
    id: str
    label: str


@dataclass(frozen=True)
class FlowDocument:
    """Trois étapes étiquetées, des liens orientés entre elles."""

    steps: tuple[FlowStep, ...]
    links: tuple[tuple[str, str], ...]


def _issue(code: str, message: str, *location: str | int) -> SpecializedIssue:
    return SpecializedIssue(f"flow.{code}", "error", message, "structure", location)


class FlowCodec:
    """Codec du témoin : octets ↔ FlowDocument, sans entrée/sortie."""

    def detect_version(self, data: bytes) -> str | None:
        try:
            parsed = loads_strict_json(data.decode("utf-8"))
        except (UnicodeError, ValueError, RecursionError):
            return None
        version = parsed.get("format_version") if isinstance(parsed, dict) else None  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        return version if isinstance(version, str) else None

    def decode(self, data: bytes) -> FlowDocument:
        try:
            parsed = loads_strict_json(data.decode("utf-8"))
        except (UnicodeError, ValueError, RecursionError):
            raise SpecializedFormatError(
                (_issue("invalid-json", "JSON invalide."),)
            ) from None
        if not isinstance(parsed, dict) or set(parsed) != set(FLOW_FIELDS):  # pyright: ignore[reportUnknownArgumentType]
            raise SpecializedFormatError((_issue("shape", "Champs attendus."),))
        raw: dict[str, Any] = parsed  # pyright: ignore[reportUnknownVariableType]
        try:
            steps = tuple(FlowStep(str(s["id"]), str(s["label"])) for s in raw["steps"])
            links = tuple((str(a), str(b)) for a, b in raw["links"])
        except (KeyError, TypeError, ValueError):
            raise SpecializedFormatError(
                (_issue("shape", "Étapes ou liens invalides."),)
            ) from None
        return FlowDocument(steps, links)

    def encode(self, resource: FlowDocument) -> bytes:
        payload = {
            "format_version": "0.1",
            "steps": [{"id": s.id, "label": s.label} for s in resource.steps],
            "links": [list(link) for link in resource.links],
        }
        return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode()

    def validate(self, resource: FlowDocument) -> SpecializedValidationResult:
        ids = {step.id for step in resource.steps}
        issues = [
            _issue("unknown-step", "Lien vers une étape inconnue.", "links", index)
            for index, (a, b) in enumerate(resource.links)
            if a not in ids or b not in ids
        ]
        return SpecializedValidationResult.bounded(issues)


def flow_bytes(labels: tuple[str, str, str] = ("Début", "Vérifier", "Fin")) -> bytes:
    return FlowCodec().encode(
        FlowDocument(
            tuple(
                FlowStep(i, label) for i, label in zip(STEP_IDS, labels, strict=True)
            ),
            (("start", "check"),),
        )
    )


def flow_scene(document: FlowDocument) -> dict[str, Any]:
    """Projection runtime : une étape → un nœud étiqueté, un lien → une arête."""
    nodes = [
        {
            "id": step.id,
            "label": step.label,
            "rect": {"x": 40 + 240 * index, "y": 40, "width": 160, "height": 60},
            "lines": [step.label],
        }
        for index, step in enumerate(document.steps)
    ]
    centers = {step.id: 120 + 240 * index for index, step in enumerate(document.steps)}
    edges = [
        {
            "id": f"{a}-{b}",
            "source": a,
            "target": b,
            "points": [
                {"x": centers[a] + 80, "y": 70},
                {"x": centers[b] - 80, "y": 70},
            ],
            "presentation": {"arrow": "end"},
        }
        for a, b in document.links
    ]
    return {
        "width": 760,
        "height": 140,
        "title": "Flux témoin",
        "nodes": nodes,
        "edges": edges,
    }


def rename_step(
    document: FlowDocument, payload: ModuleActionPayload
) -> ModuleActionResult:
    """Action témoin : renommer une étape ; pure, nouvelle instance."""
    step_id = payload.text("step", max_chars=32)
    label = payload.text("label", max_chars=80, empty=False)
    if step_id not in {step.id for step in document.steps}:
        raise ModuleActionRefused(f"Étape inconnue : {step_id}.")
    steps = tuple(
        replace(step, label=label) if step.id == step_id else step
        for step in document.steps
    )
    return ModuleActionResult(replace(document, steps=steps))


RENAME_STEP = ModuleAction("rename-step", "flow", ("step", "label"), rename_step)


def flow_editor_config(document: FlowDocument) -> dict[str, Any]:
    return {
        "renameAction": RENAME_STEP.id,
        "steps": [step.id for step in document.steps],
    }


def flow_module(
    module_id: str = "flow",
    *,
    script: str = "flow-editor.js",
    edit: bool = True,
    requires: str | None = None,
) -> ModuleDescriptor:
    names: tuple[PlatformCapability, ...] = (
        ("open", "validate", "edit", "save") if edit else ("open", "validate")
    )
    capabilities = tuple(SpecializedCapability.platform(name) for name in names)
    resource_type = SpecializedResourceType(
        id="flow",
        format_id="flow-json",
        suffix=f".{module_id}.json",
        source_prefix=f"mvc/{module_id}",
        read_versions=frozenset({"0.1"}),
        write_version="0.1",
        editable=edit,
        max_size=64 * 1024,
        capabilities=capabilities,
        validation_levels=("structure",),
        blocking_validation_levels=frozenset({"structure"}),
        persistent_state=("steps", "links"),
        runtime_only_state=(),
    )
    definition = SpecializedToolDefinition(
        id=module_id,
        name=f"Flux témoin {module_id}",
        description="Module témoin FD-ARCH-001, interne aux tests.",
        resource_types=(resource_type,),
        capabilities=capabilities,
        optional_dependencies=(),
        ui_entry=UiEntry(f"Flux {module_id}"),
    )
    return ModuleDescriptor(
        definition=definition,
        version="0.1.0",
        api_version=MODULE_API_VERSION,
        bindings=(
            ResourceBinding(
                "flow",
                FlowCodec(),
                flow_scene,
                editor_script=script,
                editor_config=flow_editor_config,
            ),
        ),
        asset_package="flow_witness",
        assets=(ModuleAsset(script, f"static/{script}"),),
        # Sans capacité d'édition, aucune action n'est déclarable (le descripteur
        # refuse une action sur un type non modifiable).
        actions=(RENAME_STEP,) if edit else (),
        requires_forge_design=requires,
    )


def broken_flow_module(module_id: str = "flow-broken") -> ModuleDescriptor:
    """Même domaine, script d'éditeur qui échoue à la création."""
    return flow_module(module_id, script="flow-broken.js")
