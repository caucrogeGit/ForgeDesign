"""Comparaison pure de contenus ; aucune lecture ou écriture de la cible."""

from dataclasses import dataclass
from difflib import SequenceMatcher, unified_diff

from forge_design.limits import MAX_TEMPLATE_DIFF_CHARS


@dataclass(frozen=True)
class TemplateDiffIssue:
    code: str
    message: str


@dataclass(frozen=True)
class TemplateDiffResult:
    target: str
    origin: str
    current: str
    generated: str
    unified_diff: str
    changed: bool
    added_lines: int
    removed_lines: int
    modified_lines: int
    issues: tuple[TemplateDiffIssue, ...]
    complete: bool


def _validate_metadata(value: object, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(label + " doit être une chaîne non vide.")


def build_template_diff(
    *, target: str, current: str, generated: str, origin: str
) -> TemplateDiffResult:
    """Comparer exactement les contenus ; métriques sur lignes sans séparateur."""
    _validate_metadata(target, "La cible")
    _validate_metadata(origin, "L'origine")
    if current == generated:
        return TemplateDiffResult(
            target, origin, current, generated, "", False, 0, 0, 0, (), True
        )

    added = removed = modified = 0
    matcher = SequenceMatcher(None, current.splitlines(), generated.splitlines())
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        old_count, new_count = i2 - i1, j2 - j1
        if tag == "replace":
            paired = min(old_count, new_count)
            modified += paired
            added += new_count - paired
            removed += old_count - paired
        elif tag == "insert":
            added += new_count
        elif tag == "delete":
            removed += old_count

    parts: list[str] = []
    size = 0
    issues: tuple[TemplateDiffIssue, ...] = ()
    for line in unified_diff(
        current.splitlines(keepends=True),
        generated.splitlines(keepends=True),
        fromfile=target,
        tofile=target + ".generated",
        lineterm="\n",
    ):
        # difflib laisse les lignes sans LF collées à la prochaine ligne du diff.
        # Le marqueur explicite préserve la lisibilité et la distinction du LF final.
        suffix = "" if line.endswith("\n") else "\n\\ No newline at end of file\n"
        if size + len(line) + len(suffix) > MAX_TEMPLATE_DIFF_CHARS:
            parts.clear()
            issues = (
                TemplateDiffIssue(
                    "diff.output_too_large", "Le diff dépasse la limite de caractères."
                ),
            )
            break
        parts.append(line + suffix)
        size += len(line) + len(suffix)
    return TemplateDiffResult(
        target,
        origin,
        current,
        generated,
        "".join(parts),
        True,
        added,
        removed,
        modified,
        issues,
        not issues,
    )
