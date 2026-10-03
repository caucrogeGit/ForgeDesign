# Rapport — FD-CIRCUIT-002

Format normatif : [Ressource Circuit V0.1](../circuit/circuit-resource.md).

## Ticket et objectif

Définir puis implémenter le contrat persistant minimal de Circuit V0.1 :
emplacement, suffixe, version, identités, structure, conventions Graphics
adoptées, limites, JSON Schema, modèles Pydantic, codec, sérialisation
canonique, lecture et écriture par le socle spécialisé. Sans catalogue,
géométrie de symbole, routage, renderer, éditeur ni simulation.

## État Git initial

```text
$ git log -1 --oneline
c2a135e docs: définir le noyau graphique commun depuis DrawCiel (FD-GRAPHICS-001)
$ git rev-parse origin/main
c2a135e06c7bbb69ad99125ca125ae845fa97786
$ git status --short
 M docs/rapports/FD-CONTRACT-001.md
```

Baseline conforme ; `FD-CONTRACT-001.md` conservé hors commit.

## Référence DrawCiel précédente

`c229b2ed` (FD-GRAPHICS-001), consignée dans
[Référence DrawCiel](../graphics/drawciel-reference.md).

## Référence DrawCiel du ticket

Procédure appliquée avant toute construction : `git fetch` dans SéquenCiel
(seule opération sur ce dépôt), `origin/main` = **`aac36b27`**
(3 octobre 2026, « feat(drawciel): intégrer et qualifier le profil
expérimental UNO R4 »), désormais publié. `DRAWCIEL_REFERENCE_CURRENT` =
`aac36b27`, figée pour le ticket. Journal mis à jour.

## Delta DrawCiel

`c229b2ed..aac36b27` (un commit, 564 fichiers) : profil UNO R4 / RA4M1,
ADR-287 à 306, contrats de périphériques (GPIO, ADC, UART, PWM, I²C, SPI,
DAC), QEMU et Renode, cosimulation, frontières runtime, qualification
fonctionnelle. Éléments examinés en plus de l'analyse de FD-GRAPHICS-001 :
`mvc/services/drawciel.py` (+8 lignes) et `mvc/services/drawciel_r4/document.py`.

**Nouveau** : la validation serveur d'un composant R4 applique une **liste
fermée de champs** (`CHAMPS`), exige `properties` et `state` vides, une
`board_definition_version` égale à `"1"`, refuse tout état d'exécution au
niveau racine et toute redéfinition (`terminalOverrides`, `customDefs`) de la
carte. Les champs `flipX`/`flipY` figurent dans cette liste sans usage dans
`app.js`. Un aiguillage par identifiant de carte apparaît dans `app.js`
(résolution des bornes, palette, simulation).

## Impact du delta

| Domaine | Impact |
|---|---|
| Graphic Core | Aucun changement architectural |
| Circuit V0.1 | Aucun nouveau champ |
| Simulation future | Significatif (contrats de périphériques, cosimulation) : à conserver pour les tickets ultérieurs |
| Microcontrôleurs | Hors Phase 10 ; aucun code R4, MCU, QEMU ni cosimulation dans Forge Design |

Principes confirmés et appliqués : interfaces explicites, capacités déclarées,
contrats versionnés, aucune sémantique déduite d'un nom, état transitoire hors
document, runtime séparé, qualification par capacité. L'aiguillage par
identifiant de carte est une dette DrawCiel à ne pas reproduire.

## Décisions de format

| Sujet | Décision |
|---|---|
| Zone, emplacement | Zone C, `mvc/circuit/**/*.circuit.json`, sous-dossiers autorisés |
| Suffixe | `.circuit.json` |
| Version | `format_version: "0.1"` obligatoire, lue avant décodage |
| Identités | `<préfixe>_<jeton>`, `c_`/`e_`/`j_`/`a_`, espace global, 96 bits |
| Découpe d'une connexion | La connexion portant l'extrémité désignée (A) conserve l'identité |
| Racine | Six champs exacts, tous obligatoires |
| Coordonnées | Entiers de grille `[0, 4096]` ; page `[1, 4096]` |
| Rotation | `0`, `90`, `180`, `270` entiers |
| Extrémités | Union discriminée `terminal` / `junction` |
| Route | `mode: "orthogonal"` + points intermédiaires |
| Annotation | Texte brut, sans présentation |
| Propriétés | Clé → scalaire (chaîne, booléen, entier sûr, décimal fini) |
| Niveaux de validation | `structure` seul, déclaré et implémenté |
| Capacités | `create`, `open`, `validate`, `save` |

## Relation avec Graphic Core

