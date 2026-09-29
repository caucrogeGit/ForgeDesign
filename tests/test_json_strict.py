"""Primitive JSON commune : mêmes règles qu'avant l'extraction des contrats."""

import pytest

from forge_design.json_strict import loads_strict_json


@pytest.mark.parametrize(
    "text",
    [
        '{"x":1,"x":2}',
        '{"x":{"y":1,"y":2}}',
        "NaN",
        "Infinity",
        "-Infinity",
        "{/*comment*/}",
        '{"x":1,}',
    ],
)
def test_rejected(text: str) -> None:
    with pytest.raises(ValueError):
        loads_strict_json(text)


def test_nested_unicode_and_distinct_keys() -> None:
    assert loads_strict_json('{"é":[true,null,1,0.5],"e":{"é":""}}') == {
        "é": [True, None, 1, 0.5],
        "e": {"é": ""},
    }
