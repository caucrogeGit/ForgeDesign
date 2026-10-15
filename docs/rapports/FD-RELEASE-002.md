# Rapport — FD-RELEASE-002

Clôture de la release locale Forge Design 0.2.0 avant le premier essai sur SéquenCiel. Date : 2026-10-15.

## Objectif

Une question : la version 0.2.0 est-elle une release installable, reproductible, correctement empaquetée et prête pour le premier essai réel sur SéquenCiel ?

Aucune fonctionnalité n'est ajoutée et aucun fichier de `forge_design/` n'est modifié. Il n'y a ni tag, ni push, ni publication.

| Décision | Résultat |
|---|---|
| A. Nouvelle fonctionnalité ? | Non |
| B. La version change ? | Non : 0.2.0 |
| C. Wheel + sdist ? | Oui, construits deux fois |
| D. Installation réelle de la wheel ? | Oui, venv neuf, hors ligne |
| E. Installation réelle du sdist ? | Oui, venv neuf, hors ligne |
| F. Contrôle d'identité avec Git ? | Oui : wheel et sdist |
| G. Circuit + Flowchart ? | Oui, 0.1.0, même environnement que la wheel |
| H. Acceptance complète rejouée ? | Non : elle repose sur FD-ACCEPTANCE-002 |
| I. Smoke tests critiques ? | Oui : 72/72 sur les artefacts installés |
| J. Publication PyPI ? | Non |
| K. Tag Git ? | Non |
| L. Décision ? | **RELEASE_READY** |
| M. Gate SéquenCiel décidé ici ? | Non : déjà OPEN |
| N. Premier essai SéquenCiel ici ? | Non |

## État Git initial

| Élément | Valeur |
|---|---|
| HEAD | `b38a2c2` (FD-DOCS-001) |
| `origin/main` | `e411d0c` ; 0 commit en retard, 12 en avance |
| Collision | Aucune : FD-RELEASE-002 n'apparaissait que comme recommandation (et dans un diff de preuves de la requalification concurrente) |
| `docs/rapports/FD-CONTRACT-001.md` | Modifié par l'utilisateur ; préservé, hors commit |
| Dépôts des modules | ForgeDesign-Circuit `967b5b3`, ForgeDesign-Flowchart `a8ec22d` : 0 changement avant comme après |

Travail concurrent présent dans le dépôt principal, sans être committé, et exclu de la release :

- **FD-EDITOR-008** : `forge_design/design/io.py`, `forge_design/web/editor.py`, `forge_design/design/locking.py`, tests, `scripts/acceptance/run.sh`, `docs/design/design-json.md`, `docs/editor/structural-editor.md` ;
- **rapports et preuves** de FD-EDITOR-007, FD-EDITOR-008 et d'une requalification FD-ACCEPTANCE-001.

## Baseline release

Le commit de release est **`b38a2c2`**. Il contient :

- FD-ACCEPTANCE-002 (`837bf1b`) : ACCEPTED_WITH_MINOR_ISSUES, SéquenCiel gate: OPEN ;
- FD-DOCS-001 (`b38a2c2`) : ACC-001 corrigé.

Entre la baseline qualifiée par FD-ACCEPTANCE-002 (`8ca9b72`) et `b38a2c2`, `forge_design/` et `pyproject.toml` sont **identiques**. Seul `README.md` a changé, avec FD-DOCS-001 : c'est la description longue de la distribution. Le code publié est donc exactement celui qui a passé les deux passes d'acceptance.

## Isolation du worktree

Toute la qualification part d'un worktree détaché : `git worktree add --detach <scratch>/release/wt b38a2c2`.

| Moment | `git status --short --untracked-files=all` |
|---|---|
| Avant la qualification | 0 ligne |
| Après les builds et la suite complète | 0 ligne |

Les seuls fichiers produits dans le worktree sont ignorés par Git : `forge_design.egg-info`, retiré, et les caches de la suite. Les artefacts, les venvs et les projets de smoke sont tous **hors dépôt**, sous `<scratch>/release/`.

