# Contrat des outils spécialisés

Contrat normatif de FD-SPECIALIZED-001 (Phase 9), mis en œuvre partiellement par
FD-SPECIALIZED-002 (voir « Implémentation minimale »). Il décrit ce dont Forge
Design a besoin pour héberger un futur outil spécialisé (Circuit, Network,
3D…) **sans connaître son domaine**. Aucun registre ni outil livré n'existe encore.

Il a été confronté à un cas réel, DrawCiel intégré à SéquenCiel (voir « Cas de
référence DrawCiel »). Trois marqueurs distinguent la nature des affirmations :

- **Observé** : constaté dans l'audit DC-016-00 ou dans la caractérisation
  DC-016-01 de SéquenCiel ;
- **Décision** : règle de Forge Design fixée par ce contrat ;
- **Reporté** : question laissée ouverte, à trancher par un ticket ultérieur.

## Objectif

Pouvoir décrire, pour n'importe quel outil spécialisé :

- son identité ;
- ses types de ressources éditables et leur format ;
- ses capacités ;
- sa validation et ses erreurs ;
- sa stratégie de sauvegarde ;
- ses exports ;
- ses dépendances optionnelles ;
- son runtime éventuel et sa frontière avec l'hôte.

Le contrat ne connaît ni l'électricité, ni SVG, ni Canvas, ni WebGL, ni la
pédagogie.

## Relation avec Tool

Le contrat existant `forge_design.platform.tool.Tool` (FD-PLATFORM-001) expose
`id`, `name`, `description` et `run(project_root) -> résultat`, de façon
synchrone, en lecture seule, orientée inspection. Il convient aux cinq Tools
actuels.

**Décision** :

- Le Protocol `Tool` est **inchangé**, et le registre des Tools reste à cinq.
- Un outil spécialisé éditable **n'est pas** une extension de `Tool`. Il
  n'existe pas de `class SpecializedTool(Tool)` : les deux notions ne
  partagent que le mot « outil ».

Un outil spécialisé ouvre une ressource, la modifie, la valide, la
sauvegarde, l'exporte et parfois la simule. Ces cycles ont des durées de vie
distinctes : ils ne tiennent pas dans un `run(project_root)` en lecture
seule. Un outil spécialisé pourra en revanche *fournir*, plus tard, un Tool
d'inspection (par exemple lister ses ressources d'un projet). Ce Tool
respecterait alors le contrat existant.

## Implémentation minimale — FD-SPECIALIZED-002

Le paquet `forge_design.specialized` implémente la partie de ce contrat qu'un
premier outil peut exercer sans runtime. Il est éprouvé par un outil témoin qui
n'existe que dans les tests : il n'est ni livré, ni enregistré, ni visible.

**Codé et testé** :

