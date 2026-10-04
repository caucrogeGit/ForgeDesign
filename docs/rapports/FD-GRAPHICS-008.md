# Rapport — FD-GRAPHICS-008

API : [Moteur graphique — clients](../graphics/graphics-engine.md#clients) ;
contrat : [Graphic Core](../graphics/graphics-core-contract.md#troisième-client--fd-graphics-008) ;
outil : [Debug Center](../tools/debug-center.md#flux-runtime-sur-le-graphic-core-fd-graphics-008).

## Ticket et objectif

Faire du graphe « Flux runtime » de `/debug/event` le troisième client réel du
Graphic Core, sans changer la sémantique de Debug Center, et utiliser ce
client de nature différente (un flux séquentiel, et non une structure) pour
éprouver la généricité du moteur.

## État Git initial

```text
$ git log --oneline -3
c24dc6c feat: ajouter la minicarte au Graphic Core (FD-GRAPHICS-007)
3221814 feat: ajouter le semantic zoom au Graphic Core (FD-GRAPHICS-006)
04f0af8 feat: compacter le routage des graphes (FD-GRAPHICS-005)
$ git rev-parse --short HEAD
c24dc6c
$ git rev-parse --short origin/main
3221814
$ git status --short
 M docs/rapports/FD-CONTRACT-001.md
```

## Divergence HEAD / origin éventuelle

HEAD local a **un commit d'avance** sur `origin/main` : FD-GRAPHICS-007
(`c24dc6c`), validé et non poussé. Aucun commit distant absent localement. Le
ticket est construit sur `c24dc6c` ; aucun retour à `origin/main`.

## Référence DrawCiel

Précédente : `88f95b75`. `git fetch` dans la copie SéquenCiel (lecture
seule) : `origin/main` = **`88f95b75`**, inchangé, figé pour le ticket.

## Delta DrawCiel

Vide. Impact : aucun ; le ticket ne reprend rien de DrawCiel.

## Debug Center avant migration

```text
DebugError → build_debug_flow → DebugFlow → layout_debug_flow → SVG Jinja spécifique
```

Le SVG est statique : 220 × 90 par étape, une étape tous les 300, hauteur 130,
marqueur de flèche local, `role="img"` avec titre et description. Il est
affiché à 100 % dans un conteneur défilant, sans interaction.

## Sémantique de DebugFlow

`build_debug_flow` (inchangé, **0 modification**) ne retient que les
propriétés structurées présentes :

- requête (méthode et chemin), route, contrôleur, SQL (« Requête
  disponible »), template ;
- aucune inférence depuis le message, la catégorie ou la traceback ;
- aucun modèle ni réponse.

Le graphe relie ces étapes dans leur **ordre conceptuel** ; ce n'est pas une
trace d'exécution. La phrase « Ce schéma ne constitue pas une trace
d'exécution. » reste visible au-dessus du graphe, avec ou sans JavaScript, et
figure dans la description de la scène.

## Architecture après migration

```text
DebugError ─▶ build_debug_flow ─▶ DebugFlow ─▶ layout_debug_flow ─▶ DebugFlowLayout
                         (un seul calcul par GET /debug/event)        │
                                    ┌─────────────────────────────────┤
                                    ▼                                 ▼
                     SVG Jinja (repli sans JavaScript)   debug_flow_scene.build_debug_graphic_scene
                                                                      ▼
                                                     scene_json_payload → <script type="application/json">
                                                                      ▼
                                                     /debug-flow.js → createGraphicEngine (mêmes modules)
```

`show_debug_detail` calcule le flux et le layout une seule fois, puis la scène
seulement s'il existe au moins une étape. Sans étape : ni scène, ni hôte, ni
client.

## Adaptateur Debug → GraphicScene

`forge_design/web/debug_flow_scene.py` : transformation pure de
`DebugFlowLayout` en GraphicScene sérialisable. Il n'importe ni `DebugError`
ni `build_debug_flow`, il ne lit aucun fichier, Tool, Request ou journal (tests
statique, de signature et d'isolement). Le vocabulaire Debug (requête, route,
contrôleur, SQL, template) reste dans ce fichier.

## Identités

- Nœuds : `debug-node-request`, `-router`, `-controller`, `-sql`,
  `-template`, reprises telles quelles (et identiques à celles du repli).
- Arêtes : `json.dumps(("debug-flow", source, cible))`, par exemple
  `["debug-flow","debug-node-request","debug-node-router"]`. C'est
  déterministe (aucun `hash()`) et unique, puisque le flux est séquentiel.
- Même layout → même scène → même JSON (test).

## Nœuds

| Champ | Valeur |
|---|---|
| `label` | « Libellé — détail complet » (nom accessible, `<title>`), borné à 256 caractères avec « … » ; SQL : « SQL — Requête disponible » |
| `lines` | `[libellé, détail tronqué du layout]` (24 caractères), ou `[libellé]` seul |
| `levels` | `overview: []`, `normal: [0]` ; `detail` : tout |
| `presentation` | requête → `category-1`, route → `category-2`, contrôleur → `category-3`, SQL → `category-4`, template → `category-5` (modèle → `category-6`, réponse → `default`, jamais produits aujourd'hui) |
| `data` | aucune : pas de panneau, rien à transporter |

Le libellé figure à la fois dans `label` (nom accessible complet) et dans
`lines[0]` (texte affiché) : c'est la convention actuelle du renderer, qui
n'affiche que `lines`. Ce n'est pas une duplication inutile.

Une valeur de journal peut atteindre 64 Kio, au-delà de la borne du moteur
(8 192). Plutôt qu'élargir la borne, l'adaptateur limite le nom accessible ; la
valeur complète reste dans les sections Requête HTTP et Contexte Forge, et dans
le `<title>` du repli.

## Arêtes

`source` et `target` repris exactement de `DebugFlowEdge`. Les points sont
`[{x1, y1}, {x2, y2}]` du layout, avec `arrow: "end"` : la flèche générique
du moteur remplace le marqueur local, sans libellé d'arête.

## Layout

Inchangé, côté Python : une ligne horizontale, `20 + i × 300`, nœuds de
220 × 90, hauteur 130. Ni compaction, ni couloirs, ni routeur : le moteur
reçoit une scène positionnée.

## Semantic zoom

Mécanisme de FD-GRAPHICS-006, sans nouvelle logique. Mesuré (Chromium et
Firefox) :

| Flux | Taille | Échelle au fit | Niveau au fit |
|---|---|---:|---|
| complet, 5 étapes | 1460 × 130 | **0,523** | **overview** (aucun texte, 6,3 px équivalents) |
| partiel, 2 étapes | 560 × 130 | 1,0 | detail |

Les trois niveaux sont atteints par zoom :

- `overview` à 0,523 ;
- `normal` à 0,654 : libellés seuls ;
- `detail` à partir de 0,818 : libellés et détails.

Voir les limites restantes : le niveau au fit d'un flux long est un constat
important.

## Viewport

Fit, zoom (boutons, Ctrl + molette), pan (glisser, Maj + flèches), home et
resize fonctionnent sans code Debug. Pan mesuré : 100,0 px pour un glisser de
100 px.

## Minicarte

Fonctionne sans code Debug :

- au fit, toute la scène est visible : minicarte masquée ;
- au zoom : visible, en bande de 5 rectangles colorés ;
- un clic recentre à échelle constante (cible 1314, centre obtenu 1313,9996).

## Sélection

Clic, Entrée, Espace et Échap (focus conservé) sont ceux du moteur. Les voisins
directs sont mis en évidence (2 pour le contrôleur). Pas de panneau : un
statut `role="status"` annonce « Étape sélectionnée : Contrôleur —
HomeController.index » ou « Sélectionnez une étape du flux. ». Les sections
existantes ne bougent pas.

## Accessibilité

Celle du moteur : SVG `role="group"` avec titre (« Flux des étapes runtime
connues ») et description (nuance « pas une trace d'exécution » comprise) ;
nœuds `role="button"`, focalisables, `aria-label` et `<title>`, clavier.
Statut annoncé. Le repli garde son `role="img"`, son `<title>` et son
`<desc>`.

## Fallback sans JavaScript

Le SVG Jinja actuel devient le repli statique (`data-graphic-fallback`),
masqué seulement après montage réussi du moteur. Il ne portait aucun faux
attribut interactif : les `id` et `data-*` sont purement descriptifs, et le
`tabindex` du conteneur sert au défilement clavier. Vérifié sans JavaScript
dans Chromium et Firefox : 5 étapes, titre, description, nuance et statut
« La sélection du graphe nécessite JavaScript… ». Aucun flux : « Aucun flux
structuré disponible pour cet événement. », aucun moteur.

## Sécurité

- CSP inchangée (`script-src 'self'`, sans `unsafe-inline`).
- Seuls deux `<script>` sont admis sur `/debug/event` : le bloc JSON inerte et
  le module `/debug-flow.js`. Les anciens tests « aucun `<script>` » sont
  remplacés par ce contrat exact (`foreign_scripts`), plus strict qu'une
  simple présence.
- Ni SQL complet, ni traceback, ni query HTTP dans la scène (tests) ; aucun
  `innerHTML` ; aucun accès réseau ou stockage dans le client.

## Données hostiles

`</text><script>alert(1)</script>` comme route :

- scène : `<`, `>` et `&` échappés en `\uXXXX` ; `JSON.parse` restitue le
  texte exact ;
- moteur : nom accessible « Route — </text><script>… » et ligne tronquée
  affichés comme texte (nœuds texte sans enfant) ;
- repli : échappé par Jinja ;
- aucune boîte de dialogue ni exception dans les deux navigateurs.

## Forge MVC

`/debug/event` reste une route Forge MVC (`create_application`, un `Router`,
Jinja, `create_wsgi_app`). Une seule route fixe ajoutée, `/debug-flow.js`,
comme `/route-graph.js` et `/entity-graph.js` (option A : pas de mécanique
générique pour trois scripts). Aucun endpoint JSON, polling, SSE, WebSocket
ni serveur parallèle. `/debug` reste le tableau filtrable, sans graphe.

## Absence de logique Debug dans Graphics

Test de vocabulaire étendu à `request`, `router`, `sql`, `debug`, `flow`,
`step`, `timeline` et `trace`, en mots entiers : `requestAnimationFrame` et
`PAN_STEP` ne sont pas des faux positifs. Le JavaScript du moteur est
**inchangé** (`git diff` vide sur `static/graphics/`).

## Comparaison Route / Entity / Debug

| Capacité | Route | Entity | Debug |
|---|---|---|---|
| Type de graphe | structure | structure (avec retours) | flux séquentiel |
| Layout (Python, client) | multi-colonnes | deux colonnes | une ligne |
| Couloirs partagés | oui | oui | non (arêtes droites) |
| Viewport | oui | oui | oui |
| Semantic zoom | oui | oui | oui |
| Minicarte | oui | oui | oui |
| Libellés d'arêtes | oui | oui | non |
| Données opaques | oui | oui | aucune |
| Panneau spécifique | oui | oui | non (statut accessible) |
| Source métier | RouteGraph | EntityGraph | DebugFlow |

## Modifications du Graphic Core nécessaires

- **JavaScript : aucune.**
- CSS : style des variantes génériques `category-5` et `category-6` (scène,
  vue d'ensemble, minicarte). Elles sont déclarées par le moteur depuis
  FD-GRAPHICS-002, mais aucun client n'en avait encore besoin. Sans ce style,
  le cinquième type serait blanc. Ce n'est pas une notion Debug.

## Extensions refusées

- Notion de flux, d'étape ou de chronologie dans le moteur.
- Élargissement des bornes de libellé : l'adaptateur borne le nom accessible.
- Mécanique générique de service des scripts clients : une route explicite
  suffit.
- Panneau Debug, lien d'un nœud vers une section ou vers la source :
  hors V1.
- Changement de politique d'ajustement ou compaction du layout pour le flux
  long : constat documenté, à arbitrer (voir les limites restantes).

## Tests Python

- `tests/test_debug_flow_scene.py` (40) : cas nominal (identités, ordre,
  extrémités, positions, taille, variantes, niveaux) ; identités d'arêtes
  déterministes ; 31 combinaisons partielles, sans requête obligatoire ;
  flux vide ; SQL jamais transporté et aucune inférence ; données hostiles ;
  valeurs longues ; adaptateur limité au layout ; projection sans accès ;
  scène validée par le vrai `validateScene`.
- `tests/test_web_debug_flow_interaction.py` (3) : contrat du client ;
  suite Node ; HTTP (deux scripts exactement, repli visible, identités de la
  scène égales à celles du repli, SQL dans sa section mais pas dans la scène,
  ressource `text/javascript`, aucun moteur sans étape).
- Contrat « scripts admis » dans `test_web_debug_flow.py`,
  `test_web_debug_detail.py` et `test_debug_center_stabilization.py`.
- Liste `node --check` et nombre de suites (13).
- Ciblés (debug flow, layout, scène, détail, filtres, Web Debug, Route,
  Entity, assets, frontière Forge, LOD, minicarte) : 690 réussis.

## Tests Node

99 tests (95 + 4) :

- `debug-client.test.mjs` (3) : montage, repli masqué, statut, voisins,
  Entrée, Espace, Échap, `destroy` ; texte hostile ; scène refusée ou absente ;
  aucun contournement (zoom, pan, minicarte, niveau, viewBox, points…
  interdits).
- `engine-three-clients.test.mjs` (1) : formes colonnes, deux colonnes et
  séquence dans trois instances. Même moteur et niveaux différents au fit
  (`overview`, `normal`, `detail`). Sélection, viewport, niveau et minicarte
  indépendants après interaction sur l'une puis l'autre.

## Chromium

Chrome 154 headless (CDP), projet témoin synthétique `tmp/gx8-browser` (copie
de `gx3-browser` plus un journal de trois événements).

Scénario Debug **12/12** :

- moteur visible, repli masqué, ordre, 4 arêtes et flèches, titre et nuance ;
- niveau au fit selon l'échelle mesurée, minicarte masquée ;
- les trois niveaux par zoom ;
- minicarte visible au zoom, clic exact ;
- pan ; sélection à la souris et au clavier ;
- flux partiel ; aucun flux ; 400 et 404 sans scène ;
- trois clients réels dans une page (Debug, Route, Entity), indépendants ;
- aucune exception, boîte de dialogue ni violation CSP.

Sans JavaScript : repli complet. Non-régression Route et Entity : minicarte
**20/20**, semantic zoom **16/16**, viewport **29/29**. Captures inspectées :
au fit, 5 boîtes colorées sans texte ; en detail, libellés et détails,
minicarte en bande.

## Firefox

Firefox ESR 153 headless (BiDi) : Debug **12/12**, sans JavaScript complet ;
Route et Entity : minicarte **20/20**, semantic zoom **16/16**, viewport
**27/27**.

## Mutations

Une à la fois, `__pycache__` purgé, sources restaurées : **12/12 tuées**.

| Sabotage | Résultat | Premier test en échec |
|---|---|---|
| Debug contourne le Graphic Core (client retiré) | Tué | `test_http_scene_fallback_and_asset` |
| l'adaptateur relit DebugError | Tué | `test_adapter_receives_only_the_layout` |
| contrôleur inféré depuis la traceback | Tué | `test_flow_http[fields2-expected2]` |
| SQL complet injecté dans la scène | Tué | `test_sql_is_never_transported_and_no_inference` |
| source et cible inversées | Tué | `test_nominal_ids_order_endpoints_positions_and_size` |
| identité d'arête non déterministe | Tué | `test_edge_ids_are_deterministic_and_unique` |
| repli supprimé | Tué | `test_http_scene_fallback_and_asset` |
| le client implémente son propre zoom | Tué | `le client ne contourne pas le moteur` |
| le client implémente sa propre minicarte | Tué | idem |
| vocabulaire Debug dans le moteur | Tué | `aucune connaissance de Route Explorer ni d'un domaine` |
| données hostiles interprétées comme balisage (`|safe`) | Tué | `test_http_scene_fallback_and_asset` |
| troisième instance partage le viewport | Tué | `deux instances : minicartes…` et, seul, `trois instances…` |

Un premier mutant de partage était **quasi équivalent** : il ne partageait que
l'état initial gelé, aussitôt réassigné localement, et a survécu. Il a été
reconstruit en vrai partage de la variable d'état, puis tué, y compris par le
seul témoin à trois instances.

## Packaging

`pyproject.toml` : `static/debug-flow.js` ajouté. La wheel contient
`web/debug_flow_scene.py` et `web/static/debug-flow.js`.

## Installation wheel

Installée isolément, sur le projet témoin Debug :

- `/debug` : 200, tableau seul ;
- `/debug/event` : 200, 5 nœuds, 4 arêtes, client et repli présents ;
- `/debug-flow.js` et les 8 modules `/graphics/*.js` servis en
  `text/javascript; charset=utf-8`, CSP inchangée ;
- l'adaptateur est chargé depuis l'installation.

## Performance

Rendu O(V + E). Flux complet : création du moteur en 2,0 à 6,2 ms (Node, faux
DOM, 3 mesures), 61 éléments DOM, minicarte comprise. Aucun polling, aucune
relecture du journal.

## Limites restantes

- **Constat principal du troisième client : un flux long et plat s'ajuste
  en vue d'ensemble.** 5 étapes (1460 × 130) dans une zone de 796 px donnent
  l'échelle 0,523, sous le seuil `normal` (0,583) : au chargement, l'utilisateur
  voit 5 boîtes colorées sans texte, dans une zone de 478 px de haut
  surtout vide. Un clic sur « + » affiche les libellés, deux affichent les
  détails ; le statut et les sections de la page restent lisibles.
  Auparavant, le SVG statique s'affichait à 100 % avec défilement horizontal.
  Pistes, non tranchées : une politique générique d'ajustement lisible (par
  exemple ajuster à la hauteur d'une scène plate, la minicarte servant alors
  à la navigation horizontale) ; une compaction du layout Debug (un pas de 260
  donnerait 0,588, donc `normal`) ; une hauteur de zone adaptée aux scènes
  plates. Les flux de 4 étapes ou moins sont en `normal` ou `detail` au fit.
- Pas de panneau ni de lien d'un nœud vers une section (V1).
- Hors périmètre : le test instable `test_runtime_detects_dead_proxy`
  (Real Preview).

## Roadmap

FD-GRAPHICS-008 fait. La suite dépend de la décision J, à confirmer par le
porteur.

### Décisions obligatoires

| | Question | Réponse |
|---|---|---|
| A | Le Graphic Core actuel a-t-il suffi ? | **Oui.** Aucune modification du JavaScript du moteur ; seul le style CSS des variantes génériques `category-5` et `category-6`, déjà déclarées, a été ajouté |
| B | Le moteur connaît-il flow, debug, request, controller ou SQL ? | **Non** (test de vocabulaire étendu, mutation tuée) |
| C | Le lane router a-t-il été nécessaire ? | **Non** : arêtes droites à deux points ; le routage par couloirs reste une stratégie de layout client |
| D | Viewport, semantic zoom et minicarte sans code Debug ? | **Oui** (client de 37 lignes, interdits vérifiés ; deux navigateurs) |
| E | Le flux est-il une trace réelle d'exécution ? | **Non.** Il reste un ordre conceptuel des étapes connues, et l'interface le dit |
| F | Le SQL complet est-il envoyé dans la scène ? | **Non** (« Requête disponible » seulement ; tests et mutation) |
| G | Les trois clients utilisent-ils exactement les mêmes modules ? | **Oui** : les 8 modules `GRAPHICS_MODULES`, identiques |
| H | Capacités réellement utilisées par Debug ? | Mesuré dans les navigateurs : validation et rendu SVG, flèches génériques (4), variantes `category-1…5`, titre et description, sélection (souris, Entrée, Espace, Échap), voisins (2), `onSelectionChange` et `node(id)` pour le statut, fit, zoom, pan, les trois niveaux de détail, minicarte (apparition, clic). Non utilisées : libellés d'arêtes, données opaques, `edge(id)`, polylignes à plus de deux points, couloirs |
| I | Nouvelle abstraction nécessaire ? | **Aucune abstraction de modèle.** Un seul constat générique, de présentation : la politique d'ajustement donne une vue d'ensemble sans texte pour une scène longue et plate. À arbitrer (ajustement lisible, compaction client ou hauteur de zone), sans urgence de modèle |
| J | Le moteur est-il assez éprouvé pour commencer un premier module spécialisé externe ? | **Oui, pour la visualisation ; et c'est le moment d'arrêter de l'enrichir à vide.** Faits : trois clients de natures différentes (structure multi-colonnes, structure avec retours, flux séquentiel) sur les mêmes modules, sans retouche du JavaScript ; viewport, semantic zoom, minicarte, sélection et repli prouvés dans deux navigateurs ; aucune abstraction manquante révélée par le troisième client. Ce qui manque à un module spécialisé, ce sont des capacités **d'édition** (ports, commandes et historique, glisser de nœuds, routage interactif). Elles ne doivent pas être conçues dans le vide, mais contre les besoins réels du premier module. La prochaine phase peut donc devenir **l'architecture des modules spécialisés externes**. Graphics n'est pas « terminé » : l'édition reste à construire, pilotée par cette phase, et le constat d'ajustement lisible reste ouvert |

## Fichiers créés

- `forge_design/web/debug_flow_scene.py`
- `forge_design/web/static/debug-flow.js`
- `tests/test_debug_flow_scene.py`, `tests/test_web_debug_flow_interaction.py`
- `tests/js/graphics/debug-client.test.mjs`,
  `tests/js/graphics/engine-three-clients.test.mjs`
- `docs/rapports/FD-GRAPHICS-008.md`

## Fichiers modifiés

- `forge_design/web/debug_detail.py` (scène calculée une fois),
  `web/templates/debug_detail.html` (hôte, repli, scène, statut, client),
  `web/server.py` (`/debug-flow.js`), `web/static/shell.css` (`category-5`
  et `category-6`), `pyproject.toml`
- `tests/js/graphics/model.test.mjs` (vocabulaire),
  `tests/test_route_graph_script.py`, `tests/test_web_debug_flow.py`,
  `tests/test_web_debug_detail.py`, `tests/test_debug_center_stabilization.py`
- `docs/graphics/graphics-engine.md`, `docs/graphics/graphics-core-contract.md`,
  `docs/graphics/drawciel-reference.md`, `docs/02-architecture.md`,
  `docs/03-roadmap.md`, `docs/tools/debug-center.md`

## Validation globale finale

| Contrôle | Résultat |
|---|---|
| `python -m compileall -q forge_design` | Réussi |
| `ruff check forge_design tests` | Réussi |
| `ruff format --check .` | 391 fichiers conformes (Markdown compris) |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Réussi |
| `node --check` (8 modules, 3 clients, 15 fichiers de test) | Réussi |
| Suites Node `tests/js/graphics` | 99 réussis |
| Ciblés : debug flow, layout, scène, détail, filtres, Web Debug, Route, Entity, assets, frontière Forge | 690 réussis |
| Suite globale `pytest` (hors du dépôt, `--basetemp` court sous `tmp/`) | **4668 réussis**, relancée après insertion de ces résultats |
| `python -m pip check` | Aucune dépendance cassée |
| Chromium 154 | Debug 12/12, sans JavaScript complet ; Route et Entity : minicarte 20/20, semantic zoom 16/16, viewport 29/29 |
| Firefox 153 | Debug 12/12, sans JavaScript complet ; Route et Entity : minicarte 20/20, semantic zoom 16/16, viewport 27/27 |
| Wheel installée isolément | `/debug`, `/debug/event`, `/debug-flow.js`, `/graphics/*.js` |
| MkDocs | N/A : aucune configuration MkDocs dans Forge Design |

## État Git final

Commit unique `feat: migrer Debug Center sur le Graphic Core (FD-GRAPHICS-008)`,
au-dessus de `c24dc6c` (lui-même non poussé). `docs/rapports/FD-CONTRACT-001.md`
reste modifié localement, hors commit. Aucun push.
