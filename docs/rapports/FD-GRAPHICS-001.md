# Rapport — FD-GRAPHICS-001

Statuts : **observé**, **décidé**, **reporté**. Pour DrawCiel, chaque constat
est aussi daté : **historique** (audit antérieur), **encore vrai**,
**corrigé depuis**, **nouveau**. Documents normatifs produits :
[Graphic Core](../graphics/graphics-core-contract.md) et
[Référence DrawCiel](../graphics/drawciel-reference.md).

## Ticket et objectif

Définir, avant FD-CIRCUIT-002, le **plus petit noyau graphique commun** aux
futurs outils graphiques (Circuit, Flowchart, Network, UML/schémas
fonctionnels), en capitalisant sur DrawCiel vivant, et établir une procédure
durable pour que ses évolutions continuent d'alimenter Forge Design. Ticket
d'audit, d'architecture et de stratégie : aucun code produit.

## État Git initial Forge Design

```text
$ git log -1 --oneline
233e146 docs: cadrer le Tool Circuit à partir de DrawCiel (FD-CIRCUIT-001)
$ git rev-parse origin/main
233e146e4f0019624af2181c962cbdd5af5ca82d
$ git status --short
 M docs/rapports/FD-CONTRACT-001.md
```

Baseline conforme ; `FD-CONTRACT-001.md` conservé hors commit.

## Référence DrawCiel précédente

`DRAWCIEL_REFERENCE_PREVIOUS` = `c229b2ed` (FD-CIRCUIT-001).

## Référence DrawCiel courante

`git fetch` dans la copie SéquenCiel (aucune autre opération sur ce dépôt) :

```text
origin/main = c229b2ed  2026-10-02  feat(drawciel): regrouper les annotations en cinq outils
HEAD local  = aac36b27  2026-10-03  feat(drawciel): intégrer et qualifier le profil expérimental UNO R4
              (commit local non publié ; ?? livrables/ préexistant)
```

`DRAWCIEL_REFERENCE_CURRENT` = **`c229b2ed`**, figée pour ce ticket : la
procédure retient `origin/main` ; un commit non publié peut être réécrit.
Les fichiers ont été lus au commit de référence (`git archive c229b2ed` dans
le répertoire temporaire de session), pas dans la copie de travail.

## Delta DrawCiel

- **Publié** (`c229b2ed..origin/main`) : vide.
- **Local non publié** (`c229b2ed..aac36b27`, examiné pour détecter une
  correction critique) : 564 fichiers, essentiellement profil UNO R4
  (ADR-287 à 306, `r4-*.js`, `i2c-bus.js`, `spi-bus.js`, `tools/drawciel_r4/`,
  `tools/drawciel_renode/`, tests R4). Dans `app.js` : cas particuliers par
  identifiant de carte R4 (résolution des bornes, palette, simulation,
  instruments). **Aucun changement** de géométrie, routage, sélection,
  historique ou export. Impact : nul sur le noyau ; constat *nouveau* consigné
  (nouvel aiguillage par identifiant de type) ; à reprendre au prochain ticket
  une fois publié.

Constats par rapport aux audits antérieurs :

| Constat | Statut |
|---|---|
| `component.state` mêlant état physique et document (DC-016-00) | **Corrigé depuis** (DC-015-25) ; `commandPosition` y reste : **encore vrai** |
| Classification électrique par nom ou regex | **Corrigé depuis** (DC-015-24) pour l'électricité ; **encore vrai** dans le routage (`19_cartes_developpement__arduino_uno_r3` dans `smartPoints`, `routeObstructed`) ; **nouveau** pour R4 (commit local) |
| Deux constructions de graphe concurrentes | **Corrigé depuis** (DC-015-23, ADR-262) |
| Escaliers et désorganisation du routage au déplacement | **Corrigé depuis** (DC-015-FINAL) |
| `restore()` sans notification de modification (FD-SPECIALIZED-001, « à confirmer ») | **Corrigé depuis** : `restore()` émet `drawciel:change` si l'état change |
| Version native `0.15.0` filtrée à la persistance | **Encore vrai** |
| Jonctions automatiques en faux composant | **Encore vrai** |
| Définitions personnalisées recopiées en stockage local | **Encore vrai** |
| Historique par instantanés JSON complets, non borné | **Encore vrai** (constat de ce ticket) |
| Bornes hors grille (0/359 sur la grille de 20 px à 90 px) | **Encore vrai** (constat de ce ticket) |
| Sémantique de `wire.points` variable selon `autoRoute`/`routeLocked` | **Encore vrai** (constat de ce ticket) |
| Graphe unique, contrats de bornes, session isolée, SimulationIR, SPICE, cosimulation | **Nouveau** depuis DC-016-00 |

## Fichiers DrawCiel examinés

Au commit `c229b2ed`, dans `static/vendor/drawciel/js/` :

| Fichier | Taille | Rôle |
|---|---|---|
| `app.js` | 267 Ko | Monolithe : éditeur, scène SVG, géométrie, routage, sélection, historique, inspecteur, export, instruments, TP, simulation UI |
| `model.js` | 33 Ko | `TerminalModel`, `ComponentModel`, `NetModel`, `CircuitModel`, `buildElectricalGraph` |
| `electrical-contracts.js` | 282 Ko | Contrats générés : `profiles`, `models` (94), `definitions` (182) |
| `components-data.js` | 172 Ko | 160 définitions de données : id, nom, catégorie, SVG 512², bornes |
| `simulation.js` | 67 Ko | Snapshot, moteur pédagogique, résultats |
| `simulation-ir.js`, `simulation-translation-policy.js`, `spice-netlist.js` | 25 + 5 + 8 Ko | IR, politique de traduction, sérialiseur SPICE |
| `tp.js` | 28 Ko | TP |
| `cosim-core.js`, `avr-adapter.js`, `mcu-ui.js`, `board-definitions.js`, `serial-terminal.js`, `readouts.js` | — | Microcontrôleurs, cosimulation |

