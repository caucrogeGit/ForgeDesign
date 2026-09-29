"""Inventaire et lecture confinée de contrats, sans résolution de leurs références."""

import os
from dataclasses import dataclass
from pathlib import Path
from stat import S_ISDIR, S_ISREG

from pydantic import ValidationError

from forge_design.contracts.models import ViewContract
from forge_design.forge.filesystem import open_directory
from forge_design.forge.project_detection import detect_forge_project
from forge_design.forge.project_root import resolve_project_root
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.forge.source import (
    SourceLocation,
    SourceReadError,
    read_project_source_details,
    template_source,
)
from forge_design.json_strict import loads_strict_json
from forge_design.limits import (
    MAX_VIEW_CONTRACT_DIRECTORY_ENTRIES,
    MAX_VIEW_CONTRACT_FILES,
    MAX_VIEW_CONTRACT_ISSUES,
    MAX_VIEW_CONTRACT_SCAN_DEPTH,
    MAX_VIEW_CONTRACT_VALIDATION_ISSUES,
)


@dataclass(frozen=True)
class ViewContractIssue:
    code: str
    message: str
    path: str | None = None
    location: tuple[str | int, ...] = ()


@dataclass(frozen=True)
class ViewContractInfo:
    path: str
    size: int
    modified_ns: int


@dataclass(frozen=True)
class ViewContractsResult:
    contracts: tuple[ViewContractInfo, ...]
    issues: tuple[ViewContractIssue, ...]
    source_present: bool
    truncated: bool


@dataclass(frozen=True)
class ViewContractReadResult:
    path: str
    size: int | None
    modified_ns: int | None
    contract: ViewContract | None
    issues: tuple[ViewContractIssue, ...]


def view_contract_source(reference: str) -> SourceLocation | None:
    """Chemin relatif à views, suffixe exact ; politique commune sans duplication."""
    if not reference.endswith(".view.json"):
        return None
    return template_source(reference)


def _root(root: Path) -> Path:
    canonical = resolve_project_root(root)
    if not detect_forge_project(canonical).valid:
        raise NotForgeProjectError("La racine n'est pas un projet Forge reconnu.")
    return canonical


def _truncation(path: str | None = None) -> ViewContractIssue:
    return ViewContractIssue(
        "contract.analysis_truncated", "Limite d'analyse des contrats atteinte.", path
    )


def read_view_contracts(root: Path) -> ViewContractsResult:
    """Inventorier les fichiers réguliers seulement, sans lecture de contenu."""
    canonical = _root(root)
    contracts: list[ViewContractInfo] = []
    issues: list[ViewContractIssue] = []
    entries = 0
    exhausted = False
    truncated = False
    present = False

    def unreadable(path: str | None) -> None:
        nonlocal truncated
        if len(issues) < MAX_VIEW_CONTRACT_ISSUES:
            issues.append(
                ViewContractIssue(
                    "contract.unreadable", "Contrat ou dossier inaccessible.", path
                )
            )
        else:
            truncated = True

    def scan(directory: int, prefix: str, depth: int) -> None:
        nonlocal entries, exhausted, truncated
        if exhausted:
            return
        names: list[str] = []
        with os.scandir(directory) as iterator:
            for entry in iterator:
                if entries >= MAX_VIEW_CONTRACT_DIRECTORY_ENTRIES:
                    exhausted = truncated = True
                    break
                entries += 1
                names.append(entry.name)
        for name in sorted(names):
            path = prefix + name
            # Les dossiers n'ont pas à porter le suffixe des contrats.
            if template_source(path) is None:
                continue
            candidate = view_contract_source(path) is not None
            try:
                metadata = os.stat(name, dir_fd=directory, follow_symlinks=False)
                if S_ISDIR(metadata.st_mode):
                    if depth >= MAX_VIEW_CONTRACT_SCAN_DEPTH:
                        truncated = True
                        continue
                    with open_directory(name, directory) as child:
                        if not os.path.samestat(metadata, os.fstat(child)):
                            raise OSError("Dossier remplacé.")
                        scan(child, path + "/", depth + 1)
                elif candidate and S_ISREG(metadata.st_mode):
                    if len(contracts) >= MAX_VIEW_CONTRACT_FILES:
                        truncated = True
                        continue
                    descriptor = os.open(
                        name,
                        os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                        dir_fd=directory,
                    )
                    try:
                        opened = os.fstat(descriptor)
                        if not S_ISREG(opened.st_mode) or not os.path.samestat(
                            metadata, opened
                        ):
                            raise OSError("Fichier remplacé.")
                        contracts.append(
                            ViewContractInfo(path, opened.st_size, opened.st_mtime_ns)
                        )
                    finally:
                        os.close(descriptor)
            except OSError:
                # Un stat en échec peut aussi masquer un sous-dossier à parcourir.
                unreadable(path)

    try:
        with open_directory(str(canonical)) as project:
            with open_directory("mvc", project) as mvc:
                try:
                    metadata = os.stat("views", dir_fd=mvc, follow_symlinks=False)
                except FileNotFoundError:
                    return ViewContractsResult((), (), False, False)
                present = True
                with open_directory("views", mvc) as views:
                    if not os.path.samestat(metadata, os.fstat(views)):
                        raise OSError("Dossier remplacé.")
                    scan(views, "", 0)
    except OSError:
        unreadable(None)
    if truncated:
        issues = issues[: MAX_VIEW_CONTRACT_ISSUES - 1] + [_truncation()]
    return ViewContractsResult(
        tuple(sorted(contracts, key=lambda item: item.path)),
        tuple(issues),
        present,
        truncated,
    )


def read_view_contract(root: Path, contract_path: str) -> ViewContractReadResult:
    """Lire un seul fichier ; refus lexical/projet et absence restent des exceptions.

    Métadonnées None si aucune lecture sûre n'a abouti. Aucun contrat partiel.
    """
    location = view_contract_source(contract_path)
    if location is None:
        raise SourceReadError("Chemin de contrat refusé.")
    canonical = _root(root)
    try:
        content = read_project_source_details(canonical, location.path)
    except SourceReadError:
        return ViewContractReadResult(
            contract_path,
            None,
            None,
            None,
            (
                ViewContractIssue(
                    "contract.unreadable",
                    "Contrat inaccessible ou illisible.",
                    contract_path,
                ),
            ),
        )
    contract = None
    issues: tuple[ViewContractIssue, ...] = ()
    try:
        data = loads_strict_json(content.text)
    except (ValueError, RecursionError):
        issues = (
            ViewContractIssue(
                "contract.json_invalid", "Document JSON invalide.", contract_path
            ),
        )
    else:
        try:
            contract = ViewContract.model_validate(data)
        except ValidationError as error:
            errors = error.errors(
                include_url=False, include_context=False, include_input=False
            )
            over_limit = len(errors) > MAX_VIEW_CONTRACT_VALIDATION_ISSUES
            count = MAX_VIEW_CONTRACT_VALIDATION_ISSUES - int(over_limit)
            issues = tuple(
                ViewContractIssue(
                    "contract.validation_error",
                    "Valeur non conforme au contrat de vue.",
                    contract_path,
                    tuple(item["loc"]),
                )
                for item in errors[:count]
            )
            if over_limit:
                issues += (_truncation(contract_path),)
    return ViewContractReadResult(
        contract_path, content.size, content.modified_ns, contract, issues
    )
