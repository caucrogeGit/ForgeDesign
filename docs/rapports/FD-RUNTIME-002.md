# Rapport — FD-RUNTIME-002

Exécuter l'audit officiel Forge (`forge project:audit`) à la demande depuis Debug Center. Date : 2026-10-14.

## Objectif

Ajouter à Debug Center une seconde commande Forge, lancée uniquement sur un clic explicite : `forge project:audit`. C'est un audit officiel, plus détaillé que le diagnostic et en lecture seule. Il passe par la même frontière de processus que `forge doctor` (FD-RUNTIME-001) et par le même masquage (FD-DEBUG-006).

| Décision | Résultat |
|---|---|
| A. Nouvelle commande runtime ? | Oui |
| B. Commande choisie ? | `project:audit` |
| C. `project:check` inclus ? | Non |
| D. Nouveau Tool ? | Non : cinq Tools |
| E. Runner borné réutilisé ? | Oui : runner privé commun, liste fermée |
| F. Arguments arbitraires permis ? | Non |
| G. Résultat persisté ? | Non |
| H. Graphic Core modifié ? | Non : 134/134 |

## État Git initial

| Élément | Valeur |
|---|---|
| HEAD | `12dd8c7` (FD-DEBUG-006), qui contient FD-ROUTES-021, FD-PERF-001 et FD-RUNTIME-001 |
| `origin/main` | `e411d0c` ; 0 commit en retard, 4 en avance |
| Arbre | Seul `docs/rapports/FD-CONTRACT-001.md` est modifié par l'utilisateur ; il est préservé et hors commit |
| Version | 0.2.0, inchangée |

L'identifiant FD-RUNTIME-002 était libre : il n'apparaissait que comme recommandation dans le rapport FD-DEBUG-006.

## Périmètre

Le ticket ajoute un bouton, un POST, une section de résultat et une fonction publique, `run_forge_project_audit`. Le runner de FD-RUNTIME-001 devient un runner privé commun aux deux commandes. Le ticket ne modifie ni Forge, ni le Bridge, ni le masqueur, ni Project Inspector, ni Route Explorer, ni Entity Explorer, ni Template Viewer.

## Commandes Forge étudiées

| Commande | Ce qu'elle fait (forge-mvc 1.0.0rc9) | Décision |
|---|---|---|
| `doctor` | Exécute `config.py`, importe le moteur d'entités, se connecte à la base | Intégrée (FD-RUNTIME-001) |
| `project:audit` | Lit et analyse les fichiers, sans exécuter le projet | **Intégrée ici** |
| `project:check` | Importe réellement `mvc.routes`, donc les contrôleurs et leurs imports | Reportée |

## Pourquoi project:audit

L'audit couvre neuf familles : structure, configuration, entités, routes, templates, modules, migrations, documentation et tests. Il n'exécute aucun code du projet, ce qui est démontré plus bas. Il complète Project Inspector par le point de vue officiel de Forge, sans les effets de `doctor`.

## Pourquoi project:check est reporté

`project:check` importe `mvc.routes`, donc les contrôleurs et leurs imports transitifs. C'est une frontière d'exécution plus forte que celle de `doctor` pour le code applicatif. Elle mérite un ticket dédié, avec un avertissement spécifique.

## Implémentation officielle Forge inspectée

- `forge.py`, `cmd_project_audit` : refuse (`cli_fail`, code 1) si `app.py` ou `mvc/` manque. Sinon, appelle `run_project_audit(Path.cwd())` puis `print_audit_report`, et fait `sys.exit(1)` si au moins un résultat est en `fail`.
- `cli/project/project_audit.py` (452 lignes) : neuf familles, chacune isolée. Une exception devient `[FAIL] Erreur inattendue`.
- La sortie n'existe qu'en texte ; aucun JSON n'est proposé, ce qui ne remet pas en cause le §42.

## Effets de bord

Projet réel `okproj` (copie de gx8 avec son `.venv` réel) ; commande lancée sous des audit hooks Python (`sys.addaudithook`) :

