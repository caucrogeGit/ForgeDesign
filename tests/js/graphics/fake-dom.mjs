// Double DOM minimal pour éprouver le Graphic Core hors navigateur.
// innerHTML et les styles en ligne sont interdits : tout usage lève une erreur.

export const SVG = "http://www.w3.org/2000/svg";

class FakeClassList {
  constructor() {
    this.values = new Set();
  }
  toggle(name, enabled) {
    if (enabled) this.values.add(name);
    else this.values.delete(name);
  }
  contains(name) {
    return this.values.has(name);
  }
}

export class FakeElement {
  constructor(document, namespace, name) {
    this.ownerDocument = document;
    this.namespace = namespace;
    this.localName = name;
    this.attributes = new Map();
    this.children = [];
    this.parent = null;
    this.listeners = [];
    this.classList = new FakeClassList();
    this._text = "";
    this.hidden = false;
    this.focused = false;
    // Mise en page simulée : taille client et position fixées par le test.
    this.clientWidth = 0;
    this.clientHeight = 0;
    this.left = 0;
    this.top = 0;
    this.captured = new Set();
  }
  get parentNode() {
    return this.parent;
  }
  getBoundingClientRect() {
    return { left: this.left, top: this.top, width: this.clientWidth, height: this.clientHeight };
  }
  setPointerCapture(id) {
    this.captured.add(id);
  }
  releasePointerCapture(id) {
    this.captured.delete(id);
  }
  setAttribute(name, value) {
    if (name === "style" || name.startsWith("on")) throw new Error(`attribut interdit : ${name}`);
    this.attributes.set(name, String(value));
    if (name === "class") for (const item of String(value).split(" ")) this.classList.values.add(item);
  }
  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }
  set innerHTML(_value) {
    throw new Error("innerHTML interdit");
  }
  get innerHTML() {
    throw new Error("innerHTML interdit");
  }
  set textContent(value) {
    this._text = String(value);
    this.children = [];
  }
  get textContent() {
    return this._text + this.children.map((child) => child.textContent).join("");
  }
  append(...nodes) {
    for (const node of nodes) {
      node.parent = this;
      this.children.push(node);
    }
  }
  remove() {
    if (this.parent) this.parent.children = this.parent.children.filter((child) => child !== this);
    this.parent = null;
  }
  addEventListener(type, handler, options = {}) {
    const entry = { type, handler };
    if (options.signal) {
      if (options.signal.aborted) return;
      options.signal.addEventListener("abort", () => {
        this.listeners = this.listeners.filter((item) => item !== entry);
      });
    }
    this.listeners.push(entry);
  }
  // Événement simulé ; il remonte aux ancêtres comme dans le DOM réel.
  dispatch(type, init = {}) {
    const event = {
      type,
      target: this,
      button: 0,
      pointerId: 1,
      clientX: 0,
      clientY: 0,
      deltaY: 0,
      deltaMode: 0,
      ctrlKey: false,
      metaKey: false,
      shiftKey: false,
      altKey: false,
      ...init,
      defaultPrevented: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
    };
    for (let node = this; node; node = node.parent) {
      for (const { type: kind, handler } of [...node.listeners]) if (kind === type) handler(event);
    }
    return event;
  }
  focus() {
    this.ownerDocument.activeElement = this;
    this.focused = true;
  }
  *walk() {
    yield this;
    for (const child of this.children) yield* child.walk();
  }
  matches(selector) {
    const attribute = /^\[([a-z-]+)\]$/.exec(selector) || /^[a-z]+\[([a-z-]+)\]$/.exec(selector);
    if (attribute) {
      const tag = selector.startsWith("[") ? null : selector.split("[")[0];
      return this.attributes.has(attribute[1]) && (tag === null || this.localName === tag);
    }
    if (selector.startsWith(".")) return this.classList.contains(selector.slice(1));
    return this.localName === selector;
  }
  querySelector(selector) {
    for (const node of this.walk()) if (node !== this && node.matches(selector)) return node;
    return null;
  }
  querySelectorAll(selector) {
    return [...this.walk()].filter((node) => node !== this && node.matches(selector));
  }
}

export class FakeDocument {
  constructor() {
    this.activeElement = null;
  }
  createElementNS(namespace, name) {
    if (namespace !== SVG) throw new Error(`espace de noms inattendu : ${namespace}`);
    return new FakeElement(this, namespace, name);
  }
  createElement(name) {
    return new FakeElement(this, "http://www.w3.org/1999/xhtml", name);
  }
}

export function container() {
  return new FakeDocument().createElement("div");
}

// Donne une taille à la zone de vue d'une instance puis la remesure.
export function sized(host, engine, width, height) {
  const area = host.querySelector(".gx-viewport");
  area.clientWidth = width;
  area.clientHeight = height;
  return engine.resize();
}

// Éléments rendus d'une instance, par rôle.
export function rendered(host) {
  const svg = host.querySelector("svg");
  return {
    svg,
    nodes: svg ? svg.querySelectorAll(".gx-node") : [],
    edges: svg ? svg.querySelectorAll(".gx-edge") : [],
  };
}
