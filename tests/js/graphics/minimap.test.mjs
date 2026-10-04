// Minicarte : mathématiques pures (dimensions explicites, aucun DOM).
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  HIDE_FROM,
  MINIMAP_MIN_MARKER,
  SHOW_BELOW,
  describeVisible,
  minimapLayout,
  minimapToWorld,
  minimapViewportRect,
  needsMinimap,
  sceneCoverage,
  worldToMinimap,
} from "../../../forge_design/web/static/graphics/minimap.js";
import { centerState, createViewport, visibleWorldRect } from "../../../forge_design/web/static/graphics/viewport.js";

const close = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) <= eps, `${a} ≉ ${b}`);

test("2000 × 1000 dans 200 × 100 sans marge : conversions exactes", () => {
  const layout = minimapLayout({ width: 2000, height: 1000 }, { maxWidth: 200, maxHeight: 100, padding: 0 });
  assert.deepEqual([layout.scale, layout.width, layout.height], [0.1, 200, 100]);
  assert.deepEqual(worldToMinimap(layout, { x: 0, y: 0 }), { x: 0, y: 0 });
  assert.deepEqual(worldToMinimap(layout, { x: 1000, y: 500 }), { x: 100, y: 50 });
  assert.deepEqual(worldToMinimap(layout, { x: 2000, y: 1000 }), { x: 200, y: 100 });
});

test("avec la marge par défaut : calcul exact et proportions conservées", () => {
  const layout = minimapLayout({ width: 2000, height: 1000 });
  assert.equal(layout.padding, 6);
  close(layout.scale, 188 / 2000);
  close(layout.width, 200);
  close(layout.height, 94 + 12);
  const middle = worldToMinimap(layout, { x: 1000, y: 500 });
  close(middle.x, 6 + 94);
  close(middle.y, 6 + 47);
  close((layout.width - 12) / (layout.height - 12), 2);
});

test("minimapToWorld est l'inverse de worldToMinimap", () => {
  const layout = minimapLayout({ width: 2120, height: 1066 });
  for (const point of [{ x: 0, y: 0 }, { x: 2120, y: 1066 }, { x: 123.4, y: 987.6 }, { x: -50, y: 2000 }]) {
    const back = minimapToWorld(layout, worldToMinimap(layout, point));
    close(back.x, point.x, 1e-9);
    close(back.y, point.y, 1e-9);
  }
});

test("scènes très large, très haute, carrée : toujours entières dans 200 × 140", () => {
  const wide = minimapLayout({ width: 10000, height: 100 });
  close(wide.width, 200);
  close(wide.height, 100 * (188 / 10000) + 12);
  const tall = minimapLayout({ width: 100, height: 10000 });
  close(tall.height, 140);
  close(tall.width, 100 * (128 / 10000) + 12);
  const square = minimapLayout({ width: 500, height: 500 });
  close(square.width, 140);
  close(square.height, 140);
  for (const layout of [wide, tall, square]) {
    const end = worldToMinimap(layout, { x: layout.sceneWidth, y: layout.sceneHeight });
    assert.ok(end.x <= layout.width - layout.padding + 1e-9 && end.y <= layout.height - layout.padding + 1e-9);
  }
  // Route réelle et Entity réelle.
  const route = minimapLayout({ width: 2120, height: 1066 });
  close(route.width, 200);
  close(route.height, 1066 * (188 / 2120) + 12);
  const entity = minimapLayout({ width: 780, height: 740 });
  close(entity.height, 140);
  close(entity.width, 780 * (128 / 740) + 12);
});

test("dimensions invalides refusées", () => {
  for (const bad of [Number.NaN, Infinity, -Infinity, 0, -10, "100", null]) {
    assert.throws(() => minimapLayout({ width: bad, height: 100 }), RangeError, String(bad));
    assert.throws(() => minimapLayout({ width: 100, height: bad }), RangeError, String(bad));
    assert.throws(() => minimapLayout({ width: 100, height: 100 }, { maxWidth: bad }), RangeError, String(bad));
  }
  for (const padding of [-1, Number.NaN, 70, 100]) {
    assert.throws(() => minimapLayout({ width: 100, height: 100 }, { padding }), RangeError, String(padding));
  }
  const layout = minimapLayout({ width: 100, height: 100 });
  assert.throws(() => worldToMinimap(layout, { x: Number.NaN, y: 0 }), RangeError);
  assert.throws(() => minimapToWorld(layout, { x: 0, y: Infinity }), RangeError);
});

test("visibleWorldRect : fit, zoom, pan ; null avant mesure", () => {
  const scene = { width: 2000, height: 1000 };
  assert.equal(visibleWorldRect({ scale: 1, x: 0, y: 0 }, { width: 0, height: 0 }), null);
  const viewport = createViewport(scene, { width: 800, height: 480 });
  const fit = viewport.visibleWorldRect();
  assert.ok(fit.x <= 0 && fit.y <= 0 && fit.x + fit.width >= 2000 && fit.y + fit.height >= 1000);
  const { scale } = viewport.state();
  viewport.zoomAt({ x: 400, y: 240 }, 2);
  const zoomed = viewport.visibleWorldRect();
  close(zoomed.width, fit.width / 2);
  close(zoomed.height, fit.height / 2);
  viewport.panBy(100, -40);
  const panned = viewport.visibleWorldRect();
  close(panned.x, zoomed.x - 100 / (2 * scale));
  close(panned.y, zoomed.y + 40 / (2 * scale));
  close(panned.width, zoomed.width);
});

