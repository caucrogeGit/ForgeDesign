import assert from "node:assert/strict";
import { test } from "node:test";

import { GraphicSceneError, validateScene } from "../../../forge_design/web/static/graphics/model.js";
import { createSelection, indexScene, neighbourhood } from "../../../forge_design/web/static/graphics/scene.js";
import { edge, node, witness } from "./scenes.mjs";

test("incidence directe et voisins", () => {
  const index = indexScene(validateScene(witness()));
  assert.deepEqual(neighbourhood(index, "A"), { nodeId: "A", edgeIds: ["A-B", "A-C"], neighbourIds: ["B", "C"] });
  assert.deepEqual(neighbourhood(index, "B"), { nodeId: "B", edgeIds: ["A-B"], neighbourIds: ["A"] });
  assert.deepEqual(neighbourhood(index, "C").neighbourIds, ["A"]);
});

test("aucune analyse transitive ; boucle sur soi-même sans voisin", () => {
  const scene = {
    width: 10,
    height: 10,
    nodes: [node("A"), node("B"), node("C")],
    edges: [edge("ab", "A", "B"), edge("bc", "B", "C"), edge("cc", "C", "C")],
  };
  const index = indexScene(validateScene(scene));
  assert.deepEqual(neighbourhood(index, "A").neighbourIds, ["B"]);
  assert.deepEqual(neighbourhood(index, "C"), { nodeId: "C", edgeIds: ["bc", "cc"], neighbourIds: ["B"] });
});

test("sélection simple : remplacement, effacement, identité inconnue refusée", () => {
  const selection = createSelection(indexScene(validateScene(witness())));
  assert.equal(selection.current(), null);
  assert.equal(selection.select("B").nodeId, "B");
  assert.equal(selection.select("C").nodeId, "C");
  assert.deepEqual(selection.current().edgeIds, ["A-C"]);
  assert.throws(() => selection.select("Z"), GraphicSceneError);
  assert.equal(selection.current().nodeId, "C");
  assert.equal(selection.clear(), null);
  assert.equal(selection.current(), null);
  assert.ok(Object.isFrozen(selection));
});

test("deux index indépendants", () => {
  const first = createSelection(indexScene(validateScene(witness())));
  const second = createSelection(indexScene(validateScene(witness())));
  first.select("A");
  assert.equal(second.current(), null);
});

test("incidence en O(degré) : index de plusieurs milliers d'arêtes", () => {
  const nodes = Array.from({ length: 2000 }, (_, i) => node(`n${i}`));
  const edges = Array.from({ length: 4000 }, (_, i) => edge(`e${i}`, `n${i % 2000}`, `n${(i * 7 + 1) % 2000}`));
  const index = indexScene(validateScene({ width: 10, height: 10, nodes, edges }));
  const total = [...index.incident.values()].reduce((sum, list) => sum + list.length, 0);
  assert.ok(total <= 2 * edges.length);
  assert.ok(neighbourhood(index, "n0").edgeIds.length < 10);
});
