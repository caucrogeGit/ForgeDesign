# Rapport — FD-SEQUENCIEL-003

Deuxième frontière d'exécution de Forge Design 0.2.1 sur SéquenCiel :
**`forge doctor` seul**, lancé depuis Debug Center, **base de développement
arrêtée**. Date : 2026-10-18.

## Objectif

Une question : Forge Design 0.2.1 peut-il lancer `forge doctor` sur le vrai
SéquenCiel, avec sa configuration réelle mais base de développement arrêtée, sans
écrire dans le checkout, sans fuite de secret et en rendant fidèlement l'échec de
connexion attendu ?

La frontière change par rapport à FD-SEQUENCIEL-002 : `project:audit` lisait des
fichiers, `doctor` **exécute `config.py`** et tente une connexion à la base.

Non lancés : `project:audit`, `project:check`, Real Preview, l'éditeur, les
actions de modules, la génération, SAFEWRITE, les migrations, l'application
SéquenCiel et sa MariaDB de développement (`tmp/base-locale/demarrer.sh` non
touché).

| Décision | Résultat |
|---|---|
| A. doctor uniquement ? | Oui : 2 POST `/debug/forge-diagnostic`, 0 POST audit ou check |
| B. project:audit ? | Non |
| C. project:check ? | Non |
| D. DB développement démarrée ? | **Non** : aucun écouteur sur 33389 avant, pendant et après |
| E. DB arrêtée et connexion refusée qualifiée ? | Oui : `ECONNREFUSED` vu par le noyau, FAIL rendu fidèlement |
| F. config.py lu avant exécution ? | Oui, en entier, à travers un filtre de masquage |
| G. T0/T1 ? | Oui : T0 = T1 à 5 min 19 s |
| H. Deux exécutions si première propre ? | Oui |
| I. Surveillance réseau/processus ? | Oui : `strace` attaché au serveur et surveillant `/proc` |
| J. Secrets uniquement en mémoire ? | Oui |
| K. Chromium uniquement ? | Oui, clic réel |
| L. Aucune modification SéquenCiel ? | Oui : instantané final = T1 |
| M. Verdict formel ? | **SEQUENCIEL_DOCTOR_PASS_WITH_ISSUES** |

## Baseline Forge Design

Dépôt ForgeDesign à `47b7799` (FD-SEQUENCIEL-002), sur `main`, 1 commit d'avance
sur `origin/main` (`bb16f90`). Seuls autres changements : `FD-CONTRACT-001.md`
(modification utilisateur, préservée) et les fichiers non suivis historiques.
Le dépôt ne sert qu'au rapport : **le code exécuté est celui de la roue
installée**.

## Artefact utilisé

| Élément | Valeur |
|---|---|
| Roue | `tmp/fd-release-003-dist/forge_design-0.2.1-py3-none-any.whl` (FD-RELEASE-003, RELEASE_READY) |
| SHA-256 | `8f4167c92567964ac5663cc0720bd338675ecf0ba7d8eb850608da78ce91a9da` (vérifié) |
| Venv | Neuf, dans le scratchpad ; dépendances téléchargées puis installation `--no-index` ; ni éditable ni `PYTHONPATH` |
| `pip check` | No broken requirements found |
| `forge-design --version` | Forge Design 0.2.1 |
| Paquets | forge-design 0.2.1, forge-mvc 1.0.0rc9 ; ni Circuit ni Flowchart ; aucun `.pth` |
| Constantes installées | `FORGE_DIAGNOSTIC_TIMEOUT_SECONDS = 10.0`, `MAX_FORGE_DIAGNOSTIC_OUTPUT_BYTES = 262144`, `DIAGNOSTIC_ARGUMENTS = ("-s", "-B", "-P", "-u", "-m", "forge", "doctor")` |

Outil d'observation ajouté pour ce ticket : `strace` 6.13 (paquet Debian trixie
`strace_6.13+ds-1`, avec `libunwind8` 1.8.1). Il a été obtenu par `apt download`,
qui vérifie le paquet contre les index signés, puis extrait dans le scratchpad par
`dpkg-deb -x`. Il n'y a eu aucune installation système et aucun privilège : la
machine a `ptrace_scope = 0`. `tcpdump` est absent, et `ss -E` ne capte rien sans
privilège.

## Baseline SéquenCiel

