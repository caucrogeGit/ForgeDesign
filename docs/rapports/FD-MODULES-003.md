# Rapport — FD-MODULES-003

Normatif : [Architecture des modules](../modules/module-architecture.md) ;
hôte : [Hôte des modules](../modules/module-host.md) ; renvoi Circuit :
[Circuit : module externe](../circuit/README.md).

## Ticket et objectif

Extraire Circuit du cœur dans un dépôt indépendant, `ForgeDesign-Circuit`
(distribution `forge-design-circuit`, paquet `forge_design_circuit`, module
`circuit`, version 0.1.0). Le module est activé par
`forge-design --module forge_design_circuit`. Une première projection
`CircuitDocument → GraphicScene` est ajoutée côté module. Ensuite seulement,
`forge_design/circuit/`, ses tests et ses documents sont retirés du cœur, avec
une provenance traçable et sans réécriture d'historique. Ni édition, ni
simulation.

## État Git initial Forge Design

```text
$ git log --oneline -5
2a0db00 feat: implémenter l'hôte des modules spécialisés (FD-MODULES-002)
558933b feat: définir le contrat des modules spécialisés (FD-MODULES-001)
69f48d8 feat: migrer Debug Center sur le Graphic Core (FD-GRAPHICS-008)
c24dc6c feat: ajouter la minicarte au Graphic Core (FD-GRAPHICS-007)
3221814 feat: ajouter le semantic zoom au Graphic Core (FD-GRAPHICS-006)
$ git rev-parse --short HEAD          → 2a0db00
$ git rev-parse --short origin/main   → 2a0db00
$ git rev-list --left-right --count origin/main...HEAD → 0 0
$ git status --short
 M docs/rapports/FD-CONTRACT-001.md
```

`FD-CONTRACT-001.md` est une modification locale préexistante, laissée hors
commit et jamais restaurée.

## État Git initial ForgeDesign-Circuit

Le dépôt n'existait pas, ni en local (`/home/roger/Projets/ForgeDesign-Circuit`
absent) ni sur GitHub (`gh repo view caucrogeGit/ForgeDesign-Circuit` :
« Could not resolve to a Repository »). Il a été créé par `git init -b main`,
avec l'auteur Git du cœur.

## Référence DrawCiel

Procédure [drawciel-reference](../graphics/drawciel-reference.md) appliquée
avant `scene.py` : `git fetch` dans SéquenCiel, en lecture seule. Référence
figée : `9a38dce8`, ligne ajoutée au journal.

## Delta DrawCiel

`88f95b75..9a38dce8` contient un seul commit SéquenCiel (« proposer une palette
de texte à dix couleurs », éditeur riche). Il ne touche aucun fichier sous
`static/vendor/drawciel/` (`git diff --stat` vide), donc il n'a pas d'impact.

Principes comparés pour la projection (position monde des bornes, rotation,
jonction, route de fil) :

| Principe DrawCiel | Statut |
|---|---|
| `componentBox` : composant centré, emprise permutée à 90° | ADAPT |
| `localTerminal` / `terminalPort` : borne locale tournée | REWRITE (entiers, quarts de tour exacts ; DrawCiel : cos/sin) |
| `rotateSide` : N → E → S → W | REWRITE |
| Fil = extrémités + points intermédiaires | ADAPT |
| `astarGrid`, `cleanRoute`, `simplifyExact` | NON APPLICABLE (aucun routage) |
| Symboles électriques, annotations | NON APPLICABLE en V1 |

Aucun code DrawCiel n'a été copié ni translittéré, et aucun principe n'est
EXTRACT. Le détail est dans `PROVENANCE.md` du module.

## Source Circuit avant extraction

Commit source exact : `2a0db00be875c60f985d6a52fdc6a44e1b31250e`. Circuit y
comprenait :

- 11 fichiers sous `forge_design/circuit/`, dont `circuit.schema.json` ;
- `tests/circuit_support.py` et 8 fichiers `tests/test_circuit_*.py`
  (299 tests) ;
- 3 documents `docs/circuit/*.md` ;
- dans `pyproject.toml`, le paquet `forge_design.circuit` et sa package-data.

