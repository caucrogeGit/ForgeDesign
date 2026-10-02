# Preview réelle — contrat

Contrat normatif de FD-REALPREVIEW-001, corrigé par FD-REALPREVIEW-001A
(confinement réseau garanti avant le bind). Il fixe les décisions dont
dépendent FD-REALPREVIEW-002 (runner local) et les tickets d'intégration Web
suivants. Le runner est implémenté par FD-REALPREVIEW-002 et le proxy par
FD-REALPREVIEW-003 (voir « Implémentation du runner » et « Implémentation du
proxy ») ; iframe et UI restent à venir.

Les faits Forge cités ont été vérifiés statiquement dans `forge-mvc==1.0.0rc9`
(version épinglée par Forge Design), le paquet installé et le dépôt Forge local
au commit `73a956e587e5f169c028415e0e540c149cbaff56`
(`v1.0.0-rc.9-7-g73a956e5`, même `version = "1.0.0rc9"`). Aucune application
Forge n'a été lancée pour les établir.

## Implémentation du runner

FD-REALPREVIEW-002 implémente ce contrat dans `forge_design/real_preview/` :

- `RealPreviewController` (`start(project_root)`, `stop()`, `status()`),
  synchrone ; `RealPreviewConfig`, `RealPreviewStatus`, `RealPreviewState`,
  `RealPreviewError` ;
- `child_bootstrap.py`, exécuté par l'interpréteur du projet, jamais importé
  ni exporté par Forge Design.

Précisions et écarts découverts en implémentant, sans changer le contrat :

- **Code de sortie 6** : bind impossible pour une autre raison que
  `EADDRINUSE`, par exemple un refus de la garde d'audit si l'adresse était
  modifiée.
- **Survivants du groupe** : dès que le leader se termine (arrêt, échec ou
  sortie spontanée), `SIGKILL` est envoyé au groupe, *avant* de récolter le
  leader. Son PID, encore réservé tant qu'il n'est pas récolté, garantit que le
  groupe visé est bien le sien (`os.waitid(..., WNOWAIT)`). Sans `os.waitid`,
  le leader est récolté directement : cette garantie n'existe pas.
- **Arrêt pendant `starting`** : `stop()` interrompt l'attente de readiness de
  `start()`, qui rend l'état courant, puis arrête le groupe.
- **Préconditions** : plateforme, racine, projet non reconnu, interpréteur,
  bootstrap ou port indisponible donnent `failed` avec une raison, sans
  lancement. Seul un usage incohérent (start pendant
  `starting`/`running`/`stopping`) lève `RealPreviewError`. Une
  configuration invalide lève `ValueError` à la construction.
- **Après `stop()`** : `project_root`, `exit_code` et les logs restent
  visibles jusqu'au prochain `start()`, qui les réinitialise.
- **Logs** : lignes sans terminaison, du plus ancien au plus récent ; une
  ligne trop longue garde ses `max_log_chars` premiers caractères et le reste
  est lu puis jeté.
- **Sonde** : ni proxy d'environnement (`http_proxy`…), ni redirection
  suivie ; corps lu au plus 1 024 octets.
- **Paquet** : `forge_design.real_preview` est ajouté à la liste explicite des
  paquets de `pyproject.toml`, faute de quoi la wheel ne contiendrait pas le
  bootstrap.

## Implémentation du proxy

FD-REALPREVIEW-003 implémente le proxy B de « Iframe / proxy » dans
`forge_design/real_preview/proxy.py` :
`create_real_preview_proxy(controller, *, frame_ancestor_origin, host,
port, config)` renvoie un `RealPreviewProxyServer` (listener
`127.0.0.1:<port proxy>`, sans thread caché), configuré par
`RealPreviewProxyConfig` (délai 10 s, réponses et statiques bornés à 8 Mio).
Il ne consomme que `controller.status()`.

Précisions et écarts découverts en implémentant, sans changer le contrat :

- **Origine d'encadrement** : fournie explicitement, exactement
  `http://127.0.0.1:<port>`. Le proxy n'en invente aucune et ne pose jamais
  `frame-ancestors *`.
- **CSP** : chaque politique active est découpée comme le fait la
  spécification (`,` puis `;`). Seule la directive `frame-ancestors` est
  remplacée, et les politiques multiples restent des en-têtes séparés. Si
  aucune ne contient la directive, une politique
  `frame-ancestors <origine>` est ajoutée. `Report-Only` est intacte.
- **Réponses d'erreur du proxy** (400, 403, 404, 405, 502, 503, 504) : texte
  brut, `no-store`, `nosniff`, `default-src 'none'; frame-ancestors
  <origine>`.
- **En-têtes de requête** : liste blanche positive (`Accept`,
  `Accept-Language`, `User-Agent`, `Cookie`, `Referer`, `Origin`,
  `Cache-Control`, `Pragma`, en-têtes conditionnels et `HX-*`). Ne sont
  jamais relayés : `Accept-Encoding` (la cible répond sans compression, le
  corps reste opaque), `Authorization` (routes publiques seulement), les
  en-têtes hop-by-hop et `X-Forwarded-*`.
- **Corps amont** : lu au plus jusqu'à la borne + 1. Un corps plus court que
  son `Content-Length` donne 502, parce que `http.client` rend un corps
  partiel sans erreur. Une durée totale de lecture supérieure au délai donne
  504.
- **Statiques** : `/static/` est décodé (`%XX` en UTF-8 strict) ; `%2F` et
  `%5C` sont refusés. La politique lexicale `unsafe_relative_path` est
  extraite de `source_parts` et partagée. Code 400 pour un chemin refusé,
  404 pour un fichier absent, 403 pour un lien, un fichier non ordinaire, un
  fichier trop gros ou modifié pendant la lecture. Le type MIME vient de la
  table intégrée de `mimetypes`, sans `/etc/mime.types`, pour un résultat
  déterministe.
