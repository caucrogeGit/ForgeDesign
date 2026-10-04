# FD-CIRCUIT-001 — Définir les besoins et le périmètre du Tool Circuit

> **Histoire avant extraction.** Ce rapport décrit Circuit lorsqu'il vivait dans le
> cœur (`forge_design/circuit/`, `docs/circuit/`). Depuis FD-MODULES-003, Circuit est
> le module externe ForgeDesign-Circuit (paquet `forge_design_circuit`) ; ses
> documents y ont été déplacés et les liens ci-dessous mènent au
> [renvoi](../circuit/README.md). Le reste du rapport n'est pas réécrit.

Statuts employés : **observé** (constaté dans DrawCiel ou ses rapports),
**décidé** (règle retenue pour Circuit), **reporté** (renvoyé à un ticket).
Le détail normatif est dans [Circuit — besoins et périmètre](../circuit/README.md).

## Ticket et objectif

Ouvrir la Phase 10 en définissant ce que doit être Circuit dans Forge Design
avant toute implémentation, à partir de DrawCiel intégré à SéquenCiel.
Ticket d'analyse et de cadrage : aucun code produit, aucun format, aucun
moteur, aucun frontend, aucun enregistrement de Circuit.

## État Git initial

```text
$ git log -1 --oneline
183941f feat: implémenter le socle des ressources spécialisées (FD-SPECIALIZED-002)
$ git rev-parse origin/main
183941fae18a0c2ed5bfdfb4a52be651e74c5808
$ git status --short
 M docs/rapports/FD-CONTRACT-001.md
```

Baseline conforme. `docs/rapports/FD-CONTRACT-001.md` (modification locale
de l'utilisateur) est conservé tel quel, hors commit.

## Sources DrawCiel étudiées

Dépôt SéquenCiel en lecture seule, HEAD `c229b2ed` (2 octobre 2026). Aucun
fichier SéquenCiel modifié, aucune application lancée.

- Repris sans nouvel audit : DC-016-00 (audit d'architecture au commit
  `5a02277d`, 27 septembre) et DC-016-01 (contrat de persistance), déjà
  exploités par FD-SPECIALIZED-001.
- Lus en complément : synthèse ergonomie/bibliothèque, DC-015-FINAL
  (bibliothèque, routage, validation terrain), DC-015-11 (historique),
  DC-015-13 (plan de travail), rapports DC-015-23 (graphe électrique),
  DC-015-24 (contrat des bornes), DC-015-25 (isolation du calcul),
  DC-015-26 (validation numérique), DC-015-27 (relais), DC-015-28
  (contrat de modèles et netlist), DC-015-29 (SimulationIR et SPICE),
  DC-015-30 à 32 (banc, service et API ngspice), DC-016-01 et DC-016-04
  (microcontrôleurs, cosimulation Arduino).
- Vérifications ponctuelles du code courant (sans copie) : `baseState()`
  (`version: '0.15.0'`, `annotations`, `page`, `customDefs`,
  `terminalOverrides`), `snapStep = 20`, rotation `(rot + 90) % 360`,
  `invertComponentConnections` (permutation des extrémités de fils selon
  `swapPairs`), filtrage au chargement des anciennes clés physiques de
  `component.state`, `commandPosition` encore dans `component.state`,
  `page.indicatorOffsets`, recopie de `customDefs` dans le stockage local.

**Observé** : DC-015-23 à 32 sont postérieurs à DC-016-00 et ont corrigé une
partie des dettes qu'il relevait (graphe unique, contrats de bornes explicites,
résultats hors du document, IR). Circuit s'appuie sur cet état récent ; le
tableau des écarts du contrat des outils spécialisés reste exact à la date de
l'audit et n'est pas modifié.

## Capacités DrawCiel recensées

39 capacités recensées et classées dans la
[matrice](../circuit/README.md) : document,
catalogue, placement, sélection, déplacement, rotation, inversion, symétrie,
redimensionnement, bornes, connexions, jonctions, routage orthogonal,
annotations, références, grille, zoom, pan, undo/redo, copier/coller, aligner,
grouper, verrouiller, inspecteur, propriétés électriques, simulation,
multimètre, ohmmètre, oscilloscope, mesures, effets physiques, validation,
export, TP, Arduino, bibliothèque, symboles personnalisés, page, noms de réseau.

## Capacités retenues

CORE : document, catalogue réduit, placement, sélection, déplacement,
rotation, bornes, connexions, jonctions (redéfinies), références, grille,
zoom, pan, undo/redo (redéfini), inspecteur, propriétés électriques,
validation (sans TP).
V1 : routage orthogonal, annotations texte, copier/coller interne, export SVG,
page unique, masse GND.