Commits historiques : `233e146` (FD-CIRCUIT-001), `c2a135e` (FD-GRAPHICS-001),
`d8275f2` (FD-CIRCUIT-002), `2023aea` (FD-CIRCUIT-003), `f9fe502`
(FD-GRAPHICS-002).

## Inventaire migré

| Ancien | Nouveau | État |
|---|---|---|
| `forge_design/circuit/models.py` | `forge_design_circuit/models.py` | copié, espace de noms adapté |
| `forge_design/circuit/codec.py` | `forge_design_circuit/codec.py` | copié, imports publics du cœur |
| `forge_design/circuit/catalog.py` | `forge_design_circuit/catalog.py` | copié |
| `forge_design/circuit/domain.py` | `forge_design_circuit/domain.py` | copié |
| `forge_design/circuit/topology.py` | `forge_design_circuit/topology.py` | copié |
| `forge_design/circuit/validation.py` | `forge_design_circuit/validation.py` | copié |
| `forge_design/circuit/ids.py` | `forge_design_circuit/ids.py` | copié |
| `forge_design/circuit/limits.py` | `forge_design_circuit/limits.py` | copié |
| `forge_design/circuit/circuit.schema.json` | `forge_design_circuit/circuit.schema.json` | copié, package-data du module |
| `forge_design/circuit/contract.py` | `forge_design_circuit/contract.py` | copié, `ui_entry=UiEntry("Circuit")` |
| `forge_design/circuit/__init__.py` | `forge_design_circuit/__init__.py` | réécrit : API publique et `FORGE_DESIGN_MODULE` |
| — | `forge_design_circuit/scene.py` | nouveau : projection |
| `tests/circuit_support.py`, 8 `tests/test_circuit_*.py` | mêmes noms dans `tests/` | copiés : 299 tests identiques, une assertion `ui_entry` ajustée |
| — | `tests/test_scene.py`, `tests/test_module.py` | nouveaux : 25 tests |
| `docs/circuit/circuit-{scope,resource,domain}.md` | `docs/circuit-{scope,resource,domain}.md` | déplacés, note d'extraction, contenu historique conservé |

## Nouveau dépôt

```text
ForgeDesign-Circuit/
├── PROVENANCE.md   README.md   pyproject.toml   .gitignore
├── forge_design_circuit/   (11 modules Python + circuit.schema.json)
├── tests/                  (circuit_support + 10 fichiers de test)
└── docs/                   (circuit-scope, circuit-resource, circuit-domain)
```

