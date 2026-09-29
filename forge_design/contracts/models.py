"""Modèles en mémoire du schéma normatif, sans accès à un projet Forge."""

from typing import Annotated, Literal, TypeVar

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from pydantic.json_schema import JsonSchemaValue

ViewValueType = Literal["string", "boolean", "integer", "number", "object", "list"]
_NonEmpty = Annotated[str, Field(min_length=1)]
_T = TypeVar("_T")


def _reject_null(value: object) -> object:
    if value is None:
        raise ValueError("Omit the property instead of providing null")
    return value


def _omission_schema(schema: JsonSchemaValue) -> None:
    # Le validator refuse null ; le schéma expose seulement le type présent.
    # None représente l'absence Python, pas une valeur par défaut du format JSON.
    schema.pop("default", None)
    alternatives = schema.pop("anyOf", [])
    for branch in alternatives:
        if branch != {"type": "null"}:
            schema.update(branch)


_Omissible = Annotated[
    _T | None,
    BeforeValidator(_reject_null),
    Field(json_schema_extra=_omission_schema),
]


class _ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ViewContextVariable(_ContractModel):
    """Description d'une variable, sans valeur backend ni résolution d'entité."""

    type: ViewValueType
    label: _Omissible[str] = None
    entity: _Omissible[_NonEmpty] = None
    fields: _Omissible[dict[_NonEmpty, _NonEmpty]] = None


class ViewAction(_ContractModel):
    """Action déclarative ; aucune interprétation routeur ou protection CSRF."""

    method: Annotated[str, Field(min_length=1, pattern="^[A-Z]+$")]
    path: _NonEmpty
    csrf: _Omissible[bool] = None


class ViewContract(_ContractModel):
    """Contrat validé ; attributs gelés, dictionnaires imbriqués ordinaires."""

    name: Annotated[str, Field(min_length=1, max_length=256)]
    template: Annotated[
        str, Field(min_length=1, max_length=4096, pattern="^mvc/views/.+")
    ]
    context: dict[_NonEmpty, ViewContextVariable]
    actions: _Omissible[dict[_NonEmpty, ViewAction]] = None
