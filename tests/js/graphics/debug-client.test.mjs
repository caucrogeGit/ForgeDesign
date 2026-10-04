// Client Debug Center : statut accessible, moteur partagé, aucun contournement.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

import { mountDebugFlow } from "../../../forge_design/web/static/debug-flow.js";
import { container, rendered } from "./fake-dom.mjs";

const HOSTILE = "</text><script>alert(1)</script>";

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
  const fallback = make("div", "data-graphic-fallback");
  const status = make("p", "data-selection-status");
  root.append(host, fallback, scene, status);
  return { root, host, fallback, status };
}

function step(id, x, label, detail) {
  return {
    id,
    label: detail ? `${label} — ${detail}` : label,
    rect: { x, y: 20, width: 220, height: 90 },
    lines: detail ? [label, detail] : [label],
    levels: { overview: [], normal: [0] },
    presentation: { variant: "category-1" },
  };
}

// Flux séquentiel : trois étapes reliées dans l'ordre conceptuel.
const SCENE = {
  width: 900,
  height: 130,
  title: "Flux",
  nodes: [step("a", 20, "Requête", "GET /"), step("b", 320, "Contrôleur", HOSTILE), step("c", 620, "Template")],
  edges: [
    { id: '["x","a","b"]', source: "a", target: "b", points: [{ x: 240, y: 65 }, { x: 320, y: 65 }], presentation: { arrow: "end" } },
    { id: '["x","b","c"]', source: "b", target: "c", points: [{ x: 540, y: 65 }, { x: 620, y: 65 }], presentation: { arrow: "end" } },
  ],
};

test("montage : moteur créé, repli masqué, statut de l'étape sélectionnée", () => {
  const view = page(JSON.stringify(SCENE));
  const engine = mountDebugFlow(view.root);
  assert.ok(engine && view.fallback.hidden);
  assert.equal(view.status.textContent, "Sélectionnez une étape du flux.");
  const nodes = rendered(view.host).nodes;
  assert.deepEqual(nodes.map((node) => node.getAttribute("aria-label")), ["Requête — GET /", `Contrôleur — ${HOSTILE}`, "Template"]);
  nodes[1].dispatch("click");
  assert.deepEqual(engine.selection().neighbourIds, ["a", "c"]);
  assert.equal(view.status.textContent, `Étape sélectionnée : Contrôleur — ${HOSTILE}`);
  // Le texte hostile reste un nœud texte, jamais du balisage.
  const texts = nodes[1].querySelectorAll("text");
  assert.equal(texts[1].textContent, HOSTILE);
  assert.ok(texts.every((text) => text.children.length === 0));
  nodes[1].dispatch("keydown", { key: "Escape" });
  assert.equal(engine.selection(), null);
  assert.equal(view.status.textContent, "Sélectionnez une étape du flux.");
  nodes[2].dispatch("keydown", { key: "Enter" });
  assert.equal(engine.selection().nodeId, "c");
  nodes[2].dispatch("keydown", { key: " " });
  assert.equal(engine.selection(), null);
  engine.destroy();
  assert.equal(rendered(view.host).svg, null);
});

test("scène refusée ou absente : repli conservé et message", () => {
  const broken = { ...SCENE, edges: [{ ...SCENE.edges[0], target: "absent" }] };
  for (const text of ["", "{", JSON.stringify(broken)]) {
    const view = page(text);
    assert.equal(mountDebugFlow(view.root), null);
    assert.equal(view.fallback.hidden, false);
    assert.match(view.status.textContent, /Vue interactive indisponible/);
    assert.equal(rendered(view.host).svg, null);
  }
  const empty = container();
  assert.equal(mountDebugFlow(empty), null);
});

test("le client ne contourne pas le moteur", async () => {
  const source = await readFile(new URL("../../../forge_design/web/static/debug-flow.js", import.meta.url), "utf8");
  assert.match(source, /from "\.\/graphics\/engine\.js"/);
  for (const forbidden of ["createElementNS", "innerHTML", "data-node-id", "classList", "fetch(", "eval(", "viewBox", "zoom", "panBy", "fit(", "home(", "resize(", "wheel", "pointer", "detailLevel", "gx-detail", "levels", "minimap", "centerAt", "gx-minimap", "points"]) {
    assert.ok(!source.includes(forbidden), forbidden);
  }
});
