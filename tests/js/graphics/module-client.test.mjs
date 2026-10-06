// Client générique des ressources de modules : moteur partagé, aucun vocabulaire de module.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

import { bootModuleResource, mountModuleResource } from "../../../forge_design/web/static/module-resource.js";
import { container, rendered } from "./fake-dom.mjs";

const HOSTILE = "</script><svg onload=alert(1)>";

function page(sceneText, editorContext = undefined) {
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
  const editorStatus = make("p", "data-editor-status");
  editorStatus.hidden = true;
  if (editorContext !== undefined) {
    const editor = make("script", "data-module-editor");
    editor.textContent = typeof editorContext === "string" ? editorContext : JSON.stringify(editorContext);
    root.append(editor, editorStatus);
  }
  return { root, host, fallback, status, editorStatus };
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
  for (const forbidden of ["createElementNS", "innerHTML", "fetch(", "eval(", "/modules/", "zoom", "minimap", "detailLevel", "viewBox", "circuit", "witness", "network", "component", "grid"]) {
    assert.ok(!source.toLowerCase().includes(forbidden.toLowerCase()), forbidden);
  }
  // FD-GRAPHICS-EDIT-001 : un seul import dynamique, celui de l'URL fournie par l'hôte.
  assert.equal(source.split("import(").length - 1, 1);
  assert.match(source, /load = \(url\) => import\(url\)/);
});

const CONTEXT = {
  script: "/modules/witness/assets/witness-editor.js",
  type: "document",
  path: "mvc/witness/a.witness.json",
  revision: "a".repeat(64),
  actions: { "move-node": "/modules/witness/actions/move-node" },
  config: { step: 10, nested: { list: [1, 2] } },
};

function editorScript(record, overrides = {}) {
  return {
    createResourceEditor(context) {
      record.context = context;
      return {
        nodeMove: { canMove: (node) => node.id !== "C", keyboardStep: 10, onMove: () => false },
        attach(engine) {
          record.engine = engine;
        },
        ...overrides,
      };
    },
  };
}

test("boot sans contexte d'édition : consultation, aucun chargement", async () => {
  const view = page(JSON.stringify(SCENE));
  let loaded = 0;
  const engine = await bootModuleResource(view.root, { load: async () => loaded++ });
  assert.ok(engine && view.fallback.hidden);
  assert.equal(loaded, 0);
  assert.deepEqual(engine.movableNodes(), []);
});

test("boot avec contexte : script de l'hôte importé, contexte gelé, nodeMove et attach", async () => {
  const view = page(JSON.stringify(SCENE), CONTEXT);
  const record = {};
  const urls = [];
  const engine = await bootModuleResource(view.root, {
    load: async (url) => {
      urls.push(url);
      return editorScript(record);
    },
  });
  assert.deepEqual(urls, [CONTEXT.script]);
  assert.equal(record.engine, engine);
  assert.deepEqual(engine.movableNodes(), ["A", "B"]);
  const { context } = record;
  assert.equal(context.resourceType, "document");
  assert.equal(context.path, CONTEXT.path);
  assert.equal(context.revision, CONTEXT.revision);
  assert.deepEqual({ ...context.actions }, CONTEXT.actions);
  assert.deepEqual(context.config.nested.list, [1, 2]);
  for (const value of [context, context.actions, context.config, context.config.nested, context.config.nested.list]) {
    assert.ok(Object.isFrozen(value));
  }
  assert.equal(view.editorStatus.hidden, true);
  context.announce("Message du module");
  assert.equal(view.editorStatus.hidden, false);
  assert.equal(view.editorStatus.textContent, "Message du module");
});

test("échecs du script : consultation seule et indisponibilité annoncée", async () => {
  const failures = [
    ["chargement", async () => Promise.reject(new Error("404"))],
    ["export absent", async () => ({})],
    ["création", async () => ({ createResourceEditor: () => { throw new Error("config"); } })],
    ["attach", async () => editorScript({}, { attach: () => { throw new Error("attach"); } })],
    ["nodeMove refusé", async () => editorScript({}, { nodeMove: { canMove: () => true, onMove: () => false } })],
  ];
  for (const [what, load] of failures) {
    const view = page(JSON.stringify(SCENE), CONTEXT);
    const engine = await bootModuleResource(view.root, { load });
    assert.ok(engine, what);
    assert.deepEqual(engine.movableNodes(), [], what);
    assert.equal(view.host.querySelectorAll(".gx-frame").length, 1, what);
    assert.equal(view.editorStatus.hidden, false, what);
    assert.match(view.editorStatus.textContent, /^Édition indisponible .* consultation seule\.$/, what);
    assert.ok(view.fallback.hidden, what);
  }
});

test("contexte refusé : URL hors du serveur, champs absents ou JSON invalide", async () => {
  const forged = [
    { ...CONTEXT, script: "//evil.example/x.js" },
    { ...CONTEXT, script: "https://evil.example/x.js" },
    { ...CONTEXT, script: "data:text/javascript,alert(1)" },
    { ...CONTEXT, script: "/\\evil.example/x.js" },
    { ...CONTEXT, actions: { move: "javascript:alert(1)" } },
    { ...CONTEXT, revision: "" },
    { ...CONTEXT, path: 3 },
    "{",
  ];
  for (const context of forged) {
    const view = page(JSON.stringify(SCENE), context);
    let loaded = 0;
    const engine = await bootModuleResource(view.root, { load: async () => loaded++ });
    assert.equal(loaded, 0, JSON.stringify(context));
    assert.deepEqual(engine.movableNodes(), []);
    assert.match(view.editorStatus.textContent, /Édition indisponible/);
  }
});
