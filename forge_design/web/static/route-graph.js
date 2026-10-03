// Route Explorer — client du Graphic Core (FD-GRAPHICS-002).
// Lit la GraphicScene inerte fournie par le serveur, crée une instance du moteur
// par conteneur et remplit le panneau de détails à partir des données opaques
// du nœud. Sans JavaScript ou si la scène est refusée, le SVG serveur reste
// affiché comme repli statique.

import { createGraphicEngine } from "./graphics/engine.js";

const IDLE = "Sélectionnez un élément du graphe.";

export function mountRouteGraph(container) {
  const source = container.querySelector("script[data-graphic-scene]");
  const host = container.querySelector("[data-graphic-host]");
  const fallback = container.querySelector("[data-graphic-fallback]");
  const status = container.querySelector("[data-selection-status]");
  const details = container.querySelector("[data-selection-details]");
  const kind = container.querySelector("[data-selection-kind]");
  const label = container.querySelector("[data-selection-label]");
  const presence = container.querySelector("[data-selection-presence]");
  const clear = container.querySelector("[data-selection-clear]");
  if (!source || !host || !status || !details || !kind || !label || !presence || !clear) return null;
  let engine;
  try {
    engine = createGraphicEngine(host, JSON.parse(source.textContent), {
      onSelectionChange(state) {
        const node = state ? engine.node(state.nodeId) : null;
        details.hidden = node === null;
        clear.hidden = node === null;
        kind.textContent = node ? node.data["kind-label"] ?? "—" : "";
        label.textContent = node ? node.label : "";
        presence.textContent = node ? node.data["presence-label"] ?? "—" : "";
        status.textContent = node ? `Élément sélectionné : ${node.label}` : IDLE;
      },
    });
  } catch (error) {
    status.textContent = `Vue interactive indisponible (${error.message}) ; le graphe statique reste affiché.`;
    return null;
  }
  if (fallback) fallback.hidden = true;
  status.textContent = IDLE;
  clear.addEventListener("click", () => {
    const current = engine.selection();
    engine.clearSelection();
    if (current) engine.focus(current.nodeId);
  });
  return engine;
}

if (typeof document !== "undefined") {
  document.querySelectorAll("[data-route-graph]").forEach(mountRouteGraph);
}
