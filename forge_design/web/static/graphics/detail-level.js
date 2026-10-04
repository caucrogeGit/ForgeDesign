// Graphic Core — niveau de détail selon l'échelle (FD-GRAPHICS-006).
// Fonctions pures, sans DOM : le moteur décide QUAND changer de niveau à partir
// de l'échelle réelle du viewport ; le client décide QUOI montrer à chaque niveau
// (indices de lignes déclarés dans la scène). Les niveaux décrivent une densité
// de présentation, jamais une importance métier.

export const DETAIL_LEVELS = Object.freeze(["overview", "normal", "detail"]);

// Taille logique des textes de scène (CSS .gx-node-text et .gx-edge-label).
export const SCENE_TEXT_SIZE = 12;
// Tailles écran minimales mesurées (Chromium, DPR 1, FD-GRAPHICS-006) : à 4,3 px
// les glyphes se confondent ; à 7 px le texte principal se lit ; à 9 px les
// lignes secondaires se lisent sans effort. Lisibilité mesurée, pas un critère WCAG.
export const PRIMARY_TEXT_PX = 7;
export const SECONDARY_TEXT_PX = 9;
// Hystérésis : on ne redescend qu'une demi-unité écran sous le seuil d'entrée,
// pour qu'un pincement oscillant autour d'un seuil ne fasse pas clignoter le texte.
export const HYSTERESIS_PX = 0.5;

const scaleFor = (pixels) => pixels / SCENE_TEXT_SIZE;
export const THRESHOLDS = Object.freeze({
  normalAbove: scaleFor(PRIMARY_TEXT_PX),
  overviewBelow: scaleFor(PRIMARY_TEXT_PX - HYSTERESIS_PX),
  detailAbove: scaleFor(SECONDARY_TEXT_PX),
  normalBelow: scaleFor(SECONDARY_TEXT_PX - HYSTERESIS_PX),
});

// Niveau pour une échelle ; `previous` (facultatif) applique l'hystérésis.
export function detailLevelForScale(scale, previous = null) {
  if (typeof scale !== "number" || !Number.isFinite(scale) || scale <= 0) {
    throw new RangeError("Échelle finie strictement positive attendue.");
  }
  if (previous !== null && !DETAIL_LEVELS.includes(previous)) {
    throw new RangeError("Niveau précédent inconnu.");
  }
  const t = THRESHOLDS;
  if (previous === "overview") {
    if (scale < t.normalAbove) return "overview";
    return scale < t.detailAbove ? "normal" : "detail";
  }
  if (previous === "detail") {
    if (scale >= t.normalBelow) return "detail";
    return scale >= t.overviewBelow ? "normal" : "overview";
  }
  if (previous === "normal") {
    if (scale < t.overviewBelow) return "overview";
    return scale >= t.detailAbove ? "detail" : "normal";
  }
  // Sans historique : seuils d'entrée.
  if (scale < t.normalAbove) return "overview";
  return scale < t.detailAbove ? "normal" : "detail";
}