Pas de `filter-repo`, pas de `subtree split`, pas de sous-module, pas de
monorepo. Le dépôt GitHub `caucrogeGit/ForgeDesign-Circuit` a été créé par
`gh repo create`, public comme `ForgeDesign`, sans description de licence
(le cœur n'en a pas). Il est déclaré comme `origin`
(`git@github.com:caucrogeGit/ForgeDesign-Circuit.git`) et reste **vide** :
aucun push.

## Packaging module

- `name = "forge-design-circuit"` ; version dynamique depuis
  `forge_design_circuit.__version__ = "0.1.0"`, et non 1.0 tant qu'il n'y a ni
  éditeur ni simulation.
- `requires-python = ">=3.12"`.
- `packages = ["forge_design_circuit"]`, package-data `circuit.schema.json`.
- Extra `dev` : pytest, Ruff, Pyright (strict).

Roue : `forge_design_circuit-0.1.0-py3-none-any.whl` (12 fichiers du paquet,
schéma compris). Aucune URL Git dans les dépendances.

## Provenance

`PROVENANCE.md` contient :

- le dépôt et le commit source exact ;
- la date (2026-10-04) et la stratégie de copie (`git show 2a0db00:<chemin>`) ;
- la table des 23 chemins copiés ;
- les adaptations ;
- les cinq commits historiques et les rapports restés dans le cœur ;
- la provenance DrawCiel, la validation et l'état du dépôt distant.

Ces détails ne sont pas dupliqués dans un `docs/extraction.md` séparé. Les
trois documents migrés portent une note d'extraction à la place du bandeau
FD-MODULES-001.

## Dépendances

| Dépendance module | Pourquoi | API publique ? |
|---|---|---|
| `forge_design.specialized` | contrat ResourceHost : définitions, codec, issues, `UiEntry`, `loads_strict_json`, bornes d'issues | oui |
| `forge_design.modules` | `ModuleDescriptor`, `ResourceBinding`, `MODULE_API_VERSION` | oui |
| Pydantic (`>=2,<3`) | modèles stricts du document | oui (dépendance tierce déclarée) |
| `forge-design>=0.1.0.dev0,<0.2` | première version portant l'hôte des modules (API 1) | distribution |
| bibliothèque standard | `json`, `math`, `re`, `secrets`, `itertools`, `dataclasses`, `types`, `typing`, `collections.abc` | — |

Le module ne dépend ni de forge-mvc, ni de Jinja, ni de SéquenCiel ou DrawCiel.
Il n'importe ni `os`, ni `pathlib`, ni `io`, ni `socket`, ni `forge_design.web`,
et il n'appelle jamais `open(` (test `test_module_never_touches_the_filesystem_or_web`).

## API publique core exposée

La dette notée par FD-MODULES-001 est corrigée : `forge_design.specialized`
exporte maintenant `loads_strict_json`, `MAX_SPECIALIZED_ISSUES` et
`MAX_SPECIALIZED_LOCATION_DEPTH`. Ce sont des réexportations, sans aucune copie
de code. Le cœur livre aussi `forge_design/py.typed` (PEP 561) : sans ce
fichier, Pyright refusait l'API typée depuis un dépôt externe.

## Imports adaptés

- `forge_design.circuit` devient `forge_design_circuit` partout (code, tests,
  documents).
- `forge_design.json_strict` et `forge_design.limits` deviennent
  `forge_design.specialized` (codec, `test_circuit_codec`,
  `test_circuit_validation`).
- `SpecializedReadResult` vient de `forge_design.specialized`.

Le test `test_module_uses_only_the_public_core_api` n'accepte du cœur que
`forge_design.modules` et `forge_design.specialized`.

## ModuleDescriptor

```python
FORGE_DESIGN_MODULE = ModuleDescriptor(
    definition=CIRCUIT_TOOL,
    version=__version__,
    api_version=MODULE_API_VERSION,  # importée, pas recopiée
    bindings=(
        ResourceBinding(
            CIRCUIT_RESOURCE_TYPE.id, CircuitCodec(), project_circuit_scene
        ),
    ),
)
```

Il n'y a ni asset, ni sonde de dépendance. La version vient de la constante du
paquet, sans `importlib.metadata`.

## ResourceBinding

Type `schematic`, codec `CircuitCodec()`, projection `project_circuit_scene`.
Le test de descripteur vérifie l'identité de chacun.

## UiEntry

`UiEntry("Circuit")`, sans icône. Les capacités restent `create`, `open`,
`validate` et `save` : ce sont des capacités du domaine et du socle
(`write_specialized_resource`). L'hôte Web V1 ne fait que de la consultation :
aucune action de création ou d'enregistrement n'apparaît dans l'interface
(POST → 405, `/actions/…` → 404). La docstring du contrat consigne cette
différence (capacité ≠ action UI disponible).

## Projection Circuit → GraphicScene

`forge_design_circuit/scene.py` contient `project_circuit_scene(document,
catalog=CIRCUIT_CATALOG) -> dict`. La fonction est pure et déterministe : elle
ne touche ni système de fichiers, ni requête, ni routeur, ni hôte, et ne
modifie pas le document. Conversion : `GRID_UNIT = 40` px par unité de grille,
marge `PAGE_MARGIN = 2` unités. Titre « Schéma Circuit ». La description
précise qu'il s'agit d'une visualisation V1 en rectangles orientés, pas de
symboles électriques. Le Graphic Core n'a pas été modifié.

## Géométrie composants

Chaque composant devient un `GraphicNode` d'identité `component.id`. Son corps
rectangulaire est centré sur `component.position`, source d'autorité, avec des
dimensions V1 par type :

- résistance, interrupteur, lampe, LED, diode, potentiomètre : 4 × 2 ;
- source : 2 × 4 ;
- masse : 2 × 2.

Les rectangles restent alignés sur les axes : à 90° et 270°, largeur et hauteur
sont permutées (`body_box`). La variante est générique et choisie par la
classification déclarée (`domain_kind`) :

| Variante | Types |
|---|---|
| category-1 | source |
| category-2 | dipôles passifs |
| category-3 | semi-conducteurs |
| category-4 | masse |
| category-6 | jonction |

Aucune classe `gx-resistor` n'est créée.

Libellé : nom du type, suivi de la référence si elle existe, puis de la
rotation si elle n'est pas nulle. Lignes de texte : la référence (ou à défaut le
nom), le nom du type, la rotation. Niveaux : aucune ligne en vue d'ensemble, la
première en vue normale. Aucune propriété n'est affichée.

