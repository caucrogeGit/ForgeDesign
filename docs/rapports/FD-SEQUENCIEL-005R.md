# Rapport — FD-SEQUENCIEL-005R

Reprise de Real Preview sur le vrai SéquenCiel avec Forge Design 0.3.0, depuis
Route Explorer et `GET /`, sans Design ni contrat de vue.
Dates : 2026-10-18 (préparation), 2026-10-19 (exécution).

## Objectif

Une question : Forge Design 0.3.0 peut-il démarrer, exposer et arrêter proprement
le vrai SéquenCiel par Real Preview depuis Route Explorer, avec `GET /`, tout en
rendant observables et maîtrisés les effets réels de l'application ?

**Verdict : SEQUENCIEL_REALPREVIEW_BLOCKED.**

Le parcours 0.3.0 fonctionne jusqu'au bout côté Forge Design :

- `GET /` est éligible ;
- un vrai clic déclenche un vrai démarrage ;
- l'échec est rendu proprement : état, cause, logs masqués ;
- rien ne survit, rien n'est écrit dans le projet.

Mais l'application ne démarre pas. Le bootstrap de Real Preview exige
`app.application`, et l'`app.py` de SéquenCiel, hérité du squelette rc3,
n'expose que `application_armee`. Le blocage, annoncé au préflight, a été
observé réellement sur décision du porteur.

## Baseline Forge Design

Dépôt ForgeDesign à `bb83b86` (FD-RELEASE-004), sur `main`, 7 commits d'avance
sur `origin/main`. Seuls autres changements : `FD-CONTRACT-001.md`
(modification utilisateur, préservée) et les fichiers non suivis historiques. Le
code exécuté est celui de la roue installée.

## Artefact utilisé

| Élément | Valeur |
|---|---|
| Roue | `tmp/fd-release-004-dist/forge_design-0.3.0-py3-none-any.whl` (FD-RELEASE-004, RELEASE_READY) |
| SHA-256 | `d7e9f2eccdda838775f6ad2d72c896dbdff06903d5d039fe0c8ab216b072c2b1` (vérifié) |
| Venv | Neuf, dans le scratchpad, installation hors ligne ; ni éditable ni `PYTHONPATH` |
| `pip check` / version | OK / `Forge Design 0.3.0` |
| Paquets | forge-design 0.3.0, forge-mvc 1.0.0rc9 ; aucun module, aucun `.pth` |
| `child_bootstrap.py` installé | Identique à celui de la roue |

## Baseline SéquenCiel

| Élément | Valeur |
|---|---|
| Branche | `main` |
| HEAD | `89fb8a1329b05fb1ca0f8635aa2b1c3bb31e673f` |
| Statut (`GIT_OPTIONAL_LOCKS=0`) | 20 fichiers non suivis, préexistants ; empreinte `cdfb4f1f…`, identique depuis FD-SEQUENCIEL-002 |

Rien n'a été nettoyé, et aucun `.design.json`, `.view.json` ni `.forge-design/`
n'a été créé.

## DB développement

`127.0.0.1:33389` est **restée arrêtée** (aucun écouteur avant, pendant ni
après), et `tmp/base-locale/demarrer.sh` n'a pas été lancé. La question « quand
l'application tente-t-elle la base ? » **reste ouverte** : l'application n'a
traité aucune requête. Pendant tout le cycle, aucun `connect` n'a visé 33389.

## Lecture app.py

`app.py` (774 lignes) a été lu en entier à travers le filtre de masquage.
L'en-tête annonce « Forge 1.0.0-rc.3 ». Au niveau module :

1. `argparse` : `--env` (défaut `dev`), puis
   `os.environ.setdefault("APP_ENV", …)` ;
2. imports de `config` (charge `env/example` et `env/dev`), CSP, en-têtes,
   `mvc.services.securite_csp`, `core.forge` ;
3. **`forge.configure(..., session_store=DbSessionStore(ttl=SESSION_TTL))`** ;
4. **`set_replay_store(DbTotpReplayStore())`**, commenté « paresseux : aucune
   connexion ni écriture au démarrage » ;
