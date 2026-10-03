// Viewport : mathématiques pures, sans DOM.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  FIT_MAX_SCALE,
  FIT_PADDING,
  GraphicViewportError,
  MAX_SCALE,
  MIN_SCALE,
  NEUTRAL,
  ZOOM_STEP,
  createViewport,
  fitState,
  panState,
  resizeState,
  viewBox,
  wheelFactor,
  zoomAtState,
} from "../../../forge_design/web/static/graphics/viewport.js";

const EPSILON = 1e-9;

function near(actual, expected, epsilon = EPSILON) {
  assert.ok(Math.abs(actual - expected) <= epsilon * Math.max(1, Math.abs(expected)), `${actual} ≉ ${expected}`);
}

// Point écran → monde selon l'état.
function world(state, point) {
  return { x: state.x + point.x / state.scale, y: state.y + point.y / state.scale };
}

function visible(state, area) {
  const box = viewBox(state, area, { width: 1, height: 1 });
  return { x1: box.x, y1: box.y, x2: box.x + box.width, y2: box.y + box.height };
}

test("fit : scène large dans une zone carrée, centrée, marge respectée", () => {
  const area = { width: 500, height: 500 };
  const state = fitState({ width: 1000, height: 500 }, area);
  near(state.scale, (500 - 2 * FIT_PADDING) / 1000);
  const box = visible(state, area);
  near((box.x1 + box.x2) / 2, 500);
  near((box.y1 + box.y2) / 2, 250);
  // Toute la scène est visible, avec la marge écran de chaque côté.
  near(-box.x1 * state.scale, FIT_PADDING);
  assert.ok(box.x2 >= 1000 && box.y1 <= 0 && box.y2 >= 500);
});

test("fit : très large, très haute, carrée, petite", () => {
  const area = { width: 800, height: 480 };
  const cases = [
    [{ width: 20000, height: 100 }, (800 - 2 * FIT_PADDING) / 20000],
    [{ width: 100, height: 9000 }, (480 - 2 * FIT_PADDING) / 9000],
    [{ width: 400, height: 400 }, FIT_MAX_SCALE],
    [{ width: 2120, height: 1306 }, (480 - 2 * FIT_PADDING) / 1306],
    [{ width: 10, height: 10 }, FIT_MAX_SCALE],
  ];
  for (const [bounds, scale] of cases) {
    const state = fitState(bounds, area);
    near(state.scale, scale);
    const box = visible(state, area);
    assert.ok(box.x1 <= 0 && box.y1 <= 0 && box.x2 >= bounds.width && box.y2 >= bounds.height, JSON.stringify(bounds));
  }
});

test("fit : bornes, déterminisme, zone nulle ou étroite", () => {
  near(fitState({ width: 1e6, height: 1e6 }, { width: 800, height: 480 }).scale, MIN_SCALE);
  assert.ok(fitState({ width: 1, height: 1 }, { width: 800, height: 480 }).scale <= FIT_MAX_SCALE);
  const area = { width: 640, height: 360 };
  assert.deepEqual(fitState({ width: 900, height: 700 }, area), fitState({ width: 900, height: 700 }, area));
  for (const empty of [{ width: 0, height: 300 }, { width: 300, height: 0 }, { width: 0, height: 0 }]) {
    assert.equal(fitState({ width: 900, height: 700 }, empty), NEUTRAL);
  }
  const tiny = fitState({ width: 100, height: 100 }, { width: 20, height: 20 });
  assert.ok(Number.isFinite(tiny.scale) && tiny.scale > 0);
  assert.deepEqual(viewBox(NEUTRAL, { width: 0, height: 0 }, { width: 900, height: 700 }), { x: 0, y: 0, width: 900, height: 700 });
});

test("zoom autour d'un point : le point monde reste sous le point écran", () => {
  const start = fitState({ width: 2120, height: 1306 }, { width: 800, height: 480 });
  for (const point of [{ x: 0, y: 0 }, { x: 400, y: 240 }, { x: 799, y: 13 }, { x: 37.5, y: 470.25 }]) {
    for (const factor of [ZOOM_STEP, 1 / ZOOM_STEP, 3, 0.2]) {
      const after = zoomAtState(start, point, factor);
      const before = world(start, point);
      const now = world(after, point);
      near(now.x, before.x);
      near(now.y, before.y);
    }
  }
});

test("zoom : bornes MIN_SCALE / MAX_SCALE, même sous le pointeur", () => {
  let state = NEUTRAL;
  for (let i = 0; i < 100; i += 1) state = zoomAtState(state, { x: 10, y: 10 }, ZOOM_STEP);
  assert.equal(state.scale, MAX_SCALE);
  for (let i = 0; i < 200; i += 1) state = zoomAtState(state, { x: 10, y: 10 }, 1 / ZOOM_STEP);
  assert.equal(state.scale, MIN_SCALE);
  const atLimit = zoomAtState(state, { x: 300, y: 300 }, 1 / ZOOM_STEP);
  near(world(atLimit, { x: 300, y: 300 }).x, world(state, { x: 300, y: 300 }).x);
});