- **Requêtes refusées** : un corps annoncé (≤ 1 Mio) est lu puis jeté avant
  la réponse 400 ou 405, pour que la fermeture n'efface pas la réponse (RST).
  Un délai de 15 s s'applique côté client.
- **HEAD** : Forge rc9 ne route pas HEAD vers GET (seul `/health` répond).
  `HEAD /` donne donc le 405 de la cible, relayé tel quel.
- **Cookies** : relayés dans les deux sens, sans ajout. Ils ne sont pas
  isolés par port : l'origine du proxy partage les cookies `127.0.0.1` avec
  Forge Design et le runner. Forge Design n'en pose aucun.

## Définition

> Une preview réelle est le rendu d'une vue par une instance **réellement
> exécutée du projet Forge cible**, dans un processus séparé de Forge Design.

Ce n'est ni `render_preview(...)` (preview statique) ni
`generate_simple_template(...)` (template généré). C'est la réponse HTTP que
l'application du projet produit elle-même, avec son code, sa configuration,
ses données et ses dépendances.

Jusqu'ici, Forge Design lit le projet statiquement, sans l'importer ni
l'exécuter. La preview réelle franchit volontairement cette frontière, et
uniquement par le mécanisme décrit ici.

## Niveaux de preview

| Niveau | Entrée | Projet exécuté | Ce qui est montré |
|---|---|---|---|
| 1. Preview statique | Design + données fictives | Non | Structure du Design, inerte |
| 2. Template généré | Design + contrat | Non | HTML/Jinja produit, diff, écriture SAFEWRITE |
| 3. Preview réelle | Projet sur disque | **Oui** | Route réellement rendue par l'application |

Les trois niveaux restent distincts dans l'architecture (paquets séparés) et
dans l'UI (libellés et emplacements distincts). Un niveau ne remplace jamais
silencieusement un autre : une preview réelle indisponible n'est pas
remplacée par la preview statique, et inversement.

## Frontière d'exécution

```text
Forge Design (processus serveur, 127.0.0.1)
     │
     │ contrôle explicite (action utilisateur)
     ▼
RealPreviewController (détenu par la composition)
     │
     │ processus enfant, shell=False, nouveau groupe de processus
     ▼
<projet>/.venv/bin/python -I -u <child_bootstrap.py de Forge Design> --port <port>
     │  1. garde d'audit socket.bind (loopback seulement)
     │  2. import app  →  config.py, env/example, env/dev, build_application()
     │  3. create_wsgi_app(app.application)
     ▼
serveur WSGI du bootstrap, lié à 127.0.0.1:<port>   ← bind après toute configuration projet,
                                                      valeurs jamais lues dans le projet
```

Ce qui peut être exécuté : uniquement le bootstrap enfant fourni par Forge
Design, avec l'interpréteur du projet, qui importe `app.py` comme module
(voir « Commande Forge »). Rien d'autre : ni commande fournie par le
navigateur, ni script du projet, ni `forge` CLI, ni `python app.py`.

## Processus séparé

Décision : **le projet cible n'est jamais importé dans le processus Python de
Forge Design.** Sont interdits comme architecture, dans tout module de Forge
Design exécuté par Forge Design : `import mvc`, `import config`,
`import bootstrap`, `from app import …`, `importlib` sur un module du projet,
ajout de la racine du projet à `sys.path`, `runpy`, `exec` de sources du
projet.

Le projet doit bien être exécuté quelque part : il l'est **dans le processus
enfant uniquement**, où le bootstrap l'importe. Le bootstrap est un script
autonome (bibliothèque standard seulement) qui n'importe jamais
`forge_design` et n'est jamais importé par Forge Design.

Raison : le code cible peut modifier `sys.path` ou `os.environ`, ouvrir une
base, lancer des threads, installer des handlers de signaux ou des hooks
globaux, lire des secrets, ou faire planter l'interpréteur. Seul un processus
séparé garantit que ces effets ne contaminent pas Forge Design.

Aucun shell : le runner utilise `subprocess.Popen([...], shell=False)` avec
une liste d'arguments construite côté serveur. Sont interdits `shell=True`,
toute commande construite par concaténation de chaînes, `bash -c`, `sh -c`,
et l'exécution de scripts du projet (`scripts/dev-server.sh`).

## Commande Forge

### Faits vérifiés dans Forge 1.0.0rc9

- `forge run` (`cli/project/run.py`) : par défaut, `--env dev` **avec
  reloader** (`cli/project/dev_reloader.py`) qui surveille les fichiers et
  relance `python app.py` à chaque changement ; `--no-reload` exécute
  `bash scripts/dev-server.sh` si ce script existe dans le projet (POSIX),
  sinon `[sys.executable, "app.py"]` ; `--env prod` est refusé. `forge run`
  n'a **aucune option d'hôte ni de port**.
- `app.py` (squelette) n'accepte que `--env` avec `choices=["dev", "prod"]`,
  sous `if __name__ == "__main__":` ; aucune option d'hôte, de port ni de TLS.
- `config.py` (squelette) lit `APP_ENV` (`read_app_env`), puis
  `load_dotenv("env/example")` et `load_dotenv(f"env/{APP_ENV}",
  override=True)`, puis seulement `APP_HOST`, `APP_PORT` et `APP_SSL_ENABLED`
  par `os.getenv`, une fois, à l'import. **`env/dev` écrase donc toute valeur
  reçue du processus parent.**
- `APP_HOST`, `APP_PORT` et `APP_SSL_ENABLED` ne sont consommés que par le bloc
  `if __name__ == "__main__":` de `app.py` (garde prod, bind
  `TLSThreadingHTTPServer((APP_HOST, APP_PORT), RequestHandler)`, contexte
  TLS, messages) ; aucun module de `core/` ne les lit (recherche exhaustive).
