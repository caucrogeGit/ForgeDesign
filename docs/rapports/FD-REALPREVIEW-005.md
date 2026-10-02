# Rapport — FD-REALPREVIEW-005

## Ticket et objectif

Valider la preview réelle (FD-REALPREVIEW-001 à 004) dans de vrais
navigateurs, et ne corriger que les écarts réellement observés entre les
contrats HTTP testés et le comportement du navigateur, sans changer
l'architecture runner → proxy → application Web → iframe.

## État Git initial

`main` synchronisée avec `origin/main` à `dc377e3` — FD-REALPREVIEW-004.
Seule modification suivie préexistante : `docs/rapports/FD-CONTRACT-001.md`,
préservée hors commit.

## Environnement navigateur

La machine de dev est un Debian 13 (trixie) sans session graphique, et aucun
navigateur n'y était installé. Avec l'accord de l'utilisateur, celui-ci a
installé les paquets officiels :

| Navigateur | Version | Pilotage |
|---|---|---|
| Chromium | 154.0.8037.92 (Debian 13) | `--headless=new`, Chrome DevTools Protocol |
| Firefox ESR | 153.4.0esr | `--headless`, WebDriver BiDi |

**Nature exacte de la validation.** Ce sont de vrais moteurs, qui appliquent
eux-mêmes CSP, `frame-ancestors`, `X-Frame-Options`, sandbox, cookies et
navigation. Ils ont été pilotés en headless par un petit client WebSocket
(bibliothèque standard, jetable, dans le scratchpad), sans Playwright,
Selenium ni dépendance ajoutée au projet.

Les actions passent par la page : clics sur les vrais boutons et
formulaires, liens, `fetch`. Console, réseau (statuts et en-têtes réels
reçus par le navigateur) et DOM sont lus par le protocole. Le rendu a été
vérifié sur des captures d'écran, examinées une à une. Il n'y a **pas** eu de
session humaine devant un écran.

Forge Design tournait sur `http://127.0.0.1:8765` (`run_server`), avec un
`XDG_CONFIG_HOME` dédié pour ne pas toucher aux projets récents de
l'utilisateur.

## Projet de test

Les projets sont synthétiques et construits depuis le squelette rc9 installé.
SéquenCiel n'a pas été utilisé, ni aucun projet réel. Projet A :
- routes publiques `/demo` (template `demo/index.html`), `/demo/page2` et
  `/demo/long` (300 lignes) ;
- `/demo/redirect` (302 `Location: /demo/page2`) et `/demo/absolute` (302 vers
  `http://127.0.0.1:<port runner>/demo/page2?via=absolute`, construit depuis
  le Host reçu) ;