| Élément | Valeur |
|---|---|
| Branche | `main` |
| HEAD | `89fb8a1329b05fb1ca0f8635aa2b1c3bb31e673f` (identique à FD-SEQUENCIEL-002) |
| Statut (`GIT_OPTIONAL_LOCKS=0`) | 20 fichiers non suivis, préexistants ; empreinte `cdfb4f1f…` identique à FD-SEQUENCIEL-002 ; aucun fichier modifié |
| `.venv` | `/usr/bin/python3.13` (3.13.5), forge-mvc 1.0.0rc9 et ses opt-ins rc9, `mariadb` 1.1.14 (MariaDB Connector/Python) |

Rien n'a été nettoyé.

## Stabilisation

| Contrôle | Résultat |
|---|---|
| Processus avec SéquenCiel pour cwd | 0 (la fenêtre VS Code SéquenCiel reste fermée depuis FD-SEQUENCIEL-002) ; 0 descripteur ouvert sous SéquenCiel |
| nginx, gunicorn locaux | Absents |
| Session SSH sortante | Aucune |
| Ports 8090, 8092, 8765, 9341 | Libres |
| `mariadbd` système | Présent (`127.0.0.1:3306` et `/run/mysqld/mysqld.sock`), hors cible, laissé tel quel |
| Racine SéquenCiel | mtime 20:22:23 (fermeture de la fenêtre, avant FD-SEQUENCIEL-002), inchangée depuis |

Processus préexistants autorisés : session VS Code Remote-SSH entrante, fenêtre
ForgeDesign et sa session Claude Code, `mariadbd` système.

## État DB développement

| Contrôle | Résultat |
|---|---|
| Écouteur sur `127.0.0.1:33389` | **Aucun**, avant T0, entre les deux exécutions et à la fin |
| `tmp/base-locale/demarrer.sh` | Non lancé |
| Configuration effective (classée en mémoire, aucune valeur affichée) | `DB_HOST` : **IP de loopback**, dans `env/example` comme dans `env/dev` ; `DB_PORT` : 33389, depuis `env/dev` ; `DB_NAME`, `DB_APP_LOGIN`, `DB_APP_PWD`, `DB_ADMIN_LOGIN`, `DB_ADMIN_PWD` : renseignés dans `env/dev` ; pas de `DB_SOCKET` ni de `DB_BACKEND` ; `APP_ENV=dev` |

Point vérifié avant le clic : le pilote MariaDB Connector/C traite
`host="localhost"` comme un **socket Unix**. Avec `localhost`, `doctor` se serait
connecté au `mariadbd` système par `/run/mysqld/mysqld.sock`. La configuration
indique une IP de loopback, donc une connexion TCP vers un port sans écouteur :
c'est ce qu'il fallait pour rester dans le périmètre.

## Lecture de config.py

`config.py` (98 lignes, 5 136 octets) a été lu en entier **avant toute
exécution**, à travers un filtre qui masquait en mémoire toute valeur candidate
(même extraction que le contrôle des secrets), les littéraux des lignes à nom
sensible et les mots de passe d'URL.

Fichiers lus en plus, uniquement pour comprendre la chaîne d'effets :

- `cli/project/doctor.py` : les 16 contrôles et leur ordre ;
- `core/security/csp.py` : `nonce_enabled()`, lecture d'une variable
  d'environnement ;
- `core/database/backend.py` : découverte du backend par entry point ;
- `core/forge.py` : registre de configuration en mémoire ;
- `forge_mvc_mariadb/backend.py` : pool de connexions et variables lues ;
- `cli/optins/registry_format.py` et `optins/registry.py` : backend `mariadb` et
  9 opt-ins inscrits ;
- `cli/_support/generated_marker.py` : empreinte `make:auth`, contrat 2.

## Effets potentiels de config.py

| Catégorie | Constat |
|---|---|
| Lecture env | `load_dotenv("env/example")`, puis `load_dotenv("env/dev", override=True)` : `APP_ENV` est absent de l'environnement de l'enfant, d'où `dev` |
| Accès filesystem | Lecture de `env/example` et `env/dev`, chemins relatifs au cwd (= racine) |
| Import de modules projet | **Aucun**. Seul import non standard : `core.security.csp`, du cœur forge-mvc dans `.venv` |
| Connexion DB | Aucune dans `config.py`. Elle vient de `check_db` (backend mariadb, pool créé à la demande) |
| Réseau | Aucun dans `config.py` |
| Création de dossiers ou fichiers | Aucune |
| Modification de `os.environ` | **Oui**, dans le processus enfant seulement (`load_dotenv`) |
| Autre | `os.getuid()` ; chemins de sockets AVR, SPICE et R4 construits comme chaînes, jamais ouverts |