5. `Jinja2Renderer(VIEWS_DIR)` et ses globaux (`statique`, `manque_seance`,
   `adresse_copie`, rappel de mot de passe, filtres `enrichi` et `nu`), puis
   `template_manager.register` ;
6. `importlib.import_module(APP_ROUTES_MODULE)` → `mvc.routes`, puis
   `forge.configure(router=…)` ;
7. **`_app = Application(router, middlewares=[…7…])`** : `AuthMiddleware`,
   `PosturePermissionMiddleware`, `ProprieteFamilleMiddleware`,
   `MotDePasseAChangerMiddleware`, `ClasseFermeeMiddleware`,
   `SessionGlissanteMiddleware`, `PresenceMiddleware` ;
8. **`application_armee = _app`**, « pour le point d'entrée WSGI (`wsgi.py`,
   ADR-137) ». Il n'y a **aucun nom `application`** ;
9. `RequestHandler` (serveur de développement : `/health`, `/static`, `/guide`,
   `/media` avant le routage) et `TLSThreadingHTTPServer` : des définitions
   seulement ;
10. le serveur, `logging.basicConfig` et TLS ne s'exécutent que sous
    `if __name__ == "__main__":`.

## Lecture wsgi.py

`wsgi.py` (102 lignes) a été lu en entier. Il est réservé à la production : si
`APP_ENV != "prod"`, il lève `RuntimeError` avant tout import d'`app`. Il expose
`application = avec_la_politique(avec_medias_proteges(create_wsgi_app(application_armee)))`
pour Gunicorn. Forge Design ne le charge pas, et il ne serait de toute façon pas
utilisable par Real Preview, qui fixe `APP_ENV=dev`.

## Lecture child_bootstrap.py

Lu dans la roue 0.3.0 installée :

1. arguments `--port` ;
2. garde d'audit `socket.bind` (loopback seul) ;
3. forge-mvc == 1.0.0rc9, puis `import core.app.wsgi` ;
4. `sys.path.insert(0, cwd)` puis **`importlib.import_module("app")`** ;
5. **`application = getattr(project, "application", None)` ; sans `dispatch` :
   « app.application.dispatch introuvable. », `EXIT_INCOMPATIBLE` (3)** ;
6. `create_wsgi_app(application)`, garde `Host`, bind `127.0.0.1:<port>`,
   `serve_forever`.

Le squelette forge-mvc rc9 du `.venv` définit bien `application =
build_application()` (`skeleton/data/app.py`, l. 131) : c'est la convention que
le bootstrap suit. **SéquenCiel ne la suit pas**, ce que permet Forge, qui ne
réécrit jamais `app.py`.

## Graphe de démarrage

```text
child_bootstrap  (-I -B -u, cwd = SéquenCiel, APP_ENV=dev)
→ import core.app.wsgi                      (Forge, .venv)
→ import app
   → config.py → env/example, env/dev       (os.environ)
   → DbSessionStore, DbTotpReplayStore      (constructeurs d'affectation, paresseux)
   → Jinja2Renderer                         (sans cache de bytecode)
   → mvc.routes                             (375 modules, FD-SEQUENCIEL-004)
       → mvc.services.pdf → weasyprint → ctypes.util → ldconfig/gcc/ld
   → Application(router, 7 middlewares)     (mvc.api_routes absent, ignoré)
→ getattr(app, "application") → None
→ exit 3                                     ← ARRÊT ICI
   (create_wsgi_app, bind, /health, GET / : jamais atteints)
```

Analyse statique AST, sans exécution, depuis `app`, avec les mêmes règles qu'en
FD-SEQUENCIEL-004 :

- 3 modules locaux de plus que `mvc.routes` : `app`, `classe_ouverte` et
  `session_glissante` ;
- 17 modules Forge de plus (sessions-db, mfa replay, application,
  `runtime_error_logger`…) ;
- aucun effet de fichier, de base, de réseau ou de processus au niveau module,
  hormis `load_dotenv`.

