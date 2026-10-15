# Rapport — FD-ACCEPTANCE-002

Requalification de bout en bout de Forge Design 0.2.0 après les corrections d'ACC-004 et d'ACC-003. Ce rapport décide le gate SéquenCiel. Date : 2026-10-15.

## Objectif

Une question : Forge Design 0.2.0 est-il désormais assez stable et sûr pour être utilisé sur SéquenCiel ?

Aucune fonctionnalité n'est développée, aucun fichier de `forge_design/` n'est modifié, et SéquenCiel n'est ni ouvert ni utilisé.

| Décision | Résultat |
|---|---|
| A. Nouvelle fonctionnalité ? | Non |
| B. Acceptance complète ? | Oui : `run.sh` sans `ONLY`, toutes les étapes, deux passes |
| C. Worktree isolé ? | Oui, propre avant et après |
| D. Travail concurrent exclu ? | Oui : roue identique octet pour octet à la baseline |
| E. Roue réelle ? | Oui, installée dans un venv neuf, hors ligne |
| F. Chromium + Firefox ? | Oui : 29/29 étapes chacun, dans les deux passes |
| G. Sans JavaScript ? | Oui : 10/10 étapes, dans les deux passes |
| H. Circuit + Flowchart ? | Oui |
| I. ACC-004 rejoué ? | Oui : corrigé |
| J. ACC-003 rejoué ? | Oui : corrigé |
| K. SéquenCiel utilisé ? | Non |
| L. Gate décidé ? | Oui : **OPEN** |

## État Git initial

| Élément | Valeur |
|---|---|
| HEAD | `8ca9b72` (FD-REALPREVIEW-007) |
| `origin/main` | `e411d0c` ; 0 commit en retard, 10 en avance |
| Collision | Aucune : FD-ACCEPTANCE-002 n'apparaissait que comme recommandation |
| Dépôt principal | `docs/rapports/FD-CONTRACT-001.md` est modifié par l'utilisateur et préservé ; le travail concurrent n'est pas committé (voir plus bas) |
| Dépôts des modules | ForgeDesign-Circuit `967b5b3`, ForgeDesign-Flowchart `a8ec22d` : 0 changement avant comme après |
| Version | 0.2.0 |

## Baseline qualifiée

Le commit qualifié est `8ca9b72`. Il contient :

- `97a214a` : FD-ACCEPTANCE-001 et son kit ;
- `561ff93` : FD-EDITOR-007, qui corrige ACC-004 ;
- `8ca9b72` : FD-REALPREVIEW-007, qui corrige ACC-003.

## Isolation du worktree

La qualification part d'un worktree détaché : `git worktree add --detach <scratch>/acc2/wt 8ca9b72`.

| Moment | `git status --short --untracked-files=all` |
|---|---|
| Avant la qualification | 0 ligne |
| Après les deux passes et la suite automatique | 0 ligne, HEAD toujours `8ca9b72` |

Les seuls fichiers produits dans le worktree sont ignorés par Git :

- les caches (`__pycache__`, `.ruff_cache`) ;
- le `forge_design.egg-info` du build de la roue ;
- `storage/`, créé par un test qui fait lever un handler.

Le kit tourne depuis le worktree : son `REPO`, donc la source de la roue, est le worktree. La suite automatique utilise l'interpréteur du `.venv` principal avec `PYTHONPATH=<worktree>` ; `forge_design.__file__` pointe bien dans le worktree (vérifié). `pyright` reçoit `--pythonpath`. Aucun lien `.venv` n'est créé dans le worktree.

## Travail concurrent exclu

Sont présents dans le dépôt principal, sans être committés :

- **Fichiers modifiés** : `forge_design/design/io.py`, `forge_design/web/editor.py`, `scripts/acceptance/run.sh`, `docs/design/design-json.md`, `docs/editor/structural-editor.md` et trois tests (`test_design_io.py`, `test_web_editor.py`, `test_web_editor_revision.py`) ;
- **Fichiers non suivis** : `forge_design/design/locking.py`, `tests/test_design_concurrency.py`, `tests/test_design_locking.py`, les fichiers de vérification de FD-EDITOR-007, et `docs/rapports/FD-EDITOR-008-RAPPORT.md` avec `docs/rapports/fd-editor-008/`, apparus pendant la qualification.

