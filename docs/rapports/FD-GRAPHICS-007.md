# Rapport — FD-GRAPHICS-007

API : [Moteur graphique — minicarte](../graphics/graphics-engine.md#minimap) ;
contrat : [Graphic Core](../graphics/graphics-core-contract.md#minimap--navigation-spatiale--fd-graphics-007).

## Ticket et objectif

Donner à chaque instance du Graphic Core une minicarte générique synchronisée
avec son viewport. Elle doit montrer toute la scène et la zone visible, et
permettre de recentrer la vue d'un geste, sans connaissance métier.
**Une seule scène, un seul viewport, une minicarte dérivée.**

## État Git initial

```text
$ git log --oneline -1
3221814 feat: ajouter le semantic zoom au Graphic Core (FD-GRAPHICS-006)
$ git rev-parse --short origin/main
3221814
$ git status --short
 M docs/rapports/FD-CONTRACT-001.md
```

## Référence DrawCiel

Précédente : `88f95b75`. `git fetch` dans la copie SéquenCiel (lecture
seule) : `origin/main` = **`88f95b75`**, inchangé, figé pour le ticket. Aucun
commit local non publié.

## Delta DrawCiel

Vide.

## Minicarte DrawCiel étudiée

Fichiers : `static/vendor/drawciel/js/app.js`, `index.html`, `style.css` à
`88f95b75`.

- **Élément** : `<canvas id="minimap" width="190" height="125"
  title="Mini-carte · cliquer pour se déplacer">`. Superposition fixe en bas à
  droite (CSS `position: absolute; right: 12px; bottom: 12px; z-index: 4`),
  masquée en mode impression ou élève. Pas de nom accessible, pas de focus,
  pas de clavier.
- **`renderMinimap()`** : **redessine tout** à chaque changement de vue (12
  appels : zoom, pan, centrage, historique de vue, auto-pan de câblage).
  Bornes = `navigationBounds()` : union de la vue et du projet, marge 120,
  minimum 200 × 160. Elles **varient avec le viewport**. Ajustement uniforme
  `s = min(W/b.w, H/b.h)`, centré (`ox`, `oy`), découpe. Fils en polylignes,
  composants en rectangles bleus, textes en rectangles violets, zone visible
  en rectangle orange (`viewportWorld()`). Couleurs fixes, thème sombre.
- **`minimapNavigate(e)`** : client → pixel canvas (corrigé de l'échelle
  CSS), puis `x = b.x + (px − ox) / s`, puis `centerWorldPoint(x, y)` : le
  zoom est conservé.
- **Écouteurs** : `pointerdown` (capture, navigation), `pointermove` tant que
  `minimapDrag`, `pointerup` (navigation + historique), `pointercancel`. Le
  « glisser » est un **recentrage continu sur le pointeur**, sans décalage de
  saisie : la vue saute au point pressé.
- **État** : entièrement global (`minimap`, `minimapState`, `minimapDrag`,
  `zoom`, `pan`, `scrollArea`, `workspace`) ; une seule minicarte par page.

## Besoin observé après FD-GRAPHICS-006

À `normal` (0,70), Route s'affiche sur environ 1 490 px pour une zone de
796 px. On ne sait plus où l'on se trouve dans la scène, et atteindre une
zone éloignée demande plusieurs pans.

## Architecture

```text
GraphicScene ──┬──▶ renderer SVG principal ──▶ viewport { scale, x, y }
               │                                      │ visibleWorldRect()
               └──▶ minimap.js : structure (une fois) ◀─┘ rectangle visible (O(1))
                         │ clic / glisser / flèches
                         └──▶ viewport.centerAt(point monde) / panBy
```

Nouveau module `graphics/minimap.js` : fonctions pures et vue SVG. Le moteur
possède la minicarte (création, écouteurs, destruction) dans un conteneur
générique `.gx-stage` : la minicarte d'abord, la zone `.gx-viewport` ensuite.
Les clients Route et Entity et les templates sont inchangés.

## Choix Canvas ou SVG

| Critère | Canvas (DrawCiel) | SVG (retenu) |
|---|---|---|
| Simplicité | Redessin manuel, gestion de la densité de pixels | Éléments déclaratifs, `viewBox` |
| Performance du pan | Redessin complet (ou calques) à chaque pan | 4 attributs d'un `<rect>` |
| Coût DOM | 1 élément | **10 éléments au plus** (fond, arêtes, une par variante présente — 7 au plus —, zone) grâce à des chemins regroupés, quel que soit V ou E ; 7 pour Route et pour le gros témoin |
| Hit-testing | Inutile (conversion de coordonnées) | Inutile (même conversion) |
| Accessibilité | `title` seulement | Conteneur focalisable, nom accessible, SVG `aria-hidden` |
| Mise à l'échelle | Flou sur écran haute densité sans code dédié | Vectoriel, net, réductible en CSS |
| Réutilisation | Aucune | Mêmes classes génériques de variantes, mêmes conventions de rendu |
| Tests | Canvas absent du faux DOM | Testable hors navigateur (Node) |
| Généralisation | — | Même projection possible pour d'autres clients |

**Décision : SVG**, et pas « parce que Forge Design fait déjà du SVG » :
pour le DOM constant, la mise à jour en O(1), la netteté et la testabilité.

## Modèle géométrique

Entrées explicites, aucune lecture du DOM dans les mathématiques :
`scene.width`, `scene.height`, `node.rect`, `node.presentation.variant`,
`edge.points`, l'état du viewport et la taille de zone. Ni re-routage, ni
layout, ni modification de la scène.

## Dimensions

`minimapLayout` : ajustement uniforme dans **200 × 140 px au plus**, marge
interne de 6 px, proportions de la scène (la minicarte prend sa forme, sans
bandes vides). Route : **200 × 106,5** ; Entity : **146,9 × 140**. En CSS, au
plus 40 % de la largeur de la zone. Dans une zone de 445 px, Route passe à
178,8 px et la conversion reste exacte (vérifié dans les navigateurs).
Dimensions invalides (`NaN`, `±Infinity`, `0`, négatif, marge excessive)
refusées (`RangeError`).

## worldToMinimap

`(marge + x × s, marge + y × s)`, avec
`s = min((maxW − 2·marge) / largeur, (maxH − 2·marge) / hauteur)`.
Exemples testés : sans marge, 2000 × 1000 dans 200 × 100 donne (0,0) → (0,0),
(1000,500) → (100,50) et (2000,1000) → (200,100). Avec la marge par défaut,
(1000,500) → (100,53) exactement.

## minimapToWorld

`((px − marge) / s, (py − marge) / s)`, inverse vérifié à 10⁻⁹. Le passage
client → minicarte applique le rapport taille naturelle / taille affichée (la
même correction que DrawCiel), donc reste juste quand la CSS réduit la
minicarte.

## Rectangle viewport

`visibleWorldRect(state, zone) = {x, y, largeur / scale, hauteur / scale}`,
c'est-à-dire le viewBox courant (`null` tant que la zone n'est pas mesurée).
Projeté en pixels de minicarte, puis **borné à la minicarte** (marge
comprise) : au fit, il couvre exactement la scène. Si la vue sort
entièrement de la scène, un repère minimal de 4 px reste au bord, à la
projection bornée du vrai centre, et indique la direction. Le centre réel
n'est jamais faussé : seul le dessin est borné.

## Politique d'affichage

**Option B** : affichée seulement si toute la scène n'est pas visible.
`sceneCoverage = min(part visible de la largeur, de la hauteur)` ;
`needsMinimap` affiche sous **0,97** et masque à partir de **0,995**
(hystérésis contre le clignotement). La politique dépend de la géométrie
visible, jamais du niveau de détail. Elle n'agit pas pendant un glisser ni
lorsque la minicarte a le focus, pour ne pas la retirer sous l'utilisateur.
Mesuré :

- Route au fit : masquée ; zoomée à 0,70 : visible ;
- Entity au fit : masquée ; zoomée à 0,75 : visible (86 % de la hauteur
  seulement) ;
- Ajuster : de nouveau masquée ;
- un pan au fit fait sortir une partie de la scène : la minicarte apparaît.

## Navigation au clic

Un clic recentre la vue sur le point monde pointé, **échelle conservée**.
Mesuré dans Chromium et Firefox :

- Route : cible (1908, 533), centre obtenu (1907,999, 533,18) ;
- Entity : cible (702, 370), centre obtenu (701,996, 369,97) ;
- tolérance : 1,5 px de minicarte ;
- la sélection et le panneau sont conservés.

## Drag éventuel

**Inclus**, sans complexité excessive :

- depuis le rectangle visible, le rectangle suit le pointeur en **gardant le
  décalage de saisie**, sans saut (amélioration sur DrawCiel) ;
- ailleurs, le glisser est un recentrage continu ;
- un appui-relâcher sans mouvement (≤ 3 px), même dans le rectangle, reste
  un clic qui recentre ;
- Pointer Events, capture du pointeur, `pointercancel`, bouton secondaire
  ignoré, `touch-action: none` (utilisable au doigt).

Mesuré : glisser de −12 px → vue déplacée de −12,0 px de minicarte
(Chromium et Firefox).

## API Viewport ajoutée

`centerState(state, zone, point)` et `viewport.centerAt(point)` : recentrer
une vue sur un point monde, échelle conservée, interaction comptée (le resize
garde ensuite le centre). Plus `visibleWorldRect`, sur lequel `viewBox`
s'appuie désormais. Côté moteur : `engine.centerAt(point)` et
`engine.minimap()` (inspection en lecture seule). Aucune API métier. La
minicarte passe par l'API du viewport, jamais par une écriture directe de
`x` ou `y`.

## Mise à jour

À chaque navigation (fit, home, boutons, molette, pan, resize, clic ou
glisser de minicarte), `updateMinimap` met à jour la visibilité, les 4
attributs du rectangle et le nom accessible. La structure (fond, chemins) est
créée une fois par rendu et n'est **jamais réécrite** (test : 0 écriture
pendant 100 pans et 100 zooms, transitions de niveau comprises).
`requestAnimationFrame` n'a pas été nécessaire : la mise à jour est O(1).

