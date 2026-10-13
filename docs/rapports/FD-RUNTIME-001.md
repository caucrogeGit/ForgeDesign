# Rapport — FD-RUNTIME-001

Exécuter à la demande le diagnostic officiel Forge (`forge doctor`) depuis Debug Center. Date : 2026-10-13.

## Objectif

Permettre de lancer, sur demande explicite, le diagnostic officiel de Forge sur le projet ouvert, puis d'en afficher le résultat dans Debug Center. Forge Design ne réimplémente aucun contrôle. Le diagnostic tourne dans un sous-processus séparé et borné, jamais dans le processus serveur.

| Décision | Résultat |
|---|---|
| A. Nouveau Tool ? | Non : cinq Tools |
| B. Exécution automatique ? | Non : `POST` explicite seulement, jamais au `GET` |
| C. Sous-processus ? | Oui : `Popen`, nouvelle session, groupe tué |
| D. Import du projet dans Forge Design ? | Non |
| E. Écriture dans le projet ? | Non : vérifié par instantané (tests, navigateurs) |
| F. Graphic Core modifié ? | Non : 0 diff, 134 tests Node |
| G. Action explicite de l'utilisateur ? | Oui : bouton « Exécuter le diagnostic Forge » |

## État Git initial

| Élément | Valeur |
|---|---|
| HEAD | `a34ee3f` (FD-PERF-001) |
| `origin/main` | `e411d0c` ; 0 commit en retard, 2 en avance (FD-ROUTES-021, FD-PERF-001, non poussés) |
| Version | `forge-design 0.2.0`, inchangée |
| Arbre | Seul `docs/rapports/FD-CONTRACT-001.md` est modifié par l'utilisateur ; il est préservé et hors commit |
| Modules | ForgeDesign-Circuit et ForgeDesign-Flowchart : arbres propres, non modifiés |

L'identifiant FD-RUNTIME-001 était libre.

## Périmètre

Le ticket couvre une action unique : `forge doctor`, lancé avec l'interpréteur du projet (`<racine>/.venv/bin/python`). Ce choix (B) a été validé explicitement par l'utilisateur, en dérogation au §35, car l'interpréteur est déterminé par Forge Design et jamais reçu par HTTP.

Hors périmètre :

