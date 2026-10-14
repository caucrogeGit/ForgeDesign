# Rapport — FD-RUNTIME-003

Exécuter `forge project:check` à la demande depuis Debug Center, avec une frontière d'exécution explicite. Date : 2026-10-14.

## Objectif

Ajouter à Debug Center une troisième commande Forge, lancée uniquement sur un clic explicite : `forge project:check`. Contrairement à `project:audit`, elle importe réellement les routes du projet et exécute donc du code applicatif. Le ticket intègre la commande avec les mêmes garanties de processus, et surtout **démontre** la frontière entre les trois commandes et l'annonce à l'utilisateur avant le clic.

| Décision | Résultat |
|---|---|
| A. Nouvelle commande runtime ? | Oui |
| B. Commande ? | `project:check` |
| C. Exécute potentiellement du code projet ? | **Oui** : démontré par sentinelles |
| D. Action explicite obligatoire ? | Oui : un POST par clic, jamais au GET |
| E. Sous-processus séparé ? | Oui |
| F. Sandbox OS ? | **Non** : dit dans l'avertissement |
| G. Arguments arbitraires ? | Non : liste fermée de trois commandes |
| H. Nouveau Tool ? | Non : cinq Tools |
| I. Résultat persisté ? | Non |
| J. Graphic Core modifié ? | Non : 134/134 |

## État Git initial

| Élément | Valeur |
|---|---|
| HEAD | `2da0d67` (FD-RUNTIME-002), qui contient FD-ROUTES-021, FD-PERF-001, FD-RUNTIME-001 et FD-DEBUG-006 |
| `origin/main` | `e411d0c` ; 0 commit en retard, 5 en avance |
| Arbre | Seul `docs/rapports/FD-CONTRACT-001.md` est modifié par l'utilisateur ; il est préservé et hors commit |
| Collision | Aucune : pas de `docs/rapports/FD-RUNTIME-003*`, l'identifiant n'apparaissait que comme recommandation |
| Version | 0.2.0, inchangée |

## Périmètre

Le ticket ajoute :

- une troisième entrée à la liste fermée du runner privé, avec `run_forge_project_check` ;
- un POST, une section et un avertissement.

Il adapte trois tests de contrat de FD-RUNTIME-002 (passage de 2 à 3 commandes) et ne modifie ni Forge, ni le masqueur, ni Project Inspector, ni Route Explorer, ni Entity Explorer, ni Template Viewer, ni le journal.

## project:check inspecté

`cli/project/project_check.py` (285 lignes, forge-mvc 1.0.0rc9) fait 7 contrôles : structure, configuration, entités, routes, templates, modules et migrations. Six sont des lectures de fichiers comparables à l'audit. Le septième, `check_project_routes`, procède ainsi :

1. `ast.parse` ;
2. insertion de la racine en tête de `sys.path` ;
3. **`importlib.import_module("mvc.routes")`** ;
4. retrait des modules `mvc.*` et de la racine.

Une exception levée à l'import devient `[FAIL] Routes — erreur au chargement … — {type}: {message}`.

La sortie est uniquement textuelle, sans format machine (§87).

## Comparaison doctor / audit / check

| Commande | Code projet exécuté | Services externes possibles | Niveau |
|---|---|---|---|
| `project:audit` | Non constaté | Non constaté | Analyse officielle essentiellement statique |
| `doctor` | `config.py` et ses imports | Base configurée possible | Diagnostic avec configuration exécutée |
| `project:check` | Routes, contrôleurs et imports transitifs | Tout effet produit par ce code est possible | Exécution applicative explicite |

En résumé : **`project:audit` lit ; `doctor` exécute la configuration ; `project:check` exécute une partie du code applicatif.**

## Point d'entrée officiel

`forge.py`, `cmd_project_check` :

- `cli_fail` (code 1) si `app.py` ou `mvc/` manque ;
- sinon `run_project_check(Path.cwd())`, puis `print_check_report` ;
- `sys.exit(1)` si au moins un contrôle est en `fail`.

## Imports réalisés

