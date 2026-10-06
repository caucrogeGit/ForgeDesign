# Hôte des modules spécialisés

Mode d'emploi de l'hôte livré par FD-MODULES-002. Contrat normatif :
[Architecture des modules spécialisés](module-architecture.md).

## Activer un module

```sh
pip install -e ../ForgeDesign-Circuit          # environnement de développement
forge-design --module forge_design_circuit     # activation explicite
forge-design --module pkg_a --module pkg_b     # plusieurs, dans cet ordre
```

- Sans `--module`, aucun module n'est importé : Forge Design est complet seul.
- La liste ne vient jamais du projet ouvert (ni `config.py`, ni
  `bootstrap.py`, ni `mvc/`, ni fichier de projet).
- Activation **une fois par démarrage**, avant le serveur. Changer de projet
  ne réactive rien.
- `--help` et `--version` n'importent ni modules ni backend Web.

| Situation au démarrage | Effet |
|---|---|
| Nom malformé ou listé deux fois | message, code de sortie 2, aucun serveur |
| Module absent | `Module <paquet> non chargé (module-missing) : …` sur stderr ; Forge Design démarre |
| Import en échec, descripteur absent ou invalide, API incompatible, doublon | diagnostic sur stderr, module non chargé |
| Asset déclaré introuvable | module non exposé au Web, `asset-missing` sur l'accueil |

L'accueil affiche un bloc « Modules non chargés » (paquet, code, message
borné, jamais de trace) seulement s'il existe des diagnostics.

## Ce que le module déclare

