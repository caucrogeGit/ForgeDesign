// Ressource d'un module spécialisé — client générique du Graphic Core (FD-MODULES-002).
// Lit la GraphicScene inerte projetée par le module, crée une instance du moteur
// partagé et annonce l'élément sélectionné. Aucun vocabulaire de module : la scène
// est validée par validateScene comme n'importe quel contenu non fiable. Sans
// JavaScript ou si la scène est refusée, seul le message de repli reste affiché.

import { createGraphicEngine } from "./graphics/engine.js";

const IDLE = "Sélectionnez un élément du graphe.";

export function mountModuleResource(container) {
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
        status.textContent = node ? `Élément sélectionné : ${node.label}` : IDLE;
      },
    });
  } catch (error) {
    status.textContent = `Vue interactive indisponible (${error.message}).`;
    return null;
  }
  if (fallback) fallback.hidden = true;
  status.textContent = IDLE;
  return engine;
}

if (typeof document !== "undefined") {
  document.querySelectorAll("[data-module-graph]").forEach(mountModuleResource);
}
