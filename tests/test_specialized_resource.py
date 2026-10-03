"""Hôte des ressources spécialisées : lecture confinée, écriture contrôlée.

Validé avec l'outil témoin de tests/specialized_support.py (non livré).
"""

import json
import os
import stat
import time
from pathlib import Path
from typing import Any, cast

import pytest
from specialized_support import (
    WITNESS_PATH,
    WITNESS_PREFIX,
    WitnessCodec,
    WitnessDocument,
    WitnessSession,
    make_project,
    witness_bytes,
    witness_tool,
    witness_type,
)

import forge_design.specialized.resource as host
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.specialized import (
    InvalidSpecializedResourceError,
    SpecializedCapability,
    SpecializedCapabilityError,
    SpecializedResourceConflictError,
    SpecializedResourceError,
    SpecializedResourceHistoryError,
    SpecializedResourceRef,
    SpecializedResourceRefusedError,
    SpecializedResourceRevision,
    UnsupportedSpecializedVersionError,
    read_specialized_resource,
    write_specialized_resource,
)

TOOL = witness_tool()
TYPE = TOOL.resource_type("document")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return make_project(tmp_path / "projet")


def put(root: Path, data: bytes, path: str = WITNESS_PATH) -> Path:
    target = root / path
    target.write_bytes(data)
    return target


def read(
    root: Path, path: str = WITNESS_PATH, codec: WitnessCodec | None = None
) -> Any:
    return read_specialized_resource(root, TOOL, TYPE, path, codec or WitnessCodec())


def write(
    root: Path,
    document: Any,
    expected: SpecializedResourceRevision | None,
    *,
    path: str = WITNESS_PATH,
    codec: WitnessCodec | None = None,
    tool: Any = TOOL,
    resource_type: Any = TYPE,
) -> Any:
    return write_specialized_resource(
        root,
        tool,
        resource_type,
        path,
        document,
        codec or WitnessCodec(),
        expected_revision=expected,
    )


def temporaries(root: Path) -> list[str]:
    return [
        p.name
        for p in (root / WITNESS_PREFIX).iterdir()
        if p.name.startswith(".forge-design-write-")
    ]


def history_lines(root: Path) -> list[dict[str, Any]]:
    path = root / ".forge-design/history.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


# ── Lecture ──────────────────────────────────────────────────────────────────


def test_read_nominal(root: Path) -> None:
    data = witness_bytes()
    put(root, data)
    result = read(root)
    assert result.resource == WitnessDocument("Exemple", "Texte")
    assert result.ref == SpecializedResourceRef(
        "witness", "document", WITNESS_PATH, "0.1"
    )
    assert (result.issues, result.truncated, result.error) == ((), False, None)
    revision = result.revision
    metadata = os.stat(root / WITNESS_PATH)
    assert revision.size == len(data)
    assert revision.inode == metadata.st_ino and revision.device == metadata.st_dev
    assert revision.modified_ns == metadata.st_mtime_ns
    assert revision.changed_ns == metadata.st_ctime_ns
    import hashlib

    assert revision.digest == hashlib.sha256(data).hexdigest()


def test_unknown_version_refused_before_decode(root: Path) -> None:
    put(root, witness_bytes(version="0.2"))
    codec = WitnessCodec()
    result = read(root, codec=codec)
    assert result.error == "unsupported-version"
    assert result.resource is None and result.ref is None
    assert result.revision is not None
    assert [issue.code for issue in result.issues] == ["unsupported-version"]
    assert codec.decode_calls == 0


@pytest.mark.parametrize(
    "data",
    [
        b"{pas du json",
        b"[1, 2]",
        b'{"title": "x", "content": "y"}',
        b'{"format_version": 1}',
    ],
)
def test_unreadable_version_is_invalid_without_decode(root: Path, data: bytes) -> None:
    put(root, data)
    codec = WitnessCodec()
    result = read(root, codec=codec)
    assert result.error == "invalid-resource"
    assert [issue.code for issue in result.issues] == ["invalid-resource"]
    assert codec.decode_calls == 0