## Capacités reportées

FUTUR : symétrie, redimensionnement, annotations graphiques, aligner, grouper,
verrouiller, simulation, multimètre, ohmmètre, oscilloscope, mesures, export
PNG, modèles réutilisables, composants personnalisés par contrat, noms de
réseau, multipage.
À ÉTUDIER : effets physiques, Arduino, presse-papiers système, import DrawCiel.

## Capacités SéquenCiel

TP (consignes, signatures, évaluation), bibliothèque personnelle en base,
insertion WebP dans les textes, élèves, copies, droits, téléversement USB.

## Capacités abandonnées

Mécanismes DrawCiel à ne pas reproduire (le besoin peut subsister autrement) :

- `invertComponentConnections` : opération topologique déclenchée comme un
  geste graphique ;
- jonctions automatiques sous forme de faux composant et découpe implicite ;
- import SVG libre + `terminalOverrides` + recopie en stockage local ;
- état runtime ou de commande sérialisé dans `component.state` ;
- préférences d'affichage dans le document (`page.indicatorOffsets`) ;
- classification par nom ou expression régulière (déjà corrigée par DC-015-24) ;
- historique par instantanés avec deux événements divergents ;
- version native filtrée à la persistance.

## Rôle de Circuit

**Décidé** : éditeur de schémas électriques exacts dans un projet Forge,
ressource versionnée en zone C ; simulation = capacité optionnelle future.

## Utilisateurs

Développeur Forge, enseignant (production de ressources), créateur de
ressource technique. L'élève n'utilise pas Forge Design : il passe par
l'application intégrante (Phase 12).

## Cas d'usage

Créer, poser, relier, tourner, renseigner, vérifier, enregistrer, rouvrir,
gérer un conflit, exporter. Hors V1 : simuler, mesurer, TP, microcontrôleurs,
import DrawCiel.

**Circuit sans simulateur a-t-il une valeur suffisante ? Oui** : l'usage
observé de DrawCiel dans SéquenCiel est dominé par la production
d'illustrations ; un schéma exact a de la valeur sans calcul, l'inverse non ;
le socle (topologie explicite, bornes contractuelles, validation) est requis
par toute simulation future. L'hypothèse « éditeur + topologie + validation +
export avant simulation » est retenue, sous condition que le modèle V1
n'empêche pas la simulation et que son absence soit annoncée.

## Périmètre V1

Voir [Périmètre V1](../circuit/README.md) : ressource
versionnée via `forge_design.specialized`, catalogue de 8 types + jonction,
édition sur grille, routes orthogonales, validation à trois niveaux,
historique, session et conflit, export SVG, bureau et clavier.

## Document et runtime

**Décidé** : `CircuitDocument` (persistant) ≠ `CircuitRuntimeState` (session,
historique, sélection, vue, dirty) ≠ `SimulationResult` (futur). La simulation
lit un instantané et n'écrit jamais le document. L'état de conception d'un
interrupteur est une propriété ; son basculement en simulation est runtime.

## Concepts invariants

Document, composant, borne, connexion, jonction, route, réseau (dérivé),
annotation, page, propriété, référence. Identités stables obligatoires ; un
indice est insuffisant (suppression, réordonnancement, historique, mapping).
Schéma d'identité **reporté** à FD-CIRCUIT-002, sans choix d'UUID.

## Topologie

**Décidé** : la topologie est l'autorité électrique, calculée sans géométrie.
Croisement sans connexion = deux réseaux ; jonction explicite ; connexion sur
borne ; connexion sur fil = insertion explicite d'une jonction en une action
d'historique. Aucune connexion par recouvrement. Invariant testable : une
opération graphique laisse la signature topologique identique.
**Observé** : DrawCiel crée des jonctions automatiques qui découpent les fils.

## Géométrie

**Décidé** : coordonnées monde en unités de grille entières, indépendantes du
viewport ; grille logique obligatoire ; rotation 0/90/180/270 ; bornes
calculées par transformation entière exacte. Rotation, inversion et miroir
sont distincts : rotation en V1, inversion abandonnée, miroir futur. Aucun
composant redimensionnable en V1.

## Routage

