# Rapport — FD-RELEASE-003

Consolidation et qualification de Forge Design 0.2.1 avant le premier essai réel
sur SéquenCiel. Date : 2026-10-16.

## Objectif

Transformer trois correctifs locaux déjà qualifiés séparément en **une seule
baseline corrective 0.2.1**, committée et traçable, puis qualifier cet ensemble.

Les trois correctifs :

- **FD-FORGE-004** : `bootstrap.py` optionnel ; déjà committé.
- **FD-EDITOR-008** : verrou interprocessus de `write_design` ; qualifié, non committé.
- **FD-ACC-002** : registre d'opt-ins vide reconnu ; qualifié, non committé.

Aucune capacité nouvelle. Pas de tag, pas de push, pas de PyPI.

| Décision | Résultat |
|---|---|
| A. Corrective 0.2.1 ? | Oui |
| B. FD-FORGE-004 inclus ? | Oui (`9f4fb21`) |
| C. FD-EDITOR-008 sélectionné ? | Oui, après audit du diff : `e6c6017` |
| D. FD-ACC-002 sélectionné ? | Oui, après audit du diff : `4ae645d` |
| E. FD-STABILISATION-001 intégré ? | **Non** : il ne touche que des preuves non versionnées |
| F. Un commit par responsabilité ? | Oui : quatre commits |
| G–H. Acceptance complète, deux passes ? | Oui ; résultats déterministes identiques |
| I. Fixture sans `bootstrap.py` ? | Oui : `A-no-bootstrap` |
| J–K. Wheel + sdist, installations réelles ? | Oui |
| L. Circuit + Flowchart ? | Oui, 0.1.0, sans modification |
| M. SéquenCiel ouvert réellement ? | Non |
| N. Sonde statique SéquenCiel ? | Oui : `valid True` |
| O. Tag, push, PyPI ? | Non |
| P. Verdict | **RELEASE_READY** |

## État Git initial

| Élément | Valeur |
|---|---|
| Branche | `main` |
| HEAD | `9f4fb21` (FD-FORGE-004) |
| `origin/main` | `e411d0c` ; 0 commit en retard, 15 en avance |
| Index | Vide |
| Statut | 11 fichiers modifiés et 16 entrées non suivies, soit 593 fichiers avec `--untracked-files=all` |
| Worktrees | Le dépôt principal, plus `tmp/fd-audit-002/wt` resté de FD-AUDIT-002 |
| Espace disque | `/` : **350 Mo libres** ; `/tmp` : 632 Mo |

J'ai d'abord retiré mes propres restes de FD-AUDIT-002 : le worktree, plus
`tmp/fda2d` et `tmp/fda2e`, soit environ 157 Mo. Rien d'autre n'a été supprimé.
En particulier, les caches `~/.cache/forge-pytest-tmp` (4,3 Go) et
`~/.cache/forge-tmp` (1,7 Go) ainsi que les dossiers `/tmp/sequenciel-*`
appartiennent à d'autres projets et n'ont pas été touchés.

## Collision / proposition existante

`find -iname '*FD-RELEASE-003*'` trouve un seul fichier :
`docs/rapports/FD-RELEASE-003-PROPOSITION.md`. C'est une **proposition non
exécutée**, rédigée pendant FD-STABILISATION-001 (« aucune étape de ce ticket n'a
été commencée »). Les autres mentions sont des recommandations, dans la roadmap,
FD-AUDIT-002, FD-STABILISATION-001 et FD-FORGE-004.

Il n'existe donc aucun rapport exécuté sous cet identifiant. La proposition est
classée comme **historique** : je l'ai lue, elle reste non suivie et n'est pas
committée. Ses exigences (sélection explicite, aucune inclusion implicite, roue
reliée au jalon) sont couvertes par le présent ticket.

## Baseline de départ

`9f4fb21`, qui contient FD-RELEASE-002 (`7805152`), FD-AUDIT-002 (`909ceca`) et
FD-FORGE-004 (`9f4fb21`).

## Inventaire du travail concurrent

Avant toute indexation, les 593 entrées hors commit se répartissaient en cinq
groupes :

- les 11 fichiers suivis modifiés : 8 pour 008, 2 pour ACC-002, et `FD-CONTRACT-001.md`, modifié par l'utilisateur ;
- 5 fichiers de code ou de test non suivis ;
- 6 rapports ;
- 571 fichiers de preuves, dans cinq dossiers ;
- aucun autre fichier.

## Manifest FD-EDITOR-008

