// Viewport intégré au moteur : barre d'outils, molette, pan, resize, isolation.
import assert from "node:assert/strict";
import { test } from "node:test";

import { createGraphicEngine } from "../../../forge_design/web/static/graphics/engine.js";
import { ZOOM_STEP, fitState } from "../../../forge_design/web/static/graphics/viewport.js";
import { container, rendered, sized } from "./fake-dom.mjs";
import { witness } from "./scenes.mjs";

// Scène plus grande que la zone : 2120 × 1306, comme Route Explorer.
function large() {
  const scene = witness();
  scene.width = 2120;
  scene.height = 1306;
  return scene;
}

function setup(scene = large(), width = 800, height = 480, options = {}) {
  const host = container();
  const engine = createGraphicEngine(host, scene, options);
  sized(host, engine, width, height);
  const area = host.querySelector(".gx-viewport");
  return { host, engine, area, svg: rendered(host).svg };
}

function viewBoxOf(svg) {
  return svg.getAttribute("viewBox").split(" ").map(Number);
}

function buttons(host) {
  return host.querySelectorAll("button");
}

test("barre d'outils générique et accessible", () => {
  const { host } = setup();
  const toolbar = host.querySelector(".gx-toolbar");
  assert.equal(toolbar.getAttribute("role"), "toolbar");
  assert.deepEqual(
    buttons(host).map((b) => [b.textContent, b.getAttribute("type"), b.getAttribute("aria-label")]),
    [
      ["Ajuster", "button", "Ajuster toute la scène à la zone"],
      ["+", "button", "Zoom avant"],
      ["−", "button", "Zoom arrière"],
    ],
  );
  assert.ok(buttons(host).every((b) => b.getAttribute("title")));
});

test("avant mesure : viewBox de la scène ; après mesure : fit", () => {
  const host = container();
  const engine = createGraphicEngine(host, large());
  const svg = rendered(host).svg;
  assert.deepEqual(viewBoxOf(svg), [0, 0, 2120, 1306]);
  assert.equal(svg.getAttribute("width"), null);
  sized(host, engine, 800, 480);
  const fit = fitState({ width: 2120, height: 1306 }, { width: 800, height: 480 });
  assert.deepEqual(viewBoxOf(svg), [fit.x, fit.y, 800 / fit.scale, 480 / fit.scale]);
  assert.equal(host.querySelector(".gx-toolbar-scale").textContent, `${Math.round(fit.scale * 100)} %`);
});

test("boutons + / − / Ajuster ; la scène n'est jamais modifiée", () => {
  const { host, engine } = setup();
  const before = JSON.stringify(engine.scene());
  const fit = engine.viewport().scale;
  const [fitButton, plus, minus] = buttons(host);
  plus.dispatch("click");
  assert.ok(Math.abs(engine.viewport().scale - fit * ZOOM_STEP) < 1e-12);
  minus.dispatch("click");
  minus.dispatch("click");
  assert.ok(Math.abs(engine.viewport().scale - fit / ZOOM_STEP) < 1e-12);
  fitButton.dispatch("click");
  assert.equal(engine.viewport().scale, fit);
  assert.deepEqual(engine.home(), engine.fit());
  assert.equal(JSON.stringify(engine.scene()), before);
});

test("molette seule non interceptée ; Ctrl/Cmd + molette zoome sous le pointeur", () => {
  const { engine, area, svg } = setup();
  const initial = viewBoxOf(svg);
  const plain = area.dispatch("wheel", { deltaY: -100, clientX: 200, clientY: 100 });
  assert.equal(plain.defaultPrevented, false);
  assert.deepEqual(viewBoxOf(svg), initial);
  area.left = 50;
  area.top = 30;
  const before = engine.viewport();
  const point = { x: 250 - 50, y: 130 - 30 };
  const worldBefore = { x: before.x + point.x / before.scale, y: before.y + point.y / before.scale };
  for (const modifier of [{ ctrlKey: true }, { metaKey: true }]) {
    const event = area.dispatch("wheel", { deltaY: -100, clientX: 250, clientY: 130, ...modifier });
    assert.ok(event.defaultPrevented);
  }
  const after = engine.viewport();
  assert.ok(Math.abs(after.scale - before.scale * ZOOM_STEP * ZOOM_STEP) < 1e-12);
  assert.ok(Math.abs(after.x + point.x / after.scale - worldBefore.x) < 1e-9);
  assert.ok(Math.abs(after.y + point.y / after.scale - worldBefore.y) < 1e-9);
});