## Performance

- Rendu initial O(V + E), DOM constant.
- Navigation O(1) : moins de 0,01 ms par navigation dans Node.
- Route réelle (22 nœuds, 19 arêtes) : 7 éléments SVG.
- Gros témoin, 1 000 nœuds × 4 000 arêtes (Node, faux DOM, 3 mesures) :
  minicarte en 6,4 à 9,9 ms, moteur complet (validation, rendu, minicarte) en
  73 à 96 ms, 200 navigations en 1,1 à 1,8 ms ; 7 éléments ; chemin des
  arêtes de 97 359 caractères ; aucune réécriture de structure.
- Pas de micro-benchmark fragile : seule une borne large (< 5 s) est
  vérifiée.

## Route Explorer

Fit (36 %) : minicarte masquée, toute la scène est visible. Zoomée en
`normal` (70 %) : minicarte de 200 × 106,5 px en haut à droite. Elle montre
les 4 colonnes colorées par catégorie générique, les couloirs et la zone
visible ; son nom accessible annonce « Zone visible : de 23 à 77 % de la
largeur, de 18 à 82 % de la hauteur ». Un clic sur la colonne des
dépendances recentre. Inspection visuelle faite.

## Entity Explorer

Même mécanisme, aucun code spécifique. Fit (60 %) : masquée ; detail (75 %) :
visible, 146,9 × 140. Clic, glisser, pan, zoom, clavier et Ajuster vérifiés.

