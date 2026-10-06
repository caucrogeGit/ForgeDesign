// Déplacement de nœuds (FD-GRAPHICS-EDIT-001) : opt-in runtime, coordonnées monde,
// seuil écran, aperçu O(degré), annulation, clavier, isolation. Aucun HTTP ici :
// le moteur signale une intention, le client décide.
import assert from "node:assert/strict";
import { test } from "node:test";

import { DRAG_THRESHOLD, MOVE_SHORTCUTS, createGraphicEngine } from "../../../forge_design/web/static/graphics/engine.js";
import { container, rendered, sized } from "./fake-dom.mjs";

// A (100,100) → B (500,100) avec deux points intermédiaires ; C → A (flèche) ; B → C.
function scene() {
  const box = (id, x, y) => ({ id, label: `Nœud ${id}`, rect: { x, y, width: 80, height: 40 } });
  return {
    width: 1000,
    height: 600,
    nodes: [box("A", 100, 100), box("B", 500, 100), box("C", 300, 400)],
    edges: [
      {
        id: "A-B",
        source: "A",
        target: "B",
        points: [{ x: 180, y: 120 }, { x: 300, y: 120 }, { x: 300, y: 60 }, { x: 500, y: 120 }],
      },
      {
        id: "C-A",
        source: "C",
        target: "A",
        points: [{ x: 340, y: 400 }, { x: 140, y: 300 }, { x: 140, y: 140 }],
        presentation: { arrow: "end" },
      },
      { id: "B-C", source: "B", target: "C", points: [{ x: 540, y: 140 }, { x: 340, y: 400 }] },
    ],
  };
}

function setup({ moves = [], canMove = (node) => node.id !== "C", onMove, constrain, keyboardStep = 20, withMove = true } = {}) {
  const host = container();
  const options = withMove
    ? {
        nodeMove: {
          canMove,
          keyboardStep,
          constrain,
          onMove:
            onMove ??
            ((move) => {
              moves.push(move);
              return false;
            }),
        },
      }
    : {};
  const engine = createGraphicEngine(host, scene(), options);
  // Zone 500 × 300 : le fit donne l'échelle 0,48 (marge 16 px).
  sized(host, engine, 500, 300);
  const view = rendered(host);
  const area = host.querySelector(".gx-viewport");
  const byId = (id) => view.nodes.find((element) => element.getAttribute("aria-label") === `Nœud ${id}`);
  const edgeOf = (id) => view.edges[["A-B", "C-A", "B-C"].indexOf(id)];
  return { host, engine, view, area, byId, edgeOf, moves };
}

// Point écran (relatif à la zone) d'un point monde, d'après l'état du viewport.
function screen(engine, world) {
  const { scale, x, y } = engine.viewport();
  return { clientX: (world.x - x) * scale, clientY: (world.y - y) * scale };
}

function drag(ctx, id, fromWorld, steps, { end = "pointerup" } = {}) {
  const start = screen(ctx.engine, fromWorld);
  ctx.byId(id).dispatch("pointerdown", { ...start, pointerId: 7 });
  for (const [dx, dy] of steps) {
    ctx.area.dispatch("pointermove", { clientX: start.clientX + dx, clientY: start.clientY + dy, pointerId: 7 });
  }
  if (end) {
    const [dx, dy] = steps.at(-1) ?? [0, 0];
    return ctx.area.dispatch(end, { clientX: start.clientX + dx, clientY: start.clientY + dy, pointerId: 7 });
  }
  return null;
}

const pointsOf = (edge) => edge.querySelector(".gx-edge-path").getAttribute("points");
const close = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-9, `${actual} ≠ ${expected}`);

test("sans nodeMove : aucun nœud déplaçable, comportement inchangé", () => {
  const ctx = setup({ withMove: false });
  assert.deepEqual(ctx.engine.movableNodes(), []);
  const before = ctx.engine.viewport();
  drag(ctx, "A", { x: 140, y: 120 }, [[30, 0], [60, 10]]);
  assert.equal(ctx.byId("A").getAttribute("transform"), null);
  assert.equal(ctx.byId("A").getAttribute("aria-keyshortcuts"), null);
  assert.ok(!ctx.byId("A").classList.contains("gx-movable"));
  // Un appui sur un nœud n'est jamais un pan.
  assert.deepEqual(ctx.engine.viewport(), before);
  ctx.byId("A").dispatch("click");
  assert.equal(ctx.engine.selection().nodeId, "A");
  assert.equal(ctx.engine.movePreview(), null);
});

