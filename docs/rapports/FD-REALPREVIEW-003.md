# Rapport — FD-REALPREVIEW-003

## Ticket et objectif

Exposer la preview réelle par un proxy HTTP local dédié : listener
`127.0.0.1:<port proxy>` sur une origine distincte de Forge Design et du
runner. Le proxy relaie GET/HEAD vers le runner, sert `/static/` par lecture
confinée, réécrit uniquement les en-têtes d'encadrement et borne les
réponses. Pas d'iframe, d'UI, de Start/Stop ni de composition Web.

## État Git initial

`main` synchronisée avec `origin/main` à `64dd45d` — FD-REALPREVIEW-002.
Seule modification suivie préexistante : `docs/rapports/FD-CONTRACT-001.md`,
préservée hors commit.

## Architecture

```text
client ──▶ RealPreviewProxyServer 127.0.0.1:<port proxy>   (ThreadingMixIn + HTTPServer)
            1. Host exact          → 400 sinon
            2. GET/HEAD            → 405 + Allow sinon (corps ≤ 1 Mio lu et jeté)
            3. cible d'origine, ASCII, bornée, sans corps → 400 sinon
            4. controller.status() : running + port + racine → 503 sinon
            5a. /static/…  → <racine>/static, lecture confinée
            5b. autre      → HTTPConnection("127.0.0.1", status.port), une tentative
```

Un seul module, `forge_design/real_preview/proxy.py`. Le runner
(`controller.py`, `child_bootstrap.py`) n'est pas modifié. Le proxy n'utilise
que `controller.status()` : jamais `start`, `stop`, `Popen`, PID ni groupe.
Un test AST et un double de contrôleur dont `start`/`stop` lèvent le
vérifient.

## API publique

`forge_design.real_preview` exporte en plus `RealPreviewProxyConfig`,
`RealPreviewProxyServer` et `create_real_preview_proxy`.

- `create_real_preview_proxy(controller, *, frame_ancestor_origin,
  host="127.0.0.1", port=0, config=None)`.
  - Hôte autre que `127.0.0.1`, port hors [0, 65535] ou booléen : `ValueError`.
  - Erreur de bind : `OSError`, sans repli.
  - Aucun thread n'est lancé : l'appelant fait `with … as proxy:` puis
    `proxy.serve_forever()`.
- `RealPreviewProxyConfig` (gelée, validée) : `request_timeout=10.0`,
  `max_response_bytes` et `max_static_bytes` de 8 Mio, dans [1, 64 Mio].
  Aucune URL, aucun hôte ni port amont : le port vient exclusivement du
  contrôleur.
- Fonctions pures du module : `validate_frame_ancestor_origin`,
  `rewrite_frame_ancestors`, `rewrite_location`.

## Origine dédiée

Le listener a son propre socket sur `127.0.0.1` (port 0 = éphémère),
distinct du runner (testé en intégration) et de Forge Design. La classe
serveur a `daemon_threads=True`, `allow_reuse_address=False` et
`allow_reuse_port=False`. Un port déjà en écoute donne `OSError`.

## Host guard

Seul un en-tête `Host` unique égal à `127.0.0.1:<port proxy>` passe. Sont
refusés en 400, **avant tout appel à `status()`, statique ou relais** : Host
absent, vide, `localhost`, nom DNS, `[::1]`, IP sans port, autre port, et
deux en-têtes Host. Testé sur `/` et `/static/`, avec un compteur d'appels du
contrôleur à 0.

## Méthodes

Seules GET et HEAD sont admises. Toute autre méthode, y compris inconnue
(POST, PUT, PATCH, DELETE, OPTIONS, TRACE, CONNECT, FOO), reçoit
`405 Method Not Allowed` avec `Allow: GET, HEAD`. **Preuve : POST n'atteint
jamais l'application.** Pour les 8 méthodes, le serveur amont n'enregistre
aucune requête et `status()` n'est pas appelé. En intégration réelle,
`POST /` donne 405 et le runner reste `running`. Le corps annoncé
(≤ 1 Mio) est lu puis jeté, jamais relayé.

## État runner

