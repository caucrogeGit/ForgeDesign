"""Données synthétiques Circuit V0.1 pour les tests ; aucune donnée réelle."""

import copy
import json
from pathlib import Path
from typing import Any

from forge_design.circuit import CircuitDocument

R1 = "c_resistor01"
LED = "c_led000001"
J1 = "j_junction01"
E1 = "e_connect001"
E2 = "e_connect002"
A1 = "a_annotate01"

SAMPLE: dict[str, Any] = {
    "format_version": "0.1",
    "page": {"width": 80, "height": 60},
    "components": [
        {
            "id": R1,
            "type": "placeholder",
            "reference": "R1",
            "position": {"x": 10, "y": 8},
            "rotation": 90,
            "properties": {
                "resistanceOhms": 220,
                "ratedPowerW": 0.25,
                "label": "Résistance µ Ω é",
                "visible": True,
            },
        },
        {
            "id": LED,
            "type": "placeholder",
            "position": {"x": 20, "y": 8},
            "rotation": 0,
            "properties": {},
        },
    ],
    "connections": [
        {
            "id": E1,
            "a": {"kind": "terminal", "component_id": R1, "terminal_id": "t2"},
            "b": {"kind": "junction", "junction_id": J1},
            "route": {"mode": "orthogonal", "points": [{"x": 15, "y": 8}]},
        },
        {
            "id": E2,
            "a": {"kind": "junction", "junction_id": J1},
            "b": {"kind": "terminal", "component_id": LED, "terminal_id": "anode"},
            "route": {"mode": "orthogonal", "points": []},
        },
    ],
    "junctions": [{"id": J1, "position": {"x": 15, "y": 10}}],
    "annotations": [
        {
            "id": A1,
            "kind": "text",
            "position": {"x": 2, "y": 2},
            "text": "Montage d'essai\nLED témoin",
        }
    ],
}


def sample(**changes: Any) -> dict[str, Any]:
    data = copy.deepcopy(SAMPLE)
    data.update(changes)
    return data


def sample_document() -> CircuitDocument:
    return CircuitDocument.model_validate_json(json.dumps(SAMPLE))


def unchecked(**changes: Any) -> CircuitDocument:
    """Document construit sans validation, pour éprouver validate() et l'hôte."""
    document = sample_document()
    values: dict[str, Any] = {
        k: getattr(document, k) for k in type(document).model_fields
    }
    values.update(changes)
    return CircuitDocument.model_construct(**values)


def to_bytes(data: object) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode()


def make_project(root: Path, *, circuit_dir: bool = True) -> Path:
    """Signatures Forge minimales ; l'espace mvc/circuit est créé explicitement."""
    root.mkdir(parents=True)
    for name in ("app.py", "config.py", "bootstrap.py"):
        (root / name).write_text("raise AssertionError('never execute')")
    (root / "mvc/routes").mkdir(parents=True)
    (root / "mvc/views").mkdir(parents=True)
    if circuit_dir:
        (root / "mvc/circuit/led").mkdir(parents=True)
    return root.resolve()
