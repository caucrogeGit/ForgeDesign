# Rapport — FD-GRAPHICS-006

API : [Moteur graphique — niveaux de détail](../graphics/graphics-engine.md#detail-levels-semantic-zoom) ;
contrat : [Graphic Core](../graphics/graphics-core-contract.md#semantic-zoom--niveau-de-détail--fd-graphics-006).

## Ticket et objectif

Ajouter au Graphic Core un niveau de détail qui dépend de l'échelle du
viewport (`overview`, `normal`, `detail`), pour qu'une scène reste
compréhensible en vue d'ensemble, à échelle intermédiaire et en vue détaillée,
sans connaissance métier dans le moteur. **Le moteur décide quand changer de
niveau ; le client décide quoi présenter.**

## État Git initial

```text
$ git log --oneline -1
04f0af8 feat: compacter le routage des graphes (FD-GRAPHICS-005)
$ git rev-parse --short origin/main
04f0af8
$ git status --short
 M docs/rapports/FD-CONTRACT-001.md
```

## Référence DrawCiel

Précédente : `88f95b75`. `git fetch` dans la copie SéquenCiel (lecture
seule) : `origin/main` = **`88f95b75`**, inchangé, figé pour le ticket. Aucun
commit local non publié.

## Delta DrawCiel

Vide.

## Semantic zoom DrawCiel étudié

Recherche explicite dans `static/vendor/drawciel/js/app.js` à `88f95b75`
(zoom, échelle, visibilité, libellés, détail des composants, minicarte,
simplification visuelle). Constats :

| Trouvé | Où | Classification | Raison |
|---|---|---|---|
| Zoom borné 0,25–3, facteur 1,1 par cran, `applyTransform` CSS | `wheel`, `applyTransform`, `fit` | NON APPLICABLE | Déjà traité par FD-GRAPHICS-004 |
| Tolérances d'interaction constantes à l'écran (`11/Math.max(.35, zoom)`, `10/zoom` pour l'accroche, trait de capture `10/zoom`) | sélection de fil, `snap`, annotations | NON APPLICABLE | Principe voisin (raisonner en pixels écran), mais il s'agit d'interaction, pas de présentation ; non repris |
| Minicarte (canvas 2D, navigation au clic) | `renderMinimap`, `minimapNavigate` | NON APPLICABLE | Hors périmètre (pas de minicarte) |
| Zoom de zone (rectangle) | `startZoomArea`, `finishZoomRect` | NON APPLICABLE | Hors périmètre |
| Affichage ou masquage selon l'échelle | — | **Absent** | Aucune condition `zoom <` ou `zoom >` sur un rendu ; les symboles ont des tailles de police fixes |

**DrawCiel n'a pas de semantic zoom.** Aucune provenance n'est revendiquée.

## Limite mesurée après FD-GRAPHICS-005

Route : 2120 × 1066, fit 0,3604 limité par la largeur, texte de 12 → 4,32 px
écran. Les 66 lignes de nœud et les 19 libellés d'arête étaient tous
affichés, illisibles. Entity : fit 0,6027, texte à 7,23 px, 14 lignes et
4 libellés affichés.

## Architecture retenue

```text
viewport.scale ──▶ detail-level.js : detailLevelForScale(scale, previous) ──▶ niveau
                                                                               │
engine.js : à chaque navigation, si le niveau change ─▶ applyDetailLevel(view, niveau)
                                                        (classe + data-detail-level sur le SVG)
adaptateur Python ─▶ node.levels (indices de lignes) ─▶ renderer : classes gx-at-<niveau>
                                                        sur chaque ligne, rendue une seule fois
shell.css ─▶ masque les lignes absentes du niveau et, en overview, les libellés d'arêtes
```

Nouveau module pur `detail-level.js`, ajouté à la liste fermée
`GRAPHICS_MODULES` servie par le Router Forge. Le renderer, le moteur et la
validation sont étendus ; les clients JavaScript sont inchangés.

## Niveaux

`overview`, `normal`, `detail` : trois densités de présentation, pas des
niveaux métier. Les noms du ticket conviennent : l'inspection du moteur n'a
pas révélé de meilleure terminologie.

## Seuils

| Transition | Échelle | Texte de 12 → écran |
|---|---:|---:|
| overview → normal | 7/12 ≈ 0,5833 | 7 px |
| normal → overview | 6,5/12 ≈ 0,5417 | 6,5 px |
| normal → detail | 9/12 = 0,75 | 9 px |
| detail → normal | 8,5/12 ≈ 0,7083 | 8,5 px |

Sans historique (première mesure), les seuils d'entrée s'appliquent.

## Justification des seuils

- Taille logique réelle : `.gx-node-text` et `.gx-edge-label` à **12 px**
  (vérifié dans le CSS et par `getComputedStyle` dans les deux navigateurs).
  La règle `.entity-graph text` (13 px) ne vise que le SVG de repli. Un test
  lie `SCENE_TEXT_SIZE = 12` au CSS.
- Taille écran = taille logique × `scale`.
- Calibrage : un vrai nœud Route rendu par le moteur dans Chromium (DPR 1) à
  4,32, 6, 6,5, 7, 8, 9, 10 et 12 px écran, capturé en pixels réels et agrandi
  ×3 au plus proche voisin. À **4,32 px**, les glyphes se confondent
  (« HomeController.index » illisible). À 6 px, c'est à la limite. À
  **6,5–7 px**, les lettres monospace sont distinctes. À **9 px**, la lecture
  est confortable. Hauteur de boîte mesurée : 5, 7, 8, 8, 9, 10, 11, 14 px.
- D'où : texte principal (le nom) à partir de 7 px ; lignes secondaires à
  partir de 9 px.
- **Lisibilité mesurée, pas accessibilité** : ces seuils ne valent pas
  conformité WCAG. L'accessibilité sémantique (nom accessible, panneau,
  clavier) ne dépend pas du niveau.

## Hystérésis

**Retenue**, 0,5 px écran. Mesure navigateur sur un vrai pincement
(Ctrl + molette de ±4, Chromium et Firefox, Route et Entity) : 30 événements
oscillant autour de 7/12, **29 franchissements** du seuil. Une politique à
seuils simples aurait basculé **29 fois** (le texte apparaît et disparaît à
chaque événement) ; avec l'hystérésis : **0** bascule. Les boutons (pas de
1,25) ne sont pas concernés. L'historique ne commence qu'avec une zone
mesurée. Ce défaut a été trouvé par les tests : l'échelle provisoire 1 avant
mesure faisait sinon garder `detail` à un premier fit de 0,747.

## Contrat GraphicScene

Un seul ajout, facultatif, sur le nœud :

```json
"levels": { "overview": [], "normal": [0, 1] }
```

- indices dans `lines`, strictement croissants, existants ;
  `overview ⊆ normal` ;
- `detail` montre **toujours** toutes les lignes : aucune ligne ne peut être
  rendue inatteignable ;
- clés inconnues refusées (`tiny`, `super-detail`, et même `detail`,
  implicite) ; ni CSS, ni HTML, ni texte dupliqué ;
- bornes : au plus 2 × 4 petits entiers par nœud, soit 40 000 au plus pour
  5 000 nœuds. Aucune chaîne n'est multipliée (le ticket redoutait 3 × 4 ×
  256 caractères × 5 000 ; ce modèle l'évite par construction) ;
- normalisé par `validateScene` : `levels.{overview, normal, detail}` est
  toujours présent et gelé.

Les seuils ne sont pas dans la scène : ils relèvent du runtime (test).

## Compatibilité avec scènes sans LOD

Option retenue : **API facultative, normalisée** par `validateScene`. Sans
`levels`, toutes les lignes sont visibles à tous les niveaux : le rendu des
nœuds est celui d'avant. Seule différence documentée : les libellés d'arêtes
suivent la politique générique (masqués à `overview`).

## Node LOD

Toutes les lignes sont rendues **une seule fois**, à leur position d'origine
(pas de saut vertical au changement de niveau), avec des classes
`gx-at-overview`, `gx-at-normal` ou `gx-at-detail`. Stratégie A
(pré-rendu + classe) préférée à B (réécriture du contenu) : DOM identique à
avant, aucun élément recréé (focus et sélection intacts), bascule en O(1)
(une classe sur le SVG), niveau actif lisible (`data-detail-level`).

À `overview`, les teintes des catégories génériques `category-1…4` sont
renforcées (par exemple `rgb(214, 228, 245)` au lieu de `rgb(245, 248, 252)`) :
c'est un choix de densité générique, sans icône ni forme métier.

## Edge LOD

Politique générique : libellés masqués à `overview`, visibles à `normal` et
`detail`. L'arête elle-même est toujours rendue (19/19 et 5/5 à tous les
niveaux, vérifié dans les navigateurs). Aucune déclaration par arête : aucun
client n'en a besoin, donc pas d'API à règles arbitraires.

