# Domaine Circuit V1

> **Phase Modules (FD-MODULES-001)** : Circuit quitte le cœur pour le module externe
> ForgeDesign-Circuit ([architecture](../modules/module-architecture.md)). Ce document
> migrera avec lui ; aucune nouvelle fonctionnalité Circuit n'est ajoutée au cœur.

Statut : **normatif et implémenté** (FD-CIRCUIT-003). Code :
`forge_design/circuit/catalog.py`, `domain.py`, `topology.py`, `validation.py`.
Format persistant inchangé : [Ressource Circuit V0.1](circuit-resource.md).

## Objectif

Répondre de manière pure et déterministe à la question : ce `CircuitDocument`
décrit-il un schéma structurellement correct, topologiquement cohérent et
suffisamment renseigné pour une future analyse électrique ?

```text
CircuitDocument ── CircuitCatalog ──▶ structure de domaine
       │
       └──▶ CircuitTopology (bornes, connexions, réseaux dérivés) ──▶ topology
                                                                 └──▶ electrical-readiness
plus tard : CircuitTopology → IR de simulation → moteur
```

Aucun Graphic Core, routage, rendu, éditeur, simulation, mesure ni export.

## Référence DrawCiel

Référence `aac36b27` (delta vide depuis FD-CIRCUIT-002). Contrats consultés :
`static/vendor/drawciel/js/electrical-contracts.js` (définitions, profils,
propriétés requises), `components-data.js`, `model.js` (`buildElectricalGraph`,
ADR-262), contrats de bornes (ADR-264), fixtures A–J (`tests/drawciel-graph.cjs`,
DC-015-23). Aucun code, symbole SVG ni valeur d'exemple n'est repris.

| Type Circuit | Source DrawCiel | Retenu | Abandonné | Adaptation |
|---|---|---|---|---|
| `resistor` | `03_…__resistance` (`resistor`) | `t1`/`t2` symétriques ; `resistanceOhms` requis ; `ratedPowerW` | Tolérance, bandes, coefficients thermiques ; défaut 0,25 W | `resistance`, `rated_power` ; rôle `passive` |
| `dc-source` | `02_…__pile` (`dc_voltage_source`) | `t1` positive, `t2` negative ; `voltageV` requis ; `internalResistanceOhms ≥ 0` | Capacité Ah, courant maximal ; défaut 0,05 Ω | Bornes `positive`/`negative` ; `voltage` sans minimum |
| `switch` | `07_…__interrupteur_spst_ouvert` / `_ferme` (`switch`, position de repos) | Contacts `t1`/`t2` ; position ouverte/fermée | Deux types distincts, position par défaut, résistance de contact, limites | Un type, propriété `closed` requise, sans défaut |
| `lamp` | `08_…__lampe` (`incandescent_lamp`) | `nominalVoltageV`, `nominalPowerW` requis | Facteur à froid, température | `rated_voltage`, `rated_power` |
| `led` | `05_…__led` (`led`) | `t1` anode, `t2` cathode ; `forwardVoltageV ≥ 0` requis ; `nominalCurrentA` ; couleur | Courant et puissance maximaux, thermique ; défauts (rouge, 20 mA) | `anode`/`cathode` ; `color` texte libre |
| `diode` | `05_…__diode` (`diode`) | anode/cathode ; `forwardVoltageV ≥ 0` requis ; `maxForwardCurrentA` | Tension inverse, puissance | `forward_voltage`, `max_current` |
| `potentiometer` | `03_…__potentiometre` (`variable_resistor`) | `t1` end1, `t2` wiper, `t3` end2 ; `resistanceOhms` requis ; position du curseur | Bornes UI 0,1–99,9 %, défaut 50 % | `position` fraction `[0, 1]`, requise |
| `ground` | `power__gnd` (`net_reference`, `net_name = GND`) | Une borne de rôle `reference` | `label`, `net_name` | Borne `ref` ; fusion des masses par rôle |

Correspondance des bornes pour un import futur : `dc-source` `t1→positive`,
`t2→negative` ; `led`/`diode` `t1→anode`, `t2→cathode` ; `potentiometer`
`t1→end1`, `t2→wiper`, `t3→end2` ; `ground` `t1→ref` ; autres types identiques.
Correspondance des propriétés : `resistanceOhms→resistance`,
`ratedPowerW→rated_power`, `voltageV→voltage`,
`internalResistanceOhms→internal_resistance`, `nominalVoltageV→rated_voltage`,
`nominalPowerW→rated_power`, `forwardVoltageV→forward_voltage`,
`nominalCurrentA→nominal_current`, `maxForwardCurrentA→max_current`,
`wiperPosition (%)→position (÷ 100)`, position de commande `→closed`.

## Catalogue

`CIRCUIT_CATALOG` : constante immuable construite explicitement ; aucune
découverte dynamique, aucun plugin, aucun accès disque. `CircuitCatalog`
refuse les types dupliqués ; `get(type_id)` renvoie la définition ou `None`.

## Types V1

