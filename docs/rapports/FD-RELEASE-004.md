# Rapport — FD-RELEASE-004

Qualification de la release locale **Forge Design 0.3.0**, qui intègre Real
Preview depuis Route Explorer sans Design (FD-REALPREVIEW-008).
Date : 2026-10-18.

## Objectif

Transformer la baseline issue de FD-REALPREVIEW-008 en release locale 0.3.0,
complètement qualifiée et reproductible : version, artefacts wheel et sdist,
acceptance de release et modules.

Aucune capacité nouvelle, aucune dette corrigée :

- FD-ROUTES-023 ;
- déclarations GET conflictuelles du parcours éditeur ;
- `favicon.ico` ;
- WeasyPrint ;
- `TMPDIR` ;
- `pycache_prefix`.

**Verdict : RELEASE_READY.**

## État Git initial

| Commande | Résultat |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse --short HEAD` | `8f1c245` |
| `git rev-parse --short origin/main` | `bb16f90` |
| `git rev-list --left-right --count origin/main...HEAD` | `0 5` |
| `git status --short` | `M docs/rapports/FD-CONTRACT-001.md` (modification utilisateur, préservée) et 9 entrées non suivies historiques (rapports et dossiers de vérification) |
| Collision (§4) | Aucun rapport FD-RELEASE-004 ; seulement des mentions dans la roadmap et dans FD-REALPREVIEW-008 → poursuite |

Aucun `reset`, `clean`, `stash`, checkout destructif ni `git add .` ou `-A`.

## Baseline

`git log` contient, dans l'ordre :

- `a80316e` FD-RELEASE-003 ;
- `bb16f90`, `47b7799`, `9d125f2`, `3a9e711`, `385587b` : FD-SEQUENCIEL-001 à 005 ;
- `8f1c245` : `feat: ouvrir Real Preview depuis Route Explorer (FD-REALPREVIEW-008)`.

Le commit de release produit par ce ticket est **`295bc91`**
(`build: passer à 0.3.0 (FD-RELEASE-004)`). Tous les artefacts et l'acceptance
sont construits depuis ce commit. Le commit de rapport qui suit ne touche que la
documentation.

## Version 0.3.0

| Source | Valeur |
|---|---|
| `forge_design.__version__` (source unique, seule modifiée) | `0.3.0` |
| `pyproject.toml` | `dynamic = ["version"]`, inchangé |
| METADATA de la roue | `Version: 0.3.0` |
| PKG-INFO du sdist | `Version: 0.3.0` |
| `forge-design --version` (roue, sdist, `.venv` éditable) | `Forge Design 0.3.0` |
| Démarrage installé | `Forge Design 0.3.0` / `http://127.0.0.1:8765/` |
| `results/version.txt` des deux passes d'acceptance | `Forge Design 0.3.0` |

C'est une version **MINEURE** (`docs/release/versioning.md`) : la capacité
publique est additive et compatible (nouvelle entrée utilisateur, trois routes
HTTP).

Assertions de version exacte mises à jour, de `== "0.2.1"` à `== "0.3.0"`, sans
affaiblissement :

- `tests/test_import.py` ;
- `tests/test_module_version_compatibility.py` : `__version__` et le message
  « version installée : 0.3.0. ».

Le `.venv` de développement éditable a été réinstallé en mode `compat`, hors
ligne avec setuptools 84.0.0 local : il reste un `.pth` et non un finder, et sa
métadonnée vaut 0.3.0. Il n'y a pas de `build/` résiduel.

## Compatibilité

- Formats Design, ViewContract et schémas : inchangés.
- Parcours éditeur : inchangé, avec un gardien de mutation (voir Mutations).
- API Python : ajouts seulement, ceux de FD-REALPREVIEW-008.

## Module API

`MODULE_API_VERSION = 1` (`forge_design/modules/descriptor.py`), inchangé.
`ModuleDescriptor` et `ResourceBinding` sont inchangés.

## Circuit

- Dépôt à `967b5b3`, 0 changement ; version 0.1.0.
- Déclare `forge-design>=0.2.0,<1`, dans `Requires-Dist` comme dans
  `requires_forge_design`. La 0.3.0 est acceptée **sans modification**.