Clés sensibles présentes, sans valeur :

| Clé | Source | Usage |
|---|---|---|
| `DB_APP_PWD`, `DB_ADMIN_PWD` | `env/dev` | Mot de passe du pool (app) et de la connexion d'administration (non utilisée par `doctor`) |
| `DB_APP_LOGIN`, `DB_ADMIN_LOGIN`, `DB_NAME` | `env/dev` | Comptes et nom de la base ; `check_prod_security` compare les deux comptes |
| `DB_HOST`, `DB_PORT` | `env/example`, `env/dev` | Destination du pool : IP de loopback, port 33389 |
| `SSL_CERTFILE`, `SSL_KEYFILE` | `env/example`, défauts de `config.py` | Noms de fichiers (`cert.pem`, `key.pem`), vérifiés par `exists()` seulement |
| Autres clés sensibles de `env/actualisation` et `env/prod`, contenu de `cert.pem` et `key.pem` | — | Non lues par `doctor` (confirmé par la trace) ; surveillées dans les sorties |

## T0 / T1

Même outil et même méthode que FD-SEQUENCIEL-002 :

- **niveau complet** : chemin, type, taille, `mtime_ns`, `ctime_ns`, inode, mode,
  SHA-256 ou cible, pour tout sauf `.git`, `.venv`, `node_modules`, `tmp` et
  `sauvegardes` ;
- **niveau lourd** : les mêmes champs sans SHA-256, `.venv` compris ;
- **`.git`** : HEAD et empreinte du statut, avec `GIT_OPTIONAL_LOCKS=0`.

| Instantané | Heure | Entrées | Comparaison |
|---|---|---:|---|
| T0 | 20:45:55 | 519 214 (7 828 complet / 511 385 lourd) | — |
| T1 | 20:51:14 (5 min 19 s après) | 519 214 | **= T0**, même HEAD, même statut : gate franchi |

## HOME / XDG isolés

Serveur lancé par `env -i` avec `HOME`, `XDG_CONFIG_HOME`, `XDG_STATE_HOME`,
`XDG_CACHE_HOME` et `XDG_DATA_HOME` dans le scratchpad, `PATH=/usr/bin:/bin` et
`LANG=C.UTF-8`, depuis `/tmp`, avec `--no-browser` et sans module.

- Écoute sur `127.0.0.1:8765` seulement ; Host `localhost` et Host étranger : 400 ;
  `Cache-Control: no-store`.
- À la fin, le HOME isolé ne contient que
  `.config/forge-design/recent-projects.json` (77 octets).
- Le vrai `~/.config/forge-design/` est inchangé (4 octobre).
- Aucun `storage/` dans le cwd du serveur.

## Frontière attendue

D'après le code installé et le code forge-mvc lu :

```text
<racine>/.venv/bin/python -s -B -P -u -m forge doctor
cwd = racine SéquenCiel ; nouvelle session ; stdin /dev/null
environnement : PATH, HOME, LANG (liste blanche)
délai 10 s, groupe tué ; 256 Kio par flux ; masquage appliqué aux deux flux
```

Effets attendus : exécution de `config.py`, lecture de `env/example` et `env/dev`,
lectures statiques (entités, migrations, templates, registre d'opt-ins,
détection MFA/RBAC par lecture de texte de `mvc/**/*.py`), puis **une tentative TCP
vers 127.0.0.1:33389, refusée**, d'où un FAIL et le code 1. Aucune écriture.

## Debug Center avant exécution

| Contrôle | Résultat |
|---|---|
| Ouverture (POST `/inspector`, Chromium) | 759 ms ; projet reconnu, synthèse identique aux tickets précédents |
| `doctor` / `audit` / `check` | « non exécuté » / « non exécuté » / « non exécuté » |
| Avertissement de `doctor` | « Il exécute la configuration du projet et peut donc exécuter son code ou accéder aux services qui y sont configurés, notamment la base de données. » |
| GET `/debug` sans exécution | 80 ms ; **aucun processus** avec SéquenCiel pour cwd (surveillant `/proc`) |
| Instantané après ouverture | = T1 |

## Commande réelle

Relevée par `strace` (`execve`) pour les deux exécutions :

```text
execve("/home/roger/Projets/SequenCiel/.venv/bin/python",
       ["/home/roger/Projets/SequenCiel/.venv/bin/python", "-s", "-B", "-P", "-u",
        "-m", "forge", "doctor"], /* 3 vars */) = 0
```

