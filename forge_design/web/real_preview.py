"""Preview réelle dans l'application Web (FD-REALPREVIEW-004).

Composition seulement : RealPreviewController (runner) et le proxy
FD-REALPREVIEW-003 sont réutilisés tels quels. Une instance d'application
possède un RealPreviewRuntime : au plus un runner et un proxy, l'origine exacte
de l'éditeur (connue après le bind de Forge Design) et le thread du proxy.

Seuls les POST Start/Stop, à origine locale exacte, agissent. La route est
recalculée côté serveur depuis Route Explorer ; le navigateur ne fournit ni
route, ni port, ni URL. Aucune lecture d'état ne démarre la preview.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from core.http.request import Request
from core.http.response import Response

from forge_design.current_project import CurrentProjectContext
from forge_design.design.io import design_source
from forge_design.forge.project_root import (
    ProjectRootNotDirectoryError,
    ProjectRootNotFoundError,
    ProjectRootResolutionError,
)
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.forge.routes import (
    RoutesResult,
    RoutesSourceMissingError,
    RoutesSourceUnreadableError,
)
from forge_design.limits import MAX_SOURCE_PATH_LENGTH
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.real_preview import (
    RealPreviewController,
    RealPreviewError,
    RealPreviewState,
    create_real_preview_proxy,
)
from forge_design.real_preview.proxy import validate_frame_ancestor_origin
from forge_design.real_preview.route_selection import (
    RealPreviewRouteSelection,
    is_static_route_path,
    select_real_preview_route,
)
from forge_design.web.editor import (
    ContractState,
    EditorHttpError,
    check_editor_post,
    editor_form_fields,
    editor_url,
    load_contract,
    load_design,
    parse_node_path,
    parse_preview_mode,
    render_editor_error,
)

REAL_PREVIEW_WARNING = (
    "La preview réelle exécute le projet Forge sélectionné et peut déclencher "
    "ses effets de bord habituels."
)
_STATE_LABELS: dict[str, str] = {
    "stopped": "arrêtée",
    "starting": "démarrage en cours",
    "running": "en cours d'exécution",
    "failed": "en échec",
    "stopping": "arrêt en cours",
}
_PROXY_POLL_INTERVAL = 0.1
_PROXY_JOIN_TIMEOUT = 5.0
_REQUIRED_FIELDS = frozenset({"design"})
_OPTIONAL_FIELDS = frozenset({"node", "preview"})
_ROUTE_ERRORS = (
    ProjectRootNotFoundError,
    ProjectRootNotDirectoryError,
    ProjectRootResolutionError,
    NotForgeProjectError,
    RoutesSourceMissingError,
    RoutesSourceUnreadableError,
)


class ProxyServer(Protocol):
    """Sous-ensemble de RealPreviewProxyServer utilisé par le runtime."""

    @property
    def server_port(self) -> int: ...

    def serve_forever(self, poll_interval: float = 0.5) -> None: ...

    def shutdown(self) -> None: ...

    def server_close(self) -> None: ...


ProxyFactory = Callable[[RealPreviewController, str], ProxyServer]


def _create_proxy(controller: RealPreviewController, origin: str) -> ProxyServer:
    return create_real_preview_proxy(controller, frame_ancestor_origin=origin)


@dataclass(frozen=True)
class RealPreviewRuntimeStatus:
    state: RealPreviewState
    project_root: Path | None
    error: str | None
    logs: tuple[str, ...]
    proxy_origin: str | None


class RealPreviewRuntime:
    """Runner et proxy d'une instance Web ; aucun singleton, aucun état disque.

    Un verrou court sérialise start/stop/close et la création/destruction du
    proxy ; il n'est jamais tenu pendant serve_forever. Les lectures d'état ne
    l'attendent pas.
    """

    def __init__(
        self,
        controller: RealPreviewController | None = None,
        *,
        proxy_factory: ProxyFactory = _create_proxy,
    ) -> None:
        self._controller = (
            controller if controller is not None else RealPreviewController()
        )
        self._proxy_factory = proxy_factory
        self._operation = threading.Lock()
        self._editor_origin: str | None = None
        self._proxy: ProxyServer | None = None
        self._thread: threading.Thread | None = None
        self._proxy_origin: str | None = None
        self._failure: str | None = None
        self._closed = False

    def bind_editor_origin(self, origin: str) -> None:
        """Origine effective de Forge Design (port réellement lié), jamais un Host."""
        self._editor_origin = validate_frame_ancestor_origin(origin)

    @property
    def enabled(self) -> bool:
        return self._editor_origin is not None and not self._closed

    def start(self, root: Path) -> RealPreviewRuntimeStatus:
        """Démarrer le runner puis le proxy ; même projet actif : état inchangé."""
        if self._editor_origin is None or self._closed:
            raise RealPreviewError("Preview réelle indisponible sur ce serveur.")
        if not self._operation.acquire(blocking=False):
            raise RealPreviewError("Une opération de preview réelle est en cours.")
        try:
            self._sync_locked()
            current = self._controller.status()
            if (
                current.state == "running"
                and current.project_root == root
                and self._proxy is not None
            ):
                return self._snapshot()
            if not self._stop_locked():
                return self._snapshot()
            status = self._controller.start(root)
            if status.state != "running":
                return self._snapshot()
            self._start_proxy_locked(self._editor_origin)
            return self._snapshot()
        finally:
            self._operation.release()

    def _start_proxy_locked(self, origin: str) -> None:
        """Proxy et son thread ; en cas d'échec, le runner est arrêté."""
        try:
            proxy = self._proxy_factory(self._controller, origin)
        except (OSError, ValueError):
            self._controller.stop()
            self._failure = "Le proxy de preview n'a pas pu être créé."
            return
        thread = threading.Thread(
            target=proxy.serve_forever,
            kwargs={"poll_interval": _PROXY_POLL_INTERVAL},
            name="forge-design-real-preview-proxy",
            daemon=True,
        )
        try:
            thread.start()
        except RuntimeError:
            proxy.server_close()
            self._controller.stop()
            self._failure = "Le proxy de preview n'a pas pu être lancé."
            return
        self._proxy, self._thread = proxy, thread
        self._proxy_origin = f"http://127.0.0.1:{proxy.server_port}"

    def _close_proxy_locked(self) -> None:
        """Arrêt explicite : shutdown, join, fermeture du socket (pas de démon seul)."""
        proxy, thread = self._proxy, self._thread
        self._proxy = self._thread = self._proxy_origin = None
        if proxy is None:
            return
        if thread is not None and thread.is_alive():
            proxy.shutdown()
        if thread is not None:
            thread.join(_PROXY_JOIN_TIMEOUT)
        proxy.server_close()

    def _stop_locked(self) -> bool:
        """Proxy d'abord, runner ensuite ; False si le runner reste actif."""
        self._close_proxy_locked()
        status = self._controller.stop()
        if status.state == "stopped":
            self._failure = None
            return True
        self._failure = status.error or "Preview réelle impossible à arrêter."
        return False

    def _sync_locked(self) -> None:
        """Fermer un proxy devenu inutile ; proxy mort → runner arrêté."""
        if self._proxy is None:
            return
        status = self._controller.status()
        alive = self._thread is not None and self._thread.is_alive()
        if status.state == "running" and alive:
            return
        self._close_proxy_locked()
        if status.state == "running":
            self._controller.stop()
            self._failure = (
                "Le proxy de preview s'est arrêté de façon inattendue ; "
                "la preview a été arrêtée."
            )

    def stop(self) -> bool:
        """Arrêt explicite, idempotent ; False si le runner n'a pas pu être arrêté."""
        with self._operation:
            return self._stop_locked()

    def close(self) -> None:
        """Fermeture définitive (arrêt de Forge Design), idempotente."""
        with self._operation:
            if self._closed:
                return
            self._closed = True
            self._stop_locked()

    def status(self) -> RealPreviewRuntimeStatus:
        """Instantané ; nettoie un proxy orphelin si aucune opération n'est en cours."""
        if self._operation.acquire(blocking=False):
            try:
                self._sync_locked()
            finally:
                self._operation.release()
        return self._snapshot()

    def _snapshot(self) -> RealPreviewRuntimeStatus:
        status = self._controller.status()
        state, error = status.state, status.error
        if self._failure is not None and state in ("stopped", "failed"):
            state, error = "failed", self._failure
        origin = self._proxy_origin if state == "running" else None
        return RealPreviewRuntimeStatus(
            state, status.project_root, error, status.logs, origin
        )