## Semantic zoom

Indépendants. La minicarte ne suit pas les niveaux : jamais de texte, ni de
libellé d'arête ; structure identique en `normal` et en `detail` (vérifié
dans les navigateurs) ; un changement de niveau ne réécrit rien (test Node).

## Sélection

Non représentée dans la V1 : la minicarte montre l'espace, pas l'état. Un
marqueur de sélection a été écarté : il faudrait un élément ou une mise à
jour de plus pour un gain d'orientation faible. Sélectionner ne modifie pas
la minicarte ; cliquer la minicarte ne change pas la sélection.

## Accessibilité

- La minicarte n'est jamais la seule voie : Ajuster, +, −, molette, pan et
  Maj + flèches couvrent tout.
- Conteneur focalisable (`tabindex="0"`, `role="group"`) placé **juste après
  la barre d'outils**. Nom accessible : « Mini-carte de la scène. Zone
  visible : de … à … % de la largeur, de … à … % de la hauteur. », mis à jour
  à chaque navigation.
- SVG intérieur `aria-hidden`, aucun nœud focalisable, aucune tabulation par
  nœud de minicarte.
- Flèches seules : déplacent la zone visible (même pas que Maj + flèches).
  Tab entre puis sort (pas de piège ; vérifié : « − » → minicarte → premier
  nœud).
- Masquée, elle sort de l'ordre de tabulation ; elle ne disparaît jamais
  quand elle a le focus.

## Deux instances

Chaque instance a sa minicarte, son rectangle, sa politique et sa navigation.
Page Entity avec une instance Route ajoutée : cliquer la minicarte Route
déplace Route et laisse le viewBox Entity identique (Chromium, Firefox). Un
test de mutation vérifie qu'aucun état n'est partagé.