## Géométrie inchangée

Les `rect`, les `points` et le viewBox ne dépendent pas du niveau ; nombre de
nœuds et d'arêtes identique à chaque niveau (navigateurs).

## Identités

Aucun élément n'est recréé : mêmes objets DOM de nœuds, de textes et de
libellés avant et après chaque transition (test Node). `node.id` et `edge.id`
sont inchangés.

## Sélection

Conservée : nœud sélectionné en `overview`, puis
`overview → normal → detail → normal → overview` par Ctrl + molette réelle.
Mêmes nœud, voisins, panneau et relations (Chromium et Firefox, Route et
Entity).

## Focus

Le nœud focalisé reste `document.activeElement` à travers toutes les
transitions (navigateurs et Node). L'ordre de tabulation est inchangé :
aucun élément n'est ajouté, retiré ou réordonné.

## Accessibilité

- LOD visuel ≠ LOD sémantique : `aria-label` et `<title>` complets à tous les
  niveaux (vérifiés sur tous les nœuds).
- Les lignes masquées ne participaient pas au nom accessible du nœud
  (`role="button"` + `aria-label`).
- Libellés d'arêtes : de simples `<text>` SVG, jamais reliés à un objet
  focalisable ; masqués (`display: none`) en `overview`, ils sortent de
  l'arbre d'accessibilité à ce niveau. Les relations restent disponibles dans
  la liste (Route), les tableaux et le panneau (Entity).
