// Graphic Core — instance de moteur graphique (FD-GRAPHICS-002, viewport FD-GRAPHICS-004,
// niveau de détail FD-GRAPHICS-006, minicarte FD-GRAPHICS-007, déplacement de nœuds
// FD-GRAPHICS-EDIT-001).
// Une instance par conteneur, sans singleton ni état global : scène validée,
// index, sélection et viewport runtime, rendu et écouteurs lui appartiennent ;
// destroy() les libère. Le moteur ne lit ni n'écrit aucun projet et ne persiste rien.

import { detailLevelForScale } from "./detail-level.js";
import {
  describeVisible,
  minimapLayout,
  minimapToWorld,
  minimapViewportRect,
  needsMinimap,
  renderMinimap,
} from "./minimap.js";
import { validateScene } from "./model.js";
import { createSelection, indexScene } from "./scene.js";
import { applyDetailLevel, applyMovable, applySelection, previewNodeMove, renderScene } from "./svg-renderer.js";
import { createViewport, wheelFactor } from "./viewport.js";

// Minicarte : en deçà de ce déplacement (pixels écran), un appui-relâcher est un clic.
const CLICK_SLOP = 3;
// Déplacement clavier (Maj + flèches) : fraction de la zone visible.
const PAN_STEP = 0.15;
const ARROWS = { ArrowLeft: [1, 0], ArrowRight: [-1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] };
// Déplacement de nœud : seuil écran (pixels, constant quel que soit le zoom) au-delà
// duquel un appui sur un nœud devient un glisser ; en deçà, c'est un clic (sélection).
// Provenance : seuil 4/zoom de DrawCiel (startComponentDrag / workspacePointerMove).
export const DRAG_THRESHOLD = 4;
// Ctrl + Maj + flèches : un pas client (keyboardStep) dans la direction de la flèche.
// Ni Alt + flèches (Précédent / Suivant des navigateurs sous Linux et Windows), ni
// Maj + flèches (pan), ni Ctrl + flèches (espaces de travail macOS).
const MOVES = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
export const MOVE_SHORTCUTS =
  "Control+Shift+ArrowLeft Control+Shift+ArrowRight Control+Shift+ArrowUp Control+Shift+ArrowDown";

function htmlElement(document, name, attributes = {}, text = "") {
  const element = document.createElement(name);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  if (text) element.textContent = text;
  return element;
}

// Option nodeMove (opt-in, runtime, jamais dans la scène) : sans elle, aucun nœud
// n'est déplaçable. canMove(node) choisit les nœuds ; keyboardStep (monde) rend le
// déplacement disponible au clavier comme au pointeur ; constrain({ nodeId, delta })
// peut aligner ou borner le delta monde ; onMove({ nodeId, from, to, delta, input })
// reçoit l'intention finale et rend true (ou une promesse de true) si le client
// l'accepte : l'aperçu reste alors jusqu'au remplacement de la scène ; sinon il est
// annulé et la scène validée fait foi.
function moveOptions(value) {
  if (value === undefined || value === null) return null;
  if (typeof value !== "object") throw new TypeError("nodeMove : objet attendu.");
  const { canMove, constrain, keyboardStep, onMove } = value;
  if (typeof canMove !== "function" || typeof onMove !== "function") {
    throw new TypeError("nodeMove : canMove et onMove sont des fonctions.");
  }
  if (constrain !== undefined && typeof constrain !== "function") throw new TypeError("nodeMove : constrain est une fonction.");
  if (typeof keyboardStep !== "number" || !Number.isFinite(keyboardStep) || keyboardStep <= 0) {
    throw new TypeError("nodeMove : keyboardStep est un nombre fini strictement positif.");
  }
  return Object.freeze({ canMove, constrain: constrain ?? ((proposal) => proposal.delta), keyboardStep, onMove });
}

function finiteDelta(value) {
  if (value === null || typeof value !== "object") return null;
  const { x, y } = value;
  if (typeof x !== "number" || typeof y !== "number" || !Number.isFinite(x) || !Number.isFinite(y)) return null;
  // -0 normalisé : un delta nul reste nul.
  return Object.freeze({ x: x + 0, y: y + 0 });
}