Exécutable : `/usr/bin/python3.13` (cible du lien du venv). Le cwd est la racine
SéquenCiel, et le flux d'entrée est `/dev/null`, ouvert par le serveur en
`O_RDWR|O_CLOEXEC`.

## Première exécution doctor

Clic souris réel (CDP) sur « Exécuter le diagnostic Forge », une fois, avec
`strace -f` attaché au serveur juste avant.

| Mesure | Valeur |
|---|---|
| POST | 1 (`/debug/forge-diagnostic`) |
| Clic → page chargée | 981 ms (sous `strace`) |
| État | `checks-failed` : « Terminé avec le code 1 : au moins un contrôle en échec, ou erreur de la commande » |
| Code retour | 1 |
| `timed_out` | Non (0,82 s sur 10 s) |
| Durée affichée | 0,82 s |
| stdout | 1 124 caractères, 16 lignes de contrôle |
| stderr | vide |
| Troncature | aucune |
| Autres sections | audit et check « non exécuté » |
| Nouveau GET `/debug` | 3 sections « non exécuté » : non persisté |
| Alerte, CSP, exception JS | 0 |

## Processus enfant

| Constat | Exécution 1 | Exécution 2 |
|---|---|---|
| PID / PPID | 1519264 / serveur 1518876 | 1519530 / serveur |
| PGID / SID | 1519264 / 1519264 : **nouvelle session** | 1519530 / 1519530 |
| cwd | `/home/roger/Projets/SequenCiel` | idem |
| argv | exact (ci-dessus) | exact |
| Environnement | **3 variables** : `PATH=/usr/bin:/bin`, `LANG=C.UTF-8`, `HOME` isolé | `/* 3 vars */` dans l'`execve` |
| Descendants | **Aucun** (aucun `clone`, `fork` ni `execve` après le premier) | Aucun |
| Durée de vie | 819 ms (`/proc`) ; `execve` → `exit_group(1)` : 821 ms | 784 ms ; `execve` → `exit_group(1)` : 784 ms |
| Restant | Aucun membre du groupe | Aucun |

Le surveillant `/proc` a relevé le PID 1519530 dans la fenêtre entre `fork` et
`exec`. Son cwd était déjà SéquenCiel, mais il portait encore l'argv et les
7 variables du serveur. Comme le surveillant ne lit l'argv qu'à la première
observation, c'est cet état qu'il a gardé. La trace du même PID montre l'`execve`
exact avec 3 variables. Les 3 `git --no-optional-locks status` relevés sont ceux
de l'outil d'instantané. Un PID vu 0 ms et disparu avant lecture leur est
attribué (plausible, non démontré, comme en FD-SEQUENCIEL-002).

## Réseau enfant

Toutes les opérations réseau de l'enfant, identiques dans les deux exécutions :

| Appel | Destination | Résultat |
|---|---|---|
| `socket(AF_UNIX)` + `connect` × 2 | `/var/run/nscd/socket` | `ENOENT` : nscd absent. Recherche NSS glibc locale, suivie de `nsswitch.conf` puis `/etc/services` |
| `socket(AF_INET, SOCK_STREAM)` | — | fd TCP |
| `connect` (non bloquant) | **`127.0.0.1:33389`** | `EINPROGRESS` |
| `getsockopt(SO_ERROR)` | même socket | **`ECONNREFUSED`** |

- **Une seule** tentative de connexion : le pool `mariadb` s'arrête à la
  première.
- Aucune adresse IPv6, aucune adresse hors loopback, aucune donnée envoyée.
- Le socket du `mariadbd` système n'a pas été touché.
- Côté serveur : uniquement `accept4` et `sendto` sur `127.0.0.1:8765` (Chromium).

## Résultat doctor

