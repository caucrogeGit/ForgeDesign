// Ressource d'un module spécialisé — client générique du Graphic Core (FD-MODULES-002).
// Lit la GraphicScene inerte projetée par le module, crée une instance du moteur
// partagé et annonce l'élément sélectionné. Aucun vocabulaire de module : la scène
// est validée par validateScene comme n'importe quel contenu non fiable. Sans
// JavaScript ou si la scène est refusée, seul le message de repli reste affiché.
//
// Édition (FD-GRAPHICS-EDIT-001) : si l'hôte a placé un contexte d'édition inerte
// (data-module-editor), le script déclaré par le module est importé depuis l'URL
// calculée par l'hôte ; son createResourceEditor(context) peut fournir l'option
// nodeMove du moteur et reçoit ensuite l'instance. En cas d'échec, la vue reste en
// consultation et l'indisponibilité est annoncée.

import { createGraphicEngine } from "./graphics/engine.js";

const IDLE = "Sélectionnez un élément du graphe.";
// Seule forme d'URL acceptée : un chemin absolu du même serveur.
const SAME_ORIGIN_PATH = /^\/[^/\\]/;

export function mountModuleResource(container, editor = null) {
  const source = container.querySelector("script[data-graphic-scene]");
  const host = container.querySelector("[data-graphic-host]");
  const fallback = container.querySelector("[data-graphic-fallback]");
  const status = container.querySelector("[data-selection-status]");
  if (!source || !host || !status) return null;
  let engine;
  try {
    engine = createGraphicEngine(host, JSON.parse(source.textContent), {
      onSelectionChange(state) {
        const node = state ? engine.node(state.nodeId) : null;
        status.textContent = node ? `Élément sélectionné : ${node.label}` : IDLE;
      },
      ...(editor && editor.nodeMove ? { nodeMove: editor.nodeMove } : {}),
    });
  } catch (error) {
    status.textContent = `Vue interactive indisponible (${error.message}).`;
    return null;
  }
  if (editor && typeof editor.attach === "function") {
    try {
      editor.attach(engine);
    } catch (error) {
      // Un éditeur à moitié branché ne doit pas laisser de nœud déplaçable.
      engine.destroy();
      throw error;
    }
  }
  if (fallback) fallback.hidden = true;
  status.textContent = IDLE;
  return engine;
}

function frozenCopy(value) {
  if (value === null || typeof value !== "object") return value;
  const copy = Array.isArray(value) ? value.map(frozenCopy) : {};
  if (!Array.isArray(value)) for (const [key, item] of Object.entries(value)) copy[key] = frozenCopy(item);
  return Object.freeze(copy);
}

// Contexte transmis au script du module : données de l'hôte, en lecture seule.
export function readEditorContext(container) {
  const source = container.querySelector("script[data-module-editor]");
  if (!source) return null;
  const raw = JSON.parse(source.textContent);
  const paths = [raw.script, ...Object.values(raw.actions ?? {})];
  if (!paths.every((path) => typeof path === "string" && SAME_ORIGIN_PATH.test(path))) {
    throw new Error("contexte d'édition invalide");
  }
  for (const key of ["type", "path", "revision"]) {
    if (typeof raw[key] !== "string" || !raw[key]) throw new Error("contexte d'édition invalide");
  }
  return frozenCopy({
    script: raw.script,
    resourceType: raw.type,
    path: raw.path,
    revision: raw.revision,
    actions: raw.actions ?? {},
    config: raw.config ?? {},
  });
}

// Montage complet : le script d'édition éventuel est chargé avant le moteur.
export async function bootModuleResource(container, { load = (url) => import(url) } = {}) {
  const status = container.querySelector("[data-editor-status]");
  const announce = (message) => {
    if (!status) return;
    status.hidden = false;
    status.textContent = String(message);
  };
  let editor = null;
  try {
    const context = readEditorContext(container);
    if (context) {
      const script = await load(context.script);
      if (typeof script.createResourceEditor !== "function") throw new Error("script d'édition sans createResourceEditor");
      const created = script.createResourceEditor(Object.freeze({ ...context, announce }));
      editor = created !== null && typeof created === "object" ? created : null;
    }
  } catch (error) {
    editor = null;
    announce(`Édition indisponible (${error.message}) : consultation seule.`);
  }
  if (editor === null) return mountModuleResource(container);
  let engine;
  try {
    engine = mountModuleResource(container, editor);
  } catch (error) {
    // Échec du module dans attach : remontage en consultation seule.
    announce(`Édition indisponible (${error.message}) : consultation seule.`);
    return mountModuleResource(container);
  }
  if (engine !== null) return engine;
  // Option d'édition refusée par le moteur : la scène reste consultable sans elle.
  const readOnly = mountModuleResource(container);
  if (readOnly !== null) announce("Édition indisponible (option refusée par le moteur) : consultation seule.");
  return readOnly;
}

if (typeof document !== "undefined") {
  document.querySelectorAll("[data-module-graph]").forEach((container) => bootModuleResource(container));
}