- Changement instantané, sans animation (compatible `prefers-reduced-motion`).
- Aucune indication du niveau ni de réglage utilisateur : le semantic zoom
  est automatique.

## Route Explorer

`route_graph_scene.py` déclare `levels = {"overview": [], "normal": [0, 1]}`
sur les lignes `[type, nom, présence]`.

- `overview` : **aucun texte**. À 36 %, le nom fait 4,3 px : il a été testé
  (calibrage) et ne transmet rien, il n'est donc pas affiché. La vue montre la
  forme, la catégorie et les relations.
- `normal` : type et nom.
- `detail` : tout, présence comprise.

Le nom complet reste dans le label accessible et dans le panneau. Aucun
libellé externe compensé, aucun `vector-effect`.

## Entity Explorer

`entity_graph_scene.py` déclare `levels = {"overview": [], "normal": [1]}`
sur `[type — n champs, nom, table]` (ou `[type — n champs, nom]` pour un
pivot) : `overview` sans texte, `normal` le nom seul, `detail` tout. Au fit
(60 %), Entity est **normal** selon le seuil mesuré : rien n'est forcé. Les
trois niveaux sont atteints par zoom réel (0,48 → overview, 0,75 → detail).

## Panneaux de détails

Non soumis au LOD : contenu complet en overview (Route : `Handler`,
`HomeController.index`, `—` ; Entity : `Entité`, `Comment`, `comment`, `1`,
`2`, plus les relations), identique à chaque niveau.

## Viewport

Inchangé. Le niveau est réévalué après chaque navigation (fit, home, boutons,
`zoomAt`, molette, resize) depuis `viewport.state().scale`, jamais depuis le
DOM. Le pan ne change pas l'échelle, donc jamais le niveau (test : pan et
Maj + flèches sans aucune écriture). Le resize avant interaction refait un
fit et réévalue le niveau (Entity : 0,60 normal → zone de 250 px → 0,29
overview → retour normal).

## Performance

- Bascule : 3 bascules de classe et 1 attribut sur le SVG racine, O(1) ; la
  CSS fait le reste. Pas de revalidation, d'index, de routage ni de layout.
- Entre deux bascules : rien. Test : 100 événements Ctrl + molette, un pan et
  10 Maj + flèche dans `normal` font **0 écriture** ; un franchissement en
  fait exactement 1.
- Calcul du niveau : O(1) par navigation. Validation : O(lignes) par nœud en
  plus. DOM : identique à FD-GRAPHICS-005 (mêmes éléments, classes en plus).

## Deux instances

Instance Route en `overview` et Entity en `normal` dans la même page réelle,
indépendantes : zoomer Route jusqu'à `detail` laisse Entity en `normal`. Le
niveau appartient à l'instance (aucune variable de module, test de mutation
dédié). `destroy()` rend `detailLevel()` inaccessible ; les écouteurs restent
libérés par les mécanismes existants.

## Fallback sans JavaScript

