// Graphic Core — minicarte : projection runtime simplifiée de la scène (FD-GRAPHICS-007).
// Mathématiques pures (dimensions explicites, aucun DOM) et vue SVG à DOM constant :
// un chemin pour toutes les arêtes, un chemin par variante de nœuds, un rectangle de
// zone visible. Aucun texte, aucune topologie propre, aucun état global.
// Provenance : idée de la minicarte de DrawCiel (SéquenCiel 88f95b75,
// static/vendor/drawciel/js/app.js, renderMinimap / minimapNavigate) : ajustement
// uniforme centré et conversion mini → monde (x = b.x + (px − ox) / s), réécrits en
// fonctions pures liées à une instance ; bornes fixes (la scène), pas de canvas.

export const MINIMAP_MAX_WIDTH = 200;
export const MINIMAP_MAX_HEIGHT = 140;
export const MINIMAP_PADDING = 6;
// Taille minimale du repère de zone visible, en pixels de minicarte.
export const MINIMAP_MIN_MARKER = 4;
// Politique d'affichage : couverture = min(part visible de la largeur, de la hauteur).
// Apparaît sous 0,97 ; disparaît à partir de 0,995 (hystérésis contre le clignotement).
export const SHOW_BELOW = 0.97;
export const HIDE_FROM = 0.995;

const SVG = "http://www.w3.org/2000/svg";

function positive(value, what) {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    throw new RangeError(`${what} : nombre fini strictement positif attendu.`);
  }
  return value;
}

function finite(value, what) {
  if (typeof value !== "number" || !Number.isFinite(value)) throw new RangeError(`${what} : nombre fini attendu.`);
  return value;
}

// Ajustement uniforme de la scène dans au plus maxWidth × maxHeight, marge comprise ;
// la minicarte prend exactement les proportions de la scène.
export function minimapLayout(bounds, { maxWidth = MINIMAP_MAX_WIDTH, maxHeight = MINIMAP_MAX_HEIGHT, padding = MINIMAP_PADDING } = {}) {
  const width = positive(bounds.width, "scene.width");
  const height = positive(bounds.height, "scene.height");
  positive(maxWidth, "maxWidth");
  positive(maxHeight, "maxHeight");
  if (typeof padding !== "number" || !Number.isFinite(padding) || padding < 0 || 2 * padding >= Math.min(maxWidth, maxHeight)) {
    throw new RangeError("padding invalide.");
  }
  const scale = Math.min((maxWidth - 2 * padding) / width, (maxHeight - 2 * padding) / height);
  return Object.freeze({
    scale,
    padding,
    sceneWidth: width,
    sceneHeight: height,
    width: width * scale + 2 * padding,
    height: height * scale + 2 * padding,
  });
}

export function worldToMinimap(layout, point) {
  return Object.freeze({
    x: layout.padding + finite(point.x, "point.x") * layout.scale,
    y: layout.padding + finite(point.y, "point.y") * layout.scale,
  });
}

export function minimapToWorld(layout, point) {
  return Object.freeze({
    x: (finite(point.x, "point.x") - layout.padding) / layout.scale,
    y: (finite(point.y, "point.y") - layout.padding) / layout.scale,
  });
}

// Part de la scène visible (0 à 1) : minimum des parts horizontale et verticale.
export function sceneCoverage(bounds, visible) {
  const share = (start, size, total) => Math.max(0, Math.min(start + size, total) - Math.max(start, 0)) / total;
  return Math.min(share(visible.x, visible.width, bounds.width), share(visible.y, visible.height, bounds.height));
}

// Faut-il montrer la minicarte ? Dépend de la seule géométrie visible, jamais du niveau de détail.
export function needsMinimap(bounds, visible, previous = null) {
  if (visible === null) return false;
  const coverage = sceneCoverage(bounds, visible);
  return previous === true ? coverage < HIDE_FROM : coverage < SHOW_BELOW;
}

// Rectangle de zone visible en pixels de minicarte : la partie visible bornée à la
// minicarte (marge comprise) ; si la vue sort de la scène, un repère minimal au bord,
// centré sur la projection bornée du vrai centre, indique la direction.
export function minimapViewportRect(layout, visible) {
  const a = worldToMinimap(layout, { x: visible.x, y: visible.y });
  const b = worldToMinimap(layout, { x: visible.x + visible.width, y: visible.y + visible.height });
  const clamp = (value, max) => Math.min(max, Math.max(0, value));
  const axis = (low, high, max) => {
    let start = clamp(low, max);
    let end = clamp(high, max);
    if (end - start < MINIMAP_MIN_MARKER) {
      const center = clamp((low + high) / 2, max);
      start = clamp(center - MINIMAP_MIN_MARKER / 2, max - MINIMAP_MIN_MARKER);
      end = start + MINIMAP_MIN_MARKER;
    }
    return [start, end];
  };
  const [x1, x2] = axis(a.x, b.x, layout.width);
  const [y1, y2] = axis(a.y, b.y, layout.height);
  return Object.freeze({ x: x1, y: y1, width: x2 - x1, height: y2 - y1 });
}