| Fichier | Statut Git initial | Responsabilité | Qualification existante | Dans 0.2.1 |
|---|---|---|---|---|
| `forge_design/design/locking.py` | non suivi | Protocole `flock`, nom stable, métadonnées sûres, montage ext4/tmpfs, délai 5 s | Empreinte = `qualified-files.json` | **Oui** |
| `forge_design/design/io.py` | modifié | `design_mutation` ; `write_design` sous verrou, API inchangée ; distinction après publication | Empreinte identique | **Oui** |
| `forge_design/web/editor.py` | modifié | Verrou pris avant la lecture décisionnelle et tenu jusqu'à la publication ; 409, 503, 500 | Empreinte identique | **Oui** |
| `tests/test_design_locking.py`, `tests/test_design_concurrency.py` | non suivis | Pannes, refus, héritage ; courses | Empreinte identique | **Oui** |
| `tests/test_design_io.py`, `tests/test_web_editor.py`, `tests/test_web_editor_revision.py` | modifiés | Assertions adaptées et durcies (exactement 303/409) | Empreinte identique | **Oui** |
| `scripts/acceptance/run.sh` | modifié | Seul chemin de verrou autorisé dans B-write | Version qualifiée = `561ff93` + ce même hunk (vérifié) ; le reste vient de FD-REALPREVIEW-007 | **Oui** |
| `docs/design/design-json.md`, `docs/editor/structural-editor.md` | modifiés | Contrat et limites du verrou | Empreinte identique | **Oui** |
| `docs/rapports/FD-EDITOR-008-RAPPORT.md` | non suivi | Rapport du ticket | — | **Oui**, inchangé |
| `docs/rapports/fd-editor-008/` (29 fichiers) | non suivis | Preuves | — | **Non** |

L'audit du diff confirme la responsabilité annoncée : **rendre exclusif le cycle
contrôler → publier de `write_design`**.

- La signature publique est inchangée.
- Une divergence observée après publication devient « sauvegarde incertaine »
  (500), et non un faux 409.
- `write_specialized_resource`, les actions de modules, l'historique et `NodePath`
  ne sont pas touchés (§15–16).

## Manifest FD-ACC-002

| Fichier | Statut Git initial | Responsabilité | Qualification existante | Dans 0.2.1 |
|---|---|---|---|---|
| `forge_design/forge/optin_routes.py` | non suivi | Détection AST du registre vide conventionnel, sans import ; lecture bornée, `O_NOFOLLOW` | 37 tests, suite complète ; aucune empreinte archivée | **Oui** |
| `forge_design/forge/routes.py` | modifié | N'omet que l'appel prouvé vide ; avertissement si le branchement est non résolu | Empreinte = `preservation.json` (vérifiée) | **Oui** |
| `tests/test_optin_routes.py` | non suivi | Nominal, câblage manquant ou ambigu, registre actif, code hostile | Aucune empreinte archivée | **Oui** |
| `docs/tools/route-explorer.md` | modifié | Limite du lecteur | Empreinte = `preservation.json` (vérifiée) | **Oui** |
| `docs/rapports/FD-ACC-002-RAPPORT.md` | non suivi | Rapport du ticket, cité par `route-explorer.md` | — | **Oui**, inchangé |
| `docs/rapports/fd-acc-002/` (37 fichiers) | non suivis | Preuves | — | **Non** |

La correction ne fait que reconnaître le registre **vide**. Un registre actif,
comme celui de SéquenCiel, reste signalé (§19).

Les deux nouveaux fichiers n'ont pas d'empreinte archivée. Leurs dates de
modification (15/10, 20:16 et 20:19) précèdent le rapport ACC-002 (20:23), et ils
sont requalifiés ici : suite complète, acceptance, mutation.

## Manifest FD-STABILISATION-001

| Fichier | Statut Git initial | Responsabilité | Qualification existante | Dans 0.2.1 |
|---|---|---|---|---|
| 7 scripts sous `fd-editor-007-verification/` et `fd-editor-008/` | non suivis | Lint des scripts de preuve (28 diagnostics) | AST des corps identiques, rejeux | **Non** : ce sont des preuves |
| `FD-STABILISATION-001-RAPPORT.md` | non suivi | Rapport du ticket | — | **Non** |
| `docs/rapports/fd-stabilisation-001/` (106 fichiers) | non suivis | Preuves | — | **Non** |

**Décision : hors release.** Le ticket ne modifie aucun fichier produit ni
versionné. Sur l'arbre versionné, `ruff check .` vaut 0 sans lui, dans le worktree
propre (§74–75) : il n'est donc pas nécessaire au contrat de lint de la release.

Autres éléments laissés hors commit :

- `FD-ACCEPTANCE-001-REQUALIFICATION-RAPPORT.md` et ses 381 preuves ;
- `FD-EDITOR-007-VERIFICATION.md` et ses 18 preuves ;
- `FD-RELEASE-003-PROPOSITION.md` ;
- `FD-CONTRACT-001.md`, modifié par l'utilisateur et préservé.

## Sélection Git

- **Aucun `git add .` ni `-A`.** Chaque commit a reçu une liste explicite de
  chemins, vérifiée avec `git diff --cached --stat`, l'index étant vide au départ.
- Pas de stash, reset, clean ni checkout destructif. Aucune preuve n'a été supprimée.
- Les commits produit ne contiennent **aucun fichier de preuve**, conformément au
  contrat historique : `git ls-files docs/rapports` ne contient que 140 rapports
  Markdown à plat, sans aucun sous-dossier.
- Les rapports 008 et ACC-002 sont committés **tels quels**. Leurs liens vers les
  dossiers de preuves pointent vers des fichiers restés locaux, comme les
  `results/` non versionnés de FD-ACCEPTANCE-002.

## Commits intégrés

