"""Déclarations statiques de la racine de routes Forge, sans import cible."""

import ast
import os
import re
from collections import deque
from dataclasses import dataclass, replace
from os import PathLike
from pathlib import Path
from stat import S_ISDIR, S_ISREG
from typing import Literal

from jinja2 import Environment, TemplateSyntaxError, nodes

from forge_design.forge.project_detection import detect_forge_project
from forge_design.forge.project_root import resolve_project_root
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.forge.source import SourceLocation, template_source
from forge_design.forge.template_cycles import TemplateCycle, detect_template_cycles


class RoutesSourceMissingError(ValueError):
    """La source conventionnelle des routes est absente."""


class RoutesSourceUnreadableError(ValueError):
    """Source refusée, inaccessible ou syntaxiquement invalide."""


Verification = Literal[
    "found",
    "class-missing",
    "method-missing",
    "unreadable",
    "not-applicable",
    "ambiguous",
]


TemplateResolutionStatus = Literal[
    "found", "none", "dynamic", "ambiguous", "not-applicable"
]


TemplatePresenceStatus = Literal[
    "present", "missing", "invalid-path", "unreadable", "not-applicable"
]


TemplateSyntaxStatus = Literal["valid", "invalid", "unreadable", "not-applicable"]


TemplateDependencyKind = Literal["extends", "include", "import", "from-import"]


@dataclass(frozen=True)
class TemplateDependency:
    kind: TemplateDependencyKind
    path: str | None
    dynamic: bool
    line: int
    presence: TemplatePresenceStatus = "not-applicable"
    syntax: TemplateSyntaxStatus = "not-applicable"
    syntax_line: int | None = None
    syntax_message: str | None = None
    source: SourceLocation | None = None


MAX_TEMPLATE_DEPTH = 8
MAX_VISITED_TEMPLATES = 128


@dataclass(frozen=True)
class TemplateNodeInfo:
    path: str
    presence: TemplatePresenceStatus
    syntax: TemplateSyntaxStatus
    dependencies: tuple[TemplateDependency, ...]
    source: SourceLocation | None = None


@dataclass(frozen=True)
class TemplateDependencyGraph:
    root: str
    templates: tuple[TemplateNodeInfo, ...]
    truncated: bool = False
    cycles: tuple[TemplateCycle, ...] = ()


@dataclass(frozen=True)
class TemplateResolution:
    status: TemplateResolutionStatus = "not-applicable"
    path: str | None = None
    presence: TemplatePresenceStatus = "not-applicable"
    syntax: TemplateSyntaxStatus = "not-applicable"
    syntax_line: int | None = None
    syntax_message: str | None = None
    dependencies: tuple[TemplateDependency, ...] = ()
    dependency_graph: TemplateDependencyGraph | None = None
    source: SourceLocation | None = None


@dataclass(frozen=True)
class HandlerInfo:
    reference: str
    controller_file: str | None = None
    verification: Verification = "not-applicable"
    template: TemplateResolution = TemplateResolution()
    class_source: SourceLocation | None = None
    method_source: SourceLocation | None = None
    missing_controller: str | None = None


@dataclass(frozen=True)
class RouteInfo:
    method: str
    path: str
    name: str | None
    public: bool
    handler: HandlerInfo | None = None
    source: SourceLocation | None = None
    handler_dynamic: bool = False


@dataclass(frozen=True)
class RoutesResult:
    routes: tuple[RouteInfo, ...]
    warnings: tuple[str, ...]
    source: str = "mvc/routes/__init__.py"


def _handler(node: ast.expr) -> HandlerInfo | None:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return HandlerInfo(".".join(reversed(parts)))


def _controller_imports(tree: ast.Module) -> dict[str, tuple[str, str]]:
    candidates: dict[str, tuple[str, str]] = {}
    ambiguous: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        for alias in node.names:
            symbol = alias.asname or alias.name
            if symbol in candidates:
                ambiguous.add(symbol)
            if (
                node.level == 0
                and re.fullmatch(
                    r"mvc\.controllers\.[A-Za-z_][A-Za-z_0-9]*", node.module or ""
                )
                and alias.name != "*"
            ):
                candidates[symbol] = (
                    (node.module or "").replace(".", "/") + ".py",
                    alias.name,
                )
    # Une réaffectation explicite rend l'association ambiguë, sans interpréter Python.
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            ambiguous.update(
                n.id
                for n in ast.walk(node)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
            )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            ambiguous.add(node.name)
    return {name: path for name, path in candidates.items() if name not in ambiguous}


