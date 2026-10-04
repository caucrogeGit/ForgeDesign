// Graphic Core — validation d'une GraphicScene (FD-GRAPHICS-002).
// Une scène fournie au moteur est un contenu non fiable : forme stricte,
// clés connues, identités uniques, références d'arêtes résolues, nombres finis.
// Le résultat est une copie normalisée et gelée ; l'entrée n'est jamais conservée.

import { GraphicGeometryError, MAX_COORDINATE, point, rect } from "./geometry.js";

export const MAX_GRAPHIC_NODES = 5000;
export const MAX_GRAPHIC_EDGES = 20000;
// Une identité ou un libellé peut porter un chemin source complet (4096) échappé.
export const MAX_GRAPHIC_ID_CHARS = 8192;
export const MAX_GRAPHIC_LABEL_CHARS = 8192;
export const MAX_GRAPHIC_TEXT_CHARS = 2048;
export const MAX_GRAPHIC_LINES = 4;
export const MAX_GRAPHIC_LINE_CHARS = 256;
export const MAX_GRAPHIC_EDGE_POINTS = 64;
export const MAX_GRAPHIC_DATA_ENTRIES = 16;
export const MAX_GRAPHIC_DATA_CHARS = 512;

// Présentations génériques bornées : le moteur ne reçoit jamais de CSS libre.
export const NODE_VARIANTS = Object.freeze([
  "default",
  "category-1",
  "category-2",
  "category-3",
  "category-4",
  "category-5",
  "category-6",
]);
export const NODE_TONES = Object.freeze(["default", "warning", "muted"]);
export const EDGE_LINES = Object.freeze(["solid", "dashed"]);
export const EDGE_ARROWS = Object.freeze(["none", "end"]);

const DATA_KEY = /^[a-z][a-z0-9-]{0,63}$/;

export class GraphicSceneError extends Error {
  constructor(message, path = "") {
    super(path ? `${path} : ${message}` : message);
    this.name = "GraphicSceneError";
    this.path = path;
  }
}

function fail(path, message) {
  throw new GraphicSceneError(message, path);
}