| Observation | Résultat |
|---|---|
| Ouvertures en écriture (`open` w/a/x/+, `O_WRONLY`, `O_RDWR`, `O_CREAT`) | Aucune |
| `socket.*` | Aucun |
| `subprocess.Popen`, `os.system`, `os.exec*`, `os.posix_spawn`, `os.fork` | Aucun |
| `sqlite3.connect` | Aucun |
| `os.environ` | Inchangé |
| Fichiers du projet | Aucun créé ni modifié (instantané avant/après, `find -newer`) |
| `__pycache__` | Aucun (`-B`) |

Les tests et les navigateurs le confirment : instantané identique avant et après.

## Code projet exécuté ou non

**Aucun code du projet n'est exécuté :**

- aucun des 180 événements `exec` (corps de modules importés) ne vient d'un fichier du projet ;
- aucun module du projet n'apparaît dans `sys.modules` ;
- le seul `compile` sur un fichier du projet est celui de `mvc/routes/__init__.py` par `ast.parse`, qui produit un AST et n'exécute rien.

Les paquets chargés se limitent à `forge.py`, `cli`, `core` (forge-mvc) et `dotenv`.

Deux sentinelles le prouvent dans les tests et les navigateurs :

- un `config.py` qui crée `CONFIG_EXECUTED` : le fichier n'apparaît jamais ;
- un `config.py` qui imprime « CONFIG EXECUTEE » : le texte apparaît dans la sortie de `doctor`, jamais dans celle de l'audit.

Le CLI Forge et les paquets du `.venv` s'exécutent, eux. L'avertissement de la page le dit et précise que ces garanties valent pour forge-mvc 1.0.0rc9.

## Services externes contactés ou non

Aucun : ni réseau, ni base de données, ni sous-processus, ni tests, ni `npm` (sonde vide). `doctor`, lui, appelle `shutil.which("npm")` et ouvre la base.

## Configuration lue

`audit_project_config` fait `dotenv_values(env/example)` puis `dotenv_values(env/dev)` :

- les valeurs sont **chargées en mémoire**, jamais exécutées, et ne modifient pas `os.environ` ;
- seuls servent les quatre contrôles de clés `APP_NAME`, `APP_ROUTES_MODULE`, `DB_NAME` et `DB_HOST` ;
- seuls les **noms** des clés vides sont imprimés.

Test réel : avec `DB_PASSWORD=VerySecret123` et `API_TOKEN=abc123` dans `env/dev`, aucune valeur n'apparaît dans la sortie. `APP_ENV` n'est jamais lu, donc Forge Design ne le fixe pas.

## Codes retour

| Code | Cause | État affiché |
|---|---|---|
| 0 | Aucun `FAIL` (les `WARN` et `INFO` restent possibles : `okproj` donne 3 WARN) | Terminé avec le code 0 : aucun constat FAIL (des avertissements restent possibles) |
| 1 | Au moins un `FAIL`, `cli_fail` (`app.py` ou `mvc/` absent), erreur projet ou base | Terminé avec le code 1 : au moins un constat FAIL, ou erreur de la commande |
| 130, autres | Interruption, autre cause | Terminé avec un autre code retour |
| — | Lancement impossible ou délai dépassé | Échec du lancement ; Audit interrompu : délai dépassé |

## Sorties

Stdout contient, dans l'ordre :

- `Forge project:audit — <version>` ;
- une rubrique par famille, avec des lignes `[OK]`, `[WARN]`, `[FAIL]` ou `[INFO]` ;
- un résumé ;
- `Audit terminé — …`.

Il n'y a ni ANSI ni JSON. Stderr ne reçoit que des erreurs.

Les messages d'exception (JSON, syntaxe) ne citent pas le contenu des fichiers. Les **noms** de fichiers et de dossiers du projet sont imprimés : un dossier d'entité nommé `DB_PASSWORD=VerySecret123`, nom légal énuméré par l'audit, apparaît en clair dans la sortie brute. Il est masqué par FD-DEBUG-006.

