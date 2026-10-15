# Rapport — FD-AUDIT-002

Audit d'état global de Forge Design, sans changement fonctionnel. Date : 2026-10-15.

## Objectif

Répondre, preuves à l'appui, à la question : **où en est réellement Forge Design,
qu'est-ce qui est terminé, qu'est-ce qui reste ouvert, et quelle est la prochaine
étape logique ?**

Aucun fichier de `forge_design/`, des tests, du kit, de Circuit, de Flowchart ou de
SéquenCiel n'est modifié. Il n'y a ni nettoyage, ni stash, ni push.

Réponse courte :

| Question | Réponse |
|---|---|
| 1. Baseline stable | `7805152`, release locale 0.2.0 qualifiée. Son `forge_design/` est identique à celui de `8ca9b72`, la baseline de l'acceptance. |
| 2. Parties stabilisées | Les cinq outils Forge, le runtime borné, l'éditeur (ACC-004), la preview réelle (ACC-003), le Graphic Core, le Module Host et deux modules externes : tous qualifiés de bout en bout. |
| 3. Dettes et travaux ouverts | Travail qualifié mais non committé (FD-EDITOR-008, FD-ACC-002, FD-STABILISATION-001), 13 commits non poussés, et un **nouveau défaut de détection** qui refuse SéquenCiel. |
| 4. Toujours prêt pour SéquenCiel ? | **Non, en l'état.** Le gate est OPEN sur les fixtures, mais la 0.2.0 refuse le vrai projet : `bootstrap.py : absent.` |
| 5. Prochaine étape | **FD-FORGE-004** : reconnaître un projet Forge sans `bootstrap.py`, comme le fait forge-mvc 1.0.0rc9. |

## État Git initial

Commandes du §4 exécutées au démarrage.

| Élément | Valeur |
|---|---|
| Branche | `main`, seule branche locale ; aucune autre branche distante que `origin/main` |
| HEAD | `7805152` (FD-RELEASE-002) |
| `origin/main` (référence locale) | `e411d0c` (FD-PROJECT-006) |
| `origin/main` réel (`git ls-remote origin`) | `e411d0c` : la référence locale est à jour |
| Écart | **0 commit en retard, 13 en avance** |
| Tags | Aucun |
| Stash | Vide |
| Worktrees | Le dépôt principal seul, avant la création de celui de cet audit (voir Fichiers modifiés) |
| Index | Vide |
| `git status --short` | 11 fichiers modifiés et 16 entrées non suivies, soit **593 fichiers** avec `--untracked-files=all` |
| Collision FD-AUDIT-002 | Aucune : l'identifiant n'apparaît nulle part dans le dépôt |

## Baseline auditée

**Baseline : `7805152`.** Elle est qualifiée dans un worktree détaché et propre
(`git worktree add --detach tmp/fd-audit-002/wt 7805152`), avec 0 ligne de
`git status` avant comme après.

Le travail non committé est **exclu** de cette qualification. Il est mesuré à part
sur l'arbre courant, à titre d'information.

`forge_design/` et `pyproject.toml` sont identiques entre `8ca9b72` (baseline de
FD-ACCEPTANCE-002), `b38a2c2` (commit de release) et `7805152` (vérifié par
`git diff`). Le code audité est donc exactement celui qui a passé l'acceptance et
la release.

## Travail concurrent

Rien n'est committé au-delà de `7805152`. Trois travaux sont terminés et qualifiés
sur disque, sans commit, et un rapport n'est qu'une proposition.

### Fichiers suivis modifiés (11)

| Fichier | Travail | Classement |
|---|---|---|
| `forge_design/design/io.py`, `forge_design/web/editor.py` | FD-EDITOR-008 | modifié, qualifié |
| `tests/test_design_io.py`, `tests/test_web_editor.py`, `tests/test_web_editor_revision.py` | FD-EDITOR-008 | modifié, qualifié |
| `scripts/acceptance/run.sh` | FD-EDITOR-008 (autorise le chemin du verrou de la fixture) | modifié, qualifié |
| `docs/design/design-json.md`, `docs/editor/structural-editor.md` | FD-EDITOR-008 | modifié |
| `forge_design/forge/routes.py`, `docs/tools/route-explorer.md` | FD-ACC-002 | modifié, qualifié |
| `docs/rapports/FD-CONTRACT-001.md` | Utilisateur : un titre changé d'un caractère (« État Git initiala ») | modifié, **préservé, non touché** |

### Fichiers non suivis (582)

| Groupe | Nombre | Classement |
|---|---:|---|
| `forge_design/design/locking.py`, `tests/test_design_locking.py`, `tests/test_design_concurrency.py` | 3 | non suivi, FD-EDITOR-008 |
| `forge_design/forge/optin_routes.py`, `tests/test_optin_routes.py` | 2 | non suivi, FD-ACC-002 |
| `FD-EDITOR-008-RAPPORT.md`, `FD-ACC-002-RAPPORT.md`, `FD-STABILISATION-001-RAPPORT.md`, `FD-ACCEPTANCE-001-REQUALIFICATION-RAPPORT.md`, `FD-EDITOR-007-VERIFICATION.md` | 5 | non suivi, rapports de travaux exécutés |
| `FD-RELEASE-003-PROPOSITION.md` | 1 | **rapport seulement** : proposition non exécutée |
| Preuves : `fd-acceptance-001-requalification-20261015/` (381), `fd-stabilisation-001/` (106), `fd-acc-002/` (37), `fd-editor-008/` (29), `fd-editor-007-verification/` (18) | 571 | non suivi, preuves archivées |

### Preuves temporaires hors dépôt

- `/tmp/fd-acc-002-20261015/` : copies des projets A, B, C et des deux cas altérés d'ACC-002 ;
- `/tmp/fd-acceptance-final-20261015/` : passes de la requalification ;
- le scratchpad tmpfs d'une autre session Claude : il contient les **seuls exemplaires** des artefacts de release 0.2.0. Leurs SHA-256 sont revérifiés et identiques au rapport FD-RELEASE-002.

### État de chaque travail