def _controller(
    handler: HandlerInfo,
    imports: dict[str, tuple[str, str]],
    root: Path,
    warnings: list[str],
    line: int,
    cache: dict[str, ast.Module | None],
) -> HandlerInfo:
    if "." not in handler.reference:
        return handler
    binding = imports.get(handler.reference.split(".", 1)[0])
    if binding is None:
        return handler
    relative, symbol = binding
    try:
        # lstat ne suit ni le fichier ni ses parents liés ; aucun contenu ouvert.
        for parent in (root / "mvc", root / "mvc/controllers"):
            if not S_ISDIR(parent.lstat().st_mode):
                raise ValueError("parent non ordinaire ou lien symbolique")
        if not S_ISREG((root / relative).lstat().st_mode):
            raise ValueError("fichier non ordinaire ou lien symbolique")
    except FileNotFoundError:
        warnings.append(f"Ligne {line} : contrôleur importé introuvable : {relative}.")
        return HandlerInfo(
            handler.reference, verification="unreadable", missing_controller=relative
        )
    except (OSError, ValueError):
        warnings.append(
            f"Ligne {line} : contrôleur refusé (accès/lien/type) : {relative}."
        )
        return HandlerInfo(handler.reference, verification="unreadable")
    status, template, class_source, method_source = _verify(
        root, relative, symbol, handler.reference, cache, warnings
    )
    return HandlerInfo(
        handler.reference, relative, status, template, class_source, method_source
    )


def _verify(
    root: Path,
    relative: str,
    symbol: str,
    reference: str,
    cache: dict[str, ast.Module | None],
    warnings: list[str],
) -> tuple[
    Verification, TemplateResolution, SourceLocation | None, SourceLocation | None
]:
    if len(reference.split(".")) != 2:
        return "not-applicable", TemplateResolution(), None, None
    if relative not in cache:
        try:
            cache[relative] = _tree(_read_source(root / relative))
        except (RoutesSourceMissingError, RoutesSourceUnreadableError):
            cache[relative] = None
            warnings.append(
                f"{relative} : lecture ou syntaxe Python invalide, non vérifiable."
            )
    tree = cache[relative]
    if tree is None:
        return "unreadable", TemplateResolution(), None, None
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == symbol
    ]
    if not classes:
        warnings.append(f"{relative} : classe {symbol} introuvable.")
        return "class-missing", TemplateResolution(), None, None
    if len(classes) != 1:
        warnings.append(f"{relative} : classe {symbol} ambiguë.")
        return "ambiguous", TemplateResolution(), None, None
    class_source = SourceLocation(relative, classes[0].lineno)
    method = reference.split(".")[1]
    methods = [
        node
        for node in classes[0].body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == method
    ]
    if not methods:
        warnings.append(
            f"{relative} : méthode {method} non définie directement dans {symbol}."
        )
        return "method-missing", TemplateResolution(), class_source, None
    if len(methods) != 1:
        warnings.append(f"{relative} : méthode {method} ambiguë dans {symbol}.")
        return "ambiguous", TemplateResolution(), class_source, None
    return (
        "found",
        _template(methods[0]),
        class_source,
        SourceLocation(relative, methods[0].lineno),
    )


def _template(method: ast.FunctionDef | ast.AsyncFunctionDef) -> TemplateResolution:
    """Collecter BaseController.render sans interpréter les branches ou les noms."""
    paths: set[str] = set()
    dynamic = False
    pending: list[ast.AST] = list(reversed(method.body))
    while pending:
        node = pending.pop()
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            continue
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "BaseController"
            and node.func.attr == "render"
        ):
            arguments = [
                keyword.value for keyword in node.keywords if keyword.arg == "template"
            ]
            if node.args:
                arguments.insert(0, node.args[0])
            if (
                len(arguments) == 1
                and not any(keyword.arg is None for keyword in node.keywords)
                and not any(isinstance(arg, ast.Starred) for arg in node.args)
                and isinstance(arguments[0], ast.Constant)
                and isinstance(arguments[0].value, str)
            ):
                paths.add(arguments[0].value)
            else:
                dynamic = True
        pending.extend(reversed(list(ast.iter_child_nodes(node))))
    if dynamic:
        return TemplateResolution("dynamic")
    if len(paths) > 1:
        return TemplateResolution("ambiguous")
    if paths:
        return TemplateResolution("found", next(iter(paths)))
    return TemplateResolution("none")


