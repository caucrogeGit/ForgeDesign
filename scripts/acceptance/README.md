# Kit d'acceptation — FD-ACCEPTANCE-001

Qualification de bout en bout de Forge Design, rejouable avant chaque release.
Hors paquet : rien de ce dossier n'entre dans la roue `forge-design`.

```bash
scripts/acceptance/run.sh <dossier-de-travail> [étape ...]
```

Étapes, dans l'ordre par défaut : `wheels install projects startup security
browsers nojs measures shutdown`. Tout est écrit sous `<dossier-de-travail>`
(roues, venvs, projets jetables, profils navigateur, journaux, résultats dans
`results/`) ; aucun projet utilisateur n'est lu ni modifié. Les étapes `browsers`
et `nojs` reconstruisent les projets avant et après chaque passage.

Prérequis : Python 3.12+, `pip` avec accès aux dépendances (téléchargées une fois
dans `deps/`, puis installation hors ligne), Node 24, `chromium` et `firefox`
dans le `PATH`, `ss`, `curl`. Variables : `CIRCUIT_REPO` et `FLOWCHART_REPO`
(dépôts des modules, par défaut à côté de ce dépôt), `PYTHON`, `PORT` (8765).

| Fichier | Rôle |
|---|---|
| `run.sh` | Orchestrateur : roues, venv neuf, serveur réel isolé (HOME/XDG propres), étapes |
| `build_projects.py` | Projets A, A-preview, A-bare, B, B-write, C, C-check, C-timeout, D, invalides |
| `fixtures/` | gx8 (projet hostile, base de B), ressources Circuit et Flowchart ; exclu de ruff |
| `probes.py` | Instantanés sha256, écarts, écoute, garde Host/Origin, processus, mémoire, mesures, roue |
| `drivers.mjs` | Pilotes Chromium (CDP) et Firefox (BiDi) sans dépendance ; réseau et CSP relevés |
| `browser.mjs`, `scenario.mjs` | Parcours complet avec JavaScript, modules actifs |
| `nojs.mjs` | Parcours Firefox sans JavaScript |

`ONLY=<regex>` restreint `scenario.mjs` aux étapes dont le nom correspond.
Les valeurs « secrètes » des fixtures sont synthétiques (`AccSecret123`…) et
servent uniquement à vérifier le masquage.

Écritures attendues, seules tolérées par les instantanés : éditeur et actions de
modules dans `B-write` (`.design.json`, ressources, `.forge-design/history.jsonl`,
rotation du journal faite par le scénario), sentinelle `CONTROLLER_IMPORTED` dans
`C-check`. Tout autre écart est signalé dans `results/diff-<navigateur>.txt`.
