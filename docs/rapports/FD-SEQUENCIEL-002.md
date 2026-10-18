# Rapport — FD-SEQUENCIEL-002

Première frontière d'exécution de Forge Design 0.2.1 sur SéquenCiel :
**`forge project:audit` seul**, lancé depuis Debug Center. Date : 2026-10-18.

## Objectif

Une question : le runner de Debug Center peut-il lancer l'audit officiel de
forge-mvc sur le vrai SéquenCiel, avec l'interpréteur du projet, sans écrire dans le
projet, sans fuite de secret, sans processus restant et avec une sortie fidèle ?

Aucune correction fonctionnelle. Les éléments suivants n'ont pas été lancés :

- `doctor` et `project:check` (formulaires affichés, jamais soumis) ;
- Real Preview, l'éditeur, les actions de modules ;
- la génération, SAFEWRITE, les migrations ;
- l'application SéquenCiel et sa base.

Aucun module externe n'est activé. Aucun fichier n'est créé dans SéquenCiel.

| Décision | Résultat |
|---|---|
| A. 0.2.1 installé depuis la wheel ? | Oui, SHA-256 vérifié, venv neuf hors ligne |
| B. Vrai checkout SéquenCiel ? | Oui : `/home/roger/Projets/SequenCiel` |
| C. Une seule commande Forge ? | Oui : `project:audit`, 2 POST `/debug/forge-audit` ; 0 POST doctor ou check |
| D. Deux instantanés de stabilité ? | Oui : T0 = T1 |
| E. Instantané après chaque étape ? | Oui : après ouverture, après chaque audit, final |
| F. HOME et XDG isolés ? | Oui, pour le serveur comme pour l'enfant |
| G. Chromium uniquement ? | Oui, clic réel sur le bouton |
| H. Processus enfant observé ? | Oui : argv, session, environnement, durée de vie |
| I. Sortie vérifiée indépendamment ? | Oui : recomptage sans forge-mvc, 23/23 lignes justes |
| J. Secrets recherchés uniquement en mémoire ? | Oui : 0 correspondance |
| K. SéquenCiel modifié ? | **Non** : instantané final = T1 |
| L. Verdict | **SEQUENCIEL_AUDIT_PASS** |

## Ce que fait la commande

Lu dans le forge-mvc 1.0.0rc9 installé dans `.venv` de SéquenCiel (lecture seule),
avant toute exécution :

- `forge.py` importe le CLI (`cli.*`, `core.*`) depuis `site-packages` ; avec `-P`,
  le cwd n'est pas dans `sys.path`, et aucun `forge.py` du projet ne peut masquer le
  CLI officiel ;
- `cli/project/project_audit.py` : neuf familles (structure, configuration,
  entités, routes, templates, modules, migrations, documentation, tests) faites
  uniquement de `exists`, `iterdir`, `rglob`, `read_text`, `json.loads`,
  `ast.parse` et `dotenv_values` ;
- aucune écriture, aucun import du code du projet, aucune connexion ;
- `env/example` et `env/dev` sont lus, mais seuls des **noms** de clés vides
  peuvent être affichés, jamais une valeur.

C'est conforme à l'avertissement que Debug Center affiche avant le clic.

## Baseline

| Élément | Valeur |
|---|---|
| Forge Design | `bb16f90` (FD-SEQUENCIEL-001), `main` ; seul changement : `FD-CONTRACT-001.md` (modification utilisateur, préservée) et les fichiers non suivis historiques |
| Roue | `tmp/fd-release-003-dist/forge_design-0.2.1-py3-none-any.whl`, SHA-256 `8f4167c92567964ac5663cc0720bd338675ecf0ba7d8eb850608da78ce91a9da` (identique à FD-RELEASE-003) |
| Venv | Neuf, dans le scratchpad ; dépendances téléchargées puis installation `--no-index` ; `pip check` OK ; forge-design 0.2.1 et forge-mvc 1.0.0rc9, ni Circuit ni Flowchart, aucun `.pth` |
| SéquenCiel HEAD | `89fb8a1329b05fb1ca0f8635aa2b1c3bb31e673f` (« fix(arduino): enforce disabled R4 WiFi on compilation worker ») |
| Statut SéquenCiel | 20 fichiers non suivis, préexistants (3 rapports `SC-*` à la racine, ADR 327, DC-017-09A et ses 13 fichiers, 2 livrables) ; aucun fichier modifié |
| `.venv` SéquenCiel | `/usr/bin/python3.13`, forge-mvc 1.0.0rc9 et ses opt-ins rc9 |

