// Client Entity Explorer : panneau propre, moteur partagé, aucun contournement.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

import { mountEntityGraph } from "../../../forge_design/web/static/entity-graph.js";
import { container, rendered } from "./fake-dom.mjs";

const PANEL = [
  "data-selection-kind",
  "data-selection-label",
  "data-selection-table",
  "data-selection-field-count",
  "data-selection-field-label",
  "data-selection-relation-count",
];

function page(sceneText) {
  const root = container();
  const document = root.ownerDocument;
  const make = (name, attribute) => {
    const element = document.createElement(name);
    element.setAttribute(attribute, "");
    return element;
  };
  const scene = make("script", "data-graphic-scene");
  scene.textContent = sceneText;
  const parts = {
    host: make("div", "data-graphic-host"),
    fallback: make("div", "data-graphic-fallback"),
    status: make("p", "data-selection-status"),
    details: make("dl", "data-selection-details"),
    relations: make("ul", "data-selection-relations"),
    clear: make("button", "data-selection-clear"),
  };
  const fields = Object.fromEntries(PANEL.map((name) => [name, make("dd", name)]));
  root.append(scene, ...Object.values(parts), ...Object.values(fields));
  return { root, ...parts, fields };
}

const HOSTILE = "<script>alert(1)</script>";

function node(id, kind, name, y, extra = {}) {
  return {
    id,
    label: `${kind} ${name}`,
    rect: { x: kind === "Pivot" ? 480 : 40, y, width: 260, height: 100 },
    lines: [`${kind} — 2 champs`, name],
    data: { "kind-label": kind, name, table: name, "field-count": "2", "field-label": kind === "Pivot" ? "Champs supplémentaires" : "Champs" },
    ...extra,
  };
}

function edge(id, source, target, kind, name) {
  return { id, source, target, points: [{ x: 300, y: 50 }, { x: 480, y: 50 }], data: { kind, name } };
}

// Deux relations parallèles A → B (même source, même cible) et un many_to_many via pivot.
const SCENE = {
  width: 800,
  height: 500,
  nodes: [
    node("entity:0", "Entité", HOSTILE, 100),
    node("entity:1", "Entité", "Tag", 240),
    node("pivot:2", "Pivot", "article_tag", 100),
  ],
  edges: [
    edge("relation:0", "entity:0", "entity:1", "many_to_one", "auteur"),
    edge("relation:1", "entity:0", "entity:1", "many_to_one", "relecteur"),
    edge("relation:2:from", "entity:0", "pivot:2", "many_to_many_from", "tags"),
    edge("relation:2:to", "pivot:2", "entity:1", "many_to_many_to", ""),
  ],
};

function panel(view) {
  return Object.fromEntries(PANEL.map((name) => [name, view.fields[name].textContent]));
}

test("montage, relations parallèles et liste des relations directes", () => {
  const view = page(JSON.stringify(SCENE));
  const engine = mountEntityGraph(view.root);
  assert.ok(engine && view.fallback.hidden);
  const nodes = rendered(view.host).nodes;
  nodes[0].dispatch("click");
  assert.deepEqual(engine.selection().edgeIds, ["relation:0", "relation:1", "relation:2:from"]);
  assert.deepEqual(panel(view), {
    "data-selection-kind": "Entité",
    "data-selection-label": HOSTILE,
    "data-selection-table": HOSTILE,
    "data-selection-field-count": "2",
    "data-selection-field-label": "Champs",
    "data-selection-relation-count": "3",
  });
  assert.deepEqual(
    view.relations.children.map((item) => item.textContent),
    [`${HOSTILE} → auteur → Tag`, `${HOSTILE} → relecteur → Tag`, `${HOSTILE} → tags → article_tag`],
  );
  assert.equal(view.status.textContent, `Élément sélectionné : ${HOSTILE}`);
  assert.equal(view.relations.hidden, false);
});

test("pivot sélectionné comme n'importe quel nœud", () => {
  const view = page(JSON.stringify(SCENE));
  const engine = mountEntityGraph(view.root);
  rendered(view.host).nodes[2].dispatch("keydown", { key: "Enter" });
  assert.deepEqual(engine.selection().neighbourIds, ["entity:0", "entity:1"]);
  assert.equal(panel(view)["data-selection-field-label"], "Champs supplémentaires");
  assert.deepEqual(
    view.relations.children.map((item) => item.textContent),
    [`${HOSTILE} → tags → article_tag`, "article_tag → many_to_many_to → Tag"],
  );
  view.clear.dispatch("click");
  assert.equal(engine.selection(), null);
  assert.equal(view.details.hidden, true);
  assert.equal(view.relations.children.length, 0);
  assert.equal(view.root.ownerDocument.activeElement, rendered(view.host).nodes[2]);
});

test("scène refusée : repli conservé et message", () => {
  const broken = { ...SCENE, edges: [...SCENE.edges, SCENE.edges[0]] };
  for (const text of ["", JSON.stringify(broken)]) {
    const view = page(text);
    assert.equal(mountEntityGraph(view.root), null);
    assert.equal(view.fallback.hidden, false);
    assert.match(view.status.textContent, /Vue interactive indisponible/);
    assert.equal(rendered(view.host).svg, null);
  }
});

test("le client ne contourne pas le moteur", async () => {
  const source = await readFile(new URL("../../../forge_design/web/static/entity-graph.js", import.meta.url), "utf8");
  assert.match(source, /from "\.\/graphics\/engine\.js"/);
  // Ni rendu, ni sélection, ni viewport propres au client : tout passe par le moteur.
  for (const forbidden of ["createElementNS", "innerHTML", "data-node-id", "classList", "fetch(", "eval(", "viewBox", "zoom", "panBy", "fit(", "home(", "resize(", "wheel", "pointer", "detailLevel", "gx-detail", "gx-at-", "levels"]) {
    assert.ok(!source.includes(forbidden), forbidden);
  }
});