Rien de tout cela n'entre dans la qualification.

**Preuve de non-contamination**, pour chacune des deux passes : chaque fichier `forge_design/*` de la roue est comparé octet pour octet (SHA-256) à `git ls-tree -r 8ca9b72 forge_design`. Ce contrôle est ponctuel, hors kit.

| Contrôle | Passe 1 | Passe 2 |
|---|---|---|
| Fichiers suivis / fichiers empaquetés | 161 / 161 | 161 / 161 |
| Dans la roue mais pas dans la baseline | aucun | aucun |
| Dans la baseline mais pas dans la roue | aucun | aucun |
| Contenu différent | aucun | aucun |
| `revision_tokens.py`, `child_bootstrap.py`, `py.typed` | présents | présents |
| `forge_design/design/locking.py` | **absent** | **absent** |
| `io.py`, `editor.py` | identiques à la baseline | identiques à la baseline |

## Kit d'acceptation

Le kit versionné `scripts/acceptance/` est utilisé tel quel, sans modification et sans procédure parallèle :

```bash
env -u ONLY PYTHON=/usr/bin/python3 CIRCUIT_REPO=… FLOWCHART_REPO=… \
  <worktree>/scripts/acceptance/run.sh <dossier neuf>
```

Étapes : `wheels install projects startup security browsers nojs measures shutdown`, toutes, sans `ONLY`.

**Deux passes complètes** ont été faites sur deux dossiers neufs (`pass1`, `pass2`) ; aucun artefact précédent n'est réutilisé. Entre les deux, seuls les artefacts lourds de la passe 1 (venvs, roues, projets) ont été supprimés ; ses `results/` sont conservés. Les deux passes donnent les mêmes résultats.

**Complément hors kit**, rejoué sur chaque passe avec la roue installée et les sondes HTTP du kit :

- causes des FAIL de `doctor` et `check` sur B et C, pour les étiqueter ;
- huit rondes d'endurance sur un même serveur, pour le plateau mémoire.

Tous les projets ont été photographiés avant et après ce complément : aucune écriture, aucun processus restant.

