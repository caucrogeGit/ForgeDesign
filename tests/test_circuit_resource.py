"""Ressource Circuit dans un projet Forge synthétique, via le socle spécialisé."""

import json
from pathlib import Path
from typing import Any

import pytest
from circuit_support import (
    circuit_document,
    make_project,
    sample,
    to_bytes,
    unchecked,
)

from forge_design.circuit import (
    CIRCUIT_RESOURCE_TYPE,
    CIRCUIT_TOOL,
    CircuitCodec,
    CircuitComponent,
    CircuitDocument,
    CircuitPage,
    CircuitPoint,
    new_circuit_document,
    new_component_id,
)
from forge_design.circuit.limits import MAX_CIRCUIT_RESOURCE_BYTES
from forge_design.specialized import (
    InvalidSpecializedResourceError,
    SpecializedResourceConflictError,
    SpecializedResourceRefusedError,
    SpecializedResourceRevision,
    read_specialized_resource,
    write_specialized_resource,
)
from forge_design.specialized.resource import SpecializedReadResult

PATH = "mvc/circuit/led/simple.circuit.json"
CODEC = CircuitCodec()


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return make_project(tmp_path / "projet")


def read(root: Path, path: str = PATH) -> SpecializedReadResult[CircuitDocument]:
    return read_specialized_resource(
        root, CIRCUIT_TOOL, CIRCUIT_RESOURCE_TYPE, path, CODEC
    )


def write(
    root: Path,
    document: CircuitDocument,
    revision: SpecializedResourceRevision | None,
    path: str = PATH,
) -> Any:
    return write_specialized_resource(
        root,
        CIRCUIT_TOOL,
        CIRCUIT_RESOURCE_TYPE,
        path,
        document,
        CODEC,
        expected_revision=revision,
    )


def history(root: Path) -> list[dict[str, Any]]:
    path = root / ".forge-design/history.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_declarations() -> None:
    resource_type = CIRCUIT_RESOURCE_TYPE
    assert (CIRCUIT_TOOL.id, CIRCUIT_TOOL.name) == ("circuit", "Circuit")
    assert CIRCUIT_TOOL.resource_type("schematic") is resource_type
    assert (resource_type.format_id, resource_type.suffix) == (
        "circuit-json",
        ".circuit.json",
    )
    assert resource_type.source_prefix == "mvc/circuit"
    assert resource_type.read_versions == frozenset({"0.1"})
    assert resource_type.write_version == "0.1" and resource_type.editable
    assert resource_type.max_size == MAX_CIRCUIT_RESOURCE_BYTES == 4 * 1024 * 1024
    assert {c.id for c in resource_type.capabilities} == {
        "create",
        "open",
        "validate",
        "save",
    }
    assert all(c.kind == "platform" for c in resource_type.capabilities)
    assert not resource_type.has_capability("edit")
    assert not resource_type.has_capability("export")
    assert not resource_type.has_capability("interactive-runtime")
    assert resource_type.validation_levels == (
        "structure",
        "topology",
        "electrical-readiness",
    )
    assert resource_type.blocking_validation_levels == {"structure", "topology"}
    assert CIRCUIT_TOOL.optional_dependencies == () and CIRCUIT_TOOL.ui_entry is None


def test_create_read_update_and_history(root: Path) -> None:
    created = write(root, new_circuit_document(), None)
    assert created.created and created.ref.format_version == "0.1"
    assert (root / PATH).read_bytes() == CODEC.encode(new_circuit_document())
    result = read(root)
    assert result.error is None and result.resource == new_circuit_document()
    assert result.revision == created.revision

    component = CircuitComponent(
        id=new_component_id(),
        type="resistor",
        position=CircuitPoint(x=4, y=4),
        rotation=180,
        properties={"resistance": 1000.0},
    )
    assert result.resource is not None
    updated = result.resource.model_copy(
        update={"page": CircuitPage(width=120, height=60), "components": (component,)}
    )
    write(
        root,
        CircuitDocument.model_validate(updated.model_dump(exclude_none=True)),
        result.revision,
    )
    reread = read(root)
    assert reread.resource is not None and reread.resource.page.width == 120
    assert reread.resource.components == (component,)
    # Résistance non connectée et sans masse : avertissements, écriture admise.
    assert reread.error is None
    assert {issue.code for issue in reread.issues} == {
        "circuit.unconnected-terminal",
        "circuit.missing-ground",
    }
    assert {issue.severity for issue in reread.issues} == {"warning"}
    lines = history(root)
    assert [(line["action"], line["file"]) for line in lines] == [
        ("write_specialized_resource", PATH),
        ("write_specialized_resource", PATH),
    ]
    assert not any("circuit" in line["action"] for line in lines)


