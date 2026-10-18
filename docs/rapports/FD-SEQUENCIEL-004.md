# Rapport — FD-SEQUENCIEL-004

Troisième frontière d'exécution de Forge Design 0.2.1 sur SéquenCiel :
**`forge project:check` seul**, lancé depuis Debug Center, base de développement
arrêtée. Date : 2026-10-18.

## Objectif

Démontrer que la frontière `project:check`, nettement plus puissante que
`doctor`, reste comprise, observable et maîtrisée. Elle importe réellement
`mvc.routes`, donc les contrôleurs, les services, les opt-ins et leurs imports
transitifs, et exécute du code applicatif au niveau module.

L'objectif n'est pas un code retour 0, mais de savoir précisément :

- quels modules sont importés ;
- quels effets ont eu lieu ;
- quelles connexions ont été tentées ;
- quels fichiers ont été touchés ;
- quels processus ont existé ;
- si un secret a été exposé.

Non lancés : `project:audit`, `doctor`, Real Preview, l'éditeur, les actions de
modules, la génération, SAFEWRITE, les migrations, l'application SéquenCiel et sa
MariaDB de développement.

| Décision | Résultat |
|---|---|
| A. project:check uniquement ? | Oui : 2 POST `/debug/forge-project-check`, 0 autre commande |
| B. doctor / audit ? | Non |
| C. DB dev démarrée ? | Non : aucun écouteur sur 33389 du début à la fin |
| D. Graphe d'imports lu avant le clic ? | Oui : 375 modules locaux et 106 modules Forge, par AST, sans exécution |
| E. Gate préflight sur effets dangereux ? | Oui : franchi (aucun effet destructif atteignable) |
| F. `strace -f` ? | Oui, attaché au serveur pendant chaque clic |
| G. Surveillance `/proc` ? | Oui, 80 279 relevés |
| H. Réseau surveillé ? | Oui : **0 socket** dans les deux lignées |
| I. Filesystem surveillé ? | Oui : 81 temporaires dans `/tmp` par exécution, tous supprimés ; 0 écriture dans le checkout |
| J. Secrets uniquement en mémoire ? | Oui : 0 correspondance |
| K. Deuxième exécution conditionnelle ? | Oui : effets compris, S1 = T1, exécution rejouée |
| L. Chromium uniquement ? | Oui, clic réel |
| M. Aucune correction SéquenCiel ? | Oui |
| N. Verdict formel ? | **SEQUENCIEL_CHECK_PASS_WITH_ISSUES** |

## Baseline Forge Design

Dépôt ForgeDesign à `9d125f2` (FD-SEQUENCIEL-003), sur `main`, 2 commits d'avance
sur `origin/main` (`bb16f90`). Seuls autres changements : `FD-CONTRACT-001.md`
(modification utilisateur, préservée) et les fichiers non suivis historiques.
Le code exécuté est celui de la roue installée, jamais le checkout.

## Artefact utilisé

| Élément | Valeur |
|---|---|
| Roue | `tmp/fd-release-003-dist/forge_design-0.2.1-py3-none-any.whl` (FD-RELEASE-003, RELEASE_READY) |
| SHA-256 | `8f4167c92567964ac5663cc0720bd338675ecf0ba7d8eb850608da78ce91a9da` (vérifié) |
| Venv | Neuf, dans le scratchpad ; dépendances téléchargées puis installation `--no-index` ; ni éditable ni `PYTHONPATH` |
| `pip check` / version | No broken requirements found / Forge Design 0.2.1 |
| Paquets | forge-design 0.2.1, forge-mvc 1.0.0rc9 ; ni Circuit ni Flowchart ; aucun `.pth` |
| `CHECK_ARGUMENTS` installé | `("-s", "-B", "-P", "-u", "-m", "forge", "project:check")` |
| Observation | `strace` 6.13 (paquet Debian extrait dans le scratchpad, comme en FD-SEQUENCIEL-003) |

## Baseline SéquenCiel

| Élément | Valeur |
|---|---|
| Branche | `main` |
| HEAD | `89fb8a1329b05fb1ca0f8635aa2b1c3bb31e673f` |
| Statut (`GIT_OPTIONAL_LOCKS=0`) | 20 fichiers non suivis, préexistants ; empreinte `cdfb4f1f…` identique aux trois tickets précédents |
| `.venv` | `/usr/bin/python3.13`, forge-mvc 1.0.0rc9 et opt-ins rc9 |

Rien n'a été nettoyé.

## Stabilisation