**Écarts de formulation entre le ticket et le kit** (documentés, le kit n'est pas modifié) :

| Point du ticket | Couverture réelle |
|---|---|
| §23 Sélection racine après le 409 | Vérifiée par l'étape sans JavaScript « vue périmée, racine et rechargement » et par pytest (`test_conflict_page_shows_current_design_root_selection_and_reload`). L'étape JavaScript vérifie le 409, le message, l'absence d'écriture et le rechargement. |
| §34 stderr partiel conservé au délai dépassé | La fixture C-timeout n'écrit que sur stdout : le navigateur vérifie stdout. stderr est couvert par pytest (`test_unbuffered_output_is_preserved_before_timeout`, sur les trois commandes). |
| §39 Instantanés avant/après | Faits autour de chaque passage navigateur et du Ctrl+C. L'étape `nojs` vérifie les processus restants mais ne compare pas d'instantanés ; ses étapes d'éditeur comparent elles-mêmes les octets du design. |
| §42 Processus « après chaque bloc critique » | `strays` (dossier courant et ligne de commande) après chaque navigateur, après l'étape sans JavaScript et après le Ctrl+C ; aucun enfant après l'endurance. Pas de contrôle après chaque étape du scénario. |

## Projets utilisés

Ce sont les projets de FD-ACCEPTANCE-001, reconstruits à neuf par `build_projects.py` avant les navigateurs et après chaque passage :

| Projet | Rôle |
|---|---|
| A | Squelette Forge réel, nominal, lecture seule |
| A-preview | Seule cible de la preview réelle |
| A-bare | États optionnels (journal et entités absents) |
| B | gx8 enrichi, hostile et problématique |
| B-write | Seule cible des écritures (éditeur, modules, rotation du journal) |
| C | Diagnostics |
| C-check | Effet de bord contrôlé de `project:check` |
| C-timeout | Délai dépassé avec `-u` |
| D | Volume |
| invalid | Projets invalides |

Venv Forge 1.0.0rc9 réel, avec `pip check` OK.

## Wheel

| Vérification | Passe 1 | Passe 2 |
|---|---|---|
| `forge_design-0.2.0-py3-none-any.whl` | 166 fichiers | 166 fichiers |
| Ressources du dépôt (gabarits, statiques, schémas) | 34/34 | 34/34 |
| Interdits (tests, docs, scripts, rapports, fixtures, `__pycache__`, `.pyc`, Circuit, Flowchart, `env/dev`, `.venv`) | aucun | aucun |
| Identité avec la baseline | 161/161, octet pour octet | 161/161, octet pour octet |

Par rapport à FD-ACCEPTANCE-001 (165 fichiers), il y a un fichier de plus : `revision_tokens.py` (FD-EDITOR-007).

## Installation

Dans un venv neuf, sans checkout source, installation hors ligne (`--no-index`) depuis les roues et les dépendances téléchargées :

- `pip check` : No broken requirements found ;
- `forge-design --version` : Forge Design 0.2.0 ;
- installés : `forge-design` 0.2.0, `forge-design-circuit` 0.1.0, `forge-design-flowchart` 0.1.0, `forge-mvc` 1.0.0rc9.

## Démarrage

`forge-design --no-browser`, HOME et XDG isolés :

| Dossier courant | Prêt (passe 1 / passe 2) | Projet ouvert implicitement |
|---|---:|---|
| `/tmp` | 365 / 464 ms | Non |
| Dossier HOME de test | 463 / 467 ms | Non |
| Racine d'un projet Forge (A) | 470 / 463 ms | **Non** |

Sans projet : aucune analyse et aucune commande proposée.

## Sécurité locale

Résultats identiques dans les deux passes :

| Contrôle | Résultat |
|---|---|
| Écoute | `127.0.0.1:8765` uniquement |
| Host `127.0.0.1:8765` | 200 |
| Host `localhost:8765` | 400, par contrat (ACC-001) |
| Host étranger, DNS rebinding | 400 |
| POST avec Origin étrangère, sans Origin, ou `cross-site` | 403 |
| Preview réelle active (Ctrl+C) | Serveur, proxy et application sur `127.0.0.1` seulement |

## Project Inspector

A, B et C, dans les deux navigateurs et les deux passes : reconnaissance, version Forge 1.0.0rc9, structure, 9 sections de synthèse en texte, liens vers chaque page.

| Projet | Sections non OK |
|---|---|
| A | **Routes — ! Attention** (ACC-002, toujours présent) |
| B | Routes ✕, Migrations !, Diagnostics !, Contrats ! (défauts de la fixture) |
| C | Routes ✕, Entités ✕, Migrations !, Diagnostics !, Contrats ! (défauts de la fixture) |

Les autres comportements sont conformes :

- **Actualiser et Fermer** : conformes, et un GET n'exécute aucune commande.
- **Projets récents** : ajout, ordre, ouverture, retrait ; un projet supprimé passe en `missing`, « Projet introuvable », sans bouton Ouvrir.
- **Projets invalides** (non Forge, absent, fichier) : aucun projet ouvert.
- **Marqueur supprimé hors Forge Design**, puis Actualiser : le projet est fermé.

## Route Explorer

- **B** : routes, handlers, contrôleurs, méthodes, templates, contrats, diagnostics, filtres, chaîne dépliée, graphe du Graphic Core (**22 nœuds**), source.
- **C** : route dynamique `/items/<int:item_id>` complète ; template calculé « non déterminable », chaîne partielle, jamais absent ; `/absent` et `/broken` problématiques.

## Entity Explorer

- **B** : entités et relations hostiles affichées en texte et échappées, filtres, graphe.
- **A-bare** : l'absence d'entités reste optionnelle, jamais une erreur.

## Template Viewer

- **B** : inventaire, lecture brute, analyse, arbre, références, contrats.
- **C** : « Syntaxe Jinja invalide à la ligne 2. » ; contenu hostile affiché en texte ; contrats invalides globaux.

## Contrats

Ce sont les mêmes cas que FD-ACCEPTANCE-001, rejoués par les étapes Template Viewer et Route Explorer :

- contrat valide associé ;
- JSON invalide, listé et compté sans être associé ;
- contrat sans template ;
- plusieurs contrats pour un même template ;
- liaison route, template et contrat.

## Éditeur

Sur B-write, dans les deux navigateurs :

- lecture du design et de son arbre ;
- action explicite enregistrée ;
- même action répétée : « Aucune modification. », sans écriture ;
- conflit d'écriture interne ;
- preview statique.

Les dix actions mutables sont couvertes par la suite Python, verte : `test_every_action_refuses_a_stale_view_without_writing` et `test_every_action_accepts_the_current_revision`, chacun paramétré sur les dix actions.

## Régression ACC-004

Scénario « deux onglets », dans Chromium et Firefox, deux passes :

1. ajout d'une section : `[section, table, section]` ;
2. l'onglet A affiche la `table` (révision R1) ;
3. l'onglet B supprime le bloc 0 avec son propre formulaire et sa propre révision : `[table, section]` (R2) ;
4. l'onglet A soumet sa vue R1.

| Attendu | Observé |
|---|---|
| 409, aucune écriture de A | Message de conflit affiché ; design **identique octet pour octet** à l'état R2 (SHA-256) |
| Design dans l'état R2 | `[table, section]` |
| Message | « Le design a été modifié depuis l'affichage de cette page. Rechargez l'éditeur avant de recommencer. » |
| Sélection racine | Vérifiée sans JavaScript et par pytest (voir Kit) |
| Recharger, puis action valide | Rechargement par le lien du message, puis « Modification enregistrée. » |

Sans JavaScript (Firefox), les deux étapes passent dans les deux passes :

- vue périmée refusée par formulaire natif, aucun bloc touché ;
- modification externe : sélection racine, rechargement, action valide enregistrée.

## Real Preview

Sur A-preview, dans les deux navigateurs et les deux passes :

- démarrage, état `running` ;
- iframe sur une origine dédiée (`127.0.0.1:<port>/contacts`) ;
- **GET de l'URL de l'iframe : 200**, 1 531 octets HTML ;
- arrêt, état `stopped`, proxy fermé (la requête échoue) ;
- redémarrage, puis changement de projet : la preview est arrêtée.

Dans la console, seules apparaissent les polices `fonts.googleapis.com` du squelette, bloquées par la CSP de la preview. C'est attendu.

Arrêt par Ctrl+C avec la preview active :

- l'enfant tourne avec `python -I -B -u …/child_bootstrap.py` ;
- seuls trois ports loopback sont ouverts (serveur, proxy, application) ;
- arrêt propre, aucun processus restant.

Sans JavaScript : sans objet, car hors contrat de la preview réelle.

## Régression ACC-003

| Instantané A-preview | FD-ACCEPTANCE-001 | Passe 1 | Passe 2 |
|---|---|---|---|
| Après Chromium | ÉCART, 12 `__pycache__` | **conforme** | **conforme** |
| Après Firefox | ÉCART, 12 `__pycache__` | **conforme** | **conforme** |
| Après le Ctrl+C serveur | non mesuré | **conforme** | **conforme** |

Conforme signifie 0 ajout, 0 suppression, 0 modification et 0 mtime modifié : aucun nouveau `__pycache__`, aucun `.pyc` modifié.

La suite Python continue de démontrer, dans `tests/test_real_preview_bytecode.py` :

- un projet identique **pendant** `running`, et pas seulement après l'arrêt ;
- des caches préexistants (à jour, périmé, non importé) ni supprimés ni réécrits ;
- un témoin sans `-B`.

## Debug Center

| Journal | Projet | Résultat |
|---|---|---|
| Absent | A-bare | « Aucune erreur runtime enregistrée. » |
| Vide | A | idem |
| Valide, partiellement invalide | C, B | Événements et anomalies de lecture |
| Volumineux (au plafond) | D | « Lecture partielle du journal. » |

Sur B-write :

- secrets masqués ;
- recherche `q` et filtres ;
- recherche d'une valeur sensible : aucun événement ;
- doublons d'id ;
- détail avec URL de connexion masquée ;
- flux en SVG serveur et en Graphic Core ;
- rotation du journal : l'ancien lien répond **404**.

Redaction : sur **chaque** page parcourue, le kit vérifie qu'aucune des valeurs synthétiques sensibles n'apparaît dans le HTML ni dans les attributs (liste, détail, recherche, URL). Les sorties runtime sont masquées : `DB_PASSWORD=[masqué]` dans `check`, `SERVICE_TOKEN=[masqué]` dans le délai dépassé.

## Doctor

Le GET n'exécute rien. Un POST lance une seule exécution, isolée des deux autres commandes. Le résultat n'est pas persisté : au retour sur la page, les trois commandes sont « non exécutées ».

| Projet | État, code | FAIL | Statut |
|---|---|---|---|
| A | succeeded, 0 | — | — |
| B | checks-failed, 1 | `Entités` : `hostile.json` invalide ; `Environnement` : `SSL_CERTFILE`, `SSL_KEYFILE` manquantes | **Attendus** de la fixture, identiques à FD-ACCEPTANCE-001 |
| C | checks-failed, 1 | `Entités` : `relations.json` invalide | **Attendu** de la fixture, identique à FD-ACCEPTANCE-001 |

## Project audit

A, B et C : succeeded, code 0, dans les deux navigateurs et les deux passes. Un POST par exécution, isolé, non persisté.

## Project check

| Projet | État, code | FAIL ou effet | Statut |
|---|---|---|---|
| A | succeeded, 0 | — | — |
| B | checks-failed, 1 | `Routes — AssertionError: controller executed` (contrôleur hostile de gx8) | **Attendu** |
| C | succeeded, 0 | — | — |
| C-check | succeeded | `DB_PASSWORD=[masqué] depuis le contrôleur` ; sentinelle `CONTROLLER_IMPORTED` écrite par le code applicatif | Effet contrôlé attendu |

L'avertissement de chaque commande est lisible avant le clic, conformément à la frontière de confiance.

## Timeout / sortie runtime

C-timeout, vrai délai :

| | Passe 1 | Passe 2 |
|---|---|---|
| Chromium | 10,11 s | 10,13 s |
| Firefox | 10,11 s | 10,12 s |

Dans tous les cas :

- état `timed-out` ;
- stdout partiel conservé : `AVANT TIMEOUT`, `SERVICE_TOKEN=[masqué] avant blocage`, `SANS-LF` ;
- aucun processus restant.

stderr partiel : voir Kit (couvert par pytest).

## Modules

Les dépôts des modules ne sont pas modifiés. Leurs roues sont construites depuis leurs commits propres.

- **Circuit** : ressource `demo.circuit.json` ouverte ; composant déplacé au clavier ; persistance attendue dans B-write ; aucun asset Flowchart chargé.
- **Flowchart** : ressource `simple.flow.json` ouverte ; nœud puis arête renommés ; persistance attendue ; aucun asset Circuit chargé.
- **Historique** : 3 lignes dans `.forge-design/history.jsonl`, dans les deux navigateurs.
- **Sans JavaScript** : navigation, métadonnées, et le message « La visualisation graphique nécessite JavaScript. », conformément au contrat des modules.

## Graphic Core

Rendus vérifiés avec JavaScript :

- graphe des routes (22 nœuds sur B) ;
- graphe des entités ;
- flux runtime du détail Debug ;
- ressources Circuit et Flowchart.

Sans JavaScript, les replis SVG serveur sont présents (routes, entités, flux). 134/134 tests Node.

## Sans JavaScript

Firefox avec `javascript.enabled=false` : **10/10** étapes dans les deux passes. Les deux étapes de plus que FD-ACCEPTANCE-001 (8/8) sont les étapes d'éditeur ajoutées par FD-EDITOR-007.

Étapes couvertes :

- Project Inspector ;
- Route Explorer (filtre, repli SVG serveur) ;
- Entity Explorer ;
- Template Viewer ;
- Debug Center (liste masquée, filtre, détail, flux SVG statique) ;
- `doctor`, audit et check par POST natif ;
- modules ;
- éditeur : vue périmée, racine et rechargement ;
- éditeur : vue périmée refusée par formulaire natif ;
- aucune requête hors `127.0.0.1`.

## CSP

Aucune violation et aucune exception sur les pages de Forge Design, dans les deux navigateurs et les deux passes (écouteur injecté avant les scripts de page). Seules violations : les polices externes du squelette dans l'iframe de preview, bloquées conformément au contrat.

## Réseau

| | Passe 1 | Passe 2 |
|---|---:|---:|
| Requêtes Chromium | 610 | 610 |
| Requêtes Firefox | 799 | 799 |

Toutes vont vers `127.0.0.1`, hormis les polices du projet dans la preview, bloquées. Même chose sans JavaScript. Aucune ressource de Forge Design ne sort vers Internet.

## Snapshots

Instantanés (nom, taille, mtime, SHA-256) des 10 projets avant et après chaque passage navigateur, `.venv` exclu, plus A-preview autour du Ctrl+C :

| Projet | Chromium (P1 / P2) | Firefox (P1 / P2) | Écarts |
|---|---|---|---|
| A, A-bare, B, C, C-timeout, D, invalid | conforme / conforme | conforme / conforme | **Aucun**, ni octet ni mtime, alors que `doctor`, audit et check y ont tourné |
| A-preview | conforme / conforme | conforme / conforme | **Aucun** (ACC-003 corrigé) ; aussi conforme au Ctrl+C |
| B-write | conforme / conforme | conforme / conforme | Écritures attendues seulement |
| C-check | conforme / conforme | conforme / conforme | Sentinelle `CONTROLLER_IMPORTED` |

Aucun `__pycache__`, aucun `.forge-design/` inattendu, aucune réécriture et aucun mtime parasite.

## Écritures attendues

Ce sont les seuls écarts tolérés par le kit, inchangés depuis FD-ACCEPTANCE-001 :

- **B-write** :
  - `mvc/views/contacts/list.design.json` (éditeur) ;
  - `mvc/circuit/demo.circuit.json` et `mvc/flowchart/simple.flow.json` (actions des modules) ;
  - `.forge-design/history.jsonl` (historique des modules) ;
  - `storage/logs/errors.dev.jsonl` (rotation faite par le scénario lui-même).
- **C-check** : `CONTROLLER_IMPORTED`, écrit par le code applicatif.

## Processus

| Contrôle | Passe 1 | Passe 2 |
|---|---|---|
| Après Chromium, Firefox, sans JavaScript (cwd ou commande dans le dossier de travail) | aucun | aucun |
| Ctrl+C avec preview réelle active | arrêt propre, aucun restant | arrêt propre, aucun restant |
| Endurance (30 commandes) et complément | aucun enfant | aucun enfant |

## Packaging

Voir Wheel. Le kit `scripts/acceptance/` n'entre pas dans la roue. Le durcissement de la sonde de roue (identité avec l'arbre Git) est laissé à FD-RELEASE-002.