Ainsi que `static/drawciel-cadre.js`, `static/drawciel-hote.js`,
`static/vendor/drawciel/README.md` et `INTEGRATION.md`, et les outils
`tools/drawciel-catalogue.cjs`, `tools/drawciel-traductibilite.cjs`,
`tools/drawciel-spice/`.

Fonctions lues en détail dans `app.js` : `snap`, `point`, `viewportWorld`,
`localTerminal`, `endpoint`, `terminalLocalSide`, `rotateSide`, `terminalPort`,
`componentBox`, `simplifyExact`, `segmentHitsBox`, `obstacleScore`,
`fallbackBetween`, `astarGrid`, `normalizeOrthogonalPath`, `smartPoints`,
`orthogonalizeCore`, `cleanRoute`, `routeObstructed`, `storeCleanRoute`,
`adaptedRoute`, `wirePoints`, `prepareStableRoutesForMove`,
`translateInternalWireRoutes`, `moveWireSegmentStable`, `repairManual`,
`createAutoJunction`, `splitWireAtPoint`, `cleanupAutoJunctions`, `commit`,
`recordHistory`, `copySelection`, `pastePayload`, `finishSelectionRect`,
`rotateSelection`, `align`, `componentDefaultSize`, `invertComponentConnections` ;
dans `model.js` : `ComponentModel.terminalPosition`.

## Tests DrawCiel examinés

