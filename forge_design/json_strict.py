"""Décodage JSON sans doublons ni constantes non standard."""

import json


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Clé JSON dupliquée.")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise ValueError("Constante JSON non standard.")


def loads_strict_json(text: str) -> object:
    return json.loads(
        text, parse_constant=_reject_constant, object_pairs_hook=_unique_object
    )
