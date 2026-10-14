// node browser.mjs <chromium|firefox> <base> : lance le navigateur headless sur un
// profil jetable, exécute scenario.mjs, imprime les résultats (JSON en dernière ligne)
// et sort en 1 si une étape échoue. Variables : PROJECTS, WORK (dossiers de run.sh).
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { chromium, firefox, sleep } from "./drivers.mjs";
import { runScenario } from "./scenario.mjs";

const [which, base] = process.argv.slice(2);
const profile = mkdtempSync(join(process.env.WORK ?? tmpdir(), `profile-${which}-`));
const port = which === "chromium" ? 9333 : 9334;
const args =
  which === "chromium"
    ? ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--no-first-run", "--no-default-browser-check", "--disable-gpu", "about:blank"]
    : ["--headless", `--remote-debugging-port=${port}`, "--profile", profile, "--no-remote", "about:blank"];
// Groupe de processus propre : les lanceurs démarrent le vrai navigateur.
const child = spawn(which, args, { stdio: ["ignore", "ignore", "pipe"], detached: true });
const stop = () => {
  try {
    process.kill(-child.pid, "SIGTERM");
  } catch {}
};
let stderr = "";
child.stderr.on("data", (chunk) => (stderr += chunk));
let page;
for (let i = 0; i < 100 && !page; i += 1) {
  await sleep(200);
  try {
    page = which === "chromium" ? await chromium(port) : await firefox(port);
  } catch {}
}
if (!page) {
  console.error(stderr);
  stop();
  process.exit(2);
}
let failed = 1;
try {
  const results = await runScenario(page, { base, projects: process.env.PROJECTS, work: process.env.WORK, browser: which, log: console.log });
  failed = results.steps.filter((step) => step.status !== "OK").length;
  console.log(JSON.stringify({ browser: which, ...results }));
} finally {
  await page.close();
  stop();
  await new Promise((resolve) => setTimeout(resolve, 1000));
  rmSync(profile, { recursive: true, force: true });
}
process.exit(failed ? 1 : 0);
