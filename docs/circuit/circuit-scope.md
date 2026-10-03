# Circuit — besoins et périmètre

Statut : **normatif** pour la Phase 10 (FD-CIRCUIT-001). Ce document fixe ce
que doit être Circuit avant toute implémentation. Il ne crée ni format, ni
classe, ni dépendance. Les noms employés (`CircuitDocument`,
`CircuitRuntimeState`, `SimulationResult`…) désignent des **responsabilités
conceptuelles**, pas du code existant.

Conventions de lecture :

- **Observé** : constaté dans DrawCiel ou dans ses rapports SéquenCiel.
- **Décidé** : règle de Forge Design pour Circuit.
- **Reporté** : question explicitement renvoyée à un ticket ultérieur.

Circuit est un **outil spécialisé** au sens du
[contrat des outils spécialisés](../specialized-tools/specialized-tool-contract.md) :
il en respecte la séparation ressource / runtime / export, la validation par
niveaux, la discipline de révision et l'absence de pédagogie.

**Frontière Graphics (FD-GRAPHICS-001).** La géométrie, la grille, les
transformations, les nœuds, ports, arêtes et routes, le routage, le texte, la
sélection, les commandes génériques et l'historique relèvent du
[Graphic Core](../graphics/graphics-core-contract.md). Circuit en **configure**
les règles (grille obligatoire, quarts de tour, routes orthogonales) et garde
toute la **sémantique** : types, bornes et rôles, polarité, propriétés,
jonction électrique, topologie, réseaux, validation, simulation. Les décisions
de ce document restent valides ; seules leurs responsabilités d'implémentation
sont réparties entre Graphics et Circuit.

## Objectif

**Décidé.** Circuit permet de produire, dans un projet Forge, des **schémas
électriques exacts** : composants identifiés, bornes explicites, connexions
vérifiables, géométrie sur grille, exports fidèles. La ressource Circuit est une
source éditable et versionnée en zone C, lisible sans le runtime d'édition.

La simulation est une **capacité optionnelle future**, construite sur un
document dont la topologie est déjà exacte. Elle n'est ni un prérequis du
schéma, ni une raison d'altérer son modèle.

## Utilisateurs

| Utilisateur | Besoin principal | Statut |
|---|---|---|
| Développeur Forge | Documenter le câblage d'un montage, d'un banc ou d'un projet IoT dans les sources du projet | Cible V1 |
| Enseignant | Préparer des schémas exacts pour des supports, sujets et corrigés | Cible V1 (production de ressources, pas pédagogie) |
| Créateur de ressource technique | Produire un schéma réutilisable et exportable, versionné avec le projet | Cible V1 |
| Élève | Utiliser des schémas ou en produire dans une application | **Hors Forge Design** : via l'application intégrant Circuit (Phase 12, SéquenCiel) |

Forge Design reste un outil de développeur local : l'élève n'est pas un
utilisateur direct de Forge Design.

## Cas d'usage

| Cas | V1 | Remarque |
|---|---|---|
| Créer un schéma vide dans l'espace de sources Circuit d'un projet | Oui | Création exclusive (`create`) |
| Poser des composants du catalogue minimal, les déplacer, les tourner | Oui | Grille logique, rotation par quarts de tour |
| Relier des bornes, créer une jonction explicite | Oui | Topologie explicite |
| Renseigner références et valeurs électriques | Oui | Valeurs absentes autorisées |
| Vérifier structure, topologie et préparation électrique | Oui | Diagnostics localisés |
| Enregistrer, rouvrir à l'identique, gérer un conflit | Oui | Socle FD-SPECIALIZED-002 |
| Exporter une image vectorielle exacte | Oui | SVG |
| Simuler le circuit, mesurer | Non | Capacité future (§ Simulation) |
| Poser un TP, évaluer une réponse | Non | SéquenCiel |
| Programmer un microcontrôleur | Non | À étudier hors Phase 10 |
| Importer un schéma DrawCiel | Non | Étude ultérieure (§ Compatibilité DrawCiel) |

**Un Circuit sans simulateur a-t-il une valeur suffisante ? Décidé : oui.**

- **Observé** : dans SéquenCiel, le parcours principal de DrawCiel est la
  production d'illustrations insérées comme WebP dans les textes, avec une
  bibliothèque de schémas (ADR-256, synthèse ergonomie, DC-015-FINAL).
  Les retours terrain portent surtout sur le routage, le texte, la
  bibliothèque et les doublons, pas sur l'absence d'un calcul.
- Les trois utilisateurs cibles ont besoin d'un schéma **exact et vérifiable**
  avant d'avoir besoin d'un calcul. Un schéma faux mais simulé n'a pas de
  valeur ; un schéma exact non simulé en a.
- Toute simulation exige de toute façon un document à topologie explicite,
  des bornes contractuelles et une validation : ce socle est le même.

L'hypothèse « éditeur de schéma + topologie explicite + validation structurelle
+ export, avant la simulation » est donc **retenue**, avec deux conditions :

1. le modèle V1 ne doit rien contenir qui empêche une simulation future
   (bornes à rôles, polarité, unités SI, état de conception des commandes) ;
2. l'absence de simulation est annoncée, sans capacité `simulate` déclarée
   ni bouton factice.

## Référence DrawCiel

**Observé.** Sources étudiées (SéquenCiel, lecture seule, HEAD `c229b2ed`) :

| Source | Apport pour Circuit |
|---|---|
| DC-016-00, audit d'architecture (au commit `5a02277d`) | Cartographie du document, du runtime, de l'intégration hôte et des dettes ; repris sans nouvel audit |
| DC-016-01 (tickets), contrat de persistance | Corpus synthétique, `component.state` persisté, version filtrée |
| DC-015-01, 02, 07, 08, 12 | Annotations vectorielles, trait libre, texte, rappels : annotations ≠ électricité |
| DC-015-03, 04, 05, synthèse ergonomie | Identité de la source, bibliothèque, doublons, fermeture des accès externes |
| DC-015-06, 10, 11, 13 | Organisation de l'interface, inspecteur unique, saisie immédiate et historique regroupé, plan de travail |
| DC-015-FINAL | Routage orthogonal : cause des escaliers, stabilité au déplacement, neutralité électrique |
| DC-015-17 à 21 | Ohmmètre en circuit ouvert, cartouches de simulation, potentiels ≠ sources, sources AC |
| DC-015-22, 23 | Audit simulation ; graphe électrique unique, déterministe, validé ; `net_name` ≠ libellé |
| DC-015-24 | Contrat explicite des bornes, rôles, polarités et capacités (fin des heuristiques par nom) |
| DC-015-25, 26 | Session de simulation isolée du document ; validation numérique sans correction silencieuse |
| DC-015-27 | Relais/contacteurs par identité d'appareil persistante |
| DC-015-28 à 32 | SimulationIR, sérialiseur SPICE, banc ngspice isolé, service et API expérimentaux |
| DC-016-01 à 12 (rapports) | Microcontrôleurs, Arduino Uno, avr8js, cosimulation, téléversement : hors Circuit V1 |

