# Rapport — FD-MODULES-002

Normatif : [Architecture des modules](../modules/module-architecture.md) ;
mode d'emploi : [Hôte des modules](../modules/module-host.md).

## Ticket et objectif

Brancher le contrat de FD-MODULES-001 sur l'application Forge Design. Un
module explicitement activé peut alors apparaître dans le shell, avoir sa
page sous `/modules/<id>/`, voir ses ressources inventoriées et lues par
l'hôte, décodées par son codec, projetées en GraphicScene et rendues par le
Graphic Core. La preuve est faite avec des modules témoins limités aux tests,
sans extraire Circuit.

## État Git initial

```text
$ git log --oneline -5
558933b feat: définir le contrat des modules spécialisés (FD-MODULES-001)
69f48d8 feat: migrer Debug Center sur le Graphic Core (FD-GRAPHICS-008)
c24dc6c feat: ajouter la minicarte au Graphic Core (FD-GRAPHICS-007)
3221814 feat: ajouter le semantic zoom au Graphic Core (FD-GRAPHICS-006)
04f0af8 feat: compacter le routage des graphes (FD-GRAPHICS-005)
$ git rev-parse --short HEAD          → 558933b
$ git rev-parse --short origin/main   → 558933b
$ git rev-list --left-right --count origin/main...HEAD → 0 0
$ git status --short
 M docs/rapports/FD-CONTRACT-001.md
```

## Référence DrawCiel

`git fetch` dans SéquenCiel (lecture seule) : `origin/main` = `88f95b75`,
inchangé. Delta vide, aucun impact : le ticket ne touche ni la scène, ni le
renderer, ni le viewport.

## Contrat hérité de FD-MODULES-001

Le contrat est utilisé tel quel :

- `ModuleDescriptor` (définition spécialisée, version, `api_version`, codecs
  et projections, assets en liste fermée, sonde) ;
- `activate_modules` (liste explicite, diagnostics) ;
- `read_specialized_resource`.

Seul ajout : le code de diagnostic `asset-missing`, propre à l'hôte. Le
ToolRegistry et le Graphic Core ne changent pas.

## Source d'activation

**`forge-design --module PAQUET`**, répétable. C'est explicite, hors projet,
déterministe (l'ordre est celui de la ligne de commande) et sans fichier de
configuration. La liste ne vient jamais de `config.py`, `bootstrap.py`,
`mvc/` ou d'un fichier du projet.

## CLI

- `--module` (`action="append"`), absent par défaut : aucun module.
- Après l'analyse des arguments seulement : `activate_modules(paquets)`, une
  fois.
- Configuration malformée (nom invalide, chaîne vide, doublon) : message
  « Configuration des modules… » et **code 2 avant tout démarrage du
  serveur**.
- Diagnostics sur stderr : `Module fd_absent non chargé (module-missing) :
  Module non installé ; rien n'est chargé.`, sans bloquer le démarrage.
- `--help` et `--version` n'importent ni `forge_design.web` ni
  `forge_design.modules` (test en sous-processus).

## Composition Forge MVC

```text
CLI ─▶ activate_modules ─▶ run_server(modules=) ─▶ create_server(modules=)
    ─▶ create_application(modules=) ─▶ ModuleHost ─▶ Router Forge (routes exactes)
```

Le chargement Python reste hors de la composition HTTP : `create_application`
reçoit une `ModuleActivation` déjà calculée. Les tests en injectent une
directement, sans `sys.path`. Forge MVC reste l'unique pile Web
(`Application`, `Router`, `Request`, `Response`, Jinja, `create_wsgi_app`).
Aucun serveur secondaire, aucun serveur statique générique.

**Zone « Modules » du shell.** Une `ContextVar` (`_SHELL`) est posée par
l'application autour de chaque handler (enveloppe `add` de
`create_application`) et lue par `render_page`. Aucun handler existant n'est
modifié. La valeur ne vit que le temps d'une requête et appartient à
l'application qui la pose : deux applications de test ont chacune la leur. Ce
n'est pas un registre global.