| Commit | Message | Fichiers |
|---|---|---|
| `9f4fb21` | `fix: accepter les projets Forge sans bootstrap.py (FD-FORGE-004)` | Déjà présent |
| `e6c6017` | `fix: sérialiser les mutations concurrentes de designs (FD-EDITOR-008)` | 12 |
| `4ae645d` | `fix: reconnaître le registre d'opt-ins vide du squelette (FD-ACC-002)` | 5 |
| `98bbdb8` | `build: passer à 0.2.1 et qualifier un projet sans bootstrap.py (FD-RELEASE-003)` | 7 : version, trois assertions de version, fixture et étapes du kit |
| Commit final | `release: qualifier Forge Design 0.2.1 (FD-RELEASE-003)` | Ce rapport et la roadmap |

`98bbdb8` remplace un premier `3b797e7`, local et non poussé, que j'ai amendé. La
suite complète avait révélé une assertion de version oubliée dans
`test_module_version_compatibility.py` (`__version__ == "0.2.0"` et le message
« version installée : 0.2.0. »). Je l'ai remplacée par la valeur exacte 0.2.1, sans
l'affaiblir. Toute la qualification porte sur `98bbdb8`.

## Version 0.2.1

| Source | Valeur |
|---|---|
| `forge_design.__version__` (source unique) | `0.2.1` |
| `pyproject.toml` | `dynamic = ["version"]`, inchangé |
| METADATA de la roue | `Version: 0.2.1` |
| PKG-INFO du sdist | `Version: 0.2.1` |
| `forge-design --version` (venv roue et venv sdist) | `Forge Design 0.2.1` |
| Démarrage installé | `Forge Design 0.2.1` / `http://127.0.0.1:8765/` |

C'est une version CORRECTIVE (PATCH), conforme à `docs/release/versioning.md` :
correction compatible, sans capacité publique nouvelle.

Le `.venv` de développement, éditable, a été réinstallé en mode `compat`, hors
ligne, pour que sa métadonnée passe à 0.2.1. Il n'y a pas de `build/` résiduel.
Les venvs de développement de Circuit et Flowchart n'ont pas été touchés : ils
conservent la métadonnée 0.2.0, ce qui satisfait toujours `>=0.2.0,<1`.

## Contrat de compatibilité

- `MODULE_API_VERSION = 1`, `SUPPORTED_MODULE_API_VERSIONS = {1}` : inchangés.
- Circuit 0.1.0 et Flowchart 0.1.0 déclarent `forge-design>=0.2.0,<1`, dans
  `Requires-Dist` comme dans leur descripteur. La 0.2.1 est **acceptée sans
  modification des modules** : `pip check` passe et les deux modules s'activent
  dans les deux passes et dans le smoke.
- Les dépôts des modules restent à `967b5b3` et `a8ec22d`, avec 0 changement avant
  comme après.

## Fixture sans bootstrap.py

`scripts/acceptance/build_projects.py` construit un nouveau projet,
**`A-no-bootstrap`** : c'est A (squelette Forge réel avec contacts, journal vide),
sans `bootstrap.py` et **sans `.venv`**. Il n'est jamais exécuté (§36) et coûte
environ 0,6 Mo au lieu d'environ 25 Mo.

Les instantanés du kit parcourent tous les projets : il est donc couvert
automatiquement, avant et après chaque navigateur.

Nouvelles étapes, ajoutées sans modifier les étapes historiques :

- navigateur : « ACC-002 : squelette A à registre d'opt-ins vide → Routes OK » ;
- navigateur : « FD-FORGE-004 : A-no-bootstrap reconnu, Structure OK, analyses
  statiques disponibles ». Elle vérifie la synthèse, l'absence du texte
  « bootstrap.py : absent. », l'information `bootstrap.py`, et que Routes, Entités,
  Templates et Diagnostics ne sont jamais indisponibles. Elle parcourt aussi les
  pages `/routes`, `/entities`, `/templates` et `/debug` ;
- sans JavaScript : « A-no-bootstrap reconnu sans bootstrap.py, Structure et
  Routes OK ».

Validation à blanc avant l'acceptance : A et A-no-bootstrap, construits depuis le
squelette rc9 installé, sont OK dans les 9 sections.

## FD-FORGE-004

`A-no-bootstrap` est reconnu dans les deux navigateurs, les deux passes, sans
JavaScript et dans le smoke installé : Structure OK, `bootstrap.py` affiché comme
« Élément optionnel absent. », 9 sections OK.

Mutation : rendre `bootstrap.py` à nouveau obligatoire est tué (voir Mutations
ciblées).

## FD-EDITOR-008

Le code intégré est celui qui avait été qualifié (empreintes). Il est requalifié
en combinaison :

- suite complète ;
- acceptance : 10 actions, ACC-004, instantané de B-write avec le verrou attendu ;
- smoke : verrou créé, vide, en mode 0600 ;
- course sur la roue installée ;
- mutations.

L'acceptance n'ajoute pas de course navigateur (§42) : la garantie de concurrence
reste portée par les tests Python et processus dédiés, et par la course sur
l'artefact.

## FD-ACC-002

