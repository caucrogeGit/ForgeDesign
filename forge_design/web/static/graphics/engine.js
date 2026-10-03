// Graphic Core — instance de moteur graphique (FD-GRAPHICS-002).
// Une instance par conteneur, sans singleton ni état global : scène validée,
// index, sélection runtime, rendu et écouteurs lui appartiennent ; destroy()
// les libère. Le moteur ne lit ni n'écrit aucun projet et ne persiste rien.

import { validateScene } from "./model.js";
import { createSelection, indexScene } from "./scene.js";
import { applySelection, renderScene } from "./svg-renderer.js";

export function createGraphicEngine(container, input, options = {}) {
  const scene = validateScene(input);
  const index = indexScene(scene);
  const selection = createSelection(index);
  const onSelectionChange = typeof options.onSelectionChange === "function" ? options.onSelectionChange : null;
  let listeners = null;
  let view = null;
  let destroyed = false;

  function alive() {
    if (destroyed) throw new Error("Moteur graphique détruit.");
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

  function detach() {
    if (listeners) listeners.abort();
    listeners = null;
    if (view) view.svg.remove();
    view = null;
  }

  function render() {
    alive();
    detach();
    view = renderScene(container, scene);
    listeners = new AbortController();
    const { signal } = listeners;
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
    return view.svg;
  }

  function destroy() {
    if (destroyed) return;
    detach();
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
    selection: () => selection.current(),
    node: (nodeId) => index.nodes.get(nodeId) ?? null,
    scene: () => scene,
    isDestroyed: () => destroyed,
  });
}