La suite complète utilise l'interpréteur du `.venv` principal avec `PYTHONPATH=<worktree>` ; `forge_design.__file__` pointe bien dans le worktree (vérifié). Les installations et les smoke tests n'utilisent ni `PYTHONPATH`, ni checkout, ni installation éditable.

## Version

Une seule source de version : `pyproject.toml` la lit dynamiquement dans `forge_design.__version__`.

| Source | Valeur |
|---|---|
| `forge_design.__version__` (commit de release) | `0.2.0` |
| `pyproject.toml` | `dynamic = ["version"]`, `version = {attr = "forge_design.__version__"}` |
| `METADATA` de la wheel | `Version: 0.2.0` |
| `PKG-INFO` du sdist | `Version: 0.2.0` |
| `forge-design --version` (venv wheel et venv sdist) | `Forge Design 0.2.0` |
| `forge_design.__version__` installé (wheel et sdist) | `0.2.0` |

## Build wheel

Venv de build dédié, créé depuis `/usr/bin/python3` : **Python 3.13.5, setuptools 84.0.0, build 1.6.1**.

Commande : `python -m build --no-isolation --outdir <dossier neuf> <worktree>`. Elle produit d'abord le sdist, puis **construit la wheel à partir du sdist**. La wheel complète prouve donc que le sdist est complet.

Résultat : `forge_design-0.2.0-py3-none-any.whl`, 166 fichiers, dont 161 sous `forge_design/` et 5 sous `forge_design-0.2.0.dist-info/` (`METADATA`, `RECORD`, `WHEEL`, `entry_points.txt`, `top_level.txt`).

**Avertissement de setuptools, classé non bloquant.** setuptools 84 signale que `forge_design.web.static`, `forge_design.web.static.graphics` et `forge_design.web.templates` sont importables mais absents de `packages`. Ces dossiers ne sont pas des paquets Python : ce sont les données de `forge_design.web`, déclarées dans `package-data`, et **toutes sont présentes** dans la wheel et le sdist (voir Ressources). C'est une dette de configuration, sans effet sur la 0.2.0 : un passage à la découverte par espaces de noms, ou une déclaration explicite, relèverait d'un ticket de packaging.

## Build sdist

`forge_design-0.2.0.tar.gz` : 311 fichiers.

- **Membres de l'arbre Git** (303) : `forge_design/` (161 fichiers), `tests/`, `pyproject.toml`, `README.md`. Setuptools inclut `tests/` par défaut, ce qui est normal pour un sdist.
- **Métadonnées générées** (8) : `PKG-INFO`, `setup.cfg`, `forge_design.egg-info/*`.
- **Hors sdist** : `docs/`, `scripts/` et les fixtures d'acceptance.

## Reproductibilité

Deux builds complets dans deux dossiers neufs (`build1`, `build2`), avec la même chaîne d'outils. Le contenu logique est comparé, pas les octets des archives :

| Contrôle | Résultat |
|---|---|
| Wheel : liste des fichiers | Identique (166 / 166) |
| Wheel : contenu de chaque fichier (`METADATA`, `RECORD`, `entry_points.txt` et données compris) | **Identique**, 0 différence |
| sdist : liste des membres | Identique (311 / 311) |
| sdist : contenu de chaque membre (`PKG-INFO` compris) | **Identique**, 0 différence |
| Empreintes des archives | Différentes, à cause des horodatages ZIP et tar : attendu |

Les artefacts de release sont ceux de `build1`, copiés dans `<scratch>/release/dist-release/`.

## Identité wheel / arbre Git

Chaque fichier `forge_design/*` de la wheel est comparé octet pour octet (SHA-256) à `git ls-tree -r b38a2c2 forge_design` :

| Contrôle | Résultat |
|---|---|
| Fichiers suivis / fichiers empaquetés | **161 / 161** |
| Dans la wheel mais pas dans Git | aucun |
| Dans Git mais pas dans la wheel | aucun |
| Contenu différent | aucun |
| Hors paquet | `dist-info` seulement |