- les déclarations gelées, validées à la construction :
  `SpecializedToolDefinition`, `SpecializedResourceType`,
  `SpecializedCapability` (vocabulaire plateforme fermé en `Literal`,
  capacités d'outil en kebab-case et distinctes de la plateforme),
  `OptionalDependency`, `UiEntry`, `SpecializedIssue` et
  `SpecializedValidationResult` (borné par `MAX_SPECIALIZED_ISSUES`, avec
  indicateur `truncated`) ;
- `SpecializedResourceCodec` : détection de version, décodage, encodage et
  validation, sur des octets et une ressource en mémoire seulement ;
- `read_specialized_resource` : chemin confiné, taille bornée avant lecture,
  version détectée **avant** tout décodage (une version inconnue donne
  `unsupported-version` sans appel à `decode`), issues structurées, révision ;
- `write_specialized_resource` : encodage, borne, validation bloquante par
  niveau, contrôle de la version produite par le codec, révision attendue
  (création exclusive, conflit sinon), publication atomique, journalisation
  dans `history.jsonl` ;
- les catégories `resource-not-found`, `resource-refused`,
  `unsupported-version`, `invalid-resource`, `conflict` et
  `capability-unavailable`.

**Encore descriptif** (représentable, jamais exécuté) :
- `interactive-runtime` et le protocole runtime ↔ hôte ;
- l'autosave réel ;
- `export` et les formats d'export ;
- les dépendances optionnelles et leur sonde de disponibilité ;
- l'entrée UI ;
- les capacités propres à un outil ;
- les catégories `dependency-unavailable` et `runtime-error`.

**Précisions apportées par l'implémentation**, sans changer les décisions
ci-dessous :

1. Une issue porte aussi son **niveau de validation** (`level`). C'est
   nécessaire pour appliquer les niveaux bloquants. Un niveau non déclaré par
   le type est un défaut du codec (exception), pas un diagnostic.
2. Une validation **tronquée** bloque l'écriture : l'absence d'erreur
   bloquante ne peut pas être prouvée.
3. Le niveau `structure` est obligatoire et toujours bloquant. Un type non
   éditable ne peut déclarer ni `create`, ni `edit`, ni `save`. Les capacités
   d'un type sont incluses dans celles de son outil.
4. Une défaillance d'entrée/sortie de l'hôte (disque, `fsync`) n'est pas une
   catégorie de ressource : elle lève `SpecializedResourceError` avec
   `category = None`. Il faut alors relire la ressource avant de réessayer.
5. L'espace de sources doit exister : l'hôte ne crée aucun dossier. La
   création sécurisée d'arborescences relève d'un ticket ultérieur.
6. La détection de version peut lire le conteneur (par exemple parser JSON),
   mais jamais décoder le domaine.

## Définitions

| Terme | Sens |
|---|---|
| **SpecializedToolDefinition** | Déclaration descriptive d'un outil spécialisé : identité, types de ressources, capacités, dépendances optionnelles, entrée UI. Une définition, pas un objet exécutable. |
| **SpecializedResourceType** | Type de ressource éditable persistante : format, versions, espace de sources, état persistant/runtime, validation, capacités applicables. |
| **SpecializedResource** | Une ressource concrète : un fichier source du projet, identifié par son type et son chemin relatif. |
| **SpecializedCapability** | Ce qu'un outil sait faire, de façon atomique et déclarative ; jamais comment il le fait. |
| **Runtime spécialisé** | Code qui manipule interactivement une ressource (moteur graphique, solveur…), distinct de la ressource persistante. |
| **Hôte** | Forge Design : il possède le projet, les chemins, l'écriture, la révision, l'export et l'autorisation. |
| **Domaine** | Connaissances propres à l'outil (composants électriques, topologie réseau, géométrie…). Hors contrat. |

Quatre frontières sont distinguées et ne doivent jamais être fusionnées :
**ressource persistante**, **runtime spécialisé**, **intégration hôte**,
**domaine métier**.

Forme conceptuelle :

```text
SpecializedToolDefinition
├── id, name, description
├── resource_types : SpecializedResourceType…
├── capabilities   : SpecializedCapability…
├── optional_dependencies
└── ui_entry

SpecializedResourceType
├── id
├── format         : identifiant, suffixe, détection de version
├── versions       : lues {…}, écrite (une seule)
├── source_space   : espace de sources autorisé (zone C)
├── editable
├── persistent_state / runtime_only_state
├── validation     : niveaux, niveaux bloquants pour l'écriture
├── max_size
└── capabilities   : sous-ensemble applicable à ce type
```

Aucune méthode `open()`, `save()`, `render()` ou `simulate()` n'est imposée à
un Protocol unique. Les interfaces exécutables viendront **par capacité**
(lecteur, écrivain, validateur, éditeur interactif, exporteur, simulateur…),
quand un outil réel les exigera.

## Identité

- `id` : identifiant technique stable en kebab-case, même convention que les
  Tools. Exemples futurs : `circuit`, `network`, `three-d`.
- `name` : nom affiché ; `description` : responsabilité courte.
- L'identifiant d'un type de ressource est en kebab-case et unique dans son
  outil. Sa forme qualifiée est `<outil>/<type>` (par exemple
  `circuit/schematic`, à titre purement illustratif).

**Décision** : aucun outil spécialisé n'est enregistré dans le registre des
Tools. Il n'existe encore ni `SpecializedToolRegistry`, ni chargeur de
plugins, ni entry points, ni import dynamique. Un registre ne viendra qu'après
validation de ce contrat par un outil minimal (FD-SPECIALIZED-002).

## Ressource

Une ressource spécialisée est la **source éditable persistante** de l'outil.
Elle est distincte :

- du runtime ;
- du rendu exporté ;
- de tout cache ;
- de l'état d'interface (sélection, viewport courant…).

**Observé** : DrawCiel manipule une source native (`.drawciel`), une
définition d'exercice (`.drawcielt`), un résultat de tentative (`.drawcielr`),
des formats historiques (`.drawcielx`, `.edrawx`) et des rendus (PNG, SVG,
WebP). Le WebP inséré dans un texte est un rendu, pas une sauvegarde
éditable.

**Décision** : chaque `SpecializedResourceType` déclare :

| Élément | Exigence |
|---|---|
| Identifiant de type | kebab-case, unique dans l'outil. |
| Format | Identifiant et suffixe de fichier. Le contrat n'impose **pas** JSON : un format binaire ou textuel quelconque est admis s'il porte une version observable. |
| Éditable | `true` (créé, modifié, sauvegardé par Forge Design) ou `false` (lecture seule). |
| Espace de sources | Préfixe relatif à la racine du projet et suffixe autorisés (voir « Stockage »). |
| Taille maximale | Borne explicite, vérifiée avant lecture complète et avant écriture. |

**Identité d'une ressource** : `(type, chemin relatif, format_version
observée)`. Aucun UUID universel n'est imposé.

- *Avantages* : lisible, sans registre, cohérent avec Git et les autres
  sources.
- *Limites* : un déplacement ou un renommage change l'identité, et une
  référence externe par chemin casse. Un identifiant stable interne pourra
  être ajouté par un format qui en démontre le besoin, sans changer ce
  contrat.

Une ressource persistée ne contient jamais :
- de chemin absolu ;
- de nom d'utilisateur ou de machine ;
- de secret.

Les références qu'elle porte vers d'autres ressources sont des chemins
relatifs à la racine du projet.

## Versionnement

**Décision** :

1. Toute ressource spécialisée persistante porte une `format_version`
   observable. Le type déclare comment la lire (champ, en-tête, signature),
   sans dépendre d'un parse complet du domaine.
2. Le type déclare les **versions lues** (ensemble) et la **version écrite**
   (une seule).
3. Une version inconnue ou supérieure est **refusée explicitement** :
   `unsupported-version`, sans lecture partielle, migration silencieuse ni
   réécriture.
4. Une migration est une écriture comme une autre : diff, décision
   explicite, écriture contrôlée, conformément au contrat de stockage
   (§5 et §6).

**Observé** : DrawCiel produit `version: "0.15.0"` dans son état natif, mais
SéquenCiel filtre ce champ à la persistance. Aucune version d'enveloppe n'est
persistée ni dispatchée vers une migration. La définition TP conserve sa
propre `version`, distincte de celle du circuit. Ce contrat interdit ce cas
pour une ressource gérée par Forge Design.

## État persistant / runtime

**Décision** : chaque type de ressource déclare explicitement :
- son **état persistant** : ce que la ressource contient et ce qui survit à
  un aller-retour lecture/écriture ;
- son **état runtime-only** : ce qui n'est jamais écrit.

Par défaut, rien de ce qui suit n'est sauvegardé implicitement :
- sélection et viewport temporaire ;
- simulation active et résultats de calcul ;
- historique d'annulation ;
- références d'interface ;
- PID, sockets et threads.

L'état **éditorial** (positions, page, zoom souhaité, annotations) peut
légitimement appartenir à la ressource : c'est le format du type qui le
décide, explicitement.

Un aller-retour de l'état persistant doit être sans perte pour les champs
déclarés. Un champ connu qui serait filtré à l'écriture doit l'être
explicitement et être documenté par le type.

**Observé** : DrawCiel utilise les mêmes objets `component` pour le rendu,
les propriétés et le solveur. `component.state` reçoit tension, courant et
température de la simulation, et une capture pendant la simulation peut les
emporter. DC-016-01 confirme que cet état physique survit à la sauvegarde.
Le contrat interdit de supposer `état runtime == ressource persistante`.

## Capabilities

Une capacité indique ce que l'outil sait faire, **pas comment**. Les capacités
sont atomiques et déclarées par type de ressource. Il n'y a pas de profil
monolithique.

**Observé** : aucun registre de profils `electronics`, `melec`, `network`,
`embedded_iot`… n'existe dans DrawCiel. `profileFor()` y désigne le modèle
électrique d'un composant, pas un profil d'outil.

**Décision** : deux niveaux.

| Niveau | Capacités | La plateforme connaît |
|---|---|---|
| **Plateforme** (vocabulaire de Forge Design) | `create`, `open`, `edit`, `validate`, `save`, `export`, `interactive-runtime` | leur sémantique et les règles de ce contrat : écriture contrôlée, export publié par l'hôte, frontière runtime |
| **Outil** (vocabulaire propre) | par exemple `simulate`, `measure` | seulement leur identifiant, libellé, disponibilité et dépendances ; jamais leur appel |

- Le vocabulaire plateforme est **fermé**. L'élargir exige un ticket qui
  modifie ce contrat.
- Une capacité d'outil est en kebab-case et n'a de sens que dans son outil.
- Une capacité n'est jamais un domaine : `simulate` est une capacité,
  `electronics` est un domaine.
- Aucune méthode universelle `tool.simulate(...)`, `tool.export(...)` ou
  `tool.measure(...)` n'est définie.
- `preview` n'est pas retenu dans le vocabulaire plateforme. Il serait
  ambigu avec les previews de vues de la Phase 8. Il est **reporté** : un
  outil peut le déclarer comme capacité d'outil.

## Validation

**Observé** : DrawCiel connaît plusieurs niveaux de validité :
- contrat structurel serveur (bornes, types de conteneurs) ;
- préparation électrique (`readinessFor`, valeurs requises) ;
- simulabilité, puisque les modèles non pris en charge sont traités comme
  ouverts ;
- vérification pédagogique d'étapes TP (signature, mesure).

La signature de circuit est dupliquée en JavaScript et en Python, et ne
distingue pas deux composants de même type.

**Décision** :

- Aucun `validate() -> bool`. Un résultat de validation est une liste
  d'`issues`, chacune avec :
  - un `code` stable (catégorie plateforme ou code d'outil
    `<outil>.<code>`) ;
  - une `severity` (`error` ou `warning`) ;
  - un `message` affichable ;
  - une `location` éventuelle (relative à la ressource) ;

  plus un indicateur de troncature si les issues sont bornées.
- Le type déclare ses **niveaux de validation** (par exemple « structure »,
  puis des niveaux de domaine) et **lesquels bloquent l'écriture**.
  - Le niveau structurel (format lisible, version, bornes, types) bloque
    toujours.
  - Les niveaux de domaine ne bloquent que si le type le déclare.

  Un circuit incomplet ou non simulable peut ainsi être sauvegardé.
- Validité ≠ simulabilité ≠ validité pédagogique : ce sont des niveaux
  différents, et la pédagogie n'en fait pas partie (voir « Relation avec les
  applications métier »).
- **Validation du document ≠ autorisation.** Un résultat de validation
  n'accorde jamais un droit de lecture ou d'écriture.

## Erreurs

**Décision** : catégories communes de la plateforme, en nombre limité.

| Catégorie | Situation |
|---|---|
| `resource-not-found` | La ressource n'existe pas à ce chemin. |
| `resource-refused` | Chemin hors espace de sources, lien, type de fichier ou taille refusés. |
| `unsupported-version` | Version de format inconnue ou supérieure. |
| `invalid-resource` | Issues bloquantes de validation (le détail est dans les issues). |
| `conflict` | La ressource a changé depuis la révision lue. |
| `capability-unavailable` | Capacité non déclarée pour ce type, ou désactivée. |
| `dependency-unavailable` | Capacité déclarée mais dépendance optionnelle absente. |
| `runtime-error` | Échec du runtime spécialisé (chargement, plantage, protocole). |

Les erreurs de domaine restent des **issues** de l'outil, jamais de nouvelles
catégories plateforme. Exemples : circuit flottant, valeur de résistance
absente, conflit d'alimentation.

## Révision et sauvegarde

**Décision** : même discipline que `DesignRevision` et SAFEWRITE, sans
obligation de réutiliser leurs classes.

```text
lecture bornée → révision → édition (mémoire ou runtime) → validation
→ diff → décision explicite → revalidation → écriture atomique avec révision attendue
→ journalisation (history.jsonl)
```

- **Révision observable** : taille, `mtime_ns`, empreinte du contenu et, si
  disponibles, périphérique et inode.
- **Conflit** : si la ressource a changé extérieurement, `conflict`. On
  n'écrase **jamais** silencieusement.
- **Écriture** : uniquement par l'hôte, avec les primitives de lecture et
  d'écriture confinées existantes (pas de lien, fichier ordinaire, écriture
  atomique). Aucune écriture n'est déclenchée par un GET, une preview ou une
  inspection.
- **Diff** : textuel quand le format s'y prête. Sinon, le type fournit un
  résumé de changements pour la décision. Il n'y a jamais d'écriture sans
  décision ou session explicite.
- **Source de vérité** : pour une ressource de projet Forge Design, le
  fichier du projet.

**Observé** : SéquenCiel tient la base SQL pour source de vérité de DrawCiel.
L'écriture y passe par une transaction et `SELECT … FOR UPDATE` avec
contrôle de `Revision`, et un conflit répond 409 avec demande de recharge.
Le principe (révision attendue, pas d'écrasement) est le même. La source
(fichier contre SQL) diffère et ne doit pas être confondue.

## Autosave

**Observé** : l'adaptateur DrawCiel annonce `dirty`, puis sauvegarde après
450 ms sans changement. `tp.js` a sa propre autosauvegarde. Les sauvegardes
sont sérialisées, la révision est mise à jour à l'acquittement, et
`beforeunload` avertit d'un travail en attente.

**Décision** :

- Le contrat **n'impose pas** la sauvegarde manuelle seule.
- L'ouverture explicite d'une **session d'édition** par l'utilisateur est
  une action explicite suffisante. Elle peut autoriser l'autosave pendant
  cette session, sans confirmation à chaque modification.
- Chaque écriture d'autosave respecte malgré tout :
  - la révision attendue ;
  - la validation bloquante ;
  - les bornes de taille ;
  - l'écriture contrôlée ;
  - la journalisation.
- Un `conflict` **suspend** l'autosave jusqu'à une décision explicite de
  l'utilisateur (recharger, ou écraser après diff) ; aucune fusion
  automatique.
- La fréquence est bornée (temporisation et sérialisation), et les écritures
  ne se chevauchent pas.
- Fermer la session arrête toute écriture ultérieure.
- L'autosave n'est jamais actif hors d'une session ouverte explicitement
  (inspection, preview, ouverture en lecture).

## Runtime spécialisé

**Observé** : DrawCiel est une application JavaScript autonome. Son état est
global (`components`, `wires`, historique, moteur). Sa scène est
principalement SVG, avec un canvas pour les exports raster, la mini-carte et
l'oscilloscope. Elle est embarquée dans une iframe sandbox (`allow-scripts
allow-downloads allow-modals`, sans `allow-same-origin`).

**Décision** :

- Un outil peut nécessiter un runtime interactif (navigateur ou autre). Il
  le déclare par la capacité `interactive-runtime`.
- Le contrat n'impose **aucune** technologie : ni iframe, ni DOM direct,
  ni SVG, ni Canvas, ni WebGL. Le choix et son isolation sont propres à
  l'outil et à son ticket.
- Le runtime **n'a aucun accès arbitraire au système de fichiers** et
  n'écrit jamais lui-même dans le projet. Il reçoit un contenu et rend un
  contenu ou une demande ; l'hôte valide, contrôle la révision et écrit.

```text
runtime → save-request(contenu) → hôte → validation + révision → écriture → acquittement / conflit
runtime → export-request(données) → hôte → destination, protections, publication
```

## Intégration hôte

**Observé** : deux adaptateurs entourent DrawCiel.
- `drawciel-cadre.js`, dans l'iframe, connaît l'API et le DOM du moteur.
- `drawciel-hote.js`, dans la page parente, connaît les routes, le CSRF et
  les révisions.

Ils échangent par `postMessage` : `hello`/`ready`, `load`, `loaded`, `dirty`,
`save`, `export`/`capture`, `verify`, statuts et erreurs. Les modes
`professeur`, `élève`, `consultation` et `correction` ne sont **pas** des
preuves d'autorisation : le serveur reste l'autorité.

**Décision** : le contrat fixe les **responsabilités logiques** de l'échange,
pas un protocole filaire. Le transport (`postMessage`, appel direct,
WebSocket…) n'est pas standardisé ici.

| Événement logique | Sens | Responsabilité |
|---|---|---|
| `ready` | runtime → hôte | Le runtime peut recevoir une ressource. |
| `load` | hôte → runtime | Contenu, type, version et droits d'édition **décidés par l'hôte**. |
| `dirty` | runtime → hôte | État modifié non sauvegardé. |
| `save-request` | runtime → hôte | Demande d'écriture d'un contenu ; l'hôte décide. |
| `export-request` | runtime → hôte | Données exportables ; l'hôte décide destination et publication. |
| `error` | runtime → hôte | Erreur runtime, mappée en `runtime-error` avec détail borné. |

- L'hôte ne déduit jamais une identité ou un droit du contenu d'un message.
- Un mode d'interface (lecture, édition) **n'est pas** une autorisation :
  l'hôte refuse toute `save-request` hors session d'édition.
- Les messages sont bornés et validés côté hôte.

## Exports

**Décision** :

- Source ≠ export : un export (PNG, SVG, WebP, PDF…) est un **rendu**. Il ne
  remplace jamais la source, n'en est jamais une sauvegarde, et n'est pas
  réimporté comme source sans action explicite.
- Un type déclare ses formats d'export par identifiant et type MIME. Le
  contrat ignore comment ils sont produits.
- Forge Design décide **où** et **comment** un export est publié : fichier
  sous contrôle d'écriture, téléchargement, ou référence depuis une vue plus
  tard. Il applique ses protections (chemin, taille, type).
- Aucune API définitive `export() -> bytes` n'est fixée.

**Observé** : l'insertion WebP DrawCiel passe par une sauvegarde préalable de
la source, une rasterisation bornée et un dépôt dans les médias. Le titre de
l'image (`DrawCiel #<id>`) permet de retrouver la source. Le lien entre source
et rendu est un point de fragilité identifié par l'audit.

