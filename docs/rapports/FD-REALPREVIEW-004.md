# Rapport — FD-REALPREVIEW-004

## Ticket et objectif

Intégrer à l'application Web le runner (FD-REALPREVIEW-002) et le proxy
(FD-REALPREVIEW-003), sans les modifier. Depuis l'éditeur, l'utilisateur
voit si une route réelle publique est disponible, démarre explicitement la
preview, la voit dans une iframe sur l'origine dédiée du proxy, puis l'arrête.
Changement ou fermeture de projet et arrêt de Forge Design ne laissent aucune
preview active.

## État Git initial

`main` synchronisée avec `origin/main` à `969291f` — FD-REALPREVIEW-003.
Seule modification suivie préexistante : `docs/rapports/FD-CONTRACT-001.md`,
préservée hors commit.

## Architecture

```text
ForgeDesignServer (127.0.0.1:<port lié>)            server_close() / finally run_server
 └─ Application                                      → runtime.close()
     ├─ CurrentProjectContext
     ├─ ProjectSelector(before_change=runtime.stop)
     ├─ RealPreviewPanel (données du panneau de l'éditeur)
     └─ RealPreviewRuntime          forge_design/web/real_preview.py
         ├─ RealPreviewController   runner, inchangé
         └─ RealPreviewProxyServer  proxy, inchangé, + thread dédié
```

Fichiers d'implémentation :
- **Créés** : `forge_design/real_preview/route_selection.py` (service pur) et
  `forge_design/web/real_preview.py` (runtime, panneau, URL d'iframe,
  actions).
- **Modifiés de façon ciblée** : `server.py` (composition, routes,
  `ForgeDesignServer`), `editor.py` (panneau, CSP, notices, contrôles POST
  publics), `inspector.py` et `recent_projects.py` (arrêt avant changement),
  `project_selector.py` (rappel `before_change`), `editor.html`, `shell.css`.
- **Non modifiés** : `controller.py`, `child_bootstrap.py`, `proxy.py`,
  `design/`, `editor/` (le paquet), `generate/`, `safewrite/`, le JavaScript.
  Aucun Tool n'est ajouté : le registre reste à cinq (test existant).

## Ownership runtime

Un `RealPreviewRuntime` par application, sans singleton ni état disque. Il
porte le contrôleur, le proxy éventuel, son thread, l'origine de l'éditeur et
une éventuelle erreur Web (échec du proxy). Un verrou court sérialise
start, stop, close et la création ou destruction du proxy. Il n'est jamais
tenu pendant `serve_forever`, et les lectures d'état ne l'attendent pas (essai
non bloquant). La machine d'état du contrôleur n'est pas recopiée.

`create_application(real_preview=…)` accepte un runtime explicite (tests).
Sans runtime, la preview est désactivée, car l'origine n'est connue qu'après
le bind. `create_server(…, real_preview=…)` crée ou reçoit le runtime et
renvoie `ForgeDesignServer`, sous-classe explicite de `WSGIServer` dont
l'attribut typé `real_preview` est fermé par `server_close()`.

## Cycle de vie