Sonde par audit hooks sur le **vrai squelette Forge** (`site-packages/skeleton/data` avec un vrai `.venv`) :

| Effet | Observé ? | Exemple |
|---|---|---|
| Import des routes | **Oui** | `mvc/routes/__init__.py` exécuté |
| Import des contrôleurs | **Oui** | `mvc/controllers/home_controller.py` |
| Imports transitifs | **Oui** | `optins/__init__.py`, `optins/registry.py` (hors `mvc/`) |
| `config.py` | Non | Le cœur ne l'importe que dans `core/app/app_factory.py` |
| Lecture du système de fichiers | Oui | Structure, `env/example`, JSON, templates, migrations |
| Écriture du système de fichiers | Non avec `-B` | Sans `-B` : `__pycache__` dans `mvc/routes`, `mvc/controllers`, `optins` |
| Base de données | Non | Aucun `sqlite3.connect` |
| Réseau | Non | Aucun `socket.*` |
| Sous-processus | Non | Aucun `Popen`, `system`, `exec`, `spawn` ou `fork` |
| Threads | Non | Aucun `_thread.start_new_thread` |
| Tests | Non | — |

Paquets chargés : `forge.py`, `cli`, `core` (forge-mvc) et `dotenv`, plus les opt-ins éventuels. `os.environ` reste inchangé.

## Code projet exécuté

Fixture à sentinelles (tests réels, projet temporaire) :

- les routes écrivent `ROUTES_IMPORTED` ;
- le contrôleur importé écrit `CONTROLLER_IMPORTED` ;
- le module importé par ce contrôleur écrit `TRANSITIVE_IMPORTED`.

Les trois fichiers apparaissent. Un contrôleur **non importé** par les routes (`UNUSED_IMPORTED`) n'apparaît jamais : seule la chaîne réellement importée s'exécute.

## Imports transitifs

Démontrés deux fois :

- par `app_side_effect.py`, module à la racine du projet importé par le contrôleur, ce qui est possible parce que la racine est en tête de `sys.path` pendant l'import ;
- sur le squelette, par `optins/registry.py`.

## config.py

Non chargé par la commande : la sentinelle `CONFIG_EXECUTED` n'apparaît jamais. Il le serait si un module importé l'importait ; l'avertissement le dit.

## Effets filesystem

- La commande officielle n'écrit rien, avec `-B`.
- Forge Design n'écrit rien.
- Le code importé peut écrire : dans les tests comme dans les navigateurs, la **seule** différence d'instantané est la sentinelle écrite par la fixture. Aucun `__pycache__`.

**Forge Design n'a pas écrit ce fichier. Le code applicatif exécuté par `project:check` l'a écrit.** C'est une distinction architecturale : Forge Design ne modifie rien directement ; la commande, explicitement demandée, peut exécuter du code du projet qui garde les droits de l'utilisateur. Ce n'est pas une violation de la lecture seule de Forge Design, et la page l'annonce avant le clic.

## Effets réseau

Aucun sur le squelette. Le code importé pourrait en avoir ; aucune connexion externe n'a été tentée dans les fixtures (§91-92).

## Effets base de données

Aucun : ni connexion, ni `sqlite3.connect`, ni base créée.

## Sous-processus / threads

| Cas (code importé) | Résultat |
|---|---|
| Enfant `sleep 60`, puis sortie normale | L'enfant garde les tubes, le délai joue, **le groupe est tué**, l'enfant ne survit pas (test) |
| Import bloquant avec enfant | « Vérification interrompue : délai dépassé. », groupe tué, enfant mort (test) |
| Thread non démon | Le processus ne sort pas : délai. Le rapport, écrit dans un stdout tamponné jamais vidé, est **perdu** ; stderr, vidé ligne par ligne, reste (test) |
| Enfant détaché par `start_new_session=True` | **Survit** : il sort du groupe lancé par Forge Design (test qui documente la limite, enfant tué par le test) |

D'où la formulation validée de l'avertissement : « arrête le groupe de processus qu'il a lancé », et non « tous les processus ».

## Codes retour

