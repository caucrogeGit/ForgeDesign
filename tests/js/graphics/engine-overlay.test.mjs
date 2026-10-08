// Calques monde et onViewChange (FD-GRAPHICS-EDIT-002) : racine dédiée, soumise au
// viewport, survivant au rendu, isolée par instance, retirée au destroy ; état de vue
// notifié seulement quand il change. Aucun vocabulaire de domaine.
import assert from "node:assert/strict";
import { test } from "node:test";

import { createGraphicEngine } from "../../../forge_design/web/static/graphics/engine.js";
import { SVG, container, rendered, sized } from "./fake-dom.mjs";

function scene() {
  const box = (id, x, y) => ({ id, label: `Nœud ${id}`, rect: { x, y, width: 80, height: 40 } });
  return {
    width: 1000,
    height: 600,
    nodes: [box("A", 100, 100), box("B", 500, 100)],
    edges: [{ id: "A-B", source: "A", target: "B", points: [{ x: 180, y: 120 }, { x: 500, y: 120 }] }],
  };
}

function setup(options = {}) {
  const host = container();
  const engine = createGraphicEngine(host, scene(), options);
  sized(host, engine, 500, 300);
  return { host, engine, area: host.querySelector(".gx-viewport") };
}

const svgOf = (host) => rendered(host).svg;

test("sans calque : aucun élément ajouté au rendu", () => {
  const { host } = setup();
  assert.equal(svgOf(host).querySelectorAll(".gx-overlay").length, 0);
});

test("addOverlay : racine dédiée vide après les nœuds, nom accessible borné", () => {
  const { host, engine } = setup();
  const overlay = engine.addOverlay({ label: "  Poignées du client  " });
  const svg = svgOf(host);
  assert.equal(overlay.root.parentNode, svg);
  assert.equal(svg.children.at(-1), overlay.root);
  assert.equal(overlay.root.namespace, SVG);
  assert.ok(overlay.root.classList.contains("gx-overlay"));
  assert.equal(overlay.root.getAttribute("role"), "group");
  assert.equal(overlay.root.getAttribute("aria-label"), "Poignées du client");
  assert.equal(overlay.root.children.length, 0);
  assert.ok(Object.isFrozen(overlay));
  const long = engine.addOverlay({ label: "x".repeat(500) });
  assert.equal(long.root.getAttribute("aria-label").length, 200);
  assert.equal(engine.addOverlay().root.getAttribute("aria-label"), null);
  for (const bad of [null, "calque", 3]) assert.throws(() => engine.addOverlay(bad), TypeError);
});

test("le contenu client survit au rendu ; l'ordre de création est conservé", () => {
  const { host, engine } = setup();
  const first = engine.addOverlay();
  const second = engine.addOverlay();
  const mark = host.ownerDocument.createElementNS(SVG, "circle");
  first.root.append(mark);
  const before = svgOf(host);
  engine.render();
  const after = svgOf(host);
  assert.notEqual(after, before);
  assert.deepEqual(after.children.slice(-2), [first.root, second.root]);
  assert.equal(first.root.children[0], mark);
});

test("remove() retire le calque, idempotent ; destroy() retire tous les calques", () => {
  const { host, engine } = setup();
  const one = engine.addOverlay();
  const two = engine.addOverlay();
  one.remove();
  one.remove();
  assert.equal(one.root.parentNode, null);
  engine.render();
  assert.deepEqual(svgOf(host).querySelectorAll(".gx-overlay"), [two.root]);
  engine.destroy();
  assert.equal(two.root.parentNode, null);
  assert.throws(() => engine.addOverlay(), /détruit/);
  assert.throws(() => engine.worldAt({ clientX: 0, clientY: 0 }), /détruit/);
  two.remove();
});

test("deux instances : calques et notifications indépendants", () => {
  const seen = { a: [], b: [] };
  const a = setup({ onViewChange: (state) => seen.a.push(state) });
  const b = setup({ onViewChange: (state) => seen.b.push(state) });
  const overlayA = a.engine.addOverlay();
  const overlayB = b.engine.addOverlay();
  assert.equal(svgOf(a.host).querySelectorAll(".gx-overlay")[0], overlayA.root);
  assert.equal(svgOf(b.host).querySelectorAll(".gx-overlay")[0], overlayB.root);
  const countB = seen.b.length;
  a.engine.zoomIn();
  assert.equal(seen.b.length, countB);
  a.engine.destroy();
  assert.equal(overlayB.root.parentNode, svgOf(b.host));
});