function isPlainObject(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function object(value, path, required, optional = []) {
  if (!isPlainObject(value)) fail(path, "objet attendu");
  const allowed = new Set([...required, ...optional]);
  for (const key of Object.keys(value)) {
    if (!allowed.has(key)) fail(path, `clé inconnue « ${key} »`);
  }
  for (const key of required) {
    if (!Object.prototype.hasOwnProperty.call(value, key)) fail(path, `clé « ${key} » manquante`);
  }
  return value;
}

function text(value, path, max, { allowEmpty = false } = {}) {
  if (typeof value !== "string") fail(path, "chaîne attendue");
  if (!allowEmpty && value.length === 0) fail(path, "chaîne vide");
  if (value.length > max) fail(path, `au plus ${max} caractères`);
  return value;
}

function list(value, path, max) {
  if (!Array.isArray(value)) fail(path, "tableau attendu");
  if (value.length > max) fail(path, `au plus ${max} éléments`);
  return value;
}

function oneOf(value, path, allowed) {
  if (typeof value !== "string" || !allowed.includes(value)) {
    fail(path, `valeur attendue parmi ${allowed.join(", ")}`);
  }
  return value;
}

function geometry(build, path) {
  try {
    return build();
  } catch (error) {
    if (error instanceof GraphicGeometryError) fail(path, error.message);
    throw error;
  }
}

function pointOf(value, path) {
  object(value, path, ["x", "y"]);
  return geometry(() => point(value.x, value.y), path);
}

function rectOf(value, path) {
  object(value, path, ["x", "y", "width", "height"]);
  return geometry(() => rect(value.x, value.y, value.width, value.height), path);
}

function dataOf(value, path) {
  if (value === undefined) return Object.freeze(Object.create(null));
  object(value, path, [], Object.keys(isPlainObject(value) ? value : {}));
  const keys = Object.keys(value);
  if (keys.length > MAX_GRAPHIC_DATA_ENTRIES) fail(path, `au plus ${MAX_GRAPHIC_DATA_ENTRIES} entrées`);
  const result = Object.create(null);
  for (const key of keys) {
    if (!DATA_KEY.test(key)) fail(path, `clé de données invalide « ${key} »`);
    result[key] = text(value[key], `${path}.${key}`, MAX_GRAPHIC_DATA_CHARS, { allowEmpty: true });
  }
  return Object.freeze(result);
}

// Lignes visibles par niveau (FD-GRAPHICS-006) : indices dans `lines`, sans texte
// dupliqué. `detail` montre toujours toutes les lignes ; `overview` ⊆ `normal`.
// Sans `levels`, toutes les lignes restent visibles à tous les niveaux.
function levelsOf(value, path, count) {
  const all = Object.freeze([...Array(count).keys()]);
  if (value === undefined) return Object.freeze({ overview: all, normal: all, detail: all });
  object(value, path, ["overview", "normal"]);
  const indices = (name) =>
    list(value[name], `${path}.${name}`, MAX_GRAPHIC_LINES).map((item, position, items) => {
      if (!Number.isInteger(item) || item < 0 || item >= count) fail(`${path}.${name}[${position}]`, "indice de ligne inexistant");
      if (position > 0 && item <= items[position - 1]) fail(`${path}.${name}[${position}]`, "indices strictement croissants attendus");
      return item;
    });
  const overview = indices("overview");
  const normal = indices("normal");
  if (overview.some((item) => !normal.includes(item))) fail(`${path}.overview`, "toute ligne de overview doit figurer dans normal");
  return Object.freeze({ overview: Object.freeze(overview), normal: Object.freeze(normal), detail: all });
}

function nodeOf(value, path) {
  object(value, path, ["id", "label", "rect"], ["kind", "lines", "levels", "presentation", "data"]);
  const presentation = value.presentation ?? {};
  object(presentation, `${path}.presentation`, [], ["variant", "tone"]);
  const lines = list(value.lines ?? [], `${path}.lines`, MAX_GRAPHIC_LINES).map((line, index) =>
    text(line, `${path}.lines[${index}]`, MAX_GRAPHIC_LINE_CHARS, { allowEmpty: true }),
  );
  return Object.freeze({
    id: text(value.id, `${path}.id`, MAX_GRAPHIC_ID_CHARS),
    kind: oneOf(value.kind ?? "node", `${path}.kind`, ["node"]),
    label: text(value.label, `${path}.label`, MAX_GRAPHIC_LABEL_CHARS),
    rect: rectOf(value.rect, `${path}.rect`),
    lines: Object.freeze(lines),
    levels: levelsOf(value.levels, `${path}.levels`, lines.length),
    presentation: Object.freeze({
      variant: oneOf(presentation.variant ?? "default", `${path}.presentation.variant`, NODE_VARIANTS),
      tone: oneOf(presentation.tone ?? "default", `${path}.presentation.tone`, NODE_TONES),
    }),
    data: dataOf(value.data, `${path}.data`),
  });
}

function edgeOf(value, path, nodes) {
  object(value, path, ["id", "source", "target", "points"], ["label", "labelAt", "presentation", "data"]);
  const source = text(value.source, `${path}.source`, MAX_GRAPHIC_ID_CHARS);
  const target = text(value.target, `${path}.target`, MAX_GRAPHIC_ID_CHARS);
  if (!nodes.has(source)) fail(`${path}.source`, "nœud inexistant");
  if (!nodes.has(target)) fail(`${path}.target`, "nœud inexistant");
  const points = list(value.points, `${path}.points`, MAX_GRAPHIC_EDGE_POINTS);
  if (points.length < 2) fail(`${path}.points`, "au moins deux points");
  const presentation = value.presentation ?? {};
  object(presentation, `${path}.presentation`, [], ["line", "arrow", "tone"]);
  return Object.freeze({
    id: text(value.id, `${path}.id`, MAX_GRAPHIC_ID_CHARS),
    source,
    target,
    label: value.label === undefined ? null : text(value.label, `${path}.label`, MAX_GRAPHIC_TEXT_CHARS),
    labelAt: value.labelAt === undefined ? null : pointOf(value.labelAt, `${path}.labelAt`),
    points: Object.freeze(points.map((item, index) => pointOf(item, `${path}.points[${index}]`))),
    presentation: Object.freeze({
      line: oneOf(presentation.line ?? "solid", `${path}.presentation.line`, EDGE_LINES),
      arrow: oneOf(presentation.arrow ?? "none", `${path}.presentation.arrow`, EDGE_ARROWS),
      tone: oneOf(presentation.tone ?? "default", `${path}.presentation.tone`, NODE_TONES),
    }),
    data: dataOf(value.data, `${path}.data`),
  });
}

function dimension(value, path) {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0 || value > MAX_COORDINATE) {
    fail(path, `nombre fini dans ]0, ${MAX_COORDINATE}] attendu`);
  }
  return value;
}

// Valide une scène et renvoie une copie gelée ; lève GraphicSceneError sinon.
export function validateScene(input) {
  object(input, "scene", ["width", "height", "nodes", "edges"], ["title", "description"]);
  const nodes = new Map();
  for (const [index, raw] of list(input.nodes, "nodes", MAX_GRAPHIC_NODES).entries()) {
    const node = nodeOf(raw, `nodes[${index}]`);
    if (nodes.has(node.id)) fail(`nodes[${index}].id`, "identité dupliquée");
    nodes.set(node.id, node);
  }
  const edges = new Map();
  for (const [index, raw] of list(input.edges, "edges", MAX_GRAPHIC_EDGES).entries()) {
    const edge = edgeOf(raw, `edges[${index}]`, nodes);
    if (edges.has(edge.id)) fail(`edges[${index}].id`, "identité dupliquée");
    edges.set(edge.id, edge);
  }
  return Object.freeze({
    width: dimension(input.width, "width"),
    height: dimension(input.height, "height"),
    title: input.title === undefined ? "" : text(input.title, "title", MAX_GRAPHIC_TEXT_CHARS, { allowEmpty: true }),
    description:
      input.description === undefined
        ? ""
        : text(input.description, "description", MAX_GRAPHIC_TEXT_CHARS, { allowEmpty: true }),
    nodes: Object.freeze([...nodes.values()]),
    edges: Object.freeze([...edges.values()]),
  });
}