SéquenCiel a avancé depuis FD-SEQUENCIEL-001 (HEAD `008a895e` → `89fb8a13`).
`tmp/` est passé de 57 à 42 Go, d'où **519 214 entrées** au lieu de 567 471. Le
commit SéquenCiel `fa237219` (« encadrer et surveiller les fichiers temporaires »)
en est l'explication plausible.

Tous les contrôles Git ont utilisé `git --no-optional-locks` : aucune écriture
dans `.git`, cette fois, même avant T0.

## Stabilisation

| Contrôle | Constat initial | Action |
|---|---|---|
| Fenêtre VS Code SéquenCiel | Ouverte : hôte d'extensions, `ruff server`, 3 terminaux ; mtime de la racine à 20:22:23 (activité en cours) | Question posée ; **tu as fermé la fenêtre**. Vérifié ensuite : 0 processus avec SéquenCiel pour cwd, 0 descripteur ouvert dessous |
| Session `ssh roger@192.168.1.234` sortante | Ouverte depuis 11:56, dans un terminal de cette fenêtre | Disparue avec la fenêtre ; aucun processus touché par moi |
| Ports 8090, 8092, 33389, 8765, 9341 | Libres (base de développement SéquenCiel arrêtée) | — |
| `mariadbd` système (3306) | Présent, hors cible | Laissé tel quel ; aucune connexion |

## Snapshots

Outil réécrit pour ce ticket, même méthode que FD-SEQUENCIEL-001, sans suivre
aucun lien :

- **niveau complet** (chemin, type, taille, `mtime_ns`, `ctime_ns`, inode, mode,
  SHA-256 ou cible) pour tout sauf `.git`, `.venv`, `node_modules`, `tmp` et
  `sauvegardes` ;
- **niveau métadonnées** (sans SHA-256) pour ces quatre dossiers. `.venv` y est :
  un `__pycache__` écrit par l'interpréteur du projet serait visible ;
- **`.git`** : `rev-parse HEAD` et l'empreinte de `status --porcelain=v1
  --untracked-files=all`.

| Instantané | Heure | Entrées | Comparaison |
|---|---|---:|---|
| T0 | 20:24:30 | 519 214 (7 828 complet / 511 385 métadonnées) | — |
| T1 | 20:29:48 (5 min 18 s après) | 519 214 | **= T0** : gate de stabilité franchi |
| Après ouverture | 20:30:53 | 519 214 | = T1 |
| Après audit n° 1 | 20:31:36 | 519 214 | = T1 |
| Après audit n° 2 | 20:32:08 | 519 214 | = T1 |
| Final (serveur arrêté) | 20:33:03 | 519 214 | **= T1** |

« = T1 » signifie 0 ajout, 0 suppression et 0 champ changé, ctime et inodes
compris, même HEAD et même empreinte de statut (`cdfb4f1f…`).

## Serveur et ouverture

Serveur lancé avec `env -i`, depuis `/tmp`, `--no-browser`, sans `--module`. Il a
7 variables : `HOME` et les quatre `XDG_*` du scratchpad, `PATH=/usr/bin:/bin` et
`LANG=C.UTF-8`.

| Contrôle | Résultat |
|---|---|
| Bannière | `Forge Design 0.2.1`, `http://127.0.0.1:8765/` |
| Écoute | `127.0.0.1:8765` seulement |
| Host `localhost` / étranger | 400 / 400 |
| En-têtes | `Cache-Control: no-store`, CSP `default-src 'self'` |
| Aucun projet implicite | Oui |
| Ouverture de SéquenCiel (formulaire, Chromium) | 811 ms ; synthèse identique à FD-SEQUENCIEL-001 (Forge, Routes et Diagnostics en Attention ; 629 routes, 86 entités, 497 templates, 251 migrations) |
| Debug Center avant le clic | 3 sections « non exécuté », 3 boutons, actions `/debug/forge-diagnostic`, `/debug/forge-audit`, `/debug/forge-project-check` ; avertissement de l'audit affiché (« il n'exécute ni `config.py`, ni l'application, ni les tests, et ne contacte aucune base de données ») |

