// Entity Explorer — client du Graphic Core (FD-GRAPHICS-003).
// Lit la GraphicScene inerte fournie par le serveur, crée une instance du moteur
// partagé et remplit le panneau propre à Entity Explorer à partir des données
// opaques des nœuds et des arêtes. Sans JavaScript ou si la scène est refusée,
// le SVG serveur reste affiché comme repli statique.

import { createGraphicEngine } from "./graphics/engine.js";

const IDLE = "Sélectionnez une entité ou un pivot dans le graphe.";

export function mountEntityGraph(container) {
  const source = container.querySelector("script[data-graphic-scene]");
  const host = container.querySelector("[data-graphic-host]");
  const fallback = container.querySelector("[data-graphic-fallback]");
  const status = container.querySelector("[data-selection-status]");
  const details = container.querySelector("[data-selection-details]");
  const kind = container.querySelector("[data-selection-kind]");
  const label = container.querySelector("[data-selection-label]");
  const table = container.querySelector("[data-selection-table]");
  const count = container.querySelector("[data-selection-field-count]");
  const countLabel = container.querySelector("[data-selection-field-label]");
  const relationCount = container.querySelector("[data-selection-relation-count]");
  const relations = container.querySelector("[data-selection-relations]");
  const clear = container.querySelector("[data-selection-clear]");
  const fields = [source, host, status, details, kind, label, table, count, countLabel, relationCount, relations, clear];
  if (fields.some((field) => !field)) return null;
  let engine;

  function describe(edgeId) {
    const edge = engine.edge(edgeId);
    const from = engine.node(edge.source);
    const to = engine.node(edge.target);
    const item = container.ownerDocument.createElement("li");
    item.textContent = `${from.data.name} → ${edge.data.name || edge.data.kind} → ${to.data.name}`;
    return item;
  }

  function show(state) {
    const node = state ? engine.node(state.nodeId) : null;
    details.hidden = node === null;
    clear.hidden = node === null;
    relations.hidden = node === null;
    relations.textContent = "";
    kind.textContent = node ? node.data["kind-label"] ?? "—" : "";
    label.textContent = node ? node.data.name ?? node.label : "";
    table.textContent = node ? node.data.table ?? "" : "";
    count.textContent = node ? node.data["field-count"] ?? "0" : "";
    countLabel.textContent = node ? node.data["field-label"] ?? "Champs" : "Champs";
    relationCount.textContent = node ? String(state.edgeIds.length) : "";
    if (node) relations.append(...state.edgeIds.map(describe));
    status.textContent = node ? `Élément sélectionné : ${node.data.name ?? node.label}` : IDLE;
  }

  try {
    engine = createGraphicEngine(host, JSON.parse(source.textContent), { onSelectionChange: show });
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
  document.querySelectorAll("[data-entity-graph]").forEach(mountEntityGraph);
}
