"""Jeton opaque de révision commun (FD-EDITOR-007) : extraction strictement
conservatrice pour les modules (vecteurs relevés avant l'extraction), périmètres
séparés, sensibilité à chaque champ de la révision complète."""

from dataclasses import replace

import pytest

from forge_design.design.io import DesignRevision
from forge_design.modules.actions import is_revision_token as module_is_token
from forge_design.modules.actions import revision_token as module_token
from forge_design.revision_tokens import is_revision_token, revision_token
from forge_design.specialized import SpecializedResourceRevision as Revision

# Vecteurs calculés avec modules/actions.revision_token AVANT l'extraction.
KNOWN = [
    (
        ("circuit", "schematic", "mvc/circuit/demo.circuit.json"),
        Revision(
            1340,
            1_700_000_000_123_456_789,
            "9" * 64,
            64769,
            1234567,
            1_700_000_001_000_000_000,
        ),
        "ce18cc27f3c80b0424f42ecea58fa8a4bcbc98fceeb5960c5669b61729856186",
    ),
    (
        ("flowchart", "flowchart", "mvc/flowchart/é ü.flow.json"),
        Revision(
            0,
            0,
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            1,
            2,
            3,
        ),
        "e4320bde3affaa21574320fc5200fb2ebf20c7a9bcea27c6e7e516aa306770f8",
    ),
    (
        ("m", "t", "p"),
        Revision(2**40, 1, "a" * 64, 0, 0, 0),
        "2600f108377f84a17357277043cbc292585e988d20613d755bd0e2868363fda4",
    ),
]


@pytest.mark.parametrize(("scope", "revision", "token"), KNOWN)
def test_module_tokens_are_byte_identical_after_extraction(
    scope: tuple[str, str, str], revision: Revision, token: str
) -> None:
    assert module_token(*scope, revision) == token
    assert revision_token(scope, revision) == token


def test_scopes_are_separated() -> None:
    revision = Revision(10, 20, "b" * 64, 1, 2, 3)
    design = DesignRevision(10, 20, "b" * 64, 1, 2, 3)
    editor = revision_token(("design", "contacts/list.design.json"), design)
    assert editor == revision_token(("design", "contacts/list.design.json"), revision)
    assert editor != revision_token(("design", "contacts/other.design.json"), design)
    assert editor != module_token("design", "contacts", "list.design.json", revision)


@pytest.mark.parametrize(
    "field", ["size", "modified_ns", "digest", "device", "inode", "changed_ns"]
)
def test_every_revision_field_changes_the_token(field: str) -> None:
    base = DesignRevision(10, 20, "b" * 64, 1, 2, 3)
    value = "c" * 64 if field == "digest" else getattr(base, field) + 1
    changed = replace(base, **{field: value})
    scope = ("design", "x.design.json")
    assert revision_token(scope, changed) != revision_token(scope, base)


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("0" * 64, True),
        ("a" * 64, True),
        ("A" * 64, False),
        ("0" * 63, False),
        ("0" * 65, False),
        ("g" * 64, False),
        ("", False),
        (None, False),
        (123, False),
    ],
)
def test_token_shape(value: object, valid: bool) -> None:
    assert is_revision_token(value) is valid
    assert module_is_token(value) is valid