## Terminaux

Le catalogue (source autoritaire) donne les bornes, leur rôle et leur direction,
mais pas de position locale. Le module déclare donc une table `SYMBOLS` : une
position locale entière pour chaque borne de chaque type, sur le côté de sa
direction déclarée (par exemple `t1` W en (−2, 0), `positive` N en (0, −2),
`wiper` N en (0, −1)). `check_symbols` vérifie la table contre le catalogue à
l'import :

- mêmes types ;
- dimensions paires ;
- ensemble exact des bornes, sans borne en plus ni en moins ;
- chaque borne sur son côté déclaré.

Position monde = position du composant + borne locale tournée
(`terminal_position`).

## Rotation

Rotation par quarts de tour exacts dans le sens horaire de l'écran (y vers le
bas) : 0 → (x, y), 90 → (−y, x), 180 → (−x, −y), 270 → (y, −x). L'ordre des
côtés est N → E → S → W. Toute autre valeur lève `CircuitProjectionError`. Le
Graphic Core ne reçoit aucune notion de rotation : seuls l'emprise permutée et
les points des arêtes la traduisent.

## Connexions

Chaque connexion devient une arête d'identité `connection.id`, avec pour source
et cible l'identité du composant ou de la jonction. Ses points sont, dans
l'ordre, l'extrémité A, les points intermédiaires persistés, puis l'extrémité B,
tous convertis par la même transformation grille → scène.

## Jonctions

Chaque jonction devient un nœud générique de 16 × 16 px centré sur sa position,
d'identité `junction.id`, avec le libellé « Jonction <id> » et la variante
category-6. Une extrémité de jonction se place sur ce centre. Le Graphic Core
n'a pas de type « jonction ».

## Routes

`route.points` est repris tel quel : pas de re-routage, pas d'A*, pas
d'allocateur de couloirs, pas de simplification ni de réparation. Une arête au
delà de 64 points (borne du Graphic Core) est refusée explicitement plutôt que
tronquée.

## Annotations

**Décision A** : les annotations ne sont pas dessinées. Le Graphic Core V1 n'a
pas d'annotation textuelle, et un nœud « annotation » ne serait pas sans
ambiguïté (sélection, emprise, minicarte). La description de la scène indique
« Annotations textuelles non représentées : N. ».

## Exactitude et refus

Rien n'est inventé : ni borne, ni connexion, ni valeur. La projection lève
`CircuitProjectionError` avec un message en français dans ces cas :

- type de composant inconnu ;
- borne inconnue pour le type ;
- extrémité vers un composant ou une jonction absents ;
- rotation hors des quarts de tour ;
- plus de 5000 nœuds ou plus de 64 points par arête.

Rien n'est deviné d'après un nom. L'hôte isole l'exception et affiche
« Projection graphique du module en échec (CircuitProjectionError). » : métadonnées
et diagnostics restent lisibles, et le serveur reste disponible.

La scène couvre la page et tout contenu qui la déborde, donc rien n'est caché.
Les libellés restent du texte, sans HTML.

## Intégration ModuleHost

`tests/test_module.py` (module) passe par l'hôte réel du cœur :

- `activate_modules(["forge_design_circuit"])` avec l'importeur réel,
  sans diagnostic et avec les 4 capacités disponibles ;