| Code | Cause | État affiché |
|---|---|---|
| 0 | Aucun FAIL | Terminé avec le code 0 : aucun contrôle en échec (des avertissements restent possibles) |
| 1 | FAIL, `cli_fail` ou erreur de la commande | Terminé avec le code 1 : au moins un contrôle en échec, ou erreur de la commande |
| Autre | Notamment `sys.exit(n)` du code importé, qui sort **sans rapport** (`SystemExit` échappe aux `except Exception`) | Terminé avec un autre code retour : le code importé du projet a pu terminer le processus |
| — | Lancement impossible, délai | Échec du lancement ; Vérification interrompue : délai dépassé |

## Sorties

`Forge project:check — <version>`, une ligne `[OK]`, `[WARN]` ou `[FAIL]` par contrôle, puis le bilan. Ce qu'imprime le code importé **précède** le rapport, sur stdout ou stderr. Le texte n'est jamais interprété.

## Architecture

| Fichier | Changement |
|---|---|
| `forge/runtime_diagnostics.py` | `CHECK_ARGUMENTS` ; troisième entrée de `_COMMANDS` ; `run_forge_project_check` ; `_ForgeCommand(arguments, not_launched, timed_out)` porte des phrases complètes |
| `web/debug.py` | `run_forge_check_action` ; table `_NOT_LAUNCHED` des messages accordés ; paramètres `check` et `check_error` |
| `web/server.py` | Route `POST /debug/forge-project-check` |
| `web/templates/debug.html` | Troisième appel de la macro ; l'article est fourni par l'appelant |

En corrigeant l'article, le texte « lancer le audit » de FD-RUNTIME-002 a aussi été corrigé en « lancer l'audit ».

## Runner partagé

`_run_forge_command` (FD-RUNTIME-002) est réutilisé sans modification de son cycle :

- interpréteur ;
- `Popen(shell=False, start_new_session=True, stdin=DEVNULL)` ;
- drainage borné ;
- `killpg` dans tous les cas ;
- nettoyage et masquage.

## Liste fermée

`_COMMANDS` est un `MappingProxyType` de **l'ensemble exact** `{"doctor", "project:audit", "project:check"}`. Le test de contrat vérifie l'ensemble, et non un compteur. Les autres garanties sont vérifiées par tests :

- tout autre nom (dont `project:check --fix`) lève `ValueError` sans lancement ;
- l'AST ne contient que trois appels littéraux au runner privé ;
- ni le runner privé ni `_COMMANDS` ne sont référencés ailleurs ;
- l'API publique se limite à `run_forge_diagnostic`, `run_forge_project_audit` et `run_forge_project_check`.

## Commande argv

`CHECK_ARGUMENTS = ("-s", "-B", "-P", "-m", "forge", "project:check")`. Un test vérifie l'égalité exacte de l'argv reçu par l'interpréteur.

## Interpréteur

`<racine>/.venv/bin/python` via `project_interpreter`, sans repli. S'il est absent : « … : vérification non lancée. ».

## cwd

La racine vérifiée (test).

## Environnement

Même liste blanche. Un test injecte `PYTHONPATH`, `PYTHONHOME`, `VIRTUAL_ENV`, `APP_ENV=prod` et `SERVICE_TOKEN` : aucune n'est transmise. `APP_ENV` n'est pas lu par la commande ; le code importé retombe sur son défaut, comme en terminal.

`-s` est vérifié par le test du `.pth` du site utilisateur (venv `--system-site-packages`), étendu aux trois commandes.

## Timeout

10 s, inchangé. Mesures : 103 ms sur le squelette, 144 ms avec 150 contrôleurs réellement importés et 1 000 templates. Aucun arbitrage n'est nécessaire (§38).

## Groupe de processus

`SIGKILL` au groupe après une sortie normale comme au délai : aucun descendant du groupe ne survit (deux tests réels). Seul un processus détaché volontairement dans une nouvelle session échappe à cette garantie (test).

## Bornes stdout / stderr

256 Kio par flux, avec drainage continu ; troncature comptée (test).

## ANSI

Même `clean_output`.

## Masquage FD-DEBUG-006