def _template_presence(root: Path, reference: str) -> TemplatePresenceStatus:
    # Convention portable stricte : ne jamais normaliser un traversal en chemin sûr.
    parts = reference.split("/")
    if (
        not reference
        or "\\" in reference
        or ":" in reference
        or "\x00" in reference
        or any(part in ("", ".", "..") for part in parts)
    ):
        return "invalid-path"
    candidate = root
    components = ["mvc", "views", *parts]
    try:
        for index, component in enumerate(components):
            candidate = candidate / component
            mode = candidate.lstat().st_mode
            expected = S_ISREG if index == len(components) - 1 else S_ISDIR
            if not expected(mode):
                return "invalid-path"
    except FileNotFoundError:
        return "missing"
    except OSError:
        return "unreadable"
    return "present"


def _template_dependencies(tree: nodes.Template) -> tuple[TemplateDependency, ...]:
    dependencies: list[TemplateDependency] = []
    pending: list[nodes.Node] = [tree]
    while pending:
        node = pending.pop()
        kind: TemplateDependencyKind | None = None
        if isinstance(node, nodes.Extends):
            kind = "extends"
        elif isinstance(node, nodes.Include):
            kind = "include"
        elif isinstance(node, nodes.Import):
            kind = "import"
        elif isinstance(node, nodes.FromImport):
            kind = "from-import"
        if kind is not None and isinstance(
            node, (nodes.Extends, nodes.Include, nodes.Import, nodes.FromImport)
        ):
            expression = node.template
            candidates = (
                expression.items
                if isinstance(node, nodes.Include)
                and isinstance(expression, nodes.List)
                else [expression]
            )
            paths: list[str] = []
            for candidate in candidates:
                if not isinstance(candidate, nodes.Const) or not isinstance(
                    candidate.value, str
                ):
                    break
                paths.append(candidate.value)
            if paths and len(paths) == len(candidates):
                dependencies.extend(
                    TemplateDependency(kind, path, False, node.lineno) for path in paths
                )
            else:
                dependencies.append(TemplateDependency(kind, None, True, node.lineno))
        pending.extend(reversed(list(node.iter_child_nodes())))
    # Tri stable : ordre lexical, y compris branches et occurrences sur une même ligne.
    return tuple(sorted(dependencies, key=lambda dependency: dependency.line))


def _template_syntax(
    root: Path, template: TemplateResolution
) -> tuple[TemplateResolution, nodes.Template | None]:
    assert template.path is not None and template.presence == "present"
    try:
        source = _read_source(root / "mvc/views" / template.path)
    except (RoutesSourceMissingError, RoutesSourceUnreadableError):
        return replace(template, syntax="unreadable"), None
    try:
        # Pas de loader, extension, compilation, contexte ou rendu.
        tree = Environment(loader=None).parse(source)
    except TemplateSyntaxError as error:
        return replace(
            template,
            syntax="invalid",
            syntax_line=error.lineno,
            syntax_message=" ".join(
                (error.message or "Syntaxe Jinja invalide.").split()
            )[:240],
        ), None
    except RecursionError:
        return replace(template, syntax="unreadable"), None
    return replace(template, syntax="valid"), tree


