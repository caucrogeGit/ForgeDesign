# Rapport — FD-SEQUENCIEL-005R2

Requalification de Real Preview sur le vrai SéquenCiel avec Forge Design 0.3.0,
depuis Route Explorer et `GET /`, après l'alias `app.application` de
SC-FORGE-001.
Date : 2026-10-19.

## Objectif

La question restée ouverte en FD-SEQUENCIEL-005R : Forge Design 0.3.0 peut-il
maintenant démarrer réellement SéquenCiel, réussir `/health`, servir `GET /`,
exposer ses ressources, rester stable puis s'arrêter proprement ?

**Verdict : SEQUENCIEL_REALPREVIEW_PASS_WITH_ISSUES.**

SéquenCiel démarre réellement en preview et franchit l'ancien point de blocage :

1. `app.application` est trouvé ;
2. `create_wsgi_app` ;
3. bind loopback ;
4. `/health` 200 ;
5. `GET /`, qui répond 302 vers `/login` ;
6. 16 ressources `/static` en 200 ;
7. 60 s de maintien stable ;
8. Stop complet.

Deux cycles déterministes ont été joués. Il n'y a aucune écriture dans le
checkout, aucune fuite et aucun survivant. Les écarts sont attendus ou non
bloquants : la base arrêtée donne `/login` en 503, et une CSP plus stricte qu'en
production bloque les styles en ligne.

## Baseline Forge Design

Dépôt ForgeDesign à `d4b13ad` (FD-SEQUENCIEL-005R), sur `main`, 8 commits d'avance
sur `origin/main`. Seuls autres changements : `FD-CONTRACT-001.md`
(modification utilisateur, préservée) et les fichiers non suivis historiques. Le
code exécuté est celui de la roue installée.

## Artefact utilisé

| Élément | Valeur |
|---|---|
| Roue | `tmp/fd-release-004-dist/forge_design-0.3.0-py3-none-any.whl` (FD-RELEASE-004) |
| SHA-256 | `d7e9f2eccdda838775f6ad2d72c896dbdff06903d5d039fe0c8ab216b072c2b1` (vérifié) |
| Venv | Neuf, hors ligne, dans le scratchpad ; ni éditable ni `PYTHONPATH` |
| `pip check` / version | OK / `Forge Design 0.3.0` |
| `child_bootstrap.py` installé | Identique à la roue |

## Baseline SéquenCiel

