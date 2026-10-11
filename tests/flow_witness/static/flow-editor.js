// Témoin FD-ARCH-001 (tests seulement) : script d'éditeur d'un domaine sans rapport
// avec Circuit. Il n'utilise que le contexte de l'hôte et l'API publique du moteur :
// un calque monde (addOverlay) avec une poignée focalisable par étape ; Entrée sur
// une poignée renomme l'étape par l'action déclarée, puis la page est rechargée.
const SVG_NS = "http://www.w3.org/2000/svg";

export function createResourceEditor(context) {
  const { renameAction, steps } = context.config;
  const url = context.actions[renameAction];
  if (typeof url !== "string" || !Array.isArray(steps)) return null;
  let overlay = null;
  const marks = [];
  let pending = false;

  async function rename(stepId, label) {
    if (pending) return;
    pending = true;
    const body = new URLSearchParams([
      ["type", context.resourceType],
      ["path", context.path],
      ["revision", context.revision],
      ["step", stepId],
      ["label", `${label} ✓`],
    ]);
    const response = await fetch(url, { method: "POST", body, credentials: "same-origin", redirect: "follow" });
    if (response.ok && response.redirected) {
      location.assign(response.url);
      return;
    }
    pending = false;
    context.announce(`Renommage refusé (${response.status}).`);
  }

  return Object.freeze({
    onViewChange(state) {
      const scale = state.scale > 0 ? state.scale : 1;
      for (const mark of marks) mark.setAttribute("r", String(6 / scale));
    },
    attach(engine) {
      overlay = engine.addOverlay({ label: "Étapes du flux" });
      const document = overlay.root.ownerDocument;
      for (const stepId of steps) {
        const node = engine.node(stepId);
        if (!node) continue;
        const item = document.createElementNS(SVG_NS, "g");
        item.setAttribute("class", "gx-overlay-item");
        item.setAttribute("tabindex", "0");
        item.setAttribute("role", "button");
        item.setAttribute("aria-label", `Renommer ${node.label}`);
        const mark = document.createElementNS(SVG_NS, "circle");
        mark.setAttribute("class", "gx-overlay-handle");
        mark.setAttribute("cx", String(node.rect.x + node.rect.width / 2));
        mark.setAttribute("cy", String(node.rect.y));
        mark.setAttribute("r", "6");
        item.append(mark);
        item.addEventListener("keydown", (event) => {
          if (event.key !== "Enter") return;
          event.preventDefault();
          rename(stepId, node.label);
        });
        overlay.root.append(item);
        marks.push(mark);
      }
      context.announce(`Flux témoin : ${marks.length} étapes balisées.`);
    },
  });
}