```text
Forge doctor — 1.0.0rc9

  [OK]    Python — 3.13.5 — requis >= 3.12
  [OK]    Environnement — env/dev chargé — clés essentielles présentes
  [OK]    Structure MVC — mvc/ valide
  [OK]    Entités — 86 entité(s) valide(s)
  [OK]    Migrations — 251 fichier(s) SQL valide(s)
  [OK]    i18n — translations/ absent — i18n non activé (optionnel)
  [OK]    Templates — 496 template(s) présent(s)
  [OK]    Modules — forge_modules.json absent — aucun module installé
  [OK]    Registre opt-ins — 10 inscrit(s), tous installés
  [OK]    MFA (sécurité) — forge_mvc_mfa disponible — 3 indice(s) MFA détecté(s)
  [OK]    RBAC (sécurité) — forge_mvc_rbac disponible — 2 indice(s) RBAC détecté(s)
  [OK]    Certificats SSL — cert.pem et key.pem présents
  [OK]    Node.js / npm — npm disponible
  [FAIL]  Base de données — connexion via le backend mariadb impossible alors que le projet est configuré — serveur joignable ? accès à jour dans env/ ? (Can't connect to server on '127.0.0.1' (115))
  [OK]    Sécurité prod — privilèges DB séparés et uploads bornés
  [OK]    Code engendré — contrats à jour

0 avertissement(s), 1 erreur(s).
```

Cette sortie ne contient aucun secret (voir Secrets / redaction). L'IP de loopback
qui y figure est la destination configurée, pas une valeur sensible.

## Vérification indépendante

Un script de prévision, écrit sans importer forge-mvc et lancé après T1 et avant
le clic, a rejoué chaque contrôle d'après le code de `doctor.py` lu :

| # | Contrôle | Attendu | Observé | Verdict |
|---|---|---|---|---|
| 1 | Python | OK 3.13.5 | OK 3.13.5 | Juste |
| 2 | Environnement | OK : `APP_NAME`, `APP_ROUTES_MODULE`, `SSL_CERTFILE`, `SSL_KEYFILE` présents et renseignés | OK | Juste |
| 3 | Structure MVC | OK | OK | Juste |
| 4 | Entités | 86 dossiers ; validation `check_model` non rejouée, OK probable | OK, 86 valides | Juste (validation non rejouée) |
| 5 | Migrations | OK, 251 | OK, 251 | Juste |
| 6 | i18n | `translations/` absent | idem | Juste |
| 7 | Templates | 496 `.html` | 496 | Juste |
| 8 | Modules | `forge_modules.json` absent | idem | Juste |
| 9 | Registre opt-ins | backend + 9 opt-ins = 10 paquets, tous dans `.venv` | 10, tous installés | Juste |
| 10 | MFA | 3 indices, `forge_mvc_mfa` installé | idem | Juste |
| 11 | RBAC | 2 indices, `forge_mvc_rbac` installé | idem | Juste |
| 12 | Certificats SSL | `cert.pem` et `key.pem` présents | idem | Juste |
| 13 | Node.js / npm | `/usr/bin/npm` dans `PATH=/usr/bin:/bin` | OK | Juste |
| 14 | Base de données | **FAIL** : `DB_NAME` et `DB_APP_LOGIN` renseignés, connexion refusée | FAIL | Juste ; cause identifiable (serveur injoignable) |
| 15 | Sécurité prod | Comptes app et admin distincts, `UPLOAD_MAX_SIZE` > 0 | OK | Juste |
| 16 | Code engendré | Empreintes `make:auth contrat=2` = contrat courant | « contrats à jour » | Juste |
| — | Code de sortie | 1 (un FAIL) | 1 | Juste |

**16/16 contrôles justes**, ordre conforme à `run_all`.

Un seul élément est **trompeur**, et il ne vient ni de forge-mvc ni de Forge
Design. Le « (115) » final est `EINPROGRESS`, l'errno du `connect()` non bloquant
de MariaDB Connector/C. Le noyau, lui, a rendu `ECONNREFUSED` (111) par
`SO_ERROR`, que le pilote ne cite pas. Le texte reste exploitable : « Can't
connect to server on '127.0.0.1' » et l'indice « serveur joignable ? » désignent
la bonne cause.

## Secrets / redaction

Protocole de FD-SEQUENCIEL-002 : extraction en mémoire dans un seul processus,
aucune valeur en argument, en sortie ou dans un fichier.

| Mesure | Résultat |
|---|---|
| Secrets candidats | 58 occurrences, **49 valeurs distinctes** (`env/actualisation`, `env/dev`, `env/example`, `env/prod`, `config.py`, `cert.pem`, `key.pem`) |
| Identifiants surveillés (§30) | Comptes et nom de base : 3 valeurs distinctes |
| Surfaces | HTML des deux pages de résultat, stdout et stderr extraits, les deux traces `strace` complètes (683 000 caractères chacune), journal du serveur |
| Correspondances de secret | 1 par surface, **toujours la même** : la valeur de `SSL_KEYFILE`, vérifiée en mémoire comme égale au nom de fichier `key.pem`, sur la ligne « cert.pem et key.pem présents » ; faux positif connu (FD-SEQUENCIEL-001) |
| **Vraie valeur sensible retrouvée** | **0** |
| Correspondances d'identifiant | **0** |
| URL | 0 URL de connexion dans les sorties ; les URL navigateur ne portent aucun paramètre |