// Description textuelle de la zone visible (nom accessible de la minicarte).
export function describeVisible(bounds, visible) {
  const percent = (value, total) => Math.round((Math.min(total, Math.max(0, value)) / total) * 100);
  const x1 = percent(visible.x, bounds.width);
  const x2 = percent(visible.x + visible.width, bounds.width);
  const y1 = percent(visible.y, bounds.height);
  const y2 = percent(visible.y + visible.height, bounds.height);
  return `Mini-carte de la scène. Zone visible : de ${x1} à ${x2} % de la largeur, de ${y1} à ${y2} % de la hauteur.`;
}

const round = (value) => Math.round(value * 10) / 10;

function element(document, name, attributes = {}) {
  const node = document.createElementNS(SVG, name);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  return node;
}

// Vue de la minicarte : structure rendue une fois (O(V + E), DOM constant), puis
// seule la zone visible est mise à jour (O(1)).
export function renderMinimap(container, scene, layout) {
  const document = container.ownerDocument;
  const frame = document.createElement("div");
  for (const [key, value] of Object.entries({ class: "gx-minimap", tabindex: 0, role: "group", "aria-label": "Mini-carte de la scène" })) {
    frame.setAttribute(key, String(value));
  }
  frame.hidden = true;
  const svg = element(document, "svg", {
    class: "gx-minimap-svg",
    viewBox: `0 0 ${round(layout.width)} ${round(layout.height)}`,
    width: round(layout.width),
    height: round(layout.height),
    "aria-hidden": "true",
    focusable: "false",
  });
  const toMini = (point) => worldToMinimap(layout, point);
  const origin = toMini({ x: 0, y: 0 });
  svg.append(
    element(document, "rect", {
      class: "gx-minimap-scene",
      x: round(origin.x),
      y: round(origin.y),
      width: round(layout.sceneWidth * layout.scale),
      height: round(layout.sceneHeight * layout.scale),
    }),
  );
  // Polylignes sans flèche : à cette taille, une flèche n'ajoute que du bruit.
  const edgePath = scene.edges
    .map((edge) =>
      edge.points
        .map(toMini)
        .map((p, index) => `${index === 0 ? "M" : "L"} ${round(p.x)} ${round(p.y)}`)
        .join(" "),
    )
    .join(" ");
  svg.append(element(document, "path", { class: "gx-minimap-edges", d: edgePath }));
  const byVariant = new Map();
  for (const node of scene.nodes) {
    const { x, y } = toMini(node.rect);
    const rectangle = `M ${round(x)} ${round(y)} h ${round(node.rect.width * layout.scale)} v ${round(node.rect.height * layout.scale)} h ${round(-node.rect.width * layout.scale)} Z`;
    const list = byVariant.get(node.presentation.variant) ?? [];
    list.push(rectangle);
    byVariant.set(node.presentation.variant, list);
  }
  for (const [variant, rectangles] of byVariant) {
    svg.append(element(document, "path", { class: `gx-minimap-nodes gx-variant-${variant}`, d: rectangles.join(" ") }));
  }
  const viewportRect = element(document, "rect", { class: "gx-minimap-viewport", x: 0, y: 0, width: 0, height: 0 });
  svg.append(viewportRect);
  frame.append(svg);
  container.prepend(frame);
  return {
    element: frame,
    svg,
    layout,
    // Point client → point de minicarte, en tenant compte d'une mise à l'échelle CSS.
    toMinimap(clientX, clientY) {
      const box = svg.getBoundingClientRect();
      const sx = box.width > 0 ? layout.width / box.width : 1;
      const sy = box.height > 0 ? layout.height / box.height : 1;
      return { x: (clientX - box.left) * sx, y: (clientY - box.top) * sy };
    },
    update(rect, label) {
      viewportRect.setAttribute("x", round(rect.x));
      viewportRect.setAttribute("y", round(rect.y));
      viewportRect.setAttribute("width", round(rect.width));
      viewportRect.setAttribute("height", round(rect.height));
      frame.setAttribute("aria-label", label);
    },
    setVisible(visible) {
      frame.hidden = !visible;
    },
  };
}