## Architecture avant

`run_forge_diagnostic(checked, *, launcher, environ, timeout, limit)` contenait tout le lancement :

- l'argv `DIAGNOSTIC_ARGUMENTS` ;
- `Popen` et les bornes ;
- l'arrêt du groupe ;
- les messages propres au diagnostic.

`web/debug.py` exposait `run_forge_diagnostic_action`, et le gabarit avait une seule section.

## Factorisation du runner

- `_run_forge_command(checked, name, …)` est privé. Il porte tout le cycle : interpréteur, argv, `Popen`, drainage borné, arrêt du groupe, nettoyage et masquage.
- `run_forge_diagnostic` (signature inchangée) et `run_forge_project_audit` (même signature) délèguent avec un nom littéral.
- `_ForgeCommand(arguments, noun, noun_capitalized)` ne porte que l'argv et le libellé des messages.

## Frontière des commandes autorisées

La liste fermée est structurelle :

- `_COMMANDS` est un `MappingProxyType` immuable de deux entrées, `doctor` et `project:audit`.
- Le runner privé reçoit un **nom** et construit l'argv depuis cette table seulement. Tout autre nom (`run`, `db:apply`, `project:check`, `doctor --fix`, chaîne vide) lève `ValueError` avant tout lancement. Le test vérifie que le lanceur n'est jamais appelé.
- Un test AST vérifie que :
  - les deux seuls appels à `_run_forge_command` passent les littéraux `"doctor"` et `"project:audit"` ;
  - ni `_run_forge_command` ni `_COMMANDS` n'apparaissent ailleurs dans `forge_design` ;
  - les seules fonctions publiques `run_*` du module sont les deux commandes.
- HTTP ne transmet rien : la signature des runners ne reçoit que la racine vérifiée, et tout champ ou paramètre donne 400.

## Commande argv

`AUDIT_ARGUMENTS = ("-s", "-B", "-P", "-m", "forge", "project:audit")`. L'argv complet est `[<racine>/.venv/bin/python, *AUDIT_ARGUMENTS]` ; un test vérifie l'égalité exacte, et un autre que le lanceur reçoit cette liste.

## Interpréteur

`project_interpreter(root)` (FD-RUNTIME-001) : `<racine>/.venv/bin/python`. Dossiers sans lien, cible exécutable, aucun repli. S'il est absent : `launch-failed`, « … : audit non lancé. ».

## cwd

La racine canonique vérifiée par `check_forge_root` juste avant le lancement (test : `cwd` reçu par le faux interpréteur).

## Environnement

`child_environment` : `PATH`, `HOME`, `LANG`, `LC_ALL`, `LC_CTYPE`, `TZ`, `TMPDIR`. Un test injecte `PYTHONPATH`, `VIRTUAL_ENV`, `APP_ENV=prod` et `DB_PASSWORD` : aucune de ces variables n'est transmise.

## Timeout

10 s, commun aux deux commandes et non configurable. Mesures : 87 ms sur un petit projet, 118 ms sur 3 883 fichiers. La marge est large et la constante reste inchangée. Message : « Audit interrompu : délai dépassé. ».

## Groupe de processus

L'audit normal ne crée aucun enfant (sonde), mais la garantie est conservée : `SIGKILL` au groupe dans tous les cas. Test : un petit-enfant est tué au délai.

## Bornes stdout/stderr

256 Kio par flux, avec drainage continu au-delà ; « 786432 octets ignorés au-delà de 256 Kio » est affiché (test Web).

## ANSI

`clean_output` est le même (CSI, OSC, contrôles).

## Redaction FD-DEBUG-006

Même `redact_debug_text`, même pipeline : octets → UTF-8 avec remplacement → ANSI et contrôles → masquage → Jinja autoéchappé.

Dans la vraie sortie, `4 entité(s) sans fichier SQL : DB_PASSWORD=VerySecret123, article, …` devient `DB_PASSWORD=[masqué], article, …`.

## Modèle de résultat

