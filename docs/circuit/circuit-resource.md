# Ressource Circuit V0.1

Statut : **normatif et implémenté** (FD-CIRCUIT-002). Schéma :
[`forge_design/circuit/circuit.schema.json`](../../forge_design/circuit/circuit.schema.json)
(JSON Schema 2020-12) ; application : modèles Pydantic stricts de
`forge_design.circuit`, sans dépendance `jsonschema`.

## Objectif

Rendre persistante une ressource Circuit **exacte et minimale** : créée, lue,
validée structurellement, sérialisée de façon déterministe, réécrite avec
révision, protégée contre les conflits et journalisée. Ni catalogue, ni
topologie, ni géométrie de symbole, ni routage, ni rendu, ni éditeur, ni
simulation : ces responsabilités arrivent avec FD-CIRCUIT-003 et les tickets
Graphics.

## Relation avec Graphic Core

Le fichier Circuit est la **seule source de vérité** ; aucun `GraphicsDocument`
n'est persisté. Le document adopte les **conventions de champs** du
[Graphic Core](../graphics/graphics-core-contract.md#projection-des-documents-métier)
(`position {x, y}`, `rotation` en degrés, route = `mode` + `points`
intermédiaires) mais reste propriétaire de son schéma, de sa version, de ses
identités, de sa validation et de sa sémantique.

```text
CircuitDocument ──(adaptateur Circuit, futur)──▶ GraphicScene (reconstructible) ──▶ Graphic Core
```

Les extrémités restent **métier** (`terminal`, `junction`) plutôt que
`node`/`port` : l'adaptateur les projettera sans seconde identité
(§ Projection Graphics future).

## Emplacement

Zone C, sources du projet versionnées par Git :

```text
mvc/circuit/**/*.circuit.json
```

Sous-dossiers autorisés (`mvc/circuit/led/simple.circuit.json`). L'espace
`mvc/circuit/` doit exister : l'hôte ne crée aucun dossier. La politique de
chemins est celle du socle spécialisé : chemin relatif, aucun segment caché ou
`..`, aucun nom sensible, aucun lien, fichier ordinaire. Hors de `mvc/views`
(contrats et designs) et de `.forge-design` (zone B).

## Suffixe

`.circuit.json`. Un nom réduit au suffixe est refusé par le socle.

## Version

```json
"format_version": "0.1"
```

Versions lues `{"0.1"}`, version écrite `"0.1"`. La version est lue **avant**
tout décodage métier : absente ou non textuelle ⇒ `invalid-resource` ;
inconnue ⇒ `unsupported-version`, sans appel au décodeur. `0.x` est un format
pré-stable (contrat de stockage §5) ; tout changement qu'un lecteur 0.1
interpréterait mal augmente la version.

## Encodage

UTF-8 strict ; JSON sans clé dupliquée, sans `NaN` ni `Infinity`
(`loads_strict_json`) ; champs inconnus interdits à tous les niveaux ; `null`
interdit (absence = clé omise) ; types stricts : un nombre décimal, un booléen
ou une chaîne ne remplacent jamais un entier.

## Identités

| Genre | Préfixe | Exemple |
|---|---|---|
| Composant | `c_` | `c_k7v4xQm2Lr9TzA1b` |
| Connexion | `e_` | `e_92mqaP0dXkF3sW7u` |
| Jonction | `j_` | `j_h8dr1Nc4Vb6Ye2Zo` |
| Annotation | `a_` | `a_t4p3fJ5gHs8Kq0Wi` |

- Forme `<préfixe>_<jeton>`, jeton base64url de 8 à 64 caractères
  (`[A-Za-z0-9_-]`), longueur totale ≤ 66.
- Générées par `new_component_id`, `new_connection_id`, `new_junction_id`,
  `new_annotation_id` : `secrets.token_urlsafe(12)`, 16 caractères, **96 bits**
  d'entropie ; aucune dépendance UUID.
- **Espace de noms global** au document : une identité n'apparaît qu'une fois,
  toutes collections confondues (`first_duplicate_identity`, O(n)). Les
  préfixes rendent une collision inter-genres inexprimable ; la règle reste
  globale par construction.
- Une identité manquante, mal formée, mal préfixée ou dupliquée est **refusée**,
  jamais régénérée.
- Les références visibles (`R1`) et les indices (`components[3]`) ne sont
  jamais des identités ; l'indice n'apparaît que dans la localisation d'un
  diagnostic.

Politique de **découpe d'une connexion** (pour la future commande
`InsertJunction`) : quand `A ── e1 ── B` devient `A ── J ── B`, la connexion qui
porte l'extrémité `A` **conserve `e1`**, la seconde reçoit une nouvelle identité.
La commande désigne explicitement l'extrémité conservée ; la décision ne dépend
ni des coordonnées, ni du sens visuel, ni d'un tri. La **fusion** d'une jonction
de degré 2 conserve l'identité de la connexion désignée par la commande, selon
la même logique explicite.