Le squelette nominal A est désormais **OK dans les 9 sections**, Routes compris.
C'était « ! Attention » dans FD-ACCEPTANCE-002. C'est vérifié par la nouvelle
étape, dans les deux navigateurs et les deux passes, sans JavaScript (A-no-bootstrap)
et dans le smoke installé.

B et C gardent leurs erreurs de fixture : leurs étapes historiques sont inchangées
et vertes.

## Acceptance passe 1

Kit du commit `98bbdb8` lancé tel quel depuis le worktree propre :

```bash
env -u ONLY PYTHON=/usr/bin/python3 CIRCUIT_REPO=… FLOWCHART_REPO=… \
  <worktree>/scripts/acceptance/run.sh /tmp/fd-release-003-20261016/pass1
```

Toutes les étapes ont été jouées, sans `ONLY`, et le code de sortie est 0.

| Contrôle | Résultat |
|---|---|
| Roue du kit | 168 fichiers, 34 ressources contrôlées, aucun manquant ni interdit |
| `pip check` / version | No broken requirements found / `Forge Design 0.2.1` |
| Démarrage depuis `/tmp`, HOME, A | Aucun projet implicite |
| Écoute | `127.0.0.1:8765` uniquement |
| Garde Host et Origin | 200 / 400 (localhost) / 400 (étranger, rebinding) / 403 ×3 |
| Chromium | **31/31** (29 historiques + 2 nouvelles) |
| Firefox | **31/31** |
| Sans JavaScript | **11/11** (10 historiques + 1 nouvelle) |
| Instantanés | 11 projets conformes par navigateur |
| Ctrl+C, preview active | Enfant `-I -B -u`, trois ports loopback, aucun processus restant, A-preview conforme |
| Endurance | 52 196 → 54 080 Kio (+1 884), aucun enfant |

Le worktree est resté propre pendant toute la passe, et les dépôts des modules à
0 changement.

## Acceptance passe 2

Dossier neuf : seuls les `results/` de la passe 1 ont été conservés. Les résultats
déterministes sont **identiques** à ceux de la passe 1 : étapes, instantanés, roue,
garde, écoute, `pip check`, version, paquets installés.

Seules varient les grandeurs non déterministes :

- PID et ports de la preview ;
- mémoire : 52 336 → 54 180 Kio ;
- durées : `doctor` 134 ms, `audit` 106 ms, `check` 123 ms.

## Chromium

31/31 dans les deux passes, CSP sans violation sur les pages de Forge Design.

| Mesure | Valeur |
|---|---|
| Requêtes | 644 par passe (610 en FD-ACCEPTANCE-002, avant les nouvelles étapes), toutes vers `127.0.0.1` |
| Graphe des routes B | 22 nœuds |
| Délai dépassé | 10,12 s, puis 10,15 s |
| Focus visible | Oui |

## Firefox

31/31 dans les deux passes.

| Mesure | Valeur |
|---|---|
| Requêtes | 841 par passe (799 auparavant) |
| Délai dépassé | 10,12 s, puis 10,12 s |
| Focus | Non vérifiable en headless (limite connue) |

Seules les polices externes du squelette sont bloquées dans l'iframe de preview,
par la CSP : c'est attendu.

## Sans JavaScript

11/11 dans les deux passes, dont la nouvelle étape `A-no-bootstrap`. Les étapes
d'éditeur (vue périmée, racine, rechargement, formulaire natif) passent.

## Circuit

Activé et qualifié dans les deux passes : ressource `demo.circuit.json`,
composant déplacé, écriture attendue dans B-write, aucun asset Flowchart chargé.
Dans le smoke : pages 200, assets isolés et servis.

## Flowchart

Activé et qualifié dans les deux passes : ressource `simple.flow.json`, nœud et
arête renommés, écriture attendue, aucun asset Circuit chargé. L'historique des
modules compte 3 lignes. Dans le smoke : pages 200, assets isolés.

## ACC-004

Scénario « deux onglets » dans les deux navigateurs, les deux passes et sans
JavaScript : la vue périmée reçoit **409**, avec le message attendu.

L'état final est `["table", "section"]`, celui laissé par l'autre onglet, sans
mauvaise écriture. Après rechargement, une action valide est acceptée.

Dans le smoke installé : B enregistre (303), A périmée reçoit 409, le fichier est
identique octet pour octet à l'état laissé par B, puis l'action valide donne 303.

## ACC-003

A-preview est conforme dans les instantanés des deux navigateurs et autour du
Ctrl+C, dans les deux passes : aucun `__pycache__` ni mtime modifié.

L'enfant est lancé avec `…/A-preview/.venv/bin/python -I -B -u …/site-packages/forge_design/real_preview/child_bootstrap.py`.
Le GET de l'iframe donne 200 (1 531 octets).

Dans le smoke installé : start, iframe sur une origine loopback dédiée à 200,
enfant `-I -B -u`, stop, proxy fermé, aucun enfant, A-preview identique.

## Concurrence write_design

Course réelle entre deux processus `spawn`, exécutée avec le **paquet installé
depuis la roue 0.2.1**, sans `PYTHONPATH` et en `python -I`.