| Travail | Commit | Qualification | Statut |
|---|---|---|---|
| **FD-EDITOR-008**, verrou interprocessus des mutations de designs | Aucun | 600 courses, 27 pannes par stockage (ext4 et tmpfs), navigateurs, suite complète ; **acceptance complète** en deux passes sur une roue contenant `locking.py` (requalification FD-ACCEPTANCE-001, base `837bf1b` + 008) | Terminé, non committé, **hors release 0.2.0** |
| **FD-ACC-002**, opt-ins vides du squelette | Aucun | 37 tests, tranche ciblée de 238 tests, suite complète de 5 173 tests ; pas d'acceptance navigateur | Terminé, non committé, hors release |
| **FD-STABILISATION-001**, lint des scripts de preuve | Aucun | `ruff check .` à 0 ; preuves rejouées | Terminé, non committé, hors code produit |
| **FD-RELEASE-003** | — | — | Proposition à valider, non commencée |

**Le code 008 n'a pas bougé depuis sa requalification.** Les 648 empreintes de
`qualified.json` ont été comparées à l'arbre courant : 634 fichiers identiques.
Les 14 différences sont `forge_design/forge/routes.py` (ACC-002, postérieur), le
README (FD-DOCS-001, committé) et 12 documents. **008 et ACC-002 n'ont jamais été
qualifiés ensemble par l'acceptance navigateur** ; ils ne l'ont été que par la
suite Python (5 173 tests réussis, rejoués ici).

## Historique récent

Les 13 commits locaux non poussés sont tous **terminés**, chacun avec son rapport :

| Commit | Ticket | Nature |
|---|---|---|
| `87adc58` | FD-ROUTES-021 | Chaîne route → handler → template → contrat |
| `a34ee3f` | FD-PERF-001 | Détection de la racine partagée pour les contrats |
| `4bf67ab` | FD-RUNTIME-001 | `forge doctor` à la demande |
| `12dd8c7` | FD-DEBUG-006 | Masquage renforcé |
| `2da0d67` | FD-RUNTIME-002 | `project:audit` |
| `942775f` | FD-RUNTIME-003 | `project:check` |
| `08a4354` | FD-RUNTIME-004 | `-u`, sortie partielle avant délai |
| `97a214a` | FD-ACCEPTANCE-001 | Kit d'acceptance ; verdict REJECTED (ACC-004) |
| `561ff93` | FD-EDITOR-007 | ACC-004 : vue périmée refusée en 409 |
| `8ca9b72` | FD-REALPREVIEW-007 | ACC-003 : `-I -B -u`, aucun bytecode écrit |
| `837bf1b` | FD-ACCEPTANCE-002 | ACCEPTED_WITH_MINOR_ISSUES ; gate OPEN |
| `b38a2c2` | FD-DOCS-001 | ACC-001 : l'URL `127.0.0.1` |
| `7805152` | FD-RELEASE-002 | RELEASE_READY |

Ce sont des travaux **terminés mais non poussés**, pas des travaux en cours.
FD-ARCH-001, FD-RELEASE-001 et FD-PROJECT-006 sont déjà sur `origin/main`.

## Version

| Source | Valeur |
|---|---|
| `forge_design.__version__` (baseline et arbre courant) | `0.2.0` |
| `pyproject.toml` | `dynamic = ["version"]`, lu dans `forge_design.__version__` |
| METADATA de la roue de release (SHA-256 `9e4c3c36…1a65`) | `Version: 0.2.0`, 166 fichiers, sans `locking.py` ni `optin_routes.py` |
| Installation du `.venv` | Éditable, pointe sur le dépôt principal, donc **sur l'arbre non committé** |

Le `.venv` de développement n'exécute donc pas la release 0.2.0, mais le travail
en cours. Cela compte pour tout essai lancé depuis ce venv.

## Architecture générale

L'architecture réelle correspond à la cible :

```text
Forge Design (forge_design/)
├── outils Forge : 5 Tools du ToolRegistry (forge_design/tools, web/)
├── moteur générique
│   ├── Resource Host : forge_design/specialized (lecture, écriture, historique)
│   ├── Module Host : forge_design/modules (descripteur, activation, actions, hôte)
│   ├── Graphic Core : web/static/graphics/*.js + forge_design/graphics/lanes.py
│   ├── révision / conflit : revision_tokens.py, design/io.py, specialized/resource.py
│   ├── filesystem sécurisé : forge/filesystem.py, checked_root.py, safewrite/
│   └── preview / édition : preview/, real_preview/, editor/, design/
└── modules externes, dépôts séparés : ForgeDesign-Circuit, ForgeDesign-Flowchart
```

## Frontières core / modules

Toutes les vérifications ont été faites sur la baseline.

| Dérive recherchée | Constat |
|---|---|
| Circuit dans le cœur | **Aucune.** `grep -i circuit` sur `.py`, `.js`, `.html` et `.css` de `forge_design/` : 0 occurrence |
| Flowchart dans le cœur | **Aucune**, en dehors du témoin de test `tests/flow_witness/` (normatif, FD-ARCH-001) |
| Sémantique spécialisée dans le Graphic Core | **Aucune** : vocabulaire générique uniquement (nœuds, arêtes, variantes, tonalités, calques) |
| Modules enregistrés comme Tools | **Non** : `forge_design/modules` n'importe pas le `ToolRegistry` ; un module apparaît sous « Modules » |
| Outil Forge dépendant d'un module | **Non** : aucun import de `forge_design_circuit` ni de `forge_design_flowchart` dans le cœur |

Les tests de garde sont verts : `test_module_boundaries.py`,
`test_graphics_forge_boundary.py` et `test_modules_contract.py`.

## ToolRegistry

Le registre a été instancié réellement, avec `create_tool_registry()`, hors du dépôt :
**5 Tools**, conformément à l'attendu :

```text
project-inspector, route-explorer, entity-explorer, debug-center, template-viewer
```

Le registre est explicite : ordre d'insertion, identifiant kebab-case, doublon refusé.
Il n'y a ni découverte automatique ni chargement dynamique. FD-RELEASE-002 a
constaté les mêmes 5 Tools avec les deux modules actifs.

## Graphic Core