- Start :
  1. arrêt de tout runtime d'un autre projet ;
  2. `controller.start(racine)` ;
  3. si `running`, création du proxy (`127.0.0.1`, port 0, origine de
     l'éditeur) et thread `daemon` nommé.
- Échec du runner : aucun proxy.
- Échec de création ou de lancement du proxy : runner arrêté, état `failed`,
  « Le proxy de preview n'a pas pu être créé. ».
- Stop : `shutdown`, `join` et `server_close` du proxy, **puis**
  `controller.stop()`. Le résultat est `True` seulement si le runner est
  `stopped`.
- Lecture d'état (`status()`) :
  - runner `failed` ou `stopped` alors que le proxy existe : proxy fermé ;
  - thread du proxy mort alors que le runner tourne : proxy fermé, runner
    arrêté, état `failed` (« Le proxy de preview s'est arrêté de façon
    inattendue… »).

  Aucun thread de surveillance permanent.
- `close()` est idempotent ; ensuite, Start est refusé.

## Sélection de route

`select_real_preview_route(contract_template, routes)` est pur. Il reçoit le
template du contrat (`ViewContract.template`, `mvc/views/…`) chargé par
l'éditeur, et le `RoutesResult` de Route Explorer. Une candidate est une
route qui remplit toutes ces conditions :
- méthode GET et handler présent ;
- vérification `found` et template `found` égal au template attendu ;
- `presence == "present"` ;
- chemin statique (aucun `{…}`, `?`, `#`, `\`, blanc, ni `//`).

Elle n'est retenue que si elle est unique et `public`. Résultat :
`RealPreviewRouteSelection(available, path, reason)`, gelé.

Cas représentés, chacun avec sa raison :
- disponible ;
- aucune route ;
- plusieurs routes (y compris une statique et une dynamique) ;
- route protégée ;
- route dynamique seule ;
- template absent ;
- template du contrat hors `mvc/views` ;
- résolution incertaine.

**Écart précisé.** Route Explorer avertit toujours que sa lecture est
statique et partielle (et le squelette rc9 produit en plus « déclaration non
interprétée » pour `register_optins`). Refuser sur ces avertissements
rendrait la preview impossible partout. Est « partiel pertinent » toute route
GET dont le template n'est pas déterminable : handler absent ou dynamique,
méthode non vérifiée, rendu `dynamic` ou `ambiguous`. Elle pourrait rendre le
même template, donc la sélection est refusée. Aucune déduction lexicale
(`/contacts/list` ne remplace pas Route Explorer, testé).

**Preuve : route recalculée côté serveur.** La sélection est refaite à chaque
affichage de l'éditeur et juste avant `runtime.start`. **Preuve : une route
protégée, dynamique ou ambiguë ne démarre pas.** Dans chacun de ces cas, Start
répond 409 avec la raison et le runner n'est jamais appelé. C'est testé en Web
pour route protégée, contrat absent, routes illisibles, template absent et
Design absent, et en pur pour tous les cas.

## Start Web

`POST /editor/real-preview/start` :
- `is_local_action` (Origin exacte, `Sec-Fetch-Site` same-origin si présent),
  `csrf=False` par route ;
- `Content-Type` exactement `application/x-www-form-urlencoded` ;
- champs exacts `design`, plus `node` et `preview` facultatifs, sans doublon,
  bornés.

Pipeline :
1. `load_design` ;
2. `load_contract` ;
3. Route Explorer ;
4. sélection ;
5. projet courant ;
6. `runtime.start(context.root)` ;
7. 303 vers l'éditeur, avec la notice `real-started` ou `real-failed`.

Start sur le même projet déjà actif ne redémarre rien. Une opération
concurrente donne 409.

**Preuve : Start n'accepte aucun path, port ni URL utilisateur.** Un POST
avec `route=/admin`, `port=1234`, `url=http://127.0.0.1:1/admin`,
`path=/admin`, `action=start` ou un `design` dupliqué reçoit 400 sans aucun
appel au runner (testé).

Codes de réponse :
- 403 : sans Origin, avec Origin étrangère ou autre port, ou en cross-site ;
- 415 : `text/plain` ou multipart ;
- 409 : sans projet ;
- 404 : Design absent.

**Preuve : un GET de l'éditeur ne démarre jamais le runtime.** `/`,
`/inspector`, `/routes`, `/editor`, l'éditeur avec Design et
`/editor/preview`, ainsi que l'ouverture d'un récent et le refresh, ne lancent
aucun `start` (testé). Seul le POST Start le fait.

## Stop Web

`POST /editor/real-preview/stop` applique les mêmes protections HTTP. Le
Design ne sert qu'au retour : seule la forme du chemin est vérifiée, et Stop
fonctionne même si le Design a été supprimé. L'ordre est proxy
(`shutdown`, `close`) puis runner (testé). La réponse est 303 avec la notice
`real-stopped`. Stop est idempotent depuis `stopped` et `failed`. Un runner
impossible à arrêter donne 500 « Preview réelle impossible à arrêter. ».

## Changement de projet

`ProjectSelector` reçoit un rappel générique `before_change: Callable[[],
bool]`, appelé **seulement** quand un candidat valide va remplacer un autre
projet, après inspection et avant `set_project`. S'il renvoie `False`, le
statut est `busy`, le projet courant est conservé et la réponse est 409
(Inspector et récents). Le sélecteur ne connaît pas la preview.

**Preuve : le passage de A à B arrête A avant d'activer B.** Le journal
partagé (runtime et contexte instrumentés) montre `runner-stop` avant
`context-set B`, par l'Inspector comme par les récents. En réel, aucun
processus de A ne survit. **Preuve : une sélection de B invalide conserve
A.** Un chemin absent ou un dossier non Forge n'appelle pas `stop`, et A
reste courant et `running` (testé). Rouvrir le même projet ne touche pas la
preview.

## Fermeture de projet

**Preuve : la fermeture du projet arrête le runtime avant le clear.** Le
journal montre `proxy-shutdown`, `proxy-close` et `runner-stop` avant
`context-clear`, et le test réel ne laisse aucun survivant. Si l'arrêt
échoue : 409, aucun `clear`, le projet reste affiché.

## Refresh

`refresh_project(…, release=runtime.stop)` arrête la preview avant tout
`clear`, que l'inspection lève une erreur ou que le projet ne soit plus
reconnu (journal : `runner-stop` avant `context-clear`). Il l'arrête aussi
avant un changement de racine canonique. Un refresh valide sur la même racine
ne touche pas la preview. Si l'arrêt échoue : 409, projet conservé. Retirer
un récent, même courant, ne touche pas la preview (testé).

## Fermeture serveur

**Preuve : l'arrêt de Forge Design arrête le runner et le proxy.**
- `ForgeDesignServer.server_close()` ferme le runtime puis l'écoute, donc
  aussi en sortie de `with create_server(…)`.
- `run_server` ferme le runtime dans un `finally`, avant `server_close`
  (ordre testé), pour `KeyboardInterrupt`, `RuntimeError` et une fin normale.
- En réel, à la sortie du bloc serveur avec une preview active, le proxy
  refuse les connexions et aucun processus ne survit.

Deux faux serveurs de `tests/test_cli.py` reçoivent `real_preview = None`
pour suivre ce contrat.

## Origine proxy

**Preuve : l'origine vient du port effectif de Forge Design.** Après le bind,
`create_server` appelle `runtime.bind_editor_origin(f"http://127.0.0.1:{port
lié}")` (validée par `validate_frame_ancestor_origin`). L'origine n'est
jamais tirée d'un en-tête `Host`. Testé : la fabrique du proxy reçoit
exactement l'origine du port éphémère ; la mutation « 8765 fixe » est
détectée.

## CSP éditeur

Sans proxy actif, la réponse de l'éditeur garde la CSP Forge par défaut
(`build_csp_header()`, sans `frame-src` ; la preview statique same-origin est
couverte par `default-src 'self'`). Avec un proxy actif, **cette réponse
seule** porte la CSP par défaut suivie de `; frame-src 'self'
http://127.0.0.1:<port proxy>`, exactement. Pas de joker et pas d'autre port
(mutation « joker » détectée).

Après Stop, l'origine disparaît de la CSP et du HTML. Les autres pages (`/`)
gardent la CSP Forge. `/editor/preview` garde sa politique propre
(`frame-ancestors 'self'`, `SAMEORIGIN`). L'éditeur garde
`X-Frame-Options: DENY`.

## Iframe

L'iframe a pour source `real_preview_frame_url(origine proxy, route)`.
L'origine est validée ; la route doit être un chemin statique d'origine,
jamais une URL absolue, `//`, un paramètre ou une requête (testé). Autres
attributs : `title="Preview réelle"` et `referrerpolicy="no-referrer"`. Le
navigateur ne fournit jamais l'URL. Le Design affiché détermine la route ; le
runtime représente l'application, pas un Design.

**Preuves :**
- l'iframe utilise uniquement l'origine du proxy ;
- le port du runner n'est jamais exposé. Il apparaît ni dans le HTML ni dans
  l'URL de l'iframe, testé en réel en lisant le `--port` du processus enfant ;
  la mutation « iframe vers le runner » est détectée.

## Sandbox

L'iframe porte exactement `sandbox="allow-scripts allow-same-origin"`.
`allow-forms`, `allow-popups`, `allow-top-navigation`, `allow-downloads` et
`allow-modals` sont absents de la page (testé ; mutation `allow-forms`
détectée).

**Preuve : un POST dans l'iframe reste refusé par le proxy.** Le proxy répond
405 à un POST sur l'URL de l'iframe (testé en réel). La sandbox sans
`allow-forms` en est la première barrière **côté navigateur, non vérifiée
ici** (voir « Validation navigateur »).

## Preview statique préservée

La section « Prévisualisation indicative » et son iframe `sandbox` vide sont
inchangées, et la nouvelle section « Preview réelle » est distincte. Les
tests existants de l'éditeur et de `/editor/preview` passent sans
modification. La page de l'éditeur avec preview active contient toujours
l'iframe statique (testé).

## États UI

- Route indisponible : la raison.
- `stopped` : route, avertissement, « Démarrer la preview réelle ».
- `running` : route, origine du proxy, « Arrêter la preview réelle », iframe.
- `failed` : erreur, derniers logs (`<pre>`, bornés par le runner),
  « Démarrer à nouveau » si la route reste disponible.
- `starting` et `stopping` : libellé seulement.

Notices : `real-started`, `real-failed` et `real-stopped`. Ni JavaScript, ni
polling : HTML, POST, 303, GET.

## Effets de bord

L'avertissement exact du contrat est affiché avant le bouton Start (testé) :

> La preview réelle exécute le projet Forge sélectionné et peut déclencher
> ses effets de bord habituels.

## Tests route selection

`tests/test_real_preview_route_selection.py` : 36 tests purs.
- Disponibles : route publique unique, racine `/`, avertissements généraux
  non bloquants, même route listée deux fois, route POST incertaine non
  bloquante.
- 19 indisponibles : aucune, protégée, plusieurs (3), dynamique, méthode,
  handler absent ou dynamique, vérification (2), template `dynamic` ou
  `ambiguous`, autre template, `none`, absent, chemin invalide, autre route
  GET incertaine (2).
- Contrat hors `mvc/views`, absence de déduction lexicale, 9 chemins non
  statiques, modèle gelé.

## Tests Web

`tests/test_web_real_preview.py` : 74 tests.
- Runtime seul (16 + URL d'iframe 9) : origine absente ou invalide, ordre
  start et stop, même projet, autre projet, échec du runner, échec du proxy
  (2), runner mort, proxy mort, start concurrent, échec d'arrêt, `close` et
  `stop` idempotents.
- Application réelle sur port éphémère avec runtime double :
  - origine liée ;
  - aucun démarrage par lecture ;
  - avertissement ;
  - protections POST (6 × Start et Stop) ;
  - champs inattendus (6) ;
  - `design` manquant ;
  - sans projet ;
  - indisponibilités (5) ;
  - iframe, CSP et preview statique ;
  - double Start ;
  - échecs du runner et du proxy ;
  - Stop (ordre, idempotence, Design supprimé, échec).

## Tests cycle projet

Fermeture (ordre, échec conservant le projet), changement par l'Inspector et
par les récents (ordre), candidat absent ou non Forge (A conservé), même
projet, changement refusé si l'arrêt échoue, refresh valide et invalide
(ordre), retrait d'un récent, fermeture du serveur, `finally` de
`run_server` (3 sorties).

## Tests runtime

Les régressions runner, bootstrap et proxy sont incluses dans les
répétitions ci-dessous. Le proxy et le contrôleur ne sont pas modifiés.

## Tests d'intégration

Vrai runner et vrai proxy sur des projets synthétiques copiés du squelette
rc9 (Design et contrat pour `home/index.html`, route publique `/`), jamais un
projet réel :
1. **Bout en bout** :
   - ouverture du projet ; l'éditeur propose `/` ;
   - POST Start → 303 ;
   - iframe vers l'origine du proxy, CSP `frame-src` exacte, port du runner
     absent du HTML ;
   - GET de l'iframe : HTML réel ; `GET /static/preview.css` : l'asset ;
   - POST sur le proxy : 405 ;
   - POST Stop : proxy fermé (connexion refusée), aucun processus, iframe
     absente.
2. **A puis B** : aucun processus de A ne survit, aucun thread de proxy, B
   courant.
3. **Fermeture du projet** pendant l'exécution.
4. **Arrêt de Forge Design** pendant l'exécution.

Une fixture vérifie après chaque test qu'aucun processus mentionnant le
dossier du test ni aucun thread `forge-design-real-preview-proxy` ne
survit. Le socket du proxy est fermé : la connexion est refusée après Stop et
après l'arrêt du serveur.

## Répétitions anti-race

Les tests Web, de sélection, de proxy et du runner (343 tests, dont les 4
scénarios réels : start → running → stop, start puis fermeture du projet,
start A puis B, arrêt de Forge Design) ont tourné **5 fois de suite** : 343
réussis à chaque passe, en environ 23 s, sans processus survivant ni
`storage/` créé.

Mutations, lancées depuis le scratchpad avec restauration vérifiée par
`cmp` : **25 sur 25 détectées**.
- Sélection :
  - publique non exigée ;
  - dynamique acceptée ;
  - première de plusieurs routes ;
  - incertitude ignorée ;
  - présence non exigée ;
  - déduction lexicale.
- Web :
  - GET de l'éditeur qui démarre ;
  - champs supplémentaires acceptés ;
  - contrôle d'origine absent ;
  - route non revérifiée avant Start ;
  - iframe vers le port du runner ;
  - `frame-src` joker ;
  - `frame-src` sans proxy ;
  - sandbox avec `allow-forms`.
- Runtime :
  - runner laissé actif après un échec du proxy ;
  - runner arrêté avant le proxy ;
  - proxy mort, runner conservé ;
  - même projet redémarré.
- Serveur et projet :
  - origine fixe 8765 ;
  - `clear` avant `stop` à la fermeture ;
  - `server_close` sans runtime ;
  - `run_server` sans `finally` ;
  - activation avant arrêt ;
  - sélection invalide qui arrête A ;
  - refresh invalide sans arrêt.

Le test du `finally` de `run_server` a été rendu sensible à l'ordre
(fermeture du runtime avant `server_close`), sans quoi `server_close`
masquait l'absence du `finally`.

## Packaging

Aucun nouveau paquet : `route_selection.py` est dans
`forge_design.real_preview` et `real_preview.py` dans `forge_design.web`, tous
deux déjà listés. `editor.html` et `shell.css` sont déjà dans les
package-data. `pyproject.toml` n'est pas modifié. Wheel
`forge_design-0.1.0.dev0-py3-none-any.whl` dans `tmp/wheels` (ignoré),
SHA-256 `c3f724d3ec00ef14b7e62876ad79155ac3a6b7a97e7ba1842facffb1345537ca`.

## Installation wheel

Installation `--no-deps --no-index --target` temporaire, `python -I`,
origine de `forge_design.web.server` et `forge_design.web.real_preview`
vérifiée dans l'installation. Forge Design est lancé par `create_server(port=0)`
(port 39347 lors de l'exécution), sur un projet synthétique :

| Étape | Résultat |
|---|---|
| `POST /inspector` | 200 |
| `POST /editor/real-preview/start` | 303 |
| `GET /editor` | iframe `http://127.0.0.1:43635/`, CSP `frame-src 'self' http://127.0.0.1:43635` |
| GET de l'iframe | 200 `text/html; charset=utf-8`, page réelle |
| `GET /static/preview.css` (proxy) | 200 |
| `POST /editor/real-preview/stop` | 303, proxy fermé (connexion refusée) |
| Arrêt du serveur | aucun processus ni thread de preview survivant |

## Validation navigateur

**Non effectuée.** Aucun navigateur réel n'a été utilisé. Sont testés :
- les contrats HTTP et HTML : en-têtes CSP et XFO, attributs `sandbox`,
  `referrerpolicy` et `title`, URL de l'iframe, réponses du proxy et du
  runner ;
- le refus du POST par le proxy.

Ne sont **pas** vérifiés : l'acceptation effective de l'iframe par un
navigateur (CSP `frame-src` de l'éditeur, `frame-ancestors` réécrit par le
proxy, absence de XFO), le blocage effectif des formulaires et de la
navigation par la sandbox, et le rendu visuel.

## Fichiers créés

- `forge_design/real_preview/route_selection.py`
- `forge_design/web/real_preview.py`
- `tests/test_real_preview_route_selection.py`
- `tests/test_web_real_preview.py`
- `docs/rapports/FD-REALPREVIEW-004.md`

## Fichiers modifiés

- `forge_design/web/server.py` : runtime, panneau, routes Start/Stop, arrêt
  avant fermeture, `ForgeDesignServer`, `create_server(real_preview=…)`,
  `finally` de `run_server`.
- `forge_design/web/editor.py` : protocole du panneau, `editor_frame_policy`,
  `render_editor_error`, notices, `check_editor_post` et
  `editor_form_fields` (renommage public des contrôles existants).
- `forge_design/web/inspector.py` : `release` du refresh, statut `busy`.
- `forge_design/web/recent_projects.py` : statut `busy`.
- `forge_design/project_selector.py` : `before_change`, statut `busy`.
- `forge_design/web/templates/editor.html`,
  `forge_design/web/static/shell.css`.
- `tests/test_cli.py` : `real_preview = None` sur deux faux serveurs.
- `docs/preview/real-preview-contract.md` (« Intégration Web »),
  `docs/02-architecture.md`, `docs/editor/structural-editor.md`.

`docs/04-compatibilite-forge.md` n'est pas modifié : aucune nouvelle
différence Forge.

## Validation globale finale

Ordre suivi : code, tests de sélection, tests Web, tests de cycle de
projet, intégration réelle, mutations, répétitions, documentation, rapport,
wheel et installation (avant les validations finales, pour que le rapport
soit complet), statique final, et enfin suite globale.

| Commande | Résultat |
|---|---|
| `pytest -q tests/test_real_preview_route_selection.py` | 36 réussis |
| `pytest -q tests/test_web_real_preview.py` | 74 réussis |
| Régressions Web, projet, récents, Inspector, CLI, routes, registre, runtime | 1124 réussis |
| Répétition ×5 (Web, sélection, proxy, runner) | 343 réussis à chaque passe |
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` / `ruff format --check .` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |
| `pytest` (depuis le scratchpad, `--rootdir` vers le dépôt) | **4048 réussis** en 66 s, aucun échec |
| `python -m pip check` | No broken requirements found |
| `node --check` / MkDocs | N/A : aucun JavaScript modifié, aucune configuration MkDocs |

Seul ce tableau a été ajouté au rapport après l'exécution. Les validations
statiques et la suite globale ont ensuite été relancées sur le contenu final,
avec un résultat identique. Aucun `storage/` n'a été créé dans le répertoire
d'exécution, et aucun processus de preview n'a survécu.

## Limites restantes

- Aucune validation navigateur réelle (voir ci-dessus).
- Start est synchrone : la requête attend la readiness (jusqu'à 15 s), et un
  Stop concurrent attend la fin de Start.
- Route Explorer est relu à chaque affichage de l'éditeur, ce qui coûte
  autant que la page Routes sur un gros projet.
- Les déclarations non interprétées par Route Explorer (opt-ins) ne sont pas
  prises en compte dans l'unicité de la route.
- Les cookies ne sont pas isolés par port. HEAD vers une route Forge rc9 donne
  405, comportement de la cible.
- Un runner impossible à arrêter garde son projet courant ; à l'arrêt de
  Forge Design, la fermeture reste au mieux, sans garantie.

## État Git final

Un commit sur `main`, rapport inclus, sans push.
Message : `feat: intégrer la preview réelle au Web (FD-REALPREVIEW-004)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit. Hash :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-REALPREVIEW-004.md
```