- Node hors DOM (`tests/*.cjs`) : `drawciel-graph` (16), `-contracts` (13),
  `-session` (14), `-numerique` (32), `-simulation-ir` (42), `-spice` (13),
  `-traductibilite` (5), ainsi que `-condensateurs`, `-relais-contacteurs`,
  `-arduino`, `-cosim`, `-uart` (nombre d'appels `test(` indiqué).
- Navigateur (`tests/browser/`, 31 scénarios) : notamment `drawciel-routage`,
  `-graphe`, `-interface`, `-plan-travail`, `-annotations`, `-texte`,
  `-rappel`, `-trait-libre`, `-sources`, `-ac`, `-rendus`, `-insertion`,
  `-inspecteur`, `-saisie-proprietes`, `-session`, `-ohmmetre`.
- Fixtures : `tests/fixtures/drawciel/` (circuits A–J, définitions, références),
  `drawciel_015/` (illustration, circuit, natif, TP, tentative),
  `drawciel_annotations/`, `drawciel_spice/`, `drawciel_arduino/`, `drawciel_avr/`.

**Observé** : géométrie, routage, sélection et historique ne sont couverts
**que** par des scénarios navigateur ; aucun test pur n'isole ces algorithmes.

## ADR examinées

Décisions relues : ADR-262 (graphe électrique canonique), ADR-265 (session de
simulation et résultats par branche), ADR-268 (IR de simulation et adaptateurs),
ADR-286 (capture oscilloscope par l'hôte). Les autres (255 à 285 : intégration,
bibliothèque, sources, bornes ADR-264, numérique ADR-266, relais ADR-267,
ngspice ADR-269 à 271, microcontrôleurs ADR-272 à 285) sont couvertes par les
rapports DC-015-23 à 32 et DC-016-01 à 12 déjà exploités par FD-CIRCUIT-001.
Aucune ADR de routage dédiée : la décision est dans DC-015-FINAL.

## Architecture DrawCiel courante

```text
index.html ── app.js (état global : components, wires, texts, annotations, page,
             │         selection, history, zoom, pan, simulation…)
             ├── scène SVG (svgEl / innerHTML, render() complet)
             ├── routage, sélection, historique, export (dans app.js)
             ├── model.js ── buildElectricalGraph ── electrical-contracts.js
             ├── simulation.js ── snapshot ── SimulationEngine ── résultats
             ├── simulation-ir.js ── spice-netlist.js ── (worker ngspice côté serveur SéquenCiel)
             ├── cosim-core.js / avr-adapter.js / mcu-ui.js
             └── tp.js
drawciel-cadre.js ⇄ postMessage ⇄ drawciel-hote.js ⇄ routes /drawciel (SQL)
```

**Observé** : la chaîne électrique et de simulation est désormais découplée
(entrées gelées, contrats explicites, tests hors DOM) ; la couche graphique ne
l'est pas : elle réside entièrement dans `app.js`, lit des globales et ne
dispose d'aucun test pur.

## Responsabilités graphiques

| Responsabilité DrawCiel | Générique graphique | Circuit | Simulation | SéquenCiel | À étudier |
|---|---|---|---|---|---|
| Coordonnées monde, viewport, zoom, pan | ✔ | | | | |
| Grille, aimantation | ✔ (paramétrée) | Grille obligatoire | | | |
| Sélection simple, multiple, rectangle | ✔ | | | | |
| Déplacement, rotation | ✔ | Rotations admises | | | |
| Miroir, redimensionnement | FUTUR | | | | ✔ |
| Ports / points d'accroche | ✔ | Bornes, rôles | | | |
| Arêtes, routes, routage orthogonal, édition de segment | ✔ | Mode orthogonal | | | |
| Jonctions | | ✔ | | | |
| Texte | ✔ | | | | |
| Formes, rappels, trait libre | FUTUR | | | | |
| Copier/coller | ✔ (remappage) | Renumérotation des références | | | Presse-papiers système |
| Groupes, verrous, alignement | FUTUR | | | | |
| Commandes, historique | ✔ | Commandes de domaine | | | |
| Hit-testing, poignées, focus, clavier | ✔ | | | | |
| Export de scène | ✔ | | | Insertion WebP | |
| Minimap | | | | | ✔ |
| Inspecteur | Cadre d'affichage | Propriétés | | | |

## Responsabilités Circuit

Types de composants électriques, rôles des bornes, polarités, propriétés
électriques et unités, jonction électrique, topologie et réseaux (`net_name`,
GND), validation `structure`/`topology`/`electrical-readiness`, mapping vers la
simulation, conversion de catalogue.

## Responsabilités simulation

SimulationIR, solveurs (moteur pédagogique, adaptateur ngspice), état de
session, résultats, mesures et instruments, effets physiques, cosimulation
microcontrôleur.

## Responsabilités SéquenCiel

TP et étapes, élèves, copies, droits, notation, bibliothèque personnelle SQL,
WebP dans les contenus, Arduino pédagogique, téléversement USB, adaptateurs
`drawciel-cadre.js` / `drawciel-hote.js`, capture oscilloscope par l'hôte.

## Concepts Graphic Core

**Décidé** : `GraphicScene`, `Node`, `Port`, `Edge`, `Route`,
`TextAnnotation`, et les primitives `Point`, `Vector`, `Rect`, `Transform` ;
services `OrthogonalRouter`, sélection et hit-testing, commandes et
historique. Rien d'autre n'entre dans le noyau (pas de `Junction`, `Net`,
`Group`, `Layer`, propriétés métier).

## Node

Objet placé : identité de l'objet métier, position, orientation admise,
emprise et présentation opaque, ports fournis par le domaine, drapeau
d'obstacle avec marge, libellés de présentation. Le type métier est inconnu
du noyau.

## Port

Point d'accroche nommé d'un nœud : identifiant, position locale, direction
déclarée (`N`/`E`/`S`/`W`) ou aucune. Position monde = fonction pure.
Compatibilité et cardinalité : domaine. **Observé** : DrawCiel déduit la
direction du bord le plus proche (`terminalLocalSide`) ; heuristique retirée
de l'exécution, conservée seulement comme aide de conversion.

## Edge

Identité, extrémités A et B toujours sur des ports, route, présentation
opaque (marqueurs, libellé). Le noyau connaît un graphe de connexion visuel,
jamais une topologie de domaine.

## Route

**Décidé** : *endpoints = relation ; route = présentation*, règle générique.
Route = points intermédiaires ; extrémités dérivées des ports ; modes
`straight` et `orthogonal`. Croisement ou superposition sans relation.

## Junction

**Décidé** : **Circuit**, pas Graphics.

- Circuit a besoin d'une jonction électrique n-aire ; Network n'a pas de
  sémantique équivalente (un lien réseau relie deux interfaces, un point de
  ramification est un équipement) ; Flowchart exprime une bifurcation par les
  ports d'un nœud Decision.
- Projection : une jonction Circuit devient un `Node` sans obstacle portant un
  port omnidirectionnel qui accepte plusieurs arêtes ; ces deux propriétés
  (direction absente, cardinalité décidée par le domaine) sont génériques.
- Le mécanisme DrawCiel (faux composant, découpe et nettoyage automatiques)
  est DEPRECATED ; le besoin reste Circuit, par commandes explicites.
- `Net` reste également Circuit.

## Annotation

`TextAnnotation` est commune. Formes, rappels et trait libre : FUTUR, sur le
modèle des tickets DC-015-01, 02, 07, 08, 12.

## Géométrie

Coordonnées monde indépendantes du viewport ; nombres finis ; entiers si le
domaine l'exige, avec comparaisons exactes. Rotation par quarts de tour en
arithmétique exacte. **Observé** : `terminalPosition` utilise `cos`/`sin` et
le repère symbole 512, et aucune borne ne tombe sur la grille à la taille par
défaut ; le routage compense par des raccords (stub + ancre) — option
conservée pour les domaines sans grille obligatoire. Grille supportée, non
imposée (`grid_step`, `grid_required`).

## Sélection

Hétérogène (identités de scène), simple, multiple, rectangle par inclusion,
hit-testing géométrique avec priorité port > nœud > arête > texte.
**Observé** : DrawCiel tient quatre sélections distinctes par nature et
s'appuie sur des cibles DOM (`data-uid`) ; le rectangle étend la sélection aux
groupes.

## Commandes

Intentions génériques (`MoveNodes`, `RotateNodes`, `SetRoute`,
`MoveRouteSegment`, `ResetRoute`, `MoveText`, `SetTextPresentation`,
`RemoveObjects`, `AddObjects`) appliquées au **document métier** par
l'adaptateur de domaine, qui peut refuser. Commandes sémantiques (relier,
insérer une jonction) : domaine, même contrat, même historique.

## Historique

