// Debug Center — client du Graphic Core (FD-GRAPHICS-008).
// Lit la GraphicScene inerte du flux runtime (étapes renseignées, ordre
// conceptuel, jamais une trace d'exécution), crée une instance du moteur partagé
// et annonce l'étape sélectionnée. Pas de panneau : les sections de la page
// détaillent déjà l'événement. Sans JavaScript ou si la scène est refusée, le SVG
// serveur reste affiché comme repli statique.

import { createGraphicEngine } from "./graphics/engine.js";

const IDLE = "Sélectionnez une étape du flux.";

export function mountDebugFlow(container) {
  const source = container.querySelector("script[data-graphic-scene]");
  const host = container.querySelector("[data-graphic-host]");
  const fallback = container.querySelector("[data-graphic-fallback]");
  const status = container.querySelector("[data-selection-status]");
  if (!source || !host || !status) return null;
  let engine;
  try {
    engine = createGraphicEngine(host, JSON.parse(source.textContent), {
      onSelectionChange(state) {
        const node = state ? engine.node(state.nodeId) : null;
        status.textContent = node ? `Étape sélectionnée : ${node.label}` : IDLE;
      },
    });
  } catch (error) {
    status.textContent = `Vue interactive indisponible (${error.message}) ; le schéma statique reste affiché.`;
    return null;
  }
  if (fallback) fallback.hidden = true;
  status.textContent = IDLE;
  return engine;
}

if (typeof document !== "undefined") {
  document.querySelectorAll("[data-debug-flow]").forEach(mountDebugFlow);
}