test("options invalides refusées ; clavier obligatoire pour annoncer un déplacement", () => {
  const ok = { canMove: () => true, onMove: () => false, keyboardStep: 10 };
  for (const nodeMove of [
    "oui",
    { ...ok, canMove: undefined },
    { ...ok, onMove: null },
    { ...ok, constrain: 3 },
    { ...ok, keyboardStep: undefined },
    { ...ok, keyboardStep: 0 },
    { ...ok, keyboardStep: Number.NaN },
  ]) {
    assert.throws(() => createGraphicEngine(container(), scene(), { nodeMove }), TypeError);
  }
});

test("opt-in par nœud : classe et raccourcis annoncés seulement sur les nœuds choisis", () => {
  const ctx = setup({ canMove: (node) => node.id === "B" || node.id === "A" });
  assert.deepEqual(ctx.engine.movableNodes(), ["A", "B"]);
  for (const id of ["A", "B"]) {
    assert.ok(ctx.byId(id).classList.contains("gx-movable"));
    assert.equal(ctx.byId(id).getAttribute("aria-keyshortcuts"), MOVE_SHORTCUTS);
  }
  assert.ok(!ctx.byId("C").classList.contains("gx-movable"));
  assert.equal(ctx.byId("C").getAttribute("aria-keyshortcuts"), null);
  // canMove qui lève ou ne rend pas true : non déplaçable.
  const strict = setup({ canMove: (node) => (node.id === "A" ? 1 : node.id === "B" ? true : boom()) });
  assert.deepEqual(strict.engine.movableNodes(), ["B"]);
});

function boom() {
  throw new Error("client");
}

test("clic sans mouvement : sélection, aucune intention", () => {
  const ctx = setup();
  drag(ctx, "A", { x: 140, y: 120 }, []);
  ctx.byId("A").dispatch("click");
  assert.equal(ctx.engine.selection().nodeId, "A");
  assert.equal(ctx.moves.length, 0);
  assert.equal(ctx.area.captured.size, 0);
});

test("seuil écran constant : sous le seuil, clic ; au-delà, glisser — quel que soit le zoom", () => {
  for (const factor of [1, 3, 0.2]) {
    const ctx = setup();
    ctx.engine.zoomAt({ x: 250, y: 150 }, factor);
    const below = DRAG_THRESHOLD - 0.5;
    drag(ctx, "A", { x: 140, y: 120 }, [[below * 0.6, below * 0.8]]);
    assert.equal(ctx.moves.length, 0, `zoom ${factor}`);
    assert.equal(ctx.byId("A").getAttribute("transform"), null);
    drag(ctx, "A", { x: 140, y: 120 }, [[DRAG_THRESHOLD, 0], [DRAG_THRESHOLD + 1, 0]]);
    assert.equal(ctx.moves.length, 1, `zoom ${factor}`);
  }
});

test("glisser : une seule intention, en coordonnées monde, aperçu du nœud et des extrémités", () => {
  let previewed = null;
  const ctx = setup({
    onMove(move) {
      previewed = ctx.engine.movePreview();
      ctx.moves.push(move);
      return new Promise(() => {});
    },
  });
  const sceneBefore = JSON.stringify(ctx.engine.scene());
  const viewBefore = ctx.engine.viewport();
  const { scale } = viewBefore;
  const steps = Array.from({ length: 100 }, (_, i) => [(i + 1) * 0.6, (i + 1) * 0.3]);
  drag(ctx, "A", { x: 140, y: 120 }, steps);
  assert.equal(ctx.moves.length, 1);
  const [move] = ctx.moves;
  assert.equal(move.nodeId, "A");
  assert.equal(move.input, "pointer");
  close(move.delta.x, 60 / scale);
  close(move.delta.y, 30 / scale);
  assert.deepEqual(move.from, { x: 100, y: 100 });
  close(move.to.x, 100 + 60 / scale);
  close(move.to.y, 100 + 30 / scale);
  assert.ok(Object.isFrozen(move) && Object.isFrozen(move.delta));
  assert.equal(previewed.state, "submitted");
  // Aperçu : nœud translaté ; A-B (A source) premier point déplacé ; C-A (A cible)
  // dernier point déplacé et flèche recalculée ; points intermédiaires fixes ; B-C intact.
  const { x: dx, y: dy } = move.delta;
  assert.equal(ctx.byId("A").getAttribute("transform"), `translate(${dx} ${dy})`);
  assert.equal(pointsOf(ctx.edgeOf("A-B")), `${180 + dx},${120 + dy} 300,120 300,60 500,120`);
  assert.equal(pointsOf(ctx.edgeOf("C-A")), `340,400 140,300 ${140 + dx},${140 + dy}`);
  assert.notEqual(ctx.edgeOf("C-A").querySelector(".gx-edge-arrow"), null);
  assert.equal(pointsOf(ctx.edgeOf("B-C")), "540,140 340,400");
  assert.equal(ctx.byId("B").getAttribute("transform"), null);
  // Sélection et focus sur le nœud déplacé ; ni pan, ni scène modifiée.
  assert.equal(ctx.engine.selection().nodeId, "A");
  assert.equal(ctx.host.ownerDocument.activeElement, ctx.byId("A"));
  assert.deepEqual(ctx.engine.viewport(), viewBefore);
  assert.equal(JSON.stringify(ctx.engine.scene()), sceneBefore);
  // Le clic qui suit le glisser n'inverse pas la sélection.
  ctx.byId("A").dispatch("click");
  assert.equal(ctx.engine.selection().nodeId, "A");
});

