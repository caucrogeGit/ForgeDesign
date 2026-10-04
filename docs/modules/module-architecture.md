# Architecture des modules spécialisés

Statut : **normatif pour la phase Modules** (FD-MODULES-001, hôte Web
FD-MODULES-002). Code : `forge_design/modules/` (descripteur, activation,
`ModuleHost`), `forge_design/specialized/listing.py` (inventaire),
`forge_design/web/modules.py` (pages). Mode d'emploi : [Hôte des modules](module-host.md).

## Objectif

Permettre à Forge Design d'héberger des **modules spécialisés externes**
(Circuit, Network, Flowchart…) sans embarquer leur logique métier dans le
cœur. Le cœur reste complet et utilisable seul ; un module ne s'ajoute que s'il
est installé, compatible et explicitement activé. Ce n'est pas un système de
plugins universel : c'est une frontière simple, explicite, testable.

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

## ModuleDescriptor

Un paquet de module expose l'attribut `FORGE_DESIGN_MODULE`, un
`ModuleDescriptor` gelé et validé à la construction :

| Champ | Contrat |
|---|---|
| `definition` | `SpecializedToolDefinition` existante : `id` (kebab-case, au plus 32 caractères), nom, description, types de ressources, capacités, dépendances optionnelles, entrée UI |
| `version` | Version du paquet, observable (même forme que les versions de format) |
| `api_version` | Version de l'API hôte ciblée (entier) |
| `bindings` | Un `ResourceBinding` par type de ressource déclaré, ni plus ni moins : codec `SpecializedResourceCodec` (octets seulement) et projection facultative `document → GraphicScene` |
| `asset_package` | Paquet Python contenant les assets (lu par l'hôte via `importlib.resources`) |
| `assets` | Liste fermée (au plus 32) de `ModuleAsset(name, source)` : nom `[a-z0-9-]+.(js\|css\|svg)`, source relative sans segment vide, `.`, `..` ou caché |
| `dependency_probe` | Sonde facultative, sans effet de bord : `{id de dépendance: disponible}` |

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
  ses pages ; aucun JS de module n'est chargé en V1.
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
- L'édition viendra par des **actions bornées** POST
  (`/modules/<id>/actions/<nom>`), avec le contrôle d'origine du cœur et une
  sauvegarde par `write_specialized_resource`. Le contrat ne fige pas ces
  actions avant le premier besoin réel.

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

Deux versions séparées : la **version du paquet** (`ModuleDescriptor.version`,
cycle de release du module) et l'**API hôte** (`api_version`, entier
incrémenté seulement pour une rupture du contrat). La métadonnée Python
`forge-design >= X, < Y` complète, au niveau de l'installation.

## Testing

- Le cœur garde des **tests de contrat** avec un faux module (descripteur,
  activation, diagnostics, lecture par l'hôte, frontières), sans aucun test
  métier d'un domaine après migration.
- Chaque module a sa propre suite : domaine, codec, projection, et
  compatibilité contre la **version minimale supportée** de Forge Design.
- Développement : `pip install -e ../ForgeDesign-Circuit` dans
  l'environnement de développement, jamais de `PYTHONPATH` bricolé.
- CI future du module : matrice minimale (version minimale et dernière version
  du cœur).

## Migration Circuit

`forge_design/circuit/` (FD-CIRCUIT-002/003) quitte le cœur **avant** toute
poursuite fonctionnelle : FD-CIRCUIT-004 n'est pas poursuivi dans le cœur.
Plan fichier par fichier : rapport FD-MODULES-001. Stratégie Git : **nouveau
dépôt** initialisé par copie du contenu à un commit source nommé, avec un
fichier de provenance (commits source, chemins, rapports). Puis suppression du
cœur dans un commit ultérieur. Aucune réécriture d'historique.

## Out of scope V1

- Découverte automatique, entry points, `pkgutil`, chargement de paquets
  inconnus.
- Sandbox de processus pour un module.
- Handlers Forge MVC fournis par un module ; actions d'édition (POST).
- Sauvegarde depuis l'interface, glisser, simulation.
- Solveur de dépendances entre modules.
- Moteur 3D : ce n'est pas une extension automatique du Graphic Core 2D ;
  ce serait une capacité ou un module séparé, à étudier le moment venu.