## Dépendances optionnelles

**Décision** : une dépendance optionnelle se déclare par :

| Champ | Sens |
|---|---|
| `id` | Identifiant kebab-case. |
| `purpose` | Rôle affichable. |
| `required_for` | Capacités qui en dépendent. |
| `availability` | Disponible ou indisponible (avec raison), déterminée par une sonde de l'outil sans effet de bord. |

- Une dépendance absente ne rend indisponibles **que** les capacités qui en
  dépendent. Par exemple : édition disponible, simulation indisponible.
- Le diagnostic est explicite : « Simulation indisponible : dépendance X
  absente. » (`dependency-unavailable`).
- Il n'y a **aucune installation automatique** : ni paquet système, ni
  `pip`, ni `npm`, ni téléchargement de moteur.
- Ce contrat ne choisit **aucun** moteur, en particulier pour Circuit
  (ni ngspice, ni PySpice, ni autre). Ce choix relève d'une étude dédiée.

**Observé** : la simulation DrawCiel 0.15 est un solveur JavaScript intégré
(analyse nodale modifiée), pas une dépendance externe. Les travaux
microcontrôleurs ultérieurs de SéquenCiel illustrent toutefois la notion :
- DC-016-02 : le banc de compilation AVR échoue explicitement si le SDK ou
  l'isolation sont indisponibles, sans téléchargement automatique ;