test("zoom et pan : le delta monde suit l'échelle et ignore la position de la vue", () => {
  for (const prepare of [
    (engine) => engine.zoomAt({ x: 100, y: 80 }, 2.5),
    (engine) => engine.panBy(-137, 61),
    (engine) => {
      engine.zoomIn();
      engine.panBy(45, -20);
    },
  ]) {
    const ctx = setup();
    prepare(ctx.engine);
    const { scale } = ctx.engine.viewport();
    drag(ctx, "B", { x: 520, y: 110 }, [[10, 0], [50, -20]]);
    const [move] = ctx.moves;
    close(move.delta.x, 50 / scale);
    close(move.delta.y, -20 / scale);
    assert.deepEqual(move.from, { x: 500, y: 100 });
  }
});

test("constrain : aperçu et intention alignés ; résultat invalide ignoré", () => {
  const snap = (value) => Math.round(value / 40) * 40;
  const ctx = setup({ constrain: ({ delta }) => ({ x: snap(delta.x), y: snap(delta.y) }) });
  const { scale } = ctx.engine.viewport();
  drag(ctx, "A", { x: 140, y: 120 }, [[10, 0], [70 * scale, 15 * scale]]);
  assert.deepEqual({ ...ctx.moves[0].delta }, { x: 80, y: 0 });
  assert.equal(ctx.byId("A").getAttribute("transform"), null);
  // Delta aligné nul : aucune intention, aperçu restauré.
  drag(ctx, "A", { x: 140, y: 120 }, [[10 * scale, 10 * scale]]);
  assert.equal(ctx.moves.length, 1);
  // Contrainte qui lève ou rend un non-nombre : mouvement ignoré, jamais transmis.
  for (const constrain of [boom, () => ({ x: Number.NaN, y: 0 }), () => null, () => ({ x: "1", y: 0 })]) {
    const bad = setup({ constrain });
    drag(bad, "A", { x: 140, y: 120 }, [[50, 50]]);
    assert.equal(bad.moves.length, 0);
    assert.equal(bad.byId("A").getAttribute("transform"), null);
  }
});

test("pointercancel, Échap, perte de capture : aucune intention, rendu autoritaire", () => {
  for (const cancel of [
    (ctx) => ctx.area.dispatch("pointercancel", { pointerId: 7 }),
    (ctx) => ctx.byId("A").dispatch("keydown", { key: "Escape" }),
    (ctx) => ctx.area.dispatch("lostpointercapture", { pointerId: 7 }),
  ]) {
    const ctx = setup();
    ctx.engine.select("A");
    const original = pointsOf(ctx.edgeOf("A-B"));
    drag(ctx, "A", { x: 140, y: 120 }, [[40, 40]], { end: null });
    assert.equal(ctx.engine.movePreview().state, "dragging");
    assert.ok(ctx.area.captured.has(7));
    const escape = cancel(ctx);
    assert.equal(ctx.engine.movePreview(), null);
    assert.equal(ctx.byId("A").getAttribute("transform"), null);
    assert.equal(pointsOf(ctx.edgeOf("A-B")), original);
    assert.equal(pointsOf(ctx.edgeOf("C-A")), "340,400 140,300 140,140");
    if (escape?.type === "keydown") assert.ok(escape.defaultPrevented);
    // La sélection reste ; le relâcher qui suit n'émet rien.
    assert.equal(ctx.engine.selection().nodeId, "A");
    ctx.area.dispatch("pointerup", { pointerId: 7 });
    assert.equal(ctx.moves.length, 0);
    assert.ok(!ctx.area.classList.contains("gx-moving"));
  }
});

