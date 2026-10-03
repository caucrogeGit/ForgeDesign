"""Topologie Circuit : réseaux dérivés canoniques, jonctions, masse, invariants."""

import copy
import random
from typing import Any

import pytest
from circuit_support import (
    BAT,
    CIRCUIT,
    DIODE,
    GND,
    JN,
    RES,
    SW,
    circuit,
    circuit_document,
    component,
    junction,
    terminal,
)

from forge_design.circuit import (
    CIRCUIT_CATALOG,
    CircuitTopology,
    JunctionRef,
    TerminalRef,
    build_circuit_topology,
    validate_circuit,
)
from forge_design.circuit.topology import analyze_topology


def _topology(data: dict[str, Any]) -> CircuitTopology:
    return build_circuit_topology(circuit_document(data), CIRCUIT_CATALOG)


def _nets(data: dict[str, Any]) -> list[set[tuple[str, str]]]:
    return [
        {(t.component_id, t.terminal_id) for t in net.terminals}
        for net in _topology(data).nets
    ]


def _topology_issues(data: dict[str, Any]) -> list[tuple[str, str, tuple[Any, ...]]]:
    analysis = analyze_topology(circuit_document(data), CIRCUIT_CATALOG)
    assert all(i.level == "topology" for i in analysis.issues)
    return [(i.code, i.severity, i.location) for i in analysis.issues]


def _wire(identity: str, a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": identity,
        "a": a,
        "b": b,
        "route": {"mode": "orthogonal", "points": []},
    }


