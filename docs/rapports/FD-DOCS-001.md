# Rapport — FD-DOCS-001

Aligner la documentation utilisateur sur le comportement réel de Forge Design (correction d'ACC-001). Date : 2026-10-15.

## Objectif

Fermer ACC-001 (COSMETIC), dernière incohérence documentaire connue des acceptances. Une partie de la documentation active présentait `localhost` comme adresse de Forge Design, alors que le serveur refuse `Host: localhost` (400) par contrat.

La documentation s'aligne sur le produit. Le comportement de Forge Design reste la référence et n'est pas modifié : aucun fichier de `forge_design/`, aucun test.

| Décision | Résultat |
|---|---|
| A. Changement fonctionnel ? | Non |
| B. Corrige ACC-001 ? | Oui |
| C. Autoriser `localhost` ? | Non |
| D. Documenter `127.0.0.1` ? | Oui : `http://127.0.0.1:8765/` |
| E. Modifier les rapports historiques ? | Non |
| F. Corriger ACC-002 ? | Non (FD-ROUTES-022) |
| G. Modifier Circuit / Flowchart ? | Non |
| H. Ajouter MkDocs ? | Non |
| I. Le gate SéquenCiel change ? | Non : il reste **OPEN** |
| J. Prochain ticket ? | FD-RELEASE-002 |

## État Git initial

| Élément | Valeur |
|---|---|
| HEAD | `837bf1b` (FD-ACCEPTANCE-002 : ACCEPTED_WITH_MINOR_ISSUES, gate OPEN) |
| `origin/main` | `e411d0c` ; 0 commit en retard, 11 en avance |
| Collision | Aucune : FD-DOCS-001 n'apparaissait que comme recommandation (FD-ACCEPTANCE-001, FD-ACCEPTANCE-002, roadmap) |
| `docs/rapports/FD-CONTRACT-001.md` | Modifié par l'utilisateur ; préservé, hors commit |
| Version | 0.2.0 |

**Travail concurrent** (verrou de `write_design`, FD-EDITOR-008), présent sans être committé :

- `forge_design/design/io.py`, `forge_design/web/editor.py`, `forge_design/design/locking.py` ;
- `scripts/acceptance/run.sh` ;
- tests ;
- `docs/design/design-json.md`, `docs/editor/structural-editor.md` ;
- rapports et preuves de FD-EDITOR-007 et FD-EDITOR-008.

Aucun des deux documents concernés ne contient d'occurrence à corriger : ils ne sont pas touchés. Les quatre fichiers visés par ce ticket étaient identiques à HEAD au départ, et l'ont été vérifiés à nouveau juste avant l'indexation.

**Méthode.** Le `.venv` principal charge le code du dépôt principal, qui contient ce travail concurrent. Les corrections, la vérification fonctionnelle, la roue et la suite ont donc été faites dans un **worktree détaché** sur `837bf1b`, contenant uniquement les fichiers de ce ticket. `forge_design.__file__` pointe bien dans ce worktree (vérifié avant la suite).

## ACC-001

| Élément | Valeur |
|---|---|
| Sévérité | COSMETIC |
| Zone | Documentation |
| Relevé | `01-cadrage-fonctionnel.md` annonçait « écoute sur `127.0.0.1` / `localhost` par défaut » |
| Comportement qualifié (FD-ACCEPTANCE-002, deux passes) | Bind `127.0.0.1` ; `Host 127.0.0.1:8765` → 200 ; `Host localhost:8765` → 400 ; `Host` étranger → 400 |
| Risque | Un utilisateur qui tape `http://localhost:8765` reçoit une erreur 400 sans comprendre pourquoi |

## Inventaire des occurrences

La recherche a porté sur `docs/`, `README.md` et `pyproject.toml`. Les termes recherchés sont `localhost`, `127.0.0.1`, `8765`, `forge-design`, `Host`, `loopback` et les options de la CLI.

Occurrences de `localhost` **avant** correction, hors rapports :

| Fichier | Texte | Classe |
|---|---|---|
| `docs/01-cadrage-fonctionnel.md:264` | « écoute sur `127.0.0.1` / `localhost` par défaut » | **A**, incorrecte (ACC-001) |
| `README.md:104` | « l'interface loopback (`127.0.0.1` / `localhost`) » | **A**, incorrecte, non citée par ACC-001 |
| `docs/02-architecture.md:128` | « `localhost`, `[::1]` et un `Host` absent sont refusés » | B, correcte : elle décrit le refus |

Les rapports historiques contiennent 13 occurrences dans 6 fichiers (classe D).

`pyproject.toml` ne contient pas `localhost`, mais il déclare `readme = "README.md"` : le README devient la **description longue de la distribution** (`METADATA`, `pip show`, index de paquets). L'erreur du README était donc publiée avec la roue.

**Divergence connexe**, relevée en comparant les commandes documentées au produit (§29). Les lignes 66 à 77 de `docs/02-architecture.md` présentaient encore la CLI comme future : « non contractuel tant que la CLI correspondante n'est pas implémentée », « `--no-browser` pourra être étudiée ». Or FD-CLI-002 (`1641ada`) a livré `forge-design`, l'ouverture du navigateur et `--no-browser`, et `--module` existe aussi.

## Occurrences corrigées

| Fichier | Avant | Après |
|---|---|---|
| `docs/01-cadrage-fonctionnel.md` §14 | « écoute sur `127.0.0.1` / `localhost` par défaut ; » | « écoute sur `127.0.0.1` uniquement, port `8765` par défaut (`http://127.0.0.1:8765/`) ; Forge Design refuse les autres valeurs de `Host`, y compris `localhost`, conformément à sa garde locale ; » |
| `README.md`, lancement | « Forge Design écoute uniquement sur cette adresse locale. » | « … sur cette adresse locale et refuse les autres valeurs de `Host`, y compris `localhost` : utiliser `http://127.0.0.1:8765/`. » |
| `README.md`, architecture directrice | « l'interface loopback (`127.0.0.1` / `localhost`) » | « l'interface loopback (`127.0.0.1`) » |
| `docs/02-architecture.md`, comportement par défaut | Bloc de CLI « future » (12 lignes) | « La commande `forge-design` (FD-CLI-002) démarre le backend local, affiche la version et l'URL `http://127.0.0.1:8765/`, puis ouvre le navigateur par défaut ; `--no-browser` ne l'ouvre pas ; `--module PAQUET` active un module externe installé ([hôte des modules](modules/module-host.md)). » |

Pour `02-architecture.md`, le reste de la section n'est pas touché : `host = 127.0.0.1`, pas d'exposition réseau, `0.0.0.0` et l'accès distant exclus du comportement par défaut. Les explications sur le DNS, `/etc/hosts` ou IPv6 ne sont pas ajoutées (§17).

## Occurrences conservées

Inventaire **après** correction, documentation active :

| Fichier | Occurrence | Classe | Justification |
|---|---|---|---|
| `README.md:47` | « refuse les autres valeurs de `Host`, y compris `localhost` » | B | Annonce le refus : c'est la correction elle-même |
| `docs/01-cadrage-fonctionnel.md:264` | « y compris `localhost`, conformément à sa garde locale » | B | idem |
| `docs/02-architecture.md:117` (ancienne ligne 128) | « `localhost`, `[::1]` et un `Host` absent sont refusés » | B | Contrat FD-WEB-003, exact |
| `docs/03-roadmap.md:34` | « le refus de `localhost` par la garde `Host` » | B | État d'avancement de ce ticket |

Aucun document actif ne présente plus `localhost` comme adresse valide de Forge Design.

Les rapports historiques sont conservés tels quels (classe D, voir « Rapports historiques »).

Les autres `127.0.0.1` de la documentation active sont exacts :

- architecture et contrat Web ;
- `real-preview-contract.md`, avec un port dédié par preview ;
- `structural-editor.md` (CSP, garde) ;
- `debug-center.md` et `module-actions.md` (`is_local_action`) ;
- roadmap.

`docs/04-compatibilite-forge.md` décrit le serveur de **Forge MVC** (`APP_HOST`, défaut `127.0.0.1`, pas de contrôle de `Host` côté Forge) : c'est un autre contexte (B), non modifié.

## 01-cadrage-fonctionnel.md

La correction porte sur la seule ligne relevée par ACC-001, au §14 « Interface Web locale ». Elle donne l'URL à utiliser et le refus de `localhost` en une phrase. Les autres principes du §14 sont inchangés : pas d'accès direct au système de fichiers, pas d'exposition réseau implicite.

## URL utilisateur

L'URL documentée est **`http://127.0.0.1:8765/`**, celle que la CLI affiche et ouvre :

- `README.md` : section de lancement, plus la phrase de refus ;
- `docs/01-cadrage-fonctionnel.md` §14 ;
- `docs/02-architecture.md` : comportement par défaut.

Le manuel de démarrage existant a été vérifié, sans nouveau manuel (§28) :

| Étape | Document | État |
|---|---|---|
| Installation, `forge-design --version` | README | Cohérent (Forge Design 0.2.0) |
| Lancement, URL, `--no-browser`, port occupé | README | Cohérent ; URL désormais explicite |
| Arrêt par Ctrl+C | README | Cohérent : arrêt propre, code 0 (vérifié) |
| Ouverture d'un projet | `docs/tools/project-inspector.md` | Cohérent |
| `--module` | `docs/modules/module-host.md` | Cohérent ; désormais aussi cité dans l'architecture |

## Contrat Host

Le vocabulaire est cohérent entre l'architecture (FD-WEB-003), la documentation de Debug Center et celle des actions de modules :

- bind loopback IPv4 `127.0.0.1` ;
- `Host` autorisé : exactement `127.0.0.1:<port>` ;
- `localhost`, `[::1]` et un `Host` absent sont refusés.

Rien n'est modifié dans ces documents.

## Documentation Web

La section « Contrôle de l'en-tête Host (FD-WEB-003) » de `02-architecture.md` était déjà exacte : elle n'est pas modifiée. La garde d'origine (`Origin` = `http://` + Host) et `is_local_action` sont inchangés.

## Documentation architecture

Une seule modification dans `docs/02-architecture.md` : le bloc de CLI « future » est remplacé par la phrase factuelle ci-dessus (−12 lignes, +1). La séparation fondamentale n'est pas touchée : le cœur (outils Forge, moteur générique, contrat de modules) d'un côté, les modules externes Circuit et Flowchart de l'autre. Le seul ajout sur les modules dit qu'ils sont **externes** et activés explicitement par `--module`.

## Documentation Preview

Elle n'est pas modifiée. La preview réelle utilise aussi le loopback, sur un port dédié distinct du serveur. Son contrat reste exact : `python -I -B -u`, et la formulation de FD-REALPREVIEW-007 est conservée (Forge Design n'écrit plus de bytecode en démarrant la preview ; le code applicatif garde ses propres effets de bord).

