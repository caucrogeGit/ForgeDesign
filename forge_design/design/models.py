"""Modèles structurels design v0.1, sans règles d'imbrication ni accès projet."""

import re
from typing import Annotated, Literal, TypeVar

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field
from pydantic.json_schema import JsonSchemaValue

DesignNodeType = Literal[
    "page",
    "section",
    "container",
    "grid",
    "card",
    "title",
    "text",
    "button",
    "table",
    "form",
    "field",
    "alert",
    "empty_state",
]
PropValue = str | bool | int | float
_NonEmpty = Annotated[str, Field(min_length=1)]
_T = TypeVar("_T")
_SOURCE_PATTERN = r"^[^/\\:\r\n]+(?:/[^/\\:\r\n]+)*\.view\.json$"
_SOURCE_EXCLUSIONS = (
    r"(^|/)\.{1,2}(/|$)",
    "^mvc/views/",
    r"(^|/)\.view\.json$",
    r"[\r\n]",
)


def _reject_null(value: object) -> object:
    if value is None:
        raise ValueError("Omit the property instead of providing null")
    return value


def _omission_schema(schema: JsonSchemaValue) -> None:
    # None est seulement le défaut Python interne ; le validator refuse null fourni.
    schema.pop("default", None)
    for branch in schema.pop("anyOf", []):
        if branch != {"type": "null"}:
            schema.update(branch)


_Omissible = Annotated[
    _T | None, BeforeValidator(_reject_null), Field(json_schema_extra=_omission_schema)
]


def _source_exclusions(value: str) -> str:
    if any(re.search(pattern, value) for pattern in _SOURCE_EXCLUSIONS):
        raise ValueError("Contract reference excluded by the design schema")
    return value


class _DesignModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, allow_inf_nan=False
    )


class TableColumn(_DesignModel):
    label: _NonEmpty
    binding: _NonEmpty


class _NodeProperties(_DesignModel):
    binding: _Omissible[_NonEmpty] = None
    visible_if: _Omissible[_NonEmpty] = None
    props: _Omissible[dict[_NonEmpty, PropValue]] = None
    columns: _Omissible[list[TableColumn]] = None


class DesignNode(_NodeProperties):
    type: DesignNodeType
    children: _Omissible[list["DesignNode"]] = None


class PageRoot(_NodeProperties):
    # Modèle explicite partageant les propriétés, sans override mutable d'un champ.
    type: Literal["page"]
    children: list[DesignNode]


class DesignFile(_DesignModel):
    version: Literal["0.1"]
    view: Annotated[str, Field(min_length=1, max_length=256)]
    source_contract: Annotated[
        str,
        Field(
            min_length=1,
            max_length=4096,
            pattern=_SOURCE_PATTERN,
            json_schema_extra={
                "not": {"anyOf": [{"pattern": p} for p in _SOURCE_EXCLUSIONS]}
            },
        ),
        AfterValidator(_source_exclusions),
    ]
    root: PageRoot
