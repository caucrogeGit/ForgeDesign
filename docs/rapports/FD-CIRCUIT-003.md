# Rapport — FD-CIRCUIT-003

Contrat normatif : [Domaine Circuit V1](../circuit/circuit-domain.md).

## Ticket et objectif

Construire le domaine électrique Circuit V1 au-dessus de la ressource V0.1 :
catalogue fermé, contrats de bornes et de polarités, propriétés autorisées,
graphe électrique, réseaux dérivés, validation `structure` / `topology` /
`electrical-readiness`. Sans Graphic Core, routage, rendu, éditeur, simulation,
mesures ni export.

Le ticket transmis s'interrompt au début de la section « Preuves
obligatoires » ; les consignes manquantes (dont le message de commit) ont été
déduites des tickets précédents : commit unique
`feat: implémenter le domaine Circuit V1 (FD-CIRCUIT-003)`, pas de push.

## État Git initial

```text
$ git log -1 --oneline
d8275f2 feat: définir la ressource Circuit v0.1 (FD-CIRCUIT-002)
$ git rev-parse origin/main
d8275f2d5f980e538a437dcc9094d2f035fc129e
$ git status --short
 M docs/rapports/FD-CONTRACT-001.md
```

## Référence DrawCiel précédente

`aac36b27` (FD-CIRCUIT-002).

## Référence DrawCiel du ticket

`git fetch` : `origin/main` = `aac36b27`, inchangé ; référence figée
`aac36b27`. La copie de travail SéquenCiel porte des modifications locales non
commitées (contrôleur R4, documentation, `mkdocs.yml`) : non publiées, ni lues
ni retenues.

## Delta DrawCiel

Vide.

## Sources DrawCiel consultées

Au commit `aac36b27`, en lecture : `electrical-contracts.js` (définitions,
profils, `propertySchema`, `requiredProperties`, rôles, polarités, `ports`,
`command`), `components-data.js`, l'identité canonique des réseaux et la
fusion par référence (ADR-262, `model.js`, DC-015-23), le contrat explicite
des bornes (ADR-264, DC-015-24), les cas A–J (croisement F, jonction G,
potentiels H). Aucun SVG, aucune valeur d'exemple, aucun code repris.

| Usage | Référence |
|---|---|
| Catalogue | `resistance`, `pile`, `interrupteur_spst_ouvert/ferme`, `lampe`, `led`, `diode`, `potentiometre`, `power__gnd` |
| Bornes | Rôles et `ports` explicites (ADR-264), polarité `+`/`−` |
| Graphe | Membres triés comme identité de réseau (ADR-262) |
| GND | `net_reference` sans énergie, refus des potentiels implicites (DC-015-19/23) |

## Catalogue Circuit V1

`forge_design/circuit/catalog.py` : `CircuitTerminalDefinition`,
`CircuitPropertyDefinition`, `CircuitComponentDefinition`, `CircuitCatalog`
(dataclasses gelées, tuples, index `MappingProxyType`), constante
`CIRCUIT_CATALOG` construite explicitement, sans découverte dynamique.

## Types retenus

**Exactement huit** : `resistor`, `dc-source`, `switch`, `lamp`, `led`,
`diode`, `potentiometer`, `ground`. Identifiants kebab-case propres à Circuit ;
correspondance avec les types DrawCiel documentée, sans identifiant historique.
`domain_kind` explicite (`resistor`, `dc-voltage-source`, `switch`, `lamp`,
`led`, `diode`, `potentiometer`, `ground-reference`) ; aucune API de
simulation.

## Contrats des bornes