## Lifecycle

La minicarte appartient à `createGraphicEngine()`.

- `render()` la recrée une seule fois ; l'ancienne perd tous ses écouteurs,
  liés au même `AbortController` que les nœuds.
- `destroy()` retire la minicarte et tous ses écouteurs, et rend
  `minimap()` inaccessible.

## Fallback sans JavaScript

Inchangé. Pas de minicarte, ce qui est accepté : le SVG serveur reste complet
et défilable. Firefox sans JavaScript : 2/2.

## Forge MVC

`create_application()` reste l'unique composition HTTP (tests de frontière).
`minimap.js` rejoint la liste fermée `GRAPHICS_MODULES` (route fixe,
`text/javascript; charset=utf-8`) ; un module hors liste répond 404. Pas
d'endpoint, de serveur JavaScript, de backend Node, de build ni de npm.

## CSP

Inchangée. Ni canvas ni image : aucune contamination de canvas possible.
Aucun `innerHTML`, aucun style en ligne, aucun stockage navigateur. Aucune
exception ni violation dans les deux navigateurs.

## Tests Node

95 tests (71 + 24) :

- `minimap.test.mjs` (11) : conversions avec et sans marge ; inverse ;
  scènes très large, très haute et carrée ; dimensions invalides ;
  `visibleWorldRect` (fit, zoom, pan, non mesurée) ; `centerState` ;
  couverture et hystérésis ; rectangle (intérieur, bords, hors scène,
  minimal) ; navigation ; description.
- `engine-minimap.test.mjs` (13) :
  - structure et DOM constant, accessibilité, ordre de tabulation ;
  - politique d'affichage ; rectangle DOM conforme après pan, zoom, fit et
    resize ;
  - clic ; mise à l'échelle CSS ; glisser avec décalage, clic dans le
    rectangle et `pointercancel` ; clavier et focus ; Ctrl + molette ;
  - 100 pans et 100 zooms sans réécriture ; sélection ;
  - deux instances ; `render()` et `destroy()` ; gros témoin.
- Clients Route et Entity : `minimap`, `centerAt` et `gx-minimap` interdits.
- Test de vocabulaire étendu de fait (il couvre tout `graphics/`).

## Tests Python

`tests/test_graphics_minimap.py` (3) :

- module dans la liste fermée ;
- CSS générique et locale (`position: absolute`, jamais `fixed`, `hidden`
  respecté, au plus 40 %, classes `gx-minimap*` seulement) ;
- pas de canvas, de texte ni d'état global.

Mises à jour : liste des modules et nombre de suites (11). Ciblés (assets,
Router Forge, Web Route et Entity, frontière Forge, LOD) : 380 réussis.

## Chromium

Chrome 154 headless (CDP), serveur de test sur 8766, projet témoin.

- Scénario minicarte : **20/20**, Route et Entity : fit masquée ; zoomée
  visible, bornée, dans la zone, sous la barre d'outils ; clic exact (échelle
  et sélection conservées) ; pan principal (rectangle déplacé de −12,6 px
  pour −12,599 attendus) ; zoom (rectangle réduit, structure identique malgré
  le niveau) ; glisser ; clavier ; Ajuster ; zone étroite. Plus deux
  instances et l'absence d'exception.
- Non-régression : semantic zoom **16/16**, viewport FD-GRAPHICS-005
  **29/29** (clavier Tab, Entrée, Espace, Ajuster, +, −, molette, pan,
  resize, sans JavaScript).

## Firefox

Firefox ESR 153 headless (BiDi) : minicarte **20/20** (glissers par actions
de pointeur réelles, Tab et flèches au clavier), semantic zoom **16/16**,
viewport **27/27**, sans JavaScript **2/2**.

## Mutations

Une à la fois, sources restaurées : **13/13 tuées**.