## Documentation éditeur

Elle n'est pas modifiée. `docs/editor/structural-editor.md` fait d'ailleurs partie du travail concurrent. Le contrat FD-EDITOR-007 (vue périmée → 409) est inchangé. Les deux mentions de `127.0.0.1` de ce document (CSP, garde) sont exactes.

## Modules externes

Circuit et Flowchart ne sont ni modifiés ni présentés comme intégrés au cœur. Rien dans les corrections ne présente Forge Design comme un éditeur Circuit.

## Rapports historiques

Ils ne sont pas modifiés : ils restent les preuves de ce qui a été observé. Cela comprend :

- les 13 occurrences de `localhost` de `FD-ACCEPTANCE-001.md`, `FD-ACCEPTANCE-002.md`, `FD-WEB-001.md`, `FD-WEB-003.md`, `FD-REALPREVIEW-002.md` et `FD-REALPREVIEW-003.md` ;
- la mention d'ACC-001 « restant » dans FD-ACCEPTANCE-002.

## Roadmap

`docs/03-roadmap.md`, deux modifications :

- « **ACC-001 corrigé par FD-DOCS-001** », avec la portée de la correction ; seul ACC-002 (MINOR) reste ;
- prochaine étape : **FD-RELEASE-002**, dernier ticket avant le premier essai sur SéquenCiel.