- `/demo/fragment` (renvoie l'en-tête `HX-Request` reçu), `/demo/cookie`
  (`Set-Cookie`) et `/demo/boom` (500) ;
- `POST /demo/submit` ;
- un lien vers une route absente (404) ;
- `static/preview.css` et `static/preview.js`. Le JS modifie la page, sonde
  `window.top.document` et `window.parent.location`, et fournit des appels de
  type HTMX en GET et en POST par `fetch` avec en-têtes `HX-*`.

Trois Designs :
- `demo/index` : route `/demo` ;
- `demo/page2` : route `/demo/page2` ;
- `demo/orphan` : template sans route.

Autres projets :
- B, une copie valide de A ;
- un projet en échec au démarrage (`raise RuntimeError` dans `app.py`) ;
- un dossier non Forge.

**HTMX** : la bibliothèque htmx n'est pas disponible hors ligne dans le
squelette. Les interactions HTMX sont simulées par `fetch` avec les mêmes
en-têtes.

## Validation Chromium

Version : Chromium 154.0.8037.92. Tous les scénarios des sections suivantes
ont été exécutés deux fois : avant la correction, puis après, sans écart sur
les points de preview.

**Console** : aucune erreur `Refused to frame`, aucune violation CSP, aucune
erreur MIME. Messages observés, tous attendus :
- `[error/security] Blocked form submission to '/demo/submit' because the
  form's frame is sandboxed and the 'allow-forms' permission is not set.` ;
- `[error/network] … status of 405 (Method Not Allowed)` pour le `fetch`
  POST volontaire ;
- `404` de `/favicon.ico` de Forge Design, préexistant et sans rapport avec
  la preview (voir « Écarts observés »).

**Network** : statuts et en-têtes réels reçus, détaillés ci-dessous.

**Écart** : arrêt par SIGTERM et SIGHUP (voir « Écarts observés »).

## Validation Firefox

Version : Firefox ESR 153.4.0. Le parcours est réduit à l'essentiel : Start,
iframe, en-têtes, static, JS, sondes d'isolation, navigation GET, formulaire
POST, HTMX GET et POST, Stop.

- **Console (BiDi)** : aucun message. Il n'y a ni erreur CSP ni erreur de
  cadre ; Firefox ne remonte pas non plus par BiDi de message pour le
  formulaire bloqué (voir « Formulaires POST »).
- **Network** : mêmes en-têtes que sous Chromium (voir « CSP éditeur » et
  suivantes).
- **Écart** : aucun.

## Start

Un clic réel sur « Démarrer la preview réelle » envoie un POST (le navigateur
pose lui-même `Origin` et `Sec-Fetch-Site`), puis le 303 mène à
`/editor?design=…&notice=real-started`. L'état est alors « en cours
d'exécution », avec « Arrêter la preview réelle », l'origine du proxy et
l'iframe. **Iframe visible** dans les deux navigateurs : elle mesure 796 × 640
px et affiche la page cible avec son titre, sa feuille de style
(`rgb(26, 77, 143)` calculé pour le titre) et son JS (« JS exécuté »).

Avant Start, on observe la route `/demo`, l'avertissement d'effets de bord,
le bouton Démarrer, aucune iframe réelle et la preview statique présente.

## CSP éditeur

Réponse `GET /editor?…` reçue par le navigateur, preview active :

```text
default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-src 'self' http://127.0.0.1:41019
```

L'origine est exactement celle du proxy actif, sans joker ni autre port.
Acceptée par Chromium et Firefox : aucune erreur, iframe chargée.
`X-Frame-Options: DENY` reste sur l'éditeur. Sans preview, ou après Stop, la
CSP est la politique Forge sans `frame-src`.

## X-Frame-Options

**Absent, confirmé** sur la réponse du proxy reçue par le navigateur
(`x-frame-options` : absent), dans Chromium comme dans Firefox.

## frame-ancestors

CSP de la page cible reçue à travers le proxy :

```text
default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors http://127.0.0.1:8765; object-src 'none'; base-uri 'none'; form-action 'self'
```

**Accepté** : l'iframe se charge sans erreur dans les deux navigateurs. Les
autres directives Forge (`default-src`, `script-src`, `style-src`…) sont
conservées, seule `frame-ancestors` a changé.

## Sandbox

L'élément inspecté dans le DOM porte `sandbox="allow-scripts
allow-same-origin"`, `referrerpolicy="no-referrer"` et `title="Preview
réelle"`. `allow-forms`, `allow-popups`, `allow-top-navigation`,
`allow-downloads` et `allow-modals` sont absents. Effets réels dans les deux
navigateurs :
- les scripts s'exécutent ;
- l'origine propre est conservée (`fetch` same-origin et cookies) ;
- `window.top.document` et `window.parent.location` lèvent `SecurityError` :
  le script de l'iframe n'accède pas au DOM de Forge Design.

**Port du runner non exposé** : le port lu dans la ligne de commande de
l'enfant (par exemple 46693) n'apparaît pas dans le HTML de l'éditeur, et
l'iframe vise le seul port du proxy.

## Static

Requêtes émises par le navigateur et réponses reçues, en Chromium et en
Firefox :

| Requête | Statut | Type |
|---|---|---|
| `GET http://127.0.0.1:<proxy>/static/preview.css` | 200 | `text/css` |
| `GET http://127.0.0.1:<proxy>/static/preview.js` | 200 | `text/javascript` |

**Static chargé** : le CSS est appliqué et le JS exécuté. Aucune requête vers
le port du runner, et aucune erreur MIME.

## Navigation GET

**La navigation GET fonctionne** :
- un clic sur « Page 2 » dans l'iframe mène à
  `http://127.0.0.1:<proxy>/demo/page2` ;
- l'URL du parent reste celle de l'éditeur, dans les deux navigateurs ;
- le retour par lien fonctionne.

## Redirects

Testé en Chromium :
- **Relative** : 302 `Location: /demo/page2`, suivi dans l'iframe sur
  l'origine du proxy.
- **Absolue vers le runner** : la cible renvoie
  `http://127.0.0.1:<port runner>/…`, mais le navigateur reçoit
  `Location: /demo/page2?via=absolute` (réécrit par le proxy) et reste sur
  l'origine du proxy. Toutes les requêtes émises visent le proxy : **aucune**
  vers le port du runner.

## Formulaires POST

**Le formulaire POST est bloqué par la sandbox.** Un clic réel sur « Envoyer
(POST) » :
- **Chromium** : aucune requête POST émise, l'iframe reste sur `/demo`, et la
  console affiche « Blocked form submission to '/demo/submit' because the
  form's frame is sandboxed and the 'allow-forms' permission is not set. ».
- **Firefox** : aucune requête POST émise, l'iframe reste sur `/demo`, mais
  aucun message n'est remonté par BiDi `log.entryAdded`. Le blocage est
  constaté par l'absence de requête, pas par un message.

**POST au proxy : 405.** Une requête POST brute vers le proxy reçoit
`HTTP/1.0 405 Method Not Allowed`, `Allow: GET, HEAD`, et la réponse porte
`Content-Security-Policy: default-src 'none'; frame-ancestors
http://127.0.0.1:8765`.

## HTMX

Simulation par `fetch` avec en-têtes `HX-*`, en Chromium et en Firefox :
- **GET** `/demo/fragment` (`HX-Request`, `HX-Target`) : 200, fragment
  injecté « fragment HX-Request=true ». L'en-tête est bien transmis par le
  proxy jusqu'à la cible.
- **POST** `/demo/submit` avec `HX-Request` : 405, `Allow: GET, HEAD`. La
  cible n'est pas atteinte.

La bibliothèque htmx elle-même n'a pas été testée.

## JavaScript

Sous la CSP de la cible (`script-src 'self'`), le script externe
`/static/preview.js` s'exécute dans les deux navigateurs grâce à
`allow-scripts`. Le `fetch` same-origin de `/static/preview.css` donne
`200 text/css`.

## Cookies

Testé en Chromium : `/demo/cookie` pose `preview_cookie=bonjour`. Au
rechargement, la cible reçoit `Cookie: preview_cookie=bonjour`, visible aussi
dans `document.cookie`. Limite rappelée : les cookies `127.0.0.1` ne sont pas
isolés par port (Forge Design n'en pose aucun).

## Erreurs HTTP

Testé en Chromium : `/demo/absent` donne **404** (page « 404 · Forge » de la
cible) et `/demo/boom` donne **500** (page « 500 · Forge », mode dev). Les
deux réponses réelles s'affichent dans l'iframe, sans page Forge Design de
remplacement, et le parent ne change pas.

## Stop

**Stop ferme réellement la preview** (Chromium et Firefox). Un clic réel sur
« Arrêter » mène à la notice `real-stopped`. Ensuite :
- l'iframe réelle a disparu ;
- le bouton Démarrer est revenu ;
- la CSP de l'éditeur est revenue à la politique Forge, sans l'origine du
  proxy ;
- le port de l'ancien proxy refuse les connexions ;
- aucun processus du projet ne reste.

## Redémarrage

Testé en Chromium, trois cycles Start/Stop. Chaque fois :
- nouveau port de proxy, et CSP exactement égale à `frame-src 'self'
  <nouvelle origine>` ;
- ancien proxy fermé, proxy courant fermé après Stop ;
- aucune iframe fantôme, aucun processus ni thread survivant.

## Changement Design

Testé en Chromium, runtime actif :
- `demo/page2` : l'iframe vise `<même proxy>/demo/page2`, et les PID du
  runner sont inchangés (aucun redémarrage).
- `demo/orphan` : « Preview réelle indisponible : Aucune route GET publique
  connue pour ce template. », sans iframe. L'application reste en cours
  d'exécution, avec le bouton Arrêter.

## Changement projet

Testé en Chromium, A en cours d'exécution :
- **ouverture de B** par le formulaire de l'Inspector : B devient courant,
  aucun processus de A ne survit, et l'ancien proxy de A refuse les
  connexions ;
- **dossier non Forge** : A reste courant, son runner tourne, et l'iframe
  reste présente.

## Fermeture projet

Testé en Chromium : avec la preview active, un clic sur « Fermer le projet »
donne « Aucun projet ouvert. ». Aucun processus de A ne reste et le proxy
refuse les connexions.

## Fermeture Forge Design

Avec la preview active, pour chaque signal :

| Signal | Avant correction | Après correction |
|---|---|---|
| SIGINT (Ctrl+C) | serveur arrêté, preview arrêtée | idem |
| SIGTERM | serveur tué, **runner orphelin** (PPID 1, propre session) | serveur arrêté, runner et proxy arrêtés |
| SIGHUP | même mécanisme que SIGTERM | serveur arrêté, runner et proxy arrêtés |

Après correction : aucun survivant, aucune trace dans le journal, et le port
8765 est fermé.

Lors du premier essai, SIGINT semblait ignoré. C'était un artefact du
lancement en arrière-plan par `&` (SIGINT hérité ignoré). Le lanceur a été
corrigé, et ce n'était pas un défaut de Forge Design.

## Validation visuelle

Examinée sur les captures d'écran, sans validation humaine à l'écran :
- les zones « Prévisualisation indicative » et « Preview réelle » sont
  distinctes et lisibles, dans les deux navigateurs ;
- les boutons sont clairs ;
- l'état « en cours d'exécution », « arrêtée » ou « en échec » est visible ;
- l'avertissement est encadré ;
- l'erreur et les logs sont lisibles dans un bloc (`<pre>`) ;
- l'iframe est dimensionnée sans débordement ;
- la page longue défile dans l'iframe, et cliquer dans l'iframe laisse
  l'éditeur utilisable.

Remarque mineure, non corrigée : les lignes « Route » et « État » sont
serrées, sans espacement.

Testé en largeur desktop seulement : 1400 px de fenêtre, iframe de 796 px
dans la colonne de contenu. Aucun preset responsive n'a été ajouté.

## Écarts observés

1. **Arrêt de Forge Design par SIGTERM ou SIGHUP : application cible
   orpheline.**
   - *Défaut* : `run_server` ne traitait que `KeyboardInterrupt`. SIGTERM
     (`kill`, `systemd`) ou SIGHUP (terminal fermé) tuaient le processus sans
     exécuter le `finally`.
   - *Effet* : l'enfant de preview, lancé avec `start_new_session=True` et
     donc hors du groupe du terminal, survivait avec PPID 1, toujours en
     écoute. Le proxy disparaissait avec le serveur.
   - *Correction* : voir ci-dessous.
2. **`/favicon.ico` de Forge Design.**
   - *Défaut* : 404 dans la console sur chaque page. Côté serveur, Forge
     journalise une trace « Rendu de errors/404.html impossible ; repli sur
     une réponse minimale », car Forge Design n'a pas ce template.
   - *Portée* : préexistant et sans rapport avec la preview, donc non corrigé
     ici.
   - *Ticket proposé* : servir une icône ou fournir un template d'erreur à
     Forge Design.
3. **Mise en page** : espacement serré dans le panneau, remarque mineure et
   non corrigée.
4. **Formulaire bloqué sous Firefox** : pas de message BiDi.
   - *Constat* : le blocage reste vérifié (aucune requête POST, aucune
     navigation).

Aucun écart CSP, `frame-ancestors`, XFO, sandbox, static, navigation,
redirection, cookie ou cycle de vie n'a été observé.

## Corrections appliquées

`forge_design/web/server.py`, de façon minimale, sans changer
l'architecture : `run_server` entre dans `_stop_signals_as_interrupt()`,
placé à l'extérieur de `create_server`.
- Dans le thread principal seulement, pendant le service, SIGTERM et SIGHUP
  lèvent `KeyboardInterrupt`, donc suivent le chemin de Ctrl+C et du
  `finally` : runtime fermé (proxy, puis runner), puis écoute fermée.
- Après le premier signal, les suivants sont ignorés jusqu'à la fin de la
  fermeture.
- Les gestionnaires d'origine sont restaurés en sortie.
- Hors du thread principal, rien n'est installé.

Aucun autre fichier de code n'est modifié : ni `controller.py`,
`child_bootstrap.py`, `proxy.py`, `real_preview.py`, `editor.py`, ni le
template ou la CSS.

## Tests automatisés

Ajouts à `tests/test_web_real_preview.py` (6 tests), qui reproduisent le
défaut :
- `test_run_server_stops_on_signal[SIGTERM|SIGHUP]` : le signal, envoyé
  pendant `serve_forever`, interrompt le service. Le gestionnaire extérieur
  n'est pas appelé, le runtime est fermé (proxy, puis runner), le socket est
  fermé et le gestionnaire d'origine est restauré.
- `test_run_server_outside_main_thread_installs_no_handler`.
- `test_real_signal_stops_preview[SIGINT|SIGTERM|SIGHUP]` : `run_server` dans
  un vrai sous-processus et un vrai runner sur un projet synthétique rc9. Le
  signal arrête le serveur sans trace ; aucun processus survivant et proxy
  fermé.

**Mutation** : sans la correction, 4 tests échouent (SIGTERM et SIGHUP,
unitaires et réels) et la fixture signale 2 orphelins. Le cas SIGINT passe,
comme attendu. Restauration vérifiée par `cmp`.

Les sessions navigateur elles-mêmes (sandbox, rendu, console) ne sont pas
reproductibles par pytest seul. Elles restent consignées dans ce rapport, et
leurs scripts sont restés hors du dépôt.

## Wheel

Wheel `forge_design-0.1.0.dev0-py3-none-any.whl` dans `tmp/wheels` (ignoré),
SHA-256 `e4b80a187e86ff80596a71b447cba54d4fe82dfd85f37da884156e2c6c8fac0f`.
Elle a été installée en `--no-deps --no-index --target` dans un dossier
temporaire. Le serveur a été lancé depuis l'installation, origine vérifiée,
sur un projet synthétique :

| Étape | Résultat |
|---|---|
| `POST /inspector` | 200 |
| Start | 303, iframe `http://127.0.0.1:56891/`, `frame-src 'self' http://127.0.0.1:56891` |
| GET de l'iframe | 200 `text/html`, sans `X-Frame-Options` |
| `/static/preview.css` | 200 |
| Stop | 303, proxy fermé |
| Start, puis SIGTERM du serveur | sortie 0, aucun survivant, aucune trace |

## Limites restantes

- **Pas de session humaine à l'écran** : la validation visuelle repose sur
  des captures examinées. Une passe manuelle courte sur le poste de
  l'utilisateur reste possible (voir la checklist proposée en fin de
  ticket).
- **Firefox** : parcours réduit, et le blocage du formulaire n'y est pas
  signalé par un message BiDi.
- **htmx** : bibliothèque réelle non testée (simulation `fetch` + `HX-*`).
- **Échec du proxy** (§73) : non reproductible simplement en navigateur (le
  proxy prend un port éphémère). Il reste couvert par les tests automatisés de
  FD-REALPREVIEW-004.
- **Arrêt brutal** : un `SIGKILL` de Forge Design laisse toujours la preview
  orpheline, ce qui est impossible à intercepter ; la limite est déjà
  documentée.
- **Favicon et espacement du panneau** : voir « Écarts observés ».
- **Cookies** : non isolés par port.
- **Environnement de test** : `/tmp` (tmpfs de 5,9 Go) a saturé pendant la
  session, occupé par des copies `/tmp/sequenciel-*` étrangères à ce ticket.
  Profils navigateurs, journaux et dossiers temporaires de pytest ont été
  déplacés sous `ForgeDesign/tmp/` (ignoré par Git).

## Fichiers modifiés

- `forge_design/web/server.py` : `_stop_signals_as_interrupt`, `run_server`.
- `tests/test_web_real_preview.py` : 6 tests d'arrêt par signal.
- `docs/preview/real-preview-contract.md` : section « Validation
  navigateur ».
- `docs/rapports/FD-REALPREVIEW-005.md` (créé).

`docs/02-architecture.md`, `docs/04-compatibilite-forge.md` et
`docs/editor/structural-editor.md` ne sont pas modifiés : il n'y a ni
changement d'architecture, ni nouveau comportement Forge, ni différence
d'usage. Aucune capture d'écran n'est ajoutée au dépôt.

## Validation finale

Ordre suivi :
1. état Git ;
2. Forge Design et projets de test ;
3. sessions Chromium puis Firefox ;
4. écarts ;
5. correction ;
6. nouvelle session navigateur et contrôle des trois signaux ;
7. tests automatisés et mutation ;
8. documentation et rapport ;
9. wheel et installation ;
10. statique final ;
11. suite globale.

| Commande | Résultat |
|---|---|
| `python -m compileall -q forge_design` | Succès |
| `ruff check forge_design tests` / `ruff format --check .` | Succès |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Succès |
| Tests ciblés : `test_web_real_preview`, sélection, proxy, contrôleur, bootstrap, `test_web_*`, sélection de projet, récents, Inspector, routes, CLI | 1104 réussis |
| `pytest` (depuis le scratchpad, `--rootdir` vers le dépôt) | **4054 réussis** en 67 s, aucun échec |
| `python -m pip check` | No broken requirements found |
| `node --check` / MkDocs | N/A : aucun JavaScript modifié, aucune configuration MkDocs |

Incident d'environnement : une première suite globale lancée avec
`--basetemp` sous `ForgeDesign/tmp/` (choisi à cause de `/tmp` saturé) a fait
échouer deux tests existants. Leurs sockets Unix dépassaient la limite de 108
caractères (`AF_UNIX path too long`). Après suppression de mes propres
dossiers pytest dans `/tmp`, la suite a été relancée avec le dossier
temporaire par défaut : tous les tests réussissent. Aucun code n'est en
cause.

Seul ce tableau a été ajouté au rapport après l'exécution. Les validations
statiques et la suite globale ont ensuite été relancées sur le contenu final,
avec un résultat identique. Aucun `storage/` n'a été créé dans le répertoire
d'exécution, et aucun processus de preview n'a survécu.

## État Git final

Un commit sur `main`, rapport inclus, sans push.
Message : `fix: fiabiliser la preview réelle navigateur (FD-REALPREVIEW-005)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit. Hash :

```bash
git log -1 --format='%H %s' -- docs/rapports/FD-REALPREVIEW-005.md
```
