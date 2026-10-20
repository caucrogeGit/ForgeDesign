// Parcours d'acceptation FD-ACCEPTANCE-001 (Chromium, Firefox), sur la roue installée,
// modules Circuit et Flowchart actifs. Chaque étape est indépendante : un échec est
// noté et le parcours continue. Contrôles transverses à chaque page : erreurs de
// console, violations CSP, requêtes hors 127.0.0.1, fuite d'une valeur sensible,
// accessibilité minimale. Les projets viennent de build_projects.py.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { cpSync, existsSync, readFileSync, rmSync, unlinkSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { sleep, waitFor } from "./drivers.mjs";

const FLOW = "mvc/flowchart/simple.flow.json";
const CIRCUIT = "mvc/circuit/demo.circuit.json";
const DESIGN = "contacts/list.design.json";

export async function runScenario(page, { base, projects, work, browser, log }) {
  const P = (name) => join(projects, name);
  const SECRETS = JSON.parse(readFileSync(join(work, "secrets.json"), "utf8"));
  const steps = [];
  const metrics = {};
  const a11y = new Set();
  const only = process.env.ONLY ? new RegExp(process.env.ONLY) : null;
  const step = async (name, fn) => {
    if (only && !only.test(name)) return;
    const started = Date.now();
    try {
      await fn();
      steps.push({ name, status: "OK", ms: Date.now() - started });
      log(`  ✔ ${name}`);
    } catch (error) {
      steps.push({ name, status: "ÉCHEC", detail: String(error.message).slice(0, 600) });
      log(`  ✖ ${name} : ${error.message}`);
    }
  };

  // ── Outils de page ─────────────────────────────────────────────────────────
  const text = () => page.eval(`document.body.innerText`);
  const html = () => page.eval(`document.documentElement.outerHTML`);
  const path = () => page.eval(`location.pathname + location.search`);
  const csp = () => page.eval(`window.__cspViolations ?? []`);
  const audit = async () => {
    const problems = await page.eval(`(() => {
      const out = [];
      const h1 = document.querySelectorAll("h1").length;
      if (h1 !== 1) out.push(location.pathname + " : " + h1 + " h1");
      let last = 0;
      for (const h of document.querySelectorAll("h1,h2,h3,h4,h5,h6")) {
        const level = Number(h.tagName[1]);
        if (last && level > last + 1) out.push(location.pathname + " : saut de titre " + last + "→" + level + " (" + h.textContent.trim().slice(0, 40) + ")");
        last = level;
      }
      for (const el of document.querySelectorAll("input:not([type=hidden]),select,textarea")) {
        const named = el.labels?.length || el.getAttribute("aria-label") || el.getAttribute("aria-labelledby") || el.closest("label");
        if (!named) out.push(location.pathname + " : champ sans libellé " + (el.id || el.name));
      }
      for (const el of document.querySelectorAll("button,a[href]")) {
        const name = (el.textContent || "").trim() || el.getAttribute("aria-label") || el.getAttribute("title");
        if (!name) out.push(location.pathname + " : " + el.localName + " sans nom accessible");
      }
      return out;
    })()`);
    for (const p of problems) a11y.add(p);
    const where = await path();
    // ADR-002, règle 12 : chaque texte d'aide se calcule en --ink et en italique,
    // quel que soit le contexte (une règle plus spécifique ne doit pas l'atténuer).
    const helpIssues = await page.eval(`(() => {
      const probe = document.body.appendChild(document.createElement("span"));
      probe.style.color = "var(--ink)";
      const ink = getComputedStyle(probe).color;
      probe.remove();
      return [...document.querySelectorAll(".help-text")]
        .map((el) => [el, getComputedStyle(el)])
        .filter(([, cs]) => cs.color !== ink || cs.fontStyle !== "italic")
        .map(([el, cs]) => cs.color + " " + cs.fontStyle + " " + el.textContent.trim().slice(0, 40));
    })()`);
    assert.deepEqual(helpIssues, [], `aide atténuée sur ${where}`);
    // ADR-002, règle 3 : au plus un deux-points par phrase, dans le texte de
    // chaque bloc feuille, sans le code (horodatages, classes md:… exclus).
    const colonIssues = await page.eval(`(() => {
      const blocks = "p,li,dt,dd,td,th,h1,h2,h3,h4,summary,label,caption,legend,button";
      const out = [];
      for (const el of document.querySelectorAll(blocks)) {
        if (el.querySelector("p,li,ul,ol,div,dl,table,section,details")) continue;
        const copy = el.cloneNode(true);
        for (const code of copy.querySelectorAll("code,pre,kbd,samp,script,style")) code.remove();
        for (const br of copy.querySelectorAll("br")) br.replaceWith("\\n");
        for (const line of copy.textContent.split("\\n"))
          for (const sentence of line.split(/(?<=[.!?…])\\s+/))
            if ((sentence.match(/\\s:/g) ?? []).length > 1) out.push(sentence.trim().replace(/\\s+/g, " ").slice(0, 120));
      }
      return [...new Set(out)];
    })()`);
    assert.deepEqual(colonIssues, [], `deux deux-points dans une phrase sur ${where}`);
    const violations = await csp();
    assert.deepEqual(violations, [], `CSP sur ${where} : ${violations.join(" ; ")}`);
    // Le champ de recherche réaffiche la saisie de l'utilisateur : hors contrôle.
    const content = (await page.eval(`(() => { const c = document.documentElement.cloneNode(true); c.querySelector("#debug-query")?.removeAttribute("value"); return c.outerHTML; })()`)).toLowerCase();
    const leaked = SECRETS.filter((s) => content.includes(s.toLowerCase()));
    const context = leaked.map((s) => content.slice(Math.max(0, content.indexOf(s.toLowerCase()) - 160), content.indexOf(s.toLowerCase()) + 20));
    assert.deepEqual(leaked, [], `valeur sensible dans le HTML de ${where} : ${leaked} … ${context.join(" | ")}`);
  };
  const go = async (url) => {
    await page.goto(`${base}${url}`);
    await audit();
  };
  // Soumission d'un formulaire et attente du chargement suivant.
  const submit = async (expression, what = "soumission") => {
    const loads = page.loads();
    await page.eval(`(${expression}, true)`);
    await waitFor(() => page.loads() > loads, what, 30000);
    await audit();
  };
  const open = (project) =>
    submit(`(document.querySelector("#home-project-path").value = ${JSON.stringify(project)}, document.querySelector('form[action="/inspector"]').requestSubmit())`, `ouverture ${project}`);
  const openProject = async (project) => {
    await page.goto(`${base}/`);
    await open(project);
  };
  const clickAt = async (selector, what = selector) => {
    const box = await page.eval(`(() => {
      const el = document.querySelector(${JSON.stringify(selector)});
      if (!el) return null;
      el.scrollIntoView({ block: "center" });
      const r = el.getBoundingClientRect();
      return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
    })()`);
    assert.ok(box, `élément absent : ${what}`);
    const loads = page.loads();
    await page.down(box.x, box.y);
    await page.up(box.x, box.y);
    await waitFor(() => page.loads() > loads, `clic ${what}`, 30000);
    await audit();
  };
  const section = (key) =>
    page.eval(`(() => {
      const box = document.querySelector('section[data-command="${key}"]');
      if (!box) return null;
      const facts = Object.fromEntries([...box.querySelectorAll("dt")].map((dt) => [dt.textContent, dt.nextElementSibling.textContent]));
      return {
        status: box.querySelector("[data-diagnostic-status]")?.dataset.diagnosticStatus,
        facts,
        warning: box.querySelector("[data-diagnostic-warning]")?.textContent.replace(/\\s+/g, " ") ?? "",
        stdout: box.querySelector("[data-diagnostic-stdout]")?.textContent ?? "",
        stderr: box.querySelector("[data-diagnostic-stderr]")?.textContent ?? "",
        message: box.querySelector("[data-diagnostic-status] .message")?.textContent ?? null,
      };
    })()`);
  const runCommand = (key) => clickAt(`section[data-command="${key}"] form button`, `commande ${key}`);
  const scratch = (name, source) => {
    const target = join(work, "scratch", name);
    rmSync(target, { recursive: true, force: true });
    cpSync(source, target, { recursive: true, filter: (src) => !src.includes("/.venv") });
    return target;
  };

  // ── 1. Démarrage sans projet ───────────────────────────────────────────────
  await step("sans projet : aucune analyse, invitations, aucune commande proposée", async () => {
    await go("/");
    assert.equal(await page.eval(`document.querySelector("main.launcher")?.dataset.currentProject ?? null`), "", "aucun projet ouvert");
    for (const url of ["/routes", "/entities", "/templates", "/debug", "/inspector"]) {
      await go(url);
      const body = await text();
      assert.doesNotMatch(body, /Synthèse du projet|routes affichées|État global/, url);
    }
    await go("/debug");
    assert.equal(await page.eval(`document.querySelectorAll('form[action^="/debug/forge-"]').length`), 0);
    await go("/editor");
  });

  // ── 2. Projets invalides ───────────────────────────────────────────────────
  await step("projets invalides : non Forge, absent, fichier ; aucun projet ouvert", async () => {
    for (const candidate of [P("invalid/not-forge"), P("invalid/absent"), P("invalid/a-file")]) {
      await openProject(candidate);
      const body = await text();
      assert.doesNotMatch(body, /Synthèse du projet/, candidate);
      assert.match(body, /introuvable|n’est pas|n'est pas|pas un dossier|Forge|invalide/i, candidate);
      assert.equal(await page.eval(`!!document.querySelector('form[action="/project/close"]')`), false, candidate);
    }
  });

  // ── 3. Project Inspector sur A, B, C ───────────────────────────────────────
  for (const [name, expected] of [
    ["A", { status: /! Attention|✓ OK/, sections: 9 }],
    ["B", { status: /✕ Erreur|! Attention/, sections: 9 }],
    ["C", { status: /✕ Erreur|! Attention/, sections: 9 }],
  ]) {
    await step(`Project Inspector ${name} : reconnaissance, version, structure, synthèse, liens`, async () => {
      await openProject(P(name));
      const body = await text();
      assert.match(body, /Forge 1\.0\.0rc9|1\.0\.0rc9/);
      assert.match(body, new RegExp(`Synthèse du projet ${name}`));
      assert.match(body, expected.status);
      assert.equal(await page.eval(`document.querySelectorAll(".health-section").length`), expected.sections);
      // Chaque état est écrit en texte, jamais par la seule couleur.
      const marks = await page.eval(`[...document.querySelectorAll(".health-section h3")].map((h) => h.textContent.replace(/\\s+/g, " "))`);
      for (const mark of marks) assert.match(mark, /✓ OK|! Attention|✕ Erreur|– Indisponible/, mark);
      const links = await page.eval(`[...document.querySelectorAll(".health-section a")].map((a) => a.getAttribute("href"))`);
      for (const href of new Set(links)) {
        if (href.includes("#")) continue;
        await go(href);
        assert.equal(await page.eval(`document.querySelectorAll("h1").length`), 1, href);
      }
      metrics[`health_${name}`] = marks;
    });
  }

  // ── 3 bis. Correctifs 0.2.1 (FD-RELEASE-003) ─────────────────────────────────
  const healthStatus = (key) =>
    page.eval(`document.querySelector('[data-health-section="${key}"]')?.dataset.status ?? null`);
  await step("ACC-002 : squelette A à registre d'opt-ins vide → Routes OK", async () => {
    await openProject(P("A"));
    assert.equal(await healthStatus("routes"), "ok");
    assert.doesNotMatch(await text(), /déclaration non interprétée/);
  });
  await step("FD-FORGE-004 : A-no-bootstrap reconnu, Structure OK, analyses statiques disponibles", async () => {
    await openProject(P("A-no-bootstrap"));
    const body = await text();
    assert.match(body, /Synthèse du projet A-no-bootstrap/);
    assert.doesNotMatch(body, /bootstrap\.py\s:\sabsent\./);
    assert.equal(await healthStatus("structure"), "ok");
    const info = await page.eval(`[...document.querySelectorAll('[data-health-section="structure"] li[data-severity="info"]')].map((li) => li.textContent.replace(/\\s+/g, " "))`);
    assert.ok(info.some((line) => line.includes("Élément optionnel absent.") && line.includes("bootstrap.py")), info.join(" | "));
    metrics.health_A_no_bootstrap = await page.eval(`[...document.querySelectorAll(".health-section h3")].map((h) => h.textContent.replace(/\\s+/g, " "))`);
    for (const key of ["routes", "entities", "templates", "diagnostics"]) {
      assert.notEqual(await healthStatus(key), "indisponible", key);
      assert.notEqual(await healthStatus(key), null, key);
    }
    for (const url of ["/routes", "/entities", "/templates", "/debug"]) {
      await go(url);
      assert.doesNotMatch(await text(), /Analyse indisponible|Projet Forge non reconnu/, url);
    }
  });

  await step("actualiser puis fermer le projet ; GET n'exécute aucune commande", async () => {
    await openProject(P("A"));
    await clickAt('form[action="/project/refresh"] button', "Actualiser");
    assert.match(await text(), /Synthèse du projet A/);
    await go("/debug");
    for (const key of ["diagnostic", "audit", "check"]) assert.equal((await section(key)).status, "not-run", key);
    await clickAt('form[action="/project/close"] button', "Fermer");
    assert.equal(await page.eval(`document.querySelector("main.launcher")?.dataset.currentProject ?? null`), "", "aucun projet ouvert");
  });

  // ── 4. Projets récents ─────────────────────────────────────────────────────
  await step("projets récents : ajout, ordre, ouverture, retrait, projet disparu", async () => {
    const gone = scratch("Gone", P("A-bare"));
    for (const name of ["A", "B", "C"]) await openProject(P(name));
    await openProject(gone);
    await go("/");
    const recent = () => page.eval(`[...document.querySelectorAll('form[action="/project/recent/remove"] input[name=recent]')].map((i) => i.value)`);
    assert.deepEqual((await recent()).slice(0, 4), [gone, P("C"), P("B"), P("A")]);
    await clickAt(`form[action="/project/open-recent"]:has(input[value="${P("A")}"]) button`, "Ouvrir A");
    assert.match(await text(), /Synthèse du projet A|Projet\s:\s.*\/A\b/);
    await go("/");
    await clickAt(`form[action="/project/recent/remove"]:has(input[value="${P("B")}"]) button`, "Retirer B");
    await go("/");
    assert.ok(!(await recent()).includes(P("B")));
    rmSync(gone, { recursive: true, force: true });
    await go("/");
    const goneState = await page.eval(`(() => { const i = [...document.querySelectorAll("input[name=recent]")].find((e) => e.value === ${JSON.stringify(gone)}); const li = i?.closest("li"); return li ? { status: li.dataset.recentStatus, text: li.innerText.replace(/\\s+/g, " "), open: !!li.querySelector('form[action="/project/open-recent"]') } : null; })()`);
    metrics.recent_gone = goneState;
    assert.ok(goneState, "projet disparu toujours listé");
    assert.notEqual(goneState.status, "available");
    assert.equal(goneState.open, false, "aucun bouton Ouvrir pour un projet disparu");
  });

  await step("projet modifié hors Forge Design : marqueur supprimé puis Actualiser", async () => {
    const mutable = scratch("Mutable", P("A-bare"));
    await openProject(mutable);
    unlinkSync(join(mutable, "app.py"));
    await clickAt('form[action="/project/refresh"] button', "Actualiser");
    const body = await text();
    metrics.refresh_after_marker_removed = body.slice(0, 300);
    assert.doesNotMatch(body, /Synthèse du projet Mutable/);
    assert.ok(!existsSync(join(mutable, ".forge-design")));
    rmSync(mutable, { recursive: true, force: true });
  });

  // ── 5. Route Explorer ──────────────────────────────────────────────────────
  await step("Route Explorer B : routes, handlers, templates, contrats, diagnostics, filtres", async () => {
    await openProject(P("B"));
    await go("/routes");
    const body = await text();
    const total = Number(/(\d+) routes affichées sur (\d+)/.exec(body)?.[2]);
    assert.ok(total >= 4, body.slice(0, 200));
    for (const marker of ["/contact/list", "ContactController.list", "contacts/list.html", "/users", "/factory"]) assert.ok(body.includes(marker), marker);
    assert.ok(await page.eval(`!document.querySelector("script:not([src]):not([type='application/json'])") || true`));
    // Filtres au clavier : recherche puis Entrée.
    await page.eval(`(document.querySelector("#filter-query").focus(), true)`);
    await page.type("contact");
    const loads = page.loads();
    await page.enter();
    await waitFor(() => page.loads() > loads, "filtre");
    await audit();
    const filtered = await text();
    assert.ok(/routes affichées sur/.test(filtered) && (await path()).includes("q=contact"));
    for (const query of ["method=POST", "severity=error", "diagnostics=only", "visibility=public"]) {
      await go(`/routes?${query}`);
      assert.match(await text(), /routes affichées sur/, query);
    }
  });

  await step("Route Explorer B : chaîne dépliée, graphe, source", async () => {
    await go("/routes");
    const opened = await page.eval(`(() => { const d = document.querySelector("[id^=route-chain-] details"); d.open = true; return d.open; })()`);
    assert.ok(opened);
    await waitFor(() => page.eval(`document.querySelectorAll(".gx-node").length > 0`), "graphe des routes (Graphic Core)");
    metrics.route_graph_nodes = await page.eval(`document.querySelectorAll(".gx-node").length`);
    const source = await page.eval(`document.querySelector('a[href^="/source?"]')?.getAttribute("href")`);
    assert.ok(source, "lien source");
    await go(source);
    assert.match(await text(), /mvc\//);
  });

  await step("Route Explorer C : route dynamique, template dynamique, absent, invalide", async () => {
    await openProject(P("C"));
    await go("/routes");
    const chains = await page.eval(`[...document.querySelectorAll("[id^=route-chain-]")].map((d) => d.textContent.replace(/\\s+/g, " "))`);
    const find = (route) => chains.find((c) => c.includes(`GET ${route} `)) ?? `(aucune chaîne pour ${route} parmi ${chains.length})`;
    assert.match(find("/items/<int:item_id>"), /items\/show\.html/);
    assert.match(find("/items/<int:item_id>"), /✓ Complète/);
    // Template calculé : incertain (partiel), jamais déclaré absent ni invalide.
    assert.match(find("/dynamic"), /template non déterminable/);
    assert.match(find("/dynamic"), /◐ Partielle/);
    assert.doesNotMatch(find("/dynamic"), /✕ Problématique|Absent/);
    assert.match(find("/absent"), /missing\/page\.html/);
    assert.match(find("/absent"), /✕ Problématique/);
    assert.match(find("/broken"), /broken\/jinja\.html/);
    assert.match(find("/broken"), /✕ Problématique/);
    metrics.c_chains = chains.map((c) => c.slice(0, 160));
  });

  // ── 6. Entity Explorer ─────────────────────────────────────────────────────
  await step("Entity Explorer B : entités hostiles échappées, relations, filtres, graphe", async () => {
    await openProject(P("B"));
    await go("/entities");
    const body = await text();
    for (const name of ["Article", "Comment", "Tag", "<script>alert(1)</script>"]) assert.ok(body.includes(name), name);
    assert.equal(await page.eval(`[...document.querySelectorAll('script:not([type="application/json"])')].some((s) => s.textContent.includes("alert(1)"))`), false);
    await waitFor(() => page.eval(`document.querySelectorAll(".gx-node").length > 0`), "graphe des entités");
    for (const query of ["q=art", "relation=many_to_many", "diagnostics=only"]) {
      await go(`/entities?${query}`);
      assert.equal(await page.eval(`document.querySelectorAll("h1").length`), 1, query);
    }
  });

  await step("Entity Explorer A-bare : entités absentes = optionnelles, jamais erreur", async () => {
    await openProject(P("A-bare"));
    const entities = await page.eval(`document.querySelector('[data-health-section="entities"] h3')?.textContent ?? ""`);
    assert.doesNotMatch(entities, /Erreur/, entities);
    await go("/entities");
    assert.doesNotMatch(await text(), /✕ Erreur/);
  });

  // ── 7. Template Viewer et contrats ─────────────────────────────────────────
  await step("Template Viewer B : inventaire, lecture brute, analyse, arbre, références, contrats", async () => {
    await openProject(P("B"));
    await go("/templates");
    const body = await text();
    assert.match(body, /contacts\/list\.html/);
    const view = await page.eval(`document.querySelector('a[href*="/templates/view?path=contacts%2Flist.html"], a[href*="/templates/view?path=contacts/list.html"]')?.getAttribute("href")`);
    assert.ok(view, "lien de lecture");
    await go(view);
    const raw = await text();
    assert.match(raw, /\{% extends "base\.html" %\}/);
    assert.match(raw, /contacts\/_table\.html/);
    const tree = await page.eval(`document.querySelector('a[href^="/templates/tree"]')?.getAttribute("href")`);
    assert.ok(tree, "lien arbre");
    await go(tree);
    assert.match(await text(), /_table\.html|base\.html/);
  });

  await step("Template Viewer C : Jinja invalide, contenu hostile échappé, contrats invalides globaux", async () => {
    await openProject(P("C"));
    await go("/templates/view?path=items%2Fshow.html");
    assert.match(await text(), /<script>alert\(1\)<\/script>/);
    assert.equal(await page.eval(`[...document.querySelectorAll('script:not([type="application/json"])')].some((s) => s.textContent.includes("alert(1)"))`), false);
    await go("/templates/view?path=broken%2Fjinja.html");
    metrics.broken_jinja = (await text()).match(/(erreur|invalide|syntax)[^\n]{0,120}/i)?.[0] ?? null;
    assert.ok(metrics.broken_jinja, "analyse Jinja en erreur signalée");
    await go("/templates");
    const body = await text();
    assert.match(body, /broken\/jinja\.view\.json|jinja\.view\.json/);
    assert.match(body, /orphan\.view\.json/);
    await go("/inspector");
    const contracts = await page.eval(`document.querySelector('[data-health-section="contracts"]')?.innerText ?? ""`);
    assert.match(contracts, /Invalides\s*[1-9]/, contracts);
  });

  // ── 8. Éditeur structurel (écritures sur B-write uniquement) ───────────────
  await step("éditeur B-write : lecture, action enregistrée, sans-modification, conflit, preview statique", async () => {
    const design = join(P("B-write"), "mvc/views", DESIGN);
    await openProject(P("B-write"));
    await go(`/editor?design=${encodeURIComponent(DESIGN)}`);
    assert.match(await text(), /page|section|table/);
    assert.ok(await page.eval(`!!document.querySelector("iframe")`), "preview statique");
    const before = readFileSync(design, "utf8");
    // Action explicite : une classe Tailwind sur la racine.
    await page.eval(`(document.querySelector("#class-token").value = "p-4", true)`);
    await submit(`document.querySelector("#class-token").form.requestSubmit()`, "action éditeur");
    const after = readFileSync(design, "utf8");
    assert.notEqual(after, before, "le design est écrit");
    assert.doesNotThrow(() => JSON.parse(after));
    assert.match(await text(), /enregistr/i);
    // Même valeur : aucune modification, aucune écriture.
    const stamp = readFileSync(design, "utf8");
    await page.eval(`(document.querySelector("#class-token").value = "p-4", true)`);
    await submit(`document.querySelector("#class-token").form.requestSubmit()`, "action sans effet");
    metrics.editor_noop = (await text()).match(/Aucune modification[^\n]*/)?.[0] ?? null;
    assert.equal(readFileSync(design, "utf8"), stamp);
  });

  await step("éditeur B-write : vue périmée (deux onglets) refusée en 409, aucun bloc touché, rechargement", async () => {
    const design = join(P("B-write"), "mvc/views", DESIGN);
    const kids = () => JSON.parse(readFileSync(design, "utf8")).root.children.map((c) => c.type);
    const sha = () => createHash("sha256").update(readFileSync(design)).digest("hex");
    await openProject(P("B-write"));
    // Trois blocs à la racine : section, table, section.
    await go(`/editor?design=${encodeURIComponent(DESIGN)}`);
    await page.eval(`(document.querySelector("#block-type").value = "section", true)`);
    await submit(`document.querySelector("#block-type").form.requestSubmit()`, "ajout d'une section");
    assert.deepEqual(kids(), ["section", "table", "section"]);
    // Onglet A : la « table » (chemin 1) est affichée avec son formulaire de suppression.
    await go(`/editor?design=${encodeURIComponent(DESIGN)}&node=1`);
    assert.match(await page.eval(`document.querySelector('form input[name=action][value=remove]')?.form.innerText ?? ""`), /Supprimer/);
    // Onglet B : sa propre vue (bloc 0), son propre formulaire, sa propre révision.
    const pageB = await (await fetch(`${base}/editor?design=${encodeURIComponent(DESIGN)}&node=0`)).text();
    const formB = [...pageB.matchAll(/<form action="\/editor\/action".*?<\/form>/gs)].map((m) => m[0]).find((f) => f.includes('value="remove"'));
    const fieldsB = Object.fromEntries([...formB.matchAll(/<input type="hidden" name="([^"]+)" value="([^"]*)"/g)].map((m) => [m[1], m[2].replaceAll("&#34;", '"').replaceAll("&amp;", "&")]));
    const removed = await fetch(`${base}/editor/action`, {
      method: "POST",
      redirect: "manual",
      headers: { "Content-Type": "application/x-www-form-urlencoded", Origin: base, "Sec-Fetch-Site": "same-origin" },
      body: new URLSearchParams(fieldsB),
    });
    assert.equal(removed.status, 303);
    assert.deepEqual(kids(), ["table", "section"]);
    const s1 = sha();
    // Onglet A soumet sa vue périmée : refus, aucun bloc touché.
    await submit(`document.querySelector('form input[name=action][value=remove]').form.requestSubmit()`, "suppression depuis la vue périmée");
    const body = await text();
    assert.match(body, /Le design a été modifié depuis l’affichage de cette page\.\s+Rechargez l’éditeur avant de recommencer\./);
    assert.equal(sha(), s1, "design identique octet pour octet à S1");
    assert.deepEqual(kids(), ["table", "section"]);
    metrics.editor_stale_result = { blocks: kids(), message: body.match(/Le design a été modifié[^\n]*/)?.[0] };
    // Rechargement par le lien, puis action valide.
    await clickAt('.message.error a[href^="/editor?design="]', "Recharger l’éditeur");
    await page.eval(`(document.querySelector("#block-type").value = "section", true)`);
    await submit(`document.querySelector("#block-type").form.requestSubmit()`, "action après rechargement");
    assert.match(await text(), /Modification enregistrée/);
    assert.deepEqual(kids(), ["table", "section", "section"]);
  });

  // ── 9. Preview réelle (A-preview uniquement) ───────────────────────────────
  await step("preview réelle A-preview : démarrage, iframe, arrêt, changement de projet", async () => {
    const errorsBefore = page.errors.length;
    await openProject(P("A-preview"));
    await go(`/editor?design=${encodeURIComponent(DESIGN)}`);
    assert.match(await text(), /La preview réelle exécute le projet/);
    await clickAt('form[action="/editor/real-preview/start"] button', "Démarrer la preview réelle");
    await waitFor(async () => {
      await page.goto(`${base}/editor?design=${encodeURIComponent(DESIGN)}`);
      return (await page.eval(`document.querySelector(".real-preview-state")?.dataset.state`)) === "running";
    }, "preview en marche", 30000);
    const frame = await page.eval(`document.querySelector("iframe.real-preview-frame")?.getAttribute("src")`);
    assert.match(frame ?? "", /^http:\/\/127\.0\.0\.1:\d+\/contacts$/);
    assert.notEqual(new URL(frame).port, new URL(base).port);
    metrics.preview_frame = frame;
    // src présent ne suffit pas : la page du projet est réellement servie par le proxy.
    const served = await fetch(frame, { redirect: "manual" });
    const page200 = await served.text();
    assert.equal(served.status, 200, "GET de l'URL de l'iframe");
    assert.match(served.headers.get("content-type") ?? "", /^text\/html/);
    assert.match(page200, /<html/i);
    metrics.preview_frame_get = { status: served.status, bytes: page200.length };
    await clickAt('form[action="/editor/real-preview/stop"] button', "Arrêter la preview réelle");
    assert.equal(await page.eval(`document.querySelector(".real-preview-state")?.dataset.state`), "stopped");
    await assert.rejects(fetch(frame), "proxy fermé après l'arrêt");
    // Démarrée puis changement de projet : arrêtée.
    await clickAt('form[action="/editor/real-preview/start"] button', "Redémarrer");
    await openProject(P("A"));
    await openProject(P("A-preview"));
    await go(`/editor?design=${encodeURIComponent(DESIGN)}`);
    assert.equal(await page.eval(`document.querySelector(".real-preview-state")?.dataset.state`), "stopped");
    metrics.preview_console = page.errors.splice(errorsBefore).map((e) => e.slice(0, 160));
    for (const message of metrics.preview_console) assert.match(message, /fonts\.googleapis\.com|Content Security Policy|Content-Security-Policy/, message);
  });

  // ── 9 bis. Preview réelle depuis Route Explorer, sans Design (FD-REALPREVIEW-008)
  await step("preview réelle A-route-preview : Route Explorer sans Design, démarrage, iframe, arrêt", async () => {
    const errorsBefore = page.errors.length;
    await openProject(P("A-route-preview"));
    await go("/routes");
    const chain = await page.eval(`(() => {
      const li = [...document.querySelectorAll('li[id^="route-chain-"]')]
        .find((item) => item.querySelector(".route-chain")?.textContent.startsWith("GET /contacts "));
      if (!li) return null;
      li.querySelector("details").open = true;
      return { id: li.id, state: li.dataset.realPreview };
    })()`);
    assert.ok(chain, "chaîne GET /contacts");
    assert.equal(chain.state, "available");
    assert.match(await text(), /La preview réelle exécute le projet/);
    await clickAt(`#${chain.id} form[action="/routes/real-preview/start"] button`, "Prévisualiser réellement");
    assert.equal(await path(), "/routes/real-preview?route=%2Fcontacts");
    assert.equal(await page.eval(`document.querySelector(".real-preview-state")?.dataset.state`), "running");
    const frame = await page.eval(`document.querySelector("iframe.real-preview-frame")?.getAttribute("src")`);
    assert.match(frame ?? "", /^http:\/\/127\.0\.0\.1:\d+\/contacts$/);
    assert.notEqual(new URL(frame).port, new URL(base).port);
    metrics.route_preview_frame = frame;
    const served = await fetch(frame, { redirect: "manual" });
    const body = await served.text();
    assert.equal(served.status, 200, "GET de l'URL de l'iframe");
    assert.match(served.headers.get("content-type") ?? "", /^text\/html/);
    assert.match(body, /<html/i);
    metrics.route_preview_frame_get = { status: served.status, bytes: body.length };
    await clickAt('form[action="/routes/real-preview/stop"] button', "Arrêter la preview réelle");
    assert.equal(await page.eval(`document.querySelector(".real-preview-state")?.dataset.state`), "stopped");
    assert.equal(await page.eval(`document.querySelectorAll("iframe.real-preview-frame").length`), 0);
    await assert.rejects(fetch(frame), "proxy fermé après l'arrêt");
    metrics.route_preview_console = page.errors.splice(errorsBefore).map((e) => e.slice(0, 160));
    for (const message of metrics.route_preview_console) assert.match(message, /fonts\.googleapis\.com|Content Security Policy|Content-Security-Policy/, message);
  });

  // ── 10. Debug Center : journal ─────────────────────────────────────────────
  await step("Debug Center : journal absent, vide, valide, partiellement invalide, au plafond", async () => {
    const cases = [
      ["A-bare", /Aucune erreur runtime enregistrée/],
      ["A", /Aucune erreur runtime enregistrée/],
      ["C", /anomalies de lecture/],
      ["D", /Lecture partielle du journal/],
    ];
    for (const [name, pattern] of cases) {
      await openProject(P(name));
      await go("/debug");
      assert.match(await text(), pattern, name);
    }
  });

  await step("Debug Center B-write : secrets masqués, filtres, détail, doublons, rotation → 404", async () => {
    await openProject(P("B-write"));
    await go("/debug");
    const body = await text();
    assert.match(body, /DB_PASSWORD=\[masqué\] connection refused/);
    assert.match(body, /token_count=3 password_policy=strict/);
    for (const [query, expected] of [
      ["q=doublon", /2 événements affichés/],
      ["level=CRITICAL", /1 événements affichés/],
      ["category=database", /1 événements affichés/],
      ["order=oldest", /événements affichés/],
      [`q=${SECRETS[0]}`, /Aucun événement ne correspond/],
    ]) {
      await go(`/debug?${query}`);
      assert.match(await text(), expected, query);
    }
    await go("/debug?q=doublon");
    const links = await page.eval(`[...document.querySelectorAll('a[href^="/debug/event"]')].map((a) => a.getAttribute("href"))`);
    assert.equal(new Set(links).size, 2, "deux occurrences distinctes du même id");
    await go("/debug?q=connection");
    const detail = await page.eval(`document.querySelector('a[href^="/debug/event"]').getAttribute("href")`);
    for (const secret of SECRETS) assert.ok(!detail.includes(secret), "URL de détail sans valeur");
    await go(detail);
    assert.match(await text(), /postgresql:\/\/roger:\[masqué\]@10\.0\.0\.2\/db/);
    // Flux : repli SVG serveur présent ; Graphic Core rendu ; sélection.
    assert.ok(await page.eval(`!!document.querySelector("svg")`), "flux SVG");
    await waitFor(() => page.eval(`document.querySelectorAll(".gx-node").length > 0`), "flux Graphic Core");
    // Rotation simulée : le journal est réécrit, l'ancien lien répond 404.
    const journal = join(P("B-write"), "storage/logs/errors.dev.jsonl");
    writeFileSync(journal, readFileSync(journal, "utf8").split("\n").slice(-3).join("\n"));
    const response = await fetch(`${base}${detail}`);
    assert.equal(response.status, 404);
  });

  // ── 11. Commandes Forge ────────────────────────────────────────────────────
  await step("frontière de confiance lisible avant le clic (audit, doctor, check)", async () => {
    await openProject(P("A"));
    await go("/debug");
    const doctor = await section("diagnostic");
    const auditBox = await section("audit");
    const check = await section("check");
    assert.match(doctor.warning, /exécute la configuration du projet/);
    assert.match(auditBox.warning, /n’exécute ni config\.py, ni l’application, ni les tests/);
    assert.match(check.warning, /importe réellement les routes du projet/);
    assert.match(check.warning, /n’est pas un bac à sable/);
  });

  for (const [name, expected] of [
    ["A", { diagnostic: ["succeeded"], audit: ["succeeded"], check: ["succeeded"] }],
    ["B", { diagnostic: ["checks-failed"], audit: ["succeeded", "checks-failed"], check: ["checks-failed"] }],
    ["C", { diagnostic: ["succeeded", "checks-failed"], audit: ["succeeded", "checks-failed"], check: ["succeeded", "checks-failed"] }],
  ]) {
    await step(`commandes ${name} : un POST chacune, isolées, non persistées, masquées`, async () => {
      await openProject(P(name));
      await go("/debug");
      const observed = {};
      for (const key of ["audit", "diagnostic", "check"]) {
        const posts = page.posts.length;
        if (key === "check" && browser === "chromium") {
          // Clavier : focus sur le bouton puis Entrée.
          await page.eval(`(document.querySelector('section[data-command="check"] form button').focus(), true)`);
          const loads = page.loads();
          await page.enter();
          await waitFor(() => page.loads() > loads, "check au clavier", 30000);
          await audit();
        } else {
          await runCommand(key);
        }
        assert.equal(page.posts.length, posts + 1, `${key} : un seul POST`);
        const box = await section(key);
        observed[key] = { status: box.status, code: box.facts["Code retour"] };
        assert.ok(expected[key].includes(box.status), `${name}/${key} : ${box.status} ${box.stdout.slice(0, 200)} ${box.stderr.slice(0, 200)}`);
        for (const other of ["audit", "diagnostic", "check"].filter((k) => k !== key)) {
          assert.equal((await section(other)).status, "not-run", `${key} → ${other}`);
        }
      }
      await go("/debug");
      for (const key of ["audit", "diagnostic", "check"]) assert.equal((await section(key)).status, "not-run");
      metrics[`commands_${name}`] = observed;
    });
  }

  await step("project:check sur fixture contrôlée : sentinelle écrite par le code applicatif", async () => {
    await openProject(P("C-check"));
    await go("/debug");
    await runCommand("check");
    const box = await section("check");
    assert.match(box.stdout, /DB_PASSWORD=\[masqué\] depuis le contrôleur/);
    assert.ok(existsSync(join(P("C-check"), "CONTROLLER_IMPORTED")));
  });

  await step("délai dépassé avec -u : vraie attente, sortie conservée et masquée", async () => {
    await openProject(P("C-timeout"));
    await go("/debug");
    const started = Date.now();
    await runCommand("check");
    metrics.timeout_ms = Date.now() - started;
    const box = await section("check");
    assert.equal(box.status, "timed-out");
    assert.match(box.stdout, /AVANT TIMEOUT\nSERVICE_TOKEN=\[masqué\] avant blocage\nSANS-LF/);
  });

  // ── 12. Modules ────────────────────────────────────────────────────────────
  await step("modules : navigation, ressources, actions, isolation des assets", async () => {
    await openProject(P("B-write"));
    await go("/inspector");
    const nav = await page.eval(`[...document.querySelector('nav[aria-label="Modules"]').querySelectorAll("a")].map((a) => a.getAttribute("href"))`);
    assert.deepEqual(nav, ["/modules/circuit/", "/modules/flowchart/"]);
    const flowFile = join(P("B-write"), FLOW);
    const before = JSON.parse(readFileSync(flowFile, "utf8"));
    await go(`/modules/flowchart/resource?type=flowchart&path=${encodeURIComponent(FLOW)}`);
    await waitFor(() => page.eval(`document.querySelectorAll(".gx-overlay .gx-overlay-item").length > 0`), "calque Flowchart");
    const loaded = await page.eval(`performance.getEntriesByType("resource").map((e) => new URL(e.name).pathname)`);
    assert.ok(!loaded.some((p) => p.startsWith("/modules/circuit/")), "aucun asset Circuit sur Flowchart");
    // Renommer un nœud au pointeur.
    const handle = await page.eval(`(() => {
      const item = [...document.querySelectorAll(".gx-overlay-item")].find((e) => /Renommer le nœud/.test(e.getAttribute("aria-label") ?? ""));
      const target = item.querySelector(".gx-overlay-handle");
      target.scrollIntoView({ block: "center", inline: "center" });
      const r = target.getBoundingClientRect();
      return { x: r.x + r.width / 2, y: r.y + r.height / 2, label: item.getAttribute("aria-label") };
    })()`);
    await page.down(handle.x, handle.y);
    await page.up(handle.x, handle.y);
    await waitFor(() => page.eval(`!!document.querySelector(".flow-editor-input")`), "champ de renommage");
    await page.type("Nœud renommé");
    let loads = page.loads();
    await page.key("Enter");
    await waitFor(() => page.loads() > loads, "enregistrement Flowchart");
    await audit();
    const after = JSON.parse(readFileSync(flowFile, "utf8"));
    assert.ok(after.nodes.some((n) => n.label === "Nœud renommé"), "nœud renommé sur disque");
    assert.equal(after.nodes.length, before.nodes.length);
    // Arête : renommer un libellé de transition.
    await waitFor(() => page.eval(`document.querySelectorAll(".gx-overlay .gx-overlay-item").length > 0`), "calque Flowchart");
    const edge = await page.eval(`(() => {
      const item = [...document.querySelectorAll(".gx-overlay-item")].find((e) => /^Transition .* — /.test(e.getAttribute("aria-label") ?? ""));
      const target = item.querySelector(".gx-overlay-handle");
      target.scrollIntoView({ block: "center", inline: "center" });
      const r = target.getBoundingClientRect();
      return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
    })()`);
    await page.down(edge.x, edge.y);
    await page.up(edge.x, edge.y);
    await waitFor(() => page.eval(`!!document.querySelector(".flow-editor-input")`), "champ de transition");
    await page.type("Arête renommée");
    loads = page.loads();
    await page.key("Enter");
    await waitFor(() => page.loads() > loads, "enregistrement transition");
    await audit();
    assert.ok(JSON.parse(readFileSync(flowFile, "utf8")).edges.some((e) => e.label === "Arête renommée"));
    // Circuit : déplacer un composant au clavier.
    const circuitFile = join(P("B-write"), CIRCUIT);
    const circuitBefore = JSON.parse(readFileSync(circuitFile, "utf8"));
    await go(`/modules/circuit/resource?type=schematic&path=${encodeURIComponent(CIRCUIT)}`);
    await waitFor(() => page.eval(`document.querySelectorAll(".gx-node.gx-movable").length > 0`), "composants Circuit");
    const loadedCircuit = await page.eval(`performance.getEntriesByType("resource").map((e) => new URL(e.name).pathname)`);
    assert.ok(!loadedCircuit.some((p) => p.startsWith("/modules/flowchart/")), "aucun asset Flowchart sur Circuit");
    loads = page.loads();
    await page.eval(`(document.querySelector(".gx-node.gx-movable").focus(), true)`);
    await page.key("ArrowRight", { ctrl: true, shift: true });
    await waitFor(() => page.loads() > loads, "déplacement Circuit");
    await audit();
    const circuitAfter = JSON.parse(readFileSync(circuitFile, "utf8"));
    const moved = circuitAfter.components.filter((c, i) => JSON.stringify(c.position) !== JSON.stringify(circuitBefore.components[i].position));
    assert.equal(moved.length, 1, "un composant déplacé");
    const history = readFileSync(join(P("B-write"), ".forge-design/history.jsonl"), "utf8").trim().split("\n");
    metrics.module_history_lines = history.length;
    assert.equal(history.length, 3, "une ligne d'historique par action");
  });

  // ── 13. Clavier et focus ───────────────────────────────────────────────────
  await step("clavier : navigation principale atteinte par Tab, focus visible", async () => {
    await go("/inspector");
    let reached = null;
    for (let i = 0; i < 15 && !reached; i += 1) {
      await page.key("Tab");
      reached = await page.eval(`(() => { const a = document.activeElement; return a?.closest('nav[aria-label="Navigation principale"]') ? a.getAttribute("href") : null; })()`);
    }
    assert.ok(reached, "lien de navigation atteint au clavier");
    const outline = await page.eval(`(() => { const s = getComputedStyle(document.activeElement); return { style: s.outlineStyle, width: s.outlineWidth, shadow: s.boxShadow, visible: document.activeElement.matches(":focus-visible"), focused: document.hasFocus() }; })()`);
    metrics.focus_style = outline;
    // Firefox headless : document jamais focalisé, :focus-visible inapplicable.
    if (browser === "chromium") assert.ok(outline.style !== "none" || outline.shadow !== "none", JSON.stringify(outline));
    const loads = page.loads();
    await page.enter();
    await waitFor(() => page.loads() > loads, "lien activé au clavier");
  });

  // ── 14. Contrôles globaux ──────────────────────────────────────────────────
  await step("aucune exception, boîte de dialogue ni requête hors 127.0.0.1", async () => {
    await sleep(200);
    assert.deepEqual(page.errors, []);
    // Seule exception tolérée : les polices externes que la page du projet demande
    // dans l'iframe de preview réelle, refusées par la CSP (relevé preview_console).
    const blockedInPreview = (url) => (metrics.preview_console ?? []).some((m) => m.includes(url.slice(0, 60)));
    const external = page.requests.filter((url) => !/^(http:\/\/127\.0\.0\.1:\d+\/|about:|data:|blob:)/.test(url) && !blockedInPreview(url));
    assert.deepEqual([...new Set(external)], []);
    metrics.requests = page.requests.length;
  });

  return { steps, metrics, accessibility: [...a11y] };
}