## Vérification fonctionnelle

Vrai démarrage depuis le worktree, par `forge_design.cli.main(["--no-browser"])`, avec HOME isolé et cwd `/tmp` :

| Contrôle | Résultat |
|---|---|
| Code chargé | `forge_design` du worktree |
| Sortie de la CLI | `Forge Design 0.2.0`, puis `http://127.0.0.1:8765/` |
| Écoute | `127.0.0.1:8765` uniquement |
| `GET /` avec `Host: 127.0.0.1:8765` | **200** |
| `GET /` avec `Host: localhost:8765` | **400** |
| `GET /` avec `Host: evil.example` | 400 |
| Ctrl+C (SIGINT) | Arrêt propre, code de sortie 0 |

La documentation corrigée décrit donc exactement le produit. Aucun test n'a été modifié pour coller à la documentation.

**Roue et `METADATA`.** La roue est construite depuis le worktree, sans installation ni acceptance (§44) :

- `forge_design-0.2.0-py3-none-any.whl`, `Version: 0.2.0` ;
- l'ancienne formulation « `127.0.0.1` / `localhost` » est absente de la description longue ;
- `http://127.0.0.1:8765/` est présent ;
- la seule ligne contenant `localhost` est la phrase de refus.

## Tests

La suite complète est relancée dans le worktree, la documentation et la roadmap faisant partie de la baseline de release (voir Validation finale). Aucun test n'est ajouté ni modifié : le ticket ne change aucun comportement.