Même contrôle pour le sdist : les 303 membres présents dans l'arbre Git, `forge_design/` compris, sont **identiques à Git**, et aucun fichier de `forge_design/` ne manque.

| Fichier clé | Wheel | sdist |
|---|---|---|
| `forge_design/revision_tokens.py` | présent | présent |
| `forge_design/real_preview/child_bootstrap.py` | présent | présent |
| `forge_design/py.typed` | présent | présent |
| `forge_design/design/locking.py` (travail concurrent) | **absent** | **absent** |

Aucun fichier non suivi, généré par les tests ou issu d'un autre ticket n'entre dans la release.

## Ressources

Ressources attendues, calculées depuis le dépôt par la sonde du kit (`expected_resources`) : **32** (16 gabarits, 14 statiques, 2 schémas). Avec `py.typed` et `child_bootstrap.py`, cela fait les 34 ressources contrôlées par l'acceptance.

| | Wheel | sdist | Installé (wheel) | Installé (sdist) |
|---|---|---|---|---|
| Gabarits `web/templates/*.html` | 16 | 16 | 16 | 16 |
| Statiques `web/static/**` | 14 | 14 | 14 | 14 |
| Schémas (`design.schema.json`, `view_contract.schema.json`) | 2 | 2 | 2 | 2 |
| Manquants | aucun | aucun | — | — |

## Exclusions

**Wheel** : aucune occurrence, dans les noms de fichiers, de `tests/`, `docs/`, `scripts/`, `rapports`, `fixtures`, `__pycache__`, `.pyc`, `.venv`, `storage/`, `env/dev`, `.forge-design`, `secrets`, `forge_design_circuit` ou `forge_design_flowchart`.

**sdist** : les exclusions de la wheel ne lui sont pas appliquées mécaniquement. Il contient en plus `tests/` (normal pour un sdist), mais ni `docs/`, ni `scripts/`, ni fixtures, ni modules.

**Chemins absolus**, recherchés dans tous les membres des deux archives :

| Motif | Occurrences | Classement |
|---|---|---|
| Chemin du dossier de release, `/tmp/claude…`, `scratchpad`, `venv-build` | aucune | — |
| `/home/roger` | `tests/test_entity_source.py` (sdist seulement) | Entrée hostile d'un test de sécurité : un chemin absolu qui doit être **refusé**. Ce n'est pas un chemin de la machine de build. |
| `/.venv/` | `project_python.py`, `runtime_diagnostics.py`, `child_bootstrap.py` (et 3 tests du sdist) | Motif relatif documenté `<racine>/.venv/bin/python`, dans des docstrings. Ce n'est pas un chemin de venv. |

**Secrets** :

