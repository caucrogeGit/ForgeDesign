import assert from "node:assert/strict";
import { test } from "node:test";

import { createGraphicEngine } from "../../../forge_design/web/static/graphics/engine.js";
import { GraphicSceneError } from "../../../forge_design/web/static/graphics/model.js";
import { container, rendered, SVG } from "./fake-dom.mjs";
import { HOSTILE, witness } from "./scenes.mjs";

function labelOf(element) {
  return element.getAttribute("aria-label");
}

function byLabel(host, label) {
  return rendered(host).nodes.find((element) => labelOf(element) === label);
}

test("rendu SVG : racine accessible, nœuds focusables, arêtes et flèche", () => {
  const host = container();
  createGraphicEngine(host, witness());
  const { svg, nodes, edges } = rendered(host);
  assert.equal(svg.namespace, SVG);
  assert.equal(svg.getAttribute("viewBox"), "0 0 400 120");
  assert.equal(svg.getAttribute("role"), "group");
  assert.equal(svg.getAttribute("aria-label"), "Témoin");
  assert.equal(svg.querySelector("desc").textContent, "Trois nœuds, deux arêtes.");
  assert.equal(nodes.length, 3);
  for (const element of nodes) {
    assert.equal(element.getAttribute("tabindex"), "0");
    assert.equal(element.getAttribute("role"), "button");
    assert.equal(element.getAttribute("aria-pressed"), "false");
    assert.ok(element.classList.contains("gx-variant-default"));
  }
  assert.equal(edges.length, 2);
  assert.equal(edges[0].querySelectorAll("polygon").length, 1);
  assert.equal(edges[1].querySelectorAll("polygon").length, 0);
  assert.equal(edges[0].querySelector("polyline").getAttribute("points"), "0,0 10,0 10,20");
});

test("libellés hostiles rendus comme texte", () => {
  const scene = witness();
  scene.nodes.forEach((node, index) => {
    node.label = HOSTILE[index];
    node.lines = HOSTILE.slice(0, 4);
  });
  scene.edges[0].label = HOSTILE[1];
  scene.edges[0].labelAt = { x: 5, y: 5 };
  const host = container();
  createGraphicEngine(host, scene);
  const { svg, nodes } = rendered(host);
  assert.equal(labelOf(nodes[0]), HOSTILE[0]);
  assert.equal(nodes[0].querySelector("title").textContent, HOSTILE[0]);
  assert.deepEqual(nodes[1].querySelectorAll("text").map((t) => t.textContent), HOSTILE.slice(0, 4));
  for (const element of svg.walk()) {
    assert.ok(["svg", "g", "title", "desc", "rect", "text", "polyline", "polygon"].includes(element.localName));
    assert.equal(element.children.length > 0 && element._text !== "", false);
  }
  assert.equal(svg.querySelectorAll("script").length, 0);
});

test("sélection souris et clavier, voisins directs, Escape", () => {
  const host = container();
  const events = [];
  const engine = createGraphicEngine(host, witness(), { onSelectionChange: (state) => events.push(state) });
  const a = byLabel(host, "Node A");
  const b = byLabel(host, "Node B");
  const c = byLabel(host, "Node C");
  a.dispatch("click");
  assert.equal(engine.selection().nodeId, "A");
  assert.ok(a.classList.contains("gx-selected") && a.getAttribute("aria-pressed") === "true");
  assert.ok(b.classList.contains("gx-related") && c.classList.contains("gx-related"));
  assert.ok(rendered(host).edges.every((edge) => edge.classList.contains("gx-related")));
  const enter = b.dispatch("keydown", { key: "Enter" });
  assert.ok(enter.defaultPrevented);
  assert.equal(engine.selection().nodeId, "B");
  assert.ok(a.classList.contains("gx-related") && !c.classList.contains("gx-related"));
  assert.deepEqual(rendered(host).edges.map((edge) => edge.classList.contains("gx-related")), [true, false]);
  const space = c.dispatch("keydown", { key: " " });
  assert.ok(space.defaultPrevented && engine.selection().nodeId === "C");
  c.dispatch("keydown", { key: "x" });
  assert.equal(engine.selection().nodeId, "C");
  const escape = rendered(host).svg.dispatch("keydown", { key: "Escape" });
  assert.ok(escape.defaultPrevented);
  assert.equal(engine.selection(), null);
  assert.equal(host.ownerDocument.activeElement, c);
  assert.ok(rendered(host).nodes.every((n) => !n.classList.contains("gx-selected") && !n.classList.contains("gx-related")));
  a.dispatch("click");
  a.dispatch("click");
  assert.equal(engine.selection(), null);
  assert.deepEqual(events.map((state) => state && state.nodeId), ["A", "B", "C", null, "A", null]);
  assert.throws(() => engine.select("Z"), GraphicSceneError);
});

test("deux instances indépendantes", () => {
  const first = container();
  const second = container();
  const a = createGraphicEngine(first, witness());
  const b = createGraphicEngine(second, witness());
  a.select("A");
  assert.equal(b.selection(), null);
  assert.ok(rendered(second).nodes.every((n) => !n.classList.contains("gx-selected")));
  byLabel(second, "Node C").dispatch("click");
  assert.equal(a.selection().nodeId, "A");
  assert.equal(b.selection().nodeId, "C");
});

