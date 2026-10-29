// Script d'inspection du mode analyse (FD-INSPECT-001), injecté par le proxy
// de preview dans chaque page HTML de l'application, sur l'origine du proxy.
//
// Il ne lit aucune trace : il envoie à Forge Design (data-origin, seule
// destinataire) l'identifiant de trace de la page (data-trace) et, au choix
// d'un élément, la chaîne des marqueurs <!--fd:…--> qui l'entourent.
// Alt+clic choisit un élément ; Forge Design peut aussi armer un seul clic.
(() => {
  "use strict";
  const script = document.currentScript;
  if (!script || window.parent === window) return;
  const trace = /^\d+$/.test(script.dataset.trace || "") ? script.dataset.trace : null;
  const origin = script.dataset.origin || "";
  if (!/^http:\/\/127\.0\.0\.1:\d{1,5}$/.test(origin)) return;

  const MARKER = /^(\/?)fd:([tb]):(\d+)(?::(\w+))?$/;
  let armed = false;
  let box = null;

  function post(message) {
    window.parent.postMessage({ source: "forge-design-inspect", trace, ...message }, origin);
  }

  // Marqueurs ouverts au point où commence l'élément, du plus externe au plus
  // interne : un commentaire compte s'il précède l'élément dans le document.
  function chainOf(element) {
    const stack = [];
    const walker = document.createTreeWalker(document, NodeFilter.SHOW_COMMENT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (!(node.compareDocumentPosition(element) & Node.DOCUMENT_POSITION_FOLLOWING)) break;
      const match = MARKER.exec(node.data.trim());
      if (!match) continue;
      const [, closing, kind, id, block] = match;
      if (closing) {
        const index = stack.findLastIndex((entry) => entry.kind === kind && entry.id === Number(id));
        if (index >= 0) stack.splice(index);
      } else {
        stack.push({ kind, id: Number(id), block: block || null });
      }
    }
    return stack;
  }

  function describe(element) {
    const text = (element.innerText || element.textContent || "").trim().replace(/\s+/g, " ");
    return {
      tag: element.tagName.toLowerCase(),
      id: element.id || null,
      classes: Array.from(element.classList).slice(0, 8),
      text: text.slice(0, 120),
    };
  }

  // Cadre posé par le CSSOM (autorisé par style-src 'self'), jamais cliquable.
  function highlight(element) {
    if (!box) {
      box = document.createElement("div");
      Object.assign(box.style, {
        position: "fixed",
        zIndex: "2147483647",
        pointerEvents: "none",
        border: "2px solid #c2410c",
        background: "rgba(194, 65, 12, 0.08)",
        borderRadius: "2px",
      });
    }
    const rect = element.getBoundingClientRect();
    Object.assign(box.style, {
      left: `${rect.left - 2}px`,
      top: `${rect.top - 2}px`,
      width: `${rect.width + 4}px`,
      height: `${rect.height + 4}px`,
    });
    if (!box.isConnected) document.documentElement.appendChild(box);
  }

  function clear() {
    if (box) box.remove();
  }

  function pick(event) {
    if (!(event.altKey || armed) || !(event.target instanceof Element)) return;
    event.preventDefault();
    event.stopPropagation();
    armed = false;
    document.documentElement.style.cursor = "";
    const element = event.target;
    highlight(element);
    post({ type: "pick", chain: chainOf(element), element: describe(element) });
  }

  document.addEventListener("click", pick, true);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      armed = false;
      document.documentElement.style.cursor = "";
      clear();
    }
  });
  window.addEventListener("scroll", clear, { passive: true });
  window.addEventListener("message", (event) => {
    if (event.origin !== origin || event.source !== window.parent) return;
    const data = event.data;
    if (data && data.source === "forge-design" && data.type === "arm") {
      armed = true;
      document.documentElement.style.cursor = "crosshair";
    }
  });
  post({ type: "page", path: location.pathname });
})();