def _doc(
    components: list[dict[str, Any]],
    connections: list[dict[str, Any]],
    junctions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return circuit(
        components=components,
        connections=connections,
        junctions=junctions or [],
        annotations=[],
    )


R1, R2, R3 = "c_res00000r1", "c_res00000r2", "c_res00000r3"


def _r(identity: str) -> dict[str, Any]:
    return component(identity, "resistor", {"resistance": 100.0})


def test_reference_circuit_nets() -> None:
    topology = _topology(CIRCUIT)
    assert len(topology.nets) == 4
    reference = [net for net in topology.nets if net.reference]
    assert len(reference) == 1
    assert {(t.component_id, t.terminal_id) for t in reference[0].terminals} == {
        (BAT, "negative"),
        (DIODE, "cathode"),
        (GND, "ref"),
    }
    assert reference[0].junctions == (JunctionRef(JN),)
    assert topology.net_of(TerminalRef(SW, "t1")) == topology.net_of(
        TerminalRef(BAT, "positive")
    )
    assert topology.net_of(TerminalRef("c_absent0001", "t1")) is None


def test_lone_resistor() -> None:
    nets = _nets(_doc([_r(R1)], []))
    assert nets == [{(R1, "t1")}, {(R1, "t2")}]


def test_two_components_connected() -> None:
    data = _doc(
        [_r(R1), _r(R2)], [_wire("e_w0000001", terminal(R1, "t2"), terminal(R2, "t1"))]
    )
    assert sorted(map(sorted, _nets(data))) == [
        [(R1, "t1")],
        [(R1, "t2"), (R2, "t1")],
        [(R2, "t2")],
    ]


def test_series_and_parallel() -> None:
    series = _doc(
        [_r(R1), _r(R2), _r(R3)],
        [
            _wire("e_w0000001", terminal(R1, "t2"), terminal(R2, "t1")),
            _wire("e_w0000002", terminal(R2, "t2"), terminal(R3, "t1")),
        ],
    )
    assert len(_nets(series)) == 4
    parallel = _doc(
        [_r(R1), _r(R2)],
        [
            _wire("e_w0000001", terminal(R1, "t1"), terminal(R2, "t1")),
            _wire("e_w0000002", terminal(R1, "t2"), terminal(R2, "t2")),
        ],
    )
    assert sorted(map(sorted, _nets(parallel))) == [
        [(R1, "t1"), (R2, "t1")],
        [(R1, "t2"), (R2, "t2")],
    ]


def test_crossing_without_junction_is_neutral() -> None:
    # Cas F DrawCiel : deux fils dont les routes se croisent, sans jonction.
    components = [_r(R1), _r(R2), _r(R3), _r("c_res00000r4")]
    first = _wire("e_w0000001", terminal(R1, "t2"), terminal(R2, "t1"))
    second = _wire("e_w0000002", terminal(R3, "t2"), terminal("c_res00000r4", "t1"))
    first["route"]["points"] = [{"x": 10, "y": 0}, {"x": 10, "y": 20}]
    second["route"]["points"] = [{"x": 0, "y": 10}, {"x": 20, "y": 10}]
    nets = _nets(_doc(components, [first, second]))
    assert {(R1, "t2"), (R2, "t1")} in nets and {
        (R3, "t2"),
        ("c_res00000r4", "t1"),
    } in nets
    assert len(nets) == 6


def test_explicit_junction_connects() -> None:
    # Cas G DrawCiel : trois conducteurs réunis par une jonction.
    jid = "j_node000009"
    data = _doc(
        [_r(R1), _r(R2), _r(R3)],
        [
            _wire("e_w0000001", terminal(R1, "t2"), junction(jid)),
            _wire("e_w0000002", junction(jid), terminal(R2, "t1")),
            _wire("e_w0000003", terminal(R3, "t1"), junction(jid)),
        ],
        [{"id": jid, "position": {"x": 5, "y": 5}}],
    )
    topology = _topology(data)
    shared = topology.net_of(JunctionRef(jid))
    assert shared is not None
    assert set(shared.terminals) == {
        TerminalRef(R1, "t2"),
        TerminalRef(R2, "t1"),
        TerminalRef(R3, "t1"),
    }


def test_multiple_grounds_merge_without_source() -> None:
    g1, g2 = "c_ground00g1", "c_ground00g2"
    data = _doc(
        [_r(R1), _r(R2), component(g1, "ground", {}), component(g2, "ground", {})],
        [
            _wire("e_w0000001", terminal(R1, "t1"), terminal(g1, "ref")),
            _wire("e_w0000002", terminal(R2, "t1"), terminal(g2, "ref")),
        ],
    )
    topology = _topology(data)
    reference = topology.net_of(TerminalRef(g1, "ref"))
    assert reference is not None and reference.reference
    assert reference is topology.net_of(TerminalRef(g2, "ref"))
    assert set(reference.terminals) == {
        TerminalRef(g1, "ref"),
        TerminalRef(g2, "ref"),
        TerminalRef(R1, "t1"),
        TerminalRef(R2, "t1"),
    }
    assert sum(net.reference for net in topology.nets) == 1
    text = repr(topology).lower()
    for invented in ("voltage", "source", "5v", "12v", "potential"):
        assert invented not in text
    assert not any(net.reference for net in _topology(_doc([_r(R1)], [])).nets)


def _shuffled(data: dict[str, Any], seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    result = copy.deepcopy(data)
    for key in ("components", "connections", "junctions"):
        rng.shuffle(result[key])
    for wire in result["connections"]:
        if rng.random() < 0.5:
            wire["a"], wire["b"] = wire["b"], wire["a"]
    return result


@pytest.mark.parametrize("seed", range(5))
def test_permutation_invariance(seed: int) -> None:
    assert _topology(_shuffled(CIRCUIT, seed)) == _topology(CIRCUIT)


def test_geometry_and_presentation_do_not_change_topology() -> None:
    reference = _topology(CIRCUIT)
    data = circuit()
    for index, item in enumerate(data["components"]):
        item["position"] = {"x": 40 + index, "y": 7 * index}
        item["rotation"] = [90, 180, 270, 0, 90][index]
        item.pop("reference", None)
    for wire in data["connections"]:
        wire["route"]["points"] = [{"x": 1, "y": 2}, {"x": 1, "y": 9}]
    data["junctions"][0]["position"] = {"x": 70, "y": 50}
    data["annotations"] = []
    assert _topology(data) == reference


def test_net_keys_are_canonical_and_order_free() -> None:
    topology = _topology(CIRCUIT)
    keys = [net.key for net in topology.nets]
    assert keys == sorted(keys) and len(set(keys)) == len(keys)
    for net in topology.nets:
        assert list(net.terminals) == sorted(net.terminals)
    assert '["junction","j_node000001"]' in next(
        n.key for n in topology.nets if n.reference
    )


def test_missing_component_terminal_and_junction() -> None:
    data = circuit()
    data["connections"][0]["a"]["component_id"] = "c_unknown001"
    data["connections"][1]["b"]["terminal_id"] = "anode"
    data["connections"][4]["a"]["junction_id"] = "j_unknown001"
    assert _topology_issues(data) == [
        (
            "circuit.component-not-found",
            "error",
            ("connections", 0, "a", "component_id"),
        ),
        ("circuit.terminal-not-found", "error", ("connections", 1, "b", "terminal_id")),
        ("circuit.junction-not-found", "error", ("connections", 4, "a", "junction_id")),
    ]
    topology = _topology(data)
    assert {c.id for c in topology.connections} == {
        "e_wire000003",
        "e_wire000004",
        "e_wire000006",
    }


def test_self_connection_is_an_error() -> None:
    data = circuit()
    data["connections"][1]["b"] = terminal(SW, "t2")
    data["connections"][4]["b"] = junction(JN)
    assert _topology_issues(data) == [
        ("circuit.self-connection", "error", ("connections", 1)),
        ("circuit.self-connection", "error", ("connections", 4)),
    ]


def test_duplicate_connection_is_a_warning_in_both_directions() -> None:
    data = circuit()
    data["connections"].append(
        _wire("e_dup000001", terminal(SW, "t1"), terminal(BAT, "positive"))
    )
    data["connections"].append(
        _wire("e_dup000002", terminal(BAT, "positive"), terminal(SW, "t1"))
    )
    assert _topology_issues(data) == [
        ("circuit.duplicate-connection", "warning", ("connections", 6)),
        ("circuit.duplicate-connection", "warning", ("connections", 7)),
    ]


def test_junction_degree() -> None:
    data = circuit()
    data["junctions"] += [
        {"id": "j_degree0000", "position": {"x": 1, "y": 1}},
        {"id": "j_degree1000", "position": {"x": 2, "y": 2}},
        {"id": "j_degree2000", "position": {"x": 3, "y": 3}},
    ]
    data["connections"] += [
        _wire("e_deg1000001", terminal(RES, "t1"), junction("j_degree1000")),
        _wire("e_deg2000001", terminal(RES, "t1"), junction("j_degree2000")),
        _wire("e_deg2000002", junction("j_degree2000"), terminal(SW, "t2")),
    ]
    assert _topology_issues(data) == [
        ("circuit.junction-dangling", "warning", ("junctions", 1)),
        ("circuit.junction-dangling", "warning", ("junctions", 2)),
    ]


def test_several_connections_on_one_terminal_are_allowed() -> None:
    data = circuit()
    data["connections"].append(
        _wire("e_extra00001", terminal(RES, "t2"), terminal(GND, "ref"))
    )
    assert _topology_issues(data) == []


def test_unknown_type_endpoints_are_not_evaluated_twice() -> None:
    data = circuit()
    data["components"][2]["type"] = "transistor"
    assert _topology_issues(data) == []
    codes = [i.code for i in validate_circuit(circuit_document(data)).issues]
    assert codes.count("circuit.unknown-component-type") == 1


def test_large_corpus_is_linear_enough() -> None:
    count = 3000
    components = [
        component(f"c_r{i:09d}", "resistor", {"resistance": 1.0}) for i in range(count)
    ]
    connections = [
        _wire(
            f"e_w{i:09d}",
            terminal(f"c_r{i:09d}", "t2"),
            terminal(f"c_r{i + 1:09d}", "t1"),
        )
        for i in range(count - 1)
    ]
    topology = _topology(_doc(components, connections))
    assert len(topology.nets) == count + 1
    assert len(topology.connections) == count - 1
