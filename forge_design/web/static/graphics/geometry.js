// Graphic Core — primitives géométriques pures (FD-GRAPHICS-002).
// Aucune dépendance au DOM ni à un domaine.

export const MAX_COORDINATE = 1000000;

export class GraphicGeometryError extends Error {
  constructor(message) {
    super(message);
    this.name = "GraphicGeometryError";
  }
}

export function isFiniteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function coordinate(value, what) {
  if (!isFiniteNumber(value) || Math.abs(value) > MAX_COORDINATE) {
    throw new GraphicGeometryError(`${what} : nombre fini attendu dans ±${MAX_COORDINATE}.`);
  }
  return value;
}

export function point(x, y) {
  return Object.freeze({ x: coordinate(x, "x"), y: coordinate(y, "y") });
}

export function rect(x, y, width, height) {
  coordinate(width, "width");
  coordinate(height, "height");
  if (width <= 0 || height <= 0) {
    throw new GraphicGeometryError("Dimensions strictement positives attendues.");
  }
  return Object.freeze({ x: coordinate(x, "x"), y: coordinate(y, "y"), width, height });
}

export function rectCenter(box) {
  return point(box.x + box.width / 2, box.y + box.height / 2);
}

// Pointe de flèche triangulaire au bout du dernier segment non nul ; null sinon.
export function arrowHead(points, size = 8) {
  for (let index = points.length - 1; index > 0; index -= 1) {
    const tip = points[index];
    const from = points[index - 1];
    const dx = tip.x - from.x;
    const dy = tip.y - from.y;
    const length = Math.hypot(dx, dy);
    if (length > 0) {
      const ux = dx / length;
      const uy = dy / length;
      const bx = tip.x - ux * size;
      const by = tip.y - uy * size;
      const half = size / 2;
      return [
        Object.freeze({ x: tip.x, y: tip.y }),
        Object.freeze({ x: bx - uy * half, y: by + ux * half }),
        Object.freeze({ x: bx + uy * half, y: by - ux * half }),
      ];
    }
  }
  return null;
}

export function formatPoints(points) {
  return points.map((p) => `${p.x},${p.y}`).join(" ");
}
