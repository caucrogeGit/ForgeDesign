# Rapport — FD-REALPREVIEW-007

Empêcher la preview réelle d'écrire du bytecode Python dans le projet (correction d'ACC-003). Date : 2026-10-15.

## Objectif

Corriger ACC-003 (MINOR, relevé par FD-ACCEPTANCE-001) : la preview réelle lançait le projet sans `-B`, et Python écrivait des `__pycache__` dans le projet.

Garantie apportée : la preview réelle exécute le projet sans écrire aucun bytecode Python dans le projet, et rien d'autre ne change dans son comportement.

| Décision | Résultat |
|---|---|
| A. Corrige ACC-003 ? | Oui |
| B. Ajouter `-B` ? | Oui, et seulement `-B` |
| C. Modifier `-I` ? | Non |
| D. Modifier `-u` ? | Non |
| E. Nettoyer les pycache existants ? | Non : ils sont conservés et jamais modifiés |
| F. Runner refactorisé ? | Non : un seul token ajouté à l'argv |
| G. UI modifiée ? | Non |
| H. Nouveau Tool ? | Non : cinq Tools |
| I. Graphic Core modifié ? | Non : 134/134 |
| J. Gate SéquenCiel ouvert ici ? | Non : FD-ACCEPTANCE-002 en décidera |

## État Git initial

| Élément | Valeur |
|---|---|
| HEAD | `561ff93` (FD-EDITOR-007), qui contient FD-ACCEPTANCE-001 |
| `origin/main` | `e411d0c` ; 0 commit en retard, 9 en avance |
| Arbre | `docs/rapports/FD-CONTRACT-001.md` est modifié par l'utilisateur ; il est préservé et hors commit. `FD-EDITOR-007-VERIFICATION.md` et son dossier sont non suivis, d'une autre origine ; ils ne sont ni touchés ni committés. |
| Collision | Aucune : FD-REALPREVIEW-007 n'apparaissait que comme recommandation |
| Version | 0.2.0, inchangée |

**Travail concurrent.** Pendant ce ticket, une autre partie a modifié sur disque `forge_design/design/io.py` et `forge_design/web/editor.py`, et créé `forge_design/design/locking.py`. Il s'agit d'un verrou pour `write_design`, hors périmètre.

Ce travail n'est ni modifié ni committé ici. Pour qu'il ne contamine pas les preuves, toute la qualification a été refaite dans un **worktree isolé** (HEAD et les seuls fichiers de ce ticket) : tests, mutations, mesures, roue, acceptance.

Une première acceptance « avant » avait embarqué `locking.py` dans la roue. Elle a été écartée et rejouée dans le worktree, avec les mêmes 12 entrées.

## Défaut ACC-003

Une simple utilisation de la preview réelle laissait des `__pycache__/*.pyc` dans le projet :

- à la racine (`app`, `bootstrap`, `config`) ;
- dans `mvc/controllers` ;
- dans `mvc/routes` ;
- dans `optins`.

Le `.gitignore` du squelette les ignore et aucune donnée n'est perdue, mais c'est une écriture évitable de Forge Design. Debug Center lançait déjà ses commandes avec `-B`.

## Reproduction avant correction

**En Python**, avec le vrai contrôleur, un vrai squelette rc9 et son vrai `.venv` : `start`, puis `running`, `GET /` à 200, `stop`, et un instantané complet du projet avant et après.

| Cas | Changements |
|---|---|
| Projet vierge | 11 ajouts : 4 dossiers `__pycache__` et 7 `.pyc`. S'y ajoute le mtime de `mvc/controllers`, `mvc/routes` et `optins`. Identique pendant `running` et après `stop`. |
| Caches préexistants | 7 ajouts, et le `.pyc` **périmé** de `config.py` est **réécrit** |

Les 9 nouveaux tests et assertions d'instantané ont été lancés avant la correction : 9 échecs, et le témoin passe.