test("Échap hors glisser : désélection inchangée", () => {
  const ctx = setup();
  ctx.engine.select("A");
  ctx.byId("A").dispatch("keydown", { key: "Escape" });
  assert.equal(ctx.engine.selection(), null);
});

test("refus du client : rollback ; promesse en attente : aperçu gardé et nouveaux gestes bloqués", async () => {
  let settle;
  const ctx = setup({
    onMove(move) {
      ctx.moves.push(move);
      return new Promise((resolve) => {
        settle = resolve;
      });
    },
  });
  drag(ctx, "A", { x: 140, y: 120 }, [[50, 0]]);
  const transform = ctx.byId("A").getAttribute("transform");
  assert.notEqual(transform, null);
  // Pendant l'attente : ni glisser ni clavier ne soumettent une seconde intention.
  drag(ctx, "B", { x: 520, y: 110 }, [[50, 0]]);
  const key = ctx.byId("A").dispatch("keydown", { key: "ArrowRight", ctrlKey: true, shiftKey: true });
  assert.ok(key.defaultPrevented);
  assert.equal(ctx.moves.length, 1);
  assert.equal(ctx.byId("B").getAttribute("transform"), null);
  assert.equal(ctx.engine.movePreview().state, "submitted");
  settle(false);
  await Promise.resolve();
  assert.equal(ctx.byId("A").getAttribute("transform"), null);
  assert.equal(ctx.engine.movePreview(), null);
  // Rejet : rollback aussi ; onMove qui lève : rollback immédiat.
  const rejected = setup({ onMove: () => Promise.reject(new Error("réseau")) });
  drag(rejected, "A", { x: 140, y: 120 }, [[50, 0]]);
  await Promise.resolve();
  await Promise.resolve();
  assert.equal(rejected.byId("A").getAttribute("transform"), null);
  const thrown = setup({ onMove: boom });
  drag(thrown, "A", { x: 140, y: 120 }, [[50, 0]]);
  assert.equal(thrown.byId("A").getAttribute("transform"), null);
  assert.equal(thrown.engine.movePreview(), null);
});

test("acceptation : l'aperçu reste jusqu'au remplacement de la scène", async () => {
  for (const accepted of [true, Promise.resolve(true)]) {
    const ctx = setup({ onMove: () => accepted });
    drag(ctx, "A", { x: 140, y: 120 }, [[50, 0]]);
    await Promise.resolve();
    assert.notEqual(ctx.byId("A").getAttribute("transform"), null);
    assert.equal(ctx.engine.movePreview().state, "submitted");
    ctx.engine.render();
    assert.equal(ctx.engine.movePreview(), null);
    assert.equal(rendered(ctx.host).nodes[0].getAttribute("transform"), null);
  }
});

test("clavier : Ctrl + Maj + flèche = un pas, une intention ; sans effet hors nœud déplaçable", () => {
  const ctx = setup({ keyboardStep: 40 });
  for (const [key, delta] of [
    ["ArrowRight", { x: 40, y: 0 }],
    ["ArrowLeft", { x: -40, y: 0 }],
    ["ArrowUp", { x: 0, y: -40 }],
    ["ArrowDown", { x: 0, y: 40 }],
  ]) {
    const event = ctx.byId("B").dispatch("keydown", { key, ctrlKey: true, shiftKey: true });
    assert.ok(event.defaultPrevented, key);
    const move = ctx.moves.at(-1);
    assert.deepEqual({ ...move.delta }, delta);
    assert.equal(move.input, "keyboard");
    assert.deepEqual(move.from, { x: 500, y: 100 });
  }
  assert.equal(ctx.moves.length, 4);
  assert.equal(ctx.engine.selection().nodeId, "B");
  // Flèche seule, Alt (historique du navigateur), Ctrl ou Maj seuls (pan), Alt ou Méta
  // en plus, ou nœud non déplaçable : ignoré, et le comportement par défaut est laissé.
  const before = ctx.engine.viewport();
  const ignored = [
    ["B", { key: "ArrowRight" }],
    ["B", { key: "ArrowLeft", altKey: true }],
    ["B", { key: "ArrowRight", ctrlKey: true }],
    ["B", { key: "ArrowRight", ctrlKey: true, shiftKey: true, altKey: true }],
    ["B", { key: "ArrowRight", ctrlKey: true, shiftKey: true, metaKey: true }],
    ["C", { key: "ArrowRight", ctrlKey: true, shiftKey: true }],
  ];
  for (const [id, init] of ignored) {
    const event = ctx.byId(id).dispatch("keydown", init);
    assert.equal(event.defaultPrevented, false, JSON.stringify(init));
  }
  assert.equal(ctx.moves.length, 4);
  // Maj + flèche sur un nœud déplaçable : toujours le pan, jamais un déplacement.
  ctx.byId("B").dispatch("keydown", { key: "ArrowRight", shiftKey: true });
  assert.notDeepEqual(ctx.engine.viewport(), before);
  assert.equal(ctx.moves.length, 4);
  // Le pas passe par constrain (bornes) : un delta nul n'émet rien.
  const bounded = setup({ keyboardStep: 40, constrain: ({ delta }) => ({ x: Math.max(0, delta.x), y: delta.y }) });
  bounded.byId("A").dispatch("keydown", { key: "ArrowLeft", ctrlKey: true, shiftKey: true });
  assert.equal(bounded.moves.length, 0);
});