- Importé comme module (`import app`), `app.py` exécute `config.py`,
  `build_application()` (routes, `bootstrap.py`) et définit
  `application`, **sans créer de serveur**. Forge le revendique et le teste :
  nom public `application` (« Ne pas le renommer »), aucun effet de bord à
  l'import (`tests/test_skeleton_public_application_001.py`).
- Chemin WSGI documenté (`docs/deployment/wsgi-deployment.md`) :
  `from app import application` puis
  `core.app.wsgi.create_wsgi_app(application)`, servi par un serveur WSGI
  externe **qui choisit lui-même son bind** (`gunicorn wsgi:application
  --bind 127.0.0.1:8000`). L'adaptateur sert `/health` et `/media/`, pose les
  en-têtes de sécurité, mais ne sert pas `/static/` (rôle du reverse proxy).
  HSTS n'est posé que si `wsgi.url_scheme == "https"`.
- `GET /health` → `200`, `application/json`, corps exact
  `{"status": "ok"}` (`core/http/health.py`), servi par les deux chemins et
  inscrit au contrat de stabilité Forge. La sonde ne touche ni base ni
  session.
- Forge applique par défaut `X-Frame-Options: DENY` et une CSP contenant
  `frame-ancestors 'none'` (`core/security/headers.py`, `core/security/csp.py`),
  et ne contrôle pas l'en-tête `Host`.
- Les routes non `public` passent par les middlewares (authentification)
  avant le handler (`core/app/application.py`).
- La documentation Forge prescrit un environnement `python -m venv .venv` à la
  racine du projet.

### Ordre réel de `python app.py --env dev`

```text
1. app.py __main__ : --env → os.environ.setdefault("APP_ENV")
2. from config import … : read_app_env → load_dotenv(env/example)
   → load_dotenv(env/dev, override=True) → os.getenv(APP_HOST, APP_PORT, APP_SSL_ENABLED)
3. application = build_application()     (config, routes, bootstrap.py)
4. __main__ : garde prod → bind (APP_HOST, APP_PORT) → TLS si APP_SSL_ENABLED → serve_forever
```

Toute variable posée par Forge Design est relue à l'étape 2, **après**
`env/dev`, et utilisée au bind de l'étape 4. Forge n'offre aucun moyen
supporté de la réimposer entre 2 et 4. Lancer `app.py` en script ne permet
donc pas de garantir le confinement : cette commande, retenue par
FD-REALPREVIEW-001, **n'est plus acceptable**.

### Commande retenue

```python
[f"{root}/.venv/bin/python", "-I", "-u", CHILD_BOOTSTRAP, "--port", str(port)]
# cwd = racine canonique, shell=False, start_new_session=True
```

`CHILD_BOOTSTRAP` est le chemin absolu du fichier
`forge_design/real_preview/child_bootstrap.py` installé avec Forge Design,
résolu par Forge Design. `-I` (mode isolé) ignore les variables `PYTHON*`,
le site utilisateur et n'ajoute ni le cwd ni le dossier du script à
`sys.path` ; `-u` remplace `PYTHONUNBUFFERED`, ignoré sous `-I`.

`forge run` n'est pas retenu (reloader, script shell), ni `python app.py`
(bind dérivé de `env/dev`).

### Bootstrap enfant

Script autonome, bibliothèque standard seulement, exécuté uniquement dans
l'enfant. Étapes normatives, dans cet ordre :

1. Arguments : exactement `--port <entier 1024–65535>`, sinon sortie `2`.
   L'hôte n'est **pas** un argument : c'est la constante `"127.0.0.1"` du
   bootstrap.
2. `sys.addaudithook` installe la garde de bind (ci-dessous), avant tout code
   du projet.
3. Racine = cwd ; insertion explicite en tête de `sys.path`.
4. Compatibilité : `importlib.metadata.version("forge-mvc")` doit appartenir à
   l'ensemble supporté (`1.0.0rc9`), et
   `core.app.wsgi.create_wsgi_app` doit être importable et appelable ; sinon
   sortie `3`, sans bind.
5. `import app` : exécute `config.py` et `env/dev`, construit l'application.
   Exception → trace sur stderr, sortie `5`, sans bind. `app.application`
   doit exposer `dispatch` appelable, sinon sortie `3`.
6. `create_wsgi_app(app.application)`, enveloppé d'une garde `Host` : toute
   requête dont `Host` n'est pas exactement `127.0.0.1:<port>` reçoit `400`
   sans atteindre l'application.
7. Bind : serveur WSGI de la bibliothèque standard
   (`wsgiref.simple_server.make_server`, classe avec `ThreadingMixIn`,
   `allow_reuse_address = False`, `allow_reuse_port = False`) sur
   `("127.0.0.1", port)`. `EADDRINUSE` → sortie `4`.
8. `serve_forever()` ; aucun handler de signal installé par le bootstrap.

Le bootstrap ne reconstruit ni `Application`, ni `Router`, ni les en-têtes, et
ne patche aucun module Forge ou métier : il n'utilise que le nom public
`application` et `create_wsgi_app`, exactement comme le `wsgi.py` documenté
par Forge. Le serveur WSGI externe que Forge laisse au déployeur est ici celui
du bootstrap.

Codes de sortie : `2` usage, `3` Forge incompatible, `4` port occupé, `5`
échec d'import du projet ; toute autre sortie est un arrêt inattendu.

#### Garde d'audit `socket.bind`

