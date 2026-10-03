"""Déclarations des outils spécialisés (FD-SPECIALIZED-002)."""

from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest
from specialized_support import (
    CAPABILITIES,
    witness_tool,
    witness_type,
)

import forge_design.specialized as specialized
from forge_design.app import create_tool_registry
from forge_design.limits import MAX_SPECIALIZED_ISSUES
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.specialized import (
    PLATFORM_CAPABILITIES,
    OptionalDependency,
    SpecializedCapability,
    SpecializedIssue,
    SpecializedToolDefinition,
    SpecializedValidationResult,
    UiEntry,
)
from forge_design.specialized.models import is_kebab_case

PACKAGE = Path(specialized.__file__).parent


def test_witness_definition_is_valid_and_frozen() -> None:
    tool = witness_tool()
    assert (tool.id, tool.ui_entry, tool.optional_dependencies) == ("witness", None, ())
    resource_type = tool.resource_type("document")
    assert resource_type.write_version in resource_type.read_versions
    with pytest.raises(FrozenInstanceError):
        tool.id = "autre"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        resource_type.max_size = 1  # type: ignore[misc]
    with pytest.raises(KeyError):
        tool.resource_type("absent")


def test_definition_is_descriptive_only() -> None:
    tool = witness_tool()
    for method in ("run", "open", "save", "render", "simulate", "export"):
        assert not hasattr(tool, method)


def test_platform_vocabulary_is_closed() -> None:
    assert PLATFORM_CAPABILITIES == {
        "create",
        "open",
        "edit",
        "validate",
        "save",
        "export",
        "interactive-runtime",
    }
    for name in ("preview", "simulate", "measure", "Open", ""):
        with pytest.raises(ValueError):
            SpecializedCapability(name, "platform")


def test_tool_capabilities_are_distinct_from_platform() -> None:
    assert SpecializedCapability.tool("simulate").kind == "tool"
    assert SpecializedCapability.tool("simulate") != SpecializedCapability.platform(
        "open"
    )
    for name in ("export", "open", "Simulate", "simulate_x", "", "-x"):
        with pytest.raises(ValueError):
            SpecializedCapability.tool(name)
    with pytest.raises(ValueError):
        SpecializedCapability("simulate", "domain")  # type: ignore[arg-type]


KEBAB_SAMPLES = [
    "witness",
    "three-d",
    "a1-b2",
    "",
    "Witness",
    "with_underscore",
    "-x",
    "x-",
    "a--b",
    "1abc",
    "é",
]


class _FakeTool:
    def __init__(self, identifier: str) -> None:
        self.id = identifier
        self.name = "Faux"
        self.description = "Faux"

    def run(self, project_root: Path) -> None:
        return None


@pytest.mark.parametrize("value", KEBAB_SAMPLES)
def test_kebab_case_matches_tool_registry_policy(value: str) -> None:
    registry = ToolRegistry()
    try:
        registry.register(_FakeTool(value))
        accepted = True
    except ValueError:
        accepted = False
    assert is_kebab_case(value) is accepted


@pytest.mark.parametrize("value", ["", "Witness", "with_underscore", "a--b", 3])
def test_invalid_tool_id(value: object) -> None:
    with pytest.raises(ValueError):
        witness_tool(id=value)