**Décidé** : V1 exige des routes orthogonales ; topologie = autorité, route =
présentation. Route = points intermédiaires, extrémités dérivées. Automatique
simple (droite, 1 coude, 2 coudes), déplacement de segment manuel. Au
déplacement d'un composant, seules les routes incidentes changent ; translation
si les deux extrémités bougent ; recalcul seulement si non orthogonale.
Verrous et évitement d'obstacles FUTUR. **Observé** : DC-015-FINAL a corrigé
les escaliers dus aux ancres de grille et au gel préalable des routes.

## Catalogue

**Décidé** : résistance, source DC, interrupteur unipolaire, lampe, LED,
diode, potentiomètre, masse ; jonction hors catalogue. Composant ≠ symbole ;
bornes explicites par type, polarité dans le modèle, aucune classification par
nom. LDR reportée : sa valeur dépend d'un éclairement, grandeur d'environnement
à concevoir avec la simulation.

## Propriétés

**Décidé** : graphiques, électriques, éditoriales ; unités SI ; absence
explicite ; `0` seulement si déclaré ; aucune valeur inventée ; un composant
peut exister sans valeur électrique, la sauvegarde reste permise.

## Validation

**Décidé** : `structure` (bloquant), `topology` (erreurs bloquantes),
`electrical-readiness` (avertissements, non bloquant). Aucune validation
pédagogique. Compatible avec `forge_design.specialized` sans modification.

## Simulation

**Reporté** : aucune simulation en V1 ni au premier jalon ; moteur non choisi.
Besoins classés minimal futur / futur / hors document. Frontière
`CircuitDocument → graphe dérivé → entrée de simulation → moteur →
SimulationResult`. Question IR / traduction directe posée, non tranchée ;
recommandation d'une frontière de traduction explicite (enseignement de
DC-015-23 à 29). Moteur JS DrawCiel = référence de témoins ; ngspice =
candidat (qualifié par SéquenCiel en contexte serveur), sans benchmark ici.

## Mesures

**Décidé** (futur) : instruments d'interface = runtime de session ;
instruments dessinés = composants ; multimètre et ohmmètre chargent le circuit
simulé, pas le document ; qualité explicite, jamais de zéro par défaut ;
oscilloscope FUTUR.

## Export

**Décidé** : SVG en V1, exact, sans élément d'interface ni ressource externe,
jamais relu comme source. PNG FUTUR ; WebP SéquenCiel. Emplacement des
exports reporté.

## Historique

**Décidé** : commandes atomiques, un geste = une entrée ; historique runtime
borné ; annuler/rétablir rend `dirty` si l'état diffère de l'enregistré.
**Observé** : divergence `drawciel:state` / `drawciel:change` dans DrawCiel.

## Sauvegarde

**Décidé** : ouvrir → session → éditer → dirty → enregistrer avec révision →
fermer. Sauvegarde explicite en V1 ; autosave possible par le contrat, non
requis. Changement externe → conflit visible, pas d'écrasement.

## UI

**Décidé** : zones catalogue, espace de travail, barre d'outils, inspecteur,
diagnostics (instruments absents en V1) ; commandes nommées et prévisibles ;
liaison électrique distincte des annotations ; bureau d'abord, mobile hors V1
(consultation comprise) ; accessibilité clavier de base.

## Sécurité

**Décidé** : l'hôte lit et écrit ; le runtime ne touche jamais au projet ;
contenu non fiable, validé, borné, échappé ; aucun SVG importé ; hors ligne,
aucun CDN ; aucune donnée pédagogique, machine ou runtime dans la ressource.
Espace de sources et frontière iframe/Worker **reportés**.

## Compatibilité DrawCiel

**Décidé** : aucune compatibilité en V1. Import unidirectionnel DrawCiel →
Circuit **à étudier** après le premier jalon, partiel, avec rapport de pertes,
sur corpus synthétique ; ni export vers DrawCiel, ni migration. Les `uid`
DrawCiel ne deviennent pas automatiquement des identités Circuit.

## Premier jalon

**Décidé** : *Circuit éditable exact, sans simulation* — créer, poser source,
interrupteur, résistance, LED et masse, relier, déplacer, tourner, voir les
diagnostics, enregistrer, rouvrir à l'identique, voir un conflit, exporter un
SVG exact. Mesurable par les six invariants et un parcours navigateur.

## Roadmap Phase 10

FD-CIRCUIT-002 contrat de ressource → 003 modèle, catalogue, codec,
validation → 004 géométrie et routage → 005 étude du rendu → 006 intégration
hôte et session → 007 éditeur Web minimal → 008 export SVG → 009
qualification du jalon → 010 étude des moteurs et de l'IR → 011 simulation DC
minimale → 012 mesures → ultérieur. Justification : le format conditionne
tout ; l'exactitude se teste avant le rendu ; le frontend se choisit sur un
modèle stable ; la simulation vient après le jalon.

