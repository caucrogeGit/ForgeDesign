// Parcours sans JavaScript (FD-ACCEPTANCE-001) : Firefox avec javascript.enabled=false,
// piloté par WebDriver BiDi sans aucun script de page. Formulaires soumis par vrais
// clics et vraie saisie ; vérifications par localisation CSS/XPath (innerText n'est
// pas géré par Firefox). Fenêtre haute : sans script, pas de scrollIntoView.
// Usage : PROJECTS=<dossier> node nojs.mjs <base> ; sort en 1 si une étape échoue.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { sleep } from "./drivers.mjs";

const base = process.argv[2];
const projects = process.env.PROJECTS;
const P = (name) => join(projects, name);
const SECRETS = JSON.parse(readFileSync(join(projects, "..", "secrets.json"), "utf8"));
const profile = mkdtempSync(join(process.env.WORK ?? tmpdir(), "profile-nojs-"));
writeFileSync(join(profile, "user.js"), 'user_pref("javascript.enabled", false);\n');
// Groupe de processus propre : le lanceur « firefox » démarre le vrai navigateur.
const child = spawn("firefox", ["--headless", "--remote-debugging-port=9337", "--profile", profile, "--no-remote", "about:blank"], { stdio: "ignore", detached: true });
const stop = () => {
  try {
    process.kill(-child.pid, "SIGTERM");
  } catch {}
};

let ws;
for (let i = 0; i < 100 && !ws; i += 1) {
  await sleep(200);
  try {
    const socket = new WebSocket("ws://127.0.0.1:9337/session");
    await new Promise((resolve, reject) => {
      socket.onopen = resolve;
      socket.onerror = reject;
    });
    ws = socket;
  } catch {}
}
let id = 0;
const pending = new Map();
const events = [];
ws.onmessage = (message) => {
  const data = JSON.parse(message.data);
  if (pending.has(data.id)) {
    pending.get(data.id)(data);
    pending.delete(data.id);
  } else events.push(data);
};
const send = (method, params) =>
  new Promise((resolve) => {
    const n = ++id;
    pending.set(n, resolve);
    ws.send(JSON.stringify({ id: n, method, params }));
  });
await send("session.new", { capabilities: {} });
await send("session.subscribe", { events: ["browsingContext.load", "network.beforeRequestSent"] });
const context = (await send("browsingContext.getTree", {})).result.contexts[0].context;
await send("browsingContext.setViewport", { context, viewport: { width: 1280, height: 4000 } });

