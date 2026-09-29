"""Étapes structurées connues, sans inférence depuis le message ou la pile."""

from dataclasses import dataclass
from typing import Literal

from forge_design.forge.debug_errors import DebugError

DebugFlowKind = Literal[
    "request", "router", "controller", "model", "sql", "template", "response"
]


@dataclass(frozen=True)
class DebugFlowNode:
    id: str
    kind: DebugFlowKind
    label: str
    detail: str | None = None


@dataclass(frozen=True)
class DebugFlowEdge:
    source: str
    target: str


@dataclass(frozen=True)
class DebugFlow:
    nodes: tuple[DebugFlowNode, ...]
    edges: tuple[DebugFlowEdge, ...]


def build_debug_flow(event: DebugError) -> DebugFlow:
    nodes: list[DebugFlowNode] = []
    if event.request is not None:
        detail = (
            " ".join(
                value for value in (event.request.method, event.request.path) if value
            )
            or None
        )
        nodes.append(DebugFlowNode("debug-node-request", "request", "Requête", detail))
    steps: tuple[tuple[DebugFlowKind, str, str | None], ...] = (
        ("router", "Route", event.route),
        ("controller", "Contrôleur", event.controller),
        ("sql", "SQL", event.sql),
        ("template", "Template", event.template),
    )
    for kind, label, value in steps:
        if value:
            nodes.append(
                DebugFlowNode(
                    "debug-node-" + kind,
                    kind,
                    label,
                    "Requête disponible" if kind == "sql" else value,
                )
            )
    # Model et Response ne sont pas des propriétés du contrat DebugError actuel.
    return DebugFlow(
        tuple(nodes),
        tuple(
            DebugFlowEdge(source.id, target.id)
            for source, target in zip(nodes, nodes[1:])
        ),
    )
