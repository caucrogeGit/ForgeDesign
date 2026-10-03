# Rapport — FD-GRAPHICS-003

API : [Moteur graphique — API JavaScript](../graphics/graphics-engine.md) ;
contrat : [Graphic Core](../graphics/graphics-core-contract.md#deuxième-client-réel--fd-graphics-003).

## Ticket et objectif

Faire d'Entity Explorer le deuxième client réel du Graphic Core pour vérifier
que le moteur de FD-GRAPHICS-002 est générique, et ne l'étendre que si ce second
client démontre un besoin réel et générique.

## État Git initial

```text
$ git log --oneline -1
f9fe502 feat: implémenter le premier noyau graphique avec Route Explorer (FD-GRAPHICS-002)
$ git rev-parse --short origin/main
f9fe502
$ git status --short
 M docs/rapports/FD-CONTRACT-001.md
```

## Référence DrawCiel

`git fetch` : `origin/main` = `aac36b27`, inchangé ; référence figée.

## Delta DrawCiel

Vide. Journal mis à jour ; aucun élément DrawCiel repris, aucun travail
Circuit ni simulation.

## Rappel de la frontière Forge MVC / Graphic Core

Forge MVC produit le HTML et la scène (`Application`, un seul `Router`,
`Request`, `Response`, Jinja, `create_wsgi_app`) ; le Graphic Core, JavaScript
navigateur, la rend. Aucun nouveau serveur, micro-framework, serveur de
fichiers générique ni point d'accès JSON ; aucun backend Node.

## Entity Explorer avant migration

`read_entities → EntitiesResult → filter_entities → build_entity_graph_from_items
→ EntityGraph → layout_entity_graph → SVG serveur interactif` (attributs
`data-node-*`, `role="button"`), plus `entity-graph.js` (sélection par
comparaison d'attributs DOM, panneau, liste des relations directes).

## Pipeline après migration

```text
EntityExplorerTool (un seul appel) → EntitiesResult
  ├── diagnostics, filtres, tableaux (inchangés)
  └── EntityGraph → EntityGraphLayout
        ├── SVG serveur de repli (statique)
        └── build_entity_graphic_scene → scene_json_payload → bloc JSON inerte
              → /entity-graph.js → createGraphicEngine (mêmes modules que Route)
```

Bridge, Tool, diagnostics et filtres non modifiés.

## Adaptateur Entity → GraphicScene

`forge_design/web/entity_graph_scene.py`, `build_entity_graphic_scene(layout)` :
pur (aucun fichier, Tool, `Request` ni `Response` ; test interdisant tout accès
disque pendant l'appel), déterministe (même entrée ⇒ même dict ⇒ même JSON).

## Identités

Nœuds : identités de l'`EntityGraph` reprises (`entity:<i>`, `pivot:<i>`).
Arêtes : identités logiques existantes (`relation:<i>`, `relation:<i>:from`,
`relation:<i>:to`), qui portent l'indice de la déclaration. Aucun identifiant
aléatoire ni second système.

## Nœuds

Libellé accessible « Entité nom » ; lignes « Entité — n champs », nom, table
(raccourcis par le layout) ; `data` bornée : `kind-label`, `name`, `table`,
`field-count`, `field-label`. Pas de sérialisation complète d'`EntityInfo`.

## Pivots

Nœuds ordinaires pour le moteur : `category-2`, libellé « Pivot table »,
ligne « Pivot — n champs », `field-label` « Champs supplémentaires ». La
distinction est textuelle (et la variante) ; le contour pointillé du SVG
serveur n'est pas reproduit, aucune forme propre au pivot n'entre dans le
moteur.

## Arêtes

Points exacts du layout (`PositionedEntityEdge.points`, chemin SVG du repli
dérivé des mêmes valeurs, testé) ; flèche ; `label`/`labelAt` seulement si la
relation a un nom affiché ; `data` `kind` et `name` complets pour le panneau.

## Relations parallèles

Deux `many_to_one` de `Comment` vers `Article` (`article`, `parent`) : deux
arêtes, deux identités, deux tracés, toutes deux incidentes, `Article` compté
une fois comme voisin. **Le moteur les gérait déjà** (aucune fusion par paire
source/cible) ; tests génériques ajoutés (A ⇢ B deux fois, plus B → A).

## Présentations génériques

entité → `category-1`, pivot → `category-2` ; aucune variante ni classe
Entity dans le moteur ou le renderer ; `category-6` reste le plafond.

## Transport JSON

Même mécanisme que Route Explorer ; `scene_json_payload` **extraite** dans
`forge_design/web/graphics.py` (échappement `<`, `>`, `&`, U+2028, U+2029),
utilisée par les deux clients ; les mappings restent dans leurs adaptateurs.

## Moteur partagé

`/entity-graph.js` importe `./graphics/engine.js` comme `/route-graph.js` ;
aucune copie du moteur, aucune nouvelle route d'asset Graphics.

## Sélection

Celle du moteur : clic, Entrée, Espace, Échap ; incidence directe ; pivot sans
cas particulier.

## Panneau Entity

Local au client : type, nom, table, champs (libellé selon le type), nombre et
liste des relations directes (« source → relation → cible », texte via
`textContent`), bouton Désélectionner rendant le focus, statut `role="status"`
`aria-live="polite"`.

## Accessibilité

Celle du moteur (`role="button"`, `tabindex`, `aria-pressed`, `aria-label`,
focus visible) ; information jamais portée par la couleur seule (type écrit
dans le libellé et la première ligne).

## Fallback sans JavaScript

SVG serveur conservé, lisible, sans `tabindex`, `role="button"`,
`aria-pressed` ni identités ; `role="img"` ; livré visible (testé) ; masqué
seulement quand le moteur démarre ; message d'état explicite. Scène refusée :
repli conservé et message sobre (testé dans Node).

## Sécurité

Noms d'entité, de table, de champ et de relation hostiles rendus comme texte
(Node, Chromium, Firefox) ; aucune exécution.

## CSP

Inchangée (`script-src 'self'`, `style-src 'self'`, sans `unsafe-inline`) ;
`X-Content-Type-Options: nosniff` présent ; aucun script en ligne exécutable,
aucune donnée massive en attribut, aucun `fetch` produit.

## Utilisation de Forge MVC

Entity Explorer Web est toujours rendu par l'application Forge MVC :
`render_page` et `Router`. `create_application()` reste l'unique composition
HTTP (test : un seul `Router()` dans le paquet, dans `web/server.py`, et
`create_wsgi_app(application)` ; aucun `http.server` dans `web/` — le proxy de
preview réelle, hors de `web/`, est l'exception documentée de FD-REALPREVIEW).

## Absence de logique Entity dans Graphics

Test de vocabulaire étendu (mots entiers) : `route`, `handler`, `controller`,
`template`, `entity`, `relation`, `pivot`, `many_to_one`, `many_to_many`,
`table`, `field`, `circuit`, `resistor`, `network` absents des cinq modules.

## Comparaison Route / Entity

| Besoin | Route Explorer | Entity Explorer | Graphic Core |
|---|---|---|---|
| node | route, handler, contrôleur, template | entité, pivot | `Node` : rect, lignes, présentation, `data` |
| edge | handles, defined-in, renders, includes… | many_to_one, many_to_many (deux demi-arêtes via pivot) | `Edge` : points, flèche, ligne |
| label | type de relation, « (cycle) » | nom de relation (si présent) | `label`, `labelAt` |
| parallel edge | impossible (identité source-cible-type) | oui (relations distinctes) | conservées, identités distinctes |
| selection | simple | simple | `select`, `clearSelection`, clavier |
| neighbourhood | voisins directs | voisins directs, relations listées | `edgeIds`, `neighbourIds` en O(degré) |
| layout | Python, 5 colonnes, couloir par arête | Python, 2 colonnes, couloir par arête | aucun (scène positionnée) |
| business data | type, présence | type, nom, table, champs ; type et nom de relation | `data` opaque (nœuds, arêtes) |
| details panel | type, nom, présence | type, nom, table, champs, relations | aucun (client) |

Les deux layouts produisent la même géométrie d'arête : polyligne
orthogonale à six points via un couloir horizontal propre à chaque arête au
sommet, libellé au milieu du couloir, raccourci des libellés à 30 caractères,
emprise calculée sur les nœuds. Primitives communes futures identifiées, **non
extraites** : placement en colonnes, routage « par couloir », raccourci de
libellé, calcul d'emprise.

## Extensions du moteur nécessaires

Une seule, générique : `data` opaque sur les arêtes (mêmes bornes que les
nœuds) et `engine.edge(id)`. Besoin Entity : décrire les relations incidentes
dans le panneau ; besoin générique : tout panneau listant les arêtes d'une
sélection.

## Extensions refusées

- Module JS de transport (`readSceneScript`) : le partage réel est une ligne
  (`JSON.parse(script.textContent)`) ; montage et panneaux restent propres à
  chaque client.
- Forme ou variante propre au pivot dans le moteur.
- Nouvelle catégorie ou classe `gx-entity`.
- Fusion des layouts Python.
- Zoom/pan.

## Tests Python

`tests/test_entity_graph_scene.py` (nouveau, 8) : entité simple, identités,
pivot ordinaire, relations parallèles et identités d'arêtes, points ↔ chemin,
Unicode et texte hostile, déterminisme, aucun accès disque.
`tests/test_graphics_forge_boundary.py` (nouveau, 3) : composition Forge
unique, assets Graphics en routes fixes, aucun double serveur du moteur.
Mis à jour au nouveau contrat : `test_web_entity_graph.py`,
`test_web_entity_filters.py`, `test_web_entity_diagnostics.py`,
`test_web_entity_graph_interaction.py` (scène JSON, repli statique visible,
script module, CSP), `test_web_inspector.py` (repli Route livré visible),
`test_route_graph_scene.py` (sérialiseur partagé), `test_route_graph_script.py`
(cinq suites, `node --check` d'`entity-graph.js`). Supprimé :
`tests/js/entity_graph_dom.cjs` (ancien script).

## Tests Node

29 (22 de FD-GRAPHICS-002 + 7) : arêtes parallèles, `data` d'arête et
`edge(id)`, deux clients de formes différentes simultanés et isolés, client
Entity (montage, relations parallèles listées, pivot au clavier, repli sur
scène refusée ou vide, absence de contournement). Vocabulaire du moteur élargi.

## Tests navigateur

Projet synthétique combinant routes (« rich ») et entités (`Article`, `Tag`,
`Comment`, nom hostile `<script>alert(1)</script>`, deux relations
parallèles, pivot `article_tag`), serveur de test sur 8766 (instance du
porteur sur 8765 intacte).

| Vérification | Chromium 154.0.8037.92 | Firefox 153.4.0 |
|---|---|---|
| Entity : moteur visible, 5 nœuds, 5 arêtes, pivot, libellés | OK | OK |
| Entity : clic, relations parallèles, voisins, panneau | OK | OK |
| Entity : Échap (focus rendu), pivot à Entrée, Espace | OK | OK |
| Entity : nom hostile en texte | OK | OK |
| Deux clients réels simultanés (scène Route montée sur la page Entity) et isolés | OK | OK |
| Route : rendu, clic, voisins, Échap (non-régression) | OK | OK |
| Aucune exécution, erreur ou violation CSP | OK (404 favicon connu) | OK |
| Sans JavaScript : `/entities` et `/routes` | OK (exécution désactivée) | OK (profil `javascript.enabled=false`) |

## Mutations

11 sabotages, tous détectés :

| Sabotage | Détecté par |
|---|---|
| Entity contourne le Graphic Core | client Entity (montage) et contrat statique |
| Logique pivot dans le moteur | test de vocabulaire du moteur |
| Relation parallèle écrasée (clé source>cible) | deux clients simultanés (arêtes parallèles) |
| Collision d'identité d'arête (source->cible) | `test_edges_keep_identities_and_parallel_relations` |
| Libellé hostile injecté (innerHTML) | client Entity (double DOM refusant innerHTML) |
| Sélection partagée entre instances | `deux instances indépendantes` |
| Repli supprimé (livré masqué) | `test_http_interaction_and_asset` |
| Adaptateur relit le projet | `test_projection_never_touches_the_filesystem` |
| Second appel EntityExplorerTool | `test_http_graph` |
| CSP relâchée | `test_http_interaction_and_asset` |
| Arêtes incidentes dédupliquées par voisin | deux clients simultanés |

Le test d'accès disque provoquait d'abord une erreur interne de pytest
(remplacement global de `Path.stat`) : il limite désormais ses remplacements à
l'appel, et le mutant échoue proprement.

## Performance

Projection Python, validation JS, index d'incidence et rendu en O(V + E) ;
voisins en O(degré) ; les arêtes parallèles n'ajoutent qu'une entrée
d'incidence chacune. Aucun benchmark.

## Packaging

Aucun nouveau paquet : modules `web/entity_graph_scene.py` et `web/graphics.py`.
Wheel : `entity-graph.js`, `graphics/*.js`, `entities.html`, adaptateurs
présents ; installée isolément, `/entities` (5 nœuds, 5 arêtes, script
module), `/entity-graph.js`, `/route-graph.js` et les cinq modules servis en
`text/javascript; charset=utf-8`.

## Installation wheel

Voir Packaging : serveur lancé depuis `pip install --target`, aucun accès
réseau externe.

## Limites restantes

Contour pointillé et nom en gras des pivots/entités du SVG serveur non
reproduits (distinction textuelle) ; libellés d'arêtes du layout Entity
raccourcis à 30 caractères (noms complets dans le panneau) ; une valeur de
`data` au-delà de 512 caractères fait refuser la scène (repli statique) ;
segments verticaux partagés par les arêtes d'une même colonne (layout Entity).

## Roadmap

Priorité Graphics conservée ; Circuit inchangé (fonctionnel, non prioritaire,
aucune capacité nouvelle). FD-GRAPHICS-003 marqué fait.

### Décisions obligatoires

| | Question | Réponse |
|---|---|---|
| A | Modification du Graphic Core nécessaire ? | **Oui, une seule** |
| B | Laquelle, pourquoi générique ? | `data` opaque d'arête et `edge(id)` : tout panneau décrivant les arêtes d'une sélection en a besoin ; aucune sémantique Entity |
| C | Arêtes parallèles correctement représentées ? | **Oui**, sans modification (tests génériques et navigateur) |
| D | Pivot totalement opaque pour Graphics ? | **Oui** (nœud ordinaire, test de vocabulaire) |
| E | Mêmes modules moteur pour les deux clients ? | **Oui** |
| F | Adaptateur métier propre à chaque client ? | **Oui** (`route_graph_scene.py`, `entity_graph_scene.py`) |
| G | Serveur exclusivement Forge MVC ? | **Oui** |
| H | Moteur utilisable hors Forge avec une scène générique ? | **Oui** (Node, témoins) |
| I | Zoom/pan déjà nécessaire ? | **Non** : les deux clients restent utilisables par défilement |
| J | Prochaine limitation réellement observée ? | La **taille des scènes** : les deux layouts allouent un couloir par arête au-dessus des nœuds (hauteur ≈ 60 + 24 × arêtes pour Route), si bien que la scène Route du projet synthétique mesure déjà 2120 × 1306 et impose un défilement dans les deux axes, sans vue d'ensemble ; la lisibilité des arêtes (segments verticaux partagés) relève des layouts clients |

**Recommandation pour FD-GRAPHICS-004** : *viewport* (ajustement au
conteneur, zoom et déplacement) plutôt qu'un troisième client : c'est la
contrainte qui grandit avec les projets réels et elle est commune aux deux
clients, alors que Debug Center n'apporterait vraisemblablement pas de besoin
de modèle nouveau (nœuds, arêtes, sélection déjà prouvés). La décision reste au
porteur.

## Fichiers créés

- `forge_design/web/entity_graph_scene.py`, `forge_design/web/graphics.py`
- `tests/test_entity_graph_scene.py`, `tests/test_graphics_forge_boundary.py`,
  `tests/js/graphics/entity-client.test.mjs`
- `docs/rapports/FD-GRAPHICS-003.md`

## Fichiers modifiés

- `forge_design/web/static/graphics/model.js` (`data` d'arête),
  `graphics/engine.js` (`edge(id)`), `static/entity-graph.js` (client),
  `templates/entities.html` (repli, hôte, scène, module), `entities.py`
  (scène), `entity_graph_layout.py` (points), `route_graph_scene.py` et
  `routes.py` (sérialiseur partagé), `static/shell.css`
- `tests/js/graphics/engine.test.mjs`, `selection.test.mjs`, `model.test.mjs`,
  `tests/test_route_graph_script.py`, `tests/test_route_graph_scene.py`,
  `tests/test_web_entity_graph.py`, `tests/test_web_entity_filters.py`,
  `tests/test_web_entity_diagnostics.py`,
  `tests/test_web_entity_graph_interaction.py`, `tests/test_web_inspector.py`
- `docs/graphics/graphics-engine.md`, `docs/graphics/graphics-core-contract.md`,
  `docs/graphics/drawciel-reference.md`, `docs/02-architecture.md`,
  `docs/03-roadmap.md`

Supprimé : `tests/js/entity_graph_dom.cjs`.

## Validation globale finale

| Contrôle | Résultat |
|---|---|
| `python -m compileall -q forge_design` | Réussi |
| `ruff check forge_design tests` | Réussi |
| `ruff format --check .` | 376 fichiers conformes |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Réussi |
| `node --check` (5 modules, `route-graph.js`, `entity-graph.js`, 7 fichiers de test) | Réussi |
| Suites Node `tests/js/graphics` | 29 réussis |
| Route, Web, Entity, Graphics ciblés | 1058 réussis |
| Suite globale `pytest` (hors du dépôt, `--basetemp` sous `tmp/`) | **4544 réussis**, relancée après insertion de ces résultats |
| `python -m pip check` | Aucune dépendance cassée |
| Chromium 154 / Firefox 153, avec et sans JavaScript | Toutes vérifications réussies |
| Wheel installée isolément | `/entities`, `/routes` et assets servis |

## État Git final

Commit unique `feat: migrer Entity Explorer sur le Graphic Core
(FD-GRAPHICS-003)`, au-dessus de `f9fe502`. `docs/rapports/FD-CONTRACT-001.md`
reste modifié localement, hors commit. Aucun push.