**Acceptance ciblée**, sur la roue, dans le worktree, avec `ONLY="preview réelle"` : A-preview est en **ÉCART, avec 12 entrées `__pycache__`**, dans Chromium, dans Firefox et à l'arrêt par Ctrl+C. Ce sont les 12 de FD-ACCEPTANCE-001 : A-preview a un contrôleur de plus que le squelette.

## Commande avant

Lue dans `/proc/<pid>/cmdline` de l'enfant réel :

```text
<projet>/.venv/bin/python -I -u <forge_design>/real_preview/child_bootstrap.py --port <port>
```

## Commande après

```text
<projet>/.venv/bin/python -I -B -u <forge_design>/real_preview/child_bootstrap.py --port <port>
```

La seule modification de code est `"-B"`, ajouté entre `"-I"` et `"-u"` dans `RealPreviewController._launch_plan`. Le tuple passe sur plusieurs lignes parce qu'il dépassait 88 colonnes.

## Pourquoi -B

`-B` empêche Python d'écrire des `.pyc` : rien n'est créé ni réécrit. Un `.pyc` existant et à jour peut encore être lu.

La politique est exprimée dans l'argv, comme pour les commandes de Debug Center, et non par `PYTHONDONTWRITEBYTECODE`. Sous `-I`, cette variable est d'ailleurs **ignorée** (`sys.dont_write_bytecode` reste `False`, vérifié). La remplacer par la variable ne serait donc pas équivalent : la mutation correspondante est tuée par le comportement, pas seulement par le contrat.

Aucune autre option (`-s`, `-P`, `-E`, `-S`) n'est ajoutée.

## Runner

L'architecture est inchangée : interpréteur du projet, argv, `child_bootstrap.py`, `/health`, proxy. `project_python.py`, la liste blanche d'environnement et `APP_ENV=dev` sont réutilisés tels quels. Il n'y a ni factorisation d'argv, ni partage avec Debug Center.

## child_bootstrap

Comportement inchangé : `import app`, `create_wsgi_app`, garde `Host`, bind `127.0.0.1`. Seule la docstring, qui citait la commande, passe à `-I -B -u`.

`tests/test_real_preview_bootstrap.py` continue de lancer le bootstrap directement en `-I -u` : il qualifie le bootstrap, pas la politique d'argv du contrôleur.

## Environnement

Liste blanche inchangée, avec `APP_ENV=dev`. Le test d'argv vérifie que `PYTHONDONTWRITEBYTECODE` n'est **pas** dans l'environnement transmis, et `/proc/<pid>/environ` le confirme chez l'enfant réel.

## Start

`start` passe à `running` (tests réels). Projet identique **pendant** `running`, ce qui exclut la fausse correction qui créerait les caches puis les supprimerait à l'arrêt.

## Readiness

La sonde `/health` est inchangée : les tests de sonde existants passent sans modification.

## Proxy

Le proxy est inchangé. Le test réel de bout en bout reçoit un 200 en HTML par le proxy, un 405 sur `POST`, et le proxy est fermé après l'arrêt. L'acceptance fait désormais un **GET** sur l'URL de l'iframe : 200, 1 531 octets HTML, dans les deux navigateurs.

## Stop

Arrêt en 50 ms environ ; aucun enfant ni proxy restant (`no_survivors`). Projet identique après l'arrêt.

## Restart

`start`, `stop`, `start`, `stop` : aucun changement, aucun bytecode (`test_restart_writes_no_bytecode`).

## Changement projet

Preview active, puis ouverture d'un autre projet : le premier est arrêté, et **les deux** projets restent identiques (`test_real_switch_project_stops_previous`). La fermeture du projet est couverte de même (`test_real_close_project`).

## Fermeture serveur

Preview active, puis sortie du serveur (`server_close`) : proxy fermé, enfant arrêté, projet identique (`test_real_server_shutdown_while_running`). En acceptance, l'arrêt par Ctrl+C (SIGINT) laisse A-preview **conforme**, alors qu'il était en ÉCART avant correction ; aucun processus ne reste.