Exactement huit types, dans cet ordre : `resistor`, `dc-source`, `switch`,
`lamp`, `led`, `diode`, `potentiometer`, `ground`. Identifiants stables, ASCII,
kebab-case, indépendants des libellés ; aucun identifiant DrawCiel historique.
La jonction n'est pas un type.

## Composants

`CircuitComponentDefinition` (gelée) : `id`, `name` (libellé), `domain_kind`
(classification explicite pour une traduction future, sans API de simulation),
`terminals`, `properties`, `symmetric` (dipôle non polarisé dont les bornes
sont interchangeables). Composant ≠ symbole : aucun SVG.

## Bornes

`CircuitTerminalDefinition` : `id` local au type, `role`, `polarity`,
`direction` de port (`N`/`E`/`S`/`W`, convention de projection : dipôles de
gauche à droite, source verticale, curseur et masse vers le haut). Identité
d'instance : `(component_id, terminal_id)`, sans identifiant persisté.
Positions locales et transformations : FD-GRAPHICS-002.

| Type | Bornes (rôle) |
|---|---|
| `resistor`, `switch`, `lamp` | `t1`, `t2` (passive) |
| `dc-source` | `positive` (source-positive), `negative` (source-negative) |
| `led`, `diode` | `anode` (anode), `cathode` (cathode) |
| `potentiometer` | `end1` (passive), `wiper` (wiper), `end2` (passive) |
| `ground` | `ref` (reference) |

## Rôles

`passive`, `source-positive`, `source-negative`, `anode`, `cathode`, `wiper`,
`reference`. Tout comportement repose sur un rôle déclaré (fusion des masses,
source court-circuitée), jamais sur un nom, un identifiant ou un ordre.

## Polarités

`positive`, `negative`, `none`. Déclarées, et **contrôlées** à la construction :
`source-positive` et `anode` ⇒ `positive` ; `source-negative` et `cathode` ⇒
`negative` ; autres rôles ⇒ `none`. Aucune polarité n'est déduite de l'ordre
des bornes ; aucun avertissement d'orientation d'une LED ou d'une diode (non
déterminable sans potentiels).

## Propriétés

`CircuitPropertyDefinition` : `name` (snake_case), `value_type` (`number`,
`boolean`, `string`), `unit`, `minimum`, `maximum`, `required_for_readiness`.

| Type | Propriétés (requises pour la préparation en gras) |
|---|---|
| `resistor` | **`resistance`** Ω ≥ 0, `rated_power` W ≥ 0 |
| `dc-source` | **`voltage`** V, `internal_resistance` Ω ≥ 0 |
| `switch` | **`closed`** booléen (état de conception) |
| `lamp` | **`rated_voltage`** V ≥ 0, **`rated_power`** W ≥ 0 |
| `led` | **`forward_voltage`** V ≥ 0, `nominal_current` A ≥ 0, `color` texte |
| `diode` | **`forward_voltage`** V ≥ 0, `max_current` A ≥ 0 |
| `potentiometer` | **`resistance`** Ω ≥ 0, **`position`** ratio `[0, 1]` (de end1 vers end2) |
| `ground` | aucune |

Seules les contraintes contractuelles sont déclarées (positivité, fraction) ;
aucune limite physique arbitraire. Zéro est une valeur (résistance idéale,
source 0 V, curseur en butée) ; la simulation future décidera des cas
problématiques. Une tension de source peut être négative.

## Valeurs et unités

Valeurs en unités SI ; identifiants d'unité `ohm`, `volt`, `ampere`, `watt`,
`ratio` ; symboles (`Ω`, `V`) et préfixes (`k`, `m`) relèvent de la
présentation. Aucune conversion (`"1k"` est refusé). Un nombre est un entier ou
un décimal fini (jamais un booléen).

Absence de clé = valeur non renseignée, distincte de zéro. **Aucune valeur
n'est inventée** : aucun défaut, y compris pour `switch.closed`, qui est requis
pour la préparation plutôt que fixé silencieusement. Un document lu n'est
jamais modifié.

## Structure domaine

Niveau `structure` (erreurs bloquantes), après la validation du format :

| Code | Situation | Localisation |
|---|---|---|
| `circuit.unknown-component-type` | Type absent du catalogue | `components[i].type` |
| `circuit.unknown-property` | Clé non autorisée par le type (dont toute clé d'état d'exécution) | `components[i].properties.<clé>` |
| `circuit.invalid-property` | Mauvais type ou hors domaine | `components[i].properties.<clé>` |

Les règles dépendant du catalogue restent hors de Pydantic : le format est
découplé du catalogue. Un document décodé peut donc être invalide pour le
domaine.

## Topologie

`build_circuit_topology(document, catalog) → CircuitTopology`, pure et
immuable :

- `terminals` : toutes les bornes des composants de type connu ;
- `junctions`, `connections` (connexions valides, non orientées, extrémités en
  ordre canonique) ;
- `nets` : réseaux dérivés ; `net_of(membre)`.

