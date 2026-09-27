/* Amélioration locale du SVG serveur : aucune donnée métier supplémentaire. */
(() => {
  "use strict";
  document.querySelectorAll("[data-route-graph]").forEach((container) => {
    const nodes = Array.from(container.querySelectorAll("[data-node-id]"));
    const edges = Array.from(container.querySelectorAll("[data-source-id]"));
    const status = container.querySelector("[data-selection-status]");
    const details = container.querySelector("[data-selection-details]");
    const kind = container.querySelector("[data-selection-kind]");
    const label = container.querySelector("[data-selection-label]");
    const presence = container.querySelector("[data-selection-presence]");
    const clear = container.querySelector("[data-selection-clear]");
    if (!nodes.length || !status || !details || !kind || !label || !presence || !clear) return;
    const kinds = {route: "Route", handler: "Handler", controller: "Contrôleur", template: "Template"};
    const presences = {present: "Présent", missing: "Absent", "invalid-path": "Chemin refusé", unreadable: "Non vérifiable", "not-applicable": "—"};
    let selected = null;

    function select(node) {
      selected = node;
      const id = node ? node.dataset.nodeId : null;
      const neighbours = new Set();
      edges.forEach((edge) => {
        const related = id !== null && (edge.dataset.sourceId === id || edge.dataset.targetId === id);
        edge.classList.toggle("is-related", related);
        if (related) {
          neighbours.add(edge.dataset.sourceId);
          neighbours.add(edge.dataset.targetId);
        }
      });
      nodes.forEach((candidate) => {
        const active = candidate === node;
        candidate.classList.toggle("is-selected", active);
        candidate.classList.toggle("is-related", !active && neighbours.has(candidate.dataset.nodeId));
        candidate.setAttribute("aria-pressed", String(active));
      });
      details.hidden = node === null;
      clear.hidden = node === null;
      kind.textContent = node ? (kinds[node.dataset.nodeKind] || "—") : "";
      label.textContent = node ? node.dataset.nodeLabel : "";
      presence.textContent = node ? (presences[node.dataset.nodePresence] || "—") : "";
      status.textContent = node ? `Élément sélectionné : ${node.dataset.nodeLabel}` : "Sélectionnez un élément du graphe.";
    }

    nodes.forEach((node) => {
      node.addEventListener("click", () => select(selected === node ? null : node));
      node.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          select(selected === node ? null : node);
        }
      });
    });
    function reset() {
      const previous = selected;
      select(null);
      if (previous) previous.focus();
    }
    clear.addEventListener("click", reset);
    container.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && selected) {
        event.preventDefault();
        reset();
      }
    });
    select(null);
  });
})();