Un paquet expose `FORGE_DESIGN_MODULE = ModuleDescriptor(...)` :
`SpecializedToolDefinition` (avec `UiEntry` pour apparaître dans le shell),
version, `api_version`, un `ResourceBinding(type, codec, scene)` par type,
`asset_package` et `assets`, et une sonde facultative. Il ne reçoit ni
Router, ni Request, ni racine de projet, ni chemin système. Un binding peut
ajouter `editor_script` (nom d'un asset `.js` déclaré) et `editor_config`
(document → JSON) : voir [Édition](#édition).

## Routes

Pour un module `<id>` exposé muni d'une `UiEntry`, et seulement celles-ci :

| Route | Contenu | Cache |
|---|---|---|
| `GET /modules/<id>/` | Libellé, version, API, capacités disponibles, dépendances indisponibles, ressources du projet courant par type | `no-store` |
| `GET /modules/<id>/resource?type=<type>&path=<chemin>` | Métadonnées (module, type, chemin, version du format, révision `sha256` et taille, validation), diagnostics, visualisation | `no-store` |
| `GET /modules/<id>/assets/<name>` | Un asset déclaré, avec le type MIME fixé par le cœur | politique des assets du cœur |
| `POST /modules/<id>/actions/<action>` | Action exposée (FD-EDIT-001) : 303 vers la page ressource, ou page d'erreur au statut de la [matrice](module-actions.md#statuts-http) | `no-store` |

Tout le reste (`/modules/<id>/foo`, une action non déclarée ou non exposée,
un asset non déclaré, un autre module, une traversée) répond 404. Un POST
sur une page GET répond 405, de même qu'un GET sur une route d'action.
L'ordre de la zone « Modules » est l'ordre d'activation.

Paramètres de `/resource` : exactement `type` et `path`, une valeur chacun,
plus `notice` facultatif (`saved` ou `unchanged`, retour d'action affiché en
`role="status"`). Si le type a une action exposée, la ligne « Révision »
porte le jeton public `data-revision-token`.

| Cas | Statut |
|---|---|
| Paramètre inconnu ou en double, type absent ou inconnu, chemin absent ou trop long | 400 |
| Chemin refusé par l'hôte (hors espace, suffixe, segment interdit, lien) | 400 |
| Aucun projet ouvert, racine devenue invalide | 409 |
| Ressource introuvable | 404 |
| Ressource invalide, version non prise en charge | 200, avec les diagnostics |

## Inventaire et lecture

- `list_specialized_resources` (cœur) parcourt l'espace de sources du type :
  - ouverture relative au parent, `O_NOFOLLOW` et `samestat` ;
  - liens, FIFO et entrées cachées ignorés ;
  - même politique lexicale que la lecture ;
  - tri lexical ;
  - bornes de 512 ressources, 4 096 entrées et 32 niveaux, avec indicateur
    `truncated`.

  Il ne lit aucun contenu. C'est un inventaire au mieux, pas un instantané
  atomique.
- `read_specialized_resource` (cœur) lit le fichier, puis le codec du module
  décode les octets.
- Une exception du codec ou de la projection n'interrompt pas la page :
  message borné `… du module en échec (Classe).`, trace sur la journalisation
  du serveur (logger `forge_design.modules`).

## Visualisation

Si le type a une projection et que la lecture réussit, la `GraphicScene`
produite :

- est contrôlée par l'hôte : objet, JSON strict sans `NaN`, au plus 8 Mio ;
- est copiée, puis transportée par `scene_json_payload` ;
- est validée et rendue dans le navigateur par le Graphic Core via
  `/module-resource.js`, un client générique sans vocabulaire de module.

Sélection, viewport, niveaux de détail et minicarte sont ceux du moteur.

Sans JavaScript, les métadonnées et diagnostics restent lisibles, avec le
message « La visualisation graphique nécessite JavaScript. ». Il n'y a pas de
rendu SVG côté serveur pour un module.

## Édition

FD-GRAPHICS-EDIT-001 (premier client : ForgeDesign-Circuit, FDC-EDIT-001).
Le cœur ne contient aucun éditeur métier ; il charge, de façon générique, le
script d'édition déclaré par le module, et seulement là où il sert.

| Condition (toutes requises) | Effet |
|---|---|
| Le type a une action **exposée** (capability gate), la lecture donne une révision, la projection une scène, et le binding déclare `editor_script` | La page ressource porte un bloc inerte `<script type="application/json" data-module-editor>` et une zone `data-editor-status` (`role="status"`) |
| Sinon (module en lecture seule, capacité indisponible, ressource illisible, projection en échec) | Page inchangée : aucun bloc, aucun script de module |

Contexte calculé par l'hôte, jamais par le module :

| Clé | Valeur |
|---|---|
| `script` | `/modules/<id>/assets/<editor_script>` |
| `type`, `path` | Type et chemin de la ressource affichée |
| `revision` | Jeton public de la révision lue (`data-revision-token`) |
| `actions` | `{ id: URL }` des seules actions exposées de ce type |
| `config` | Résultat de `editor_config(document)` : isolé (exception → message borné, trace journalisée), objet JSON strict sans `NaN`, au plus 1 Mio (`MAX_MODULE_EDITOR_CONFIG_BYTES`), copie détachée |

Le JSON est échappé comme la scène (`scene_json_payload`). Si la
configuration échoue, la scène reste affichée et la page annonce « Édition
indisponible : … ».

Côté navigateur, `/module-resource.js` (générique) lit ce contexte, vérifie
que chaque URL est un chemin absolu du même serveur, importe le script par
`import()` (CSP `script-src 'self'` inchangée) et appelle
`createResourceEditor(context)` avec un contexte gelé
(`resourceType`, `path`, `revision`, `actions`, `config`, `announce`). Le
résultat peut fournir l'option `nodeMove` du moteur et `attach(engine)`.
Script introuvable, export absent, exception, option refusée par le moteur ou
`attach` en échec : la vue est montée en consultation seule et l'indisponibilité
est annoncée. Le script du module envoie lui-même l'action (formulaire encodé,
URL et jeton du contexte) ; la page d'erreur du cœur marque son message
`data-action-error`.

## Limites V1

Pas de formulaire d'édition générique dans le cœur (aucun bouton Enregistrer,
Modifier, Créer ou Supprimer) : l'édition passe par le script déclaré du module
et les actions POST (FD-EDIT-001, [contrat](module-actions.md)). Un seul
script d'édition par type, chargé seulement sur la page ressource. Pas de
template fourni par le module, pas d'icône d'`UiEntry` affichée, pas de
découverte automatique ni d'installation.
