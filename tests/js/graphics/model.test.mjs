import assert from "node:assert/strict";
import { test } from "node:test";

import { arrowHead, isFiniteNumber, point, rect } from "../../../forge_design/web/static/graphics/geometry.js";
import {
  GraphicSceneError,
  MAX_GRAPHIC_EDGES,
  MAX_GRAPHIC_LABEL_CHARS,
  MAX_GRAPHIC_NODES,
  validateScene,
} from "../../../forge_design/web/static/graphics/model.js";
import { edge, node, witness } from "./scenes.mjs";

function refused(scene, pattern) {
  assert.throws(() => validateScene(scene), (error) => error instanceof GraphicSceneError && pattern.test(error.message));
}

test("géométrie : nombres finis seulement", () => {
  assert.deepEqual(point(1, 2), { x: 1, y: 2 });
  assert.ok(Object.isFrozen(point(1, 2)));
  for (const bad of [NaN, Infinity, -Infinity, "1", null, undefined, 2e6]) {
    assert.equal(isFiniteNumber(bad) && Math.abs(bad) <= 1e6, false);
    assert.throws(() => point(bad, 0));
  }
  assert.deepEqual(rect(0, 0, 5, 6), { x: 0, y: 0, width: 5, height: 6 });
  for (const [w, h] of [[0, 1], [1, 0], [-1, 1], [1, NaN]]) assert.throws(() => rect(0, 0, w, h));
  assert.equal(arrowHead([point(0, 0), point(0, 0)]), null);
  assert.deepEqual(arrowHead([point(0, 0), point(10, 0)])[0], { x: 10, y: 0 });
});

test("scène nominale : trois nœuds, deux arêtes, copie gelée", () => {
  const input = witness();
  const scene = validateScene(input);
  assert.equal(scene.nodes.length, 3);
  assert.equal(scene.edges.length, 2);
  assert.ok(Object.isFrozen(scene) && Object.isFrozen(scene.nodes[0]) && Object.isFrozen(scene.edges[0].points));
  assert.notEqual(scene.nodes[0], input.nodes[0]);
  input.nodes[0].label = "modifié";
  assert.equal(scene.nodes[0].label, "Node A");
  assert.equal(scene.nodes[0].kind, "node");
  assert.deepEqual(scene.nodes[0].presentation, { variant: "default", tone: "default" });
  assert.deepEqual(scene.edges[0].presentation, { line: "solid", arrow: "end", tone: "default" });
  assert.equal(scene.edges[1].label, null);
});

test("identités dupliquées refusées", () => {
  const scene = witness();
  scene.nodes.push(node("A", 300));
  refused(scene, /nodes\[3\]\.id : identité dupliquée/);
  const edges = witness();
  edges.edges.push(edge("A-B", "B", "C"));
  refused(edges, /edges\[2\]\.id : identité dupliquée/);
});

test("arête vers un nœud absent : scène refusée", () => {
  const scene = witness();
  scene.edges.push(edge("A-Z", "A", "Z"));
  refused(scene, /edges\[2\]\.target : nœud inexistant/);
  const source = witness();
  source.edges[0].source = "Z";
  refused(source, /edges\[0\]\.source : nœud inexistant/);
});

test("forme stricte : clés inconnues, types, nombres non finis", () => {
  const cases = [
    [{ ...witness(), extra: 1 }, /clé inconnue/],
    [{ ...witness(), nodes: {} }, /tableau attendu/],
    [{ ...witness(), width: NaN }, /width/],
    [{ ...witness(), height: -1 }, /height/],
    [{ ...witness(), width: Infinity }, /width/],
  ];
  for (const [scene, pattern] of cases) refused(scene, pattern);
  const mutations = [
    (s) => (s.nodes[0].style = "fill:red"),
    (s) => (s.nodes[0].rect.width = -5),
    (s) => (s.nodes[0].rect.x = NaN),
    (s) => (s.nodes[0].rect.y = Infinity),
    (s) => (s.nodes[0].id = 1),
    (s) => (s.nodes[0].id = ""),
    (s) => (s.nodes[0].label = null),
    (s) => (s.nodes[0].kind = "route"),
    (s) => (s.nodes[0].presentation = { variant: "red" }),
    (s) => (s.nodes[0].presentation = { css: "fill:red" }),
    (s) => (s.nodes[0].data = { "__proto__x": "x" }),
    (s) => (s.nodes[0].lines = ["a", "b", "c", "d", "e"]),
    (s) => (s.edges[0].points = [{ x: 0, y: 0 }]),
    (s) => (s.edges[0].points[1].y = NaN),
    (s) => (s.edges[0].presentation = { line: "dotted" }),
    (s) => (s.edges[0].labelAt = { x: 1 }),
  ];
  for (const mutate of mutations) {
    const scene = witness();
    mutate(scene);
    assert.throws(() => validateScene(scene), GraphicSceneError, mutate.toString());
  }
  for (const bad of [null, [], "scene", Object.create({ inherited: true })]) refused(bad, /objet attendu|clé/);
});

test("limites : borne et borne + 1", () => {
  const many = (count) => Array.from({ length: count }, (_, i) => node(`n${i}`));
  const atNodes = { width: 10, height: 10, nodes: many(MAX_GRAPHIC_NODES), edges: [] };
  assert.equal(validateScene(atNodes).nodes.length, MAX_GRAPHIC_NODES);
  refused({ ...atNodes, nodes: many(MAX_GRAPHIC_NODES + 1) }, /au plus/);
  const edges = (count) => Array.from({ length: count }, (_, i) => edge(`e${i}`, "n0", "n1"));
  const base = { width: 10, height: 10, nodes: many(2) };
  assert.equal(validateScene({ ...base, edges: edges(MAX_GRAPHIC_EDGES) }).edges.length, MAX_GRAPHIC_EDGES);
  refused({ ...base, edges: edges(MAX_GRAPHIC_EDGES + 1) }, /au plus/);
  const label = witness();
  label.nodes[0].label = "x".repeat(MAX_GRAPHIC_LABEL_CHARS);
  validateScene(label);
  label.nodes[0].label += "x";
  refused(label, /au plus/);
});

test("aucune connaissance de Route Explorer ni d'un domaine", async () => {
  const { readFile, readdir } = await import("node:fs/promises");
  const directory = new URL("../../../forge_design/web/static/graphics/", import.meta.url);
  for (const name of await readdir(directory)) {
    const source = (await readFile(new URL(name, directory), "utf8")).toLowerCase();
    // Mots entiers : AbortController n'est pas un contrôleur Forge.
    // « route » est absent : le moteur ne connaît pas de route HTTP Forge.
    for (const word of ["route", "route-explorer", "route explorer", "handler", "controller", "template", "circuit", "resistor", "entity", "relation", "pivot", "many_to_many", "many_to_one", "table", "field", "network"]) {
      assert.ok(!new RegExp(`\\b${word}\\b`).test(source), `${name} contient « ${word} »`);
    }
    for (const word of ["innerhtml", "eval(", "new function", "fetch(", "localstorage", "document.cookie"]) {
      assert.ok(!source.includes(word), `${name} contient « ${word} »`);
    }
  }
});