Lecture ciblée des constructeurs non suivis par l'analyseur :

- `DbSessionStore.__init__` et `DbTotpReplayStore.__init__` : affectations
  seulement ;
- `Jinja2Renderer` : `Environment(loader=…, autoescape=…)`, sans
  `bytecode_cache` ;
- les 4 middlewares locaux : aucun `__init__`, des constantes au niveau module ;
- `Application.__init__` charge `mvc.api_routes` (absent, `ModuleNotFoundError`
  ignoré) ;
- `runtime_error_logger` n'écrit qu'**à une erreur dispatchée**.

## Route /health

Dans le serveur de développement de SéquenCiel, `/health` est servi par
`RequestHandler.do_GET`. Sous Real Preview, c'est le chemin WSGI de Forge qui le
servirait (`core/app/wsgi.py`, l. 376, `is_health_request` →
`health_response()`), **avant** l'application, sans session ni base.

**Non atteint** dans ce ticket : l'enfant est sorti avant tout bind. Les 16
`connect` du serveur vers le port alloué (`127.0.0.1:60297`) sont les tentatives
de la sonde, toutes sans écouteur.

## Route GET /

Chaîne statique : `GET /` (groupe public) → `HomeController.index` →
`home/index.html` exact et présent. C'est la **seule** route éligible des 629 de
SéquenCiel.

**Non atteinte** : aucune requête applicative n'a été servie.

## Effets potentiels

| Phase | Effets attendus d'après le préflight | Constat |
|---|---|---|
| Import | `os.environ` (`config.py`) ; rafale weasyprint (environ 86 processus, 81 temporaires `/tmp`) ; aucun socket | **Conforme** |
| `/health`, `GET /`, maintien | Session et base possibles à la première requête dispatchée | Non atteints |
| Arrêt | Groupe arrêté par le runner | Sortie de l'enfant avant tout arrêt |

## Gate préflight

**Franchi pour l'observation, avec un blocage annoncé.** Aucun effet destructif
ni non maîtrisable n'est atteignable. L'échec du contrat de point d'entrée,
`app.application` absent, est démontré statiquement.

Sur décision du porteur, le démarrage a été **observé réellement** plutôt
qu'arrêté au préflight. C'est le parcours utilisateur normal, un clic sur Start,
sans aucun contournement.

## Stabilisation

| Contrôle | Résultat |
|---|---|
| Fenêtre VS Code SéquenCiel | **Ouverte** au départ (6 processus, dont `ruff server` et des terminaux) ; question posée, **fermée par le porteur** ; ensuite 0 processus et 0 descripteur sous SéquenCiel |
| nginx, gunicorn, session SSH sortante | Absents |
| Écouteurs 8090, 8092, 33389, 8765, 9341 | Aucun |
| Racine SéquenCiel | mtime inchangée depuis le 2026-10-18 à 20:22 |

## T0 / T1

| Instantané | Heure | Entrées | Comparaison |
|---|---|---:|---|
| T0 | 15:34:19 | 519 214 (7 828 complet / 511 385 lourd) | — |
| T1 | 15:39:31 (5 min 12 s après) | 519 214 | **= T0**, même HEAD, même statut |

Même méthode qu'aux tickets précédents : niveau complet avec SHA-256 hors dossiers
lourds ; `.venv`, `node_modules`, `tmp` et `sauvegardes` en métadonnées ; `.git`
par HEAD et empreinte du statut.

## HOME / XDG isolés

- **Serveur** : `env -i`, `HOME` et les quatre `XDG_*` dans le scratchpad,
  `PATH=/usr/bin:/bin`, `LANG=C.UTF-8`, cwd `/tmp`, `--no-browser`, sans
  module.
- **Écoute** : `127.0.0.1:8765` seulement ; Host `localhost` et étranger → 400 ;
  `no-store` sur `/routes`.
- **À la fin** : le HOME isolé ne contient que `recent-projects.json` (77
  octets), et aucun `storage/` n'a été créé dans le cwd du serveur.

