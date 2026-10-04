// Témoin test-only : trois formes de scène (structure multi-colonnes, deux colonnes,
// flux séquentiel) dans trois instances simultanées, sans aucun état partagé.
import assert from "node:assert/strict";
import { test } from "node:test";

import { createGraphicEngine } from "../../../forge_design/web/static/graphics/engine.js";
import { container, rendered, sized } from "./fake-dom.mjs";

function box(id, x, y, variant, lines = ["Ligne", id, "Détail"]) {
  return { id, label: `Nœud ${id}`, rect: { x, y, width: 220, height: 90 }, lines, levels: { overview: [], normal: [0, 1] }, presentation: { variant } };
}

function link(source, target, points) {
  return { id: `${source}-${target}`, source, target, points, presentation: { arrow: "end" } };
}

const SHAPES = {
  // Colonnes et couloirs (forme Route).
  columns: {
    width: 2120,
    height: 1066,
    nodes: [box("r", 30, 300, "category-1"), box("h", 390, 300, "category-2"), box("t", 1830, 300, "category-4")],
    edges: [link("r", "h", [{ x: 250, y: 345 }, { x: 270, y: 345 }, { x: 270, y: 54 }, { x: 370, y: 54 }, { x: 370, y: 345 }, { x: 390, y: 345 }]),
      link("h", "t", [{ x: 610, y: 345 }, { x: 1830, y: 345 }])],
  },
  // Deux colonnes avec arête de retour (forme Entity).
  pair: {
    width: 780,
    height: 740,
    nodes: [box("a", 40, 180, "category-1"), box("b", 480, 180, "category-2")],
    edges: [link("a", "b", [{ x: 260, y: 225 }, { x: 480, y: 225 }]), link("b", "a", [{ x: 700, y: 225 }, { x: 720, y: 225 }, { x: 720, y: 30 }, { x: 20, y: 30 }, { x: 20, y: 225 }, { x: 40, y: 225 }])],
  },
  // Flux séquentiel horizontal (forme Debug).
  sequence: {
    width: 860,
    height: 130,
    nodes: [box("s1", 20, 20, "category-1", ["Étape"]), box("s2", 320, 20, "category-3", ["Étape"]), box("s3", 620, 20, "category-5", ["Étape"])],
    edges: [link("s1", "s2", [{ x: 240, y: 65 }, { x: 320, y: 65 }]), link("s2", "s3", [{ x: 540, y: 65 }, { x: 620, y: 65 }])],
  },
};

test("trois instances : sélection, viewport, niveau et minicarte indépendants", () => {
  const instances = Object.fromEntries(
    Object.entries(SHAPES).map(([name, scene]) => {
      const host = container();
      const engine = createGraphicEngine(host, { ...scene, nodes: scene.nodes.map((node) => ({ ...node, levels: { overview: [], normal: [0] } })) });
      sized(host, engine, 800, 480);
      return [name, { host, engine }];
    }),
  );
  const snapshot = () =>
    Object.fromEntries(
      Object.entries(instances).map(([name, { engine }]) => [
        name,
        { selection: engine.selection(), viewport: engine.viewport(), level: engine.detailLevel(), minimap: engine.minimap() },
      ]),
    );
  const initial = snapshot();
  assert.deepEqual(
    Object.values(initial).map((item) => item.level),
    ["overview", "normal", "detail"],
    "même moteur, niveaux différents selon l'échelle de chaque scène",
  );
  assert.ok(Object.values(initial).every((item) => item.minimap.visible === false));
  // Interaction sur la séquence seulement.
  const { engine, host } = instances.sequence;
  rendered(host).nodes[1].dispatch("click");
  engine.zoomIn();
  engine.zoomIn();
  engine.panBy(-200, 0);
  const after = snapshot();
  assert.deepEqual(engine.selection().neighbourIds, ["s1", "s3"]);
  assert.equal(after.sequence.minimap.visible, true);
  assert.deepEqual(after.columns, initial.columns);
  assert.deepEqual(after.pair, initial.pair);
  // Interaction sur les colonnes : la séquence ne bouge pas.
  instances.columns.engine.zoomIn();
  instances.columns.engine.select("h");
  const last = snapshot();
  assert.deepEqual(last.sequence, after.sequence);
  assert.deepEqual(last.pair, initial.pair);
  for (const { engine: each } of Object.values(instances)) each.destroy();
});