Inchangé, sans niveau : le SVG serveur complet et défilable (templates
intacts). Firefox sans JavaScript : `0 0 2120 1066` et `0 0 780 740`
affichés, tableaux présents.

## Forge MVC

`create_application()` reste l'unique composition HTTP (tests de frontière
existants verts). Seule évolution : `detail-level` dans la liste fermée
`GRAPHICS_MODULES` (route fixe `/graphics/detail-level.js`,
`text/javascript; charset=utf-8`). Pas d'endpoint, de serveur JavaScript, de
backend Node, de build ni de npm.

## CSP

Inchangée (`script-src 'self'`, `style-src 'self'`). Niveaux par classes et
feuille de style ; aucun style en ligne. Aucune violation ni exception dans
les deux navigateurs.

## Tests Node

71 tests (51 + 20) :

- `detail-level.test.mjs` (10) : seuils dérivés des tailles écran, niveaux
  aux fits mesurés, bornes exactes, hystérésis en entrée et en sortie de
  chaque zone, oscillation (39 bascules simples contre 1), échelles invalides
  (`NaN`, `±Infinity`, `0`, négatif, non numérique) et niveaux inconnus
  refusés (`RangeError`). Contrat `levels` : normalisation, copie
  indépendante, 16 cas invalides, contenu hostile.
- `engine-detail.test.mjs` (10) : `detail` avant mesure puis `overview` au
  fit ; lignes par niveau avec label, titre et éléments inchangés ; contenu
  hostile en texte ; scène sans `levels` ; sélection, voisins et focus à
  travers les transitions ; 0 écriture pendant 100 zooms et le pan ;
  oscillation ≤ 1 transition ; deux instances ; resize ; `render()` et
  `destroy()`.
- Clients Route et Entity : interdiction de `detailLevel`, `gx-detail`,
  `gx-at-` et `levels` (aucune logique LOD côté client).
- Test de vocabulaire existant étendu de fait au nouveau module (il couvre
  tout `graphics/`).

## Tests Python

`tests/test_graphics_detail_level.py` (7) :

- niveaux déclarés par chaque adaptateur, avec des listes distinctes par
  nœud ;
- seuils absents de la scène ;
- règles CSS exactes et génériques (aucune classe métier) ;
- taille de texte liée aux seuils ;
- scènes réelles validées par le vrai `validateScene` dans Node.

Mises à jour : liste `GRAPHICS_MODULES`, liste des modules et nombre de
suites Node. Ciblés (scènes, sérialisation, Web Route et Entity, assets,
frontière Forge) : 433 réussis.

## Chromium

Chrome 154 headless (CDP), serveur de test sur 8766, projet témoin
`tmp/gx3-browser`.

- Scénario LOD : **16/16**. Niveau initial (Route `overview` à 36 %, Entity
  `normal` à 60 %), taille de police 12 et noms accessibles complets.
  Trois niveaux atteints par les boutons. Contenu par niveau avec géométrie et
  topologie identiques. Sélection, panneau et focus à travers les niveaux.
  Échap. Hystérésis sur pincement réel. Resize. Deux instances. Aucune
  exception.
- Non-régression du scénario FD-GRAPHICS-005 (fit, clavier
  Tab/Entrée/Espace, Ajuster, +, −, molette, pan, resize, sans JavaScript) :
  **29/29**.

Captures inspectées :

- **Route en overview** : quatre colonnes de couleurs distinctes, toutes les
  arêtes et la structure des couloirs, aucun texte de 4 px ;
- **Entity en normal** : les noms seuls, lisibles, le texte hostile restant
  du texte.

## Firefox

Firefox ESR 153 headless (BiDi) : scénario LOD **16/16**, mêmes mesures et
même hystérésis (29 → 0) ; non-régression **27/27** (activation des boutons
par clics réels, limite BiDi déjà documentée) ; sans JavaScript **2/2**.

## Mutations

Une à la fois, sources restaurées : **12/12 tuées**.

| Sabotage | Résultat | Premier test en échec |
|---|---|---|
| LOD toujours detail | Tué | `sans historique : échelle faible, intermédiaire, forte` |
| LOD toujours overview | Tué | idem |
| seuil overview ignoré | Tué | `trois niveaux génériques, seuils dérivés…` |
| seuil detail ignoré | Tué | idem |
| changement à chaque molette sans transition | Tué | `100 zooms dans un même niveau et le pan` |
| sélection perdue à la transition | Tué | `sélection, voisins et focus conservés…` |
| focus perdu à la transition | Tué | idem |
| vocabulaire Route ajouté au moteur | Tué | `aucune connaissance de Route Explorer ni d'un domaine` |
| vocabulaire Entity ajouté au moteur | Tué | idem |
| libellés d'arêtes toujours visibles en overview | Tué | `test_css_hides_by_level_with_generic_classes` |
| aria-label réduit avec le visuel | Tué | `lignes par niveau ; label accessible…` |
| deux instances partagent le niveau | Tué | `deux instances : niveaux simultanés différents` |