- Roue reconstruite depuis `git archive HEAD` : 20 membres, contenu identique à
  la roue qualifiée en 0.2.1 (seuls les horodatages zip diffèrent).

## Flowchart

- Dépôt à `a8ec22d`, 0 changement ; version 0.1.0, même contrainte.
- Roue : 16 membres, contenu identique à celle de la 0.2.1.

## Nouveau parcours Real Preview

Route Explorer → route GET éligible → **Prévisualiser réellement** → Start →
iframe → Stop, sans `.design.json` ni `.view.json`. C'est désormais un contrat
de release, qualifié par :

- le smoke sur artefacts installés ;
- les deux passes d'acceptance (Chromium, Firefox, sans JavaScript) ;
- les tests Python.

## Parcours historique Real Preview

Design → ViewContract → route → Real Preview, qualifié de même : smoke sur
`A-preview` et étape « preview réelle A-preview » des deux passes. Les deux
parcours partagent le même `RealPreviewRuntime`, le même
`RealPreviewController`, le même `child_bootstrap.py`, le même proxy et le même
arrêt (smoke « runtime partagé »).

## Sélection de route

Les garanties de Route Explorer sont revérifiées sur installation, par le smoke
avec R-mix, et par les tests :

- GET ;
- chemin statique ;
- publique ;
- handler vérifié et non dynamique ;
- template exact et présent ;
- identité `GET <chemin>` unique.

Les mutants M3 à M6 sont tués.

## Revalidation serveur

Chaque POST relit l'inventaire, retrouve la route par égalité exacte, recalcule
l'éligibilité et refuse si elle a changé. C'est vérifié sur installation (smoke
TOCTOU et R-mix) et par mutation : M2, qui supprime la revalidation, est tué.

## Sécurité

| Contrôle | Résultat (smoke et deux passes) |
|---|---|
| Écoute | `127.0.0.1:8765` seulement ; preview : écoutes nouvelles toutes en `127.0.0.1` |
| Garde Host | `127.0.0.1` 200 ; `localhost`, Host étranger et rebinding 400 |
| Origin | POST étranger, sans Origin ou `cross-site` → 403 |
| `no-store` | `/routes` et page d'état de la preview |
| CSP | Forge par défaut ; `frame-src 'self' <proxy>` seulement sur la page d'état, proxy actif ; `X-Frame-Options: DENY` |
| POST explicite | GET `/routes` et page d'état : aucun runner |

## Package data

Point critique, issu de FD-REALPREVIEW-008 : `route_real_preview.html` doit être
présent partout.

| Étape | `forge_design/web/templates/route_real_preview.html` |
|---|---|
| Git (`295bc91`) | Présent |
| Roue (build1 et build2) | Présent, blob identique à Git |
| sdist (build1 et build2) | Présent, identique à Git |
| Installation roue | Présent (164 fichiers installés) |
| Installation sdist | Présent, identique à l'installation roue |
| Acceptance (sonde roue du kit) | 169 fichiers, 35 ressources contrôlées, **0 manquant** |

Mutation M1 (entrée retirée de `package-data`) : tuée par
`test_web_package_data_lists_every_template_and_asset`.

## Build wheel 1

- **Chaîne** : venv de build dédié, Python 3.13.5, setuptools 84.0.0, build
  1.6.1, installés hors ligne (même chaîne qu'en 0.2.1).
- **Source** : `git archive 295bc91`, extrait dans un dossier neuf.
- **Commande** : `python -m build --no-isolation`.
- **Résultat** : `forge_design-0.3.0-py3-none-any.whl`, 324 520 octets, 169
  membres (164 sous `forge_design/` et 5 en `dist-info`). RECORD vérifié sur les
  169 entrées, aucun écart.
- **Point d'entrée** : `forge-design = forge_design.cli:main`.
- **`Requires-Dist`** : `packaging>=24.0`, `forge-mvc==1.0.0rc9`,
  `jinja2==3.1.6`, `pydantic<3,>=2`, plus l'extra `dev`.
- **Avertissement setuptools** : le même qu'en 0.2.0 et 0.2.1 (`web.static`,
  `web.static.graphics` et `web.templates` absents de `packages`), non corrigé ;
  toutes les ressources sont présentes.