## Éligibilité GET /

| Mesure | Valeur |
|---|---|
| `/routes` | 3,05 s, 4,1 Mo ; 629 chaînes |
| Chaînes `data-real-preview="available"` | **1** : `GET / → HomeController.index → home/index.html → sans contrat` |
| Bouton | « Prévisualiser réellement », avec l'avertissement « La preview réelle exécute le projet Forge sélectionné et peut déclencher ses effets de bord habituels. » |
| Exception propre à SéquenCiel | Aucune : la règle générique de 0.3.0 s'applique |

Les 628 autres chaînes ne sont pas éligibles, pour les raisons de la règle :
POST, dynamique, template non exact, ou présence non vérifiée à cause de la borne
de 128 templates (FD-ROUTES-023).

## Surveillance

| Outil | Couverture |
|---|---|
| `strace -f -ff` (6.13, scratchpad) | Attaché au serveur juste avant le clic et détaché après la phase Stop ; `%process`, `%file` et `%network` ; 89 TID, 5,2 Mo de trace |
| Surveillant `/proc` (2 ms) | 70 232 relevés : PID, PPID, PGID, SID, cwd, argv, **noms** d'environnement, durées |
| `ss -ltnH` (0,2 s) | 333 échantillons pendant tout le cycle |

## Start Preview

Clic souris réel (CDP) sur « Prévisualiser réellement » de la chaîne `GET /`,
dans Chromium.

| Étape | Instant | Depuis le clic |
|---|---|---:|
| Clic | 15:40:46,060 | 0 |
| `execve` de l'enfant | 15:40:47,258 | +1,20 s |
| Rafale weasyprint | 15:40:48,294 → 15:40:49,821 | +2,23 → +3,76 s |
| `exit_group(3)` de l'enfant | 15:40:50,724 | +4,66 s |
| Recueil par le serveur (`wait4`, `WEXITSTATUS == 3`) | 15:40:50,901 | +4,84 s |
| POST → 303 (journal du serveur) | 15:40:50 | — |
| Page d'état chargée | 15:40:52,259 | +6,20 s |
| Bind applicatif, `/health`, page `running` | — | **Jamais** |

Page d'état (`/routes/real-preview?route=%2F`) :

- état **`failed`**, « en échec » ;
- alerte **« Forge incompatible »**, avec le log « Preview réelle :
  app.application.dispatch introuvable. » ;
- pas de bouton Arrêter, puisque rien ne tourne ; « Démarrer à nouveau » est
  proposé ;
- pas d'iframe.

## Commande réelle

```text
execve("/home/roger/Projets/SequenCiel/.venv/bin/python",
       [".../SequenCiel/.venv/bin/python", "-I", "-B", "-u",
        "<scratchpad>/venv/lib/python3.13/site-packages/forge_design/real_preview/child_bootstrap.py",
        "--port", "60297"], /* 4 vars */)
```

- **cwd** : racine SéquenCiel ;
- **environnement** : `APP_ENV`, `HOME` (isolé), `LANG` et `PATH`, soit la liste
  blanche plus `APP_ENV=dev` ;
- **stdin** : `/dev/null` ;
- **session** : nouvelle, pgid = sid = 1571563.

## Processus racine

PID 1571563, enfant du serveur Forge Design (1570985), dans sa propre session.
Il a vécu environ 3,47 s, de l'`execve` à `exit_group(3)`, et le serveur l'a
recueilli : il n'y a pas de zombie.

## Descendants

**86 processus**, identiques à FD-SEQUENCIEL-004 : `ldconfig` × 22, `gcc` × 16,
`collect2` × 16, `ld` × 32. Ils viennent de `mvc/services/pdf.py`, qui importe
weasyprint, lequel passe par `ctypes.util.find_library`.