- `ModuleHost.navigation` → `("circuit", "Circuit", "/modules/circuit/")` ;
- `list_resources` puis `read_resource` sur un projet temporaire → scène de
  6 nœuds ;
- une borne inconnue donne `scene_error` borné.

## Navigation Circuit

Avec `--module forge_design_circuit`, l'accueil affiche la zone « Modules »
avec l'entrée « Circuit » (`/modules/circuit/`), et `aria-current="page"` sur
la page du module. Sans le module, il n'y a aucune zone.

## Listing ressources

`list_specialized_resources` du cœur liste `mvc/circuit/**/*.circuit.json`
dans l'ordre lexical. Sur le corpus de test : `borne`, `casse`, `demo`,
`sous/rotations`.

## Lecture

`read_specialized_resource` du cœur lit les octets, puis `CircuitCodec`
décode. Le module n'ouvre aucun fichier.

## Validation

`CircuitCodec.validate` applique les niveaux `structure`, `topology` et
`electrical-readiness`. La page affiche « valide » pour `demo`, et
`invalid-resource` pour un fichier JSON illisible.

## Graphic Core

La scène est validée par le vrai `validateScene` (Node, test
`test_scenes_pass_the_real_graphic_core_validation` : document vide, démo,
rotations avec texte hostile). Elle est rendue par le client générique
`/module-resource.js`. Sélection, viewport, niveaux de détail et minicarte sont
ceux du moteur, sans code Circuit côté navigateur. Le Graphic Core est
inchangé.

## Sans JavaScript

Chromium (exécution désactivée par CDP) et Firefox (profil
`javascript.enabled=false`) : métadonnées et validation lisibles, message
« La visualisation graphique nécessite JavaScript. », aucune scène.

## Suppression Circuit du core

Retirés du cœur :

- `forge_design/circuit/` (11 fichiers) ;
- `tests/circuit_support.py` et les 8 `tests/test_circuit_*.py` ;
- `docs/circuit/circuit-{scope,resource,domain}.md`, remplacés par
  [`docs/circuit/README.md`](../circuit/README.md), un renvoi sans contenu
  normatif ;
- dans `pyproject.toml`, `forge_design.circuit` (paquets) et sa package-data.

Le dossier `build/` non suivi contenait une copie périmée de
`forge_design/circuit/` issue de builds antérieurs ; il a été supprimé avant
la construction de la roue, faute de quoi elle aurait pu la reprendre.

Rapports FD-CIRCUIT-001 à 003 : une note « Histoire avant extraction » a été
ajoutée. Les liens vers les documents déplacés de ces rapports et de
FD-GRAPHICS-001 mènent au renvoi. Le reste n'est pas réécrit.

## Tests migrés

Les 299 tests Circuit passent à l'identique dans le module, avant tout retrait
du cœur. Ordre suivi : module créé, sa suite verte, test avec l'hôte, puis
retrait. Une seule assertion a changé : `ui_entry` vaut `UiEntry("Circuit")`
au lieu de `None`.

## Tests core

`tests/test_modules_contract.py` :

- `test_core_never_imports_circuit` : plus d'exception pour
  `forge_design/circuit` ; vérifie que le dossier n'existe plus et qu'aucun
  `forge_design.circuit` ni `forge_design_circuit` n'est importé ;
- nouveau `test_core_distribution_ships_no_circuit` : aucun paquet,
  package-data ni dépendance « circuit » dans `pyproject.toml`, aucun fichier
  nommé « circuit » dans `forge_design/`, aucun mot « circuit » dans le code
  livré (`.py`, `.js`, `.html`, `.css`, `.json`), aucun test Circuit.
  La documentation n'est pas visée, car le mot y reste légitime ;
- `test_graphics_and_tool_registry_know_no_module` : inchangé, 5 Tools.

Les tests de contrat continuent d'utiliser des modules témoins, sans aucun test
métier Circuit.

## Tests module