## Performance

Médianes en ms, 7 GET sur B et 5 GET sur D :

| Page | B (ACC-001) | B (P1 / P2) | D (ACC-001) | D (P1 / P2) |
|---|---:|---:|---:|---:|
| Ouverture du projet | 26 | 27 / 26 | 198 | 178 / 178 |
| `/inspector` | 21,9 | 22,1 / 22,2 | 204,4 | 175,3 / 173,7 |
| `/routes` | 53,5 | 53,3 / 53,2 | 205,8 | 210,8 / 210,9 |
| `/entities` | 31,2 | 31,2 / 31,3 | 58,8 | 58,8 / 60,0 |
| `/templates` | 8,7 | 8,5 / 8,5 | 19,7 | 19,7 / 19,6 |
| `/debug` | 19 | 19,2 / 19,3 | 72 | 72,1 / 72,8 |

Commandes runtime sur A, médianes sur 5 :

| Commande | ACC-001 | P1 / P2 |
|---|---:|---:|
| `doctor` | 134 | 136,3 / 137,1 |
| audit | 107 | 107,2 / 108,3 |
| check | 124 | 125,0 / 126,5 |

Aucune régression manifeste. Les écarts restent de l'ordre du bruit de mesure ; `/inspector` sur D est même un peu plus rapide.