Les secrets imprimés par le code importé sont masqués sur stdout et stderr, y compris quand le processus sort par `sys.exit(3)`. Les valeurs n'apparaissent ni dans le résultat, ni dans le HTML (vérifié par tests et navigateurs) :

- `DB_PASSWORD=VerySecret123` et `SERVICE_TOKEN=abc123` deviennent `[masqué]` ;
- `mysql://roger:MotDePasse9@db.local/app` devient `mysql://roger:[masqué]@db.local/app`.

## Debug Center

La troisième section s'intitule « Vérification du projet Forge » et son bouton « Exécuter la vérification Forge ». L'explication cite `forge project:check`.

Ordre : Diagnostic, Audit, Vérification, Journal.

## Avertissement utilisateur

Texte validé, affiché avant le bouton :

> La vérification `forge project:check` est exécutée avec l'environnement Python du projet (`.venv/bin/python`) dans un processus séparé. Elle importe réellement les routes du projet (`mvc/routes`) : ce code s'exécute, ainsi que les contrôleurs et modules qu'il importe (dans le squelette Forge : contrôleurs et registre `optins/`). Ce code peut lire ou écrire des fichiers, contacter des services ou lancer des processus avec les droits de votre compte ; `config.py` n'est pas chargé par la commande elle-même, mais peut l'être par le code importé. Forge Design n'exécute pas ce code dans son propre processus, limite la durée et arrête le groupe de processus qu'il a lancé, mais ce sous-processus n'est pas un bac à sable.

Une garde de test (§114) exige ses phrases-clés et refuse « tous les processus » et « analyse les routes ». Trois mutations la vérifient.

## Séparation doctor / audit / check

Test avec espion sur les trois runners :

- le POST de la vérification n'exécute que la vérification, puis celui de l'audit que l'audit, puis celui de `doctor` que `doctor` ;
- à chaque réponse, seule la section visée est exécutée et les deux autres restent « non exécutées » ;
- le GET suivant revient à trois « non exécuté ».

Concurrence : 9 exécutions simultanées (3 projets × 3 commandes), chacune avec son propre argv et son propre `cwd`. Il n'y a aucun état mutable global.

## Sécurité HTTP

Les gardes sont les mêmes :

- 403 pour une Origin étrangère ou absente ;
- 415 hors formulaire ;
- 400 pour tout champ ou paramètre (`command`, `args`, `cwd`, `?env=`) ;
- `no-store` ;
- `GET /debug/forge-project-check` : 405.

Aucun lancement lors de `GET /debug`, `/inspector`, `/routes`, `/entities` ou `/templates`, ni d'une actualisation ou d'une ouverture de projet (test).

## Projet absent

409 « Aucun projet sélectionné : vérification non lancée. » ; aucun processus.

## Projet invalide

`app.py` supprimé après l'ouverture : 409 « Vérification non lancée : … » ; aucun processus.

## Interpréteur absent

200, `launch-failed`, « … : vérification non lancée. ».

## Persistance

Aucune : ni « dernier check », ni stockage XDG, ni `.forge-design/`, ni session. Non intégrée à Project Inspector : une commande qui exécute du code ne doit jamais être déclenchée par le cockpit.

## Tests Python

`tests/test_runtime_project_check.py` (13 tests).

Avec le faux interpréteur :

- argv, `cwd`, environnement ;
- codes 0, 1 et 3 ;
- secrets et bornes ;
- délai et interpréteur absent, avec les messages au féminin ;
- concurrence des trois commandes.

**Vrais `project:check`** (venv lié à forge-mvc 1.0.0rc9) :

- sentinelles routes, contrôleur et transitif présentes ; `config.py` et le contrôleur non importé absents ;
- seule différence d'instantané : les trois sentinelles ;
- aucun `__pycache__` ;
- `forge.py` hostile neutralisé ;
- secrets masqués ;
- enfant tué après une sortie normale ;
- import bloquant avec enfant : délai et groupe tué ;
- thread non démon : délai, rapport perdu ;
- `sys.exit(3)` : code 3 sans rapport, secret masqué ;
- enfant détaché : limite documentée.