Déroulé de chaque essai : les deux processus lisent la même révision, préparent
deux contenus distincts (`section` et `table`), se synchronisent sur une barrière,
puis appellent `write_design`.

| Version | ext4 | tmpfs |
|---|---|---|
| **0.2.1** (roue installée) | **50/50** : une écriture, un conflit, fichier final = gagnant | **50/50** |
| 0.2.0 (roue FD-RELEASE-002, témoin) | 50/50 | **43/50** : 7 essais donnent une écriture et un `DesignWriteError` « Sauvegarde impossible » chez l'autre |

Le témoin 0.2.0 montre que la course est **discriminante sur tmpfs**. Sur ext4,
la 0.2.0 n'a pas été prise en défaut en 50 essais : je ne revendique pas de
discrimination sur ce stockage.

La garantie ext4 repose sur les 600 courses de FD-EDITOR-008 (forcées par
barrière avant acquisition) et sur la suite, où ces tests sont tous verts.

Une première exécution du témoin était invalide, et c'est ma faute : le projet de
course n'avait pas de `bootstrap.py`. La 0.2.0 le refusait donc, et un processus
attendait indéfiniment à la barrière. J'ai arrêté ce contrôle, ajouté
`bootstrap.py`, rendu la barrière interruptible, puis rejoué les deux versions.

## Build wheel

Chaîne : venv de build dédié, Python 3.13.5, setuptools 84.0.0, build 1.6.1,
installés hors ligne. C'est la même chaîne que FD-RELEASE-002.

Source : `git archive 98bbdb8`, extrait dans un dossier neuf pour chaque build,
donc sans aucun fichier non suivi. Commande :
`python -m build --no-isolation --outdir buildN srcN`.

Le résultat, `forge_design-0.2.1-py3-none-any.whl`, compte **168 fichiers** :

- 163 fichiers sous `forge_design/` (les 161 de la 0.2.0, plus `locking.py` et `optin_routes.py`) ;
- 5 fichiers sous `dist-info`.

L'avertissement de setuptools 84 est le même qu'en 0.2.0 : `web.static`,
`web.static.graphics` et `web.templates` sont absents de `packages`. Il n'est
**pas corrigé** (§60) ; toutes les ressources sont présentes.

## Build sdist

`forge_design-0.2.1.tar.gz` : 316 membres.

- 308 membres suivis par Git : `forge_design/`, `tests/`, `pyproject.toml`, `README.md` ;
- 8 métadonnées générées : `PKG-INFO`, `setup.cfg`, `egg-info`.

Ni `docs/`, ni `scripts/`, ni fixtures.

## Reproductibilité

| Contrôle | Résultat |
|---|---|
| Wheel : liste et contenu des 168 membres | Identiques |
| sdist : liste et contenu des 316 membres | Identiques |
| SHA-256 de la wheel | **Identique entre build1 et build2** : `8f4167c9…a9da` |
| SHA-256 du sdist | Différent (horodatage gzip) ; contenu identique |

La roue est reproductible octet pour octet, parce que l'export Git fixe les dates
des fichiers. C'est mieux qu'en 0.2.0, où les archives différaient.

## Identité avec Git

| Contrôle | Résultat |
|---|---|
| Wheel `forge_design/*` vs `git ls-tree -r 98bbdb8 forge_design` | **163/163** identiques ; aucun fichier en plus, en moins ou différent |
| sdist : membres présents dans Git | 308/308 identiques ; aucun fichier `forge_design/` manquant |
| `locking.py`, `optin_routes.py` | Présents dans Git, la wheel et le sdist |
| `revision_tokens.py`, `child_bootstrap.py`, `py.typed` | Présents |

## Ressources

32 ressources attendues, calculées depuis le dépôt (16 gabarits, 14 statiques,
2 schémas) : **0 manquante** dans la wheel comme dans le sdist. Avec `py.typed` et
`child_bootstrap.py`, cela fait les 34 ressources contrôlées par le kit.

## Exclusions

- **Wheel** : aucun fichier de `tests/`, `docs/`, `scripts/`, rapports ou fixtures,
  aucun `__pycache__`, `.pyc`, `.venv`, `storage/`, `.forge-design`, `secrets`, ni
  module Circuit ou Flowchart.
- **Secrets synthétiques** du kit : aucune occurrence dans la wheel ni dans le sdist.
- **Chemins absolus** : ce sont les mêmes classements qu'en 0.2.0.
  - `/home/roger` n'apparaît que dans `tests/test_entity_source.py`, en entrée hostile refusée ;
  - `/.venv/` n'apparaît que dans des docstrings décrivant un motif relatif ;
  - aucun chemin de scratchpad ou de build.
- **Contamination** : aucun fichier non suivi n'est entré, puisque la source vient
  de `git archive` et que l'identité est de 163/163.

## Installation wheel

Venv neuf, installation hors ligne (`--no-index`) depuis la roue de build1 et les
dépendances téléchargées par le kit :

- `pip check` : OK ;
- `forge-design --version` : `Forge Design 0.2.1` ; `--help` : OK ;
- le code chargé vient de `site-packages`.