## Exécutions

Deux exécutions par un **clic souris réel** (CDP `Input.dispatchMouseEvent`) sur
« Exécuter l'audit Forge », chacune dans une phase Chromium distincte avec un
profil neuf.

| Mesure | Audit n° 1 | Audit n° 2 |
|---|---|---|
| POST | 1 (`/debug/forge-audit`) | 1 (`/debug/forge-audit`) |
| Clic → page chargée | 279 ms | 224 ms |
| État | `succeeded` : « Terminé avec le code 0 : aucun constat FAIL (des avertissements restent possibles) » | idem |
| Code retour | 0 | 0 |
| Durée affichée | 0,14 s | 0,12 s |
| Interpréteur | `.venv/bin/python` du projet | idem |
| stdout | 1 136 caractères (1 179 octets), 23 lignes de constat, non tronqué | **identique octet pour octet** |
| stderr | vide | vide |
| Autres sections | doctor et check « non exécuté » | idem |
| Nouveau GET `/debug` | 3 sections « non exécuté » : résultat **non persisté** | idem |
| Alerte, CSP, exception JS | 0 | 0 |

Sortie affichée :

```text
Forge project:audit — 1.0.0rc9

Structure :
  [OK]    app.py présent
  [OK]    config.py présent
  [OK]    mvc/ présent
  [OK]    mvc/routes/__init__.py présent
  [OK]    mvc/controllers/ présent
  [OK]    mvc/views/ présent
  [OK]    mvc/entities/ présent
  [OK]    static/ présent

Configuration :
  [OK]    env/example présent
  [OK]    env/dev présent
  [OK]    clés essentielles configurées

Entités :
  [OK]    relations.json valide
  [OK]    86 entité(s) déclarée(s)
  [WARN]  1 entité(s) sans fichier SQL : page_document — forge build:model
  [WARN]  1 entité(s) sans _base.py : page_document — forge build:model

Routes :
  [OK]    mvc/routes/__init__.py syntaxe valide
  [OK]    variable «router» déclarée

Templates :
  [OK]    496 template(s) .html trouvé(s)

Modules :
  [INFO]  forge_modules.json absent — modules non activés

Migrations :
  [OK]    251 fichier(s) SQL trouvé(s)
  [OK]    toutes les migrations conformes

Documentation :
  [OK]    README.md présent

Tests :
  [INFO]  270 fichier(s) test_*.py détecté(s) (non exécutés ici)

Résumé :
  OK     19
  WARN   2
  INFO   2

Audit terminé — 2 avertissement(s).
```

## Processus enfant

Un surveillant (`/proc`, relevé toutes les 2 ms, 40 000 relevés) a noté chaque
processus dont le cwd était sous SéquenCiel, de l'ouverture à la fin de la
navigation.

| Constat | Audit n° 1 | Audit n° 2 |
|---|---|---|
| PID / parent | 1516196 / serveur (1515806) | 1516396 / serveur |
| Session et groupe | pgid = sid = pid : **nouvelle session**, groupe tuable en entier | idem |
| argv | `/home/roger/Projets/SequenCiel/.venv/bin/python -s -B -P -u -m forge project:audit` | idem |
| Exécutable | `/usr/bin/python3.13` (cible du lien du venv) | idem |
| Environnement | **3 variables** : `PATH=/usr/bin:/bin`, `LANG=C.UTF-8`, `HOME` isolé | idem |
| Durée de vie observée | 131 ms | 109 ms |
| Descendants | Aucun | Aucun |
| Restant après la réponse | Aucun membre du groupe | Aucun |