## Mémoire

Le kit mesure, avec modules actifs, sur B-write, 20 rondes de 9 pages puis 30 commandes :

| | Avant | Après 20 rondes | Après 30 commandes |
|---|---:|---:|---:|
| Passe 1 | 52 476 Kio | 54 096 Kio | 54 160 Kio |
| Passe 2 | 52 408 Kio | 54 112 Kio | 54 164 Kio |

Le complément enchaîne huit fois ce cycle sur un même serveur. RSS après chaque cycle :

- passe 1 : 54 032, 53 880, 55 384, 55 384, 55 384, 55 384, 55 384, 55 504 Kio ;
- passe 2 : 54 180, 54 168, 55 568, 55 568, 55 568, 55 568, 55 568, 55 568 Kio.

C'est un échauffement suivi d'un **plateau** dès le troisième cycle (+120 Kio, puis +0 sur les cinq derniers), comme dans FD-ACCEPTANCE-001 : pas de fuite.

## Matrice d'acceptation

Dans la colonne Snapshot, « conforme » vaut pour les deux passes.

| Domaine | Chromium | Firefox | Sans JS | Snapshot | Verdict |
|---|---:|---:|---:|---:|---|
| Project Inspector | OK | OK | OK | conforme | Accepté avec réserve mineure (ACC-002) |
| Routes | OK | OK | OK | conforme | Accepté |
| Entités | OK | OK | OK | conforme | Accepté |
| Templates | OK | OK | OK | conforme | Accepté |
| Contrats | OK | OK | OK | conforme | Accepté |
| Éditeur / ACC-004 | OK (409) | OK (409) | OK (409, racine) | B-write : écritures attendues | **Accepté : ACC-004 corrigé** |
| Debug | OK | OK | OK | conforme | Accepté |
| doctor | OK (FAIL attendus B, C) | OK | OK | conforme | Accepté |
| audit | OK | OK | OK | conforme | Accepté |
| check | OK (FAIL attendu B ; sentinelle C-check) | OK | OK | conforme ; C-check : sentinelle | Accepté |
| Runtime timeout | OK (10,1 s) | OK (10,1 s) | — | conforme | Accepté |
| Real Preview / ACC-003 | OK (GET 200) | OK (GET 200) | N/A | **conforme**, Ctrl+C compris | **Accepté : ACC-003 corrigé** |
| Circuit | OK | OK | contrat | B-write : écritures attendues | Accepté |
| Flowchart | OK | OK | contrat | B-write : écritures attendues | Accepté |