| Sabotage | Résultat | Premier test en échec |
|---|---|---|
| worldToMinimap axe X faux | Tué | `rectangle : suit le pan…` |
| worldToMinimap axe Y faux | Tué | `clic : recentre…` |
| minimapToWorld faux | Tué | `clic : recentre…` |
| rectangle non mis à jour au pan | Tué | `rectangle : suit le pan…` |
| rectangle non redimensionné au zoom | Tué | `rectangle : suit le pan…` |
| clic minicarte change l'échelle | Tué | `clic : recentre…` |
| clic minicarte centre au mauvais point | Tué | `clic : recentre…` |
| minicarte spécifique Route | Tué | `aucune connaissance de Route Explorer ni d'un domaine` |
| minicarte spécifique Entity | Tué | idem |
| état partagé entre deux instances | Tué | `deux instances : minicartes et navigations indépendantes` |
| structure rerendue à chaque pan | Tué | `100 pans et 100 zooms… jamais réécrite` |
| destroy laisse des écouteurs | Tué | `render() recrée une seule minicarte…` |
| minicarte visible inutilement au fit | Tué | `politique : masquée au fit…` |

Deux tests ont été renforcés avant la campagne : le rectangle **dessiné**
(DOM) est comparé au rectangle calculé, et la visibilité d'une instance est
vérifiée à côté d'une autre au fit.

## Provenance DrawCiel

| Élément | DrawCiel | Forge Design | Classification |
|---|---|---|---|
| rendu mini-scène | Canvas 190 × 125, redessin complet à chaque vue | SVG à DOM constant, rendu une fois par `render()` | REWRITE |
| world → mini | Ajustement uniforme centré sur des bornes variables (vue ∪ projet, marge 120) | Même principe d'ajustement uniforme, sur des bornes fixes (la scène), fonctions pures | ADAPT |
| rectangle viewport | `strokeRect(viewportWorld())`, découpé par la mini-scène | `visibleWorldRect`, borné à la minicarte, repère minimal hors scène | ADAPT |
| clic navigation | `minimapNavigate` : px → monde, `centerWorldPoint`, zoom conservé | `minimapToWorld` + `viewport.centerAt`, zoom conservé | ADAPT |
| drag | Recentrage continu sur le pointeur (saut au point pressé) | Décalage de saisie dans le rectangle, recentrage continu ailleurs, seuil de clic | REWRITE (amélioration) |
| couleurs | Fixes (composants bleus, fils gris, textes violets, vue orange) | Variantes génériques `category-1…4`, sans type métier | REWRITE |
| texte | Textes figurés par des rectangles | Aucun texte | NON APPLICABLE |
| état global | `minimap`, `minimapState`, `minimapDrag`, `zoom`, `pan`, `scrollArea`, `workspace` globaux | Aucun : tout appartient à l'instance | Non repris |
| multi-instance | Une minicarte par page | Une par instance, isolées | REWRITE |

Aucune ligne de code DrawCiel n'est copiée. Le commentaire d'en-tête de
`minimap.js` cite la source (commit, fichier, fonctions) des principes
adaptés.

## Limites

- La minicarte zoomée de Route masque environ 6 % de la zone (200 × 106,5
  sur 796 × 478), en haut à droite. Elle est masquée dès que toute la scène
  est visible.
- Gain mesuré modeste sur ce corpus : depuis la vue `normal` centrée, il faut
  3 appuis sur Maj + flèche pour atteindre le bord droit, contre 1 clic.
  Calcul pour un coin opposé : environ 6 appuis horizontaux et 4 verticaux,
  contre 1 clic. Pour Entity zoomé, la largeur est déjà entière.
- Pas de marqueur de sélection, ni d'aperçu des niveaux de détail : choix de
  V1.
- Sans JavaScript, pas de minicarte (accepté).
- Hors périmètre : le test instable `test_runtime_detects_dead_proxy`
  (Real Preview) existait avant ce ticket.

## Roadmap

FD-GRAPHICS-007 fait. FD-GRAPHICS-008 sera décidé sur l'usage observé.

### Décisions obligatoires