### Réponses obligatoires

| | Question | Réponse |
|---|---|---|
| A | Rôle de Circuit | Éditeur de schémas électriques exacts, ressource versionnée en zone C ; simulation optionnelle future |
| B | Ce qui est en V1 | Catalogue de 8 types + jonction, édition sur grille, rotation, routes orthogonales, références, valeurs SI, texte, validation `structure`/`topology`/`electrical-readiness`, historique, session, sauvegarde avec révision et conflit, export SVG, bureau et clavier |
| C | Ce qui est hors V1 | Simulation, mesures, instruments, effets physiques, TP, Arduino, symboles personnalisés, redimensionnement, miroir, groupes, verrous, formes, noms de réseau hors GND, multipage, PNG/WebP, import DrawCiel, mobile |
| D | Ce qui relève de SéquenCiel | TP et évaluation, élèves et copies, bibliothèque personnelle en base, droits, insertion WebP, persistance SQL, Arduino et téléversement |
| E | Simulation nécessaire au premier jalon ? | **Non** |
| F | Concepts invariants | Document, composant, borne, connexion, jonction, route, réseau dérivé, annotation, page, propriété, référence ; identités stables |
| G | Topologie et routage séparés ? | **Oui** : topologie = autorité électrique, route = présentation sans effet électrique |
| H | Niveau de compatibilité DrawCiel | Aucun en V1 ; import unidirectionnel partiel à étudier plus tard sur corpus |
| I | Exports requis | SVG exact en V1 ; PNG futur ; WebP côté SéquenCiel |
| J | Prochain ticket technique | **FD-CIRCUIT-002 — Contrat de ressource Circuit** (format, version, identités, espace de sources, limites) |

## Décisions retenues

Les dix-huit décisions de la section
[Décisions](../circuit/README.md) du périmètre, dont : aucun
écart ne justifie de modifier le contrat des outils spécialisés ; le contrat de
stockage n'est pas modifié (aucun chemin réservé).

## Questions reportées

Voir [Questions reportées](../circuit/README.md) :
format, identités, limites (FD-CIRCUIT-002) ; positions de bornes
(003/004) ; frontend et isolation du runtime (005/006) ; registre (006) ;
autosave (007) ; emplacement des exports (008) ; moteur et IR (010) ;
modèles diode/LED/lampe (010/011) ; effets physiques ; presse-papiers système ;
noms de réseau, multipage ; composants personnalisés ; import DrawCiel ;
microcontrôleurs ; intégration SéquenCiel (Phase 12).

## Fichiers créés

- `docs/circuit/circuit-scope.md`
- `docs/rapports/FD-CIRCUIT-001.md`

## Fichiers modifiés

- `docs/02-architecture.md` : sous-section « Frontière conceptuelle de Circuit »
  au §13, explicitement non implémentée.
- `docs/03-roadmap.md` : Phase 10 réordonnée et justifiée, premier jalon.

Non modifiés : contrat des outils spécialisés (aucun écart réel), contrat de
stockage (aucun chemin réservé), code produit, tests, SéquenCiel, Forge.

## Validations

| Contrôle | Résultat |
|---|---|
| Tests lisant `docs/` : `tests/test_design_schema.py`, `tests/test_view_contract_schema.py` (lancés hors du dépôt, `--rootdir` ForgeDesign) | 45 réussis |
| `git diff --check` | Réussi |
| Tests des ressources spécialisées | Non requis : contrat non modifié |
| MkDocs | Sans objet : aucun `mkdocs.yml` dans Forge Design |
| Suite globale | Non requise : aucun code produit ni test modifié |
| Liens internes du périmètre et du rapport (fichiers et ancres) | Vérifiés |

Aucun benchmark, aucune installation, aucune exécution de DrawCiel, de
SéquenCiel ou d'un moteur de simulation.

## État Git final

Avant commit :

```text
$ git status --short
 M docs/02-architecture.md
 M docs/03-roadmap.md
 M docs/rapports/FD-CONTRACT-001.md
?? docs/circuit/
?? docs/rapports/FD-CIRCUIT-001.md
```

Commit : `docs: cadrer le Tool Circuit à partir de DrawCiel (FD-CIRCUIT-001)`,
contenant les quatre fichiers du ticket. `docs/rapports/FD-CONTRACT-001.md`
reste modifié localement, hors commit. Aucun push.