`status()` est appelé à chaque requête admise. `stopped`, `starting`,
`failed` et `stopping` donnent 503 « Preview réelle indisponible. », tout
comme `running` sans port ou sans racine (pas d'assertion). Cela vaut aussi
pour `/static/`. Une course (enfant mort après `status()`) donne 502 ou 504,
sans redémarrage ni nouvel essai.

## Forward HTTP

`http.client.HTTPConnection("127.0.0.1", status.port, timeout=10)`, une
seule tentative. `http.client` ne lit aucune variable de proxy. La cible de
requête doit être sous forme d'origine (`/…`), ASCII, sans caractère de
contrôle, avec un chemin ≤ 4096 et une requête ≤ 8192 caractères. Elle est
relayée **octet pour octet**, sans décodage (`/a%20b/c?x=1&y=%2F&z=a+b`
arrive tel quel, testé). Un GET ou HEAD avec corps (`Content-Length` non
nul ou `Transfer-Encoding`) donne 400. Aucune redirection n'est suivie.

**Preuve : Host cible = celui du bootstrap.** Le proxy envoie toujours
`Host: 127.0.0.1:<port runner>` (testé sur le serveur amont). L'enfant réel,
dont la garde refuse tout autre Host, répond 200 à travers le proxy.

## Headers requête

Liste blanche positive : `Accept`, `Accept-Language`, `User-Agent`,
`Cookie`, `Referer`, `Origin`, `Cache-Control`, `Pragma`, `If-None-Match`,
`If-Modified-Since`, et `HX-Request`, `HX-Target`, `HX-Trigger`,
`HX-Trigger-Name`, `HX-Current-URL`, `HX-Boosted`,
`HX-History-Restore-Request`, `HX-Prompt`.

Jamais relayés : le Host du navigateur, `Authorization` et
`Proxy-Authorization` (preview limitée aux routes publiques),
`Accept-Encoding` (la cible répond sans compression), les en-têtes
hop-by-hop, ceux nommés dans `Connection`, et `X-Forwarded-*`. Le test
compare l'ensemble exact des en-têtes reçus par l'amont.

## Headers réponse

Statut et raison conservés (200, 201, 302, 401, 403, 404, 500 testés) :
aucune page Forge Design ne remplace une erreur métier.

Retirés : en-têtes hop-by-hop (`Connection`, `Keep-Alive`,
`Proxy-Authenticate`, `TE`, `Trailer`, `Transfer-Encoding`, `Upgrade`),
en-têtes nommés dans `Connection`, `X-Frame-Options` et `Content-Length`
(recalculé).

Conservés : tous les autres, dont `Set-Cookie` multiples, `HX-Trigger`,
`X-Content-Type-Options`, `Referrer-Policy` et `Content-Encoding` (corps
opaque, jamais décompressé).

HEAD : aucun corps. Le `Content-Length` de la cible est repris s'il est
numérique. Pour un GET, `Content-Length` vaut la taille réelle, sauf pour
1xx, 204 et 304.

## CSP

`rewrite_frame_ancestors` applique le découpage de la spécification CSP
(politiques séparées par `,`, directives par `;`, nom de directive sans
casse). **Seule `frame-ancestors` est remplacée** par
`frame-ancestors <origine éditeur>`. Les autres directives restent dans
l'ordre. Plusieurs en-têtes CSP restent séparés, donc cumulatifs. Si aucune
politique ne contient la directive, une politique `frame-ancestors
<origine>` est ajoutée : jamais de `*`, jamais de suppression pure.
`Content-Security-Policy-Report-Only` est conservée telle quelle.

Testé :
- sans CSP ;
- `default-src 'self'; frame-ancestors 'none'; script-src 'self'` ;
- deux en-têtes ;
- liste à virgule ;
- casse ;
- directive dupliquée ;
- nom voisin (`frame-ancestors-x`) ;
- directives vides.

L'origine (`validate_frame_ancestor_origin`) est exactement
`http://127.0.0.1:<1-65535>`. 22 formes sont refusées, dont `https`,
`localhost`, l'absence de port, le port 0, les zéros initiaux, un chemin,
une requête, un fragment, `user@`, `[::1]`, la casse du schéma, des espaces,
`*`, `'self'` et les non-chaînes.

Les réponses d'erreur du proxy portent `default-src 'none'; frame-ancestors
<origine>`.

## X-Frame-Options

**Preuve : X-Frame-Options cible est retiré** de toute réponse relayée.
C'est testé avec un amont synthétique (`DENY`), et en intégration réelle :
`X-Frame-Options` est absent de la réponse relayée. Que Forge pose `DENY` par
défaut vient de l'inspection statique.

## Redirects

Le proxy ne suit jamais une redirection : le 302 revient au client, et
l'amont ne reçoit qu'une requête. Le traitement de `Location` dépend de sa
forme :
- relative (`/login`, `login?next=/`) : conservée ;
- absolue ou sans schéma vers exactement `127.0.0.1:<port runner>` :
  réécrite en `/chemin?requête#fragment` ;
- externe, autre port loopback, `https`, `user@` ou `localhost` :
  inchangée, jamais proxifiée.

## Bornes réponse

`MAX_REAL_PREVIEW_RESPONSE_BYTES` vaut 8 Mio (borne dédiée, distincte de
`MAX_SOURCE_BYTES`). La lecture se fait par blocs de 64 Kio, jusqu'à la
borne + 1. Résultats testés avec une borne de 1 000 :
- exactement 1 000 octets : 200 ;
- 1 001 octets : 502 « Réponse de preview trop volumineuse. », jamais un
  corps tronqué ;
- sans `Content-Length` ou avec un `Content-Length` mensonger : la borne
  réelle s'applique.

Écart découvert : `http.client.read(n)` rend un corps **plus court que son
`Content-Length`** sans erreur, si la connexion se ferme. Le proxy compare la
taille reçue à la taille annoncée, et l'écart donne 502 (testé).

## Timeouts

Le délai de 10 s s'applique par opération socket, et la durée totale de
lecture du corps est aussi bornée. Délai dépassé : 504 « Preview réelle sans
réponse. » (testé avec un délai de 0,3 s contre un amont lent de 2 s, réponse
en moins de 1,5 s). Connexion refusée : 502. Une seule tentative. Côté
client, un délai de 15 s par connexion empêche un client lent de bloquer un
thread.

## Static

`/static/<chemin>` n'est jamais relayé à la cible (testé). Le fichier est lu
dans `<status.project_root>/static/` et seulement si le runner est
`running`. Le chemin est décodé (`%XX`, UTF-8 strict), puis la politique
lexicale s'applique. Le type MIME vient de la table intégrée de `mimetypes`
(sans `/etc/mime.types`), avec `application/octet-stream` par défaut. Les
réponses portent `Cache-Control: no-store` et `X-Content-Type-Options:
nosniff`. HEAD renvoie les mêmes en-têtes sans corps. Testé : CSS, JS
(`text/javascript`), PNG, type inconnu, nom avec espace et requête ignorée.

Codes :
- 400 pour un chemin refusé : `/static`, `/static/`, `..`, `.`, `%2e%2e`,
  `%2F`, `%5C`, segment vide, segment caché, `env`/`ENV`, `.pem`, `id_rsa`,
  `:`, NUL, UTF-8 invalide ;
- 404 pour un fichier ou dossier absent ;
- 403 pour un lien, un fichier non ordinaire, un fichier trop gros ou
  modifié pendant la lecture.

## Sécurité filesystem

La politique lexicale de `source_parts` est **extraite** dans
`forge/source.py` en `unsafe_relative_path` (refactor pur, partagé ; les
tests existants des sources, routes et templates passent). La lecture
réutilise `open_directory` (`O_NOFOLLOW` sur chaque composant, depuis la
racine), puis :
1. `os.open(…, O_DIRECTORY | O_NOFOLLOW, dir_fd)` pour chaque dossier ;
2. `os.stat(…, follow_symlinks=False)` et `S_ISREG` ;
3. `os.open(O_RDONLY | O_NOFOLLOW | O_NONBLOCK)` ;
4. `fstat`, `samestat` et la borne de taille ;
5. une lecture bornée par `os.read`, puis une vérification de stabilité
   (taille et mtime).

Pas de `Path.read_bytes`, pas de `SimpleHTTPRequestHandler`. La borne
`MAX_REAL_PREVIEW_STATIC_BYTES` vaut 8 Mio : 10 octets passent et 11 sont
refusés avec une borne de 10 (testé).

**Preuve : /static ne suit aucun symlink.** Sont refusés en 403 :
- un lien vers un fichier hors de `static/` ;
- un lien interne vers un fichier de `static/` ;
- un lien de dossier ;
- `static/` lui-même lié.

Une FIFO est refusée sans blocage, et un dossier aussi.

## SSRF

**Preuve : une requête ne peut pas choisir la destination upstream.** La
destination est construite exclusivement depuis `status().port`, sur
`127.0.0.1`. Un second serveur témoin n'a reçu **aucune** requête, quelles
que soient les tentatives :
- cible absolue `http://evil.example/…` ou `http://127.0.0.1:<témoin>/…` ;
- forme autorité, `*` ;
- chemins `//127.0.0.1:<témoin>/x`, `/@127.0.0.1:<témoin>/x` et
  `/http://evil.example/` (relayés au seul runner) ;
- Host vers le port témoin ;
- `X-Forwarded-Host` ;
- `HTTP_PROXY`, `http_proxy` et `ALL_PROXY` pointés vers le témoin, en
  unitaire comme en intégration réelle.

## Cookies

`Cookie` est relayé tel quel et les `Set-Cookie` multiples reviennent au
client. Le proxy n'ajoute aucun cookie ni aucune session. Limite connue,
rappelée dans le contrat : les cookies ne sont pas isolés par port, donc
l'origine du proxy partage les cookies `127.0.0.1` avec Forge Design (qui
n'en pose aucun) et le runner.

## HTMX GET

Les en-têtes `HX-*` de requête sont relayés (testé : `HX-Request`,
`HX-Target`, `HX-Current-URL`). Les en-têtes `HX-*` de réponse sont conservés
(testé : `HX-Trigger`). Une requête HTMX mutante (POST…) reçoit 405 sans
atteindre la cible. Les corps ne sont pas modifiés.

**Preuve : aucun body HTML/CSS/JS n'est réécrit.** Une page contenant un
lien absolu vers le runner, `/static/app.css` et `/a.js` revient octet pour
octet, sans `<base>` injecté. Un corps `gzip` revient opaque avec son
`Content-Encoding`.

## Tests unitaires

`tests/test_real_preview_proxy.py` : 149 tests.
- Fonctions pures : origine (2 acceptées, 22 refusées), CSP (8), `Location`
  (12), configuration (9).
- Proxy réel en thread contre un serveur amont synthétique :
  - création sans thread et refus ;
  - bind non retenté ;
  - classe serveur ;
  - Host (8) ;
  - méthodes (8) ;
  - états (6) ;
  - relais, HEAD, politiques d'en-têtes, corps refusé ;
  - cibles invalides (8) ;
  - SSRF ;
  - statuts (5) ;
  - CSP et XFO ;
  - corps non réécrit ;
  - redirections (4) ;
  - bornes (5) ;
  - timeout et refus ;
  - statiques (5 types, 17 chemins refusés, absents, liens, FIFO, taille,
    jamais relayés) ;
  - hygiène (imports AST, aucun processus lancé) ;
  - 5 requêtes parallèles.

`tests/test_real_preview_controller.py` : seul le test d'exports change,
pour inclure les trois nouveaux symboles.

## Tests d'intégration

Vrai runner FD-REALPREVIEW-002 sur un projet synthétique (squelette rc9 et
`static/test.css`), avec `HTTP_PROXY` hostile, puis proxy. Résultats :
- `GET /health` : la réponse du runner ;
- `GET /` : HTML, sans XFO, `frame-ancestors <origine>`, `default-src
  'self'` conservé ;
- `HEAD /health` : 200 sans corps ;
- `HEAD /` : 405 de Forge, relayé ;
- `GET` et `HEAD /static/test.css` ;
- `POST /` : 405, runner toujours `running` ;
- après `stop()` du runner : `/health` donne 503.

Ensuite, aucun processus de preview ni thread du proxy ne survit et le
serveur témoin n'a rien reçu.

Écart Forge observé : le routeur rc9 ne traite pas HEAD comme GET. Il est
documenté dans `docs/04-compatibilite-forge.md`.

## Répétitions anti-race

Proxy, runner et bootstrap (297 tests, dont les intégrations réelles
runner + proxy, timeouts et refus) ont tourné **5 fois de suite** : 297
réussis à chaque passe, en environ 19 s. Aucun processus survivant et aucun
`storage/` créé.

Les teardowns ferment les serveurs avec `poll_interval=0.05`. Le fichier
passe ainsi de 68 s à 8 s, sans changement de comportement.

Mutations, lancées depuis le scratchpad avec restauration vérifiée par
`cmp` : **20 sur 20 détectées**.
- Requête :
  - garde Host inactive ;
  - méthode refusée relayée ;
  - forme absolue acceptée ;
  - Host navigateur relayé ;
  - tous les en-têtes relayés ;
  - `Accept-Encoding` ajouté.
- Réponse :
  - XFO conservé ;
  - CSP cible supprimée ;
  - `frame-ancestors` non remplacé ;
  - `Location` non réécrite ;
  - jetons `Connection` gardés.
- Bornes et erreurs :
  - borne de réponse absente ;
  - corps tronqué accepté ;
  - timeout pris pour 502 ;
  - corps GET accepté.
- Statiques :
  - statique servi avant le contrôle du runner ;
  - statique relayé à la cible ;
  - lien de fichier suivi (`lstat` et `O_NOFOLLOW` retirés ensemble : un
    seul des deux reste bloquant, défense en profondeur) ;
  - dossier lié suivi ;
  - borne statique absente ;
  - politique lexicale absente.

Deux mutations ciblaient d'abord un texte d'avant le formatage. Elles ont
été recalées sur le code réel, puis détectées.

## Packaging

Pas de nouveau paquet : `proxy.py` est dans `forge_design.real_preview`,
déjà listé. `pyproject.toml` n'est pas modifié. Wheel
`forge_design-0.1.0.dev0-py3-none-any.whl` dans `tmp/wheels` (ignoré),
SHA-256
`cc7a864d3158da7854fd7f061db0003e3acab1c19113c8c0ab38b7b42c3bbb45`. Elle
contient `real_preview/proxy.py` et `forge/source.py` à jour.

## Installation wheel

Installation `--no-deps --no-index --target` temporaire, `python -I`,
origine du proxy vérifiée dans l'installation. Projet synthétique, runner
`running`, puis à travers le proxy installé :

| Requête | Statut | Type | Taille |
|---|---|---|---|
| `GET /health` | 200 | `application/json` | 16 |
| `GET /` | 200 | `text/html; charset=utf-8` | 2 688 |
| `GET /static/test.css` | 200 | `text/css` | 4 |
| `HEAD /health` | 200 | `application/json` | 0 |
| `HEAD /static/test.css` | 200 | `text/css` | 0 |
| `POST /` | 405 | `text/plain` | — |

Le runner est ensuite `stopped`, sans survivant. Aucun projet réel n'a été
lancé.

## Fichiers créés

- `forge_design/real_preview/proxy.py`
- `tests/test_real_preview_proxy.py`
- `docs/rapports/FD-REALPREVIEW-003.md`

## Fichiers modifiés

- `forge_design/real_preview/__init__.py` : trois exports.
- `forge_design/forge/source.py` : extraction de `unsafe_relative_path`
  (comportement de `source_parts` inchangé).
- `tests/test_real_preview_controller.py` : liste des exports.
- `docs/preview/real-preview-contract.md` : section « Implémentation du
  proxy ».
- `docs/02-architecture.md` : runner → proxy à origine dédiée → futur
  iframe.
- `docs/04-compatibilite-forge.md` : HEAD non routé par Forge rc9, CSP vue à
  travers le proxy.

Non modifiés : `controller.py`, `child_bootstrap.py`, `web/`, `editor/`,
`preview/`, `design/`, `generate/`, `safewrite/`, `tools/`, `app.py`,
`pyproject.toml`, le JavaScript.

## Validation globale finale

Ordre suivi : code, tests unitaires, tests de sécurité et mutations,
intégration runner + proxy, répétitions, documentation, rapport, wheel et
installation (avant les validations finales, pour que le rapport soit
complet), statique final, et enfin suite globale.

| Commande | Résultat |
|---|---|
| `pytest -q tests/test_real_preview_proxy.py` | 149 réussis |
| `pytest -q tests/test_real_preview_controller.py tests/test_real_preview_bootstrap.py tests/test_real_preview_proxy.py` | 297 réussis (×5) |
| Régressions du refactor (`test_source`, `test_routes`, `test_templates`, `test_template_navigation`, `test_entity_source`, runner) | 423 réussis |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` / `ruff format --check .` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |
| `pytest` (depuis le scratchpad, `--rootdir` vers le dépôt) | **3938 réussis** en 59 s, aucun échec |
| `python -m pip check` | No broken requirements found |
| Node / MkDocs | N/A : aucun JavaScript modifié, aucune configuration MkDocs |

Seul ce tableau a été ajouté au rapport après l'exécution. Les validations
statiques et la suite globale ont ensuite été relancées sur le contenu final,
avec un résultat identique. Aucun `storage/` n'a été créé dans le répertoire
d'exécution, et aucun processus de preview n'a survécu.

## Limites restantes

- Pas encore de composition : `create_application` ne possède ni contrôleur
  ni proxy. Pas d'iframe, pas de Start/Stop, pas d'arrêt au changement de
  projet ou à la fermeture (FD-REALPREVIEW-004).
- Les cookies ne sont pas isolés par port.
- HEAD vers une route Forge rc9 donne 405 : comportement de la cible.
- Le proxy relaie seulement GET/HEAD : formulaires et HTMX mutants donnent
  405.
- Pas de compression (`Accept-Encoding` non relayé), et un corps entier en
  mémoire jusqu'à 8 Mio par requête.
- Le délai de 10 s vaut par opération socket, et la lecture du corps est
  bornée en durée totale. La réception des en-têtes de la cible ne l'est pas :
  une cible qui les envoie très lentement peut dépasser 10 s au total.

## État Git final

Un commit sur `main`, rapport inclus, sans push.
Message : `feat: ajouter le proxy de preview réelle (FD-REALPREVIEW-003)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit. Hash :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-REALPREVIEW-003.md
```