- Tous sont dans la session du runner (pgid = sid = 1571563).
- Aucun ne vit plus de 70 ms (76 relevés par le surveillant), et aucun ne survit.
- **Aucun** worker, démon, scheduler, ni processus Arduino, R4, SPICE, AVR ou mail.
- Leur environnement hérite, **par noms seulement**, de `DB_APP_PWD`,
  `DB_ADMIN_PWD`, `DB_APP_LOGIN`, `DB_ADMIN_LOGIN`, `SECRET_KEY`,
  `FORGE_MFA_SECRET_KEY` et `SSL_KEYFILE`, chargés par `config.py` (comme en
  FD-SEQUENCIEL-004).

## Threads

Aucun thread applicatif : tous les `clone` de l'enfant sont des lancements de
processus. Le serveur de preview, multithreadé, n'a jamais existé.

## Réseau startup

| Acteur | Opérations |
|---|---|
| Enfant et descendants | **0** `socket`, `bind`, `listen`, `connect` ou `accept` |
| Serveur Forge Design | `accept4` et `sendto` sur `127.0.0.1:8765` (Chromium) ; 16 `connect` de la sonde vers `127.0.0.1:60297`, sans écouteur |
| Nouvelles écoutes (`ss`) | Aucune de l'enfant ni d'un proxy. Seul le port CDP `127.0.0.1:9341` (Chromium du scénario) apparaît puis disparaît ; les autres écoutes de la machine préexistaient et restent inchangées |
| `127.0.0.1:33389`, connexion externe, `0.0.0.0` | Aucun |

## Filesystem startup

| Constat | Valeur |
|---|---|
| Ouvertures en écriture de l'enfant et des descendants | 81, **toutes dans `/tmp`** (temporaires de `ctypes.util`, `gcc` et `collect2`) |
| Suppressions | 81 `unlink` dans `/tmp` ; 0 fichier restant |
| Écritures dans SéquenCiel | **0**, sans `__pycache__`, `.pyc`, `storage/`, `storage/logs/` ni `storage/sessions/` |
| Écritures du serveur Forge Design | 0 (hors `/dev/null`) |
| Modules du projet chargés | 375 (`mvc.routes`, FD-SEQUENCIEL-004) + `app`, `classe_ouverte`, `session_glissante`, soit les 3 prévus par le graphe ; `forge_mvc_sessions_db` chargé |
| `-B` | Aucun bytecode écrit |

## Readiness /health

**Non atteinte.** Il n'y a eu ni bind ni requête `/health`. Le contrôleur a
détecté la sortie de l'enfant, code 3, motif « Forge incompatible », et a rendu
l'état `failed` avec les derniers logs. L'échec vient de l'application, ou plus
exactement de son contrat de point d'entrée : pas de Forge Design, pas du proxy
(jamais créé), pas de `child_bootstrap`, qui a fait son travail, ni de la base,
qui n'a jamais été contactée.

## Snapshot S-START

S-START, pris à 15:41:23 après la sortie de l'enfant et 30 s d'observation
(aucun enfant ni processus SéquenCiel à +10, +20 et +30 s) : **= T1**.

## GET /

**Non atteint** : aucune requête applicative n'est possible sans application
liée. Aucune autre requête vers l'application n'a été faite (§44).

## Réponse GET /

Sans objet.

## Réseau GET /

Sans objet.

## Filesystem GET /

Sans objet.

## Snapshot S-GET

Non pris : la phase `GET /` n'existe pas dans ce cycle. S-START et S-STOP
l'encadrent, tous deux égaux à T1.

## Secrets / redaction

Protocole des tickets précédents : extraction en mémoire, aucune valeur en
argument, en sortie ni dans un fichier.

| Mesure | Résultat |
|---|---|
| Candidats | 49 secrets distincts et 3 identifiants (comptes, nom de base) |
| Surfaces | HTML de la page d'état après Start et après Stop, données du scénario, trace `strace` complète (5,2 Mo, `argv` de tous les `execve` compris), journal du serveur |
| Correspondances de secret | **0** |
| Correspondances d'identifiant | **0** |
| stdout et stderr de l'enfant (logs affichés) | « Preview réelle : app.application.dispatch introuvable. » seulement |
| Environnement des descendants | Noms sensibles hérités (voir Descendants), valeurs jamais lues ni exposées |