const locate = async (value, type = "css") => {
  const reply = await send("browsingContext.locateNodes", { context, locator: { type, value }, maxNodeCount: 500 });
  if (!reply.result) throw new Error(JSON.stringify(reply).slice(0, 300));
  return reply.result.nodes;
};
const count = async (css) => (await locate(css)).length;
const quote = (text) => `concat('${text.replaceAll("'", "', \"'\", '")}', '')`;
// Valeur textuelle complète de body : contains(text(), …) ne lirait que le premier
// nœud texte d'un élément.
const hasText = async (text) => (await locate(`//body[contains(., ${quote(text)})]`, "xpath")).length > 0;
const go = (path) => send("browsingContext.navigate", { context, url: `${base}${path}`, wait: "complete" });
const loaded = async (before) => {
  for (let i = 0; i < 400 && !events.slice(before).some((e) => e.method === "browsingContext.load"); i += 1) await sleep(50);
};
// Vrai clic sur un élément, attente du chargement suivant (sauf wait: false, par
// exemple pour ouvrir un <details>, natif sans script).
const click = async (css, { type = "css", wait = true } = {}) => {
  const [node] = await locate(css, type);
  assert.ok(node, `élément absent : ${css}`);
  const before = events.length;
  const reply = await send("input.performActions", {
    context,
    actions: [{ type: "pointer", id: "souris", parameters: { pointerType: "mouse" }, actions: [
      { type: "pointerMove", x: 0, y: 0, origin: { type: "element", element: { sharedId: node.sharedId } } },
      { type: "pointerDown", button: 0 },
      { type: "pointerUp", button: 0 },
    ] }],
  });
  assert.ok(!reply.error, JSON.stringify(reply).slice(0, 300));
  if (wait) await loaded(before);
};
// Vraie saisie dans un champ : clic, effacement, frappe, Entrée.
const fill = async (css, value, submit = true) => {
  const [node] = await locate(css);
  assert.ok(node, `champ absent : ${css}`);
  const focused = await send("input.performActions", {
    context,
    actions: [{ type: "pointer", id: "souris", parameters: { pointerType: "mouse" }, actions: [
      { type: "pointerMove", x: 0, y: 0, origin: { type: "element", element: { sharedId: node.sharedId } } },
      { type: "pointerDown", button: 0 },
      { type: "pointerUp", button: 0 },
    ] }],
  });
  // Champ vidé de façon déterministe : Fin (\uE010), puis Retour arrière (\uE003)
  // répété ; Ctrl+A puis Suppr ne remplaçait pas une valeur déjà présente.
  const keys = [
    { type: "keyDown", value: "\uE010" }, { type: "keyUp", value: "\uE010" },
    ...Array.from({ length: 400 }, () => [{ type: "keyDown", value: "\uE003" }, { type: "keyUp", value: "\uE003" }]).flat(),
    ...[...value].flatMap((c) => [{ type: "keyDown", value: c }, { type: "keyUp", value: c }]),
  ];
  assert.ok(!focused.error, `clic impossible sur ${css} : ${JSON.stringify(focused).slice(0, 200)}`);
  const before = events.length;
  await send("input.performActions", { context, actions: [{ type: "key", id: "clavier", actions: keys }] });
  if (submit) {
    await send("input.performActions", { context, actions: [{ type: "key", id: "clavier", actions: [{ type: "keyDown", value: "\uE006" }, { type: "keyUp", value: "\uE006" }] }] });
    await loaded(before);
  }
  await send("input.releaseActions", { context });
};
const noLeak = async (where) => {
  for (const secret of SECRETS) {
    // Texte de la page et tout attribut, sauf la saisie réaffichée par la recherche.
    const nodes = await locate(`//body[contains(., ${quote(secret)})] | //*[@*[contains(., ${quote(secret)})]][not(self::input[@id="debug-query"])]`, "xpath");
    assert.equal(nodes.length, 0, `${where} : ${secret}`);
  }
};

const steps = [];
const only = process.env.ONLY ? new RegExp(process.env.ONLY) : null;
const step = async (name, fn) => {
  if (only && !only.test(name)) return;
  try {
    await fn();
    steps.push({ name, status: "OK" });
    console.log(`  ✔ ${name}`);
  } catch (error) {
    steps.push({ name, status: "ÉCHEC", detail: String(error.message).slice(0, 400) });
    console.log(`  ✖ ${name} : ${error.message}`);
  }
};
// Ouverture comme un utilisateur : fermer le projet courant (le formulaire revient
// en haut de page, la synthèse disparaît), puis saisir le chemin.
const open = async (project) => {
  await go("/inspector");
  if ((await count('form[action="/project/close"] button')) > 0) await click('form[action="/project/close"] button');
  await go("/inspector");
  await fill("#project-path", project);
  assert.ok(await hasText(`Synthèse du projet ${project.split("/").pop()}`), `projet ${project} non ouvert`);
};

await step("sans JS : Project Inspector (formulaire, synthèse, sections)", async () => {
  await open(P("A"));
  assert.equal(await count(".health-summary"), 1);
  assert.equal(await count(".health-section"), 9);
  assert.ok(await hasText("Synthèse du projet A"));
});

await step("sans JS : A-no-bootstrap reconnu sans bootstrap.py, Structure et Routes OK (0.2.1)", async () => {
  await open(P("A-no-bootstrap"));
  assert.equal(await count('[data-health-section="structure"][data-status="ok"]'), 1);
  assert.equal(await count('[data-health-section="routes"][data-status="ok"]'), 1);
  assert.ok(await hasText("Élément optionnel absent."));
});