Aucun `GraphicsDocument`, aucun module Graphics créé. Le document adopte les
conventions de champs (`position {x, y}`, `rotation`, route = `mode` + points
intermédiaires) et reste propriétaire de son schéma. Le contrat Graphics n'a
pas été modifié : aucune incohérence révélée. Les extrémités restent métier ;
leur projection `Node`/`Port` est vérifiée par une fonction limitée aux tests
(`test_projection_reuses_identities_without_loss`).

## Emplacement et suffixe

`CIRCUIT_SOURCE_PREFIX = "mvc/circuit"`, `CIRCUIT_SUFFIX = ".circuit.json"`.
Ajouté au tableau de la zone C du contrat de stockage. Hors `mvc/views` et
`.forge-design`. L'hôte ne crée pas l'arborescence
(`test_missing_source_space_is_not_created`).

## Version

`read_versions = {"0.1"}`, `write_version = "0.1"`. Version absente ou non
textuelle : `invalid-resource` sans décodage ; version inconnue :
`unsupported-version` sans décodage (`test_version_is_checked_before_decode`,
espion sur `decode`). Le codec seul refuse aussi une version absente ou
inconnue.

## JSON Schema

`forge_design/circuit/circuit.schema.json`, Draft 2020-12, sans `$id`,
`additionalProperties: false` sur tous les objets, collections bornées
(`maxItems`), motifs d'identité par genre, extrémité en `oneOf` (sans le
mot-clé non standard `discriminator`). Le schéma est normatif ; Pydantic
l'applique, aucune dépendance `jsonschema`. Concordance vérifiée par
comparaison avec `CircuitDocument.model_json_schema()` (titres, descriptions et
`discriminator` retirés). Règles d'exécution non exprimables en JSON Schema,
décrites dans le schéma : unicité globale des identités, refus de la conversion
d'un grand entier en décimal.

## Identités

`forge_design/circuit/ids.py` : `new_component_id`, `new_connection_id`,
`new_junction_id`, `new_annotation_id` (`secrets.token_urlsafe(12)`, 16
caractères, 96 bits), `id_pattern`, `is_circuit_id`. Validation : jeton
base64url 8 à 64 caractères, total ≤ 66. Unicité globale par
`first_duplicate_identity` (O(n), toutes collections confondues). Identité
manquante, mal formée, mal préfixée ou dupliquée : refusée, jamais régénérée.
Les indices ne servent qu'à localiser un diagnostic. 8 000 identités générées
sans collision observée ; aucun test sur une valeur exacte.

## Politique de découpe de connexion

`A ── e1 ── B` découpée par `J` : la connexion portant l'extrémité désignée par
la commande (A) conserve `e1`, l'autre reçoit une nouvelle identité. La future
commande `InsertJunction` désigne explicitement ce côté ; la fusion d'une
jonction de degré 2 suit la même règle. Aucune décision géométrique ou par tri.
Documenté dans la ressource et le périmètre Circuit ; aucune commande
implémentée.

## Document racine

`format_version`, `page`, `components`, `connections`, `junctions`,
`annotations`, tous obligatoires. Champs inconnus refusés (`viewport`,
`selection`, `history`, `simulation`, `dirty`, `nets`, `tp`…).
`new_circuit_document()` : page 80 × 60, collections vides, aucune donnée
utilisateur ou machine, aucun identifiant de document.

## Page

Entiers `[1, 4096]` en unités de grille ; aucun pixel, DPI ni zoom.

## Composants

`id`, `type` (lexical, existence non vérifiée : `placeholder` est valide),
`reference` facultative omise (jamais `null`), `position`, `rotation`,
`properties`. **Aucune borne** dans l'instance. Champs directs `voltage`,
`current`, `temperature`, `state`, `terminals` refusés.

## Endpoints

`{"kind": "terminal", "component_id", "terminal_id"}` ou
`{"kind": "junction", "junction_id"}` ; préfixe vérifié (`c_` / `j_`) avant
toute vérification d'existence ; existence et bornes : FD-CIRCUIT-003.

## Connexions

Exactement deux extrémités ; aucune extrémité libre ; auto-connexion
représentable structurellement (refus topologique ultérieur).

## Routes

`mode` toujours `orthogonal` (conservé pour la convention Graphics), points
intermédiaires entiers, au plus 256 ; aucune extrémité dans la route
(`start`/`end` refusés). Orthogonalité et colinéarité non validées par le codec.

## Jonctions

`id` et `position` seulement ; ni type, référence, propriétés ni degré.
Distincte d'un composant (préfixe `j_`, collection propre).

## Annotations

