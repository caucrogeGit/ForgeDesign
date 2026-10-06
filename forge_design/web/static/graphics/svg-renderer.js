// Graphic Core — renderer SVG remplaçable (FD-GRAPHICS-002).
// Entrée : une scène validée. Éléments créés par createElementNS, texte par
// textContent, attributs fixes ou numériques : aucun balisage injecté, aucun style en
// ligne, aucune référence d'identifiant (pas de marqueur partagé entre instances).

import { DETAIL_LEVELS } from "./detail-level.js";
import { arrowHead, formatPoints } from "./geometry.js";

const SVG = "http://www.w3.org/2000/svg";
const LINE_TOP = 24;
const LINE_STEP = 26;
const LINE_INSET = 12;

function element(document, name, attributes = {}) {
  const node = document.createElementNS(SVG, name);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  return node;
}

function textElement(document, value, attributes) {
  const node = element(document, "text", attributes);
  node.textContent = value;
  return node;
}

function renderEdge(document, edge) {
  const classes = ["gx-edge", `gx-line-${edge.presentation.line}`, `gx-tone-${edge.presentation.tone}`];
  const group = element(document, "g", { class: classes.join(" ") });
  group.append(element(document, "polyline", { class: "gx-edge-path", points: formatPoints(edge.points) }));
  if (edge.presentation.arrow === "end") {
    const head = arrowHead(edge.points);
    if (head) group.append(element(document, "polygon", { class: "gx-edge-arrow", points: formatPoints(head) }));
  }
  if (edge.label !== null && edge.labelAt !== null) {
    group.append(textElement(document, edge.label, { class: "gx-edge-label", x: edge.labelAt.x, y: edge.labelAt.y }));
  }
  return group;
}

function renderNode(document, node) {
  const { x, y, width, height } = node.rect;
  const classes = ["gx-node", `gx-variant-${node.presentation.variant}`, `gx-tone-${node.presentation.tone}`];
  const group = element(document, "g", {
    class: classes.join(" "),
    tabindex: 0,
    role: "button",
    "aria-pressed": "false",
    "aria-label": node.label,
  });
  const title = element(document, "title");
  title.textContent = node.label;
  group.append(title, element(document, "rect", { class: "gx-node-box", x, y, width, height, rx: 6 }));
  // Toutes les lignes sont rendues une fois, à leur place ; leurs classes
  // gx-at-<niveau> disent à quels niveaux elles restent visibles (CSS).
  node.lines.forEach((line, index) => {
    const levels = DETAIL_LEVELS.filter((level) => node.levels[level].includes(index)).map((level) => `gx-at-${level}`);
    group.append(
      textElement(document, line, {
        class: ["gx-node-text", ...levels].join(" "),
        x: x + LINE_INSET,
        y: y + LINE_TOP + index * LINE_STEP,
      }),
    );
  });
  return group;
}

// Rend la scène dans le conteneur et renvoie les éléments indexés par identité.
export function renderScene(container, scene) {
  const document = container.ownerDocument;
  const svg = element(document, "svg", {
    class: "gx-scene",
    // Taille visible fixée par la CSS ; le viewport pilote ensuite le viewBox.
    viewBox: `0 0 ${scene.width} ${scene.height}`,
    role: "group",
    "aria-label": scene.title || "Graphe",
  });
  if (scene.title) {
    const title = element(document, "title");
    title.textContent = scene.title;
    svg.append(title);
  }
  if (scene.description) {
    const description = element(document, "desc");
    description.textContent = scene.description;
    svg.append(description);
  }
  const edgeLayer = element(document, "g", { class: "gx-edges" });
  const nodeLayer = element(document, "g", { class: "gx-nodes" });
  const edges = new Map();
  const nodes = new Map();
  for (const edge of scene.edges) {
    const rendered = renderEdge(document, edge);
    edges.set(edge.id, rendered);
    edgeLayer.append(rendered);
  }
  for (const node of scene.nodes) {
    const rendered = renderNode(document, node);
    nodes.set(node.id, rendered);
    nodeLayer.append(rendered);
  }
  svg.append(edgeLayer, nodeLayer);
  container.append(svg);
  return { svg, nodes, edges };
}

// Applique un état de sélection (ou null) aux éléments rendus.
export function applySelection(view, state) {
  const edgeIds = new Set(state ? state.edgeIds : []);
  const neighbours = new Set(state ? state.neighbourIds : []);
  for (const [id, node] of view.nodes) {
    const selected = state !== null && id === state.nodeId;
    node.classList.toggle("gx-selected", selected);
    node.classList.toggle("gx-related", neighbours.has(id));
    node.setAttribute("aria-pressed", String(selected));
  }
  for (const [id, edge] of view.edges) edge.classList.toggle("gx-related", edgeIds.has(id));
}

// Nœuds déplaçables (FD-GRAPHICS-EDIT-001) : classe et raccourcis annoncés, rien d'autre.
export function applyMovable(view, nodeIds, shortcuts) {
  for (const [id, node] of view.nodes) {
    const movable = nodeIds.has(id);
    node.classList.toggle("gx-movable", movable);
    if (movable) node.setAttribute("aria-keyshortcuts", shortcuts);
    else node.removeAttribute("aria-keyshortcuts");
  }
}

function edgeGeometry(group, edge, points) {
  group.querySelector(".gx-edge-path").setAttribute("points", formatPoints(points));
  if (edge.presentation.arrow !== "end") return;
  const head = arrowHead(points);
  let arrow = group.querySelector(".gx-edge-arrow");
  if (head === null) {
    if (arrow) arrow.remove();
    return;
  }
  if (!arrow) {
    arrow = element(group.ownerDocument, "polygon", { class: "gx-edge-arrow" });
    group.querySelector(".gx-edge-path").after(arrow);
  }
  arrow.setAttribute("points", formatPoints(head));
}

// Aperçu runtime d'un déplacement : le nœud est translaté, les extrémités de ses
// arêtes incidentes suivent (premier point si source, dernier si cible), les points
// intermédiaires restent fixes. O(degré) ; la scène validée n'est jamais modifiée.
// Un delta nul restaure exactement le rendu de la scène.
export function previewNodeMove(view, nodeId, edges, delta) {
  const node = view.nodes.get(nodeId);
  const still = delta.x === 0 && delta.y === 0;
  if (still) node.removeAttribute("transform");
  else node.setAttribute("transform", `translate(${delta.x} ${delta.y})`);
  for (const edge of edges) {
    const points = edge.points.map((point) => ({ x: point.x, y: point.y }));
    const last = points.length - 1;
    if (edge.source === nodeId) points[0] = { x: points[0].x + delta.x, y: points[0].y + delta.y };
    if (edge.target === nodeId) points[last] = { x: points[last].x + delta.x, y: points[last].y + delta.y };
    edgeGeometry(view.edges.get(edge.id), edge, still ? edge.points : points);
  }
}

// Niveau de détail actif : une classe sur le SVG racine (O(1)), la CSS masque les
// lignes absentes du niveau et, en overview, les libellés d'arêtes. Aucun élément
// n'est recréé : identités, sélection et focus sont inchangés.
export function applyDetailLevel(view, level) {
  for (const name of DETAIL_LEVELS) view.svg.classList.toggle(`gx-detail-${name}`, name === level);
  view.svg.setAttribute("data-detail-level", level);
}