| Fichier | Tests |
|---|---|
| 8 `test_circuit_*.py` migrés | 299 |
| `test_scene.py` | 19 : document vide, 1 composant, 2 composants + connexion, jonction, rotations 0/90/180/270 (paramétrées), sens des quarts de tour, route intermédiaire, annotation (décision A), texte hostile, débordement de page, type inconnu, borne / composant / jonction inconnus, bornes du Graphic Core, déterminisme et pureté (`open`, `os.stat`, `Path.read_text` interdits), table des symboles, `validateScene` réel |
| `test_module.py` | 6 : descripteur, activation réelle, hôte (liste, lecture, projection), projection refusée isolée, imports publics seulement, aucun accès fichier ni Web |

Total : **324 réussis**. Ruff : `check` et `format --check` réussis. Pyright
strict : 0 erreur. `pip check` : propre.

Mutations module (11/11 tuées) :

| Mutation | Tuée par |
|---|---|
| import ancien namespace (`forge_design.json_strict`) | `test_module_uses_only_the_public_core_api` |
| terminal inventé (table non vérifiée) | `test_symbol_table_is_checked_against_the_catalog` |
| rotation ignorée | `test_quarter_turns_are_exact[90]` |
| jonction ignorée | `test_host_lists_reads_and_projects` |
| route persistée ignorée | `test_connections_use_terminals_and_persisted_routes` |
| connexion reroutée automatiquement (coude ajouté) | `test_connections_use_terminals_and_persisted_routes` |
| composant inconnu accepté silencieusement | `test_unknown_component_type_is_refused` |
| terminal inconnu accepté silencieusement | `test_host_isolates_a_refused_projection` |
| `FORGE_DESIGN_MODULE` absent (renommé) | erreur d'import de `test_module.py` (l'hôte réel donne `descriptor-missing`) |
| binding sans scene | `test_descriptor_declares_circuit` |
| accès filesystem direct dans le module | `test_module_never_touches_the_filesystem_or_web` |

Une première version du mutant « FORGE_DESIGN_MODULE absent » laissait le nom
défini par affectation chaînée : elle était équivalente. Elle a été remplacée
par un vrai renommage.

Mutations core (4/4 tuées) :

| Mutation | Tuée par |
|---|---|
| `forge_design.circuit` encore packagé | `test_core_distribution_ships_no_circuit` |
| le cœur importe `forge_design_circuit` | `test_core_never_imports_circuit` |
| ToolRegistry reçoit un Tool `circuit` | `test_graphics_and_tool_registry_know_no_module` |
| module absent devient fatal (`SystemExit`) | 5 tests, dont `test_failures_are_isolated_with_diagnostics` |

## Chromium

Chrome 154.0.8037.92 headless (CDP), avec deux serveurs de test :

- 8766 : cœur et module en éditable, activation réelle par
  `activate_modules(["forge_design_circuit"])` ;
- 8767 : cœur seul, où le module est absent.

Corpus temporaire : `tmp/gxc-browser`, copie du projet témoin avec
`mvc/circuit/demo.circuit.json`, `sous/rotations.circuit.json`,
`casse.circuit.json` et `borne.circuit.json`. **15/15** :

- accueil avec « Modules → Circuit » ;
- page sans projet ;
- page module (0.1.0, listing trié) ;
- ressource valide : métadonnées, révision `sha256`, « valide », 6 nœuds et
  6 arêtes rendus ;
- sélection et Échap ;
- zoom : `overview → normal → detail` et minicarte ;
- pan de 100 px exact ;
- rotations : emprises 80 × 160 à 90°/270° et 160 × 80 à 180°, texte hostile
  inerte ;
- route persistée à 4 points ;
- ressource illisible ;
- borne inconnue : message borné, sans trace ;
- routes hors contrat : 404 / 400, POST 405 ;
- cœur sans module : aucune entrée, diagnostic `module-missing`,
  `/modules/circuit/` → 404 ;
- aucune exception, boîte de dialogue ni violation CSP.

Sans JavaScript : OK.

Au fit, la page entière de 80 × 60 unités (3360 × 2560 px) apparaît à
l'échelle 0,17, en vue d'ensemble. Il faut 6 et 7 zooms avant (× 1,25) pour
atteindre les vues normale (≥ 0,58) et détail (≥ 0,75).

## Firefox

