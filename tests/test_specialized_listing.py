"""Inventaire confiné des ressources spécialisées : sans lecture, sans lien, borné."""

import os
from pathlib import Path

import pytest
from specialized_support import (
    WITNESS_PREFIX,
    WITNESS_SUFFIX,
    make_project,
    witness_tool,
    witness_type,
)

from forge_design.forge.project_version import NotForgeProjectError
from forge_design.specialized import list_specialized_resources
from forge_design.specialized import listing as listing_module
from forge_design.specialized import resource as resource_module

TOOL = witness_tool()
TYPE = TOOL.resource_type("document")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return make_project(tmp_path / "projet")


def put(root: Path, relative: str, content: bytes = b"{}") -> Path:
    target = root / WITNESS_PREFIX / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def listed(root: Path) -> tuple[str, ...]:
    return list_specialized_resources(root, TOOL, TYPE).paths


def test_empty_and_absent_prefix(root: Path, tmp_path: Path) -> None:
    empty = list_specialized_resources(root, TOOL, TYPE)
    assert (empty.paths, empty.present, empty.truncated, empty.issues) == (
        (),
        True,
        False,
        (),
    )
    bare = make_project(tmp_path / "nu", witness_dir=False)
    absent = list_specialized_resources(bare, TOOL, TYPE)
    assert (absent.paths, absent.present) == ((), False)


def test_nested_sorted_and_suffix_filtered(root: Path) -> None:
    for name in (
        "b/z" + WITNESS_SUFFIX,
        "a" + WITNESS_SUFFIX,
        "b/a" + WITNESS_SUFFIX,
        "c/d/e" + WITNESS_SUFFIX,
    ):
        put(root, name)
    put(root, "notes.json")
    put(root, "a.witness.json.bak")
    put(root, WITNESS_SUFFIX)  # nom vide avant le suffixe : refusé comme à la lecture
    put(root, ".cache/x" + WITNESS_SUFFIX)  # dossier caché : jamais parcouru
    put(root, ".x" + WITNESS_SUFFIX)  # fichier caché : refusé lexicalement
    assert listed(root) == tuple(
        f"{WITNESS_PREFIX}/{name}"
        for name in (
            "a" + WITNESS_SUFFIX,
            "b/a" + WITNESS_SUFFIX,
            "b/z" + WITNESS_SUFFIX,
            "c/d/e" + WITNESS_SUFFIX,
        )
    )


def test_content_is_never_read(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    put(root, "a" + WITNESS_SUFFIX, b"\xff not json")

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("aucune lecture de contenu")

    monkeypatch.setattr(os, "read", forbidden)
    assert listed(root) == (f"{WITNESS_PREFIX}/a{WITNESS_SUFFIX}",)


def test_symlinks_and_special_files_ignored(root: Path, tmp_path: Path) -> None:
    put(root, "real" + WITNESS_SUFFIX)
    outside = tmp_path / "dehors"
    outside.mkdir()
    (outside / ("secret" + WITNESS_SUFFIX)).write_text("{}")
    base = root / WITNESS_PREFIX
    (base / ("lien" + WITNESS_SUFFIX)).symlink_to(outside / ("secret" + WITNESS_SUFFIX))
    (base / "dossier-lien").symlink_to(outside)
    os.mkfifo(base / ("fifo" + WITNESS_SUFFIX))
    assert listed(root) == (f"{WITNESS_PREFIX}/real{WITNESS_SUFFIX}",)


def test_symlinked_source_prefix_is_never_traversed(tmp_path: Path) -> None:
    root = make_project(tmp_path / "projet", witness_dir=False)
    outside = tmp_path / "dehors"
    outside.mkdir()
    (outside / ("x" + WITNESS_SUFFIX)).write_text("{}")
    target = root / WITNESS_PREFIX
    target.parent.mkdir(parents=True)
    target.symlink_to(outside)
    result = list_specialized_resources(root, TOOL, TYPE)
    assert result.paths == () and result.present is False
    assert [issue.code for issue in result.issues] == ["resource-refused"]


def test_too_long_paths_are_skipped(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Même borne de longueur que la lecture (resource_parts), abaissée ici."""
    put(root, "court" + WITNESS_SUFFIX)
    put(root, "un-nom-bien-trop-long-pour-la-borne" + WITNESS_SUFFIX)
    limit = len(f"{WITNESS_PREFIX}/court{WITNESS_SUFFIX}")
    monkeypatch.setattr(resource_module, "MAX_SOURCE_PATH_LENGTH", limit)
    assert listed(root) == (f"{WITNESS_PREFIX}/court{WITNESS_SUFFIX}",)


def test_count_limit_truncates(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(listing_module, "MAX_SPECIALIZED_LISTED_RESOURCES", 3)
    for index in range(6):
        put(root, f"r{index}{WITNESS_SUFFIX}")
    result = list_specialized_resources(root, TOOL, TYPE)
    assert result.truncated is True
    assert result.paths == tuple(
        f"{WITNESS_PREFIX}/r{i}{WITNESS_SUFFIX}" for i in range(3)
    )


def test_entry_and_depth_limits_truncate(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    put(root, "a/b/c/profond" + WITNESS_SUFFIX)
    put(root, "surface" + WITNESS_SUFFIX)
    monkeypatch.setattr(listing_module, "MAX_SPECIALIZED_SCAN_DEPTH", 2)
    deep = list_specialized_resources(root, TOOL, TYPE)
    assert deep.truncated is True
    assert deep.paths == (f"{WITNESS_PREFIX}/surface{WITNESS_SUFFIX}",)
    monkeypatch.setattr(listing_module, "MAX_SPECIALIZED_SCAN_DEPTH", 32)
    monkeypatch.setattr(listing_module, "MAX_SPECIALIZED_DIRECTORY_ENTRIES", 1)
    assert list_specialized_resources(root, TOOL, TYPE).truncated is True


def test_wrong_type_and_invalid_root_refused(root: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        list_specialized_resources(root, TOOL, witness_type(id="autre"))
    (tmp_path / "pas-forge").mkdir()
    with pytest.raises(NotForgeProjectError):
        list_specialized_resources(tmp_path / "pas-forge", TOOL, TYPE)


def test_replaced_directory_is_rejected(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un dossier dont l'identité change entre stat et ouverture est écarté."""
    put(root, "sous/x" + WITNESS_SUFFIX)

    def never(a: os.stat_result, b: os.stat_result) -> bool:
        return False

    monkeypatch.setattr(listing_module.os.path, "samestat", never)
    result = list_specialized_resources(root, TOOL, TYPE)
    assert result.paths == ()
    assert [issue.code for issue in result.issues] == ["resource-refused"]