def test_round_trip_is_byte_exact(root: Path) -> None:
    write(root, circuit_document(), None)
    data = (root / PATH).read_bytes()
    result = read(root)
    assert result.resource == circuit_document() and result.resource is not None
    assert CODEC.encode(result.resource) == data


def test_create_is_exclusive(root: Path) -> None:
    write(root, new_circuit_document(), None)
    with pytest.raises(SpecializedResourceConflictError):
        write(root, circuit_document(), None)
    assert read(root).resource == new_circuit_document()


def test_external_modification_is_conflict(root: Path) -> None:
    write(root, new_circuit_document(), None)
    revision = read(root).revision
    (root / PATH).write_bytes(CODEC.encode(circuit_document()))
    with pytest.raises(SpecializedResourceConflictError):
        write(root, new_circuit_document(), revision)
    assert read(root).resource == circuit_document()
    assert len(history(root)) == 1


def test_missing_source_space_is_not_created(tmp_path: Path) -> None:
    root = make_project(tmp_path / "vide", circuit_dir=False)
    with pytest.raises(SpecializedResourceRefusedError):
        write(root, new_circuit_document(), None, "mvc/circuit/a.circuit.json")
    assert not (root / "mvc/circuit").exists()


@pytest.mark.parametrize(
    "path",
    [
        "mvc/views/foo.circuit.json",
        "mvc/circuit/led/simple.json",
        "mvc/circuit/led/simple.circuit.json.bak",
        "mvc/circuit/../views/x.circuit.json",
        "mvc/circuit/.cache/x.circuit.json",
        "/abs/mvc/circuit/x.circuit.json",
        "mvc/circuit/.circuit.json",
    ],
)
def test_source_space_is_confined(root: Path, path: str) -> None:
    (root / "mvc/views/foo.circuit.json").write_bytes(to_bytes(sample()))
    assert read(root, path).error == "resource-refused"
    with pytest.raises(SpecializedResourceRefusedError):
        write(root, new_circuit_document(), None, path)


def test_symlink_refused(root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "dehors.circuit.json"
    outside.write_bytes(CODEC.encode(circuit_document()))
    (root / PATH).symlink_to(outside)
    assert read(root).error == "resource-refused"
    # Le socle refuse d'écrire à travers un lien, en création comme en mise à jour.
    revision = SpecializedResourceRevision(0, 0, "0" * 64, 0, 0, 0)
    for expected in (None, revision):
        with pytest.raises(SpecializedResourceConflictError):
            write(root, new_circuit_document(), expected)
    assert (root / PATH).is_symlink()
    assert outside.read_bytes() == CODEC.encode(circuit_document())


@pytest.mark.parametrize(
    ("data", "category"),
    [
        (
            {k: v for k, v in sample().items() if k != "format_version"},
            "invalid-resource",
        ),
        (sample(format_version="0.2"), "unsupported-version"),
        (sample(format_version=0.1), "invalid-resource"),
        (sample(viewport={}), "invalid-resource"),
    ],
)
def test_version_is_checked_before_decode(
    root: Path, data: dict[str, Any], category: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    (root / PATH).write_bytes(to_bytes(data))
    decoded: list[bytes] = []
    original = CircuitCodec.decode

    def spy(self: CircuitCodec, payload: bytes) -> CircuitDocument:
        decoded.append(payload)
        return original(self, payload)

    monkeypatch.setattr(CircuitCodec, "decode", spy)
    result = read(root)
    assert result.error == category and result.resource is None
    assert bool(decoded) == (category == "invalid-resource" and "viewport" in data)


def test_invalid_structure_reported_with_circuit_codes(root: Path) -> None:
    data = sample()
    data["components"][1]["id"] = data["components"][0]["id"]
    (root / PATH).write_bytes(to_bytes(data))
    result = read(root)
    assert result.error == "invalid-resource"
    assert [i.code for i in result.issues] == ["circuit.identity-duplicate"]


def test_invalid_document_is_never_written(root: Path) -> None:
    broken = unchecked(junctions=circuit_document().junctions * 2)
    with pytest.raises(InvalidSpecializedResourceError):
        write(root, broken, None)
    assert not (root / PATH).exists() and history(root) == []


def test_oversized_resource_refused(root: Path) -> None:
    (root / PATH).write_bytes(b" " * (MAX_CIRCUIT_RESOURCE_BYTES + 1))
    assert read(root).error == "resource-refused"