Le masquage est appliqué par construction (`_displayed` → `redact_debug_text` dans
le code installé), mais il n'avait **rien à masquer** : le message du pilote ne
contient ni compte, ni mot de passe, ni URL. La sortie ne contient aucun
« [masqué] ».

`DB_HOST`, l'IP de loopback, figure dans le message du pilote. Ce n'est pas un
secret, et c'est aussi l'adresse de Forge Design. Il n'est donc pas un critère de
fuite.

## Snapshot après doctor

| Instantané | Heure | Comparaison |
|---|---|---|
| Après doctor n° 1 | 20:52:40 | **= T1** : 0 ajout, 0 suppression, 0 changement, `.venv` compris |

Trace de l'enfant : **1 357 `openat`, tous en lecture seule**. Aucun `mkdir`,
`unlink`, `rename`, `utimensat` ni `truncate`, et aucune ouverture en écriture.
Aucun `__pycache__` créé et aucun `.pyc` modifié, ce que confirment la trace et
l'instantané.

Fichiers du projet lus, en ouvertures :

- `.venv` 357, `mvc/entities` 266, `mvc/services` 195, `mvc/views` 193,
  `mvc/forms` 68, `mvc/routes` 57, `mvc/controllers` 37, `mvc/fixtures` 14 ;
- `env/dev` (2 fois), `env/example` (1 fois), `optins/registry.py` ;
- **ni `env/prod` ni `env/actualisation`** ;
- `cert.pem` et `key.pem` : `stat` seulement, aucun contenu lu.

Les `mvc/**/*.py` sont lus comme texte par la détection MFA/RBAC. **Aucun module
du projet n'est importé**, puisqu'aucun `.pyc` sous `mvc/` n'est ouvert.

Constat : `config.py` n'est pas relu depuis sa source. Python exécute le
bytecode préexistant `__pycache__/config.cpython-313.pyc` du projet (13 octobre,
18:12, ignoré par Git), après l'avoir validé : en-tête cohérent avec la source
actuelle (magic, mtime, taille). L'option `-B` empêche l'écriture du bytecode,
pas sa lecture. C'est le bytecode du projet lui-même, au même niveau de confiance
que sa source.

## Deuxième exécution

Conditions du §33 vérifiées avant de rejouer : 0 écriture, 0 processus restant,
0 fuite, pas de délai dépassé. La base est restée arrêtée (aucun écouteur sur
33389, revérifié).

| Mesure | Exécution 2 |
|---|---|
| POST | 1 |
| Clic → page chargée | 918 ms (sous `strace`) |
| État / code | `checks-failed` / 1 |
| Durée affichée | 0,79 s |
| stderr / troncature | vide / aucune |
| Réseau | identique : nscd × 2 (`ENOENT`), 1 `connect` vers `127.0.0.1:33389`, `SO_ERROR = ECONNREFUSED` |
| `openat` | 1 357, tous en lecture seule |
| Instantané après | 20:54:03, **= T1** |
| Nouveau GET `/debug` | non persisté |

## Déterminisme

stdout et stderr sont **identiques octet pour octet** entre les deux exécutions,
le message du pilote et son « (115) » compris. Seules diffèrent la durée (0,82 s
puis 0,79 s) et les PID, ce qui est attendu. Les traces des deux enfants ont le
même nombre d'appels système (2 977).

## Comparaison project:audit / doctor

| Domaine commun | `project:audit` (FD-SEQUENCIEL-002) | `doctor` | Lecture |
|---|---|---|---|
| Structure | 8 × OK | « mvc/ valide » | Cohérent |
| Configuration | `env/example` et `env/dev` présents ; `APP_NAME`, `APP_ROUTES_MODULE`, `DB_NAME`, `DB_HOST` renseignés (statique) | `config.py` exécuté, clés du cadre présentes ; **base injoignable** (FAIL) | Complémentaire : configuration complète, service arrêté |
| Entités | 86 déclarées ; `page_document` sans `.sql` ni `_base.py` (2 WARN) | 86 valides (`check_model` sur les JSON) | Cohérent : `doctor` ne contrôle pas les fichiers générés |
| Templates | 496 | 496 | Identique |
| Migrations | 251 conformes | 251 valides | Identique |
| Modules | `forge_modules.json` absent : « modules non activés » (trompeur) | même constat, **plus** « Registre opt-ins — 10 inscrit(s), tous installés » | `doctor` corrige la lacune de l'audit |