Inventaire fait dans le code (`engine.js` et ses modules) et dans les 134 tests Node.

| Capacité | Présente | Preuve |
|---|---|---|
| Scène validée (`validateScene`, bornes : 5 000 nœuds, 20 000 arêtes) | Oui | `model.js`, `model.test.mjs` |
| Nœuds et arêtes (variantes, tonalités, `label` + `labelAt`, flèches) | Oui | `model.js`, `svg-renderer.js` |
| Viewport (fit, zoom, pan, home, resize, `centerAt`) | Oui | `viewport.js`, `engine-viewport.test.mjs` |
| Niveaux de détail (overview, normal, detail) | Oui | `detail-level.js` |
| Minicarte | Oui | `minimap.js`, `engine-minimap.test.mjs` |
| Sélection de nœud | Oui | `scene.js` `createSelection`, `selection.test.mjs` |
| Sélection d'arête | **Non** | Non prévue (roadmap, piste C) |
| `nodeMove` opt-in (souris et Ctrl + Maj + flèches) | Oui | `engine-move.test.mjs` |
| Calques monde `addOverlay` | Oui | `engine-overlay.test.mjs` |
| `worldAt`, `onViewChange` | Oui | `engine.js` l. 84–720 |
| Historique, undo et redo | **Non, côté JS** | L'historique est côté serveur : `.forge-design/history.jsonl` pour les actions de modules. Les designs n'ont pas d'historique. |
| Repli serveur sans JavaScript | Oui | SVG serveur pour les routes, les entités et le flux Debug (`web/*_scene.py`), qualifié sans JavaScript |
| Formes autres que le rectangle | **Non** | Limite de Flowchart, candidate `presentation.shape` non créée |

Le Graphic Core a trois clients dans le cœur (routes, entités, flux Debug) et deux
modules.

## Module Host

| Élément | État réel |
|---|---|
| `ModuleDescriptor` | `definition`, `version`, `api_version`, `bindings`, `asset_package`, `assets`, `dependency_probe`, `actions`, `requires_forge_design` |
| `ResourceBinding` | `resource_type`, `codec`, `scene`, `editor_script`, `editor_config` |
| `ModuleAsset` | `name`, `source` ; types de médias bornés (`ASSET_MEDIA_TYPES`) |
| `ModuleAction` | POST exact par action, payload borné (`MAX_MODULE_ACTION_*`), jeton de révision opaque, handler pur, écriture et historique par le cœur |
| `MODULE_API_VERSION` | `1` ; `SUPPORTED_MODULE_API_VERSIONS = {1}` |
| `requires_forge_design` | Spécificateur PEP 440 vérifié à l'activation ; diagnostics `core-version-incompatible` et `core-version-unknown` |
| Activation | Explicite, `--module PAQUET`, uniquement des paquets nommés, jamais depuis un projet |
| Routes, assets, ressources | GET exacts sous `/modules/<id>/`, assets déclarés et isolés par module (FD-RELEASE-002) |

L'API publique est figée par `__all__` (25 noms dans `forge_design.modules`, 30
dans `forge_design.specialized`).

## Circuit

| Élément | Valeur |
|---|---|
| Version | `forge-design-circuit` 0.1.0, API de modules 1 |
| Commit | `967b5b3` ; arbre propre ; `origin/main` identique (`ls-remote`) ; aucun tag |
| Compatibilité | `forge-design>=0.2.0,<1`, identique dans `Requires-Dist` et dans le descripteur |
| Démontré | Ressources `*.circuit.json`, validation, projection, déplacement de composant, routes orthogonales, connexions, dérivations, évitement local (FDC-EDIT-001 à 007) ; qualifié avec la 0.2.0 |
| Limites | Pas de simulation ; la création et la modification de connexions ne sont pas rejouées par le kit d'acceptance (requalification) ; l'export SVG du modèle n'est pas fait |

## Flowchart

| Élément | Valeur |
|---|---|
| Version | `forge-design-flowchart` 0.1.0, API de modules 1 |
| Commit | `a8ec22d` (FD-MODULE-PILOT-001) ; arbre propre ; `origin/main` identique ; aucun tag |
| Compatibilité | `forge-design>=0.2.0,<1` ; aucune dépendance à Circuit |
| Démontré | Second pilote **réalisé sans aucune modification du cœur** : renommage de nœuds et d'arêtes, coexistence avec Circuit, qualifié avec la 0.2.0 |
| Limites | Ni création, ni suppression, ni déplacement ; rectangles seulement (pas de losange) ; pas de repli textuel sans JavaScript |

## Project Inspector

| Capacité | État |
|---|---|
| Détection du projet | Exige `app.py`, `bootstrap.py`, `config.py`, `mvc/` et `mvc/routes/` ; ne fait que des `stat`, sans import |
| Forge et version | Version lue avec sa source ; compatibilité « non évaluée » : aucune règle de version Forge |
| Synthèse santé | 9 sections (Projet, Forge, Structure, Routes, Entités, Templates, Migrations, Diagnostics, Contrats), état global, `no-store` |
| Projets récents | Ajout, ordre, retrait, projet disparu (`missing`) |
| Qualification | FD-ACCEPTANCE-002 et FD-RELEASE-002, avec la réserve ACC-002 |

**Nouveau constat : la détection est plus stricte que Forge.** forge-mvc 1.0.0rc9
traite `bootstrap.py` comme optionnel. `core/app/app_factory.py::load_bootstrap`
dit : « Un projet sans `bootstrap.py` n'en a pas besoin », avec rien à migrer
(ADR-093).

Forge Design l'exige pourtant (`project_detection.py`, l. 87, depuis FD-FORGE-002).
Un projet Forge valide créé avant ce câblage est donc refusé. SéquenCiel est dans
ce cas (voir SéquenCiel readiness).

## Route Explorer

Capacités qualifiées : route, handler, contrôleur, méthode, candidats de template
avec niveau de confiance, contrats de vue, diagnostics avec origine et état de
chaîne, filtres, graphe (22 nœuds sur B), source.

C'est une lecture **statique** : aucun opt-in, aucune configuration et aucun import
dynamique ne sont exécutés. Les limites sont documentées
(`docs/tools/route-explorer.md`).