## ModuleHost

`forge_design/modules/host.py` :

- **possède** l'activation et les modules exposés (dans l'ordre), les
  diagnostics (activation, puis hôte) et les assets lus à la construction ;
- **fournit** `modules()`, `module(id)`, `navigation()`, `diagnostics()`,
  `assets(id)`, `asset(id, name)`, `resource_type(id, type)`,
  `list_resources(id, root)`, `read_resource(id, type, root, path)` ;
- **ne possède pas** le ToolRegistry, une sémantique métier ni un accès au
  système de fichiers pour le compte du module.

## Cycle de vie activation / projet

L'activation vit le temps d'un démarrage, et l'hôte le temps de
l'application. Le projet relève de `CurrentProjectContext` : chaque opération
reçoit la racine courante. Test : ouvrir un projet, puis un autre ; la page du
module reflète le second, et l'importeur n'est appelé qu'une fois.

## Listing sécurisé des ressources

Nouvelle primitive générique du cœur :
`forge_design.specialized.list_specialized_resources(root, tool, type)` →
`SpecializedResourceListing(paths, present, truncated, issues)`.

- Même racine et mêmes exceptions que la lecture (projet Forge requis).
- Espace de sources ouvert segment par segment, chacun relativement à son
  parent (`O_NOFOLLOW`), avec contrôle `samestat`. Un préfixe lié ou non
  répertoire n'est jamais traversé.
- Parcours : `scandir` sur le descripteur, `stat` sans suivre les liens.
  Seuls sont retenus les fichiers ordinaires portant le suffixe et acceptés
  par `resource_parts`, la même politique lexicale que la lecture. Liens
  (fichiers et dossiers), FIFO, dossiers et fichiers cachés sont ignorés ; un
  dossier remplacé pendant le parcours est écarté avec une issue
  `resource-refused`.
- **Aucun contenu lu** : test avec `os.read` interdit.
- Tri lexical déterministe. Inventaire au mieux, pas un instantané atomique
  (documenté).

## Bornes du listing

Nouvelles constantes (`forge_design/limits.py`), aux mêmes ordres de grandeur
que l'inventaire des contrats de vue :

- `MAX_SPECIALIZED_LISTED_RESOURCES = 512` ;
- `MAX_SPECIALIZED_DIRECTORY_ENTRIES = 4096` ;
- `MAX_SPECIALIZED_SCAN_DEPTH = 32`.

La longueur de chemin réutilise `MAX_SOURCE_PATH_LENGTH`, via
`resource_parts`. Toute borne atteinte donne `truncated = True`, sans aucun
balayage non borné.

## Navigation Modules

Une zone `<nav aria-label="Modules">` apparaît sous la navigation des outils,
qui reste inchangée (Accueil, Project Inspector, Route Explorer, Entity
Explorer, Debug Center, Template Viewer, Éditeur). Elle n'apparaît que si au
moins un module **actif, compatible, exposé et muni d'une `UiEntry`** existe,
dans l'ordre d'activation, avec `aria-current` sur la page du module.
L'icône d'`UiEntry` est ignorée (documenté). Un module désactivé, refusé ou
sans `UiEntry` n'a ni entrée ni route.

## Page module

`GET /modules/<id>/` (`no-store`), template du cœur `module.html` :

- libellé, identifiant, description, version, API ;
- capacités disponibles ;
- dépendances indisponibles (nom et rôle) ;
- par type : espace et suffixe, ressources triées en liens, « Espace de
  sources absent », troncature et issues.

Sans projet : « Aucun projet ouvert. » (200). Racine devenue invalide : 409.

## Page ressource

`GET /modules/<id>/resource?type=&path=` (`no-store`), template
`module_resource.html`. Validation stricte : exactement `type` et `path`, une
valeur chacun ; type connu (kebab-case, déclaré) ; chemin non vide et d'au
plus 4 096 caractères. Statuts :