**Constat important.** L'audit DC-016-00 décrit DrawCiel au 27 septembre 2026.
Les tickets DC-015-23 à 32, postérieurs, ont corrigé plusieurs dettes qu'il
relevait : graphe électrique unique (ADR-262), contrat explicite des bornes
(ADR-264), résultats de simulation hors du document (ADR-265), IR de simulation
(ADR-268). Le tableau des écarts du
[contrat des outils spécialisés](../specialized-tools/specialized-tool-contract.md#cas-de-référence-drawciel)
reste exact **à la date de l'audit** ; Circuit s'appuie sur l'état le plus récent.
Restent observables au HEAD étudié : `version: '0.15.0'` native, filtrage au
chargement des anciennes clés physiques de `component.state`, position de
commande des interrupteurs stockée dans `component.state.commandPosition`,
jonctions automatiques sous forme de composant `__drawciel_auto_junction__`,
définitions personnalisées recopiées dans le stockage local du navigateur,
grille de 20 px, rotation par pas de 90°.

DrawCiel est une **référence**, pas une cible : aucun fichier (`app.js`,
`model.js`, `simulation.js`, `components-data.js`, `tp.js`, adaptateurs) n'est
copié, importé ou transposé. Ses enseignements sont classés : fonction à
conserver, à améliorer, dette à ne pas reproduire, spécificité SéquenCiel,
hors V1.

## Matrice des capacités

Classes :

- **CORE** : indispensable à l'existence même de Circuit ; présent dès le premier jalon.
- **V1** : attendu dans la première version utilisable, éventuellement après le premier jalon.
- **FUTUR** : utile, reporté à une version ultérieure explicitement planifiée.
- **SEQUENCIEL** : relève de l'application intégrante (pédagogie, élèves, médias), pas de Forge Design.
- **ABANDON** : mécanisme DrawCiel à ne pas reproduire (le besoin peut subsister autrement).
- **À ÉTUDIER** : décision impossible sans étude dédiée.

| Capacité | DrawCiel (observé) | Classe | Justification / décision |
|---|---|---|---|
| Document | Six champs persistés + `version` native filtrée, enveloppe SéquenCiel | CORE | Ressource versionnée, `format_version` observable (fixé : [ressource V0.1](circuit-resource.md)) |
| Catalogue | 181 définitions résolues, contrats explicites (DC-015-24) | CORE (réduit) | 8 types exacts en V1 (§ Composants) ; l'étendue de DrawCiel n'est pas un objectif |
| Placement | Glisser depuis la palette, aimantation à la grille | CORE | Position sur la grille logique |
| Sélection | Simple, multiple, rectangle | CORE | Simple et multiple ; rectangle en V1 |
| Déplacement | Composants, textes, segments ; routes adaptées | CORE | Sans changement de topologie |
| Rotation | `rot = (rot + 90) % 360` | CORE | Quarts de tour uniquement (§ Géométrie) |
| Inversion | `invertComponentConnections` : permute les extrémités des fils selon `swapPairs` | ABANDON | Opération topologique déguisée en geste graphique ; remplacée par une reconnexion explicite |
| Symétrie visuelle (miroir) | Absente | FUTUR | Transformation géométrique pure, distincte de l'inversion ; non nécessaire en V1 |
| Redimensionnement | `w`, `h`, tailles 70/90/120 | FUTUR | Symboles à taille fixe par type en V1 ; redimensionnement réservé à des types déclarés plus tard |
| Bornes | Contrat explicite : ID, rôle, polarité, symétrie (DC-015-24) | CORE | Déclarées par type, jamais déduites du nom ou du dessin |
| Connexions | Fil `a`/`b` = {composant, borne}, points, `autoRoute`, `routeLocked` | CORE | Connexion entre deux extrémités explicites |
| Jonctions | Composant automatique `__drawciel_auto_junction__`, découpe de fil | CORE (redéfinie) | Nœud topologique explicite, jamais un faux composant, jamais créé par simple recouvrement |
| Routage orthogonal | A\*, candidats droite / 1 coude / 2 coudes (DC-015-FINAL) | V1 | Routes orthogonales sur grille ; évitement d'obstacles FUTUR |
| Annotations | Texte, rappel, ligne, flèche, formes, trait libre | V1 (texte) / FUTUR (formes) | Texte libre en V1 ; formes et rappels plus tard ; toujours électriquement neutres |
| Références | `ref` incrémentée, renumérotation au collage | CORE | Référence éditoriale unique par document, distincte de l'identité |
| Grille | `snapStep = 20` px, désactivable | CORE | Grille logique en unités entières, non désactivable en V1 |
| Zoom | Oui | CORE | État runtime |
| Pan | Oui, retour à l'origine | CORE | État runtime |
| Undo/redo | Instantanés JSON ; événements `drawciel:state` / `drawciel:change` divergents | CORE (redéfini) | Commandes atomiques ; toute annulation modifiant le document rend `dirty` |
| Copier/coller | Interne, références incrémentées | V1 | Presse-papiers interne, nouvelles identités ; presse-papiers système À ÉTUDIER |
| Aligner | Absent ou limité | FUTUR | Confort d'édition |
| Grouper | `groupId` | FUTUR | Sans effet topologique ; non requis en V1 |
| Verrouiller | `locked` | FUTUR | Confort d'édition |
| Inspecteur | Inspecteur unique, saisie immédiate (DC-015-10, 11) | CORE | Propriétés de l'objet sélectionné, transaction par champ |
| Propriétés électriques | Profils par modèle, valeurs requises pouvant manquer | CORE | Unités SI, absence explicite, aucun défaut inventé |
| Simulation | Moteur MNA JS + session isolée ; banc ngspice expérimental | FUTUR | Après le jalon d'édition et une étude des moteurs |
| Multimètre | Outil runtime, impédance d'entrée chargeant le circuit | FUTUR | Instrument de la session de simulation |
| Ohmmètre | Mesure hors tension, corrigée en circuit ouvert (DC-015-17) | FUTUR | Même famille que le multimètre |
| Oscilloscope | Sondes, canvas, traces par branche | FUTUR | Exige le transitoire |
| Mesures | Résultats par net, branche, composant, qualité explicite | FUTUR | `SimulationResult` hors du document |
| Effets physiques | Température, dommages, défaillances, luminosité, vitesse | À ÉTUDIER | Couche du simulateur, jamais état du document |
| Validation | Structure serveur, graphe électrique, préparation, TP | CORE (sans TP) | Niveaux `structure`, `topology`, `electrical-readiness` |
| Export | PNG/SVG natifs, WebP via l'hôte, recadrage serré | V1 (SVG) | SVG exact en V1 ; PNG FUTUR ; WebP SEQUENCIEL |
| TP | `tp.js`, étapes, signature, mesures, évaluation | SEQUENCIEL | Pédagogie hors Forge Design |
| Arduino | Uno, avr8js, cosimulation, terminal série, USB | À ÉTUDIER | Domaine microcontrôleur, hors Phase 10 |
| Bibliothèque | Bibliothèque personnelle en base, modèles `.drawcielt` | SEQUENCIEL / FUTUR | La bibliothèque est le projet (zone C) ; modèles réutilisables FUTUR |
| Symboles personnalisés | Import SVG libre + `terminalOverrides` + stockage local | ABANDON (mécanisme) / FUTUR (besoin) | Un composant personnalisé futur passera par un contrat de type explicite |
| Page | `page` : dimensions, guide d'impression, origine, positions des cartouches | V1 (page unique) | Zone de travail bornée ; multipage et cartouche FUTUR |
| Noms de réseau | `wire.net_name`, potentiels nommés, GND (DC-015-23) | V1 (GND) / FUTUR (noms) | Masse GND en V1 ; étiquettes de réseau nommées FUTUR |

## Périmètre V1

**Décidé.** Circuit V1 est un **éditeur de schémas électriques exacts** :

- ressource Circuit versionnée en zone C, lue et écrite par le socle
  `forge_design.specialized` ;
- catalogue minimal de 8 types de composants + jonction explicite ;
- placement, sélection, déplacement, rotation par quarts de tour, suppression,
  copier/coller interne ;
- connexions entre bornes et jonctions, routes orthogonales sur grille ;
- références, valeurs électriques en unités SI, annotations textuelles ;
- validation `structure`, `topology`, `electrical-readiness` avec diagnostics
  localisés ;
- historique annuler/rétablir par commandes atomiques ;
- session d'édition, état `dirty`, sauvegarde avec révision attendue, conflit
  visible ;
- export SVG exact ;
- interface de bureau, au clavier comme à la souris.

## Hors périmètre V1

- simulation, mesures, instruments, effets physiques ;
- TP, évaluation, données élèves, statuts pédagogiques ;
- microcontrôleurs, Arduino, cosimulation, IoT ;
- symboles personnalisés, import SVG, définitions locales au document ;
- redimensionnement de composants, miroir, groupes, verrous, alignement ;
- annotations graphiques autres que le texte ;
- étiquettes de réseau nommées autres que GND, multipage, cartouche ;
- export PNG, WebP, PDF, netlist ;
- import ou export DrawCiel ;
- usage mobile (édition comme consultation).

## Frontière avec SéquenCiel

| Responsabilité | Circuit (Forge Design) | SéquenCiel (application) |
|---|---|---|
| Schéma, composants, bornes, connexions | Oui | Consomme |
| Format de ressource et validation | Oui | Consomme ou adapte (Phase 12) |
| Export image exact | Oui (SVG) | Conversion et insertion WebP dans les textes |
| Bibliothèque de schémas | Le projet (zone C) | Bibliothèque personnelle en base, droits par compte |
| TP, consignes, attendus, notation | Non | Oui |
| Élèves, tentatives, copies, consultation professorale | Non | Oui |
| Simulation pédagogique (effets, dommages, cartouches) | Non en V1 ; capacité future éventuelle | Oui (DrawCiel actuel) |
| Arduino, téléversement, terminal série | Non | Oui |
| Persistance SQL, révisions, droits | Non | Oui |

Une ressource Circuit ne contient **aucune donnée pédagogique, machine ou
d'exécution** : pas d'attendu, pas de résultat, pas d'identifiant d'élève,
pas de mesure, pas d'état de simulation, pas de préférence d'interface.
L'intégration d'une ressource Circuit dans une application (Phase 12) se fait
par l'application, qui associe ses propres données à la ressource sans les y
écrire.

## Concepts invariants

**Décidé.** Ces concepts et leurs relations sont stables quels que soient le
format, le frontend ou le moteur futurs.

| Concept | Responsabilité | Relations |
|---|---|---|
| Document | Racine persistante : version, page, éléments | Contient composants, connexions, jonctions, annotations |
| Composant | Instance placée d'un type du catalogue | A un type, une identité, une référence, une position, une rotation, des propriétés ; expose les bornes de son type |
| Borne | Point de connexion déclaré par le type | Identifiée par (identité du composant, identifiant de borne du type) ; a un rôle et une polarité éventuelle |
| Connexion | Liaison électrique idéale entre deux extrémités | Chaque extrémité est une borne ou une jonction ; porte une route |
| Jonction | Nœud topologique explicite placé sur la grille | Relie plusieurs connexions ; n'a pas de type de catalogue |
| Route | Présentation géométrique d'une connexion | Appartient à une connexion ; n'a aucune autorité électrique |
| Réseau (net) | Ensemble des bornes électriquement reliées | **Dérivé** des connexions et jonctions ; jamais persisté comme autorité |
| Annotation | Élément graphique ou textuel | Électriquement neutre |
| Page | Zone de travail bornée du document | Dimensions en unités de grille |
| Propriété | Valeur typée d'un composant | Graphique, électrique ou éditoriale |
| Référence | Nom visible (R1, D2) | Éditoriale, unique par document, distincte de l'identité |

Règles :

1. Toute entité persistante adressable (composant, connexion, jonction,
   annotation) porte une **identité stable**, unique dans le document, non
   réutilisée dans ce document, indépendante de son indice, de sa position et
   de sa référence. Un indice de tableau est **insuffisant** : il change à la
   suppression et au réordonnancement, et rend l'historique, les diagnostics et
   le mapping de simulation ambigus. **Fixé par FD-CIRCUIT-002** : identités
   `<préfixe>_<jeton>` (`c_`, `e_`, `j_`, `a_`) dans un espace de noms global,
   générées par `secrets` (voir [ressource V0.1](circuit-resource.md#identités)).
2. L'identité d'une borne est le couple (identité du composant, identifiant de
   borne déclaré par le type). Elle ne dépend ni de l'ordre des bornes, ni de
   leur position dessinée.
3. Un réseau est calculé ; son identité canonique dérive de ses membres triés
   (approche validée par DC-015-23), pas d'un nom ou d'un ordre de construction.

## Document / runtime

**Décidé.** Trois responsabilités strictement séparées :

```text
CircuitDocument        persistant, versionné, zone C, seule source de vérité
    │ (lecture seule)
    ├── CircuitRuntimeState    session d'édition, jamais persistée dans la ressource
    └── (futur) SimulationSession → SimulationResult   jamais écrits dans le document
```

| Persistant (`CircuitDocument`) | Runtime (`CircuitRuntimeState`) | Simulation future (`SimulationResult`) |
|---|---|---|
| Version de format | Sélection, survol, outil actif | Tensions, courants, puissances |
| Page | Zoom, pan, vue | Qualité, convergence, diagnostics numériques |
| Composants : identité, type, référence, position, rotation, propriétés | Glisser en cours, aperçu de route | États internes (charges, températures) |
| État de conception des commandes (interrupteur dessiné ouvert/fermé) | Historique annuler/rétablir | Commandes manipulées pendant la simulation |
| Connexions : identité, extrémités, route | Presse-papiers interne | Effets physiques |
| Jonctions : identité, position | Diagnostics de validation affichés | Mesures d'instruments |
| Annotations | État `dirty`, révision attendue | — |

Règles :

- La simulation lit un **instantané** du document et ne le modifie jamais.
  Manipuler un interrupteur en simulation ne change pas son état de
  conception. (**Observé** : DrawCiel conserve encore
  `component.state.commandPosition` et filtre au chargement d'anciennes clés
  physiques sérialisées ; Circuit ne reproduit pas ce mélange.)
- L'état de conception d'une commande est une **propriété** du composant,
  explicite et nommée, pas un état runtime sérialisé.
- Aucune préférence d'interface (familles repliées, positions de panneaux,
  positions de cartouches) n'est écrite dans la ressource.
  (**Observé** : `page.indicatorOffsets` de DrawCiel mêle une préférence
  d'affichage de simulation au document.)

## Composants

**Décidé.** Un **composant** n'est pas un **symbole** :

| Aspect | Porté par |
|---|---|
| Identité de l'instance | Le document |
| Type (résistance, LED…) | Le catalogue, par identifiant stable |
| Symbole (dessin) | La présentation du type ; remplaçable sans changer le modèle |
| Bornes | Le contrat du type : identifiants, rôles, polarité, position locale sur la grille |
| Propriétés | Le profil du type : nom, nature, unité, domaine, obligation |
| Modèle de domaine | Le type (dipôle, source, commande…) ; aucune classification par nom |

Le type est la seule autorité : aucune sémantique n'est déduite d'un nom,
d'un identifiant textuel, d'une expression régulière ou d'un dessin
(**observé** : DrawCiel classait par nom jusqu'à DC-015-24, dette corrigée).

Catalogue V1 (**décidé**) :

| Type | Bornes (rôles) | Polarité | Propriétés électriques | Justification |
|---|---|---|---|---|
| Résistance | `t1`, `t2` | Non (symétrique) | résistance (Ω), puissance nominale (W) | Dipôle de base |
| Source de tension continue (pile) | `positive`, `negative` | Oui | tension (V), résistance interne (Ω) | Source polarisée ; une seule source DC en V1 |
| Interrupteur unipolaire | `t1`, `t2` | Non | état de conception ouvert/fermé | Commande ; teste la séparation conception/runtime |
| Lampe | `t1`, `t2` | Non | tension nominale (V), puissance nominale (W) | Récepteur usuel |
| LED | `anode`, `cathode` | Oui | tension directe (V), courant nominal (A), couleur | Polarité explicite |
| Diode | `anode`, `cathode` | Oui | tension directe (V), courant maximal (A) | Polarité explicite |
| Potentiomètre | `end1`, `wiper`, `end2` | Non | résistance totale (Ω), position du curseur (0–1) | Premier composant à trois bornes |
| Masse (GND) | `ref` | — | — | Référence de réseau ; ne génère aucune énergie |
| Jonction | — | — | — | Nœud topologique, **pas un composant du catalogue** |

Reportés (**FUTUR**) : LDR (sa résistance dépend d'un éclairement, grandeur
d'environnement qui n'appartient pas au document et doit être conçue avec la
simulation), condensateur, bobine, sources AC et de courant, interrupteurs
multipolaires, relais, moteurs, fusibles, instruments comme composants,
étiquettes de réseau nommées.

Les noms d'unités et libellés affichés sont de la présentation ; le modèle
stocke des grandeurs SI.

## Bornes

**Décidé.**

- Les bornes sont **déclarées par le type** : identifiant stable, rôle,
  polarité éventuelle, position locale en unités de grille entières.
- La polarité appartient au **modèle** (rôles `positive`/`negative`,
  `anode`/`cathode`), pas au dessin.
- Une borne est toujours sur un nœud de la grille, quelle que soit la rotation.
- Plusieurs connexions peuvent aboutir à une même borne (V1 : autorisé ; une
  jonction n'est pas obligatoire sur une borne).
- Une borne non connectée est valide structurellement ; elle produit au plus
  un avertissement `electrical-readiness`.
- Une borne est projetée en `Port` du Graphic Core ; sa **direction de sortie
  est déclarée** par le type.
- **Observé (FD-GRAPHICS-001)** : aucune borne du catalogue DrawCiel ne tombe
  sur la grille de 20 px à la taille par défaut ; une conversion de catalogue
  devra renormaliser symboles et bornes sur la grille.
- **Reporté (FD-CIRCUIT-003)** : distinguer identifiant de borne et rôle,
  comme les contrats DrawCiel (`t1` de rôle `terminal_a`, `positive=t1`…), et
  aligner identifiants, clés et unités de propriétés sur ces contrats lorsque la
  sémantique est identique, afin de préserver l'IR de simulation et un import
  futur. Les noms de rôles du tableau précédent restent valables.

## Connexions

**Décidé.**

- Une connexion relie exactement **deux extrémités**, chacune étant une borne
  (composant + borne) ou une jonction. Aucune extrémité libre n'est
  persistée : un tracé inachevé reste runtime.
- Une connexion d'une extrémité à elle-même est refusée.
- Deux connexions entre les mêmes extrémités sont signalées (avertissement
  `topology`), pas fusionnées silencieusement.
- Raccorder un fil **sur un fil existant** n'est possible que par une
  commande explicite « insérer une jonction » : elle crée une jonction,
  remplace la connexion A–B par A–J et J–B, et ajoute la nouvelle connexion
  vers J, en **une seule action d'historique**. Le réseau de A–B est inchangé.
  **Fixé par FD-CIRCUIT-002** : la connexion portant l'extrémité désignée par
  la commande (A) conserve son identité, l'autre en reçoit une nouvelle ; la
  fusion d'une jonction de degré 2 suit la même règle explicite.
- La jonction est un concept **Circuit**, projeté dans la scène comme un nœud
  sans obstacle à un port omnidirectionnel ; elle n'appartient pas au Graphic
  Core (FD-GRAPHICS-001).
- Supprimer une jonction de degré 2 peut fusionner ses deux connexions
  (commande explicite) ; jamais par nettoyage automatique.
  (**Observé** : DrawCiel crée des jonctions automatiques et découpe les fils
  en modifiant la topologie ; Circuit garde le besoin mais rend l'opération
  explicite.)

## Topologie

**Décidé.** La topologie est l'**autorité électrique** ; elle se calcule
uniquement à partir des composants (types, bornes), connexions, jonctions et
masses. Elle exclut coordonnées, routes, rotations, symboles, références et
annotations.

| Situation | Représentation |
|---|---|
| Croisement sans connexion | Deux routes qui se croisent ; aucune jonction ; deux réseaux |
| Jonction connectée | Une jonction, trois connexions ou plus ; un réseau ; point visible |
| Connexion sur une borne | Extrémité = (composant, borne) |
| Connexion sur un fil | Jonction explicite insérée (§ Connexions) |
| Masse | Toutes les bornes `ref` des masses appartiennent au même réseau GND |

Invariants (**décidé**, testables) :

1. Une opération purement graphique (déplacer, tourner, modifier une route,
   zoomer, exporter) **ne change pas** la topologie : la signature
   topologique canonique avant/après est identique.
2. Le recouvrement géométrique (une borne posée sur un fil, deux routes
   superposées) **ne crée jamais** de connexion.
3. Une modification de topologie est toujours le résultat d'une commande
   topologique explicite et visible dans l'historique.
4. La signature topologique est invariante par permutation des collections
   du document.

## Routage

**Décidé.** Le routage est fourni par le service `OrthogonalRouter` du
[Graphic Core](../graphics/graphics-core-contract.md#routage), extrait de
DrawCiel ; Circuit impose le mode orthogonal et la grille. Les règles
suivantes sont celles que Circuit exige de ce service.

- La topologie est l'autorité électrique ; la route est une **présentation**.
  Une route invalide ou absente ne change jamais les réseaux.
- **V1 exige des routes orthogonales** : segments horizontaux et verticaux
  dont tous les points sont sur la grille.
- Une route est la suite ordonnée de ses **points intermédiaires** ; les
  extrémités dérivent des positions des bornes et jonctions et ne sont pas
  dupliquées dans la route. Une route sans point intermédiaire est droite si
  ses extrémités sont alignées, sinon calculée.
- Routage automatique V1 : candidats droite, un coude, puis deux coudes,
  respectant la direction de sortie des bornes, choisis par nombre de coudes
  puis longueur ; points colinéaires et segments nuls supprimés
  (**observé** : c'est la correction validée par DC-015-FINAL).
- Édition manuelle V1 : déplacer un segment perpendiculairement à lui-même.
- Déplacement d'un composant (**décidé**, contre la désorganisation observée
  dans DrawCiel avant DC-015-FINAL) :
  - seules les routes **incidentes** au composant déplacé peuvent changer ;
  - si les deux extrémités bougent ensemble, la route est translatée ;
  - sinon seuls les segments adjacents à l'extrémité déplacée s'adaptent ;
  - la route n'est recalculée que si elle devient non orthogonale ou
    dégénérée ;
  - l'opération est déterministe et réversible par annulation exacte.
- **FUTUR** : verrouillage de route, évitement d'obstacles, re-routage global,
  points manipulés individuellement par poignées.

## Géométrie

**Décidé.** L'exactitude prime sur la liberté au pixel. Les primitives,
transformations et positions monde des ports sont celles du
[Graphic Core](../graphics/graphics-core-contract.md#géométrie) ; Circuit
fixe les restrictions ci-dessous.

- **Coordonnées monde** en unités de grille **entières**, indépendantes du
  viewport, du zoom et de la densité d'écran. Le pas d'affichage de la grille
  est de la présentation.
- La grille est une **grille logique** obligatoire en V1 (pas de
  désactivation de l'aimantation pour les éléments électriques).
- Composants : position = point d'ancrage sur la grille ; rotation ∈
  {0, 90, 180, 270}. La position monde de chaque borne est calculée par une
  transformation entière exacte (rotation par quart de tour + translation) ;
  elle est donc toujours sur la grille.
- **Rotation** (géométrie), **inversion des connexions** (topologie) et
  **miroir visuel** (géométrie) sont trois opérations distinctes. V1 offre la
  rotation seulement ; l'inversion DrawCiel est abandonnée ; le miroir est
  FUTUR.
- Redimensionnement : aucun type de composant V1 n'est redimensionnable.
  Les géométries redimensionnables futures (boîtiers à pas de bornes sur
  grille, annotations rectangulaires) devront déclarer leurs règles de
  placement des bornes. Le texte V1 a une taille de police dans un ensemble
  borné.
- Après déplacement ou rotation, les bornes restent exactes et les
  connexions restent attachées (identité inchangée).

## Propriétés

**Décidé.**

| Nature | Exemples | Effet |
|---|---|---|
| Graphique | Afficher la référence, afficher la valeur, position d'étiquette | Rendu seulement |
| Électrique | Résistance, tension, polarité de source, état de conception | Préparation électrique, simulation future |
| Éditoriale | Référence, note | Documentation |

- Les valeurs électriques sont des nombres finis en **unités SI** ; la saisie
  avec préfixes (k, m, µ) est de la présentation.
- Une valeur technique inconnue est une **absence explicite**. La valeur `0`
  n'est stockée que lorsqu'elle est la valeur déclarée. **Aucune valeur n'est
  inventée** : un composant posé n'a pas de valeur électrique par défaut, sauf
  si le type déclare une valeur intrinsèque.
- Un composant peut exister graphiquement et topologiquement avec une valeur
  électrique manquante ; la sauvegarde est permise ; une simulation future
  pourra le refuser.
- Une propriété inconnue du type est une erreur `structure`.

## Validation

**Décidé.** Niveaux déclarés selon le contrat des outils spécialisés :

| Niveau | Contenu | Bloque l'écriture |
|---|---|---|
| `structure` | Format, version, champs, types connus, identités uniques, propriétés connues et bien typées, coordonnées entières, rotation admise | Oui (obligatoire) |
| `topology` | Extrémités existantes, borne déclarée par le type, pas d'auto-connexion, route orthogonale sur grille ; avertissements : connexion doublée, jonction de degré ≤ 1 | Oui pour les erreurs |
| `electrical-readiness` | Valeurs requises absentes, borne non connectée, source court-circuitée, absence de masse | **Non** (avertissements) |

- La préparation électrique ne bloque jamais la sauvegarde : un schéma en
  cours de conception est légitimement incomplet.
- L'éditeur ne doit pas pouvoir produire une erreur `structure` ou
  `topology` ; ces erreurs protègent contre un fichier modifié à l'extérieur.
- Diagnostics : codes `circuit.<code>`, localisation par identité (jamais
  par indice seul), liste bornée par le socle.
- **Hors périmètre** : validation pédagogique (conformité à un attendu de TP).

## Simulation

**Reporté** : aucune simulation en V1 ni dans le premier jalon. Le moteur
n'est pas choisi.

Inventaire des besoins (**décidé**, classement) :

| Besoin | Classe | Remarque |
|---|---|---|
| Point de fonctionnement DC | Minimal futur | Première analyse utile |
| Sources DC (avec résistance interne) | Minimal futur | |
| Résistances, potentiomètre | Minimal futur | Deux branches pour le potentiomètre |
| Interrupteurs (état figé) | Minimal futur | Commandes interactives en session |
| Lampe | Minimal futur | Modèle simplifié à qualifier |
| Diode, LED | Minimal futur | Modèle explicite requis ; aucun modèle arbitraire |
| Condensateurs, bobines, transitoires | Futur | Conditions initiales explicites |
| Sources AC | Futur | Temporel ≠ AC petit signal |
| Contacts multiples, relais, contacteurs | Futur | Orchestration logique (DC-015-27) |
| Moteurs, fusibles | Futur | Comportement de session |
| Instruments (multimètre, ohmmètre) | Futur | § Mesures |
| Oscilloscope | Futur | Exige le transitoire |
| Défaillances, dommages, thermique | Hors document | Couche du simulateur éventuelle, à étudier |

Frontière (**décidé**) :

```text
CircuitDocument ──(instantané validé)──▶ graphe électrique dérivé
    ──▶ entrée de simulation (IR éventuelle) ──▶ moteur ──▶ SimulationResult
                                                     (mappé par identités)
```

- `SimulationSession` lit un instantané et ne modifie jamais la source.
- Les effets physiques (température, luminosité, dommages) appartiennent au
  simulateur et à ses résultats, jamais au document.
- Un composant non simulable bloque une simulation complète ou produit un
  refus explicite ; jamais un modèle ouvert silencieux ni un export partiel
  (**observé** : DrawCiel traitait les modèles absents comme ouverts avant
  DC-015-24 et refuse atomiquement depuis DC-015-29).

Question **posée, non tranchée** : `CircuitDocument → Simulation IR → moteur`
ou `CircuitDocument → moteur` direct ? **Observé** : DrawCiel a dû introduire
a posteriori un graphe unique, un instantané immuable, une IR et un mapping
inverse (DC-015-23 à 29) pour découpler document, moteur pédagogique et SPICE.
Recommandation pour l'étude : prévoir une frontière de traduction explicite
dès le premier moteur. Aucune IR n'est créée ici.

Critères de l'étude future des moteurs : exactitude, DC, AC, transitoires,
non-linéaire, sources, interrupteurs, mesures, performance, licence,
installation, isolation, déterminisme, API, Linux, tests reproductibles,
fonctionnement hors ligne, dépendance optionnelle par capacité.

Candidats à évaluer, **sans décision** :

- **Moteur MNA JS de DrawCiel** : référence de comportement pédagogique et
  source de témoins analytiques (circuits A–J, DC-015-23 et 26), pas une base
  de code à copier.
- **ngspice** : candidat technique ; SéquenCiel l'a qualifié sur un
  sous-ensemble R/C/L/V/I isolé (DC-015-30 à 32), contexte serveur
  multi-utilisateur différent du poste local de Forge Design. Aucun
  benchmark n'est fait ici.
- Autres (Xyce, moteur propre) : à recenser par l'étude.

## Mesures

**Décidé (pour le futur).**

- Les instruments **outils d'interface** (multimètre, ohmmètre,
  oscilloscope) appartiennent à la session de simulation : leurs sondes et
  réglages sont runtime.
- Un instrument **composant du circuit** (voltmètre, ampèremètre dessinés)
  est un type du catalogue, persisté comme tout composant ; FUTUR.
- Un multimètre ou un ohmmètre réaliste **charge le circuit** (impédance
  d'entrée, source de test) : la mesure modifie le circuit simulé, pas le
  document.
- Une grandeur indéterminée, une non-convergence ou un dépassement donnent
  une qualité explicite, jamais un zéro normal.
- L'oscilloscope est FUTUR (transitoire requis).

## Export

**Décidé.**

- V1 : **SVG** obligatoire. PNG FUTUR. WebP et insertion dans des textes :
  SéquenCiel (Phase 12).
- Un export **n'est pas** une source : il n'est jamais relu pour reconstruire
  le schéma.
- Correspondance exacte : l'export contient exactement les composants,
  connexions, jonctions, annotations et textes du document, aux positions du
  document, sans élément d'interface (sélection, poignées, grille,
  diagnostics) et sans ressource externe (pas de police ni d'image
  distante).
- Recadrage déterministe sur l'emprise du contenu avec une marge fixe ;
  textes échappés.
- L'emplacement des exports dans le projet est **reporté** au ticket d'export.

## Historique

**Décidé.** Le mécanisme d'historique est celui du
[Graphic Core](../graphics/graphics-core-contract.md#historique) ; Circuit y
ajoute ses commandes de domaine (relier, insérer ou supprimer une jonction).

- Toute modification persistante passe par une **commande atomique** :
  un geste utilisateur = une entrée (un glisser complet, une rotation,
  une insertion de jonction avec ses connexions, la saisie d'un champ
  regroupée par champ).
- L'historique est **runtime uniquement**, borné, jamais écrit dans la
  ressource.
- Annuler ou rétablir une modification persistante rend le document `dirty`
  si l'état diffère de l'état enregistré. (**Observé** : dans DrawCiel,
  `restore()` émettait un événement distinct de celui écouté par
  l'autosave ; Circuit n'a qu'une seule notion de modification.)
- Les changements de vue, de sélection et d'outil ne créent pas d'entrée.

## Sessions et sauvegarde

**Décidé.** Cycle :

```text
ouvrir (lecture + validation + révision)
  → session (CircuitRuntimeState)
  → éditer (commandes) → dirty
  → enregistrer (write_specialized_resource avec révision attendue)
  → fermer (avertissement si dirty)
```

- Sauvegarde explicite en V1. Autosave **possible** dans le cadre du contrat
  (session ouverte explicitement) mais non requis en V1.
- Changement externe de la ressource : la révision attendue ne correspond
  plus → **conflit visible**, la session garde les modifications, aucune
  écriture n'écrase le fichier. Choix proposés : recharger (abandonner les
  modifications locales) ou continuer d'éditer. La fusion est hors V1.
- La création utilise l'écriture exclusive du socle ; un fichier existant
  n'est jamais écrasé par une création.

## UI

**Décidé** (zones fonctionnelles, sans choix de technologie) :

| Zone | Rôle |
|---|---|
| Catalogue | Types du catalogue V1, recherche simple |
| Espace de travail | Page, grille, composants, connexions, annotations |
| Barre d'outils | Fichier, historique, sélection, liaison, texte, navigation |
| Inspecteur | Propriétés de la sélection, saisie immédiate |
| Diagnostics | Liste des issues par niveau, navigation vers l'objet |
| Instruments | Réservée à la simulation future ; absente en V1 |

- Commandes prévisibles : chaque commande a un nom, une icône avec nom
  accessible, une infobulle, un raccourci clavier si pertinent.
- L'outil « Liaison » (relier électriquement) est distinct de toute
  annotation graphique (**observé** : confusion fil / ligne dans DrawCiel).
- **Bureau d'abord** ; mobile **hors V1**, consultation comprise.
- Accessibilité de base : utilisable au clavier (sélection, déplacement,
  rotation, suppression, navigation dans les diagnostics), focus visible,
  diagnostics en texte et non par la seule couleur, contraste suffisant.

## Sécurité

**Décidé.**

- La ressource est lue et écrite par l'**hôte** Forge Design
  (`read_specialized_resource` / `write_specialized_resource`) ; le runtime
  d'édition ne lit ni n'écrit jamais le projet directement.
- Le contenu d'une ressource est **non fiable** : validation stricte,
  tailles bornées, textes échappés à l'affichage et à l'export, aucun SVG ou
  script importé, aucune URL suivie.
- Aucune ressource externe, aucun CDN : fonctionnement **hors ligne** complet.
- Aucune donnée pédagogique, personnelle, machine ou runtime dans la ressource.
- Espace de sources en zone C : **fixé par FD-CIRCUIT-002**,
  `mvc/circuit/**/*.circuit.json`, déclaré au contrat de stockage ; jamais créé
  automatiquement.
- Frontière iframe / Worker / processus du runtime et d'un futur moteur :
  **reportée** ; un moteur externe éventuel s'exécute isolé, sans shell, sans
  réseau, avec entrées générées sur liste fermée (enseignements DC-015-28 à 31).

## Compatibilité DrawCiel

**Décidé.** Stratégie : **aucune compatibilité en V1.**

| Option | Décision |
|---|---|
| Aucune compatibilité | **V1** |
| Import DrawCiel → Circuit | **À ÉTUDIER** après le premier jalon, sur corpus |
| Import + export | Non : DrawCiel n'est pas une cible |
| Migration des schémas existants | Non : relève de SéquenCiel et de sa Phase 12 |

- Aucune promesse de conversion parfaite sans corpus : les définitions
  DrawCiel (181 types, symboles personnalisés, surcharges de bornes, jonctions
  automatiques, anciens potentiels) excèdent largement le catalogue V1.
- Un import futur serait unidirectionnel, partiel et accompagné d'un rapport
  de pertes explicite (types non pris en charge, géométrie non orthogonale,
  annotations non reprises).
- Les identifiants DrawCiel (`uid`) **ne deviennent pas automatiquement** des
  identités Circuit ; un import éventuel génère des identités Circuit et peut
  conserver la provenance hors du modèle électrique.
- Corpus d'étude : fixtures synthétiques (comme DC-016-01) ; jamais de travaux
  d'élèves ni de données réelles sans décision explicite.

## Tests futurs

Familles (**décidé**) :

| Famille | Exemples |
|---|---|
| Modèle | Types du catalogue, bornes, rôles, propriétés, identités uniques |
| Géométrie | Transformations exactes, bornes sur grille pour les quatre rotations |
| Topologie | Réseaux, croisements, jonctions, masses, signature canonique |
| Routage | Orthogonalité, candidats, stabilité au déplacement, non-incidence |
| Sérialisation | Encodage déterministe, versions, refus de champs inconnus |
| Round-trip | Lire → écrire → lire identique |
| Conflits | Révision attendue, création exclusive, changement externe |
| Navigateur | Gestes, historique, dirty, sauvegarde, accessibilité clavier |
| Export | Correspondance document ↔ SVG, absence d'éléments d'interface |
| Simulation (futur) | Témoins analytiques, refus atomiques, non-mutation du document |

Invariants à tester systématiquement :

1. Opération graphique ⇒ signature topologique inchangée.
2. Permutation des collections ⇒ topologie et encodage canonique inchangés.
3. Round-trip exact de la ressource.
4. Toute borne est sur la grille pour toute rotation.
5. Annuler puis rétablir ⇒ document identique ; annuler ⇒ `dirty` si différent
   de l'état enregistré.
6. Aucune donnée runtime dans la ressource écrite.

Corpus : **synthétique** uniquement (circuits types : série, dérivation,
LED polarisée, croisement sans jonction, jonction, interrupteur ouvert/fermé,
potentiomètre, masse multiple), inspiré des fixtures A–J de DC-015-23 sans
reprise de données réelles.

## Premier jalon

**Décidé.** *Circuit éditable exact, sans simulation.*

Dans un projet de test, un utilisateur peut :

1. créer une ressource Circuit vide ;
2. poser une source, un interrupteur, une résistance, une LED et une masse ;
3. les relier, déplacer et tourner sans changer la topologie ;
4. voir les diagnostics `structure`, `topology`, `electrical-readiness` ;
5. enregistrer avec révision, rouvrir à l'identique, provoquer et voir un
   conflit ;
6. exporter un SVG correspondant exactement au document.

Critère mesurable : les six invariants de la section précédente passent sur le
corpus synthétique, et un parcours navigateur réalise les étapes 1 à 6.

**La simulation n'entre pas dans le premier jalon** : elle dépend d'une étude
de moteurs qui n'a de sens qu'une fois le document exact et stable.

## Roadmap technique

Ordre retenu pour la Phase 10, révisé par FD-GRAPHICS-001 (numéros
indicatifs ; les tickets FD-CIRCUIT-003 et suivants de la première version de
ce tableau sont renumérotés) :

| Ticket | Contenu | Justification de l'ordre |
|---|---|---|
| FD-CIRCUIT-001 | Besoins et périmètre (ce document) | Cadrage |
| FD-GRAPHICS-001 | Contrat du noyau graphique commun, capitalisation DrawCiel | Répartir Graphics / Circuit avant de figer le format |
| FD-CIRCUIT-002 | Contrat de ressource Circuit : format, version, identités, espace de sources, limites ; adopte les conventions de champs Graphics | Tout le reste lit ce format |
| FD-GRAPHICS-002 | Primitives géométriques pures, transformations exactes, ports | Base commune ; règles de grille et de direction utiles à la conversion du catalogue |
| FD-GRAPHICS-003 | Routage orthogonal extrait de DrawCiel, témoins portés | Algorithme éprouvé, référence encore fraîche |
| FD-CIRCUIT-003 | Domaine, catalogue V1 (inventaire et conversion contrôlée), codec, validation `structure`/`topology`/`electrical-readiness`, topologie | Exactitude testable avant tout rendu |
| FD-GRAPHICS-004 | Étude du renderer et de l'interaction (choix) | Choix éclairé par un modèle stable |
| FD-GRAPHICS-005 | Scène, projection, sélection, commandes, historique, éprouvés par un domaine témoin non électrique limité aux tests | Généricité prouvée avant Circuit |
| FD-CIRCUIT-004 | Projection Circuit → scène, commandes Circuit | Circuit sur le noyau |
| FD-CIRCUIT-005 | Intégration hôte, session, éditeur Web minimal (registre minimal si nécessaire) | Premier usage réel |
| FD-CIRCUIT-006 | Export SVG depuis le modèle | Complète le premier jalon |
| FD-CIRCUIT-007 | Qualification du premier jalon en navigateur | Preuve du jalon |
| FD-CIRCUIT-008 | Étude des moteurs et de l'IR Circuit (compatibilité avec la SimulationIR DrawCiel) | Seulement après le jalon |
| FD-CIRCUIT-009 | Adaptateur et simulation DC minimale | Après décision de l'étude |
| FD-CIRCUIT-010 | Mesures (multimètre, ohmmètre) | Après la simulation |
| ultérieur | Instruments, transitoires, extension du catalogue, import DrawCiel | Selon besoins |

Différences avec l'ordre initial : la validation structurelle est avancée avec
le modèle, la géométrie et le routage deviennent des tickets Graphics communs,
le choix du rendu est une étude explicite et la généricité du noyau est prouvée
par un domaine témoin non électrique avant la projection Circuit.

## Décisions

1. Circuit est un éditeur de schémas exacts ; la simulation est une capacité
   optionnelle future.
2. Un Circuit sans simulateur a une valeur suffisante pour les utilisateurs
   cibles.
3. Document, runtime et résultats de simulation sont séparés ; la simulation
   ne modifie jamais le document.
4. Identités stables obligatoires ; un indice ne suffit pas.
5. La topologie est l'autorité électrique ; la route est une présentation.
6. Aucune connexion par recouvrement ; insertion de jonction explicite.
7. Routes orthogonales sur grille en V1.
8. Coordonnées entières de grille, rotation par quarts de tour, pas de miroir
   ni de redimensionnement de composant en V1 ; inversion DrawCiel abandonnée.
9. Catalogue V1 : résistance, source DC, interrupteur unipolaire, lampe, LED,
   diode, potentiomètre, masse ; jonction topologique.
10. Valeurs SI, absence explicite, aucune valeur inventée.
11. Niveaux `structure`, `topology` bloquants ; `electrical-readiness` non
    bloquant ; aucune validation pédagogique.
12. Export SVG en V1, exact, jamais relu comme source.
13. Historique runtime par commandes atomiques ; annuler/rétablir rend `dirty`.
14. Conflit visible, aucun écrasement.
15. Bureau d'abord ; mobile hors V1.
16. Aucune compatibilité DrawCiel en V1 ; import éventuel étudié plus tard.
17. Premier jalon sans simulation.
18. Aucun écart justifiant une modification du contrat des outils spécialisés.

## Questions reportées

Tranchées par FD-CIRCUIT-002 ([ressource V0.1](circuit-resource.md)) : format,
suffixe `.circuit.json`, version `0.1`, espace `mvc/circuit/`, identités,
politique de découpe d'une connexion, limites.

| Question | Ticket attendu |
|---|---|
| Positions locales exactes des bornes et sorties de route par type | FD-GRAPHICS-002 / FD-CIRCUIT-003 |
| Frontend, rendu, isolation iframe/Worker du runtime | FD-GRAPHICS-004 / FD-CIRCUIT-005 |
| Registre d'outils spécialisés | FD-CIRCUIT-005 |
| Autosave | FD-CIRCUIT-005 ou ultérieur |
| Emplacement des exports | FD-CIRCUIT-006 |
| Moteur de simulation ; IR ou traduction directe | FD-CIRCUIT-008 |
| Modèles diode/LED/lampe | FD-CIRCUIT-008 / 009 |
| Effets physiques | Étude ultérieure |
| Presse-papiers système | Ultérieur |
| Étiquettes de réseau nommées, multipage, cartouche | Ultérieur |
| Composants personnalisés par contrat de type | Ultérieur |
| Import DrawCiel | Étude sur corpus, après le premier jalon |
| Microcontrôleurs, Arduino | Hors Phase 10 |
| Intégration SéquenCiel | Phase 12 |