## Maintien preview

Sans objet en tant que preview vivante. L'**état d'échec** a été maintenu et
observé pendant environ 60 s, de 15:40:52 à 15:41:50 :

- aucun processus ni descendant tardif ;
- aucune écriture ;
- aucune nouvelle écoute ;
- **aucune requête répétée** par Forge Design : la sonde s'arrête avec l'enfant.

## Snapshot S-LIVE

Équivalent : S-START, pris pendant cette fenêtre, **= T1**.

## Stop Preview

Phase Stop jouée depuis la page d'état : **aucun bouton Arrêter**, puisque
l'état est `failed` et `can_stop` faux. C'est le comportement attendu : il n'y a
rien à arrêter, l'enfant étant déjà sorti et recueilli. Après la phase, l'état
reste `failed`, avec « Démarrer à nouveau ».

## Processus après stop

Aucun processus Forge Design de preview, aucun enfant ni descendant, aucune
session orpheline : `strays` vide au sens du surveillant, et 0 processus avec
SéquenCiel pour cwd.

## Ports après stop

`60297` (port alloué) n'a jamais écouté, et aucun proxy n'a été créé. `8765` est
libéré à l'arrêt du serveur, et `33389` est resté libre.

## Snapshot S-STOP

Pris à 15:41:53 : **= T1**.

## Deuxième cycle

**Non joué.** Le §72 conditionne un second cycle à l'absence de blocage, or le
premier a démontré un blocage **déterministe** : un attribut absent du module,
indépendant de l'état. Rejouer n'aurait rien appris de plus et aurait refait la
rafale weasyprint.

## Déterminisme

La cause est structurelle : `getattr(app, "application")` vaut `None` tant que
`app.py` est inchangé. Les effets d'import sont identiques, au processus près, à
ceux de FD-SEQUENCIEL-004, mesurés deux fois : même lignée de 1 + 86 processus,
mêmes binaires, 81 temporaires, 0 socket, 0 écriture dans le checkout.

## Chromium

Chromium seul : une phase d'ouverture, une phase Start, avec vrai clic sur le
bouton de la chaîne `GET /`, et une phase Stop, chacune avec un profil neuf
détruit ensuite. Toutes les pages ont un seul `h1`.

## CSP / console

| Origine | Constat |
|---|---|
| Forge Design | 0 violation CSP, 0 exception JavaScript ; seulement `GET /favicon.ico` en 404 (× 3, connu) |
| Application en preview | Aucune page applicative chargée, donc aucune console applicative |
| Alerte | Une seule, celle de l'échec (« Forge incompatible »), attendue |

## Origin isolation

Forge Design est resté sur `127.0.0.1:8765`. L'origine dédiée de la preview
n'a jamais été créée, ni proxy, ni iframe. La CSP de la page d'état n'a pas été
élargie, puisqu'il n'y avait pas de `frame-src`. Il n'y a eu aucune écoute
`0.0.0.0`.

## Performances / mémoire

| Mesure | Valeur |
|---|---|
| RSS Forge Design au démarrage / après ouverture | 46,2 / 86,7 Mio |
| RSS Forge Design après Start (page 4 Mo de `/routes` comprise) / après Stop | 111,0 / 111,1 Mio |
| RSS de l'enfant | Non relevée (vie de 3,5 s sous `strace`) |
| Durée de vie de l'enfant | 3,47 s (sous `strace`), dont environ 1,53 s de rafale weasyprint, comparable aux environ 1,4 s de FD-SEQUENCIEL-004 |
| Clic → page d'état | 6,20 s |
| `/routes` | 3,05 s |

## Snapshot final

Pris à 15:43:33, après l'arrêt de Forge Design : **= T1**. Les 519 214 entrées
n'ont aucune différence de contenu, de mtime, de ctime ni d'inode.

## États Git finaux

**SéquenCiel** : HEAD `89fb8a13…` inchangé, statut identique (20 non suivis,
empreinte `cdfb4f1f…`), aucune modification.