## Anomalies restantes

Comparaison avec FD-ACCEPTANCE-001 :

| ID | FD-ACCEPTANCE-001 | FD-ACCEPTANCE-002 |
|---|---|---|
| **ACC-004** | MAJOR, échec : une vue périmée modifiait silencieusement un autre bloc | **Corrigé** (FD-EDITOR-007) : 409, aucune écriture, Chromium, Firefox et sans JavaScript, deux passes |
| **ACC-003** | MINOR : 12 `__pycache__` écrits dans A-preview | **Corrigé** (FD-REALPREVIEW-007) : A-preview conforme, Ctrl+C compris |
| **ACC-002** | MINOR | **Restant** : A, squelette officiel, « Routes — ! Attention » à cause de `register_optins(router)`, dans les deux passes. Il n'est pas présenté comme un succès. |
| **ACC-001** | COSMETIC | **Restant** : `01-cadrage-fonctionnel.md`, ligne 264, annonce toujours `localhost`, alors que `Host: localhost` reçoit 400 par contrat |

**Limite connue, non classée.** Entre deux threads d'un même processus, `write_design` peut laisser passer deux publications (constat de FD-EDITOR-007). Ce chemin n'est pas atteignable avec le serveur livré, qui traite une requête à la fois (`WSGIServer` sans `ThreadingMixIn`, figé par un test), et le design n'est jamais mélangé. L'acceptance n'a révélé aucun chemin livré qui l'atteigne. Le verrou en cours d'écriture par ailleurs devra avoir son propre ticket et sa propre requalification ciblée.

