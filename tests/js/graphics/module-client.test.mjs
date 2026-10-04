// Client générique des ressources de modules : moteur partagé, aucun vocabulaire de module.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

import { mountModuleResource } from "../../../forge_design/web/static/module-resource.js";
import { container, rendered } from "./fake-dom.mjs";

const HOSTILE = "</script><svg onload=alert(1)>";

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
  const host = make("div", "data-graphic-host");
  const fallback = make("p", "data-graphic-fallback");
  const status = make("p", "data-selection-status");
  root.append(host, fallback, scene, status);
  return { root, host, fallback, status };
}

const box = (id, x, label) => ({ id, label, rect: { x, y: 20, width: 200, height: 80 }, lines: [label] });
const SCENE = {
  width: 940,
  height: 120,
  nodes: [box("A", 20, HOSTILE), box("B", 370, "B"), box("C", 720, "C")],
  edges: [
    { id: "A-B", source: "A", target: "B", points: [{ x: 220, y: 60 }, { x: 370, y: 60 }] },
    { id: "B-C", source: "B", target: "C", points: [{ x: 570, y: 60 }, { x: 720, y: 60 }] },
  ],
};

test("montage : moteur, repli masqué, sélection annoncée, texte hostile inerte", () => {
  const view = page(JSON.stringify(SCENE));
  const engine = mountModuleResource(view.root);
  assert.ok(engine && view.fallback.hidden);
  assert.equal(view.status.textContent, "Sélectionnez un élément du graphe.");
  const nodes = rendered(view.host).nodes;
  nodes[0].dispatch("click");
  assert.equal(view.status.textContent, `Élément sélectionné : ${HOSTILE}`);
  assert.deepEqual(engine.selection().neighbourIds, ["B"]);
  assert.ok(nodes[0].querySelectorAll("text").every((text) => text.children.length === 0));
  nodes[0].dispatch("keydown", { key: "Escape" });
  assert.equal(view.status.textContent, "Sélectionnez un élément du graphe.");
});

test("scène refusée par validateScene : repli textuel conservé", () => {
  const forged = { ...SCENE, nodes: [{ ...SCENE.nodes[0], style: "x" }, ...SCENE.nodes.slice(1)] };
  for (const text of ["", "{", JSON.stringify(forged), JSON.stringify({ ...SCENE, edges: [{ ...SCENE.edges[0], target: "Z" }] })]) {
    const view = page(text);
    assert.equal(mountModuleResource(view.root), null);
    assert.equal(view.fallback.hidden, false);
    assert.match(view.status.textContent, /Vue interactive indisponible/);
    assert.equal(rendered(view.host).svg, null);
  }
});

test("le client est générique et ne contourne pas le moteur", async () => {
  const source = await readFile(new URL("../../../forge_design/web/static/module-resource.js", import.meta.url), "utf8");
  assert.match(source, /from "\.\/graphics\/engine\.js"/);
  for (const forbidden of ["createElementNS", "innerHTML", "fetch(", "eval(", "import(", "/modules/", "zoom", "minimap", "detailLevel", "viewBox", "circuit", "witness", "network"]) {
    assert.ok(!source.toLowerCase().includes(forbidden.toLowerCase()), forbidden);
  }
});
