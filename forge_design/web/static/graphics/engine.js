// Graphic Core — instance de moteur graphique (FD-GRAPHICS-002, viewport FD-GRAPHICS-004,
// niveau de détail FD-GRAPHICS-006).
// Une instance par conteneur, sans singleton ni état global : scène validée,
// index, sélection et viewport runtime, rendu et écouteurs lui appartiennent ;
// destroy() les libère. Le moteur ne lit ni n'écrit aucun projet et ne persiste rien.

import { detailLevelForScale } from "./detail-level.js";
import { validateScene } from "./model.js";
import { createSelection, indexScene } from "./scene.js";
import { applyDetailLevel, applySelection, renderScene } from "./svg-renderer.js";
import { createViewport, wheelFactor } from "./viewport.js";

// Déplacement clavier (Maj + flèches) : fraction de la zone visible.
const PAN_STEP = 0.15;
const ARROWS = { ArrowLeft: [1, 0], ArrowRight: [-1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] };

function htmlElement(document, name, attributes = {}, text = "") {
  const element = document.createElement(name);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  if (text) element.textContent = text;
  return element;
}

export function createGraphicEngine(container, input, options = {}) {
  const scene = validateScene(input);
  const index = indexScene(scene);
  const selection = createSelection(index);
  const onSelectionChange = typeof options.onSelectionChange === "function" ? options.onSelectionChange : null;
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
  const area = htmlElement(document, "div", { class: "gx-viewport" });
  toolbar.append(controls.fit, controls.zoomIn, controls.zoomOut, scaleText);
  frame.append(toolbar, area);
  container.append(frame);
  const viewport = createViewport(scene, measure());
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
  let destroyed = false;

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
    return viewportState();
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
    if (nodeListeners) nodeListeners.abort();
    nodeListeners = null;
    if (view) view.svg.remove();
    view = null;
    nodeElements = new Set();
  }

  function render() {
    alive();
    detach();
    view = renderScene(area, scene);
    nodeElements = new Set(view.nodes.values());
    nodeListeners = new AbortController();
    const { signal } = nodeListeners;
    for (const [nodeId, element] of view.nodes) {
      element.addEventListener("click", () => toggle(nodeId), { signal });
      element.addEventListener(
        "keydown",
        (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            toggle(nodeId);
          }
        },
        { signal },
      );
    }
    view.svg.addEventListener(
      "keydown",
      (event) => {
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
  on(area, "pointerup", endPan);
  on(area, "pointercancel", endPan);
  // Maj + flèches : déplacement accessible sans glisser.
  on(area, "keydown", (event) => {
    const direction = ARROWS[event.key];
    if (!direction || !event.shiftKey || event.altKey || event.ctrlKey || event.metaKey) return;
    event.preventDefault();
    const { width, height } = viewport.area();
    navigate(() => viewport.panBy(direction[0] * width * PAN_STEP, direction[1] * height * PAN_STEP));
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
    detailLevel: () => {
      alive();
      return detailLevel;
    },
    selection: () => selection.current(),
    node: (nodeId) => index.nodes.get(nodeId) ?? null,
    edge: (edgeId) => index.edges.get(edgeId) ?? null,
    scene: () => scene,
    isDestroyed: () => destroyed,
  });
}