## Dette restante

- **ACC-002 (MINOR)** : `register_optins(router)` du squelette affiche « Routes — ! Attention ». Il relève de FD-ROUTES-022, hors chemin critique.
- **Accès hors loopback** : non documenté comme possible, et il ne l'est pas. Une éventuelle ouverture relèverait d'une conception de sécurité dédiée, comme le dit l'architecture.
- **Pas de MkDocs** : la documentation reste en Markdown simple, `git diff --check` en est le contrôle (§38-39).

## Impact sur ACC-001

**ACC-001 : CORRIGÉ.**

Toute la documentation active destinée à l'utilisateur indique l'URL réellement servie, `http://127.0.0.1:8765/`. Aucun document actif ne présente plus `localhost` comme adresse valide ; les quatre occurrences restantes annoncent son refus. Le comportement Web est inchangé et vérifié (200 / 400).

**Documentation cohérente avec le comportement livré : OUI.**

Seule anomalie connue restante : ACC-002 (MINOR). Le gate SéquenCiel reste **OPEN**.

## Recommandation ticket suivant

**FD-RELEASE-002** : clôture de la release 0.2.0, avec le durcissement de la sonde de roue recommandé par FD-ACCEPTANCE-002 (identité avec l'arbre Git, présence des modules Python attendus). C'est le dernier ticket avant le premier essai sur SéquenCiel.

Hors chemin critique : FD-ROUTES-022 (ACC-002), et le ticket du verrou de `write_design` en cours, avec sa propre requalification ciblée.

## Fichiers créés

- `docs/rapports/FD-DOCS-001.md`

## Fichiers modifiés

- `docs/01-cadrage-fonctionnel.md` : §14, URL et refus de `localhost`
- `README.md` : lancement (URL et refus), architecture directrice (`127.0.0.1`)
- `docs/02-architecture.md` : CLI réellement livrée au lieu de la CLI « future »
- `docs/03-roadmap.md` : ACC-001 corrigé, prochain ticket FD-RELEASE-002

Non modifiés :

- `forge_design/`, les tests, `scripts/` ;
- les rapports historiques ;
- la documentation de la preview, de l'éditeur, de Debug Center et des modules ;
- Circuit et Flowchart.

## Validation finale

Suite lancée dans le worktree (`837bf1b` plus ce ticket) :

| Commande | Résultat |
|---|---|
| `python -m compileall -q forge_design tests` | OK |
| `ruff check forge_design tests scripts` | All checks passed |
| `ruff format --check .` | Aucun fichier à reformater |
| `pyright` (strict) | 0 erreur, 0 avertissement |
| `git diff --check` | OK |
| `pytest` (suite complète) | 5 097 passed |
| `node --test tests/js/graphics/*.test.mjs` | 134/134 |
| `mkdocs build --strict` | Sans objet (MkDocs non configuré) |
| Liens internes modifiés | `modules/module-host.md` existe ; aucun lien cassé introduit |
| Vérification fonctionnelle | 200 / 400 / 400, URL affichée `http://127.0.0.1:8765/` |
| `METADATA` de la roue | Ancienne formulation absente, URL présente |

## État Git final

Un seul commit : `docs: aligner l'accès local sur le contrat Web (FD-DOCS-001)`, au-dessus de `837bf1b`. Il n'a pas été poussé.

Restent hors commit, sur disque :

- `docs/rapports/FD-CONTRACT-001.md`, modifié par l'utilisateur ;
- le travail concurrent (FD-EDITOR-008) ;
- les fichiers de vérification de FD-EDITOR-007.

La version reste 0.2.0.