Texte seul (`kind: "text"`), brut, LF et tabulation admis, 1 à 4096 caractères,
aucun champ de présentation : le strict minimum, une présentation viendra avec
l'éditeur par une nouvelle version.

## Propriétés

Au plus 64 entrées ; clés `^[A-Za-z][A-Za-z0-9_]*$` compatibles avec les clés
DrawCiel ; valeurs chaîne (1 à 256), booléen, entier `|n| ≤ 2⁵³ − 1`, décimal
fini. Un entier JSON hors intervalle sûr est refusé : Pydantic l'aurait sinon
converti silencieusement en décimal (défaut détecté et corrigé pendant le
ticket). Exposition en lecture seule par `MappingProxyType`.

## État runtime exclu

Aucun champ structurel runtime, dérivé, de simulation, de mesure, d'interface
ou pédagogique n'est accepté, à aucun niveau (`extra="forbid"` partout, tests
paramétrés). Aucun réseau ni borne persistés.

> **Limite** : `FD-CIRCUIT-002` interdit les champs runtime structurels mais ne
> peut pas encore interdire une clé arbitraire placée dans `properties` ; cette
> garantie viendra de l'allowlist de propriétés par type de `FD-CIRCUIT-003`.

Un test le constate explicitement
(`test_runtime_like_property_keys_are_not_yet_refused`) ; aucune liste noire
n'est ajoutée au codec.

## Limites

`forge_design/circuit/limits.py` (module dédié : seize constantes propres à
Circuit, `forge_design/limits.py` inchangé) : 4 Mio, page et coordonnées 4096,
4096 composants, 8192 connexions, 4096 jonctions, 4096 annotations, 256 points
par route, 64 propriétés, textes 4096, identités 66, type 64, borne 64,
référence 32, clé 64, valeur texte 256, entier sûr 2⁵³ − 1. Justifications dans
la ressource ; le profil DrawCiel le plus riche déclare 8 propriétés. Chaque
limite de collection et de texte est testée à la borne puis à la borne + 1.

## Modèles Pydantic

`forge_design/circuit/models.py` : `CircuitPoint`, `CircuitPage`,
`CircuitComponent`, `TerminalEndpoint`, `JunctionEndpoint`, `CircuitRoute`,
`CircuitConnection`, `CircuitJunction`, `CircuitTextAnnotation`,
`CircuitDocument`. Configuration `extra="forbid"`, `strict=True`,
`frozen=True`, `allow_inf_nan=False` ; collections en `tuple` ; `null` refusé
pour les champs omissibles ; rotation et décimaux protégés par des validateurs
avant conversion (une rotation `90.0` était acceptée par le `Literal` :
détecté et corrigé). En mode Python strict, les collections doivent être des
tuples ; le JSON accepte des tableaux.

## Codec

`CircuitCodec` implémente `SpecializedResourceCodec[CircuitDocument]` :

- `detect_version` : JSON strict, lecture du seul `format_version`, aucune
  validation de modèle (vérifié par un test qui interdit `model_validate*`) ;
- `decode` : UTF-8 → `loads_strict_json` (clés dupliquées, `NaN`, `Infinity`)
  → `CircuitDocument.model_validate_json` → issues `circuit.*` localisées par le
  chemin réel (étiquettes d'union retirées), bornées à 512 + 1 ;
- `encode` : sérialisation canonique ;
- `validate` : revalide une copie sérialisée, niveau `structure` uniquement.

Codes : `circuit.json-invalid`, `circuit.validation-error`,
`circuit.identity-invalid`, `circuit.identity-duplicate`,
`circuit.limit-exceeded`. Le JSON est analysé jusqu'à trois fois par lecture
(détection, contrôle strict, Pydantic) ; accepté pour 4 Mio, contrat spécialisé
inchangé. Pydantic ne détecte pas les clés dupliquées en JSON, d'où le contrôle
strict préalable.

## Sérialisation canonique

UTF-8, `ensure_ascii=False`, `indent=2`, `allow_nan=False`, LF final ; ordre
des champs du schéma, ordre des collections et des propriétés du document.
Même document ⇒ mêmes octets ; décoder puis réencoder restitue les octets ;
aucune normalisation Unicode (forme décomposée conservée).

## SpecializedResourceType

`CIRCUIT_RESOURCE_TYPE` : `schematic`, `circuit-json`, `.circuit.json`,
`mvc/circuit`, `{0.1}` / `0.1`, éditable, 4 Mio, niveaux `("structure",)`,
bloquant `{structure}`, état persistant (`page`, `components`, `connections`,
`junctions`, `annotations`), état runtime (`selection`, `viewport`, `history`,
`dirty`, `simulation`). `CIRCUIT_TOOL` : `circuit`, « Circuit », aucune
dépendance optionnelle, aucune entrée UI, aucun registre. Le contrat permet de
ne déclarer que les niveaux implémentés : `topology` et
`electrical-readiness` seront ajoutés par FD-CIRCUIT-003 (niveau déclaré =
niveau implémenté). Contrat spécialisé non modifié.

## Capabilities

`create`, `open`, `validate`, `save`. `edit` non déclarée : aucun éditeur
n'existe ; la mutabilité d'un objet Python n'est pas une capacité produit.
`export` et `interactive-runtime` absentes.

## Lecture

`read_specialized_resource(root, CIRCUIT_TOOL, CIRCUIT_RESOURCE_TYPE, path,
CircuitCodec())` : ressource égale au document écrit, révision cohérente,
issues `circuit.*` pour une structure invalide (`invalid-resource`).

## Écriture

`write_specialized_resource(..., expected_revision=None)` : création
exclusive ; avec révision : mise à jour. Un document construit sans validation
et invalide n'est jamais écrit (`InvalidSpecializedResourceError`, aucun
fichier, aucun journal).