await step("sans JS : Route Explorer (tableau, chaînes, filtre, repli graphique serveur)", async () => {
  await open(P("B"));
  await go("/routes");
  assert.ok((await count("[id^=route-chain-]")) >= 4);
  assert.ok((await count("svg")) >= 1, "repli SVG serveur");
  await fill("#filter-query", "contact");
  assert.ok(await hasText("routes affichées sur"));
  await noLeak("/routes");
});

await step("sans JS : Entity Explorer (entités échappées, repli graphique serveur)", async () => {
  await go("/entities");
  assert.ok(await hasText("<script>alert(1)</script>"));
  assert.equal(await count("script:not([type='application/json'])"), await count("script[src]"), "aucun script en ligne exécutable");
  assert.ok((await count("svg")) >= 1, "repli SVG serveur");
});

await step("sans JS : Template Viewer (inventaire, lecture brute, arbre)", async () => {
  await go("/templates");
  assert.ok(await hasText("contacts/list.html"));
  await go("/templates/view?path=contacts%2Flist.html");
  assert.ok(await hasText("{% extends"));
  await go("/templates/tree?path=contacts%2Flist.html");
  assert.ok(await hasText("_table.html") || await hasText("base.html"));
});

await step("sans JS : Debug Center (liste masquée, filtre, détail avec flux SVG statique)", async () => {
  await go("/debug");
  assert.ok(await hasText("DB_PASSWORD=[masqué] connection refused"));
  await noLeak("/debug");
  await fill("#debug-query", "connection");
  const [link] = await locate('a[href^="/debug/event"]');
  assert.ok(link, "lien de détail");
  await click('a[href^="/debug/event"]');
  assert.ok((await count("svg")) >= 1, "flux SVG statique");
  assert.ok(await hasText("postgresql://roger:[masqué]@10.0.0.2/db"));
  await noLeak("/debug/event");
});

await step("sans JS : doctor, audit, check par POST natif, chacun dans sa section", async () => {
  await open(P("A"));
  await go("/debug");
  for (const key of ["audit", "diagnostic", "check"]) {
    await click(`section[data-command="${key}"] form button`);
    for (const other of ["audit", "diagnostic", "check"]) {
      const expected = other === key ? "succeeded" : "not-run";
      assert.equal(await count(`section[data-command="${other}"] [data-diagnostic-status="${expected}"]`), 1, `${key} → ${other}`);
    }
  }
});

// Contrat des modules (module-host.md) : sans JavaScript, métadonnées et diagnostics
// lisibles, message explicite, aucun rendu SVG serveur.
await step("sans JS : modules (navigation, métadonnées et message des ressources)", async () => {
  await open(P("B-write"));
  await go("/");
  assert.equal(await count('nav[aria-label="Modules"] a'), 2);
  for (const url of [
    "/modules/flowchart/resource?type=flowchart&path=mvc%2Fflowchart%2Fsimple.flow.json",
    "/modules/circuit/resource?type=schematic&path=mvc%2Fcircuit%2Fdemo.circuit.json",
  ]) {
    await go(url);
    assert.ok(await hasText("Validation"), url);
    assert.ok(await hasText("valide"), url);
    assert.ok(await hasText("La visualisation graphique nécessite JavaScript."), url);
  }
});

await step("sans JS : éditeur, vue périmée, racine et rechargement", async () => {
  await open(P("B-write"));
  await go("/editor?design=contacts%2Flist.design.json&node=1");
  const file = join(P("B-write"), "mvc/views/contacts/list.design.json");
  const data = JSON.parse(readFileSync(file, "utf8"));
  data.root.children.unshift({ type: "section", children: [] });
  writeFileSync(file, JSON.stringify(data) + "\n");
  const current = readFileSync(file);
  await click('form:has(input[name="action"][value="remove"]) button');
  assert.deepEqual(readFileSync(file), current);
  assert.ok(await hasText("Le design a été modifié depuis l’affichage"));
  assert.ok(await count('input[name="path"][value=""]'));
  await click('a[href="/editor?design=contacts%2Flist.design.json"]');
  assert.equal(await count('[role="alert"]'), 0);
  await click('form:has(input[name="action"][value="append"]) button');
  assert.ok(await hasText("Modification enregistrée."));
});

