// Minicarte intégrée au moteur : synchronisation, navigation, coût, isolation, cycle de vie.
import assert from "node:assert/strict";
import { test } from "node:test";

import { createGraphicEngine } from "../../../forge_design/web/static/graphics/engine.js";
import { minimapLayout, worldToMinimap } from "../../../forge_design/web/static/graphics/minimap.js";
import { container, rendered, sized } from "./fake-dom.mjs";
import { edge, node, witness } from "./scenes.mjs";

const close = (a, b, eps = 1e-6) => assert.ok(Math.abs(a - b) <= eps, `${a} ≉ ${b}`);

// Proportions de Route (2120 × 1066), catégories génériques et étiquettes.
function scene() {
  const base = witness();
  return {
    ...base,
    width: 2120,
    height: 1066,
    nodes: [
      node("A", 0, { presentation: { variant: "category-1" }, levels: { overview: [], normal: [0] } }),
      node("B", 900, { presentation: { variant: "category-2" } }),
      node("C", 1900, { presentation: { variant: "category-2" } }),
    ],
    edges: [edge("A-B", "A", "B", { label: "lien", labelAt: { x: 60, y: 5 } }), edge("B-C", "B", "C")],
  };
}

function setup(input = scene(), width = 800, height = 480) {
  const host = container();
  const engine = createGraphicEngine(host, input);
  sized(host, engine, width, height);
  const mini = host.querySelector(".gx-minimap");
  const svg = mini.querySelector("svg");
  const layout = minimapLayout(input);
  // Mise en page simulée : la minicarte occupe sa taille naturelle à (1000, 20).
  Object.assign(svg, { clientWidth: layout.width, clientHeight: layout.height, left: 1000, top: 20 });
  return { ...rendered(host), host, engine, mini, miniSvg: svg, layout };
}

function center(engine) {
  const v = engine.viewport();
  return { x: v.x + v.width / (2 * v.scale), y: v.y + v.height / (2 * v.scale) };
}

function clientOf(layout, world) {
  const p = worldToMinimap(layout, world);
  return { clientX: 1000 + p.x, clientY: 20 + p.y };
}

function writes(elements, names) {
  const counter = { count: 0 };
  for (const element of elements) {
    const original = element.setAttribute.bind(element);
    element.setAttribute = (name, value) => {
      if (names.includes(name)) counter.count += 1;
      original(name, value);
    };
  }
  return counter;
}

test("structure : SVG dérivé de la scène, sans texte, DOM constant, accessible", () => {
  const { host, mini, miniSvg: svg } = setup();
  const stage = host.querySelector(".gx-stage");
  assert.equal(stage.children[0], mini, "la minicarte précède la zone (ordre de tabulation)");
  assert.equal(stage.children[1], host.querySelector(".gx-viewport"));
  assert.equal(mini.getAttribute("role"), "group");
  assert.equal(mini.getAttribute("tabindex"), "0");
  assert.match(mini.getAttribute("aria-label"), /^Mini-carte de la scène\. Zone visible/);
  assert.equal(svg.getAttribute("aria-hidden"), "true");
  assert.equal(svg.querySelectorAll("text").length, 0);
  assert.equal(svg.querySelectorAll("title").length, 0);
  const paths = svg.querySelectorAll("path");
  assert.deepEqual(paths.map((p) => p.getAttribute("class")), [
    "gx-minimap-edges",
    "gx-minimap-nodes gx-variant-category-1",
    "gx-minimap-nodes gx-variant-category-2",
  ]);
  assert.equal(paths[0].getAttribute("d").split("M").length - 1, 2, "une polyligne par arête");
  assert.equal(paths[2].getAttribute("d").split("Z").length - 1, 2, "un rectangle par nœud");
  assert.equal(svg.querySelectorAll(".gx-minimap-viewport").length, 1);
  // Aucun nœud focalisable dans la minicarte.
  assert.ok([...svg.walk()].every((element) => element.getAttribute("tabindex") === null));
});