Firefox 153.4.0 headless (WebDriver BiDi), même scénario : **15/15**. Sans
JavaScript : OK.

## Wheels

| Roue | Contenu |
|---|---|
| `forge_design-0.1.0.dev0-py3-none-any.whl` | 158 entrées, 0 « circuit », `forge_design/py.typed` présent |
| `forge_design_circuit-0.1.0-py3-none-any.whl` | 12 fichiers du paquet, `circuit.schema.json` compris |

## Core seul

Environnement A : venv neuf, roue du cœur installée avec ses dépendances, et
`pip check` propre. La vraie commande `forge-design` est lancée dans un espace
réseau isolé (`unshare -rn`) : son port fixe 8765 y est libre, sans toucher
l'instance de l'utilisateur.

- `forge_design` vient de la roue ; `forge_design.circuit` et
  `forge_design_circuit` sont introuvables.
- `forge-design --no-browser` : accueil 200 sans zone Modules,
  `/modules/circuit/` → 404, arrêt propre.

## Core + module

Environnement B : venv neuf, deux roues installées, `pip check` propre.
`forge-design --module forge_design_circuit --no-browser` (même isolement
réseau) :

- accueil avec Circuit et aucun diagnostic ;
- projet ouvert par `POST /inspector` ;
- page module 0.1.0 avec listing trié ;
- `demo` : scène JSON de 6 nœuds et 6 arêtes ;
- `rotations` : scène, texte hostile échappé ;
- `casse` : diagnostic, aucune scène ;
- `borne` : projection refusée proprement ;
- `/foo` → 404, type inconnu → 400, chemin `../` → 400, asset → 404 ;
- arrêt propre, port refermé.

## Module absent

Dans l'environnement A, `forge-design --module forge_design_circuit` écrit
« Module forge_design_circuit non chargé (module-missing) : Module non installé ;
rien n'est chargé. » sur stderr. Forge Design démarre quand même, l'accueil
affiche le diagnostic et `/modules/circuit/` → 404. Même constat en
navigateur (serveur 8767).

## ToolRegistry

Toujours 5 Tools : debug-center, entity-explorer, project-inspector,
route-explorer, template-viewer. Circuit est un module, pas un Tool.

## Frontières d'import

- Le cœur n'importe jamais `forge_design_circuit` : test AST, plus mutation.
- Le seul chemin d'import du module est `activate_modules`.
- Le module n'importe que `forge_design.modules` et `forge_design.specialized`
  (test AST), jamais `forge_design.web`, `json_strict` ou `limits`.

| Capacité | Forge Design | Circuit |
|---|---|---|
| filesystem projet | oui | non |
| listing | oui | non |
| read/write | oui | codec seulement |
| format | non | oui |
| catalogue | non | oui |
| topologie électrique | non | oui |
| validation électrique | non | oui |
| projection Graphics | non | oui |
| rendering | Graphic Core | non |
| simulation | non | future Circuit |

## Documentation

Cœur :

- `docs/circuit/README.md` : renvoi ;
- `02-architecture.md` : notes d'extraction, liens vers le renvoi, frontière
  des modules mise à jour ;
- `03-roadmap.md` : FD-MODULES-003 fait ;
- `modules/module-architecture.md` : migration « Fait » ;
- `graphics/drawciel-reference.md` : référence `9a38dce8` et ligne de journal ;
- `graphics-core-contract.md`, `storage-contract.md` : liens ;
- rapports FD-CIRCUIT-001 à 003 : note « Histoire avant extraction » ;
- FD-GRAPHICS-001 : liens.

Module : `README.md`, avec l'installation de développement
(`pip install -e ../ForgeDesign`, `pip install -e .`, mode `compat` pour
Pyright) et l'activation ; `PROVENANCE.md` ; trois documents migrés.

MkDocs : N/A, aucune configuration MkDocs dans Forge Design ni dans le module.

### Décisions