## Build wheel 2

Second dossier neuf, même commit et même commande. La roue est **identique
octet pour octet** :
`d7e9f2eccdda838775f6ad2d72c896dbdff06903d5d039fe0c8ab216b072c2b1`.

## Build sdist 1

`forge_design-0.3.0.tar.gz`, 574 517 octets, 317 membres :

- 309 suivis par Git : `forge_design/`, `tests/`, `pyproject.toml`, `README.md` ;
- 8 métadonnées générées : `PKG-INFO`, `setup.cfg`, `forge_design.egg-info/*`.

Ni `docs/`, ni `scripts/`, ni fixtures.

## Build sdist 2

574 490 octets, 317 membres, mêmes noms et **mêmes contenus**. Les différences
se limitent aux métadonnées d'archive : les en-têtes tar (mtime) des 8
métadonnées générées au moment du build, et l'horodatage gzip.

## Reproductibilité

| Contrôle | Résultat |
|---|---|
| Wheel : noms et contenus des 169 membres | Identiques |
| Wheel : SHA-256 | **Identique** (`d7e9f2ec…c2b1`) |
| sdist : noms et contenus des 317 membres | Identiques |
| sdist : SHA-256 | Différent (`99ec6e13…84d5` / `8b9a88e5…bd4c`), en-têtes tar des 8 fichiers générés et horodatage gzip seulement ; acceptable (§27) |
| METADATA, PKG-INFO, RECORD, `entry_points`, `package-data` | Identiques |

## Identité avec Git

| Contrôle | Résultat |
|---|---|
| Wheel `forge_design/*` contre les blobs de `git ls-tree -r 295bc91` | **164/164** identiques ; 0 manquant, 0 en plus, 0 différent |
| sdist : membres suivis contre les blobs Git | **309/309** identiques |
| sdist : fichiers `forge_design/` de Git absents | 0 |

## Ressources

**35 ressources** attendues, calculées depuis le dépôt : 17 gabarits, 14
statiques, 2 schémas, `py.typed` et `child_bootstrap.py`. Il n'en manque
**aucune** dans la roue ni dans le sdist.

| Ressource clé | Git | Roue | sdist |
|---|---|---|---|
| `web/templates/route_real_preview.html` | ✓ | ✓ identique | ✓ identique |
| `web/templates/routes.html` | ✓ | ✓ | ✓ |
| `real_preview/route_selection.py` | ✓ | ✓ | ✓ |
| `web/real_preview.py` | ✓ | ✓ | ✓ |

## Exclusions

- **Roue** : aucun fichier de `tests/`, `docs/`, `scripts/` ou rapports, aucun
  scratchpad ni preuve ; aucun `.venv`, `__pycache__`, `.pyc`, `storage/` ou
  `.forge-design`, ni module Circuit ou Flowchart.
- **sdist** : aucun scratchpad, `tmp/`, rapport, `storage/`, `.venv`,
  `__pycache__` ni `.pyc` ; aucun fichier utilisateur non suivi (source
  `git archive`).
- **Secrets synthétiques** du kit (6) : aucune occurrence dans la roue ni dans
  le sdist.
- **Chemins absolus** : aucun dans la roue. Dans le sdist, seulement
  `tests/test_entity_source.py`, une entrée hostile refusée, déjà classée en
  0.2.0 et 0.2.1.

## Installation wheel