test("bouton du milieu sur un nœud : pan, jamais un déplacement", () => {
  const ctx = setup();
  const before = ctx.engine.viewport();
  const start = screen(ctx.engine, { x: 140, y: 120 });
  ctx.byId("A").dispatch("pointerdown", { ...start, button: 1, pointerId: 3 });
  ctx.area.dispatch("pointermove", { clientX: start.clientX + 30, clientY: start.clientY, pointerId: 3 });
  ctx.area.dispatch("pointerup", { clientX: start.clientX + 30, clientY: start.clientY, pointerId: 3 });
  assert.equal(ctx.moves.length, 0);
  assert.notDeepEqual(ctx.engine.viewport(), before);
  // Fond : pan toujours disponible.
  const panned = ctx.engine.viewport();
  ctx.area.dispatch("pointerdown", { clientX: 5, clientY: 5, pointerId: 4 });
  ctx.area.dispatch("pointermove", { clientX: 25, clientY: 5, pointerId: 4 });
  ctx.area.dispatch("pointerup", { clientX: 25, clientY: 5, pointerId: 4 });
  assert.notDeepEqual(ctx.engine.viewport(), panned);
  assert.equal(ctx.moves.length, 0);
});

test("deux instances : états de déplacement indépendants", () => {
  const one = setup();
  const two = setup();
  drag(one, "A", { x: 140, y: 120 }, [[50, 0]], { end: null });
  assert.equal(one.engine.movePreview().state, "dragging");
  assert.equal(two.engine.movePreview(), null);
  drag(two, "B", { x: 520, y: 110 }, [[0, 50]]);
  assert.equal(two.moves.length, 1);
  assert.equal(one.moves.length, 0);
  one.area.dispatch("pointerup", { pointerId: 7, clientX: 0, clientY: 0 });
  assert.equal(one.moves.length, 1);
  assert.equal(one.moves[0].nodeId, "A");
  assert.equal(two.moves[0].nodeId, "B");
});

test("destroy pendant un glisser : état libéré, aucune intention", () => {
  const ctx = setup();
  drag(ctx, "A", { x: 140, y: 120 }, [[50, 0]], { end: null });
  ctx.engine.destroy();
  ctx.area.dispatch("pointerup", { pointerId: 7, clientX: 0, clientY: 0 });
  assert.equal(ctx.moves.length, 0);
  assert.throws(() => ctx.engine.movePreview());
});

test("arêtes sans flèche ou boucle : extrémités translatées, rien d'autre", () => {
  const input = scene();
  input.edges.push({ id: "A-A", source: "A", target: "A", points: [{ x: 100, y: 110 }, { x: 60, y: 110 }, { x: 100, y: 130 }] });
  const host = container();
  const moves = [];
  const engine = createGraphicEngine(host, input, {
    nodeMove: { canMove: () => true, keyboardStep: 10, onMove: (move) => moves.push(move) && new Promise(() => {}) },
  });
  sized(host, engine, 500, 300);
  const node = rendered(host).nodes[0];
  node.dispatch("keydown", { key: "ArrowDown", ctrlKey: true, shiftKey: true });
  const loop = rendered(host).edges[3];
  assert.equal(pointsOf(loop), "100,120 60,110 100,140");
  assert.equal(loop.querySelector(".gx-edge-arrow"), null);
});