def real_preview_frame_url(proxy_origin: str, route_path: str) -> str:
    """URL d'iframe : origine du proxy validée et chemin statique d'origine."""
    validate_frame_ancestor_origin(proxy_origin)
    if not is_static_route_path(route_path):
        raise ValueError("Chemin de route de preview refusé.")
    return proxy_origin + route_path


def route_selection(
    context: CurrentProjectContext, registry: ToolRegistry, contract: ContractState
) -> RealPreviewRouteSelection:
    """Route recalculée côté serveur : contrat du Design, puis Route Explorer."""
    if contract.contract is None or context.root is None:
        return RealPreviewRouteSelection(
            False, None, "Contrat indisponible : route réelle inconnue."
        )
    try:
        result = registry.get("route-explorer").run(context.root)
    except _ROUTE_ERRORS:
        return RealPreviewRouteSelection(False, None, "Routes du projet illisibles.")
    if not isinstance(result, RoutesResult):
        raise TypeError("route-explorer doit retourner RoutesResult.")
    return select_real_preview_route(contract.contract.template, result)


@dataclass(frozen=True)
class RealPreviewWebState:
    """Données primitives du panneau ; aucun contrôleur, proxy ni thread."""

    enabled: bool
    state: str
    state_label: str
    error: str | None
    logs: tuple[str, ...]
    route_available: bool
    route_path: str | None
    route_reason: str | None
    proxy_origin: str | None
    frame_url: str | None
    warning: str
    can_start: bool
    can_stop: bool


