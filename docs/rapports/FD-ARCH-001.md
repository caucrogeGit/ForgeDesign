# Rapport — FD-ARCH-001

## Objectif

Répondre, preuves à l'appui, à la question : **Forge Design fournit-il un moteur
réellement générique capable d'accueillir plusieurs domaines spécialisés, sans
dépendance implicite à Circuit ?** Le ticket est un audit et une consolidation
limitée : auditer, classer, resserrer, tester, documenter. Aucune fonctionnalité
métier, aucun commit dans ForgeDesign-Circuit.

**Réponse : oui.** Le cœur ne contient aucune sémantique Circuit active, n'importe
aucun module, n'a pas eu à être modifié pour accueillir un second domaine (le
témoin « flowchart-like ») qui déclare, projette, pose un calque, agit et
recharge par le seul contrat public, à côté de Circuit dans la même application.
Le code de `forge_design/` est inchangé : l'audit n'a révélé aucun défaut
concret de frontière ; il ajoute des gardes, un second domaine témoin et une
documentation normative.

Décisions validées avant le lancement : matrice normative dans
`docs/architecture/core-module-boundaries.md` (référencée par
`02-architecture.md` et `module-architecture.md`) ; second témoin dans les tests
seulement, validation combinée avec Circuit hors suite ; exports figés et
classés sans retrait ; mutations sur la frontière réelle ; roadmap en quatre
pistes ; commit `docs:` si `forge_design/` reste intact.

## État Git initial

| Dépôt | État |
|---|---|
| Forge Design | `44ded4b` (FD-GRAPHICS-EDIT-002) ; `origin/main` = `691e83e` ; 1 commit local en avance ; seul `docs/rapports/FD-CONTRACT-001.md` modifié (hors commit, préservé) |

## État du module Circuit

| Élément | Valeur |
|---|---|
| HEAD | `6627212` (FDC-EDIT-007) ; `origin/main` = `536adfc` ; 5 commits locaux (FDC-EDIT-003 à 007), arbre propre |
| Usage | Lecture seule pour la preuve d'usage ; aucun commit, aucun push |

## Architecture actuelle

```text
Forge Design (application Forge MVC locale)
├── outils propres à Forge : Inspector, Route, Entity, Debug, Template Viewer/Designer
├── moteur générique
│   ├── hôte de ressources (forge_design.specialized) : FS sûr, révision, conflit, historique
│   ├── hôte des modules (forge_design.modules, web/modules.py) : activation, routes exactes,
│   │   assets déclarés, actions bornées, contexte d'édition
│   └── Graphic Core (web/static/graphics/*.js) + client /module-resource.js
└── modules externes activés explicitement (ForgeDesign-Circuit ; témoins des tests)
```

## Responsabilités Forge-specific

Project Inspector, détection et version Forge, Route Explorer, Entity Explorer,
Debug Center, Template Viewer et Designer, preview réelle, `ToolRegistry`
(exactement `project-inspector`, `route-explorer`, `entity-explorer`,
`debug-center`, `template-viewer`), `ProjectSelector`,
`CurrentProjectContext` (runtime seulement), projets récents (XDG).

## Responsabilités du moteur générique