Aucun autre processus de Forge Design n'a eu SéquenCiel pour cwd : la navigation
(Inspector, Debug, Routes, Entités, Templates) n'en lance aucun. Les trois
`git --no-optional-locks status` relevés sont ceux de l'outil d'instantané. Un PID
vu 0 ms, disparu avant lecture, coïncide avec l'un d'eux et lui est attribué
(plausible, non démontré).

## Fidélité de la sortie

Un recomptage indépendant, écrit sans forge-mvc et lancé avant l'audit, prévoyait
chaque fait :

| Famille | Recomptage | Sortie affichée | Verdict |
|---|---|---|---|
| Structure | 8 éléments présents, dossiers non vides | 8 × OK | Juste |
| Configuration | `env/example` et `env/dev` présents ; 0 clé requise vide (noms seuls) | 3 × OK | Juste |
| Entités | 86 dossiers, `relations.json` valide ; `page_document` sans `.sql` ni `_base.py` (le dossier ne contient que `page_document.json`) | 2 OK + 2 WARN | Juste |
| Routes | syntaxe valide, nom `router` présent | 2 × OK | Juste |
| Templates | 496 `.html` (`rglob`) ; `base.html` et `layout.html` présents, donc pas d'INFO | 1 OK | Juste |
| Modules | `forge_modules.json` et `modules/` absents | 1 INFO | Juste (voir Limites Forge) |
| Migrations | 251, 0 nom non conforme, 0 vide, 0 timestamp dupliqué | 2 × OK | Juste |
| Documentation | `README.md`, 3 708 caractères | 1 OK | Juste |
| Tests | 270 `tests/test_*.py` (niveau 1) | 1 INFO | Juste |

**23/23 lignes justes**, code 0 attendu et obtenu. Aucun marqueur « [masqué] »
dans la sortie : le masquage de Debug Center n'a rien altéré. Le nettoyage ANSI n'a
rien retiré, puisque la sortie n'en contient pas.

Écarts apparents avec les outils statiques, tous attendus :

- 496 `.html` pour l'audit contre **497** pour Template Viewer, qui compte aussi
  `components/pdf/texte_enrichi.css.jinja` ;
- Entity Explorer : 0 avertissement pour `page_document`, parce qu'il lit les
  définitions JSON sans vérifier les fichiers générés par `forge build:model`.
  L'audit complète utilement cette vue.

## Vérification des secrets

Méthode identique à FD-SEQUENCIEL-001 : un seul processus extrait les candidats
**en mémoire** et compare sur place, sans afficher une seule valeur.