def _with_template_presence(
    root: Path, routes: list[RouteInfo], warnings: list[str]
) -> tuple[RouteInfo, ...]:
    cache: dict[str, TemplateResolution] = {}
    parsed_cache: dict[str, tuple[TemplateResolution, nodes.Template | None]] = {}
    extracted_cache: dict[str, tuple[TemplateDependency, ...]] = {}
    limit_reported = False
    depth_reported = False

    def parsed(reference: str) -> tuple[TemplateResolution, nodes.Template | None]:
        nonlocal limit_reported
        if reference not in parsed_cache:
            if len(parsed_cache) >= MAX_VISITED_TEMPLATES:
                if not limit_reported:
                    warnings.append(
                        f"Limite globale de {MAX_VISITED_TEMPLATES} templates "
                        "atteinte ; "
                        "analyse partielle."
                    )
                    limit_reported = True
                return TemplateResolution("found", reference), None
            checked = TemplateResolution(
                "found",
                reference,
                _template_presence(root, reference),
                source=template_source(reference),
            )
            tree = None
            if checked.presence == "present":
                checked, tree = _template_syntax(root, checked)
            parsed_cache[reference] = checked, tree
            if checked.syntax == "invalid":
                warnings.append(
                    f"mvc/views/{reference}:{checked.syntax_line} : "
                    f"syntaxe Jinja invalide : {checked.syntax_message}"
                )
            elif checked.syntax == "unreadable":
                warnings.append(
                    f"mvc/views/{reference} : syntaxe Jinja non vérifiable "
                    "(lecture, encodage, taille ou profondeur)."
                )
        return parsed_cache[reference]

    def dependency_syntax(dependency: TemplateDependency) -> TemplateDependency:
        if dependency.dynamic or dependency.path is None:
            return dependency
        checked, _ = parsed(dependency.path)
        return replace(
            dependency,
            presence=checked.presence,
            syntax=checked.syntax,
            syntax_line=checked.syntax_line,
            syntax_message=checked.syntax_message,
        )

    def extracted(reference: str) -> tuple[TemplateDependency, ...]:
        if reference not in extracted_cache:
            checked, tree = parsed(reference)
            extracted_cache[reference] = (
                tuple(
                    replace(
                        d,
                        source=SourceLocation(checked.source.path, d.line)
                        if checked.source is not None
                        else None,
                    )
                    for d in _template_dependencies(tree)
                )
                if tree is not None
                else ()
            )
        return extracted_cache[reference]

    # Les données directes ont priorité sur l'expansion transitive.
    for route in routes:
        handler = route.handler
        if handler is None or handler.template.status != "found":
            continue
        reference = handler.template.path
        if reference is not None and reference not in cache:
            checked, _ = parsed(reference)
            cache[reference] = replace(
                checked,
                dependencies=tuple(dependency_syntax(d) for d in extracted(reference)),
            )

    reported_cycles: set[tuple[tuple[str, str, str], ...]] = set()
    for reference, checked in tuple(cache.items()):
        queue = deque([(reference, 0)])
        discovered = {reference}
        templates: list[TemplateNodeInfo] = []
        truncated = False
        while queue:
            current, depth = queue.popleft()
            current_result, _ = parsed(current)
            if current not in parsed_cache:
                truncated = True
                continue
            declarations = extracted(current)
            dependencies: list[TemplateDependency] = []
            for declaration in declarations:
                if declaration.dynamic or declaration.path is None:
                    dependencies.append(declaration)
                    continue
                if depth >= MAX_TEMPLATE_DEPTH:
                    dependencies.append(declaration)
                    truncated = True
                    if not depth_reported:
                        warnings.append(
                            f"Profondeur maximale de {MAX_TEMPLATE_DEPTH} atteinte ; "
                            "analyse partielle."
                        )
                        depth_reported = True
                    continue
                dependency = dependency_syntax(declaration)
                dependencies.append(dependency)
                path = declaration.path
                if path not in parsed_cache:
                    truncated = True
                elif path not in discovered:
                    discovered.add(path)
                    queue.append((path, depth + 1))
            templates.append(
                TemplateNodeInfo(
                    current,
                    current_result.presence,
                    current_result.syntax,
                    tuple(dependencies),
                    current_result.source,
                )
            )
        graph = TemplateDependencyGraph(reference, tuple(templates), truncated)
        cycles = detect_template_cycles(graph)
        for cycle in cycles:
            if cycle.key not in reported_cycles:
                reported_cycles.add(cycle.key)
                warnings.append("Cycle de templates Jinja : " + " → ".join(cycle.paths))
        cache[reference] = replace(
            checked, dependency_graph=replace(graph, cycles=cycles)
        )

    enriched: list[RouteInfo] = []
    for route in routes:
        handler = route.handler
        if handler is not None and handler.template.status == "found":
            reference = handler.template.path
            if reference is not None:
                route = replace(
                    route, handler=replace(handler, template=cache[reference])
                )
        enriched.append(route)
    return tuple(enriched)


def _literal(node: ast.expr) -> object:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_literal(item) for item in node.elts]
    raise ValueError("Expression dynamique")