**ACC-002, vérifié ici par une sonde en lecture seule** sur les copies du kit, sans
modification des sources (empreintes identiques) :

| Projet | Baseline `7805152` | Arbre courant (FD-ACC-002 non committé) |
|---|---|---|
| A, squelette nominal | **Attention** (« Ligne 23 : déclaration non interprétée. ») | OK |
| A sans l'appel `register_optins` | OK (lacune) | Attention |
| A avec `other_router` | Attention | Attention |

**ACC-002 reste ouvert dans la baseline.** Le correctif existe, mais il n'est pas
committé : c'est le travail nommé FD-ACC-002, qui réalise ce que les rapports
appelaient FD-ROUTES-022. Il ne reconnaît que le registre **vide** conventionnel.
Un registre actif, comme celui de SéquenCiel, reste une limite signalée.

## Entity Explorer

Capacités qualifiées : entités, champs, relations, diagnostics, filtres, graphe.
Le contenu hostile est échappé, et l'absence d'entités reste optionnelle.

Limites assumées : bornes centralisées (256 fichiers, 4 096 entrées, 512 relations,
256 champs) avec avertissements de troncature, et un ordre non garanti au-delà de
4 096 entrées.

## Template Viewer

Capacités qualifiées : inventaire, lecture brute, structure (arbre), références,
diagnostics Jinja (syntaxe invalide localisée), contrats de vue (JSON invalide
compté, sans template, multiples).

Aucun rendu : l'analyse est syntaxique, avec des bornes (512 fichiers, profondeur 8,
1 Mio par source).

## Debug Center

Quatre niveaux de confiance, distincts dans le code et dans l'interface :

| Niveau | Code projet exécuté ? | config | routes | Base possible | Réseau possible | Délai | Masquage |
|---|---|---|---|---|---|---|---|
| Journal runtime (`storage/logs/errors.dev.jsonl`) | Non : lecture bornée | Non | Non | Non | Non | Sans objet (lecture bornée à 8 Mio) | Oui |
| `project:audit` | Non (lecture seule, Forge rc9) | Non | Non | Non | Non | 10 s | Oui |
| `doctor` | Oui : `config.py` | Oui | Non | **Oui** | Oui (base distante) | 10 s | Oui |
| `project:check` | Oui : importe les routes et les contrôleurs | Oui | Oui | Oui | Oui | 10 s | Oui |

Le masquage est **non exhaustif** par contrat (FD-DEBUG-006 : secret sans clé, clé
métier inconnue, base64…). Il n'y a pas de bac à sable : seule la frontière de
processus protège Forge Design.

## Runtime commands

Vérifié dans le code de la baseline (`runtime_diagnostics.py`, `limits.py`) :

| Garantie | État |
|---|---|
| Interpréteur | `<racine>/.venv/bin/python -s -B -P -u -m forge <commande>`, cwd = racine |
| Liste fermée | 3 commandes : `doctor`, `project:audit`, `project:check` |
| `-u` | Présent pour les trois commandes |
| Délai | `FORGE_DIAGNOSTIC_TIMEOUT_SECONDS = 10.0` |
| Borne de sortie | `MAX_FORGE_DIAGNOSTIC_OUTPUT_BYTES = 256 * 1024`, par flux |
| Groupe de processus | `start_new_session=True`, puis `os.killpg(SIGKILL)` |
| Masquage | `redact_debug_text(clean_output(...))` sur les sorties |
| stdout et stderr partiels | Conservés au délai dépassé (pytest sur les trois commandes ; navigateur pour stdout) |
| Déclenchement | POST explicite seulement ; un GET n'exécute rien ; rien n'est persisté |

Limites assumées : code 1 ambigu, Python principal seul tamponné par `-u`, enfant
détaché non arrêté, pas de streaming.

## Real Preview

| Garantie | État |
|---|---|
| Interpréteur | Python du projet (`.venv`), `-I -B -u child_bootstrap.py --port <éphémère>` |
| Proxy | Listener dédié `127.0.0.1:<port>`, origine distincte ; aucune redirection suivie |
| Health | `GET /health` direct, sans proxy ni redirection, corps exact |
| Loopback | `HOST = "127.0.0.1"` pour l'enfant et le proxy ; autre hôte refusé |
| Stop | Signal au groupe (`killpg`) ; proxy arrêté puis joint |
| Changement de projet | `ProjectSelector(before_change=runtime.stop)` ; fermeture refusée si l'arrêt échoue |
| Arrêt du serveur | Ctrl+C, SIGTERM et SIGHUP ferment la preview, puis l'écoute |
| ACC-003 | Corrigé : aucun bytecode écrit, caches existants intacts (FD-ACCEPTANCE-002) |

Limite de contrat : le code de l'application garde ses effets de bord (journaux,
base, fichiers).

## Éditeur structurel

| Élément | État |
|---|---|
| `DesignFile` / `NodePath` | `NodePath` repose sur des indices : toute modification périme la page |
| Actions | Dix actions mutables, toutes paramétrées dans `test_web_editor_revision.py` |
| Jeton de révision | Opaque, commun avec les actions de modules (`revision_tokens.py`) |
| Vue périmée | **409**, aucune mutation (ACC-004 corrigé, deux navigateurs et sans JavaScript, deux passes) |
| Écriture | `write_design` : création exclusive (`link`), mise à jour atomique (`replace`), fsync du temporaire et du répertoire |
| Historique | Aucun pour les designs ; il n'existe que pour les ressources de modules |

## write_design / concurrence

