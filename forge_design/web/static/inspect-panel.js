// Panneau du mode analyse (FD-INSPECT-001). Reçoit les messages du script
// d'inspection de l'iframe (origine du proxy seulement), lit la trace auprès
// de Forge Design (GET /inspect/trace) et l'affiche en texte : la trace vient
// du code du projet, aucun HTML n'en est interprété.

const workspace = document.querySelector("[data-inspect-workspace]");
const frame = workspace?.querySelector("iframe");
const output = workspace?.querySelector("[data-inspect-output]");
const arm = workspace?.querySelector("[data-inspect-arm]");
const proxyOrigin = workspace?.dataset.proxyOrigin;
const NBSP = " ";
const traces = new Map();
let latest = 0;

function element(tag, options = {}, ...children) {
  const node = document.createElement(tag);
  if (options.className) node.className = options.className;
  if (options.href) node.href = options.href;
  for (const child of children) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : String(child));
  }
  return node;
}

function section(title, ...children) {
  return element("section", { className: "inspect-section" }, element("h3", {}, title), ...children);
}

function facts(rows) {
  const list = element("dl", { className: "inspect-facts" });
  for (const [term, value] of rows) {
    if (value === null || value === undefined || value === "") continue;
    list.append(element("dt", {}, term), element("dd", {}, value));
  }
  return list;
}

function milliseconds(value) {
  if (typeof value !== "number") return null;
  return `${value.toLocaleString("fr-FR", { maximumFractionDigits: 1 })}${NBSP}ms`;
}

function plural(count, one, many) {
  return `${count}${NBSP}${count > 1 ? many : one}`;
}

async function loadTrace(id) {
  if (!traces.has(id)) {
    traces.set(
      id,
      fetch(`/inspect/trace?id=${encodeURIComponent(id)}`, { cache: "no-store" }).then((response) =>
        response.ok ? response.json() : null,
      ),
    );
  }
  return traces.get(id);
}

function templateLabel(template) {
  return typeof template?.name === "string" ? template.name : "gabarit inconnu";
}

function renderElement(pick, templates, links) {
  if (!pick) return null;
  const chain = Array.isArray(pick.chain) ? pick.chain : [];
  const innermost = chain.at(-1);
  const source = innermost ? templates.get(innermost.id) : null;
  const described = pick.element || {};
  const tag = typeof described.tag === "string" ? `<${described.tag}>` : null;
  const link = source && links.templates?.[String(source.id)];
  const origin = source
    ? element(
        "span",
        {},
        link ? element("a", { href: link }, templateLabel(source)) : templateLabel(source),
        innermost.block ? `, bloc ${innermost.block}` : null,
      )
    : "Aucun gabarit repéré autour de cet élément.";
  return section(
    "Élément choisi",
    facts([
      ["Balise", tag],
      ["Texte", typeof described.text === "string" && described.text ? described.text : null],
      ["Produit par", origin],
    ]),
  );
}

function renderPage(trace) {
  const route = trace.route;
  return [
    section(
      "Page",
      facts([
        ["Requête", `${trace.method || ""} ${trace.path || ""}`.trim()],
        ["Statut", trace.status ? String(trace.status) : null],
        ["Durée", milliseconds(trace.duration_ms)],
      ]),
    ),
    section(
      "Route",
      route
        ? facts([
            ["Motif", route.pattern],
            ["Nom", route.name],
            ["Méthodes", Array.isArray(route.methods) ? route.methods.join(", ") : null],
            ["Accès", route.public ? "publique" : "protégée"],
            ["Paramètres", Array.isArray(route.params) && route.params.length ? route.params.join(", ") : null],
          ])
        : element("p", {}, "Aucune route trouvée pour cette requête."),
    ),
  ];
}

function renderHandler(trace, links) {
  const handler = trace.handler;
  if (!handler) return null;
  const name = typeof handler.qualname === "string" ? handler.qualname : "handler";
  const where = handler.file ? `${handler.file}${handler.line ? `, ligne ${handler.line}` : ""}` : handler.module;
  return section(
    "Handler",
    facts([
      ["Méthode", links.handler ? element("a", { href: links.handler }, name) : name],
      ["Fichier", where],
    ]),
  );
}

function renderTemplates(trace, chain, links) {
  const list = element("ol", { className: "inspect-templates" });
  const inChain = new Map(chain.map((entry, index) => [entry.id, index]));
  for (const template of Array.isArray(trace.templates) ? trace.templates : []) {
    const link = links.templates?.[String(template.id)];
    const item = element(
      "li",
      {},
      link ? element("a", { href: link }, templateLabel(template)) : templateLabel(template),
      template.extends ? element("span", { className: "inspect-note" }, ` étend ${template.extends}`) : null,
    );
    if (inChain.has(template.id)) {
      item.className = inChain.get(template.id) === chain.length - 1 ? "inspect-source" : "inspect-around";
    }
    list.append(item);
  }
  return section("Gabarits rendus", list.childElementCount ? list : element("p", {}, "Aucun gabarit."));
}

function renderQueries(trace) {
  const queries = Array.isArray(trace.queries) ? trace.queries : [];
  if (!queries.length) return section("Requêtes SQL", element("p", {}, "Aucune requête SQL."));
  const list = element("ol", { className: "inspect-queries" });
  for (const query of queries) {
    const meta = query.error
      ? `Erreur ${query.error}`
      : [typeof query.rows === "number" ? plural(query.rows, "ligne", "lignes") : null, milliseconds(query.duration_ms)]
          .filter(Boolean)
          .join(" · ");
    list.append(
      element("li", {}, element("pre", {}, element("code", {}, query.sql || "")), element("p", { className: "inspect-note" }, meta)),
    );
  }
  const dropped = trace.queries_dropped ? element("p", { className: "inspect-note" }, `${plural(trace.queries_dropped, "requête", "requêtes")} de plus, non conservées.`) : null;
  return section(`Requêtes SQL (${queries.length})`, list, dropped);
}

async function show(id, pick) {
  const ticket = ++latest;
  const payload = await loadTrace(id).catch(() => null);
  if (ticket !== latest) return;
  output.replaceChildren();
  if (!payload || typeof payload.trace !== "object") {
    output.append(element("p", { className: "inspect-empty" }, "Trace indisponible pour cette page."));
    return;
  }
  const { trace, links = {} } = payload;
  const templates = new Map((Array.isArray(trace.templates) ? trace.templates : []).map((t) => [t.id, t]));
  const chain = pick && Array.isArray(pick.chain) ? pick.chain : [];
  output.append(
    ...[renderElement(pick, templates, links), ...renderPage(trace), renderHandler(trace, links), renderTemplates(trace, chain, links), renderQueries(trace)].filter(
      Boolean,
    ),
  );
}

if (workspace && frame && output && proxyOrigin) {
  window.addEventListener("message", (event) => {
    if (event.origin !== proxyOrigin || event.source !== frame.contentWindow) return;
    const data = event.data;
    if (!data || data.source !== "forge-design-inspect" || !/^\d+$/.test(data.trace || "")) return;
    if (data.type === "page") show(data.trace, null);
    else if (data.type === "pick") show(data.trace, data);
  });
  arm?.addEventListener("click", () => {
    frame.contentWindow?.postMessage({ source: "forge-design", type: "arm" }, proxyOrigin);
    frame.focus();
  });
}