**Forge Design** : un commit, rapport et roadmap
(`test: qualifier Real Preview 0.3.0 sur SéquenCiel (FD-SEQUENCIEL-005R)`). Il
n'est pas poussé : 8 commits d'avance sur `origin/main`.
`FD-CONTRACT-001.md` est préservé.

## Observations SéquenCiel

| # | Observation | Classement |
|---|---|---|
| 1 | `app.py` (lignée rc3) n'expose pas `application`, convention du squelette rc9 ; l'application armée de ses 7 middlewares s'y appelle `application_armee`, et seul `wsgi.py`, réservé à `APP_ENV=prod`, la sert sous un nom public | **SEQUENCIEL-ISSUE** (écart à la convention rc9 ; légitime pour Forge, qui ne réécrit pas `app.py`) |
| 2 | Import de weasyprint au niveau module, avec rafale `ctypes.util` à chaque démarrage | SEQUENCIEL-ISSUE (mineure, déjà relevée en FD-SEQUENCIEL-004) |
| 3 | `/static`, `/guide` et `/media` ne sont servis que par le `RequestHandler` de développement (et par nginx en production), pas par le chemin WSGI qu'utilise Real Preview | UNKNOWN : à vérifier lors d'une reprise (la page `GET /` pourrait s'afficher sans ses feuilles ni ses scripts) |
| 4 | Secrets de `env/dev` hérités par les sous-processus | EXPECTED_APPLICATION_SIDE_EFFECT |

## Observations Forge Design

| # | Observation | Gravité | Classement |
|---|---|---|---|
| 1 | Échec rendu proprement : état `failed`, motif « Forge incompatible », log explicite, pas de faux Stop, « Démarrer à nouveau », aucune requête répétée, enfant recueilli, aucun survivant | — | EXPECTED |
| 2 | **Route Explorer propose « Prévisualiser réellement » alors que le démarrage échouera à coup sûr**, pour une raison statiquement détectable : `app.py` n'assigne aucun `application`. L'éligibilité ne regarde que la route, pas le contrat de point d'entrée du projet. C'est contraire à l'esprit du §11 de FD-REALPREVIEW-008 (« ne pas afficher un bouton actif qui échouera plus tard ») | Moyenne | **FORGEDESIGN-ISSUE** |
| 3 | Le bootstrap ne connaît qu'une convention de point d'entrée, `app.application` (squelette rc9). Un projet Forge valide, à `app.py` hérité d'une version antérieure, ne peut pas être prévisualisé | Bloquante pour SéquenCiel | **FORGEDESIGN-LIMITATION** |
| 4 | `-B`, la nouvelle session, la liste blanche d'environnement et la garde de bind restent conformes sur le vrai projet | — | EXPECTED |
| 5 | `favicon.ico` en 404 | Cosmétique | FORGEDESIGN-ISSUE (préexistant) |

## Limites Forge

- forge-mvc rc9 ne réécrit pas `app.py` : un projet né en rc3 garde son point
  d'entrée, c'est le contrat de stabilité de Forge.
- Le point d'entrée WSGI générique de Forge, `create_configured_wsgi_app`, ne
  convient pas à SéquenCiel : il sert l'application **sans ses middlewares**.
  SéquenCiel l'explique dans `wsgi.py` (ADR-137), et c'est pourquoi le bootstrap
  ne doit pas non plus s'en servir comme repli. FORGE-LIMITATION.

## Classification

| Catégorie | Constats |
|---|---|
| BLOCKING | Real Preview impossible sur SéquenCiel : `app.application` absent, contrat de point d'entrée du bootstrap 0.3.0 |
| FORGEDESIGN-LIMITATION | Une seule convention de point d'entrée (`app.application`) |
| FORGEDESIGN-ISSUE | Bouton éligible pour un démarrage voué à l'échec (contrat de point d'entrée non vérifié statiquement) ; `favicon.ico` |
| SEQUENCIEL-ISSUE | `app.py` sans `application` (écart à la convention rc9) ; weasyprint au niveau module |
| FORGE-LIMITATION | `app.py` jamais réécrit ; WSGI générique sans middlewares |
| EXPECTED_APPLICATION_SIDE_EFFECT | 86 descendants et 81 temporaires `/tmp`, nettoyés ; secrets hérités, par noms seulement |
| EXPECTED | Échec propre, aucun survivant, 0 écriture dans le checkout, 0 socket, 0 fuite |
| UNKNOWN | Comportement de `/health`, de `GET /`, de la session et de la base, et service de `/static` : non atteints |

