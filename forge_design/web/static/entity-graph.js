/* Amélioration locale du SVG serveur : aucune donnée métier supplémentaire. */
(() => {
  "use strict";
  document.querySelectorAll("[data-entity-graph]").forEach((container) => {
    const nodes = Array.from(container.querySelectorAll("[data-node-id]"));
    const edges = Array.from(container.querySelectorAll("[data-source-id]"));
    const status = container.querySelector("[data-selection-status]");
    const details = container.querySelector("[data-selection-details]");
    const kind = container.querySelector("[data-selection-kind]");
    const label = container.querySelector("[data-selection-label]");
    const table = container.querySelector("[data-selection-table]");
    const count = container.querySelector("[data-selection-field-count]");
    const countLabel = container.querySelector("[data-selection-field-label]");
    const relationCount = container.querySelector("[data-selection-relation-count]");
    const relations = container.querySelector("[data-selection-relations]");
    const clear = container.querySelector("[data-selection-clear]");
    if (!nodes.length || !status || !details || !kind || !label || !table || !count || !countLabel || !relationCount || !relations || !clear) return;
    const kinds = {entity: "Entité", pivot: "Pivot"};
    const byId = new Map(nodes.map(node => [node.dataset.nodeId, node]));
    let selected = null;

    function select(node) {
      selected = node;
      const id = node ? node.dataset.nodeId : null;
      const neighbours = new Set();
      relations.textContent = "";
      let incidentCount = 0;
      edges.forEach((edge) => {
        const related = id !== null && (edge.dataset.sourceId === id || edge.dataset.targetId === id);
        edge.classList.toggle("is-related", related);
        if (related) {
          const source = byId.get(edge.dataset.sourceId);
          const target = byId.get(edge.dataset.targetId);
          if (source && target) {
            const item = document.createElement("li");
            const name = edge.dataset.edgeLabel || edge.dataset.edgeKind || "";
            item.textContent = `${source.dataset.nodeLabel} → ${target.dataset.nodeLabel}${name ? " — " + name : ""}`;
            relations.append(item);
            incidentCount += 1;
          }
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
      table.textContent = node ? (node.dataset.nodeTable || node.dataset.nodeLabel) : "";
      count.textContent = node ? (node.dataset.nodeFieldCount || "0") : "";
      countLabel.textContent = node && node.dataset.nodeKind === "pivot" ? "Champs supplémentaires" : "Champs";
      relationCount.textContent = node ? String(incidentCount) : "";
      relations.hidden = node === null;
      status.textContent = node ? `Élément sélectionné : ${node.dataset.nodeLabel}` : "Sélectionnez une entité ou un pivot dans le graphe.";
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