test("un appui sur un calque n'est jamais un pan ; le fond reste un pan", () => {
  const { host, engine, area } = setup();
  const overlay = engine.addOverlay();
  const item = host.ownerDocument.createElementNS(SVG, "circle");
  overlay.root.append(item);
  const before = engine.viewport();
  item.dispatch("pointerdown", { clientX: 100, clientY: 100, pointerId: 3 });
  area.dispatch("pointermove", { clientX: 160, clientY: 140, pointerId: 3 });
  area.dispatch("pointerup", { clientX: 160, clientY: 140, pointerId: 3 });
  assert.deepEqual(engine.viewport(), before);
  svgOf(host).dispatch("pointerdown", { clientX: 100, clientY: 100, pointerId: 4 });
  area.dispatch("pointermove", { clientX: 160, clientY: 140, pointerId: 4 });
  area.dispatch("pointerup", { clientX: 160, clientY: 140, pointerId: 4 });
  assert.notDeepEqual(engine.viewport(), before);
});

test("onViewChange : état initial, zoom, pan, fit, resize, niveau ; rien sans changement", () => {
  const states = [];
  const { host, engine } = setup({ onViewChange: (state) => states.push(state) });
  const initial = states.at(-1);
  assert.ok(Object.isFrozen(initial));
  assert.deepEqual(Object.keys(initial), ["scale", "x", "y", "width", "height", "detailLevel"]);
  assert.equal(initial.width, 500);
  assert.equal(initial.detailLevel, engine.detailLevel());
  let count = states.length;
  // Aucun changement observable : aucune notification.
  engine.render();
  engine.panBy(0, 0);
  engine.fit();
  assert.equal(states.length, count);
  engine.zoomIn();
  assert.equal(states.length, ++count);
  assert.ok(states.at(-1).scale > initial.scale);
  engine.panBy(30, 0);
  assert.equal(states.length, ++count);
  engine.fit();
  assert.equal(states.length, ++count);
  assert.deepEqual(states.at(-1), initial);
  sized(host, engine, 800, 400);
  assert.equal(states.length, ++count);
  assert.equal(states.at(-1).width, 800);
  // Le niveau de détail fait partie de l'état notifié.
  // Jusqu'à l'échelle minimale : au-delà, zoomOut ne change plus rien.
  let previous;
  do {
    previous = engine.viewport().scale;
    engine.zoomOut();
  } while (engine.viewport().scale !== previous);
  assert.equal(states.at(-1).detailLevel, engine.detailLevel());
  assert.equal(states.at(-1).detailLevel, "overview");
  const atMinimum = states.length;
  engine.zoomOut();
  engine.zoomOut();
  assert.equal(states.length, atMinimum);
});

test("onViewChange : une erreur du client ne casse pas le moteur", () => {
  let calls = 0;
  const { engine } = setup({
    onViewChange: () => {
      calls += 1;
      throw new Error("client");
    },
  });
  engine.zoomIn();
  assert.ok(calls >= 2);
  assert.ok(engine.viewport().scale > 0);
});

test("worldAt : point monde sous zoom et pan ; entrée invalide refusée", () => {
  const { engine } = setup();
  engine.zoomIn();
  engine.panBy(-40, 25);
  const { scale, x, y } = engine.viewport();
  const world = engine.worldAt({ clientX: 120, clientY: 80 });
  assert.ok(Object.isFrozen(world));
  assert.ok(Math.abs(world.x - (x + 120 / scale)) < 1e-9);
  assert.ok(Math.abs(world.y - (y + 80 / scale)) < 1e-9);
  for (const bad of [null, {}, { clientX: 1 }, { clientX: Number.NaN, clientY: 0 }, { clientX: "1", clientY: 2 }]) {
    assert.throws(() => engine.worldAt(bad), TypeError);
  }
});

test("une touche déjà traitée par un calque n'est pas reprise par le moteur", () => {
  const { host, engine } = setup();
  const overlay = engine.addOverlay();
  const item = host.ownerDocument.createElementNS(SVG, "g");
  overlay.root.append(item);
  item.addEventListener("keydown", (event) => event.preventDefault());
  engine.select("A");
  item.dispatch("keydown", { key: "Escape" });
  assert.equal(engine.selection().nodeId, "A");
  const before = engine.viewport();
  item.dispatch("keydown", { key: "ArrowRight", shiftKey: true });
  assert.deepEqual(engine.viewport(), before);
  // Sans traitement préalable, Échap reste la désélection du moteur.
  svgOf(host).dispatch("keydown", { key: "Escape" });
  assert.equal(engine.selection(), null);
});