- les autres commandes Forge ;
- le format structuré (le diagnostic n'en a pas) ;
- la persistance du résultat ;
- un délai configurable ;
- l'intégration à la synthèse de Project Inspector.

## Diagnostic officiel Forge inspecté

forge-mvc 1.0.0rc9 :

- `forge.py` expose `cli_entrypoint` ;
- `cmd_doctor` appelle `run_all(Path.cwd())`, puis `print_report`, puis `sys.exit(1)` si au moins un contrôle est en `FAIL` ;
- `cli/project/doctor.py` contient seize contrôles : Python, environnement, structure MVC, entités, migrations, i18n, templates, modules, registre des opt-ins, MFA, RBAC, certificats SSL, Node.js/npm, base de données, sécurité prod et code engendré ;
- chaque contrôle est isolé : une exception devient `[FAIL] Erreur inattendue`.

## Commande réelle

```text
<racine>/.venv/bin/python -s -B -P -m forge doctor      cwd = racine Forge vérifiée
```

`-I` a été écarté par l'utilisateur. Les trois options retenues sont justifiées par des constats :

| Option | Constat sans l'option | Conséquence |
|---|---|---|
| `-B` | Écriture de `__pycache__/config.cpython-313.pyc` dans le projet | Le projet serait modifié, ce qui est bloquant (§107) |
| `-P` | Un `forge.py` placé à la racine du projet s'exécute à la place du CLI officiel | Détournement de la commande |
| `-s` | Le site-packages de l'utilisateur est chargé | Environnement non maîtrisé |

Avec `-s -B -P`, un `config.py` qui importe un module local du projet fonctionne toujours : le diagnostic ajoute lui-même la racine à `sys.path` au chargement de la configuration.

## Effets de bord

Projets réels (copie de gx8 avec `.venv` réel : forge-mvc, forge-mvc-sqlite, forge-mvc-entities 1.0.0rc9) :

- aucun fichier créé ni modifié (instantané taille + mtime avant/après), y compris après des exécutions en navigateur ;
- aucune base SQLite créée : le backend ouvre avec `create=False`, et le contrôle rapporte un avertissement « Aucune base SQLite… » ;
- aucun fichier temporaire observé hors du projet.

## Import / exécution de code projet

| Le diagnostic… | Détail |
|---|---|
| exécute | `config.py` (`exec_module`), donc tout ce qu'il importe, et `load_dotenv` sur `env/` |
| importe | `forge_mvc_entities` (validation de `mvc/entities`), le backend de base de données installé, des modules du CLI |
| se connecte | à la base configurée (`get_backend().get_connection()`) |
| cherche | `npm` dans `PATH` (`shutil.which`, sans l'exécuter) |
| lit en texte | les sources `.py` (indices MFA et RBAC), les templates, les migrations, `forge_modules.json` et les certificats |
| n'importe pas | `app.py`, les contrôleurs ; il ne démarre aucun serveur |

Le diagnostic peut donc exécuter du code du projet. L'avertissement validé est affiché avant le bouton : « Le diagnostic Forge est exécuté avec l'environnement Python du projet (`.venv/bin/python`) dans un processus séparé. Il exécute la configuration du projet et peut donc exécuter son code ou accéder aux services qui y sont configurés, notamment la base de données. »

## Codes retour

| Code | État | Libellé |
|---|---|---|
| 0 | `succeeded` | Réussi (code 0) |
| 1 | `checks-failed` | Terminé avec le code 1 : au moins un contrôle en échec, ou erreur de la commande |
| autre (dont 130) | `exit-code` | Terminé avec un autre code retour |
| — | `launch-failed` | Échec du lancement (interpréteur absent ou inutilisable, `OSError`) |
| — | `timed-out` | Diagnostic interrompu : délai dépassé |

Le code 1 couvre aussi `cli_error`. Forge Design ne peut pas distinguer ce cas sans lire le texte, et il ne le lit pas : le libellé le dit.

## Format stdout / stderr

La sortie standard contient le texte lisible `Forge doctor — <version>`, une ligne `[OK]`, `[WARN]`, `[FAIL]` ou `[SKIP]` par contrôle, puis un bilan. Elle n'a ni JSON ni couleurs ANSI. La sortie d'erreur ne reçoit que ce que le code du projet ou les bibliothèques y écrivent. Il n'existe pas de format structuré officiel, donc pas de mutation §127.

## Architecture

| Fichier | Rôle |
|---|---|
| `forge/project_python.py` (nouveau) | `project_interpreter(root)` et `child_environment(source)`, liste blanche ; extraits de `real_preview/controller.py` sans changement de comportement |
| `forge/runtime_diagnostics.py` (nouveau) | Runner : `run_forge_diagnostic(checked)`, `ForgeDiagnosticRun`, `clean_output` |
| `limits.py` | `FORGE_DIAGNOSTIC_TIMEOUT_SECONDS = 10.0`, `MAX_FORGE_DIAGNOSTIC_OUTPUT_BYTES = 256 Kio` |
| `web/debug.py` | `run_forge_diagnostic_action` ; `show_debug` et l'action partagent `_render_debug` |
| `web/server.py` | Route `POST /debug/forge-diagnostic` (`public`, `csrf=False` comme les autres actions locales, `no_store`) |
| `web/templates/debug.html` | Section « Diagnostic Forge » avant le journal |
| `real_preview/controller.py` | Utilise `project_python` ; ajoute toujours `APP_ENV=dev` |

## Runner

`run_forge_diagnostic(checked, *, launcher=None, environ=None, timeout=10.0, limit=256 Kio)` reçoit une `CheckedForgeRoot` vérifiée par l'appelant. `launcher` et `environ` ne sont injectables que depuis Python, pour les tests ; HTTP n'y a aucun accès. Le runner ne lève pas d'exception pour les cas prévus : il retourne toujours un `ForgeDiagnosticRun`.

## Frontière de processus

Le projet n'est jamais importé dans Forge Design : `sys.path`, `os.environ` et le dossier courant du serveur restent intacts. Un `sys.exit`, un import cassé ou un état global du diagnostic ne touchent que l'enfant. Ce n'est pas un bac à sable du système d'exploitation : l'enfant a les droits de l'utilisateur.

## Commande argv

`argv = (str(<racine>/.venv/bin/python), "-s", "-B", "-P", "-m", "forge", "doctor")`. L'appel est `subprocess.Popen(list(argv), shell=False, start_new_session=True, stdin=DEVNULL, stdout=PIPE, stderr=PIPE)`. Un test statique (AST et texte) interdit `shell=True`, `os.system`, `os.popen`, `eval(` et `exec(` dans le module.

## Working directory

Le dossier courant est `checked.root`, la racine canonique vérifiée juste avant le lancement. Le faux interpréteur des tests le confirme.

## Environnement

La liste blanche est construite positivement : `PATH`, `HOME`, `LANG`, `LC_ALL`, `LC_CTYPE`, `TZ`, `TMPDIR`. Ni `PYTHONPATH`, ni `PYTHONHOME`, ni `VIRTUAL_ENV`, ni aucune autre variable n'est transmise ; un test injecte `PYTHONPATH`, `DB_ADMIN_PASSWORD` et `API_TOKEN` et vérifie leur absence. `APP_ENV` n'est pas fixé : le diagnostic suit son défaut `dev`, comme en terminal. La preview réelle conserve son `APP_ENV=dev`. L'environnement n'est jamais affiché.

## Timeout

Le délai est de 10 s, fixe et non modifiable par HTTP. Mesure : le diagnostic réel dure environ 0,12 à 0,16 s, ce qui laisse une marge large. Au-delà du délai : état `timed-out`, `exit_code=None`, message « Diagnostic interrompu : délai dépassé. ». Les sorties déjà lues sont conservées.

## Gestion des processus enfants

`start_new_session=True` crée un groupe de processus. Dans le `finally`, **toujours** (sortie normale, délai, exception) :

1. `os.killpg(pid, SIGKILL)`, en ignorant un groupe déjà disparu ;
2. `wait` ;
3. fermeture des tubes.

Les tests le prouvent dans deux cas : un petit-enfant `sleep 60` tué au délai ; un petit-enfant orphelin, qui garde les tubes ouverts après la sortie du parent, tué lui aussi. Un zombie est compté comme mort.

## Bornes stdout / stderr

Un sélecteur lit les deux flux en continu par blocs de 64 Kio. Le runner garde au plus 256 Kio par flux ; l'excédent est lu, jeté et compté. Un tube plein ne bloque donc jamais l'enfant. Test : 1 Mio par flux donne 256 Kio gardés et 786 432 octets ignorés, affichés par « Sortie tronquée : 786432 octets ignorés au-delà de 256 Kio. ».

## ANSI

Après décodage UTF-8 (octets invalides remplacés par `�`), le runner retire :

- les séquences CSI ;
- les séquences OSC (corps borné à 4 096 caractères, terminées par BEL ou ST) ;
- les échappements à deux caractères.

Les autres contrôles C0 et DEL sont remplacés par `�`, sauf la tabulation et les fins de ligne. Le masquage textuel de Debug Center (`redact_debug_text`) s'applique ensuite, car le diagnostic recopie les messages d'exception des pilotes de base de données (`… ({exc})`). Voir les limites plus bas.

## Résultat ForgeDiagnosticRun

`ForgeDiagnosticRun` est une dataclass gelée et interne : `status`, `exit_code`, `stdout`, `stderr`, `duration`, `timed_out`, `stdout_truncated`, `stderr_truncated`, `interpreter` (libellé `.venv/bin/python`, jamais le chemin absolu) et `message`. Elle n'est ni exportée ni sérialisée.

## Debug Center

La section « Diagnostic Forge » contient :

- l'explication ;
- l'avertissement ;
- les bornes ;
- le bouton, si un projet est ouvert ;
- l'état, le code retour, la durée, l'interpréteur ;
- la sortie standard et la sortie d'erreur dans des `<pre>` ;
- les éventuelles marques de troncature.

Le journal des erreurs runtime reste une section distincte (`#journal-title`) et ses filtres GET sont inchangés.

## Déclenchement explicite

Aucun `GET` n'exécute le diagnostic, quelles que soient la page, les filtres ou l'actualisation du projet : un espion sur le runner le vérifie sur `/debug`, `/inspector`, `/routes`, `/` et `/project/refresh`. `GET /debug/forge-diagnostic` répond 405. Le `POST` lance le diagnostic exactement une fois et rend la page directement : pas de redirection, pas de persistance. Le `GET` suivant revient à « non exécuté ».

## Projet absent

Sans projet ouvert, la page n'affiche pas de bouton. Un `POST` répond 409 « Aucun projet sélectionné : diagnostic non lancé. » ; aucun processus n'est créé.

## Projet inaccessible

Racine supprimée après l'ouverture : 409 « Diagnostic non lancé : … », aucun processus, aucune trace Python dans la page. Interpréteur absent, `.venv` qui est un lien symbolique, ou `python` non exécutable : 200 avec l'état `launch-failed` et le message contrôlé, sans repli sur un autre Python.

## Projet non Forge

Si `app.py` disparaît après l'ouverture, `check_forge_root` lève `NotForgeProjectError` : réponse 409, aucun processus.

## Sécurité HTTP

| Contrôle | Réponse |
|---|---|
| Origine non locale ou absente (`is_local_action`) | 403 |
| Content-Type autre que `application/x-www-form-urlencoded` | 415 |
| Tout champ ou paramètre (`command`, `path`, `env`, `?cwd=`) | 400 « Ce formulaire n'accepte aucun paramètre. » |
| Toutes les réponses | `Cache-Control: no-store` |

La sortie est échappée par Jinja, sans `| safe`. Test hostile : `<script>`, `<img onerror>`, guillemets, ANSI et NUL ; aucun élément injecté dans les navigateurs, aucune boîte de dialogue.

## Lecture seule

Forge Design n'écrit rien : ni dans le projet, ni dans `.forge-design/`, ni en session. Le diagnostic lui-même n'écrit rien grâce à `-B`, ce qui est vérifié avec le vrai `forge doctor`. Un `POST` coûte une vérification de racine plus la lecture habituelle du journal par le Tool `debug-center`, exactement comme un `GET` : aucune autre analyse Forge Design n'est lancée (§118).

## Tests Python

`tests/test_runtime_diagnostics.py` (18 tests) utilise un faux interpréteur exécutable réel (script `sh` dans `.venv/bin/python`), lancé par le vrai `Popen`. Couverture :

- argv, dossier courant et liste blanche ;
- argv reçu par le lanceur ;
- interdits statiques ;
- codes 0, 1 et 3 ;
- sortie hostile et ANSI ;
- masquage ;
- `clean_output` ;
- bornes ;
- délai et groupe tué ;
- orphelin tué ;
- bornes par défaut ;
- interpréteur absent, lien ou non exécutable ;
- erreur de lancement ;
- erreurs de racine ;
- projet non modifié ;
- **vrai `forge doctor`** dans un venv `--without-pip` relié au forge-mvc installé, avec un `forge.py` hostile dans le projet : le CLI officiel répond (« Forge doctor — ») et aucun fichier n'est écrit hors `.venv`.

## Tests Web

`tests/test_web_runtime_diagnostics.py` (9 tests) passe par un vrai serveur HTTP :

- `GET` sans exécution ;
- `POST` qui exécute une seule fois, en `no-store`, avec le journal séparé et le projet intact ;
- échappement ;
- délai et troncature rendus ;
- sans projet, non Forge et supprimé : 409 sans exécution ;
- 403, 415 et 400 ;
- interpréteur absent ;
- résultat non persisté ;
- cinq Tools.

## Mutations

Script hors dépôt. Pour chaque mutation : édition, `pytest -x` sur les deux fichiers, restauration à l'octet, empreinte des sources vérifiée. Résultat : **18/18 tuées**.

| Mutation | Tuée par |
|---|---|
| Diagnostic lancé au GET | `test_get_never_runs_the_diagnostic` |
| `shell=True` | `test_command_cwd_and_environment_are_fixed` |
| cwd incorrect (parent) | `test_command_cwd_and_environment_are_fixed` |
| Paramètres HTTP acceptés | `test_http_guards` |
| Délai ignoré (3 600 s) | `test_timeout_kills_the_whole_group` |
| Groupe non tué | `test_timeout_kills_the_whole_group` |
| stdout non borné | `test_outputs_are_bounded_while_reading` |
| stderr non borné | `test_outputs_are_bounded_while_reading` |
| Sortie `| safe` | `test_hostile_output_is_escaped` |
| Code retour ignoré | `test_exit_codes[fail-checks-failed-1]` |
| Exécuté sans projet | `test_no_project_and_invalid_projects_never_run` |
| Exécuté sur un projet non Forge | `test_no_project_and_invalid_projects_never_run` |
| `-P` retiré | `test_command_cwd_and_environment_are_fixed` |
| `-B` retiré | `test_command_cwd_and_environment_are_fixed` |
| Environnement hérité en entier | `test_command_cwd_and_environment_are_fixed` |
| ANSI conservé | `test_hostile_output_is_plain_text_without_ansi` |
| Masquage retiré | `test_sensitive_assignments_are_masked` |
| Repli sur l'interpréteur de Forge Design | `test_missing_or_unusable_interpreter_is_a_controlled_failure` |

## Chromium

Conditions :

- roue 0.2.0 dans un venv neuf ;
- vraie commande `forge-design --no-browser` sur 8765, avec un HOME isolé ;
- **vrai `forge doctor`** de deux projets réels, chacun avec son propre `.venv` :
  - `okproj` : diagnostic en code 0 ;
  - `failproj` : relation hostile (code 1) et `config.py` qui imprime `<script>`, de l'ANSI et `<img onerror>` sur les deux flux.

Scénario, 8/8 :

1. sans projet : aucun bouton ;
2. projet ouvert, `GET` : état « non exécuté », avertissement visible, aucun champ ;
3. clic réel de souris : `succeeded`, code 0, stdout « Forge doctor — 1.0.0rc9 … [OK] Entités — 3 entité(s) valide(s) », un seul POST ;
4. rechargement : état « non exécuté » ;
5. projet en échec : `checks-failed`, code 1, sortie hostile rendue en texte, sans ANSI, aucun `script` ni `img` injecté ;
6. retour à Project Inspector ;
7. aucune erreur JavaScript ni boîte de dialogue ;
8. aucun fichier modifié, aucune base SQLite créée.

Aller-retour du clic : environ 210 ms.

## Firefox

Même scénario par WebDriver BiDi : 8/8. Aller-retour du clic : 270 à 310 ms.

## Sans JavaScript

Firefox, avec `javascript.enabled=false` : `GET /debug` affiche l'état « non exécuté ». Un clic réel (BiDi `input.performActions`) envoie le formulaire en POST natif : état `succeeded`, sortie standard rendue, journal présent. La page n'a besoin d'aucun JavaScript.

## Performance

Médianes sur 10 exécutions, même commande et même environnement :

| Projet | Fichiers hors `.venv` | `forge doctor` direct | Via Forge Design | Surcoût |
|---|---:|---:|---:|---:|
| `okproj` | 41 | 120 ms | 119 ms | −0,7 ms (bruit) |
| `bigproj` (+2 000 templates, +300 contrôleurs) | 2 381 | 154 ms | 155 ms | +1,4 ms |

Le coût vient du démarrage de Python et du diagnostic. Le surcoût de Forge Design (sélecteur, nettoyage, masquage, arrêt du groupe) est négligeable.

## ToolRegistry

Cinq Tools, inchangés : `project-inspector`, `route-explorer`, `entity-explorer`, `debug-center`, `template-viewer`.

## Graphic Core

Aucune modification ; `node --test tests/js/graphics/*.test.mjs` donne 134/134.

## Modules externes

Circuit et Flowchart n'ont pas été modifiés. Validation légère : le scénario Chromium complet, avec `--module forge_design_circuit --module forge_design_flowchart`, donne 8/8.

## Dette / limites

- **Masquage non exhaustif.** `redact_debug_text` ne reconnaît que les clés isolées (`password=`, `token:`, `api_key=`, `Authorization:`…). Un nom préfixé comme `DB_PASSWORD=x` ou une URL `mysql://u:secret@h` ne sont pas masqués. `forge doctor` n'imprime pas les valeurs de `env/` ; le risque vient d'un `config.py` du projet qui imprimerait ses secrets, ou d'un message de pilote. Cette limite est partagée avec le journal de Debug Center. La corriger demande un ticket sur le masqueur commun.
- **Code 1 ambigu.** Forge utilise le même code pour « un contrôle en échec » et « erreur de la commande » ; Forge Design ne lit pas le texte pour les distinguer.
- **Pas de bac à sable.** Le diagnostic exécute `config.py` et se connecte à la base avec les droits de l'utilisateur ; seule la frontière de processus protège Forge Design. Une base distante peut être contactée.
- **Délai et bornes fixes.** 10 s et 256 Kio, non configurables, volontairement.
- **Requête bloquante.** Le POST attend la fin du diagnostic (10 s au plus) ; le serveur reste disponible pour les autres requêtes.

## Recommandation ticket suivant

Deux pistes :

- Corriger le masqueur commun (`FD-DEBUG-006`) pour qu'il reconnaisse les clés suffixées (`*_PASSWORD`, `*_TOKEN`, `*_SECRET`) et les identifiants d'URL. Cela profiterait au journal et au diagnostic.
- Poursuivre la Phase 5 avec une autre commande Forge si elle offre une sortie fiable, sur le même runner et la même frontière.

## Fichiers créés

- `forge_design/forge/project_python.py`
- `forge_design/forge/runtime_diagnostics.py`
- `tests/runtime_diagnostics_support.py`
- `tests/test_runtime_diagnostics.py`
- `tests/test_web_runtime_diagnostics.py`
- `docs/rapports/FD-RUNTIME-001.md`

## Fichiers modifiés

- `forge_design/limits.py`
- `forge_design/real_preview/controller.py`
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
| `ruff format --check .` | 422 fichiers formatés |
| `pyright` (strict) | 0 erreur, 0 avertissement |
| `git diff --check` | OK |
| `pytest` (suite complète) | 4 754 passed |
| `node --test tests/js/graphics/*.test.mjs` | 134/134 |
| Roue `forge-design 0.2.0`, venv neuf | `pip check` OK, `forge-design --version` : 0.2.0 |
| Chromium, Firefox, Chromium + modules | 8/8 chacun, vrai `forge doctor` |
| Firefox sans JavaScript | OK |
| Mutations | 18/18 tuées |

## État Git final

Un seul commit : `feat: exécuter le diagnostic Forge à la demande (FD-RUNTIME-001)`, au-dessus de `a34ee3f`. Il n'a pas été poussé. `docs/rapports/FD-CONTRACT-001.md` reste modifié localement, hors commit. La version reste 0.2.0. Circuit et Flowchart ne sont pas modifiés.