`ForgeDiagnosticRun` est conservé tel quel pour les deux commandes (décision C), sans renommage ni alias. Seuls les messages diffèrent (`noun`).

## Debug Center

Une macro Jinja `forge_command` rend les deux sections, `section[data-command="diagnostic"]` et `section[data-command="audit"]`. Chacune a :

- son titre (`h2`) ;
- son explication et son avertissement, fournis par le bloc `call` ;
- ses bornes, son formulaire et son bouton ;
- son erreur et son résultat.

Ordre : Diagnostic Forge, Audit du projet Forge, Journal des erreurs runtime.

Avertissement de l'audit, validé : « L'audit est exécuté avec l'environnement Python du projet (`.venv/bin/python`) dans un processus séparé : le CLI Forge et les paquets installés dans `.venv` s'exécutent. Avec forge-mvc 1.0.0rc9, il lit les fichiers du projet, notamment `env/example` et `env/dev`, sans en afficher les valeurs ; il n'exécute ni `config.py`, ni l'application, ni les tests, et ne contacte aucune base de données. »

## Séparation doctor / audit

- Deux POST : `/debug/forge-diagnostic` et `/debug/forge-audit`.
- Une action privée commune, `_forge_command_action`, qui ne rend son résultat ou son erreur que dans la section visée.
- Tests avec espion :
  - le POST de l'audit n'exécute que l'audit, et inversement ;
  - l'autre section reste « non exécutée » ;
  - le GET suivant revient à « non exécuté » pour les deux.
- Aucun état partagé : un test lance 8 exécutions concurrentes (4 projets, deux commandes) et chacune reçoit son propre argv et son propre `cwd`.

## Sécurité HTTP

Les gardes sont identiques à celles de `doctor` :

- `is_local_action`, sinon 403 (Origin étrangère ou absente) ;
- formulaire encodé, sinon 415 ;
- tout champ ou paramètre (`command`, `args`, `timeout`, `?cwd=`), sinon 400 ;
- `no-store` ;
- `GET /debug/forge-audit` : 405.

## Projet absent

409 « Aucun projet sélectionné : audit non lancé. », dans la section Audit seulement ; aucun processus.

## Projet invalide

`app.py` supprimé après l'ouverture : 409 « Audit non lancé : … » ; aucun processus. Une racine supprimée ou devenue inaccessible suit la même politique, couverte par les tests du diagnostic sur la même action commune.

## Interpréteur absent

200, `launch-failed`, « Interpréteur du projet introuvable ou inutilisable (.venv/bin/python) : audit non lancé. ».

## Lecture seule

Un instantané avant/après a été pris sur :

- le faux interpréteur (sortie hostile) ;
- le vrai audit (y compris `__pycache__` et la sentinelle `config.py`) ;
- les deux projets du scénario navigateur.

Aucune différence. Forge Design n'écrit rien ; l'audit non plus.

## Tests Python

`tests/test_runtime_audit.py` (16 tests) :

- argv, `cwd`, environnement et absence d'`APP_ENV` ;
- argv reçu par le lanceur pour les deux commandes ;
- liste fermée structurelle (table immuable, noms refusés sans lancement, AST, API publique) ;
- codes 0, 1 et 3 ;
- sorties hostiles et secrets ;
- délai et groupe tué ;
- bornes ;
- interpréteur absent ;
- projet intact ;
- concurrence ;
- **vrai `project:audit`** :
  - venv lié à forge-mvc 1.0.0rc9 ;
  - `forge.py` hostile, `config.py` sentinelle ;
  - secrets dans `env/dev` ;
  - code 0, « aucun problème détecté », sentinelle absente, aucun `__pycache__`, instantané identique ;
- **vrai audit en échec** : `relations.json` invalide, code 1, nom d'entité sensible masqué ;
- **`-s`** : venv `--system-site-packages` avec un `.pth` du site utilisateur, jamais exécuté, pour l'audit comme pour `doctor`.

Les 27 tests de FD-RUNTIME-001 restent verts sans modification.

## Tests Web

