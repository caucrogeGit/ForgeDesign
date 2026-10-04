# Moteur graphique — API JavaScript

Statut : **implémenté** (FD-GRAPHICS-002), première tranche verticale du
[Graphic Core](graphics-core-contract.md). Ce document décrit l'API réelle ;
le contrat reste la référence normative des frontières.

## Modules

ES modules natifs, sans build, sans npm, sans dépendance ni CDN, livrés dans
`forge_design/web/static/graphics/` et servis par des routes fixes
(`/graphics/<module>.js`, `text/javascript; charset=utf-8`, liste fermée).

| Module | Rôle |
|---|---|
| `geometry.js` | `point`, `rect`, `rectCenter`, `arrowHead`, `formatPoints`, `isFiniteNumber`, `MAX_COORDINATE` |
| `model.js` | `validateScene`, `GraphicSceneError`, limites, présentations autorisées |
| `scene.js` | `indexScene`, `neighbourhood`, `createSelection` (sans DOM) |
| `svg-renderer.js` | `renderScene`, `applySelection`, `applyDetailLevel` (renderer remplaçable) |
| `detail-level.js` | Niveau de détail pur (FD-GRAPHICS-006) : `detailLevelForScale`, `DETAIL_LEVELS`, `THRESHOLDS`, tailles écran de référence |
| `viewport.js` | Viewport pur (FD-GRAPHICS-004) : `createViewport`, `fitState`, `zoomAtState`, `panState`, `resizeState`, `viewBox`, `wheelFactor`, bornes ; `visibleWorldRect`, `centerState` (FD-GRAPHICS-007) |
| `minimap.js` | Minicarte (FD-GRAPHICS-007) : `minimapLayout`, `worldToMinimap`, `minimapToWorld`, `sceneCoverage`, `needsMinimap`, `minimapViewportRect`, `describeVisible` (purs) et `renderMinimap` (vue SVG) |
| `engine.js` | `createGraphicEngine` (instance, barre d'outils, interactions, cycle de vie) |

Aucun module ne connaît un domaine, Route Explorer, un projet Forge ou un
stockage ; aucun état global (pas de singleton, pas de variable de module
mutable).

## GraphicScene

Objet JSON transmis au moteur, **non persistant** :

```json
{
  "width": 400, "height": 120,
  "title": "Témoin", "description": "Trois nœuds, deux arêtes.",
  "nodes": [ { "id": "A", "label": "Node A", "rect": {"x": 0, "y": 10, "width": 80, "height": 40} } ],
  "edges": [ { "id": "A-B", "source": "A", "target": "B", "points": [{"x": 80, "y": 30}, {"x": 120, "y": 30}] } ]
}
```

`width`, `height` : nombres finis dans `]0, 10⁶]` ; `title`, `description`
facultatifs (accessibilité).

## Node

| Champ | Contrat |
|---|---|
| `id` | Chaîne non vide, opaque, unique ; jamais interprétée |
| `kind` | Facultatif, `"node"` seul en V1 (groupes futurs) |
| `label` | Libellé complet, accessible (`aria-label`, `<title>`), toujours texte |
| `rect` | `{x, y, width, height}`, dimensions strictement positives |
| `lines` | Facultatif, au plus 4 lignes affichées (≤ 256 caractères), texte |
| `levels` | Facultatif (FD-GRAPHICS-006) : `{"overview": [indices], "normal": [indices]}`, indices de `lines` strictement croissants, `overview ⊆ normal` ; `detail` montre toujours toutes les lignes. Absent : toutes les lignes à tous les niveaux |
| `presentation` | `variant` ∈ `default`, `category-1`…`category-6` ; `tone` ∈ `default`, `warning`, `muted` |
| `data` | Facultatif, ≤ 16 paires `clé-kebab → chaîne` ; opaque, jamais rendu ni interprété, restitué par `node(id)` |

## Edge

| Champ | Contrat |
|---|---|
| `id` | Unique, opaque |
| `source`, `target` | Identités de nœuds **existants** (sinon scène refusée) ; boucle permise |
| `points` | Polyligne fournie, 2 à 64 points ; le renderer ne route pas |
| `label`, `labelAt` | Facultatifs ; texte et position |
| `presentation` | `line` ∈ `solid`, `dashed` ; `arrow` ∈ `none`, `end` ; `tone` |
| `data` | Facultatif (FD-GRAPHICS-003), mêmes règles que pour un nœud ; opaque, restitué par `edge(id)` |

Plusieurs arêtes entre deux mêmes nœuds (arêtes parallèles) sont admises et
conservées : identités distinctes, toutes incidentes, voisin compté une fois.

## Validation

`validateScene(input)` traite la scène comme un contenu non fiable : objets
simples seulement, clés inconnues refusées à tous les niveaux, types
primitifs, nombres finis, identités uniques, références d'arêtes résolues,
limites. Elle renvoie une **copie gelée** ; l'entrée n'est jamais conservée.
Toute violation lève `GraphicSceneError` avec un chemin (`edges[2].target :
nœud inexistant`). Une scène invalide n'est jamais rendue.

## Geometry

Primitives pures `{x, y}` et `{x, y, width, height}`, `Number.isFinite`,
`|v| ≤ 10⁶`, NaN et Infinity refusés. Pas de transformation en V1 (aucune
rotation nécessaire).

## Renderer

`renderScene(container, scene)` crée un `<svg class="gx-scene">` dans le
conteneur fourni : `createElementNS`, `setAttribute` sur des attributs fixes
ou numériques, `textContent` pour tout texte. Aucun balisage injecté, aucun
style en ligne (CSP `style-src 'self'`), aucune référence d'identifiant
partagée (les flèches sont des polygones calculés, pas des marqueurs `id`).
Apparence par classes `gx-*` définies dans `shell.css`. Complexité O(V + E).

## Selection

Sélection **simple**, runtime seulement : `select(id)` (identité inconnue :
`GraphicSceneError`, état inchangé), `clearSelection()`. L'état expose
`nodeId`, `edgeIds` (arêtes incidentes) et `neighbourIds` (voisins directs),
calculés en O(degré) par un index d'incidence construit en O(V + E). Aucune
analyse transitive. Rendu : classes `gx-selected`, `gx-related`,
`aria-pressed`.

Interaction : clic, Entrée, Espace (bascule), Échap (efface et rend le focus
au nœud).

## Viewport

État runtime de l'instance `{ scale, x, y }` : `(x, y)` est le point monde au
coin supérieur gauche de la zone, `scale` le nombre de pixels écran par unité
monde. Seule autorité d'affichage : l'attribut `viewBox` du SVG
(`x y largeur/scale hauteur/scale`), le SVG occupant toute la zone par CSS
(`.gx-viewport`, 30 rem de haut, redimensionnable verticalement). La scène
n'est jamais modifiée ; rien n'est persisté (ni stockage navigateur, ni cookie).

| Élément | Règle |
|---|---|
| Fit | Scène entière, centrée, marge écran de 16 px, jamais agrandie au-delà de 100 % |
| Home | = fit |
| Zoom | Pas symétrique 1,25 ; boutons autour du centre ; bornes 0,02 à 4 |
| Zoom au point | Le point monde sous le point écran y reste (formule DrawCiel adaptée) |
| Molette | Seule : défilement normal de la page ; Ctrl/Cmd + molette (et pincement) : zoom sous le pointeur, un pas au plus par événement |
| Pan | Glisser au bouton principal sur le fond (jamais sur un nœud), ou bouton du milieu ; Pointer Events et capture ; Maj + flèches (15 % de la zone) |
| Resize | Avant toute interaction (ou après Ajuster) : le fit suit la zone ; ensuite échelle et centre visibles conservés. `ResizeObserver` si disponible, sinon taille initiale ; `engine.resize()` pour remesurer |
| Zone non mesurée | État neutre et viewBox de la scène : jamais NaN ni Infinity |
| Barre d'outils | `role="toolbar"`, boutons natifs « Ajuster », « + », « − » (titre et nom accessible), échelle courante en texte |
| Recentrage | `centerAt(point)` (FD-GRAPHICS-007) : le point monde au centre de la zone, échelle conservée |

## Detail levels (semantic zoom)

FD-GRAPHICS-006. **Le moteur décide quand changer de niveau ; le client décide
quoi montrer.** Trois niveaux génériques de densité de présentation,
`overview`, `normal`, `detail`, dérivés de la seule échelle réelle du viewport
(`viewport.scale`, quelle que soit son origine : fit, boutons, molette,
resize). Le pan ne change pas l'échelle, donc jamais le niveau.

| Seuil | Échelle | Texte de 12 → écran |
|---|---:|---:|
| overview → normal (entrée) | 7/12 ≈ 0,583 | 7 px |
| normal → overview (sortie) | 6,5/12 ≈ 0,542 | 6,5 px |
| normal → detail (entrée) | 9/12 = 0,75 | 9 px |
| detail → normal (sortie) | 8,5/12 ≈ 0,708 | 8,5 px |

Tailles mesurées sur un rendu réel (Chromium, DPR 1) : c'est une lisibilité
mesurée, pas un critère d'accessibilité. Hystérésis de 0,5 px écran, pour
qu'un pincement oscillant autour d'un seuil ne fasse pas clignoter le texte.
L'historique ne commence qu'avec une zone mesurée. Les seuils sont des
constantes du moteur : ni dans la scène, ni configurables par client en V1.

| Élément | overview | normal | detail |
|---|---|---|---|
| Géométrie des nœuds | identique | identique | identique |
| Lignes de nœud | `levels.overview` | `levels.normal` | toutes |
| Arêtes | toutes | toutes | toutes |
| Libellés d'arêtes | masqués | visibles | visibles |
| Catégories (`category-1…4`) | teintes renforcées | teintes normales | teintes normales |
| `aria-label`, `<title>`, sélection, focus | inchangés | inchangés | inchangés |

Rendu : toutes les lignes sont créées une seule fois, à leur position, avec
des classes `gx-at-<niveau>`. Une transition ne fait que changer la classe
`gx-detail-<niveau>` et l'attribut `data-detail-level` du SVG racine (O(1)) ;
la CSS masque le reste. Aucun élément n'est recréé, et rien n'est touché tant
que le niveau ne change pas. `engine.detailLevel()` lit le niveau courant ; il
n'existe pas de `setDetailLevel`.

## Minimap

FD-GRAPHICS-007. **Une seule scène, un seul viewport, une minicarte dérivée.**
La minicarte est une projection runtime simplifiée de la `GraphicScene` : elle
n'a ni topologie, ni document, ni état métier ; elle ne connaît que `node.rect`,
`node.presentation.variant`, `edge.points`, `scene.width`, `scene.height` et
l'état du viewport.

| Élément | Règle |
|---|---|
| Rendu | SVG à DOM constant : fond, **un** chemin pour toutes les arêtes (polylignes sans flèche), **un** chemin par variante de nœuds, un rectangle de zone visible. Aucun texte, aucun libellé, aucun nœud focalisable |
| Dimensions | Ajustement uniforme de la scène dans 200 × 140 px au plus, marge interne de 6 px, proportions de la scène (Route 200 × 106,5 ; Entity 146,9 × 140) ; en CSS, au plus 40 % de la largeur de la zone (réduite, conversion inchangée) |
| Position | Coin supérieur droit de la scène (`.gx-stage`, position relative ; minicarte absolue, jamais `fixed`), hors de la zone de pan, sans couvrir la poignée de redimensionnement |
| Conversions | `worldToMinimap(p) = marge + p × s`, `minimapToWorld` inverse ; client → minicarte en tenant compte de la mise à l'échelle CSS |
| Zone visible | `visibleWorldRect` = viewBox courant ; affichée bornée à la minicarte, avec un repère minimal de 4 px au bord si la vue sort de la scène |
| Affichage | Seulement quand toute la scène n'est pas visible : couverture `min(part de largeur, part de hauteur)` ; apparaît sous 0,97, disparaît à partir de 0,995 (hystérésis). Jamais masquée pendant un glisser ni lorsqu'elle a le focus. Indépendante du niveau de détail |
| Clic | Recentre la vue sur le point monde pointé ; échelle conservée |
| Glisser | Depuis le rectangle : il suit le pointeur en gardant le décalage de saisie ; ailleurs : recentrage continu. Pointer Events et capture, `pointercancel` |
| Clavier | Focalisable (`role="group"`, nom accessible décrivant la zone visible, juste après la barre d'outils) ; flèches seules : même pas que Maj + flèches dans la zone ; Ctrl/Cmd + molette dessus : zoom de la vue, jamais celui de la page |
| Mise à jour | Structure rendue une fois (O(V + E)) ; à chaque navigation, seuls le rectangle et le nom accessible changent (O(1)) |

## Instance lifecycle

```js
const engine = createGraphicEngine(container, scene, { onSelectionChange(state) {} });
engine.select(id); engine.clearSelection(); engine.focus(id);
engine.selection(); engine.node(id); engine.edge(id); engine.scene();
engine.fit(); engine.home(); engine.zoomIn(); engine.zoomOut();
engine.zoomAt({x, y}, factor); engine.panBy(dx, dy); engine.resize(); engine.viewport();
engine.detailLevel();   // "overview" | "normal" | "detail", dérivé de l'échelle
engine.centerAt({x, y}); engine.minimap();   // recentrage ; inspection de la minicarte
engine.render();   // re-rendu, écouteurs précédents retirés
engine.destroy();  // retire SVG, écouteurs (AbortController) et état
```

Chaque instance possède sa scène, son index, sa sélection, son rendu et ses
écouteurs : deux instances sont indépendantes. Après `destroy()`, toute
opération lève une erreur.

## Clients

| Client | Adaptateur serveur (pur) | Client navigateur |
|---|---|---|
| Route Explorer (FD-GRAPHICS-002) | `web/route_graph_scene.py` | `/route-graph.js` |
| Entity Explorer (FD-GRAPHICS-003) | `web/entity_graph_scene.py` | `/entity-graph.js` |
| Debug Center (FD-GRAPHICS-008) | `web/debug_flow_scene.py` | `/debug-flow.js` |

Sérialisation commune : `web/graphics.py` (`scene_json_payload`). Chaque client
garde son vocabulaire, ses données opaques et, s'il en a besoin, son panneau de
détails (Debug n'en a pas : un statut accessible annonce l'étape sélectionnée).

| Capacité | Route | Entity | Debug |
|---|---|---|---|
| Type de graphe | structure | structure (avec retours) | flux séquentiel |
| Layout (Python, client) | multi-colonnes | deux colonnes | une ligne |
| Couloirs partagés | oui | oui | non (arêtes droites) |
| Viewport, semantic zoom, minicarte | oui | oui | oui |
| Libellés d'arêtes | oui | oui (nom de relation) | non |
| Données opaques | oui | oui | aucune |
| Panneau spécifique | oui | oui | non (statut) |
| Source métier | RouteGraph | EntityGraph | DebugFlow |

## Entity Explorer adapter

`build_entity_graphic_scene(layout)` projette `EntityGraphLayout` : identités
de l'`EntityGraph` (`entity:<i>`, `pivot:<i>`, `relation:<i>[:from|:to]`, donc
relations parallèles distinctes), entité → `category-1`, pivot → `category-2`
(nœud ordinaire, distingué par sa ligne « Pivot — n champs »), libellé
accessible « Entité nom » / « Pivot table », données `kind-label`, `name`,
`table`, `field-count`, `field-label` ; arêtes avec `data` `kind` et `name`,
libellé seulement s'il existe. Le client liste les relations directes via
`edge(id)`. Niveaux (FD-GRAPHICS-006) : `overview` sans texte, `normal` le nom
seul, `detail` toutes les lignes.

## Route Explorer adapter

Côté serveur, `forge_design/web/route_graph_scene.py` projette
`RouteGraphLayout` (déjà calculé, sans nouvel appel au Tool ni accès au
projet) en GraphicScene : identités de nœuds du `RouteGraph`, identité
d'arête dérivée de `(source, cible, type)`, `route`/`handler`/`controller`/
`template` → `category-1`…`category-4`, présence absente/refusée/non
vérifiable → `tone: warning` (toujours accompagné du texte de présence), arête
de cycle → `line: dashed` et libellé « (cycle) ». Les libellés métier du
panneau de détails passent par `data`. Niveaux (FD-GRAPHICS-006) :
`overview` sans texte (forme et catégorie), `normal` type et nom, `detail`
toutes les lignes (présence comprise).

Côté navigateur, `/route-graph.js` (module) lit la scène, crée une instance et
masque le repli serveur ; il ne manipule jamais le SVG lui-même.

## Shared lanes (server layouts)

FD-GRAPHICS-005. Les arêtes des deux layouts serveur montent de leur source
vers un couloir horizontal au-dessus des nœuds, le parcourent, puis
redescendent vers leur cible. Les couloirs ne sont plus attribués « une arête,
un couloir » : `forge_design/graphics/lanes.py` (Python pur, partagé par
`route_graph_layout.py` et `entity_graph_layout.py`) les répartit.

| Élément | Règle |
|---|---|
| Parcours | `HorizontalSpan(edge_id, start, end)` : abscisses du segment de couloir (sortie + 20, entrée − 20) ; une arête de retour occupe `[min, max]` |
| Allocation | `allocate_horizontal_lanes` : tri stable (gauche, droite, ordre d'entrée), plus petit couloir libre ; O(E log E) ; nombre de couloirs = chevauchement maximal (minimal) |
| Partage | Deux parcours partagent un couloir seulement s'ils sont séparés d'au moins `gap` = 20 ; deux arêtes parallèles ont toujours deux couloirs |
| Ordonnées | Pas de 24 ; couloir 0 au plus près des nœuds (empilement vers le haut) |
| Haut des nœuds | `band_bottom + 30` : dépend du nombre de couloirs, pas du nombre d'arêtes |
| Géométrie | `route_via_horizontal_lane` (6 points orthogonaux), `svg_path` (repli `M/H/V`), `lane_label_position` (milieu du segment de couloir, 5 au-dessus) |

La GraphicScene, le moteur et les clients JavaScript sont inchangés : seules
les coordonnées produites par les layouts changent. Ce n'est pas le routeur
orthogonal interactif (ports, obstacles, A\*), qui reste à construire.

## Security

- Scène transportée dans un `<script type="application/json"
  data-graphic-scene>` inerte ; `<`, `>`, `&`, U+2028 et U+2029 sont échappés
  en `\uXXXX` : aucun libellé de projet ne peut fermer le bloc. Lecture par
  `textContent` puis `JSON.parse` ; ni `eval`, ni `Function`, ni balisage.
- CSP inchangée : `script-src 'self'`, `style-src 'self'` ; un bloc JSON
  n'est pas exécuté.
- Aucun accès réseau, stockage ou cookie dans le moteur.

## Accessibility

SVG racine `role="group"`, `aria-label` (titre), `<title>`, `<desc>` ; chaque
nœud `role="button"`, `tabindex="0"`, `aria-pressed`, `aria-label` et
`<title>` ; focus visible (`:focus-visible`) ; aucune information portée par
la couleur seule (ton + texte, trait pointillé + libellé « (cycle) »).

## Limits

| Constante | Valeur |
|---|---|
| `MAX_GRAPHIC_NODES` | 5 000 |
| `MAX_GRAPHIC_EDGES` | 20 000 |
| `MAX_GRAPHIC_ID_CHARS` | 8 192 (chemin source 4 096 échappé dans une identité) |
| `MAX_GRAPHIC_LABEL_CHARS` | 8 192 |
| `MAX_GRAPHIC_TEXT_CHARS` | 2 048 (titre, description, libellé d'arête) |
| `MAX_GRAPHIC_LINES` / `MAX_GRAPHIC_LINE_CHARS` | 4 / 256 |
| `MAX_GRAPHIC_EDGE_POINTS` | 64 |
| `MAX_GRAPHIC_DATA_ENTRIES` / `MAX_GRAPHIC_DATA_CHARS` | 16 / 512 |
| `MAX_COORDINATE` | 10⁶ |

Une scène au-delà est refusée ; Route Explorer garde alors son repli statique
et l'annonce.

## Current limitations

Prouvé par deux clients réels : graphes positionnés, nœuds, arêtes (y compris
parallèles), libellés, sélection, voisins directs, SVG, viewport (fit, zoom,
pan, resize), couloirs partagés côté serveur (FD-GRAPHICS-005), niveau de
détail selon l'échelle (FD-GRAPHICS-006), minicarte et recentrage
(FD-GRAPHICS-007). Pas encore : layout générique, ports, routeur orthogonal
interactif (obstacles, A\*, stabilité au déplacement), grille, glisser de
nœuds, édition, commandes, historique, multi-sélection, groupes, niveaux de
détail des arêtes déclarés par le client.
Debug Center est le troisième client depuis FD-GRAPHICS-008.
