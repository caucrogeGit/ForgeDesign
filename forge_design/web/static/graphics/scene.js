// Graphic Core — index d'incidence et sélection, sans DOM (FD-GRAPHICS-002).
// Incidence directe seulement : aucune analyse transitive.

import { GraphicSceneError } from "./model.js";

// Index construit en O(V + E) ; voisins d'un nœud en O(degré).
export function indexScene(scene) {
  const nodes = new Map();
  const incident = new Map();
  for (const node of scene.nodes) {
    nodes.set(node.id, node);
    incident.set(node.id, []);
  }
  const edges = new Map();
  for (const edge of scene.edges) {
    edges.set(edge.id, edge);
    incident.get(edge.source).push(edge);
    if (edge.target !== edge.source) incident.get(edge.target).push(edge);
  }
  return Object.freeze({ nodes, edges, incident });
}

export function neighbourhood(index, nodeId) {
  const edges = index.incident.get(nodeId);
  if (edges === undefined) throw new GraphicSceneError("nœud inconnu", "selection");
  const neighbours = new Set();
  for (const edge of edges) {
    if (edge.source !== nodeId) neighbours.add(edge.source);
    if (edge.target !== nodeId) neighbours.add(edge.target);
  }
  return Object.freeze({
    nodeId,
    edgeIds: Object.freeze(edges.map((edge) => edge.id)),
    neighbourIds: Object.freeze([...neighbours]),
  });
}

// Sélection simple, runtime seulement. Une identité inconnue est refusée et
// laisse l'état inchangé.
export function createSelection(index) {
  let current = null;
  return Object.freeze({
    select(nodeId) {
      current = neighbourhood(index, nodeId);
      return current;
    },
    clear() {
      current = null;
      return current;
    },
    current() {
      return current;
    },
  });
}