Construite uniquement à partir des composants, des bornes du catalogue, des
connexions, des jonctions et des masses ; positions, rotations, routes,
annotations, références visibles et ordre des collections n'ont aucun effet.
Union-find : O((V + E) α) puis tri ; aucune boucle quadratique.

## Connexions

| Code (niveau `topology`) | Sévérité | Localisation |
|---|---|---|
| `circuit.component-not-found` | erreur | `connections[i].<a\|b>.component_id` |
| `circuit.terminal-not-found` | erreur | `connections[i].<a\|b>.terminal_id` |
| `circuit.junction-not-found` | erreur | `connections[i].<a\|b>.junction_id` |
| `circuit.self-connection` | erreur | `connections[i]` |
| `circuit.duplicate-connection` | avertissement (A–B ≡ B–A) | `connections[i]` |

Une connexion invalide ne participe à aucun réseau. Une extrémité vers un
composant de type inconnu n'est pas réévaluée (erreur `structure` déjà émise).
Plusieurs connexions sur une même borne sont admises.

## Jonctions

Nœud du graphe, jamais une borne du catalogue. Degré 0 ou 1 :
`circuit.junction-dangling` (avertissement) ; degré 2 valide.

## Réseaux

`CircuitNet` : bornes et jonctions membres triées, `key` canonique (JSON des
membres triés, comme l'identité de réseau de DrawCiel), `reference`. Aucune
identité persistée ; ni ordre de construction, ni indice, ni premier membre
rencontré. Les réseaux sont triés par clé.

## GND

Toutes les bornes de rôle `reference` (masses) forment **un seul réseau**, même
non reliées graphiquement (décision FD-CIRCUIT-001). Cette fusion est une
**référence commune** : elle n'ajoute ni tension, ni source, ni énergie ; aucun
potentiel implicite (dette des anciens potentiels DrawCiel non reproduite).

## Electrical readiness

Niveau `electrical-readiness`, **avertissements seulement**, jamais bloquant :

| Code | Situation | Localisation |
|---|---|---|
| `circuit.missing-property` | Propriété requise absente | `components[i].properties.<nom>` |
| `circuit.unconnected-terminal` | Borne sans connexion (message : borne) | `components[i]` |
| `circuit.source-shorted` | Bornes `source-positive` et `source-negative` dans le même réseau | `components[i]` |
| `circuit.missing-ground` | Composants présents, aucune borne `reference` | racine |

Validité ≠ simulabilité : un document structurellement et topologiquement
valide, avec avertissements de préparation, est sauvegardable.

## Diagnostics

`validate_circuit(document, catalog=CIRCUIT_CATALOG) →
SpecializedValidationResult`, utilisé par `CircuitCodec.validate` après la
revalidation du format. Ordre déterministe : `structure`, puis `topology`, puis
`electrical-readiness` ; dans chaque niveau, ordre du document puis ordre des
règles (pour une connexion : extrémité a, extrémité b, auto-connexion,
doublon ; pour un composant : propriétés, bornes, source). Au plus 512 issues,
troncature signalée. Les messages citent les identités.

`CIRCUIT_RESOURCE_TYPE` déclare les trois niveaux ; bloquants : `structure` et
`topology`. Le socle ne bloque que les erreurs : un avertissement `topology`
(doublon, jonction pendante) ne bloque pas.

## Relation avec la ressource V0.1

Aucun champ ajouté ; `format_version` reste `0.1`. La limite de FD-CIRCUIT-002
est fermée : une clé d'état d'exécution dans `properties` est désormais refusée
au niveau `structure` (allowlist par type). La validité de format (type
lexical, ex. `placeholder`) reste distincte de la validité de domaine.

## Relation avec Graphic Core

`component → Node`, borne → `Port` (identifiant et direction déclarés),
`connection → Edge`, `junction → Node + Port omnidirectionnel`. La validation
géométrique des routes (orthogonalité, colinéarité) n'est pas de la topologie :
elle relève de FD-GRAPHICS-003 et de l'adaptateur Circuit.

## Préparation de la simulation future

`domain_kind`, rôles, polarités, unités SI et état de conception `closed`
permettent une traduction sans heuristique de nom vers une IR de simulation ;
les correspondances DrawCiel sont documentées ci-dessus. Aucun modèle physique
(diode, LED, lampe), aucune IR, aucun moteur n'est créé.

## Limites

- Pas de positions locales de bornes ni de géométrie de symboles.
- Pas d'étiquettes de réseau nommées autres que la masse.
- Couleur de LED en texte libre.
- Validation des routes déléguée à Graphics.

## Questions reportées

| Question | Ticket |
|---|---|
| Positions locales des bornes, symboles | FD-GRAPHICS-002 |
| Validation géométrique des routes | FD-GRAPHICS-003 |
| Projection `GraphicScene` | FD-CIRCUIT-004 |
| Préfixe de référence par type (R, D…) | Éditeur (FD-CIRCUIT-005) |
| Modèles physiques, IR, moteur | FD-CIRCUIT-008 et suivants |
| Extension du catalogue | Ultérieur |