| Contrôle | Résultat |
|---|---|
| Processus avec SéquenCiel pour cwd | 0 ; 0 descripteur ouvert sous SéquenCiel |
| nginx, gunicorn locaux | Absents |
| Codex / VS Code SéquenCiel | Aucun. Le seul `codex app-server` présent appartient à la fenêtre ForgeDesign (cwd `/home/roger`, parent : son hôte d'extensions), préexistant et autorisé, sans descripteur sur SéquenCiel |
| Écouteurs 8090, 8092, 33389, 8765, 9341 | Aucun |
| `mariadbd` système (3306) | Hors cible, laissé tel quel |

## DB développement

`127.0.0.1:33389` est **restée arrêtée** : aucun écouteur avant T0, entre les deux
exécutions ni à la fin, et `tmp/base-locale/demarrer.sh` n'a pas été lancé. La
configuration a été classée en FD-SEQUENCIEL-003 : IP de loopback et non
`localhost`, donc pas le socket du `mariadbd` système.

Le cas ne s'est pas présenté : **aucun module importé n'a tenté de connexion**. Le
backend `mariadb` est paresseux et n'a pas été chargé.

## Frontière attendue

```text
<racine>/.venv/bin/python -s -B -P -u -m forge project:check
cwd = racine ; nouvelle session ; stdin /dev/null
environnement : PATH, HOME, LANG
délai 10 s, groupe tué ; 256 Kio par flux ; masquage
```

Le contrat affiché par Debug Center autorise explicitement des effets du code
importé : « Ce code peut lire ou écrire des fichiers, contacter des services ou
lancer des processus avec les droits de votre compte […] ce sous-processus n'est
pas un bac à sable. »

## Lecture du code Forge project:check

`cli/project/project_check.py` (285 lignes, rc9) :

| Point | Constat |
|---|---|
| Ordre | 7 contrôles : Structure, Configuration (`env/example` lu par `dotenv_values`, `env/dev` présent), Entités (JSON de chaque entité et `relations.json`), **Routes**, Templates (`rglob("*.html")`), Modules (`forge_modules.json`), Migrations |
| Module importé | Uniquement dans `check_project_routes` : `ast.parse` de `mvc/routes/__init__.py`, puis `importlib.import_module("mvc.routes")`, avec la racine insérée en tête de `sys.path` et `mvc.*` retirés puis restaurés dans `sys.modules` |
| Exceptions | `ImportError` → FAIL avec conseil d'installation ; toute autre `Exception` → FAIL « erreur au chargement — Type: message » ; module sans `router` → FAIL ; chaque contrôle est en outre protégé par `run_project_check` |
| Code retour | 1 si au moins un FAIL, sinon 0 |
| Sortie | « Forge project:check — 1.0.0rc9 », une ligne `[STATUT] Libellé — détail` par contrôle, puis un bilan |
| Configuration | **La commande ne charge pas `config.py`** : le code importé ne voit que les 3 variables de l'enfant, sauf s'il importe lui-même `config` |

## Analyse statique du graphe d'imports

Méthode, **sans aucune exécution**, par AST et lecture de texte seulement :

1. `mvc/routes/__init__.py` (340 lignes) a été lu en entier à travers le filtre
   de masquage. Au niveau module, il importe 57 modules de routes, 1 contrôleur,
   `forge_mvc_rbac`, `mvc.services.posture_rbac`, `optins.registry` et
   `mvc.models.user_model`, puis **appelle à l'import** une cinquantaine de
   `register_*(router)`, `register_optins(router)` et
   `register_jinja_context_provider(...)`.
2. Un analyseur suit le **contexte exécuté à l'import** :
   - corps de module et de classe, décorateurs, valeurs par défaut, branches
     `if`, `try` et `with` ;
   - **pas** les blocs `if TYPE_CHECKING:` ni `if __name__ == "__main__":` ;
   - et, transitivement, le corps des fonctions et constructeurs appelés dans ce
     contexte, réexportations comprises.

   La résolution suit l'ordre de `project:check` : la racine d'abord, avec les
   paquets namespace (`tools/`), puis le `site-packages` du `.venv`. Le code Forge
   (`core`, `cli`, `forge_mvc_*`) est suivi ; les paquets tiers sont listés sans
   être suivis.
3. Filet de sécurité textuel : toute ligne exécutable en colonne 0 contenant un
   mot-clé à risque, sur les 475 fichiers atteints.

| Mesure | Valeur |
|---|---|
| Modules locaux atteints | **375** : `mvc.services` 104, `mvc.models` 89, `mvc.controllers` 74, `mvc.routes` 55, `mvc.forms` 33, `mvc.helpers` 4, `tools.drawciel_r4` 7, `tools.drawciel_avr` 4, `tools.drawciel_renode` 2, `optins` 2, `config` 1 |
| Modules Forge du `.venv` atteints | 106 |
| Paquets tiers importés (non suivis) | argon2, dotenv, jinja2, jsonschema, markupsafe, pyotp, **weasyprint** |
| Fonctions et constructeurs exécutés à l'import | 97 |
| Imports non résolus | 0 |
| Appels pointés exécutés à l'import | 31 formes distinctes, revues à la main : `router.add` et `router.group` (enregistrement en mémoire), `re.compile`, `logging.getLogger`, `Path(...).resolve`, `threading.Lock`, `RLock` et `local` (verrous, aucun thread), `registry.register` (dictionnaire en mémoire, `forge_mvc_admin`) |

Faux positifs écartés pendant l'analyse, chacun vérifié dans la source :

- `tools.drawciel_renode.banc.main()` (`Popen`, `mkdir`, `rmtree`) est derrière
  `if __name__ == "__main__":` (l. 280), donc jamais exécuté à l'import ;
- `SELECT_ALL.replace` et `dataclasses.replace` sont des copies, pas des
  opérations sur fichiers ;
- `BACKEND = "mariadb"` est une affectation de chaîne.

## Modules importés

Classement des modules locaux chargés à l'import :

| Classe | Modules | Justification |
|---|---|---|
| PURE_IMPORT | 374 | Niveau module : constantes, chemins calculés (`Path(__file__).resolve()`), expressions régulières, loggers sans handler, enregistrements en mémoire (routes, ressource admin, fournisseur Jinja) |
| ENV_MUTATION (classe ajoutée, sans effet hors du processus) | 1 : `config` | `load_dotenv("env/example")`, puis `load_dotenv("env/dev", override=True)` ; importé transitivement par 6 modules atteints (`fiche_perimetre`, `courriel_code`, `arduino_cibles`, `arduino_tp`, `arduino_programme_controller`, `drawciel_spice_controller`) |
| POTENTIAL_FILESYSTEM / DB / NETWORK / THREAD_PROCESS | **0** dans le code local et Forge | — |
| UNKNOWN | Paquets tiers non suivis, dont **weasyprint** (chargement de bibliothèques natives) | Point de surveillance déclaré avant le clic |

Revue ciblée des 38 modules sensibles atteints (AVR, R4, SPICE, MCU, Renode,
Arduino, PDF, courriel, session) : le niveau module ne contient que des
constantes et des chemins. Ne sont **pas** importés :
`mvc.services.drawciel_r4.daemon`, `arduino_reseau_r4`, `session_glissante` et
`arduino_presentation`.

## Effets potentiels identifiés

| Effet recherché (§11) | Constat statique |
|---|---|
| `open`, `write_*`, `mkdir`, `unlink`, `rename`, `FileHandler` | Aucun appel exécuté à l'import |
| Connexion DB, création de pool | Aucune : le pool `mariadb` est créé au premier emprunt ; le backend n'est pas importé |
| socket, requests, http | Aucun |
| subprocess, thread, timer, worker | Aucun dans le code local et Forge ; `banc.main()` protégé |
| Initialisation matérielle AVR, SPICE, R4, Tailscale | Aucune : chemins de sockets construits comme chaînes, jamais ouverts |
| `os.environ` | Modifié par `config.py` (processus enfant seulement) |
| Bibliothèques tierces | `weasyprint`, importé au niveau module par `mvc/services/pdf.py` l. 15, charge Pango, Cairo et HarfBuzz : effet non prévisible statiquement, surveillé par `strace` |

## Gate préflight

**Franchi.** Aucune écriture critique, suppression, migration, appel distant,
thread durable ni commande système n'est atteignable statiquement à l'import. Les
effets potentiels sont absents (code local et Forge), ou attendus et surveillés
(`os.environ`, bibliothèques natives de weasyprint).

## T0 / T1

Même outil et même méthode qu'aux tickets précédents. Niveau complet : chemin,
type, taille, `mtime_ns`, `ctime_ns`, inode, mode, SHA-256 ou cible. Niveau lourd
(`.venv`, `node_modules`, `tmp`, `sauvegardes`) : les mêmes champs sans SHA-256.
`.git` : HEAD et empreinte du statut.

| Instantané | Heure | Entrées | Comparaison |
|---|---|---:|---|
| T0 | 21:12:59 | 519 214 (7 828 / 511 385) | — |
| T1 | 21:18:18 (5 min 19 s après) | 519 214 | **= T0**, même HEAD, même statut : gate franchi |

## HOME / XDG isolés

Serveur lancé par `env -i` avec `HOME` et les quatre `XDG_*` dans le scratchpad,
`PATH=/usr/bin:/bin` et `LANG=C.UTF-8`, depuis `/tmp`, avec `--no-browser` et sans
module. Il écoute sur `127.0.0.1:8765` seulement ; Host `localhost` et Host
étranger donnent 400 ; `Cache-Control: no-store`.

À la fin, le HOME isolé ne contient que `.config/forge-design/recent-projects.json`
(77 octets) : weasyprint n'y a écrit **aucun** cache fontconfig. Le vrai
`~/.config/forge-design/` est inchangé, et aucun `storage/` n'a été créé dans le cwd
du serveur.

## Debug Center avant clic

| Contrôle | Résultat |
|---|---|
| Ouverture (un POST `/inspector`) | 818 ms |
| doctor / audit / check | « non exécuté » × 3 |
| Avertissement de check (§23) | « Elle importe réellement les routes du projet (`mvc/routes`) : ce code s'exécute […] Ce code peut lire ou écrire des fichiers, contacter des services ou lancer des processus […] ce sous-processus n'est pas un bac à sable. » |
| GET `/debug` sans exécution (§24) | 81 ms ; aucun processus enfant, aucun import de projet (surveillant `/proc`) |
| Instantané après ouverture | = T1 |

## Commande réelle

Relevée par `strace` (`execve`), identique dans les deux exécutions :

```text
execve("/home/roger/Projets/SequenCiel/.venv/bin/python",
       ["/home/roger/Projets/SequenCiel/.venv/bin/python", "-s", "-B", "-P", "-u",
        "-m", "forge", "project:check"], /* 3 vars */) = 0
```

Le cwd est la racine SéquenCiel, et stdin est `/dev/null`, ouvert par le serveur.

## Première exécution

Un seul clic souris réel (CDP) sur « Exécuter la vérification Forge », avec
`strace -f` attaché au serveur.

| Mesure | Valeur |
|---|---|
| POST | 1 (`/debug/forge-project-check`) |
| État | `succeeded` : « Terminé avec le code 0 : aucun contrôle en échec » |
| Code retour | 0 |
| `timed_out` | Non |
| Durée | 3,31 s (sous `strace`) |
| Clic → page | 3 436 ms |
| stdout / stderr | 424 / 0 caractères |
| Troncature | aucune |
| Persistance | aucune (nouveau GET : « non exécuté ») |

## Processus enfant

| Constat | Exécution 1 | Exécution 2 |
|---|---|---|
| PID racine / PPID | 1521892 / serveur 1521498 | 1522304 / serveur |
| PGID / SID | 1521892 / 1521892 : nouvelle session | 1522304 / 1522304 |
| Environnement de la racine | 3 variables : `PATH=/usr/bin:/bin`, `LANG=C.UTF-8`, `HOME` isolé | idem |
| Durée de la racine | `execve` 21:19:38.816 → `exit_group(0)` 21:19:42.117 | 21:21:38.126 → 21:21:41.213 |
| Threads | Aucun (tous les `clone` sont des `CLONE_VM\|CLONE_VFORK`, donc des lancements de processus) | idem |

## Imports observés

Reconstruits depuis la trace (ouverture réussie du `.pyc` dans `__pycache__` ou
du `.py`) :

| Mesure | Valeur |
|---|---|
| `mvc.routes` réellement chargé (§38) | **Oui** : `mvc/routes/__pycache__/__init__.cpython-313.pyc` ouvert |
| Modules du projet chargés | **375 / 375 prévus** par le graphe statique, aucun hors graphe (`config` compris, depuis `__pycache__/config.cpython-313.pyc`) |
| Par zone | `mvc.services` 104, `mvc.models` 89, `mvc.controllers` 74, `mvc.routes` 55, `mvc.forms` 33, `mvc.helpers` 4, `tools.drawciel_*` 13, `optins` 2, `config` 1 |
| Modules du `.venv` chargés | 491 ; les 106 modules Forge prévus sont tous observés ; la pile weasyprint (cffi, pycparser, PIL, fontTools, pydyf, tinycss2, cssselect2, pyphen…) est chargée |
| Opt-ins chargés (§40) | **5 sur 9** : `forge_mvc_admin`, `forge_mvc_files`, `forge_mvc_mfa`, `forge_mvc_notifications`, `forge_mvc_rbac` |
| Opt-ins inscrits non chargés | `mail`, `sessions-db`, `deploy`, `fixtures`, ainsi que `forge_mvc_entities` et le backend `mariadb` : imports paresseux ou opt-ins de CLI |
| `env/*` ouverts | `env/example` 2 fois (`check_project_config` par chemin absolu, puis `config.py` par chemin relatif), `env/dev` 1 fois (`config.py`) ; ni `env/prod` ni `env/actualisation` |

**Bytecode** : 374 modules sont chargés depuis un `.pyc` existant. Un seul est
recompilé depuis sa source, `mvc/services/arduino_compilation_r4.py`, modifié
aujourd'hui à 18:49 alors que son `.pyc` date du 13/10. Sans `-B`, Python aurait
**réécrit** `mvc/services/__pycache__/arduino_compilation_r4.cpython-313.pyc` dans
le checkout ; avec `-B`, rien n'est écrit. C'est la démonstration directe, sur le
vrai projet, de l'utilité de `-B` dans le runner.

## Descendants

L'enfant a lancé **86 processus** par exécution, tous synchrones et terminés avant
lui :

| Binaire | Nombre |
|---|---:|
| `/sbin/ldconfig -p` | 22 |
| `/usr/bin/gcc -Wl,-t -o /tmp/tmpXXXXXXXX -l<nom>` | 16 |
| `/usr/libexec/gcc/x86_64-linux-gnu/14/collect2` | 16 |
| `/usr/bin/ld` (`ld -t -o /dev/null -l<nom>` et lien de `gcc`) | 32 |

**Attribution démontrée** (§32), par l'ordre des ouvertures dans la trace :

1. `mvc/services/pdf.py`, ligne 15 : `from weasyprint import HTML`, au niveau
   module ;
2. `weasyprint/text/ffi.py`, lignes 503 et suivantes :
   `gobject = _dlopen(ffi, …)`, `pango = _dlopen(…)`, `harfbuzz = _dlopen(…)`…,
   au niveau module, qui essaient plusieurs noms par bibliothèque, dont des noms
   de style Windows (`libgobject-2.0-0`, `libpango-1.0-0`) ;
3. un échec de `dlopen` fait passer cffi par `ctypes.util.find_library`. La
   bibliothèque standard de CPython essaie alors `/sbin/ldconfig -p`, puis
   `gcc -Wl,-t` (`_findLib_gcc`), puis `ld -t` (`_findLib_ld`).

Les derniers fichiers ouverts avant le premier `ldconfig` sont, dans l'ordre,
`weasyprint/text/ffi.pyc`, `cffi/*.pyc`, `pycparser/*.pyc`, puis
`ctypes/util.pyc`. La rafale dure environ 1,4 s (sous `strace`) : 39,80 → 41,17,
puis 39,04 → 40,41.

Toute la lignée reste dans la session créée par le runner : chaque descendant
porte pgid = sid = PID racine, qu'il hérite de la racine, chef de session après
le `setsid` du runner. Le surveillant a vu la racine juste avant ce `setsid`,
encore dans le groupe du serveur, d'où la preuve par les descendants. Aucun
descendant ne vit plus de 64 ms, ni ne survit à la racine.

**Environnement des descendants** (surveillant `/proc`, **noms seulement**) :
`ldconfig` reçoit 2 variables (`ctypes.util` les fixe). `gcc` et `ld` en héritent
36 à 44. Parmi elles figurent `DB_APP_PWD`, `DB_ADMIN_PWD`, `DB_APP_LOGIN`,
`DB_ADMIN_LOGIN`, `SECRET_KEY` et `FORGE_MFA_SECRET_KEY`, chargées dans
`os.environ` par le `config.py` importé avant weasyprint.

C'est l'héritage standard de l'environnement d'un processus. Aucune valeur n'est
passée en argument (`argv` : `-Wl,-t`, `-o /tmp/tmp…`, `-l<nom>`), écrite dans un
fichier ou rendue dans une sortie (0 correspondance). Elles restent lisibles dans
`/proc/<pid>/environ`, pour le seul compte de l'utilisateur, pendant moins de
64 ms.

## Réseau

| Famille | Enfant et ses 86 descendants | Serveur |
|---|---|---|
| AF_INET | **0** socket, 0 connect | `accept4` et `sendto` sur `127.0.0.1:8765` (Chromium) |
| AF_INET6 | 0 | 0 |
| AF_UNIX | 0 (pas même nscd, contrairement à `doctor`) | 0 |

Il n'y a eu aucune tentative vers `127.0.0.1:33389` ni ailleurs : le code
importé ne contacte rien à l'import.

## Filesystem

| Constat | Exécution 1 | Exécution 2 |
|---|---|---|
| Ouvertures en écriture (hors `/dev/null`) | 81, **toutes dans `/tmp`** : `tmpXXXXXXXX` de `tempfile` (ctypes), `cc*.res`, `cc*.cdtor.c` et `.o` de `gcc` et `collect2` | 81, idem |
| Mutations | 81 `unlink`, toutes dans `/tmp` | idem |
| Fichiers temporaires restants | **0** (chaque chemin créé vérifié absent) | 0 |
| Écritures sous SéquenCiel | **0** | 0 |
| Écritures sous le HOME isolé | 0 | 0 |
| Écritures du serveur Forge Design | 0 (seul `/dev/null` pour stdin) | 0 |
| `mkdir`, `rename`, `truncate`, `utimensat`, `link`, `symlink` | 0 | 0 |

Classement (§33) : **EXPECTED_APPLICATION_SIDE_EFFECT**. Ces écritures sont
produites par du code tiers (CPython `ctypes.util`, via cffi et WeasyPrint) que le
code SéquenCiel importe. Elles sont hors du checkout, éphémères et nettoyées par
leurs auteurs.

Distinction des responsables (§34) :

- **runner Forge Design** : aucune écriture, aucun processus hors de l'enfant
  prévu ;
- **processus enfant Forge** (CLI forge-mvc) : aucune écriture ;
- **code SéquenCiel importé** : la rafale `ctypes`, via weasyprint, et la
  modification de `os.environ`.

## Résultat project:check

```text
Forge project:check — 1.0.0rc9

  [OK]    Structure — structure projet conforme
  [OK]    Configuration — env/example et env/dev présents
  [OK]    Entités — 86 entité(s) vérifiée(s)
  [OK]    Routes — mvc/routes/__init__.py valide
  [OK]    Templates — 496 template(s) présent(s)
  [OK]    Modules — forge_modules.json absent — aucun module installé
  [OK]    Migrations — 251 fichier(s) SQL valide(s)

Tout est conforme.
```

## Vérification indépendante

| Contrôle | Prévision (lecture du code rc9 et recomptage, après T1) | Observé | Verdict |
|---|---|---|---|
| Structure | 7 éléments présents | OK | Juste |
| Configuration | `env/example` lisible, `env/dev` présent | OK | Juste |
| Entités | 86 dossiers, JSON et `relations.json` valides | OK, 86 | Juste |
| Routes | OK si l'import réussit ; graphe : 375 modules, aucun import manquant | OK ; 375/375 modules chargés | Juste |
| Templates | 496 `.html` | 496 | Juste |
| Modules | `forge_modules.json` absent | OK | Juste |
| Migrations | 251, 0 non conforme, 0 vide | 251 | Juste |
| Code retour | 0 | 0 | Juste |

**7/7 contrôles justes**, et le graphe statique est exact à 100 % sur les modules
du projet. La seule chose qu'il ne pouvait pas prévoir est l'effet de bord du
paquet tiers weasyprint, qui avait été déclaré comme point de surveillance.

## Secrets / redaction

| Mesure | Résultat |
|---|---|
| Secrets candidats | 49 valeurs distinctes (`env/*`, `config.py`, `cert.pem`, `key.pem`), en mémoire |
| Identifiants surveillés | 3 valeurs distinctes (comptes, nom de base) |
| Surfaces | HTML des deux pages de résultat, stdout et stderr, les deux traces `strace` complètes (2,9 Mo chacune, `argv` des 87 `execve` compris), journal du serveur |
| **Correspondances de secret** | **0** |
| Correspondances d'identifiant | 0 |
| URL | Aucune URL navigateur ne porte de paramètre |
| Masquage | Appliqué par construction, rien à masquer ; aucun « [masqué] » dans la sortie |

Aucune valeur sensible en argument, en fichier temporaire, dans le rapport ou en
sortie. La présence de *noms* sensibles dans l'environnement des descendants est
traitée plus haut (Descendants).

## Snapshot S1

Pris à 21:19:43, juste après la première exécution : **= T1** (0 ajout,
0 suppression, 0 changement, `.venv` compris).

## Deuxième exécution

Conditions des §49 et §50 réunies : effets compris (temporaires `/tmp` créés puis
supprimés par leurs auteurs, processus synchrones), non destructifs, état initial
toujours comparable (S1 = T1), aucune fuite, aucun survivant, pas de délai
dépassé. La base est restée arrêtée.

| Mesure | Exécution 2 |
|---|---|
| POST | 1 |
| État / code | `succeeded` / 0 |
| Durée | 3,09 s (sous `strace`) ; clic → page 3 180 ms |
| Snapshot S2 (21:21:42) | **= T1** |

## Déterminisme

| Axe | Comparaison |
|---|---|
| stdout, stderr | **Identiques** octet pour octet |
| Code retour | 0 et 0 |
| Imports | Mêmes modules (375 locaux) |
| Descendants | Mêmes binaires, mêmes nombres (22/16/16/32) |
| Connexions | 0 et 0 |
| Effets fichiers | 81 créations et 81 suppressions dans `/tmp`, 0 restant, dans les deux cas |
| Variations | PID, durées (3,31 / 3,09 s) et noms aléatoires des temporaires : attendues |

## Timeout / groupe de processus

- Délai non atteint : 3,3 s sur 10 s, mesuré **sous `strace`**, dont environ
  1,4 s de rafale `ctypes`.
- La marge reste réelle mais non nulle : sur une machine plus lente ou à froid,
  cette rafale pèse sur le délai (à surveiller, voir Observations).
- Toute la lignée est dans la session du runner, donc atteinte par
  `killpg(SIGKILL)` en cas de délai.
- **Aucun processus détaché** (§54) : aucun membre n'a changé de session, aucun
  n'a survécu à la racine (`ps` par PGID vide après chaque exécution), et aucun
  processus n'avait SéquenCiel pour cwd à la fin.

## Chromium

Chromium seul, une phase d'ouverture et deux phases de commande, chacune avec un
profil neuf détruit ensuite, et un clic souris réel par commande. Toutes les
pages ont un seul `h1` et aucune alerte d'erreur.

## Console / CSP

- 0 violation CSP, 0 exception JavaScript.
- Erreurs réseau : uniquement les 3 `GET /favicon.ico` en 404, déjà connus
  (cosmétique).
- Réseau navigateur : `127.0.0.1:8765` uniquement.
- Journal du serveur : 3 POST au total (`/inspector` et 2 ×
  `/debug/forge-project-check`).

## Performances / mémoire

| Mesure | Valeur |
|---|---|
| RSS serveur au démarrage | 46,0 Mio |
| RSS avant check (après ouverture) | 86 932 Kio |
| RSS après check n° 1 | 86 996 Kio |
| RSS après check n° 2 | 86 996 Kio |
| Durée du runner | 3,31 s / 3,09 s (sous `strace`) |
| Clic → page | 3 436 / 3 180 ms |

Ce sont des observations, pas un banc d'essai : les durées incluent le surcoût de
`strace`.

## Snapshot final

Pris à 21:23:25, après l'arrêt de Forge Design : **= T1**, sur 519 214 entrées,
sans aucune différence de contenu, de mtime, de ctime ou d'inode. HEAD et statut
sont inchangés.

## Processus finaux

- `SIGTERM` au serveur : arrêt propre, code 0.
- Aucun processus Forge Design, `project:check`, descendant (`ldconfig`, `gcc`,
  `collect2`, `ld`), Chromium ou `strace` ; plus de `TracerPid` sur le serveur
  après chaque détachement.
- Aucun proxy ni preview.
- Ports 8765, 9341 et 33389 libres ; 0 processus avec SéquenCiel pour cwd.

## Observations SéquenCiel

| # | Observation | Classement |
|---|---|---|
| 1 | `mvc/services/pdf.py` importe weasyprint **au niveau module**. Chaque import des routes (démarrage de l'application, `project:check`, tests) déclenche donc environ 86 lancements de la chaîne de compilation par `ctypes.util.find_library` : environ 1,4 s ici, et une dépendance implicite à `gcc` et `ld`. Un import paresseux, dans la fonction de rendu PDF, l'éviterait. À documenter, pas à corriger ici | SEQUENCIEL-ISSUE (mineure : performance et hygiène d'import) |
| 2 | Les secrets de `env/dev`, chargés dans `os.environ` par `config.py`, sont hérités par tout sous-processus, ici ceux de `ctypes.util` | EXPECTED_APPLICATION_SIDE_EFFECT (conception ADR-060 : le backend lit l'environnement) |
| 3 | `arduino_compilation_r4.cpython-313.pyc` est périmé (source modifiée aujourd'hui) : sans `-B`, n'importe quel import le réécrirait | EXPECTED |
| 4 | Le démarrage par import est sain : 0 connexion, 0 thread, 0 écriture dans le projet ; démons et transports R4 non importés | EXPECTED |

## Observations Forge Design

| # | Observation | Gravité | Classement |
|---|---|---|---|
| 1 | Frontière conforme : argv de la liste fermée, nouvelle session englobant les 86 descendants, 3 variables, stdin `/dev/null`, aucun survivant, résultat non persisté | — | EXPECTED |
| 2 | `-B` a empêché une écriture réelle de bytecode dans le checkout | — | EXPECTED |
| 3 | L'avertissement de `project:check` décrit exactement ce qui a été observé (lancement de processus, écriture de fichiers par le code importé) | — | EXPECTED |
| 4 | Le runner ne fixe pas `TMPDIR` : les temporaires du code importé vont dans `/tmp` partagé. Les donner à un dossier temporaire dédié faciliterait l'observation et le nettoyage. Amélioration possible, pas un défaut | Mineure | EXPECTED |
| 5 | Délai de 10 s : la moitié environ de l'exécution observée vient d'une rafale tierce ; marge à surveiller sur d'autres machines | À surveiller | UNKNOWN |
| 6 | `favicon.ico` 404 | Cosmétique | FORGEDESIGN-ISSUE |

## Limites Forge

- La famille « Modules » de `project:check` rc9, comme celle de l'audit, ne lit
  que `forge_modules.json` : « aucun module installé », alors que 9 opt-ins sont
  inscrits et 5 importés. FORGE-LIMITATION (déjà relevée en FD-SEQUENCIEL-002).
- `project:check` ne charge pas la configuration lui-même. Le code importé peut
  la charger (ici par `config.py`), ce qui fait dépendre l'environnement vu par les
  modules de l'ordre des imports. C'est le contrat de rc9, correctement affiché
  par Forge Design : EXPECTED.

## Classification

| Catégorie | Constats |
|---|---|
| EXPECTED | Code 0, 7/7 ; 375 modules chargés ; 5 opt-ins importés ; `config.py` chargé transitivement ; `-B` effectif ; frontière de processus |
| EXPECTED_APPLICATION_SIDE_EFFECT | 86 descendants `ldconfig`, `gcc`, `collect2` et `ld` (weasyprint → cffi → `ctypes.util`) ; 81 temporaires `/tmp` créés puis supprimés ; héritage de l'environnement (secrets de `env/dev`) par ces descendants |
| SEQUENCIEL-ISSUE | Import de weasyprint au niveau module (coût et dépendance à la chaîne de compilation à chaque import des routes) |
| FORGEDESIGN-ISSUE | `favicon.ico` 404 (cosmétique, préexistant) |
| FORGE-LIMITATION | Famille « Modules » aveugle au registre d'opt-ins |
| UNKNOWN | Marge du délai de 10 s sur une machine plus lente |
| BLOCKING | **Aucun** |

## Verdict

**SEQUENCIEL_CHECK_PASS_WITH_ISSUES**

`project:check` fonctionne et sa sortie est fiable : 7/7, déterministe, et le
graphe d'imports est vérifié à 375/375.

La frontière est **comprise, observable et maîtrisée** :

- 0 écriture dans le checkout (S1, S2 et l'instantané final = T1) ;
- 0 connexion ;
- 0 fuite ;
- 0 survivant ;
- toute la lignée reste dans le groupe du runner.

Pourquoi « with issues » (§69) : des effets applicatifs contrôlés ont été
observés. Ce sont 86 sous-processus et 81 fichiers temporaires hors du checkout,
supprimés par leurs auteurs, et l'héritage des secrets d'environnement par ces
processus. La conformité au §62 est complète :

- cause démontrée (`pdf.py` l. 15 → `weasyprint/text/ffi.py` → `ctypes.util`) ;
- effet non destructif ;
- autorisé explicitement par l'avertissement de `project:check` ;
- attribution sans ambiguïté.

Aucune condition de BLOCKED (§66) n'est remplie.

## Recommandation ticket suivant

**FD-SEQUENCIEL-005 : Real Preview uniquement**, toujours avant toute édition.

Real Preview lance l'application elle-même (`python -I -B -u`, FD-REALPREVIEW-007)
et la garde vivante. On y retrouvera au minimum ce que ce ticket a observé :

- import des 375 modules ;
- rafale weasyprint ;
- `config.py` ;
- **et** ce que fait `app.py` au démarrage (middlewares, sessions, pool de base à
  la première requête, éventuels démons DrawCiel).

À préparer :

- lire `app.py` et `wsgi.py` comme `mvc/routes/__init__.py` ici ;
- garder la base arrêtée et s'attendre à des erreurs de connexion **à la
  première requête** ;
- réutiliser `strace -f` et le surveillant `/proc` pendant toute la vie de la
  preview, et vérifier l'arrêt du groupe au stop ;
- prévoir des instantanés pendant la preview (un processus vivant peut écrire
  dans `storage/`) ;
- ne demander aucune page applicative au-delà de ce que le ticket autorise.

Hors chemin critique : FD-ROUTES-023 (borne de templates).

## Fichiers créés

- `docs/rapports/FD-SEQUENCIEL-004.md`

Aucun fichier n'est créé dans SéquenCiel. Les outils (graphe d'imports AST, filet
textuel, comparateur des imports observés, instantané, surveillant `/proc`,
scénario Chromium, contrôle des secrets, analyseur `strace`) et les traces restent
dans le scratchpad de la session. Les instantanés compressés sont dans
`tmp/fd-sequenciel-004/` (ignoré par Git) et ne contiennent que des métadonnées et
des empreintes.

## Fichiers modifiés

- `docs/03-roadmap.md` : FD-SEQUENCIEL-004 et son verdict, et la suite
  (FD-SEQUENCIEL-005).

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
`test: qualifier project:check sur SéquenCiel (FD-SEQUENCIEL-004)`. Il contient ce
rapport et la roadmap. Il n'est pas poussé : 3 commits d'avance sur `origin/main`.
`FD-CONTRACT-001.md` et les fichiers non suivis historiques sont inchangés.

**SéquenCiel** : HEAD `89fb8a1329b05fb1ca0f8635aa2b1c3bb31e673f`, statut
identique (20 fichiers non suivis, préexistants), **aucun commit et aucune
modification**.