## Document racine

```json
{
  "format_version": "0.1",
  "page": {"width": 80, "height": 60},
  "components": [],
  "connections": [],
  "junctions": [],
  "annotations": []
}
```

Six champs exacts, tous obligatoires (collections éventuellement vides).
`new_circuit_document()` renvoie ce document : aucune date, aucun utilisateur,
aucun chemin, aucune machine, aucun identifiant de document (le chemin de la
ressource suffit en V0.1).

## Page

Page unique ; `width` et `height` entiers dans `[1, 4096]`, en unités de grille
Circuit. Aucun pixel, DPI ni zoom. Page par défaut : 80 × 60.

## Composants

```json
{
  "id": "c_k7v4xQm2Lr9TzA1b",
  "type": "placeholder",
  "reference": "R1",
  "position": {"x": 12, "y": 8},
  "rotation": 90,
  "properties": {"resistanceOhms": 220}
}
```

| Champ | Règle |
|---|---|
| `id` | Identité `c_` |
| `type` | Identifiant lexical `^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$`, ≤ 64 ; l'existence dans le catalogue relève de FD-CIRCUIT-003 |
| `reference` | Facultative, **omise** si absente ; 1 à 32 caractères sans contrôle |
| `position` | Point de grille (convention Graphics), entiers `[0, 4096]` |
| `rotation` | Entier `0`, `90`, `180` ou `270` (convention Graphics restreinte par Circuit) |
| `properties` | § Propriétés |

Aucune borne n'est copiée dans le composant : les bornes appartiennent au type
du catalogue (pas de duplication type/instance, pas de `terminalOverrides`).

## Endpoints

Union discriminée par `kind` :

```json
{"kind": "terminal", "component_id": "c_k7v4xQm2Lr9TzA1b", "terminal_id": "anode"}
{"kind": "junction", "junction_id": "j_h8dr1Nc4Vb6Ye2Zo"}
```

`terminal_id` : `^[a-z][a-z0-9_]*$`, ≤ 64. Les identités référencées sont
contrôlées **lexicalement** (bon préfixe) ; leur existence, celle de la borne
dans le type et l'auto-connexion relèvent du niveau `topology` (FD-CIRCUIT-003).

## Connexions

`id` (`e_`), `a`, `b`, `route`. Exactement deux extrémités ; aucune connexion
n-aire ; aucune extrémité libre persistée (un tracé en cours est runtime). Une
connexion dont les deux extrémités sont identiques est structurellement
représentable et sera refusée par la topologie.

## Routes

```json
"route": {"mode": "orthogonal", "points": [{"x": 15, "y": 8}, {"x": 15, "y": 20}]}
```

- Convention Graphics : `mode` + **points intermédiaires** ; aucune extrémité
  (`start`/`end`) dans la route, les extrémités dérivent des bornes et jonctions.
- `mode` vaut toujours `orthogonal` en V0.1 ; il est conservé pour rester
  conforme à la convention Graphics, qui connaît aussi `straight`.
- `points` vide : le routeur décidera la polyligne orthogonale minimale.
- Au plus 256 points entiers. Orthogonalité et colinéarité relèvent d'un niveau
  de validation géométrique ultérieur, pas du codec.

## Jonctions

`id` (`j_`) et `position`. Concept **Circuit** : ni type, ni référence, ni
propriétés, ni degré persisté (le degré est dérivé).

## Annotations

Texte seulement : `id` (`a_`), `kind: "text"`, `position`, `text`. Texte brut
UTF-8 de 1 à 4096 caractères, saut de ligne LF et tabulation admis, aucun autre
caractère de contrôle ; jamais interprété (ni HTML ni Markdown). **Aucun champ
de présentation** en V0.1 : le futur renderer appliquera un style unique ; une
présentation (taille, alignement) sera ajoutée par une nouvelle version lorsque
l'éditeur en aura besoin.

## Propriétés

Objet `clé → scalaire`, au plus 64 entrées, ordre du document conservé :

- clés `^[A-Za-z][A-Za-z0-9_]*$`, ≤ 64 (compatibles avec les clés des contrats
  DrawCiel comme `resistanceOhms`) ;
