// Niveau de détail intégré au moteur : transitions, identités, sélection, focus, coût.
import assert from "node:assert/strict";
import { test } from "node:test";

import { THRESHOLDS } from "../../../forge_design/web/static/graphics/detail-level.js";
import { createGraphicEngine } from "../../../forge_design/web/static/graphics/engine.js";
import { container, rendered, sized } from "./fake-dom.mjs";
import { HOSTILE, edge, node, witness } from "./scenes.mjs";

const LEVEL_CLASSES = ["gx-detail-overview", "gx-detail-normal", "gx-detail-detail"];

// Proportions de la scène Route réelle (2120 × 1066) : fit ≈ 0,36 dans 800 × 480.
function scene({ levels = true } = {}) {
  const base = witness();
  const extra = levels ? { levels: { overview: [], normal: [0, 1] } } : {};
  return {
    ...base,
    width: 2120,
    height: 1066,
    nodes: [
      node("A", 0, { label: "Nœud A complet", lines: ["Catégorie", "A", "Secondaire"], ...extra }),
      node("B", 120, { lines: ["Catégorie", "B", "Secondaire"], ...extra }),
      node("C", 240, { lines: [HOSTILE[0], HOSTILE[1], HOSTILE[2]], ...extra }),
    ],
    edges: [
      edge("A-B", "A", "B", { label: "lien", labelAt: { x: 60, y: 5 } }),
      edge("A-C", "A", "C", { label: "</text><script>alert(1)</script>", labelAt: { x: 120, y: 5 } }),
    ],
  };
}

function setup(input = scene(), width = 800, height = 480) {
  const host = container();
  const engine = createGraphicEngine(host, input);
  sized(host, engine, width, height);
  return { host, engine, ...rendered(host) };
}

function activeLevel(svg) {
  const active = LEVEL_CLASSES.filter((name) => svg.classList.contains(name));
  assert.equal(active.length, 1, `une seule classe de niveau : ${active}`);
  assert.equal(svg.getAttribute("data-detail-level"), active[0].slice("gx-detail-".length));
  return svg.getAttribute("data-detail-level");
}

// Lignes déclarées visibles au niveau (la CSS masque les autres).
function visibleLines(nodeElement, level) {
  return nodeElement
    .querySelectorAll(".gx-node-text")
    .filter((text) => text.classList.contains(`gx-at-${level}`))
    .map((text) => text.textContent);
}

function zoomUntil(engine, wanted, step) {
  for (let i = 0; i < 40 && engine.detailLevel() !== wanted; i += 1) step();
  assert.equal(engine.detailLevel(), wanted);
}

test("avant mesure : échelle 1 → detail ; après fit Route : overview", () => {
  const host = container();
  const engine = createGraphicEngine(host, scene());
  const { svg } = rendered(host);
  assert.equal(engine.detailLevel(), "detail");
  assert.equal(activeLevel(svg), "detail");
  sized(host, engine, 800, 480);
  assert.ok(engine.viewport().scale < THRESHOLDS.normalAbove);
  assert.equal(engine.detailLevel(), "overview");
  assert.equal(activeLevel(svg), "overview");
});

test("lignes par niveau ; label accessible, titre et identités indépendants du niveau", () => {
  const { engine, svg, nodes } = setup();
  const before = { nodes: [...nodes], texts: svg.querySelectorAll("text") };
  const expected = { overview: [], normal: ["Catégorie", "A"], detail: ["Catégorie", "A", "Secondaire"] };
  for (const [level, step] of [
    ["overview", () => {}],
    ["normal", () => engine.zoomIn()],
    ["detail", () => engine.zoomIn()],
    ["normal", () => engine.zoomOut()],
    ["overview", () => engine.zoomOut()],
  ]) {
    zoomUntil(engine, level, step);
    assert.equal(activeLevel(svg), level);
    assert.deepEqual(visibleLines(nodes[0], level), expected[level]);
    assert.equal(nodes[0].getAttribute("aria-label"), "Nœud A complet");
    assert.equal(nodes[0].querySelector("title").textContent, "Nœud A complet");
    // Aucun élément recréé : mêmes nœuds, mêmes textes, mêmes libellés d'arêtes.
    assert.deepEqual(rendered(svg.parent.parent.parent).nodes, before.nodes);
    assert.deepEqual(svg.querySelectorAll("text"), before.texts);
  }
  assert.equal(engine.node("A").id, "A");
  assert.deepEqual(engine.scene().edges.map((item) => item.id), ["A-B", "A-C"]);
});

test("contenu hostile : du texte à chaque niveau", () => {
  const { engine, svg, nodes } = setup();
  for (const step of [() => {}, () => engine.zoomIn(), () => engine.zoomIn()]) {
    step();
    for (const text of svg.querySelectorAll("text")) assert.equal(text.children.length, 0);
  }
  zoomUntil(engine, "detail", () => engine.zoomIn());
  assert.deepEqual(visibleLines(nodes[2], "detail"), HOSTILE.slice(0, 3));
  assert.deepEqual(
    svg.querySelectorAll(".gx-edge-label").map((label) => label.textContent),
    ["lien", "</text><script>alert(1)</script>"],
  );
});