@dataclass(frozen=True)
class RealPreviewPanel:
    runtime: RealPreviewRuntime
    registry: ToolRegistry

    def view(
        self, context: CurrentProjectContext, contract: ContractState
    ) -> RealPreviewWebState:
        selection = route_selection(context, self.registry, contract)
        status = self.runtime.status()
        # Le runtime représente l'application courante, pas un Design.
        same = status.project_root is not None and status.project_root == context.root
        state = status.state if same else "stopped"
        origin = status.proxy_origin if same else None
        frame = (
            real_preview_frame_url(origin, selection.path)
            if origin is not None and selection.path is not None
            else None
        )
        return RealPreviewWebState(
            enabled=self.runtime.enabled,
            state=state,
            state_label=_STATE_LABELS[state],
            error=status.error if same else None,
            logs=status.logs if same and state == "failed" else (),
            route_available=selection.available,
            route_path=selection.path,
            route_reason=selection.reason,
            proxy_origin=origin,
            frame_url=frame,
            warning=REAL_PREVIEW_WARNING,
            can_start=self.runtime.enabled
            and selection.available
            and state in ("stopped", "failed"),
            can_stop=state in ("running", "starting"),
        )


def _redirect(url: str) -> Response:
    return Response(303, b"", headers={"Location": url})


def real_preview_action(
    request: Request,
    context: CurrentProjectContext,
    registry: ToolRegistry,
    runtime: RealPreviewRuntime,
    *,
    stop: bool,
) -> Response:
    """POST Start/Stop : champs exacts design (+ node, preview), aucune route."""
    design_path: str | None = None
    try:
        check_editor_post(request, context)
        fields = editor_form_fields(request)
        names = frozenset(fields)
        if not _REQUIRED_FIELDS <= names <= _REQUIRED_FIELDS | _OPTIONAL_FIELDS:
            raise EditorHttpError(400, "Champs de formulaire inattendus.")
        try:
            preview = parse_preview_mode(fields.get("preview"))
            node = parse_node_path(fields.get("node", ""))
        except ValueError as error:
            raise EditorHttpError(400, str(error)) from None
        design_path = fields["design"]
        if stop:
            # Le Design ne sert qu'au retour : l'arrêt ne dépend pas de sa lecture.
            if (
                len(design_path) > MAX_SOURCE_PATH_LENGTH
                or design_source(design_path) is None
            ):
                raise EditorHttpError(400, "Chemin de Design refusé.")
            if not runtime.stop():
                raise EditorHttpError(500, "Preview réelle impossible à arrêter.")
            return _redirect(editor_url(design_path, node, "real-stopped", preview))
        read = load_design(context, design_path)
        if read.design is None:
            raise EditorHttpError(
                409, "Design illisible ou invalide : preview réelle impossible."
            )
        selection = route_selection(
            context, registry, load_contract(context, read.design)
        )
        if not selection.available:
            raise EditorHttpError(
                409, f"Preview réelle indisponible : {selection.reason}"
            )
        assert context.root is not None
        try:
            status = runtime.start(context.root)
        except RealPreviewError as error:
            raise EditorHttpError(409, str(error)) from None
    except EditorHttpError as error:
        return render_editor_error(context, design_path, error.message, error.status)
    notice = "real-started" if status.state == "running" else "real-failed"
    return _redirect(editor_url(design_path, node, notice, preview))