test("politique : masquée au fit, visible dès que la scène dépasse, de nouveau masquée par Ajuster", () => {
  const { engine, mini, host } = setup();
  assert.equal(mini.hidden, true);
  assert.equal(engine.minimap().visible, false);
  engine.zoomIn();
  assert.equal(mini.hidden, false);
  host.querySelector(".gx-toolbar-button").dispatch("click");
  assert.equal(mini.hidden, true);
  // Pan au fit : une partie de la scène sort de la vue → utile.
  engine.panBy(-400, 0);
  assert.equal(mini.hidden, false);
  engine.home();
  assert.equal(mini.hidden, true);
});

// Le rectangle affiché (DOM) correspond toujours à la zone visible calculée.
function assertDrawn(host, engine) {
  const rect = host.querySelector(".gx-minimap-viewport");
  const expected = engine.minimap().rect;
  for (const key of ["x", "y", "width", "height"]) close(Number(rect.getAttribute(key)), Math.round(expected[key] * 10) / 10, 1e-9);
}

test("rectangle : suit le pan, se redimensionne au zoom, couvre la scène au fit, suit le resize", () => {
  const { engine, host, layout } = setup();
  assertDrawn(host, engine);
  // Au fit, le rectangle couvre toute la scène (bornée à la marge interne).
  const fit = engine.minimap().rect;
  assert.ok(fit.x <= layout.padding && fit.x + fit.width >= layout.width - layout.padding);
  assert.ok(fit.y <= layout.padding && fit.y + fit.height >= layout.height - layout.padding);
  engine.zoomIn();
  const zoomed = engine.minimap().rect;
  assert.ok(zoomed.width < fit.width && zoomed.height <= fit.height);
  engine.panBy(-100, 0);
  const panned = engine.minimap().rect;
  close(panned.width, zoomed.width);
  assert.ok(panned.x > zoomed.x);
  assertDrawn(host, engine);
  engine.zoomIn();
  assert.ok(engine.minimap().rect.width < panned.width);
  assertDrawn(host, engine);
  const before = engine.minimap().rect.width;
  sized(host, engine, 400, 480);
  close(engine.minimap().rect.width, before / 2, 0.06);
  assertDrawn(host, engine);
});

test("clic : recentre sur le point monde pointé, échelle conservée", () => {
  const { engine, mini, layout } = setup();
  engine.zoomIn();
  engine.zoomIn();
  const scale = engine.viewport().scale;
  const target = { x: 1800, y: 600 };
  mini.dispatch("pointerdown", { ...clientOf(layout, target), pointerId: 3 });
  assert.ok(mini.captured.has(3));
  mini.dispatch("pointerup", { ...clientOf(layout, target), pointerId: 3 });
  assert.ok(!mini.captured.has(3));
  assert.equal(engine.viewport().scale, scale);
  close(center(engine).x, 1800, 1e-6);
  close(center(engine).y, 600, 1e-6);
});

test("mise à l'échelle CSS de la minicarte : la conversion reste exacte", () => {
  const { engine, mini, miniSvg: svg, layout } = setup();
  engine.zoomIn();
  Object.assign(svg, { clientWidth: layout.width / 2, clientHeight: layout.height / 2 });
  const p = worldToMinimap(layout, { x: 300, y: 200 });
  mini.dispatch("pointerdown", { clientX: 1000 + p.x / 2, clientY: 20 + p.y / 2, pointerId: 1 });
  mini.dispatch("pointerup", { clientX: 1000 + p.x / 2, clientY: 20 + p.y / 2, pointerId: 1 });
  close(center(engine).x, 300);
  close(center(engine).y, 200);
});