- 400 : paramètre ou chemin refusé ;
- 404 : ressource introuvable ;
- 409 : aucun projet ;
- 200 : ressource valide, invalide ou de version non supportée, avec ses
  diagnostics.

Affichage : module et version, type et format, chemin relatif, version du
format, révision (`sha256` abrégé et taille, jamais le device ni l'inode),
validation, issues. Aucun bouton d'édition ni formulaire.

## Lecture via ResourceHost

Exclusivement `read_specialized_resource(root, definition, type, path,
binding.codec)`. La couche Web ne fait aucun `open`, `read_bytes`,
`read_text`, `os.`, `scandir` ou `Path(` (test statique et mutation). Le
chemin est revalidé par `resource_parts`. Les messages affichés ne
contiennent jamais la racine absolue (test).

## Projection GraphicScene

Si `binding.scene` existe et que la lecture rend un document,
`binding.scene(document)` est appelée par l'hôte. Le résultat doit être un
objet, sérialisable en JSON strict (`allow_nan=False`), d'au plus
**8 Mio** (`MAX_MODULE_SCENE_BYTES`) ; l'hôte en transporte une copie JSON
détachée. En cas d'exception, la page affiche
« Projection graphique du module en échec (Classe). » ; la trace part sur le
logger `forge_design.modules` (développeur), jamais dans la page. Même
traitement pour un codec en exception : « Décodage du module en échec
(Classe). ». La forme exacte de la scène est validée dans le navigateur par
le vrai `validateScene` : l'hôte ne réimplémente pas `model.js`.

## Client graphique générique

`/module-resource.js` (route fixe du cœur, comme `/debug-flow.js`) : il lit
la scène, appelle `createGraphicEngine`, masque le repli seulement en cas de
succès et annonce « Élément sélectionné : … ». Aucun vocabulaire de module,
aucun `/modules/`, zoom, minicarte ni `import()` (test). Viewport, niveaux de
détail et minicarte viennent du moteur.

## Fallback sans JavaScript

**Option A** : pas de second renderer SVG serveur. Les métadonnées, la
validation et les diagnostics restent lisibles, avec le message « La
visualisation graphique nécessite JavaScript. ». Vérifié sans JavaScript
dans Chromium et Firefox : métadonnées présentes, message visible, aucune
scène rendue.

## Assets modules

- Une route exacte par asset déclaré, `/modules/<id>/assets/<name>`.
- Lu par `importlib.resources.files(asset_package).joinpath(source)` **à la
  construction de l'hôte** : existence vérifiée, octets en mémoire.
- Type MIME fixé par le cœur selon l'extension.
- Asset introuvable : module non exposé au Web, diagnostic `asset-missing`,
  donc jamais de route cassée.
- Les CSS du module ne sont chargées que sur ses propres pages. Aucun JS de
  module n'est chargé en V1, et aucun SVG de module n'est injecté (pour une
  éventuelle utilisation future : `<img src>`).

## Namespace et routes

`/modules/<id>/` est confirmé. Pour le témoin `witness` :

```text
GET /modules/witness/
GET /modules/witness/resource
GET /modules/witness/assets/witness.css
```

Vérifié en HTTP et dans les navigateurs :

- `/modules/witness/foo`, `/modules/witness`, `/modules/unknown/`,
  `/modules/witness/actions/save`, un asset non déclaré, l'asset d'un autre
  module, `../` et `%2e%2e` → **404** ;
- `POST /modules/witness/` et `POST /modules/witness/resource` → **405** ;
- sans `--module`, tout `/modules/...` → 404.

## Diagnostics d'activation

- CLI : sur stderr.
- Accueil : bloc « Modules non chargés » (paquet, code, message borné, jamais
  de trace), affiché seulement s'il y a des diagnostics et absent des autres
  pages.
- Codes : ceux de FD-MODULES-001, plus `asset-missing`.

## Dépendances optionnelles

Affichées sur la page du module : capacités disponibles (par exemple
`open, validate`, sans `simulate`) et dépendances indisponibles (`spice` —
« Moteur de simulation »). Aucun bouton d'installation.

## Sécurité filesystem

L'inventaire et la lecture relèvent du cœur (O_NOFOLLOW, `samestat`,
fichiers ordinaires, bornes) ; le module ne voit que des octets. Tests :
liens, FIFO, préfixe lié, dossier remplacé, chemins longs, bornes, et
lecture refusée hors espace, y compris celui d'un autre module.