## Mesures Route

| Mesure | Avant (FD-GRAPHICS-005) | Overview (fit) | Normal | Detail |
|---|---:|---:|---:|---:|
| échelle | 0,3604 | 0,3604 | 0,7039 | 0,8798 |
| texte écran | 4,32 px | — | 8,45 px | 10,56 px |
| lignes de nœud visibles | 66 / 66 | **0** / 66 | 44 / 66 | 66 / 66 |
| libellés d'arêtes visibles | 19 / 19 | **0** / 19 | 19 / 19 | 19 / 19 |
| arêtes visibles | 19 | 19 | 19 | 19 |
| nœuds | 22 | 22 | 22 | 22 |

## Mesures Entity

| Mesure | Avant (FD-GRAPHICS-005) | Overview | Normal (fit) | Detail |
|---|---:|---:|---:|---:|
| échelle | 0,6027 | 0,4822 | 0,6027 | 0,7534 |
| texte écran | 7,23 px | — | 7,23 px | 9,04 px |
| lignes de nœud visibles | 14 / 14 | 0 / 14 | 5 / 14 | 14 / 14 |
| libellés d'arêtes visibles | 4 / 4 | 0 / 4 | 4 / 4 | 4 / 4 |
| arêtes visibles | 5 | 5 | 5 | 5 |

| Client | Fit initial | Niveau initial | Textes visibles | Labels edges visibles |
|---|---:|---|---:|---:|
| Route | 0,3604 | overview | 0 (66 avant) | 0 (19 avant) |
| Entity | 0,6027 | normal | 5 (14 avant) | 4 (4 avant) |

Aucune information n'est perdue : tout reste accessible par le zoom, la
sélection et le panneau, le nom accessible, les listes et tableaux de la
page, et le repli sans JavaScript.

| Élément | Overview | Normal | Detail |
|---|---|---|---|
| node geometry | identique | identique | identique |
| node primary label (nom) | masqué (Route, Entity) | visible | visible |
| node secondary lines | masquées | type (Route) ; aucune (Entity) | toutes |
| edge | visible | visible | visible |
| edge label | masqué | visible | visible |
| aria-label | complet | complet | complet |
| sélection | conservée | conservée | conservée |

## Provenance DrawCiel

Aucune : DrawCiel n'a pas de semantic zoom (voir l'étude). Les seuils, le
contrat `levels`, la stratégie de rendu et l'hystérésis sont originaux
(REWRITE).

## Limites

- En `overview`, Route n'identifie aucun nœud par son nom : l'identification
  passe par le zoom (3 crans de +, échelle 0,70), la sélection (panneau) ou le
  clavier (nom accessible). C'est assumé : un texte de 4,3 px n'identifiait
  rien non plus.
- À l'échelle `normal` de Route (0,70), la scène fait 1 490 px de large pour
  une zone de 796 : lire tous les noms demande de naviguer horizontalement.
- Teintes de catégorie : la couleur aide sans porter seule l'information
  (colonnes, nom accessible, panneau).
- Seuils calibrés sur un rendu Chromium à DPR 1 et une police monospace de
  12 ; à DPR 2 le texte est plus net, à seuils égaux.