Ajout de `forge-design-circuit` et `forge-design-flowchart` 0.1.0 dans le même
venv : `pip check` OK. Paquets installés : forge-design 0.2.1, Circuit 0.1.0,
Flowchart 0.1.0, forge-mvc 1.0.0rc9, Jinja2 3.1.6, pydantic 2.14.1.

## Installation sdist

Second venv neuf, installation hors ligne du sdist, avec setuptools 84.0.0 local
comme backend : `pip check` OK, `Forge Design 0.2.1`.

Les fichiers installés depuis la roue et depuis le sdist sont **identiques** :
163/163 (`__pycache__` exclus).

## Smoke utilisateur

**86/86 contrôles**, réalisés avec les artefacts installés : la roue, Circuit et
Flowchart, avec un serveur lancé depuis `/tmp`, HOME isolé et environnement minimal.
Les projets sont construits à neuf par le kit du commit.

Le script est adapté de celui de FD-RELEASE-002 (lu en entier avant usage) :
version 0.2.1, fixture A-no-bootstrap, ACC-002, verrou attendu.

| Bloc | Contrôles |
|---|---|
| Démarrage depuis `/tmp`, un dossier quelconque et la racine de A | Sortie CLI 0.2.1, aucun projet implicite, écoute `127.0.0.1:8765` seule, Ctrl+C code 0, aucun processus restant |
| Sécurité | Host `127.0.0.1` 200 ; `localhost` 400 ; étranger et rebinding 400 ; POST étranger, sans Origin ou cross-site 403 |
| Parcours A | Ouverture ; `/inspector`, `/routes`, `/entities`, `/templates`, `/debug` à 200 avec leur contenu ; Routes OK (ACC-002) ; fermeture |

## Smoke sans bootstrap

Avec l'artefact installé, sur A-no-bootstrap :

- `bootstrap.py` absent de la fixture ;
- ouverture, synthèse « A-no-bootstrap », Structure OK ;
- « Information : Élément optionnel absent. `bootstrap.py` » affiché, sans le texte « bootstrap.py : absent. » ;
- `/routes`, `/entities`, `/templates` et `/debug` analysables ;
- fermeture.

## Smoke modules

- Démarrage avec `--module forge_design_circuit --module forge_design_flowchart`.
- Navigation vers Circuit et Flowchart, pages de modules à 200.
- Isolation des assets : chaque page ne référence que les assets de son propre
  module, tous servis à 200.
- **5 Tools** avec les modules actifs : `project-inspector`, `route-explorer`,
  `entity-explorer`, `debug-center`, `template-viewer`.

## Smoke éditeur

- ACC-004 : 303, puis **409** pour la vue périmée, aucune écriture, 303 après rechargement.
- Verrou de FD-EDITOR-008 : `.forge-design/locks/design-<sha256>.lock` créé, vide, en mode 0600.

## Smoke preview

ACC-003 : start (303), iframe sur une origine loopback dédiée, GET de l'iframe à
200, enfant `-I -B -u`, stop (303), proxy fermé, aucun enfant, A-preview
**identique** (aucun `__pycache__`).

Commandes runtime sur A : `doctor`, `audit` et `check` réussis, aucun enfant restant.
Sur C-check : sortie masquée (`DB_PASSWORD=[masqué]`), sentinelle écrite par le
code applicatif.

Écritures, seules celles attendues :

- B-write : le design, `.forge-design/` et `.forge-design/locks/`, et le fichier de verrou ;
- C-check : `CONTROLLER_IMPORTED`.

Les 11 instantanés sont conformes.

## Suite complète

Dans le worktree propre du commit `98bbdb8`, avec le `.venv` principal et
`PYTHONPATH=<worktree>` :

| Commande | Résultat |
|---|---|
| `python -m compileall -q forge_design tests` | OK |
| `ruff check .` (arbre versionné entier) | All checks passed |
| `ruff format --check .` | 456 fichiers déjà formatés |
| `pyright` (strict) | 0 erreur, 0 avertissement |
| `git diff --check 4ae645d HEAD` | OK |
| `pytest` | **5 196 réussis**, 161,03 s |
| `node --test tests/js/graphics/*.test.mjs` | 134/134 |
| `node --check` des scénarios, `bash -n run.sh` | OK |

La première exécution, sur `3b797e7`, avait donné 1 échec (l'assertion de version
oubliée). Elle est corrigée par l'amendement décrit plus haut.

## Mutations ciblées

Chaque mutant est appliqué sur une copie de `forge_design/` du commit, chargée par
`PYTHONPATH`. Le worktree n'est jamais modifié. Un témoin non muté passe d'abord :
**173 réussites**.

| Mutant | Résultat | Preuve |
|---|---|---|
| `bootstrap.py` redevient obligatoire (FD-FORGE-004) | Tué | `test_required` : `assert 2 == 1` |
| Verrou supprimé de `design_mutation` (FD-EDITOR-008) | Tué | 28 échecs, dont les 12 cellules de course (threads et processus, ext4 et tmpfs), le délai 503 et la sonde « même verrou » |
| Verrou ignoré par l'action Web (FD-EDITOR-008) | Tué | 9 échecs, dont les courses Web/Web et Web/API ; la course API/API reste verte, ce qui est cohérent |
| Registre vide à nouveau signalé (FD-ACC-002) | Tué | `test_optin_routes` : `assert 2 == 1` |