## Sécurité Web

GET seulement : aucun nouvel enjeu CSRF. La garde d'hôte local
(`127.0.0.1`, contrôle de l'en-tête Host) est conservée. Pages dépendant du
projet en `no-store`. Paramètres stricts. La scène est transportée par
`scene_json_payload` (`<`, `>`, `&`, U+2028 et U+2029 échappés) : le libellé
hostile `</script><svg onload=alert(1)>` reste du texte (tests et deux
navigateurs, aucune boîte de dialogue).

## CSP

Inchangée : `script-src 'self'`, `style-src 'self'`. Ni JS en ligne, ni
`unsafe-eval`, ni CDN. Aucune violation dans les deux navigateurs.

## ToolRegistry

**Inchangé**, cinq Tools. `server.py` ne contient ni `registry.register` ni
`ToolRegistry(` (test statique, mutation tuée).

## Fake module témoin

`tests/module_support.py` (jamais livré) :

- identifiant `witness`, `UiEntry("Module témoin")` ;
- un type `document` (`mvc/witness`, `*.witness.json`) ;
- `RecordingCodec`, qui trace les types reçus : **uniquement `bytes`** ;
- projection A → B → C, où le titre devient un libellé ;
- asset `witness.css`, qui réutilise `forge_design.web:static/shell.css`
  comme témoin.

Il est fourni par un importeur injecté. Le harnais navigateur (hors dépôt)
définit le même témoin pour son serveur.

## Deux modules témoins

`witness-a` et `witness-b` : routes, assets, types et espaces de sources
séparés ; navigation dans l'ordre d'activation (B puis A) ; l'asset de l'un
n'est jamais servi sous l'autre ; la ressource de l'un est refusée (400) par
l'autre. Les doublons de module et de type de ressource restent refusés à
l'activation (FD-MODULES-001), et donc jamais exposés.

## Tests Python

- `test_specialized_listing.py` (10) : vide, absent, imbrication et tri,
  suffixes, cachés, contenu jamais lu, liens fichier et dossier, FIFO,
  préfixe lié, chemin trop long, bornes de nombre, d'entrées et de
  profondeur, mauvais type, racine non Forge, dossier remplacé.
- `test_module_host.py` (14) : exposition et ordre, navigation, assets,
  asset manquant, inventaire, lecture et projection (le module ne voit que
  des octets), lecture invalide, version future, ressource introuvable,
  refus, module, type ou projet inconnu, 5 échecs de projection, copie
  détachée, codec en exception, dépendances optionnelles.
- `test_web_modules.py` (15) : zéro module ; module absent ou incompatible ;
  pages, ressource, assets, 404 et 405 ; 7 requêtes invalides ; doublon de
  paramètre et absence de projet ; ressources invalides et projection en
  échec ; deux modules ; changement de projet sans réactivation ; frontière
  statique Web et ToolRegistry.
- `test_cli.py` (17, dont 5 nouveaux) : `--module` répétable, module absent
  non fatal, 3 configurations malformées (code 2), `--help` et `--version`
  sans import.
- Ajustés : `test_modules_contract.py` (nouveaux imports légitimes de l'hôte,
  jamais Web, Graphics ni Circuit) ; `test_graphics_forge_boundary.py`
  (routes enregistrées par l'enveloppe `add`) ; signatures des faux
  `create_server` et `run_server` dans `test_web_server.py`,
  `test_web_real_preview.py` et `test_cli.py` (nouvel argument `modules`) ;
  `test_route_graph_script.py` (client et 14 suites).

## Tests Node

102 tests (99 + 3) :

- `module-client.test.mjs` : montage, sélection et texte hostile ; 4 scènes
  refusées par `validateScene` (vide, JSON cassé, clé inconnue, arête vers un
  nœud absent), repli conservé ; client générique, sans contournement du
  moteur.
- Test de vocabulaire du moteur étendu à `witness`, `specialized` et
  `/modules/`.

## Chromium

Chrome 154 headless (CDP). Deux serveurs de test : 8766 avec
`pkg_witness`, `pkg_b`, `fd_absent` (absent) et `pkg_future` (API 99) ; 8767
sans module. Projet synthétique `tmp/gxm-browser`.

Scénario **12/12** :

- fermeture du projet initial ;
- accueil : zone ordonnée, distincte, avec deux diagnostics ;
- page module sans projet, CSS du module chargée ;
- page module : version, capacités, dépendance, 4 ressources triées ;
- ressource : métadonnées, moteur rendu, texte hostile inerte ;
- sélection et Échap ;
- semantic zoom (detail, normal, overview, detail) et minicarte ;
- ressources invalide et future ;
- statuts réels des assets et routes (200, 404, 405) ;
- deux modules séparés ;
- serveur sans module : aucune zone, aucune route ;
- aucune exception ni violation.

Sans JavaScript : OK. Non-régression Graphics : viewport **29/29**, Debug et
trois clients **12/12**.

## Firefox

Firefox ESR 153 headless (BiDi) : scénario modules **12/12**, sans JavaScript
OK, viewport **27/27**, Debug **12/12**. Le premier passage Firefox avait
échoué sur « page module sans projet », parce que le serveur gardait le
projet ouvert pendant le passage Chromium. Le scénario ferme désormais le
projet au départ, et les deux navigateurs ont été relancés.

## Mutations

Une à la fois, `__pycache__` purgé, sources restaurées : **15/15 tuées**.

| Sabotage | Résultat | Premier test en échec |
|---|---|---|
| module absent devient fatal | Tué | `test_absent_and_incompatible_modules_are_diagnosed_not_fatal` |
| module non exposable (asset manquant) obtient une route | Tué | `test_missing_asset_hides_the_module_with_a_diagnostic` |
| zone Modules affichée sans module actif | Tué | `test_without_modules_nothing_is_exposed` |
| module sans UiEntry obtient une entrée | Tué | `test_exposure_navigation_order_and_assets` |
| le module reçoit un objet hôte (au-delà de son document) | Tué | `test_module_pages_resources_and_assets` |
| listing suit les liens | Tué | `test_symlinks_and_special_files_ignored` |
| listing dépasse la borne | Tué | `test_count_limit_truncates` |
| lecture directe par le Web (`read_bytes`) | Tué | `test_web_layer_never_touches_project_files_or_the_tool_registry` |
| route d'assets dynamique (traversée, non déclarés) | Tué | `test_module_pages_resources_and_assets` |
| assets d'un module servis sous un autre | Tué | `test_two_modules_are_isolated_and_ordered` |
| projection en exception casse la page | Tué | `test_invalid_versions_and_failing_projection_are_displayed` |
| module enregistré comme Tool | Tué | `test_web_layer_never_touches_project_files_or_the_tool_registry` |
| page module sans `no-store` | Tué | `test_module_pages_resources_and_assets` |
| deux modules partagent leurs routes (liaison tardive de fermeture) | Tué | `test_two_modules_are_isolated_and_ordered` |
| logique de module dans le Graphic Core | Tué | `aucune connaissance de Route Explorer ni d'un domaine` |

« Module reçoit Router » n'a pas d'équivalent direct : le contrat n'a aucun
point d'entrée qui pourrait transmettre un Router. La mutation la plus proche
transmet un objet de l'hôte à la projection ; elle est détectée, car le
module ne doit recevoir que ses octets puis son document.

## Packaging

`pyproject.toml` : `templates/module.html`, `templates/module_resource.html`
et `static/module-resource.js`. Les modules Python (`modules/host.py`,
`specialized/listing.py`, `web/modules.py`) font partie de paquets déjà
déclarés.

## Wheel installée

Installée isolément, chargée depuis l'installation :

- **sans module** : accueil sans zone, `/module-resource.js` 200,
  `/modules/witness/`, ressource et asset → 404 ;
- **avec le témoin injecté** (et un module absent) : zone et diagnostics,
  page module 200 `no-store` avec ressources, page ressource avec scène et
  client, asset 200 `text/css; charset=utf-8`.

Observation hors périmètre : une 404 du Router Forge écrit sur stderr une
trace « Aucun renderer enregistré » (page d'erreur par défaut de Forge). C'est
le comportement de la bibliothèque, antérieur et indépendant de ce ticket.

## Performance

Mesuré dans Node et Python, sur un faux module :

- activation : une fois par démarrage ; construction de l'hôte (assets lus)
  en 3,3 ms ;
- inventaire de 500 ressources sur 10 dossiers : 3,3 à 3,6 ms ;
- lecture, validation et projection : 0,4 à 0,6 ms ;
- assets servis depuis la mémoire ; aucune activation par requête.

## Limites V1

- Consultation seulement : pas d'édition, de POST, de création ni de
  suppression.
- Pas de JS, de template ni de rendu sans JavaScript fournis par un module ;
  icône d'`UiEntry` ignorée.
- Les diagnostics `asset-missing` sont visibles sur l'accueil, mais pas sur
  la sortie de la CLI : l'hôte est construit par `create_application`.
- Inventaire au mieux, borné, sans instantané atomique.
- Hors périmètre : le test instable `test_runtime_detects_dead_proxy` (Real
  Preview).

## Circuit

Aucune modification de `forge_design/circuit/`, aucun nouvel import de
Circuit (test de frontière sur tout le cœur). Circuit reste gelé.

## Roadmap

FD-MODULES-002 fait ; **FD-MODULES-003 — extraire Circuit dans
ForgeDesign-Circuit** devient le ticket suivant, avec une cible
d'intégration réelle.

### Décisions

| | Question | Réponse |
|---|---|---|
| A | Source d'activation V1 ? | **CLI `--module PAQUET`**, répétable |
| B | Activation répétée par requête ? | **Non** : une par démarrage (test : un seul import malgré un changement de projet) |
| C | Le module reçoit-il le Router ? | **Non** : aucun point d'entrée ; routes enregistrées par l'hôte |
| D | Le module reçoit-il la racine du projet ? | **Non** : octets pour le codec, document pour la projection (types tracés) |
| E | Qui liste les fichiers ? | **L'hôte du cœur** (`list_specialized_resources`) |
| F | Qui lit le fichier ? | **ResourceHost du cœur** (`read_specialized_resource`) |
| G | Qui décode ? | **Le codec du module** |
| H | Qui projette vers Graphics ? | **`ResourceBinding.scene` du module**, isolée et bornée par l'hôte |
| I | Qui rend ? | **Le Graphic Core** (`/module-resource.js`, mêmes modules) |
| J | Fallback graphique sans JavaScript ? | **Non en V1** : métadonnées, diagnostics et message explicite |
| K | Le module fournit-il son HTML ? | **Non en V1** : templates du cœur |
| L | Comment les assets sont-ils servis ? | **Routes exactes générées par l'hôte**, vérifiées et lues à l'activation Web, MIME du cœur |
| M | Navigation module ? | **Seulement un module actif, compatible, exposé et muni d'une `UiEntry`**, dans l'ordre d'activation |
| N | Le ToolRegistry change-t-il ? | **Non** |
| O | Le Graphic Core change-t-il ? | **Non** (aucun fichier `static/graphics/` modifié ; seul le test de vocabulaire est étendu) |
| P | L'hôte est-il assez réel pour extraire Circuit ? | **Oui.** Faits : activation réelle par la CLI, routes Forge exactes, inventaire et lecture sécurisés, codec du module, projection rendue par le Graphic Core, assets, diagnostics, 0, 1 et 2 modules, module absent ou incompatible, avec et sans JavaScript, dans deux navigateurs et depuis la wheel installée. Pour Circuit, il restera à fournir `FORGE_DESIGN_MODULE` (définition existante, codec existant, projection CircuitDocument → GraphicScene, éventuellement des assets), sans toucher à l'hôte |

## Fichiers créés

- `forge_design/modules/host.py`, `forge_design/specialized/listing.py`,
  `forge_design/web/modules.py`
- `forge_design/web/templates/module.html`,
  `forge_design/web/templates/module_resource.html`,
  `forge_design/web/static/module-resource.js`
- `tests/module_support.py`, `tests/test_module_host.py`,
  `tests/test_specialized_listing.py`, `tests/test_web_modules.py`,
  `tests/js/graphics/module-client.test.mjs`
- `docs/modules/module-host.md`, `docs/rapports/FD-MODULES-002.md`

## Fichiers modifiés

- `forge_design/cli.py` (`--module`), `forge_design/web/server.py`
  (`modules=`, enveloppe `add`, routes des modules, `/module-resource.js`),
  `forge_design/web/rendering.py` (zone Modules par requête),
  `forge_design/web/templates/layout.html`, `templates/index.html`,
  `static/shell.css`, `forge_design/modules/activation.py`
  (`asset-missing`), `forge_design/specialized/__init__.py`,
  `forge_design/limits.py`, `pyproject.toml`
- `tests/test_cli.py`, `tests/test_modules_contract.py`,
  `tests/test_graphics_forge_boundary.py`, `tests/test_route_graph_script.py`,
  `tests/test_web_real_preview.py`, `tests/test_web_server.py`,
  `tests/js/graphics/model.test.mjs`
- `docs/modules/module-architecture.md`, `docs/02-architecture.md`,
  `docs/03-roadmap.md`

## Validation globale finale

| Contrôle | Résultat |
|---|---|
| `python -m compileall -q forge_design` | Réussi |
| `ruff check forge_design tests` | Réussi |
| `ruff format --check .` | 406 fichiers conformes (Markdown compris) |
| `pyright` | 0 erreur, 0 avertissement |
| `git diff --check` | Réussi |
| `node --check` (8 modules, 4 clients, 16 fichiers de test) | Réussi |
| Suites Node `tests/js/graphics` | 102 réussis |
| Ciblés : modules, hôte, listing, Web, CLI, Specialized, frontières, Real Preview, serveur | 546 réussis |
| Mutations | 15/15 tuées |
| Suite globale `pytest` (hors du dépôt, `--basetemp` court sous `tmp/`) | **4759 réussis**, relancée après insertion de ces résultats |
| `python -m pip check` | Aucune dépendance cassée |
| Chromium 154 | modules 12/12, sans JavaScript OK ; viewport 29/29, Debug 12/12 |
| Firefox 153 | modules 12/12, sans JavaScript OK ; viewport 27/27, Debug 12/12 |
| Wheel installée isolément | sans module et avec le témoin injecté : routes, templates, client, assets |
| MkDocs | N/A : aucune configuration MkDocs dans Forge Design |

## État Git final

Commit unique `feat: implémenter l'hôte des modules spécialisés (FD-MODULES-002)`,
au-dessus de `558933b`. `docs/rapports/FD-CONTRACT-001.md` reste modifié
localement, hors commit. Aucun push.