## Console / CSP

Chromium uniquement, 2 phases de commande et 1 phase d'ouverture, chacune avec un
profil neuf :

- 0 violation CSP, 0 exception JavaScript, 0 alerte d'erreur ; un seul `h1` par
  page ;
- erreurs réseau : uniquement les 3 `GET /favicon.ico` en 404, déjà connus
  (cosmétique) ;
- réseau navigateur : 127.0.0.1:8765 uniquement, aucune ressource externe ;
- journal du serveur : 3 POST au total (`/inspector` et 2 ×
  `/debug/forge-diagnostic`).

## Performances / mémoire

| Moment | RSS du serveur |
|---|---:|
| Démarrage | 46,2 Mio |
| Après ouverture, avant doctor | 87,0 Mio (87 016 Kio) |
| Après doctor n° 1 | 87,1 Mio (87 080 Kio) |
| Après doctor n° 2 | 87,1 Mio (87 080 Kio) |

Le runner ne retient rien. Les deux exécutions ont eu lieu sous `strace` (suivi
de `%network`, `%file` et `%process`) : 0,79 à 0,82 s et un clic → page de 0,9 à
1,0 s **incluent ce surcoût**. Il n'y a pas eu d'exécution non tracée, pour ne pas
dépasser les deux exécutions prévues.

## Snapshot final

Pris à 20:55:07, après l'arrêt de Forge Design : **= T1**, sur 519 214 entrées.
0 création, 0 suppression, 0 contenu modifié, et aucune mtime, ctime ou inode
modifiée.

## Processus finaux

- `SIGTERM` au serveur : arrêt propre, code de sortie 0.
- Aucun processus Forge Design, `doctor`, Chromium ou `strace` ; plus de
  `TracerPid` sur le serveur après chaque détachement ; aucun runtime enfant,
  proxy ou preview.
- Ports 8765, 9341 et 33389 libres.
- Restent les processus préexistants autorisés.

## Observations SéquenCiel

- **Base de développement arrêtée** : FAIL attendu et voulu par le ticket
  (EXPECTED), pas un défaut.
- Configuration exécutable et cohérente : clés du cadre présentes, comptes app et
  admin séparés, uploads bornés, opt-ins inscrits tous installés, empreintes
  `make:auth` à jour.
- Bytecode `__pycache__/config.cpython-313.pyc` présent à la racine, valide pour
  la source actuelle (EXPECTED).