Hook d'audit (PEP 578, API standard, non retirable une fois installé) sur
l'événement `socket.bind`, levé **avant** l'appel système : pour une famille
`AF_INET` ou `AF_INET6`, toute adresse autre qu'une IP littérale de bouclage
(`127.0.0.0/8`, `::1`) lève une exception et le bind n'a pas lieu. Les sockets
Unix ne sont pas concernés. Elle est active pendant toute la vie de l'enfant,
donc aussi pendant l'import de `app.py` et de `bootstrap.py`.

Elle couvre un `app.py` personnalisé qui ouvrirait un serveur à l'import avec
l'hôte de `env/dev` : le bind échoue, l'import échoue, sortie `5`. Elle ne
couvre pas le code natif, `ctypes`, ni les sous-processus lancés par le
projet (nouvel interpréteur sans hook) : ce n'est pas une sandbox.

#### Dépendance à une API Forge hors contrat de stabilité

`create_wsgi_app` (`core.app.wsgi`) n'est pas listé parmi les imports publics
du contrat de stabilité Forge (qui couvre `core.http`, `core.auth`,
`core.security`). Il est retenu parce qu'il est **la** voie documentée par
Forge pour servir l'application armée hors `python app.py`, testée par Forge
(`tests/test_wsgi_entrypoint_001.py`) et utilisée par le `wsgi.py` engendré
par `forge deploy:init`. Risque : changement de signature dans une version
mineure. Détection : étape 4 (version Forge du projet dans l'ensemble
supporté, symbole présent et appelable) avant tout bind, et état `failed` avec
la raison « Forge incompatible » ; l'ensemble supporté évolue avec la matrice
de compatibilité de Forge Design.

### Interpréteur