test("centerState : point monde au centre, échelle conservée", () => {
  const area = { width: 800, height: 480 };
  const current = { scale: 0.5, x: 10, y: 20 };
  const next = centerState(current, area, { x: 1000, y: 300 });
  assert.equal(next.scale, 0.5);
  const visible = visibleWorldRect(next, area);
  close(visible.x + visible.width / 2, 1000);
  close(visible.y + visible.height / 2, 300);
  assert.throws(() => centerState(current, area, { x: Number.NaN, y: 0 }));
  const viewport = createViewport({ width: 2000, height: 1000 }, area);
  viewport.zoomIn();
  const before = viewport.state().scale;
  viewport.centerAt({ x: 1500, y: 200 });
  assert.equal(viewport.state().scale, before);
  assert.equal(viewport.pristine(), false);
});

test("couverture et politique d'affichage avec hystérésis", () => {
  const scene = { width: 1000, height: 500 };
  const all = { x: -10, y: -10, width: 1020, height: 520 };
  assert.equal(sceneCoverage(scene, all), 1);
  assert.equal(needsMinimap(scene, all), false);
  assert.equal(needsMinimap(scene, all, true), false);
  const half = { x: 0, y: 0, width: 500, height: 500 };
  assert.equal(sceneCoverage(scene, half), 0.5);
  assert.equal(needsMinimap(scene, half), true);
  // Bande d'hystérésis [0,97 ; 0,995[ : dépend de l'état précédent.
  const band = { x: 0, y: 0, width: 980, height: 500 };
  assert.equal(needsMinimap(scene, band, false), false);
  assert.equal(needsMinimap(scene, band, true), true);
  assert.equal(needsMinimap(scene, { x: 0, y: 0, width: SHOW_BELOW * 1000 - 1, height: 500 }, false), true);
  assert.equal(needsMinimap(scene, { x: 0, y: 0, width: HIDE_FROM * 1000, height: 500 }, true), false);
  // Hors de la scène : couverture nulle ; zone non mesurée : jamais affichée.
  assert.equal(sceneCoverage(scene, { x: 5000, y: 0, width: 100, height: 100 }), 0);
  assert.equal(needsMinimap(scene, null, true), false);
});

test("rectangle de zone visible : intérieur exact, bords bornés, repère minimal hors scène", () => {
  const layout = minimapLayout({ width: 2000, height: 1000 }, { maxWidth: 200, maxHeight: 100, padding: 0 });
  assert.deepEqual(minimapViewportRect(layout, { x: 500, y: 200, width: 800, height: 400 }), { x: 50, y: 20, width: 80, height: 40 });
  // Fit avec marge : borné à la minicarte.
  assert.deepEqual(minimapViewportRect(layout, { x: -100, y: -50, width: 2200, height: 1100 }), { x: 0, y: 0, width: 200, height: 100 });
  // Partiellement hors scène à droite.
  assert.deepEqual(minimapViewportRect(layout, { x: 1800, y: 0, width: 800, height: 400 }), { x: 180, y: 0, width: 20, height: 40 });
  // Entièrement hors scène : repère minimal collé au bord le plus proche du vrai centre.
  const away = minimapViewportRect(layout, { x: 5000, y: 300, width: 400, height: 200 });
  assert.deepEqual(away, { x: 200 - MINIMAP_MIN_MARKER, y: 30, width: MINIMAP_MIN_MARKER, height: 20 });
  // Très petit : au moins le repère minimal, centré.
  const tiny = minimapViewportRect(layout, { x: 1000, y: 500, width: 2, height: 2 });
  assert.deepEqual(tiny, { x: 100.1 - MINIMAP_MIN_MARKER / 2, y: 50.1 - MINIMAP_MIN_MARKER / 2, width: MINIMAP_MIN_MARKER, height: MINIMAP_MIN_MARKER });
});

test("navigation : point de minicarte → centre monde attendu", () => {
  const layout = minimapLayout({ width: 2120, height: 1066 });
  const area = { width: 796, height: 478 };
  const mini = worldToMinimap(layout, { x: 1700, y: 400 });
  const world = minimapToWorld(layout, mini);
  const next = centerState({ scale: 0.7, x: 0, y: 0 }, area, world);
  const visible = visibleWorldRect(next, area);
  close(visible.x + visible.width / 2, 1700);
  close(visible.y + visible.height / 2, 400);
});

test("description textuelle de la zone visible", () => {
  assert.equal(
    describeVisible({ width: 1000, height: 500 }, { x: 250, y: -10, width: 500, height: 600 }),
    "Mini-carte de la scène. Zone visible : de 25 à 75 % de la largeur, de 0 à 100 % de la hauteur.",
  );
});