def _tree(source: str) -> ast.Module:
    try:
        return ast.parse(source)
    except (SyntaxError, ValueError, RecursionError) as error:
        raise RoutesSourceUnreadableError("Syntaxe de routes invalide.") from error


def _parse(
    tree: ast.Module,
    root: Path,
    receiver: str | None = None,
    imports: dict[str, tuple[str, str]] | None = None,
    cache: dict[str, ast.Module | None] | None = None,
    source_path: str = "mvc/routes/__init__.py",
) -> RoutesResult:
    cache = {} if cache is None else cache
    controller_imports = _controller_imports(tree) if imports is None else imports
    routes: list[RouteInfo] = []
    warnings = [
        "Lecture statique des routes explicitement branchées ; "
        "configuration, imports dynamiques "
        "et opt-ins non exécutés. La liste peut être partielle."
    ]

    def visit(body: list[ast.stmt], receivers: dict[str, tuple[str, bool]]) -> None:
        for statement in body:
            try:
                if isinstance(statement, (ast.Import, ast.ImportFrom, ast.Pass)):
                    continue
                if isinstance(statement, ast.Expr) and isinstance(
                    statement.value, ast.Constant
                ):
                    continue
                if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
                    target, value = statement.targets[0], statement.value
                    if (
                        isinstance(target, ast.Name)
                        and target.id == "router"
                        and isinstance(value, ast.Call)
                        and isinstance(value.func, ast.Name)
                        and value.func.id == "Router"
                        and not value.args
                        and not value.keywords
                    ):
                        receivers["router"] = ("", False)
                        continue
                if isinstance(statement, ast.With) and len(statement.items) == 1:
                    item = statement.items[0]
                    call = item.context_expr
                    if (
                        isinstance(call, ast.Call)
                        and isinstance(call.func, ast.Attribute)
                        and isinstance(call.func.value, ast.Name)
                        and call.func.attr == "group"
                        and call.func.value.id in receivers
                        and isinstance(item.optional_vars, ast.Name)
                    ):
                        options = {k.arg: _literal(k.value) for k in call.keywords}
                        prefix = _literal(call.args[0]) if len(call.args) == 1 else None
                        public = options.get("public", False)
                        if not isinstance(prefix, str) or type(public) is not bool:
                            raise ValueError
                        nested = dict(receivers)
                        nested[item.optional_vars.id] = (prefix.rstrip("/"), public)
                        visit(statement.body, nested)
                        continue
                if isinstance(statement, ast.Expr) and isinstance(
                    statement.value, ast.Call
                ):
                    call = statement.value
                    if (
                        isinstance(call.func, ast.Attribute)
                        and call.func.attr == "add"
                        and isinstance(call.func.value, ast.Name)
                        and call.func.value.id in receivers
                    ):
                        if len(call.args) != 3 or any(
                            k.arg is None for k in call.keywords
                        ):
                            raise ValueError
                        method, path = _literal(call.args[0]), _literal(call.args[1])
                        options = {k.arg: _literal(k.value) for k in call.keywords}
                        prefix, default_public = receivers[call.func.value.id]
                        name, public = (
                            options.get("name"),
                            options.get("public", default_public),
                        )
                        if public is None:
                            public = default_public
                        methods = (
                            [_literal(item) for item in call.args[0].elts]
                            if isinstance(call.args[0], (ast.List, ast.Tuple))
                            else [method]
                        )
                        if (
                            not isinstance(path, str)
                            or not methods
                            or not all(isinstance(m, str) for m in methods)
                            or (name is not None and not isinstance(name, str))
                            or type(public) is not bool
                        ):
                            raise ValueError
                        handler = _handler(call.args[2])
                        if handler is None:
                            warnings.append(
                                f"Ligne {call.lineno} : handler dynamique non résolu."
                            )
                        else:
                            handler = _controller(
                                handler,
                                controller_imports,
                                root,
                                warnings,
                                call.lineno,
                                cache,
                            )
                        for m in methods:
                            assert isinstance(m, str)
                            routes.append(
                                RouteInfo(
                                    m.upper(),
                                    prefix + path,
                                    name,
                                    public,
                                    handler,
                                    SourceLocation(source_path, call.lineno),
                                    handler_dynamic=handler is None,
                                )
                            )
                        continue
                warnings.append(
                    f"Ligne {statement.lineno} : déclaration non interprétée."
                )
            except (ValueError, RecursionError):
                warnings.append(
                    f"Ligne {statement.lineno} : déclaration dynamique non résolue."
                )

    visit(tree.body, {receiver: ("", False)} if receiver is not None else {})
    return RoutesResult(tuple(routes), tuple(warnings))


