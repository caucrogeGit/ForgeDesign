# Graphic Core

Statut : **normatif** (FD-GRAPHICS-001). Ce contrat fixe les frontières du
noyau graphique 2D commun aux futurs outils graphiques de Forge Design
(Circuit, Flowchart, Network, schémas fonctionnels, UML éventuel). **Rien
n'est implémenté** : aucun module `forge_design/graphics/`, aucun renderer,
aucune dépendance. Les noms (`GraphicScene`, `Node`, `Port`…) désignent des
**concepts et responsabilités**, pas des classes existantes.

Règle majeure :

> **Graphics présente et manipule une ressource métier ; il n'en définit pas
> la sémantique.**

Statuts employés : **observé** (DrawCiel ou Forge Design existant),
**décidé** (règle du contrat), **reporté** (ticket ultérieur).

## Objectif

Extraire le **plus petit noyau graphique réellement commun** : géométrie,
scène projetée, nœuds, ports, arêtes, routes, texte, sélection, commandes,
historique, routage et interaction, sans connaître l'électricité, le réseau,
la logique d'organigramme, la simulation ni la pédagogie.

Le noyau capitalise sur DrawCiel (prototype avancé, laboratoire fonctionnel,
source d'algorithmes et de tests éprouvés) **sans copier son monolithe**.

Deux risques encadrent toutes les décisions :

- **duplication** : `CircuitRoute`, `NetworkRoute`, `FlowRoute` réimplémentant
  la même géométrie ;
- **surabstraction** : un moteur universel conçu sans cas réels.

La généralisation ne s'appuie que sur DrawCiel réel, les besoins Circuit
validés (FD-CIRCUIT-001) et les besoins minimaux évidents de Flowchart et
Network.

## Référence DrawCiel vivante

**Observé.** Référence de ce contrat : SéquenCiel `origin/main` =
`c229b2ed` (2 octobre 2026), relevée après `git fetch` le 3 octobre 2026.
Le suivi des références et la procédure de delta sont décrits dans
[Référence DrawCiel](drawciel-reference.md).

État de DrawCiel utile au noyau :

| Élément | Constat au commit de référence |
|---|---|
| Rendu | Scène SVG construite par `createElementNS` (`svgEl`) et `innerHTML`, rendu complet à chaque modification ; canvas pour minimap, oscilloscope et exports raster |
| Coordonnées | Monde en pixels, `snapStep = 20`, aimantation désactivable (`snapToggle`) |
| Symboles | SVG 512 × 512, bornes en coordonnées symbole ; taille d'instance 70/90/120 px |
| Bornes | Position monde = transformation flottante (`cos`/`sin`) ; **aucune des 359 bornes** du catalogue de données ne tombe sur la grille de 20 px à la taille par défaut (90 px) |
| Routage | `cleanRoute` (droite, 1 coude, 2 coudes), `adaptedRoute`, `moveWireSegmentStable`, `astarGrid`, `fallbackBetween`, `simplifyExact` ; raccords de bornes (`terminalPort` : stub + ancre de grille) |
| Sélection | Ensembles séparés par nature : composants (`Set`), fil, texte, annotation |
| Historique | Instantané JSON complet par entrée (`stateJSON`), non borné ; `restore()` émet désormais `drawciel:change` lorsqu'il modifie l'état |
| Jonctions | Composant interne `__drawciel_auto_junction__`, découpe et nettoyage automatiques des fils |
| Annotations | Collection `texts` (texte, rappel) et collection `annotations` (lignes, flèches, formes, trait libre) |
| Export | SVG par clonage nettoyé de la scène DOM vivante ; PNG par rasterisation |
| Tests | Géométrie et routage couverts uniquement par des scénarios navigateur (Playwright) ; graphe, contrats, session, IR, SPICE couverts par des tests Node hors DOM |

## Synchronisation DrawCiel

**Décidé.** DrawCiel continue d'évoluer ; Forge Design le suit par une
**procédure de développement**, jamais par synchronisation automatique ni par
dépendance runtime :

1. Avant chaque ticket FD-GRAPHICS-\* important, chaque ticket FD-CIRCUIT-\*
   architectural et chaque ticket de simulation : relever `origin/main` de
   SéquenCiel, calculer le delta depuis la dernière référence consignée,
   rechercher les changements DrawCiel pertinents, évaluer leur impact.
2. La référence est **figée pour la durée du ticket** ; une évolution ultérieure
   est prise en compte au ticket suivant, sauf correction critique invalidant
   le travail en cours.
3. Chaque rapport concerné consigne : commit de référence, date, delta depuis
   la référence précédente, éléments examinés, impacts retenus.
4. Une amélioration DrawCiel postérieure à un ancien audit prévaut sur un
   constat devenu obsolète ; les rapports distinguent *historique*,
   *encore vrai*, *corrigé depuis*, *nouveau*.

Détails, zones surveillées et journal des références :
[Référence DrawCiel](drawciel-reference.md).

## Périmètre

Le Graphic Core 2D comprend :

- primitives géométriques : point, vecteur, rectangle, transformation ;
- politique de grille et d'aimantation paramétrée par le domaine ;
- scène projetée en mémoire : nœuds, ports, arêtes, routes, textes ;
- géométrie dérivée : position monde des ports, emprises, obstacles ;
- routage : droit et orthogonal, stabilité au déplacement, édition de segment ;
- sélection hétérogène, rectangle de sélection, hit-testing géométrique ;
- commandes, historique, état « modifié » ;
- interaction : traduction des gestes et du clavier en intentions ;
- viewport : zoom, pan, cadrage ;
- interface d'adaptation vers un renderer et export de scène.

## Hors périmètre

- toute sémantique de domaine : compatibilité de ports, réseaux électriques,
  jonctions électriques, propriétés métier, validation métier ;
- format persistant propre (§ Projection des documents métier) ;
- simulation (électrique, réseau ou autre) et instruments ;
- pédagogie, TP, données élèves ;
- 3D ;
- lecture et écriture des ressources : responsabilité de l'hôte
  (`forge_design.specialized`) ;
- choix définitif d'une technologie de rendu (§ Renderer).

Vocabulaire interdit dans le noyau : *Circuit*, *borne électrique*, *tension*,
*courant*, *résistance*, *net électrique*, *GND*, *jonction électrique*,
*interface réseau*, *décision*, ainsi que tout identifiant de type de domaine.

## Scene

**Décidé.** Une `GraphicScene` est une **projection en mémoire** d'un document
métier, jamais une source de vérité ni un fichier.

```text
GraphicScene
├── nodes        Node par identité
├── edges        Edge par identité
├── texts        TextAnnotation par identité
├── grid         politique de grille (pas, obligatoire ou non)
└── bounds       emprise de la page déclarée par le domaine
```

- Elle est **reconstructible à tout instant** à partir du document et du
  catalogue de présentation du domaine.
- Son contenu est **déterministe** : même document ⇒ même scène, quel que soit
  l'ordre des collections du document.
- Elle porte uniquement des informations de **présentation et de géométrie** ;
  chaque objet de scène porte l'identité de l'objet métier qu'il présente.
- Une scène sans ports reliés ni arêtes est valide (dessin de nœuds seuls).

## Node

**Décidé.** Objet placé dans une scène.

| Champ | Nature |
|---|---|
| Identité | Identité stable de l'objet métier présenté |
| Position | Point d'ancrage en coordonnées monde |
| Orientation | Transformation admise par le domaine (§ Transformations) |
| Forme | Emprise locale (rectangle) et présentation opaque fournie par le domaine |
| Ports | Liste fournie par le domaine |
| Obstacle | Indique si le routage doit contourner le nœud, avec marge éventuelle |
| Libellés | Textes de présentation éventuels (référence, valeur) ancrés au nœud |

Le noyau ne connaît pas le **type** métier d'un nœud ; il reçoit une
présentation opaque (symbole, gabarit) que seul le renderer interprète.

## Port

**Décidé.** Concept générique fondamental : **point d'accroche nommé**
appartenant à un nœud.

| Champ | Nature |
|---|---|
| Identifiant | Unique dans le nœud, fourni par le domaine |
| Position locale | Dans le repère du nœud |
| Direction | Côté de sortie (`N`, `E`, `S`, `W`) ou **aucune** (accroche omnidirectionnelle) |

- La position monde d'un port est une **fonction pure** de la position et de
  l'orientation du nœud et de sa position locale ; elle est testable sans
  domaine.
- La direction est **déclarée**, jamais déduite de la distance au bord du
  dessin. (**Observé** : `terminalLocalSide` de DrawCiel choisit le bord le
  plus proche dans le repère 512 ; heuristique à ne plus utiliser à
  l'exécution, utilisable une fois lors d'une conversion de catalogue.)
- Le noyau **ne décide jamais** si deux ports sont compatibles, ni combien
  d'arêtes un port accepte : ces règles appartiennent au domaine.

Sémantiques par domaine : borne électrique (Circuit), interface (Network),
entrée/sortie de flux (Flowchart).

## Edge

**Décidé.** Le noyau connaît :

| Champ | Nature |
|---|---|
| Identité | Identité stable de la relation métier présentée |
| Extrémité A, extrémité B | Chacune = (identité de nœud, identifiant de port) |
| Route | Présentation géométrique (§ Route) |
| Présentation | Style opaque : trait, marqueurs d'extrémité, libellé éventuel |

- Une extrémité est **toujours un port** : pas d'extrémité libre persistée,
  pas d'extrémité « sur une arête ». Un domaine qui a besoin d'un point de
  ramification le représente par un nœud (§ Junction ci-dessous, et
  [rapport FD-GRAPHICS-001](../rapports/FD-GRAPHICS-001.md#junction)).
- Le noyau connaît un **graphe de connexion visuel** (quels ports sont reliés
  par quelles arêtes) ; il ne prétend jamais connaître une topologie de
  domaine (réseau électrique, routage IP, flux de contrôle).

Interprétations : liaison électrique (Circuit), lien réseau (Network),
transition (Flowchart).

## Route

**Décidé.** Règle générique, valable pour tous les domaines :

> **endpoints = relation ; route = présentation.**

- La route n'est **jamais** l'autorité de la relation. Une route absente,
  invalide ou recalculée ne change jamais les extrémités.
- Une route est la suite ordonnée de ses **points intermédiaires** ; les
  extrémités dérivent des positions monde des ports et ne sont pas dupliquées.
  (**Observé** : dans DrawCiel, `points` désigne selon les drapeaux
  `autoRoute`/`routeLocked` soit la polyligne complète, soit les seuls points
  intermédiaires ; cette ambiguïté n'est pas reproduite.)
- Modes de route : `straight` et `orthogonal` en premier lieu ; d'autres modes
  (courbes) sont FUTUR.
- **Croisement** : deux routes peuvent se croiser ou se superposer visuellement
  sans qu'aucune relation n'en résulte. Le recouvrement géométrique ne crée
  jamais d'arête.

## Annotation

**Décidé.** Le noyau commun minimal est `TextAnnotation` : identité, position,
texte, taille de police dans un ensemble borné, alignement, largeur fixe ou
automatique. Elle est neutre pour toute sémantique de domaine.

**FUTUR** : rappel de texte (ligne vers une cible), formes (ligne, flèche,
rectangle, ellipse), trait libre. DrawCiel les possède et les a qualifiés
(DC-015-01, 02, 07, 08, 12) ; ils entreront dans le noyau lorsqu'un domaine
en aura besoin, sur le modèle de ces tickets.

## Géométrie

**Décidé.**

- **Coordonnées monde** indépendantes du viewport, du zoom et de la densité
  d'écran. Le viewport n'est qu'une transformation d'affichage runtime.
- Unité monde : nombre fini ; un domaine peut exiger des **entiers** (Circuit :
  unités de grille entières). Les comparaisons d'alignement des routes
  orthogonales sont **exactes** dans ce cas (pas de tolérance `.01` comme dans
  DrawCiel).
- Primitives pures : `Point`, `Vector`, `Rect`, `Transform` ; fonctions
  d'emprise, d'intersection segment/rectangle, de simplification de polyligne
  (suppression des points colinéaires et des segments nuls).

## Grille

**Décidé.** Le noyau **supporte** une grille et l'aimantation ; il ne les
**impose** pas.

| Paramètre du domaine | Effet |
|---|---|
| `grid_step` | Pas de la grille logique |
| `grid_required` | Si vrai, positions de nœuds, ports et points de route toujours sur la grille ; aimantation non désactivable |

Circuit : `grid_required = true`. Flowchart : probablement vrai. Network :
à décider par son domaine.

## Transformations

**Décidé.**

- Le noyau gère des transformations ; le domaine **restreint** les valeurs
  admises.
- Premier lot : rotation par **quarts de tour** (0, 90, 180, 270) calculée en
  arithmétique exacte (permutation et changement de signe des coordonnées),
  sans trigonométrie flottante. (**Observé** : `ComponentModel.terminalPosition`
  de DrawCiel utilise `cos`/`sin`, ce qui produit des résidus flottants à 90°.)
- **Miroir** : FUTUR, transformation géométrique pure distincte de toute
  opération de domaine (l'inversion de connexions DrawCiel est une opération
  topologique, hors noyau).
- **Rotation libre** et **redimensionnement** : FUTUR ; ils exigeront des règles
  de placement des ports déclarées par le domaine.
- Une rotation de sélection multiple tourne chaque nœud autour de son propre
  ancrage (comportement observé dans DrawCiel) ; la rotation autour d'un pivot
  commun est FUTUR.

## Sélection

**Décidé.**

- Sélection **hétérogène** : un ensemble d'identités d'objets de scène (nœuds,
  arêtes, textes), et non un ensemble par nature.
- Sélection simple, multiple (modificateur), rectangle (objets entièrement
  contenus), tout sélectionner, vider.
- Hit-testing **géométrique** et pur (point dans emprise, distance à une
  route), indépendant du DOM et du renderer, avec priorité déclarée
  (port, puis nœud, puis arête, puis texte). Le renderer peut accélérer mais
  ne fait pas autorité.
- La sélection est runtime ; elle n'est jamais persistée.
- Groupes et verrous : FUTUR (absents de Circuit V1).

## Commandes

**Décidé.** Toute modification passe par une **commande** appliquée au
**document métier**, jamais à la scène directement.

```text
geste (pointer, clavier)
  → intention (MoveNodes, RotateNodes, SetRoute, MoveText, Remove…)
  → commande
  → adaptateur de domaine → document métier modifié
  → nouvelle projection → scène
```

Commandes génériques candidates (géométrie seule) :

| Commande | Effet |
|---|---|
| `MoveNodes` | Déplace des nœuds ; adapte les routes incidentes |
| `RotateNodes` | Change l'orientation admise ; adapte les routes incidentes |
| `SetRoute` / `MoveRouteSegment` / `ResetRoute` | Modifie la présentation d'une arête |
| `MoveText` / `SetTextPresentation` | Modifie une annotation textuelle |
| `RemoveObjects` | Demande la suppression ; le domaine décide des suppressions induites |
| `AddObjects` | Insère des objets fournis par le domaine (ex. collage) |

Les commandes qui changent la **sémantique** sont des commandes de domaine
(ex. Circuit : relier deux bornes, insérer une jonction électrique ;
Flowchart : relier une branche « vrai »). Elles implémentent le même contrat
de commande et entrent dans le même historique.

Une commande générique est appliquée par l'intermédiaire de l'adaptateur de
domaine (§ Projection), qui peut **refuser** (objet verrouillé, règle
métier) : le refus est explicite et ne crée pas d'entrée d'historique.

## Historique

**Décidé.**

- Mécanisme **générique** : pile annuler/rétablir de commandes atomiques,
  bornée, runtime uniquement.
- Un geste = une entrée (un glisser complet, une rotation, une commande de
  domaine composite) ; saisies d'un même champ regroupées.
- La représentation d'une entrée (inverse explicite ou instantané du
  document) est **reportée** au ticket d'implémentation ; un instantané
  complet non borné par entrée n'est pas reproduit.
- Le noyau signale que le document diffère de l'état enregistré
  (`dirty`) ; l'hôte reste seul responsable de la révision, de la sauvegarde
  et du conflit.
- Changements de vue, de sélection et d'outil : aucune entrée.

## Routage

**Décidé.** `OrthogonalRouter` est un **service pur** :

```text
entrée : port de départ (position monde, direction),
         port d'arrivée (position monde, direction),
         obstacles (rectangles avec marge), grille,
         route précédente éventuelle, mode
sortie : points intermédiaires de la route
```

Il ne connaît que la géométrie, les ports et les obstacles ; jamais un type
de nœud. Comportements à garantir, tous issus de DrawCiel :

| Comportement | Origine DrawCiel |
|---|---|
| Ports alignés ⇒ route droite | `smartPoints`, `cleanRoute` |
| Candidats droite, un coude, deux coudes, classés par nombre de coudes puis longueur | `cleanRoute` (DC-015-FINAL) |
| Premier segment sortant dans la direction du port | `cleanRoute` (`outward`) |
| Évitement des obstacles par rejet des candidats obstrués | `routeObstructed`, `segmentHitsBox` |
| Points colinéaires et segments nuls supprimés | `simplifyExact` |
| Déplacement : seuls les segments adjacents à l'extrémité déplacée s'adaptent ; recalcul si la route devient non orthogonale ou obstruée | `adaptedRoute` |
| Déplacement conjoint des deux extrémités : translation | `translateInternalWireRoutes` |
| Routes non incidentes inchangées | `prepareStableRoutesForMove` |
| Segment déplacé perpendiculairement, y compris une route droite | `moveWireSegmentStable` |
| Recours lorsque les candidats simples échouent | `astarGrid`, `fallbackBetween` (FUTUR dans le noyau) |

Ce qui **ne** passe **pas** dans le noyau :

- les cas particuliers par identifiant de type (`19_cartes_developpement__arduino_uno_r3`
  dans `smartPoints` et `routeObstructed`) : remplacés par la marge
  d'obstacle déclarée par le nœud ;
- l'exclusion des jonctions par `isAutoJunction` : remplacée par le drapeau
  `obstacle` du nœud ;
- les raccords stub + ancre de grille de `terminalPort` : rendus inutiles
  lorsque le domaine exige des ports sur la grille ; conservés comme option
  pour les domaines sans grille obligatoire ;
- les lectures d'état global (`components`, `page`, `snapStep`, `zoom`) :
  remplacées par des paramètres explicites.

## Renderer

**Décidé.** Le noyau est **indépendant du rendu** :

```text
Graphic Core ──▶ Renderer adapter
                   ├── SVG          candidat naturel 2D
                   ├── Canvas       éventuel (grands volumes, aperçus)
                   └── (3D : moteur séparé, hors Graphic Core)
```

Comparaison pour les outils 2D (**analyse**, sans choix définitif) :

| Critère | SVG | Canvas | Hybride |
|---|---|---|---|
| Rendu vectoriel et zoom net | Natif | À recalculer à chaque zoom | SVG pour la scène |
| Texte et sélection de texte | Natif, accessible | Dessiné, non accessible | SVG |
| Objets DOM, focus, noms accessibles | Oui | Non (DOM parallèle requis) | SVG |
| Hit-testing | Natif ou géométrique | Géométrique | Géométrique |
| Nombre d'objets | Quelques milliers d'éléments | Très élevé | Canvas pour la masse |
| Export vectoriel | Naturel, depuis le modèle | Rasterisation seulement | SVG |
| Hors ligne, sans CDN | Oui | Oui | Oui |
| Réutilisation DrawCiel | Directe (scène SVG, symboles SVG) | Faible (minimap, oscilloscope) | Partielle |
| Cohérence Forge Design | SVG serveur déjà utilisé (graphes routes/entités) | Aucun usage | — |
| CSP stricte | Compatible si symboles sans `style` ni script (vérifié : 0/160 dans les données DrawCiel) | Compatible | — |

Conclusion : **SVG reste le candidat naturel** pour Circuit, Network,
Flowchart et UML ; Canvas reste possible pour des usages spécialisés
(minimap, grands volumes). Le choix est fait par FD-GRAPHICS-004 selon les
critères : performance, accessibilité, SVG natif, texte, hit-testing,
nombre d'objets, zoom, pan, ports, arêtes, routage, export, hors ligne, pas
de CDN, maintenance, tests, **coût de récupération du code DrawCiel**.

Export : l'export de scène est produit **depuis le modèle** (scène projetée),
sans élément d'interface, et non par clonage d'un DOM vivant.
(**Observé** : `cleanSvgClone` de DrawCiel nettoie a posteriori la scène
affichée.)

## Interaction

**Décidé.** Quatre couches distinctes :

| Couche | Responsabilité | Testable sans navigateur |
|---|---|---|
| Modèle | Scène projetée, géométrie, routage, hit-testing | Oui |
| Commandes | Intentions, application via le domaine, historique | Oui |
| Interaction DOM | `pointerdown/move/up`, clavier, focus → intentions | Non (navigateur) |
| Renderer | Scène → affichage | Partiellement |

`move_node()` est testable indépendamment d'un `pointermove` : le navigateur
**traduit** un geste en intention, il ne modifie jamais le modèle lui-même.

Clavier (minimum commun) : sélection, déplacement par pas de grille, rotation,
suppression, annuler/rétablir, échappement d'un geste en cours ; focus
visible ; noms accessibles des objets.

Langage d'exécution (**décidé**, à confirmer par FD-GRAPHICS-002) : le noyau
interactif s'exécute dans le **navigateur**, en JavaScript sans étape de
build, livré comme ressource statique packagée, testé par des tests Node hors
DOM pilotés par pytest (pratique déjà en place pour `entity-graph.js` et
`route-graph.js`). Raisons : l'interaction est côté client, les algorithmes
DrawCiel à extraire sont en JavaScript, aucune dépendance supplémentaire.
L'hôte Python reste responsable des ressources et de leur validation
(codec du domaine). Une règle normative ne doit avoir **qu'une seule
implémentation** ; si une règle de domaine doit exister des deux côtés, elle
est couverte par des **fixtures communes** (JSON) exécutées par les deux suites.
(**Observé** : DrawCiel duplique la signature de TP en JavaScript et en Python.)

## Domaine vs Graphics

| Responsabilité | Graphics | Domaine |
|---|---|---|
| Coordonnées, grille, transformations | Oui | Choisit pas, obligation, rotations admises |
| Nœuds, ports, positions monde | Oui | Fournit types, présentations, ports et directions |
| Compatibilité de ports, cardinalité | Non | Oui |
| Arêtes, routes, routage | Oui (présentation) | Décide de la relation (création, suppression) |
| Jonction, ramification, réseau dérivé | Non | Oui |
| Propriétés de présentation (libellé affiché, style) | Oui | Fournit les valeurs |
| Propriétés métier, unités, validation | Non | Oui |
| Commandes géométriques | Oui | Peut refuser |
| Commandes sémantiques | Contrat de commande seulement | Oui |
| Historique, dirty | Oui | — |
| Révision, sauvegarde, conflit | Non | Hôte (`forge_design.specialized`) |
| Simulation, mesures | Non | Domaine / simulation |

## Projection des documents métier

**Décidé.** Le Graphic Core **ne possède pas de format persistant propre**.

```text
                  Forge Design Host
                         │
              Specialized resources
                         │
      ┌──────────────────┼──────────────────┐
CircuitDocument    FlowchartDocument   NetworkDocument
      │                  │                  │
      └──────── adaptateurs de domaine ─────┘
                         │
                   GraphicScene
                         │
        ┌────────────────┼────────────────┐
     commandes        routage         sélection
        └────────── Graphic Core ─────────┘
                         │
                     renderer
                         │
                     navigateur
```

Un domaine fournit un **adaptateur** composé de :

| Fonction | Contrat |
|---|---|
| `project(document) → GraphicScene` | Pure, déterministe, sans effet ; reconstruit la scène |
| `apply(document, intention) → document' \| refus` | Applique une intention générique (géométrie) au document métier |
| Commandes de domaine | Commandes sémantiques propres, au même contrat de commande |
| `presentation(type)` | Symbole/gabarit, emprise, ports et directions d'un type |

Règles :

- **Source de vérité unique** : le document métier. La scène est dérivée,
  jetable, jamais écrite. Pas de `GraphicsDocument` parallèle, donc pas de
  divergence possible.
- Après chaque commande, la scène est re-projetée (intégralement ou par
  invalidation ciblée ; optimisation reportée) ; elle n'est jamais modifiée
  directement.
- **Conventions de champs partagées** : pour éviter des représentations
  divergentes, Graphics définit des **fragments de convention** que chaque
  format de domaine peut adopter tels quels : placement (`position`,
  `rotation` en quarts de tour), extrémités d'arête (`node`, `port`), route
  (`mode`, `points` intermédiaires), texte. Ce ne sont pas un format : le
  domaine reste propriétaire de son schéma, de sa version et de sa validation.
- La question « faut-il un format graphique persistant universel ? » a été
  **posée et rejetée** pour l'instant : les domaines diffèrent trop
  (propriétés, identités, validation) et un double état serait un risque de
  divergence plus coûteux que la duplication de quelques champs conventionnels.

## Circuit

Circuit se projette ainsi :

| Concept Circuit | Projection Graphics |
|---|---|
| Composant | `Node` (présentation = symbole du type ; ports = bornes) |
| Borne | `Port` (identifiant = identifiant de borne ; direction déclarée par le type) |
| Connexion électrique | `Edge` (route orthogonale) |
| Jonction électrique | `Node` sans obstacle, un port omnidirectionnel accueillant plusieurs arêtes |
| Masse GND | `Node` |
| Texte | `TextAnnotation` |
| Réseau, polarité, valeurs, validation, simulation | Domaine Circuit uniquement |

Paramètres : `grid_required = true`, rotations admises 0/90/180/270, mode de
route `orthogonal`. Commandes de domaine : relier deux bornes, insérer une
jonction sur une connexion, supprimer une jonction de degré 2. Le
[périmètre Circuit](../circuit/circuit-scope.md) précise ce qui relève du
domaine.

## Flowchart

Cas de contrôle (sur papier, **aucune implémentation**) :

| Élément | Projection |
|---|---|
| Start/End | `Node` (ovale) ; port de sortie (Start) ou d'entrée (End) |
| Process | `Node` (rectangle) ; ports entrée, sortie |
| Decision | `Node` (losange) ; port d'entrée, ports `true`, `false` |
| Input/Output | `Node` (parallélogramme) ; ports entrée, sortie |
| Transition | `Edge` avec marqueur de flèche et libellé éventuel (« oui », « non ») |
| Bifurcation | Port supplémentaire d'un nœud Decision — **pas de jonction** |

Le domaine Flowchart valide (une seule sortie `true`, pas d'entrée sur Start),
le noyau ne fait que présenter. **Aucune notion Circuit n'est nécessaire.**
Besoins révélés : marqueurs d'extrémité et libellé d'arête (présentation
opaque d'`Edge`, couverts).

## Network

Second cas de contrôle :

| Élément | Projection |
|---|---|
| Router, Switch, Host, Server | `Node` avec présentation propre |
| Interface | `Port` (souvent nombreux, créés par le domaine) |
| Lien | `Edge` (route droite ou orthogonale selon le domaine) |
| Adresse, nom, VLAN | Libellés de présentation de nœud/arête ; données métier dans le domaine |

Une arête réseau partage rendu, routage, ports et sélection avec Circuit sans
partager sa sémantique. La simulation réseau suit le même schéma que Circuit,
**hors Graphic Core** :

```text
NetworkDocument → NetworkTopology → NetworkSimulation
CircuitDocument → topologie / IR Circuit → simulation
```

Besoin révélé : un lien vers un équipement dont l'interface n'est pas encore
choisie ; le domaine l'exprime par un port « corps » du nœud. Aucun ajout au
noyau.

## 3D

**Décidé.** Le Graphic Core est **explicitement 2D**. La 3D (Phase 11) aura
son propre moteur (scène, caméra, transformations 3D, rendu WebGL ou autre) ;
ses primitives ne sont pas déformées pour entrer dans le noyau 2D.
Seuls des **principes** peuvent être partagés : projection d'un document métier
sans double état, commandes et historique, hôte responsable des ressources.

## Stratégie de réutilisation DrawCiel

**Décidé.** Classes de réutilisation :

| Classe | Sens |
|---|---|
| REUSE-AS-IS | Déjà découplé ; réutilisable presque tel quel |
| EXTRACT | Bon algorithme enfoui dans `app.js` ; à extraire en fonction pure |
| ADAPT | Concept exploitable avec adaptation à la nouvelle frontière |
| REWRITE | Besoin correct, implémentation trop couplée |
| DOMAIN-ONLY | Reste dans le domaine Circuit (ou simulation) |
| SEQUENCIEL-ONLY | N'entre pas dans Forge Design |
| DEPRECATED | Comportement à ne plus reproduire |

Synthèse (matrice complète dans le
[rapport](../rapports/FD-GRAPHICS-001.md#matrice-de-réutilisation-drawciel)) :

| Sous-système | Classe | Destination |
|---|---|---|
| Routage orthogonal simple et stabilité | EXTRACT | Graphics |
| Routage de recours (A\*, repli) | ADAPT (FUTUR) | Graphics |
| Grille/aimantation, primitives d'emprise | EXTRACT | Graphics |
| Position monde des bornes | REWRITE (exacte, entière) | Graphics |
| Direction des ports | DEPRECATED à l'exécution ; ADAPT à la conversion | Catalogue Circuit |
| Viewport, zoom, pan | ADAPT | Graphics |
| Sélection, rectangle | ADAPT | Graphics |
| Glisser, rotation | ADAPT | Graphics |
| Historique par instantanés | REWRITE | Graphics |
| Copier/coller (remappage des identités, renumérotation) | ADAPT | Graphics + domaine |
| Jonctions automatiques | DEPRECATED (mécanisme) ; besoin DOMAIN-ONLY | Circuit |
| Annotations texte et formes | ADAPT | Graphics (texte d'abord) |
| Rendu SVG `render()` | REWRITE | Renderer |
| Export par clonage DOM | REWRITE | Export depuis le modèle |
| Catalogue (données + contrats) | ADAPT par conversion contrôlée | Catalogue Circuit |
| Graphe électrique, contrats de bornes | ADAPT | Circuit |
| SimulationIR, sérialiseur SPICE | ADAPT / DOMAIN-ONLY | Simulation Circuit |
| Moteur pédagogique | ADAPT (adaptateur futur) | Simulation Circuit |
| TP, bibliothèque SQL, adaptateurs hôte, Arduino pédagogique | SEQUENCIEL-ONLY | — |

Règles :

1. **Aucun copier-coller massif.** Même un élément REUSE-AS-IS est isolé,
   testé et débarrassé de ses dépendances SéquenCiel et électriques inutiles.
2. **Provenance** de tout code repris : commit source, fichier, fonction ou
   algorithme, adaptations, tests associés, consignés dans le rapport du
   ticket d'extraction et en commentaire d'en-tête du module concerné.
3. DrawCiel et Forge Design relèvent du même porteur ; cela ne dispense pas
   d'une provenance technique claire. La licence publique de Forge Design est
   une question séparée.
4. Les symboles SVG du catalogue ont une provenance non documentée dans
   DrawCiel (archive `DrawCiel_V0.15.0.zip`, SHA-256 consigné dans
   `INTEGRATION.md`) ; leur origine doit être établie avant toute reprise.

## Tests de référence

**Décidé.** Les scénarios DrawCiel servent de **témoins de comportement**
pour toute extraction ; ils ne sont pas déplacés maintenant.

| Source DrawCiel | Comportement garanti | Candidat de portage |
|---|---|---|
| `tests/browser/drawciel-routage.cjs` | Orthogonalité, absence de segment nul et de points colinéaires, 3/2/3/2 points pour la boucle P1–I1–R1–LED1, pas d'escalier après déplacement (≤ 4 points), routes non incidentes identiques, annuler/rétablir exact, reprise identique, neutralité électrique | Tests purs de `OrthogonalRouter` et de la stabilité au déplacement (fixture du circuit terrain) |
| `tests/fixtures/drawciel_015/b_circuit.json` | Ancien circuit chargé sans recalcul de route | Fixture de non-régression de conversion |
| `tests/browser/drawciel-graphe.cjs`, `tests/drawciel-graph.cjs`, fixtures A–J | Croisement sans jonction (F), jonction (G), invariance par permutation et déplacement | Tests de topologie Circuit et invariant « opération graphique ⇒ topologie inchangée » |
| `tests/browser/drawciel-interface.cjs` (DC-015-06) | Modes accessibles, gestes, liaison distincte des annotations | Tests navigateur de l'interaction |
| `tests/browser/drawciel-plan-travail.cjs` (DC-015-13) | Grille/aimantation, page, historique, signature inchangée | Tests de grille et de vue |
| `tests/browser/drawciel-annotations.cjs`, `-texte.cjs`, `-rappel.cjs`, `-trait-libre.cjs` | Gestes, historique, reprise, neutralité, exports | Tests `TextAnnotation` puis annotations FUTUR |
| `tests/browser/drawciel-sources.cjs`, `drawciel-ac.cjs` | Rotation, duplication, annuler/rétablir, reprise | Tests de rotation des ports et de copier/coller |
| `tests/browser/drawciel-rendus.cjs`, `-insertion.cjs` | Exports SVG/PNG/WebP, recadrage | Tests d'export depuis le modèle |
| `tests/browser/drawciel-inspecteur.cjs`, `-saisie-proprietes.cjs` | Inspecteur unique, transactions par champ | Tests d'historique regroupé |

Scénarios à écrire au portage : rotation des ports (quatre orientations,
positions exactes), déplacement de nœud (routes incidentes seulement),
stabilité de route, croisement sans relation, édition de segment ; sélection
simple, multiple, rectangle, suppression, copie.

## Implémentation minimale — FD-GRAPHICS-002

Première tranche exécutable, API détaillée dans
[Moteur graphique — API JavaScript](graphics-engine.md) :

```text
RouteGraph / RouteGraphLayout ─(adaptateur Route Explorer, Python)─▶ GraphicScene (JSON inerte)
      ─▶ validateScene ─▶ indexScene / createSelection ─▶ renderScene (SVG) ─▶ navigateur
```

- **Décidé** : ES modules natifs (`engine`, `geometry`, `model`, `scene`,
  `svg-renderer`), sans build ni dépendance, servis par routes fixes ; testés
  hors DOM par `node --test` piloté par pytest. CSP inchangée.
- Implémenté : `GraphicScene` (nœuds, arêtes), validation stricte d'un contenu
  non fiable, géométrie `Point`/`Rect`, renderer SVG sans balisage injecté,
  sélection simple (clic, Entrée, Espace, Échap), incidence directe, instances
  isolées avec cycle de vie explicite (`destroy`).
- `Node` porte `rect`, `lines`, présentation bornée et `data` opaque ; `Port`,
  routes calculées, grille, transformations, commandes et historique restent à
  implémenter (tickets suivants).
- Premier client : Route Explorer, par un adaptateur qui garde tout le
  vocabulaire métier ; un témoin générique test-only (A → B, A → C) prouve
  l'indépendance du moteur.
- Le layout reste fourni par le client (scène déjà positionnée) ; aucun
  layout universel.

## Deuxième client réel — FD-GRAPHICS-003

Entity Explorer passe par le même moteur (mêmes cinq modules) avec son propre
adaptateur (`web/entity_graph_scene.py`) et son propre client
(`/entity-graph.js`). Résultat : l'API de FD-GRAPHICS-002 suffisait pour les
nœuds, arêtes, libellés, pivots (nœuds ordinaires) et **arêtes parallèles**,
déjà conservées et indexées. Une seule extension, générique : `data` opaque
sur les arêtes et `engine.edge(id)`, pour qu'un panneau décrive les arêtes
incidentes. Le moteur ne connaît ni entité, ni relation, ni pivot (test de
vocabulaire). Sérialisation commune extraite dans `web/graphics.py`.

## Questions reportées

| Question | Ticket attendu |
|---|---|
| Langage et forme des modules | **Tranché par FD-GRAPHICS-002** : ES modules natifs, sans build |
| Layout générique (hiérarchique, force, orthogonal) | Ultérieur |
| Représentation des entrées d'historique (inverse ou instantané) | FD-GRAPHICS-005 |
| Choix du renderer (SVG, Canvas, hybride) | FD-GRAPHICS-004 |
| Re-projection complète ou incrémentale | FD-GRAPHICS-005 |
| Routage de recours (A\*) et évitement d'obstacles complet | Après FD-GRAPHICS-003 |
| Annotations graphiques, rappels, trait libre | Quand un domaine en a besoin |
| Groupes, verrous, alignement, pivot commun de rotation | FUTUR |
| Miroir, rotation libre, redimensionnement | FUTUR |
| Ports flottants (accroche n'importe où sur le bord, UML) | À étudier avec UML |
| Convergence des graphes en lecture seule existants (routes, entités, debug) vers les primitives communes | À étudier ; aucune migration imposée |
| Provenance et licence des symboles SVG DrawCiel | Avant toute reprise de symboles |
| Script de rapport de delta DrawCiel | Si le besoin se confirme |
