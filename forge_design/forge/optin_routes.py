"""Reconnaissance bornée du branchement opt-ins vide, sans import du projet.

Cette preuve syntaxique ne valide ni l'installation ni l'identité à l'exécution
des paquets. Un registre actif ou personnalisé reste une limite explicite.
"""

import ast
import os
from contextlib import ExitStack
from pathlib import Path
from stat import S_ISDIR, S_ISREG

from forge_design.limits import MAX_SOURCE_BYTES

# Forme sans effets du registre Forge ADR-061. Comparaison d'AST, indépendante
# des commentaires, espaces, docstrings et noms/chemins des projets du kit.
_EMPTY_REGISTRY = """
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.http.router import Router
BACKEND: str | None = None
ENABLED_OPTINS: dict[str, str] = {}
def register_optins(router: Router) -> None:
    return None
"""


def _shape(tree: ast.Module) -> str:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef)):
            if node.body and isinstance(node.body[0], ast.Expr):
                value = node.body[0].value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    node.body = node.body[1:]
    return ast.dump(tree, include_attributes=False)


_EMPTY_SHAPE = _shape(ast.parse(_EMPTY_REGISTRY))


def _registry(root: Path) -> tuple[bool, str | None]:
    """Lire uniquement le fichier régulier borné, sans suivre de lien parent."""
    try:
        # Ne pas ouvrir de source supplémentaire pour les projets sans optins.
        # Ce filtre ne remplace pas les ouvertures O_NOFOLLOW ci-dessous.
        if not S_ISDIR((root / "optins").lstat().st_mode):
            return True, None
        with ExitStack() as stack:
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            root_fd = os.open(root, flags)
            stack.callback(os.close, root_fd)
            optins_fd = os.open("optins", flags, dir_fd=root_fd)
            stack.callback(os.close, optins_fd)
            fd = os.open(
                "registry.py",
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=optins_fd,
            )
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not S_ISREG(info.st_mode) or info.st_size > MAX_SOURCE_BYTES:
                    return True, None
                data = stream.read(MAX_SOURCE_BYTES + 1)
                if len(data) > MAX_SOURCE_BYTES:
                    return True, None
                return True, data.decode("utf-8-sig")
    except FileNotFoundError:
        return False, None
    except (OSError, UnicodeError, AttributeError, NotImplementedError):
        return True, None


def _binds(node: ast.AST, name: str) -> bool:
    if isinstance(node, ast.Name):
        return node.id == name and isinstance(node.ctx, (ast.Store, ast.Del))
    if isinstance(node, ast.alias):
        return (node.asname or node.name.split(".")[0]) == name
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name == name
    if isinstance(node, ast.arg):
        return node.arg == name
    return False


def empty_optin_call(
    root: Path, tree: ast.Module
) -> tuple[ast.stmt | None, str | None]:
    """Ignorer seulement un appel inconditionnel au registre vide reconnu.

    Sans registre ni référence aux opt-ins, le contrat historique reste inchangé.
    Toute ambiguïté conserve un diagnostic ; aucun paquet n'est chargé.
    """
    present, source = _registry(root)
    references = any(
        isinstance(node, ast.Name)
        and node.id == "register_optins"
        or isinstance(node, ast.ImportFrom)
        and node.module == "optins.registry"
        for node in ast.walk(tree)
    )
    if not present and not references:
        return None, None
    warning = (
        "Branchement opt-ins non résolu : vérifier l'import, l'appel "
        "register_optins(router) et le registre. Seul le registre vide "
        "conventionnel est reconnu ; les opt-ins ne sont pas exécutés."
    )
    # Nœuds syntaxiques uniquement : aucun routeur Forge n'est instancié ici.
    expected: tuple[ast.stmt, ...] = (
        ast.ImportFrom(
            module="core.http.router", names=[ast.alias(name="Router")], level=0
        ),
        ast.ImportFrom(
            module="optins.registry", names=[ast.alias(name="register_optins")], level=0
        ),
        ast.Assign(
            targets=[ast.Name(id="router", ctx=ast.Store())],
            value=ast.Call(
                func=ast.Name(id="Router", ctx=ast.Load()), args=[], keywords=[]
            ),
        ),
        ast.Expr(
            value=ast.Call(
                func=ast.Name(id="register_optins", ctx=ast.Load()),
                args=[ast.Name(id="router", ctx=ast.Load())],
                keywords=[],
            )
        ),
    )
    matches: list[ast.stmt] = []
    for expected_statement in expected:
        shape = ast.dump(expected_statement)
        found = [node for node in tree.body if ast.dump(node) == shape]
        if len(found) != 1:
            return None, warning
        matches.append(found[0])
    router_import, registry_import, creation, call = matches
    if not (
        router_import.lineno < creation.lineno < call.lineno
        and registry_import.lineno < call.lineno
    ):
        return None, warning
    for name in ("Router", "router", "register_optins"):
        if sum(_binds(node, name) for node in ast.walk(tree)) != 1:
            return None, warning
    if any(isinstance(node, ast.alias) and node.name == "*" for node in ast.walk(tree)):
        return None, warning
    try:
        if source is not None and _shape(ast.parse(source)) == _EMPTY_SHAPE:
            return call, None
    except (SyntaxError, ValueError, RecursionError):
        pass
    return None, warning