- Aucun LOD déclaré par arête ni seuil par instance (non nécessaire
  aujourd'hui).
- Hors périmètre : le test instable `test_runtime_detects_dead_proxy`
  (Real Preview) existait avant ce ticket.

## Roadmap

FD-GRAPHICS-006 fait. FD-GRAPHICS-007 sera décidé sur l'usage observé ; ni
Circuit ni Debug Center ne sont annoncés d'office.

### Décisions obligatoires

| | Question | Réponse |
|---|---|---|
| A | Seuils exacts ? | Entrée en normal à 7/12 ≈ 0,5833, sortie vers overview sous 6,5/12 ≈ 0,5417 ; entrée en detail à 9/12 = 0,75, sortie vers normal sous 8,5/12 ≈ 0,7083 |
| B | Grandeur ? | **`scale`** réelle du viewport, quelle que soit son origine ; le pan est neutre |
| C | Hystérésis ? | **Oui**, 0,5 px écran : sur un vrai pincement oscillant, 29 bascules évitées sur 29 franchissements (Chromium et Firefox) |
| D | Scène sans LOD ? | `levels` facultatif, normalisé : toutes les lignes à tous les niveaux ; libellés d'arêtes masqués en overview (politique générique documentée) |
| E | Géométrie selon le niveau ? | **Non** |
| F | Topologie selon le niveau ? | **Non** |
| G | Sélection après transition ? | **Oui** (ainsi que les voisins, le panneau et le focus) |
| H | Le moteur connaît-il un type métier ? | **Non** (test de vocabulaire, mutations Route et Entity tuées) |
| I | Même mécanisme Route et Entity ? | **Oui** : même module, même renderer, même CSS ; seuls les indices déclarés diffèrent |
| J | Overview Route plus exploitable ? | **Oui, pour la structure.** Mesures : 85 textes de 4,3 px illisibles remplacés par 0 texte, 22 nœuds en 4 teintes nettement distinctes, 19 arêtes et leurs couloirs. Tests navigateur : sélection et panneau complets en overview. Inspection visuelle : colonnes et relations lisibles d'un coup d'œil. L'identification des noms demande un zoom ou une sélection, comme avant en pratique |
| K | Prochaine limite observée ? | **Non prédéterminée.** Constat principal : Route au niveau `normal` dépasse la zone en largeur (1 490 px pour 796), car le layout fait 6 colonnes de 360. Cela pointe vers le **layout horizontal**, ou une aide à la navigation (minicarte). Le routage avancé, les ports, l'édition et un troisième client ne sont pas apparus comme des limites dans ce ticket |

## Fichiers créés

- `forge_design/web/static/graphics/detail-level.js`
- `tests/js/graphics/detail-level.test.mjs`,
  `tests/js/graphics/engine-detail.test.mjs`
- `tests/test_graphics_detail_level.py`
- `docs/rapports/FD-GRAPHICS-006.md`

## Fichiers modifiés

- `forge_design/web/static/graphics/model.js` (`levels`),
  `graphics/svg-renderer.js` (classes `gx-at-*`, `applyDetailLevel`),
  `graphics/engine.js` (niveau par instance, `detailLevel()`),
  `static/shell.css` (règles de niveau), `web/server.py`
  (`GRAPHICS_MODULES`), `web/route_graph_scene.py`,
  `web/entity_graph_scene.py`, `pyproject.toml`
- `tests/js/graphics/route-client.test.mjs`,
  `tests/js/graphics/entity-client.test.mjs`,
  `tests/test_route_graph_script.py`, `tests/test_graphics_forge_boundary.py`
- `docs/graphics/graphics-engine.md`, `docs/graphics/graphics-core-contract.md`,
  `docs/graphics/drawciel-reference.md`, `docs/02-architecture.md`,
  `docs/03-roadmap.md`

## Validation globale finale

| Contrôle | Résultat |
|---|---|
| `python -m compileall -q forge_design` | Réussi |
| `ruff check forge_design tests` | Réussi |
| `ruff format --check .` | 385 fichiers conformes (Markdown compris) |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Réussi |
| `node --check` (7 modules, 2 clients, 11 fichiers de test) | Réussi |
| Suites Node `tests/js/graphics` | 71 réussis |
| Ciblés : scènes, sérialisation, Web Route et Entity, assets, frontière Forge, LOD | 433 réussis |
| Suite globale `pytest` (hors du dépôt, `--basetemp` court sous `tmp/`) | **4616 réussis**, relancée après insertion de ces résultats |
| `python -m pip check` | Aucune dépendance cassée |
| Chromium 154 | LOD 16/16, non-régression 29/29 |
| Firefox 153 | LOD 16/16, non-régression 27/27, sans JavaScript 2/2 |
| Wheel installée isolément | `detail-level.js` packagé et servi (`text/javascript; charset=utf-8`) ; `/routes` et `/entities` portent `levels` ; règles CSS servies |
| MkDocs | N/A : aucune configuration MkDocs dans Forge Design |

## État Git final

Commit unique `feat: ajouter le semantic zoom au Graphic Core (FD-GRAPHICS-006)`,
au-dessus de `04f0af8`. `docs/rapports/FD-CONTRACT-001.md` reste modifié
localement, hors commit. Aucun push.