| Question | Réponse |
|---|---|
| Fenêtre de concurrence dans la baseline ? | **Oui.** Aucun verrou interprocessus. La doc de la baseline le dit (`design-json.md`, l. 437 : « pas de verrou interprocessus »). Les témoins de FD-EDITOR-008, exécutés sur `561ff93` (dont `io.py` et `editor.py` sont identiques à `7805152`), montrent : deux threads WSGI → 303 et 500 ; deux processus → une réussite et une sauvegarde incertaine. |
| Atteignable avec le produit livré ? | **Pas par l'interface seule.** Le serveur traite une requête à la fois (`ForgeDesignServer` sans `ThreadingMixIn`, figé par un test), et le port est fixe (8765), donc il ne peut y avoir qu'un serveur à la fois. Il faut un second écrivain : un script appelant l'API publique `write_design` pendant que le Web tourne. |
| FD-EDITOR-008 terminé ? | **Oui, localement** : implémenté et qualifié (voir Travail concurrent). |
| `locking.py` intégré ? | Dans l'arbre de travail seulement. **Absent** de la baseline, de la roue 0.2.0 et de tout commit. |
| Tests de concurrence présents ? | `tests/test_design_concurrency.py` et `tests/test_design_locking.py`, non suivis ; verts dans la suite de l'arbre courant (5 173 tests). |
| Commit existant ? | **Aucun.** |
| Modifie la baseline `RELEASE_READY` ? | **Non.** La 0.2.0 qualifiée ne contient pas 008 ; sa limite est déclarée dans ses notes de release. Intégrer 008 demande une nouvelle version (CORRECTIVE, 0.2.1) et une requalification de l'ensemble. |

Constat associé, **plausible et non reproduit** : `write_specialized_resource`
(actions des modules) suit le même schéma, sans verrou, même dans l'arbre courant.
Il vérifie la révision deux fois puis publie par `replace`. FD-EDITOR-008 ne couvre
que les designs.

La même atténuation s'applique (serveur mono-thread). Un ticket éventuel devra
d'abord reproduire la course.

## Design / génération