`tests/test_web_runtime_audit.py` (7 tests, vrai serveur HTTP) :

- GET sans exécution, deux boutons, avertissement propre à l'audit, ordre des sections ;
- chaque POST ne lance que sa commande, aucun mélange, rien n'est persisté, projet intact ;
- libellé du code 0 ;
- gardes, sans projet, projet invalide ;
- sortie hostile échappée, secrets, délai, troncature ;
- interpréteur absent ;
- cinq Tools.

## Mutations

Script hors dépôt, lancé depuis le scratchpad. Pour chaque mutation : une ou plusieurs éditions, `pytest -x` sur cinq fichiers de tests runtime et Debug Center, restauration à l'octet, empreinte vérifiée. Résultat : **21/21 tuées**.

| Mutation | Tuée par |
|---|---|
| Audit lancé au GET | `test_get_never_runs_and_shows_both_commands` (et 405) |
| Action audit qui appelle `doctor` | `test_each_post_runs_only_its_command` |
| Action `doctor` qui appelle l'audit | `test_each_post_runs_only_its_command` |
| Runner audit qui appelle `doctor` | `test_command_cwd_and_environment_are_fixed` |
| argv `project:check` au lieu de `project:audit` | idem |
| `-P` retiré | idem |
| `-B` retiré | idem |
| `-s` retiré | idem ; tuée aussi **à elle seule** par `test_user_site_pth_is_never_executed` (vérifié séparément) |
| `cwd` incorrect | idem |
| `shell=True` | idem |
| Champ HTTP accepté | `test_guards_and_projects` |
| Timeout ignoré | `test_timeout_kills_the_group_with_audit_message` |
| stdout non borné | `test_outputs_are_bounded` |
| stderr non borné | idem |
| Masquage retiré | `test_hostile_and_secret_outputs` |
| Résultat persisté (dernier résultat réaffiché au GET) | `test_each_post_runs_only_its_command` |
| Audit exécuté sans projet | `test_guards_and_projects` |
| Audit exécuté sur un projet non Forge | `test_guards_and_projects` |
| Commande arbitraire acceptée (nom inconnu → argv construit) | `test_closed_command_list_is_structural` |
| Liste fermée contournée (table mutable) | idem |
| Message d'audit générique (« Diagnostic interrompu ») | `test_timeout_kills_the_group_with_audit_message` |

La mutation « arguments HTTP transmis » n'a pas d'équivalent distinct : aucun canal ne relie la requête à l'argv, puisque les runners ne reçoivent que la racine vérifiée. Elle se réduit à « champ HTTP accepté », tuée.

## Chromium

Conditions :

- roue 0.2.0 dans un venv neuf, vraie commande `forge-design`, HOME isolé ;
- projets réels avec leur `.venv` (forge-mvc 1.0.0rc9) :
  - `auditproj` : audit en code 0 avec 3 WARN. Il contient des secrets dans `env/dev`, une entité `DB_PASSWORD=VerySecret123` et un `config.py` qui imprime « CONFIG EXECUTEE » avec des secrets ;
  - `auditfail` : `relations.json` invalide, code 1.

Scénario, 8/8 :

1. GET : les deux sections sont « non exécutées », deux boutons distincts, avertissement propre à l'audit ;
2. clic réel sur « Exécuter l'audit Forge » : vrai `project:audit`, code 0, libellé avec avertissements possibles, nom sensible masqué, aucun « CONFIG EXECUTEE », diagnostic toujours non exécuté ;
3. rechargement : les deux sections sont « non exécutées » ;
4. clic réel sur « Exécuter le diagnostic Forge » : vrai `doctor`, sortie de `config.py` masquée (`DB_PASSWORD=[masqué] vers mysql://roger:[masqué]@…`), audit toujours non exécuté ;
5. projet en échec : audit en code 1, libellé « au moins un constat FAIL » ;
6. retour à Project Inspector ;
7. aucune erreur JavaScript ;
8. aucun fichier modifié dans les deux projets.