## Round-trip

Document → `encode` → `detect_version` → `decode` → égal ; octets identiques
après lecture par l'hôte et réencodage.

## Conflits

Création sur une cible existante : conflit. Lecture → modification externe →
sauvegarde : conflit, fichier externe intact, une seule ligne de journal.

## Journal

Chaque écriture : `action = write_specialized_resource`,
`file = mvc/circuit/led/simple.circuit.json`. Aucune action propre à Circuit.

## Sécurité filesystem

Couverture exhaustive dans le socle ; cas d'intégration Circuit : préfixe
(`mvc/views/foo.circuit.json` refusé), suffixe (`.json`, `.circuit.json.bak`),
`..`, segment caché, chemin absolu, nom réduit au suffixe, lien symbolique
(refusé en lecture ; écriture refusée en création comme en mise à jour, cible
extérieure intacte), taille supérieure à 4 Mio refusée avant analyse.

## Tests

| Fichier | Tests | Contenu |
|---|---|---|
| `tests/test_circuit_schema.py` | 10 | Dialecte, racine stricte, collections bornées, objets fermés, page/point/rotation, motifs d'identité, composant sans bornes, route et extrémités, absence d'état runtime, concordance, packaging |
| `tests/test_circuit_models.py` | 105 | Document vide, gel, tuples, entiers stricts, rotation, propriétés, clés, référence omise, type lexical, champs runtime refusés, limite `properties`, extrémités, connexions, routes, annotations, identités par genre, doublons, espace global, génération, indices, API publique, projection Graphics |
| `tests/test_circuit_codec.py` | 34 | Round-trip, octets canoniques, Unicode, ordre, détection de version, version absente/inconnue, JSON invalide, localisation, codes, limites exactes et +1, issues bornées, `validate` |
| `tests/test_circuit_resource.py` | 21 | Déclarations, création/lecture/mise à jour/journal, octets exacts, création exclusive, conflit externe, espace absent, confinement, lien, version avant décodage, codes `circuit.*`, document invalide jamais écrit, taille |

`tests/circuit_support.py` fournit un document synthétique (aucune donnée
réelle). Régressions : `test_specialized_models.py`,
`test_specialized_resource.py` et les tests d'historique, de stockage, d'I/O
design et de source : **389 réussis**.

## Mutations

Campagne ciblée : 18 mutants, tous **tués**, aussi bien avec la suite Circuit
complète qu'**en excluant** le test de concordance du schéma (preuve par les
seuls tests de comportement).

| Mutant | Résultat |
|---|---|
| `format_version` facultative | Tué (après ajout de `test_missing_version_decode_refused` : survivant aux seuls tests de comportement lors du premier passage) |
| Version inconnue décodée (modèle) | Tué |
| Version inconnue lue (type) | Tué |
| Champ supplémentaire accepté | Tué |
| Coordonnée décimale acceptée | Tué |
| Rotation 45 acceptée | Tué |
| Identité mal préfixée acceptée | Tué |
| Collision inter-genres acceptée (unicité par collection) | Tué (après extraction de `first_duplicate_identity`, testable directement : les préfixes rendent la collision inexprimable dans un document) |
| `null` accepté | Tué |
| Route avec extrémité dupliquée (`start`) | Tué |
| `nets` persistés | Tué |
| Champ runtime racine (`viewport`) | Tué |
| Mauvais préfixe de source | Tué |
| Suffixe contourné | Tué |
| Limite de collection ignorée | Tué |
| Encodage non déterministe | Tué |
| `detect_version` validant le document | Tué |
| Clés JSON dupliquées acceptées au décodage | Tué |