@pytest.mark.parametrize(
    "changes",
    [
        {"name": ""},
        {"description": "  "},
        {"resource_types": ()},
        {"resource_types": [witness_type()]},
        {"resource_types": (witness_type(), witness_type())},
        {"capabilities": CAPABILITIES + (CAPABILITIES[0],)},
        {"capabilities": CAPABILITIES[1:]},
        {"capabilities": ["open"]},
        {"ui_entry": "entrée"},
        {
            "optional_dependencies": (
                OptionalDependency(
                    "moteur", "Calcul", (SpecializedCapability.platform("export"),)
                ),
            )
        },
        {
            "optional_dependencies": (
                OptionalDependency("moteur", "Calcul", (CAPABILITIES[0],)),
                OptionalDependency("moteur", "Autre", (CAPABILITIES[0],)),
            )
        },
    ],
)
def test_invalid_tool_definition(changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        witness_tool(**changes)


def test_optional_dependency_and_ui_entry() -> None:
    simulate = SpecializedCapability.tool("simulate")
    tool = witness_tool(
        capabilities=CAPABILITIES + (simulate,),
        optional_dependencies=(OptionalDependency("solveur", "Calcul", (simulate,)),),
        ui_entry=UiEntry("Témoin", icon="note"),
    )
    assert tool.optional_dependencies[0].required_for == (simulate,)
    for bad in (
        {"id": "Solveur", "purpose": "x", "required_for": (simulate,)},
        {"id": "solveur", "purpose": "", "required_for": (simulate,)},
        {"id": "solveur", "purpose": "x", "required_for": ()},
    ):
        with pytest.raises(ValueError):
            OptionalDependency(**bad)  # type: ignore[arg-type]
    for label, icon in (("", None), ("Témoin", "")):
        with pytest.raises(ValueError):
            UiEntry(label, icon)


@pytest.mark.parametrize(
    "suffix",
    ["", ".", "witness.json", "..json", ".a/b", ".a\\b", ".a:b", ".a\x00", ".a b"],
)
def test_invalid_suffix(suffix: str) -> None:
    with pytest.raises(ValueError):
        witness_type(suffix=suffix)


@pytest.mark.parametrize(
    "prefix",
    [
        "",
        "/mvc/resources",
        "mvc/resources/",
        "mvc/../resources",
        "mvc/./resources",
        "mvc//resources",
        "mvc/.cache",
        "mvc/env/x",
        "mvc\\resources",
        "c:/mvc",
        "mvc/id_rsa",
    ],
)
def test_invalid_source_prefix(prefix: str) -> None:
    with pytest.raises(ValueError):
        witness_type(source_prefix=prefix)


@pytest.mark.parametrize(
    "changes",
    [
        {"id": "Document"},
        {"format_id": "witness_json"},
        {"read_versions": frozenset[str]()},
        {"read_versions": {"0.1"}},
        {"read_versions": frozenset({"0.1", " 0.2"})},
        {"read_versions": frozenset({"0.1", ""})},
        {"write_version": "0.2"},
        {"max_size": 0},
        {"max_size": -1},
        {"max_size": True},
        {"max_size": 1.5},
        {"max_size": 64 * 1024 * 1024 + 1},
        {"editable": "oui"},
        {"editable": False},
        {"capabilities": CAPABILITIES + (CAPABILITIES[0],)},
        {"validation_levels": ("content",)},
        {"validation_levels": ("structure", "content", "content")},
        {"validation_levels": ("structure", "Content")},
        {"blocking_validation_levels": frozenset({"structure", "pedagogie"})},
        {"blocking_validation_levels": frozenset({"content"})},
        {"blocking_validation_levels": {"structure"}},
        {"persistent_state": ("title", "selected_tab")},
        {"runtime_only_state": ("selected_tab", "selected_tab")},
        {"persistent_state": ["title"]},
    ],
)
def test_invalid_resource_type(changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        witness_type(**changes)


def test_read_only_type_is_allowed_without_editing_capabilities() -> None:
    read_only = witness_type(
        editable=False,
        capabilities=(
            SpecializedCapability.platform("open"),
            SpecializedCapability.platform("validate"),
        ),
    )
    assert not read_only.has_capability("save")


@pytest.mark.parametrize(
    "code", ["resource-not-found", "conflict", "witness.empty-title", "three-d.x"]
)
def test_issue_codes_accepted(code: str) -> None:
    assert SpecializedIssue(code, "error", "Message").code == code


@pytest.mark.parametrize(
    "code",
    ["empty-title", "Witness.x", "witness.", ".x", "witness.Empty", "witness.a.b", ""],
)
def test_issue_codes_refused(code: str) -> None:
    with pytest.raises(ValueError):
        SpecializedIssue(code, "error", "Message")


@pytest.mark.parametrize(
    "changes",
    [
        {"severity": "info"},
        {"message": ""},
        {"level": "Structure"},
        {"location": ["title"]},
        {"location": ("title", 1.5)},
        {"location": (True,)},
        {"location": tuple(range(65))},
    ],
)
def test_issue_fields_refused(changes: dict[str, Any]) -> None:
    values: dict[str, Any] = {
        "code": "witness.x",
        "severity": "error",
        "message": "Message",
        "level": "structure",
        "location": (),
    }
    values.update(changes)
    with pytest.raises(ValueError):
        SpecializedIssue(**values)


def _warning(index: int) -> SpecializedIssue:
    return SpecializedIssue("witness.x", "warning", f"n°{index}", "content", (index,))


def test_validation_result_is_bounded() -> None:
    consumed: list[int] = []

    def generate() -> Any:
        for index in range(10_000):
            consumed.append(index)
            yield _warning(index)

    result = SpecializedValidationResult.bounded(generate())
    assert len(result.issues) == MAX_SPECIALIZED_ISSUES and result.truncated
    assert len(consumed) == MAX_SPECIALIZED_ISSUES + 1
    exact = SpecializedValidationResult.bounded(
        _warning(i) for i in range(MAX_SPECIALIZED_ISSUES)
    )
    assert not exact.truncated
    with pytest.raises(ValueError):
        SpecializedValidationResult(
            tuple(_warning(i) for i in range(MAX_SPECIALIZED_ISSUES + 1))
        )
    with pytest.raises(ValueError):
        SpecializedValidationResult([_warning(0)])  # type: ignore[arg-type]


def test_blocking_depends_on_level_and_severity() -> None:
    resource_type = witness_type()
    structure_error = SpecializedIssue("witness.x", "error", "E", "structure")
    content_error = SpecializedIssue("witness.y", "error", "E", "content")
    structure_warning = SpecializedIssue("witness.z", "warning", "W", "structure")
    result = SpecializedValidationResult(
        (structure_error, content_error, structure_warning)
    )
    assert result.blocking(resource_type) == (structure_error,)
    strict = witness_type(
        blocking_validation_levels=frozenset({"structure", "content"})
    )
    assert result.blocking(strict) == (structure_error, content_error)


def test_tool_registry_still_has_five_tools() -> None:
    tools = create_tool_registry().list()
    assert [tool.id for tool in tools] == [
        "project-inspector",
        "route-explorer",
        "entity-explorer",
        "debug-center",
        "template-viewer",
    ]
    assert not isinstance(witness_tool(), type(tools[0]))
    assert not any(isinstance(tool, SpecializedToolDefinition) for tool in tools)


def test_witness_is_not_shipped() -> None:
    assert not any("witness" in name.lower() for name in dir(specialized))
    for source in PACKAGE.glob("*.py"):
        assert "witness" not in source.read_text().lower(), source