test("glisser dans le rectangle : garde le décalage de saisie ; pointercancel termine", () => {
  const { engine, mini, layout } = setup();
  engine.zoomIn();
  engine.zoomIn();
  const start = center(engine);
  const grab = { x: start.x + 50, y: start.y - 20 };
  mini.dispatch("pointerdown", { ...clientOf(layout, grab), pointerId: 4 });
  close(center(engine).x, start.x, 1e-6);
  close(center(engine).y, start.y, 1e-6);
  const moved = clientOf(layout, { x: grab.x + 300, y: grab.y + 100 });
  mini.dispatch("pointermove", { ...moved, pointerId: 4 });
  close(center(engine).x, start.x + 300, 1e-6);
  close(center(engine).y, start.y + 100, 1e-6);
  mini.dispatch("pointermove", { ...moved, pointerId: 9 });
  mini.dispatch("pointercancel", { pointerId: 4 });
  assert.ok(!mini.captured.has(4));
  const after = center(engine);
  mini.dispatch("pointermove", { ...clientOf(layout, { x: 0, y: 0 }), pointerId: 4 });
  assert.deepEqual(center(engine), after);
  // Appui-relâcher sans mouvement dans le rectangle : un clic, qui recentre.
  const inside = center(engine);
  const tap = clientOf(layout, { x: inside.x + 40, y: inside.y + 10 });
  mini.dispatch("pointerdown", { ...tap, pointerId: 6 });
  close(center(engine).x, inside.x, 1e-6);
  mini.dispatch("pointerup", { ...tap, pointerId: 6 });
  close(center(engine).x, inside.x + 40, 1e-6);
  close(center(engine).y, inside.y + 10, 1e-6);
  const after2 = center(engine);
  // Bouton secondaire ignoré.
  mini.dispatch("pointerdown", { ...clientOf(layout, { x: 0, y: 0 }), button: 2, pointerId: 5 });
  assert.deepEqual(center(engine), after2);
});

test("clavier : flèches seules sur la minicarte focalisée ; jamais masquée sous le focus", () => {
  const { host, engine, mini } = setup();
  engine.zoomIn();
  mini.focus();
  const x = engine.viewport().x;
  assert.ok(mini.dispatch("keydown", { key: "ArrowRight" }).defaultPrevented);
  assert.ok(engine.viewport().x > x);
  assert.equal(mini.dispatch("keydown", { key: "ArrowLeft", shiftKey: true }).defaultPrevented, false);
  engine.fit();
  assert.equal(mini.hidden, false, "focalisée : reste visible");
  host.ownerDocument.activeElement = null;
  mini.dispatch("blur");
  assert.equal(mini.hidden, true);
});

test("Ctrl + molette sur la minicarte : zoom de la vue, jamais celui de la page", () => {
  const { engine, mini } = setup();
  engine.zoomIn();
  const scale = engine.viewport().scale;
  assert.equal(mini.dispatch("wheel", { deltaY: -100 }).defaultPrevented, false);
  assert.ok(mini.dispatch("wheel", { deltaY: -100, ctrlKey: true }).defaultPrevented);
  assert.ok(engine.viewport().scale > scale);
});

test("100 pans et 100 zooms, transitions de niveau comprises : structure jamais réécrite", () => {
  const { engine, miniSvg: svg, host } = setup();
  const structure = writes([...svg.querySelectorAll("path"), svg.querySelector(".gx-minimap-scene"), svg], ["d", "x", "y", "width", "height", "viewBox"]);
  const viewportRect = writes([svg.querySelector(".gx-minimap-viewport")], ["x"]);
  const area = host.querySelector(".gx-viewport");
  const levels = new Set();
  for (let i = 0; i < 100; i += 1) {
    engine.panBy(i % 2 ? 7 : -5, 3);
    area.dispatch("wheel", { ctrlKey: true, deltaY: i % 3 ? -40 : 30, clientX: 400, clientY: 240 });
    levels.add(engine.detailLevel());
  }
  assert.ok(levels.size >= 2, `niveaux traversés : ${[...levels]}`);
  assert.equal(structure.count, 0);
  assert.ok(viewportRect.count <= 200 && viewportRect.count > 0);
});