@pytest.mark.parametrize(
    ("payload", "codes"),
    [
        (
            {"format_version": "0.1", "title": "x", "content": "y", "extra": 1},
            ["witness.unknown-field"],
        ),
        (
            {"format_version": "0.1", "title": 3, "content": "y"},
            ["witness.invalid-field"],
        ),
        ({"format_version": "0.1", "content": "y"}, ["witness.invalid-field"]),
    ],
)
def test_structural_issues(
    root: Path, payload: dict[str, Any], codes: list[str]
) -> None:
    put(root, json.dumps(payload).encode())
    result = read(root)
    assert result.error == "invalid-resource" and result.resource is None
    assert result.ref is not None and result.ref.format_version == "0.1"
    assert [issue.code for issue in result.issues] == codes
    assert all(
        issue.level == "structure" and issue.severity == "error"
        for issue in result.issues
    )


def test_warning_keeps_resource(root: Path) -> None:
    put(root, witness_bytes(title=""))
    result = read(root)
    assert result.resource == WitnessDocument("", "Texte") and result.error is None
    (issue,) = result.issues
    assert (issue.code, issue.severity, issue.level) == (
        "witness.empty-title",
        "warning",
        "content",
    )


def test_oversize_refused_before_reading(root: Path) -> None:
    small = witness_type(max_size=64)
    tool = witness_tool(small)
    put(root, witness_bytes(content="x" * 100))
    codec = WitnessCodec()
    result = read_specialized_resource(root, tool, small, WITNESS_PATH, codec)
    assert result.error == "resource-refused" and result.revision is None
    assert codec.detect_calls == 0 and codec.decode_calls == 0


@pytest.mark.parametrize(
    "path",
    [
        "mvc/resources/autre/note.witness.json",
        "mvc/resources/witness",
        "mvc/resources/witness/note.json",
        "mvc/resources/witness/.witness.json",
        "mvc/resources/witness/../witness/note.witness.json",
        "mvc/resources/witness/./note.witness.json",
        "mvc/resources/witness//note.witness.json",
        "mvc/resources/witness/.cache/note.witness.json",
        "mvc/resources/witness/env/note.witness.json",
        "/mvc/resources/witness/note.witness.json",
        "mvc/resources/witness\\note.witness.json",
        "mvc/resources/witnessx/note.witness.json",
        "mvc/resources/witness/a:b.witness.json",
        "mvc/resources/witness/n\x00.witness.json",
    ],
)
def test_path_refused_without_filesystem_access(tmp_path: Path, path: str) -> None:
    # La racine n'existe même pas : le refus lexical précède tout accès.
    result = read(tmp_path / "absente", path=path)
    assert result.error == "resource-refused"
    with pytest.raises(SpecializedResourceRefusedError):
        write(tmp_path / "absente", WitnessDocument("x", "y"), None, path=path)


def test_nested_path_inside_prefix_allowed(root: Path) -> None:
    (root / WITNESS_PREFIX / "chapitre").mkdir()
    path = WITNESS_PREFIX + "/chapitre/note.witness.json"
    put(root, witness_bytes(), path)
    assert read(root, path=path).error is None


def test_missing_resource(root: Path) -> None:
    result = read(root)
    assert (result.error, result.revision) == ("resource-not-found", None)