// Onglet B simulé côté Node : sa propre page, son propre formulaire, sa révision.
const postDisplayedForm = async (url, action, edit = {}) => {
  const html = await (await fetch(`${base}${url}`)).text();
  const form = [...html.matchAll(/<form action="\/editor\/action".*?<\/form>/gs)].map((m) => m[0]).find((f) => f.includes(`value="${action}"`));
  const fields = Object.fromEntries([...form.matchAll(/<input type="hidden" name="([^"]+)" value="([^"]*)"/g)].map((m) => [m[1], m[2]]));
  return fetch(`${base}/editor/action`, {
    method: "POST",
    redirect: "manual",
    headers: { "Content-Type": "application/x-www-form-urlencoded", Origin: base, "Sec-Fetch-Site": "same-origin" },
    body: new URLSearchParams({ ...fields, ...edit }),
  });
};

await step("sans JS : éditeur, vue périmée refusée par formulaire natif, aucun bloc touché", async () => {
  const designUrl = "/editor?design=contacts%2Flist.design.json";
  const file = join(projects, "B-write/mvc/views/contacts/list.design.json");
  await open(P("B-write"));
  assert.equal((await postDisplayedForm(designUrl, "append", { block_type: "section" })).status, 303);
  await go(`${designUrl}&node=1`);  // vue A : « table » au chemin 1
  assert.equal((await postDisplayedForm(`${designUrl}&node=0`, "remove")).status, 303);  // onglet B
  const s1 = readFileSync(file);
  await click('form input[name="action"][value="remove"] ~ button, form:has(input[value="remove"]) button');
  assert.ok(await hasText("Le design a été modifié depuis l’affichage de cette page."));
  assert.ok(await hasText("Recharger l’éditeur"));
  assert.ok(Buffer.compare(readFileSync(file), s1) === 0, "design identique à S1");
});

// FD-REALPREVIEW-008 : la preview réelle depuis Route Explorer est un formulaire
// HTML natif ; sans script, le cadre est rendu et l'arrêt reste un POST natif.
await step("sans JS : preview réelle depuis Route Explorer sans Design, POST natif, arrêt", async () => {
  await open(P("A-route-preview"));
  await go("/routes");
  const chain = "//li[starts-with(@id, 'route-chain-')][.//span[@class='route-chain' and starts-with(., 'GET /contacts ')]]";
  assert.equal((await locate(`${chain}[@data-real-preview='available']`, "xpath")).length, 1);
  await click(`${chain}/details/summary`, { type: "xpath", wait: false });
  await click(`${chain}//form[@action='/routes/real-preview/start']/button`, { type: "xpath" });
  assert.equal(await count('.real-preview-state[data-state="running"]'), 1);
  assert.equal(await count('iframe.real-preview-frame[src$="/contacts"]'), 1);
  await noLeak("/routes/real-preview");
  await click('form[action="/routes/real-preview/stop"] button');
  assert.equal(await count('.real-preview-state[data-state="stopped"]'), 1);
  assert.equal(await count("iframe.real-preview-frame"), 0);
});

await step("sans JS : aucune requête hors 127.0.0.1", async () => {
  const urls = events.filter((e) => e.method === "network.beforeRequestSent").map((e) => e.params.request.url);
  const external = urls.filter((u) => !/^(http:\/\/127\.0\.0\.1:\d+\/|about:|data:)/.test(u));
  assert.deepEqual([...new Set(external)], []);
});

await send("session.end", {});
ws.close();
stop();
await sleep(1000);
rmSync(profile, { recursive: true, force: true });
console.log(JSON.stringify({ browser: "firefox-nojs", steps }));
process.exit(steps.some((s) => s.status !== "OK") ? 1 : 0);