| Capacité | API interne | Exposée dans l'interface | Testée |
|---|---|---|---|
| `.design.json` (schéma, modèles, bindings) | Oui | Oui (éditeur) | Oui |
| Validation | Oui | Oui (diagnostics de l'éditeur) | Oui |
| Éditeur structurel (dix actions) | Oui | Oui : `GET /editor`, `POST /editor/action` | Oui, plus l'acceptance |
| Preview statique | Oui | Oui : `GET /editor/preview` | Oui, plus l'acceptance |
| Preview réelle | Oui | Oui (démarrage et arrêt dans l'éditeur) | Oui, plus l'acceptance |
| Génération de template Jinja (`forge_design/generate`) | Oui | **Non** : aucun import dans `web/` | **Testée seulement** |
| SAFEWRITE (détection, décision, écriture anti-écrasement) | Oui | **Non** | **Testée seulement** |
| Historique de génération (`generate/history.py`) | Oui | Indirectement : réutilisé par l'historique des ressources de modules | Oui |

Aucun module de `forge_design/web/` n'importe `forge_design.generate` ni
`forge_design.safewrite`. Le seul consommateur hors de ces paquets est
`specialized/resource.py`, pour l'historique.

## Filesystem sécurisé

Primitives présentes dans `forge_design/` (nombre de fichiers) : `dir_fd` 15,
`O_NOFOLLOW` 17, `O_NONBLOCK` 14, `O_DIRECTORY` 10, `fstat` 16, `samestat` 17.

Bornes centralisées dans `limits.py` : 1 Mio par source, chemins de 4 096 caractères,
et bornes par outil.

Les symlinks de signature du projet sont refusés. La racine passe toujours par
`resolve_project_root`. Les lectures sont ancrées sur des descripteurs.

Limite documentée : les analyses supposent les parents stables. Il n'y a pas
d'instantané atomique du contenu.

## Web local / sécurité

Sonde HTTP réelle sur la baseline (`create_server(port=0)`, HOME isolé, aucun
fichier écrit) :

| Requête | Résultat |
|---|---|
| Écoute | `127.0.0.1` uniquement ; port par défaut `8765` (`DEFAULT_PORT`) |
| `GET /`, `Host: 127.0.0.1:<port>` | 200, `Cache-Control: no-store`, CSP présente |
| `Host: localhost:<port>` | 400, `no-store` |
| `Host: evil.example` | 400 |
| `POST /project/close` sans Origin | 403 |
| … avec une Origin étrangère | 403 |
| … avec `Sec-Fetch-Site: cross-site` | 403 |

`no-store` est posé par défaut par `Application` de forge-mvc (`setdefault`), et
explicitement sur le refus de Host et sur le proxy de preview. Le contrôle d'origine
(`is_local_action`) est un contrôle navigateur : ce n'est pas une authentification
des clients locaux.

## Packaging

| Point | Constat |
|---|---|
| Roue et sdist 0.2.0 | Construits deux fois, contenu identique, identiques à Git (FD-RELEASE-002). Les artefacts existent encore, **uniquement en tmpfs volatile** (scratchpad d'une autre session), SHA-256 revérifiés. |
| Avertissement setuptools 84 | Toujours d'actualité : `web.static`, `web.static.graphics` et `web.templates` sont absents de `packages` (déclarés seulement en `package-data`). Sans effet sur le contenu. |
| Matrice Python | Absente : `requires-python >=3.12`, seul `/usr/bin/python3.13` est installé ; 3.12 n'est jamais testé |
| Licence | **Aucun `LICENSE`**, aucun champ de licence dans la METADATA. La roadmap demande de décider « avant la première diffusion versionnée ». |
| Dépendance Forge | `forge-mvc==1.0.0rc9` épinglé ; une seule version supportée |
| CI, changelog, signature | Absents |

## Documentation

| Point | Constat |
|---|---|
| ACC-001 | Corrigé (`b38a2c2`) : le README et le cadrage donnent `http://127.0.0.1:8765/` |
| README | Cohérent avec le contrat (URL, `--module`, versions) |
| Architecture (`02-architecture.md`) | Cohérente avec le code audité (CLI livrée, frontières, `no-store`, preview) |
| Docs de la baseline sur la concurrence | Honnêtes : aucun verrou annoncé |
| Docs modifiées hors commit | `design-json.md`, `structural-editor.md` et `route-explorer.md` décrivent 008 et ACC-002 : elles sont **en avance sur la baseline** |
| MkDocs | Non configuré |
| `project-inspector.md` | Exige `bootstrap.py`, conforme au code mais pas à forge-mvc rc9 |

## Roadmap vs réalité

| Phase ou piste | Statut réel | Écart |
|---|---|---|
| 0–2. Fondation, paquet, tranche lecture seule | Terminée | Aucune marque « fait » dans le texte historique ; FD-INSPECTOR-002 n'a pas de rapport (couvert par FD-PROJECT-*) |
| 3. Platform et contrat Tool | Terminée | — |
| 4. Interface Web locale | Terminée | Pile annoncée « Tailwind, HTMX, Alpine » : **obsolète**. Il n'y a ni HTMX ni Alpine ; Tailwind n'existe que comme classes éditées dans les designs |
| 5. Diagnostics Forge | Partiellement terminée | Trois commandes faites ; migrations et routes exécutées, non |
| 6. Exploration | Terminée | — |
| 7. Stockage `.forge-design/` | Terminée | — |
| 8. Conception de vues | Partiellement terminée | Génération et SAFEWRITE : API testée, **non exposée dans l'interface** |
| 9. Contrat d'outil spécialisé | Terminée | — |
| 10. Circuit (historique) | Obsolète comme phase du cœur | FD-CIRCUIT-004 à 008 sont désormais des tickets du module (numérotés FDC-*) |
| Modules | Terminée | **Incohérence factuelle corrigée ici** : Flowchart était encore « recommandé » comme second pilote, alors qu'il existe (0.1.0, `a8ec22d`) et qu'il est qualifié par FD-RELEASE-002 |
| Piste B, suite recommandée | Inexacte | **Corrigée ici** : l'essai SéquenCiel demande d'abord un correctif de détection |
| 11. 3D | Non commencée | — |
| 12. Intégration applicative | Non commencée | Annoncée « ouverte », sans ticket |
| Licence (gouvernance) | Non décidée | Toujours ouverte, alors qu'une release est qualifiée |

Le code n'est en avance sur la roadmap que par le travail non committé (008,
ACC-002), ce qui est normal puisqu'il n'est pas livré.

## Tests et niveau de preuve

| Niveau | Baseline `7805152` (cet audit) | Arbre courant (information) |
|---|---|---|
| `pytest --collect-only` | 5 097 tests | 5 173 tests (+76 : verrou, concurrence, opt-ins) |
| `pytest` complet | **5 097 réussis**, 148,38 s | **5 173 réussis**, 157,39 s |
| Tests Node du Graphic Core | **134/134** (Node 24.18.0) | Fichiers identiques |
| Tests de mutation documentés | 34 fichiers de tests y font référence, plus les scripts de mutation des preuves 007 | — |
| Navigateurs | Kit `scripts/acceptance/` : Chromium et Firefox 29/29, sans JavaScript 10/10, deux passes (FD-ACCEPTANCE-002) | Mêmes résultats sur 008 (requalification) ; ACC-002 non rejoué en navigateur |
| Kit d'acceptance | Versionné, rejouable (`run.sh`, 10 projets fixtures) | `run.sh` modifié pour le chemin du verrou |
| Smoke de release | 72/72 sur les artefacts installés (FD-RELEASE-002) | Sans objet |

Le test instable connu `test_runtime_detects_dead_proxy` n'a pas échoué dans les
deux suites.

## Release 0.2.0

**`RELEASE_READY` reste cohérent avec le dépôt actuel.** Le commit de release est
présent, son `forge_design/` est inchangé, sa suite est rejouée et verte ici, et
les artefacts ont le même SHA-256.

| Distribution | État |
|---|---|
| Release locale qualifiée | **Oui** : `b38a2c2` / `7805152` |
| Wheel et sdist | Construits ; exemplaires uniquement en tmpfs, reproductibles en contenu |
| Tag | Aucun |
| Push | **Non** : `origin/main` = `e411d0c`, sans les 13 commits de la release |
| PyPI | Non publié ; licence non décidée |

C'est une **release locale qualifiée, non distribuée**.

## SéquenCiel readiness

| Point | Constat |
|---|---|
| Roadmap et rapports | `RELEASE_READY`, gate OPEN, premier essai prévu |
| Essai réalisé ? | **Non** : aucun FD-SEQUENCIEL-001, ni rapport ni commit |
| Projet réel | `/home/roger/Projets/SequenCiel` : forge-mvc 1.0.0rc9 et 12 opt-ins installés, `optins/registry.py` actif (`BACKEND = "mariadb"`, `ENABLED_OPTINS` non vide) |
| Détection 0.2.0 sur SéquenCiel | Seul appel effectué : `detect_forge_project`, fonction à base de `stat`, sans lecture ni import, avec les mtimes inchangés et `git status` de SéquenCiel non modifié. Résultat : **`valid False`, erreurs : `('bootstrap.py : absent.',)`** |
| Cause | SéquenCiel n'a jamais eu de `bootstrap.py` (son historique Git n'en contient pas ; son `app.py` date de Forge 1.0.0-rc.3). forge-mvc rc9 le traite comme optionnel. |
| Conséquence | Avec la 0.2.0, l'essai s'arrêterait dès l'ouverture du projet : « projet non reconnu » |
| Attendu après correction | Routes en « Attention », parce que le registre d'opt-ins est actif. C'est une limite acceptée, que FD-ACC-002 ne couvre pas. |

**Distinction demandée :**

- **prêt techniquement sur les fixtures** : oui, gate OPEN légitime pour ce qu'il a qualifié ;
- **prêt pour le vrai SéquenCiel** : non, à cause de la détection ;
- **premier essai réalisé** : non.

La situation attendue (« 0.2.0 qualifiée, gate OPEN, essai non lancé ») est exacte,
avec cette réserve nouvelle.

## Dette consolidée

| Classe | Dette | Bloquant ? |
|---|---|---|
| CRITIQUE | **Aucune** : aucune perte de données, fuite, exposition réseau ni processus non maîtrisé | — |
| MAJEURE | **D1. Détection trop stricte** : `bootstrap.py` exigé, alors qu'il est optionnel pour forge-mvc rc9 ; SéquenCiel est refusé | **Oui, pour l'essai SéquenCiel** |
| MAJEURE | **D2. Traçabilité locale** : 13 commits non poussés (toute la release) ; 593 fichiers hors commit, dont trois travaux qualifiés ; artefacts de release seulement en tmpfs volatile ; disque `/` à 100 % (≈ 0,8 Gio libres) et `/tmp` à 93 % | Non, mais risque de perte et de confusion de baseline |
| MINEURE | ACC-002 dans la baseline ; correctif qualifié non committé | Non |
| MINEURE | Fenêtre `write_design` dans la baseline ; inatteignable par l'interface ; corrigée par 008, non committé | Non |
| MINEURE | `write_specialized_resource` sans verrou (plausible, non reproduit) | Non |
| MINEURE | Licence non décidée | Bloque une publication, pas l'usage local |
| MINEURE | Pas de matrice Python (3.12 jamais testé) | Non |
| MINEURE | Avertissement setuptools `package-data` | Non |
| COSMÉTIQUE | Roadmap : pile HTMX et Alpine obsolète, numérotation FD-CIRCUIT-004 à 008 obsolète | Non |
| HORS CHEMIN CRITIQUE | MkDocs, CI, changelog, signatures ; sélection d'arête, formes de nœud ; identité stable des blocs (`NodePath`) ; pagination des routes ; streaming runtime ; génération non exposée | Non |

Les limites explicitement acceptées ne sont pas comptées comme défauts majeurs :
masquage non exhaustif, absence de bac à sable, effets de bord de la preview,
lecture statique des routes.

## Matrice de maturité

| Domaine | État | Niveau de confiance | Dette principale |
|---|---|---|---|
| Architecture | QUALIFIED | Élevé (grep, tests de frontières, deux modules) | Aucune |
| Project Inspector | QUALIFIED (fixtures) | Moyen (cible réelle refusée) | D1, détection `bootstrap.py` |
| Routes | QUALIFIED | Élevé | ACC-002 (corrigé hors commit) ; lecture statique |
| Entities | QUALIFIED | Élevé | Bornes de découverte |
| Templates | QUALIFIED | Élevé | Analyse syntaxique seulement |
| Debug | QUALIFIED | Élevé | Masquage non exhaustif (accepté) |
| Runtime commands | QUALIFIED | Élevé | Pas de bac à sable ; code 1 ambigu |
| Editor | QUALIFIED | Élevé | Concurrence interprocessus (008 hors commit) ; `NodePath` par indices |
| Real Preview | QUALIFIED | Élevé | Effets de bord applicatifs (contrat) |
| Graphic Core | QUALIFIED | Élevé (134 tests Node, cinq clients) | Pas de sélection d'arête ni de formes |
| Module Host | QUALIFIED | Élevé | Écriture spécialisée sans verrou (plausible) |
| Packaging | QUALIFIED (local) | Moyen | Licence, matrice Python, configuration setuptools |
| Documentation | STABLE | Moyen | Roadmap partiellement obsolète (deux points corrigés ici) |
| Release | QUALIFIED (local), non distribuée | Élevé pour la 0.2.0 | Non poussée, non taguée, artefacts volatils |
| SéquenCiel readiness | EXPERIMENTAL | Faible : aucune confrontation réelle réussie | D1 |

## Terminé / stabilisé

Uniquement les éléments démontrés, committés, rejoués ou revérifiés ici :

- Architecture générique : cinq Tools, Module Host versionné, frontières gardées par des tests, aucune dérive.
- Deux modules externes réels, propres et poussés, compatibles `>=0.2.0,<1`, qualifiés ensemble avec la 0.2.0.
- Outils Forge : Inspector (9 sections), Routes (chaîne complète), Entités, Templates, Debug ; qualifiés en deux navigateurs et sans JavaScript.
- Runtime : trois commandes à liste fermée, `-u`, 10 s, 256 Kio par flux, groupe tué, masquage.
- Éditeur : vue périmée refusée en 409, sans écriture (ACC-004).
- Preview réelle : loopback, `-I -B -u`, aucun bytecode (ACC-003), arrêt au changement de projet et à la sortie.
- Web local : `127.0.0.1`, Host strict, Origin et `Sec-Fetch-Site`, `no-store` (sonde HTTP réelle).
- Release locale 0.2.0 : reproductible, identique à Git, installable hors ligne ; suite rejouée verte (5 097 tests et 134 tests Node, Ruff, format, Pyright strict à 0).

## Ouvert / à traiter

| Priorité | Sujet | Raison | Bloquant ? | Ticket recommandé |
|---|---|---|---|---|
| 1 | Détection sans `bootstrap.py` | La 0.2.0 refuse SéquenCiel ; Forge rc9 le rend optionnel | **Oui, pour SéquenCiel** | **FD-FORGE-004** |
| 2 | Jalon Git contrôlé | 008, ACC-002, stabilisation et FD-FORGE-004 à committer selon une sélection approuvée, puis version 0.2.1 (CORRECTIVE) requalifiée en une seule campagne | Non, mais nécessaire pour que l'essai porte sur une baseline traçable | FD-RELEASE-003 (proposition existante, à étendre à FD-FORGE-004) |
| 3 | Premier essai réel | Seule preuve d'usage réel manquante | — | FD-SEQUENCIEL-001, sur la 0.2.1 |
| 4 | Push et publication | `origin/main` ne contient pas la release ; licence non décidée | Non | Décision du porteur |
| 5 | Verrou des ressources de modules | Même schéma que l'ancien `write_design` | Non | À reproduire d'abord (par exemple FD-SPECIALIZED-003) |

## Améliorations non bloquantes

- Matrice Python 3.12 / 3.13.
- Configuration des paquets de données setuptools.
- MkDocs et CI.
- Changelog.
- Formes de nœud (`presentation.shape`) et repli textuel pour Flowchart.
- Sélection d'arête, si un client réel la demande.
- Identité stable des blocs de design.
- Pagination de Route Explorer.
- Exposition de la génération et de SAFEWRITE dans l'interface.

## Risque principal

**Le décalage entre la qualification et le projet réel.** Le gate OPEN repose sur des
fixtures dérivées du squelette Forge actuel. La seule confrontation faite avec
SéquenCiel, purement statique, échoue dès la détection.

Tant qu'aucun essai réel n'a eu lieu, d'autres écarts de ce type restent possibles :
registre d'opt-ins actif, structure ancienne, volume (le dossier SéquenCiel pèse
62 Gio hors `.venv` et `node_modules`). Ces autres écarts sont des hypothèses, non vérifiées par cet audit.

