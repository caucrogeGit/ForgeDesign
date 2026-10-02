# Preview réelle — contrat

Contrat normatif de FD-REALPREVIEW-001. Il fixe les décisions dont dépendent
FD-REALPREVIEW-002 (runner local) et les tickets d'intégration Web suivants.
Aucun code n'existe encore : ce document décrit ce qui sera implémenté.

Les faits Forge cités ont été vérifiés statiquement dans `forge-mvc==1.0.0rc9`
(version épinglée par Forge Design), le paquet installé et le dépôt Forge local
(`v1.0.0-rc.9-7-g73a956e5`, même `version = "1.0.0rc9"`). Aucune application
Forge n'a été lancée pour les établir.

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
Projet Forge cible : <interpréteur du projet> app.py --env dev
     │
     └── écoute 127.0.0.1:<port alloué>
```

Ce qui peut être exécuté : uniquement le point d'entrée `app.py` du projet
courant, avec l'interpréteur du projet (voir « Commande Forge »). Rien
d'autre : ni commande fournie par le navigateur, ni script du projet, ni
`forge` CLI.

## Processus séparé

Décision : **le projet cible n'est jamais importé dans le processus Python de
Forge Design.** Sont interdits comme architecture, dans tout module de Forge
Design : `import mvc`, `import config`, `import bootstrap`, `from app import …`,
`importlib` sur un module du projet, ajout de la racine du projet à
`sys.path`, `runpy`, `exec` de sources du projet.

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
- `app.py` (squelette) : sous `__main__`, accepte `--env` (`dev` par défaut)
  et positionne `APP_ENV` ; construit l'application WSGI, puis sert avec
  `TLSThreadingHTTPServer((APP_HOST, APP_PORT), RequestHandler)`
  (`ThreadingHTTPServer` : un thread par requête, aucun processus enfant) ;
  `serve_forever()` ; sur `KeyboardInterrupt`, `shutdown()` puis
  `server_close()`. Aucun handler `SIGTERM` n'est installé : `SIGTERM`
  termine le processus par l'action par défaut.
- Bind refusé `EADDRINUSE` : message `format_port_in_use_message` puis
  `exit(1)`, sans essai d'un autre port.
- `config.py` (squelette) : `load_dotenv("env/example")` puis
  `load_dotenv(f"env/{APP_ENV}", override=True)`, donc **les fichiers `env/`
  du projet peuvent écraser les variables reçues du processus parent** ;
  `APP_HOST` (défaut `127.0.0.1`), `APP_PORT` (défaut `8000`),
  `APP_SSL_ENABLED` (défaut vrai hors prod), certificats `cert.pem`/`key.pem`.
- `GET /health` → `200`, `application/json`, corps exact
  `{"status": "ok"}` (`core/http/health.py`), servi par le serveur de
  développement et par le chemin WSGI, et inscrit au contrat de stabilité
  Forge comme surface publique garantie. La sonde ne touche ni base ni
  session.
- Forge applique par défaut `X-Frame-Options: DENY` et une CSP contenant
  `frame-ancestors 'none'` (`core/security/headers.py`, `core/security/csp.py`).
- Forge ne contrôle pas l'en-tête `Host` (aucune liste d'hôtes autorisés).
- Les routes non `public` passent par les middlewares (authentification)
  avant le handler (`core/app/application.py`).
- La documentation Forge prescrit un environnement `python -m venv .venv` à la
  racine du projet.

### Commande retenue

```python
[interpreter, "app.py", "--env", "dev"]   # cwd = racine canonique, shell=False
```

`forge run` n'est **pas** retenu : reloader par défaut (processus
supplémentaires, watcher, cycle de vie à deux niveaux), et `--no-reload`
délègue à un script shell du projet. Appeler `app.py` directement reproduit
exactement la branche sans script de `forge run --no-reload`, sans reloader ni
shell.

L'hôte, le port et TLS sont transmis par variables d'environnement
(`APP_HOST`, `APP_PORT`, `APP_SSL_ENABLED`), seul mécanisme offert par Forge.
Comme `env/dev` peut les écraser, le runner ne présume pas qu'ils sont
appliqués : la sonde de démarrage vérifie l'écoute effective (voir
« Timeouts »).

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
| `APP_ENV=dev` | Fixée |
| `APP_HOST=127.0.0.1` | Fixée |
| `APP_PORT=<port alloué>` | Fixée |
| `APP_SSL_ENABLED=false` | Fixée (sonde et iframe en HTTP loopback) |
| `PYTHONUNBUFFERED=1` | Fixée (logs lisibles sans attendre un flush) |

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
`source_parts` refuse déjà le segment `env`). Le projet, lui, charge
`env/example` puis `env/dev` à son démarrage : c'est un comportement du
projet cible, documenté ici comme risque.

Conséquence explicite : **une preview réelle a accès aux secrets que
l'application lit normalement** (base, API, SMTP…). Elle n'est pas plus
confinée qu'un `python app.py` lancé à la main.

## Réseau

- Écoute exclusive sur `127.0.0.1`. Interdits : `0.0.0.0`, `::`, adresse LAN,
  adresse Tailscale ou VPN.
- Port dédié, distinct de celui de Forge Design, **alloué dynamiquement** :
  le runner lie un socket à `("127.0.0.1", 0)`, lit le port attribué par le
  système, ferme le socket et transmet le port. Aucun port global figé.
- Course connue : un autre processus peut prendre le port entre la fermeture
  et le bind de l'application. Elle se manifeste par la sortie `EADDRINUSE`
  de Forge (code 1) ou par une sonde en échec.
- Collision : état `failed` avec la raison « port occupé ». **Aucun nouvel
  essai silencieux** (ni port+1, ni nouveau port automatique) : l'utilisateur
  relance explicitement, ce qui alloue un nouveau port.
- Écoute effective : si `env/dev` impose un autre hôte, port ou TLS, la sonde
  sur `http://127.0.0.1:<port>/health` échoue et la preview passe en `failed`
  avec la raison « l'application n'écoute pas à l'adresse attendue
  (configuration env/ du projet) ». Un bind sur `0.0.0.0` imposé par `env/dev`
  et répondant aussi sur `127.0.0.1` n'est pas détectable par la sonde seule :
  risque résiduel documenté (voir « Threat model »).