def test_symlink_file_refused(root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "dehors.witness.json"
    outside.write_bytes(witness_bytes())
    (root / WITNESS_PATH).symlink_to(outside)
    assert read(root).error == "resource-refused"


def test_symlink_parent_refused(root: Path, tmp_path: Path) -> None:
    elsewhere = tmp_path / "ailleurs"
    elsewhere.mkdir()
    (elsewhere / "note.witness.json").write_bytes(witness_bytes())
    (root / WITNESS_PREFIX).rmdir()
    (root / WITNESS_PREFIX).symlink_to(elsewhere)
    assert read(root).error == "resource-refused"
    with pytest.raises(SpecializedResourceError):
        write(root, WitnessDocument("x", "y"), None)
    assert (elsewhere / "note.witness.json").read_bytes() == witness_bytes()


def test_fifo_refused_without_blocking(root: Path) -> None:
    os.mkfifo(root / WITNESS_PATH)
    started = time.monotonic()
    assert read(root).error == "resource-refused"
    assert time.monotonic() - started < 2


def test_directory_refused(root: Path) -> None:
    (root / WITNESS_PATH).mkdir()
    assert read(root).error == "resource-refused"


def test_root_must_be_forge_project(tmp_path: Path) -> None:
    (tmp_path / "plain" / WITNESS_PREFIX).mkdir(parents=True)
    with pytest.raises(NotForgeProjectError):
        read(tmp_path / "plain")


def test_type_must_belong_to_tool(root: Path) -> None:
    other = witness_type(id="other")
    with pytest.raises(ValueError):
        read_specialized_resource(root, TOOL, other, WITNESS_PATH, WitnessCodec())


def test_read_requires_open_capability(root: Path) -> None:
    no_open = witness_type(
        capabilities=(SpecializedCapability.platform("validate"),), editable=False
    )
    tool = witness_tool(no_open)
    put(root, witness_bytes())
    result = read_specialized_resource(
        root, tool, no_open, WITNESS_PATH, WitnessCodec()
    )
    assert result.error == "capability-unavailable"


# ── Écriture ─────────────────────────────────────────────────────────────────


def test_create_nominal(root: Path) -> None:
    document = WitnessDocument("Exemple", "Texte")
    result = write(root, document, None)
    assert result.created and result.ref.format_version == "0.1"
    assert (root / WITNESS_PATH).read_bytes() == WitnessCodec().encode(document)
    assert read(root).revision == result.revision
    (line,) = history_lines(root)
    assert (line["version"], line["action"], line["file"]) == (
        1,
        "write_specialized_resource",
        WITNESS_PATH,
    )
    assert temporaries(root) == []


def test_create_refuses_existing_target(root: Path) -> None:
    put(root, witness_bytes(title="Existant"))
    with pytest.raises(SpecializedResourceConflictError):
        write(root, WitnessDocument("Nouveau", "x"), None)
    assert (root / WITNESS_PATH).read_bytes() == witness_bytes(title="Existant")
    assert temporaries(root) == [] and history_lines(root) == []


def test_update_nominal(root: Path) -> None:
    put(root, witness_bytes())
    revision = read(root).revision
    result = write(root, WitnessDocument("Modifié", "Texte"), revision)
    assert not result.created
    assert read(root).resource == WitnessDocument("Modifié", "Texte")


def test_external_modification_is_conflict(root: Path) -> None:
    put(root, witness_bytes())
    revision = read(root).revision
    put(root, witness_bytes(title="Externe"))
    with pytest.raises(SpecializedResourceConflictError):
        write(root, WitnessDocument("Mien", "Texte"), revision)
    assert read(root).resource == WitnessDocument("Externe", "Texte")
    assert temporaries(root) == []


def test_same_bytes_replacement_is_conflict(root: Path) -> None:
    put(root, witness_bytes())
    revision = read(root).revision
    replacement = root / WITNESS_PREFIX / "remplacement"
    replacement.write_bytes(witness_bytes())
    os.replace(replacement, root / WITNESS_PATH)
    with pytest.raises(SpecializedResourceConflictError):
        write(root, WitnessDocument("Mien", "Texte"), revision)


def test_removed_target_is_conflict(root: Path) -> None:
    put(root, witness_bytes())
    revision = read(root).revision
    (root / WITNESS_PATH).unlink()
    with pytest.raises(SpecializedResourceConflictError):
        write(root, WitnessDocument("Mien", "Texte"), revision)
    assert not (root / WITNESS_PATH).exists()


def test_warning_is_saved(root: Path) -> None:
    result = write(root, WitnessDocument("", "Texte"), None)
    assert result.created and read(root).resource == WitnessDocument("", "Texte")


def test_blocking_error_is_not_saved(root: Path) -> None:
    invalid = cast(Any, WitnessDocument(cast(Any, 3), "Texte"))

    class Lenient(WitnessCodec):
        def encode(self, resource: WitnessDocument) -> bytes:
            return witness_bytes()

    with pytest.raises(InvalidSpecializedResourceError) as caught:
        write(root, invalid, None, codec=Lenient())
    assert [issue.code for issue in caught.value.issues] == ["witness.invalid-field"]
    assert not (root / WITNESS_PATH).exists() and history_lines(root) == []


def test_truncated_validation_is_not_saved(root: Path) -> None:
    from forge_design.specialized import SpecializedIssue, SpecializedValidationResult

    class Noisy(WitnessCodec):
        def validate(self, resource: WitnessDocument) -> SpecializedValidationResult:
            return SpecializedValidationResult.bounded(
                SpecializedIssue("witness.x", "warning", "W", "content")
                for _ in range(600)
            )

    with pytest.raises(InvalidSpecializedResourceError) as caught:
        write(root, WitnessDocument("x", "y"), None, codec=Noisy())
    assert caught.value.truncated
    assert not (root / WITNESS_PATH).exists()


def test_undeclared_issue_level_is_codec_defect(root: Path) -> None:
    from forge_design.specialized import SpecializedIssue, SpecializedValidationResult

    class Rogue(WitnessCodec):
        def validate(self, resource: WitnessDocument) -> SpecializedValidationResult:
            return SpecializedValidationResult(
                (SpecializedIssue("witness.x", "error", "E", "pedagogie"),)
            )

    with pytest.raises(ValueError):
        write(root, WitnessDocument("x", "y"), None, codec=Rogue())
    assert not (root / WITNESS_PATH).exists()


def test_encoded_resource_too_large(root: Path) -> None:
    small = witness_type(max_size=80)
    tool = witness_tool(small)
    with pytest.raises(SpecializedResourceRefusedError):
        write(
            root, WitnessDocument("x", "y" * 200), None, tool=tool, resource_type=small
        )
    assert not (root / WITNESS_PATH).exists() and temporaries(root) == []


def test_codec_must_write_declared_version(root: Path) -> None:
    with pytest.raises(UnsupportedSpecializedVersionError):
        write(root, WitnessDocument("x", "y"), None, codec=WitnessCodec("0.2"))
    assert not (root / WITNESS_PATH).exists()


def test_write_capabilities(root: Path) -> None:
    open_only = witness_type(
        editable=False, capabilities=(SpecializedCapability.platform("open"),)
    )
    with pytest.raises(SpecializedCapabilityError):
        write(
            root,
            WitnessDocument("x", "y"),
            None,
            tool=witness_tool(open_only),
            resource_type=open_only,
        )
    no_create = witness_type(
        capabilities=tuple(
            SpecializedCapability.platform(n)
            for n in ("open", "edit", "validate", "save")
        )
    )
    tool = witness_tool(no_create)
    with pytest.raises(SpecializedCapabilityError):
        write(root, WitnessDocument("x", "y"), None, tool=tool, resource_type=no_create)
    put(root, witness_bytes())
    revision = read_specialized_resource(
        root, tool, no_create, WITNESS_PATH, WitnessCodec()
    ).revision
    write(root, WitnessDocument("x", "y"), revision, tool=tool, resource_type=no_create)


def test_symlink_target_at_write_time(root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "dehors.json"
    outside.write_bytes(witness_bytes())
    put(root, witness_bytes())
    revision = read(root).revision
    (root / WITNESS_PATH).unlink()
    (root / WITNESS_PATH).symlink_to(outside)
    with pytest.raises(SpecializedResourceConflictError):
        write(root, WitnessDocument("x", "y"), revision)
    with pytest.raises(SpecializedResourceConflictError):
        write(root, WitnessDocument("x", "y"), None)
    assert outside.read_bytes() == witness_bytes()
    assert (root / WITNESS_PATH).is_symlink()


def test_exclusive_creation_race(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = host._check_target  # pyright: ignore[reportPrivateUsage]
    calls: list[int] = []

    def racing(*args: Any) -> Any:
        result = original(*args)
        calls.append(1)
        if len(calls) == 2:
            # Cible créée par un tiers après le dernier contrôle, avant link.
            put(root, witness_bytes(title="Tiers"))
        return result

    monkeypatch.setattr(host, "_check_target", racing)
    with pytest.raises(SpecializedResourceConflictError):
        write(root, WitnessDocument("Mien", "y"), None)
    assert (root / WITNESS_PATH).read_bytes() == witness_bytes(title="Tiers")
    assert temporaries(root) == [] and history_lines(root) == []


def test_missing_source_space_is_not_created(tmp_path: Path) -> None:
    root = make_project(tmp_path / "projet", witness_dir=False)
    with pytest.raises(SpecializedResourceRefusedError):
        write(root, WitnessDocument("x", "y"), None)
    assert not (root / "mvc/resources").exists()


def test_existing_mode_preserved(root: Path) -> None:
    target = put(root, witness_bytes())
    target.chmod(0o640)
    revision = read(root).revision
    write(root, WitnessDocument("x", "y"), revision)
    assert stat.S_IMODE(target.stat().st_mode) == 0o640


def test_fsync_failure_keeps_target(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    put(root, witness_bytes())
    revision = read(root).revision

    def failing(descriptor: int) -> None:
        raise OSError(5, "fsync")

    monkeypatch.setattr(host.os, "fsync", failing)
    with pytest.raises(SpecializedResourceError) as caught:
        write(root, WitnessDocument("x", "y"), revision)
    assert caught.value.category is None
    monkeypatch.undo()
    assert (root / WITNESS_PATH).read_bytes() == witness_bytes()
    assert temporaries(root) == []


def test_history_failure_after_publication(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*args: Any, **kwargs: Any) -> None:
        raise OSError(28, "journal plein")

    monkeypatch.setattr(host, "append_generation_history", broken)
    with pytest.raises(SpecializedResourceHistoryError) as caught:
        write(root, WitnessDocument("x", "y"), None)
    error = caught.value
    assert error.created and error.ref.path == WITNESS_PATH
    assert read(root).revision == error.revision


def test_error_categories() -> None:
    assert SpecializedResourceRefusedError.category == "resource-refused"
    assert SpecializedResourceConflictError.category == "conflict"
    assert UnsupportedSpecializedVersionError.category == "unsupported-version"
    assert InvalidSpecializedResourceError.category == "invalid-resource"
    assert SpecializedCapabilityError.category == "capability-unavailable"
    assert SpecializedResourceError.category is None


def test_root_must_be_forge_project_for_write(tmp_path: Path) -> None:
    (tmp_path / "plain" / WITNESS_PREFIX).mkdir(parents=True)
    with pytest.raises(NotForgeProjectError):
        write(tmp_path / "plain", WitnessDocument("x", "y"), None)


# ── Aller-retour et état runtime ─────────────────────────────────────────────


def test_full_cycle_round_trip(root: Path) -> None:
    created = write(root, WitnessDocument("Titre", 'Contenu é\n"x"'), None)
    loaded = read(root)
    assert loaded.resource == WitnessDocument("Titre", 'Contenu é\n"x"')
    assert loaded.revision == created.revision
    edited = WitnessDocument(loaded.resource.title, loaded.resource.content + " suite")
    updated = write(root, edited, loaded.revision)
    again = read(root)
    assert again.resource == edited and again.revision == updated.revision
    assert (root / WITNESS_PATH).read_bytes() == WitnessCodec().encode(edited)
    assert [line["action"] for line in history_lines(root)] == [
        "write_specialized_resource",
        "write_specialized_resource",
    ]


def test_runtime_only_state_is_never_persisted(root: Path) -> None:
    session = WitnessSession(WitnessDocument("Titre", "Contenu"), selected_tab=2)
    first = write(root, session.document, None)
    data = (root / WITNESS_PATH).read_bytes()
    assert b"selected_tab" not in data
    session.selected_tab = 7
    second = write(root, session.document, first.revision)
    assert (root / WITNESS_PATH).read_bytes() == data
    assert second.revision.digest == first.revision.digest
    assert read(root).resource == session.document
