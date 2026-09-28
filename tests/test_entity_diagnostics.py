"""Conservation des faits du Bridge et pureté de la projection."""

import builtins
import json
import os
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from test_entity_graph import entity, relation

from forge_design.forge import entities as bridge
from forge_design.forge.entities import EntitiesResult, EntityIssue
from forge_design.forge.source import SourceLocation
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.entity_diagnostics import (
    EntityDiagnostic,
    EntityDiagnostics,
    build_entity_diagnostics,
)

CODES = (
    "entity.source_missing",
    "entity.unreadable",
    "entity.json_invalid",
    "entity.schema_version_unsupported",
    "entity.structure_invalid",
    "relation.unreadable",
    "relation.json_invalid",
    "relation.schema_version_unsupported",
    "relation.structure_invalid",
    "relation.type_unsupported",
    "relation.entity_missing",
)


@pytest.mark.parametrize("errors,warnings", [(0, 0), (1, 0), (0, 1), (3, 0), (3, 2)])
def test_counts_order_and_preservation(errors: int, warnings: int) -> None:
    issues = tuple(
        EntityIssue(code, f"Texte exact : {i}\n<>&", SourceLocation(f"path/{i}", 7))
        for i, code in enumerate(CODES[: errors + warnings])
    )
    result = EntitiesResult(errors=issues[:errors], warnings=issues[errors:])
    diagnostics = build_entity_diagnostics(result)
    assert (
        diagnostics.error_count,
        diagnostics.warning_count,
        diagnostics.info_count,
    ) == (errors, warnings, 0)
    assert diagnostics.items == tuple(
        EntityDiagnostic(
            issue.code,
            "error" if i < errors else "warning",
            issue.message,
            issue.source,
            issue.source.path if issue.source else None,
        )
        for i, issue in enumerate(issues)
    )
    assert all(d.source is issue.source for d, issue in zip(diagnostics.items, issues))
    if not issues:
        assert diagnostics == EntityDiagnostics()


@pytest.mark.parametrize("code", CODES)
def test_stable_codes_and_bridge_severity(code: str) -> None:
    issue = EntityIssue(code, "Ne pas interpréter ce message")
    diagnostics = build_entity_diagnostics(
        EntitiesResult(errors=(issue,), warnings=(issue,))
    )
    assert [d.code for d in diagnostics.items] == [code, code]
    assert [d.severity for d in diagnostics.items] == ["error", "warning"]
    assert all(d.subject is None and d.source is None for d in diagnostics.items)


@pytest.mark.parametrize("index", [0, 3])
@pytest.mark.parametrize(
    "source", [None, SourceLocation("mvc/entities/relations.json")]
)
def test_relation_subject_and_duplicate_occurrences(
    index: int, source: SourceLocation | None
) -> None:
    issue = EntityIssue("relation.entity_missing", "Cible absente", source, index)
    result = EntitiesResult(
        (entity("A"),), errors=(issue, issue), relations=(relation("A", "Missing"),)
    )
    diagnostics = build_entity_diagnostics(result)
    assert len(diagnostics.items) == 2 and diagnostics.error_count == 2
    assert all(
        d.relation_index == index and d.subject == f"relations[{index}]"
        for d in diagnostics.items
    )
    assert len(result.relations) == 1


def test_purity_immutability_determinism() -> None:
    result = EntitiesResult(
        (entity("A"),),
        errors=(
            EntityIssue("entity.json_invalid", "JSON invalide", SourceLocation("a")),
        ),
        warnings=(EntityIssue("relation.entity_missing", "Absente", source_index=0),),
        relations=(relation("A", "Missing"), relation("A", "A")),
    )
    before = repr(result)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Nouvelle lecture interdite")

    with pytest.MonkeyPatch.context() as guard:
        for target, names in (
            (builtins, ("open",)),
            (os, ("open", "stat", "listdir", "scandir")),
            (Path, ("open", "read_text", "read_bytes", "stat", "iterdir")),
            (json, ("loads", "load")),
            (ToolRegistry, ("get",)),
            (bridge, ("read_entities",)),
        ):
            for name in names:
                guard.setattr(target, name, forbidden)
        diagnostics = build_entity_diagnostics(result)
        assert diagnostics == build_entity_diagnostics(result)
    assert repr(result) == before
    assert isinstance(diagnostics.items, tuple)
    assert len(diagnostics.items) == 2  # Ni cycle ni fait supplémentaire.
    for obj, attr in ((diagnostics, "items"), (diagnostics.items[0], "code")):
        with pytest.raises(FrozenInstanceError):
            setattr(obj, attr, None)


def test_info_counter_contract() -> None:
    diagnostics = EntityDiagnostics((EntityDiagnostic("future.fact", "info", "Fait"),))
    assert (
        diagnostics.error_count,
        diagnostics.warning_count,
        diagnostics.info_count,
    ) == (0, 0, 1)