### Host, Origin et DNS rebinding

Le serveur cible ne bénéficie pas du contrôle `Host` de Forge Design
(FD-WEB-003), et Forge n'en propose pas. Pendant qu'une preview tourne, une
page web malveillante ouverte dans le navigateur peut tenter un DNS rebinding
vers `127.0.0.1:<port>` et lire les réponses de l'application cible.

Limitation retenue :

- le navigateur n'accède pas directement au port cible : l'iframe passe par
  le proxy de Forge Design, qui applique un contrôle `Host` strict (voir
  « Iframe / proxy ») ;
- le port cible reste néanmoins joignable par tout processus local et par un
  rebinding visant ce port précis ; ce risque est réduit (port éphémère
  imprévisible, preview arrêtée par défaut et sur action explicite, arrêt à
  la fermeture de Forge Design), **pas supprimé** ;
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
  Forge 1.0.0rc9 n'installant pas de handler `SIGTERM`, l'arrêt normal est
  immédiat, sans `shutdown()` gracieux.
- Groupe de processus : le serveur Forge ne crée pas d'enfant (threads
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
- **Host / DNS rebinding** : le navigateur parle directement au serveur cible,
  qui n'a pas de contrôle `Host`.
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
  est transparent sur son origine dédiée), donc `/static/…` et les URL
  absolues de la page fonctionnent.
- **Méthodes** : `GET` et `HEAD` seulement dans la première version ; toute
  autre méthode reçoit `405` du proxy, sans atteindre la cible.

### Décision

**B est retenu** pour la première intégration Web : un proxy transparent
minimal, sur une origine loopback dédiée, `GET`/`HEAD` uniquement, avec
contrôle `Host` strict, réponses et délais bornés, et seule réécriture des
en-têtes d'encadrement. A est écarté parce qu'il exige de modifier les
en-têtes de sécurité du projet et expose directement un serveur sans contrôle
`Host`.

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
- Sonde : `GET http://127.0.0.1:<port>/health`, garantie par Forge 1.0.0rc9 ;
  timeout de **1 s** par tentative, toutes les **200 ms** jusqu'au délai de
  démarrage. Prête seulement si statut `200` et corps exact
  `{"status": "ok"}`. Aucune route métier (`/contacts`…) n'est sondée.
