// Graphic Core — viewport 2D, mathématiques pures (FD-GRAPHICS-004).
// Aucun DOM : l'état runtime { scale, x, y } décrit la fenêtre visible, où
// (x, y) est le point monde au coin supérieur gauche et scale le nombre de
// pixels écran par unité monde. Le SVG l'applique par un seul viewBox :
// x y (largeur / scale) (hauteur / scale). La scène n'est jamais modifiée.
// Provenance : zoom autour d'un point adapté (ADAPT) de DrawCiel, SéquenCiel
// 3a1753a2, static/vendor/drawciel/js/app.js, zoomAt (pan' = m − (m − pan)·z'/z),
// réécrit en fonction pure sur { scale, x, y }, sans état global ni DOM.

// Vue d'ensemble d'une scène jusqu'à ~20 000 unités dans une zone de 450 px.
export const MIN_SCALE = 0.02;
export const MAX_SCALE = 4;
// Le fit montre toute la scène sans jamais l'agrandir au-delà de sa taille.
export const FIT_MAX_SCALE = 1;
export const FIT_PADDING = 16;
export const ZOOM_STEP = 1.25;

export class GraphicViewportError extends Error {
  constructor(message) {
    super(message);
    this.name = "GraphicViewportError";
  }
}

function finite(value, what) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new GraphicViewportError(`${what} : nombre fini attendu.`);
  }
  return value;
}

function size(width, height) {
  finite(width, "width");
  finite(height, "height");
  if (width < 0 || height < 0) throw new GraphicViewportError("Taille négative.");
  return Object.freeze({ width, height });
}

export function clampScale(scale) {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, finite(scale, "scale")));
}

function state(scale, x, y) {
  return Object.freeze({ scale: clampScale(scale), x: finite(x, "x"), y: finite(y, "y") });
}

// État neutre : échelle 1, origine. Utilisé tant que la zone n'a pas de taille.
export const NEUTRAL = state(1, 0, 0);

function measurable(area) {
  return area.width > 0 && area.height > 0;
}

// Ajuste toute la scène dans la zone, centrée, avec une marge écran.
export function fitState(bounds, area) {
  if (!measurable(area)) return NEUTRAL;
  const padX = area.width > 2 * FIT_PADDING ? area.width - 2 * FIT_PADDING : area.width;
  const padY = area.height > 2 * FIT_PADDING ? area.height - 2 * FIT_PADDING : area.height;
  const scale = clampScale(Math.min(padX / bounds.width, padY / bounds.height, FIT_MAX_SCALE));
  return state(scale, bounds.width / 2 - area.width / (2 * scale), bounds.height / 2 - area.height / (2 * scale));
}

// Le point monde sous le point écran reste sous ce point après le zoom.
export function zoomAtState(current, point, factor) {
  finite(point.x, "point.x");
  finite(point.y, "point.y");
  if (!(finite(factor, "factor") > 0)) throw new GraphicViewportError("Facteur strictement positif attendu.");
  const scale = clampScale(current.scale * factor);
  const worldX = current.x + point.x / current.scale;
  const worldY = current.y + point.y / current.scale;
  return state(scale, worldX - point.x / scale, worldY - point.y / scale);
}

// Déplacement en pixels écran : le contenu suit le pointeur.
export function panState(current, dx, dy) {
  return state(current.scale, current.x - finite(dx, "dx") / current.scale, current.y - finite(dy, "dy") / current.scale);
}

// Redimensionnement après interaction : échelle et centre visible conservés.
export function resizeState(current, before, after) {
  if (!measurable(before) || !measurable(after)) return current;
  const centerX = current.x + before.width / (2 * current.scale);
  const centerY = current.y + before.height / (2 * current.scale);
  return state(current.scale, centerX - after.width / (2 * current.scale), centerY - after.height / (2 * current.scale));
}

export function viewBox(current, area, bounds) {
  if (!measurable(area)) return Object.freeze({ x: 0, y: 0, width: bounds.width, height: bounds.height });
  return Object.freeze({ x: current.x, y: current.y, width: area.width / current.scale, height: area.height / current.scale });
}

// Facteur de molette normalisé (pixels, lignes ou pages), borné à un pas.
export function wheelFactor(deltaY, deltaMode = 0) {
  const pixels = finite(deltaY, "deltaY") * (deltaMode === 1 ? 33 : deltaMode === 2 ? 800 : 1);
  const steps = Math.max(-1, Math.min(1, -pixels / 100));
  return ZOOM_STEP ** steps;
}

// Viewport d'une instance : état, taille de la zone et politique de resize.
export function createViewport(bounds, initialArea = { width: 0, height: 0 }) {
  const scene = size(bounds.width, bounds.height);
  if (!measurable(scene)) throw new GraphicViewportError("Scène de taille nulle.");
  let area = size(initialArea.width, initialArea.height);
  let current = fitState(scene, area);
  let pristine = true;

  function interact(next) {
    current = next;
    pristine = false;
    return current;
  }

  function fit() {
    current = fitState(scene, area);
    pristine = true;
    return current;
  }

  function center() {
    return { x: area.width / 2, y: area.height / 2 };
  }

  return Object.freeze({
    state: () => current,
    area: () => area,
    pristine: () => pristine,
    viewBox: () => viewBox(current, area, scene),
    fit,
    home: fit,
    zoomAt: (point, factor) => interact(zoomAtState(current, point, factor)),
    zoomIn: () => interact(zoomAtState(current, center(), ZOOM_STEP)),
    zoomOut: () => interact(zoomAtState(current, center(), 1 / ZOOM_STEP)),
    panBy: (dx, dy) => interact(panState(current, dx, dy)),
    // Avant toute interaction le fit suit la zone ; ensuite le centre est conservé.
    setArea(width, height) {
      const next = size(width, height);
      const before = area;
      area = next;
      if (pristine || !measurable(before)) return fit();
      current = resizeState(current, before, area);
      return current;
    },
  });
}