test("destroy retire le SVG, les écouteurs et l'état", () => {
  const host = container();
  const engine = createGraphicEngine(host, witness());
  const nodeElement = byLabel(host, "Node A");
  const svg = rendered(host).svg;
  engine.select("A");
  engine.destroy();
  assert.equal(host.children.length, 0);
  assert.equal(nodeElement.listeners.length, 0);
  assert.equal(svg.listeners.length, 0);
  assert.equal(engine.selection(), null);
  assert.ok(engine.isDestroyed());
  assert.throws(() => engine.select("A"));
  engine.destroy();
});

test("re-rendu : un seul SVG et sélection conservée", () => {
  const host = container();
  const engine = createGraphicEngine(host, witness());
  engine.select("B");
  const old = byLabel(host, "Node B");
  engine.render();
  assert.equal(host.querySelectorAll("svg").length, 1);
  assert.equal(old.listeners.length, 0);
  assert.ok(byLabel(host, "Node B").classList.contains("gx-selected"));
});

test("scène invalide : aucune instance ni rendu", () => {
  const host = container();
  const scene = witness();
  scene.edges[0].target = "absent";
  assert.throws(() => createGraphicEngine(host, scene), GraphicSceneError);
  assert.equal(host.children.length, 0);
});

test("données d'arête opaques et accès par identité", () => {
  const scene = witness();
  scene.edges[0].data = { kind: "x", "free-text": "<b>texte</b>" };
  const engine = createGraphicEngine(container(), scene);
  assert.deepEqual({ ...engine.edge("A-B").data }, { kind: "x", "free-text": "<b>texte</b>" });
  assert.deepEqual({ ...engine.edge("A-C").data }, {});
  assert.equal(engine.edge("absent"), null);
  assert.ok(Object.isFrozen(engine.edge("A-B").data));
  const host = container();
  const bad = witness();
  bad.edges[0].data = { Kind: "x" };
  assert.throws(() => createGraphicEngine(host, bad), GraphicSceneError);
});

// Deux formes de graphe sans vocabulaire métier : une chaîne en colonnes et deux
// colonnes reliées par un intermédiaire avec arêtes parallèles.
function columns() {
  return {
    width: 600,
    height: 200,
    nodes: ["P", "Q", "R"].map((id, i) => ({
      id,
      label: `Colonne ${id}`,
      rect: { x: i * 200, y: 20, width: 150, height: 80 },
      lines: [`Niveau ${i}`, id, "—"],
      presentation: { variant: `category-${i + 1}` },
    })),
    edges: [
      { id: "P-Q", source: "P", target: "Q", points: [{ x: 150, y: 60 }, { x: 200, y: 60 }], label: "l1", labelAt: { x: 175, y: 55 } },
      { id: "Q-R", source: "Q", target: "R", points: [{ x: 350, y: 60 }, { x: 400, y: 60 }], presentation: { line: "dashed" } },
    ],
  };
}

function bridged() {
  return {
    width: 600,
    height: 300,
    nodes: [
      { id: "U", label: "U", rect: { x: 0, y: 20, width: 100, height: 60 }, presentation: { variant: "category-1" } },
      { id: "V", label: "V", rect: { x: 0, y: 160, width: 100, height: 60 }, presentation: { variant: "category-1" } },
      { id: "M", label: "M", rect: { x: 300, y: 90, width: 100, height: 60 }, presentation: { variant: "category-2" } },
    ],
    edges: [
      { id: "U-M:1", source: "U", target: "M", points: [{ x: 100, y: 50 }, { x: 300, y: 120 }], presentation: { arrow: "end" } },
      { id: "U-M:2", source: "U", target: "M", points: [{ x: 100, y: 60 }, { x: 300, y: 125 }], presentation: { arrow: "end" } },
      { id: "M-V", source: "M", target: "V", points: [{ x: 300, y: 130 }, { x: 100, y: 190 }] },
    ],
  };
}

test("deux clients de formes différentes, simultanés et isolés", () => {
  const first = container();
  const second = container();
  const a = createGraphicEngine(first, columns());
  const b = createGraphicEngine(second, bridged());
  assert.equal(rendered(first).nodes.length, 3);
  assert.equal(rendered(second).edges.length, 3);
  assert.ok(rendered(second).nodes[2].classList.contains("gx-variant-category-2"));
  b.select("M");
  assert.deepEqual(b.selection().edgeIds, ["U-M:1", "U-M:2", "M-V"]);
  assert.deepEqual(b.selection().neighbourIds, ["U", "V"]);
  assert.deepEqual(rendered(second).edges.map((e) => e.classList.contains("gx-related")), [true, true, true]);
  assert.equal(a.selection(), null);
  assert.ok(rendered(first).nodes.every((n) => !n.classList.contains("gx-selected")));
  byLabel(first, "Colonne Q").dispatch("keydown", { key: "Enter" });
  assert.deepEqual(a.selection().neighbourIds, ["P", "R"]);
  assert.equal(b.selection().nodeId, "M");
  a.destroy();
  assert.equal(b.selection().nodeId, "M");
  assert.ok([...second.walk()].includes(rendered(second).svg));
});