Venv neuf, installation hors ligne (`--no-index`, dépendances téléchargées
d'avance) :

- `pip check` : No broken requirements found ;
- `forge-design --version` : `Forge Design 0.3.0` ; `--help` : OK ;
- code chargé depuis `site-packages`.

## Installation sdist

Second venv neuf, installation hors ligne du sdist, avec setuptools 84.0.0 local
comme backend : `pip check` OK, `Forge Design 0.3.0`.

## Comparaison des installations

`site-packages/forge_design` installé depuis la roue et depuis le sdist
(`__pycache__` et `.pyc` exclus) : **164/164 fichiers identiques**.

## Installation avec modules

Venv de la roue avec `forge-design-circuit` et `forge-design-flowchart` 0.1.0
(roues reconstruites ci-dessus) :

- `pip check` OK ;
- installés : forge-design 0.3.0, Circuit 0.1.0, Flowchart 0.1.0, forge-mvc
  1.0.0rc9, Jinja2 3.1.6, pydantic 2.14.1 ;
- `Requires-Dist` des modules : `forge-design<1,>=0.2.0` ;
- `activate_modules` : circuit et flowchart actifs, 0 diagnostic ;
- **5 Tools** (`project-inspector`, `route-explorer`, `entity-explorer`,
  `debug-center`, `template-viewer`), les modules restant hors du registre,
  externes.

## Smoke Route Explorer sans Design

**Smoke global : 83/83.** Le script, en bibliothèque standard, a été écrit pour ce
ticket et lu en entier avant usage. Il pilote le **serveur installé** (roue et
modules), lancé depuis `/tmp`, avec un HOME isolé, un environnement minimal et
Ctrl+C. Les projets sont construits par `build_projects.py` **du commit de
release**, à partir d'un venv forge-mvc neuf.

Sur `A-route-preview` (vérifié : 0 `.design.json`, 0 `.view.json`) :

- **Démarrage** : `Forge Design 0.3.0`, `127.0.0.1:8765` seulement ; garde Host
  200, 400, 400 ; `no-store` et CSP sur `/routes`.
- **Route Explorer** : `/routes` donne `GET /contacts` et `GET /` éligibles,
  avec bouton et avertissement ; aucun runner au GET.
- **Start** : 303 vers `/routes/real-preview?route=%2Fcontacts`.
- **Page d'état** : `running`, iframe `http://127.0.0.1:<proxy>/contacts`, CSP
  `frame-src` limitée au proxy, `X-Frame-Options: DENY`, `no-store`. L'iframe
  répond 200 en HTML.
- **Stop** : 303, état `stopped`, sans iframe, proxy fermé, aucun processus.

## Smoke éditeur

Sur `A-preview`, avec Design et contrat :

- l'éditeur affiche « Route : `/contacts` » et le Start ;
- Start éditeur → 303 ;
- iframe `/contacts`, qui répond 200.

## Smoke runtime partagé

- Preview démarrée par l'éditeur → `running` visible côté Route Explorer, avec
  la même iframe.
- Start depuis Route Explorer pendant ce temps → 303, **un seul runner**.
- Stop depuis Route Explorer → l'éditeur voit la preview arrêtée.
- Inverse : Start depuis Route Explorer, Stop depuis l'éditeur → la preview de
  Route Explorer est arrêtée.
- Aucun processus restant.

## Smoke routes refusées

R-mix est une copie de `A-route-preview`, sans Design, avec des routes
supplémentaires, dérivée par le smoke.

- **Affichage** :
  - `POST /contacts/delete` : « Méthode POST » ;
  - `GET /contacts/{id}` : « Route dynamique » ;
  - `GET /prive` : « Route protégée » ;
  - `GET /dynamique` : « Template dynamique ».

  Aucune n'a d'action.
- **POST forgés** :
  - 404 pour une route inconnue, une route POST seule et `/../etc/passwd` ;
  - 409 pour une route privée, un template dynamique et un template absent ;
  - 400 pour une route dynamique, `../../etc/passwd`, une URL absolue,
    `//hôte`, un chemin de template, un champ inattendu (`port`, `design`), un
    champ dupliqué et un formulaire vide ;
  - 403 pour un Origin étranger, un Origin absent ou `cross-site`.
- **Aucun runner** démarré.

## TOCTOU

Sur R-toctou, une copie sans Design :

1. `GET /contacts` est affichée éligible ;
2. la route est rendue privée sur disque ;
3. le POST donne **409** « Route protégée » ;
4. **aucun runner**.

## ACC-003

`-I -B -u` vérifié sur l'artefact installé : argv du runner `…/venv-wheel/…/site-packages/forge_design/real_preview/child_bootstrap.py`, nouvelle session (`getsid == getpgid == pid`), cwd = projet.

Instantanés complets (smoke) de `A-route-preview` et `A-preview` : **aucune
écriture**, sans `__pycache__` ni `.pyc`. R-mix ne montre que l'écriture du
smoke lui-même (template retiré puis restauré, contenu identique).

Acceptance : `A-route-preview` et `A-preview` conformes dans les deux passes, et
« Arrêt par Ctrl+C avec preview réelle active » sans écart.

## ACC-004

Rejoué dans les deux passes, OK :

- Chromium et Firefox : « éditeur B-write : vue périmée (deux onglets) refusée
  en 409, aucun bloc touché, rechargement » ;
- sans JavaScript : « éditeur, vue périmée refusée par formulaire natif, aucun
  bloc touché ».

`B-write` ne présente que ses écritures tolérées.

## Acceptance passe 1

Kit du commit `295bc91`, lancé depuis un **worktree détaché propre** de ce
commit, sans `ONLY`, dans un dossier neuf, avec `CIRCUIT_REPO` et
`FLOWCHART_REPO` explicites.

| Contrôle | Résultat |
|---|---|
| Code de sortie | 0 |
| Version | `Forge Design 0.3.0` |
| Roue du kit | 169 fichiers, 35 ressources, 0 manquant, 0 interdit |
| `pip check` | OK ; forge-design 0.3.0, Circuit 0.1.0, Flowchart 0.1.0, forge-mvc 1.0.0rc9 |
| Écoute, garde Host et Origin | Conformes |
| Chromium / Firefox / sans JavaScript | **32/32 / 32/32 / 12/12** |
| Instantanés | 12 projets × 2 navigateurs, plus l'arrêt : 25 « conforme », 0 écart, dont `A-route-preview` |
| Processus résiduels | 4 × `[]` |
| Endurance | 52 644 → 54 568 Kio, aucun enfant |
| Worktree | 0 ligne de statut avant comme après |

## Acceptance passe 2

Second dossier neuf, même worktree, même commande.

- Code 0, `Forge Design 0.3.0`, 32/32, 32/32, 12/12, 25 conformes, 0 écart,
  processus résiduels vides.
- **Étapes identiques** à la passe 1 : noms et statuts.
- **Fichiers de résultats déterministes identiques octet pour octet** : les 25
  `diff-*.json`, `diff-*.txt`, `hostguard.json`, `listen.json`,
  `installed.txt`, `nojs.txt`, `pip-check.txt`, `strays-*.json`,
  `version.txt`, `wheel.json`.
- **Seules différences** :
  - `startup.jsonl`, par `ready_ms` (durées) ;
  - `shutdown.txt`, par les PID et les ports de la preview ;
  - l'endurance, par la RSS : 52 568 → 54 584 Kio.

## Chromium

32/32 dans les deux passes. « preview réelle A-route-preview : Route Explorer
sans Design » OK, avec une iframe `/contacts` qui répond 200 (1 531 octets),
ports 50829 et 51729. « preview réelle A-preview » (éditeur) OK.

## Firefox

32/32 dans les deux passes. Même étape OK, avec une iframe qui répond 200 (1 531
octets), ports 39267 et 49849. Parcours éditeur OK.

## Sans JavaScript

12/12 dans les deux passes. « preview réelle depuis Route Explorer sans Design,
POST natif, arrêt » OK, par formulaire natif.

## Tests Python

Sur l'arbre du commit de release (`295bc91`), cwd hors du dépôt et basetemp
court : **5305 réussis**, 0 échec. C'est le même total que FD-REALPREVIEW-008 :
aucun test perdu.

## Tests Node

`node --test tests/js/graphics/*.test.mjs` : **134/134**.

## Mutations ciblées

Chaque mutant est appliqué par remplacement exact, testé par les tests ciblés,
puis restauré, avec vérification `git diff --quiet` du fichier.

| # | Mutation | Résultat | Premier test qui échoue |
|---|---|---|---|
| M1 | Retirer `route_real_preview.html` du `package-data` | **Tué** | `test_web_package_data_lists_every_template_and_asset` |
| M2 | Supprimer la revalidation serveur du POST | **Tué** | `test_route_start_refuses_unknown_route[/inconnue]` |
| M3 | Autoriser une route privée | **Tué** | `test_designated_route_refused[…Route protégée…]` |
| M4 | Autoriser une route dynamique | **Tué** | `test_designated_route_refused[…Route dynamique…]` |
| M5 | Supprimer l'unicité `GET <chemin>` | **Tué** | `test_conflicting_declarations_are_ambiguous` |
| M6 | Faire confiance au champ du navigateur (pas de recherche dans l'inventaire) | **Tué** | `test_conflicting_declarations_are_ambiguous` |
| M7 | Modifier la sélection historique de l'éditeur (clause « incertaine ») | **Tué** | `test_unavailable[…template non déterminable…]` |
| M8 | « Corriger » en silence l'éditeur sur les déclarations conflictuelles | **Tué** | `test_editor_selection_implies_route_eligibility` |

**8/8 tués**, et tous les fichiers ont été restaurés.

M7 et M8 sont les gardiens du §57 : toute modification, même bien intentionnée,
de `select_real_preview_route` est détectée. Le constat sur les déclarations
conflictuelles reste documenté et non corrigé.

## Documentation

- `docs/03-roadmap.md` : FD-RELEASE-004, 0.3.0, RELEASE_READY et la suite.
- Ce rapport, avec les notes de version.
- Le contrat Real Preview et Route Explorer (FD-REALPREVIEW-008) décrit déjà les
  deux parcours : inchangé.

## Release notes

### Forge Design 0.3.0

Version **MINEURE**, additive et compatible.

- **Real Preview accessible depuis Route Explorer, sans Design.** Une route GET
  éligible offre « Prévisualiser réellement », même sur un projet sans aucun
  `.design.json` ni `.view.json`. Une route éligible est publique, à chemin
  statique, avec un handler vérifié, un template exact et présent, et une
  identité `GET <chemin>` non ambiguë. Une route non éligible affiche sa raison,
  sans action.
- **Mêmes garanties de sécurité et même runtime.** Un seul `RealPreviewRuntime`
  sert aux deux entrées, avec le même runner (`python -I -B -u`, nouvelle
  session, aucun bytecode écrit), le même proxy, la même origine dédiée et le
  même arrêt. Le loopback, la garde Host, l'Origin strict, `no-store` et la CSP
  sont inchangés.
- **Revalidation serveur de la route.** Le POST ne reçoit qu'un identifiant de
  route. Le serveur relit l'inventaire, exige une égalité exacte et recalcule
  l'éligibilité : 400, 404 ou 409 sans runner. Une route modifiée entre
  l'affichage et le clic est refusée.
- **Parcours éditeur historique inchangé** : Design → ViewContract → route →
  Real Preview.
- **Aucun changement de l'API des modules** : `MODULE_API_VERSION = 1`, et
  Circuit et Flowchart 0.1.0 (`forge-design>=0.2.0,<1`) restent compatibles
  sans modification.
- **Nouvelles routes HTTP** : `GET /routes/real-preview`,
  `POST /routes/real-preview/start` et `POST /routes/real-preview/stop`.
- **Empaquetage** : un test garantit que chaque gabarit et asset Web est déclaré
  dans `package-data`.

## Limites restantes

Elles sont documentées et ne sont pas traitées ici (§3) :

- la sélection de l'éditeur ne détecte pas deux déclarations `GET <chemin>`
  différentes du même chemin (gardée par M8) ;
- la borne globale de 128 templates rend des chaînes partielles, donc non
  éligibles, sur les grands projets (FD-ROUTES-023) ;
- `favicon.ico` en 404 ;
- l'import de WeasyPrint au niveau module côté SéquenCiel ;
- pas de `TMPDIR` dédié, pas de `pycache_prefix` ;
- l'avertissement setuptools sur `packages`, sans effet sur le contenu ;
- le sdist n'est pas reproductible octet pour octet (horodatages
  d'archive) ;
- la licence publique, hors périmètre (§62) : la release reste **locale**,
  sans push, sans tag, ni PyPI ni GitHub Release.

## Verdict

**RELEASE_READY**

| Condition (§66) | Constat |
|---|---|
| Version 0.3.0 cohérente | Source, METADATA, PKG-INFO, CLI, démarrage et kit |
| Wheel propre | 169 membres, identité Git 164/164, exclusions et secrets conformes |
| sdist propre | 317 membres, identité Git 309/309, exclusions conformes |
| Deux builds qualifiés | Roue identique au SHA-256 ; sdist identique en contenu |
| Installations roue et sdist | `pip check` OK, 0.3.0, installations identiques (164/164) |
| Circuit et Flowchart compatibles | `pip check` OK, activés, 5 Tools, sans modification |
| Route Explorer sans Design | Smoke installé, deux passes et trois navigateurs |
| Éditeur historique | Smoke installé et deux passes |
| Revalidation serveur | Smoke TOCTOU et R-mix ; mutant M2 tué |
| Sécurité Host, Origin et loopback | Inchangée ; smoke et deux passes |
| Acceptance complète × 2 | Vertes, déterministes |
| Suite complète | 5305 Python, 134 Node, lint, format, types |
| Aucun processus résiduel | Smoke et quatre relevés par passe |

## SéquenCiel readiness

**SéquenCiel Real Preview readiness: READY_FOR_FD-SEQUENCIEL-005-RETRY**

Roue : `tmp/fd-release-004-dist/forge_design-0.3.0-py3-none-any.whl`, SHA-256
`d7e9f2eccdda838775f6ad2d72c896dbdff06903d5d039fe0c8ab216b072c2b1`. SéquenCiel
n'a pas été rejoué dans ce ticket (§63).

## Recommandation ticket suivant

**FD-SEQUENCIEL-005R** : reprendre Real Preview sur le vrai SéquenCiel avec la
roue 0.3.0, depuis Route Explorer et `GET /` (`home/index.html`). Méthode des
tickets FD-SEQUENCIEL-002 à 004 :

- lecture préalable de `app.py` et `wsgi.py` ;
- base de développement arrêtée ;
- `strace -f` et surveillant `/proc` sur toute la vie de la preview ;
- instantanés pendant la preview et vérification de l'arrêt du groupe.

Il faudra s'attendre au moins à la rafale weasyprint (FD-SEQUENCIEL-004) et à des
erreurs de base à la première requête. Ensuite seulement, FD-SEQUENCIEL-006 :
première édition contrôlée.

## Fichiers créés

- `docs/rapports/FD-RELEASE-004.md`

Hors dépôt suivi (`tmp/`, ignoré) :

- `tmp/fd-release-004-dist/` : roue, sdist, roues Circuit et Flowchart,
  `SHA256SUMS` ;
- `tmp/fd-release-004/` : builds, venvs, smoke, deux passes d'acceptance,
  `artifacts.json`.

Les scripts de smoke, de comparaison et de mutation sont restés dans le scratchpad
de session.

## Fichiers modifiés

| Commit | Fichiers |
|---|---|
| `295bc91` `build: passer à 0.3.0 (FD-RELEASE-004)` | `forge_design/__init__.py`, `tests/test_import.py`, `tests/test_module_version_compatibility.py` |
| `release: qualifier Forge Design 0.3.0 (FD-RELEASE-004)` | `docs/rapports/FD-RELEASE-004.md`, `docs/03-roadmap.md` |

Aucun changement du kit d'acceptance n'a été nécessaire : il affiche déjà la
version installée. Non modifiés : `docs/rapports/FD-CONTRACT-001.md`, Circuit,
Flowchart, SéquenCiel.

## Validation finale

| Commande (arbre du commit de release) | Résultat |
|---|---|
| `python -m compileall -q forge_design tests` | OK |
| `ruff check .` | All checks passed |
| `ruff format --check .` | Tous les fichiers formatés (rapport compris) |
| `pyright` | 0 erreur, 0 avertissement |
| `pytest` | **5305 réussis** |
| `node --test tests/js/graphics/*.test.mjs` | 134/134 |
| `git diff --check` | OK |
| Tests qui lisent `docs/` (après ce rapport) | 45 réussis |
| `scripts/acceptance/run.sh` × 2 sans filtre | Code 0, verts, déterministes |

## État Git final

Deux commits sur `main`, après `8f1c245` :

- `295bc91` `build: passer à 0.3.0 (FD-RELEASE-004)` ;
- `release: qualifier Forge Design 0.3.0 (FD-RELEASE-004)`.

Ils ne sont **pas poussés** : 7 commits d'avance sur `origin/main`. Aucun tag.
`docs/rapports/FD-CONTRACT-001.md` et les entrées non suivies historiques sont
inchangés et hors des commits. Le worktree de qualification est retiré.
