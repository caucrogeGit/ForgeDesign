# Rapport — FD-MODULES-001

Normatif : [Architecture des modules spécialisés](../modules/module-architecture.md).

## Ticket et objectif

Définir l'architecture officielle qui permet à Forge Design d'héberger des
modules spécialisés externes, sans embarquer leur logique métier dans le
cœur. Le ticket fixe la frontière core / module avant toute migration, sans
créer ni migrer le module Circuit.

## État Git initial

```text
$ git log --oneline -5
69f48d8 feat: migrer Debug Center sur le Graphic Core (FD-GRAPHICS-008)
c24dc6c feat: ajouter la minicarte au Graphic Core (FD-GRAPHICS-007)
3221814 feat: ajouter le semantic zoom au Graphic Core (FD-GRAPHICS-006)
04f0af8 feat: compacter le routage des graphes (FD-GRAPHICS-005)
00f9eaa feat: ajouter le viewport au Graphic Core (FD-GRAPHICS-004)
$ git rev-parse --short HEAD
69f48d8
$ git rev-parse --short origin/main
69f48d8
$ git status --short
 M docs/rapports/FD-CONTRACT-001.md
```

## Divergence HEAD / origin

`git rev-list --left-right --count origin/main...HEAD` → `0 0` :
**0 commit d'avance, 0 commit de retard**. Le ticket supposait `origin/main`
à `3221814`, mais FD-GRAPHICS-007 et FD-GRAPHICS-008 ont été poussés entre
la rédaction du ticket et son exécution. Le travail part du HEAD réel
`69f48d8`, qui contient les deux.

## Référence DrawCiel

`git fetch` dans la copie SéquenCiel (lecture seule) : `origin/main` =
`88f95b75`, inchangé. Delta vide, aucun impact. Ce ticket ne touche ni à la
géométrie, ni au rendu, ni à l'interaction.

## Pourquoi changer de phase

FD-GRAPHICS-008 a montré trois clients réels (Route, Entity, Debug) sur les
mêmes modules du Graphic Core, sans retouche du JavaScript pour le troisième.
La visualisation générique est donc éprouvée ; l'édition spécialisée ne l'est
pas. Ports, glisser, commandes, annulation et rétablissement, accroche, routage
interactif, multi-sélection et édition de propriétés ne seront plus conçus
dans le vide. **Toute nouvelle capacité d'édition générique doit être motivée
par un besoin réel d'un module spécialisé.**

## Périmètre du core

Application Forge MVC ; analyse de projet Forge (cinq Tools) ; Template
Designer ; Graphic Core (JS) et couloirs Python (`forge_design.graphics`) ;
hôte de ressources spécialisées ; système de fichiers sécurisé ; historique,
révision et conflits ; contrat spécialisé (`forge_design.specialized`) et
contrat des modules (`forge_design.modules`).

| Élément | Forge Design core | Module spécialisé |
|---|---|---|
| Forge project analysis | oui | non |
| Graphic Core | oui | non |
| viewport/minimap/LOD | oui | non |
| ResourceHost | oui | non |
| secure filesystem | oui | non |
| history/conflict | oui | non |
| domain schema | non | oui |
| domain validation | non | oui |
| catalog | non | oui |
| domain graphics adapter | non | oui |
| simulation | non | oui |
| optional domain dependencies | non | oui |

## Hors core

Toute sémantique de domaine : résistance, LED, tension, courant, simulation
électrique, routeur IP, protocole réseau, sémantique d'organigramme. Le JS
d'édition propre à un domaine.

## État actuel Specialized

Inspecté et **réutilisé tel quel** (aucune modification) :