| | Question | Réponse |
|---|---|---|
| A | Canvas ou SVG ? | **SVG** |
| B | Pourquoi ? | DOM constant (chemins regroupés, 7 éléments pour 1 000 × 4 000), rectangle mis à jour en O(1) sans redessin, netteté vectorielle sur toute densité d'écran, testable hors navigateur, accessible ; le canvas de DrawCiel imposerait un redessin complet par pan |
| C | Taille ? | Au plus 200 × 140 px (marge 6 px), proportions de la scène : Route 200 × 106,5, Entity 146,9 × 140 ; au plus 40 % de la largeur de la zone |
| D | Calcul du rectangle ? | `visibleWorldRect` = viewBox (`x, y, largeur/scale, hauteur/scale`), projeté par `worldToMinimap`, borné à la minicarte, repère minimal de 4 px si hors scène |
| E | Le clic conserve-t-il le zoom ? | **Oui** (échelle identique à 10⁻⁹ près, deux navigateurs) |
| F | Drag du rectangle ? | **Inclus** : décalage de saisie dans le rectangle, recentrage continu ailleurs, capture, `pointercancel`, seuil de clic |
| G | Masquée quand toute la scène est visible ? | **Oui**, couverture ≥ 0,995 (affichée sous 0,97, hystérésis) ; jamais pendant un glisser ou sous le focus |
| H | Dépend-elle du semantic zoom ? | **Non** |
| I | Modifie-t-elle GraphicScene ? | **Non** |
| J | Le moteur connaît-il Route ou Entity ? | **Non** |
| K | DrawCiel réellement repris ? | EXTRACT : rien. ADAPT : ajustement uniforme, conversion mini → monde corrigée de l'échelle CSS, recentrage à zoom constant, rectangle de vue. REWRITE : rendu, drag, couleurs, multi-instance, politique d'affichage. NON APPLICABLE : texte figuré, bornes dépendant de la vue, état global |
| L | Améliore-t-elle la navigation à normal et detail ? | **Oui, surtout pour l'orientation.** Tests : un clic atteint n'importe quel point à 1,5 px de minicarte près, à échelle constante, dans les deux navigateurs. Mesure : 1 geste contre 3 appuis pour le bord droit de Route (et environ 10 pour un coin opposé). Inspection : la position de la vue dans la scène se lit d'un coup d'œil et dans le nom accessible. Sur Entity, le gain est faible (scène presque entièrement visible même zoomée) |
| M | Limite réelle restante ? | **Non prédéterminée.** Constats : la largeur du layout Route (6 colonnes de 360) impose toujours la navigation à `normal` ; la minicarte compense sans résoudre. Le routage avancé, les ports, l'édition et un troisième client ne sont pas apparus comme des limites dans ce ticket |

## Fichiers créés

- `forge_design/web/static/graphics/minimap.js`
- `tests/js/graphics/minimap.test.mjs`,
  `tests/js/graphics/engine-minimap.test.mjs`
- `tests/test_graphics_minimap.py`
- `docs/rapports/FD-GRAPHICS-007.md`

## Fichiers modifiés

- `forge_design/web/static/graphics/engine.js` (`.gx-stage`, minicarte de
  l'instance, `centerAt`, `minimap()`), `graphics/viewport.js`
  (`visibleWorldRect`, `centerState`, `centerAt`), `static/shell.css`,
  `web/server.py` (`GRAPHICS_MODULES`), `pyproject.toml`
- `tests/js/graphics/fake-dom.mjs` (`prepend`, scène par `.gx-scene`),
  `engine.test.mjs`, `route-client.test.mjs`, `entity-client.test.mjs`,
  `tests/test_route_graph_script.py`, `tests/test_graphics_forge_boundary.py`
- `docs/graphics/graphics-engine.md`, `docs/graphics/graphics-core-contract.md`,
  `docs/graphics/drawciel-reference.md`, `docs/02-architecture.md`,
  `docs/03-roadmap.md`

## Validation globale finale

| Contrôle | Résultat |
|---|---|
| `python -m compileall -q forge_design` | Réussi |
| `ruff check forge_design tests` | Réussi |
| `ruff format --check .` | 387 fichiers conformes (Markdown compris) |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Réussi |
| `node --check` (8 modules, 2 clients, 13 fichiers de test) | Réussi |
| Suites Node `tests/js/graphics` | 95 réussis |
| Ciblés : assets, Router Forge, Web Route et Entity, frontière Forge, LOD, minicarte | 380 réussis |
| Suite globale `pytest` (hors du dépôt, `--basetemp` court sous `tmp/`) | **4622 réussis**, relancée après insertion de ces résultats |
| `python -m pip check` | Aucune dépendance cassée |
| Chromium 154 | minicarte 20/20, semantic zoom 16/16, viewport 29/29 |
| Firefox 153 | minicarte 20/20, semantic zoom 16/16, viewport 27/27, sans JavaScript 2/2 |
| Wheel installée isolément | `minimap.js` packagé et servi (`text/javascript; charset=utf-8`), module hors liste 404, CSS servie |
| MkDocs | N/A : aucune configuration MkDocs dans Forge Design |

## État Git final

Commit unique `feat: ajouter la minicarte au Graphic Core (FD-GRAPHICS-007)`,
au-dessus de `3221814`. `docs/rapports/FD-CONTRACT-001.md` reste modifié
localement, hors commit. Aucun push.
