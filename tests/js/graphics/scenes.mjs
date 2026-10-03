// Scènes de test sans vocabulaire Forge (témoin générique test-only).

export function node(id, x = 0, extra = {}) {
  return { id, label: `Node ${id}`, rect: { x, y: 10, width: 80, height: 40 }, lines: [`Node ${id}`], ...extra };
}

export function edge(id, source, target, extra = {}) {
  return {
    id,
    source,
    target,
    points: [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 20 }],
    ...extra,
  };
}

// Témoin : A → B, A → C.
export function witness() {
  return {
    width: 400,
    height: 120,
    title: "Témoin",
    description: "Trois nœuds, deux arêtes.",
    nodes: [node("A", 0), node("B", 120), node("C", 240)],
    edges: [edge("A-B", "A", "B", { presentation: { arrow: "end" } }), edge("A-C", "A", "C")],
  };
}

export const HOSTILE = [
  "<script>alert(1)</script>",
  "</script><script>alert(2)</script>",
  '<svg onload="alert(3)">',
  "{{ config.SECRET }}",
  "&amp; & < > \" '",
];