**4 mutants sur 4 tués.**

Mon harnais avait d'abord classé le mutant « verrou supprimé » comme survivant.
Sa règle anti-faux-positif confondait un vrai `FileNotFoundError`, venu du
`tmp_path` d'un test qui attend le fichier de verrou, avec une erreur de
`--basetemp`. Un rejeu sans `-x` a listé les 28 échecs réels.

## Sonde statique SéquenCiel

Une seule sonde, à la fin, avec l'**artefact 0.2.1 installé** (`python -I`, venv
de la roue) :

```text
detect_forge_project('/home/roger/Projets/SequenCiel')
valid True  errors ()  warnings ()
bootstrap.py : absent, required=False, strict=True
```

Avant et après la sonde, j'ai relevé l'empreinte de `git status`, le nombre de
lignes de statut (4), HEAD (`008a895e`), ainsi que les mtimes et tailles de la
racine, de `app.py`, `config.py`, `mvc/`, `mvc/routes/` et `mvc/routes/__init__.py`.
Les relevés sont **identiques**.

Rien d'autre n'a été fait sur SéquenCiel : ni navigateur, ni `doctor`, `audit` ou
`check`, ni preview, ni éditeur, ni base.

## Limites restantes

- **Registre d'opt-ins actif** : Routes devrait être en « Attention » sur
  SéquenCiel. C'est une limite connue et assumée.
- **Verrou** : protocole consultatif (`flock`), Linux uniquement, ext4 et tmpfs
  locaux ; un écrivain externe qui l'ignore n'est pas sérialisé. SéquenCiel est sur
  ext4 (vérifié par `findmnt`).
- **`write_specialized_resource`** (actions de modules) : course plausible, non
  reproduite, non traitée (§16). Le serveur mono-thread l'atténue.
- **Packaging** : l'avertissement setuptools reste ouvert ; pas de matrice Python
  (seul 3.13.5 a été testé) ; pas de licence (dette de diffusion publique, §80).
- **Non qualifiés** : preview réelle, `doctor`, `audit` et `check` sur un `app.py`
  antérieur au câblage (Forge 1.0.0-rc.3, cas de SéquenCiel). C'est l'objet de
  l'essai réel.
- **Firefox headless** : focus visible non vérifiable (limite connue). Le kit ne
  rejoue ni la création de connexions Circuit ni la sélection d'un nœud de flux.
- **Artefacts** : conservés dans `tmp/fd-release-003-dist/` (ignoré par Git, sur
  ext4), avec `SHA256SUMS`. Ils ne sont pas versionnés ni publiés.
- **Disque** : `/` est à 100 % (environ 0,5 Gio libre) et `/tmp` à 96 % en fin de
  ticket, ce qui est un risque pour les campagnes suivantes.
- **Mesures** : `/inspector` sur D à environ 195 ms (175 ms en FD-ACCEPTANCE-002),
  les autres pages au même niveau. C'est observé, sans seuil défini ; ce n'est pas
  une régression qualifiée.

## Verdict release

**RELEASE_READY**

Chacune des conditions du §86 est démontrée :

| Condition | Constat |
|---|---|
| Travaux intégrés proprement | Un commit par responsabilité, sélection explicite, aucune preuve, travail utilisateur préservé |
| Version 0.2.1 cohérente | 6 sources concordantes |
| Suite verte | 5 196 tests, Pyright 0, Ruff, format |
| Acceptance complète verte | Deux passes, Chromium et Firefox 31/31, sans JavaScript 11/11 |
| Reproductible | Résultats déterministes identiques ; roue identique octet pour octet |
| Wheel et sdist propres | 163/163 identiques à Git, ressources complètes, aucune exclusion violée |
| Installations réelles | Wheel, sdist, wheel + modules : `pip check` OK |
| Projet sans `bootstrap.py` reconnu | Acceptance, sans JavaScript, smoke |
| ACC-004 non régressé | 409 sans écriture |
| ACC-003 non régressé | Aucun bytecode |
| Concurrence 008 validée | Suite, mutations, course 100/100 sur l'artefact |
| ACC-002 conforme | A en Routes OK |
| Modules compatibles | Activés sans modification |

Le verdict découle des résultats. Rien n'a été affaibli pour l'obtenir : les seules
assertions modifiées sont les valeurs de version, remplacées par 0.2.1.

## SéquenCiel readiness

**SéquenCiel readiness: READY_FOR_FD-SEQUENCIEL-001**

La cause de refus identifiée par FD-AUDIT-002 est levée dans une release
qualifiée : la détection statique de SéquenCiel donne `valid True` avec l'artefact
installé.

L'essai réel n'a pas encore eu lieu. D'autres écarts restent possibles et seront
mesurés par FD-SEQUENCIEL-001 : registre actif, `app.py` ancien, volume.

## Recommandation ticket suivant

**FD-SEQUENCIEL-001** : premier essai réel de Forge Design 0.2.1 sur SéquenCiel,
installé depuis `tmp/fd-release-003-dist/` (SHA-256 consignés).