test("scène sans levels : toutes les lignes à tous les niveaux", () => {
  const { engine, svg, nodes } = setup(scene({ levels: false }));
  for (const level of ["overview", "normal", "detail"]) {
    zoomUntil(engine, level, () => engine.zoomIn());
    assert.equal(activeLevel(svg), level);
    assert.deepEqual(visibleLines(nodes[1], level), ["Catégorie", "B", "Secondaire"]);
  }
});

test("sélection, voisins et focus conservés à travers les transitions", () => {
  const { host, engine, nodes } = setup();
  const document = host.ownerDocument;
  nodes[0].dispatch("click");
  nodes[0].focus();
  const selected = engine.selection();
  for (const [level, step] of [
    ["normal", () => engine.zoomIn()],
    ["detail", () => engine.zoomIn()],
    ["overview", () => engine.zoomOut()],
  ]) {
    zoomUntil(engine, level, step);
    assert.deepEqual(engine.selection(), selected);
    assert.deepEqual(engine.selection().neighbourIds, ["B", "C"]);
    assert.ok(nodes[0].classList.contains("gx-selected"));
    assert.equal(nodes[0].getAttribute("aria-pressed"), "true");
    assert.equal(document.activeElement, nodes[0]);
  }
  nodes[0].dispatch("keydown", { key: "Escape" });
  assert.equal(engine.selection(), null);
});

function countLevelWrites(svg) {
  const counter = { writes: 0 };
  const original = svg.setAttribute.bind(svg);
  svg.setAttribute = (name, value) => {
    if (name === "data-detail-level") counter.writes += 1;
    original(name, value);
  };
  return counter;
}

test("100 zooms dans un même niveau et le pan : aucune écriture de niveau", () => {
  const { engine, svg, host } = setup();
  zoomUntil(engine, "normal", () => engine.zoomIn());
  const counter = countLevelWrites(svg);
  const area = host.querySelector(".gx-viewport");
  for (let i = 0; i < 100; i += 1) {
    area.dispatch("wheel", { ctrlKey: true, deltaY: i % 2 ? 1 : -1, clientX: 400, clientY: 240 });
  }
  engine.panBy(50, -20);
  for (let i = 0; i < 10; i += 1) area.dispatch("keydown", { key: "ArrowRight", shiftKey: true });
  assert.equal(engine.detailLevel(), "normal");
  assert.equal(counter.writes, 0);
  engine.zoomIn();
  engine.zoomIn();
  assert.equal(engine.detailLevel(), "detail");
  assert.equal(counter.writes, 1);
});

test("pincement oscillant autour du seuil : au plus une transition (hystérésis)", () => {
  const { engine, svg, host } = setup();
  const area = host.querySelector(".gx-viewport");
  // Amène l'échelle juste sous le seuil d'entrée de normal.
  const target = THRESHOLDS.normalAbove * 0.995;
  engine.zoomAt({ x: 400, y: 240 }, target / engine.viewport().scale);
  assert.equal(engine.detailLevel(), "overview");
  const counter = countLevelWrites(svg);
  for (let i = 0; i < 60; i += 1) {
    area.dispatch("wheel", { ctrlKey: true, deltaY: i % 2 ? 2 : -2, clientX: 400, clientY: 240 });
  }
  assert.ok(counter.writes <= 1, `${counter.writes} transitions`);
});

test("deux instances : niveaux simultanés différents, aucun état partagé", () => {
  const route = setup();
  const other = setup({ ...scene(), width: 1000, height: 600 }, 800, 480);
  assert.equal(route.engine.detailLevel(), "overview");
  assert.equal(other.engine.detailLevel(), "normal");
  zoomUntil(route.engine, "detail", () => route.engine.zoomIn());
  assert.equal(other.engine.detailLevel(), "normal");
  assert.equal(activeLevel(other.svg), "normal");
  assert.equal(activeLevel(route.svg), "detail");
});

test("resize avant interaction : le fit suit la zone et le niveau aussi", () => {
  const { host, engine } = setup({ ...scene(), width: 1000, height: 600 }, 800, 480);
  assert.equal(engine.detailLevel(), "normal");
  sized(host, engine, 400, 300);
  assert.equal(engine.detailLevel(), "overview");
  sized(host, engine, 1400, 900);
  assert.equal(engine.detailLevel(), "detail");
  engine.zoomOut();
  const level = engine.detailLevel();
  sized(host, engine, 1300, 900);
  assert.equal(engine.detailLevel(), level, "après interaction : échelle conservée, niveau aussi");
});

test("render() conserve le niveau ; destroy le rend inaccessible", () => {
  const { host, engine } = setup();
  zoomUntil(engine, "normal", () => engine.zoomIn());
  engine.render();
  assert.equal(activeLevel(rendered(host).svg), "normal");
  engine.destroy();
  assert.throws(() => engine.detailLevel());
});