- Chemin : `<racine canonique>/.venv/bin/python` (convention Forge). `.venv` et
  `bin` doivent être des dossiers ordinaires de la racine (pas des liens) ;
  `python` peut être un lien symbolique (format standard d'un venv), sa cible
  résolue doit être un fichier ordinaire exécutable.
- Absent ou invalide : preview réelle **indisponible**, raison
  « interpréteur du projet introuvable ».
- Pas de recherche dans `PATH`, pas de repli sur `sys.executable` de Forge
  Design (dont les dépendances ne sont pas celles du projet), pas de
  `python -m forge`.
- Windows (`.venv\Scripts\python.exe`) : non pris en charge par la première
  version, indisponible avec raison explicite.

Le navigateur ne fournit jamais le cwd, l'exécutable, un chemin de
configuration ni un argument : le runner dérive tout de
`CurrentProjectContext.root` canonique, déjà sélectionné côté serveur.

## Environnement

`env=os.environ.copy()` est interdit. L'environnement du processus cible est
construit explicitement à partir de deux catégories.

**Transmis** (nécessaires au fonctionnement d'un processus Python et du
squelette Forge) :

| Variable | Source |
|---|---|
| `PATH`, `HOME`, `LANG`, `LC_ALL`, `LC_CTYPE`, `TZ`, `TMPDIR` | Copiées de Forge Design si présentes |
| `APP_ENV=dev` | Fixée (lue par `config.py` avant `env/`) |

`APP_HOST`, `APP_PORT` et `APP_SSL_ENABLED` ne sont **pas** transmis : ils ne
sont pas un mécanisme de confinement (`env/dev` les écrase) et ne sont lus que
par le bloc `__main__` de `app.py`, que le bootstrap n'exécute pas.

**Jamais transmises** : toute autre variable de Forge Design, en particulier
jetons et identifiants (`*_TOKEN`, `*_KEY`, `*_SECRET`, `*_PASSWORD`,
fournisseurs cloud, `GITHUB_*`, `SSH_AUTH_SOCK`), variables CI, `VIRTUAL_ENV`,
`PYTHONPATH`, `PYTHONHOME`, `PYTHONSTARTUP`, variables `XDG_*` et
configuration propre à Forge Design. La liste blanche ci-dessus fait foi :
ce qui n'y figure pas n'est pas transmis.

Les variables de base de données et autres réglages applicatifs ne sont pas
transmis par Forge Design : le projet les obtient de ses propres fichiers
`env/`, comme lors d'un lancement manuel.

### `.env` et `env/`

Forge Design ne lit, ne parse, ne copie, ne modifie ni n'affiche jamais un
`.env` ou un fichier `env/*` pour construire la preview (la politique
`source_parts` refuse déjà le segment `env`), et n'en crée aucun
(`env/preview`, `env/forge-design`, `.env.preview`…). Le projet, lui, charge
`env/example` puis `env/dev` dans l'enfant : c'est un comportement du projet
cible, documenté ici comme risque, sans effet sur l'adresse d'écoute.

Conséquence explicite : **une preview réelle a accès aux secrets que
l'application lit normalement** (base, API, SMTP…). Elle n'est pas plus
confinée qu'un `python app.py` lancé à la main.

## Réseau

### Garantie pré-bind (PRE-BIND guarantee)

> Forge Design garantit que le serveur HTTP utilisé comme endpoint de preview
> est configuré sur `127.0.0.1:<port choisi par Forge Design>`, en HTTP sans
> TLS, avant son bind.

Démonstration, sur le code de Forge 1.0.0rc9 :

1. le seul serveur dont Forge Design fait son endpoint est créé par le
   bootstrap (étape 7), jamais par `app.py` ;
2. son hôte est une constante du bootstrap et son port un argument fourni par
   Forge Design ; aucun des deux n'est lu dans `os.environ`, `config.py` ni
   `env/*`, donc `APP_HOST=0.0.0.0` ou `APP_PORT=8000` dans `env/dev` n'ont
   aucun effet sur ce bind ;
3. le bind a lieu **après** l'import de `app.py` (étape 5), donc après toute
   configuration projet (`env/example`, `env/dev`, `config.py`,
   `bootstrap.py`) ; rien du projet ne s'exécute plus entre la construction de
   l'adresse et le bind ;
4. TLS : le serveur du bootstrap ne fait pas de TLS, et `APP_SSL_ENABLED`
   n'est consommé que par le bloc `__main__` de `app.py`, non exécuté ;
   `wsgi.url_scheme` vaut `http`, donc pas de HSTS ; `APP_SSL_ENABLED=true`
   dans `env/dev` reste sans effet ;
5. la garde d'audit refuse en plus, avant l'appel système, tout bind
   `AF_INET`/`AF_INET6` non loopback dans l'enfant, y compris pendant
   l'import du projet.

La garantie porte sur l'endpoint HTTP de preview. Elle ne signifie pas que le
projet ne peut ouvrir aucun port : voir « Threat model ».

### Vérification post-bind (POST-BIND verification)

La sonde `/health` (voir « Timeouts ») vérifie que le serveur écoute, sur le
port attendu, et répond. C'est une **validation de readiness**, pas une
barrière de confinement : le confinement est acquis avant le bind.

### Port

- Port dédié, distinct de celui de Forge Design, **alloué dynamiquement** :
  le runner lie un socket à `("127.0.0.1", 0)`, lit le port attribué par le
  système, ferme le socket et transmet le port au bootstrap. Aucun port global
  figé.
- Course connue : un autre processus peut prendre le port entre la fermeture
  et le bind du bootstrap. Le bootstrap n'active ni `SO_REUSEADDR` ni
  `SO_REUSEPORT` : il ne partage jamais un port déjà écouté et sort avec le
  code `4`.
- Collision : état `failed` avec la raison « port occupé ». **Aucun nouvel
  essai silencieux** (ni port+1, ni nouveau port automatique) : l'utilisateur
  relance explicitement, ce qui alloue un nouveau port.

### Host, Origin et DNS rebinding

Forge ne contrôle pas l'en-tête `Host`. Le bootstrap ajoute ce contrôle à
l'endpoint : seules les requêtes avec `Host: 127.0.0.1:<port>` atteignent
l'application, ce qui neutralise un DNS rebinding visant directement le port
cible (le navigateur envoie alors le nom de domaine de l'attaquant).

- Le navigateur n'accède pas directement au port cible : l'iframe passe par
  le proxy de Forge Design, qui applique le contrôle `Host` strict de Forge
  Design et envoie `Host: 127.0.0.1:<port>` (voir « Iframe / proxy ») ;
- le port cible reste joignable par tout processus local, qui peut envoyer
  l'en-tête attendu ; risque réduit (port éphémère, preview arrêtée par défaut
  et sur action explicite, arrêt à la fermeture de Forge Design), **pas
  supprimé** ;
- les requêtes mutantes vers l'application suivent sa propre politique
  (CSRF, Origin) : Forge Design ne la contourne pas et ne l'affaiblit pas.

## Cycle de vie

- **Au plus une preview réelle active par instance Forge Design.**
- Le `RealPreviewController` est créé par `create_application` (composition),
  comme `CurrentProjectContext`. Aucun singleton global, aucun état de module.
- États publics : `stopped`, `starting`, `running`, `failed`, `stopping`.
  L'état initial est `stopped`. `pid is not None` n'est jamais le contrat
  public.

```text
stopped ──start()──▶ starting ──sonde OK──▶ running
   ▲                    │                      │
   │                    ├─ timeout / sortie ──▶ failed
   │                    │                      │ sortie spontanée
   │                    ▼                      ▼
   └──── stopping ◀──stop()── (starting | running)      failed ──start()──▶ starting
```

- `start()` n'est accepté que depuis `stopped` ou `failed`. Pendant `starting`
  ou `stopping`, un second `start()` est refusé (pas de file d'attente).
- Sortie spontanée de l'enfant : détectée par `poll()` à chaque lecture
  d'état ; `running` → `failed` (code de sortie conservé), jamais affiché
  comme actif.
- Le PID et le port sont conservés en mémoire pour la gestion interne, sans
  identité persistante. **Aucun état sur disque** : ni PID, ni port, ni
  « running » dans `.forge-design/` ou ailleurs.
- Activation : uniquement par action explicite de l'utilisateur (UX cible
  « Démarrer la preview réelle »). Jamais au lancement de Forge Design, à
  l'ouverture d'un projet ni après une modification.
- Pas de reload : ni `debug=True`, ni reloader, ni watcher. Un changement de
  template est visible à la requête suivante si l'application relit ses
  templates ; un changement de code Python demande un arrêt puis un démarrage
  explicites.

### Arrêt

- `stop()` explicite, idempotent (sans effet depuis `stopped` ou `failed`).
- Stratégie POSIX : `SIGTERM` au groupe de processus → attente bornée de
  **5 s** → `SIGKILL` au groupe si nécessaire → attente bornée de **2 s** ;
  état final `stopped`, ou `failed` si le processus n'a pas pu être récolté.
  Le bootstrap n'installant pas de handler `SIGTERM`, l'arrêt normal est
  immédiat, sans `shutdown()` gracieux (sauf handler installé par le projet).
- Groupe de processus : le serveur du bootstrap ne crée pas d'enfant (threads
  seulement), mais le code du projet le peut (workers, sous-processus).
  Décision : l'enfant est lancé avec `start_new_session=True` et les signaux
  visent le **groupe** (`os.killpg`), pas le PID seul. Un descendant qui
  quitte volontairement le groupe (`setsid`) n'est pas couvert : limite
  documentée.
- Fermeture de Forge Design : la composition arrête la preview (même
  stratégie) dans le chemin d'arrêt du serveur ; un arrêt brutal de Forge
  Design (`SIGKILL`) peut laisser l'enfant vivant, limite documentée.