- `page_document` (relevé par l'audit) n'est pas signalé par `doctor` : le
  constat de FD-SEQUENCIEL-002 reste ouvert côté SéquenCiel.

## Observations Forge Design

| # | Observation | Gravité | Classement |
|---|---|---|---|
| 1 | Frontière conforme : argv de la liste fermée, nouvelle session, 3 variables, stdin `/dev/null`, aucun descendant, groupe arrêté, délai et bornes respectés, résultat non persisté | — | EXPECTED |
| 2 | Échec de connexion rendu fidèlement, sans altération ni troncature | — | EXPECTED |
| 3 | L'avertissement affiché avant le clic décrit exactement les effets observés | — | EXPECTED |
| 4 | Le bytecode préexistant du projet est exécuté (`-B` n'empêche que l'écriture). `-X pycache_prefix=<dossier vide>` ferait relire les sources sans toucher au projet. Amélioration possible, pas un défaut | Mineure | EXPECTED |
| 5 | `favicon.ico` en 404 (préexistant) | Cosmétique | FORGEDESIGN-ISSUE |

## Limites Forge

- **Errno trompeur dans le message de connexion** : « (115) » est `EINPROGRESS`,
  l'errno du `connect()` non bloquant de MariaDB Connector/C (`mariadb` 1.1.14),
  et non le refus réel (`ECONNREFUSED`, 111, lu par `SO_ERROR`). `doctor` le
  relaie dans son FAIL, et Forge Design l'affiche tel quel. FORGE-LIMITATION, en
  amont, dans le pilote. L'impact est mineur : l'hôte et l'indice « serveur
  joignable ? » suffisent au diagnostic.
- La famille « Modules » de l'audit (FD-SEQUENCIEL-002) reste aveugle aux opt-ins.
  `doctor` compense par « Registre opt-ins ».

## Classification

| Catégorie | Constats |
|---|---|
| SEQUENCIEL-ISSUE | Aucun nouveau (`page_document`, de FD-SEQUENCIEL-002, reste ouvert) |
| FORGEDESIGN-ISSUE | `favicon.ico` 404 (cosmétique, préexistant) |
| FORGE-LIMITATION | Errno 115 (`EINPROGRESS`) cité à la place du refus dans le message du pilote MariaDB |
| EXPECTED | Code 1 et FAIL « Base de données » avec la DB arrêtée ; recherches nscd locales ; lecture du bytecode préexistant de `config.py` ; `key.pem` réaffiché comme nom de fichier ; IP de loopback dans le message ; durées incluant `strace` |
| UNKNOWN | Un PID éphémère (0 ms), attribué à l'outil d'instantané |
| BLOCKING | **Aucun** |

## Verdict

**SEQUENCIEL_DOCTOR_PASS_WITH_ISSUES**

Conditions de PASS réunies :

- `doctor` s'exécute correctement, deux fois, par un clic réel ;
- l'échec de base est **attendu, fidèle, identifiable et stable** : 16/16
  contrôles justes, sorties identiques ;
- **aucune écriture** : 4 instantanés = T1, `.venv` compris ; 0 ouverture en
  écriture dans les traces ;
- **aucune fuite** : 0 secret sur 49, 0 identifiant sur 3 ;
- **aucune connexion inattendue** : une seule tentative, vers
  `127.0.0.1:33389`, refusée ;
- aucun processus restant, frontière conforme.

Pourquoi « with issues » (§50) : l'exécution révèle une limite non bloquante sur
le chemin même que qualifie le ticket. Le message d'échec de connexion cite
l'errno 115 au lieu du refus. Le défaut est en amont, dans le pilote MariaDB, et
Forge Design le rend fidèlement. Aucune condition de BLOCKED (§51) n'est remplie.

## Recommandation ticket suivant

**FD-SEQUENCIEL-004 : `forge project:check` seul**, troisième niveau de
confiance. Il importe réellement `mvc.routes`, donc les contrôleurs, les services,
les opt-ins et leurs imports transitifs. Il est plus risqué que `doctor` : la
lecture préalable devra couvrir le graphe d'imports, et non plus un seul fichier.
Points à préparer :

- **lire avant le clic** `mvc/routes/__init__.py` et les effets d'import des
  modules qu'il charge (création de pools, de dossiers ou de journaux dans
  `storage/`, threads, sockets AVR, SPICE ou R4, appels réseau) ;
- **garder la base arrêtée**, avec la même vérification `localhost` / IP ;
- **réutiliser `strace`** attaché au serveur : c'est la seule preuve directe des
  écritures et connexions de l'enfant et de ses descendants ;
- s'attendre à des **`__pycache__` préexistants** sous `mvc/` : `-B` les lira
  sans en écrire ;
- et si une écriture apparaît, l'attribuer au code applicatif importé
  (comportement assumé par l'avertissement de `project:check`), pas au runner.

Hors chemin critique : FD-ROUTES-023 (borne de templates). Il y a aussi une
amélioration possible du runner, `-X pycache_prefix`, à discuter avant toute
modification du cœur.

## Fichiers créés

- `docs/rapports/FD-SEQUENCIEL-003.md`

Aucun fichier n'est créé dans SéquenCiel. Les outils (instantané, surveillant
`/proc`, scénario Chromium, prévision `doctor`, filtre de masquage, contrôle des
secrets, analyseur `strace`) et les traces restent dans le scratchpad de la
session, comme `strace` lui-même. Les instantanés compressés sont dans
`tmp/fd-sequenciel-003/` (ignoré par Git) et ne contiennent que des métadonnées et
des empreintes.

## Fichiers modifiés

- `docs/03-roadmap.md` : FD-SEQUENCIEL-003 et son verdict, et la suite
  (FD-SEQUENCIEL-004).

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
`test: qualifier forge doctor sur SéquenCiel (FD-SEQUENCIEL-003)`. Il contient ce
rapport et la roadmap. Il n'est pas poussé : 2 commits d'avance sur `origin/main`.
`FD-CONTRACT-001.md` et les fichiers non suivis historiques sont inchangés.

**SéquenCiel** : HEAD `89fb8a1329b05fb1ca0f8635aa2b1c3bb31e673f`, statut
identique (20 fichiers non suivis, préexistants), **aucun commit et aucune
modification**.