- valeurs : chaîne de 1 à 256 caractères, booléen, entier sûr
  `|n| ≤ 2⁵³ − 1` (exactement représentable par le Graphic Core en JavaScript),
  ou nombre décimal fini ;
- un entier JSON hors de l'intervalle sûr est **refusé**, jamais converti en
  décimal ; pas de `null` (absence = clé omise), pas de chaîne vide, pas de
  structure imbriquée.

Exposées en lecture seule (`MappingProxyType`), sérialisées comme objet JSON.
Les propriétés autorisées par type, leurs unités et contraintes relèvent du
catalogue (FD-CIRCUIT-003).

## État exclu

Aucun champ structurel ne peut porter : sélection, survol, viewport, zoom, pan,
historique, `dirty`, réseau (`net`), tension, courant, température, dommage,
état de simulation, mesures, préférences d'interface, données pédagogiques ou
élèves. Tout champ inconnu est refusé à tous les niveaux.

**Limite assumée** : FD-CIRCUIT-002 interdit les champs runtime structurels
mais ne peut pas encore interdire une clé arbitraire placée dans `properties` ;
cette garantie viendra de l'allowlist de propriétés par type de FD-CIRCUIT-003.
Aucune liste noire de clés n'est ajoutée au codec.

## Limites

Module `forge_design/circuit/limits.py` :

| Constante | Valeur | Raison |
|---|---|---|
| `MAX_CIRCUIT_RESOURCE_BYTES` | 4 Mio | Plusieurs milliers d'objets tiennent sous 1 Mio ; 64 Mio reste le plafond technique du socle |
| `MAX_CIRCUIT_PAGE_UNITS` | 4096 | Dimensions et coordonnées de grille |
| `MAX_CIRCUIT_COMPONENTS` | 4096 | Au-delà d'un schéma lisible ; borne les algorithmes futurs |
| `MAX_CIRCUIT_CONNECTIONS` | 8192 | Environ deux connexions par composant |
| `MAX_CIRCUIT_JUNCTIONS` | 4096 | |
| `MAX_CIRCUIT_ANNOTATIONS` | 4096 | |
| `MAX_CIRCUIT_ROUTE_POINTS` | 256 par connexion | Une route orthogonale lisible a quelques coudes |
| `MAX_CIRCUIT_PROPERTIES` | 64 par composant | Le plus riche des 110 profils DrawCiel (`aac36b27`) en déclare 8 (LED) |
| `MAX_CIRCUIT_TEXT_CHARS` | 4096 | |
| `MAX_CIRCUIT_ID_CHARS` | 66 | Préfixe + jeton ≤ 64 |
| `MAX_CIRCUIT_TYPE_CHARS` | 64 | |
| `MAX_CIRCUIT_TERMINAL_ID_CHARS` | 64 | |
| `MAX_CIRCUIT_REFERENCE_CHARS` | 32 | |
| `MAX_CIRCUIT_PROPERTY_KEY_CHARS` | 64 | |
| `MAX_CIRCUIT_PROPERTY_TEXT_CHARS` | 256 | |
| `MAX_CIRCUIT_SAFE_INTEGER` | 2⁵³ − 1 | Interopérabilité JavaScript |

La taille en octets est contrôlée par le socle avant toute analyse. La
validation structurelle est O(n) dans la taille du document.

## Validation structurelle

`CircuitCodec.decode` : octets → UTF-8 → JSON strict → `CircuitDocument`.
Les erreurs deviennent des issues `structure`, sévérité `error`, localisées par
chemin réel dans le document (étiquettes internes de Pydantic retirées) :

| Code | Situation |
|---|---|
| `circuit.json-invalid` | UTF-8 invalide, JSON illisible, clé dupliquée, `NaN`/`Infinity`, imbrication excessive |
| `circuit.identity-invalid` | Identité absente, mal formée ou mal préfixée (`id`, `component_id`, `junction_id`) |
| `circuit.identity-duplicate` | Identité déjà utilisée dans le document |
| `circuit.limit-exceeded` | Collection, chaîne ou borne supérieure dépassée |
| `circuit.validation-error` | Toute autre erreur structurelle (champ inconnu, `null`, type, version…) |

Au plus 512 issues (une de plus signale la troncature au socle).
`CircuitCodec.validate` revalide une copie sérialisée du modèle (utile pour un
modèle construit sans validation). Seul le niveau `structure` est déclaré et
implémenté ; `topology` et `electrical-readiness` seront déclarés par
FD-CIRCUIT-003 avec leurs validateurs : un niveau déclaré est un niveau
implémenté.

