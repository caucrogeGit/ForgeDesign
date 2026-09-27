// Double DOM minimal : exécution du script livré, sans navigateur ni dépendance.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor(dataset = {}) {
    this.dataset = dataset;
    this.attributes = {};
    this.listeners = {};
    this.textContent = '';
    this.hidden = false;
    this.classes = new Set();
    this.classList = {toggle: (name, enabled) => enabled ? this.classes.add(name) : this.classes.delete(name)};
  }
  setAttribute(name, value) { this.attributes[name] = value; }
  addEventListener(name, handler) { this.listeners[name] = handler; }
  focus() { this.focused = true; }
  emit(name, key) {
    const event = {key, prevented: false, preventDefault() { this.prevented = true; }};
    this.listeners[name]?.(event);
    return event;
  }
}
function graph() {
  const nodes = [
    new Element({nodeId: '["template","<script>\\\"&"]', nodeLabel: '<script>"&', nodeKind: 'template', nodePresence: 'missing'}),
    new Element({nodeId: 'b', nodeLabel: 'B', nodeKind: 'handler', nodePresence: 'not-applicable'}),
    new Element({nodeId: 'c', nodeLabel: 'C', nodeKind: 'controller', nodePresence: 'present'}),
    new Element({nodeId: 'd', nodeLabel: 'D', nodeKind: 'route', nodePresence: 'not-applicable'}),
  ];
  const edges = [
    new Element({sourceId: nodes[0].dataset.nodeId, targetId: 'b'}),
    new Element({sourceId: 'b', targetId: 'c'}),
    new Element({sourceId: 'd', targetId: nodes[0].dataset.nodeId}),
  ];
  edges[0].classes.add('graph-edge-cycle');
  const fields = Object.fromEntries(['status', 'details', 'kind', 'label', 'presence', 'clear'].map(key => [key, new Element()]));
  const container = new Element();
  container.querySelectorAll = selector => selector === '[data-node-id]' ? nodes : edges;
  container.querySelector = selector => fields[selector.slice('[data-selection-'.length, -1)];
  return {container, nodes, edges, fields};
}
const first = graph();
const second = graph();
const empty = {querySelectorAll: () => [], querySelector: () => null};
const script = fs.readFileSync(process.argv[2], 'utf8');
vm.runInNewContext(script, {document: {querySelectorAll: () => [empty, first.container, second.container]}});
const {nodes, edges, fields, container} = first;
assert.equal(fields.status.textContent, 'Sélectionnez un élément du graphe.');
assert.equal(fields.details.hidden, true);
assert.equal(fields.clear.hidden, true);
assert(nodes.every(n => n.attributes['aria-pressed'] === 'false'));
nodes[0].emit('click');
assert(nodes[0].classes.has('is-selected'));
assert.equal(nodes[0].attributes['aria-pressed'], 'true');
assert(nodes[1].classes.has('is-related'));
assert(nodes[3].classes.has('is-related')); // relation entrante
assert(!nodes[2].classes.has('is-related')); // pas de fermeture transitive
assert(edges[0].classes.has('is-related') && edges[2].classes.has('is-related'));
assert(!edges[1].classes.has('is-related'));
assert(edges[0].classes.has('graph-edge-cycle'));
assert.equal(fields.label.textContent, '<script>"&');
assert.equal(fields.kind.textContent, 'Template');
assert.equal(fields.presence.textContent, 'Absent');
assert.equal(fields.details.hidden, false);
assert.equal(second.fields.details.hidden, true); // conteneurs isolés
nodes[0].emit('click');
assert.equal(fields.details.hidden, true);
assert.equal(nodes[1].emit('keydown', 'Enter').prevented, true);
assert(nodes[1].classes.has('is-selected'));
assert.equal(fields.kind.textContent, 'Handler');
assert.equal(nodes[0].emit('keydown', ' ').prevented, true);
assert(!nodes[1].classes.has('is-selected'));
assert(nodes[0].classes.has('is-selected'));
assert.equal(container.emit('keydown', 'Escape').prevented, true);
assert(nodes[0].focused);
assert(nodes.every(n => !n.classes.has('is-selected') && !n.classes.has('is-related')));
assert(edges.every(e => !e.classes.has('is-related')));
nodes[2].emit('click');
assert.equal(fields.kind.textContent, 'Contrôleur');
assert.equal(fields.presence.textContent, 'Présent');
fields.clear.emit('click');
assert(nodes[2].focused && fields.clear.hidden);
assert.equal(nodes[0].emit('keydown', 'ArrowRight').prevented, false);
// Nouveau chargement du même DOM : aucun état persisté.
nodes[0].emit('click');
vm.runInNewContext(script, {document: {querySelectorAll: () => [container]}});
assert.equal(fields.details.hidden, true);
assert.equal(nodes[0].attributes['aria-pressed'], 'false');
console.log('clic, clavier, relations directes, XSS texte, reset, isolation : OK');