## Snapshot

Deux sondes sont utilisées.

**Tests** : `tree_snapshot` (`tests/real_preview_support.py`) enregistre pour chaque entrée le type, la taille, le `mtime_ns` et le SHA-256 (ou la cible d'un lien). Rien n'est exclu, ni `__pycache__`, ni `.pyc`, ni le `.venv` du projet. Les dossiers et la racine portent leur mtime : un `__pycache__` créé puis supprimé laisse une trace sur son parent.

**Acceptance** : `probes.py snapshot` est inchangé (`.venv` exclu) et signale tout `__pycache__` ajouté comme suspect. Il est désormais appliqué aussi autour de l'étape `shutdown`.

**Témoin positif** : le même lancement sans `-B` doit faire apparaître des `__pycache__` dans les quatre zones et réécrire le `.pyc` périmé. Cela prouve que la sonde voit le défaut qu'elle prétend exclure.

## __pycache__

Après correction, aucun `__pycache__` ni `.pyc` n'apparaît dans le projet, ni pendant `running`, ni après aucun des scénarios (tests réels et acceptance). Les zones importées sont `app.py`, `bootstrap.py`, `config.py`, `mvc/controllers`, `mvc/routes` et `optins`.

## Pycache préexistant

Trois catégories préparées avant le démarrage :

- à jour (`app.py`) ;
- **périmé** (`config.py` modifié après compilation) ;
- module jamais importé (`optins/jamais_importe.py`).

Après démarrage, `GET` et arrêt, les trois sont présents et identiques en octets comme en `mtime_ns`. Forge Design ne nettoie rien et ne modifie rien. Sans `-B`, le témoin montre que le cache périmé était réécrit.

## Effets du code applicatif

`-B` ne rend pas la preview lecture seule : le projet exécuté reste libre d'écrire (logs, base de données, fichiers).

Le contrat devient : Forge Design n'écrit plus de bytecode Python dans le projet par le simple fait de démarrer la preview ; le code applicatif exécuté reste libre de produire ses propres effets de bord. Cette formulation est reprise dans `docs/preview/real-preview-contract.md` (« Bytecode — FD-REALPREVIEW-007 »).

## Tests Python

`tests/test_real_preview_bytecode.py` (nouveau, 5 tests réels) :

- témoin sans `-B` (bytecode dans les quatre zones, cache périmé réécrit) ;
- argv réel lu dans `/proc/<pid>/cmdline` (`-I -B -u` avant le bootstrap) et environnement sans `PYTHONDONTWRITEBYTECODE` ;
- projet identique pendant `running` et après `stop` ;
- redémarrage ;
- pycache préexistant (trois catégories).

`tests/test_real_preview_controller.py` : le test d'argv exact exige `-I`, `-B`, `-u` dans cet ordre avant le bootstrap, et vérifie l'absence de `PYTHONDONTWRITEBYTECODE` dans l'environnement.

## Tests Web

`tests/test_web_real_preview.py` : contrôle d'instantané ajouté aux 4 tests réels existants (bout en bout avec proxy à 200, changement de projet, fermeture du projet, fermeture du serveur).

## Mutations

Les mutations sont appliquées dans le worktree isolé ; chaque fichier est restauré à l'octet et vérifié par empreinte. Résultat : **6/6 tuées**.

| Mutation | Nature | Tuée par |
|---|---|---|
| `-B` retiré | **Comportementale** | 4 tests d'instantané de `test_real_preview_bytecode`, 4 tests réels Web ; aussi l'argv |
| `-B` après `child_bootstrap.py` | **Comportementale** | Le bootstrap refuse l'argument (sortie 2) : `start` échoue, 20 échecs dont tous les tests réels |
| `-B` remplacé par `PYTHONDONTWRITEBYTECODE` | **Comportementale** et contractuelle | Variable ignorée sous `-I` : bytecode écrit, tests d'instantané en échec ; aussi l'argv exact et la liste blanche d'environnement |
| Instantané ignorant `__pycache__` | **Comportementale** (sonde) | Le témoin sans `-B` |
| Nettoyage à l'arrêt au lieu de prévention | **Comportementale** | Instantané **pendant** `running`, pycache préexistant supprimé, 4 tests réels Web |
| Ordre `-B -I -u` | **Contractuelle** | Seulement les 2 tests d'argv exact (`test_start_command_and_running`, `test_real_child_argv_is_explicit`) |

L'ordre `-B -I -u` n'a pas d'effet fonctionnel ici. Cette mutation protège le contrat d'argv documenté ; elle ne prouve rien du comportement.

## Chromium

Acceptance ciblée par `scripts/acceptance/run.sh`, avec `ONLY="preview réelle|modules"` et les étapes `wheels install projects browsers shutdown` :

- roue 0.2.0 (166 fichiers, 34 ressources vérifiées), venv neuf hors ligne, `pip check` OK ;
- étape preview réelle : démarrage, `running`, iframe sur l'origine dédiée, **GET de l'URL de l'iframe à 200**, arrêt, proxy fermé, redémarrage, changement de projet qui arrête la preview ;
- instantanés des 10 projets conformes, **A-preview compris**, avec 0 ajout, 0 modification et 0 mtime modifié ;
- aucun processus restant.

Les messages de console sont les polices externes bloquées par la CSP du squelette ; c'est attendu et non corrigé.

## Firefox

Mêmes étapes, toutes OK : A-preview conforme et aucun processus restant. La console montre le même blocage CSP des polices externes.

**Sans JavaScript** : non rejoué, car hors du contrat actuel de la preview réelle. Le ticket porte sur la politique de lancement de Python, pas sur l'accessibilité sans JavaScript.

## Performance

Mesures de `start` jusqu'à `running`, puis de `stop`, avec le vrai contrôleur et un intervalle de sonde de 10 ms pour la résolution. La variante « avant » est le même lancement sans `-B`.

| Mesure | Avant : médiane / pire | Après : médiane / pire |
|---|---|---|
| Démarrage **répété** (15 fois, même projet) | 119,5 / 142,7 ms | 131,8 / 177,9 ms |
| Démarrage **froid contrôlé** (7 fois, caches remis à zéro avant chaque lancement) | 132,2 / 144,5 ms | 132,1 / 133,8 ms |
| Arrêt | 50,4 / 50,5 ms | 50,4 / 50,5 ms |

Les deux populations ne sont pas comparables naïvement :

- **À froid**, le coût de `-B` est nul.
- **En répété**, l'écart d'environ 12 ms est l'avantage artificiel de l'ancien lancement, qui relisait les `.pyc` qu'il avait lui-même écrits dans le projet (4 `__pycache__` restés à la fin). Avec `-B`, chaque démarrage recompile les quelques modules du projet ; les `.pyc` de Forge dans le site-packages restent lus.

## ToolRegistry

Cinq Tools, inchangés.

## Graphic Core

Aucune modification ; 134/134 tests Node.

## Modules externes

Circuit et Flowchart ne sont pas modifiés (0 changement dans leurs dépôts). Validation légère : l'étape « modules » de l'acceptance (navigation, ressources, actions, isolation des assets) passe dans Chromium et Firefox.

## Impact sur ACC-003

**ACC-003 est corrigé.** A-preview passe de 12 entrées `__pycache__` à un instantané conforme, dans Chromium, dans Firefox et à l'arrêt par Ctrl+C. Les tests réels démontrent l'absence de bytecode sur tout le cycle de vie : démarrage, `running`, arrêt, redémarrage, changement de projet, fermeture du projet, fermeture du serveur.

Le rapport FD-ACCEPTANCE-001 n'est pas modifié : il reste l'historique du rejet. ACC-004 (FD-EDITOR-007) et ACC-003 sont désormais corrigés. Le gate SéquenCiel reste **fermé** jusqu'à FD-ACCEPTANCE-002.

## Dette / limites

- **Pas de lecture seule.** `-B` ne couvre que le bytecode : le code applicatif garde ses effets de bord (logs, base de données, fichiers). Le contrat de la preview le disait déjà ; il le précise désormais.
- **Pas de nettoyage.** Les caches laissés par une version antérieure, ou par un autre outil, restent en place. C'est voulu : Forge Design n'est pas un nettoyeur de bytecode.
- **Démarrage répété.** Environ 12 ms de recompilation des modules du projet par démarrage, au lieu de relire des caches écrits par Forge Design.
- **Sans JavaScript.** Non qualifié, car hors contrat.
- **Travail concurrent non committé.** Le verrou de `write_design` (`io.py`, `editor.py`, `locking.py`) reste sur disque, hors de ce commit. Il relève de son propre ticket.

## Recommandation ticket suivant

**FD-ACCEPTANCE-002** : rejouer `scripts/acceptance/run.sh` en entier (toutes les étapes, sans `ONLY`) sur la roue 0.2.0, pour décider du gate SéquenCiel. Le kit vérifie désormais aussi le GET de l'iframe et l'instantané d'A-preview au Ctrl+C.

## Fichiers créés

- `tests/test_real_preview_bytecode.py`
- `docs/rapports/FD-REALPREVIEW-007.md`

## Fichiers modifiés

- `forge_design/real_preview/controller.py` : `-B` dans l'argv
- `forge_design/real_preview/child_bootstrap.py` : docstring seulement
- `tests/real_preview_support.py` : `tree_snapshot`, `tree_changes`
- `tests/test_real_preview_controller.py` : argv exact, environnement
- `tests/test_web_real_preview.py` : instantanés dans les 4 tests réels
- `scripts/acceptance/scenario.mjs` : GET de l'iframe, proxy fermé après l'arrêt
- `scripts/acceptance/run.sh` : instantané et comparaison d'A-preview autour de `shutdown`
- `docs/preview/real-preview-contract.md` : commande, `-B`, section « Bytecode »
- `docs/02-architecture.md` : commande de la preview réelle, une ligne
- `docs/03-roadmap.md` : ACC-003 corrigé

## Validation finale

Toutes les commandes ci-dessous ont été lancées dans le worktree isolé (HEAD et les fichiers de ce ticket).

| Commande | Résultat |
|---|---|
| `python -m compileall -q forge_design tests` | OK |
| `ruff check forge_design tests scripts` | All checks passed |
| `ruff format --check .` | 443 fichiers formatés |
| `pyright` (strict) | 0 erreur, 0 avertissement |
| `git diff --check` | OK |
| `pytest` (suite complète) | 5 097 passed |
| `node --test tests/js/graphics/*.test.mjs` | 134/134 |
| `mkdocs build --strict` | Sans objet (MkDocs non configuré) |
| Roue 0.2.0, venv neuf, hors ligne | `pip check` OK ; la roue installée contient `-B` |
| Acceptance ciblée avant correction | A-preview en ÉCART, 12 `__pycache__` (Chromium, Firefox, Ctrl+C) |
| Acceptance ciblée après correction | A-preview conforme (Chromium, Firefox, Ctrl+C), 10 projets conformes, modules OK, aucun processus restant |
| Mutations | 6/6 tuées (5 comportementales, 1 contractuelle) |

## État Git final

Un seul commit : `fix: empêcher la preview réelle d'écrire du bytecode (FD-REALPREVIEW-007)`, au-dessus de `561ff93`. Il n'a pas été poussé.

Restent hors commit, sur disque :

- `docs/rapports/FD-CONTRACT-001.md`, modifié par l'utilisateur ;
- le travail concurrent sur le verrou de `write_design` ;
- les fichiers de vérification de FD-EDITOR-007.

La version reste 0.2.0.