- Changement de projet courant : la preview de l'ancien projet est arrêtée
  **avant** que le nouveau projet ne soit accepté comme courant ; aucune
  application d'un ancien projet ne continue de tourner silencieusement.

## Logs

- stdout et stderr sont fusionnés dans un seul tube, lu en continu par un
  thread lecteur : le processus cible ne peut pas bloquer sur un tube plein.
- Conservation en mémoire uniquement, dans un tampon circulaire borné :
  **200 lignes**, chaque ligne tronquée à **2 000 caractères**, décodage UTF-8
  avec remplacement. Les lignes les plus anciennes sont écartées.
- Forge Design n'écrit pas ces logs dans `<project>/storage/` ni dans
  `.forge-design/`. Une persistance éventuelle relèverait d'un ticket ultérieur
  et viserait le stockage utilisateur XDG.
- Les logs peuvent contenir des données sensibles imprimées par l'application.
  Ils sont affichés uniquement échappés, à la demande, jamais envoyés ailleurs.
- L'application cible peut écrire ses propres logs (par exemple
  `storage/logs/`) : c'est son comportement normal, que Forge Design ne peut
  pas empêcher et ne lit pas.

## Template réellement utilisé

La preview réelle rend le template **présent sur disque**, rien d'autre :

```text
Design modifié → génération → diff → SAFEWRITE → template sauvegardé → preview réelle
```

Interdits : monkeypatch du loader, template temporaire hors projet, overlay
filesystem, écriture puis restauration silencieuse. La preview réelle ne crée
pas de quatrième représentation invisible.

Conséquence assumée : si le Design a changé sans que le template ait été
généré et sauvegardé, preview réelle et preview statique diffèrent. L'UI le
signalera (ticket d'intégration).

## Sélection de route

L'URL n'est jamais inventée. Sont interdits : nom de vue → `/nom-de-vue`,
chemin de template → URL, ou toute autre déduction lexicale.

Source : Route Explorer (`read_routes`), dont la chaîne route → handler →
contrôleur → méthode → `render("…")` littéral est déjà statique. Le
`ViewContract` fournit le template (`mvc/views/<chemin>`) mais aucune route.

Une route est **candidate** pour le template `mvc/views/<chemin>` si :

1. `method == "GET"` ;
2. `handler.verification == "found"` ;
3. `handler.template.status == "found"` et `handler.template.path == <chemin>`,
   avec `presence == "present"` ;
4. le chemin de route ne contient aucun segment dynamique `{param}`.

Résultat représenté explicitement :

| Situation | État | Raison affichée |
|---|---|---|
| Une seule candidate, `public` | disponible | — |
| Une seule candidate, non `public` | indisponible | « route protégée par authentification » |
| Aucune route ne rend ce template | indisponible | « aucune route GET connue pour ce template » |
| Seules des routes à segments dynamiques | indisponible | « route dynamique » |
| Plusieurs candidates | indisponible | « plusieurs routes rendent ce template » |
| Résolution `dynamic`/`ambiguous`, lecture partielle | indisponible | raison de Route Explorer |

Seule la méthode `GET` est utilisée pour afficher une vue. `POST`, `PUT`,
`PATCH` et `DELETE` ne sont jamais ouverts automatiquement. Le chemin de
route est recalculé côté serveur à chaque démarrage, jamais reçu du
navigateur.

## Backend et authentification

La preview réelle utilise le vrai backend : base existante, données, session,
permissions. Forge Design ne fabrique pas de session, n'injecte pas
d'utilisateur, ne contourne pas le RBAC et ne désactive pas
l'authentification.

Première version : seules les routes `public` sont disponibles (tableau
ci-dessus), car une route protégée renverrait vers la connexion et la
connexion exige un `POST`, refusé par le proxy. Une réponse `401`, `403`,
`404` ou `500` d'une route publique est présentée telle quelle comme résultat
réel, sans contournement ni repli sur la preview statique.

## Iframe / proxy

### A. Iframe directe vers `127.0.0.1:<port>`

- **X-Frame-Options / CSP** : Forge envoie `X-Frame-Options: DENY` et
  `frame-ancestors 'none'` par défaut ; la page ne s'affiche pas dans une
  iframe sans modifier le projet. Bloquant.
- **Host / DNS rebinding** : le navigateur parle directement au serveur cible ;
  seule la garde `Host` du bootstrap protège.
- **Same-origin** : origine distincte de Forge Design (port différent), ce qui
  est bon pour l'isolation.
- **Cookies / sessions** : cookies `127.0.0.1` partagés entre ports (les
  cookies ne sont pas isolés par port) : la session de la cible et celle de
  Forge Design peuvent se voir écrasées ou lues mutuellement.
- **HTMX, navigation, assets** : fonctionnent nativement.
- **Méthodes** : aucun filtrage possible.

### B. Proxy contrôlé par Forge Design

- **X-Frame-Options / CSP** : le proxy remplace uniquement les directives
  d'encadrement de la réponse (`X-Frame-Options` retiré, `frame-ancestors`
  limité à l'origine de l'éditeur) ; le reste de la CSP cible est conservé.
- **Host** : le proxy applique le contrôle `Host` strict de Forge Design et
  envoie à la cible `Host: 127.0.0.1:<port>`.
- **Same-origin** : servi sur une **origine dédiée** (listener loopback séparé
  de Forge Design, sur un second port éphémère), donc distincte de l'éditeur ;
  le code de la page cible ne peut pas lire le DOM de Forge Design.
