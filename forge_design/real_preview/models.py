"""Modèles publics de la preview réelle (FD-REALPREVIEW-002)."""

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

RealPreviewState = Literal["stopped", "starting", "running", "failed", "stopping"]

# Bornes hautes : une configuration reste bornée en temps et en mémoire.
_MAX_SECONDS = 3600.0
_MAX_LOG_LINES = 10_000
_MAX_LOG_CHARS = 100_000


class RealPreviewError(Exception):
    """Usage incohérent du contrôleur (start pendant une preview active, etc.)."""


@dataclass(frozen=True)
class RealPreviewConfig:
    """Délais en secondes et bornes du tampon de logs, validés à la construction."""

    startup_timeout: float = 15.0
    probe_timeout: float = 1.0
    probe_interval: float = 0.2
    terminate_timeout: float = 5.0
    kill_timeout: float = 2.0
    max_log_lines: int = 200
    max_log_chars: int = 2000

    def __post_init__(self) -> None:
        for name in (
            "startup_timeout",
            "probe_timeout",
            "probe_interval",
            "terminate_timeout",
            "kill_timeout",
        ):
            value: object = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int | float)
                or not math.isfinite(value)
                or not 0 < value <= _MAX_SECONDS
            ):
                raise ValueError(f"{name} : nombre attendu dans ]0, {_MAX_SECONDS}].")
        for name, maximum in (
            ("max_log_lines", _MAX_LOG_LINES),
            ("max_log_chars", _MAX_LOG_CHARS),
        ):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError(f"{name} doit être un entier dans [1, {maximum}].")


@dataclass(frozen=True)
class RealPreviewStatus:
    """Instantané immuable ; logs sans fin de ligne, du plus ancien au plus récent."""

    state: RealPreviewState
    project_root: Path | None
    pid: int | None
    port: int | None
    exit_code: int | None
    error: str | None
    logs: tuple[str, ...]