def _read_source(path: Path) -> str:
    try:
        metadata = path.lstat()
    except FileNotFoundError as error:
        raise RoutesSourceMissingError(f"Source {path.name} absente.") from error
    except OSError as error:
        raise RoutesSourceUnreadableError("Source inaccessible.") from error
    try:
        if not S_ISREG(metadata.st_mode):
            raise RoutesSourceUnreadableError(
                "La source doit être un fichier sans lien."
            )
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        )
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not S_ISREG(opened.st_mode) or not os.path.samestat(metadata, opened):
                raise RoutesSourceUnreadableError(
                    "Source remplacée pendant la lecture."
                )
            data = stream.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            raise RoutesSourceUnreadableError("Source supérieure à 1 Mio.")
        return data.decode("utf-8-sig")
    except (OSError, UnicodeError) as error:
        raise RoutesSourceUnreadableError("Source de routes illisible.") from error


def read_routes(root: str | PathLike[str]) -> RoutesResult:
    """Racine puis branchements directs seulement, sans import ni récursion."""
    canonical = resolve_project_root(root)
    if not detect_forge_project(canonical).valid:
        raise NotForgeProjectError("La racine n'est pas un projet Forge reconnu.")
    directory = canonical / "mvc/routes"
    tree = _tree(_read_source(directory / "__init__.py"))
    imports: dict[str, str] = {}
    branches: list[tuple[str, str]] = []
    direct: list[ast.stmt] = []
    # Uniquement les instructions inconditionnelles de la racine, dans leur ordre.
    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom):
            module = statement.module or ""
            if statement.level == 0 and re.fullmatch(
                r"mvc\.routes\.[A-Za-z_][A-Za-z_0-9]*", module
            ):
                for alias in statement.names:
                    if alias.asname is None and re.fullmatch(
                        r"register_[A-Za-z_0-9]+_routes", alias.name
                    ):
                        imports[alias.name] = module.rsplit(".", 1)[1]
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            call = statement.value
            if (
                isinstance(call.func, ast.Name)
                and call.func.id in imports
                and len(call.args) == 1
                and isinstance(call.args[0], ast.Name)
                and call.args[0].id == "router"
                and not call.keywords
            ):
                branches.append((imports[call.func.id], call.func.id))
                continue
        direct.append(statement)
    cache: dict[str, ast.Module | None] = {}
    result = _parse(ast.Module(body=direct, type_ignores=[]), canonical, cache=cache)
    routes, warnings = list(result.routes), list(result.warnings)
    for module, function in branches[:64]:
        filename = f"{module}.py"
        try:
            child = _tree(_read_source(directory / filename))
            definitions = [
                node
                for node in child.body
                if isinstance(node, ast.FunctionDef) and node.name == function
            ]
            if len(definitions) != 1:
                raise RoutesSourceUnreadableError("Fonction absente ou ambiguë.")
            definition = definitions[0]
            args = definition.args
            if (
                definition.decorator_list
                or len(args.args) != 1
                or args.posonlyargs
                or args.kwonlyargs
                or args.defaults
                or args.vararg
                or args.kwarg
            ):
                raise RoutesSourceUnreadableError(
                    "Signature ou décorateur non pris en charge."
                )
            parsed = _parse(
                ast.Module(body=definition.body, type_ignores=[]),
                canonical,
                args.args[0].arg,
                _controller_imports(child),
                cache,
                "mvc/routes/" + filename,
            )
            routes.extend(parsed.routes)
            warnings.extend(
                f"{filename} : {warning}" for warning in parsed.warnings[1:]
            )
        except (RoutesSourceMissingError, RoutesSourceUnreadableError) as error:
            warnings.append(f"{filename} : branchement non résolu ({error}).")
    if len(branches) > 64:
        warnings.append("Limite de 64 branchements atteinte ; liste partielle.")
    return RoutesResult(
        _with_template_presence(canonical, routes, warnings), tuple(warnings)
    )