export function createGraphicEngine(container, input, options = {}) {
  const scene = validateScene(input);
  const index = indexScene(scene);
  const selection = createSelection(index);
  const onSelectionChange = typeof options.onSelectionChange === "function" ? options.onSelectionChange : null;
  const nodeMove = moveOptions(options.nodeMove);
  const document = container.ownerDocument;
  const frame = htmlElement(document, "div", { class: "gx-frame" });
  const toolbar = htmlElement(document, "div", { class: "gx-toolbar", role: "toolbar", "aria-label": "Navigation du graphe" });
  const button = (text, label) =>
    htmlElement(document, "button", { type: "button", class: "gx-toolbar-button", title: label, "aria-label": label }, text);
  const controls = {
    fit: button("Ajuster", "Ajuster toute la scène à la zone"),
    zoomIn: button("+", "Zoom avant"),
    zoomOut: button("−", "Zoom arrière"),
  };
  const scaleText = htmlElement(document, "span", { class: "gx-toolbar-scale" });
  // La minicarte vit dans la scène (coin supérieur droit), hors de la zone de pan.
  const stage = htmlElement(document, "div", { class: "gx-stage" });
  const area = htmlElement(document, "div", { class: "gx-viewport" });
  toolbar.append(controls.fit, controls.zoomIn, controls.zoomOut, scaleText);
  stage.append(area);
  frame.append(toolbar, stage);
  container.append(frame);
  const viewport = createViewport(scene, measure());
  const miniLayout = minimapLayout(scene);
  const frameListeners = new AbortController();
  let observer = null;
  let nodeListeners = null;
  let nodeElements = new Set();
  let view = null;
  let panning = null;
  let detailLevel = null;
  // L'hystérésis ne s'appuie que sur un niveau obtenu avec une zone mesurée :
  // l'échelle provisoire d'avant la première mesure ne fait pas historique.
  let levelMeasured = false;
  let minimap = null;
  let minimapShown = false;
  let minimapDrag = null;
  let destroyed = false;
  // Déplacement de nœud (runtime) : nœuds déplaçables du rendu courant, geste en
  // cours, intention soumise en attente du client, clic à ignorer après un glisser.
  let movable = new Set();
  let moving = null;
  let submitted = null;
  let swallowClick = false;

  function measure() {
    return { width: Math.max(0, area.clientWidth || 0), height: Math.max(0, area.clientHeight || 0) };
  }

  function alive() {
    if (destroyed) throw new Error("Moteur graphique détruit.");
  }

  function applyViewport() {
    const box = viewport.viewBox();
    view.svg.setAttribute("viewBox", `${box.x} ${box.y} ${box.width} ${box.height}`);
    scaleText.textContent = `${Math.round(viewport.state().scale * 100)} %`;
    // Le DOM n'est touché que si le niveau change, jamais à chaque zoom.
    const level = detailLevelForScale(viewport.state().scale, levelMeasured ? detailLevel : null);
    if (level !== detailLevel) {
      detailLevel = level;
      applyDetailLevel(view, level);
    }
    const { width, height } = viewport.area();
    levelMeasured = width > 0 && height > 0;
    updateMinimap();
    return viewportState();
  }

  // O(1) : seuls le rectangle visible et le nom accessible changent ; la structure jamais.
  function updateMinimap() {
    const visible = viewport.visibleWorldRect();
    // Pendant un glisser ou avec le focus, la minicarte ne disparaît pas sous l'utilisateur.
    const engaged = minimapDrag !== null || document.activeElement === minimap.element;
    minimapShown = (engaged && minimapShown) || needsMinimap(scene, visible, minimapShown);
    minimap.setVisible(minimapShown);
    if (visible !== null) minimap.update(minimapViewportRect(miniLayout, visible), describeVisible(scene, visible));
  }
  function viewportState() {
    const { scale, x, y } = viewport.state();
    const { width, height } = viewport.area();
    return Object.freeze({ scale, x, y, width, height });
  }

  function navigate(action) {
    alive();
    action();
    return applyViewport();
  }

  function changed(state) {
    applySelection(view, state);
    if (onSelectionChange) onSelectionChange(state);
    return state;
  }

  function select(nodeId) {
    alive();
    return changed(selection.select(nodeId));
  }

  function clearSelection() {
    alive();
    return changed(selection.clear());
  }

  function toggle(nodeId) {
    const current = selection.current();
    return current && current.nodeId === nodeId ? clearSelection() : select(nodeId);
  }

  // Point écran relatif à la zone de contenu (bordure de la zone exclue).
  function local(event) {
    const box = area.getBoundingClientRect();
    return { x: event.clientX - box.left - (area.clientLeft || 0), y: event.clientY - box.top - (area.clientTop || 0) };
  }

  function onNode(target) {
    for (let element = target; element && element !== area; element = element.parentNode) {
      if (nodeElements.has(element)) return true;
    }
    return false;
  }

  function detach() {
    // Un nouveau rendu repart de la scène validée : aucun aperçu ne survit.
    moving = null;
    submitted = null;
    swallowClick = false;
    movable = new Set();
    if (nodeListeners) nodeListeners.abort();
    nodeListeners = null;
    if (view) view.svg.remove();
    if (minimap) minimap.element.remove();
    view = null;
    minimap = null;
    minimapDrag = null;
    nodeElements = new Set();
  }

  function panStep(direction) {
    const { width, height } = viewport.area();
    navigate(() => viewport.panBy(direction[0] * width * PAN_STEP, direction[1] * height * PAN_STEP));
  }

  function minimapWorld(event) {
    return minimapToWorld(miniLayout, minimap.toMinimap(event.clientX, event.clientY));
  }

  // Clic : recentre sur le point pointé. Glisser depuis le rectangle visible : le
  // rectangle suit le pointeur en gardant le décalage de saisie (pas de saut) ; glisser
  // ailleurs : recentrage continu. L'échelle ne change jamais.
  function bindMinimap(signal) {
    const element = minimap.element;
    const listen = (type, listener, extra = {}) => element.addEventListener(type, listener, { signal, ...extra });
    const moveTo = (event) => {
      const world = minimapWorld(event);
      navigate(() => viewport.centerAt({ x: world.x + minimapDrag.dx, y: world.y + minimapDrag.dy }));
    };
    listen("pointerdown", (event) => {
      if (event.button !== 0 || minimapDrag) return;
      event.preventDefault();
      const world = minimapWorld(event);
      const visible = viewport.visibleWorldRect();
      const inside =
        visible !== null &&
        world.x >= visible.x &&
        world.x <= visible.x + visible.width &&
        world.y >= visible.y &&
        world.y <= visible.y + visible.height;
      const center = inside ? { x: visible.x + visible.width / 2, y: visible.y + visible.height / 2 } : world;
      minimapDrag = {
        id: event.pointerId,
        dx: center.x - world.x,
        dy: center.y - world.y,
        startX: event.clientX,
        startY: event.clientY,
        moved: false,
      };
      if (element.setPointerCapture) element.setPointerCapture(event.pointerId);
      moveTo(event);
    });
    listen("pointermove", (event) => {
      if (!minimapDrag || event.pointerId !== minimapDrag.id) return;
      minimapDrag.moved ||=
        Math.abs(event.clientX - minimapDrag.startX) > CLICK_SLOP || Math.abs(event.clientY - minimapDrag.startY) > CLICK_SLOP;
      moveTo(event);
    });
    const end = (event, click) => {
      if (!minimapDrag || event.pointerId !== minimapDrag.id) return;
      if (element.releasePointerCapture) element.releasePointerCapture(event.pointerId);
      // Un clic (sans glisser) dans le rectangle recentre aussi sur le point cliqué.
      if (click && !minimapDrag.moved) {
        const world = minimapWorld(event);
        minimapDrag = null;
        navigate(() => viewport.centerAt(world));
        return;
      }
      minimapDrag = null;
      applyViewport();
    };
    listen("pointerup", (event) => end(event, true));
    listen("pointercancel", (event) => end(event, false));
    // Ctrl/Cmd + molette sur la minicarte : zoom autour du centre de la vue (jamais le zoom de page).
    listen(
      "wheel",
      (event) => {
        if (!event.ctrlKey && !event.metaKey) return;
        event.preventDefault();
        const { width, height } = viewport.area();
        navigate(() => viewport.zoomAt({ x: width / 2, y: height / 2 }, wheelFactor(event.deltaY, event.deltaMode)));
      },
      { passive: false },
    );
    // Flèches seules sur la minicarte focalisée : déplacent la zone visible (même pas que Maj + flèches).
    listen("keydown", (event) => {
      const direction = ARROWS[event.key];
      if (!direction || event.shiftKey || event.altKey || event.ctrlKey || event.metaKey) return;
      event.preventDefault();
      panStep(direction);
    });
    // Perte du focus : la politique d'affichage s'applique de nouveau.
    listen("blur", () => applyViewport());
  }

  function movableNodes() {
    const result = new Set();
    if (!nodeMove) return result;
    for (const node of scene.nodes) {
      let allowed = false;
      try {
        allowed = nodeMove.canMove(node) === true;
      } catch {
        allowed = false;
      }
      if (allowed) result.add(node.id);
    }
    return result;
  }

  // Point monde sous un événement pointeur : le moteur seul connaît son viewport.
  function worldAt(event) {
    const point = local(event);
    const { scale, x, y } = viewport.state();
    return { x: x + point.x / scale, y: y + point.y / scale };
  }

  function constrained(nodeId, raw) {
    let delta = null;
    try {
      delta = finiteDelta(nodeMove.constrain(Object.freeze({ nodeId, delta: Object.freeze({ ...raw }) })));
    } catch {
      delta = null;
    }
    return delta;
  }

  function preview(nodeId, delta) {
    previewNodeMove(view, nodeId, index.incident.get(nodeId), delta);
  }

  function pressNode(nodeId, event) {
    if (event.button !== 0 || moving || submitted || panning || !view) return;
    swallowClick = false;
    moving = {
      nodeId,
      pointerId: event.pointerId,
      screen: { x: event.clientX, y: event.clientY },
      world: worldAt(event),
      dragging: false,
      delta: Object.freeze({ x: 0, y: 0 }),
    };
  }

  function dragTo(event) {
    if (!moving || event.pointerId !== moving.pointerId) return false;
    if (!moving.dragging) {
      if (Math.hypot(event.clientX - moving.screen.x, event.clientY - moving.screen.y) < DRAG_THRESHOLD) return true;
      // La capture ne commence qu'au seuil : un simple clic reste un clic sur le nœud.
      moving.dragging = true;
      if (area.setPointerCapture) area.setPointerCapture(event.pointerId);
      area.classList.toggle("gx-moving", true);
      const current = selection.current();
      if (!current || current.nodeId !== moving.nodeId) select(moving.nodeId);
      view.nodes.get(moving.nodeId).focus();
    }
    const world = worldAt(event);
    const delta = constrained(moving.nodeId, { x: world.x - moving.world.x, y: world.y - moving.world.y });
    if (delta && (delta.x !== moving.delta.x || delta.y !== moving.delta.y)) {
      moving.delta = delta;
      preview(moving.nodeId, delta);
    }
    return true;
  }

  function stopMoving(release) {
    const ended = moving;
    moving = null;
    area.classList.toggle("gx-moving", false);
    if (ended && ended.dragging && release && area.releasePointerCapture) area.releasePointerCapture(ended.pointerId);
    return ended;
  }

  // Échap, pointercancel, perte de capture : aucun appel au client, rendu autoritaire.
  function cancelMove(release = true) {
    const ended = stopMoving(release);
    if (!ended) return;
    if (ended.dragging) swallowClick = true;
    if (view) preview(ended.nodeId, { x: 0, y: 0 });
  }

  function submit(nodeId, delta, inputKind) {
    const rect = index.nodes.get(nodeId).rect;
    const from = Object.freeze({ x: rect.x, y: rect.y });
    const move = Object.freeze({
      nodeId,
      from,
      to: Object.freeze({ x: from.x + delta.x, y: from.y + delta.y }),
      delta,
      input: inputKind,
    });
    const token = Object.freeze({ nodeId, delta });
    submitted = token;
    const settle = (accepted) => {
      if (submitted !== token) return;
      // Accepté : l'aperçu reste jusqu'au remplacement de la scène par le client.
      if (accepted === true) return;
      submitted = null;
      if (view) preview(nodeId, { x: 0, y: 0 });
    };
    let result;
    try {
      result = nodeMove.onMove(move);
    } catch {
      settle(false);
      return;
    }
    if (result && typeof result.then === "function") result.then(settle, () => settle(false));
    else settle(result);
  }

  function release(event) {
    if (!moving || event.pointerId !== moving.pointerId) return false;
    const ended = stopMoving(true);
    if (!ended.dragging) return true;
    swallowClick = true;
    if (ended.delta.x === 0 && ended.delta.y === 0) preview(ended.nodeId, ended.delta);
    else submit(ended.nodeId, ended.delta, "pointer");
    return true;
  }

  function keyboardMove(nodeId, event) {
    if (event.altKey || event.metaKey) return;
    // Toujours consommé sur un nœud déplaçable, même pendant une intention en attente.
    event.preventDefault();
    if (moving || submitted || !view) return;
    const [dx, dy] = MOVES[event.key];
    const delta = constrained(nodeId, { x: dx * nodeMove.keyboardStep, y: dy * nodeMove.keyboardStep });
    if (!delta || (delta.x === 0 && delta.y === 0)) return;
    const current = selection.current();
    if (!current || current.nodeId !== nodeId) select(nodeId);
    preview(nodeId, delta);
    submit(nodeId, delta, "keyboard");
  }

  function render() {
    alive();
    detach();
    // La minicarte précède la zone : juste après la barre d'outils dans l'ordre de tabulation.
    minimap = renderMinimap(stage, scene, miniLayout);
    view = renderScene(area, scene);
    nodeElements = new Set(view.nodes.values());
    nodeListeners = new AbortController();
    const { signal } = nodeListeners;
    bindMinimap(signal);
    movable = movableNodes();
    applyMovable(view, movable, MOVE_SHORTCUTS);
    for (const [nodeId, element] of view.nodes) {
      element.addEventListener(
        "click",
        () => {
          // Le clic qui suit un glisser n'est pas une sélection.
          if (swallowClick) {
            swallowClick = false;
            return;
          }
          toggle(nodeId);
        },
        { signal },
      );
      element.addEventListener(
        "keydown",
        (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            toggle(nodeId);
          } else if (movable.has(nodeId) && MOVES[event.key] && event.ctrlKey && event.shiftKey) {
            keyboardMove(nodeId, event);
          }
        },
        { signal },
      );
      if (movable.has(nodeId)) element.addEventListener("pointerdown", (event) => pressNode(nodeId, event), { signal });
    }
    view.svg.addEventListener(
      "keydown",
      (event) => {
        // Échap pendant un glisser : le geste est annulé, la sélection conservée.
        if (event.key === "Escape" && moving) {
          event.preventDefault();
          cancelMove();
          return;
        }
        const current = selection.current();
        if (event.key === "Escape" && current) {
          event.preventDefault();
          clearSelection();
          view.nodes.get(current.nodeId).focus();
        }
      },
      { signal },
    );
    applySelection(view, selection.current());
    if (detailLevel !== null) applyDetailLevel(view, detailLevel);
    applyViewport();
    return view.svg;
  }

  function resize() {
    return navigate(() => {
      const { width, height } = measure();
      viewport.setArea(width, height);
    });
  }

  const on = (target, type, listener, extra = {}) =>
    target.addEventListener(type, listener, { signal: frameListeners.signal, ...extra });
  on(controls.fit, "click", () => navigate(viewport.fit));
  on(controls.zoomIn, "click", () => navigate(viewport.zoomIn));
  on(controls.zoomOut, "click", () => navigate(viewport.zoomOut));
  // Molette seule : défilement de la page ; Ctrl/Cmd + molette (ou pincement) : zoom.
  on(
    area,
    "wheel",
    (event) => {
      if (!event.ctrlKey && !event.metaKey) return;
      event.preventDefault();
      navigate(() => viewport.zoomAt(local(event), wheelFactor(event.deltaY, event.deltaMode)));
    },
    { passive: false },
  );
  // Pan : bouton principal sur le fond (jamais sur un nœud) ou bouton du milieu.
  on(area, "pointerdown", (event) => {
    if (panning || !((event.button === 0 && !onNode(event.target)) || event.button === 1)) return;
    if (event.button === 1) event.preventDefault();
    panning = { id: event.pointerId, x: event.clientX, y: event.clientY };
    if (area.setPointerCapture) area.setPointerCapture(event.pointerId);
    area.classList.toggle("gx-panning", true);
  });
  on(area, "pointermove", (event) => {
    if (dragTo(event)) return;
    if (!panning || event.pointerId !== panning.id) return;
    const dx = event.clientX - panning.x;
    const dy = event.clientY - panning.y;
    panning.x = event.clientX;
    panning.y = event.clientY;
    if (dx || dy) navigate(() => viewport.panBy(dx, dy));
  });
  const endPan = (event) => {
    if (!panning || event.pointerId !== panning.id) return;
    if (area.releasePointerCapture) area.releasePointerCapture(event.pointerId);
    panning = null;
    area.classList.toggle("gx-panning", false);
  };
  on(area, "pointerup", (event) => {
    if (!release(event)) endPan(event);
  });
  on(area, "pointercancel", (event) => {
    if (moving && event.pointerId === moving.pointerId) cancelMove();
    else endPan(event);
  });
  // Capture perdue en cours de glisser (fenêtre, élément retiré) : annulation.
  on(area, "lostpointercapture", (event) => {
    if (moving && moving.dragging && event.pointerId === moving.pointerId) cancelMove(false);
  });
  // Maj + flèches : déplacement accessible sans glisser.
  on(area, "keydown", (event) => {
    const direction = ARROWS[event.key];
    if (!direction || !event.shiftKey || event.altKey || event.ctrlKey || event.metaKey) return;
    event.preventDefault();
    panStep(direction);
  });
  if (typeof ResizeObserver === "function") {
    observer = new ResizeObserver(() => {
      if (!destroyed) resize();
    });
    observer.observe(area);
  }

  function destroy() {
    if (destroyed) return;
    detach();
    frameListeners.abort();
    if (observer) observer.disconnect();
    observer = null;
    panning = null;
    moving = null;
    submitted = null;
    frame.remove();
    selection.clear();
    destroyed = true;
  }

  function focus(nodeId) {
    alive();
    const element = view.nodes.get(nodeId);
    if (element) element.focus();
    return element !== undefined;
  }

  render();
  return Object.freeze({
    render,
    select,
    clearSelection,
    focus,
    destroy,
    fit: () => navigate(viewport.fit),
    home: () => navigate(viewport.home),
    zoomIn: () => navigate(viewport.zoomIn),
    zoomOut: () => navigate(viewport.zoomOut),
    zoomAt: (point, factor) => navigate(() => viewport.zoomAt(point, factor)),
    panBy: (dx, dy) => navigate(() => viewport.panBy(dx, dy)),
    resize,
    viewport: () => {
      alive();
      return viewportState();
    },
    centerAt: (point) => navigate(() => viewport.centerAt(point)),
    // Inspection de la minicarte (lecture seule).
    minimap: () => {
      alive();
      const visible = viewport.visibleWorldRect();
      return Object.freeze({
        visible: minimapShown,
        width: miniLayout.width,
        height: miniLayout.height,
        rect: visible === null ? null : minimapViewportRect(miniLayout, visible),
      });
    },
    detailLevel: () => {
      alive();
      return detailLevel;
    },
    selection: () => selection.current(),
    // Déplacement (lecture seule) : nœuds déplaçables et aperçu en cours.
    movableNodes: () => {
      alive();
      return Object.freeze([...movable]);
    },
    movePreview: () => {
      alive();
      if (moving && moving.dragging) return Object.freeze({ nodeId: moving.nodeId, delta: moving.delta, state: "dragging" });
      if (submitted) return Object.freeze({ nodeId: submitted.nodeId, delta: submitted.delta, state: "submitted" });
      return null;
    },
    node: (nodeId) => index.nodes.get(nodeId) ?? null,
    edge: (edgeId) => index.edges.get(edgeId) ?? null,
    scene: () => scene,
    isDestroyed: () => destroyed,
  });
}
