"""Données synthétiques Circuit pour les tests ; aucune donnée réelle.

SAMPLE n'est valide qu'au niveau du format V0.1 (type « placeholder ») ;
CIRCUIT est valide pour le domaine V1, sans aucun diagnostic.
"""

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


BAT = "c_battery001"
SW = "c_switch0001"
RES = "c_resist0001"
DIODE = "c_ledlamp001"
GND = "c_ground0001"
JN = "j_node000001"


def _wire(identity: str, a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": identity,
        "a": a,
        "b": b,
        "route": {"mode": "orthogonal", "points": []},
    }


def terminal(component: str, terminal_id: str) -> dict[str, Any]:
    return {"kind": "terminal", "component_id": component, "terminal_id": terminal_id}


def junction(junction_id: str) -> dict[str, Any]:
    return {"kind": "junction", "junction_id": junction_id}


def component(
    identity: str, type_id: str, properties: dict[str, Any], x: int = 0, y: int = 0
) -> dict[str, Any]:
    return {
        "id": identity,
        "type": type_id,
        "position": {"x": x, "y": y},
        "rotation": 0,
        "properties": properties,
    }


# Pile → interrupteur → résistance → LED → retour pile, masse sur le pôle négatif
# via une jonction explicite.
CIRCUIT: dict[str, Any] = {
    "format_version": "0.1",
    "page": {"width": 80, "height": 60},
    "components": [
        {**component(BAT, "dc-source", {"voltage": 9.0}, 4, 20), "reference": "P1"},
        {**component(SW, "switch", {"closed": True}, 12, 10), "reference": "K1"},
        {
            **component(
                RES, "resistor", {"resistance": 220.0, "rated_power": 0.25}, 20, 10
            ),
            "reference": "R1",
        },
        {
            **component(
                DIODE, "led", {"forward_voltage": 2.0, "color": "rouge"}, 28, 20
            ),
            "reference": "D1",
        },
        component(GND, "ground", {}, 16, 34),
    ],
    "connections": [
        _wire("e_wire000001", terminal(BAT, "positive"), terminal(SW, "t1")),
        _wire("e_wire000002", terminal(SW, "t2"), terminal(RES, "t1")),
        _wire("e_wire000003", terminal(RES, "t2"), terminal(DIODE, "anode")),
        _wire("e_wire000004", terminal(DIODE, "cathode"), junction(JN)),
        _wire("e_wire000005", junction(JN), terminal(BAT, "negative")),
        _wire("e_wire000006", junction(JN), terminal(GND, "ref")),
    ],
    "junctions": [{"id": JN, "position": {"x": 16, "y": 30}}],
    "annotations": [
        {
            "id": "a_note000001",
            "kind": "text",
            "position": {"x": 2, "y": 2},
            "text": "Témoin LED µA Ω",
        }
    ],
}


def circuit(**changes: Any) -> dict[str, Any]:
    data = copy.deepcopy(CIRCUIT)
    data.update(changes)
    return data


def circuit_document(data: dict[str, Any] | None = None) -> CircuitDocument:
    return CircuitDocument.model_validate_json(json.dumps(data or CIRCUIT))


def sample(**changes: Any) -> dict[str, Any]:
    data = copy.deepcopy(SAMPLE)
    data.update(changes)
    return data


def sample_document() -> CircuitDocument:
    return CircuitDocument.model_validate_json(json.dumps(SAMPLE))


def unchecked(**changes: Any) -> CircuitDocument:
    """Document construit sans validation, pour éprouver validate() et l'hôte."""
    document = circuit_document()
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