- **Valeurs synthétiques des fixtures** (`AccSecret123`, `TokAcc777`, `PgAcc456`, `KeyAcc888`, `QryAcc111`, `AuthAcc999`) : **aucune** dans la wheel ni dans le sdist.
- **Mots-clés génériques** dans la wheel, classés à la main :
  - `PASSWORD` et `OPENAI_API_KEY` : règles et docstring de masquage (`debug_redaction.py`) ;
  - `TOKEN` : `MAX_TEMPLATE_JINJA_TOKENS` (limite d'analyse Jinja, `limits.py`, `template_structure.py`), regex de forme `_TOKEN` (`revision_tokens.py`), clés citées par le masquage ;
  - `SECRET`, `Authorization:` : aucune occurrence.

Aucune valeur secrète.

## METADATA

| Champ | Valeur |
|---|---|
| Name | `forge-design` |
| Version | `0.2.0` |
| Requires-Python | `>=3.12` |
| Requires-Dist | `packaging>=24.0`, `forge-mvc==1.0.0rc9`, `jinja2==3.1.6`, `pydantic<3,>=2` ; extra `dev` : `pytest>=8`, `ruff>=0.9`, `pyright>=1.1.390` |
| Description-Content-Type | `text/markdown` (README) |
| Description longue | Contient `http://127.0.0.1:8765/`. La seule ligne qui contient `localhost` est la phrase de refus (FD-DOCS-001) : « … refuse les autres valeurs de `Host`, y compris `localhost` : utiliser `http://127.0.0.1:8765/`. » |

## Entrypoint

`entry_points.txt` : `[console_scripts] forge-design = forge_design.cli:main`.

Dans les deux venvs, le script `bin/forge-design` installé importe `from forge_design.cli import main` et appelle `sys.exit(main())`. `forge-design --help` affiche `usage: forge-design [-h] [--version] [--no-browser] [--module PACKAGE]`.

## Installation wheel

Venv neuf `venv-wheel`, créé depuis `/usr/bin/python3` 3.13.5, cwd `/tmp`. Les dépendances sont téléchargées une fois ; l'installation se fait **hors ligne** (`--no-index --find-links`) depuis l'artefact de `dist-release/` :

| Contrôle | Résultat |
|---|---|
| `pip check` | No broken requirements found |
| `forge-design --version` | Forge Design 0.2.0 |
| `forge-design --help` | OK |
| Code chargé | `venv-wheel/lib/python3.13/site-packages/forge_design/` |

Puis, **dans le même environnement**, ajout des roues `forge-design-circuit` 0.1.0 et `forge-design-flowchart` 0.1.0, construites depuis leurs dépôts propres, restés à 0 changement :

| Contrôle | Résultat |
|---|---|
| `pip check` (wheel + modules) | No broken requirements found |
| Paquets | `forge-design` 0.2.0, `forge-design-circuit` 0.1.0, `forge-design-flowchart` 0.1.0, `forge-mvc` 1.0.0rc9, `Jinja2` 3.1.6, `pydantic` 2.14.1 |

## Installation sdist

Venv neuf `venv-sdist`, installation hors ligne de `forge_design-0.2.0.tar.gz`. pip construit la wheel avec setuptools depuis le dossier local de dépendances :

| Contrôle | Résultat |
|---|---|
| `pip check` | No broken requirements found |
| `forge-design --version` | Forge Design 0.2.0 |
| `forge_design.__version__` | 0.2.0 |

**Contenu installé, wheel et sdist comparés.** On compare `site-packages/forge_design/` en ignorant `*.dist-info` et `__pycache__` (`.pyc` compilés à l'installation) :

| Contrôle | Résultat |
|---|---|
| Fichiers | 161 / 161 |
| Différences de liste ou de contenu | **aucune** |
| `__init__.py`, `cli.py`, `revision_tokens.py`, `real_preview/child_bootstrap.py`, `py.typed` | présents dans les deux, identiques |
| Gabarits, statiques, schémas | 16 / 14 / 2 dans les deux |

## Démarrage

Serveur installé (`venv-wheel/bin/forge-design --no-browser`), HOME isolé, environnement minimal (`PATH`, `HOME`, `LANG`), sans `PYTHONPATH` :

| Dossier courant | Sortie de la CLI | Projet implicite | Écoute | Ctrl+C | Processus restants |
|---|---|---|---|---|---|
| `/tmp` | `Forge Design 0.2.0` / `http://127.0.0.1:8765/` | Non | `127.0.0.1:8765` seulement | code 0 | aucun |
| Dossier quelconque | idem | Non | idem | code 0 | aucun |
| Racine du projet Forge A | idem | **Non** | idem | code 0 | aucun |

## Sécurité locale

| Contrôle | Résultat |
|---|---|
| `Host: 127.0.0.1:8765` | 200 |
| `Host: localhost:8765` | **400** |
| `Host` étranger, DNS rebinding | 400 |
| POST avec Origin étrangère, sans Origin, ou `Sec-Fetch-Site: cross-site` | 403 |
| Écoute | `127.0.0.1:8765` uniquement |

## Smoke utilisateur

**72 contrôles sur 72**, avec les artefacts installés : la wheel de `dist-release/` et les deux modules.

Les projets sont construits à neuf par `build_projects.py` du kit (venv Forge 1.0.0rc9 réel). Les contrôles utilisent les sondes HTTP de `probes.py`, sans modifier le kit. Le serveur tourne depuis cwd `/tmp`, avec `--module forge_design_circuit --module forge_design_flowchart`.

Parcours sur A :

- ouverture ;
- `/inspector`, `/routes`, `/entities`, `/templates`, `/debug` à 200, avec leur contenu ;
- fermeture du projet (« Aucun projet ») ;
- arrêt par Ctrl+C, code 0 ;
- aucun processus restant.

**Transparence sur la première exécution.** Une première exécution du script avait signalé 2 contrôles en échec sur 72. L'analyse a montré deux **défauts du script de smoke**, sans rapport avec le produit :

1. **Isolation des assets** : le script cherchait les assets des modules dans les seuls attributs `src` et `href`. Or le script d'édition est déclaré dans le JSON `data-module-editor` de la page, où se trouve d'ailleurs `/modules/circuit/assets/circuit-editor.js`.
2. **Ligne de commande de l'enfant** : `probes.cmdline` tronque à 200 caractères, et `child_bootstrap.py` se trouvait au-delà.

Le script a été corrigé : lecture de toutes les URL `/modules/<id>/assets/…`, lecture de `/proc/<pid>/cmdline` en entier. Les projets ont été reconstruits à neuf et le smoke rejoué en entier : **72/72**.

Pendant cette analyse, un serveur d'inspection lancé à la main en arrière-plan ignorait SIGINT. C'est un effet du shell non interactif (`SigIgn` contenait SIGINT), pas du produit ; il a été arrêté par SIGTERM. Les arrêts par Ctrl+C du smoke, lancés directement, rendent tous le code 0.

## Modules externes

| Contrôle | Résultat |
|---|---|
| Activation `--module forge_design_circuit --module forge_design_flowchart` | Réussie ; démarrage et sortie de la CLI normaux |
| Navigation | `/modules/circuit/` et `/modules/flowchart/` présents, 200 |
| Pages de ressource (B-write) | `simple.flow.json` et `demo.circuit.json` : 200 |
| **Isolation des assets**, page Flowchart | Référence uniquement `/modules/flowchart/assets/flow-editor.js` et `/modules/flowchart/assets/flowchart.css` : **aucun** asset Circuit ; tous servis (200) |
| **Isolation des assets**, page Circuit | Référence uniquement `/modules/circuit/assets/circuit-editor.js` : **aucun** asset Flowchart ; servi (200) |
| ToolRegistry, modules actifs | **5 Tools** : `project-inspector`, `route-explorer`, `entity-explorer`, `debug-center`, `template-viewer` |
| Conflits | Aucun (`pip check`, activation, pages) |

## Compatibilité modules

| Élément | Cœur 0.2.0 | Circuit 0.1.0 | Flowchart 0.1.0 |
|---|---|---|---|
| Version d'API des modules | `MODULE_API_VERSION = 1` (supportées : {1}) | `api_version = MODULE_API_VERSION` | idem |
| Exigence sur Forge Design (descripteur) | — | `FORGE_DESIGN_REQUIREMENT = ">=0.2.0,<1"` | idem |
| Exigence (`Requires-Dist`) | — | `forge-design>=0.2.0,<1` | idem |
| Résultat avec 0.2.0 | — | Activé | Activé |

Les cas d'incompatibilité restent couverts par les tests existants, tous verts : `core-version-incompatible`, `core-version-unknown`, `descriptor-invalid` (`tests/test_module_version_compatibility.py`, `tests/test_modules_contract.py`).

## Project Inspector

Sur l'installation de release : ouverture de A, `/inspector` à 200 avec la synthèse Forge, fermeture. Le détail fonctionnel (sections, ACC-002, projets récents et invalides) a été qualifié par FD-ACCEPTANCE-002 sur un `forge_design/` identique.

## Éditeur

Régression **ACC-004** par HTTP, sur B-write, avec les vrais jetons de révision lus dans les formulaires :

| Étape | Résultat |
|---|---|
| Vue A puis vue B affichées (révision R1) | — |
| B ajoute une section | 303 ; nouvel état du fichier |
| A soumet sa vue R1 | **409**, message « Le design a été modifié depuis l'affichage de cette page… » |
| Fichier après la soumission de A | **Identique octet pour octet** à l'état laissé par B |
| Rechargement, puis action valide | 303 |

La suite automatisée couvre en plus les 10 actions dans `tests/test_web_editor_revision.py` (verte).

## Real Preview

Régression **ACC-003** sur A-preview, avec l'installation de release :

| Étape | Résultat |
|---|---|
| Start | 303 |
| Iframe | Origine loopback dédiée, port distinct du serveur |
| GET de l'URL de l'iframe | **200**, HTML |
| Commande de l'enfant | `…/A-preview/.venv/bin/python -I -B -u …/site-packages/forge_design/real_preview/child_bootstrap.py --port <port>` : le bootstrap vient de la roue installée |
| Stop | 303 ; proxy fermé, aucun enfant restant |
| Instantané d'A-preview avant et après | **Identique** : 0 ajout, 0 modification, 0 mtime, aucun `__pycache__` |

La suite automatisée (`tests/test_real_preview_bytecode.py`) couvre aussi l'instantané pendant `running`, les caches préexistants et le témoin sans `-B`.

## Debug runtime

| Projet | Commande | Résultat |
|---|---|---|
| A (contrôlé) | `doctor` | succeeded |
| A | `project:audit` | succeeded |
| A | `project:check` | succeeded |
| C-check | `project:check` | succeeded ; `DB_PASSWORD=[masqué] depuis le contrôleur` ; valeur absente du HTML ; sentinelle `CONTROLLER_IMPORTED` écrite par le code applicatif |

Aucun enfant ne reste après les commandes. Le délai dépassé n'est pas rejoué ici (§56) : il est couvert par la suite (`tests/test_runtime_unbuffered.py`, `tests/test_runtime_*`).

## Processus

| Moment | Processus restants dans la zone de smoke |
|---|---|
| Après chacun des trois démarrages (Ctrl+C) | aucun |
| Après la preview réelle (stop) | aucun enfant |
| Après les commandes runtime | aucun enfant |
| Après l'arrêt du serveur avec modules (Ctrl+C) | aucun |

Instantanés des 10 projets avant et après le smoke :

- conformes ;
- seules écritures : `mvc/views/contacts/list.design.json` dans B-write (éditeur) et `CONTROLLER_IMPORTED` dans C-check (code applicatif) ;
- aucun mtime parasite.

## Suite complète

Lancée dans le worktree de release (`b38a2c2`, puis `b38a2c2` avec ce rapport et la roadmap) :

| Commande | Résultat |
|---|---|
| `python -m compileall -q forge_design tests` | OK |
| `ruff check forge_design tests scripts` | All checks passed |
| `ruff format --check .` | Aucun fichier à reformater |
| `pyright` (strict) | 0 erreur, 0 avertissement |
| `git diff --check` | OK |
| `pytest` (suite complète) | **5 097 passed** |
| Régressions ciblées (`test_web_editor_revision.py`, `test_real_preview_bytecode.py`, `test_module_version_compatibility.py`) | 89 passed |
| `node --test tests/js/graphics/*.test.mjs` | 134/134 |

## Documentation

| Point | État |
|---|---|
| ACC-001 | Corrigé (FD-DOCS-001) ; la `METADATA` publiée donne `http://127.0.0.1:8765/` |
| ACC-002 | Toujours documenté comme MINOR (roadmap, FD-ACCEPTANCE-002, FD-DOCS-001) |
| SéquenCiel gate | OPEN (roadmap, FD-ACCEPTANCE-002) |
| Changelog | Le dépôt n'en a pas (`docs/release/versioning.md` est une politique de version) : aucun système de changelog n'est créé, les notes de release sont ci-dessous |
| `mkdocs build --strict` | Sans objet (MkDocs non configuré) ; non ajouté |

## Limites connues

- **ACC-002 (MINOR)** : sur le squelette Forge officiel, `register_optins(router)` est une déclaration non interprétée, et Project Inspector affiche « Routes — ! Attention ». Corrigé par FD-ROUTES-022, hors chemin critique.
- **Fenêtre de concurrence interne de `write_design`** (constat de FD-EDITOR-007) : entre deux threads d'un même processus, deux publications peuvent passer. Cette fenêtre n'est pas atteignable avec le serveur livré, qui traite une requête à la fois, et le design n'est jamais mélangé. Le verrou en cours (FD-EDITOR-008) **n'est pas intégré** à cette release.
- **Configuration de packaging** : avertissement de setuptools 84 sur les dossiers de données `web/static` et `web/templates` (voir Build wheel). Toutes les ressources sont présentes.
- **Preview réelle** : elle exécute le code du projet. `-B` empêche l'écriture de bytecode, mais pas les effets de bord propres à l'application.
- **Python** : qualifié sur **3.13.5**, l'interpréteur de référence actuel (`requires-python >=3.12`). Il n'y a pas de matrice multi-version.

## Hashes SHA-256

Artefacts de release (`<scratch>/release/dist-release/`, issus de `build1`) :

| Artefact | SHA-256 |
|---|---|
| `forge_design-0.2.0-py3-none-any.whl` | `9e4c3c36cb789971f51a955ac5bc61bf3ac5572876cacc0c553e150f9fb91a65` |
| `forge_design-0.2.0.tar.gz` | `83b8580e1b88a1808127d95bb5a2af9b1be74a2c111ba846d588fc64b7169f48` |

Les archives de `build2` ont des empreintes différentes (horodatages) pour un contenu identique (voir Reproductibilité). Une nouvelle construction redonnera le même contenu, mais pas ces octets.

Roues des modules utilisées pour la qualification :

| Artefact | SHA-256 |
|---|---|
| `forge_design_circuit-0.1.0-py3-none-any.whl` | `9cd7cb2708291c178145bbca75c6b99d97580b9939c7f638844b976e95a4dd8f` |
| `forge_design_flowchart-0.1.0-py3-none-any.whl` | `aedbc147a9f4eb64ad608aebe72d13c79bc6f584834096b692aacbc3e6f65866` |

Aucune signature (GPG, Sigstore) : le projet n'en a pas.

## Notes de release

### Forge Design 0.2.0

Cockpit graphique local pour les projets Forge MVC. Il s'installe avec `pip` (Python 3.12 ou plus, qualifié sur 3.13), se lance avec `forge-design` et s'utilise dans le navigateur à l'adresse `http://127.0.0.1:8765/`.

**Principales capacités**

- **Project Inspector** : reconnaissance du projet, version Forge, synthèse de santé en neuf sections, projets récents.
- **Route Explorer** : chaîne de chaque route (handler, contrôleur, méthode, template, contrat de vue), diagnostics, filtres, graphe.
- **Entity Explorer** : entités, champs, relations, diagnostics, graphe.
- **Template Viewer** : inventaire, lecture brute, arbre, références, Jinja invalide signalé.
- **Debug Center** :
  - journal runtime avec masquage des secrets, filtres, détail et flux ;
  - exécution à la demande de `forge doctor`, `forge project:audit` et `forge project:check`, bornée et non persistée.
- **Éditeur structurel** des `.design.json` : écriture atomique, vue périmée refusée (409).
- **Preview statique** et **preview réelle** du projet, sur une origine loopback dédiée, sans bytecode écrit par Forge Design.
- **Graphic Core** commun : graphes, minicarte, zoom sémantique, édition générique.
- **Modules externes**, activés explicitement par `--module` : contrat versionné (`MODULE_API_VERSION = 1`), assets isolés.

**Sécurité locale.** Écoute sur `127.0.0.1` uniquement. `Host` strict : `localhost` est refusé. Les mutations exigent une `Origin` locale. Pas d'exposition réseau, pas d'accès du navigateur au système de fichiers.

**Compatibilité des modules.** `forge-design-circuit` 0.1.0 et `forge-design-flowchart` 0.1.0 exigent `forge-design>=0.2.0,<1`. Ils sont qualifiés ensemble dans le même environnement.

**Limites connues** : ACC-002 (MINOR, avertissement des routes sur le squelette officiel), fenêtre de concurrence interne de `write_design` non atteignable avec le serveur livré, preview réelle soumise aux effets de bord de l'application, configuration de packaging à moderniser.

**Qualification**

- FD-ACCEPTANCE-002 : ACCEPTED_WITH_MINOR_ISSUES (deux passes, Chromium, Firefox, sans JavaScript) ;
- FD-DOCS-001 : documentation alignée ;
- FD-RELEASE-002 : release reproductible, identique à l'arbre Git, installée et vérifiée.

**SéquenCiel gate: OPEN.**

## Verdict release

**RELEASE_READY**

Aucun cas de blocage n'est observé :

| Cas de blocage (§71) | Constat |
|---|---|
| Wheel contaminée | Non : 161/161 identiques à Git, `locking.py` absent |
| sdist incomplet | Non : wheel reconstruite depuis le sdist, complète ; 0 fichier `forge_design/` manquant |
| Installation qui échoue | Non : wheel, sdist, modules |
| `pip check` qui échoue | Non : trois fois OK |
| CLI cassée | Non : `--version`, `--help`, démarrage, Ctrl+C |
| Module incompatible | Non : activation réussie, contraintes cohérentes |
| Régression ACC-003 | Non : A-preview identique, enfant `-I -B -u` |
| Régression ACC-004 | Non : 409, aucune écriture |
| Fuite de secret | Non : aucune valeur dans les artefacts ni dans les pages |
| Exposition réseau | Non : `127.0.0.1` uniquement, garde `Host` |
| Processus orphelin | Non |
| Suite rouge | Non : 5 097 passed, 134/134 |

Seules les limites déjà acceptées restent (ACC-002 et la fenêtre interne de `write_design`), plus une dette de configuration de packaging, sans effet sur la 0.2.0. Le verdict découle des résultats ; rien n'a été modifié pour l'obtenir.

## SéquenCiel gate

**SéquenCiel gate: OPEN** (décidé par FD-ACCEPTANCE-002, inchangé). **Forge Design 0.2.0 est prêt pour son premier essai réel sur SéquenCiel.** Ce ticket n'a ni ouvert, ni lancé, ni modifié SéquenCiel.

## Fichiers créés

- `docs/rapports/FD-RELEASE-002.md`

## Fichiers modifiés

- `docs/03-roadmap.md` : FD-RELEASE-002 → RELEASE_READY, Forge Design 0.2.0 prêt pour le premier essai sur SéquenCiel

Non modifiés :

- `forge_design/`, tests, `scripts/`, `pyproject.toml`, README ;
- les rapports historiques ;
- Circuit et Flowchart.

Les artefacts (wheel, sdist, venvs) restent hors dépôt et ne sont pas versionnés.

## Validation finale

| Contrôle | Résultat |
|---|---|
| Worktree propre avant / après | 0 / 0 ligne |
| Version unique 0.2.0 | 6 sources concordantes |
| Builds reproductibles | 2 builds, contenu identique |
| Identité avec Git | wheel 161/161, sdist 303/303 |
| Installations | wheel, sdist, wheel + modules : `pip check` OK |
| Smoke installé | 72/72 |
| Suite complète | 5 097 passed, 134/134 Node, `pyright` 0, `ruff` OK |
| `mkdocs build --strict` | Sans objet |

La suite a été relancée après la rédaction de ce rapport et de la roadmap (voir État Git final).

## État Git final

Un seul commit : `release: qualifier Forge Design 0.2.0 (FD-RELEASE-002)`, au-dessus de `b38a2c2`. Il ne contient que ce rapport et la roadmap. Il n'y a ni tag, ni push, ni publication.

Restent hors commit, sur disque :

- `docs/rapports/FD-CONTRACT-001.md`, modifié par l'utilisateur ;
- le travail concurrent (FD-EDITOR-008, requalification FD-ACCEPTANCE-001) ;
- les fichiers de vérification de FD-EDITOR-007.

La version reste 0.2.0.