Il devrait commencer par une phase en lecture seule (Inspector, Routes, Entités,
Templates, Debug), avec des instantanés de SéquenCiel avant et après. Les commandes
qui exécutent du code projet, la preview et l'éditeur devraient chacun faire
l'objet d'une autorisation explicite.

## Release notes

### Forge Design 0.2.1

Version corrective de la 0.2.0. Elle n'apporte **aucune nouvelle fonctionnalité**.

- **Projet Forge sans `bootstrap.py` accepté** (FD-FORGE-004). Comme pour
  forge-mvc 1.0.0rc9, ce fichier est optionnel ; un `bootstrap.py` présent mais
  invalide (lien, dossier) reste refusé.
- **Concurrence de `write_design` renforcée** (FD-EDITOR-008). Les éditions Web et
  l'API publique sont sérialisées par un verrou interprocessus par design
  (`.forge-design/locks/`) :
  - une seule publication par révision ;
  - 409 pour une vue périmée, 503 si le verrou n'est pas obtenu en 5 s ;
  - Linux, ext4 ou tmpfs.
- **Registre d'opt-ins vide reconnu** (FD-ACC-002). Le squelette Forge nominal
  n'affiche plus « Routes — Attention » à cause de `register_optins(router)` ; un
  registre actif reste signalé.
- Les modules Circuit 0.1.0 et Flowchart 0.1.0 (`forge-design>=0.2.0,<1`) sont
  compatibles sans modification. `MODULE_API_VERSION` reste 1.

| Artefact | SHA-256 |
|---|---|
| `forge_design-0.2.1-py3-none-any.whl` | `8f4167c92567964ac5663cc0720bd338675ecf0ba7d8eb850608da78ce91a9da` |
| `forge_design-0.2.1.tar.gz` (build1) | `0072743d19c20c251ffc5507d275098e05a13255b87752e9768d0e97cf206f95` |
| `forge_design_circuit-0.1.0-py3-none-any.whl` (qualifiée avec) | `db4e6b53ca4fa68d94b84a17ea947c1c9d86f77ea8e04a1455af56bcdf8c8679` |
| `forge_design_flowchart-0.1.0-py3-none-any.whl` (qualifiée avec) | `42cae10ba6c8c47b19beffc7d5d075d8add57badaec994928d6cb96c514c9b10` |

Les roues des modules, reconstruites par le kit depuis les mêmes commits, ont des
empreintes différentes de celles de FD-RELEASE-002, à cause des horodatages ZIP.

## Fichiers créés

- `docs/rapports/FD-RELEASE-003.md`
- `forge_design/design/locking.py`, `tests/test_design_locking.py`, `tests/test_design_concurrency.py`, `docs/rapports/FD-EDITOR-008-RAPPORT.md` (FD-EDITOR-008, créés précédemment et committés ici)
- `forge_design/forge/optin_routes.py`, `tests/test_optin_routes.py`, `docs/rapports/FD-ACC-002-RAPPORT.md` (FD-ACC-002, idem)

## Fichiers modifiés

- **FD-EDITOR-008** (`e6c6017`) : `io.py`, `editor.py`, trois tests, `run.sh`, `design-json.md`, `structural-editor.md`.
- **FD-ACC-002** (`4ae645d`) : `routes.py`, `route-explorer.md`.
- **Build** (`98bbdb8`) :
  - version : `forge_design/__init__.py`, `tests/test_import.py`, `tests/test_module_version_compatibility.py` ;
  - kit : `build_projects.py`, `scenario.mjs`, `nojs.mjs`, `README.md`.
- **Release** : `docs/03-roadmap.md`.

Non modifiés : les rapports FD-RELEASE-002, FD-AUDIT-002 et FD-FORGE-004, ainsi
que tous les rapports historiques ; `docs/rapports/FD-CONTRACT-001.md` ; Circuit,
Flowchart, SéquenCiel ; `pyproject.toml`.

## Validation finale

Après la rédaction de ce rapport et de la roadmap, dans le worktree, sur
exactement le contenu du commit final (des tests lisent `docs/`) :

| Commande | Résultat |
|---|---|
| `python -m compileall -q forge_design tests` | OK |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 457 fichiers déjà formatés (ce rapport compris) |
| `pyright` (strict) | 0 erreur, 0 avertissement |
| `git diff --check` | OK |
| `pytest` | **5 196 réussis**, 160,18 s |
| `node --test tests/js/graphics/*.test.mjs` | 134/134 |

## État Git final

`main` contient, au-dessus de `9f4fb21` : `e6c6017` (FD-EDITOR-008), `4ae645d`
(FD-ACC-002), `98bbdb8` (build 0.2.1) et le commit `release: qualifier Forge
Design 0.2.1 (FD-RELEASE-003)`.

Il n'y a ni tag, ni push. `origin/main` reste `e411d0c`, à 19 commits.

Restent hors commit, inchangés :

- `docs/rapports/FD-CONTRACT-001.md`, modifié par l'utilisateur ;
- 575 fichiers non suivis : 571 preuves et 4 rapports historiques ou de proposition.

La version est 0.2.1.