| | Question | Réponse |
|---|---|---|
| A | Le module est-il réellement installable indépendamment ? | **oui** : roue seule, environnement B neuf, `pip check` propre |
| B | Forge Design fonctionne-t-il sans lui ? | **oui** : environnement A, suite globale sans tests Circuit |
| C | Forge Design contient-il encore du code métier Circuit ? | **non** : seuls restent les rapports historiques, le renvoi et les notes d'architecture |
| D | Le module lit-il directement le projet ? | **non** : l'hôte lit, le codec décode des octets ; test AST et mutation |
| E | Activable avec `forge-design --module forge_design_circuit` ? | **oui** : vraie commande, environnement B |
| F | La visualisation utilise-t-elle le Graphic Core existant ? | **oui** : `validateScene`, client générique, moteur inchangé |
| G | Le Graphic Core a-t-il dû être modifié ? | **non** : seuls ont changé dans le cœur des réexportations de l'API spécialisée et `py.typed` |
| H | La projection invente-t-elle une connexion, un terminal ou une valeur ? | **non** : table vérifiée contre le catalogue, routes persistées, refus explicites |
| I | La simulation est-elle incluse ? | **non** |
| J | L'édition est-elle incluse ? | **non** : consultation seulement, POST → 405 |
| K | Le nouveau dépôt conserve-t-il une provenance traçable ? | **oui** : `PROVENANCE.md`, commit source exact, notes dans les documents |
| L | Peut-on maintenant commencer les capacités d'édition pilotées par Circuit ? | **oui** : les 7 critères sont réunis (voir ci-dessous) |

Critères de la décision L : module externe installé, hôte stable, ressource
ouverte, projection exacte, rendu par le Graphic Core, cœur débarrassé du
métier Circuit, tests du module et du cœur verts.

Deux points sont à traiter au premier ticket d'édition :

- la géométrie V1 des bornes est une convention du module, non persistée ;
  l'édition devra la figer ou la rendre déclarative ;
- l'interface d'édition demandera des actions POST côté hôte, qui sont
  aujourd'hui hors contrat.

## Commits

1. ForgeDesign-Circuit : `d8d1912 feat: extraire Circuit depuis Forge Design`
   (commit initial, 30 fichiers).
2. Forge Design : `refactor: retirer Circuit du cœur (FD-MODULES-003)`, au-dessus
   de `2a0db00`, sans `FD-CONTRACT-001.md`.

## État Git final des deux dépôts

- Forge Design : un commit au-dessus de `origin/main` (`2a0db00`).
  `docs/rapports/FD-CONTRACT-001.md` reste modifié localement, hors commit.
  Aucun push.
- ForgeDesign-Circuit : `main` avec un commit. `origin` pointe sur le dépôt
  GitHub créé, qui reste vide. Aucun push.

Aucun service n'est laissé ouvert : les serveurs de test 8766 et 8767, Chromium
et les deux Firefox sont arrêtés, et les serveurs de l'environnement isolé
s'arrêtent avec l'espace réseau. L'instance de l'utilisateur sur 8765
(pid 2680921) n'a pas été touchée. Une sonde de connexion envoyée par erreur
vers elle est restée en attente : sa file d'acceptation est pleine
(Recv-Q 6 > 5), ce qui est sans rapport avec ce ticket. Cette sonde a été
interrompue.

## Validation globale finale

| Contrôle | Résultat |
|---|---|
| Cœur : `compileall`, `ruff check`, `ruff format --check`, `pyright` | Réussis (0 erreur Pyright) |
| Cœur : `git diff --check` | Réussi |
| Cœur : `node --check` et suites Node `tests/js/graphics` | 102 réussis |
| Cœur : mutations | 4/4 tuées |
| Cœur : suite globale `pytest` (hors du dépôt, `--basetemp` court sous `tmp/`) | **4461 réussis** (4759 − 299 migrés + 1), relancée après insertion de ces résultats |
| Cœur : `pip check` | Aucune dépendance cassée |
| Module : Ruff, Pyright strict | Réussis |
| Module : `pytest` | **324 réussis** |
| Module : mutations | 11/11 tuées |
| Module : `pip check` | Aucune dépendance cassée |
| Environnements A et B (roues, vraie CLI) | 11/11 |
| Chromium 154 / Firefox 153 | 15/15 chacun ; sans JavaScript OK dans les deux |
| MkDocs | N/A |