## Nouvelles anomalies

**Aucune.**

| Contrôle | Résultat |
|---|---|
| Parcours Chromium | 29/29, deux passes |
| Parcours Firefox | 29/29, deux passes |
| Sans JavaScript | 10/10, deux passes |
| Instantanés | 21/21 conformes par passe |
| Processus restants | aucun |
| Suite automatique | verte |

Le test `dead_proxy` de la preview réelle, instable avant ce ticket, n'a pas échoué : la règle d'analyse prévue n'a pas eu à s'appliquer.

Ces constats ne sont pas des défauts de Forge Design :

- Firefox headless ne donne pas le focus au document : le focus visible est vérifié dans Chromium ;
- les polices externes du squelette sont bloquées dans la preview ;
- les FAIL de B et C viennent des fixtures, cause par cause.

## Classification

| Sévérité | Nombre | IDs |
|---|---:|---|
| BLOCKER | 0 | — |
| MAJOR | 0 | — (ACC-004 corrigé) |
| MINOR | 1 | ACC-002 |
| COSMETIC | 1 | ACC-001 |

## Verdict

**ACCEPTED_WITH_MINOR_ISSUES**

Règle appliquée sans arrangement : aucun BLOCKER, aucun MAJOR, et une anomalie MINOR connue restante (ACC-002), avec ACC-001 COSMETIC. Le verdict découle des résultats des deux passes ; rien n'a été modifié pour l'obtenir, ni le cœur, ni le kit, ni les fixtures.