## Positionnement produit

**Release locale.** Forge Design 0.2.0 est une release qualifiée de bout en bout sur
ce poste : acceptance en deux passes, artefacts reproductibles et identiques à Git,
installation hors ligne.

Ce n'est pas une **release distribuée** : ni tag, ni push de la release, ni
publication, ni licence, et les artefacts sont volatils. Ce n'est pas non plus un
outil dont l'usage réel est démontré : aucun essai sur une application réelle.

## Verdict global

**FORGEDESIGN_NEEDS_CONSOLIDATION**

- **Pourquoi pas ON_TRACK.** L'architecture et la release sont saines, mais la
  prochaine étape annoncée (l'essai SéquenCiel) échouerait en l'état. Trois travaux
  qualifiés et la release elle-même restent hors de toute référence partagée.
- **Pourquoi pas BLOCKED.** Rien n'empêche la progression : le défaut de détection
  est localisé (une règle, l. 87 de `project_detection.py`), sa référence normative
  existe (forge-mvc `load_bootstrap`, ADR-093), et les travaux en attente sont déjà
  qualifiés.

## Prochaine étape recommandée

**FD-FORGE-004 — Reconnaître un projet Forge sans `bootstrap.py`.**

Contenu attendu :

- aligner la détection sur forge-mvc 1.0.0rc9, où `bootstrap.py` est optionnel ;
- ce faisant, l'afficher comme élément optionnel de la structure ;
- garder `app.py`, `config.py`, `mvc/` et `mvc/routes/` obligatoires ;
- prévoir les tests et la documentation de Project Inspector ;
- ne rien modifier dans SéquenCiel.

**Pourquoi cette étape, et non FD-SEQUENCIEL-001 directement.** La règle du §60
supposait que la release suffisait. Vérification faite, la 0.2.0 ne peut pas ouvrir
SéquenCiel.

**Pourquoi pas FD-EDITOR-008 d'abord (§61).** 008 ne change aucune garantie qualifiée
de la 0.2.0 : il renforce une limite déclarée inatteignable par l'interface. Il ne
conditionne donc pas l'essai.

La version corrective est de toute façon nécessaire pour FD-FORGE-004. La suite
logique est donc de regrouper FD-FORGE-004, 008 et ACC-002 dans un seul jalon 0.2.1
(FD-RELEASE-003), avec une seule requalification, puis de lancer FD-SEQUENCIEL-001
sur cette version.

## Fichiers créés

- `docs/rapports/FD-AUDIT-002.md`

## Fichiers modifiés

- `docs/03-roadmap.md`, deux incohérences factuelles démontrées :
  - piste D et phase Modules : Flowchart n'est plus « recommandé », il est réalisé (FD-MODULE-PILOT-001) ;
  - piste B : l'essai SéquenCiel est précédé du correctif de détection, avec un renvoi vers ce rapport.

Non modifiés : `forge_design/`, `tests/`, `scripts/`, `pyproject.toml`, README,
rapports historiques, `docs/rapports/FD-CONTRACT-001.md`, tout le travail concurrent,
Circuit, Flowchart, SéquenCiel.

Temporaires, sous `tmp/` (ignoré par Git) :

- `tmp/fda2b/` et `tmp/fda2c/` (`--basetemp`) ont été supprimés ;
- le worktree `tmp/fd-audit-002/` (détaché sur `7805152`) et les dossiers
  `--basetemp` `tmp/fda2d/` et `tmp/fda2e/` **restent sur disque**. Leur suppression
  a été bloquée par un contrôle de sécurité de l'outil ; elle est laissée au porteur :
  `git worktree remove --force tmp/fd-audit-002/wt`, puis suppression de
  `tmp/fd-audit-002/`, `tmp/fda2d/` et `tmp/fda2e/`.

Des sondes en lecture seule restent aussi dans le scratchpad de la session.

## Validation finale

Sur la baseline `7805152`, dans le worktree propre :

| Commande | Résultat |
|---|---|
| `python -m compileall -q forge_design tests` | OK |
| `ruff check forge_design tests scripts` | All checks passed |
| `ruff format --check .` | 447 fichiers déjà formatés |
| `pyright` (strict) | 0 erreur, 0 avertissement |
| `git diff --check` | OK |
| `pytest` | **5 097 réussis**, 148,38 s |
| `node --test tests/js/graphics/*.test.mjs` | **134/134** |

À titre d'information, sur l'arbre courant non committé : `pytest` donne **5 173
réussis** en 157,39 s.

Après rédaction, dans le même worktree, sur la baseline plus ce rapport et la
roadmap modifiée, c'est-à-dire le contenu exact du commit. La suite est relancée
parce que des tests lisent `docs/`.

| Commande | Résultat |
|---|---|
| `ruff check forge_design tests scripts` | All checks passed |
| `ruff format --check .` | 448 fichiers déjà formatés (ce rapport compris) |
| `git diff --check` | OK |
| `pytest` | **5 097 réussis**, 146,61 s |

## État Git final

Un seul commit au-dessus de `7805152` :
`docs: auditer l'état global de Forge Design (FD-AUDIT-002)`.

Il ne contient que `docs/rapports/FD-AUDIT-002.md` et `docs/03-roadmap.md`. Il n'a
pas été poussé : `origin/main` reste `e411d0c`, et HEAD a désormais 14 commits
d'avance.

Les 11 fichiers modifiés et les 582 fichiers non suivis du travail concurrent restent
hors commit, inchangés. La version reste 0.2.0.

```text
Verdict global: FORGEDESIGN_NEEDS_CONSOLIDATION
Positionnement produit: release locale (0.2.0 qualifiée, non distribuée)
Risque principal: décalage entre la qualification sur fixtures et le projet réel — la 0.2.0 refuse SéquenCiel (bootstrap.py absent)
Prochaine étape recommandée: FD-FORGE-004 — reconnaître un projet Forge sans bootstrap.py
```