| Élément | Valeur |
|---|---|
| Branche | `main` |
| HEAD | **`07a4aeed0fc7bcb7c8503a63c80ed9144051cc6b`** (« fix(forge): exposer l'application armée sous le nom conventionnel ») |
| Commit précédent | `89fb8a13` (baseline des tickets FD-SEQUENCIEL-002 à 005R) |
| Statut (`GIT_OPTIONAL_LOCKS=0`) | 20 fichiers non suivis, préexistants ; empreinte `cdfb4f1f…` identique |

Rien n'a été nettoyé, et aucun Design, contrat ni `.forge-design/` n'a été créé.

## SC-FORGE-001

Commit `07a4aeed` (auteur : le porteur, 2026-10-19 15:58), 3 fichiers :

| Fichier | Changement |
|---|---|
| `app.py` | **+2 lignes** : `#: Convention publique Forge ; le nom historique reste disponible.` et `application = application_armee`, juste après `application_armee = _app` |
| `tests/test_le_point_d_entree_wsgi.py` | +8 lignes (test SéquenCiel) |
| `SC-FORGE-001-RAPPORT.md` | Rapport SéquenCiel |

`wsgi.py`, les middlewares et le comportement applicatif sont **inchangés**
(`git diff 89fb8a13 07a4aeed -- wsgi.py` est vide).

Vérification du §6, dans le venv SéquenCiel existant, en `-I -B`, cwd = racine,
`APP_ENV=dev`, encadrée par deux instantanés :

```text
app.application is app.application_armee: True | type: Application | dispatch: True
```

Les instantanés avant et après cette vérification sont **identiques** : l'import
d'`app` n'a rien écrit.

## DB développement

`127.0.0.1:33389` est **restée arrêtée** (aucun écouteur au début, entre les
cycles ni à la fin), et `tmp/base-locale/demarrer.sh` n'a pas été lancé. Le
moment exact où l'application tente la base est désormais établi : voir
DB / session.

## Lecture app.py

Seul le passage modifié a été relu (l. 232-238) : `application_armee = _app`,
puis l'alias `application = application_armee`. **Même objet** (`is`), un
`Application` avec ses 7 middlewares, inchangé par ailleurs. La lecture
intégrale du fichier est dans FD-SEQUENCIEL-005R.

## Lecture wsgi.py

Inchangé : la porte `APP_ENV == "prod"`, puis `from app import
application_armee`, puis
`avec_la_politique(avec_medias_proteges(create_wsgi_app(application_armee)))`.
Le chemin de production garde ses enveloppes, et Real Preview n'en utilise
aucune (voir Observations Forge Design).

## Lecture child_bootstrap.py

Identique à la lecture de FD-SEQUENCIEL-005R (roue 0.3.0) :

1. `import app` ;
2. `getattr(app, "application")` avec `dispatch` ;
3. `create_wsgi_app(application)` ;
4. garde `Host` ;
5. bind `127.0.0.1:<port>` ;
6. `serve_forever`, un thread par requête.

La disponibilité est sondée par le contrôleur sur `GET /health`.

## Graphe de démarrage

```text
child_bootstrap  (-I -B -u, cwd = SéquenCiel, APP_ENV=dev)
→ import app → config.py → mvc.routes (375) → application_armee
→ application = application_armee           ← SC-FORGE-001
→ getattr(app, "application")               ← ancien point d'arrêt, franchi
→ create_wsgi_app(application)
→ bind 127.0.0.1:<port>                     → /health (WSGI Forge, 200)
→ proxy Forge Design 127.0.0.1:<proxy>
→ GET / (302) → /login (503, base arrêtée) ; /static servis par le proxy
```

## Gate préflight

**Franchi.** L'alias est une simple liaison de nom, et le préflight complet
d'`app.py` et du graphe d'imports (FD-SEQUENCIEL-004 et 005R) reste valable. Ce
qui est nouveau au-delà de l'import :

- `create_wsgi_app` et le bind, par le code de Forge et du bootstrap ;
- les requêtes réelles, limitées par le ticket à `/health`, `GET /` et ses
  ressources.

## Stabilisation

| Contrôle | Résultat |
|---|---|
| Processus avec SéquenCiel pour cwd | 0, et 0 descripteur ouvert sous SéquenCiel (fenêtre VS Code fermée) |
| nginx, gunicorn, SSH sortant | Absents |
| Écouteurs 8090, 8092, 33389, 8765, 9341 | Aucun |

## T0 / T1

| Instantané | Heure | Entrées | Comparaison |
|---|---|---:|---|
| T0 | 16:03:50 | 519 571 (7 829 complet / 511 741 lourd) | — |
| T1 | 16:09:01 (5 min 11 s après) | 519 571 | **= T0**, même HEAD (`07a4aeed`), même statut |

Il y a 357 entrées de plus qu'en 005R : le rapport SC-FORGE-001 et l'activité
de `tmp/` de SéquenCiel entre les deux tickets. T0 sert de nouvelle référence.

## HOME / XDG isolés

- **Serveur** : `env -i`, `HOME` et les quatre `XDG_*` dans le scratchpad,
  `PATH=/usr/bin:/bin`, `LANG=C.UTF-8`, cwd `/tmp`, `--no-browser`, sans
  module.
- **Écoute** : `127.0.0.1:8765` seulement ; Host `localhost` et étranger → 400.
- **À la fin** : le HOME isolé ne contient que `recent-projects.json` (77
  octets), et il n'y a aucun `storage/` dans le cwd du serveur.

## Éligibilité GET /

`/routes` présente 629 chaînes, dont **1 éligible**, la même qu'en 005R :
`GET / → HomeController.index → home/index.html → sans contrat`, avec le bouton
« Prévisualiser réellement » et l'avertissement d'exécution réelle. La règle
générique de la 0.3.0 s'applique, sans aucune exception propre à SéquenCiel.

## Surveillance

| Outil | Couverture |
|---|---|
| `strace -f -ff -s 200` | Attaché au serveur avant chaque clic Start, détaché après le Stop ; `%process`, `%file` et `%network` ; cycle 1 : 111 TID, 5,4 Mo |
| Surveillant `/proc` (2 ms) | 139 485 relevés sur toute la séance |
| `ss -ltnH` (0,2 s) | Pendant chaque cycle |
| Relevés `/proc` de l'enfant | Au passage en `running`, puis toutes les 10 s : argv, cwd, pgid, sid, stdin, noms d'environnement, threads, RSS, écoutes |

## Start Preview

Clic souris réel (CDP) sur « Prévisualiser réellement », chaîne `GET /`, cycle 1 :

| Étape | Instant | Depuis le clic |
|---|---|---:|
| Clic | 16:10:04,979 | 0 |
| `execve` de l'enfant | 16:10:06,176 | +1,20 s |
| Rafale weasyprint (import) | 16:10:07,111 → 16:10:08,609 | +2,13 → +3,63 s |
| **bind `127.0.0.1:55173`**, fin de l'import d'`app` | 16:10:09,323 | **+4,34 s** |
| **`GET /health` → 200** | 16:10:09,405 | **+4,43 s** |
| Page d'état `running`, avec l'iframe chargée | 16:10:11,183 | **+6,20 s** |

Page d'état :

- **`running`** ;
- iframe `http://127.0.0.1:39857/`, sur l'origine du proxy ;
- origine affichée ;
- bouton « Arrêter la preview réelle » ;
- aucune erreur ni alerte de Forge Design.

## Commande réelle

```text
/home/roger/Projets/SequenCiel/.venv/bin/python -I -B -u \
  <venv>/lib/python3.13/site-packages/forge_design/real_preview/child_bootstrap.py --port 55173
```

| Élément | Valeur (cycles 1 et 2) |
|---|---|
| cwd | `/home/roger/Projets/SequenCiel` |
| PGID / SID | = PID (1583445, puis 1587118) : nouvelle session |
| stdin | `/dev/null` |
| Environnement (noms) | `APP_ENV`, `HOME`, `LANG`, `PATH` |

## Dépassement du blocage précédent

En 005R, l'enfant sortait avec le code 3 juste après `import app`. Cette fois :
il n'y a pas d'`exit_group(3)`, le **bind** a lieu (le bootstrap n'y arrive
qu'après `getattr(app, "application")` et `create_wsgi_app`), l'écoute
`127.0.0.1:55173` appartient à l'enfant (`ss -ltnp`), `/health` répond 200 et
l'état est `running`. L'objet servi est bien `app.application`, qui est
`app.application_armee` (vérification du §6).

## Processus racine

| Mesure | Cycle 1 | Cycle 2 |
|---|---|---|
| PID | 1583445 | 1587118 |
| Durée de vie | 16:10:06,176 → 16:11:10,442 (tué par SIGTERM au Stop) | idem, au Stop |
| Threads au repos (`/proc/…/status`) | 1 | 1 |
| RSS à `running`, puis à +10, +20 et +30 s | 78 508 Kio, constante | 78 448 Kio, constante |

## Descendants

Les **86** de la rafale weasyprint : `ldconfig` × 22, `gcc` × 16, `collect2` × 16
et `ld` × 32, identiques à FD-SEQUENCIEL-004 et 005R, et pendant l'import
seulement.

- Tous sont dans la session du runner.
- **0 descendant** pendant le maintien (relevés à +10, +20 et +30 s).
- Aucun worker, démon, scheduler, ni processus Arduino, R4, SPICE, AVR ou mail.
- Leur environnement hérite, **par noms**, de `DB_*`, `SECRET_KEY` et
  `FORGE_MFA_SECRET_KEY` (comme en FD-SEQUENCIEL-004).

## Threads

L'enfant crée **3 threads par cycle**, un par requête reçue (`ThreadingMixIn`,
`daemon_threads`) : `/health`, `GET /` et `GET /login`. Chacun se termine par
`exit(0)` dès la réponse envoyée. Il n'y a aucun thread persistant ou
applicatif, et l'enfant revient à 1 thread au repos. Les 38 autres `clone` sont
des lancements de processus (`CLONE_VFORK`, rafale weasyprint).

## Réseau startup

| Acteur | Opérations |
|---|---|
| Enfant | `bind` et `listen` `127.0.0.1:55173` ; 2 `connect` locaux vers `/var/run/nscd/socket` (`ENOENT`, résolution NSS) ; **aucune** autre connexion au démarrage |
| Serveur Forge Design | `127.0.0.1:8765` (Chromium) ; proxy `127.0.0.1:39857` ; sonde vers `127.0.0.1:55173` |
| Écoutes `ss` en `running` | Enfant : `127.0.0.1:55173` ; serveur : `127.0.0.1:39857` et `127.0.0.1:8765`. Aucune écoute `0.0.0.0` ni `::` |

## Filesystem startup

| Constat | Valeur |
|---|---|
| Écritures de l'enfant et des descendants (tout le cycle) | 81 ouvertures, **toutes dans `/tmp`** (rafale weasyprint), 81 `unlink`, 0 restant |
| Écritures dans SéquenCiel | **0** : aucun `storage/`, `storage/logs/`, `storage/sessions/`, `uploads/`, `__pycache__/` ni `.pyc` |
| Écritures du serveur Forge Design | 0 (hors `/dev/null`) |
| `-B` | Aucun bytecode écrit (instantanés `.venv` compris) |

## Readiness /health

`GET /health`, reçu à 16:10:09,405 dans un thread dédié, répond **200** en moins
de 1 ms. Il est servi par le chemin WSGI de Forge (`is_health_request`, avant
l'application) :

- aucune ouverture de fichier ;
- aucune session ;
- aucune connexion à la base.

C'est conforme au §34.

## Snapshot S-START

Pris à 16:10:25, en état `running`, après le premier chargement de l'iframe :
**= T1**.

## GET /

Unique requête métier volontaire : celle de l'iframe, au chargement de la page
d'état. Il n'y a eu ni login, ni navigation, ni clic métier, ni crawl.

| Requête (reçue par l'application) | Thread | Statut | Durée |
|---|---|---:|---:|
| `GET /` (16:10:10,746) | 1583727 | **302 Found** → `/login` | 6 ms |
| `GET /login` (16:10:10,776) | 1583729 | **503 Service Unavailable** | 138 ms |

La redirection de `GET /` vers `/login` est **suivie automatiquement par
l'iframe**. C'est le comportement du navigateur, que le ticket ne peut ni
empêcher ni « ne pas suivre » (§46). La destination est connue et publique
(`AuthController.login_form`), ce n'est pas une navigation volontaire.

## Réponse GET /

- `GET /` : **302**, pour un visiteur anonyme qui n'a pas de session. Le
  thread de `GET /` n'ouvre **aucun fichier** et ne fait **aucune connexion**,
  ni base ni session.
- La page finalement affichée dans l'iframe est celle de `/login` : **503**,
  base indisponible. C'est la page d'erreur de l'application, avec ses feuilles
  et ses scripts.

## Ressources /static

**L'inconnue de 005R est levée.** Les 16 ressources demandées par la page (4 CSS
et 12 JS, dont `vendor/htmx.min.js` et `vendor/preline.js`) répondent toutes
**200** :

- elles sont servies **par le proxy de Forge Design**, qui lit lui-même
  `<projet>/static` (FD-REALPREVIEW-003 : lecture confinée, sans lien, 8 Mio
  au plus) ;
- **aucune n'atteint l'application** : 0 requête `/static` reçue par l'enfant ;
- aucune exécution de code du projet n'a lieu pour les servir.

Le `RequestHandler` de développement de SéquenCiel, qui sert `/static` hors du
WSGI, n'est donc pas nécessaire en preview. Classement : **EXPECTED**.

## Ressources /guide et /media si réellement demandées

Elles ne sont **pas demandées** par la page, donc non testées (§42).

## DB / session

| Requête | Base | Session |
|---|---|---|
| `/health` | Non | Non |
| `GET /` | **Non** (0 `connect`) | Non |
| `GET /login` | **Oui** : une tentative `127.0.0.1:33389` à 16:10:10,847, `SO_ERROR = ECONNREFUSED` | **Oui** : création de session |

L'attribution est démontrée par le code et par la trace :

- `AuthController.login_form` (`mvc/controllers/auth_controller.py`, l. 83-86)
  « garantit une session (donc un `csrf_token`) même pour un visiteur
  anonyme » : `get_session_store().create()` ;
- le magasin est `DbSessionStore` (posé par `app.py`) ;
- dans ce thread, la trace montre le balayage des `entry_points` de
  `core.database.backend._discover()`, le premier import paresseux de
  `mariadb`, puis le `connect` refusé ;
- résultat : `DatabaseUnavailableError`, donc **503**. L'exception est gérée, et
  `runtime_error_logger` n'écrit rien.

La base n'a pas été démarrée (§48).

## Réseau GET /

| Acteur | Opérations |
|---|---|
| Navigateur → proxy | `127.0.0.1:39857` : `GET /`, `GET /login`, 16 × `/static` |
| Proxy → application | `127.0.0.1:55173` : `GET /` et `GET /login` seulement |
| Application → base | 1 `connect` `127.0.0.1:33389`, refusé (`/login`) |
| Connexion externe | **Aucune** |

## Filesystem GET /

Aucune écriture dans SéquenCiel ni ailleurs. Le thread de `GET /` n'ouvre aucun
fichier ; celui de `/login` lit des modules (`mariadb`, entry points) et des
templates, sans rien écrire.

## Snapshot S-GET

`GET /` a lieu au chargement même de la page d'état : S-START (16:10:25) est pris
**après** `GET /`, `/login` et les ressources, et vaut S-GET. Il est **= T1**. La
segmentation fine des phases repose sur les horodatages `strace` ci-dessus.

## Secrets / redaction

| Mesure | Résultat (deux cycles) |
|---|---|
| Candidats | 49 secrets distincts et 3 identifiants |
| Surfaces | HTML de la page d'état en marche et arrêtée, données du scénario (URL de toutes les requêtes), traces `strace` complètes (5,4 Mo par cycle : `argv`, en-têtes et lignes HTTP tronqués à 200 octets, réponses de l'application), journal du serveur |
| Correspondances de secret | **0** |
| Correspondances d'identifiant | **0** |
| stdout et stderr de l'enfant | Non affichés par Forge Design en état `running` ; présents seulement en tampon mémoire du contrôleur |
| Environnement des descendants | Noms sensibles hérités, valeurs jamais lues ni exposées |

## Maintien preview

59 s de maintien (cycle 1), sans navigation :

- même PID ;
- 1 thread ;
- RSS constante ;
- 0 descendant ;
- **0 requête** de Chromium et 0 requête répétée de Forge Design (pas de sonde
  périodique) ;
- écoutes stables (`55173`, `39857`, `8765`) ;
- aucune écriture.

## Snapshot S-LIVE

Pris à 16:11:10, après 45 s de maintien : **= T1**.

## Stop Preview

Clic réel sur « Arrêter la preview réelle », sur la même page, cycle 1 :

| Étape | Instant | Depuis le clic |
|---|---|---:|
| Clic | 16:11:10,321 | 0 |
| Enfant : `+++ killed by SIGTERM +++` | 16:11:10,442 | +121 ms |
| Page « arrêtée », proxy fermé | 16:11:11,491 | +1,17 s |

Ensuite : état `stopped`, sans iframe ni bouton Arrêter.

## Processus après stop

L'enfant 1583445 est terminé, et son groupe compte **0 membre** (`ps` par PGID),
sans aucun processus d'une autre session. Il n'y a aucun orphelin, démon ni
worker, et 0 processus avec SéquenCiel pour cwd.

## Ports après stop

`55173` (application) et `39857` (proxy) sont fermés ; seul `127.0.0.1:8765`
(Forge Design) écoute encore. `33389` est resté libre.

## Snapshot S-STOP

Pris à 16:11:27 : **= T1**.

## Deuxième cycle

Les conditions du §67 sont réunies : pas de fuite, pas d'effet incontrôlé, pas
de survivant, pas de blocage. Cycle 2 de 16:14:10 à 16:15:38 :

- `running` en 5,91 s ;
- application sur `127.0.0.1:56891` et proxy sur `127.0.0.1:49315` ;
- même argv, même session, mêmes 4 variables ;
- maintien stable à 78 448 Kio ;
- Stop en 1,37 s ;
- S-START, S-LIVE et S-STOP **= T1**.

## Déterminisme

| Axe | Cycle 1 / cycle 2 |
|---|---|
| Lignée (`execve` par binaire) | Identique (1 + 22 + 16 + 16 + 32) |
| Threads de requête | 3 et 3 (`/health`, `/`, `/login`) |
| Requêtes reçues (application, proxy) et statuts | Identiques : `/health` 200, `/` 302, `/login` 503, 16 `/static` 200 |
| Requêtes du navigateur (hors ports et versions) | Identiques |
| Tentatives de base | 1 et 1 (`/login`) |
| Bind, écritures, `unlink`, restants | Identiques (1 bind ; 81 / 81 / 0) |
| Instantanés | Tous = T1 |
| Variations | PID, ports (55173/39857, puis 56891/49315), durées (Start 6,20 / 5,91 s, Stop 1,17 / 1,37 s) |

## Chromium

Chromium seul : phase d'ouverture, puis une phase par cycle avec vrai clic sur
Start, maintien sans navigation et vrai clic sur Stop dans la même page, chaque
fois avec un profil neuf détruit ensuite. Toutes les pages de Forge Design ont un
seul `h1`, sans alerte.

## CSP / console

| Origine | Constat |
|---|---|
| Forge Design | **0** violation CSP, 0 exception ; `GET /favicon.ico` en 404 (× 2, connu) |
| Application en preview (iframe) | **1** message : « Applying inline style violates … `style-src 'self'` » ; le 503 de `/login`, attendu |
| Ressources statiques | 16/16 en 200, aucune erreur |

La violation de style vient de la CSP du **cœur Forge**, posée par
`create_wsgi_app`. En production, SéquenCiel la complète par
`avec_la_politique` dans `wsgi.py` (ADR-112) pour autoriser les attributs
`style`. Real Preview sert `app.application` sans cette enveloppe : les styles en
ligne y sont bloqués (voir Observations Forge Design).

## Origin isolation

| Rôle | Origine |
|---|---|
| Forge Design | `http://127.0.0.1:8765` |
| Proxy (origine de l'iframe) | `http://127.0.0.1:39857`, puis `49315` |
| Application (jamais exposée au navigateur) | `127.0.0.1:55173`, puis `56891` ; le port du runner n'apparaît pas dans la page |

Il n'y a aucune écoute `0.0.0.0`. La CSP `frame-src` de la page d'état n'est
élargie qu'au proxy actif (FD-REALPREVIEW-008).

## Performances / mémoire

| Mesure | Valeur |
|---|---|
| RSS Forge Design au démarrage / après ouverture | 46,2 / 85,9 Mio |
| RSS Forge Design en `running` (cycle 1 / 2) | 108,5 / 144,0 Mio |
| RSS Forge Design après Stop (cycle 1 / 2) | 108,5 / 151,3 Mio |
| RSS de l'enfant en marche | 78,5 Mio, stable |
| Start (clic → `running`) | 6,20 / 5,91 s, dont environ 1,5 s de rafale weasyprint et environ 4,3 s jusqu'au bind |
| `/health` | Moins de 1 ms |
| `GET /` / `GET /login` | 6 ms / 138 ms |
| Stop (clic → enfant tué / page) | 121 ms / 1,17 s |

La RSS de Forge Design augmente à chaque affichage de `/routes` (page de 4 Mo,
629 chaînes) : elle ne diminue pas après le Stop. C'est à surveiller ; il ne
s'agit pas d'un banc d'essai.

## Snapshot final

Pris à 16:16:49, après l'arrêt de Forge Design : **= T1**, sur 519 571 entrées,
sans aucune différence de contenu, de mtime, de ctime ni d'inode.

## États Git finaux

**SéquenCiel** : HEAD `07a4aeed…` inchangé, statut identique (20 non suivis,
empreinte `cdfb4f1f…`), aucune modification.

**Forge Design** : un commit, rapport et roadmap
(`test: requalifier Real Preview sur SéquenCiel (FD-SEQUENCIEL-005R2)`). Il n'est
pas poussé : 9 commits d'avance sur `origin/main`. `FD-CONTRACT-001.md` est
préservé.

## Observations SéquenCiel

| # | Observation | Classement |
|---|---|---|
| 1 | SC-FORGE-001 lève le blocage : alias `application`, même objet, sans autre changement | EXPECTED |
| 2 | Pour un visiteur anonyme, `GET /` redirige vers `/login`, qui crée une session `DbSessionStore` : avec la base arrêtée, **503**. La preview n'affiche donc pas d'écran d'accueil fonctionnel, mais la page d'erreur de l'application | EXPECTED, conséquence voulue de la base arrêtée (§85) |
| 3 | `/login` sollicite la base pour un simple affichage (session et `csrf_token` créés en base dès la page de connexion) | SEQUENCIEL-ISSUE mineure, choix d'architecture à examiner |
| 4 | Import de weasyprint au niveau module, avec 86 processus `ctypes.util` à chaque démarrage | SEQUENCIEL-ISSUE (déjà relevée en 004 et 005R) |
| 5 | Secrets de `env/dev` hérités par les sous-processus | EXPECTED_APPLICATION_SIDE_EFFECT |

## Observations Forge Design

| # | Observation | Gravité | Classement |
|---|---|---|---|
| 1 | Cycle complet conforme sur le vrai projet : runner partagé, nouvelle session, liste blanche, bind loopback, `/health`, proxy, maintien sans sonde, Stop en SIGTERM au groupe, aucun survivant, aucune écriture | — | EXPECTED |
| 2 | `/static` servi par le proxy, en lecture confinée, sans exécuter de code : l'inconnue de 005R est levée | — | EXPECTED |
| 3 | La preview sert `app.application` par `create_wsgi_app` **nu** : les enveloppes de production propres au projet (`wsgi.py` de SéquenCiel : CSP complétée par ADR-112, médias protégés) ne s'appliquent pas, d'où les styles en ligne bloqués. C'est un écart de rendu entre preview et production, connu par contrat | Mineure | FORGEDESIGN-LIMITATION |
| 4 | L'iframe suit automatiquement les redirections de l'application (`/` → `/login`) : une « seule requête métier » ne peut pas être garantie quand la route répond 302 | Information | EXPECTED (comportement du navigateur) |
| 5 | La RSS de Forge Design augmente avec les affichages de `/routes` sur un grand projet (85,9 → 151,3 Mio) | À surveiller | UNKNOWN |
| 6 | FD-REALPREVIEW-009 (contrôle statique du point d'entrée, issu de 005R) reste pertinent pour d'autres projets, mais n'est plus bloquant pour SéquenCiel | Mineure | FORGEDESIGN-ISSUE (ouvert) |
| 7 | `favicon.ico` en 404 | Cosmétique | FORGEDESIGN-ISSUE (préexistant) |

## Limites Forge

- La CSP par défaut du cœur (`style-src 'self'`) ferme les attributs `style` ;
  SéquenCiel doit la compléter par sa propre enveloppe en production (ADR-112).
  FORGE-LIMITATION.
- `forge-mvc` ne réécrit pas `app.py`. L'alias `application` reste à la charge
  du projet, ce que SC-FORGE-001 a fait.

## Classification

| Catégorie | Constats |
|---|---|
| EXPECTED | Démarrage, `/health` 200, `GET /` 302, `/static` 200 par le proxy, maintien stable, Stop complet, déterminisme, 0 écriture, 0 fuite, 0 survivant ; 503 de `/login` avec la base arrêtée |
| EXPECTED_APPLICATION_SIDE_EFFECT | 86 descendants et 81 temporaires `/tmp` nettoyés ; 1 `connect` refusé vers 33389 (session de `/login`) ; noms sensibles hérités |
| SEQUENCIEL-ISSUE | Session en base dès l'affichage de `/login` ; weasyprint au niveau module |
| FORGEDESIGN-LIMITATION | Preview sans les enveloppes WSGI propres au projet (styles en ligne bloqués) |
| FORGEDESIGN-ISSUE | Contrôle statique du point d'entrée (FD-REALPREVIEW-009, ouvert) ; `favicon.ico` |
| FORGE-LIMITATION | CSP du cœur sans attributs `style` |
| UNKNOWN | Croissance de la RSS de Forge Design avec `/routes` |
| BLOCKING | **Aucun** |

## Verdict

**SEQUENCIEL_REALPREVIEW_PASS_WITH_ISSUES**

| Condition | Constat |
|---|---|
| `GET /` éligible | Oui (1 route sur 629, règle générique) |
| Start réussi | Oui : `running` en environ 6 s, ancien point d'arrêt franchi |
| `/health` réussi | Oui : 200, sans base ni session |
| `GET /` servi | Oui : 302 vers `/login` (comportement applicatif pour un anonyme) |
| Ressources suffisantes | Oui : 16/16 `/static` en 200 |
| Stop complet | Oui : SIGTERM en 121 ms, groupe vide, ports fermés |
| Aucune fuite | Oui : 0 secret, 0 identifiant |
| Aucun effet problématique | Oui : 0 écriture dans le checkout sur 6 instantanés et le final, 0 connexion externe |

« With issues » (§85) parce que la base arrêtée donne `/login` en 503, qu'il
reste des dettes SéquenCiel (session en base à l'affichage, weasyprint), et
qu'il y a une limite non bloquante de Forge Design : pas d'enveloppes WSGI
propres au projet, d'où la CSP plus stricte.

## Recommandation ticket suivant

**FD-SEQUENCIEL-006 : première édition contrôlée sur SéquenCiel**, dernier
ticket principal du parcours d'intégration réel. Il pourra s'appuyer sur ce qui
est maintenant qualifié :

- lecture ;
- `project:audit`, `doctor`, `project:check` ;
- Real Preview depuis Route Explorer.

À préparer pour 006 :

- l'édition exige un Design et un contrat de vue dans SéquenCiel : leur création
  est un choix du porteur (Phase 12), à faire dans un ticket SéquenCiel
  distinct, versionné ;
- la preview d'un template édité ne sera visible que si la route reste éligible
  (`GET /` → `home/index.html`), et derrière une base arrêtée la page servie
  reste `/login` en 503 ;
- démarrer la base de développement serait un changement d'infrastructure à
  décider explicitement.

Hors chemin critique :

- FD-REALPREVIEW-009 (point d'entrée) ;
- FD-ROUTES-023 (une seule route éligible sur 629) ;
- l'étude d'une prise en charge **déclarée** des enveloppes WSGI du projet dans
  la preview, sans devinette ;
- la mémoire de `/routes` sur un grand projet.

## Fichiers créés

- `docs/rapports/FD-SEQUENCIEL-005R2.md`

Aucun fichier n'est créé dans SéquenCiel. Les outils (orchestrateur de cycle,
scénario Chromium, instantané, surveillant, contrôle des secrets, analyseurs) et
les traces restent dans le scratchpad. Les instantanés sont dans
`tmp/fd-sequenciel-005r2/` (ignoré par Git).

## Fichiers modifiés

- `docs/03-roadmap.md` : FD-SEQUENCIEL-005R2 et la suite (FD-SEQUENCIEL-006).

Non modifiés : `forge_design/`, les tests, le kit, `FD-CONTRACT-001.md`,
SéquenCiel.

## Validation finale

| Commande | Résultat |
|---|---|
| `git diff --check` (roadmap) et recherche d'espaces finaux (rapport) | OK |
| `ruff format --check` (rapport + roadmap) | Formatés |
| Tests qui lisent `docs/` (`test_design_schema.py`, `test_view_contract_schema.py`) | 45 réussis |