Aucun mutant sur le type inconnu, la borne inconnue, l'orthogonalité ou les
valeurs électriques : responsabilités de FD-CIRCUIT-003/004.

## Packaging

`pyproject.toml` : `forge_design.circuit` dans `packages`,
`circuit.schema.json` en `package-data`. Aucune dépendance ajoutée, aucun
JavaScript.

## Installation wheel

`python -m pip wheel --no-deps --wheel-dir tmp/wheels-circuit .` : la wheel
contient `forge_design/circuit/{__init__,codec,contract,ids,limits,models}.py`
et `circuit.schema.json`. Installée isolément (`pip install --target`), module
chargé depuis l'installation : schéma lu par `importlib.resources`, encodage
déterministe, création, lecture, mise à jour, modification externe → conflit
détecté, deux lignes de journal `write_specialized_resource`.

## Questions reportées

Catalogue V1 ; définitions de types ; bornes et directions ; propriétés
autorisées (allowlist) et unités ; polarités ; topologie ; nets dérivés ;
existence des références et auto-connexion ; validation
`electrical-readiness` ; projection `GraphicScene` réelle ; géométrie
(orthogonalité, positions dans la page) ; routage ; renderer ; éditeur et
commandes (`InsertJunction`) ; simulation. Le contrat spécialisé mentionne
encore « Chemin exact et format des ressources Circuit » dans ses questions
reportées ; non modifié conformément au ticket, la réponse est désormais dans
la ressource Circuit.

## Fichiers créés

- `forge_design/circuit/__init__.py`, `ids.py`, `limits.py`, `models.py`,
  `codec.py`, `contract.py`, `circuit.schema.json`
- `tests/circuit_support.py`, `tests/test_circuit_schema.py`,
  `tests/test_circuit_models.py`, `tests/test_circuit_codec.py`,
  `tests/test_circuit_resource.py`
- `docs/circuit/circuit-resource.md`, `docs/rapports/FD-CIRCUIT-002.md`

## Fichiers modifiés

- `pyproject.toml` : package et données.
- `docs/storage/storage-contract.md` : ligne `mvc/circuit/**/*.circuit.json`
  en zone C, espace réservé.
- `docs/circuit/circuit-scope.md` : questions tranchées fermées (format,
  suffixe, version, espace, identités, découpe, limites).
- `docs/graphics/drawciel-reference.md` : référence `aac36b27` et journal.
- `docs/02-architecture.md` : sous-section « Ressource Circuit V0.1 ».
- `docs/03-roadmap.md` : FD-CIRCUIT-002 annoté comme fait.

Non modifiés : contrat spécialisé, contrat Graphics, `forge_design/limits.py`,
SéquenCiel (hors `git fetch`), Forge.

## Validation globale finale

| Contrôle | Résultat |
|---|---|
| `python -m compileall -q forge_design` | Réussi |
| `ruff check forge_design tests` | Réussi |
| `ruff format --check .` | 357 fichiers conformes |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Réussi |
| Tests Circuit ciblés (4 fichiers) | 170 réussis |
| Régressions spécialisées, historique, stockage, I/O design, source | 389 réussis |
| Suite globale `pytest` (lancée hors du dépôt, `--basetemp` sous `tmp/` ignoré par Git, `/tmp` étant saturé par d'autres projets) | **4380 réussis**, relancée après insertion de ces résultats |
| `python -m pip check` | Aucune dépendance cassée |
| Wheel installée isolément | Scénario complet réussi |
| Navigateur | Sans objet (aucune UI) |

## État Git final

Avant commit :

```text
$ git status --short
 M docs/02-architecture.md
 M docs/03-roadmap.md
 M docs/circuit/circuit-scope.md
 M docs/graphics/drawciel-reference.md
 M docs/rapports/FD-CONTRACT-001.md
 M docs/storage/storage-contract.md
 M pyproject.toml
?? docs/circuit/circuit-resource.md
?? docs/rapports/FD-CIRCUIT-002.md
?? forge_design/circuit/
?? tests/circuit_support.py
?? tests/test_circuit_codec.py
?? tests/test_circuit_models.py
?? tests/test_circuit_resource.py
?? tests/test_circuit_schema.py
```

Commit unique : `feat: définir la ressource Circuit v0.1 (FD-CIRCUIT-002)`.
`docs/rapports/FD-CONTRACT-001.md` reste modifié localement, hors commit.
Aucun push.