Pile générique de commandes atomiques, bornée, runtime ; un geste = une
entrée ; `dirty` signalé, révision/sauvegarde/conflit à l'hôte.
**Observé** : DrawCiel enregistre un instantané JSON complet par entrée sans
borne — REWRITE.

## Routage

**Décidé** : `OrthogonalRouter`, service pur (ports de départ et d'arrivée
avec direction, obstacles, grille, route précédente, mode → points
intermédiaires).

Ce qui est déjà générique dans DrawCiel : `simplifyExact`, `segmentHitsBox`,
la génération et le classement des candidats de `cleanRoute`, la contrainte
`outward`, l'adaptation de `adaptedRoute`, la translation de
`translateInternalWireRoutes`, le déplacement de segment de
`moveWireSegmentStable`, `normalizeOrthogonalPath`, `orthogonalizeCore`,
`astarGrid` (file de priorité binaire) et `fallbackBetween`.

Ce qui dépend du modèle électrique ou du catalogue : `isAutoJunction`, les
identifiants de type Arduino, `defOf`, le repère symbole 512 de
`terminalLocalSide`.

Ce qui dépend du DOM ou de l'état global : `components`, `wires`, `page`,
`snapStep`, `zoom`, `$('#snapToggle')`, `simulationMode`/`simMcuRoutes` dans
`wirePoints`, `deep`, `storeManualPath`.

Conclusion : **extractible** en fonctions pures paramétrées, sans réécriture
conceptuelle ; tolérances `.01` remplacées par des comparaisons exactes en
coordonnées entières.

## Renderer

SVG reste le **candidat naturel** 2D (vectoriel, texte, DOM objet,
accessibilité, export, réutilisation DrawCiel, cohérence avec les SVG serveur
de Forge Design, symboles DrawCiel sans `style` ni script : 0/160), sans être
imposé : le noyau parle à un adaptateur de rendu ; Canvas reste possible pour
minimap ou grands volumes. Choix : FD-GRAPHICS-004, avec le coût de
récupération du code DrawCiel comme critère majeur. Export depuis le modèle,
pas par clonage du DOM (`cleanSvgClone` : REWRITE).

## Frontière document métier / scène

**Décidé** : le domaine fournit `project(document) → GraphicScene` (pur,
déterministe) et `apply(document, intention) → document' | refus`, plus ses
commandes sémantiques et la présentation de ses types. La scène est dérivée,
reconstructible, jamais écrite ; aucun `GraphicsDocument` persistant.
Graphics publie seulement des **conventions de champs** (placement, extrémités,
route, texte) que chaque format peut adopter.

## Flowchart

Start/End, Process, Decision (ports `true`/`false`), Input/Output, transitions
avec flèche et libellé : représentables avec `Node`, `Port`, `Edge` et la
présentation opaque ; bifurcation = port de Decision ; validation Flowchart
hors noyau. **Aucune notion Circuit nécessaire.**

## Network

Router, Switch, Host, Server (`Node`), interfaces (`Port`), liens (`Edge`
droits ou orthogonaux), libellés de présentation. Simulation réseau parallèle
(`NetworkDocument → NetworkTopology → NetworkSimulation`), hors noyau. Lien
vers une interface non choisie : port « corps » fourni par le domaine.