test("pan : translation exacte en pixels écran", () => {
  const state = { scale: 0.5, x: 100, y: 50 };
  const moved = panState(state, 30, -20);
  assert.deepEqual(moved, { scale: 0.5, x: 40, y: 90 });
  // Le contenu suit le pointeur : le point monde sous (0,0) passe en (30,-20).
  near(world(moved, { x: 30, y: -20 }).x, world(state, { x: 0, y: 0 }).x);
});

test("resize : centre et échelle conservés après interaction", () => {
  const before = { width: 800, height: 480 };
  const after = { width: 600, height: 300 };
  const state = { scale: 0.8, x: 120, y: 40 };
  const next = resizeState(state, before, after);
  assert.equal(next.scale, 0.8);
  near(next.x + after.width / (2 * 0.8), state.x + before.width / (2 * 0.8));
  near(next.y + after.height / (2 * 0.8), state.y + before.height / (2 * 0.8));
  assert.equal(resizeState(state, { width: 0, height: 0 }, after), state);
});

test("viewport d'instance : home = fit, politique de resize", () => {
  const bounds = { width: 2120, height: 1306 };
  const viewport = createViewport(bounds, { width: 0, height: 0 });
  assert.equal(viewport.state(), NEUTRAL);
  viewport.setArea(800, 480);
  assert.deepEqual(viewport.state(), fitState(bounds, { width: 800, height: 480 }));
  // Avant interaction, le fit suit la zone.
  viewport.setArea(600, 600);
  assert.deepEqual(viewport.state(), fitState(bounds, { width: 600, height: 600 }));
  assert.equal(viewport.pristine(), true);
  viewport.zoomIn();
  assert.equal(viewport.pristine(), false);
  const zoomed = viewport.state();
  near(zoomed.scale, fitState(bounds, { width: 600, height: 600 }).scale * ZOOM_STEP);
  // Après interaction, l'échelle est conservée.
  viewport.setArea(900, 400);
  assert.equal(viewport.state().scale, zoomed.scale);
  assert.deepEqual(viewport.home(), fitState(bounds, { width: 900, height: 400 }));
  assert.equal(viewport.pristine(), true);
  viewport.zoomOut();
  near(viewport.state().scale, fitState(bounds, { width: 900, height: 400 }).scale / ZOOM_STEP);
});

test("valeurs invalides refusées sans état corrompu", () => {
  const viewport = createViewport({ width: 100, height: 100 }, { width: 400, height: 300 });
  const before = viewport.state();
  for (const [width, height] of [[NaN, 10], [10, Infinity], [-1, 10], [10, "1"]]) {
    assert.throws(() => viewport.setArea(width, height), GraphicViewportError);
  }
  assert.throws(() => viewport.zoomAt({ x: NaN, y: 0 }, 2), GraphicViewportError);
  assert.throws(() => viewport.zoomAt({ x: 0, y: 0 }, 0), GraphicViewportError);
  assert.throws(() => viewport.zoomAt({ x: 0, y: 0 }, -2), GraphicViewportError);
  assert.throws(() => viewport.panBy(Infinity, 0), GraphicViewportError);
  assert.deepEqual(viewport.state(), before);
  assert.throws(() => createViewport({ width: 0, height: 10 }), GraphicViewportError);
  assert.ok(Object.isFrozen(viewport) && Object.isFrozen(before));
});

test("molette : facteur normalisé et borné à un pas", () => {
  near(wheelFactor(-100), ZOOM_STEP);
  near(wheelFactor(100), 1 / ZOOM_STEP);
  near(wheelFactor(-1000), ZOOM_STEP);
  near(wheelFactor(-3, 1), ZOOM_STEP ** 0.99);
  near(wheelFactor(1, 2), 1 / ZOOM_STEP);
  near(wheelFactor(0), 1);
  near(wheelFactor(-10) * wheelFactor(10), 1);
});

test("1000 opérations : état fini, borné, sans dérive notable", () => {
  const viewport = createViewport({ width: 2120, height: 1306 }, { width: 800, height: 480 });
  const start = viewport.state();
  let seed = 7;
  const random = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);
  for (let i = 0; i < 500; i += 1) {
    const point = { x: random() * 800, y: random() * 480 };
    viewport.zoomAt(point, ZOOM_STEP);
    viewport.zoomAt(point, 1 / ZOOM_STEP);
  }
  const end = viewport.state();
  for (const value of [end.scale, end.x, end.y]) assert.ok(Number.isFinite(value));
  near(end.scale, start.scale, 1e-9);
  near(end.x, start.x, 1e-7);
  near(end.y, start.y, 1e-7);
  for (let i = 0; i < 1000; i += 1) {
    viewport.zoomAt({ x: random() * 800, y: random() * 480 }, random() < 0.5 ? ZOOM_STEP : 1 / ZOOM_STEP);
    viewport.panBy(random() * 40 - 20, random() * 40 - 20);
    const state = viewport.state();
    assert.ok(state.scale >= MIN_SCALE && state.scale <= MAX_SCALE && Number.isFinite(state.x) && Number.isFinite(state.y));
  }
});
