"""Politique JSON stricte, lecture brute et confinement de chaque segment."""

import builtins
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from forge_design.forge.source import (
    SourceLocation,
    SourceReadError,
    read_project_source,
    source_parts,
)
from forge_design.limits import MAX_SOURCE_BYTES, MAX_SOURCE_PATH_LENGTH
from forge_design.web.source import source_available, source_url

ALLOWED = (
    "mvc/entities/contact/contact.json",
    "mvc/entities/user_profile/user_profile.json",
    "mvc/entities/relations.json",
    "mvc/entities/a1_b2/a1_b2.json",
)
REFUSED = (
    "mvc/entities/__init__.py",
    "mvc/entities/relations.sql",
    "mvc/entities/contact.json",
    "mvc/entities/foo.json",
    "mvc/entities/contact/user.json",
    "mvc/entities/contact/contact.py",
    "mvc/entities/contact/contact.sql",
    "mvc/entities/contact/contact_base.py",
    "mvc/entities/contact/sub/contact.json",
    "mvc/entities/.contact/.contact.json",
    "mvc/entities/Contact/Contact.json",
    "mvc/entities/contact-profile/contact-profile.json",
    "mvc/entities/env/env.json",
    "mvc/entities/contact/../contact.json",
    "mvc/entities/foo/relations.json",
    "mvc/entities/RELATIONS.json",
    "mvc/entities/contact//contact.json",
    "mvc/entities/./contact/contact.json",
    "mvc/entities/_contact/_contact.json",
    "mvc/entities/contact_/contact_.json",
    "mvc/entities/a__b/a__b.json",
    "mvc/entities/1a/1a.json",
    "mvc/entities/id_rsa/id_rsa.json",
    "mvc/entities/id_ed25519/id_ed25519.json",
    "mvc/entities/id_dsa/id_dsa.json",
    "mvc/entities/id_ecdsa/id_ecdsa.json",
    "mvc/entities/foo.key/foo.key.json",
    "mvc/entities/foo.pem/foo.pem.json",
    "mvc\\entities\\contact\\contact.json",
    "/etc/passwd",
    "/home/roger/a",
    "C:/mvc/entities/contact/contact.json",
    "mvc/entities/a:/a:.json",
    "mvc/entities/a\x00/a\x00.json",
    "../mvc/entities/contact/contact.json",
    "mvc/entities/" + "a" * MAX_SOURCE_PATH_LENGTH,
)


@pytest.mark.parametrize("path", ALLOWED)
def test_entity_policy_and_raw_read(
    tmp_path: Path, path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert source_parts(path) == tuple(path.split("/"))
    target = tmp_path / path
    target.parent.mkdir(parents=True)
    target.write_bytes(b"\xef\xbb\xbf{\n<script>never execute</script>\n")
    before = target.read_bytes(), target.stat().st_size, target.stat().st_mtime_ns

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Aucun parsing ou exécution")

    with monkeypatch.context() as guard:
        for obj, names in (
            (json, ("loads", "load")),
            (builtins, ("exec", "eval")),
            (subprocess, ("run", "Popen")),
        ):
            for name in names:
                guard.setattr(obj, name, forbidden)
        content = read_project_source(tmp_path, path)
    assert content == "{\n<script>never execute</script>\n"
    assert before == (
        target.read_bytes(),
        target.stat().st_size,
        target.stat().st_mtime_ns,
    )
    target.unlink()
    with pytest.raises(FileNotFoundError):
        read_project_source(tmp_path, path)


@pytest.mark.parametrize("path", REFUSED)
def test_refused_before_filesystem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Aucune ouverture hors périmètre")

    monkeypatch.setattr(os, "open", forbidden)
    with pytest.raises(SourceReadError, match="Chemin source refusé"):
        read_project_source(tmp_path, path)
    assert not source_available(SourceLocation(path))


@pytest.mark.parametrize(
    "level", ["ancestor", "root", "mvc", "entities", "contact", "file"]
)
def test_symlink_each_level(tmp_path: Path, level: str) -> None:
    parent = tmp_path / "parent"
    root = parent / "project"
    path = "mvc/entities/contact/contact.json"
    target = root / path
    target.parent.mkdir(parents=True)
    target.write_text("secret")
    selected = {
        "ancestor": parent,
        "root": root,
        "mvc": root / "mvc",
        "entities": root / "mvc/entities",
        "contact": target.parent,
        "file": target,
    }[level]
    moved = tmp_path / "outside"
    selected.rename(moved)
    selected.symlink_to(moved, target_is_directory=level != "file")
    with pytest.raises(SourceReadError):
        read_project_source(root, path)


@pytest.mark.parametrize("kind", ["directory", "fifo", "large", "encoding"])
def test_invalid_files(tmp_path: Path, kind: str) -> None:
    path = "mvc/entities/contact/contact.json"
    target = tmp_path / path
    target.parent.mkdir(parents=True)
    if kind == "directory":
        target.mkdir()
    elif kind == "fifo":
        os.mkfifo(target)
    elif kind == "large":
        target.write_bytes(b"a" * (MAX_SOURCE_BYTES + 1))
    else:
        target.write_bytes(b"\xff")
    with pytest.raises(SourceReadError):
        read_project_source(tmp_path, path)


def test_lexical_helper_and_url(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Helper sans filesystem")

    with monkeypatch.context() as guard:
        guard.setattr(os, "stat", forbidden)
        guard.setattr(os, "open", forbidden)
        guard.setattr(Path, "exists", forbidden)
        assert not source_available(None)
        for path in ALLOWED:
            assert source_available(SourceLocation(path))
            assert parse_qs(urlsplit(source_url(path)).query) == {"path": [path]}
            assert "%2F" in source_url(path)
        assert not source_available(SourceLocation("mvc/entities"))
    assert "line=3" in source_url(SourceLocation("mvc/routes/a.py", 3))