La détection de version, le contrôle JSON strict et la validation Pydantic
analysent chacun le texte (jusqu'à trois analyses) ; c'est accepté pour une
ressource bornée à 4 Mio, sans modifier le contrat spécialisé.

## Sérialisation canonique

`CircuitCodec.encode` : `json.dumps(..., ensure_ascii=False, indent=2,
allow_nan=False)` puis LF final, UTF-8. Ordre des champs = ordre du schéma ;
ordre des collections et des propriétés = ordre du document. Même document ⇒
mêmes octets ; décoder puis réencoder une ressource canonique restitue les
mêmes octets. Aucune normalisation Unicode. L'ordre des collections est
conservé pour l'édition, le rendu et les diffs Git, mais n'est jamais une
identité ni une topologie ; la future signature topologique sera invariante par
permutation.

## Projection Graphics future

| Circuit | Graphic Core |
|---|---|
| `CircuitPoint` | `Point` (sans perte : entiers) |
| `component.position`, `rotation` | `Node` : position, orientation |
| `component.id` | Identité du `Node` |
| `terminal` (`component_id`, `terminal_id`) | `Port` (`node`, `port`) |
| `junction` | `Node` sans obstacle + un `Port` omnidirectionnel |
| `connection` (`id`, `a`, `b`) | `Edge` |
| `route.points` | Points intermédiaires de la route |
| `annotation` texte | `TextAnnotation` |

Aucune seconde identité n'est inventée. Un test vérifie cette projection avec
une fonction limitée aux tests ; aucun `GraphicScene` n'existe en produit.

## SpecializedResourceType

```text
CIRCUIT_TOOL           id circuit, nom Circuit, aucune dépendance, aucune entrée UI
CIRCUIT_RESOURCE_TYPE  id schematic, format circuit-json, suffixe .circuit.json,
                       préfixe mvc/circuit, versions {0.1} / 0.1, éditable,
                       max_size 4 Mio, niveaux (structure), bloquant {structure}
capacités              create, open, validate, save
```

`edit` n'est pas déclarée : aucun éditeur Circuit n'existe encore (la
mutabilité d'un objet Python n'est pas une capacité produit). `export` et
`interactive-runtime` sont absentes. Aucun registre d'outils spécialisés.

## Lecture / écriture

Par le socle `forge_design.specialized`, sans code d'accès propre :

- `read_specialized_resource(root, CIRCUIT_TOOL, CIRCUIT_RESOURCE_TYPE, path, CircuitCodec())` ;
- `write_specialized_resource(..., expected_revision=None)` : création
  exclusive ; avec révision : mise à jour, conflit si la ressource a changé ;
- journal `history.jsonl`, action `write_specialized_resource`, champ `file` =
  chemin relatif ; aucune action propre à Circuit.

## Compatibilité DrawCiel

Aucune compatibilité de fichier en V0.1. Les décisions récentes de DrawCiel
sont respectées : bornes contractuelles hors de l'instance, aucun état
d'exécution dans le document, liste fermée des champs (comme la validation des
composants UNO R4, `aac36b27`), définitions versionnées, aucune sémantique
déduite d'un nom. Les clés de propriétés admettent les clés des contrats
DrawCiel ; leur alignement effectif est décidé par FD-CIRCUIT-003.

## Évolution du format

Toute évolution suit le contrat de stockage (§5) : nouvelle version déclarée
dans `read_versions`, écriture de la seule version courante, aucune réparation
silencieuse. Ajouts prévisibles : présentation du texte, étiquettes de réseau,
miroir. Une migration `0.x → 1` fera l'objet d'un ticket dédié.

## Questions reportées

| Question | Ticket |
|---|---|
| Catalogue V1, définitions de types, bornes et directions | FD-CIRCUIT-003 |
| Propriétés autorisées par type (allowlist), unités, polarités | FD-CIRCUIT-003 |
| Topologie, nets dérivés, existence des références, auto-connexion | FD-CIRCUIT-003 |
| Validation `electrical-readiness` | FD-CIRCUIT-003 |
| Primitives géométriques, orthogonalité des routes, positions dans la page | FD-GRAPHICS-002 / 003 |
| Projection `GraphicScene` réelle | FD-CIRCUIT-004 |
| Renderer, éditeur, commandes (`InsertJunction`) | FD-GRAPHICS-004 / 005, FD-CIRCUIT-004 / 005 |
| Simulation | FD-CIRCUIT-008 et suivants |