Chaque borne déclare `id`, `role` (`passive`, `source-positive`,
`source-negative`, `anode`, `cathode`, `wiper`, `reference`), `polarity` et
`direction` (`N`/`E`/`S`/`W`). Identité d'instance `(component_id,
terminal_id)` sans identifiant persisté. Aucune position locale (FD-GRAPHICS-002).
Correspondance DrawCiel : `t1→positive`/`anode`/`end1`/`ref`, `t2→negative`/
`cathode`/`wiper`, `t3→end2` selon le type.

## Polarités

`positive` / `negative` / `none`, déclarées **et contrôlées** contre le rôle à
la construction ; jamais déduites de l'ordre. Aucun diagnostic d'orientation de
LED ou de diode.

## Propriétés

Allowlist par type (voir le domaine) : noms snake_case, sans unité dans le nom,
correspondance explicite avec les clés DrawCiel (`resistanceOhms → resistance`,
`wiperPosition % → position` ÷ 100…). Contraintes seulement contractuelles :
positivité des grandeurs, `position ∈ [0, 1]`, tension de source libre (peut
être nulle ou négative). Les bornes d'interface DrawCiel (0,1–99,9 %) ne sont
pas reprises.

## Unités

`ohm`, `volt`, `ampere`, `watt`, `ratio` ; valeurs SI ; aucun préfixe ni
conversion (`"1k"` refusé).

## Défauts et absences

Aucun défaut. Absence de clé = non renseigné ≠ zéro (zéro accepté et non
signalé). `switch.closed` est **requis pour la préparation** plutôt que fixé
à `false` : un défaut silencieux masquerait un état de conception non choisi ;
DrawCiel exprimait cet état par deux types distincts. Les défauts de simulation
DrawCiel (0,05 Ω, 0,25 W, 20 mA, rouge, 50 %) ne sont pas repris. Aucun
document lu n'est modifié (tests de pureté).

## Validation structure domaine

`domain.py` : `circuit.unknown-component-type`, `circuit.unknown-property`,
`circuit.invalid-property`, localisés `components[i].type` ou
`components[i].properties.<clé>`. Hors de Pydantic : le format reste découplé
du catalogue ; un document de format valide (`placeholder`) est invalide pour
le domaine.

## Construction topologique

`topology.py` : `analyze_topology` / `build_circuit_topology`. Union-find avec
compression de chemin et racine déterministe ; nœuds = bornes des types connus
et jonctions ; arêtes = connexions valides. Connexions non orientées : extrémités
en ordre canonique (défaut détecté par le test de permutation et corrigé
pendant le ticket). Aucune dépendance aux positions, rotations, routes,
annotations, références visibles ni à l'ordre des collections.

## Réseaux dérivés

`CircuitNet(key, terminals, junctions, reference)`, membres triés, clé JSON
canonique, réseaux triés par clé ; aucune identité persistée, aucun indice ni
ordre de construction.

## GND

Toutes les bornes de rôle `reference` fusionnent en un seul réseau, même non
reliées. La fusion est une référence commune : aucune tension, source ni
énergie n'apparaît dans le modèle (test sur la représentation de la topologie).

## Validation topology

Erreurs : `component-not-found`, `terminal-not-found`, `junction-not-found`,
`self-connection`. Avertissements : `duplicate-connection` (A–B ≡ B–A),
`junction-dangling` (degré 0 ou 1). Plusieurs connexions par borne admises ;
croisements sans effet. La vérification géométrique des routes n'est **pas**
de la topologie : déplacée vers FD-GRAPHICS-003 / adaptateur Circuit, et le
périmètre Circuit est corrigé en conséquence.

## Electrical readiness

Avertissements seulement : `missing-property`, `unconnected-terminal`,
`source-shorted`, `missing-ground`. Un schéma incomplet est sauvegardé et relu
sans erreur.

## Diagnostics

Codes `circuit.*`, `SpecializedIssue` et `SpecializedValidationResult` du
socle. Ordre : `structure`, `topology`, `electrical-readiness` ; dans chaque
niveau, ordre du document puis des règles. Bornés à 512, troncature signalée.
`CIRCUIT_RESOURCE_TYPE` déclare les trois niveaux ; bloquants `structure` et
`topology` (le socle ne bloque que les erreurs). `CircuitCodec.validate`
revalide le format puis applique `validate_circuit`. Contrat spécialisé
inchangé.

## Invariants

| Invariant | Preuve |
|---|---|
| 8 types exactement | `test_exactly_eight_types_in_order` |
| Aucune heuristique par nom | Comportements par rôle ; pas d'identifiant historique ; mutants « ordre des bornes » et « masse source » tués par les contrats |
| Bornes et polarités explicites | `test_terminal_contracts`, `test_terminal_definition_refused` |
| Propriétés en allowlist ; propriété runtime refusée | `test_unknown_property`, `test_runtime_property_refused` |
| Valeur absente ≠ zéro | `test_zero_is_a_value`, `test_no_property_is_invented` |
| Type, borne, composant, jonction inexistants refusés | Tests domaine et topologie localisés |
| Croisement neutre, jonction explicite connecte | Cas F et G |
| Routes, positions, rotations, ordre sans effet | `test_geometry_and_presentation_do_not_change_topology`, `test_permutation_invariance` (5 graines) |
| Masses fusionnées, masse non source | `test_multiple_grounds_merge_without_source` |
| Readiness non bloquant ; structure et topologie bloquantes | Tests d'écriture |
| Validateur pur | `test_validator_is_pure` |

## Relation avec Graphic Core

Directions de ports déclarées ; projection `resistor → ports t1 (W), t2 (E)`
sans ambiguïté (test). Aucun `GraphicScene` ; contrat Graphics inchangé.

## Compatibilité simulation future

`domain_kind`, rôles, polarités, unités SI, état `closed` et correspondances
DrawCiel permettent une traduction sans `type.startswith(...)`. Aucun modèle
physique, IR, MNA, SPICE, QEMU ni Arduino.

## Fermeture de la limite properties de FD-CIRCUIT-002

FD-CIRCUIT-002 ne pouvait refuser une clé arbitraire dans `properties`. Le
domaine la refuse désormais (`circuit.unknown-property`, structure, bloquant) ;
`voltage` n'est admis que sur `dc-source`. Le test de format correspondant est
renommé (`test_runtime_like_property_keys_are_format_valid`) et renvoie au
test de domaine.

## Tests

| Fichier | Tests |
|---|---|
| `tests/test_circuit_catalog.py` (nouveau) | 64 |
| `tests/test_circuit_domain.py` (nouveau) | 22 |
| `tests/test_circuit_topology.py` (nouveau) | 21 |
| `tests/test_circuit_validation.py` (nouveau) | 22 |
| `tests/test_circuit_codec.py` | 34 |
| `tests/test_circuit_resource.py` | 21 |
| `tests/test_circuit_schema.py` | 10 |
| `tests/test_circuit_models.py` | 105 |

Total Circuit : 299. Les tests de format gardent `SAMPLE` (`placeholder`) ;
les tests passant par le validateur complet utilisent `CIRCUIT`, schéma
synthétique valide sans diagnostic (pile, interrupteur, résistance, LED,
masse, jonction). Régressions spécialisées : 156 réussies.

## Mutations

20 mutants, tous tués. Un premier passage a donné de faux résultats : une
mutation permutant deux lignes conservait la taille du fichier, et sa
restauration dans la même seconde laissait un `.pyc` périmé ; la campagne a été
refaite sans bytecode (`-B`, `PYTHONDONTWRITEBYTECODE`), caches supprimés.

| Mutant | Tué par |
|---|---|
| Type inconnu accepté | `test_unknown_type` |
| Propriété inconnue acceptée | `test_unknown_property` |
| Propriété runtime acceptée (voltage autorisé sur résistance) | contrat catalogue ; aussi `test_runtime_property_refused` |
| Mauvais type de propriété accepté | `test_invalid_property` |
| Polarité non contrôlée par le rôle | `test_terminal_definition_refused` |
| Ordre des bornes de source inversé | `test_terminal_contracts` |
| Borne inexistante acceptée | `test_missing_component_terminal_and_junction` |
| Composant inexistant accepté | idem |
| Jonction inexistante acceptée | idem |
| Auto-connexion acceptée | `test_self_connection_is_an_error` |
| Doublon non détecté | `test_duplicate_connection_is_a_warning_in_both_directions` |
| Positions influençant la topologie | `test_geometry_and_presentation_do_not_change_topology` |
| Routes influençant la topologie | `test_crossing_without_junction_is_neutral` |
| Ordre des collections influençant les réseaux | `test_permutation_invariance` |
| Extrémités non canoniques | `test_permutation_invariance` |
| Masses multiples non fusionnées | `test_multiple_grounds_merge_without_source` |
| Masse traitée comme source | contrat catalogue ; aussi `test_nominal_round_trip` |
| Propriété requise absente ignorée | `test_resistor_without_value` |
| Readiness bloquant l'écriture | `test_declarations` |
| Erreur de topologie non bloquante | `test_declarations` ; aussi `test_topology_error_blocks_write` |

Équivalences de comportement assumées : les mutants « polarité non
contrôlée » et « ordre des bornes inversé » ne changent aucun résultat de
validation ou de topologie, puisque rien ne lit l'ordre ni ne dérive la
polarité ; « readiness bloquant » ne change rien tant que ce niveau n'émet que
des avertissements (le socle ne bloque que des erreurs). Ils sont tués au
niveau du contrat, qui est leur bon niveau de preuve.

## Performance

Union-find O((V + E) α) puis tris O(n log n) ; détection de doublons par
ensemble ; degrés par dictionnaire. Corpus de 3 000 résistances chaînées
(3 001 réseaux) dans la suite : 0,11 s, construction du document comprise ;
aucun benchmark fragile.

## Packaging

Aucun changement de `pyproject.toml` : les nouveaux modules appartiennent au
package `forge_design.circuit` déjà déclaré. Aucune dépendance.

## Installation wheel

Wheel construite : `catalog.py`, `domain.py`, `topology.py`, `validation.py`
présents avec les modules de FD-CIRCUIT-002 et le schéma. Installée isolément :
catalogue des huit types, document construit, topologie (4 réseaux, 1 de
référence), avertissements de préparation, écriture puis relecture sans
erreur (niveau `electrical-readiness` seul).

## Questions reportées

Positions locales des bornes et symboles (FD-GRAPHICS-002) ; validation
géométrique des routes (FD-GRAPHICS-003) ; projection `GraphicScene`
(FD-CIRCUIT-004) ; préfixes de référence (éditeur) ; étiquettes de réseau
nommées ; modèles physiques, IR et moteur (FD-CIRCUIT-008+) ; extension du
catalogue ; provenance des symboles SVG DrawCiel.

## Fichiers créés

- `forge_design/circuit/catalog.py`, `domain.py`, `topology.py`, `validation.py`
- `tests/test_circuit_catalog.py`, `tests/test_circuit_domain.py`,
  `tests/test_circuit_topology.py`, `tests/test_circuit_validation.py`
- `docs/circuit/circuit-domain.md`, `docs/rapports/FD-CIRCUIT-003.md`

## Fichiers modifiés

- `forge_design/circuit/__init__.py` (API publique), `codec.py` (validation de
  domaine), `contract.py` (trois niveaux, blocage structure/topology)
- `tests/circuit_support.py` (schéma valide `CIRCUIT`), `test_circuit_codec.py`,
  `test_circuit_resource.py`, `test_circuit_models.py`
- `docs/circuit/circuit-resource.md`, `docs/circuit/circuit-scope.md`,
  `docs/02-architecture.md`, `docs/03-roadmap.md`,
  `docs/graphics/drawciel-reference.md`

Non modifiés : format V0.1 et schéma JSON, contrat spécialisé, contrat de
stockage, contrat Graphics, SéquenCiel (hors `git fetch`).

## Validation globale finale

| Contrôle | Résultat |
|---|---|
| `python -m compileall -q forge_design` | Réussi |
| `ruff check forge_design tests` | Réussi |
| `ruff format --check .` | 367 fichiers conformes |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Réussi |
| Tests Circuit (8 fichiers) | 299 réussis |
| Régressions spécialisées | 156 réussies |
| Suite globale `pytest` (hors du dépôt, `--basetemp` sous `tmp/` ignoré par Git) | **4509 réussis**, relancée après insertion de ces résultats |
| `python -m pip check` | Aucune dépendance cassée |
| Wheel installée isolément | Scénario complet réussi |
| Navigateur | Sans objet (aucune UI) |

## État Git final

Avant commit :

```text
$ git status --short
 M docs/02-architecture.md
 M docs/03-roadmap.md
 M docs/circuit/circuit-resource.md
 M docs/circuit/circuit-scope.md
 M docs/graphics/drawciel-reference.md
 M docs/rapports/FD-CONTRACT-001.md
 M forge_design/circuit/__init__.py
 M forge_design/circuit/codec.py
 M forge_design/circuit/contract.py
 M tests/circuit_support.py
 M tests/test_circuit_codec.py
 M tests/test_circuit_models.py
 M tests/test_circuit_resource.py
?? docs/circuit/circuit-domain.md
?? docs/rapports/FD-CIRCUIT-003.md
?? forge_design/circuit/catalog.py
?? forge_design/circuit/domain.py
?? forge_design/circuit/topology.py
?? forge_design/circuit/validation.py
?? tests/test_circuit_catalog.py
?? tests/test_circuit_domain.py
?? tests/test_circuit_topology.py
?? tests/test_circuit_validation.py
```

Commit unique : `feat: implémenter le domaine Circuit V1 (FD-CIRCUIT-003)`.
`docs/rapports/FD-CONTRACT-001.md` reste hors commit. Aucun push.
