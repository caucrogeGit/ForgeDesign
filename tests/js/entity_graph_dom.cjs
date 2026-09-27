// Double DOM explicite : ni moteur SVG, ni dépendance navigateur.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor(dataset = {}) {
    this.dataset = dataset;
    this.attributes = {};
    this.listeners = {};
    this.children = [];
    this.hidden = false;
    this.classes = new Set();
    this.classList = {toggle: (name, enabled) => enabled ? this.classes.add(name) : this.classes.delete(name)};
  }
  set textContent(value) { this.text = value; this.children = []; }
  get textContent() { return this.text; }
  append(child) { this.children.push(child); }
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
    new Element({nodeId: 'a"\\<', nodeKind: 'entity', nodeLabel: '<script>alert(1)</script>', nodeTable: '<table>"', nodeFieldCount: '5'}),
    new Element({nodeId: 'p', nodeKind: 'pivot', nodeLabel: 'article_tag', nodeTable: 'article_tag', nodeFieldCount: '2'}),
    new Element({nodeId: 't', nodeKind: 'entity', nodeLabel: 'Tag', nodeTable: 'tags', nodeFieldCount: '1'}),
    new Element({nodeId: 'u', nodeKind: 'entity', nodeLabel: 'User', nodeTable: 'users', nodeFieldCount: '3'}),
  ];
  const edge = (source, target, label) => new Element({sourceId: source, targetId: target, edgeLabel: label, edgeKind: 'many_to_one'});
  const edges = [edge(nodes[0].dataset.nodeId, 'p', '<script>tags</script>'), edge('p', 't', ''),
    edge('u', nodes[0].dataset.nodeId, 'author'), edge('u', nodes[0].dataset.nodeId, 'editor'), edge('u', 'u', 'manager')];
  const fields = Object.fromEntries(['status', 'details', 'kind', 'label', 'table', 'field-count', 'field-label', 'relation-count', 'relations', 'clear'].map(key => [key, new Element()]));
  const container = new Element();
  container.querySelectorAll = selector => selector === '[data-node-id]' ? nodes : edges;
  container.querySelector = selector => fields[selector.slice('[data-selection-'.length, -1)];
  return {container, nodes, edges, fields};
}
const first = graph(), second = graph(), incomplete = graph();
delete incomplete.fields.table;
const empty = {querySelectorAll: () => [], querySelector: () => null};
const script = fs.readFileSync(process.argv[2], 'utf8');
const run = containers => vm.runInNewContext(script, {document: {
  querySelectorAll: () => containers, createElement: tag => { assert.equal(tag, 'li'); return new Element(); }
}});
run([]);
run([empty, incomplete.container, first.container, second.container]);
const {nodes, edges, fields, container} = first;
assert.equal(fields.status.textContent, 'Sélectionnez une entité ou un pivot dans le graphe.');
assert(fields.details.hidden && fields.clear.hidden && fields.relations.hidden);
nodes[0].emit('click');
assert.equal(nodes[0].attributes['aria-pressed'], 'true');
assert(nodes[1].classes.has('is-related') && nodes[3].classes.has('is-related'));
assert(!nodes[2].classes.has('is-related')); // distance 2 exclue
assert.equal(fields['relation-count'].textContent, '3');
assert.equal(fields.relations.children.length, 3); // parallèles conservées
assert.equal(fields.label.textContent, '<script>alert(1)</script>');
assert.equal(fields.table.textContent, '<table>"');
assert.equal(fields['field-count'].textContent, '5');
assert(fields.relations.children[0].textContent.includes('<script>tags</script>'));
assert(second.fields.details.hidden);
nodes[0].emit('click');
assert(fields.details.hidden && fields.relations.children.length === 0);
assert(nodes[1].emit('keydown', 'Enter').prevented);
assert.equal(fields.kind.textContent, 'Pivot');
assert.equal(fields['field-label'].textContent, 'Champs supplémentaires');
assert.equal(fields['field-count'].textContent, '2');
assert.equal(fields['relation-count'].textContent, '2');
assert(nodes[0].classes.has('is-related') && nodes[2].classes.has('is-related'));
assert(!nodes[3].classes.has('is-related'));
assert(nodes[3].emit('keydown', ' ').prevented);
assert.equal(fields['relation-count'].textContent, '3');
assert.equal(fields.relations.children.filter(li => li.textContent.includes('User → User')).length, 1);
assert(!nodes[3].classes.has('is-related') && nodes[3].classes.has('is-selected'));
assert(edges[4].classes.has('is-related'));
assert(container.emit('keydown', 'Escape').prevented);
assert(nodes[3].focused);
assert(nodes.every(n => n.attributes['aria-pressed'] === 'false'));
assert(edges.every(e => !e.classes.has('is-related')));
nodes[0].emit('click'); fields.clear.emit('click');
assert(nodes[0].focused && fields.clear.hidden);
assert(!nodes[0].emit('keydown', 'ArrowRight').prevented);
assert(!container.emit('keydown', 'Escape').prevented);
// Arête partielle : aucune cible fantôme ni exception dans le panneau.
edges.push(new Element({sourceId: 'u', targetId: 'missing'}));
run([container]); nodes[3].emit('click');
assert.equal(fields.relations.children.length, 3);
run([container]);
assert(fields.details.hidden && fields.relations.hidden);
console.log('sélection, pivot, parallèles, boucle, clavier, texte sûr, isolation : OK');
