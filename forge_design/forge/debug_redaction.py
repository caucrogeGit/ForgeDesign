"""Masquage défensif de formes textuelles explicites, sans analyser le SQL."""

import re

_KEYS = (
    r"password|passwd|pwd|secret|token|access_token|refresh_token|"
    r"api_key|apikey|authorization|cookie|set-cookie"
)
_ASSIGNMENT = re.compile(
    rf"""(?i)(?<![\w-])((?:{_KEYS})["']?\s*[:=]\s*)"""
    r"""(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s&,;"'<>]+)"""
)
_HEADER = re.compile(
    r"(?im)(?<![\w-])((?:authorization|cookie|set-cookie)\s*:\s*)[^\r\n]+"
)


def redact_debug_text(value: str) -> str:
    """Masquer les affectations sensibles connues ; aucune garantie exhaustive."""
    value = _HEADER.sub(lambda match: match[1] + "[masqué]", value)
    return _ASSIGNMENT.sub(lambda match: match[1] + "[masqué]", value)