`tests/test_runtime_audit.py` est adapté au contrat à trois commandes (ensemble exact, API publique, littéraux AST, `project:check --fix` refusé) et à `make_linked_venv` (helper déplacé dans le support). Le test `-s` couvre désormais les trois commandes.

## Tests Web

`tests/test_web_runtime_project_check.py` (7 tests) :

- GET sans exécution sur toutes les pages, et garde de l'avertissement ;
- isolation des trois commandes, aucune persistance, projet intact ;
- libellés des codes 1 et 3 ;
- gardes, sans projet, projet invalide ;
- secrets, délai, interpréteur absent ;
- cinq Tools.

## Mutations

Script hors dépôt, lancé depuis le scratchpad. Pour chaque mutation : éditions, `pytest -x` sur six fichiers de tests runtime, restauration à l'octet, empreinte vérifiée. Résultat : **28/28 tuées**.

| Mutation | Tuée par |
|---|---|
| Vérification lancée au GET | `test_get_never_runs_…` (et 405) |
| Action vérification qui appelle l'audit, ou `doctor` | `test_each_post_runs_only_its_command` |
| Action audit, ou `doctor`, qui appelle la vérification | idem |
| Runner de vérification qui appelle l'audit | `test_command_cwd_and_environment_are_fixed` |
| argv `project:audit` au lieu de `project:check` | idem |
| argv incorrect (`--fix` ajouté) | idem |
| `-P`, `-B` ou `-s` retiré | idem |
| `cwd` incorrect, `shell=True` | idem |
| Commande arbitraire acceptée | `test_closed_command_list_is_structural` |
| Liste fermée contournée (table mutable) | idem |
| Champ HTTP accepté | `test_guards_and_projects` |
| Timeout ignoré | `test_timeout_and_missing_interpreter_messages` |
| Groupe enfant non tué | `test_child_started_by_imported_code_never_survives` |
| stdout ou stderr non borné | `test_outputs_secrets_and_bounds` |
| Masquage supprimé | idem |
| Résultat persisté | `test_each_post_runs_only_its_command` |
| Vérification sans projet, ou sur un projet non Forge | `test_guards_and_projects` |
| Avertissement affaibli (« analyse les routes ») | `test_get_never_runs_and_warning_states_the_execution_boundary` |
| Avertissement qui sur-promet (« arrête tous les processus lancés ») | idem |
| Avertissement sans « pas un bac à sable » | idem |
| Message au masculin (« Vérification interrompu ») | `test_timeout_and_missing_interpreter_messages` |

## Chromium

Conditions :

- roue 0.2.0 dans un venv neuf, vraie commande `forge-design`, HOME isolé ;
- `checkdemo` recréé à chaque passage depuis le **vrai squelette Forge**, avec son propre `.venv`.

Son `home_controller.py` écrit `CONTROLLER_IMPORTED` et imprime `DB_PASSWORD`, `SERVICE_TOKEN` et une URL MySQL.

Scénario, 7/7 :

1. ouverture du projet ; trois commandes « non exécutées » ; lecture de l'avertissement de la vérification ;
2. clic réel sur la vérification : vrai `project:check`, code 0, `[OK] Routes`, secrets masqués sur les deux flux, audit et diagnostic toujours non exécutés ;
3. effet de bord contrôlé : **seul** `CONTROLLER_IMPORTED` est apparu, avec le contenu écrit par le code applicatif, et tous les autres fichiers sont identiques ;
4. rechargement : trois sections « non exécutées » ;
5. audit, puis diagnostic : chacun dans sa section ; l'audit n'exécute pas le contrôleur (aucun « depuis le contrôleur ») ;
6. aucune erreur JavaScript ;
7. ni l'audit ni le diagnostic n'ont ajouté de fichier.

Aucune valeur sensible dans le HTML. Aller-retour du clic sur la vérification : environ 218 ms, dont 0,11 s de commande.

## Firefox

Même scénario, 7/7. Aller-retour : 400 ms pour la vérification, au premier POST de la session.

## Sans JavaScript

