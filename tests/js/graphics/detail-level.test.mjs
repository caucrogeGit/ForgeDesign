// Niveau de détail : politique pure selon l'échelle et contrat `levels` de la scène.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  DETAIL_LEVELS,
  HYSTERESIS_PX,
  PRIMARY_TEXT_PX,
  SCENE_TEXT_SIZE,
  SECONDARY_TEXT_PX,
  THRESHOLDS,
  detailLevelForScale,
} from "../../../forge_design/web/static/graphics/detail-level.js";
import { MAX_GRAPHIC_LINES, validateScene } from "../../../forge_design/web/static/graphics/model.js";
import { HOSTILE, node, witness } from "./scenes.mjs";

const T = THRESHOLDS;
const EPS = 1e-9;

test("trois niveaux génériques, seuils dérivés des tailles écran mesurées", () => {
  assert.deepEqual(DETAIL_LEVELS, ["overview", "normal", "detail"]);
  assert.ok(Object.isFrozen(DETAIL_LEVELS) && Object.isFrozen(THRESHOLDS));
  assert.equal(SCENE_TEXT_SIZE, 12);
  assert.equal(T.normalAbove, PRIMARY_TEXT_PX / 12);
  assert.equal(T.detailAbove, SECONDARY_TEXT_PX / 12);
  assert.equal(T.overviewBelow, (PRIMARY_TEXT_PX - HYSTERESIS_PX) / 12);
  assert.equal(T.normalBelow, (SECONDARY_TEXT_PX - HYSTERESIS_PX) / 12);
  assert.ok(T.overviewBelow < T.normalAbove && T.normalAbove < T.normalBelow && T.normalBelow < T.detailAbove);
});

test("sans historique : échelle faible, intermédiaire, forte", () => {
  assert.equal(detailLevelForScale(0.02), "overview");
  assert.equal(detailLevelForScale(0.3604), "overview"); // fit Route mesuré
  assert.equal(detailLevelForScale(0.6027), "normal"); // fit Entity mesuré
  assert.equal(detailLevelForScale(1), "detail");
  assert.equal(detailLevelForScale(4), "detail");
});

test("bornes exactes des seuils d'entrée", () => {
  assert.equal(detailLevelForScale(T.normalAbove - EPS), "overview");
  assert.equal(detailLevelForScale(T.normalAbove), "normal");
  assert.equal(detailLevelForScale(T.detailAbove - EPS), "normal");
  assert.equal(detailLevelForScale(T.detailAbove), "detail");
});

test("hystérésis : entrée et sortie de chaque zone", () => {
  // overview → normal seulement au seuil d'entrée.
  assert.equal(detailLevelForScale(T.normalAbove - EPS, "overview"), "overview");
  assert.equal(detailLevelForScale(T.normalAbove, "overview"), "normal");
  assert.equal(detailLevelForScale(T.detailAbove, "overview"), "detail");
  // normal → overview seulement sous le seuil de sortie.
  assert.equal(detailLevelForScale(T.overviewBelow, "normal"), "normal");
  assert.equal(detailLevelForScale(T.overviewBelow - EPS, "normal"), "overview");
  // normal → detail au seuil d'entrée ; detail → normal sous le seuil de sortie.
  assert.equal(detailLevelForScale(T.detailAbove - EPS, "normal"), "normal");
  assert.equal(detailLevelForScale(T.detailAbove, "normal"), "detail");
  assert.equal(detailLevelForScale(T.normalBelow, "detail"), "detail");
  assert.equal(detailLevelForScale(T.normalBelow - EPS, "detail"), "normal");
  assert.equal(detailLevelForScale(T.overviewBelow - EPS, "detail"), "overview");
  // Dans la bande, le niveau dépend de l'historique.
  const band = (T.overviewBelow + T.normalAbove) / 2;
  assert.equal(detailLevelForScale(band, "overview"), "overview");
  assert.equal(detailLevelForScale(band, "normal"), "normal");
  assert.equal(detailLevelForScale(band, "detail"), "normal");
});

