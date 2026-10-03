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
| `svg-renderer.js` | `renderScene`, `applySelection` (renderer remplaçable) |
| `engine.js` | `createGraphicEngine` (instance et cycle de vie) |

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

## Instance lifecycle

```js
const engine = createGraphicEngine(container, scene, { onSelectionChange(state) {} });
engine.select(id); engine.clearSelection(); engine.focus(id);
engine.selection(); engine.node(id); engine.edge(id); engine.scene();
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

Sérialisation commune : `web/graphics.py` (`scene_json_payload`). Chaque client
garde son vocabulaire, ses données opaques et son panneau de détails.

## Entity Explorer adapter

`build_entity_graphic_scene(layout)` projette `EntityGraphLayout` : identités
de l'`EntityGraph` (`entity:<i>`, `pivot:<i>`, `relation:<i>[:from|:to]`, donc
relations parallèles distinctes), entité → `category-1`, pivot → `category-2`
(nœud ordinaire, distingué par sa ligne « Pivot — n champs »), libellé
accessible « Entité nom » / « Pivot table », données `kind-label`, `name`,
`table`, `field-count`, `field-label` ; arêtes avec `data` `kind` et `name`,
libellé seulement s'il existe. Le client liste les relations directes via
`edge(id)`.

## Route Explorer adapter

Côté serveur, `forge_design/web/route_graph_scene.py` projette
`RouteGraphLayout` (déjà calculé, sans nouvel appel au Tool ni accès au
projet) en GraphicScene : identités de nœuds du `RouteGraph`, identité
d'arête dérivée de `(source, cible, type)`, `route`/`handler`/`controller`/
`template` → `category-1`…`category-4`, présence absente/refusée/non
vérifiable → `tone: warning` (toujours accompagné du texte de présence), arête
de cycle → `line: dashed` et libellé « (cycle) ». Les libellés métier du
panneau de détails passent par `data`.

Côté navigateur, `/route-graph.js` (module) lit la scène, crée une instance et
masque le repli serveur ; il ne manipule jamais le SVG lui-même.

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
parallèles), libellés, sélection, voisins directs, SVG. Pas encore : layout
générique, ports, routage, grille, zoom/pan, glisser, édition, commandes,
historique, multi-sélection, groupes. Debug Center garde son rendu propre.