test("sélection : sans effet sur la minicarte", () => {
  const { engine, nodes, miniSvg: svg } = setup();
  engine.zoomIn();
  const before = engine.minimap();
  const structure = writes(svg.querySelectorAll("path"), ["d", "class"]);
  nodes[0].dispatch("click");
  assert.equal(engine.selection().nodeId, "A");
  assert.deepEqual(engine.minimap(), before);
  assert.equal(structure.count, 0);
});

test("deux instances : minicartes et navigations indépendantes", () => {
  const a = setup();
  const b = setup({ ...scene(), width: 780, height: 740 });
  a.engine.zoomIn();
  b.engine.zoomIn();
  b.engine.zoomIn();
  const before = b.engine.viewport();
  const fresh = setup();
  assert.equal(a.engine.minimap().visible, true);
  assert.equal(fresh.engine.minimap().visible, false);
  assert.equal(a.mini.hidden, false);
  a.engine.panBy(10, 0);
  assert.equal(a.mini.hidden, false, "une instance au fit ne masque pas la minicarte d'une autre");
  a.mini.dispatch("pointerdown", { ...clientOf(a.layout, { x: 2000, y: 1000 }), pointerId: 1 });
  a.mini.dispatch("pointerup", { ...clientOf(a.layout, { x: 2000, y: 1000 }), pointerId: 1 });
  assert.deepEqual(b.engine.viewport(), before);
  assert.notDeepEqual(a.engine.minimap().rect, b.engine.minimap().rect);
  assert.notEqual(a.mini, b.mini);
});

test("render() recrée une seule minicarte sans écouteurs dupliqués ; destroy libère tout", () => {
  const { host, engine, mini } = setup();
  const listeners = mini.listeners.length;
  engine.render();
  assert.equal(host.querySelectorAll(".gx-minimap").length, 1);
  assert.equal(mini.listeners.length, 0, "ancienne minicarte libérée");
  const fresh = host.querySelector(".gx-minimap");
  assert.equal(fresh.listeners.length, listeners);
  engine.destroy();
  assert.equal(fresh.listeners.length, 0);
  assert.equal(host.querySelectorAll(".gx-minimap").length, 0);
  assert.throws(() => engine.minimap());
});

test("gros témoin 1000 nœuds × 4000 arêtes : DOM constant, aucune réécriture pendant la navigation", () => {
  const nodes = Array.from({ length: 1000 }, (_, i) => ({
    id: `n${i}`,
    label: `n${i}`,
    rect: { x: (i % 50) * 120, y: Math.floor(i / 50) * 80, width: 80, height: 40 },
    presentation: { variant: `category-${(i % 4) + 1}` },
  }));
  const edges = Array.from({ length: 4000 }, (_, i) => {
    const s = nodes[i % 1000].rect;
    const t = nodes[(i * 7 + 13) % 1000].rect;
    return { id: `e${i}`, source: `n${i % 1000}`, target: `n${(i * 7 + 13) % 1000}`, points: [{ x: s.x + 80, y: s.y + 20 }, { x: t.x, y: t.y + 20 }] };
  });
  const started = performance.now();
  const { engine, miniSvg: svg } = setup({ width: 6000, height: 1600, nodes, edges }, 800, 480);
  const created = performance.now() - started;
  assert.equal([...svg.walk()].length - 1, 1 + 1 + 4 + 1, "fond, arêtes, 4 variantes, zone visible");
  const structure = writes(svg.querySelectorAll("path"), ["d"]);
  for (let i = 0; i < 100; i += 1) engine.panBy(3, 1);
  for (let i = 0; i < 100; i += 1) engine.zoomAt({ x: 400, y: 240 }, i % 2 ? 1.1 : 1 / 1.05);
  assert.equal(structure.count, 0);
  assert.ok(created < 5000, `création ${created} ms`);
});