- Une sortie de l'enfant pendant `starting` donne `failed` immédiatement.
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
| DNS rebinding | Lecture de pages cibles par un site tiers | Proxy avec `Host` strict, port imprévisible | Rebinding visant directement le port cible |
| Bind non loopback via `env/dev` | Exposition réseau | Variables fixées, sonde | Non détecté si la sonde loopback répond aussi |
| Secrets d'environnement | Fuite des secrets de Forge Design | Liste blanche d'environnement | Secrets du projet lus par le projet |
| Effets base de données | Migrations, écritures | Avertissement, `GET`/`HEAD` seulement | Écritures au démarrage ou en `GET` |
| Requêtes externes | Appels API, mails | Avertissement | Entier |
| Logs sensibles | Secrets imprimés | Mémoire bornée, échappés, non persistés | Affichage à la demande |
| Navigation iframe | Navigation du parent, popups, formulaires | Sandbox minimal, proxy `GET`/`HEAD` | Scripts actifs dans l'origine de preview |

Termes à proscrire dans l'UI et la documentation tant qu'aucune isolation OS
n'existe : « sandbox sécurisé », « isolé totalement », « sans risque ».

## Limites

- POSIX uniquement pour la première version.
- Projets suivant le squelette Forge (`app.py` sous `__main__`, `config.py`
  lisant `APP_HOST`/`APP_PORT`/`APP_SSL_ENABLED`, `.venv` à la racine).
- Routes `GET` publiques, statiques et uniques seulement.
- Pas d'authentification, pas de `POST`, pas de reload.
- Une seule preview réelle par instance.
- Pas de Docker, de container ni de sandbox OS ; aucune dépendance ajoutée.

## Décisions retenues

| Sujet | Décision |
|---|---|
| Paquet | `forge_design/real_preview/` (pas `web/`, `preview/` ni `forge/`) |
| Contrats | `RealPreviewState` (énumération des 5 états), `RealPreviewConfig` (racine, interpréteur, délais, borne de logs), `RealPreviewStatus` (état, port, raison, code de sortie, logs), `RealPreviewController` (`start`, `stop`, `status`), `RealPreviewError` |
| Commande | `[<racine>/.venv/bin/python, "app.py", "--env", "dev"]`, cwd racine canonique, `shell=False`, `start_new_session=True` |
| Interpréteur | `.venv/bin/python` du projet, sinon indisponible ; ni `PATH` ni `sys.executable` |
| Port | Éphémère via bind `127.0.0.1:0` ; collision → `failed`, pas de nouvel essai |
| Environnement | Liste blanche (`PATH`, `HOME`, locale, `TZ`, `TMPDIR`) + `APP_ENV`, `APP_HOST`, `APP_PORT`, `APP_SSL_ENABLED=false`, `PYTHONUNBUFFERED` |
| Sonde | `/health`, 200 + corps exact, 1 s par tentative, démarrage ≤ 15 s |
| Arrêt | `SIGTERM` au groupe, 5 s, `SIGKILL` au groupe, 2 s |
| Logs | Tampon mémoire 200 lignes × 2 000 caractères, stdout+stderr fusionnés |
| Route | Unique, `GET`, statique, `public`, issue de Route Explorer ; sinon indisponible avec raison |
| Affichage | Proxy transparent sur origine loopback dédiée, `GET`/`HEAD`, `Host` strict ; iframe `allow-scripts allow-same-origin` |
| Périmètre de FD-REALPREVIEW-002 | Runner seul : cycle de vie, commande, environnement, port, sonde, arrêt, logs ; ni proxy, ni iframe, ni UI |

## Questions reportées

Ces points ne bloquent pas FD-REALPREVIEW-002 :

- texte exact de l'avertissement et emplacement des contrôles (ticket UI) ;
- prise en charge de Windows ;
- sélection manuelle d'une route parmi plusieurs candidates ou avec
  paramètres ;
- routes protégées (connexion manuelle dans l'iframe, donc `POST` contrôlé) ;
- persistance optionnelle des logs dans le stockage utilisateur XDG ;
- détection d'un bind non loopback imposé par `env/dev` ;
- interpréteur configurable par l'utilisateur hors de `.venv`.