Aucune valeur sensible dans le HTML à aucune étape. Aller-retour du clic sur l'audit : environ 216 ms, dont 0,09 s d'audit.

## Firefox

Même scénario, 8/8. Aller-retour : 440 ms pour l'audit, au premier POST de la session.

## Sans JavaScript

Firefox avec `javascript.enabled=false` (fenêtre agrandie, clics BiDi réels) :

- l'audit passe par un POST natif, le diagnostic reste intact ;
- puis le diagnostic passe par un POST natif, l'audit reste intact ;
- aucune valeur sensible dans les textes ni les attributs (XPath).

Deux POST au journal du serveur.

## Performance

Médianes sur 10 exécutions, même argv et même environnement :

| Projet | Fichiers hors `.venv` | `project:audit` direct | Via Forge Design | Surcoût |
|---|---:|---:|---:|---:|
| `auditproj` | 44 | 87 ms (pire 91) | 89 ms (pire 95) | +1,6 ms |
| Grand projet (2 000 templates, 300 contrôleurs, 200 entités, 500 migrations, 200 tests) | 3 883 | 118 ms (pire 126) | 118 ms (pire 136) | −0,4 ms (bruit) |

Le démarrage de Python et du CLI domine. Un POST ne déclenche que la vérification de racine et la lecture habituelle du journal.

## ToolRegistry

Cinq Tools, inchangés (test).

## Graphic Core

Aucune modification ; 134/134 tests Node.

## Modules externes

Circuit et Flowchart non modifiés. Le scénario Chromium complet, avec `--module forge_design_circuit --module forge_design_flowchart`, donne 8/8.

## Dette / limites

- **Version de forge-mvc.** Les garanties de lecture seule valent pour forge-mvc 1.0.0rc9 ; le CLI vient du `.venv` du projet. Une autre version peut se comporter autrement, et l'avertissement le dit.
- **Liens symboliques.** Forge suit ceux du projet (lectures et `exists` hors du projet possibles). Forge Design ne le contrôle pas ; aucun contenu n'est affiché, hormis des messages d'erreur courts.
- **Noms de fichiers.** Ils sont imprimés tels quels : le masquage couvre les formes reconnues, sans exhaustivité (FD-DEBUG-006).
- **Code 1 ambigu.** Constat `FAIL`, `cli_fail` et erreur projet ou base partagent le même code, comme pour `doctor`.
- **Commandes séquentielles.** Deux commandes se lancent l'une après l'autre ; il n'y a pas de bouton « tout lancer », volontairement.

## Recommandation ticket suivant

Deux pistes :

- **FD-RUNTIME-003 — `project:check`.** Étudier son exécution avec un avertissement propre : il importe `mvc.routes`, donc les contrôleurs. À intégrer à la même liste fermée, uniquement après la même démonstration (audit hooks, sentinelles) et une décision explicite sur l'exécution du code applicatif.
- **Intégration applicative (Phase 12)**, si `project:check` est jugé hors de portée.

## Fichiers créés

- `tests/test_runtime_audit.py`
- `tests/test_web_runtime_audit.py`
- `docs/rapports/FD-RUNTIME-002.md`

## Fichiers modifiés

- `forge_design/forge/runtime_diagnostics.py`
- `forge_design/web/debug.py`
- `forge_design/web/server.py`
- `forge_design/web/templates/debug.html`
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
| `pytest` (suite complète) | 4 987 passed |
| `node --test tests/js/graphics/*.test.mjs` | 134/134 |
| Roue 0.2.0, venv neuf | `pip check` OK |
| Chromium, Firefox, Chromium + modules | 8/8 chacun, vrais `project:audit` et `doctor` |
| Firefox sans JavaScript | OK, deux POST natifs |
| Mutations | 21/21 tuées |

## État Git final

Un seul commit : `feat: exécuter l'audit Forge à la demande (FD-RUNTIME-002)`, au-dessus de `12dd8c7`. Il n'a pas été poussé. `docs/rapports/FD-CONTRACT-001.md` reste modifié localement, hors commit. La version reste 0.2.0.
