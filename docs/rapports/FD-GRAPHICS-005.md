# Rapport — FD-GRAPHICS-005

API : [Moteur graphique — couloirs partagés](../graphics/graphics-engine.md#shared-lanes-server-layouts) ;
contrat : [Graphic Core](../graphics/graphics-core-contract.md#couloirs-partagés--fd-graphics-005).

## Ticket et objectif

Remplacer la règle « une arête = un couloir » des layouts Route Explorer et
Entity Explorer par une allocation déterministe et partagée de couloirs, qui
laisse des connexions non conflictuelles partager une même voie. Le compactage
géométrique vient d'abord, puis la mesure ; un niveau de détail (LOD) ne sera
envisagé que si la mesure le justifie.

## État Git initial

```text
$ git log --oneline -1
00f9eaa feat: ajouter le viewport au Graphic Core (FD-GRAPHICS-004)
$ git rev-parse --short origin/main
00f9eaa
$ git status --short
 M docs/rapports/FD-CONTRACT-001.md
```

## Référence DrawCiel

Précédente : `3a1753a2`. `git fetch` dans la copie SéquenCiel (lecture seule) :
`origin/main` = **`88f95b75`** (3 octobre 2026, « feat(drawciel): intégrer
Circuit au tunnel de l'activité »), figée pour le ticket. Aucun commit local
non publié. La copie de travail contient des modifications non commitées
(`drawciel_r4`, documentation) : signalées, non examinées, non retenues.

## Delta DrawCiel

`3a1753a2..88f95b75` : un commit, 29 fichiers. ADR-309 (Circuit dans le tunnel
de l'activité) ; mode aperçu en lecture seule dans `drawciel-cadre.js` et
`drawciel-hote.js` ; `tp.js` : un essai d'aperçu n'est plus persisté
localement (`saveLocal`). Classement : **nouveau**, pédagogique et propre à
SéquenCiel. `static/vendor/drawciel/js/app.js`, qui porte le routage, est
**inchangé**. Impact sur le ticket : aucun.

## Routage DrawCiel étudié

Fichier : `static/vendor/drawciel/js/app.js` à `88f95b75` (identique à
`3a1753a2`). Fonctions trouvées et lues : `cleanRoute`, `adaptedRoute`,
`moveWireSegmentStable`, `prepareStableRoutesForMove`, `routeObstructed`,
`astarGrid`, `simplifyExact`.

DrawCiel route **fil par fil** dans un éditeur : il génère des candidats
(droite, un coude, deux coudes), rejette ceux qui traversent un composant
(`routeObstructed`), se replie sur un A\* de grille (`astarGrid`), simplifie
(`simplifyExact`) et stabilise les routes pendant un déplacement
(`moveWireSegmentStable`). Il n'existe **aucune allocation globale de
couloirs** : chaque fil évite des obstacles, il ne partage pas une voie avec
les autres. Le problème de Route et Entity est différent : des nœuds fixes, sans
obstacle sur le trajet (la bande est au-dessus des nœuds), et beaucoup
d'arêtes à empiler. Le ticket n'extrait donc pas le routeur DrawCiel.

Dette **encore vraie** : `routeObstructed` traite à part un type de
composant nommé (`arduino_uno_r3`). Ce cas particulier n'est pas reproduit.

## Problème des layouts existants

```python
# Route                                  # Entity
top = 60 + 24 * len(graph.edges)         top = 60 + 26 * len(graph.edges)
lane = 30 + index * 24                   lane = 30 + index * 26
```

N arêtes donnaient N couloirs, et la bande supérieure grandissait en O(N),
même quand deux arêtes occupaient des abscisses disjointes.

## Mesures avant

Corpus : projet témoin `tmp/gx3-browser` (FD-GRAPHICS-003), sans donnée réelle.
Zone de viewport 796 × 478 (navigateur, 1400 px de large). Fit =
`min((796 − 32) / largeur, (478 − 32) / hauteur, 1)`. Texte = 12 px CSS × fit.
Croisements : intersections propres entre un segment horizontal et un segment
vertical de deux arêtes distinctes (les segments colinéaires partagés et les
extrémités communes ne comptent pas).

| Mesure | Route | Entity |
|---|---:|---:|
| largeur | 2120 | 780 |
| hauteur | 1306 | 750 |
| arêtes | 19 | 5 |
| couloirs | 19 | 5 |
| fit | 0,3415 | 0,5947 |
| texte au fit | 4,10 px | 7,14 px |
| croisements | 14 | 4 |
| libellés superposés | 0 | 0 |

La référence connue (2120 × 1306, fit ≈ 34 %) est reproduite.

## Architecture retenue

```text
                       ┌───────────────────────────────┐
Route layout ─────────►│ forge_design/graphics/lanes.py│
 (colonnes, rangs)     │  allocate_horizontal_lanes    │
Entity layout ────────►│  route_via_horizontal_lane    │
 (colonnes, rangs)     │  lane_label_position, svg_path│
                       └──────────────┬────────────────┘
                                      ↓
              points orthogonaux + path du repli + position du libellé
                                      ↓
                 adaptateurs existants → GraphicScene (inchangée)
```

Chaque layout procède en deux passes : (1) colonnes et rangs, donc les
abscisses ; (2) parcours horizontaux → allocation → haut des nœuds = bande
réellement utilisée → ordonnées, points, chemin et libellé.

| Élément | Layout métier | Routeur partagé | Graphic Core JS |
|---|---|---|---|
| placement des nœuds | oui | non | non |
| choix des extrémités (sortie à droite, entrée à gauche) | oui | non (reçoit `sx, sy, tx, ty`) | non |
| demande de parcours (`HorizontalSpan`) | oui (construit) | type et règles | non |
| allocation des couloirs | non | oui | non |
| ordonnée des couloirs, bas de bande | non | oui (`LanePlan`) | non |
| haut des nœuds | oui (`band_bottom + 30`) | fournit `band_bottom` | non |
| points orthogonaux | entrée | oui | non |
| chemin SVG du repli | non | oui (`svg_path`) | non |
| position du libellé | non | oui | non |
| texte du libellé | oui | non | non |
| rendu SVG interactif | non | non | oui |
| rendu SVG sans JavaScript | oui (Jinja) | non | non |
| viewport | non | non | oui |
| sens métier de l'arête | oui | non | non |

## Emplacement de la primitive partagée

`forge_design/graphics/lanes.py`, nouveau paquet Python déclaré dans
`pyproject.toml`. Ses imports se limitent à `heapq`, `collections`,
`dataclasses` et `types` (test). Elle ne connaît ni `RouteGraph`, ni
`EntityGraph`, ni HTTP, ni Jinja, ni aucun type métier.

Le risque de confusion avec `forge_design/web/static/graphics/` (moteur
navigateur) est traité par la docstring du paquet et par l'architecture. Le
routage est une capacité graphique, pas une responsabilité HTTP, d'où le
paquet plutôt que `forge_design/web/`. Il ne contient que ce module : il n'a
pas été créé pour l'esthétique.

## Modèle d'entrée

- `HorizontalSpan(edge_id, start, end)` : identité opaque et abscisses du
  segment de couloir (sortie + 20, entrée − 20). Une arête de retour
  (`end < start`) occupe `[min, max]`.
- `route_via_horizontal_lane(source, target, lane_y, *, stub=20)` : points
  `sx, sy` et `tx, ty` déjà choisis par le layout.

L'allocation ne reçoit que des abscisses, et non les points complets : les
ordonnées des nœuds dépendent de la hauteur de bande, donc du résultat de
l'allocation. Aucune direction préférée, marge réservée ni port n'est inventé.
Le résultat `LanePlan` porte les indices, le nombre de couloirs, `y(edge_id)`
et `band_bottom`. L'indice de couloir ne sort pas de la primitive : ni
`PositionedEdge`, ni la scène ne l'exposent. Aucun format persistant n'est
créé ; ce sont des structures runtime gelées.

## Algorithme d'allocation

Partition d'intervalles (*interval partitioning*) :

1. tri stable par (gauche, droite, ordre d'entrée) ;
2. un tas des couloirs occupés, indexé par l'abscisse de libération
   (`droite + gap`), et un tas des couloirs libres ;
3. chaque parcours libère les couloirs terminés avant sa gauche, puis prend
   le **plus petit couloir libre**, ou en ouvre un.

Le nombre de couloirs obtenu est égal au chevauchement maximal des intervalles
`[gauche, droite + gap)`. C'est la borne inférieure, donc le minimum pour un
routage par bande supérieure (vérifié contre un calcul brut sur 40 tirages
aléatoires, avec deux valeurs d'écart).

Ordonnées : pas `spacing` = 24 (paramètre avec défaut, commun aux deux
layouts ; les 26 d'Entity n'avaient pas de justification). Le couloir 0 est
**le plus proche des nœuds** et la pile monte. Une première version faisait
l'inverse (couloir 0 en haut) : elle donnait 24 croisements sur Route, plus
qu'avant. L'empilement vers le haut en donne 0 sur Route et 2 sur Entity.
C'est un constat mesuré sur ces corpus, pas une garantie.

## Déterminisme

- Aucun hachage, ensemble ni hasard. Les ex aequo sont départagés par l'ordre
  d'entrée (dix parcours identiques reçoivent les couloirs 0 à 9 dans l'ordre
  donné).
- Choix documenté : **tri stable**, pas l'ordre d'entrée brut, car le tri par
  abscisse est la condition de minimalité. L'ordre d'entrée ne sert qu'à
  trancher.
- Les points, chemins et libellés sérialisés sont identiques octet pour octet
  dans trois processus avec `PYTHONHASHSEED` = 1, 2 et 3 (test, et empreinte
  `ea6936de2c1c04b2` identique sur le corpus réel).
- Stabilité : ajouter une arête ne change que les couloirs des parcours triés
  après elle. Si le nombre de couloirs augmente, toute la bande se décale de
  24 et les nœuds de 24, sans permutation de l'ordre relatif des couloirs
  existants.

## Minimum gap

`gap` = 20 (paramètre avec défaut). Deux parcours partagent un couloir
seulement si `droite_A + 20 ≤ gauche_B`. Des intervalles qui se touchent
(`A` finit à 100, `B` commence à 100) ou qui sont séparés de 19 ont deux
couloirs ; à partir de 20, ils en partagent un (test). Le couloir le plus bas
est à 54 unités au-dessus des nœuds (bande + 30). Les montées et descentes
sont à 20 du bord du nœud. Deux arêtes issues de la même source partagent
leur montée verticale, comme avant le ticket.

## Relations parallèles

Deux arêtes `A → B` ont le même intervalle, qui se chevauche avec lui-même :
elles reçoivent **toujours deux couloirs distincts**, donc deux ordonnées,
deux chemins et deux libellés différents. L'allocateur indexe par `edge_id`
opaque, refuse un identifiant dupliqué (`ValueError`) et ne fusionne jamais
deux connexions.

## Croisements

| Corpus | Avant | Après |
|---|---:|---:|
| Route | 14 | **0** |
| Entity | 4 | 2 |

La compacité n'a pas été sacrifiée : le nombre de couloirs reste minimal, et
seul l'ordre vertical a été choisi sur mesure.

## Labels

Le libellé reste lié à **son** couloir : milieu du segment horizontal, 5
unités au-dessus (`lane_label_position`). Sur un même couloir, les parcours
sont disjoints d'au moins 20, donc les abscisses diffèrent. Sur deux couloirs
différents, les ordonnées diffèrent d'au moins 24. Mesuré : 0 position
identique et 0 boîte de libellé chevauchante (estimation 0,6 em par
caractère ; `getBoundingClientRect` dans Chromium et Firefox). Aucun moteur de
placement de texte n'est construit.

## Route Explorer

`layout_route_graph` : colonnes (niveaux BFS des templates inchangés) →
`HorizontalSpan(str(index), …)` → allocation → `top = band_bottom + 30` →
points, `svg_path`, libellé. La règle `lane = 30 + index * 24` et le
`top = 60 + 24 * len(graph.edges)` sont supprimés. Arêtes de retour présentes
dans le corpus : 1 (inclusion de template en cycle), conservée. Une boucle
(template qui s'inclut lui-même) garde la forme existante : droite, montée,
retour à gauche au-dessus du nœud, descente.

## Entity Explorer

Même transformation (`HorizontalSpan(edge.id, …)`). Les règles
`top = 60 + 26 * len(graph.edges)` et `lane = 30 + index * 26` sont
supprimées. Arêtes de retour dans le corpus : 4 (pivot → entité, entité →
entité). Les boucles (relation réflexive) sont possibles et conservées
(test avec une seule entité).

Avec deux colonnes, **tous** les parcours traversent la gouttière entre les
colonnes (`[20, 320]`, `[320, 460]` et `[20, 760]` se chevauchent ou se
touchent) : aucun partage n'est possible, et le nombre de couloirs reste égal
au nombre d'arêtes. Les tests l'affirment explicitement.

## GraphicScene

Inchangée : aucun nouveau champ. `route_graph_scene.py` et
`entity_graph_scene.py` ne sont pas modifiés. La scène reçoit des `points`
déjà routés.

## Graphic Core JS

**0 modification** dans `forge_design/web/static/` (moteur, clients, CSS). Le
problème était en amont, dans la géométrie produite.

## Viewport

Inchangé. Il bénéficie d'une scène plus compacte : fit Route 34 % → 36 %.

## Forge MVC

Aucune route, aucun endpoint, aucune infrastructure HTTP. `create_application`,
`Router`, `Response`, Jinja et `create_wsgi_app` sont inchangés. Pas de
backend Node ni de paquet npm.

## Fallback sans JavaScript

Le SVG serveur utilise les mêmes `path`, issus de `svg_path(points)`. Dans
Chromium et Firefox, chaque `path` du repli, une fois décodé, est **égal**
aux `points` de la scène (19/19 et 5/5). Sans JavaScript dans Firefox, le
repli s'affiche en `0 0 2120 1066` et `0 0 780 740` : le bénéfice existe avec
et sans JavaScript.

## Mesures après

| Mesure | Route avant | Route après | Évolution | Entity avant | Entity après | Évolution |
|---|---:|---:|---:|---:|---:|---:|
| largeur | 2120 | 2120 | 0 | 780 | 780 | 0 |
| hauteur | 1306 | 1066 | −240 (−18,4 %) | 750 | 740 | −10 (−1,3 %) |
| arêtes | 19 | 19 | 0 | 5 | 5 | 0 |
| couloirs | 19 | 9 | −10 (−52,6 %) | 5 | 5 | 0 |
| fit | 0,3415 | 0,3604 | +5,5 % | 0,5947 | 0,6027 | +1,3 % |
| texte au fit | 4,10 px | 4,32 px | +0,22 px | 7,14 px | 7,23 px | +0,09 px |
| croisements | 14 | 0 | −14 | 4 | 2 | −2 |
| libellés chevauchants | 0 | 0 | 0 | 0 | 0 | 0 |

Valeurs identiques dans les deux navigateurs : fit Route `0.360377…` (36 %),
Entity `0.602702…` (60 %).

## Gain Route

19 → 9 couloirs, et la hauteur passe de 1306 à 1066. Le fit est désormais
**limité par la largeur** : 764 / 2120 = 0,3604, alors que 446 / 1066 =
0,418. Aucune compaction verticale supplémentaire ne peut augmenter le fit.
Le 9 est le chevauchement maximal : les 5 arêtes `route → handler`
convergent dans la même gouttière et ne peuvent pas partager de couloir.

## Gain Entity

Aucun couloir économisé : c'est géométriquement impossible à deux colonnes
(voir Entity Explorer). Les −10 unités de hauteur viennent seulement de
l'espacement commun (26 → 24).

## Tests unitaires

`tests/test_graphics_lanes.py` (49 tests, géométrie pure, sans projet ni
graphe) : vide, une arête, 500 parcours disjoints → 1 couloir. Témoin de
**8 arêtes → 2 couloirs**. Contacts et écart (100/100, 19, 20). Imbrication
`[0, 1000] ⊃ [100, 200], [300, 400]` → 2 couloirs. Parallèles (5 → 5).
Arêtes de retour. 40 tirages aléatoires contre la borne brute, avec deux
écarts. Ex aequo dans l'ordre d'entrée. Empilement. Entrées invalides et plan
non mutable. Points, `svg_path` et libellé (cas direct et boucle). Pureté des
imports.

## Tests layout

`tests/test_graph_layout_lanes.py` (10 tests) :

- Route, 8 arêtes → 2 couloirs, haut = `30 + 2 × 24 + 30`, topologie et
  identités inchangées ;
- parallèles Route : 3 couloirs, 3 chemins ;
- Entity, avec cycles, parallèles et pivots : couloirs = arêtes, haut =
  bande ;
- `path` = forme SVG des `points` ;
- invariants communs : 6 points orthogonaux, libellé au milieu de son
  couloir, aucun couloir partagé sans écart, pas de 24 ;
- **test statique** : les deux layouts importent et appellent les quatre
  fonctions partagées, sans multiplication par `index` ni par `graph.edges`
  et sans chemin SVG fabriqué localement. Une seule définition de l'allocateur
  dans `forge_design/`, et aucun autre module n'associe `heapq` et couloirs ;
- octet pour octet entre processus et graines de hachage.

Les tests de layout existants (`test_route_graph_layout.py`,
`test_entity_graph_layout.py`) passent **sans modification**. Ils
vérifiaient des bornes, des non-chevauchements, des colonnes et des chemins
distincts, jamais la règle « une arête = un couloir », qui n'était donc pas
figée par un instantané. Les attentes nouvelles sont écrites explicitement.

## Tests Node

`node --check` réussi sur les 6 modules, les 2 clients et les 9 fichiers de
test. Les 51 tests `tests/js/graphics` sont verts, sans modification.

## Chromium

Chrome 154 headless (CDP), serveur de test sur 8766, scénario FD-GRAPHICS-004
rejoué et complété par des contrôles de compaction : **29/29**.

- Route et Entity : taille, nombre d'arêtes et de couloirs attendus
  (9 et 5), haut des nœuds = bande, pas de 24 ;
- repli égal aux points, 0 libellé chevauchant ;
- fit, zoom au clavier, molette seule = défilement, Ctrl + molette sous le
  pointeur ;
- sélection après zoom (voisins exacts), pan au glisser et au clavier,
  Échap ;
- resize avant et après interaction, deux viewports indépendants ;
- aucune erreur ni violation CSP, aucun stockage, rendu sans JavaScript.

Captures inspectées : 9 couloirs empilés, sans croisement. La barre de
défilement horizontale de la page existait déjà en FD-GRAPHICS-004.

## Firefox

Firefox ESR 153 headless (BiDi) : **27/27**, mêmes contrôles (activation des
boutons par clics réels, limite BiDi déjà documentée), plus **2/2** sans
JavaScript (profil `javascript.enabled = false`) : repli visible, compact,
tableaux disponibles.

## Mutations

Une mutation à la fois, `__pycache__` purgé, `PYTHONDONTWRITEBYTECODE=1`,
sources restaurées après chaque essai : **11/11 tuées**.

| Sabotage | Résultat | Premier test en échec |
|---|---|---|
| 1 arête = 1 couloir restauré | Tué | `test_empty_one_and_many` |
| chevauchement permis dans un couloir | Tué | `test_eight_edges_two_lanes_witness` |
| écart minimal ignoré | Tué | `test_touching_gap_and_nesting` |
| arêtes parallèles fusionnées | Tué | `test_eight_edges_two_lanes_witness` |
| parallèles superposées (même ordonnée) | Tué | `test_parallel_and_backward_spans` |
| identité d'arête perdue (Route) | Tué | `test_route_eight_edges_share_two_lanes` |
| `top` dépend du nombre d'arêtes | Tué | `test_route_eight_edges_share_two_lanes` |
| Route sans l'allocateur | Tué | `test_route_eight_edges_share_two_lanes` |
| Entity sans l'allocateur | Tué | `test_layouts_use_the_shared_primitive[entity]` (statique) |
| ordre non déterministe (départage par `hash`) | Tué | `test_deterministic_and_independent_of_input_object_identity` |
| libellé sur le mauvais couloir | Tué | `test_route_label_and_path` |

La mutation « Entity sans l'allocateur » n'est tuée que par le test
statique, ce qui est attendu : à deux colonnes, une allocation par indice
produit le même nombre de couloirs. C'est exactement le rôle de ce test.

## Performance

- Allocation : O(E log E), soit un tri et des opérations de tas, avec
  L ≤ E couloirs. Mémoire O(E). Pas de récursion.
- Layouts : O(V + E log E) ; l'allocation est appelée une seule fois.
- Mesuré : E = 1 000 aléatoires en 1,4 ms (507 couloirs) ; E = 20 000
  aléatoires en 40 ms (10 155 couloirs) ; 20 000 parcours disjoints en
  16,5 ms (1 couloir).
- Aucun coût côté navigateur : la scène a la même structure.

## Provenance DrawCiel

| Idée | Source | Commit | Fonction / zone | Classification | Raison |
|---|---|---|---|---|---|
| Segments seulement horizontaux et verticaux, sans segment nul ni point colinéaire | SéquenCiel, `app.js` | `88f95b75` | `simplifyExact`, `cleanRoute` | Principe repris | Les polylignes à 6 points satisfont cette propriété par construction ; aucune simplification nécessaire |
| Premier segment dans la direction de sortie | `app.js` | `88f95b75` | `cleanRoute` (`outward`) | Principe repris | Sortie horizontale de 20 avant la montée |
| Candidats, rejet des obstacles, A\* de grille | `app.js` | `88f95b75` | `cleanRoute`, `routeObstructed`, `astarGrid` | Non applicable | Pas d'obstacle sur le trajet : la bande est au-dessus des nœuds |
| Stabilité pendant un déplacement | `app.js` | `88f95b75` | `moveWireSegmentStable`, `prepareStableRoutesForMove`, `adaptedRoute` | Non applicable | Nœuds fixes, pas de glisser |
| Partition d'intervalles | Algorithme classique | — | — | REWRITE (original) | Absent de DrawCiel |

Aucun code DrawCiel n'est copié, adapté ni translittéré.

## Limites

- Ce n'est **pas le routeur orthogonal interactif** : pas d'évitement
  d'obstacles quelconques, de reroutage après glisser, de ports, de grille
  ni d'A\*. Le routage par couloirs statiques reste distinct du routage
  interactif de DrawCiel ; les deux devront converger dans `OrthogonalRouter`
  (contrat Graphics, section Routage).
- Les arêtes issues d'une même source partagent leur montée verticale
  (comportement antérieur).
- Entity n'a aucun gain à deux colonnes.
- Le fit Route est maintenant limité par la largeur (6 colonnes de 360) : le
  texte au fit reste à 4,3 px, illisible.
- Le choix de l'empilement vers le haut est validé sur deux corpus, pas
  démontré en général.
- Hors périmètre : `test_runtime_detects_dead_proxy` (Real Preview) est
  instable depuis avant ce ticket.

## Roadmap

FD-GRAPHICS-005 fait. FD-GRAPHICS-006 sera décidé sur l'usage observé.

### Décisions obligatoires

| | Question | Réponse |
|---|---|---|
| A | Générique ou seulement commune ? | **Générique pour ce qu'elle fait** : identités opaques, abscisses et points, aucun type métier, aucun graphe. Mais elle ne couvre qu'**un** style (bande de couloirs horizontaux au-dessus de nœuds, sortie à droite, entrée à gauche) : elle n'est pas un routeur général. Aujourd'hui, elle est commune à Route et Entity |
| B | Emplacement ? | `forge_design/graphics/lanes.py` : capacité graphique, pas HTTP ; paquet distinct du moteur navigateur `web/static/graphics/`, documenté |
| C | Algorithme ? | Partition d'intervalles : tri stable (gauche, droite, ordre d'entrée), plus petit couloir libre, libération à `droite + gap` ; couloir 0 au plus près des nœuds |
| D | Complexité ? | O(E log E) en temps, O(E) en mémoire ; 40 ms pour 20 000 arêtes |
| E | Parallèles ? | Intervalles identiques donc chevauchants : couloirs, ordonnées, chemins et libellés distincts ; identité par `edge_id`, doublon refusé |
| F | Couloirs économisés ? | Route : **10 sur 19** (−52,6 %) ; Entity : **0 sur 5** (impossible à deux colonnes) |
| G | Gain de fit Route ? | 0,3415 → **0,3604** (+5,5 %, 34 % → 36 %) ; hauteur −18,4 % ; désormais limité par la largeur |
| H | Textes plus lisibles ? | **Marginalement, pas réellement.** Route : 12 px CSS × fit = 4,10 → 4,32 px (boîte rendue de 5 px dans Chromium, 7,4 px dans Firefox) ; Entity 7,14 → 7,23 px. Le gain mesurable vient surtout de la structure : 0 croisement sur Route contre 14 |
| I | LOD encore nécessaire ? | **Oui, pour la vue d'ensemble de Route.** Au fit, le texte reste à 4,3 px. Le fit étant limité par la largeur, aucune compaction des couloirs ne peut le relever. Pour atteindre 9 px, il faudrait une échelle ≥ 0,75, donc une scène de moins de 1 020 de large au lieu de 2120. Pour Entity (7,2 px), pas avant d'autres corpus |
| J | Prochain besoin ? | **Non prédéterminé.** Constats à arbitrer : un LOD pour la vue d'ensemble ; une compaction horizontale (colonnes plus étroites, couloirs entre colonnes) qui ne suffirait pas seule à rendre le texte lisible ; un routeur orthogonal plus avancé (ports, obstacles) dont Route et Entity n'ont pas besoin aujourd'hui ; un troisième client |

## Fichiers créés

- `forge_design/graphics/__init__.py`, `forge_design/graphics/lanes.py`
- `tests/test_graphics_lanes.py`, `tests/test_graph_layout_lanes.py`
- `docs/rapports/FD-GRAPHICS-005.md`

## Fichiers modifiés

- `forge_design/web/route_graph_layout.py`,
  `forge_design/web/entity_graph_layout.py`
- `pyproject.toml` (paquet `forge_design.graphics`)
- `docs/graphics/graphics-engine.md`, `docs/graphics/graphics-core-contract.md`,
  `docs/graphics/drawciel-reference.md`, `docs/02-architecture.md`,
  `docs/03-roadmap.md`

## Validation globale finale

| Contrôle | Résultat |
|---|---|
| `python -m compileall -q forge_design` | Réussi |
| `ruff check forge_design tests` | Réussi |
| `ruff format --check .` | 383 fichiers conformes |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Réussi |
| `node --check` (6 modules, 2 clients, 9 fichiers de test) | Réussi |
| Suites Node `tests/js/graphics` | 51 réussis |
| Ciblés : routage partagé, layouts, scènes, script, frontière, Web Route et Entity | 437 réussis |
| Suite globale `pytest` (hors du dépôt, `--basetemp` sous `tmp/`) | **4606 réussis**, relancée après insertion de ces résultats |
| `python -m pip check` | Aucune dépendance cassée |
| Chromium 154 / Firefox 153 | 29 / 27 vérifications réussies, plus 2 sans JavaScript dans Firefox |
| Wheel | `forge_design/graphics/` présent ; installée isolément : `/routes` (2120 × 1066, 9 couloirs), `/entities`, modules servis, `lanes.py` chargé depuis l'installation |
| MkDocs | N/A : aucune configuration MkDocs dans Forge Design |

Test instable préexistant : `tests/test_web_real_preview.py::test_runtime_detects_dead_proxy`
a échoué une fois sur les relances globales (`assert [] == ['proxy-close',
'runner-stop']`). Il échoue aussi isolé, sur un worktree propre de `00f9eaa`,
7 fois sur 12 : c'est une course dans le harnais du proxy Real Preview,
étrangère à ce ticket, et non corrigée ici.

## État Git final

Commit unique `feat: compacter le routage des graphes (FD-GRAPHICS-005)`,
au-dessus de `00f9eaa`. `docs/rapports/FD-CONTRACT-001.md` reste modifié
localement, hors commit. Aucun push.
