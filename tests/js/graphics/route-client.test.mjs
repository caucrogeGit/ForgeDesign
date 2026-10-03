// Client Route Explorer : passe obligatoirement par le Graphic Core.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

import { mountRouteGraph } from "../../../forge_design/web/static/route-graph.js";
import { container, rendered } from "./fake-dom.mjs";

function page(sceneText) {
  const root = container();
  const document = root.ownerDocument;
  const make = (name, attribute) => {
    const element = document.createElement(name);
    if (attribute) element.setAttribute(attribute, "");
    return element;
  };
  const scene = make("script", "data-graphic-scene");
  scene.textContent = sceneText;
  const host = make("div", "data-graphic-host");
  const fallback = make("div", "data-graphic-fallback");
  const status = make("p", "data-selection-status");
  const details = make("dl", "data-selection-details");
  details.hidden = true;
  const fields = ["data-selection-kind", "data-selection-label", "data-selection-presence"].map((name) => make("dd", name));
  const clear = make("button", "data-selection-clear");
  clear.hidden = true;
  root.append(host, fallback, scene, status, details, ...fields, clear);
  return { root, host, fallback, status, details, fields, clear };
}

const SCENE = {
  width: 300,
  height: 100,
  title: "Graphe",
  nodes: [
    {
      id: '["route","GET","/"]',
      label: "GET /",
      rect: { x: 0, y: 0, width: 50, height: 40 },
      lines: ["Route", "GET /"],
      presentation: { variant: "category-1" },
      data: { "kind-label": "Route", "presence-label": "—" },
    },
    {
      id: '["template","<script>.html"]',
      label: "<script>.html",
      rect: { x: 100, y: 0, width: 50, height: 40 },
      presentation: { variant: "category-4", tone: "warning" },
      data: { "kind-label": "Template", "presence-label": "Absent" },
    },
  ],
  edges: [
    {
      id: "e",
      source: '["route","GET","/"]',
      target: '["template","<script>.html"]',
      points: [{ x: 50, y: 20 }, { x: 100, y: 20 }],
    },
  ],
};

test("montage : moteur créé, repli masqué, détails depuis les données opaques", () => {
  const view = page(JSON.stringify(SCENE));
  const engine = mountRouteGraph(view.root);
  assert.ok(engine && view.fallback.hidden);
  assert.equal(view.status.textContent, "Sélectionnez un élément du graphe.");
  const nodes = rendered(view.host).nodes;
  nodes[1].dispatch("click");
  assert.equal(view.details.hidden, false);
  assert.deepEqual(view.fields.map((f) => f.textContent), ["Template", "<script>.html", "Absent"]);
  assert.equal(view.status.textContent, "Élément sélectionné : <script>.html");
  view.clear.dispatch("click");
  assert.equal(engine.selection(), null);
  assert.equal(view.details.hidden, true);
  assert.equal(view.root.ownerDocument.activeElement, nodes[1]);
});

test("scène refusée : repli conservé et message", () => {
  const broken = { ...SCENE, edges: [{ ...SCENE.edges[0], target: "absent" }] };
  for (const text of ["{", JSON.stringify(broken)]) {
    const view = page(text);
    assert.equal(mountRouteGraph(view.root), null);
    assert.equal(view.fallback.hidden, false);
    assert.match(view.status.textContent, /Vue interactive indisponible/);
    assert.equal(rendered(view.host).svg, null);
  }
});

test("le client ne contourne pas le moteur", async () => {
  const source = await readFile(new URL("../../../forge_design/web/static/route-graph.js", import.meta.url), "utf8");
  assert.match(source, /from "\.\/graphics\/engine\.js"/);
  for (const forbidden of ["createElementNS", "innerHTML", "data-node-id", "classList", "fetch(", "eval("]) {
    assert.ok(!source.includes(forbidden), forbidden);
  }
});