## SéquenCiel gate

**SéquenCiel gate: OPEN**

Toutes les conditions sont réunies :

- verdict ACCEPTED_WITH_MINOR_ISSUES ;
- aucun BLOCKER ni MAJOR ;
- aucune écriture non maîtrisée : 0 écart hors écritures déclarées, ACC-003 et ACC-004 corrigés ;
- aucune fuite de secret ;
- aucune exposition réseau : loopback seulement ;
- aucun processus non maîtrisé.

Le gate ouvert autorise le chemin vers le premier essai. SéquenCiel n'a été ni ouvert, ni utilisé, ni modifié par ce ticket.

## Tickets restants avant release

1. **FD-DOCS-001** : aligner `01-cadrage-fonctionnel.md` sur le contrat `127.0.0.1` (ACC-001).
2. **FD-RELEASE-002** : clôture de la release 0.2.0, avec le durcissement de la sonde de roue (identité avec l'arbre Git, présence des modules Python attendus).
3. Ensuite seulement : le premier essai de Forge Design sur SéquenCiel.

Recommandés, hors chemin critique :

- **FD-ROUTES-022** : reconnaître `register_optins(router)` du squelette comme limite connue informative (ACC-002) ;
- le **ticket du verrou de `write_design`**, actuellement en cours hors commit, avec sa propre requalification ciblée (éditeur, modules, instantanés de B-write).

## Fichiers créés

- `docs/rapports/FD-ACCEPTANCE-002.md`

## Fichiers modifiés

- `docs/03-roadmap.md` : état FD-ACCEPTANCE-002, verdict, gate, prochaine étape

Non modifiés :

- `forge_design/` ;
- `scripts/acceptance/` ;
- les rapports historiques FD-ACCEPTANCE-001, FD-EDITOR-007 et FD-REALPREVIEW-007 ;
- les dépôts Circuit et Flowchart.

Les `results/` des deux passes ne sont pas versionnés, comme pour FD-ACCEPTANCE-001.

## Validation finale

Suite automatique lancée dans le worktree (`8ca9b72`) :

| Commande | Résultat |
|---|---|
| `python -m compileall -q forge_design tests` | OK |
| `ruff check forge_design tests scripts` | All checks passed |
| `ruff format --check .` | 444 fichiers formatés (445 avec ce rapport) |
| `pyright` (strict) | 0 erreur, 0 avertissement |
| `git diff --check` | OK |
| `pytest` (suite complète) | **5 097 passed** |
| `node --test tests/js/graphics/*.test.mjs` | 134/134 |
| `mkdocs build --strict` | Sans objet (MkDocs non configuré) |
| Acceptance, passe 1 | Toutes les étapes, `exit=0` |
| Acceptance, passe 2 | Toutes les étapes, `exit=0`, résultats identiques |
| Roue et baseline | 161/161 identiques, deux passes |

La suite a été relancée après la rédaction de ce rapport et de la roadmap.

## État Git final

Un seul commit : `test: requalifier Forge Design avant SéquenCiel (FD-ACCEPTANCE-002)`, au-dessus de `8ca9b72`. Il ne contient que ce rapport et la roadmap, et il n'a pas été poussé.

Restent hors commit, sur disque :

- `docs/rapports/FD-CONTRACT-001.md`, modifié par l'utilisateur ;
- le travail concurrent (verrou de `write_design`) ;
- les fichiers de vérification de FD-EDITOR-007 ;
- `FD-EDITOR-008-RAPPORT.md` et `fd-editor-008/`, apparus pendant la qualification.

La version reste 0.2.0.