Le blocage n'enlève rien à la sûreté de la frontière : aucune des conditions
BLOCKING du §91 ne porte sur la sécurité. Il n'y a ni fuite, ni écoute hors
loopback, ni connexion externe, ni survivant, ni écriture.

## Verdict

**SEQUENCIEL_REALPREVIEW_BLOCKED**

La preview **ne démarre pas**, ce qui rend impossible la qualification de
`/health`, de `GET /`, du maintien et du Stop (§95). La cause est démontrée
statiquement avant le clic, puis observée réellement :

- le bootstrap 0.3.0 importe `app`, cherche `app.application` et sort avec le
  code 3 ;
- SéquenCiel expose son application armée sous `application_armee`.

Ce qui est qualifié, positivement, sur le vrai projet :

- éligibilité générique de `GET /` ;
- vrai démarrage par le runner partagé (`-I -B -u`, nouvelle session, 4
  variables) ;
- échec rendu fidèlement, sans survivant ;
- 0 écriture dans le checkout (T0 = T1 = S-START = S-STOP = FINAL) ;
- 0 socket de l'application, 0 fuite.

## Recommandation ticket suivant

Avant tout FD-SEQUENCIEL-006, il faut lever ce second blocage. Deux voies, à
trancher par le porteur, qui ne s'excluent pas :

1. **Côté SéquenCiel, minimal**. Un ticket SéquenCiel distinct ajoute à `app.py`
   l'alias public `application = application_armee`, conforme à la convention
   rc9 et exactement l'objet déjà servi par `wsgi.py`, sans changement de
   comportement. Puis reprise de 005R, qui y vérifiera aussi le service de
   `/static` par le chemin WSGI (observation 3).
2. **Côté Forge Design, recommandé en tout état de cause**. Un ticket
   FD-REALPREVIEW-009 ajoute à l'éligibilité un **contrôle statique du contrat
   de point d'entrée** : `app.py` assigne-t-il `application` au niveau module ?
   Sinon, Route Explorer affiche « Preview réelle indisponible : `app.py`
   n'expose pas `application` » au lieu d'un bouton voué à l'échec.

   Toute prise en charge d'un autre nom devrait être **explicite**, déclarée par
   le projet, et jamais devinée : il ne faut ni repli sur `application_armee`,
   ni repli sur le WSGI générique, qui servirait l'application sans ses
   middlewares.

Hors chemin critique : FD-ROUTES-023 (la borne de 128 templates ne laisse ici
qu'une route éligible sur 629).

## Fichiers créés

- `docs/rapports/FD-SEQUENCIEL-005R.md`

Aucun fichier n'est créé dans SéquenCiel. Les outils (instantané, surveillant,
scénario Chromium, graphe depuis `app`, contrôle des secrets, analyseur
`strace`) et les traces restent dans le scratchpad. Les instantanés sont dans
`tmp/fd-sequenciel-005r/` (ignoré par Git).

## Fichiers modifiés

- `docs/03-roadmap.md` : FD-SEQUENCIEL-005R bloqué, et la suite.

Non modifiés : `forge_design/`, les tests, le kit, `FD-CONTRACT-001.md`,
SéquenCiel.

## Validation finale

| Commande | Résultat |
|---|---|
| `git diff --check` (roadmap) et recherche d'espaces finaux (rapport) | OK |
| `ruff format --check` (rapport + roadmap) | Formatés |
| Tests qui lisent `docs/` (`test_design_schema.py`, `test_view_contract_schema.py`) | 45 réussis |