| Mesure | Résultat |
|---|---|
| Sources | `env/actualisation`, `env/dev`, `env/example`, `env/prod` (clés sensibles et mots de passe d'URL), `config.py` (constantes et défauts `getenv` à clé sensible), `cert.pem` et `key.pem` (lignes de contenu) |
| Candidats | 58, soit **49 valeurs distinctes** ; 1 valeur de moins de 6 caractères ignorée |
| Surfaces | HTML complet des deux pages de résultat, sections extraites (stdout, stderr), page Debug avant le clic, Inspector, journal du serveur (114 lignes) |
| **Correspondances** | **0** |

Les HTML capturés sont restés dans le scratchpad, en mode 600, et n'ont été
affichés qu'après le contrôle.

## Réseau, console, mémoire

- **Réseau** : toutes les requêtes vont vers `127.0.0.1:8765`, sans aucune
  ressource externe. Le journal du serveur compte 3 POST au total : `/inspector`
  (ouverture) et 2 × `/debug/forge-audit`.
- **Console** : 0 violation CSP et 0 exception. Les seules erreurs réseau sont les
  4 `GET /favicon.ico` en 404, déjà connus (cosmétique).
- **Mémoire** : RSS du serveur à 46,1 Mio au démarrage, 87,0 Mio après ouverture,
  puis 87,1 Mio après les deux audits. Le runner ne retient rien.
- **Pages** (dernière phase) : `/inspector` 829 ms, `/debug` 84 ms, `/entities`
  219 ms, `/templates` 135 ms. `/routes` met **2 247 ms**, contre 1 152 ms le
  16/10, sans lien avec l'audit. Je le note pour FD-ROUTES-023 sans l'avoir
  analysé.

## HOME isolé et état de Forge Design

- HOME isolé à la fin : un seul fichier,
  `.config/forge-design/recent-projects.json` (77 octets).
- Le vrai `~/.config/forge-design/` est **inchangé** (dernière modification le
  4 octobre).
- Aucun `storage/` créé dans le cwd du serveur (`/tmp`) : aucun handler n'a levé.

## Processus finaux

- `SIGTERM` au serveur : arrêt propre, **code de sortie 0**.
- Plus aucun processus Forge Design ni Chromium, et les ports 8765 et 9341 sont
  libres.
- Restent les processus préexistants autorisés : session VS Code Remote-SSH
  entrante, fenêtre ForgeDesign et sa session Claude Code, `mariadbd` système.

## Observations SéquenCiel

- **`page_document`** : entité déclarée (`page_document.json`, 10 septembre) sans
  `page_document.sql` ni `page_document_base.py`. `forge build:model` n'a pas été
  lancé pour elle, ou elle est volontairement incomplète. SEQUENCIEL-ISSUE mineure,
  à examiner côté application.
- Aucune autre anomalie : configuration complète, migrations conformes.

## Limites Forge

- **Famille « Modules » de l'audit rc9** : elle ne lit que l'ancien registre
  `forge_modules.json`. SéquenCiel active ses opt-ins par `optins/registry.py`
  (`register_optins(router)`, l. 225 de `mvc/routes/__init__.py`), ce que l'audit
  ne voit pas. D'où « modules non activés », trompeur pour ce projet.
  FORGE-LIMITATION, en amont, dans forge-mvc. Forge Design l'affiche tel quel, sans
  l'interpréter, ce qui est conforme à son contrat (« le texte n'est jamais
  interprété »).
- L'audit ne compte que les `.html` et seulement `tests/test_*.py` au premier
  niveau : ce sont des choix de forge-mvc (EXPECTED).

## Observations Forge Design

| # | Observation | Gravité | Classement |
|---|---|---|---|
| 1 | Runner conforme : argv de la liste fermée, nouvelle session, environnement en liste blanche, durée bornée, groupe arrêté, résultat non persisté | — | EXPECTED |
| 2 | Sortie rendue fidèlement : 23/23 lignes, aucune altération par le masquage | — | EXPECTED |
| 3 | `favicon.ico` en 404 (déjà relevé par FD-SEQUENCIEL-001) | Cosmétique | FORGEDESIGN-ISSUE |
| 4 | `/routes` à 2,2 s dans la dernière phase (1,15 s le 16/10), non analysé | À surveiller | UNKNOWN |

Aucune observation nouvelle sur la frontière d'exécution elle-même. Les constats
de lecture seule de FD-SEQUENCIEL-001 (borne de 128 templates, templates rendus par
helper, version indéterminée, déclarations non-route, opt-ins et routes en boucle)
sont inchangés et n'ont pas été requalifiés ici.

## Classification

| Catégorie | Constats |
|---|---|
| SEQUENCIEL-ISSUE | `page_document` sans fichiers générés |
| FORGEDESIGN-ISSUE | `favicon.ico` 404 (cosmétique, préexistant) |
| FORGE-LIMITATION | Famille « Modules » de l'audit rc9 aveugle au registre d'opt-ins |
| EXPECTED | Code 0 avec 2 WARN ; 496 contre 497 templates ; Entity Explorer sans contrôle des fichiers générés ; résultat non persisté ; doctor et check non lancés |
| UNKNOWN | `/routes` plus lent qu'au 16/10 ; un PID éphémère attribué à l'outil d'instantané |
| BLOCKING | **Aucun** |