- `forge_design/specialized/models.py` (402 lignes) :
  - `SpecializedToolDefinition` : identité kebab-case, types, capacités,
    dépendances, `UiEntry` ;
  - `SpecializedResourceType` : espace, suffixe, versions, taille, niveaux,
    état persistant et runtime ;
  - `SpecializedCapability` (vocabulaire plateforme fermé, plus capacités
    d'outil), `OptionalDependency`, `SpecializedIssue`,
    `SpecializedValidationResult`.
- `forge_design/specialized/resource.py` (543 lignes) :
  - Protocol `SpecializedResourceCodec` (`detect_version`, `decode`,
    `encode`, `validate`), qui ne traite que des octets ;
  - `read_specialized_resource` et `write_specialized_resource` :
    confinement, `O_NOFOLLOW`, bornes, révision, publication atomique,
    historique.

Aucun registre, chargeur ni entry point : le contrat FD-SPECIALIZED-001
réservait explicitement cette question (« Registre d'outils spécialisés —
après FD-SPECIALIZED-002 »). Ce ticket la tranche.

## État actuel Circuit

Paquet `forge_design/circuit/` (FD-CIRCUIT-002 et 003, 1 510 lignes Python et
un schéma JSON), déclaré dans `pyproject.toml` (paquet et `package-data`).

- **Aucun module du cœur n'importe Circuit** : la direction des dépendances
  est déjà la bonne, et elle est désormais vérifiée par un test.
- Circuit dépend du cœur par `forge_design.specialized`,
  `forge_design.json_strict` (`loads_strict_json`) et deux constantes de
  `forge_design.limits` (`MAX_SPECIALIZED_ISSUES`,
  `MAX_SPECIALIZED_LOCATION_DEPTH`).
- `CIRCUIT_TOOL` est une `SpecializedToolDefinition` descriptive, jamais
  enregistrée, sans `ui_entry`.

## Matrice de migration Circuit

Inspectée fichier par fichier dans le dépôt réel :

| Élément actuel | Emplacement | Destination future | Action |
|---|---|---|---|
| `__init__.py` (75 l.) — API publique Circuit | `forge_design/circuit` | `forge_design_circuit/__init__.py`, plus `FORGE_DESIGN_MODULE` | MIGRATE (MODULE) |
| `models.py` (295 l.) — `CircuitDocument` Pydantic, pages, composants, connexions, routes, annotations | `forge_design/circuit` | `forge_design_circuit/models.py` | MIGRATE (MODULE) |
| `codec.py` (159 l.) — octets ↔ document ; utilise `json_strict`, `limits`, `specialized` | `forge_design/circuit` | `forge_design_circuit/codec.py`, devient le `ResourceBinding.codec` | MIGRATE (MODULE) ; imports du cœur via l'API publique (ligne suivante) |
| `loads_strict_json`, `MAX_SPECIALIZED_ISSUES`, `MAX_SPECIALIZED_LOCATION_DEPTH` | `forge_design/json_strict.py`, `forge_design/limits.py` | restent au cœur, exposés par `forge_design.specialized` | SHARED CONTRACT (à exposer par FD-MODULES-003) |
| `circuit.schema.json` (8,5 Kio) — schéma du format | `forge_design/circuit` | `forge_design_circuit/circuit.schema.json` (`package-data` du module) | MIGRATE (MODULE) |
| `contract.py` (50 l.) — `CIRCUIT_RESOURCE_TYPE`, `CIRCUIT_TOOL` (`id="circuit"`) | `forge_design/circuit` | `forge_design_circuit/contract.py`, base du `ModuleDescriptor` | MIGRATE (MODULE) |
| `ids.py` (52 l.) — identités `c_`, `e_`, `j_`, `a_` | `forge_design/circuit` | `forge_design_circuit/ids.py` | MIGRATE (MODULE) |
| `limits.py` (32 l.) — bornes Circuit | `forge_design/circuit` | `forge_design_circuit/limits.py` | MIGRATE (MODULE) |
| `catalog.py` (373 l.) — catalogue V1 fermé | `forge_design/circuit` | `forge_design_circuit/catalog.py` | MIGRATE (MODULE) |
| `domain.py` (60 l.) — structure de domaine | `forge_design/circuit` | `forge_design_circuit/domain.py` | MIGRATE (MODULE) |
| `topology.py` (314 l.) — réseaux électriques (union-find) | `forge_design/circuit` | `forge_design_circuit/topology.py` | MIGRATE (MODULE) |
| `validation.py` (100 l.) — structure, topologie, préparation électrique | `forge_design/circuit` | `forge_design_circuit/validation.py` | MIGRATE (MODULE) |
| Tool definition `CIRCUIT_TOOL` | `contract.py` | descripteur du module | MIGRATE avec le module |
| `tests/circuit_support.py` (194 l.) | `tests/` | suite du module | MIGRATE (MODULE) |
| `tests/test_circuit_{catalog,codec,domain,models,resource,schema,topology,validation}.py` (2 258 l.) | `tests/` | suite du module | MIGRATE (MODULE) ; plus aucun test métier Circuit dans le cœur |
| `docs/circuit/circuit-scope.md`, `circuit-resource.md`, `circuit-domain.md` | `docs/circuit` | documentation du module, avec un renvoi dans le cœur | MIGRATE (bandeau ajouté dès ce ticket) |
| `docs/rapports/FD-CIRCUIT-001…003.md` | `docs/rapports` | restent au cœur (historique), cités par la provenance | CORE (archives) |
| `pyproject.toml` : `forge_design.circuit` (paquet et `package-data`) | `pyproject.toml` | supprimés dans le commit de retrait | DELETE LATER |
| Contrat spécialisé, hôte, `json_strict`, `limits` spécialisés | `forge_design/specialized`, `forge_design/` | restent | CORE / SHARED CONTRACT |

## Architecture cible

```text
Forge Design (forge-design)
├── analyse Forge (5 Tools) · Template Designer · Graphic Core
├── forge_design.specialized  (contrat de ressources, hôte de lecture/écriture)
└── forge_design.modules      (ModuleDescriptor, activation explicite)
          ▲  API publique uniquement
          │
ForgeDesign-Circuit (forge-design-circuit, forge_design_circuit)
├── FORGE_DESIGN_MODULE = ModuleDescriptor(...)
├── format, codec, catalogue, validation, topologie
├── projection CircuitDocument → GraphicScene
└── assets JS/CSS déclarés (plus tard, édition)
```

Livré par ce ticket : `forge_design/modules/` (`descriptor.py`,
`activation.py`), sans câblage Web.

## Direction des dépendances

Module → cœur, jamais l'inverse. Le cœur n'importe un module que par
`activate_modules`, à partir d'un nom configuré : c'est une dépendance
d'exécution contrôlée, pas une dépendance statique. Tests :

- aucun fichier de `forge_design/` hors `circuit/` n'importe
  `forge_design.circuit` ni `forge_design_circuit` ;
- `forge_design.modules` n'importe que `forge_design.specialized` et la
  bibliothèque standard.

## ModuleDescriptor

`ModuleDescriptor` (gelé, validé à la construction) :

| Champ | Contenu |
|---|---|
| `definition` | `SpecializedToolDefinition` existante, avec un identifiant d'au plus 32 caractères |
| `version` | Version du paquet |
| `api_version` | Entier |
| `bindings` | Un `ResourceBinding` (codec complet, projection Graphics facultative) par type déclaré, ni plus ni moins |
| `asset_package` | Paquet portant les assets |
| `assets` | Au plus 32 `ModuleAsset` |
| `dependency_probe` | Sonde facultative |

Calculés par l'hôte, jamais choisis par le module : `base_url`
(`/modules/<id>/`), `asset_url`, `media_type`. Le descripteur ne reçoit ni
Router, ni Application, ni Request, ni racine de projet.

## Activation explicite

`activate_modules(paquets, importer)` : seuls les paquets nommés sont
importés, dans l'ordre configuré ; chacun expose `FORGE_DESIGN_MODULE`. Sans
liste, rien n'est importé (test). La liste vient de la configuration de
lancement, que FD-MODULES-002 fixera (CLI ou configuration utilisateur),
**jamais du projet ouvert**.

| Option | Verdict |
|---|---|
| A. Liste Python explicite | retenue (forme) |
| B. Configuration projet | **refusée** : ouvrir un projet non fiable exécuterait du code |
| C. Entry points allowlistés | refusée en V1 : balayage de l'environnement, rien de plus qu'un nom |
| D. Registre statique côté application | retenu (lieu : racine de composition) |

## Discovery refusée

Ni `importlib.metadata`, ni `entry_points`, ni `pkgutil`, ni `sys.path`
dans `forge_design.modules` (test et mutation). Raisons : exécution de code
arbitraire, surface d'attaque, ordre implicite, débogage difficile.

## Compatibilité

`MODULE_API_VERSION = 1` ; `SUPPORTED_MODULE_API_VERSIONS = {1}`.
Appartenance à un ensemble, sans solveur. Une version non supportée donne le
diagnostic `api-incompatible` : module non activé, les autres continuent.

## Resource types

`SpecializedResourceType` inchangé. Un module déclare ses types et fournit
un codec pour chacun. Deux modules ne peuvent pas revendiquer le même couple
(espace de sources, suffixe) : `duplicate-resource-type`. Le chemin projet
(`mvc/circuit/`) ne dépend pas du paquet Python.

## Filesystem boundary

Le module ne lit ni n'écrit le projet. Le codec du module traite des octets ;
l'hôte (`read/write_specialized_resource`) lit, écrit, borne, contrôle la
révision et journalise. Test de bout en bout : un module activé (témoin) est
lu **par l'hôte** avec le codec du module, puis projeté en GraphicScene par
sa projection.

## Validation

Trois couches, inchangées :

- structurelle : décodage et format, dans le codec ;
- métier : niveaux déclarés par le type (Circuit : `structure`,
  `topology`, `electrical-readiness`) ;
- blocage : `blocking_validation_levels`, appliqué par l'hôte à l'écriture.

Le cœur ne connaît aucune règle métier.

## Graphic Core integration

Projection `document → GraphicScene` par module (Python,
`ResourceBinding.scene`, ou JS si l'édition l'exige). Le Graphic Core ne
connaît pas le document et ne change pas (aucun fichier `static/graphics/`
modifié ; 99 tests Node verts). Le JS d'un module peut importer
`/graphics/*.js` ; le cœur n'importe jamais ce JS.

## Assets module

Liste fermée, déclarée par le module :

- nom `[a-z0-9-]+.(js|css|svg)` ;
- source relative dans `asset_package`, refusée si elle est absolue, vide,
  contient `.`, `..`, un segment caché, une barre oblique inverse, un NUL ou
  une double barre (13 cas testés) ;
- type MIME fixé par l'hôte selon l'extension ;
- au plus 32 assets, sans doublon.

Le service HTTP arrive avec FD-MODULES-002, à
`/modules/<id>/assets/<name>`. CSP inchangée : ni CDN, ni JS en ligne, ni
`unsafe-eval`.

## Web integration

V1 (FD-MODULES-002) : ouvrir et visualiser, en **GET** seulement, sur des
routes fixes enregistrées par l'hôte. Le module ne fournit pas de handler
Forge MVC (option restrictive) et ne voit ni Request, ni Response, ni Router.
L'édition passera par des actions bornées POST
(`/modules/<id>/actions/<nom>`), avec le contrôle d'origine du cœur et une
sauvegarde par l'hôte. Elles ne sont pas figées avant le premier besoin
réel.

## Namespace

**`/modules/<id>/`**, avec ses sous-espaces `assets/` et, plus tard,
`actions/`. Aucune collision possible avec `/routes`, `/entities`, `/debug`,
`/editor`, `/graphics`.

## Navigation

Une zone « Modules » du shell (FD-MODULES-002) liste les modules installés,
compatibles, activés et munis d'une `UiEntry`, avec un lien vers leur
`base_url`. Module désactivé : aucune route, aucun asset, aucune entrée.

## ToolRegistry

**Inchangé**, avec ses cinq Tools : `project-inspector`, `route-explorer`,
`entity-explorer`, `debug-center` et `template-viewer` (test). Un Tool
analyse un projet Forge ; un module apporte une capacité spécialisée. Les
modules ne deviennent jamais des Tools : la distinction est normative.

## Optional dependencies

`OptionalDependency` inchangée, plus `dependency_probe`. L'activation
calcule `available_capabilities` (déclarées moins celles d'une dépendance
absente) et `unavailable_dependencies`. Une sonde en échec donne le
diagnostic `dependency-probe-failed` : capacités dépendantes indisponibles,
module actif. Exemple futur : Circuit ouvert et visualisé, simulation
indisponible.

## Versioning

Deux niveaux : `ModuleDescriptor.version`, la version du paquet ; et
`api_version`, la compatibilité avec l'hôte. La métadonnée Python
`forge-design >= X, < Y` du module gouverne l'installation.

## Security model

| Action | Core | Module |
|---|---|---|
| lire fichier projet | oui via host | non directement |
| écrire fichier projet | oui via host | non directement |
| décoder bytes métier | non | oui |
| encoder bytes métier | non | oui |
| servir asset déclaré | oui | déclare |
| modifier Router arbitrairement | non | non |
| exécuter JS métier installé | host sert | oui |
| installer dépendance | non | non automatiquement |

Un module Python installé reste **du code de confiance local**. Forge Design
ne sandboxe pas Python, et le JS d'un module partage l'origine. Le contrat
empêche les accès accidentels par construction, pas un module malveillant.
D'où l'activation explicite et le refus de l'option B.

## Failure isolation

- Configuration malformée (nom invalide, chaîne au lieu d'une liste, doublon)
  : `ValueError` immédiate, avant tout import (*fail-fast*).
- Module absent : `module-missing`.
- Dépendance interne absente d'un module installé : `module-import-failed`,
  et non « non installé ». Ce défaut, trouvé en vérifiant l'absence réelle de
  `forge_design_circuit`, est corrigé et testé.
- Exception à l'import (dont un descripteur invalide) :
  `module-import-failed`.
- Attribut absent ou invalide : `descriptor-missing`, `descriptor-invalid`.
- `api-incompatible`, `duplicate-module`, `duplicate-resource-type`,
  `dependency-probe-failed`.

Dans tous les cas, les autres modules continuent, dans l'ordre configuré.

## Missing modules

Fichiers `mvc/circuit/*.circuit.json` sans module : préservés, jamais
modifiés, supprimés ni interprétés. Le cœur n'a pas à nommer « Circuit ».
Pas de concept de « ressource inconnue » tant qu'il n'est pas utile. Aucune
installation automatique.

## Packaging

Confirmé après inspection : le dépôt du cœur s'appelle `ForgeDesign` et sa
distribution `forge-design`.

| Élément | Choix |
|---|---|
| Dépôt | `ForgeDesign-Circuit` |
| Distribution | `forge-design-circuit` |
| Paquet | `forge_design_circuit` |
| Identifiant de module | `circuit` |

Le sous-paquet `forge_design.circuit` est rejeté : `forge_design` est un
paquet ordinaire, pas un espace de noms partagé, et un préfixe distinct rend
la frontière visible. `forge_design.modules` est ajouté à la liste des paquets
de `pyproject.toml`.

## Repositories

**Dépôt séparé dès la V1** : cycle de release distinct, dépendances
distinctes (simulation future), domaine isolé, cœur utilisable seul. Le
monorepo est rejeté : il retisserait la dépendance par commodité (imports
croisés, tests mêlés) et imposerait au cœur le rythme du domaine.

## Development workflow

`pip install -e ../ForgeDesign-Circuit` dans l'environnement de
développement de Forge Design, puis activation explicite du paquet
`forge_design_circuit`. Pas de `PYTHONPATH` bricolé.

## Testing strategy

- Cœur : tests de contrat avec un module témoin injecté par un importeur de
  test (`tests/test_modules_contract.py`), sans `sys.path` ni paquet
  installé, et tests de frontière. Après la migration, aucun test métier
  Circuit dans le cœur.
- Module : sa propre suite (domaine, codec, projection), et compatibilité
  contre la version minimale supportée de Forge Design.
- CI future du module : matrice version minimale / dernière version du cœur.
  Elle est documentée seulement, pas implémentée.

## Migration Git Circuit

Historique réel inspecté. Cinq commits touchent Circuit :

- `233e146` FD-CIRCUIT-001 (documentation) ;
- `c2a135e` FD-GRAPHICS-001 (documentation) ;
- `d8275f2` FD-CIRCUIT-002 ;
- `2023aea` FD-CIRCUIT-003 ;
- `f9fe502` FD-GRAPHICS-002.

Deux d'entre eux mêlent Circuit et Graphics. Les fichiers sont répartis sur
trois arborescences : `forge_design/circuit`, `tests/` et `docs/circuit`.

| Option | Verdict |
|---|---|
| A. Nouveau dépôt initialisé par copie, avec provenance | **retenue** |
| B. `git filter-repo` | rejetée : commits mixtes découpés en commits partiels trompeurs, réécriture complexe pour 3 commits utiles |
| C. `subtree split` | rejetée : inapplicable à trois arborescences, et mêmes commits mixtes |

Plan (FD-MODULES-003) :

1. Créer `ForgeDesign-Circuit` par copie du contenu au commit source nommé
   (HEAD du cœur au moment de l'extraction).
2. Ajouter un fichier `PROVENANCE.md` : dépôt et commit source, chemins
   copiés, commits d'origine (`233e146`, `d8275f2`, `2023aea`, plus
   `c2a135e` et `f9fe502` pour les retouches) et rapports
   FD-CIRCUIT-001 à 003.
3. Adapter les imports (`forge_design.circuit` → `forge_design_circuit`) et
   exposer `FORGE_DESIGN_MODULE`.
4. Retirer `forge_design/circuit/`, les tests et le `package-data` du cœur
   dans un commit ultérieur, en référençant le commit du module.

Aucune réécriture de l'historique du cœur.

## DrawCiel

Reste une référence de développement (procédure `drawciel-reference.md`),
jamais une dépendance d'exécution, ni du cœur ni d'un module. Un éventuel
import de documents DrawCiel serait un outil de migration explicite.

## SequenCiel

Aucune dépendance : ni du cœur, ni d'un module. Le futur module Circuit ne
dépendra jamais de SéquenCiel.

## Template Designer

Reste au cœur : il sert directement la construction d'applications Forge et
n'est pas un domaine métier externe. Circuit n'est pas un bloc du Template
Designer (contrat FD-SPECIALIZED-001 inchangé).

## 3D

Conceptuel seulement : un futur moteur 3D n'est pas une extension
automatique du Graphic Core 2D. Ce serait une capacité ou un module séparé, à
étudier le moment venu. Rien n'est implémenté.

## Décisions prises

| | Question | Décision |
|---|---|---|
| A | Forge Design fonctionne-t-il sans module ? | **Oui** : rien n'est importé sans configuration ; Tools, Template Designer, Graphic Core et hôte sont inchangés |
| B | Le cœur dépend-il statiquement de Circuit ? | **Non** (test de frontière sur tout `forge_design/` hors `circuit/`) |
| C | Circuit dépend-il de Forge Design ? | **Oui**, par l'API publique : `forge_design.specialized`, `forge_design.modules`, contrat GraphicScene, `/graphics/*.js` |
| D | Découverte automatique ? | **Non en V1** |
| E | Activation explicite ? | **Oui** : liste de paquets venant de la configuration de lancement, jamais du projet |
| F | Un module lit-il directement le projet ? | **Non** : il ne traite que des octets, l'hôte lit et écrit |
| G | Un module enregistre-t-il n'importe quelle route ? | **Non** : l'hôte enregistre des routes fixes, sous l'espace du module |
| H | Namespace Web ? | **`/modules/<id>/`** (`assets/<name>`, puis `actions/<nom>`) |
| I | API des modules ? | **`MODULE_API_VERSION = 1`**, ensemble supporté `{1}`, séparé de la version du paquet |
| J | Distribution et dépôt Circuit ? | Dépôt `ForgeDesign-Circuit`, distribution `forge-design-circuit`, paquet `forge_design_circuit`, identifiant `circuit` |
| K | Que devient `forge_design/circuit/` ? | Gelé (aucune nouvelle fonctionnalité), migré fichier par fichier selon la matrice, puis retiré du cœur ; FD-CIRCUIT-004 n'est pas poursuivi dans le cœur |
| L | Stratégie Git ? | **Option A** : nouveau dépôt par copie et `PROVENANCE.md`, retrait ultérieur, sans réécriture |
| M | Le ToolRegistry change-t-il ? | **Non** (5 Tools, test) |
| N | Le Graphic Core change-t-il ? | **Non** |
| O | Prochain ticket : hôte ou migration ? | **L'hôte d'abord (FD-MODULES-002)**, puis la migration (FD-MODULES-003). Migrer d'abord produirait un module sans hôte pour l'activer ni rien pour l'afficher, et figerait son intégration avant que l'hôte n'existe. L'hôte, prouvé avec un faux module dans deux navigateurs, donne à l'extraction une cible stable. Circuit, sans interface et gelé, ne crée aucune dette entre-temps |

## Décisions reportées

| Question | Ticket |
|---|---|
| Source exacte de la liste d'activation (option CLI, configuration utilisateur) | FD-MODULES-002 |
| Pages hôte, vue d'une ressource, zone « Modules », service des assets | FD-MODULES-002 |
| Exposition de `loads_strict_json` et des bornes spécialisées par `forge_design.specialized` | FD-MODULES-003 |
| Actions d'édition POST bornées | Premier besoin d'édition d'un module |
| Détection opaque de ressources inconnues | Si elle devient utile |
| Moteur 3D | Phase 11, comme capacité ou module séparé |

## Roadmap

Nouvelle **Phase Modules** dans `docs/03-roadmap.md` :

- Graphics : socle de visualisation éprouvé, édition à construire pilotée
  par un module ;
- Circuit : suspendu dans le cœur, migration hors core avant poursuite ;
- FD-MODULES-002 (hôte), puis FD-MODULES-003 (extraction de Circuit), puis
  les tickets du module.

## Fichiers créés

- `forge_design/modules/__init__.py`, `forge_design/modules/descriptor.py`,
  `forge_design/modules/activation.py`
- `tests/test_modules_contract.py`
- `docs/modules/module-architecture.md`
- `docs/rapports/FD-MODULES-001.md`

## Fichiers modifiés

- `pyproject.toml` (paquet `forge_design.modules`)
- `docs/02-architecture.md`, `docs/03-roadmap.md`,
  `docs/specialized-tools/specialized-tool-contract.md`
- `docs/circuit/circuit-scope.md`, `circuit-resource.md`, `circuit-domain.md`
  (bandeau de migration)

## Validation finale

| Contrôle | Résultat |
|---|---|
| `python -m compileall -q forge_design` | Réussi |
| `ruff check forge_design tests` | Réussi |
| `ruff format --check .` | 397 fichiers conformes (Markdown compris) |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Réussi |
| Contrat des modules (`tests/test_modules_contract.py`) | 45 réussis |
| Ciblés : contrat, Specialized, Circuit, frontière Graphics | 503 réussis |
| Mutations du contrat (doublons, API, ressources, configuration, traversée, espace d'URL, codec, dépendances, absence ou dépendance interne, découverte) | 10/10 tuées |
| Suites Node Graphics (aucun JS modifié) | 99 réussis |
| Suite globale `pytest` (hors du dépôt, `--basetemp` court sous `tmp/`) | **4713 réussis**, relancée après insertion de ces résultats |
| `python -m pip check` | Aucune dépendance cassée |
| Wheel | `forge_design/modules/` présent ; installé isolément, s'importe sans charger Circuit ; `forge_design_circuit` absent → `module-missing` |
| Navigateurs | Non requis : aucun runtime Web modifié (`forge_design/web`, `app.py`, `platform` inchangés) |
| MkDocs | N/A : aucune configuration MkDocs dans Forge Design |

## État Git final

Commit unique `feat: définir le contrat des modules spécialisés (FD-MODULES-001)`
(un contrat exécutable minimal est ajouté), au-dessus de `69f48d8`.
`docs/rapports/FD-CONTRACT-001.md` reste modifié localement, hors commit.
Aucun push.