Hôte de ressources (lecture, écriture, inventaire, révision, conflit,
historique) ; hôte des modules (activation explicite, diagnostics, routes GET et
POST exactes sous `/modules/<id>/`, assets, barrière de capacités, contexte
d'édition) ; actions bornées (`ModuleAction`, payload, jeton, PRG) ; Graphic Core
(scène, rendu, viewport, minicarte, niveaux de détail, sélection de nœuds,
`nodeMove`, calques monde, `worldAt`, `onViewChange`) ; client générique des
ressources de module.

## Responsabilités des modules

Format, codec, validation métier, projection document → `GraphicScene`,
transformation pure des actions, script et configuration d'édition, vocabulaire
et géométrie métier (pour Circuit : bornes, fils, jonctions, routage, évitement).

## Matrice des frontières

Normative : [docs/architecture/core-module-boundaries.md](../architecture/core-module-boundaries.md).

| Élément | Forge-specific | Moteur générique | Module |
|---|:---:|:---:|:---:|
| Route Explorer, Entity Explorer, Debug Center, Inspector | ✓ | | |
| Template Viewer / Designer | ✓ | | |
| `ToolRegistry`, `ProjectSelector`, `CurrentProjectContext` | ✓ | | |
| ResourceHost (`read/write/list_specialized_resource`) | | ✓ | |
| ModuleHost, `activate_modules` | | ✓ | |
| `ModuleAction` (cycle hôte) | | ✓ | |
| Graphic Core, `/module-resource.js` | | ✓ | |
| Codec, validation, projection, handler, script d'édition | | | ✓ |
| Routage Circuit, évitement, dérivations | | | ✓ |

Matrice d'API (constat réel ; « Circuit » = usage par ForgeDesign-Circuit) :

| API | Introduite pour | Utilisée par Circuit | Générique ? | Publique ? | Décision |
|---|---|---|---|---|---|
| `ModuleDescriptor`, `ResourceBinding`, `ModuleAsset`, `MODULE_API_VERSION` | FD-MODULES-001/002 | oui | oui | oui | KEEP |
| `ModuleAction`, `ModuleActionPayload`, `ModuleActionRefused`, `ModuleActionResult` | FD-EDIT-001 | oui | oui | oui | KEEP |
| `ModuleActionPayloadError`, `ActionHandler`, bornes `MAX_MODULE_ACTION*`, `MAX_SAFE_INTEGER`, `RESERVED_ACTION_FIELDS` | FD-EDIT-001 | non | oui | oui | KEEP (DOCUMENT : audience module) |
| `activate_modules`, `ActiveModule`, `ModuleActivation`, `ModuleDiagnostic`, `SUPPORTED_MODULE_API_VERSIONS`, `DESCRIPTOR_ATTRIBUTE`, `MODULE_URL_PREFIX`, `ASSET_MEDIA_TYPES` | FD-MODULES-001/002 | non | oui | oui | DOCUMENT (audience hôte) |
| `SpecializedToolDefinition`, `SpecializedResourceType`, `SpecializedCapability`, `UiEntry`, `SpecializedIssue`, `SpecializedValidationResult`, `SpecializedFormatError` | FD-SPECIALIZED-001/002 | oui | oui | oui | KEEP |
| `loads_strict_json`, `MAX_SPECIALIZED_ISSUES`, `MAX_SPECIALIZED_LOCATION_DEPTH` | FD-MODULES-003 | oui | oui | oui | KEEP |
| `read/write/list_specialized_resource`, résultats et erreurs de ressource | FD-SPECIALIZED-002 | non (l'hôte les appelle) | oui | oui | DOCUMENT (audience hôte) |
| `ModuleHost` | FD-MODULES-002 | non | oui | non (sous-module) | PRIVATE (inchangé : non exporté) |
| `GraphicScene` / `GraphicNode` / `GraphicEdge` (JSON) | FD-GRAPHICS-001/002 | oui (projection) | oui | oui | KEEP ; projection runtime |
| `createGraphicEngine` | FD-GRAPHICS-002 | indirect (client générique) | oui | oui | KEEP |
| `scene()`, `node()` | FD-GRAPHICS-002/003 | oui | oui | oui | KEEP |
| `edge()` | FD-GRAPHICS-003 | **non** (arêtes lues dans `scene()`) | oui | oui | KEEP (cohérent avec `node()`) |
| `viewport()`, `detailLevel()` | FD-GRAPHICS-004/006 | oui | oui | oui | KEEP |
| `fit`, `home`, `zoom*`, `panBy`, `centerAt`, `resize`, `minimap()` | FD-GRAPHICS-004/007 | non | oui | oui | KEEP |
| `select`, `focus` | FD-GRAPHICS-002 | oui | oui | oui | KEEP |
| `clearSelection`, `selection()`, `onSelectionChange` | FD-GRAPHICS-002 | non | oui | oui | KEEP |
| `nodeMove`, `movableNodes()`, `movePreview()` | FD-GRAPHICS-EDIT-001 | `nodeMove` oui | oui | oui | KEEP |
| `addOverlay` | FD-GRAPHICS-EDIT-002 | oui | oui | oui | KEEP |
| `worldAt` | FD-GRAPHICS-EDIT-002 | oui | oui | oui | KEEP |
| `onViewChange` | FD-GRAPHICS-EDIT-002 | oui | oui | oui | KEEP |
| `render()`, `destroy()`, `isDestroyed()` | FD-GRAPHICS-002 | non | oui | oui | KEEP |
| `createResourceEditor(context)` → `{nodeMove?, onViewChange?, attach?}` | FD-GRAPHICS-EDIT-001/002 | oui | oui | oui | DOCUMENT (contrat JS consolidé) |

Aucune décision RENAME, HARDEN, DEPRECATE ou REMOVE : aucune API n'a montré de
défaut ; une capacité non utilisée par Circuit (`edge()`, navigation,
`clearSelection`) reste cohérente avec le moteur générique.

## API modules publique

`forge_design.modules.__all__` (25 symboles) et
`forge_design.specialized.__all__` (30 symboles) sont figés par
`test_public_exports_are_a_reviewed_snapshot` et classés par audience (module /
hôte) dans [module-architecture.md](../modules/module-architecture.md#api-publique-python).
Les sous-modules (`host`, `actions`, `descriptor`, `activation`, `listing`,
`resource`, `models`) sont internes. Circuit importe 8 symboles de
`forge_design.modules` et 10 de `forge_design.specialized`, tous dans l'audience
« module », et aucun autre sous-module du cœur.

## Version du contrat module

Tous les ajouts depuis FD-MODULES-001 sont additifs et facultatifs : `actions`
(FD-EDIT-001), `editor_script` et `editor_config` (FD-GRAPHICS-EDIT-001), options
et méthodes du moteur (`nodeMove`, `onViewChange`, `addOverlay`, `worldAt`),
exports `loads_strict_json` et `MAX_SPECIALIZED_*` ; `assets` et `UiEntry`
existaient depuis FD-MODULES-001/002. **`MODULE_API_VERSION` reste 1**
(décision F) ; aucune incompatibilité démontrée.

## Capabilities

| Capacité | Usage réel par l'hôte |
|---|---|
| `open` | Condition de lecture (`read_specialized_resource`) |
| `save` | Condition d'écriture (type modifiable) et d'exposition des actions |
| `create` | Écriture sans révision antérieure |
| `edit` | Capacité par défaut des actions ; sans elle : ni route, ni action dans le contexte, ni script d'édition |
| `validate`, `export`, `interactive-runtime` | Déclarables ; aucune fonction de l'hôte n'en dépend encore |
| Capacités d'outil | Disponibles selon les dépendances optionnelles (sonde) |

Vérifié : une capacité absente n'expose ni route, ni action, ni bouton, ni
édition (`test_capability_gate_and_read_only_modules`,
`test_absent_capability_exposes_no_route_action_or_editor`, mutant
« capacité ignorée » tué).

## ModuleAction

Garanties auditées et déjà testées : payload formulaire borné
(`MAX_MODULE_ACTION_BYTES`), champs exacts (champ en plus ou en moins :
`payload-invalid`), accesseurs typés (`text`, `integer`, `number`, `boolean`),
barrière de capacités au démarrage, jeton de révision opaque comparé à temps
constant, garde d'origine locale (403), détection de mutation du document lu,
validation bloquante, écriture atomique, historique, PRG 303 ; le handler ne
reçoit que `(document, payload)` — vérifié par les arguments effectivement
passés (`test_module_code_receives_only_the_document_and_the_payload`) et par
mutation (racine passée en argument ou dans le payload : tués).

## ResourceBinding

`codec` (octets ↔ document, quatre méthodes exigées), `scene` (facultative,
document → `GraphicScene`, isolée, ≤ 8 Mio, copie JSON détachée),
`editor_script` (asset `.js` déclaré, exige une projection) et `editor_config`
(document → JSON, exige un script). Contrat d'édition consolidé : **facultatif,
inerte sans action exposée, borné (1 Mio, limite inchangée), contrôlé par le
module, validé par l'hôte** ([édition](../modules/module-architecture.md#édition)).

## ModuleHost

Construit une fois par application ; vérifie et lit les assets à la
construction (`asset-missing` retire le module) ; calcule les actions exposées
une fois ; lit et écrit par l'hôte de ressources ; isole codec, projection,
configuration et handler (messages bornés, traces journalisées) ; ne reçoit et
ne transmet ni racine retenue, ni Request, ni Router (racine fournie à chaque
opération par la couche Web, jamais au module).

## ResourceHost

Audit sans changement : lectures par `dir_fd`, `O_NOFOLLOW | O_NONBLOCK`,
`fstat` + `samestat` avant et après lecture, refus des non-fichiers, lectures
bornées par `max_size`, liens symboliques refusés ; écriture dans un fichier
temporaire (`O_CREAT | O_EXCL | O_NOFOLLOW`), `fsync`, revérification de la
révision attendue, `os.replace` ; révision, conflit, historique. Aucun défaut
concret : pas de réécriture.

## GraphicScene

Réaffirmé : **projection runtime, jamais un document persistant**. Lire et
projeter n'écrivent rien ; un handler qui rendrait une scène au lieu du
document est refusé (`module-error`) sans écriture ni historique
(`test_graphic_scene_is_never_persisted`).

## Graphic Core

Surface publique documentée capacité par capacité (responsabilité, entrée,
sortie, cycle de vie, mutabilité, garanties) :
[API publique](../graphics/graphics-engine.md#public-api-for-clients). Le
moteur n'expose ni renderer, ni groupe SVG privé, ni structure DOM interne ;
Route, Entity et Debug n'utilisent ni `nodeMove`, ni `addOverlay`, ni
`onViewChange`.

## nodeMove

Opt-in vérifié : désactivé par défaut ; `canMove`, `constrain`, `onMove`,
`keyboardStep` obligatoire ; aperçu runtime ; une intention par geste ; Route,
Entity et Debug non déplaçables (navigateurs : « nœuds non déplaçables,
sélection intacte » 3/3 dans Chromium et Firefox).

## overlays

`addOverlay` : groupe SVG dédié en coordonnées monde, soumis au viewport,
rattaché au re-rendu, `remove()` idempotent, retiré par `destroy()`, propre à
l'instance ; aucun accès au DOM privé (suites Graphics `engine-overlay`). Le
témoin flowchart et Circuit l'utilisent sans rien partager.

## viewport / worldAt / onViewChange

`worldAt` : primitive générique point écran (client) → point monde.
`onViewChange` : émis au zoom, pan, fit, home, recentrage, redimensionnement
utile et changement de niveau de détail, **jamais sans changement** (comparaison
de l'état précédent dans `notifyView`), exception du client isolée.

## sélection

État actuel : seuls les **nœuds** sont sélectionnables et focalisables ; les
arêtes incidentes sont mises en évidence. Aucune sélection d'arête : documenté
comme état courant, sans ticket (un client interagit avec une arête dans son
calque, comme Circuit).

## cycle de vie editor

```text
/module-resource.js : bloc JSON inerte → contexte gelé
  → import(script) → createResourceEditor(context)
  → createGraphicEngine(scène, { nodeMove, onViewChange }) → attach(engine)
  → gestes du script → POST de son action → 303 → page rechargée
```

Pas de crochet de destruction : une action réussie recharge la page. Le
contexte JS nomme `resourceType` ce que le bloc JSON nomme `type` (constat,
documenté ; le témoin s'y est d'abord trompé). Échec du script : consultation
seule annoncée, ressource lisible (test JS, mutant tué, navigateurs).

## sécurité filesystem

Le module ne lit ni n'écrit jamais le projet : octets fournis par l'hôte,
octets rendus à l'hôte. Garanties du ResourceHost ci-dessus ; le Web des
modules n'ouvre aucun fichier (garde existante).

## sécurité navigateur

Même origine, CSP `script-src 'self'` et `style-src 'self'`, aucun CDN, aucun
JS en ligne ni `unsafe-eval`, routes d'assets exactes et déclarées, modules ES
natifs, aucun build JS. Aucune violation CSP dans les parcours FD-ARCH-001.

## isolation modules

Trois modules munis d'éditeurs (`witness`, `flow`, `flow-broken`) : chacun ne
sert que ses assets (croisements et traversée : 404), une action n'existe pas
dans l'espace d'un autre (404) ou y est refusée (400, jeton et type étrangers),
contexte d'édition propre (`test_three_modules_with_editors_stay_isolated`).
Échec d'activation : diagnostics par module, configuration malformée fatale au
démarrage (politique existante, inchangée et documentée).

## ToolRegistry

Exactement les cinq Tools Forge, avec ou sans modules. Nouveau garde
**comportemental** : le registre réellement composé par `create_application`,
modules activés, est capturé et vérifié (`test_modules_never_become_tools`) ;
un mutant qui contourne le garde textuel existant est tué. Modules ≠ Tools.

## dogfooding Forge MVC

`web/server.py` compose une `Application` Forge MVC avec `Router`, `Request`,
`Response` et `create_wsgi_app` ; rendu par l'intégration Jinja2 de Forge MVC
(`integrations.jinja2`). Aucune pile Web parallèle (garde statique sur Flask,
FastAPI, Starlette, Django, Bottle, aiohttp, Tornado).

## dépendances et imports

`test_core_depends_only_on_stdlib_and_declared_packages` : chaque fichier de
`forge_design/` n'importe que la bibliothèque standard, `forge_design` et les
dépendances déclarées — Forge MVC (paquets `core` et `integrations`), Jinja2,
markupsafe, pydantic, packaging. Jamais `forge_design_*`. S'ajoute aux gardes
existantes (`test_core_never_imports_circuit`,
`test_core_distribution_ships_no_circuit`, contrat des modules sans
`entry_points`, `pkgutil`, `sys.path`, `importlib.metadata`). Recherche de
vocabulaire (`circuit`, `terminal`, `wire`, `junction`, `resistor`,
`electrical`) dans le code livré : aucune occurrence.

## module témoin

`tests/flow_witness/` (non livré, absent des paquets de la roue) : domaine
« organigramme » — trois étapes étiquetées, un lien orienté, codec
`FlowCodec`, projection `flow_scene` (3 nœuds, 1 arête), action
`rename-step`, configuration d'édition, script `flow-editor.js` (calque monde,
une poignée focalisable par étape, Entrée → action → rechargement) et variante
`flow-broken.js` qui échoue. Aucun import de Circuit ; seul le contrat public.
Le témoin historique `witness` est inchangé.

## validation multi-modules

Hors suite (dossier de travail, serveur dédié), `witness` + `flow` +
`flow-broken` + ForgeDesign-Circuit activés ensemble, **5/5 dans Chromium et
Firefox** : navigation du cœur inchangée et quatre modules listés ; témoin
flowchart (scène 3 nœuds / 1 arête, calque de 3 poignées, Entrée → POST →
rechargement, fichier et historique mis à jour) ; script défaillant (repli
annoncé « Édition indisponible (témoin en échec) : consultation seule. »,
scène affichée, aucun calque) ; Circuit (15 éléments de calque) ; aucune
exception ni violation CSP. Les tests du cœur ne dépendent pas du dépôt Circuit.

## exports publics

Figés et classés (voir « API modules publique ») ; mutant « export interne
accidentel » tué. Aucun retrait.

## documentation consolidée

- `docs/architecture/core-module-boundaries.md` (nouveau, normatif) : matrice,
  dix règles, garde de chaque règle.
- `docs/modules/module-architecture.md` : statut, API publique par audience,
  contrat d'édition (Python et JS, cycle de vie, échec), exemple minimal
  (témoin), usage réel des capacités, versionnement (API 1), tests ; passage
  obsolète « aucun JS de module chargé » corrigé ; migration Circuit renommée
  en historique.
- `docs/modules/module-host.md` : clés du contexte JS (`resourceType`).
- `docs/graphics/graphics-engine.md` : API publique pour les clients, état de
  la sélection (nœuds seulement).
- `docs/02-architecture.md` : deux responsabilités, renvois normatifs.
- `docs/03-roadmap.md` : quatre pistes.
- `docs/circuit/README.md` : Circuit comme validation réelle.

Aucune documentation parallèle concurrente : le contrat détaillé reste dans
`module-architecture.md`.

## dette technique

| Dette | Classe | Suite |
|---|---|---|
| Version de distribution du cœur figée à `0.1.0.dev0` : un module ne peut pas exiger un cœur portant `actions`, `editor_script` ou `addOverlay` ; sur un cœur antérieur il échoue à l'import (`module-import-failed`) ou à `attach` | **importante** | FD-RELEASE-001 (ticket cœur principal) |
| `type` (bloc JSON) / `resourceType` (contexte JS) : deux noms pour la même valeur | mineure | Documentée ; renommer casserait Circuit |
| `validate`, `export`, `interactive-runtime` : capacités sans effet hôte | mineure | Documentées ; à câbler quand une fonction de l'hôte en dépendra |
| Arêtes non sélectionnables | mineure | État courant documenté ; pas de ticket sans besoin générique |
| Pas de crochet de destruction du script d'édition | mineure | Suffisant tant que chaque action recharge la page |
| Exports d'audience hôte dans le même paquet que l'API module | mineure | Audience documentée ; aucun retrait |
| Garde du `ToolRegistry` uniquement textuelle | mineure | **Corrigée** : garde comportemental ajouté |
| Un seul script d'édition par type | mineure | Suffisant pour les deux domaines connus |
| Aperçu Circuit sans évitement, anciens fils traversants, etc. | spécialisée — hors core | Dépôt ForgeDesign-Circuit |

Aucune dette bloquante.

## corrections réalisées

Aucune modification de `forge_design/`. Ajouts : `tests/test_module_boundaries.py`
(10 tests), module témoin `tests/flow_witness/` (Python + deux scripts),
documentation normative et consolidée, roadmap. Le seul défaut corrigé est un
manque de garde (registre d'outils) et une imprécision documentaire (JS de
module).

## corrections volontairement différées

FD-RELEASE-001 (versions et compatibilité déclarée) ; harmonisation
`type`/`resourceType` ; câblage des capacités sans effet ; sélection d'arête ;
crochet de destruction — tous hors du critère « petite, locale, sans changement
conceptuel, nécessaire à une frontière déjà décidée ».

## roadmap révisée

`docs/03-roadmap.md` : quatre pistes — **A. cœur** (ticket principal
FD-RELEASE-001), **B. outils propres à Forge** (diagnostics Forge, intégration
applicative), **C. moteur graphique générique** (aucune capacité sans besoin
réel), **D. modules externes** (Circuit poursuit dans son dépôt ; second pilote
Flowchart). Circuit sort de la progression principale ; la phase 10 devient un
historique de phase pilote close.

## second module pilote recommandé

**Flowchart.**

| Critère | Flowchart | Network |
|---|---|---|
| Nœuds porteurs de texte (étapes, décisions) | central | secondaire (noms d'équipements) |
| Sémantique d'arête différente de Circuit | oui : orientée, porteuse de sens (« oui » / « non »), libellée | proche de Circuit : liaisons entre interfaces (ports ≈ bornes) |
| Édition | texte, création et réordonnancement d'étapes, branches | placement d'équipements, liaisons port à port |
| Routage géométrique | faible (layout, flèches) | modéré (câblage, ports) |
| Primitives sollicitées | sélection, libellés d'arêtes (`label`/`labelAt` existent), layout, édition textuelle | quasiment celles de Circuit |

Flowchart teste ce que Circuit n'a pas testé (texte, libellés d'arêtes,
édition non géométrique) ; Network recouperait Circuit. Le témoin flowchart
montre déjà que le contrat suffit pour démarrer.

## fichiers créés

- `docs/architecture/core-module-boundaries.md`
- `docs/rapports/FD-ARCH-001.md`
- `tests/test_module_boundaries.py`
- `tests/flow_witness/__init__.py`, `tests/flow_witness/static/flow-editor.js`,
  `tests/flow_witness/static/flow-broken.js`

## fichiers modifiés

- `docs/02-architecture.md`, `docs/03-roadmap.md`, `docs/circuit/README.md`,
  `docs/graphics/graphics-engine.md`, `docs/modules/module-architecture.md`,
  `docs/modules/module-host.md`

Aucun fichier de `forge_design/` ; aucun fichier de ForgeDesign-Circuit.

## validations

| Contrôle | Résultat |
|---|---|
| `compileall`, Ruff, `ruff format --check`, Pyright strict, `git diff --check` | Réussis (0 erreur) |
| Pytest (suite globale, basetemp court) | **4 593 réussis** (4 583 + 10) |
| Node : suites Graphics | 134 réussis (16 fichiers) |
| Mutations de frontière | **13/13 tuées** : cœur importe Circuit ; cœur importe une autre pile Web ; handler reçoit la racine (argument) ; handler reçoit la racine (payload) ; projection reçoit la racine ; capacité ignorée ; asset d'un autre module servi ; action exécutable dans un autre espace ; routes d'actions croisées ; échec du script d'éditeur casse la page (JS) ; auto-découverte activée ; export interne accidentel ; `ToolRegistry` accepte un module |
| Navigateurs (cœur) | `reg.mjs` : Chromium 7/7, Firefox 6/6 (Route, Entity, Debug non déplaçables ; témoin ; cœur sans module) ; Firefox sans JavaScript : repli, aucun moteur |
| Navigateurs (multi-modules, hors suite) | Témoin flowchart + script défaillant + witness + Circuit : 5/5 Chromium, 5/5 Firefox |
| Roue du cœur | `forge_design-0.1.0.dev0` : 159 fichiers, aucun fichier « circuit », témoin ni test |
| Venv neuf (roues cœur + Circuit), `pip check` | Propre |
| `forge-design --module forge_design_circuit --no-browser` | Déplacement 12/12, connexion 10/10, dérivation 12/12, fil → fil 10/10, évitement 5/5, dans Chromium et Firefox ; arrêts SIGTERM code 0 |
| Performance | `forge_design/` inchangé : démarrage, activation, page ressource et Graphic Core identiques ; nouveaux tests ≈ 0,6 s |

## état Git final

- Forge Design : `44ded4b` + commit
  `docs: consolider les frontières du moteur (FD-ARCH-001)` (tests et
  documentation, `forge_design/` intact), **non poussé** ;
  `docs/rapports/FD-CONTRACT-001.md` toujours modifié, hors commit, non restauré.
- ForgeDesign-Circuit : `6627212`, inchangé, non poussé.
- Aucun serveur ni navigateur laissé ouvert (un Firefox resté ouvert par un
  premier lancement mal paramétré du parcours sans JavaScript a été fermé) ;
  dossiers `build/` des roues supprimés ; le dossier ignoré `storage/` de la
  racine date du 2 octobre et n'a pas été touché.