- DC-016-03 : avr8js est retenu « avec capacités limitées ».

## UI

**Décision** : une entrée UI identifiable se décrit par :
- le nom ;
- une icône éventuelle (référence opaque, aucun format ni bibliothèque
  imposés) ;
- une entrée (route, à définir par le ticket d'intégration) ;
- les types de ressources gérés ;
- les capacités avec leur disponibilité.

- La navigation de Forge Design n'est **pas** modifiée par ce contrat.
- Un outil spécialisé peut fournir sa propre surface d'édition. Il ne passe
  pas par l'éditeur `.design.json`.
- **Circuit n'est pas un bloc du Template Designer** : c'est un outil qui
  produit une ressource, référençable ailleurs plus tard.

## Sécurité

**Décision** :

- **Chemins** : relatifs, confinés à l'espace de sources du type, avec la
  politique lexicale commune (`unsafe_relative_path` : pas de segment caché,
  d'`env`, de clé, d'antislash, de deux-points ni de NUL). Pas de lien,
  fichier ordinaire seulement, taille bornée avant lecture.
- **Lecture et écriture** : confinées par l'hôte. Le runtime n'accède jamais
  au système de fichiers.
- **Autorisation** : Forge Design standalone est local et mono-utilisateur
  (origine locale exacte sur les mutations). Un outil spécialisé ne décide
  jamais seul qui peut lire ou écrire, et surtout pas à partir d'un mode
  d'interface.
- **Données** : aucun secret, chemin absolu, nom d'utilisateur ou de
  machine dans une ressource. Les messages runtime ↔ hôte sont bornés et ne
  portent aucun droit.

## Stockage

**Décision** (contrat de stockage, §4) :

- Une ressource spécialisée qui appartient fonctionnellement à
  l'application est une **source du projet** : elle vit en **zone C**,
  partagée par Git avec les sources.
- La zone B (`.forge-design/`) n'accueille pas de ressource spécialisée.
  Elle reste réservée aux métadonnées de Forge Design (`history.jsonl`).
- L'état d'interface propre à une personne (dernier viewport, préférences)
  va en zone A.
- Chaque type déclare son **espace de sources** (préfixe relatif et
  suffixe). Le ticket qui introduit un type l'ajoute au tableau de la
  zone C du contrat de stockage.
- **Aucun espace n'est réservé par ce contrat** : ni `mvc/circuit/`, ni
  `resources/circuit/`, ni `.forge-design/circuit/`.

## Relation avec DesignFile

**Décision** : `DesignFile` (`*.design.json`) et une ressource spécialisée
sont des notions distinctes. Ce contrat ne modifie ni `DesignFile` ni
`ViewContract`, et n'ajoute aucun champ « specialized ». Une vue pourra plus
tard *référencer* une ressource spécialisée, ou l'un de ses exports, par un
ticket dédié.

## Relation avec les applications métier

**Décision** :

- Le contrat générique **n'est pas un contrat pédagogique**. Professeur,
  élève, sujet, tentative, corrigé, notation, progression et verrous restent
  hors contrat.
- Une application comme SéquenCiel pourra associer une ressource Forge
  Design à son propre contrat pédagogique, sans modifier le moteur
  spécialisé. La manière dont SéquenCiel référencera une ressource relève de
  la **Phase 12** (intégration applicative).
- Sinon, Circuit deviendrait inutilisable hors SéquenCiel.

**Observé** : dans DrawCiel, le TP traverse le moteur (`tp.js`, restrictions
de composants et d'instruments), les adaptateurs (`verify`, `submit`) et le
serveur (sujet filtré, instantané de définition, statuts SQL `brouillon`,
`rendu`, `valide`). Les statuts natifs du client ne valent pas validation
professorale.

## Cas de référence DrawCiel

DrawCiel est un **cas d'étude**, pas une implémentation de ce contrat.

```text
DrawCiel
├── ressource éditable     circuit natif (components, wires, texts, page, customDefs, terminalOverrides)
├── runtime interactif     app.js + model.js + simulation.js (+ scène SVG)
├── domaine électronique   catalogue, propriétés, bornes, réseaux, mesures
├── simulation optionnelle solveur MNA intégré, capacité d'outil
├── validation             structure (serveur) + préparation électrique + TP
├── export                 PNG / SVG / WebP
└── intégration hôte       drawciel-cadre.js ↔ drawciel-hote.js, routes HTTP
```

| Concept du contrat | DrawCiel actuel (observé) |
|---|---|
| Ressource | Document circuit (état natif à six champs persistés), définition TP, tentative |
| Format et version | `.drawciel`, `.drawcielt` (`version: "1.0"`), `.drawcielr` ; version native filtrée à la persistance |
| Runtime | `app.js` + `model.js` + `simulation.js`, scène SVG, canvas pour exports et instruments |
| Intégration hôte | `drawciel-cadre.js` + `drawciel-hote.js`, `postMessage`, 13 routes `/drawciel` |
| Persistance | SQL SéquenCiel (`drawciel_projet`, `drawciel_copie`, colonnes LONGTEXT, `Revision`) |
| Révision et conflit | Transaction, `FOR UPDATE`, 409 en conflit |
| Autosave | `dirty` puis 450 ms, file sérialisée, avertissement `beforeunload` |
| Export | WebP inséré via les médias ; PNG/SVG natifs |
| Validation | Structure (contrat serveur) + électrique (`readinessFor`) + TP (signature, mesure) |
| Capacité simulation | Oui (solveur intégré) |
| Capacité mesure | Oui (multimètre, oscilloscope) |
| Pédagogie | Externe au contrat générique (TP, statuts, notation) |

Écarts de DrawCiel par rapport à ce contrat (observés, non corrigés ; aucune
migration n'est demandée) :

| Écart | Exigence du contrat |
|---|---|
| Document non versionné de façon uniforme : version native filtrée, version TP distincte | `format_version` observable, versions lues et écrite déclarées |
| Runtime et document partagent `component.state` (état physique sérialisable) | État persistant et runtime-only déclarés et séparés |
| Validation dupliquée en JS et Python (signature), contrat serveur superficiel | Validation structurée, une autorité côté hôte |
| Intégration hôte couplée au DOM et aux sélecteurs du moteur | Responsabilités logiques indépendantes du DOM |
| Persistance SQL propre à SéquenCiel | Fichier de projet, source de vérité en zone C |
| TP traversant moteur, adaptateurs et serveur | Pédagogie hors contrat, associée par l'application |
| Notifications `drawciel:change` / `drawciel:state` divergentes (annulation non sauvegardée, à confirmer) | `dirty` unique et fiable pour toute modification persistante |

## Ce que le contrat ne définit pas

- Le chemin et le format des ressources Circuit, Network ou 3D.
- Un moteur de simulation, une API graphique ou un protocole filaire
  runtime ↔ hôte.
- Un registre d'outils spécialisés, un chargement de plugins, des entry
  points.
- Des interfaces exécutables par capacité.
- La référence d'une ressource depuis une vue ou un `DesignFile`.
- L'intégration dans une application métier (Phase 12) et toute notion
  pédagogique.
- L'isolation technique d'un runtime (iframe sandbox, Worker, processus).
  Elle sera choisie par outil, comme la preview réelle l'a fait pour le
  runner.

## Questions reportées

| Question | Ticket attendu |
|---|---|
| Chemin exact et format des ressources Circuit | Phase 10 |
| Moteur de simulation de Circuit | Étude dédiée de la Phase 10 |
| API graphique (SVG, Canvas, WebGL) d'un outil | Ticket de l'outil |
| Protocole filaire runtime ↔ hôte | Premier outil à runtime interactif |
| Formats d'export et leur publication | Premier outil exportant |
| Capacité `preview` dans le vocabulaire plateforme | Quand un outil en aura besoin |
| Identifiant stable interne de ressource (au-delà du chemin) | Format qui le justifie |
| Registre d'outils spécialisés | **Tranché par FD-MODULES-001** : pas de registre de découverte ; activation explicite de modules externes ([architecture](../modules/module-architecture.md)) |
| 3D ; Network (sans phase dédiée à ce jour) | Phase 11 pour la 3D ; Network à planifier |
