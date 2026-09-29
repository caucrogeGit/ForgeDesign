"""Observation sécurisée et projection des liens déclaratifs, sans parsing Jinja."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from forge_design.contracts.reader import (
    ViewContractIssue,
    read_view_contract,
    read_view_contracts,
)
from forge_design.forge.project_root import resolve_project_root
from forge_design.forge.source import (
    SourceReadError,
    inspect_project_source,
    source_parts,
    template_source,
)
from forge_design.forge.templates import TemplateIssue, read_templates
from forge_design.limits import MAX_VIEW_CONTRACT_LINK_ISSUES

ViewContractLinkStatus = Literal[
    "linked",
    "template-missing",
    "template-unreadable",
    "template-invalid-path",
    "contract-invalid",
]
TemplateLinkStatus = Literal["linked", "without-contract", "ambiguous", "unknown"]
_METADATA_SUFFIXES = (".view.json", ".design.json")


@dataclass(frozen=True)
class ViewContractLink:
    contract_path: str
    contract_name: str | None
    declared_template: str | None
    template_path: str | None
    status: ViewContractLinkStatus


@dataclass(frozen=True)
class TemplateContractStatus:
    template_path: str
    contract_paths: tuple[str, ...]
    status: TemplateLinkStatus


@dataclass(frozen=True)
class ViewContractLinkIssue:
    code: str
    message: str
    contract_path: str | None = None
    template_path: str | None = None


@dataclass(frozen=True)
class ViewContractLinksResult:
    templates: tuple[TemplateContractStatus, ...]
    contracts: tuple[ViewContractLink, ...]
    issues: tuple[ViewContractLinkIssue, ...]
    contract_issues: tuple[ViewContractIssue, ...]
    template_issues: tuple[TemplateIssue, ...]
    truncated: bool
    contracts_complete: bool


def is_view_template_path(path: str) -> bool:
    """Chemin relatif à views admissible, hors métadonnées reconnues localement."""
    return not path.endswith(_METADATA_SUFFIXES) and template_source(path) is not None


def _target_path(declared: str) -> str | None:
    try:
        parts = source_parts(declared)
    except SourceReadError:
        return None
    if parts[:2] != ("mvc", "views"):
        return None
    relative = "/".join(parts[2:])
    return relative if is_view_template_path(relative) else None


def _project_links(
    template_paths: tuple[str, ...],
    links: tuple[ViewContractLink, ...],
    contract_issues: tuple[ViewContractIssue, ...],
    template_issues: tuple[TemplateIssue, ...],
    *,
    truncated: bool,
    contracts_complete: bool,
) -> ViewContractLinksResult:
    """Projection pure ; entrées déjà observées, aucun choix parmi les doublons."""
    names = Counter(
        link.contract_name for link in links if link.contract_name is not None
    )
    targets = Counter(
        link.template_path for link in links if link.template_path is not None
    )
    linked: dict[str, list[str]] = defaultdict(list)
    paths = set(template_paths)
    issues: list[ViewContractLinkIssue] = []

    def add(code: str, message: str, link: ViewContractLink) -> None:
        nonlocal truncated
        if len(issues) < MAX_VIEW_CONTRACT_LINK_ISSUES:
            issues.append(
                ViewContractLinkIssue(
                    code, message, link.contract_path, link.template_path
                )
            )
        else:
            truncated = True

    for link in links:
        if link.status == "linked":
            assert link.template_path is not None
            paths.add(link.template_path)
            linked[link.template_path].append(link.contract_path)
        elif link.status in {"template-missing", "template-unreadable"}:
            # Une observation directe plus récente invalide la ligne inventoriée.
            paths.discard(link.template_path)
            add("contract.link." + link.status, "Cible absente ou inaccessible.", link)
        elif link.status == "template-invalid-path":
            add("contract.link.invalid-template-path", "Cible template refusée.", link)
        if link.contract_name is not None and names[link.contract_name] > 1:
            add(
                "contract.link.duplicate-name",
                "Nom déclaré par plusieurs contrats.",
                link,
            )
        if link.template_path is not None and targets[link.template_path] > 1:
            add(
                "contract.link.multiple-contracts",
                "Plusieurs contrats déclarent cette cible.",
                link,
            )

    templates: list[TemplateContractStatus] = []
    for path in sorted(paths):
        matches = tuple(linked[path])
        status: TemplateLinkStatus
        if len(matches) > 1:
            status = "ambiguous"
        elif not contracts_complete:
            status = "unknown"
        else:
            status = "linked" if matches else "without-contract"
        templates.append(TemplateContractStatus(path, matches, status))
    if truncated:
        issues = issues[: MAX_VIEW_CONTRACT_LINK_ISSUES - 1] + [
            ViewContractLinkIssue(
                "contract.link.analysis-truncated",
                "Analyse de liaison partielle : limite atteinte.",
            )
        ]
    return ViewContractLinksResult(
        tuple(templates),
        links,
        tuple(issues),
        contract_issues,
        template_issues,
        truncated,
        contracts_complete,
    )


def analyze_view_contract_links(root: Path) -> ViewContractLinksResult:
    """Composer les lecteurs existants et inspecter chaque cible unique sans la lire."""
    canonical = resolve_project_root(root)
    templates = read_templates(canonical)
    inventory = read_view_contracts(canonical)
    contract_issues = list(inventory.issues)
    complete = not inventory.truncated and not inventory.issues
    truncated = templates.truncated or inventory.truncated
    links: list[ViewContractLink] = []
    observations: dict[str, ViewContractLinkStatus] = {}
    for info in inventory.contracts:
        try:
            detail = read_view_contract(canonical, info.path)
        except FileNotFoundError:
            contract_issues.append(
                ViewContractIssue(
                    "contract.unreadable",
                    "Contrat disparu après inventaire.",
                    info.path,
                )
            )
            complete = False
            links.append(
                ViewContractLink(info.path, None, None, None, "contract-invalid")
            )
            continue
        contract_issues.extend(detail.issues)
        truncated |= any(i.code == "contract.analysis_truncated" for i in detail.issues)
        if any(i.code == "contract.unreadable" for i in detail.issues):
            complete = False
        contract = detail.contract
        if contract is None:
            links.append(
                ViewContractLink(info.path, None, None, None, "contract-invalid")
            )
            continue
        path = _target_path(contract.template)
        if path is None:
            status: ViewContractLinkStatus = "template-invalid-path"
        else:
            if path not in observations:
                try:
                    inspect_project_source(canonical, contract.template)
                except FileNotFoundError:
                    observations[path] = "template-missing"
                except SourceReadError:
                    observations[path] = "template-unreadable"
                else:
                    observations[path] = "linked"
            status = observations[path]
        links.append(
            ViewContractLink(info.path, contract.name, contract.template, path, status)
        )
    return _project_links(
        tuple(
            item.path
            for item in templates.templates
            if is_view_template_path(item.path)
        ),
        tuple(links),
        tuple(contract_issues),
        templates.issues,
        truncated=truncated,
        contracts_complete=complete,
    )