test("oscillation autour d'un seuil : simple bascule à chaque pas, hystérésis jamais", () => {
  const scales = Array.from({ length: 40 }, (_, i) => T.normalAbove * (i % 2 ? 1.01 : 0.99));
  let simple = 0;
  let damped = 0;
  let previousSimple = detailLevelForScale(scales[0]);
  let previousDamped = previousSimple;
  for (const scale of scales.slice(1)) {
    const a = detailLevelForScale(scale);
    const b = detailLevelForScale(scale, previousDamped);
    if (a !== previousSimple) simple += 1;
    if (b !== previousDamped) damped += 1;
    previousSimple = a;
    previousDamped = b;
  }
  assert.equal(simple, 39);
  assert.equal(damped, 1);
});

test("échelle ou niveau précédent invalides refusés", () => {
  for (const bad of [Number.NaN, Infinity, -Infinity, 0, -0.5, "1", null, undefined]) {
    assert.throws(() => detailLevelForScale(bad), RangeError, String(bad));
  }
  for (const bad of ["tiny", "super-detail", "", "OVERVIEW"]) {
    assert.throws(() => detailLevelForScale(1, bad), RangeError, bad);
  }
});

function withLevels(levels, lines = ["a", "b", "c"]) {
  const scene = witness();
  scene.nodes[0] = node("A", 0, { lines, levels });
  return scene;
}

test("levels facultatif : normalisé vers toutes les lignes à tous les niveaux", () => {
  const scene = validateScene(witness());
  for (const item of scene.nodes) {
    assert.deepEqual(item.levels, { overview: [0], normal: [0], detail: [0] });
    assert.ok(Object.isFrozen(item.levels) && Object.isFrozen(item.levels.normal));
  }
  const empty = validateScene({ ...witness(), nodes: [node("A", 0, { lines: [] }), node("B"), node("C")] });
  assert.deepEqual(empty.nodes[0].levels, { overview: [], normal: [], detail: [] });
});

test("levels explicite : indices, detail toujours complet, copie indépendante", () => {
  const input = withLevels({ overview: [], normal: [0, 1] });
  const scene = validateScene(input);
  assert.deepEqual(scene.nodes[0].levels, { overview: [], normal: [0, 1], detail: [0, 1, 2] });
  input.nodes[0].levels.normal.push(2);
  assert.deepEqual(scene.nodes[0].levels.normal, [0, 1]);
  assert.deepEqual(validateScene(withLevels({ overview: [1], normal: [1, 2] })).nodes[0].levels.overview, [1]);
});

test("levels invalides refusés", () => {
  const cases = [
    [{ overview: [], normal: [0], tiny: [] }, /clé inconnue « tiny »/],
    [{ overview: [], normal: [0], detail: [0] }, /clé inconnue « detail »/],
    [{ overview: [], normal: [0], "super-detail": [] }, /clé inconnue/],
    [{ normal: [0] }, /clé « overview » manquante/],
    [{ overview: [] }, /clé « normal » manquante/],
    [{ overview: [], normal: [3] }, /indice de ligne inexistant/],
    [{ overview: [], normal: [-1] }, /indice de ligne inexistant/],
    [{ overview: [], normal: [0.5] }, /indice de ligne inexistant/],
    [{ overview: [], normal: ["0"] }, /indice de ligne inexistant/],
    [{ overview: [], normal: [1, 0] }, /strictement croissants/],
    [{ overview: [], normal: [1, 1] }, /strictement croissants/],
    [{ overview: [2], normal: [0, 1] }, /doit figurer dans normal/],
    [{ overview: [], normal: [0, 1, 2, 3, 4] }, /au plus 4 éléments/],
    [{ overview: "", normal: [] }, /tableau attendu/],
    [[], /objet attendu/],
    ["<script>alert(1)</script>", /objet attendu/],
  ];
  for (const [levels, pattern] of cases) {
    assert.throws(() => validateScene(withLevels(levels)), pattern, JSON.stringify(levels));
  }
  assert.equal(MAX_GRAPHIC_LINES, 4);
});

test("contenu hostile : reste du texte, quel que soit le niveau", () => {
  const lines = [...HOSTILE.slice(0, 3), "</text><script>alert(4)</script>"];
  const scene = validateScene(withLevels({ overview: [0], normal: [0, 1, 3] }, lines));
  assert.deepEqual([...scene.nodes[0].lines], lines);
  assert.deepEqual(scene.nodes[0].levels.detail, [0, 1, 2, 3]);
});