Troisième contrôle, **UML / schéma fonctionnel** : classes à compartiments et
blocs fonctionnels révèlent deux limites assumées du noyau V1 — nœuds
redimensionnables avec texte multi-ligne intérieur, et ports « flottants »
(accroche n'importe où sur le bord). Les deux sont FUTUR / à étudier ; aucune
primitive actuelle n'est trop spécifique à Circuit.

## 3D

Graphic Core **explicitement 2D** ; la 3D aura son moteur. Principes partagés
seulement : projection sans double état, commandes et historique, hôte
responsable des ressources.

## Matrice de réutilisation DrawCiel

| Sous-système | État actuel (`c229b2ed`) | Classe | Raison | Fichiers sources | Tests associés | Risque | Destination |
|---|---|---|---|---|---|---|---|
| Viewport, zoom, pan | `zoom`, `pan`, `viewportWorld`, `point`, `fit`, `zoomAt`, historique de vue | ADAPT | Concepts justes, lus depuis le DOM (`getBoundingClientRect`) | `app.js` | `drawciel-plan-travail`, `-interface` | Couplage DOM | Graphics |
| Grille / aimantation | `snap`, `snapGridPoint`, `snapStep = 20`, case `snapToggle` | EXTRACT | Pur une fois le pas paramétré | `app.js` | `drawciel-plan-travail` | Aimantation désactivable incompatible avec `grid_required` | Graphics |
| Sélection | Quatre sélections par nature, rectangle avec groupes | ADAPT | Besoin juste, modèle hétérogène à unifier | `app.js` (`finishSelectionRect`, `clearSelection`…) | `-interface`, `-inspecteur` | Régressions d'ergonomie | Graphics |
| Glisser | `startComponentDrag`, `workspacePointerMove`, `endPointer` | REWRITE | Geste et modèle mêlés dans les gestionnaires DOM | `app.js` | `-routage`, `-interface` | Perte des garanties de stabilité | Graphics (interaction + commande) |
| Rotation | `rotateSelection` (+90 par nœud), `terminalPosition` trigonométrique | ADAPT / REWRITE | Comportement repris ; calcul exact entier | `app.js`, `model.js` | `-sources`, `-ac` | Résidus flottants | Graphics |
| Ports | `terminalPort`, `terminalLocalSide`, `rotateSide`, repère 512 | ADAPT | Direction déclarée au lieu de déduite ; stub optionnel | `app.js` | `-routage`, `-contrats` | Bornes hors grille | Graphics (+ conversion catalogue) |
| Fils / arêtes | `makeWire`, `a`/`b` = {composant, borne}, `points`, `autoRoute`, `routeLocked`, `label`, `net_name`, `color` | ADAPT | Extrémités réutilisables ; `points` ambigu | `app.js` | `-graphe`, `-routage` | Migration des anciennes routes | Graphics (présentation) + Circuit (`net_name`) |
| Routage orthogonal simple et stabilité | `cleanRoute`, `adaptedRoute`, `translateInternalWireRoutes`, `moveWireSegmentStable`, `simplifyExact`, `segmentHitsBox` | **EXTRACT** | Géométrique, indépendant de l'électricité après découplage | `app.js` | `-routage` (circuit terrain, 3/2/3/2, ≤ 4 points, non-incidence, undo/redo) | Globales, cas Arduino, tolérances | Graphics `OrthogonalRouter` |
| Routage de recours | `astarGrid`, `fallbackBetween`, `obstacleScore` | ADAPT | Utile, coût et obstacles à paramétrer | `app.js` | Indirects | Performance sur grandes pages | Graphics (FUTUR) |
| Jonctions | Faux composant `__drawciel_auto_junction__`, `splitWireAtPoint`, `cleanupAutoJunctions` | DEPRECATED (mécanisme) / DOMAIN-ONLY (besoin) | Topologie modifiée implicitement | `app.js` | `-graphe` (F, G) | Import des anciens schémas | Circuit |
| Annotations | `texts` (+ rappel), `annotations` (formes, trait libre), cinq outils | ADAPT | Qualifiées, neutres ; texte d'abord | `app.js` | `-annotations`, `-texte`, `-rappel`, `-trait-libre` | Volume fonctionnel | Graphics |
| Undo/redo | Instantanés JSON complets non bornés | REWRITE | Mémoire, granularité | `app.js` (`commit`, `recordHistory`, `restore`) | `-routage`, `-saisie-proprietes` | Regroupement des saisies | Graphics |
| Copier/coller | Remappage UID et groupes, renumérotation, `localStorage`, presse-papiers système | ADAPT | Remappage générique ; référence = domaine ; pas de stockage local du document | `app.js` (`copySelection`, `pastePayload`) | `-sources`, `-ac` | Fuite de contenu vers le stockage | Graphics + Circuit |
| Renderer | `render()` complet, `svgEl`, `innerHTML` | REWRITE | Rendu monolithique lié à l'état global | `app.js` | `-rendus` | Performance, CSP | Renderer adapter |
| Export | `cleanSvgClone`, `exportRaster`, recadrage serré | REWRITE | Export depuis le DOM vivant | `app.js` | `-rendus`, `-insertion` | Écarts écran/export | Graphics (export de scène) |
| Catalogue | 160 définitions de données + 22 en code (`powerDefs`, `extraDefs`, `internalDefs`) ; 182 contrats générés | ADAPT | Conversion contrôlée, pas de saisie manuelle | `components-data.js`, `electrical-contracts.js`, `tools/drawciel-catalogue.cjs` | `drawciel-contracts` (13) | Provenance des SVG, bornes hors grille | Catalogue Circuit |
| Modèle électrique | `ComponentModel`, `TerminalModel`, contrats de bornes, rôles, polarités | ADAPT | Contrats explicites de référence | `model.js`, `electrical-contracts.js` | `drawciel-contracts` | Identifiants de bornes à aligner | Circuit |
| Topologie | `buildElectricalGraph`, identité de réseau par membres triés | ADAPT | Algorithme et invariants validés (A–J, permutations) | `model.js` | `drawciel-graph` (16), `-graphe` | Double implémentation JS/Python | Circuit |
| SimulationIR | Constructeur pur, validateur, empreinte, schéma 1.0 | ADAPT / DOMAIN-ONLY | Pur et testé ; lit le snapshot DrawCiel | `simulation-ir.js`, `simulation-translation-policy.js` | `drawciel-simulation-ir` (42) | Dépendance au format de snapshot | Simulation Circuit |
| Sérialiseur SPICE | `ngspice-44-subset`, mapping inverse | ADAPT / DOMAIN-ONLY | Déterministe, liste fermée | `spice-netlist.js` | `drawciel-spice` (13) | Version ngspice | Simulation Circuit |
| Adaptateur ngspice | Worker isolé, service multi-utilisateur, API | ADAPT | Contexte serveur ≠ poste local Forge Design | `tools/drawciel-spice/` | `-spice-integration`, `-spice-http` | Isolation à requalifier | Simulation Circuit (futur) |
| Moteur pédagogique | Snapshot → `SimulationEngine` → résultats ; effets physiques | ADAPT | Actif à préserver par adaptateur | `simulation.js` | `drawciel-session` (14), `-numerique` (32) | Taille, couplages UI résiduels | Simulation Circuit (futur) |
| Mesures / instruments | Multimètre, ohmmètre, oscilloscope dans `app.js` | ADAPT | Logique de mesure à séparer de l'UI | `app.js`, `readouts.js` | `-ohmmetre`, `-session` | Couplage UI fort | Simulation Circuit (futur) |
| Arduino / cosimulation | avr8js, cosimulation, terminal série, R4 (local) | SEQUENCIEL-ONLY (pédagogie) / À ÉTUDIER (technique) | Hors Phase 10 | `cosim-core.js`, `avr-adapter.js`, `mcu-ui.js` | `drawciel-cosim`, `-arduino` | Volume et dépendances | — |
| TP | `tp.js`, signature | SEQUENCIEL-ONLY | Pédagogie | `tp.js` | `test_drawciel.py` | — | — |
| Adaptateurs hôte | `drawciel-cadre.js` ⇄ `drawciel-hote.js`, `postMessage`, routes SQL | SEQUENCIEL-ONLY (code) / ADAPT (protocole) | Protocole utile à l'intégration hôte future | `static/drawciel-*.js` | `-identite-source`, `-bibliotheque` | Couplage DOM | Référence d'intégration |

Aucun élément n'est classé REUSE-AS-IS **au sens strict** : même les modules
purs (IR, SPICE) lisent des structures propres à DrawCiel. Les plus proches
sont `simulation-ir.js` et `spice-netlist.js`.

## Catalogue DrawCiel

**Observé** :

- `components-data.js` : tableau JSON assigné à `window` (160 définitions :
  `id`, `name`, `category`, `categoryName`, `file`, `svg` 512², `terminals`).
  0 attribut `style`, 0 script, 0 `href` ; 77 symboles contiennent du `<text>`.
- 22 définitions supplémentaires en code dans `app.js` (alimentations,
  laboratoire, générateur, supercondensateur, jonction interne) ; SVG produits
  par des fonctions.
- `electrical-contracts.js` : généré par `tools/drawciel-catalogue.cjs` ;
  182 définitions avec rôles, polarités, symétrie, connexions internes,
  branches, commandes, capacités et limites ; 94 modèles ; profils de
  propriétés (clé, unité, défaut, domaine, obligation).
- Bornes : 359 dans les données ; 200 sur des multiples de 64 dans le repère
  512 ; **aucune** sur la grille monde de 20 px à la taille par défaut.
- Provenance : archive `DrawCiel_V0.15.0.zip` fournie par le porteur
  (SHA-256 dans `INTEGRATION.md`) ; origine et licence des symboles SVG non
  documentées.

**Décidé** — stratégie :

```text
inventaire automatique (données + contrats, au commit de référence)
→ caractérisation (bornes, rôles, polarités, propriétés, capacités, alignement grille)
→ sélection des types Circuit (8 en V1)
→ conversion contrôlée (identité, bornes, rôles, propriétés : automatique ;
   symbole renormalisé sur la grille et direction des ports : proposés puis revus)
→ rapport de conversion avec provenance
```

Un **outil de conversion DrawCiel catalog → Circuit catalog** est réaliste :
les deux sources sont des données lisibles par machine. Part automatisable :
identités, noms, catégories, bornes, rôles, polarités, profils de propriétés,
capacités (≈ 100 % pour les 160 définitions de données). Part semi-automatique :
géométrie des symboles (renormalisation sur la grille, direction des ports,
nettoyage des SVG) avec revue par type. Part manuelle : les 22 définitions en
code et toute sémantique non contractuelle. Pour 8 types en V1, l'outil
n'est rentable que s'il sert aussi aux extensions ; il est conçu dans
FD-CIRCUIT-003 et ne recopie jamais les 181 définitions à la main.

## Simulation DrawCiel

**Observé** — chaîne courante :

```text
document DrawCiel
→ buildElectricalGraph (model.js, contrats explicites)
→ buildSimulationSnapshot (simulation.js, gelé)
   ├── SimulationEngine pédagogique → SimulationResults (par réseau, branche, composant)
   └── SimulationIR 1.0 (simulation-ir.js) → spice-netlist.js (ngspice-44-subset)
       → worker ngspice isolé (tools/drawciel-spice, serveur SéquenCiel) → mapping inverse
```

**Décidé** : cet ensemble est un **actif à préserver** ; il appartient à
Circuit / Simulation, jamais à Graphics. Pour qu'il reste réutilisable, le
format Circuit (FD-CIRCUIT-002/003) doit fournir : identités stables de
composants, identifiants de bornes et rôles alignés sur les contrats DrawCiel,
propriétés SI de mêmes clés et unités lorsque la sémantique est identique, état
de conception des commandes explicite, GND explicite. Deux backends futurs
peuvent alors coexister, sans décision ici :

```text
Circuit Simulation IR ──▶ adaptateur dérivé du moteur pédagogique DrawCiel
                     └──▶ adaptateur ngspice
```

Classement : graphe électrique ADAPT (Circuit) ; SimulationIR ADAPT /
DOMAIN-ONLY ; sérialisation netlist ADAPT ; adaptateur ngspice ADAPT
(requalification en poste local) ; tests analytiques (A–J, DC, RC, RL, AC,
potentiomètre, interrupteur) **réutilisables comme fixtures** ; mapping inverse
ADAPT.

## Tests de non-régression à conserver

| Source | Comportement garanti | Candidat de portage |
|---|---|---|
| `tests/browser/drawciel-routage.cjs` + circuit terrain | Escaliers corrigés (3/2/3/2 points), pas de torsion (orthogonalité, pas de colinéaires ni segments nuls), pas de désorganisation au déplacement (≤ 4 points, non-incidents identiques), undo/redo et reprise exacts, neutralité électrique | Tests purs `OrthogonalRouter` (FD-GRAPHICS-003) |
| `tests/fixtures/drawciel_015/b_circuit.json` | Anciennes routes relues sans recalcul | Fixture d'import futur |
| `tests/drawciel-graph.cjs`, `tests/browser/drawciel-graphe.cjs`, fixtures A–J | Croisement sans jonction, jonction, invariance par permutation/déplacement/rotation | Tests topologie Circuit (FD-CIRCUIT-003) |
| `tests/browser/drawciel-sources.cjs`, `-ac.cjs` | Rotation, duplication, undo/redo, reprise | Tests rotation des ports et copier/coller |
| `tests/browser/drawciel-interface.cjs`, `-plan-travail.cjs` | Sélection, modes, grille, page, signature inchangée | Tests sélection et interaction (FD-GRAPHICS-005) |
| `tests/browser/drawciel-annotations.cjs`, `-texte.cjs`, `-rappel.cjs`, `-trait-libre.cjs` | Texte, gestes, historique, neutralité, exports | Tests `TextAnnotation` |
| `tests/browser/drawciel-rendus.cjs`, `-insertion.cjs` | Exports, recadrage | Tests d'export depuis le modèle |
| `tests/drawciel-simulation-ir.cjs`, `-spice.cjs`, `-session.cjs`, `-numerique.cjs` | IR déterministe, refus atomiques, non-mutation, témoins analytiques | Simulation Circuit (FD-CIRCUIT-008+) |

Scénarios à créer lors du portage : rotation des ports (4 orientations,
positions exactes), déplacement de nœud, stabilité de route, croisement sans
relation, édition de segment ; sélection simple, multiple, rectangle,
suppression, copie. Aucun test n'est déplacé par ce ticket.

## Procédure de synchronisation future

Décrite dans [Référence DrawCiel](../graphics/drawciel-reference.md) :
`git fetch` → `origin/main` → delta depuis la dernière référence du journal →
zones surveillées → classement historique / encore vrai / corrigé depuis /
nouveau → règles d'impact → référence figée pour le ticket → consignation
(commit, date, delta, éléments examinés, impacts) et ligne de journal.
Commits locaux non publiés signalés, non retenus. Aucune synchronisation
automatique ; script de delta éventuel plus tard.

## Impact sur Circuit

[`circuit-scope.md`](../circuit/README.md) est complété, sans annuler
de décision :

- frontière Graphics / Circuit en tête du document ;
- routage, géométrie et historique fournis par le Graphic Core, Circuit en
  fixe les règles ;
- jonction confirmée comme concept Circuit, projetée en nœud ;
- bornes : direction déclarée ; renormalisation sur la grille requise lors de
  la conversion ; identifiants et rôles à aligner sur les contrats DrawCiel
  (reporté à FD-CIRCUIT-002/003) ;
- roadmap technique réordonnée et renumérotée ; questions reportées
  réaffectées.

Le contrat des outils spécialisés n'est **pas** modifié : aucune
incompatibilité (la scène n'est pas une ressource ; l'hôte garde la
révision, la sauvegarde et le conflit). Le contrat de stockage n'est pas
modifié.

## Roadmap mise à jour

```text
FD-GRAPHICS-001  contrat du noyau graphique, capitalisation DrawCiel   (ce ticket)
FD-CIRCUIT-002   contrat de ressource Circuit, conventions Graphics adoptées
FD-GRAPHICS-002  primitives géométriques pures, transformations exactes, ports
FD-GRAPHICS-003  routage orthogonal extrait de DrawCiel, témoins portés
FD-CIRCUIT-003   domaine, catalogue V1 (conversion contrôlée), codec, validation, topologie
FD-GRAPHICS-004  étude renderer et interaction (choix)
FD-GRAPHICS-005  scène, projection, sélection, commandes, historique (domaine témoin non électrique)
FD-CIRCUIT-004   projection Circuit → scène, commandes Circuit
FD-CIRCUIT-005   intégration hôte, session, éditeur Web minimal
FD-CIRCUIT-006   export SVG depuis le modèle
FD-CIRCUIT-007   qualification du premier jalon
FD-CIRCUIT-008   étude moteurs et IR Circuit (compatibilité SimulationIR DrawCiel)
FD-CIRCUIT-009   simulation DC minimale
FD-CIRCUIT-010   mesures
```

Justification : le format Circuit peut être figé dès maintenant car les
conventions de placement, d'extrémités et de route sont décidées ; les
primitives et le routage sont extraits tant que la référence DrawCiel est
fraîche et fournissent les règles de grille et de direction nécessaires à la
conversion du catalogue ; le choix du renderer suit un modèle stable ; la
généricité est prouvée par un domaine témoin avant Circuit (sur le modèle de
l'outil témoin de FD-SPECIALIZED-002).

### Décisions obligatoires

| | Question | Réponse |
|---|---|---|
| A | Parties réellement réutilisables | Algorithmes de routage et de stabilité, primitives d'emprise et de simplification, contrats de bornes et de catalogue (données), graphe électrique et ses invariants, SimulationIR, sérialiseur SPICE, témoins analytiques et fixtures A–J, scénarios navigateur comme témoins. Aucun module n'est réutilisable tel quel sans isolement |
| B | À extraire plutôt que réécrire | Routage orthogonal simple (`cleanRoute`, `adaptedRoute`, `translateInternalWireRoutes`, `moveWireSegmentStable`, `simplifyExact`, `segmentHitsBox`), grille/aimantation ; ensuite `astarGrid`/`fallbackBetween`. À réécrire : rendu, export, historique, glisser |
| C | Exclusivement Circuit | Types, bornes et rôles, polarités, propriétés électriques, jonction électrique, `net_name`/GND, topologie et réseaux, validation électrique, catalogue, mapping et IR de simulation |
| D | Noyau Graphics minimal | `GraphicScene`, `Node`, `Port`, `Edge`, `Route`, `TextAnnotation`, `Point`/`Vector`/`Rect`/`Transform`, grille paramétrée, `OrthogonalRouter`, sélection et hit-testing, commandes génériques, historique, viewport, adaptateur de rendu |
| E | Node/Port/Edge/Route bonnes primitives ? | **Oui**, vérifiées sur Circuit, Flowchart, Network et UML ; limites assumées : nœuds redimensionnables et ports flottants (FUTUR) |
| F | Junction | **Circuit**, projetée en `Node` à port omnidirectionnel |
| G | Format persistant propre à Graphics ? | **Non** ; seulement des conventions de champs adoptables par les formats de domaine. Challengé : un format universel créerait un double état et forcerait des domaines trop différents |
| H | Pilotage sans double source de vérité | Le domaine projette `document → scène` (pure, déterministe) ; toute intention est appliquée au document par l'adaptateur, puis re-projetée ; la scène n'est jamais écrite ni persistée |
| I | Routage DrawCiel extractible ? | **Oui** : géométrique ; dépendances à retirer (globales, `isAutoJunction`, identifiant Arduino, repère 512, tolérances) ; témoins dans `drawciel-routage.cjs` |
| J | Part convertible automatiquement du catalogue | Identités, bornes, rôles, polarités, propriétés, capacités des 160 définitions de données : automatique ; symboles (grille, directions, nettoyage) : semi-automatique avec revue ; 22 définitions en code : manuel. Provenance des SVG à établir |
| K | Préserver moteur et IR | Ne rien mettre dans Graphics ; aligner le format Circuit (identités, bornes/rôles, clés et unités, état de commande, GND) sur les contrats DrawCiel ; future IR Circuit compatible avec SimulationIR 1.0 ; deux adaptateurs possibles (pédagogique, ngspice) ; témoins analytiques en fixtures |
| L | Utilisable par Flowchart et Network ? | **Oui**, sans aucune notion Circuit (contrôles sur papier) |
| M | SVG candidat naturel 2D ? | **Oui**, non imposé ; choix par FD-GRAPHICS-004 |
| N | Suivi des évolutions DrawCiel | Procédure de delta par ticket, référence figée, journal dans `drawciel-reference.md` ; pas de synchronisation automatique |
| O | Prochain ticket exact | **FD-CIRCUIT-002 — Contrat de ressource Circuit**, adoptant les conventions de champs du Graphic Core |

## Questions reportées

Langage et forme des modules (JavaScript sans build, à confirmer par
FD-GRAPHICS-002) ; représentation des entrées d'historique ; re-projection
complète ou incrémentale ; choix du renderer ; routage de recours ; annotations
graphiques ; groupes, verrous, alignement, pivot commun ; miroir, rotation libre,
redimensionnement ; ports flottants ; convergence des graphes en lecture seule
existants de Forge Design (Route Explorer, Entity Explorer, Debug Center, qui
dupliquent déjà nœuds, arêtes et layout) ; provenance et licence des symboles SVG
DrawCiel ; script de delta DrawCiel ; reprise du commit R4 une fois publié.

## Fichiers créés

- `docs/graphics/graphics-core-contract.md`
- `docs/graphics/drawciel-reference.md`
- `docs/rapports/FD-GRAPHICS-001.md`

## Fichiers modifiés

- `docs/02-architecture.md` : sous-section « Noyau graphique commun », non
  implémentée.
- `docs/03-roadmap.md` : sous-phase Graphics et ordre révisé de la Phase 10.
- `docs/circuit/circuit-scope.md` : frontière Graphics, routage, géométrie,
  historique, jonction, bornes, roadmap et questions reportées.

Non modifiés : contrat des outils spécialisés, contrat de stockage, code,
tests, SéquenCiel (hors `git fetch`), Forge.

## Validations

| Contrôle | Résultat |
|---|---|
| `git diff --check` | Réussi |
| Tests consommant `docs/` : `tests/test_design_schema.py`, `tests/test_view_contract_schema.py` (lancés hors du dépôt, `--rootdir` ForgeDesign) | 45 réussis |
| Liens et ancres des six documents créés ou modifiés | Vérifiés, aucun lien cassé |
| Suite globale | Non requise : aucun code, runtime ni test modifié |
| MkDocs | Sans objet : aucun `mkdocs.yml` dans Forge Design |
| SéquenCiel | Seul `git fetch` exécuté ; HEAD local et arbre de travail inchangés (`?? livrables/` préexistant) |

Aucune incohérence nécessitant du code n'a été rencontrée.

## État Git final

Avant commit :

```text
$ git status --short
 M docs/02-architecture.md
 M docs/03-roadmap.md
 M docs/circuit/circuit-scope.md
 M docs/rapports/FD-CONTRACT-001.md
?? docs/graphics/
?? docs/rapports/FD-GRAPHICS-001.md
```

Commit unique : `docs: définir le noyau graphique commun depuis DrawCiel (FD-GRAPHICS-001)`,
contenant les six fichiers du ticket. `docs/rapports/FD-CONTRACT-001.md` reste
modifié localement, hors commit. Aucun push.