- **Cookies / sessions** : transmis tels quels entre navigateur et cible ;
  ceux de Forge Design ne sont jamais transmis (pas de cookie Forge Design
  aujourd'hui ; règle conservée). Même réserve de partage par hôte que pour A,
  réduite par le fait que Forge Design ne dépend d'aucun cookie.
- **HTMX, navigation, assets** : chemins transmis sans réécriture (le proxy
  est transparent sur son origine dédiée), donc les URL absolues de la page
  fonctionnent. Comme le reverse proxy du déploiement WSGI documenté par
  Forge, le proxy sert lui-même `/static/…` depuis `<racine>/static`, en
  lecture seule et avec les contrôles filesystem de Forge Design (pas de
  lien, pas de segment caché, pas de clé) ; l'adaptateur WSGI ne les sert
  pas.
- **Méthodes** : `GET` et `HEAD` seulement dans la première version ; toute
  autre méthode reçoit `405` du proxy, sans atteindre la cible.

### Décision

**B est retenu** pour la première intégration Web : un proxy transparent
minimal, sur une origine loopback dédiée, `GET`/`HEAD` uniquement, avec
contrôle `Host` strict, réponses et délais bornés, et seule réécriture des
en-têtes d'encadrement. A est écarté parce qu'il exige de modifier les
en-têtes de sécurité du projet, et ne permet ni de filtrer les méthodes ni de
servir les statiques que l'adaptateur WSGI ne sert pas.

Le proxy n'est pas un proxy générique : il ne relaie que vers le port de la
preview active de l'instance, jamais vers une destination fournie par une
requête. FD-REALPREVIEW-002 n'implémente ni proxy ni iframe.

### Navigation

- Liens et redirections vers la même origine de preview : autorisés (servis
  par le proxy, `GET`).
- Formulaires `POST` et requêtes HTMX mutantes : refusées par le proxy
  (`405`), affichées comme telles dans l'iframe.
- Navigation vers une autre origine, ouverture de fenêtres, navigation du
  parent : bloquées par le sandbox (ci-dessous).

## CSP et sandbox navigateur

Le `sandbox` vide de la preview statique ne suffit pas (pas de scripts, donc
pas d'HTMX). Permissions retenues, et rien d'autre :

| Permission | Justification |
|---|---|
| `allow-scripts` | HTMX et le JavaScript de l'application |
| `allow-same-origin` | L'origine de preview garde ses cookies et ses requêtes HTMX ; sans risque d'évasion vers l'éditeur parce que cette origine est distincte de celle de Forge Design |

Non accordées : `allow-forms` (les soumissions seraient refusées par le proxy),
`allow-top-navigation*`, `allow-popups*`, `allow-modals`,
`allow-downloads`, `allow-pointer-lock`, `allow-presentation`.
`allow-scripts` et `allow-same-origin` ne sont **jamais** combinés sur une
iframe de même origine que l'éditeur.

La page éditeur qui contient l'iframe déclare `frame-src` limité à l'origine
de preview active. Les en-têtes de la page de l'éditeur restent ceux de Forge
Design.

## Timeouts

- Démarrage : `starting` dure au plus **15 s** ; au-delà, arrêt (stratégie
  d'arrêt) puis `failed` avec « délai de démarrage dépassé ».
- Sonde (vérification post-bind, readiness) : `GET
  http://127.0.0.1:<port>/health` avec `Host: 127.0.0.1:<port>`, garantie par
  Forge 1.0.0rc9 et servie par l'adaptateur WSGI ;
  timeout de **1 s** par tentative, toutes les **200 ms** jusqu'au délai de
  démarrage. Prête seulement si statut `200` et corps exact
  `{"status": "ok"}`. Aucune route métier (`/contacts`…) n'est sondée.
- Une sortie de l'enfant pendant `starting` donne `failed` immédiatement, avec
  la raison dérivée du code de sortie du bootstrap (`3`, `4`, `5`).
- Toute requête de contrôle future (sonde, proxy vers la cible) a un délai
  borné : 10 s par requête proxy dans la première intégration.

## Effets de bord

> La preview réelle exécute le projet Forge sélectionné et peut déclencher ses
> effets de bord habituels.

Une application réellement exécutée peut se connecter à une base, effectuer
des migrations au démarrage, envoyer des mails, ouvrir et écrire des
fichiers, appeler des API externes et modifier des données. Forge Design ne
considère pas cette exécution comme sûre. Le message ci-dessus (texte exact
adaptable par le ticket UI) est présenté avant le premier démarrage.

La restriction `GET`/`HEAD` du proxy réduit les modifications déclenchées
depuis l'iframe, mais ne les empêche pas : un handler `GET`, `bootstrap.py` ou
le démarrage lui-même peuvent écrire.

## Threat model

Une séparation de processus améliore l'isolation de Forge Design, mais **n'est
pas une sandbox de sécurité OS**. Le projet cible conserve tous les droits du
compte utilisateur.

| Menace | Effet possible | Mesure | Résiduel |
|---|---|---|---|
| Code cible malveillant | Lecture/écriture de fichiers, réseau, exfiltration | Action explicite, avertissement | Entier : mêmes droits que l'utilisateur |
| Code cible bogué | Crash, exceptions | Processus séparé, `failed` détecté | Aucun impact sur Forge Design |
| Boucle infinie au démarrage | `starting` bloqué | Délai de 15 s puis arrêt | — |
| Boucle infinie dans une requête | Iframe sans réponse | Timeout proxy 10 s, `stop()` | Thread cible occupé |
| Processus enfant survivant | Processus orphelin | Groupe de processus, `killpg`, arrêt à la fermeture | `setsid` volontaire, arrêt brutal de Forge Design |
| Port exposé | Accès par un autre processus local | Loopback seul, port éphémère, durée limitée | Processus locaux du même hôte |
| DNS rebinding | Lecture de pages cibles par un site tiers | `Host` strict sur le proxy et sur l'endpoint du bootstrap, port imprévisible | Processus locaux envoyant le `Host` attendu |
| `env/dev` impose `APP_HOST=0.0.0.0`, `APP_PORT=8000` ou TLS | Endpoint exposé ou sur un autre port | Garantie pré-bind : adresse de l'endpoint fixée par le bootstrap, jamais lue dans le projet ; `app.py` importé sans son bloc `__main__` | Aucun pour l'endpoint de preview |
| Code projet ouvrant un serveur à l'import avec l'hôte de `env/dev` | Exposition réseau | Garde d'audit `socket.bind` : bind non loopback refusé avant l'appel système, sortie `5` | Code natif, `ctypes`, sous-processus du projet |
| Code projet ouvrant d'autres sockets | Ports supplémentaires | Garde d'audit (non loopback refusé dans l'enfant) | Sockets loopback supplémentaires ; contournements natifs ; non empêché par Forge Design |
| API Forge modifiée | Démarrage impossible ou incorrect | Contrôle de version et de `create_wsgi_app` avant bind, sortie `3` | Changement sémantique non détectable statiquement |
| Secrets d'environnement | Fuite des secrets de Forge Design | Liste blanche d'environnement | Secrets du projet lus par le projet |
| Effets base de données | Migrations, écritures | Avertissement, `GET`/`HEAD` seulement | Écritures au démarrage ou en `GET` |
| Requêtes externes | Appels API, mails | Avertissement | Entier |
| Logs sensibles | Secrets imprimés | Mémoire bornée, échappés, non persistés | Affichage à la demande |
| Navigation iframe | Navigation du parent, popups, formulaires | Sandbox minimal, proxy `GET`/`HEAD` | Scripts actifs dans l'origine de preview |

Forge Design garantit le serveur HTTP qu'il démarre comme endpoint de
preview. Il ne prétend pas empêcher un code projet malveillant d'ouvrir
explicitement `socket.bind(("0.0.0.0", …))` par un moyen qui échappe au hook
d'audit, avec les droits de l'utilisateur.

Termes à proscrire dans l'UI et la documentation tant qu'aucune isolation OS
n'existe : « sandbox sécurisé », « isolé totalement », « sans risque ».

## Limites

- POSIX uniquement pour la première version.
- Projets suivant le squelette Forge : `app.py` exposant `application` et sans
  serveur hors de `if __name__ == "__main__":`, `.venv` à la racine,
  `forge-mvc` installé dans ce venv en version supportée.
- Rendu par le chemin WSGI de Forge, pas par le `RequestHandler` du serveur
  de développement : pages d'erreur et statiques peuvent différer de
  `python app.py` (les statiques passent par le proxy).
- Routes `GET` publiques, statiques et uniques seulement.
- Pas d'authentification, pas de `POST`, pas de reload.
- Une seule preview réelle par instance.
- Pas de Docker, de container ni de sandbox OS ; aucune dépendance ajoutée.

## Décisions retenues

| Sujet | Décision |
|---|---|
| Paquet | `forge_design/real_preview/` (pas `web/`, `preview/` ni `forge/`) |
| Contrats | `RealPreviewState` (énumération des 5 états), `RealPreviewConfig` (racine, interpréteur, délais, borne de logs), `RealPreviewStatus` (état, port, raison, code de sortie, logs), `RealPreviewController` (`start`, `stop`, `status`), `RealPreviewError` |
| Commande | `[<racine>/.venv/bin/python, "-I", "-u", <child_bootstrap.py>, "--port", <port>]`, cwd racine canonique, `shell=False`, `start_new_session=True` ; `python app.py` abandonné (FD-REALPREVIEW-001A) |
| Bootstrap | `forge_design/real_preview/child_bootstrap.py`, stdlib seule : garde d'audit `socket.bind`, contrôle de compatibilité, `import app`, `create_wsgi_app(app.application)`, garde `Host`, bind `127.0.0.1:<port>` |
| Confinement | Garantie pré-bind par construction ; sonde `/health` = readiness post-bind |
| Interpréteur | `.venv/bin/python` du projet, sinon indisponible ; ni `PATH` ni `sys.executable` |
| Port | Éphémère via bind `127.0.0.1:0`, transmis en argument ; collision → `failed` (sortie `4`), pas de nouvel essai |
| Environnement | Liste blanche (`PATH`, `HOME`, locale, `TZ`, `TMPDIR`) + `APP_ENV=dev` ; ni `APP_HOST`, ni `APP_PORT`, ni `APP_SSL_ENABLED` |
| Sonde | `/health`, 200 + corps exact, 1 s par tentative, démarrage ≤ 15 s |
| Arrêt | `SIGTERM` au groupe, 5 s, `SIGKILL` au groupe, 2 s |
| Logs | Tampon mémoire 200 lignes × 2 000 caractères, stdout+stderr fusionnés |
| Route | Unique, `GET`, statique, `public`, issue de Route Explorer ; sinon indisponible avec raison |
| Affichage | Proxy transparent sur origine loopback dédiée, `GET`/`HEAD`, `Host` strict, `/static/` servi par le proxy ; iframe `allow-scripts allow-same-origin` |
| Périmètre de FD-REALPREVIEW-002 | Runner seul : cycle de vie, commande, environnement, port, sonde, arrêt, logs ; ni proxy, ni iframe, ni UI |

## Questions reportées

Ces points ne bloquent pas FD-REALPREVIEW-002 :

- texte exact de l'avertissement et emplacement des contrôles (ticket UI) ;
- prise en charge de Windows ;
- sélection manuelle d'une route parmi plusieurs candidates ou avec
  paramètres ;
- routes protégées (connexion manuelle dans l'iframe, donc `POST` contrôlé) ;
- persistance optionnelle des logs dans le stockage utilisateur XDG ;
- interpréteur configurable par l'utilisateur hors de `.venv`.