Firefox avec `javascript.enabled=false`. Vérification, audit puis diagnostic par POST natifs (clics BiDi réels). À chaque fois, seule la section visée est exécutée et aucune valeur sensible n'apparaît dans les textes ni les attributs. Trois POST au journal du serveur.

## Performance

Médianes sur 10 exécutions, même argv et même environnement :

| Projet | Fichiers hors `.venv` | `project:check` direct | Via Forge Design | Surcoût |
|---|---:|---:|---:|---:|
| Squelette Forge | 98 | 103 ms (pire 113) | 104 ms (pire 110) | +0,7 ms |
| Moyen (150 contrôleurs importés par les routes, 1 000 templates) | 1 268 | 144 ms (pire 158) | 143 ms (pire 158) | −0,7 ms (bruit) |

## ToolRegistry

Cinq Tools, inchangés (test).

## Graphic Core

Aucune modification ; 134/134 tests Node.

## Modules externes

Circuit et Flowchart non modifiés. Le scénario Chromium complet, avec `--module forge_design_circuit --module forge_design_flowchart`, donne 7/7.

## Dette / limites

- **Pas de sandbox.** Le code importé a les droits de l'utilisateur : fichiers, réseau, processus. Seul le groupe lancé est arrêté, et un processus détaché par le projet survit (testé).
- **Thread non démon.** Le rapport est perdu, puisque stdout reste tamponné et n'est jamais vidé. L'option `-u` (sortie non tamponnée) le rendrait visible jusqu'au délai, pour les trois commandes. C'est une décision d'argv, qui n'a pas été prise ici.
- **`sys.exit` du code importé.** Le code retour peut venir du projet, pas de Forge ; le libellé le dit.
- **Racine en tête de `sys.path` pendant l'import.** Un module du projet peut masquer un module importé plus tard. C'est le comportement de Forge, à l'identique d'un lancement en terminal.
- **Version de forge-mvc.** Les constats valent pour forge-mvc 1.0.0rc9.

## Recommandation ticket suivant

Trois pistes :

- **Décider de `-u`** (sortie non tamponnée) pour les trois commandes, afin de conserver la sortie déjà produite lors d'un délai dépassé. C'est un petit ticket, mais il modifie l'argv validé, donc il demande un arbitrage.
- **Phase 12 (intégration applicative).**
- **Revue de cohérence** de la documentation des trois niveaux de confiance dans le manuel utilisateur.

## Fichiers créés

- `tests/test_runtime_project_check.py`
- `tests/test_web_runtime_project_check.py`
- `docs/rapports/FD-RUNTIME-003.md`

## Fichiers modifiés

- `forge_design/forge/runtime_diagnostics.py`
- `forge_design/web/debug.py`
- `forge_design/web/server.py`
- `forge_design/web/templates/debug.html`
- `tests/runtime_diagnostics_support.py`
- `tests/test_runtime_audit.py`
- `docs/tools/debug-center.md`
- `docs/tools/project-inspector.md`
- `docs/02-architecture.md`
- `docs/03-roadmap.md`

## Validation finale

| Commande | Résultat |
|---|---|
| `python -m compileall -q forge_design tests` | OK |
| `ruff check forge_design tests` | All checks passed |
| `ruff format --check .` | OK |
| `pyright` (strict) | 0 erreur, 0 avertissement |
| `git diff --check` | OK |
| `pytest` (suite complète) | 5 008 passed |
| `node --test tests/js/graphics/*.test.mjs` | 134/134 |
| Roue 0.2.0, venv neuf | `pip check` OK |
| Chromium, Firefox, Chromium + modules | 7/7 chacun, vrais `project:check`, `project:audit` et `doctor` |
| Firefox sans JavaScript | OK, trois POST natifs |
| Mutations | 28/28 tuées |

## État Git final

Un seul commit : `feat: exécuter project:check à la demande (FD-RUNTIME-003)`, au-dessus de `2da0d67`. Il n'a pas été poussé. `docs/rapports/FD-CONTRACT-001.md` reste modifié localement, hors commit. La version reste 0.2.0.
