# Architecture des modules spécialisés

Statut : **normatif** — contrat des modules (FD-MODULES-001, hôte Web
FD-MODULES-002, actions FD-EDIT-001, édition FD-GRAPHICS-EDIT-001/002),
consolidé par l'audit FD-ARCH-001. Code : `forge_design/modules/` (descripteur,
activation, `ModuleHost`), `forge_design/specialized/` (contrat et hôte de
ressources), `forge_design/web/modules.py` (pages, actions, assets),
`forge_design/web/static/module-resource.js` (client générique). Mode d'emploi :
[Hôte des modules](module-host.md) ; actions : [contrat](module-actions.md) ;
frontières normatives : [cœur et modules](../architecture/core-module-boundaries.md).

## Objectif

Permettre à Forge Design d'héberger des **modules spécialisés externes**
(Circuit, Network, Flowchart…) sans embarquer leur logique métier dans le
cœur. Le cœur reste complet et utilisable seul ; un module ne s'ajoute que s'il
est installé, compatible et explicitement activé. Ce n'est pas un système de
plugins universel : c'est une frontière simple, explicite, testable.

L'exemple normatif est le **module témoin « flowchart-like »** des tests du cœur
(`tests/flow_witness/`, [exemple minimal](#exemple-minimal)) : un domaine sans
rapport avec Circuit. ForgeDesign-Circuit est la **validation réelle** du
contrat, jamais sa définition.

## Frontière core / module

| Élément | Forge Design (core) | Module spécialisé |
|---|---|---|
| Analyse de projet Forge (cinq Tools) | oui | non |
| Template Designer | oui | non |
| Graphic Core (JS) et couloirs Python | oui | non |
| Viewport, minicarte, niveaux de détail | oui | non |
| Hôte de ressources (`read/write_specialized_resource`) | oui | non |
| Système de fichiers sécurisé | oui | non |
| Historique, révision, conflit | oui | non |
| Contrat spécialisé (`forge_design.specialized`, `forge_design.modules`) | oui | l'utilise |
| Schéma et format du domaine | non | oui |
| Validation métier | non | oui |
| Catalogue | non | oui |
| Adaptateur Graphics du domaine (document → GraphicScene) | non | oui |
| Actions : routes POST, origine, payload, révision, écriture, statut HTTP | oui | non |
| Actions : transformation métier pure (`handler`) | non | oui |
| JS d'édition spécialisé | non | oui |
| Simulation et ses dépendances | non | oui |
| Dépendances optionnelles du domaine | non | oui |

Forge Design ne contient ni résistance, ni LED, ni tension, ni courant, ni
simulation électrique, ni routeur IP, ni protocole réseau, ni sémantique
d'organigramme.

## Dépendances

```text
Forge Design (core) ◀── module spécialisé
```

- Un module dépend du cœur par son API publique : `forge_design.specialized`,
  `forge_design.modules`, le contrat JSON `GraphicScene` et les modules JS
  `/graphics/*.js`.
- Le cœur ne dépend **jamais statiquement** d'un module : aucun `import`
  d'un module dans le code du cœur (test de frontière). Le seul lien est
  l'activation explicite, qui importe à l'exécution un paquet **nommé par la
  configuration**.
- Un module ne dépend jamais de SéquenCiel. DrawCiel reste une référence de
  développement, jamais une dépendance d'exécution ; un éventuel import de
  documents DrawCiel serait un outil de migration explicite.

## API publique Python

Seuls `forge_design.modules` et `forge_design.specialized` (avec leur `__all__`)
sont l'API supportée ; leurs exports sont figés par un test
(`test_module_boundaries.py::test_public_exports_are_a_reviewed_snapshot`) :
tout ajout ou retrait est une décision. Sous-modules (`forge_design.modules.host`,
`…actions`, `…descriptor`, `…activation`) et le reste de `forge_design` : internes.

| Audience | `forge_design.modules` | `forge_design.specialized` |
|---|---|---|
| **Module** (écrire un module) | `MODULE_API_VERSION`, `ModuleDescriptor`, `ResourceBinding`, `ModuleAsset`, `ModuleAction`, `ModuleActionPayload`, `ModuleActionPayloadError`, `ModuleActionRefused`, `ModuleActionResult`, `ActionHandler`, bornes `MAX_MODULE_ACTION*`, `MAX_SAFE_INTEGER`, `RESERVED_ACTION_FIELDS` | `SpecializedToolDefinition`, `SpecializedResourceType`, `SpecializedCapability`, `PlatformCapability`, `PLATFORM_CAPABILITIES`, `OptionalDependency`, `UiEntry`, `SpecializedResourceCodec`, `SpecializedFormatError`, `SpecializedIssue`, `SpecializedValidationResult`, `MAX_SPECIALIZED_ISSUES`, `MAX_SPECIALIZED_LOCATION_DEPTH`, `loads_strict_json` |
| **Hôte** (composition, diagnostics, tests de contrat) | `activate_modules`, `ActiveModule`, `ModuleActivation`, `ModuleDiagnostic`, `SUPPORTED_MODULE_API_VERSIONS`, `DESCRIPTOR_ATTRIBUTE`, `MODULE_URL_PREFIX`, `ASSET_MEDIA_TYPES` | Hôte de ressources : `read/write_specialized_resource`, `list_specialized_resources`, résultats (`SpecializedReadResult`, `SpecializedWriteResult`, `SpecializedResourceListing`, `SpecializedResourceRef`, `SpecializedResourceRevision`) et erreurs (`SpecializedResourceError` et sous-classes, `InvalidSpecializedResourceError`, `UnsupportedSpecializedVersionError`, `SpecializedCapabilityError`, `ErrorCategory`) |

Les symboles « hôte » restent exportés (aucun défaut constaté, retrait non
nécessaire) ; un module n'en a pas besoin : il ne lit ni n'écrit le projet et
n'active personne. Circuit importe 8 symboles de `forge_design.modules` et 10 de
`forge_design.specialized`, tous dans la colonne « Module », et aucun autre
sous-module du cœur.

## ModuleDescriptor

Un paquet de module expose l'attribut `FORGE_DESIGN_MODULE`, un
`ModuleDescriptor` gelé et validé à la construction :

| Champ | Contrat |
|---|---|
| `definition` | `SpecializedToolDefinition` existante : `id` (kebab-case, au plus 32 caractères), nom, description, types de ressources, capacités, dépendances optionnelles, entrée UI |
| `version` | Version du paquet, observable (même forme que les versions de format) |
| `api_version` | Version de l'API hôte ciblée (entier) |
| `bindings` | Un `ResourceBinding` par type de ressource déclaré, ni plus ni moins : codec `SpecializedResourceCodec` (octets seulement), projection facultative `document → GraphicScene`, et, facultatifs (FD-GRAPHICS-EDIT-001), `editor_script` (asset `.js` déclaré, exige une projection) et `editor_config` (`document → JSON`, exige un script) ([édition](module-host.md#édition)) |
| `asset_package` | Paquet Python contenant les assets (lu par l'hôte via `importlib.resources`) |
| `assets` | Liste fermée (au plus 32) de `ModuleAsset(name, source)` : nom `[a-z0-9-]+.(js\|css\|svg)`, source relative sans segment vide, `.`, `..` ou caché |
| `dependency_probe` | Sonde facultative, sans effet de bord : `{id de dépendance: disponible}` |
| `actions` | Facultatif (`()`, FD-EDIT-001) : au plus 32 `ModuleAction`, chacune sur un type déclaré, modifiable, qui offre `save` et sa capacité ([actions](module-actions.md)) |
| `requires_forge_design` | Facultatif (`None`, FD-RELEASE-001) : spécificateur PEP 440 des versions de Forge Design acceptées (`">=0.2.0,<1"`), au plus 200 caractères imprimables ; le descripteur n'en vérifie que la forme, l'activation l'interprète ([versions](../release/versioning.md)) |

Le descripteur ne reçoit ni Router, ni Application, ni Request, ni racine de
projet. Il n'a donc aucun moyen d'enregistrer une route, d'injecter un
middleware ou de lire le projet.

## Activation

**Explicite, sans découverte.** `activate_modules(paquets)` importe, dans
l'ordre donné, les seuls paquets nommés, puis lit leur descripteur.

| Option | Verdict | Raison |
|---|---|---|
| A. Liste Python explicite | **retenue** (forme) | simple, testable, ordre déterministe |
| B. Configuration du projet ouvert | **refusée** | ouvrir un projet non fiable importerait du code : exécution arbitraire |
| C. Entry points allowlistés | refusée en V1 | balaye l'environnement ; l'allowlist n'apporte rien de plus qu'un nom explicite |
| D. Registre statique dans l'application | **retenue** (lieu) | la liste arrive à la racine de composition, jamais depuis un projet |

La liste vient de la ligne de commande, **`forge-design --module PAQUET`**
(répétable, FD-MODULES-002), jamais du projet ouvert. Sans option, aucun module
n'est importé. L'activation a lieu une fois par démarrage, hors de la
composition HTTP, puis est injectée dans `create_application(modules=…)`.

## Compatibilité

- `MODULE_API_VERSION = 1` ; l'hôte n'active que
  `SUPPORTED_MODULE_API_VERSIONS`. Pas de solveur : une appartenance à un
  ensemble.
- Deux niveaux distincts : la métadonnée de distribution
  (`forge-design >= X, < Y`) gouverne l'installation ; `api_version`
  gouverne l'activation.
- Incompatible : diagnostic `api-incompatible`, module non activé, les
  autres continuent.
- Ajouts additifs restés en API 1 : `actions` (FD-EDIT-001), `editor_script`
  et `editor_config` (FD-GRAPHICS-EDIT-001), `requires_forge_design`
  (FD-RELEASE-001), tous facultatifs.
- **Version minimale du cœur** (FD-RELEASE-001, [politique](../release/versioning.md)) :
  un module déclare les versions de distribution qu'il accepte, à la fois dans
  `Requires-Dist` (`forge-design>=0.2.0,<1`, première barrière, pip) et dans
  `requires_forge_design` (même spécificateur PEP 440, seconde barrière,
  activation). Hors intervalle : `core-version-incompatible` ; version du cœur
  illisible : `core-version-unknown` ; spécificateur invalide :
  `descriptor-invalid`. Un module qui importe un symbole absent du cœur échoue
  avant toute lecture de son descripteur (`module-import-failed`).

## Resource types

Un module déclare ses types par `SpecializedResourceType`, inchangé : espace
de sources, suffixe, versions lues et écrite, taille maximale, niveaux de
validation, état persistant et état runtime. Exemple Circuit : `mvc/circuit`,
`*.circuit.json`. L'emplacement dans le projet ne dépend pas du paquet Python
qui le comprend. Deux modules ne peuvent pas revendiquer le même couple
(espace, suffixe) : `duplicate-resource-type`.

## Filesystem

**Le module ne lit ni n'écrit jamais le projet.**

```text
module (codec : octets ↔ document) ── hôte ── système de fichiers sécurisé
```

L'hôte (`read_specialized_resource`, `write_specialized_resource`) possède
le chemin, `O_NOFOLLOW`, `fstat` et `samestat`, les bornes, l'écriture
atomique, la révision, le conflit et l'historique. Le décodeur reçoit des
octets déjà lus ; l'encodeur rend des octets que l'hôte écrit. Interdit pour la
persistance dans un module : `Path(racine) / …`, `open(…)`, `os.open(…)`.

## Graphics

- Le module projette son document vers une `GraphicScene` (contrat de
  `docs/graphics/graphics-engine.md`), côté Python (`ResourceBinding.scene`)
  ou côté JS si l'édition l'exige.
- Le Graphic Core ne connaît jamais le document métier, et le cœur ne change
  pas pour accueillir un module.
- Le JS d'un module peut importer `/graphics/*.js` ; le cœur n'importe jamais
  le JS d'un module.
- Toute nouvelle capacité d'édition générique (ports, glisser, commandes,
  annulation, accroche, routage interactif, multi-sélection, propriétés) est
  motivée par un besoin réel d'un module, jamais conçue à vide.

## Assets

- Liste fermée déclarée par le module, servie par l'hôte à
  `/modules/<id>/assets/<name>`. Chaque asset est vérifié et lu à la
  construction de l'hôte ; un asset introuvable retire le module du Web avec
  le diagnostic `asset-missing`. Les CSS du module ne sont chargées que sur
  ses pages ; le seul JS de module chargé est son script d'édition, sur la page
  ressource, quand une action du type est exposée ([édition](#édition)).
- Type MIME fixé par l'hôte selon l'extension (`.js`, `.css`, `.svg`).
- Aucun chemin d'utilisateur, aucun serveur statique générique, aucune
  traversée possible.
- CSP inchangée : `script-src 'self'`, `style-src 'self'`, ni CDN, ni JS en
  ligne, ni `unsafe-eval`.

## Web integration

V1 (FD-MODULES-002) : **ouvrir et visualiser** seulement.

- L'hôte enregistre lui-même, pour chaque module exposé muni d'une
  `UiEntry`, des routes **GET** exactes : `/modules/<id>/` (page : version,
  capacités, dépendances indisponibles, ressources inventoriées),
  `/modules/<id>/resource?type=…&path=…` (lecture par l'hôte, projection par
  le module, rendu par le Graphic Core) et `/modules/<id>/assets/<name>` par
  asset déclaré. Templates du cœur ; le module ne fournit aucun HTML.
- Inventaire : `list_specialized_resources` (cœur), jamais le module.
- Sans JavaScript : métadonnées et diagnostics lisibles, message « La
  visualisation graphique nécessite JavaScript. » ; pas de second renderer
  SVG côté serveur.
- Le module ne fournit pas de handler Forge MVC : il ne voit ni Request, ni
  Response, ni Router.
- **Actions bornées** (FD-EDIT-001, [contrat](module-actions.md)) : un POST
  exact `/modules/<id>/actions/<action>` par action exposée, sous la garde
  d'origine du cœur. Le module ne fournit qu'une transformation pure
  `handler(document, payload)` ; lecture, jeton de révision, validation,
  `write_specialized_resource`, historique et statut HTTP restent au cœur.
- **Script d'édition** (FD-GRAPHICS-EDIT-001, [hôte](module-host.md#édition)) :
  un asset JS déclaré par le binding, importé par le client générique de la
  page ressource seulement si une action du type est exposée ; il reçoit un
  contexte calculé par l'hôte (URLs, jeton, configuration) et peut fournir
  l'option `nodeMove` du Graphic Core. Il ne reçoit ni Router, ni racine.

## Édition

Script et configuration d'édition (FD-GRAPHICS-EDIT-001/002) : un contrat
**facultatif, inerte sans action exposée, borné, contrôlé par le module et
validé par l'hôte**.

| Garantie | Comportement |
|---|---|
| Facultatif | `editor_script` et `editor_config` valent `None` par défaut ; un module en consultation n'en déclare pas |
| Inerte sans action | Le contexte n'existe que si le type a une action **exposée** (capacité et `save` disponibles), une révision lue, une scène et un script déclaré ; sinon aucun bloc, aucun script de module |
| Borné | Configuration : objet JSON strict sans `NaN`, au plus 1 Mio (`MAX_MODULE_EDITOR_CONFIG_BYTES`, inchangé) ; scène : au plus 8 Mio |
| Contrôlé par le module | Script : asset `.js` déclaré, servi par l'hôte ; configuration : `editor_config(document)` |
| Validé par l'hôte | URLs (script, actions), type, chemin et jeton calculés par l'hôte ; le client générique vérifie que chaque URL est un chemin du même serveur ; exceptions de configuration isolées |

Contrat JavaScript (côté navigateur, implémentation de
`/module-resource.js`) :

```js
// Asset déclaré du module, importé par le client générique (import(), même origine).
export function createResourceEditor(context) {
  // context (gelé) : { script, resourceType, path, revision, actions, config, announce }
  //   — le bloc JSON de la page nomme le type « type », le contexte JS le nomme « resourceType ».
  return {                       // ou null : consultation seule, sans message
    nodeMove,                    // facultatif : option du Graphic Core
    onViewChange(state) {},      // facultatif : option du Graphic Core
    attach(engine) {},           // facultatif : après création du moteur (calques, focus…)
  };
}
```

Cycle de vie : `module-resource.js` lit le contexte → importe le script →
`createResourceEditor(context)` → `createGraphicEngine(container, scène,
{ nodeMove, onViewChange })` → `attach(engine)` → gestes du script, qui envoie
lui-même ses actions (formulaire encodé, URL et jeton du contexte) → après
succès, navigation vers la page rechargée (nouvelle révision, nouveau moteur).
Il n'y a pas de crochet de destruction : une action réussie recharge la page.

Échec du script (introuvable, sans `createResourceEditor`, exception, option
refusée par le moteur, `attach` en échec) : la scène est montée **en
consultation seule** et l'indisponibilité est annoncée ; la ressource reste
lisible (test JS, validation navigateur FD-ARCH-001). L'API du moteur utilisable
par un script : [moteur graphique](../graphics/graphics-engine.md#public-api-for-clients).

## Exemple minimal

Le témoin `tests/flow_witness/` (non livré) montre tout le contrat sur un domaine
« organigramme » : trois étapes étiquetées, un lien, une action, un calque.

```python
ModuleDescriptor(
    definition=SpecializedToolDefinition(id="flow", …, resource_types=(flow_type,),
                                         ui_entry=UiEntry("Flux")),
    version="0.1.0",
    api_version=MODULE_API_VERSION,
    bindings=(
        ResourceBinding(
            "flow",
            FlowCodec(),                        # octets ↔ FlowDocument
            flow_scene,                         # FlowDocument → GraphicScene (runtime)
            editor_script="flow-editor.js",     # calque monde : une poignée par étape
            editor_config=flow_editor_config,   # {renameAction, steps}
        ),
    ),
    asset_package="flow_witness",
    assets=(ModuleAsset("flow-editor.js", "static/flow-editor.js"),),
    actions=(ModuleAction("rename-step", "flow", ("step", "label"), rename_step),),
)
```

Le paquet expose ce descripteur sous `FORGE_DESIGN_MODULE` et s'active par
`forge-design --module <paquet>`. Le témoin et ForgeDesign-Circuit
fonctionnent ensemble dans la même application (validation FD-ARCH-001).

## Namespace

Tout l'espace Web d'un module est sous **`/modules/<id>/`** (`base_url`
calculé par le descripteur). Aucune collision possible avec `/routes`,
`/entities`, `/debug`, `/editor`, `/graphics` ou un autre module, puisque les
identifiants sont uniques.

## Navigation

Un module **installé, compatible et activé** qui déclare une `UiEntry`
apparaît dans une zone « Modules » du shell, avec un lien vers son
`base_url`. Module désactivé : aucune route, aucun asset, aucune entrée.

## Capabilities

Vocabulaire plateforme inchangé (FD-SPECIALIZED-001) : `create`, `open`,
`edit`, `validate`, `save`, `export`, `interactive-runtime`, plus les
capacités propres à l'outil (kebab-case). L'activation calcule les capacités
**disponibles**, c'est-à-dire déclarées moins celles d'une dépendance
optionnelle indisponible.

Usage réel par l'hôte (FD-ARCH-001) :

| Capacité | Effet aujourd'hui |
|---|---|
| `open` | Lecture d'une ressource (`read_specialized_resource` refuse sans elle) |
| `save` | Écriture (type modifiable requis) ; avec la capacité de l'action, condition d'exposition de toute action |
| `create` | Écriture sans révision antérieure (création) |
| `edit` | Capacité par défaut d'une `ModuleAction` : sans elle, l'action n'est ni exposée, ni routée, ni proposée au script d'édition, qui n'est pas chargé |
| `validate`, `export`, `interactive-runtime` | Déclarables ; aucune fonction de l'hôte n'en dépend encore (la validation bloquante s'applique à toute écriture) |
| Capacités d'outil (ex. `simulate`) | Disponibles ou non selon les dépendances optionnelles ; utilisables comme capacité d'une action |

Une capacité absente n'expose donc ni route d'action, ni action dans le
contexte, ni script d'édition (tests `test_capability_gate_and_read_only_modules`,
`test_absent_capability_exposes_no_route_action_or_editor`). Le cœur ne propose
aucun bouton générique d'édition.

## Optional dependencies

`OptionalDependency` (inchangée) et la sonde du descripteur. Une dépendance
absente ou une sonde en échec ne rend indisponibles que les capacités qui en
dépendent : par exemple, Circuit installé, ouverture et visualisation
disponibles, simulation indisponible. Aucune installation automatique (ni
`pip`, ni paquet système, ni téléchargement).

## Security model

| Action | Core | Module |
|---|---|---|
| lire un fichier du projet | oui, par l'hôte | non directement |
| écrire un fichier du projet | oui, par l'hôte | non directement |
| transformer un document (action) | non | oui, handler pur |
| décider le statut HTTP d'une action | oui | non |
| décoder des octets métier | non | oui |
| encoder des octets métier | non | oui |
| servir un asset déclaré | oui | le déclare |
| modifier le Router arbitrairement | non | non |
| exécuter le JS métier installé | l'hôte le sert | oui |
| installer une dépendance | non | non, jamais automatiquement |

**Un module installé reste du code de confiance local.** Python n'est pas
sandboxé : importer un module exécute son code, et son JS partage l'origine
de Forge Design. Le contrat empêche les accès **accidentels** par
construction ; il ne protège pas contre un module volontairement malveillant.
D'où l'activation explicite, jamais depuis un projet.

## Failure isolation

| Situation | Effet |
|---|---|
| Configuration malformée (nom invalide, doublon) | `ValueError` immédiate : erreur de l'installateur, corrigée au démarrage |
| Module absent | `module-missing`, rien n'est chargé |
| Exception à l'import | `module-import-failed` (classe de l'exception), module isolé |
| Attribut absent ou d'un mauvais type | `descriptor-missing`, `descriptor-invalid` |
| API non supportée | `api-incompatible` |
| Version du cœur hors de `requires_forge_design` | `core-version-incompatible` |
| Version du cœur illisible, module contraint | `core-version-unknown` |
| `requires_forge_design` non conforme à PEP 440 | `descriptor-invalid` |
| Identifiant déjà actif | `duplicate-module` |
| Espace et suffixe déjà pris | `duplicate-resource-type` |
| Sonde de dépendances en échec | `dependency-probe-failed`, capacités dépendantes indisponibles, module actif |
| Asset déclaré introuvable | `asset-missing`, module non exposé au Web |
| Codec ou projection du module en exception | page ressource : erreur bornée (`… du module en échec (Classe).`), trace sur la journalisation du serveur, jamais dans la page |

Un descripteur invalide lève une erreur à sa construction, donc à l'import du
module : `module-import-failed`. Aucune de ces situations ne rend Forge Design
inutilisable ; l'ordre d'activation est celui de la configuration.

## Missing modules

Un projet peut contenir `mvc/circuit/*.circuit.json` sans que Circuit soit
installé. Forge Design préserve ces fichiers, ne les modifie pas, ne les
supprime pas et ne prétend pas les comprendre. Il n'a pas à afficher
« Circuit » : le nom métier peut lui être inconnu. Une détection opaque de
ressources inconnues n'est pas ajoutée tant qu'elle n'est pas utile.

## Packaging

| Élément | Convention | Exemple Circuit |
|---|---|---|
| Dépôt | `ForgeDesign-<Domaine>` (comme `ForgeDesign`) | `ForgeDesign-Circuit` |
| Distribution | `forge-design-<domaine>` (comme `forge-design`) | `forge-design-circuit` |
| Paquet Python | `forge_design_<domaine>` | `forge_design_circuit` |
| Identifiant de module | `<domaine>` en kebab-case | `circuit` |

Le paquet n'est **pas** un sous-paquet `forge_design.circuit` : `forge_design`
est un paquet ordinaire du cœur, pas un espace de noms partagé ; un préfixe
distinct rend la frontière visible à chaque import.

## Versioning

Trois versions séparées ([politique](../release/versioning.md)) : la
**version du paquet** du module (`ModuleDescriptor.version`, cycle de release du
module), l'**API hôte** (`api_version`, entier incrémenté seulement pour une
rupture du contrat) et les **versions du cœur acceptées**
(`requires_forge_design`, identique au `Requires-Dist` du module).

Audit FD-ARCH-001 : depuis FD-MODULES-001, tous les ajouts sont **additifs et
facultatifs** — `actions`, `editor_script`, `editor_config`, les options et
méthodes du Graphic Core (`nodeMove`, `onViewChange`, `addOverlay`, `worldAt`),
les exports `loads_strict_json` et `MAX_SPECIALIZED_*` ; `assets` et `UiEntry`
existaient déjà. Un module V1 sans ces champs fonctionne à l'identique :
**`MODULE_API_VERSION` reste 1**.

## Testing

- Le cœur garde des **tests de contrat** avec des modules témoins (`witness`,
  et depuis FD-ARCH-001 le second domaine `tests/flow_witness/` avec sa variante
  au script défaillant) : descripteur, activation, diagnostics, lecture par
  l'hôte, actions, édition, isolation de plusieurs modules, frontières
  (`test_modules_contract.py`, `test_module_boundaries.py`), sans aucun test
  métier d'un domaine réel.
- Chaque module a sa propre suite : domaine, codec, projection, et
  compatibilité contre la **version minimale supportée** de Forge Design.
- Développement : `pip install -e ../ForgeDesign-Circuit` dans
  l'environnement de développement, jamais de `PYTHONPATH` bricolé.
- CI future du module : matrice minimale (version minimale et dernière version
  du cœur).

## Historique : extraction de Circuit

`forge_design/circuit/` (FD-CIRCUIT-002/003) quitte le cœur **avant** toute
poursuite fonctionnelle : FD-CIRCUIT-004 n'est pas poursuivi dans le cœur.
Plan fichier par fichier : rapport FD-MODULES-001. Stratégie Git : **nouveau
dépôt** initialisé par copie du contenu à un commit source nommé, avec un
fichier de provenance (commits source, chemins, rapports). Puis suppression du
cœur dans un commit ultérieur. Aucune réécriture d'historique.

**Fait** (FD-MODULES-003) : dépôt `ForgeDesign-Circuit` créé depuis le commit
source `2a0db00` avec `PROVENANCE.md`, projection `CircuitDocument →
GraphicScene` ajoutée dans le module, puis `forge_design/circuit/`, ses tests
et ses documents retirés du cœur ([renvoi](../circuit/README.md)). Le cœur
expose pour cela `loads_strict_json`, `MAX_SPECIALIZED_ISSUES` et
`MAX_SPECIALIZED_LOCATION_DEPTH` dans `forge_design.specialized`, et livre
`py.typed`.

## Out of scope V1

- Découverte automatique, entry points, `pkgutil`, chargement de paquets
  inconnus.
- Sandbox de processus pour un module.
- Handlers Forge MVC fournis par un module (les actions POST passent par
  l'hôte, voir [actions](module-actions.md)).
- UI d'édition générique dans le cœur, undo/redo, simulation (le glisser
  opt-in du Graphic Core et le script d'édition déclaré existent depuis
  FD-GRAPHICS-EDIT-001).
- Solveur de dépendances entre modules.
- Moteur 3D : ce n'est pas une extension automatique du Graphic Core 2D ;
  ce serait une capacité ou un module séparé, à étudier le moment venu.