test("pan : glisser sur le fond ou au bouton du milieu, jamais un nœud au bouton principal", () => {
  const { host, engine, area, svg } = setup();
  const start = engine.viewport();
  svg.dispatch("pointerdown", { clientX: 100, clientY: 100, pointerId: 7 });
  assert.ok(area.captured.has(7) && area.classList.contains("gx-panning"));
  svg.dispatch("pointermove", { clientX: 140, clientY: 70, pointerId: 7 });
  svg.dispatch("pointerup", { clientX: 140, clientY: 70, pointerId: 7 });
  const moved = engine.viewport();
  assert.ok(Math.abs(moved.x - (start.x - 40 / start.scale)) < 1e-9);
  assert.ok(Math.abs(moved.y - (start.y + 30 / start.scale)) < 1e-9);
  assert.ok(!area.captured.has(7) && !area.classList.contains("gx-panning"));
  const node = rendered(host).nodes[0];
  node.dispatch("pointerdown", { clientX: 10, clientY: 10, pointerId: 8 });
  node.dispatch("pointermove", { clientX: 90, clientY: 90, pointerId: 8 });
  assert.deepEqual(engine.viewport(), moved);
  node.dispatch("click");
  assert.equal(engine.selection().nodeId, "A");
  const middle = node.dispatch("pointerdown", { button: 1, clientX: 0, clientY: 0, pointerId: 9 });
  assert.ok(middle.defaultPrevented);
  node.dispatch("pointermove", { clientX: 10, clientY: 0, pointerId: 9 });
  node.dispatch("pointercancel", { pointerId: 9 });
  assert.ok(engine.viewport().x < moved.x);
  assert.equal(engine.selection().nodeId, "A");
  node.dispatch("pointerdown", { button: 2, clientX: 0, clientY: 0, pointerId: 10 });
  assert.ok(!area.classList.contains("gx-panning"));
});

test("Maj + flèches : pan accessible ; flèches seules et Alt non interceptées", () => {
  const { host, engine } = setup();
  const node = rendered(host).nodes[0];
  const start = engine.viewport();
  assert.equal(node.dispatch("keydown", { key: "ArrowRight" }).defaultPrevented, false);
  assert.equal(node.dispatch("keydown", { key: "ArrowLeft", shiftKey: true, altKey: true }).defaultPrevented, false);
  assert.deepEqual(engine.viewport(), start);
  assert.ok(node.dispatch("keydown", { key: "ArrowRight", shiftKey: true }).defaultPrevented);
  assert.ok(Math.abs(engine.viewport().x - (start.x + (800 * 0.15) / start.scale)) < 1e-9);
  node.dispatch("keydown", { key: "ArrowDown", shiftKey: true });
  assert.ok(engine.viewport().y > start.y);
});

test("deux instances : viewports indépendants", () => {
  const a = setup();
  const b = setup(large(), 600, 400);
  const before = b.engine.viewport();
  a.engine.zoomAt({ x: 10, y: 10 }, 2);
  a.engine.panBy(30, 30);
  buttons(a.host)[1].dispatch("click");
  assert.deepEqual(b.engine.viewport(), before);
  assert.ok(a.engine.viewport().scale > before.scale);
});

test("resize : fit avant interaction, centre conservé ensuite", () => {
  const { host, engine } = setup();
  sized(host, engine, 600, 600);
  assert.deepEqual(engine.viewport(), { ...fitState({ width: 2120, height: 1306 }, { width: 600, height: 600 }), width: 600, height: 600 });
  engine.zoomIn();
  const zoomed = engine.viewport();
  sized(host, engine, 900, 300);
  const resized = engine.viewport();
  assert.equal(resized.scale, zoomed.scale);
  assert.ok(Math.abs(resized.x + 900 / (2 * resized.scale) - (zoomed.x + 600 / (2 * zoomed.scale))) < 1e-9);
});

test("ResizeObserver observé puis déconnecté par destroy", () => {
  const observed = [];
  class FakeObserver {
    constructor(callback) {
      this.callback = callback;
      observed.push(this);
    }
    observe(target) {
      this.target = target;
    }
    disconnect() {
      this.disconnected = true;
    }
  }
  globalThis.ResizeObserver = FakeObserver;
  try {
    const host = container();
    const engine = createGraphicEngine(host, large());
    const [observer] = observed;
    assert.equal(observer.target, host.querySelector(".gx-viewport"));
    observer.target.clientWidth = 800;
    observer.target.clientHeight = 480;
    observer.callback();
    assert.equal(engine.viewport().width, 800);
    engine.destroy();
    assert.ok(observer.disconnected);
    observer.callback();
  } finally {
    delete globalThis.ResizeObserver;
  }
});

test("destroy : cadre retiré, écouteurs libérés, viewport inaccessible", () => {
  const { host, engine, area, svg } = setup();
  const [fitButton] = buttons(host);
  engine.destroy();
  assert.equal(host.children.length, 0);
  assert.equal(area.listeners.length, 0);
  assert.equal(fitButton.listeners.length, 0);
  assert.equal(svg.listeners.length, 0);
  assert.throws(() => engine.viewport());
  assert.throws(() => engine.zoomIn());
  const event = area.dispatch("wheel", { ctrlKey: true, deltaY: -100 });
  assert.equal(event.defaultPrevented, false);
});

test("home = fit, indépendamment de la taille et du contenu de la scène", () => {
  const scene = large();
  scene.nodes = Array.from({ length: 50 }, (_, i) => ({ id: `n${i}`, label: `n${i}`, rect: { x: (i % 10) * 200, y: Math.floor(i / 10) * 200, width: 80, height: 40 } }));
  scene.edges = [];
  const { engine } = setup(scene);
  const fit = engine.fit();
  engine.zoomIn();
  engine.panBy(30, 10);
  assert.deepEqual(engine.home(), fit);
});