## Verdict

**SEQUENCIEL_AUDIT_PASS**

- `project:audit` lancé deux fois sur le vrai SéquenCiel, par un clic réel, avec
  l'interpréteur du projet ;
- **aucune écriture** : 6 instantanés identiques à T1, `.venv` compris (aucun
  bytecode) ;
- **aucune fuite** : 0 valeur sensible sur 49 ;
- **frontière de processus démontrée** : argv exact, nouvelle session,
  3 variables d'environnement, aucun processus restant ;
- **sortie fidèle et déterministe** : 23/23 lignes vérifiées, deux exécutions
  identiques ;
- aucune autre commande lancée.

La seule limite constatée, celle de la famille « Modules », vient de forge-mvc. Elle
n'affecte pas Forge Design.

## Recommandation ticket suivant

**FD-SEQUENCIEL-003 : `doctor` seul**, deuxième niveau de confiance. Il exécute
`config.py` et peut se connecter à la base configurée. Points à trancher avant le
ticket :

- **état de la base de développement** (127.0.0.1:33389, arrêtée aujourd'hui) :
  la laisser arrêtée qualifie le chemin « connexion refusée » et le masquage des
  messages d'exception des pilotes ; la démarrer est une décision du porteur ;
- **effets de `config.py`** : à lire en entier avant le clic, car le runner n'est
  pas un bac à sable ;
- même méthode : T0/T1, instantané après l'exécution, surveillant `/proc`,
  secrets en mémoire, et ici aussi une attention particulière au masquage
  (`DB_PASSWORD`, URL de connexion).

Hors chemin critique, FD-ROUTES-023 reste recommandé ; la mesure de `/routes`
ci-dessus y sera utile.

## Fichiers créés

- `docs/rapports/FD-SEQUENCIEL-002.md`

Aucun fichier n'est créé dans SéquenCiel. Les outils (instantané, surveillant,
scénario Chromium, recomptage, contrôle des secrets) et les sorties capturées
restent dans le scratchpad de la session. Les instantanés compressés sont dans
`tmp/fd-sequenciel-002/` (ignoré par Git) et ne contiennent que des métadonnées et
des empreintes.

## Fichiers modifiés

- `docs/03-roadmap.md` : FD-SEQUENCIEL-002 et son verdict, et la suite
  (FD-SEQUENCIEL-003).

Non modifiés : `forge_design/`, les tests, le kit, les rapports historiques,
`docs/rapports/FD-CONTRACT-001.md`, SéquenCiel, Circuit, Flowchart.

## Validation finale

Le ticket ne change que ce rapport et la roadmap : la suite complète n'est pas
relancée. Validation documentaire faite après la dernière modification :

| Commande | Résultat |
|---|---|
| `git diff --check` (roadmap) et recherche d'espaces finaux (rapport) | OK |
| `ruff format --check` (rapport + roadmap) | 2 fichiers déjà formatés |
| Tests qui lisent `docs/` (`test_design_schema.py`, `test_view_contract_schema.py`) | 45 réussis |

## États Git finaux

**Forge Design** : un commit sur `main`,
`test: qualifier project:audit sur SéquenCiel (FD-SEQUENCIEL-002)`. Il contient ce
rapport et la roadmap. Il n'est pas poussé : 1 commit d'avance sur `origin/main` (`bb16f90`, déjà poussé).
`FD-CONTRACT-001.md` et les fichiers non suivis historiques sont inchangés.

**SéquenCiel** : HEAD `89fb8a1329b05fb1ca0f8635aa2b1c3bb31e673f`, statut
identique (20 fichiers non suivis, préexistants), **aucun commit et aucune
modification**.
